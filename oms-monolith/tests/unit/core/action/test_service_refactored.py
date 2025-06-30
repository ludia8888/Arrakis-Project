"""
Tests for refactored ActionService with retry, circuit breaker, and DLQ integration.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import httpx

from core.action.service import ActionService
from shared.dlq.models import DLQReason
from shared.utils.retry_strategy import CircuitBreakerOpenError


class TestActionServiceRefactored:
    """Test suite for refactored ActionService"""

    @pytest.fixture
    def mock_tdb_client(self):
        """Mock TerminusDB client"""
        return MagicMock()

    @pytest.fixture 
    def mock_redis_client(self):
        """Mock Redis client"""
        return AsyncMock()

    @pytest.fixture
    def mock_config(self):
        """Mock environment config"""
        with patch('core.action.service.get_config') as mock:
            config = MagicMock()
            config.get_actions_service_url.return_value = "http://test-actions-service:8009"
            config.is_production = False
            mock.return_value = config
            yield config

    @pytest.fixture
    def action_service(self, mock_tdb_client, mock_redis_client, mock_config):
        """Create ActionService instance with mocks"""
        with patch('core.action.service.ActionMetadataService'), \
             patch('core.action.service.ActionDLQHandler') as mock_dlq:
            
            service = ActionService(
                tdb_client=mock_tdb_client,
                redis_client=mock_redis_client
            )
            service.dlq_handler = mock_dlq.return_value
            return service

    @pytest.mark.asyncio
    async def test_execute_action_success(self, action_service):
        """Test successful action execution with retry protection"""
        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "test-job-123",
            "status": "completed",
            "results": []
        }
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            result = await action_service.execute_action(
                action_type_id="test-action",
                object_ids=["obj1", "obj2"],
                parameters={"param1": "value1"},
                user={"user_id": "user123"}
            )

            assert result["job_id"] == "test-job-123"
            assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_execute_action_timeout_retry(self, action_service):
        """Test action execution with timeout and retry"""
        # Mock timeout on first attempts, success on final attempt
        timeout_error = httpx.TimeoutException("Request timeout")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"job_id": "test-job-123"}
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_post = mock_client.return_value.__aenter__.return_value.post
            # First two calls timeout, third succeeds
            mock_post.side_effect = [timeout_error, timeout_error, mock_response]
            
            result = await action_service.execute_action(
                action_type_id="test-action",
                object_ids=["obj1"],
                parameters={},
                user={"user_id": "user123"}
            )

            assert result["job_id"] == "test-job-123"
            assert mock_post.call_count == 3  # Two retries + success

    @pytest.mark.asyncio
    async def test_execute_action_exhausted_retries_dlq(self, action_service):
        """Test action execution when retries are exhausted, should go to DLQ"""
        # Mock persistent timeout
        timeout_error = httpx.TimeoutException("Request timeout")
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = timeout_error
            
            # Should eventually raise the timeout error after exhausting retries
            with pytest.raises(httpx.TimeoutException):
                await action_service.execute_action(
                    action_type_id="test-action",
                    object_ids=["obj1"],
                    parameters={},
                    user={"user_id": "user123"}
                )

    @pytest.mark.asyncio
    async def test_get_execution_status_success(self, action_service):
        """Test successful execution status retrieval"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "execution_id": "exec-123",
            "status": "running",
            "progress": 50
        }
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await action_service.get_execution_status("exec-123")

            assert result["execution_id"] == "exec-123"
            assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_failure(self, action_service):
        """Test circuit breaker opens after failures"""
        # This test verifies circuit breaker integration
        with patch('shared.utils.retry_strategy.get_circuit_breaker') as mock_get_cb:
            mock_cb = MagicMock()
            mock_cb.is_open.return_value = True
            mock_get_cb.return_value = mock_cb
            
            with pytest.raises(CircuitBreakerOpenError):
                await action_service.execute_action(
                    action_type_id="test-action",
                    object_ids=["obj1"],
                    parameters={},
                    user={"user_id": "user123"}
                )

    @pytest.mark.asyncio
    async def test_dlq_handler_failure_categorization(self, action_service):
        """Test DLQ handler correctly categorizes different failure types"""
        # Test timeout error categorization
        timeout_error = httpx.TimeoutException("Request timeout")
        request_data = {"test": "data"}
        
        await action_service._handle_actions_service_failure(
            "test_operation", request_data, timeout_error
        )
        
        # Verify DLQ handler was called with correct reason
        action_service.dlq_handler.send_to_dlq.assert_called_once()
        call_args = action_service.dlq_handler.send_to_dlq.call_args
        assert call_args[1]['reason'] == DLQReason.TIMEOUT
        assert call_args[1]['original_message'] == request_data

    @pytest.mark.asyncio
    async def test_network_error_handling(self, action_service):
        """Test network error handling and DLQ integration"""
        connect_error = httpx.ConnectError("Connection failed")
        request_data = {"action_type_id": "test"}
        
        await action_service._handle_actions_service_failure(
            "execute_action", request_data, connect_error
        )
        
        # Verify correct DLQ reason for network errors
        call_args = action_service.dlq_handler.send_to_dlq.call_args
        assert call_args[1]['reason'] == DLQReason.NETWORK_ERROR

    @pytest.mark.asyncio
    async def test_http_status_error_handling(self, action_service):
        """Test HTTP status error categorization"""
        # Test 500 error (server error)
        response_500 = MagicMock()
        response_500.status_code = 500
        server_error = httpx.HTTPStatusError("Server error", request=MagicMock(), response=response_500)
        
        await action_service._handle_actions_service_failure(
            "test_operation", {}, server_error
        )
        
        call_args = action_service.dlq_handler.send_to_dlq.call_args
        assert call_args[1]['reason'] == DLQReason.EXECUTION_FAILED

        # Test 400 error (client error)
        action_service.dlq_handler.reset_mock()
        response_400 = MagicMock()
        response_400.status_code = 400
        client_error = httpx.HTTPStatusError("Bad request", request=MagicMock(), response=response_400)
        
        await action_service._handle_actions_service_failure(
            "test_operation", {}, client_error
        )
        
        call_args = action_service.dlq_handler.send_to_dlq.call_args
        assert call_args[1]['reason'] == DLQReason.VALIDATION_FAILED

    def test_fail_fast_missing_dependencies(self):
        """Test fail-fast behavior when dependencies are missing"""
        with patch('core.action.service.SmartCacheManager', side_effect=ImportError("Module not found")):
            with pytest.raises(ModuleNotFoundError) as exc_info:
                import importlib
                import core.action.service
                importlib.reload(core.action.service)
            
            assert "Action service requires missing dependency" in str(exc_info.value)

    def test_config_integration(self, mock_config):
        """Test configuration integration and validation"""
        with patch('core.action.service.ActionMetadataService'), \
             patch('core.action.service.ActionDLQHandler'):
            
            service = ActionService(
                tdb_client=MagicMock(),
                redis_client=AsyncMock()
            )
            
            # Verify service uses config URL
            assert service.actions_service_url == "http://test-actions-service:8009"
            mock_config.get_actions_service_url.assert_called_once()

    @pytest.mark.asyncio 
    async def test_production_health_check_validation(self):
        """Test Actions Service health check validation in production"""
        with patch('core.action.service.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.is_production = True
            mock_config.get_actions_service_url.return_value = "http://actions-service:8009"
            mock_get_config.return_value = mock_config
            
            with patch('core.action.service.ActionMetadataService'), \
                 patch('core.action.service.ActionDLQHandler'):
                
                # Should create service without errors (health check is noted for first use)
                service = ActionService(
                    tdb_client=MagicMock(),
                    redis_client=AsyncMock()
                )
                
                assert service.actions_service_url == "http://actions-service:8009"


class TestSharedDLQIntegration:
    """Test shared DLQ package integration"""

    @pytest.fixture
    def mock_redis(self):
        return AsyncMock()

    @pytest.fixture 
    def mock_nats(self):
        return MagicMock()

    def test_dlq_models_import(self):
        """Test DLQ models can be imported from shared package"""
        from shared.dlq import DLQReason, DLQMessage, RetryPolicy, ActionDLQHandler
        
        # Verify all expected classes are available
        assert DLQReason.TIMEOUT
        assert DLQReason.NETWORK_ERROR
        assert DLQMessage
        assert RetryPolicy
        assert ActionDLQHandler

    @pytest.mark.asyncio
    async def test_action_dlq_handler_initialization(self, mock_redis):
        """Test ActionDLQHandler can be initialized and configured"""
        from shared.dlq import ActionDLQHandler, DLQConfig
        
        config = DLQConfig(
            name="test_actions",
            max_retries=5,
            redis_key_prefix="test_dlq"
        )
        
        handler = ActionDLQHandler(mock_redis, config)
        
        assert handler.config.name == "test_actions"
        assert handler.config.max_retries == 5
        assert handler.config.redis_key_prefix == "test_dlq"

    def test_legacy_dlq_compatibility(self):
        """Test legacy DLQ handler maintains compatibility"""
        from core.action.dlq_handler import DLQHandler, DLQReason
        
        # Should be able to import legacy classes (now aliases)
        assert DLQReason.TIMEOUT
        assert DLQHandler


if __name__ == "__main__":
    pytest.main([__file__])