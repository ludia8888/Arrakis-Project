"""
Secure Configuration Manager
Secure configuration management based on environment variables
"""
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class JWTConfig:
 """JWT configuration settings"""
 issuer: str
 audience: str
 algorithms: List[str]
 jwks_url: str
 cache_ttl: int = 300 # 5 minutes


@dataclass
class ServiceConfig:
 """Service configuration settings"""
 name: str
 url: str
 timeout: int = 5
 retry_count: int = 3


class SecureConfigManager:
 """
 Secure configuration management based on environment variables

 보안 원칙:
 1. 모든 민감한 정보는 환경 변수에서만 조회
 2. 기본값은 개발 환경에서만 허용
 3. 운영 환경에서는 모든 Required environment variable validation
 4. 설정 변경 시 서비스 재시작 없이 반영
 """

 def __init__(self):
 self.environment = os.getenv("ENVIRONMENT", "development")
 self.is_production = self.environment.lower() in ["production", "prod"]

 # Required environment variable validation
 self._validate_required_env_vars()

 logger.info(f"🔧 Security configuration manager initialization complete - 환경: {self.environment}")

 def _validate_required_env_vars(self):
 """Required environment variable validation"""
 required_vars = [
 'USER_SERVICE_URL',
 'OMS_SERVICE_URL'
 ]

 # 운영 환경에서는 더 엄격한 검증
 if self.is_production:
 required_vars.extend([
 'JWT_ISSUER',
 'JWT_AUDIENCE',
 'REDIS_URL',
 'DATABASE_URL'
 ])

 missing = [var for var in required_vars if not os.getenv(var)]
 if missing:
 error_msg = f"Missing required environment variables: {missing}"
 logger.error(f"❌ 설정 검증 실패: {error_msg}")
 raise ValueError(error_msg)

 logger.info(f"✅ Required environment variable validation 완료: {len(required_vars)}개")

 @property
 def jwt_config(self) -> JWTConfig:
 """JWT 설정 반환"""
 user_service_url = os.getenv('USER_SERVICE_URL', 'http://localhost:8000')
 jwks_url = f"{user_service_url}/.well-known/jwks.json"

 config = JWTConfig(
 issuer = os.getenv('JWT_ISSUER', 'user-service'),
 audience = os.getenv('JWT_AUDIENCE', 'oms'),
 algorithms = os.getenv('JWT_ALGORITHMS', 'RS256').split(','),
 jwks_url = jwks_url,
 cache_ttl = int(os.getenv('JWT_CACHE_TTL', '300'))
 )

 # 운영 환경에서는 기본값 사용 경고
 if self.is_production:
 if config.issuer == 'user-service':
 logger.warning("⚠️ JWT_ISSUER가 기본값 사용 중 - 운영 환경에서는 적절한 값 설정 권장")

 return config

 @property
 def service_urls(self) -> Dict[str, ServiceConfig]:
 """서비스 URL 설정 반환"""
 return {
 'user_service': ServiceConfig(
 name = 'user-service',
 url = os.getenv('USER_SERVICE_URL', 'http://localhost:8000'),
 timeout = int(os.getenv('USER_SERVICE_TIMEOUT', '5')),
 retry_count = int(os.getenv('USER_SERVICE_RETRY_COUNT', '3'))
 ),
 'oms_service': ServiceConfig(
 name = 'oms-service',
 url = os.getenv('OMS_SERVICE_URL', 'http://localhost:8003'),
 timeout = int(os.getenv('OMS_SERVICE_TIMEOUT', '5')),
 retry_count = int(os.getenv('OMS_SERVICE_RETRY_COUNT', '3'))
 ),
 'audit_service': ServiceConfig(
 name = 'audit-service',
 url = os.getenv('AUDIT_SERVICE_URL', 'http://localhost:8001'),
 timeout = int(os.getenv('AUDIT_SERVICE_TIMEOUT', '5')),
 retry_count = int(os.getenv('AUDIT_SERVICE_RETRY_COUNT', '3'))
 )
 }

 @property
 def database_config(self) -> Dict[str, Any]:
 """데이터베이스 설정 반환"""
 return {
 'redis_url': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
 'terminusdb_endpoint': os.getenv('TERMINUSDB_ENDPOINT', 'http://localhost:6363'),
 'terminusdb_db': os.getenv('TERMINUSDB_DB', 'oms'),
 'connection_pool_size': int(os.getenv('DB_POOL_SIZE', '10')),
 'connection_timeout': int(os.getenv('DB_TIMEOUT', '30'))
 }

 @property
 def security_config(self) -> Dict[str, Any]:
 """보안 설정 반환"""
 return {
 'cors_origins': self._parse_cors_origins(),
 'rate_limit_enabled': os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true',
 'rate_limit_per_minute': int(os.getenv('RATE_LIMIT_PER_MINUTE', '60')),
 'secure_headers_enabled': os.getenv('SECURE_HEADERS_ENABLED', 'true').lower() == 'true',


 'https_only': os.getenv('HTTPS_ONLY', 'false').lower() == 'true'
 }

 def _parse_cors_origins(self) -> List[str]:
 """CORS origins 파싱"""
 cors_str = os.getenv('CORS_ORIGINS', '["http://localhost:3000",
     "http://localhost:8080"]')
 try:
 import json
 return json.loads(cors_str)
 except json.JSONDecodeError:
 # Fallback: 콤마로 구minutes된 문자열
 return [origin.strip() for origin in cors_str.split(',')]

 @property
 def monitoring_config(self) -> Dict[str, Any]:
 """모니터링 설정 반환"""
 return {
 'log_level': os.getenv('LOG_LEVEL', 'INFO'),
 'metrics_enabled': os.getenv('METRICS_ENABLED', 'true').lower() == 'true',
 'tracing_enabled': os.getenv('TRACING_ENABLED', 'false').lower() == 'true',
 'health_check_interval': int(os.getenv('HEALTH_CHECK_INTERVAL', '30'))
 }

 def get_service_url(self, service_name: str) -> str:
 """특정 서비스 URL 조회"""
 service_configs = self.service_urls
 if service_name in service_configs:
 return service_configs[service_name].url

 # Fallback: 환경 변수에서 직접 조회
 env_var = f"{service_name.upper()}_SERVICE_URL"
 url = os.getenv(env_var)
 if url:
 return url

 raise ValueError(f"Service URL not found for: {service_name}")

 def validate_jwks_connectivity(self) -> bool:
 """JWKS 엔드포인트 연결성 검증"""
 import asyncio

 import httpx

 async def check_jwks():
 try:
 jwks_url = self.jwt_config.jwks_url
 async with httpx.AsyncClient(timeout = 5.0) as client:
 response = await client.get(jwks_url)
 response.raise_for_status()

 # JWKS 형식 검증
 jwks_data = response.json()
 if 'keys' not in jwks_data or not jwks_data['keys']:
 return False

 logger.info(f"✅ JWKS 연결성 검증 성공: {jwks_url}")
 return True

 except Exception as e:
 logger.error(f"❌ JWKS 연결성 검증 실패: {e}")
 return False

 return asyncio.run(check_jwks())

 def get_config_summary(self) -> Dict[str, Any]:
 """현재 설정 요약 정보 반환 (민감한 정보 제외)"""
 return {
 "environment": self.environment,
 "is_production": self.is_production,
 "jwt_config": {
 "issuer": self.jwt_config.issuer,
 "audience": self.jwt_config.audience,
 "algorithms": self.jwt_config.algorithms,
 "jwks_url": self.jwt_config.jwks_url
 },
 "services": {
 name: {"url": config.url, "timeout": config.timeout}
 for name, config in self.service_urls.items()
 },
 "security": {
 "rate_limit_enabled": self.security_config['rate_limit_enabled'],
 "https_only": self.security_config['https_only']
 },
 "monitoring": {
 "log_level": self.monitoring_config['log_level'],
 "metrics_enabled": self.monitoring_config['metrics_enabled']
 }
 }


# 전역 설정 관리자 인스턴스
secure_config = SecureConfigManager()
