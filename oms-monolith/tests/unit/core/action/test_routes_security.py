"""
Tests for ActionType routes security and ETag functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

from core.action.routes import router, generate_etag, check_etag_match
from core.auth import UserContext


class TestActionRouteSecurity:
    """Test security implementation in action routes"""

    @pytest.fixture
    def mock_user_context(self):
        """Mock authenticated user with appropriate scopes"""
        user = MagicMock(spec=UserContext)
        user.user_id = "user123"
        user.has_scope = MagicMock()
        return user

    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request"""
        request = MagicMock()
        request.headers = {}
        return request

    @pytest.fixture
    def mock_response(self):
        """Mock FastAPI response"""
        response = MagicMock()
        response.headers = {}
        return response

    @pytest.mark.asyncio
    async def test_create_action_type_requires_write_scope(self, mock_user_context):
        """Test create_action_type requires action:write scope"""
        # User without write scope
        mock_user_context.has_scope.return_value = False
        
        from core.action.routes import create_action_type, CreateActionTypeRequest
        
        request = CreateActionTypeRequest(
            name="test_action",
            displayName="Test Action",
            objectTypeId="test_object",
            implementation="webhook"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await create_action_type(request, mock_user_context)
        
        assert exc_info.value.status_code == 403
        assert "action:write" in exc_info.value.detail
        mock_user_context.has_scope.assert_called_with("action:write")

    @pytest.mark.asyncio
    async def test_create_action_type_success_with_scope(self, mock_user_context):
        """Test create_action_type succeeds with proper scope"""
        # User with write scope
        mock_user_context.has_scope.return_value = True
        
        with patch('core.action.routes.action_metadata_service') as mock_service:
            mock_service.create_action_type.return_value = {
                "id": "action123",
                "name": "test_action"
            }
            
            from core.action.routes import create_action_type, CreateActionTypeRequest
            
            request = CreateActionTypeRequest(
                name="test_action",
                displayName="Test Action", 
                objectTypeId="test_object",
                implementation="webhook"
            )
            
            result = await create_action_type(request, mock_user_context)
            
            assert result["id"] == "action123"
            mock_user_context.has_scope.assert_called_with("action:write")
            
            # Verify user context is added to request
            call_args = mock_service.create_action_type.call_args[0][0]
            assert call_args["createdBy"] == "user123"
            assert call_args["modifiedBy"] == "user123"

    @pytest.mark.asyncio
    async def test_get_action_type_requires_read_scope(self, mock_user_context, mock_request, mock_response):
        """Test get_action_type requires action:read scope"""
        # User without read scope
        mock_user_context.has_scope.return_value = False
        
        from core.action.routes import get_action_type
        
        with pytest.raises(HTTPException) as exc_info:
            await get_action_type("action123", mock_request, mock_response, mock_user_context)
        
        assert exc_info.value.status_code == 403
        assert "action:read" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_action_type_with_etag_match(self, mock_user_context, mock_request, mock_response):
        """Test get_action_type returns 304 when ETag matches"""
        # User with read scope
        mock_user_context.has_scope.return_value = True
        
        # Mock action data
        action_data = {"id": "action123", "name": "test_action"}
        expected_etag = generate_etag(action_data)
        
        # Set If-None-Match header to matching ETag
        mock_request.headers = {"If-None-Match": expected_etag}
        
        with patch('core.action.routes.action_metadata_service') as mock_service:
            mock_service.get_action_type.return_value = action_data
            
            from core.action.routes import get_action_type
            
            result = await get_action_type("action123", mock_request, mock_response, mock_user_context)
            
            # Should return 304 response
            assert mock_response.status_code == 304
            assert mock_response.headers["ETag"] == expected_etag

    @pytest.mark.asyncio
    async def test_get_action_type_with_fresh_etag(self, mock_user_context, mock_request, mock_response):
        """Test get_action_type returns data with ETag when no match"""
        # User with read scope
        mock_user_context.has_scope.return_value = True
        
        # Mock action data
        action_data = {"id": "action123", "name": "test_action"}
        
        # No If-None-Match header
        mock_request.headers = {}
        
        with patch('core.action.routes.action_metadata_service') as mock_service:
            mock_service.get_action_type.return_value = action_data
            
            from core.action.routes import get_action_type
            
            result = await get_action_type("action123", mock_request, mock_response, mock_user_context)
            
            # Should return the data and set ETag
            assert result == action_data
            expected_etag = generate_etag(action_data)
            assert mock_response.headers["ETag"] == expected_etag

    @pytest.mark.asyncio
    async def test_update_action_type_requires_write_scope(self, mock_user_context):
        """Test update_action_type requires action:write scope"""
        # User without write scope
        mock_user_context.has_scope.return_value = False
        
        from core.action.routes import update_action_type, UpdateActionTypeRequest
        
        request = UpdateActionTypeRequest(name="updated_action")
        
        with pytest.raises(HTTPException) as exc_info:
            await update_action_type("action123", request, mock_user_context)
        
        assert exc_info.value.status_code == 403
        assert "action:write" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_action_type_adds_modified_by(self, mock_user_context):
        """Test update_action_type adds modifiedBy field"""
        # User with write scope
        mock_user_context.has_scope.return_value = True
        
        with patch('core.action.routes.action_metadata_service') as mock_service:
            mock_service.update_action_type.return_value = {
                "id": "action123",
                "name": "updated_action",
                "modifiedBy": "user123"
            }
            
            from core.action.routes import update_action_type, UpdateActionTypeRequest
            
            request = UpdateActionTypeRequest(name="updated_action")
            
            result = await update_action_type("action123", request, mock_user_context)
            
            # Verify modifiedBy was added to updates
            call_args = mock_service.update_action_type.call_args[0]
            updates = call_args[1]
            assert updates["modifiedBy"] == "user123"
            assert updates["name"] == "updated_action"

    @pytest.mark.asyncio
    async def test_delete_action_type_requires_delete_scope(self, mock_user_context):
        """Test delete_action_type requires action:delete scope"""
        # User without delete scope
        mock_user_context.has_scope.return_value = False
        
        from core.action.routes import delete_action_type
        
        with pytest.raises(HTTPException) as exc_info:
            await delete_action_type("action123", mock_user_context)
        
        assert exc_info.value.status_code == 403
        assert "action:delete" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_list_action_types_requires_read_scope(self, mock_user_context):
        """Test list_action_types requires action:read scope"""
        # User without read scope
        mock_user_context.has_scope.return_value = False
        
        from core.action.routes import list_action_types
        
        with pytest.raises(HTTPException) as exc_info:
            await list_action_types(user=mock_user_context)
        
        assert exc_info.value.status_code == 403
        assert "action:read" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_validate_action_input_requires_read_scope(self, mock_user_context):
        """Test validate_action_input requires action:read scope"""
        # User without read scope
        mock_user_context.has_scope.return_value = False
        
        from core.action.routes import validate_action_input, ValidateActionInputRequest
        
        request = ValidateActionInputRequest(parameters={"test": "value"})
        
        with pytest.raises(HTTPException) as exc_info:
            await validate_action_input("action123", request, mock_user_context)
        
        assert exc_info.value.status_code == 403
        assert "action:read" in exc_info.value.detail

    def test_etag_generation_consistency(self):
        """Test ETag generation is consistent for same data"""
        data1 = {"id": "123", "name": "test", "value": 42}
        data2 = {"id": "123", "name": "test", "value": 42}
        data3 = {"id": "123", "name": "different", "value": 42}
        
        etag1 = generate_etag(data1)
        etag2 = generate_etag(data2)
        etag3 = generate_etag(data3)
        
        # Same data should produce same ETag
        assert etag1 == etag2
        # Different data should produce different ETag
        assert etag1 != etag3

    def test_etag_check_match_logic(self, mock_request):
        """Test ETag matching logic"""
        etag = "test-etag-123"
        
        # No If-None-Match header
        mock_request.headers = {}
        assert not check_etag_match(mock_request, etag)
        
        # Matching If-None-Match header
        mock_request.headers = {"If-None-Match": etag}
        assert check_etag_match(mock_request, etag)
        
        # Non-matching If-None-Match header
        mock_request.headers = {"If-None-Match": "different-etag"}
        assert not check_etag_match(mock_request, etag)


class TestAuthenticationIntegration:
    """Test authentication integration with existing middleware"""

    def test_routes_import_auth_dependencies(self):
        """Test routes correctly import authentication dependencies"""
        from core.action.routes import get_current_user, UserContext
        
        # Should be able to import auth components
        assert get_current_user is not None
        assert UserContext is not None

    @pytest.mark.asyncio
    async def test_unauthenticated_request_handling(self):
        """Test handling of unauthenticated requests"""
        # This would typically be handled by middleware, but we test the integration
        from core.action.routes import get_current_user
        from fastapi import Request
        
        # Mock request without user context
        mock_request = MagicMock(spec=Request)
        mock_request.state.user = None
        
        # Should raise HTTPException when no user context
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(mock_request)
        
        assert exc_info.value.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__])