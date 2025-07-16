"""
SIEM Adapter 구현체들
실제 SIEM 시스템과의 통신을 담당
"""
import asyncio
import json
import logging
import os
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

from .port import ISiemPort

logger = logging.getLogger(__name__)


class SiemHttpAdapter(ISiemPort):
 """HTTP 기반 SIEM 어댑터 (Splunk, ELK 등)"""

 def __init__(self, endpoint: str, token: str, timeout: int = 30):
 self.endpoint = endpoint
 self.token = token
 self.timeout = timeout
 self._session: Optional[aiohttp.ClientSession] = None

 async def _get_session(self) -> aiohttp.ClientSession:
 """HTTP 세션 관리"""
 if self._session is None or self._session.closed:
 self._session = aiohttp.ClientSession(
 headers={"Authorization": f"Bearer {self.token}"},
 timeout = aiohttp.ClientTimeout(total = self.timeout),
 )
 return self._session

 async def send(self, event_type: str, payload: Dict[str, Any]) -> None:
 """단일 이벤트 전송"""
 try:
 session = await self._get_session()

 # SIEM 형식으로 래핑
 siem_event = {
 "timestamp": datetime.utcnow().isoformat(),
 "event_type": event_type,
 "source": "oms_validation",
 "data": payload,
 }

 async with session.post(
 f"{self.endpoint}/events", json = siem_event
 ) as response:
 if response.status not in (200, 201, 202):
 logger.error(f"SIEM send failed: {response.status}")
 raise Exception(f"SIEM send failed with status {response.status}")

 except Exception as e:
 logger.error(f"Failed to send event to SIEM: {e}")
 raise

 async def send_batch(self, events: List[Dict[str, Any]]) -> None:
 """배치 이벤트 전송"""
 try:
 session = await self._get_session()

 # SIEM 배치 형식으로 래핑
 batch_payload = {
 "timestamp": datetime.utcnow().isoformat(),
 "source": "oms_validation",
 "events": events,
 }

 async with session.post(
 f"{self.endpoint}/batch", json = batch_payload
 ) as response:
 if response.status not in (200, 201, 202):
 logger.error(f"SIEM batch send failed: {response.status}")
 raise Exception(
 f"SIEM batch send failed with status {response.status}"
 )

 except Exception as e:
 logger.error(f"Failed to send batch to SIEM: {e}")
 raise

 async def query(self, query_params: Dict[str, Any]) -> List[Dict[str, Any]]:
 """SIEM 이벤트 조회"""
 try:
 session = await self._get_session()

 async with session.get(
 f"{self.endpoint}/search", params = query_params
 ) as response:
 if response.status == 200:
 return await response.json()
 else:
 logger.error(f"SIEM query failed: {response.status}")
 return []

 except Exception as e:
 logger.error(f"Failed to query SIEM: {e}")
 return []

 async def health_check(self) -> bool:
 """SIEM 연결 상태 확인"""
 try:
 session = await self._get_session()
 async with session.get(f"{self.endpoint}/health") as response:
 return response.status == 200
 except:
 return False

 async def close(self):
 """리소스 정리"""
 if self._session and not self._session.closed:
 await self._session.close()


class MockSiemAdapter(ISiemPort):
 """테스트용 Mock SIEM 어댑터"""

 def __init__(self):
 self.events: List[Dict[str, Any]] = []
 self.is_healthy = True
 self.send_count = 0
 self.batch_count = 0

 async def send(self, event_type: str, payload: Dict[str, Any]) -> None:
 """Mock 이벤트 저장"""
 self.send_count += 1
 self.events.append(
 {
 "timestamp": datetime.utcnow().isoformat(),
 "event_type": event_type,
 "data": payload,
 }
 )
 logger.debug(f"Mock SIEM: Received {event_type} event")

 async def send_batch(self, events: List[Dict[str, Any]]) -> None:
 """Mock 배치 이벤트 저장"""
 self.batch_count += 1
 self.events.extend(events)
 logger.debug(f"Mock SIEM: Received batch of {len(events)} events")

 async def query(self, query_params: Dict[str, Any]) -> List[Dict[str, Any]]:
 """Mock 이벤트 조회"""
 # 간단한 필터링 로직
 results = []
 for event in self.events:
 if "event_type" in query_params:
 if event.get("event_type") == query_params["event_type"]:
 results.append(event)
 else:
 results.append(event)
 return results

 async def health_check(self) -> bool:
 """Mock 헬스 체크"""
 return self.is_healthy

 def clear(self):
 """테스트용 - 저장된 이벤트 클리어"""
 self.events.clear()
 self.send_count = 0
 self.batch_count = 0


class KafkaSiemAdapter(ISiemPort):
 """Kafka 기반 SIEM 어댑터 (대용량 스트리밍용)"""

 def __init__(self, bootstrap_servers: str, topic: str):
 self.bootstrap_servers = bootstrap_servers
 self.topic = topic
 # 실제 구현시 aiokafka 사용
 logger.info(f"Kafka SIEM adapter initialized: {bootstrap_servers}/{topic}")

 async def send(self, event_type: str, payload: Dict[str, Any]) -> None:
 """Kafka로 이벤트 전송"""
 # 실제 구현 예시:
 # producer = AIOKafkaProducer(bootstrap_servers = self.bootstrap_servers)
 # await producer.start()
 # await producer.send(self.topic, value = json.dumps(payload).encode())
 # await producer.stop()
 logger.debug(f"Would send to Kafka: {event_type}")

 async def send_batch(self, events: List[Dict[str, Any]]) -> None:
 """Kafka로 배치 전송"""
 logger.debug(f"Would send batch to Kafka: {len(events)} events")

 async def query(self, query_params: Dict[str, Any]) -> List[Dict[str, Any]]:
 """Kafka는 조회 미지원 - 빈 리스트 반환"""
 logger.warning(
 "Kafka adapter does not support querying. Use a consumer to read events."
 )
 # Kafka is write-only for producers. For reading, use Kafka consumers.
 # Return empty list to maintain interface compatibility
 return []

 async def health_check(self) -> bool:
 """Kafka 연결 확인"""
 # 실제 구현시 Kafka 연결 테스트
 return True


class BufferedSiemAdapter(ISiemPort):
 """버퍼링을 지원하는 SIEM 어댑터 래퍼"""

 def __init__(
 self,
 base_adapter: ISiemPort,
 buffer_size: int = 100,
 flush_interval: float = 5.0,
 ):
 self.base_adapter = base_adapter
 self.buffer_size = buffer_size
 self.flush_interval = flush_interval
 self.buffer: deque = deque(maxlen = buffer_size)
 self._flush_task: Optional[asyncio.Task] = None
 self._start_flush_task()

 def _start_flush_task(self):
 """주기적 플러시 태스크 시작"""
 if self._flush_task is None or self._flush_task.done():
 self._flush_task = asyncio.create_task(self._periodic_flush())

 async def _periodic_flush(self):
 """주기적으로 버퍼 플러시"""
 while True:
 await asyncio.sleep(self.flush_interval)
 if self.buffer:
 await self._flush_buffer()

 async def _flush_buffer(self):
 """버퍼 내용을 배치로 전송"""
 if not self.buffer:
 return

 events = list(self.buffer)
 self.buffer.clear()

 try:
 await self.base_adapter.send_batch(events)
 logger.debug(f"Flushed {len(events)} events to SIEM")
 except Exception as e:
 logger.error(f"Failed to flush buffer: {e}")
 # 실패시 버퍼에 다시 추가 (선택적)
 self.buffer.extend(events)

 async def send(self, event_type: str, payload: Dict[str, Any]) -> None:
 """버퍼에 이벤트 추가"""
 event = {
 "type": event_type,
 "payload": payload,
 "timestamp": datetime.utcnow().isoformat(),
 }

 self.buffer.append(event)

 # 버퍼가 가득 차면 즉시 플러시
 if len(self.buffer) >= self.buffer_size:
 await self._flush_buffer()

 async def send_batch(self, events: List[Dict[str, Any]]) -> None:
 """배치는 직접 전송"""
 await self.base_adapter.send_batch(events)

 async def query(self, query_params: Dict[str, Any]) -> List[Dict[str, Any]]:
 """조회는 base adapter로 위임"""
 return await self.base_adapter.query(query_params)

 async def health_check(self) -> bool:
 """헬스체크는 base adapter로 위임"""
 return await self.base_adapter.health_check()

 async def close(self):
 """리소스 정리"""
 # 남은 버퍼 플러시
 if self.buffer:
 await self._flush_buffer()

 # 플러시 태스크 취소
 if self._flush_task and not self._flush_task.done():
 self._flush_task.cancel()

 # Base adapter 정리
 if hasattr(self.base_adapter, "close"):
 await self.base_adapter.close()


class SIEMAdapter:
 """
 Jaeger 통합을 위한 SIEM 어댑터 래퍼
 기존 ISiemPort 구현체들을 jaeger_adapter.py에서 기대하는 인터페이스로 통합
 """

 def __init__(self):
 self._adapter: Optional[ISiemPort] = None
 self._initialized = False

 async def initialize(self):
 """SIEM 어댑터 초기화"""
 if self._initialized:
 return

 try:
 # 환경에 따라 적절한 어댑터 선택
 siem_type = os.getenv("SIEM_ADAPTER_TYPE", "http")

 if siem_type == "http":
 # HTTP 기반 SIEM (Splunk, ELK 등)
 endpoint = os.getenv("SIEM_ENDPOINT", "http://siem-service:8080")
 token = os.getenv("SIEM_TOKEN")
 if not token:
 logger.warning(
 "🚨 SECURITY WARNING: SIEM_TOKEN not set. Using placeholder value. "
 "Set SIEM_TOKEN environment variable for production."
 )
 # Use a clearly non-secret placeholder to avoid false secret detection
 token = "PLACEHOLDER_NOT_A_SECRET_TOKEN"
 timeout = int(os.getenv("SIEM_TIMEOUT", "30"))

 base_adapter = SiemHttpAdapter(endpoint, token, timeout)

 # 버퍼링 사용 여부 확인
 if os.getenv("SIEM_BUFFERING_ENABLED", "true").lower() == "true":
 buffer_size = int(os.getenv("SIEM_BUFFER_SIZE", "100"))
 flush_interval = float(os.getenv("SIEM_FLUSH_INTERVAL", "5.0"))
 self._adapter = BufferedSiemAdapter(
 base_adapter, buffer_size, flush_interval
 )
 else:
 self._adapter = base_adapter

 elif siem_type == "kafka":
 # Kafka 기반 SIEM
 bootstrap_servers = os.getenv(
 "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
 )
 topic = os.getenv("SIEM_KAFKA_TOPIC", "siem-events")
 self._adapter = KafkaSiemAdapter(bootstrap_servers, topic)

 elif siem_type == "mock":
 # 테스트용 Mock
 self._adapter = MockSiemAdapter()

 else:
 logger.warning(f"Unknown SIEM adapter type: {siem_type}, using mock")
 self._adapter = MockSiemAdapter()

 # 어댑터 헬스 체크
 if await self._adapter.health_check():
 logger.info(f"SIEM adapter initialized: {siem_type}")
 self._initialized = True
 else:
 logger.warning("SIEM adapter health check failed, using mock fallback")
 self._adapter = MockSiemAdapter()
 self._initialized = True

 except Exception as e:
 logger.error(f"Failed to initialize SIEM adapter: {e}")
 # 페일오버: Mock 어댑터 사용
 self._adapter = MockSiemAdapter()
 self._initialized = True

 async def log_event(self, event_data: Dict[str, Any]) -> None:
 """
 Jaeger 이벤트를 SIEM으로 전송
 jaeger_adapter.py에서 기대하는 인터페이스
 """
 if not self._initialized or not self._adapter:
 logger.warning("SIEM adapter not initialized, skipping event")
 return

 try:
 # event_data에서 event_type 추출
 event_type = event_data.get("event_type", "unknown")

 # event_type을 제거한 나머지를 payload로 사용
 payload = {k: v for k, v in event_data.items() if k != "event_type"}

 # ISiemPort.send() 인터페이스 사용
 await self._adapter.send(event_type, payload)

 except Exception as e:
 logger.error(f"Failed to log event to SIEM: {e}")
 # 크리티컬 이벤트는 로컬 로그에라도 남김
 logger.critical(f"SIEM_EVENT_LOST: {event_data}")

 async def query_events(self, query_params: Dict[str, Any]) -> List[Dict[str, Any]]:
 """SIEM에서 이벤트 조회 (선택적 기능)"""
 if not self._initialized or not self._adapter:
 return []

 try:
 return await self._adapter.query(query_params)
 except Exception as e:
 logger.error(f"Failed to query SIEM: {e}")
 return []

 async def health_check(self) -> bool:
 """SIEM 연결 상태 확인"""
 if not self._initialized or not self._adapter:
 return False

 try:
 return await self._adapter.health_check()
 except Exception as e:
 logger.error(f"SIEM health check failed: {e}")
 return False

 async def shutdown(self):
 """SIEM 어댑터 종료 및 리소스 정리"""
 if self._adapter and hasattr(self._adapter, "close"):
 try:
 await self._adapter.close()
 logger.info("SIEM adapter shutdown complete")
 except Exception as e:
 logger.error(f"Error during SIEM adapter shutdown: {e}")

 self._initialized = False
 self._adapter = None
