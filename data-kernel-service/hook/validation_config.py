"""
Validation Configuration
Externalized validation rules and schema definitions
"""
import os
from typing import Dict, Any, Optional
from pathlib import Path


class ValidationConfig:
    """Configuration class for validation rules and schema definitions"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or os.getenv('VALIDATION_CONFIG_FILE')
        self._schemas = self._load_default_schemas()
        self._validation_settings = self._load_validation_settings()
        
        # Load custom config if provided
        if self.config_file and Path(self.config_file).exists():
            self._load_custom_config()
    
    def _load_default_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Load default schema definitions with configurable values"""
        
        # Load configurable limits from environment
        name_max_length = int(os.getenv('SCHEMA_NAME_MAX_LENGTH', '100'))
        description_max_length = int(os.getenv('SCHEMA_DESCRIPTION_MAX_LENGTH', '500'))
        branch_name_max_length = int(os.getenv('BRANCH_NAME_MAX_LENGTH', '100'))
        
        return {
            "ObjectType": {
                "required": ["name", "created_by", "created_at"],
                "properties": {
                    "name": {
                        "type": "string", 
                        "minLength": 1, 
                        "maxLength": name_max_length
                    },
                    "display_name": {
                        "type": "string", 
                        "maxLength": int(os.getenv('SCHEMA_DISPLAY_NAME_MAX_LENGTH', '200'))
                    },
                    "description": {
                        "type": "string", 
                        "maxLength": int(os.getenv('SCHEMA_DESCRIPTION_MAX_LENGTH', '1000'))
                    },
                    "created_by": {"type": "string", "minLength": 1},
                    "created_at": {"type": "string", "format": "datetime"},
                    "modified_by": {"type": "string"},
                    "modified_at": {"type": "string", "format": "datetime"},
                    "properties": {"type": "array", "items": {"type": "object"}},
                    "version_hash": {
                        "type": "string", 
                        "pattern": f"^[a-f0-9]{{{os.getenv('VERSION_HASH_LENGTH', '16')}}}$"
                    }
                }
            },
            "Branch": {
                "required": ["name", "created_by", "created_at"],
                "properties": {
                    "name": {
                        "type": "string", 
                        "pattern": f"^[a-zA-Z0-9_/-]+$", 
                        "maxLength": branch_name_max_length
                    },
                    "parent_branch": {"type": "string"},
                    "created_by": {"type": "string", "minLength": 1},
                    "created_at": {"type": "string", "format": "datetime"},
                    "is_protected": {"type": "boolean"},
                    "is_active": {"type": "boolean"},
                    "description": {
                        "type": "string", 
                        "maxLength": description_max_length
                    }
                }
            },
            "ValidationRule": {
                "required": ["name", "rule_type", "condition"],
                "properties": {
                    "name": {
                        "type": "string", 
                        "minLength": 1, 
                        "maxLength": name_max_length
                    },
                    "rule_type": {
                        "type": "string", 
                        "enum": self._get_rule_types()
                    },
                    "condition": {"type": "object"},
                    "severity": {
                        "type": "string", 
                        "enum": self._get_severity_levels()
                    },
                    "enabled": {"type": "boolean"},
                    "created_by": {"type": "string"},
                    "created_at": {"type": "string", "format": "datetime"}
                }
            },
            "AuditEvent": {
                "required": ["event_type", "user_id", "timestamp"],
                "properties": {
                    "event_type": {"type": "string", "minLength": 1},
                    "event_category": {"type": "string"},
                    "user_id": {"type": "string", "minLength": 1},
                    "username": {"type": "string"},
                    "timestamp": {"type": "string", "format": "datetime"},
                    "severity": {
                        "type": "string", 
                        "enum": self._get_audit_severity_levels()
                    },
                    "metadata": {"type": "object"}
                }
            }
        }
    
    def _get_rule_types(self) -> list:
        """Get configurable rule types"""
        default_types = ["schema", "business", "security"]
        custom_types = os.getenv('VALIDATION_RULE_TYPES', '').split(',')
        
        if custom_types and custom_types[0]:  # Check if not empty
            return [t.strip() for t in custom_types if t.strip()]
        return default_types
    
    def _get_severity_levels(self) -> list:
        """Get configurable severity levels"""
        default_levels = ["error", "warning", "info"]
        custom_levels = os.getenv('VALIDATION_SEVERITY_LEVELS', '').split(',')
        
        if custom_levels and custom_levels[0]:
            return [l.strip() for l in custom_levels if l.strip()]
        return default_levels
    
    def _get_audit_severity_levels(self) -> list:
        """Get configurable audit severity levels"""
        default_levels = ["INFO", "WARNING", "ERROR", "CRITICAL"]
        custom_levels = os.getenv('AUDIT_SEVERITY_LEVELS', '').split(',')
        
        if custom_levels and custom_levels[0]:
            return [l.strip() for l in custom_levels if l.strip()]
        return default_levels
    
    def _load_validation_settings(self) -> Dict[str, Any]:
        """Load general validation settings"""
        return {
            "strict_mode": os.getenv('VALIDATION_STRICT_MODE', 'false').lower() == 'true',
            "enable_custom_rules": os.getenv('ENABLE_CUSTOM_VALIDATION_RULES', 'true').lower() == 'true',
            "max_validation_errors": int(os.getenv('MAX_VALIDATION_ERRORS', '10')),
            "validation_timeout_seconds": float(os.getenv('VALIDATION_TIMEOUT_SECONDS', '30.0')),
            "enable_schema_caching": os.getenv('ENABLE_SCHEMA_CACHING', 'true').lower() == 'true',
            "schema_cache_ttl_seconds": int(os.getenv('SCHEMA_CACHE_TTL_SECONDS', '300'))
        }
    
    def _load_custom_config(self):
        """Load custom configuration from file"""
        import json
        try:
            with open(self.config_file, 'r') as f:
                custom_config = json.load(f)
                
            # Merge custom schemas
            if 'schemas' in custom_config:
                self._schemas.update(custom_config['schemas'])
            
            # Merge custom validation settings
            if 'validation_settings' in custom_config:
                self._validation_settings.update(custom_config['validation_settings'])
                
        except Exception as e:
            # Log error but don't fail - fall back to defaults
            import logging
            logging.getLogger(__name__).warning(f"Failed to load custom validation config: {e}")
    
    def get_schema(self, doc_type: str) -> Optional[Dict[str, Any]]:
        """Get schema definition for document type"""
        return self._schemas.get(doc_type)
    
    def get_setting(self, setting_name: str, default=None):
        """Get validation setting value"""
        return self._validation_settings.get(setting_name, default)
    
    def get_all_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Get all schema definitions"""
        return self._schemas.copy()
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all validation settings"""
        return self._validation_settings.copy()


# Global configuration instance
validation_config = ValidationConfig()


# Convenience functions for backward compatibility
def get_default_schema(doc_type: str) -> Optional[Dict[str, Any]]:
    """Get default schema definition for document type"""
    return validation_config.get_schema(doc_type)


def get_validation_setting(setting_name: str, default=None):
    """Get validation setting value"""
    return validation_config.get_setting(setting_name, default)