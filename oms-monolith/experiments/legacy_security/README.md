# Legacy Security Modules

This directory contains legacy security modules that have been deprecated and replaced with more modern, performant alternatives.

## ultimate_killer.py

**Status**: DEPRECATED  
**Replaced by**: Multi-layer security approach using:
- `core.validation.input_sanitization.InputSanitizer` (PARANOID level)
- Pydantic model validators
- `middleware.unified_security_middleware.UnifiedSecurityMiddleware`

**Deprecation Reasons**:
1. **ReDoS Risk**: 150+ complex regex patterns posed Regular Expression Denial of Service vulnerability
2. **Performance**: CPU-intensive regex matching on every input
3. **False Positives**: Overly aggressive blocking leading to poor user experience
4. **Maintainability**: Single monolithic file with all patterns mixed together

**Migration Guide**:
See ADR-013 for detailed migration instructions and security coverage mapping.

**Note**: This file is preserved for reference and regression testing only. DO NOT use in production code.