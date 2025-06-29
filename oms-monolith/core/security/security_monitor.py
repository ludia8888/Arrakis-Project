"""
생명 중요 시스템 보안 모니터링 및 감사 시스템

실시간 위협 탐지, 공격 패턴 분석, 자동 대응을 수행합니다.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import asdict
from fastapi import Request, Response

from core.security.critical_security_framework import (
    CriticalSecurityValidator, SecurityThreat, ThreatCategory, SecurityThreatLevel
)

logger = logging.getLogger(__name__)


class SecurityMonitor:
    """생명 중요 시스템 보안 모니터링"""
    
    def __init__(self):
        self.security_validator = None
        self.alert_thresholds = {
            ThreatCategory.SQL_INJECTION: 1,  # 즉시 알림
            ThreatCategory.XSS: 1,
            ThreatCategory.COMMAND_INJECTION: 1,
            ThreatCategory.PATH_TRAVERSAL: 1,
            ThreatCategory.LDAP_INJECTION: 1,
            ThreatCategory.CODE_INJECTION: 1,
        }
        self.ip_block_threshold = 3  # 3회 공격 시 IP 차단 고려
        
    def set_validator(self, validator: CriticalSecurityValidator):
        """보안 검증기 설정"""
        self.security_validator = validator
    
    async def log_security_event(self, 
                                threat: SecurityThreat,
                                request: Optional[Request] = None,
                                response: Optional[Response] = None):
        """보안 이벤트 로그 기록"""
        
        # 로그 데이터 구성
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "SECURITY_THREAT",
            "threat_id": threat.threat_id,
            "category": threat.category.value,
            "level": threat.level.value,
            "description": threat.description,
            "source_ip": threat.source_ip,
            "request_path": threat.request_path,
            "payload_hash": hash(threat.payload),  # 실제 payload는 로그하지 않음
            "blocked": threat.blocked,
            "action_taken": threat.action_taken
        }
        
        # 요청 정보 추가 (민감 정보 제외)
        if request:
            log_data.update({
                "method": request.method,
                "user_agent": request.headers.get("user-agent", "")[:100],  # 길이 제한
                "content_type": request.headers.get("content-type", ""),
                "content_length": request.headers.get("content-length", "0")
            })
        
        # 응답 정보 추가
        if response:
            log_data.update({
                "response_status": getattr(response, 'status_code', 'unknown'),
                "response_size": len(getattr(response, 'body', b''))
            })
        
        # 보안 로그 기록 (별도 파일로)
        security_logger = logging.getLogger("security_audit")
        security_logger.critical(json.dumps(log_data, ensure_ascii=False))
        
        # 실시간 알림 확인
        await self._check_alert_conditions(threat)
    
    async def _check_alert_conditions(self, threat: SecurityThreat):
        """알림 조건 확인 및 자동 대응"""
        
        if not self.security_validator:
            return
        
        # 카테고리별 알림 임계값 확인
        category_threshold = self.alert_thresholds.get(threat.category, 5)
        recent_threats = [
            t for t in self.security_validator.detected_threats
            if t.category == threat.category and
            (datetime.now(timezone.utc) - t.detected_at).seconds < 3600  # 1시간 내
        ]
        
        if len(recent_threats) >= category_threshold:
            await self._trigger_security_alert(threat, len(recent_threats))
        
        # IP별 공격 횟수 확인
        if threat.source_ip and threat.source_ip != 'unknown':
            ip_threats = [
                t for t in self.security_validator.detected_threats
                if t.source_ip == threat.source_ip and
                (datetime.now(timezone.utc) - t.detected_at).seconds < 3600
            ]
            
            if len(ip_threats) >= self.ip_block_threshold:
                await self._consider_ip_blocking(threat.source_ip, len(ip_threats))
    
    async def _trigger_security_alert(self, threat: SecurityThreat, count: int):
        """보안 알림 발송"""
        alert_data = {
            "alert_type": "SECURITY_BREACH_ATTEMPT",
            "severity": "CRITICAL",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "threat_category": threat.category.value,
            "threat_count": count,
            "source_ip": threat.source_ip,
            "description": f"Multiple {threat.category.value} attempts detected",
            "recommended_action": "IMMEDIATE_INVESTIGATION_REQUIRED"
        }
        
        # 보안 팀 알림 로그
        logger.critical(f"🚨🚨🚨 SECURITY ALERT: {json.dumps(alert_data)}")
        
        # NOTE: Notification integrations (email, SMS, Slack) should be configured via external alerting service
        # await send_security_alert(alert_data)
    
    async def _consider_ip_blocking(self, ip: str, attack_count: int):
        """IP 차단 고려 알림"""
        
        block_recommendation = {
            "recommendation_type": "IP_BLOCKING",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_ip": ip,
            "attack_count": attack_count,
            "time_window": "1_hour",
            "risk_level": "HIGH" if attack_count >= 5 else "MEDIUM",
            "action": "CONSIDER_FIREWALL_BLOCK"
        }
        
        logger.critical(f"🛡️ IP BLOCKING RECOMMENDATION: {json.dumps(block_recommendation)}")
    
    def get_security_dashboard(self) -> Dict[str, Any]:
        """보안 대시보드 데이터"""
        
        if not self.security_validator:
            return {"error": "Security validator not initialized"}
        
        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)
        last_1h = now - timedelta(hours=1)
        
        threats_24h = [
            t for t in self.security_validator.detected_threats
            if t.detected_at >= last_24h
        ]
        
        threats_1h = [
            t for t in self.security_validator.detected_threats  
            if t.detected_at >= last_1h
        ]
        
        # 카테고리별 위협 통계
        category_stats = {}
        for threat in threats_24h:
            category = threat.category.value
            if category not in category_stats:
                category_stats[category] = 0
            category_stats[category] += 1
        
        # 시간대별 위협 분포
        hourly_distribution = {}
        for threat in threats_24h:
            hour = threat.detected_at.hour
            if hour not in hourly_distribution:
                hourly_distribution[hour] = 0
            hourly_distribution[hour] += 1
        
        # 상위 공격 IP
        ip_stats = {}
        for threat in threats_24h:
            if threat.source_ip and threat.source_ip != 'unknown':
                ip = threat.source_ip
                if ip not in ip_stats:
                    ip_stats[ip] = 0
                ip_stats[ip] += 1
        
        top_attack_ips = sorted(ip_stats.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "summary": {
                "total_threats_24h": len(threats_24h),
                "total_threats_1h": len(threats_1h),
                "unique_attack_ips": len(ip_stats),
                "most_common_threat": max(category_stats.items(), key=lambda x: x[1])[0] if category_stats else "None",
                "system_status": "UNDER_ATTACK" if len(threats_1h) > 10 else "MONITORING"
            },
            "threat_categories": category_stats,
            "hourly_distribution": hourly_distribution,
            "top_attack_ips": top_attack_ips,
            "recent_critical_threats": [
                {
                    "timestamp": t.detected_at.isoformat(),
                    "category": t.category.value,
                    "source_ip": t.source_ip,
                    "path": t.request_path
                }
                for t in threats_1h
                if t.level == SecurityThreatLevel.CRITICAL
            ][-10:]  # 최근 10개
        }


# 전역 보안 모니터 인스턴스
_security_monitor = None

def get_security_monitor() -> SecurityMonitor:
    """전역 보안 모니터 인스턴스"""
    global _security_monitor
    if _security_monitor is None:
        _security_monitor = SecurityMonitor()
    return _security_monitor