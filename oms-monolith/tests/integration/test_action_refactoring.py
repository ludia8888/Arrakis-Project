"""
Integration tests for core/action refactoring.
Verifies end-to-end functionality of refactored components.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from shared.dlq import ActionDLQHandler, DLQConfig
from shared.models.action import ActionType
from shared.config.environment import EnvironmentConfig


class TestActionRefactoringIntegration:
    """Integration tests for refactored action components"""

    @pytest.mark.asyncio
    async def test_unified_dlq_integration(self):
        """Test unified DLQ system integration"""
        # Mock Redis client
        mock_redis = AsyncMock()
        
        # Create DLQ config and handler
        config = DLQConfig(
            name="test_actions",
            max_retries=3,
            redis_key_prefix="integration_test"
        )
        
        dlq_handler = ActionDLQHandler(mock_redis, config)
        
        # Mock DLQ operations
        mock_redis.set.return_value = True
        mock_redis.zadd.return_value = 1
        mock_redis.zcard.return_value = 1
        
        from shared.dlq.models import DLQReason
        
        # Test sending message to DLQ
        message_id = await dlq_handler.send_to_dlq(
            queue_name="actions_service",
            original_message={"action_type_id": "test", "parameters": {}},
            reason=DLQReason.TIMEOUT,
            error=Exception("Test timeout"),
            metadata={"test": True}
        )
        
        assert message_id is not None
        assert mock_redis.set.called
        assert mock_redis.zadd.called

    def test_shared_models_integration(self):
        """Test shared models can be imported and used"""
        from shared.models.action import ActionType, ExecutionOptions, Job
        from core.action.models import ActionTypeModel  # Legacy import
        
        # Should be able to create instances of shared models
        action_type_data = {
            "id": "test-action-123",
            "objectTypeId": "test-object",
            "name": "test_action",
            "displayName": "Test Action",
            "inputSchema": {"type": "object"},
            "implementation": "webhook",
            "versionHash": "abc123",
            "createdBy": "user123",
            "createdAt": "2024-01-01T00:00:00Z",
            "modifiedBy": "user123", 
            "modifiedAt": "2024-01-01T00:00:00Z"
        }
        
        # Both should work (shared and legacy)
        shared_action = ActionType(**action_type_data)
        legacy_action = ActionTypeModel(**action_type_data)
        
        assert shared_action.id == legacy_action.id
        assert shared_action.name == legacy_action.name

    @pytest.mark.asyncio
    async def test_config_validation_integration(self):
        """Test configuration validation integration"""
        with patch.dict('os.environ', {
            'ENVIRONMENT': 'test',
            'ACTIONS_SERVICE_URL': 'http://test-actions:8009'
        }):
            config = EnvironmentConfig()
            
            # Should be able to get Actions Service URL
            url = config.get_actions_service_url()
            assert url == 'http://test-actions:8009'
            
            # Test health check validation
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
                
                result = await config.validate_actions_service_health()
                assert result is True

    def test_legacy_compatibility(self):
        """Test legacy imports still work for backward compatibility"""
        # Legacy DLQ imports
        from core.action.dlq_handler import DLQHandler, DLQReason, RetryPolicy
        
        # Should be able to create legacy handler (now wraps unified)
        mock_redis = AsyncMock()
        handler = DLQHandler(mock_redis)
        
        # Should be instances of the unified classes
        assert hasattr(handler, 'config')
        assert DLQReason.TIMEOUT is not None
        assert RetryPolicy is not None

    @pytest.mark.asyncio 
    async def test_retry_strategy_integration(self):
        """Test retry strategy integration with Actions Service"""
        from core.action.service import ActionService
        from shared.utils.retry_strategy import with_retry, RetryConfig
        
        # Verify retry decorators are applied to service methods
        assert hasattr(ActionService.execute_action, '__wrapped__')
        assert hasattr(ActionService.get_execution_status, '__wrapped__')
        assert hasattr(ActionService.get_job_status, '__wrapped__')

    @pytest.mark.asyncio
    async def test_fail_fast_behavior(self):
        """Test fail-fast behavior when dependencies are missing"""
        # Test that missing dependencies cause immediate failure
        with patch('shared.cache.smart_cache.SmartCacheManager', side_effect=ImportError("Missing module")):
            with pytest.raises(ModuleNotFoundError) as exc_info:
                # This should fail immediately when trying to import
                from core.action.service import ActionService
            
            assert "Action service requires missing dependency" in str(exc_info.value)

    def test_api_security_integration(self):
        """Test API security integration"""
        from core.action.routes import router
        from fastapi import Depends
        
        # Check that routes have authentication dependencies
        create_route = None
        for route in router.routes:
            if hasattr(route, 'path') and route.path == "" and "POST" in route.methods:
                create_route = route
                break
        
        assert create_route is not None
        # Route should have dependencies (authentication)
        assert len(create_route.dependant.dependencies) > 0

    @pytest.mark.asyncio
    async def test_end_to_end_action_flow(self):
        """Test end-to-end action flow with all refactored components"""
        # Mock all external dependencies
        mock_tdb = MagicMock()
        mock_redis = AsyncMock()
        
        with patch('core.action.service.ActionMetadataService') as mock_metadata, \
             patch('core.action.service.get_config') as mock_config, \
             patch('httpx.AsyncClient') as mock_http:
            
            # Setup mocks
            mock_config.return_value.get_actions_service_url.return_value = "http://test:8009"
            mock_config.return_value.is_production = False
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"job_id": "test-job", "status": "completed"}
            mock_response.raise_for_status = MagicMock()
            mock_http.return_value.__aenter__.return_value.post.return_value = mock_response
            
            # Create service
            from core.action.service import ActionService
            service = ActionService(mock_tdb, mock_redis)
            
            # Execute action (should use retry wrapper)
            result = await service.execute_action(
                action_type_id="test-action",
                object_ids=["obj1"],
                parameters={"param1": "value1"},
                user={"user_id": "user123"}
            )
            
            assert result["job_id"] == "test-job"
            assert result["status"] == "completed"
            
            # Verify HTTP call was made
            mock_http.return_value.__aenter__.return_value.post.assert_called_once()

    def test_prometheus_metrics_integration(self):
        """Test Prometheus metrics are properly integrated"""
        from shared.utils.retry_strategy import retry_attempts, circuit_breaker_state
        from shared.dlq.handlers import dlq_messages, dlq_retries
        
        # Should be able to access metrics objects
        assert retry_attempts is not None
        assert circuit_breaker_state is not None
        assert dlq_messages is not None
        assert dlq_retries is not None

    @pytest.mark.asyncio
    async def test_dlq_retry_integration(self):
        """Test DLQ and retry system integration"""
        mock_redis = AsyncMock()
        
        # Mock successful retry
        async def mock_handler(message):
            return {"processed": True}
        
        # Create DLQ handler
        config = DLQConfig(name="test_integration")
        dlq_handler = ActionDLQHandler(mock_redis, config)
        dlq_handler.register_handler("test_queue", mock_handler)
        
        # Mock Redis responses for retry flow
        mock_redis.get.return_value = '{"message_id": "test", "queue_name": "test_queue", "original_message": {}, "reason": "timeout", "error_details": "test", "stack_trace": null, "retry_count": 0, "max_retries": 3, "first_failure_time": "2024-01-01T00:00:00+00:00", "last_failure_time": "2024-01-01T00:00:00+00:00", "next_retry_time": "2024-01-01T00:01:00+00:00", "status": "pending", "metadata": {}, "error_history": []}'
        mock_redis.delete.return_value = 1
        mock_redis.zrem.return_value = 1
        mock_redis.zcard.return_value = 0
        
        # Test retry
        result = await dlq_handler.retry_message("test_queue", "test")
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__])