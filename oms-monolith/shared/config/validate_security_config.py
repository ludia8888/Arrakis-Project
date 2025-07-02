#!/usr/bin/env python3
"""
Security configuration validation for life-critical OMS system
Ensures all security-critical environment variables meet requirements
"""

import sys
import os
from typing import List, Tuple
from shared.config.unified_env import unified_env, ConfigurationError


class SecurityValidationError(Exception):
    """Raised when security configuration fails validation"""
    pass


def validate_security_config() -> Tuple[bool, List[str]]:
    """
    Validate all security-critical configuration
    Returns: (success, list of errors)
    """
    errors = []
    
    # Security-critical variables that MUST be set and secure
    critical_vars = [
        "JWT_SECRET",
        "JWT_SECRET_KEY", 
        "PII_ENCRYPTION_KEY",
        "TERMINUS_DB_PASSWORD",
        "REDIS_PASSWORD"
    ]
    
    # Check each critical variable
    for var_name in critical_vars:
        try:
            value = unified_env.get(var_name)
            
            # Additional security checks
            if not value or value == "your-secret-key":
                errors.append(f"{var_name}: Using default/weak value in production")
            elif len(value) < 32:
                errors.append(f"{var_name}: Too short (min 32 chars required)")
            elif value.lower() in ["password", "secret", "12345", "admin", "test"]:
                errors.append(f"{var_name}: Common weak password detected")
                
        except ConfigurationError as e:
            errors.append(f"{var_name}: {str(e)}")
    
    # Check environment-specific requirements
    try:
        environment = unified_env.get("ENVIRONMENT")
        if environment.value in ["production", "staging"]:
            # Production/staging specific checks
            
            # JWKS should be enabled in production
            if not unified_env.get("JWT_JWKS_URL"):
                errors.append("JWT_JWKS_URL: Required for production environments")
            
            # Local validation should be disabled in production
            if unified_env.get("JWT_LOCAL_VALIDATION"):
                errors.append("JWT_LOCAL_VALIDATION: Should be False in production")
                
            # Check service URLs are HTTPS
            service_urls = [
                "USER_SERVICE_URL",
                "IAM_SERVICE_URL", 
                "AUDIT_SERVICE_URL"
            ]
            
            for url_var in service_urls:
                try:
                    url = unified_env.get(url_var)
                    if url and not url.startswith("https://"):
                        errors.append(f"{url_var}: Must use HTTPS in production")
                except ConfigurationError:
                    pass  # Optional URLs
                    
    except ConfigurationError as e:
        errors.append(f"ENVIRONMENT: {str(e)}")
    
    return len(errors) == 0, errors


def print_security_report(errors: List[str]):
    """Print security validation report"""
    print("=" * 80)
    print("SECURITY CONFIGURATION VALIDATION REPORT")
    print("=" * 80)
    
    if errors:
        print("\n❌ CRITICAL SECURITY ISSUES DETECTED:\n")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")
        print("\n⚠️  System is NOT secure for production use!")
        print("=" * 80)
    else:
        print("\n✅ All security checks PASSED")
        print("   System is properly configured for secure operation")
        print("=" * 80)


def main():
    """Main validation entry point"""
    success, errors = validate_security_config()
    
    if not success:
        print_security_report(errors)
        
        # Check if we're in production
        try:
            env = unified_env.get("ENVIRONMENT")
            if env.value in ["production", "staging"]:
                print("\n🚨 FATAL: Cannot start in production with security issues!")
                sys.exit(1)
            else:
                print("\n⚠️  WARNING: Security issues detected in development mode")
                print("   Fix these before deploying to production!")
        except:
            # If we can't even get environment, fail safe
            print("\n🚨 FATAL: Cannot determine environment - failing safe")
            sys.exit(1)
    else:
        print_security_report(errors)
        print("\n✅ Security configuration validated successfully")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())