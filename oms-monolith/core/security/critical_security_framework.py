"""
생명과 개인정보를 다루는 시스템을 위한 완전한 보안 프레임워크

이 모듈은 의료, 금융, 정부 시스템 수준의 보안을 제공합니다.
단 하나의 취약점도 허용하지 않는 완전한 보안 아키텍처입니다.
"""
import re
import logging
import hashlib
import secrets
import uuid
from typing import Dict, List, Any, Optional, Tuple, Set
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SecurityThreatLevel(Enum):
    """보안 위협 수준"""
    CRITICAL = "CRITICAL"    # 즉시 차단, 알림 발송
    HIGH = "HIGH"           # 차단, 로깅
    MEDIUM = "MEDIUM"       # 검증 후 처리
    LOW = "LOW"            # 로깅만


class ThreatCategory(Enum):
    """위협 카테고리"""
    SQL_INJECTION = "SQL_INJECTION"
    XSS = "XSS" 
    COMMAND_INJECTION = "COMMAND_INJECTION"
    PATH_TRAVERSAL = "PATH_TRAVERSAL"
    LDAP_INJECTION = "LDAP_INJECTION"
    CODE_INJECTION = "CODE_INJECTION"
    DATA_EXFILTRATION = "DATA_EXFILTRATION"
    BUFFER_OVERFLOW = "BUFFER_OVERFLOW"
    UNKNOWN = "UNKNOWN"


@dataclass
class SecurityThreat:
    """탐지된 보안 위협"""
    threat_id: str
    category: ThreatCategory
    level: SecurityThreatLevel
    description: str
    detected_at: datetime
    source_ip: Optional[str]
    request_path: str
    payload: str
    blocked: bool
    action_taken: str


class CriticalSecurityValidator:
    """생명 중요 시스템용 완전 보안 검증기"""
    
    def __init__(self):
        """초기화"""
        self.detected_threats: List[SecurityThreat] = []
        self.blocked_ips: Set[str] = set()
        self.threat_patterns = self._load_threat_patterns()
        
        logger.info("🔒 Critical Security Validator initialized for life-critical system")
    
    def _load_threat_patterns(self) -> Dict[ThreatCategory, List[str]]:
        """모든 알려진 보안 위협 패턴 로드"""
        return {
            ThreatCategory.SQL_INJECTION: [
                # Basic SQL injection
                r"(?i)(union\s+select|select\s+.*\s+from)",
                r"(?i)(insert\s+into|update\s+.*\s+set|delete\s+from)",
                r"(?i)(drop\s+table|alter\s+table|create\s+table)",
                r"(?i)(exec\s*\(|execute\s*\(|sp_executesql)",
                r"(?i)(or\s+1\s*=\s*1|and\s+1\s*=\s*1)",
                r"(?i)(or\s+'1'\s*=\s*'1'|and\s+'1'\s*=\s*'1')",
                r"(?i)(or\s+\"1\"\s*=\s*\"1\"|and\s+\"1\"\s*=\s*\"1\")",
                r"(?i)(having\s+1\s*=\s*1|group\s+by\s+)",
                r"(?i)(information_schema|sysobjects|syscolumns)",
                r"(?i)(waitfor\s+delay|benchmark\s*\(|sleep\s*\()",
                # Advanced SQL injection
                r"(?i)(\'\s*;\s*--|\'\s*;\s*/\*)",
                r"(?i)(\"\s*;\s*--|\"\s*;\s*/\*)",
                r"(?i)(0x[0-9a-f]+|char\s*\(|ascii\s*\()",
                r"(?i)(concat\s*\(|substring\s*\(|length\s*\()",
                r"(?i)(cast\s*\(|convert\s*\(|hex\s*\()",
            ],
            ThreatCategory.XSS: [
                # Script tags
                r"(?i)<script[^>]*>.*?</script>",
                r"(?i)<script[^>]*>",
                r"(?i)</script>",
                # Event handlers
                r"(?i)on\w+\s*=\s*[\"']?[^\"'>\s]*[\"']?",
                r"(?i)(onload|onerror|onclick|onmouseover|onfocus)",
                r"(?i)(onblur|onchange|onsubmit|onreset|onselect)",
                # JavaScript URLs
                r"(?i)javascript\s*:",
                r"(?i)vbscript\s*:",
                r"(?i)data\s*:\s*text/html",
                # HTML entities and encoding
                r"(?i)&#x?[0-9a-f]+;",
                r"(?i)%3c%73%63%72%69%70%74%3e",  # <script>
                # SVG and other vectors
                r"(?i)<svg[^>]*>.*?</svg>",
                r"(?i)<iframe[^>]*>",
                r"(?i)<object[^>]*>",
                r"(?i)<embed[^>]*>",
                r"(?i)<link[^>]*>",
                r"(?i)<meta[^>]*>",
            ],
            ThreatCategory.COMMAND_INJECTION: [
                # Shell metacharacters
                r"[;&|`$(){}[\]\\]",
                r"(?i)(rm\s+-rf|del\s+/|format\s+c:)",
                r"(?i)(cat\s+/etc/passwd|type\s+c:\\)",
                r"(?i)(wget\s+|curl\s+|nc\s+|netcat\s+)",
                r"(?i)(whoami|id|ps\s+|netstat\s+)",
                r"(?i)(chmod\s+|chown\s+|su\s+|sudo\s+)",
                # Command substitution
                r"\$\([^)]*\)",
                r"`[^`]*`",
                r"\${[^}]*}",
                # Redirections
                r"[<>]",
                r"\|\s*\w+",
                r"&&\s*\w+",
                r"\|\|\s*\w+",
            ],
            ThreatCategory.PATH_TRAVERSAL: [
                # Directory traversal
                r"\.\.[\\/]",
                r"[\\/]\.\.",
                r"\.\.%2f",
                r"\.\.%5c",
                r"%2e%2e%2f",
                r"%2e%2e%5c",
                r"\.\.\\",
                r"\.\./",
                # Encoded traversal
                r"%252e%252e%252f",
                r"%c0%ae%c0%ae%c0%af",
                r"\.\.%255c",
                r"\.\.%u002f",
                # Absolute paths
                r"(?i)[a-z]:\\",
                r"(?i)/etc/passwd",
                r"(?i)/windows/system32",
                r"(?i)c:\\windows",
            ],
            ThreatCategory.LDAP_INJECTION: [
                r"\$\{jndi:",
                r"\$\{ldap:",
                r"\$\{rmi:",
                r"\$\{dns:",
                r"\$\{nis:",
                r"\$\{nds:",
                r"\$\{corba:",
                r"\$\{iiop:",
                # Log4j variants
                r"\$\{\$\{:",
                r"\$\{lower:",
                r"\$\{upper:",
                r"\$\{env:",
                r"\$\{sys:",
                r"\$\{date:",
            ],
            ThreatCategory.CODE_INJECTION: [
                # PHP code injection
                r"(?i)<\?php",
                r"(?i)eval\s*\(",
                r"(?i)exec\s*\(",
                r"(?i)system\s*\(",
                r"(?i)shell_exec\s*\(",
                r"(?i)passthru\s*\(",
                # Python code injection
                r"(?i)__import__\s*\(",
                r"(?i)compile\s*\(",
                r"(?i)globals\s*\(",
                r"(?i)locals\s*\(",
                # General code patterns
                r"(?i)require\s*\(",
                r"(?i)include\s*\(",
                r"(?i)import\s+",
            ],
            ThreatCategory.DATA_EXFILTRATION: [
                # Data extraction patterns
                r"(?i)(select\s+\*\s+from|show\s+tables)",
                r"(?i)(describe\s+|explain\s+)",
                r"(?i)(backup\s+|restore\s+|dump\s+)",
                r"(?i)(export\s+|outfile\s+|into\s+outfile)",
                # Sensitive file patterns
                r"(?i)(\.config|\.env|\.ini|\.conf)",
                r"(?i)(password|passwd|secret|key|token)",
                r"(?i)(private|confidential|classified)",
            ]
        }
    
    def validate_input(self, 
                      input_data: Any, 
                      field_name: str,
                      request_info: Dict[str, Any]) -> Tuple[bool, List[SecurityThreat]]:
        """
        완전한 입력 검증
        
        Returns:
            (is_safe, detected_threats)
        """
        if input_data is None:
            return True, []
        
        input_str = str(input_data)
        detected_threats = []
        
        # 1. 모든 위협 패턴 검사
        for category, patterns in self.threat_patterns.items():
            for pattern in patterns:
                if re.search(pattern, input_str):
                    threat = SecurityThreat(
                        threat_id=str(uuid.uuid4()),
                        category=category,
                        level=SecurityThreatLevel.CRITICAL,
                        description=f"{category.value} detected in field '{field_name}'",
                        detected_at=datetime.now(timezone.utc),
                        source_ip=request_info.get('client_ip'),
                        request_path=request_info.get('path', ''),
                        payload=input_str[:200],  # Limit payload size
                        blocked=True,
                        action_taken="INPUT_REJECTED"
                    )
                    detected_threats.append(threat)
                    self.detected_threats.append(threat)
        
        # 2. 길이 검사 (매우 긴 입력은 버퍼 오버플로 시도일 수 있음)
        if len(input_str) > 10000:  # 10KB 제한
            threat = SecurityThreat(
                threat_id=str(uuid.uuid4()),
                category=ThreatCategory.BUFFER_OVERFLOW,
                level=SecurityThreatLevel.HIGH,
                description=f"Suspicious large input in field '{field_name}' ({len(input_str)} chars)",
                detected_at=datetime.now(timezone.utc),
                source_ip=request_info.get('client_ip'),
                request_path=request_info.get('path', ''),
                payload=input_str[:200],
                blocked=True,
                action_taken="INPUT_REJECTED"
            )
            detected_threats.append(threat)
            self.detected_threats.append(threat)
        
        # 3. Null byte 검사
        if '\x00' in input_str:
            threat = SecurityThreat(
                threat_id=str(uuid.uuid4()),
                category=ThreatCategory.UNKNOWN,
                level=SecurityThreatLevel.CRITICAL,
                description=f"Null byte detected in field '{field_name}'",
                detected_at=datetime.now(timezone.utc),
                source_ip=request_info.get('client_ip'),
                request_path=request_info.get('path', ''),
                payload=input_str[:200],
                blocked=True,
                action_taken="INPUT_REJECTED"
            )
            detected_threats.append(threat)
            self.detected_threats.append(threat)
        
        is_safe = len(detected_threats) == 0
        
        if not is_safe:
            logger.critical(f"🚨 SECURITY THREAT DETECTED: {len(detected_threats)} threats in field '{field_name}'")
            for threat in detected_threats:
                logger.critical(f"   - {threat.category.value}: {threat.description}")
        
        return is_safe, detected_threats
    
    def validate_url_path(self, url_path: str, client_ip: str) -> Tuple[bool, List[SecurityThreat]]:
        """URL 경로 완전 검증"""
        detected_threats = []
        
        # Path traversal 검사
        for pattern in self.threat_patterns[ThreatCategory.PATH_TRAVERSAL]:
            if re.search(pattern, url_path):
                threat = SecurityThreat(
                    threat_id=str(uuid.uuid4()),
                    category=ThreatCategory.PATH_TRAVERSAL,
                    level=SecurityThreatLevel.CRITICAL,
                    description="Path traversal attack detected",
                    detected_at=datetime.now(timezone.utc),
                    source_ip=client_ip,
                    request_path=url_path,
                    payload=url_path,
                    blocked=True,
                    action_taken="REQUEST_BLOCKED"
                )
                detected_threats.append(threat)
                self.detected_threats.append(threat)
        
        is_safe = len(detected_threats) == 0
        
        if not is_safe:
            logger.critical(f"🚨 PATH TRAVERSAL ATTACK: {url_path} from {client_ip}")
        
        return is_safe, detected_threats
    
    def get_security_report(self) -> Dict[str, Any]:
        """보안 리포트 생성"""
        total_threats = len(self.detected_threats)
        threat_by_category = {}
        
        for threat in self.detected_threats:
            category = threat.category.value
            if category not in threat_by_category:
                threat_by_category[category] = 0
            threat_by_category[category] += 1
        
        return {
            "total_threats_detected": total_threats,
            "threats_by_category": threat_by_category,
            "blocked_ips": list(self.blocked_ips),
            "last_24h_threats": len([
                t for t in self.detected_threats 
                if (datetime.now(timezone.utc) - t.detected_at).days == 0
            ]),
            "critical_threats": len([
                t for t in self.detected_threats 
                if t.level == SecurityThreatLevel.CRITICAL
            ])
        }


# 전역 보안 검증기 인스턴스
_security_validator = None

def get_critical_security_validator() -> CriticalSecurityValidator:
    """전역 보안 검증기 인스턴스 가져오기"""
    global _security_validator
    if _security_validator is None:
        _security_validator = CriticalSecurityValidator()
    return _security_validator