"""
GraphQL Auth Mutations (User Service Proxy)
Proxies authentication mutations to user-service through GraphQL
"""

from typing import List, Optional

import strawberry
from arrakis_common import get_logger
from core.monitoring.audit_metrics import record_audit_service_request
from shared.user_service_client import get_user_service_client
from strawberry.types import Info

logger = get_logger(__name__)


@strawberry.type
class AuthResponse:
    """Authentication response"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


@strawberry.type
class UserInfo:
    """User information"""

    user_id: str
    username: str
    email: str
    full_name: Optional[str] = None
    roles: List[str]
    permissions: List[str]
    teams: List[str]
    mfa_enabled: bool


@strawberry.type
class RegisterResponse:
    """Registration response"""

    user: UserInfo
    message: str = "User registered successfully"


@strawberry.type
class MFASetupResponse:
    """MFA setup response"""

    secret: str
    qr_code: str
    backup_codes: Optional[List[str]] = None


@strawberry.input
class LoginInput:
    """Login input"""

    username: str
    password: str
    mfa_code: Optional[str] = None


@strawberry.input
class RegisterInput:
    """Registration input"""

    username: str
    email: str
    password: str
    full_name: Optional[str] = None


@strawberry.input
class PasswordChangeInput:
    """Password change input"""

    old_password: str
    new_password: str


@strawberry.input
class MFAEnableInput:
    """MFA enable input"""

    code: str


@strawberry.input
class MFADisableInput:
    """MFA disable input"""

    password: str
    code: str


@strawberry.type
class AuthMutation:
    """Authentication-related GraphQL Mutations (User Service proxy)"""

    @strawberry.mutation
    async def login(self, info: Info, input: LoginInput) -> AuthResponse:
        """
        User login

        Args:
            input: Login information

        Returns:
            Authentication tokens
        """
        client = get_user_service_client()

        try:
            async with client:
                result = await client.login(
                    username=input.username,
                    password=input.password,
                    mfa_code=input.mfa_code,
                )

                # Record metrics
                record_audit_service_request(
                    method="POST",
                    endpoint="/auth/login",
                    status="success",
                    duration=0.1,
                )

                return AuthResponse(
                    access_token=result["access_token"],
                    refresh_token=result["refresh_token"],
                    token_type=result.get("token_type", "bearer"),
                    expires_in=result.get("expires_in", 1800),
                )

        except Exception as e:
            logger.error(f"GraphQL login failed: {e}")

            # Record metrics
            record_audit_service_request(
                method="POST", endpoint="/auth/login", status="error", duration=0.1
            )

            raise Exception("Authentication failed")

    @strawberry.mutation
    async def register(self, info: Info, input: RegisterInput) -> RegisterResponse:
        """
        User registration

        Args:
            input: Registration information

        Returns:
            Created user information
        """
        client = get_user_service_client()

        try:
            async with client:
                result = await client.register(
                    username=input.username,
                    email=input.email,
                    password=input.password,
                    full_name=input.full_name,
                )

                # Record metrics
                record_audit_service_request(
                    method="POST",
                    endpoint="/auth/register",
                    status="success",
                    duration=0.1,
                )

                user_data = result["user"]
                return RegisterResponse(
                    user=UserInfo(
                        user_id=user_data["user_id"],
                        username=user_data["username"],
                        email=user_data["email"],
                        full_name=user_data.get("full_name"),
                        roles=user_data.get("roles", []),
                        permissions=user_data.get("permissions", []),
                        teams=user_data.get("teams", []),
                        mfa_enabled=user_data.get("mfa_enabled", False),
                    ),
                    message=result.get("message", "User registered successfully"),
                )

        except Exception as e:
            logger.error(f"GraphQL registration failed: {e}")

            # Record metrics
            record_audit_service_request(
                method="POST", endpoint="/auth/register", status="error", duration=0.1
            )

            raise Exception("Registration failed")

    @strawberry.mutation
    async def logout(self, info: Info) -> str:
        """
        User logout

        Returns:
            Logout message
        """
        client = get_user_service_client()

        # Extract token from Authorization header
        request = info.context["request"]
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            raise Exception("Missing or invalid authorization header")

        token = auth_header[7:]  # Remove "Bearer "

        try:
            async with client:
                result = await client.logout(token)

                # Record metrics
                record_audit_service_request(
                    method="POST",
                    endpoint="/auth/logout",
                    status="success",
                    duration=0.1,
                )

                return result.get("message", "Logged out successfully")

        except Exception as e:
            logger.error(f"GraphQL logout failed: {e}")

            # Record metrics
            record_audit_service_request(
                method="POST", endpoint="/auth/logout", status="error", duration=0.1
            )

            # Return success even if logout fails
            return "Logged out"

    @strawberry.mutation
    async def change_password(self, info: Info, input: PasswordChangeInput) -> str:
        """
        Change password

        Args:
            input: Password change information

        Returns:
            Change result message
        """
        client = get_user_service_client()

        # Extract token from Authorization header
        request = info.context["request"]
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            raise Exception("Missing or invalid authorization header")

        token = auth_header[7:]  # Remove "Bearer "

        try:
            async with client:
                result = await client.change_password(
                    token=token,
                    old_password=input.old_password,
                    new_password=input.new_password,
                )

                # Record metrics
                record_audit_service_request(
                    method="POST",
                    endpoint="/auth/change-password",
                    status="success",
                    duration=0.1,
                )

                return result.get("message", "Password changed successfully")

        except Exception as e:
            logger.error(f"GraphQL password change failed: {e}")

            # Record metrics
            record_audit_service_request(
                method="POST",
                endpoint="/auth/change-password",
                status="error",
                duration=0.1,
            )

            raise Exception("Password change failed")

    @strawberry.mutation
    async def setup_mfa(self, info: Info) -> MFASetupResponse:
        """
        MFA setup

        Returns:
            MFA setup information
        """
        client = get_user_service_client()

        # Extract token from Authorization header
        request = info.context["request"]
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            raise Exception("Missing or invalid authorization header")

        token = auth_header[7:]  # Remove "Bearer "

        try:
            async with client:
                result = await client.setup_mfa(token)

                # Record metrics
                record_audit_service_request(
                    method="POST",
                    endpoint="/auth/mfa/setup",
                    status="success",
                    duration=0.1,
                )

                return MFASetupResponse(
                    secret=result["secret"],
                    qr_code=result["qr_code"],
                    backup_codes=result.get("backup_codes"),
                )

        except Exception as e:
            logger.error(f"GraphQL MFA setup failed: {e}")

            # Record metrics
            record_audit_service_request(
                method="POST", endpoint="/auth/mfa/setup", status="error", duration=0.1
            )

            raise Exception("MFA setup failed")

    @strawberry.mutation
    async def enable_mfa(self, info: Info, input: MFAEnableInput) -> str:
        """
        Enable MFA

        Args:
            input: MFA enable information

        Returns:
            Enable result message
        """
        client = get_user_service_client()

        # Extract token from Authorization header
        request = info.context["request"]
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            raise Exception("Missing or invalid authorization header")

        token = auth_header[7:]  # Remove "Bearer "

        try:
            async with client:
                result = await client.enable_mfa(token, input.code)

                # Record metrics
                record_audit_service_request(
                    method="POST",
                    endpoint="/auth/mfa/enable",
                    status="success",
                    duration=0.1,
                )

                return result.get("message", "MFA enabled successfully")

        except Exception as e:
            logger.error(f"GraphQL MFA enable failed: {e}")

            # Record metrics
            record_audit_service_request(
                method="POST", endpoint="/auth/mfa/enable", status="error", duration=0.1
            )

            raise Exception("MFA enable failed")

    @strawberry.mutation
    async def disable_mfa(self, info: Info, input: MFADisableInput) -> str:
        """
        Disable MFA

        Args:
            input: MFA disable information

        Returns:
            Disable result message
        """
        client = get_user_service_client()

        # Extract token from Authorization header
        request = info.context["request"]
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            raise Exception("Missing or invalid authorization header")

        token = auth_header[7:]  # Remove "Bearer "

        try:
            async with client:
                result = await client.disable_mfa(token, input.password, input.code)

                # Record metrics
                record_audit_service_request(
                    method="POST",
                    endpoint="/auth/mfa/disable",
                    status="success",
                    duration=0.1,
                )

                return result.get("message", "MFA disabled successfully")

        except Exception as e:
            logger.error(f"GraphQL MFA disable failed: {e}")

            # Record metrics
            record_audit_service_request(
                method="POST",
                endpoint="/auth/mfa/disable",
                status="error",
                duration=0.1,
            )

            raise Exception("MFA disable failed")


# Mutation to add to GraphQL schema
auth_mutation = AuthMutation()
