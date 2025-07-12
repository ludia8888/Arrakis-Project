"""
Test Configuration
Centralized configuration for test data and settings
"""
import os
from typing import List, Dict, Any


class TestConfig:
    """Configuration for test data and settings"""
    
    # Protected branch patterns
    PROTECTED_BRANCHES = [
        "main", "master", "production", "staging", "release", "develop"
    ]
    
    # Non-protected branch patterns for testing
    NON_PROTECTED_BRANCHES = [
        "feature/test", 
        "bugfix/issue-123", 
        "dev/user",
        "hotfix/critical-fix",
        "experimental/new-feature"
    ]
    
    # Test user data
    TEST_USERS = {
        "admin": {
            "username": "test_admin",
            "email": "admin@test.example.com",
            "password": os.getenv('TEST_ADMIN_PASSWORD', 'TestAdmin123!'),
            "roles": ["admin"]
        },
        "user": {
            "username": "test_user", 
            "email": "user@test.example.com",
            "password": os.getenv('TEST_USER_PASSWORD', 'TestUser123!'),
            "roles": ["user"]
        },
        "service": {
            "username": "test_service",
            "email": "service@test.example.com", 
            "password": os.getenv('TEST_SERVICE_PASSWORD', 'TestService123!'),
            "roles": ["service"]
        }
    }
    
    # Database configuration for tests
    TEST_DB_CONFIG = {
        "host": os.getenv('TEST_DB_HOST', 'localhost'),
        "port": int(os.getenv('TEST_DB_PORT', '5432')),
        "user": os.getenv('TEST_DB_USER', 'test_user'),
        "password": os.getenv('TEST_DB_PASSWORD', ''),
        "database": os.getenv('TEST_DB_NAME', 'test_db'),
        "driver": os.getenv('TEST_DB_DRIVER', 'postgresql')
    }
    
    # JWT configuration for tests
    JWT_CONFIG = {
        "secret": os.getenv('TEST_JWT_SECRET', 'test-secret-key-for-testing-only'),
        "algorithm": os.getenv('TEST_JWT_ALGORITHM', 'HS256'),
        "expiration_hours": int(os.getenv('TEST_JWT_EXPIRATION_HOURS', '24'))
    }
    
    # API test configuration
    API_CONFIG = {
        "base_url": os.getenv('TEST_API_BASE_URL', 'http://localhost:8000'),
        "timeout": float(os.getenv('TEST_API_TIMEOUT', '30.0')),
        "retries": int(os.getenv('TEST_API_RETRIES', '3')),
        "retry_delay": float(os.getenv('TEST_API_RETRY_DELAY', '1.0'))
    }
    
    # Load test configuration
    LOAD_TEST_CONFIG = {
        "users": int(os.getenv('LOAD_TEST_USERS', '10')),
        "spawn_rate": int(os.getenv('LOAD_TEST_SPAWN_RATE', '1')),
        "run_time": os.getenv('LOAD_TEST_RUN_TIME', '60s'),
        "password": os.getenv('LOAD_TEST_PASSWORD', 'LoadTest@Password123!')
    }
    
    # Validation test data
    VALIDATION_TEST_DATA = {
        "valid_emails": [
            "test@example.com",
            "user.name@domain.co.uk", 
            "123@test-domain.com"
        ],
        "invalid_emails": [
            "invalid-email",
            "@domain.com",
            "user@",
            "user..name@domain.com"
        ],
        "valid_phone_numbers": [
            "+1234567890",
            "123-456-7890",
            "(123) 456-7890"
        ],
        "invalid_phone_numbers": [
            "123",
            "12345678901234567890",
            "abc-def-ghij"
        ]
    }
    
    @classmethod
    def get_protected_branches(cls) -> List[str]:
        """Get list of protected branch names"""
        custom_branches = os.getenv('TEST_PROTECTED_BRANCHES')
        if custom_branches:
            return [branch.strip() for branch in custom_branches.split(',')]
        return cls.PROTECTED_BRANCHES.copy()
    
    @classmethod
    def get_non_protected_branches(cls) -> List[str]:
        """Get list of non-protected branch names for testing"""
        custom_branches = os.getenv('TEST_NON_PROTECTED_BRANCHES')
        if custom_branches:
            return [branch.strip() for branch in custom_branches.split(',')]
        return cls.NON_PROTECTED_BRANCHES.copy()
    
    @classmethod
    def get_test_user(cls, user_type: str) -> Dict[str, Any]:
        """Get test user configuration"""
        return cls.TEST_USERS.get(user_type, cls.TEST_USERS["user"]).copy()
    
    @classmethod
    def get_db_url(cls) -> str:
        """Get test database URL"""
        config = cls.TEST_DB_CONFIG
        if config["password"]:
            return f"{config['driver']}://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"
        else:
            return f"{config['driver']}://{config['user']}@{config['host']}:{config['port']}/{config['database']}"
    
    @classmethod
    def is_safe_for_production(cls) -> bool:
        """Check if current configuration is safe for production use"""
        unsafe_indicators = [
            cls.JWT_CONFIG["secret"] == "test-secret-key-for-testing-only",
            cls.TEST_DB_CONFIG["password"] == "",
            any("test" in user["password"].lower() for user in cls.TEST_USERS.values())
        ]
        return not any(unsafe_indicators)


# Global test configuration instance
test_config = TestConfig()


# Convenience functions
def get_protected_branches() -> List[str]:
    """Get list of protected branch names"""
    return test_config.get_protected_branches()


def get_non_protected_branches() -> List[str]:
    """Get list of non-protected branch names"""
    return test_config.get_non_protected_branches()


def get_test_user(user_type: str = "user") -> Dict[str, Any]:
    """Get test user configuration"""
    return test_config.get_test_user(user_type)


def get_test_db_url() -> str:
    """Get test database URL"""
    return test_config.get_db_url()