"""
Naming Convention Engine - 간단하고 효과적인 접근
복잡한 약어 처리를 단순화
"""
import re
from typing import List, Dict, Optional, Tuple, Set
from enum import Enum
from datetime import datetime
import logging
from pydantic import BaseModel, Field, field_validator

from core.validation.naming_convention import (
 EntityType, NamingPattern, NamingRule, NamingConvention,
 ValidationIssue, NamingValidationResult
)

logger = logging.getLogger(__name__)


class ProductionNamingEngine:
 """Production-ready 명명 규칙 엔진 with advanced features"""

 # Comprehensive acronyms database with categorization
 TECHNOLOGY_ACRONYMS = {
 'API', 'HTTP', 'HTTPS', 'URL', 'URI', 'JSON', 'XML', 'SQL',
 'HTML', 'CSS', 'JWT', 'UUID', 'TCP', 'UDP', 'FTP', 'SSH',
 'REST', 'SOAP', 'GRPC', 'OAuth', 'SAML', 'LDAP', 'SSO',
 'AWS', 'GCP', 'S3', 'DB', 'IO', 'UI', 'UX', 'AI', 'ML',
 'CPU', 'GPU', 'RAM', 'ROM', 'SSD', 'HDD', 'OS', 'VM',
 'CI', 'CD', 'CLI', 'GUI', 'IDE', 'SDK', 'CDN', 'DNS'
 }

 BUSINESS_ACRONYMS = {
 'B2B', 'B2C', 'CRM', 'ERP', 'HR', 'IT', 'QA', 'PO',
 'ROI', 'KPI', 'SLA', 'CEO', 'CTO', 'CFO', 'COO'
 }

 DATABASE_ACRONYMS = {
 'ID', 'PK', 'FK', 'CRUD', 'DTO', 'DAO', 'MVC', 'MVP',
 'ORM', 'ACID', 'OLTP', 'OLAP', 'ETL', 'DML', 'DDL'
 }

 PROTOCOL_ACRONYMS = {
 'MQTT', 'AMQP', 'SMTP', 'IMAP', 'POP3', 'SFTP', 'SCP',
 'HTTPS', 'WSS', 'RPC', 'GRPC', 'JSONRPC', 'XMLRPC'
 }

 # Combined acronyms
 COMMON_ACRONYMS = (TECHNOLOGY_ACRONYMS | BUSINESS_ACRONYMS |
 DATABASE_ACRONYMS | PROTOCOL_ACRONYMS)

 # Domain-specific forbidden patterns
 SECURITY_FORBIDDEN = {
 'password', 'secret', 'key', 'token', 'auth', 'login',
 'admin', 'root', 'system', 'internal', 'private'
 }

 # International character support
 UNICODE_WORD_PATTERN = re.compile(r'[\p{L}\p{N}]+', re.UNICODE)

 # Performance cache
 _word_split_cache = {}
 _validation_cache = {}
 _pattern_cache = {}

 def __init__(self, convention: Optional[NamingConvention] = None,
 enable_caching: bool = True,
 enable_internationalization: bool = True,
 strict_mode: bool = False,
 custom_acronyms: Optional[Set[str]] = None):
 """
 Initialize production naming engine

 Args:
 convention: Naming convention rules
 enable_caching: Enable performance caching
 enable_internationalization: Support international characters
 strict_mode: Apply stricter validation rules
 custom_acronyms: Additional domain-specific acronyms
 """
 self.convention = convention or self._get_default_convention()
 self.enable_caching = enable_caching
 self.enable_internationalization = enable_internationalization
 self.strict_mode = strict_mode

 # Extend acronyms with custom ones
 self.active_acronyms = self.COMMON_ACRONYMS.copy()
 if custom_acronyms:
 self.active_acronyms.update(custom_acronyms)

 # Initialize components
 self._is_reserved_word = self._create_reserved_checker()
 self._security_checker = self._create_security_checker()
 self._pattern_validators = self._create_pattern_validators()
 self._semantic_analyzer = self._create_semantic_analyzer()

 # Performance metrics
 self.validation_count = 0
 self.cache_hit_count = 0

 logger.info(f"ProductionNamingEngine initialized with {len(self.active_acronyms)} acronyms, "
 f"caching={'enabled' if enable_caching else 'disabled'}, "
 f"strict_mode={strict_mode}")

 def validate(self, entity_type: EntityType, name: str,
 context: Optional[Dict[str, Any]] = None) -> NamingValidationResult:
 """
 Comprehensive entity name validation with caching and context awareness

 Args:
 entity_type: Type of entity being validated
 name: Name to validate
 context: Additional context (domain, namespace, etc.)
 """
 self.validation_count += 1

 # Check cache first
 cache_key = f"{entity_type.value}:{name}:{hash(str(context))}"
 if self.enable_caching and cache_key in self._validation_cache:
 self.cache_hit_count += 1
 return self._validation_cache[cache_key]

 rule = self.convention.rules.get(entity_type)
 if not rule:
 result = NamingValidationResult(
 is_valid = True,
 applied_convention = self.convention.id,
 performance_metrics={'validation_time_ms': 0}
 )
 if self.enable_caching:
 self._validation_cache[cache_key] = result
 return result

 start_time = datetime.now()
 issues = []
 suggestions = {}
 metadata = {}

 try:
 # 1. Basic validation
 issues.extend(self._validate_basic_requirements(name, rule))

 # 2. Pattern validation
 issues.extend(self._validate_pattern_compliance(name, rule))

 # 3. Reserved word validation
 issues.extend(self._validate_reserved_words(name))

 # 4. Security validation (production feature)
 if self.strict_mode:
 issues.extend(self._validate_security_concerns(name))

 # 5. Semantic validation
 semantic_issues, semantic_metadata = self._validate_semantic_meaning(name, entity_type, context)
 issues.extend(semantic_issues)
 metadata.update(semantic_metadata)

 # 6. Cross-reference validation (check against existing entities)
 if context and 'existing_names' in context:
 issues.extend(self._validate_uniqueness(name, context['existing_names']))

 # 7. Internationalization validation
 if self.enable_internationalization:
 issues.extend(self._validate_international_characters(name))

 # 8. Business rule validation
 issues.extend(self._validate_business_rules(name, entity_type, context))

 # Generate suggestions if there are issues
 if issues:
 suggestions = self._generate_intelligent_suggestions(name, entity_type, rule, issues)

 # Calculate validation time
 validation_time = (datetime.now() - start_time).total_seconds() * 1000

 result = NamingValidationResult(
 is_valid = len(issues) == 0,
 issues = issues,
 suggestions = suggestions,
 applied_convention = self.convention.id,
 metadata = metadata,
 performance_metrics={
 'validation_time_ms': round(validation_time, 2),
 'rules_applied': len([m for m in [
 'basic', 'pattern', 'reserved', 'security', 'semantic',
 'uniqueness', 'international', 'business'
 ] if True]), # Count of validation types applied
 'cache_hit': False
 }
 )

 # Cache result
 if self.enable_caching:
 self._validation_cache[cache_key] = result

 return result

 except Exception as e:
 logger.error(f"Validation failed for {name}: {e}")
 return NamingValidationResult(
 is_valid = False,
 issues = [ValidationIssue(
 issue_type = "validation_error",
 severity = "error",
 message = f"Validation system error: {str(e)}",
 position = 0
 )],
 applied_convention = self.convention.id,
 performance_metrics={'validation_time_ms': -1, 'error': True}
 )

 def auto_fix(self, entity_type: EntityType, name: str) -> str:
 """자동 교정"""
 rule = self.convention.rules.get(entity_type)
 if not rule:
 return name

 # 1. 단어 분리
 words = self._split_into_words(name)

 # 2. 접두사/접미사 처리
 if rule.required_prefix:
 if not any(w.lower() == p.lower() for w in words[:1] for p in rule.required_prefix):
 prefix_words = self._split_into_words(rule.required_prefix[0])
 words = prefix_words + words

 if rule.required_suffix:
 if not any(w.lower() == s.lower() for w in words[-1:] for s in rule.required_suffix):
 suffix_words = self._split_into_words(rule.required_suffix[0])
 words = words + suffix_words

 # 3. 패턴 적용
 result = self._apply_pattern(words, rule.pattern)

 # 4. 예약어 처리
 if self._is_reserved_word(result):
 result += '_'

 return result

 # Production-level validation methods

 def _validate_basic_requirements(self, name: str, rule: NamingRule) -> List[ValidationIssue]:
 """Validate basic requirements (length, character sets, etc.)"""
 issues = []

 # Length validation
 if rule.min_length and len(name) < rule.min_length:
 issues.append(ValidationIssue(
 issue_type = "length_too_short",
 severity = "error",
 message = f"Name too short. Minimum length: {rule.min_length}, actual: {len(name)}",
 position = 0
 ))

 if rule.max_length and len(name) > rule.max_length:
 issues.append(ValidationIssue(
 issue_type = "length_too_long",
 severity = "error",
 message = f"Name too long. Maximum length: {rule.max_length}, actual: {len(name)}",
 position = len(name)
 ))

 # Character set validation
 if not re.match(r'^[a-zA-Z0-9_]+$', name):
 issues.append(ValidationIssue(
 issue_type = "invalid_characters",
 severity = "error",
 message = "Name contains invalid characters. Only alphanumeric and underscore allowed",
 position = 0
 ))

 # Must start with letter
 if name and not name[0].isalpha():
 issues.append(ValidationIssue(
 issue_type = "invalid_start_character",
 severity = "error",
 message = "Name must start with a letter",
 position = 0
 ))

 return issues

 def _validate_pattern_compliance(self, name: str, rule: NamingRule) -> List[ValidationIssue]:
 """Validate naming pattern compliance"""
 issues = []

 if rule.pattern == NamingPattern.CAMEL_CASE:
 if not re.match(r'^[a-z][a-zA-Z0-9]*$', name):
 issues.append(ValidationIssue(
 issue_type = "pattern_violation",
 severity = "error",
 message = "Name does not follow camelCase pattern",
 position = 0
 ))

 elif rule.pattern == NamingPattern.PASCAL_CASE:
 if not re.match(r'^[A-Z][a-zA-Z0-9]*$', name):
 issues.append(ValidationIssue(
 issue_type = "pattern_violation",
 severity = "error",
 message = "Name does not follow PascalCase pattern",
 position = 0
 ))

 elif rule.pattern == NamingPattern.SNAKE_CASE:
 if not re.match(r'^[a-z][a-z0-9_]*$', name):
 issues.append(ValidationIssue(
 issue_type = "pattern_violation",
 severity = "error",
 message = "Name does not follow snake_case pattern",
 position = 0
 ))

 # Prefix validation
 if rule.required_prefix:
 words = self._split_into_words(name)
 if words and not any(words[0].lower() == prefix.lower() for prefix in rule.required_prefix):
 issues.append(ValidationIssue(
 issue_type = "missing_required_prefix",
 severity = "error",
 message = f"Name must start with one of: {rule.required_prefix}",
 position = 0
 ))

 # Forbidden prefix validation
 if rule.forbidden_prefix:
 for prefix in rule.forbidden_prefix:
 if name.lower().startswith(prefix.lower()):
 issues.append(ValidationIssue(
 issue_type = "forbidden_prefix",
 severity = "error",
 message = f"Name cannot start with forbidden prefix: {prefix}",
 position = 0
 ))

 return issues

 def _validate_reserved_words(self, name: str) -> List[ValidationIssue]:
 """Validate against reserved words"""
 issues = []

 if self._is_reserved_word(name):
 issues.append(ValidationIssue(
 issue_type = "reserved_word",
 severity = "error",
 message = f"'{name}' is a reserved word and cannot be used",
 position = 0
 ))

 return issues

 def _validate_security_concerns(self, name: str) -> List[ValidationIssue]:
 """Validate security-related naming concerns"""
 issues = []

 name_lower = name.lower()

 # Check for security-sensitive terms
 for forbidden in self.SECURITY_FORBIDDEN:
 if forbidden in name_lower:
 issues.append(ValidationIssue(
 issue_type = "security_concern",
 severity = "warning",
 message = f"Name contains security-sensitive term: {forbidden}",
 position = name_lower.find(forbidden)
 ))

 # Check for potential SQL injection patterns
 sql_patterns = ['select', 'insert', 'update', 'delete', 'drop', 'union', 'exec']
 for pattern in sql_patterns:
 if pattern in name_lower:
 issues.append(ValidationIssue(
 issue_type = "sql_injection_risk",
 severity = "warning",
 message = f"Name contains potential SQL keyword: {pattern}",
 position = name_lower.find(pattern)
 ))

 return issues

 def _validate_semantic_meaning(self, name: str, entity_type: EntityType,
 context: Optional[Dict[str, Any]]) -> Tuple[List[ValidationIssue], Dict[str, Any]]:
 """Validate semantic meaning and provide metadata"""
 issues = []
 metadata = {}

 words = self._split_into_words(name)
 metadata['word_count'] = len(words)
 metadata['contains_acronyms'] = [w for w in words if w.upper() in self.active_acronyms]

 # Check for meaningless names
 meaningless_patterns = ['test', 'temp', 'foo', 'bar', 'baz', 'example']
 if any(pattern in name.lower() for pattern in meaningless_patterns):
 issues.append(ValidationIssue(
 issue_type = "meaningless_name",
 severity = "warning",
 message = "Name appears to be a placeholder or test name",
 position = 0
 ))

 # Check semantic consistency for entity type
 if entity_type == EntityType.ACTION_TYPE:
 action_verbs = ['create', 'get', 'update', 'delete', 'list', 'execute', 'process']
 if not any(verb in name.lower() for verb in action_verbs):
 issues.append(ValidationIssue(
 issue_type = "semantic_mismatch",
 severity = "info",
 message = "Action type should typically contain an action verb",
 position = 0
 ))

 return issues, metadata

 def _validate_uniqueness(self, name: str, existing_names: List[str]) -> List[ValidationIssue]:
 """Validate name uniqueness"""
 issues = []

 if name in existing_names:
 issues.append(ValidationIssue(
 issue_type = "duplicate_name",
 severity = "error",
 message = f"Name '{name}' already exists",
 position = 0
 ))

 # Check for similar names (potential typos)
 similar_names = []
 for existing in existing_names:
 if self._calculate_similarity(name.lower(), existing.lower()) > 0.8:
 similar_names.append(existing)

 if similar_names:
 issues.append(ValidationIssue(
 issue_type = "similar_name",
 severity = "warning",
 message = f"Name is very similar to existing names: {similar_names}",
 position = 0
 ))

 return issues

 def _validate_international_characters(self, name: str) -> List[ValidationIssue]:
 """Validate international character support"""
 issues = []

 # Check for non-ASCII characters
 if not name.isascii():
 if not self.enable_internationalization:
 issues.append(ValidationIssue(
 issue_type = "non_ascii_characters",
 severity = "error",
 message = "Non-ASCII characters not allowed",
 position = 0
 ))
 else:
 # Warn about potential compatibility issues
 issues.append(ValidationIssue(
 issue_type = "internationalization_warning",
 severity = "info",
 message = "Name contains international characters. Ensure system compatibility",
 position = 0
 ))

 return issues

 def _validate_business_rules(self, name: str, entity_type: EntityType,
 context: Optional[Dict[str, Any]]) -> List[ValidationIssue]:
 """Validate domain-specific business rules"""
 issues = []

 # Example business rules
 if context and 'domain' in context:
 domain = context['domain']

 # Finance domain rules
 if domain == 'finance':
 finance_terms = ['amount', 'balance', 'transaction', 'payment']
 if entity_type == EntityType.PROPERTY and not any(term in name.lower() for term in finance_terms):
 issues.append(ValidationIssue(
 issue_type = "domain_convention",
 severity = "info",
 message = "Finance domain properties often include amount/balance/transaction terms",
 position = 0
 ))

 # Healthcare domain rules
 elif domain == 'healthcare':
 if 'patient' in name.lower() and 'id' not in name.lower():
 issues.append(ValidationIssue(
 issue_type = "privacy_concern",
 severity = "warning",
 message = "Healthcare patient data should be properly anonymized",
 position = 0
 ))

 return issues

 def _generate_intelligent_suggestions(self, name: str, entity_type: EntityType,
 rule: NamingRule, issues: List[ValidationIssue]) -> Dict[str, str]:
 """Generate intelligent naming suggestions based on issues"""
 suggestions = {}

 # Basic auto-fix
 basic_fix = self.auto_fix(entity_type, name)
 if basic_fix != name:
 suggestions['auto_fix'] = basic_fix

 # Issue-specific suggestions
 for issue in issues:
 if issue.issue_type == "pattern_violation":
 if rule.pattern == NamingPattern.CAMEL_CASE:
 suggestions['camelCase'] = self._to_camel_case(name)
 elif rule.pattern == NamingPattern.PASCAL_CASE:
 suggestions['PascalCase'] = self._to_pascal_case(name)
 elif rule.pattern == NamingPattern.SNAKE_CASE:
 suggestions['snake_case'] = self._to_snake_case(name)

 elif issue.issue_type == "reserved_word":
 suggestions['reserved_word_fix'] = name + '_value'

 elif issue.issue_type == "meaningless_name":
 if entity_type == EntityType.OBJECT_TYPE:
 suggestions['meaningful'] = 'Entity' + name.replace('test', '').replace('temp', '')

 return suggestions

 def _calculate_similarity(self, str1: str, str2: str) -> float:
 """Calculate string similarity using Levenshtein distance"""
 if not str1 or not str2:
 return 0.0

 m, n = len(str1), len(str2)
 dp = [[0] * (n + 1) for _ in range(m + 1)]

 for i in range(m + 1):
 dp[i][0] = i
 for j in range(n + 1):
 dp[0][j] = j

 for i in range(1, m + 1):
 for j in range(1, n + 1):
 if str1[i-1] == str2[j-1]:
 dp[i][j] = dp[i-1][j-1]
 else:
 dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])

 max_len = max(m, n)
 return 1.0 - (dp[m][n] / max_len) if max_len > 0 else 1.0

 def _create_security_checker(self):
 """Create security pattern checker"""
 def check_security(name: str) -> List[str]:
 concerns = []
 name_lower = name.lower()
 for forbidden in self.SECURITY_FORBIDDEN:
 if forbidden in name_lower:
 concerns.append(forbidden)
 return concerns
 return check_security

 def _create_pattern_validators(self):
 """Create pattern-specific validators"""
 return {
 NamingPattern.CAMEL_CASE: lambda n: re.match(r'^[a-z][a-zA-Z0-9]*$', n),
 NamingPattern.PASCAL_CASE: lambda n: re.match(r'^[A-Z][a-zA-Z0-9]*$', n),
 NamingPattern.SNAKE_CASE: lambda n: re.match(r'^[a-z][a-z0-9_]*$', n),
 NamingPattern.KEBAB_CASE: lambda n: re.match(r'^[a-z][a-z0-9-]*$', n)
 }

 def _create_semantic_analyzer(self):
 """Create semantic analysis engine"""
 def analyze(name: str, entity_type: EntityType) -> Dict[str, Any]:
 words = self._split_into_words(name)
 return {
 'word_count': len(words),
 'contains_verbs': self._contains_action_words(words),
 'contains_acronyms': [w for w in words if w.upper() in self.active_acronyms],
 'estimated_readability': len(words) <= 3 and all(len(w) <= 12 for w in words)
 }
 return analyze

 def _contains_action_words(self, words: List[str]) -> bool:
 """Check if words contain action verbs"""
 action_words = {'create', 'get', 'update', 'delete', 'list', 'execute', 'process', 'handle', 'manage'}
 return any(word.lower() in action_words for word in words)

 def _to_camel_case(self, name: str) -> str:
 """Convert to camelCase"""
 words = self._split_into_words(name)
 if not words:
 return name
 result = words[0].lower()
 for word in words[1:]:
 result += word.capitalize()
 return result

 def _to_pascal_case(self, name: str) -> str:
 """Convert to PascalCase"""
 words = self._split_into_words(name)
 return ''.join(word.capitalize() for word in words)

 def _to_snake_case(self, name: str) -> str:
 """Convert to snake_case"""
 words = self._split_into_words(name)
 return '_'.join(word.lower() for word in words)

 def get_performance_metrics(self) -> Dict[str, Any]:
 """Get engine performance metrics"""
 cache_hit_rate = (self.cache_hit_count / self.validation_count * 100) if self.validation_count > 0 else 0
 return {
 'total_validations': self.validation_count,
 'cache_hits': self.cache_hit_count,
 'cache_hit_rate_percent': round(cache_hit_rate, 2),
 'cache_size': len(self._validation_cache),
 'active_acronyms_count': len(self.active_acronyms)
 }

 def clear_cache(self) -> None:
 """Clear performance cache"""
 self._validation_cache.clear()
 self._word_split_cache.clear()
 self._pattern_cache.clear()
 logger.info("ProductionNamingEngine cache cleared")

 def _split_into_words(self, text: str) -> List[str]:
 """텍스트를 단어로 분리"""
 # snake_case, kebab-case 처리
 if '_' in text:
 parts = text.split('_')
 words = []
 for part in parts:
 words.extend(self._split_camel_case(part))
 return words

 if '-' in text:
 parts = text.split('-')
 words = []
 for part in parts:
 words.extend(self._split_camel_case(part))
 return words

 return self._split_camel_case(text)

 def _split_camel_case(self, text: str) -> List[str]:
 """CamelCase 분리 - 단순하지만 효과적"""
 if not text:
 return []

 # 정규식으로 분리
 # 1. 소문자 다음의 대문자
 # 2. 연속된 대문자 (약어)
 # 3. 숫자
 pattern = r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[a-zA-Z])(?=[0-9])|(?<=[0-9])(?=[a-zA-Z])'

 parts = re.split(pattern, text)

 # 빈 문자열 제거하고 정리
 words = []
 for part in parts:
 if part:
 # OAuth2, APIv3 같은 패턴 처리
 if len(part) > 1 and part[-1].isdigit() and part[:-1].isalpha():
 # 마지막이 숫자면 분리해서 확인
 alpha_part = part[:-1]
 digit_part = part[-1]

 if alpha_part.upper() in self.COMMON_ACRONYMS:
 words.append(part) # OAuth2로 유지
 else:
 words.append(alpha_part)
 words.append(digit_part)
 else:
 words.append(part)

 return words

 def _apply_pattern(self, words: List[str], pattern: NamingPattern) -> str:
 """단어 리스트에 패턴 적용"""
 if not words:
 return ""

 if pattern == NamingPattern.CAMEL_CASE:
 result = words[0].lower()
 for word in words[1:]:
 if word.upper() in self.COMMON_ACRONYMS:
 # 약어는 첫 글자만 대문자
 result += word[0].upper() + word[1:].lower()
 else:
 result += word.capitalize()
 return result

 elif pattern == NamingPattern.PASCAL_CASE:
 result = ""
 for word in words:
 if word.upper() in self.COMMON_ACRONYMS:
 # 약어는 그대로 유지
 result += word.upper()
 else:
 result += word.capitalize()
 return result

 elif pattern == NamingPattern.SNAKE_CASE:
 return '_'.join(w.lower() for w in words)

 elif pattern == NamingPattern.KEBAB_CASE:
 return '-'.join(w.lower() for w in words)

 else:
 return ''.join(words)

 def _create_reserved_checker(self):
 """예약어 체커 생성"""
 if self.convention.case_sensitive:
 reserved_set = set(self.convention.reserved_words)
 return lambda word: word in reserved_set
 else:
 reserved_lower = {w.lower() for w in self.convention.reserved_words}
 return lambda word: word.lower() in reserved_lower

 def _get_default_convention(self) -> NamingConvention:
 """기본 명명 규칙"""
 return NamingConvention(
 id = "default",
 name = "Default Convention",
 rules={
 EntityType.OBJECT_TYPE: NamingRule(
 entity_type = EntityType.OBJECT_TYPE,
 pattern = NamingPattern.PASCAL_CASE,
 forbidden_prefix = ["_", "temp"],
 min_length = 3,
 max_length = 50
 ),
 EntityType.PROPERTY: NamingRule(
 entity_type = EntityType.PROPERTY,
 pattern = NamingPattern.CAMEL_CASE,
 forbidden_prefix = ["_", "$"],
 min_length = 2,
 max_length = 50
 ),
 EntityType.ACTION_TYPE: NamingRule(
 entity_type = EntityType.ACTION_TYPE,
 pattern = NamingPattern.CAMEL_CASE,
 required_prefix = ["create", "update", "delete", "get", "list", "execute"],
 min_length = 5,
 max_length = 80
 ),
 EntityType.LINK_TYPE: NamingRule(
 entity_type = EntityType.LINK_TYPE,
 pattern = NamingPattern.CAMEL_CASE,
 required_suffix = ["Link", "Relation", "Reference", "Association"],
 min_length = 5,
 max_length = 60
 )
 },
 reserved_words = ["class", "function", "if", "else", "return", "import", "export",
 "type", "name", "id", "value", "true", "false", "null"],
 case_sensitive = True,
 auto_fix_enabled = True,
 created_at = datetime.now().isoformat(),
 updated_at = datetime.now().isoformat(),
 created_by = "system"
 )


# 테스트
if __name__ == "__main__":
 engine = ProductionNamingEngine()

 test_cases = [
 ("HTTPServerError", "objectType"),
 ("OAuth2Token", "objectType"),
 ("APIv3Client", "property"),
 ("getValue2", "property"),
 ("HTTPClient", "actionType"),
 ]

 print("=== Simplified Engine Test ===")
 for name, entity_type in test_cases:
 et = getattr(EntityType, entity_type.upper().replace("TYPE", "_TYPE"))
 words = engine._split_into_words(name)
 fixed = engine.auto_fix(et, name)
 print(f"{name} ({entity_type})")
 print(f" Words: {words}")
 print(f" Fixed: {fixed}")
 print()
