"""
Authentication and authorization tests
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from utils.auth import get_current_user, require_permissions, require_role


class TestAuthentication:
    """Authentication tests"""
    
    @pytest.mark.asyncio
    async def test_valid_jwt_token(self, sample_jwt_token):
        """Test valid JWT token validation"""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=sample_jwt_token
        )
        
        user = await get_current_user(credentials)
        
        assert user is not None
        assert user["user_id"] == "test_user_123"
        assert user["username"] == "testuser"
        assert user["email"] == "test@example.com"
        assert "audit_user" in user["roles"]
        assert "audit:read" in user["permissions"]
    
    @pytest.mark.asyncio
    async def test_invalid_jwt_token(self):
        """Test invalid JWT token"""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid-token"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials)
        
        assert exc_info.value.status_code == 401
        assert "Invalid token" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_expired_jwt_token(self):
        """Test expired JWT token"""
        import jwt
        from datetime import datetime, timedelta, timezone
        
        # Create expired token
        payload = {
            "sub": "test_user_123",
            "username": "testuser",
            "email": "test@example.com",
            "roles": ["audit_user"],
            "permissions": ["audit:read"],
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "iss": "user-service",
            "aud": "oms"
        }
        
        expired_token = jwt.encode(payload, "test-secret-key-for-testing-only", algorithm="HS256")
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=expired_token
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials)
        
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_missing_token(self):
        """Test missing token"""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=""
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials)
        
        assert exc_info.value.status_code == 401
        assert "required" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_wrong_token_type(self):
        """Test wrong token type (refresh instead of access)"""
        import jwt
        from datetime import datetime, timedelta, timezone
        
        payload = {
            "sub": "test_user_123",
            "type": "refresh",  # Wrong type
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "iss": "user-service",
            "aud": "oms"
        }
        
        refresh_token = jwt.encode(payload, "test-secret-key-for-testing-only", algorithm="HS256")
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=refresh_token
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials)
        
        assert exc_info.value.status_code == 401
        assert "Invalid token type" in exc_info.value.detail


class TestAuthorization:
    """Authorization tests"""
    
    def test_require_permissions_success(self):
        """Test successful permission check"""
        user = {
            "user_id": "test_user",
            "roles": ["audit_user"],
            "permissions": ["audit:read", "audit:write", "history:read"]
        }
        
        # Should not raise exception
        result = require_permissions(user, ["audit:read"])
        assert result is True
        
        # Test multiple permissions (any)
        result = require_permissions(user, ["audit:read", "admin:write"], require_all=False)
        assert result is True
        
        # Test multiple permissions (all)
        result = require_permissions(user, ["audit:read", "audit:write"], require_all=True)
        assert result is True
    
    def test_require_permissions_failure(self):
        """Test failed permission check"""
        user = {
            "user_id": "test_user",
            "roles": ["basic_user"],
            "permissions": ["audit:read"]
        }
        
        # Missing permission
        with pytest.raises(HTTPException) as exc_info:
            require_permissions(user, ["audit:write"])
        
        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in exc_info.value.detail
        
        # Missing all required permissions
        with pytest.raises(HTTPException) as exc_info:
            require_permissions(user, ["audit:read", "audit:write"], require_all=True)
        
        assert exc_info.value.status_code == 403
    
    def test_admin_role_bypass(self):
        """Test admin role bypasses permission checks"""
        user = {
            "user_id": "admin_user",
            "roles": ["admin"],
            "permissions": []  # No specific permissions
        }
        
        # Should pass even without specific permissions
        result = require_permissions(user, ["audit:write", "system:admin"])
        assert result is True
    
    def test_require_role_success(self):
        """Test successful role check"""
        user = {
            "user_id": "test_user",
            "roles": ["audit_user", "developer"]
        }
        
        result = require_role(user, "audit_user")
        assert result is True
        
        result = require_role(user, "developer")
        assert result is True
    
    def test_require_role_failure(self):
        """Test failed role check"""
        user = {
            "user_id": "test_user",
            "roles": ["basic_user"]
        }
        
        with pytest.raises(HTTPException) as exc_info:
            require_role(user, "admin")
        
        assert exc_info.value.status_code == 403
        assert "Insufficient role" in exc_info.value.detail
    
    def test_admin_role_access(self):
        """Test admin role can access any role requirement"""
        user = {
            "user_id": "admin_user",
            "roles": ["admin"]
        }
        
        result = require_role(user, "developer")
        assert result is True
        
        result = require_role(user, "audit_user")
        assert result is True


class TestUserServiceIntegration:
    """User service integration tests"""
    
    @patch('utils.auth.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_verify_user_with_service_success(self, mock_client):
        """Test successful user verification with user service"""
        from utils.auth import verify_user_with_service
        
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        
        # Create a regular Mock for the json method to return a dict directly
        from unittest.mock import Mock
        mock_response.json = Mock(return_value={
            "id": "user123",
            "username": "testuser",
            "email": "test@example.com",
            "status": "active"
        })
        
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value = mock_client_instance
        
        result = await verify_user_with_service("user123")
        
        assert result is not None
        assert result["id"] == "user123"
        assert result["username"] == "testuser"
    
    @patch('utils.auth.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_verify_user_with_service_not_found(self, mock_client):
        """Test user not found in user service"""
        from utils.auth import verify_user_with_service
        
        # Mock 404 response
        mock_response = AsyncMock()
        mock_response.status_code = 404
        
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value = mock_client_instance
        
        result = await verify_user_with_service("nonexistent")
        
        assert result is None
    
    @patch('utils.auth.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_verify_user_with_service_error(self, mock_client):
        """Test error handling in user service verification"""
        from utils.auth import verify_user_with_service
        
        # Mock exception
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.get.side_effect = Exception("Connection error")
        mock_client.return_value = mock_client_instance
        
        result = await verify_user_with_service("user123")
        
        assert result is None


class TestSecurityHelpers:
    """Security helper function tests"""
    
    def test_mask_sensitive_data(self):
        """Test sensitive data masking"""
        from utils.auth import mask_sensitive_data
        
        data = {
            "email": "user@example.com",
            "password": "secret123",
            "token": "abcdef123456",
            "public_info": "visible"
        }
        
        masked = mask_sensitive_data(data, ["password", "token"])
        
        assert masked["email"] == "user@example.com"
        assert masked["public_info"] == "visible"
        assert masked["password"] == "*******123"  # Last 4 chars visible
        assert masked["token"] == "********3456"  # Last 4 chars visible
    
    def test_get_data_classification_permissions(self):
        """Test data classification permission checking"""
        from utils.auth import get_data_classification_permissions
        
        # Public data - everyone can access
        user = {"roles": ["basic_user"], "permissions": []}
        assert get_data_classification_permissions(user, "public") is True
        
        # Internal data - needs permission
        user = {"roles": ["user"], "permissions": ["data:internal"]}
        assert get_data_classification_permissions(user, "internal") is True
        
        user = {"roles": ["user"], "permissions": []}
        assert get_data_classification_permissions(user, "internal") is False
        
        # Admin bypass
        user = {"roles": ["admin"], "permissions": []}
        assert get_data_classification_permissions(user, "restricted") is True
    
    @patch('utils.auth.get_audit_logger')
    def test_log_access_attempt(self, mock_logger):
        """Test access attempt logging"""
        from utils.auth import log_access_attempt
        
        mock_audit_logger = AsyncMock()
        mock_logger.return_value = mock_audit_logger
        
        user = {
            "user_id": "user123",
            "ip_address": "192.168.1.100",
            "session_id": "session123"
        }
        
        log_access_attempt(
            user=user,
            resource_type="audit_log",
            resource_id="log123",
            action="read",
            success=True
        )
        
        mock_audit_logger.log_user_action.assert_called_once()