"""
Test unified environment configuration system
"""

import os
import pytest
from types import MappingProxyType
from unittest.mock import patch

from shared.config import (
    UnifiedEnv,
    unified_env,
    EnvVar,
    ConfigNamespace,
    ConfigurationError,
    get_env,
    require_env,
    validate_env
)


class TestUnifiedEnv:
    """Test UnifiedEnv functionality"""
    
    def setup_method(self):
        """Reset environment before each test"""
        unified_env.reset()
        # Re-initialize core after reset
        unified_env._initialize_core()
    
    def test_singleton_pattern(self):
        """Test that UnifiedEnv is a singleton"""
        env1 = UnifiedEnv()
        env2 = UnifiedEnv()
        assert env1 is env2
    
    def test_thread_safety(self):
        """Test thread-safe singleton creation"""
        import threading
        instances = []
        
        def create_instance():
            instances.append(UnifiedEnv())
        
        threads = [threading.Thread(target=create_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All instances should be the same
        assert all(inst is instances[0] for inst in instances)
    
    def test_namespace_registration(self):
        """Test namespace registration"""
        test_ns = ConfigNamespace("test", "Test namespace")
        test_ns.add_var(EnvVar("TEST_VAR", str, False, "default"))
        
        unified_env.register_namespace(test_ns)
        
        # Should be able to get the variable
        assert unified_env.get("TEST_VAR") == "default"
    
    def test_typed_env_vars(self):
        """Test different types of environment variables"""
        # Set test environment variables
        os.environ["TEST_STRING"] = "hello"
        os.environ["TEST_INT"] = "42"
        os.environ["TEST_FLOAT"] = "3.14"
        os.environ["TEST_BOOL"] = "true"
        os.environ["TEST_LIST"] = "a,b,c"
        os.environ["TEST_JSON"] = '{"key": "value"}'
        
        # Register typed variables
        unified_env.register_var(EnvVar("TEST_STRING", str), "test")
        unified_env.register_var(EnvVar("TEST_INT", int), "test")
        unified_env.register_var(EnvVar("TEST_FLOAT", float), "test")
        unified_env.register_var(EnvVar("TEST_BOOL", bool), "test")
        unified_env.register_var(EnvVar("TEST_LIST", list), "test")
        unified_env.register_var(EnvVar("TEST_JSON", dict), "test")
        
        # Test type conversion
        assert unified_env.get("TEST_STRING") == "hello"
        assert unified_env.get("TEST_INT") == 42
        assert unified_env.get("TEST_FLOAT") == 3.14
        assert unified_env.get("TEST_BOOL") is True
        assert unified_env.get("TEST_LIST") == ["a", "b", "c"]
        assert unified_env.get("TEST_JSON") == {"key": "value"}
        
        # Cleanup
        for key in ["TEST_STRING", "TEST_INT", "TEST_FLOAT", "TEST_BOOL", "TEST_LIST", "TEST_JSON"]:
            del os.environ[key]
    
    def test_validation(self):
        """Test environment variable validation"""
        # Register variable with validator
        unified_env.register_var(
            EnvVar(
                "TEST_PORT",
                int,
                validator=lambda v: 1 <= v <= 65535
            ),
            "test"
        )
        
        # Valid value
        os.environ["TEST_PORT"] = "8080"
        assert unified_env.get("TEST_PORT") == 8080
        
        # Invalid value
        os.environ["TEST_PORT"] = "70000"
        unified_env.clear_cache()
        with pytest.raises(ConfigurationError) as exc:
            unified_env.get("TEST_PORT")
        assert "Validation failed" in str(exc.value)
        
        del os.environ["TEST_PORT"]
    
    def test_namespace_config(self):
        """Test getting entire namespace configuration"""
        # Register test namespace
        test_ns = ConfigNamespace("test", "Test namespace")
        test_ns.add_var(EnvVar("TEST_VAR1", str, False, "value1"))
        test_ns.add_var(EnvVar("TEST_VAR2", int, False, 42))
        unified_env.register_namespace(test_ns)
        
        # Get namespace config
        config = unified_env.get_namespace_config("test")
        
        # Should be read-only MappingProxyType
        assert isinstance(config, MappingProxyType)
        assert config["var1"] == "value1"
        assert config["var2"] == 42
        
        # Should not be able to modify
        with pytest.raises(TypeError):
            config["var1"] = "modified"
    
    def test_required_variables(self):
        """Test required environment variables"""
        # Register required variable without default
        unified_env.register_var(
            EnvVar("TEST_REQUIRED", str, required=True),
            "test"
        )
        
        # Should raise error if not set
        with pytest.raises(ConfigurationError) as exc:
            unified_env.get("TEST_REQUIRED")
        assert "Required env var TEST_REQUIRED is not set" in str(exc.value)
    
    def test_default_values(self):
        """Test default values for optional variables"""
        # Register optional variable with default
        unified_env.register_var(
            EnvVar("TEST_OPTIONAL", str, required=False, default="default_value"),
            "test"
        )
        
        # Should return default if not set
        assert unified_env.get("TEST_OPTIONAL") == "default_value"
        
        # Should use env value if set
        os.environ["TEST_OPTIONAL"] = "custom_value"
        unified_env.clear_cache()
        assert unified_env.get("TEST_OPTIONAL") == "custom_value"
        
        del os.environ["TEST_OPTIONAL"]
    
    def test_cache_behavior(self):
        """Test configuration caching"""
        os.environ["TEST_CACHED"] = "initial"
        unified_env.register_var(EnvVar("TEST_CACHED", str), "test")
        
        # First access
        assert unified_env.get("TEST_CACHED") == "initial"
        
        # Change env var
        os.environ["TEST_CACHED"] = "changed"
        
        # Should still return cached value
        assert unified_env.get("TEST_CACHED") == "initial"
        
        # Clear cache and access again
        unified_env.clear_cache()
        assert unified_env.get("TEST_CACHED") == "changed"
        
        del os.environ["TEST_CACHED"]
    
    def test_validate_all(self):
        """Test full validation functionality"""
        # Register some variables
        unified_env.register_var(
            EnvVar("TEST_REQ1", str, required=True),
            "test"
        )
        unified_env.register_var(
            EnvVar("TEST_REQ2", str, required=True),
            "test"
        )
        unified_env.register_var(
            EnvVar("TEST_OPT", str, required=False, default="ok"),
            "test"
        )
        
        # Validation should fail
        errors = unified_env.validate(fail_fast=False)
        assert len(errors) == 2
        assert all("Required env var" in error for error in errors)
        
        # Set required vars
        os.environ["TEST_REQ1"] = "value1"
        os.environ["TEST_REQ2"] = "value2"
        
        # Validation should pass
        errors = unified_env.validate(fail_fast=False)
        assert len(errors) == 0
        
        # Cleanup
        del os.environ["TEST_REQ1"]
        del os.environ["TEST_REQ2"]
    
    def test_export_schema(self):
        """Test schema export functionality"""
        # Register test namespace
        test_ns = ConfigNamespace("test", "Test namespace")
        test_ns.add_var(EnvVar(
            "TEST_VAR",
            str,
            required=True,
            description="Test variable"
        ))
        unified_env.register_namespace(test_ns)
        
        # Export schema
        schema = unified_env.export_schema()
        
        assert "namespaces" in schema
        assert "test" in schema["namespaces"]
        assert schema["namespaces"]["test"]["description"] == "Test namespace"
        assert len(schema["namespaces"]["test"]["vars"]) == 1
        assert schema["namespaces"]["test"]["vars"][0]["name"] == "TEST_VAR"
        assert schema["namespaces"]["test"]["vars"][0]["type"] == "str"
        assert schema["namespaces"]["test"]["vars"][0]["required"] is True
    
    def test_convenience_functions(self):
        """Test convenience functions"""
        os.environ["TEST_CONV"] = "value"
        unified_env.register_var(EnvVar("TEST_CONV", str), "test")
        
        # get_env with default
        assert get_env("TEST_CONV") == "value"
        assert get_env("NONEXISTENT", "default") == "default"
        
        # require_env
        assert require_env("TEST_CONV") == "value"
        with pytest.raises(ConfigurationError):
            require_env("NONEXISTENT")
        
        del os.environ["TEST_CONV"]
    
    def test_reset_functionality(self):
        """Test reset functionality for testing/forking"""
        # Add some state
        unified_env.register_var(EnvVar("TEST_RESET", str), "test")
        unified_env.get("TERMINUS_DB_URL", "core")  # Cache something
        
        # Reset
        unified_env.reset()
        
        # State should be cleared
        assert len(unified_env._namespaces) == 0
        assert len(unified_env._cached_values) == 0
        assert unified_env._validated is False
        
        # Re-initialize for other tests
        unified_env._initialize_core()