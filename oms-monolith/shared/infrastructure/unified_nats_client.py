"""
Unified NATS Client - Single Connection Pool
모든 NATS 연결을 통합하여 커넥션 폭주 방지 및 운영 일관성 확보
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import uuid

import nats
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext
from nats.js.api import StreamConfig, ConsumerConfig

from shared.utils.logger import get_logger
from shared.monitoring.unified_metrics import get_metrics_collector

logger = get_logger(__name__)


class MessageDelivery(str, Enum):
    """메시지 전달 보장"""
    AT_MOST_ONCE = "at_most_once"      # 최대 1회 (Fire-and-forget)
    AT_LEAST_ONCE = "at_least_once"    # 최소 1회 (JetStream)
    EXACTLY_ONCE = "exactly_once"      # 정확히 1회 (Deduplication)


class StreamType(str, Enum):
    """스트림 타입"""
    MEMORY = "memory"       # 메모리 기반 (빠름, 휘발성)
    FILE = "file"          # 파일 기반 (지속성)
    REPLICATED = "replicated"  # 복제 (고가용성)


@dataclass
class NATSConfig:
    """NATS 설정"""
    servers: List[str] = field(default_factory=lambda: None)
    name: str = "OMS-NATS-Client"
    user: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    
    def __post_init__(self):
        if self.servers is None:
            from shared.config.environment import get_config
            config = get_config()
            nats_url = config.get_nats_url()
            self.servers = [nats_url]
    
    # 연결 설정
    max_reconnect_attempts: int = 60
    reconnect_time_wait: int = 2
    connect_timeout: int = 2
    request_timeout: int = 5
    
    # JetStream 설정
    enable_jetstream: bool = True
    jetstream_prefix: str = "oms"
    
    # TLS 설정
    tls_required: bool = False
    tls_cert: Optional[str] = None
    tls_key: Optional[str] = None
    tls_ca: Optional[str] = None
    
    # 성능 튜닝
    max_pending_size: int = 64 * 1024 * 1024  # 64MB
    max_pending_msgs: int = 65536
    flush_timeout: int = 1


@dataclass
class StreamDefinition:
    """스트림 정의"""
    name: str
    subjects: List[str]
    description: str = ""
    stream_type: StreamType = StreamType.FILE
    max_msgs: int = 1000000
    max_bytes: int = 1024 * 1024 * 1024  # 1GB
    max_age: int = 86400 * 7  # 7일 (초)
    replicas: int = 1
    duplicate_window: int = 300  # 5분 (초)


class UnifiedNATSClient:
    """
    통합 NATS 클라이언트
    
    모든 NATS 통신의 단일 진입점으로 커넥션 풀링과 
    일관된 Subject 네이밍 규칙 제공
    """
    
    def __init__(self, config: NATSConfig):
        self.config = config
        self.metrics = get_metrics_collector()
        
        # 연결 인스턴스
        self._nc: Optional[NATS] = None
        self._js: Optional[JetStreamContext] = None
        
        # 상태 관리
        self._connected = False
        self._connecting = False
        self._connection_lock = asyncio.Lock()
        
        # 스트림 관리
        self._streams: Dict[str, StreamDefinition] = {}
        self._consumers: Dict[str, str] = {}  # consumer_name -> stream_name
        
        # 메시지 핸들러
        self._subscription_handlers: Dict[str, Callable] = {}
        
        # 표준 스트림 정의
        self._register_standard_streams()
    
    def _register_standard_streams(self):
        """표준 스트림 정의 등록"""
        
        # 감사 이벤트 스트림
        self.register_stream(StreamDefinition(
            name="audit_events",
            subjects=["audit.>", "security.>"],
            description="Security and audit events",
            stream_type=StreamType.REPLICATED,
            max_age=86400 * 30,  # 30일 보관
            replicas=3
        ))
        
        # 시스템 이벤트 스트림
        self.register_stream(StreamDefinition(
            name="system_events",
            subjects=["system.>", "health.>", "metrics.>"],
            description="System and health events",
            stream_type=StreamType.FILE,
            max_age=86400 * 7  # 7일 보관
        ))
        
        # 비즈니스 이벤트 스트림
        self.register_stream(StreamDefinition(
            name="business_events",
            subjects=["ontology.>", "schema.>", "validation.>"],
            description="Business domain events",
            stream_type=StreamType.REPLICATED,
            max_age=86400 * 90,  # 90일 보관
            replicas=2
        ))
        
        # 알림 스트림
        self.register_stream(StreamDefinition(
            name="notifications",
            subjects=["notify.>", "alert.>"],
            description="Notifications and alerts",
            stream_type=StreamType.MEMORY,
            max_age=86400 * 1,  # 1일 보관
            max_msgs=100000
        ))
    
    def register_stream(self, stream_def: StreamDefinition):
        """스트림 정의 등록"""
        self._streams[stream_def.name] = stream_def
        logger.info(f"Registered stream definition: {stream_def.name}")
    
    async def connect(self) -> bool:
        """NATS 서버 연결"""
        
        async with self._connection_lock:
            if self._connected:
                return True
            
            if self._connecting:
                # 다른 연결 시도 대기
                while self._connecting:
                    await asyncio.sleep(0.1)
                return self._connected
            
            self._connecting = True
            
            try:
                logger.info(f"Connecting to NATS servers: {self.config.servers}")
                
                # 연결 옵션 구성
                options = {
                    "servers": self.config.servers,
                    "name": self.config.name,
                    "max_reconnect_attempts": self.config.max_reconnect_attempts,
                    "reconnect_time_wait": self.config.reconnect_time_wait,
                    "connect_timeout": self.config.connect_timeout,
                    "max_pending_size": self.config.max_pending_size,
                    "flush_timeout": self.config.flush_timeout
                }
                
                # 인증 설정
                if self.config.user and self.config.password:
                    options["user"] = self.config.user
                    options["password"] = self.config.password
                elif self.config.token:
                    options["token"] = self.config.token
                
                # TLS 설정
                if self.config.tls_required:
                    tls_config = {}
                    if self.config.tls_cert:
                        tls_config["cert"] = self.config.tls_cert
                    if self.config.tls_key:
                        tls_config["key"] = self.config.tls_key
                    if self.config.tls_ca:
                        tls_config["ca"] = self.config.tls_ca
                    options["tls"] = tls_config
                
                # 이벤트 핸들러 설정
                options["error_cb"] = self._error_handler
                options["disconnected_cb"] = self._disconnected_handler
                options["reconnected_cb"] = self._reconnected_handler
                options["closed_cb"] = self._closed_handler
                
                # 연결 수행
                self._nc = await nats.connect(**options)
                
                # JetStream 초기화
                if self.config.enable_jetstream:
                    self._js = self._nc.jetstream()
                    await self._setup_streams()
                
                self._connected = True
                logger.info("NATS connection established successfully")
                
                # 메트릭 기록
                self.metrics.record_event_published("nats_connection", "unified_client", "success")
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to connect to NATS: {e}")
                self.metrics.record_event_published("nats_connection", "unified_client", "failure")
                return False
                
            finally:
                self._connecting = False
    
    async def disconnect(self):
        """NATS 연결 해제"""
        
        if self._nc and self._connected:
            try:
                await self._nc.close()
                logger.info("NATS connection closed")
            except Exception as e:
                logger.error(f"Error closing NATS connection: {e}")
            finally:
                self._connected = False
                self._nc = None
                self._js = None
    
    async def publish(
        self,
        subject: str,
        data: Union[str, bytes, Dict[str, Any]],
        headers: Optional[Dict[str, str]] = None,
        delivery: MessageDelivery = MessageDelivery.AT_MOST_ONCE,
        timeout: Optional[float] = None
    ) -> bool:
        """메시지 발행"""
        
        if not await self._ensure_connected():
            return False
        
        try:
            # 데이터 직렬화
            if isinstance(data, dict):
                payload = json.dumps(data).encode('utf-8')
            elif isinstance(data, str):
                payload = data.encode('utf-8')
            else:
                payload = data
            
            # 표준 헤더 추가
            message_headers = {
                "message_id": str(uuid.uuid4()),
                "timestamp": str(int(time.time() * 1000)),
                "source": "oms_unified_client"
            }
            if headers:
                message_headers.update(headers)
            
            # 전달 보장에 따른 발행
            if delivery == MessageDelivery.AT_MOST_ONCE:
                await self._nc.publish(subject, payload, headers=message_headers)
            
            elif delivery in [MessageDelivery.AT_LEAST_ONCE, MessageDelivery.EXACTLY_ONCE]:
                if not self._js:
                    raise RuntimeError("JetStream not available for guaranteed delivery")
                
                publish_options = {}
                if timeout:
                    publish_options["timeout"] = timeout
                
                if delivery == MessageDelivery.EXACTLY_ONCE:
                    # 메시지 ID 기반 중복 제거
                    publish_options["msg_id"] = message_headers["message_id"]
                
                await self._js.publish(subject, payload, headers=message_headers, **publish_options)
            
            # 성공 메트릭
            self.metrics.record_event_published(
                event_type=subject.split('.')[0],
                publisher="unified_client",
                result="success"
            )
            
            logger.debug(f"Published message to {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish to {subject}: {e}")
            self.metrics.record_event_published(
                event_type=subject.split('.')[0],
                publisher="unified_client", 
                result="failure"
            )
            return False
    
    async def subscribe(
        self,
        subject: str,
        handler: Callable,
        queue_group: Optional[str] = None,
        stream_name: Optional[str] = None,
        durable_name: Optional[str] = None
    ) -> Optional[str]:
        """메시지 구독"""
        
        if not await self._ensure_connected():
            return None
        
        try:
            subscription_id = str(uuid.uuid4())
            
            if stream_name and self._js:
                # JetStream 구독 (지속적)
                consumer_config = ConsumerConfig(
                    durable_name=durable_name or f"consumer_{subscription_id}",
                    deliver_policy="all"
                )
                
                consumer_info = await self._js.add_consumer(stream_name, consumer_config)
                subscription = await self._js.subscribe(
                    subject,
                    stream=stream_name,
                    durable=consumer_config.durable_name
                )
                
                # 메시지 처리 태스크 시작
                asyncio.create_task(self._handle_jetstream_messages(subscription, handler))
                
            else:
                # 일반 구독
                subscription = await self._nc.subscribe(
                    subject,
                    queue=queue_group,
                    cb=lambda msg: asyncio.create_task(self._handle_core_message(msg, handler))
                )
            
            self._subscription_handlers[subscription_id] = handler
            logger.info(f"Subscribed to {subject} with ID: {subscription_id}")
            
            return subscription_id
            
        except Exception as e:
            logger.error(f"Failed to subscribe to {subject}: {e}")
            return None
    
    async def request(
        self,
        subject: str,
        data: Union[str, bytes, Dict[str, Any]],
        timeout: float = 5.0
    ) -> Optional[Dict[str, Any]]:
        """요청-응답 패턴"""
        
        if not await self._ensure_connected():
            return None
        
        try:
            # 데이터 직렬화
            if isinstance(data, dict):
                payload = json.dumps(data).encode('utf-8')
            elif isinstance(data, str):
                payload = data.encode('utf-8')
            else:
                payload = data
            
            # 요청 전송
            response = await self._nc.request(subject, payload, timeout=timeout)
            
            # 응답 역직렬화
            try:
                return json.loads(response.data.decode('utf-8'))
            except json.JSONDecodeError:
                return {"data": response.data.decode('utf-8')}
                
        except Exception as e:
            logger.error(f"Request to {subject} failed: {e}")
            return None
    
    async def _setup_streams(self):
        """스트림 설정"""
        
        for stream_name, stream_def in self._streams.items():
            try:
                # 스트림 구성
                storage_type = "file" if stream_def.stream_type == StreamType.FILE else "memory"
                if stream_def.stream_type == StreamType.REPLICATED:
                    storage_type = "file"
                
                config = StreamConfig(
                    name=f"{self.config.jetstream_prefix}_{stream_name}",
                    subjects=stream_def.subjects,
                    description=stream_def.description,
                    storage=storage_type,
                    max_msgs=stream_def.max_msgs,
                    max_bytes=stream_def.max_bytes,
                    max_age=stream_def.max_age,
                    num_replicas=stream_def.replicas,
                    duplicate_window=stream_def.duplicate_window
                )
                
                # 스트림 생성 또는 업데이트
                try:
                    await self._js.stream_info(config.name)
                    # 스트림이 존재하면 업데이트
                    await self._js.update_stream(config)
                    logger.info(f"Updated stream: {config.name}")
                except:
                    # 스트림이 없으면 생성
                    await self._js.add_stream(config)
                    logger.info(f"Created stream: {config.name}")
                
            except Exception as e:
                logger.error(f"Failed to setup stream {stream_name}: {e}")
    
    async def _handle_core_message(self, msg, handler):
        """Core NATS 메시지 처리"""
        try:
            # 메시지 데이터 역직렬화
            try:
                data = json.loads(msg.data.decode('utf-8'))
            except json.JSONDecodeError:
                data = {"raw_data": msg.data.decode('utf-8')}
            
            # 헤더 처리
            headers = dict(msg.headers) if msg.headers else {}
            
            # 핸들러 호출
            await handler(msg.subject, data, headers)
            
        except Exception as e:
            logger.error(f"Error handling message from {msg.subject}: {e}")
    
    async def _handle_jetstream_messages(self, subscription, handler):
        """JetStream 메시지 처리"""
        async for msg in subscription.messages:
            try:
                # 메시지 데이터 역직렬화
                try:
                    data = json.loads(msg.data.decode('utf-8'))
                except json.JSONDecodeError:
                    data = {"raw_data": msg.data.decode('utf-8')}
                
                # 헤더 처리
                headers = dict(msg.headers) if msg.headers else {}
                
                # 핸들러 호출
                await handler(msg.subject, data, headers)
                
                # 메시지 확인
                await msg.ack()
                
            except Exception as e:
                logger.error(f"Error handling JetStream message from {msg.subject}: {e}")
                # 메시지 NACK (재처리)
                await msg.nak()
    
    async def _ensure_connected(self) -> bool:
        """연결 상태 확인 및 재연결"""
        if self._connected:
            return True
        
        return await self.connect()
    
    # 이벤트 핸들러들
    async def _error_handler(self, error):
        """연결 오류 처리"""
        logger.error(f"NATS error: {error}")
        self.metrics.record_event_published("nats_error", "unified_client", "error")
    
    async def _disconnected_handler(self):
        """연결 해제 처리"""
        logger.warning("NATS disconnected")
        self._connected = False
    
    async def _reconnected_handler(self):
        """재연결 처리"""
        logger.info("NATS reconnected")
        self._connected = True
        self.metrics.record_event_published("nats_reconnection", "unified_client", "success")
    
    async def _closed_handler(self):
        """연결 종료 처리"""
        logger.info("NATS connection closed")
        self._connected = False
    
    def get_connection_status(self) -> Dict[str, Any]:
        """연결 상태 반환"""
        return {
            "connected": self._connected,
            "server_info": self._nc.server_info if self._nc else None,
            "jetstream_enabled": self._js is not None,
            "streams": list(self._streams.keys()),
            "active_subscriptions": len(self._subscription_handlers)
        }


# 글로벌 인스턴스
_unified_nats_client: Optional[UnifiedNATSClient] = None


def get_unified_nats_client(config: Optional[NATSConfig] = None) -> UnifiedNATSClient:
    """통합 NATS 클라이언트 반환"""
    global _unified_nats_client
    if _unified_nats_client is None:
        if config is None:
            config = NATSConfig()  # 기본 설정 사용
        _unified_nats_client = UnifiedNATSClient(config)
    return _unified_nats_client


# 편의 함수들
async def publish_event(
    subject: str,
    data: Union[str, Dict[str, Any]],
    delivery: MessageDelivery = MessageDelivery.AT_LEAST_ONCE
) -> bool:
    """이벤트 발행 편의 함수"""
    client = get_unified_nats_client()
    return await client.publish(subject, data, delivery=delivery)


async def subscribe_to_events(
    subject: str,
    handler: Callable,
    stream_name: Optional[str] = None
) -> Optional[str]:
    """이벤트 구독 편의 함수"""
    client = get_unified_nats_client()
    return await client.subscribe(subject, handler, stream_name=stream_name)