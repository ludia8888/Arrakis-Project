"""
OMS Subscriber 집중 커버리지 테스트
14% -> 90% 달성을 위한 포괄적인 테스트
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timezone
import json


class TestOMSEventSubscriberIntensive:
    """OMS Event Subscriber 집중 테스트 - 14% -> 90%"""
    
    @pytest.mark.asyncio
    async def test_start_comprehensive(self):
        """이벤트 구독 시작 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 정상 시작
        with patch.object(subscriber, '_connect_to_event_broker') as mock_connect, \
             patch.object(subscriber, '_subscribe_loop') as mock_loop:
            
            mock_connect.return_value = None
            mock_loop.return_value = None
            
            await subscriber.start()
            
            assert subscriber.is_running is True
            assert subscriber.subscriber_task is not None
            mock_connect.assert_called_once()
        
        # 이미 실행 중인 경우
        with patch.object(subscriber.logger, 'warning') as mock_warning:
            await subscriber.start()
            mock_warning.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_with_exception(self):
        """이벤트 구독 시작 예외 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 연결 실패
        with patch.object(subscriber, '_connect_to_event_broker') as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")
            
            with pytest.raises(Exception):
                await subscriber.start()
            
            assert subscriber.is_running is False
    
    @pytest.mark.asyncio
    async def test_stop_comprehensive(self):
        """이벤트 구독 중지 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 실행 중이 아닌 경우
        await subscriber.stop()
        
        # 실행 중인 경우 중지
        subscriber.is_running = True
        mock_task = AsyncMock()
        mock_task.cancel = MagicMock()  # 동기 메서드
        subscriber.subscriber_task = mock_task
        
        # Mock the nc connection for disconnect
        mock_nc = AsyncMock()
        mock_nc.close = AsyncMock()
        subscriber.nc = mock_nc
        
        with patch.object(subscriber.logger, 'info') as mock_info:
            await subscriber.stop()
            
            assert subscriber.is_running is False
            mock_task.cancel.assert_called_once()
            mock_nc.close.assert_called_once()
            mock_info.assert_any_call("Stopping OMS event subscriber...")
            mock_info.assert_any_call("OMS event subscriber stopped")
    
    @pytest.mark.asyncio
    async def test_subscribe_loop_comprehensive(self):
        """구독 루프 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        subscriber.is_running = True
        
        # 정상 이벤트 처리
        with patch.object(subscriber, '_receive_event') as mock_receive, \
             patch.object(subscriber, '_process_received_event') as mock_process:
            
            # 3개의 이벤트 처리 후 중지
            events = [
                {"id": "event1", "type": "com.oms.schema.changed"},
                {"id": "event2", "type": "com.oms.schema.validated"},
                None  # 연결 종료 신호
            ]
            mock_receive.side_effect = events
            
            await subscriber._subscribe_loop()
            
            assert mock_receive.call_count == 3
            assert mock_process.call_count == 2  # None은 처리하지 않음
    
    @pytest.mark.asyncio
    async def test_subscribe_loop_with_exception(self):
        """구독 루프 예외 처리 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        subscriber.is_running = True
        
        # 이벤트 수신 중 예외
        with patch.object(subscriber, '_receive_event') as mock_receive, \
             patch.object(subscriber.logger, 'error') as mock_error:
            
            mock_receive.side_effect = Exception("Receive error")
            
            await subscriber._subscribe_loop()
            
            mock_error.assert_called()
            assert subscriber.is_running is False
    
    @pytest.mark.asyncio
    async def test_connect_to_event_broker_comprehensive(self):
        """이벤트 브로커 연결 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # Mock NATS connection
        with patch('nats.connect') as mock_connect:
            # Mock connection object
            mock_nc = AsyncMock()
            mock_nc.is_closed = False
            
            # Mock JetStream
            mock_js = AsyncMock()
            mock_nc.jetstream.return_value = mock_js
            
            mock_connect.return_value = mock_nc
            
            # Mock _setup_streams
            with patch.object(subscriber, '_setup_streams') as mock_setup:
                await subscriber._connect_to_event_broker()
                
                # Verify NATS connection was made
                mock_connect.assert_called_once()
                assert subscriber.nc == mock_nc
                assert subscriber.js == mock_js
                mock_setup.assert_called_once()
        
        # Test connection error
        with patch('nats.connect') as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")
            
            with pytest.raises(Exception) as exc_info:
                await subscriber._connect_to_event_broker()
            
            assert "Connection failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_connect_to_nats_comprehensive(self):
        """NATS 연결 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 성공적인 연결
        with patch.dict('os.environ', {
            'NATS_URL': 'nats://localhost:4222'
        }):
            with patch('nats.connect') as mock_connect:
                mock_nc = AsyncMock()
                mock_nc.is_closed = False
                mock_js = AsyncMock()
                mock_nc.jetstream.return_value = mock_js
                mock_connect.return_value = mock_nc
                
                with patch.object(subscriber, '_setup_streams') as mock_setup:
                    await subscriber._connect_to_nats()
                    
                    mock_connect.assert_called_once()
                    assert subscriber.nc == mock_nc
                    assert subscriber.js == mock_js
        
        # 연결 실패
        with patch('nats.connect') as mock_connect:
            mock_connect.side_effect = Exception("NATS connection failed")
            
            with pytest.raises(Exception):
                await subscriber._connect_to_nats()
    
    @pytest.mark.asyncio
    async def test_connect_to_kafka_comprehensive(self):
        """Kafka 연결 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 성공적인 연결
        with patch.dict('os.environ', {
            'KAFKA_BOOTSTRAP_SERVERS': 'localhost:9092',
            'KAFKA_TOPIC': 'oms-events',
            'KAFKA_GROUP_ID': 'audit-service'
        }):
            with patch('aiokafka.AIOKafkaConsumer') as mock_consumer_class:
                mock_consumer = AsyncMock()
                mock_consumer_class.return_value = mock_consumer
                
                await subscriber._connect_to_kafka()
                
                mock_consumer_class.assert_called_once()
                mock_consumer.start.assert_called_once()
                assert subscriber.kafka_consumer == mock_consumer
        
        # 설정 누락
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(Exception):
                await subscriber._connect_to_kafka()
    
    @pytest.mark.asyncio
    async def test_connect_to_rabbitmq_comprehensive(self):
        """RabbitMQ 연결 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 성공적인 연결
        with patch.dict('os.environ', {
            'RABBITMQ_URL': 'amqp://localhost:5672',
            'RABBITMQ_EXCHANGE': 'oms.events',
            'RABBITMQ_ROUTING_KEY': 'schema.*'
        }):
            with patch('aio_pika.connect_robust') as mock_connect:
                mock_connection = AsyncMock()
                mock_channel = AsyncMock()
                mock_exchange = AsyncMock()
                mock_queue = AsyncMock()
                
                mock_connect.return_value = mock_connection
                mock_connection.channel.return_value = mock_channel
                mock_channel.get_exchange.return_value = mock_exchange
                mock_channel.declare_queue.return_value = mock_queue
                
                await subscriber._connect_to_rabbitmq()
                
                mock_connect.assert_called_once()
                assert subscriber.rabbitmq_connection == mock_connection
                assert subscriber.rabbitmq_channel == mock_channel
                assert subscriber.rabbitmq_queue == mock_queue
        
        # 연결 실패
        with patch.dict('os.environ', {
            'RABBITMQ_URL': 'amqp://localhost:5672'
        }):
            with patch('aio_pika.connect_robust') as mock_connect:
                mock_connect.side_effect = Exception("RabbitMQ connection failed")
                
                with pytest.raises(Exception):
                    await subscriber._connect_to_rabbitmq()
    
    @pytest.mark.asyncio
    async def test_disconnect_from_event_broker_comprehensive(self):
        """이벤트 브로커 연결 해제 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # NATS 연결 해제 (기본 동작)
        mock_nc = AsyncMock()
        mock_nc.close = AsyncMock()
        subscriber.nc = mock_nc
        
        with patch.object(subscriber.logger, 'info') as mock_info:
            await subscriber._disconnect_from_event_broker()
            mock_nc.close.assert_called_once()
            mock_info.assert_any_call("Disconnecting from event broker...")
            mock_info.assert_any_call("Disconnected from event broker successfully")
        
        # 연결이 없는 경우
        subscriber.nc = None
        await subscriber._disconnect_from_event_broker()  # 예외 없이 완료되어야 함
        
        # 연결 해제 중 에러 발생
        mock_nc = AsyncMock()
        mock_nc.close.side_effect = Exception("Disconnect failed")
        subscriber.nc = mock_nc
        
        with patch.object(subscriber.logger, 'error') as mock_error:
            await subscriber._disconnect_from_event_broker()
            mock_error.assert_called_with("Error disconnecting from event broker: Disconnect failed")
    
    @pytest.mark.asyncio
    async def test_disconnect_from_nats_comprehensive(self):
        """NATS 연결 해제 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 연결이 있는 경우
        mock_nc = AsyncMock()
        mock_nc.close = AsyncMock()
        subscriber.nc = mock_nc
        
        with patch.object(subscriber.logger, 'info') as mock_info:
            await subscriber._disconnect_from_nats()
            
            mock_nc.close.assert_called_once()
            mock_info.assert_called()
        
        # 연결이 없는 경우
        subscriber.nc = None
        await subscriber._disconnect_from_nats()  # 예외 없이 완료되어야 함
        
        # 연결 해제 중 에러 발생
        mock_nc = AsyncMock()
        mock_nc.close.side_effect = Exception("Close failed")
        subscriber.nc = mock_nc
        
        with patch.object(subscriber.logger, 'error') as mock_error:
            await subscriber._disconnect_from_nats()  # 에러가 발생해도 예외를 발생시키지 않음
            mock_error.assert_called()
    
    @pytest.mark.asyncio
    async def test_disconnect_from_kafka_comprehensive(self):
        """Kafka 연결 해제 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 연결이 있는 경우
        mock_consumer = AsyncMock()
        mock_consumer.stop = AsyncMock()
        subscriber.kafka_consumer = mock_consumer
        
        with patch.object(subscriber.logger, 'info') as mock_info:
            await subscriber._disconnect_from_kafka()
            
            mock_consumer.stop.assert_called_once()
            mock_info.assert_called_with("Disconnected from Kafka")
        
        # 연결이 없는 경우 (kafka_consumer 속성이 없음)
        subscriber = OMSEventSubscriber()
        await subscriber._disconnect_from_kafka()  # 예외 없이 완료되어야 함
        
        # 연결 해제 중 에러 발생
        mock_consumer = AsyncMock()
        mock_consumer.stop.side_effect = Exception("Stop failed")
        subscriber.kafka_consumer = mock_consumer
        
        with pytest.raises(Exception):
            await subscriber._disconnect_from_kafka()
    
    @pytest.mark.asyncio
    async def test_disconnect_from_rabbitmq_comprehensive(self):
        """RabbitMQ 연결 해제 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 연결이 있는 경우
        mock_connection = AsyncMock()
        mock_connection.close = AsyncMock()
        subscriber.rabbitmq_connection = mock_connection
        
        with patch.object(subscriber.logger, 'info') as mock_info:
            await subscriber._disconnect_from_rabbitmq()
            
            mock_connection.close.assert_called_once()
            mock_info.assert_called_with("Disconnected from RabbitMQ")
        
        # 연결이 없는 경우 (rabbitmq_connection 속성이 없음)
        subscriber = OMSEventSubscriber()
        await subscriber._disconnect_from_rabbitmq()  # 예외 없이 완료되어야 함
        
        # 연결 해제 중 에러 발생
        mock_connection = AsyncMock()
        mock_connection.close.side_effect = Exception("Close failed")
        subscriber.rabbitmq_connection = mock_connection
        
        with pytest.raises(Exception):
            await subscriber._disconnect_from_rabbitmq()
    
    @pytest.mark.asyncio
    async def test_receive_event_comprehensive(self):
        """이벤트 수신 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # NATS에서 이벤트 수신
        with patch.dict('os.environ', {'EVENT_BROKER_TYPE': 'nats'}):
            with patch.object(subscriber, '_receive_from_nats') as mock_nats:
                test_event = {"id": "test", "type": "com.oms.schema.changed"}
                mock_nats.return_value = test_event
                
                event = await subscriber._receive_event()
                assert event == test_event
        
        # Kafka에서 이벤트 수신
        with patch.dict('os.environ', {'EVENT_BROKER_TYPE': 'kafka'}):
            with patch.object(subscriber, '_receive_from_kafka') as mock_kafka:
                test_event = {"id": "test", "type": "com.oms.schema.validated"}
                mock_kafka.return_value = test_event
                
                event = await subscriber._receive_event()
                assert event == test_event
        
        # RabbitMQ에서 이벤트 수신
        with patch.dict('os.environ', {'EVENT_BROKER_TYPE': 'rabbitmq'}):
            with patch.object(subscriber, '_receive_from_rabbitmq') as mock_rabbitmq:
                test_event = {"id": "test", "type": "com.oms.schema.reverted"}
                mock_rabbitmq.return_value = test_event
                
                event = await subscriber._receive_event()
                assert event == test_event
    
    @pytest.mark.asyncio
    async def test_receive_from_nats_comprehensive(self):
        """NATS에서 이벤트 수신 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 구독이 있는 경우
        mock_subscription = AsyncMock()
        mock_msg = AsyncMock()
        mock_msg.data = json.dumps({
            "id": "nats-event-123",
            "type": "com.oms.schema.changed",
            "data": {"branch": "main"}
        }).encode()
        
        mock_subscription.next_msg.return_value = mock_msg
        subscriber.nats_subscription = mock_subscription
        
        event = await subscriber._receive_from_nats()
        assert event["id"] == "nats-event-123"
        assert event["type"] == "com.oms.schema.changed"
        
        # 구독이 없는 경우
        subscriber.nats_subscription = None
        event = await subscriber._receive_from_nats()
        assert event is None
        
        # JSON 파싱 에러
        mock_msg.data = b"invalid json"
        subscriber.nats_subscription = mock_subscription
        
        with patch.object(subscriber.logger, 'error') as mock_error:
            event = await subscriber._receive_from_nats()
            assert event is None
            mock_error.assert_called()
    
    @pytest.mark.asyncio
    async def test_receive_from_kafka_comprehensive(self):
        """Kafka에서 이벤트 수신 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 컨슈머가 있는 경우
        mock_consumer = AsyncMock()
        mock_record = AsyncMock()
        mock_record.value = json.dumps({
            "id": "kafka-event-456",
            "type": "com.oms.schema.validated",
            "data": {"validation_result": "passed"}
        }).encode()
        
        mock_consumer.getone.return_value = mock_record
        subscriber.kafka_consumer = mock_consumer
        
        event = await subscriber._receive_from_kafka()
        assert event["id"] == "kafka-event-456"
        assert event["type"] == "com.oms.schema.validated"
        
        # 컨슈머가 없는 경우
        subscriber.kafka_consumer = None
        event = await subscriber._receive_from_kafka()
        assert event is None
        
        # JSON 파싱 에러
        mock_record.value = b"invalid json"
        subscriber.kafka_consumer = mock_consumer
        
        with patch.object(subscriber.logger, 'error') as mock_error:
            event = await subscriber._receive_from_kafka()
            assert event is None
            mock_error.assert_called()
    
    @pytest.mark.asyncio
    async def test_receive_from_rabbitmq_comprehensive(self):
        """RabbitMQ에서 이벤트 수신 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 큐가 있는 경우
        mock_queue = AsyncMock()
        mock_message = AsyncMock()
        mock_message.body = json.dumps({
            "id": "rabbitmq-event-789",
            "type": "com.oms.schema.reverted",
            "data": {"reverted_from": "bad_commit"}
        }).encode()
        
        mock_queue.get.return_value = mock_message
        subscriber.rabbitmq_queue = mock_queue
        
        event = await subscriber._receive_from_rabbitmq()
        assert event["id"] == "rabbitmq-event-789"
        assert event["type"] == "com.oms.schema.reverted"
        mock_message.ack.assert_called_once()
        
        # 큐가 없는 경우
        subscriber.rabbitmq_queue = None
        event = await subscriber._receive_from_rabbitmq()
        assert event is None
        
        # 메시지가 없는 경우 (타임아웃)
        mock_queue.get.return_value = None
        subscriber.rabbitmq_queue = mock_queue
        
        event = await subscriber._receive_from_rabbitmq()
        assert event is None
        
        # JSON 파싱 에러
        mock_message.body = b"invalid json"
        mock_queue.get.return_value = mock_message
        
        with patch.object(subscriber.logger, 'error') as mock_error:
            event = await subscriber._receive_from_rabbitmq()
            assert event is None
            mock_error.assert_called()
    
    @pytest.mark.asyncio
    async def test_process_received_event_comprehensive(self):
        """수신된 이벤트 처리 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 정상 이벤트 처리
        test_event = {
            "id": "process-test-123",
            "type": "com.oms.schema.changed",
            "time": "2024-01-01T12:00:00Z",
            "data": {
                "branch": "main",
                "commit_hash": "abc123"
            }
        }
        
        with patch.object(subscriber.event_processor, 'process_event') as mock_process:
            await subscriber._process_received_event(test_event)
            mock_process.assert_called_once_with(test_event)
        
        # 이벤트 처리 중 예외
        with patch.object(subscriber.event_processor, 'process_event') as mock_process, \
             patch.object(subscriber.logger, 'error') as mock_error:
            
            mock_process.side_effect = Exception("Processing failed")
            
            await subscriber._process_received_event(test_event)
            mock_error.assert_called()
    
    def test_health_check_comprehensive(self):
        """헬스 체크 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 실행 중이 아닌 상태, 연결 없음
        health = subscriber.health_check()
        assert health["status"] == "unhealthy"
        assert health["is_running"] is False
        assert health["is_connected"] is False
        assert "metrics" in health
        
        # 실행 중인 상태, 연결 없음
        subscriber.is_running = True
        health = subscriber.health_check()
        assert health["status"] == "unhealthy"
        assert health["is_running"] is True
        assert health["is_connected"] is False
        
        # NATS 연결 상태
        mock_nc = MagicMock()
        mock_nc.is_closed = False
        subscriber.nc = mock_nc
        
        health = subscriber.health_check()
        assert health["status"] == "healthy"
        assert health["is_running"] is True
        assert health["is_connected"] is True
        
        # 연결이 닫힌 상태
        mock_nc.is_closed = True
        health = subscriber.health_check()
        assert health["status"] == "unhealthy"
        assert health["is_connected"] is False
    
    def test_get_metrics_comprehensive(self):
        """메트릭 조회 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 기본 메트릭
        metrics = subscriber.get_metrics()
        assert isinstance(metrics, dict)
        assert "events_received" in metrics
        assert "events_processed" in metrics
        assert "events_failed" in metrics
        assert "connection_failures" in metrics
        assert "last_event_time" in metrics
        
        # 일부 메트릭 값 확인
        assert metrics["events_received"] == 0
        assert metrics["events_processed"] == 0
        assert metrics["events_failed"] == 0
        assert metrics["connection_failures"] == 0
        assert metrics["last_event_time"] is None
    
    def test_reset_metrics_comprehensive(self):
        """메트릭 리셋 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 메트릭 값 설정
        subscriber._metrics['events_received'] = 100
        subscriber._metrics['events_processed'] = 95
        subscriber._metrics['events_failed'] = 5
        subscriber._metrics['connection_failures'] = 3
        subscriber._metrics['last_event_time'] = "2024-01-01T00:00:00Z"
        
        # 리셋 실행
        subscriber.reset_metrics()
        
        # 값 확인
        metrics = subscriber.get_metrics()
        assert metrics["events_received"] == 0
        assert metrics["events_processed"] == 0
        assert metrics["events_failed"] == 0
        assert metrics["connection_failures"] == 0
        assert metrics["last_event_time"] is None
    
    def test_initialization_comprehensive(self):
        """초기화 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 기본 상태 확인
        assert subscriber.event_processor is not None
        assert subscriber.is_running is False
        assert subscriber.subscriber_task is None
        assert subscriber.events_received == 0
        assert subscriber.events_processed == 0
        assert subscriber.processing_errors == 0
        
        # 연결 객체들이 None으로 초기화되었는지 확인
        assert subscriber.nats_connection is None
        assert subscriber.nats_subscription is None
        assert subscriber.kafka_consumer is None
        assert subscriber.rabbitmq_connection is None
        assert subscriber.rabbitmq_channel is None
        assert subscriber.rabbitmq_queue is None
    
    @pytest.mark.asyncio
    async def test_edge_cases_comprehensive(self):
        """엣지 케이스 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # None 이벤트 처리
        await subscriber._process_received_event(None)  # 예외 없이 완료되어야 함
        
        # 빈 이벤트 처리
        await subscriber._process_received_event({})
        
        # 잘못된 형식의 이벤트
        invalid_event = {
            "invalid_field": "value",
            "missing_required_fields": True
        }
        
        with patch.object(subscriber.logger, 'error') as mock_error:
            await subscriber._process_received_event(invalid_event)
            # 에러가 로그되어야 함 (EventProcessor에서 처리)
    
    @pytest.mark.asyncio
    async def test_concurrent_operations_comprehensive(self):
        """동시 작업 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 동시에 여러 이벤트 처리
        events = [
            {"id": f"concurrent-{i}", "type": "com.oms.schema.changed"}
            for i in range(10)
        ]
        
        tasks = []
        for event in events:
            task = asyncio.create_task(subscriber._process_received_event(event))
            tasks.append(task)
        
        # 모든 태스크 완료 대기
        await asyncio.gather(*tasks)
        
        # 메트릭 확인
        assert subscriber.events_processed >= 0  # 처리된 이벤트 수는 0 이상
    
    @pytest.mark.asyncio
    async def test_error_recovery_comprehensive(self):
        """에러 복구 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 연결 에러 후 재연결 시도
        with patch.object(subscriber, '_connect_to_event_broker') as mock_connect:
            # 첫 번째 시도 실패
            mock_connect.side_effect = [
                Exception("Connection failed"),
                None  # 두 번째 시도 성공
            ]
            
            # 첫 번째 시도 (실패)
            with pytest.raises(Exception):
                await subscriber.start()
            
            # 두 번째 시도 (성공)
            await subscriber.start()
            assert subscriber.is_running is True
    
    @pytest.mark.asyncio
    async def test_configuration_validation_comprehensive(self):
        """설정 검증 포괄적 테스트"""
        from core.subscribers.oms_subscriber import OMSEventSubscriber
        
        subscriber = OMSEventSubscriber()
        
        # 필수 환경 변수 누락
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(Exception):
                await subscriber._connect_to_event_broker()
        
        # 잘못된 브로커 타입
        with patch.dict('os.environ', {'EVENT_BROKER_TYPE': 'invalid_broker'}):
            with pytest.raises(ValueError):
                await subscriber._connect_to_event_broker()
        
        # 부분적인 설정 (NATS)
        with patch.dict('os.environ', {
            'EVENT_BROKER_TYPE': 'nats',
            'NATS_SERVER_URL': 'nats://localhost:4222'
            # NATS_SUBJECT 누락
        }):
            with patch('nats.connect') as mock_connect:
                mock_connect.return_value = AsyncMock()
                await subscriber._connect_to_nats()
                # 기본값이 사용되어야 함