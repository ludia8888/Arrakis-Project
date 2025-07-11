# 올바른 중앙 설정 관리 아키텍처

## 현재 문제점 분석

### 🚨 shared-config.env의 심각한 문제들
1. **보안 취약점**: JWT 비밀키가 Git 리포지토리에 평문으로 노출
2. **MSA 민첩성 파괴**: 설정 변경 시 모든 서비스 재빌드/재배포 필요
3. **환경별 설정 혼란**: 개발/스테이징/운영 환경별 설정 관리 불가
4. **감사 추적 불가**: 누가 언제 어떤 설정을 변경했는지 추적 불가

## 올바른 해결책

### Option 1: Kubernetes ConfigMap + Secret

```yaml
# 1. 비밀 정보는 Secret으로 관리
apiVersion: v1
kind: Secret
metadata:
  name: arrakis-secrets
  namespace: arrakis
type: Opaque
data:
  jwt-secret: <base64-encoded-random-secret>
  db-password: <base64-encoded-password>

---
# 2. 일반 설정은 ConfigMap으로 관리
apiVersion: v1
kind: ConfigMap
metadata:
  name: arrakis-config
  namespace: arrakis
data:
  JWT_ALGORITHM: "RS256"
  JWT_ISSUER: "iam.company"
  JWT_AUDIENCE: "oms"
  USER_SERVICE_URL: "http://user-service:8000"
  OMS_SERVICE_URL: "http://oms-service:8003"
  LOG_LEVEL: "INFO"

---
# 3. 서비스 Deployment에서 주입
apiVersion: apps/v1
kind: Deployment
metadata:
  name: oms-service
spec:
  template:
    spec:
      containers:
      - name: oms
        image: oms:latest
        env:
        - name: JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: arrakis-secrets
              key: jwt-secret
        envFrom:
        - configMapRef:
            name: arrakis-config
```

### Option 2: HashiCorp Vault

```bash
# 1. Vault에 시크릿 저장
vault kv put secret/arrakis/jwt \
  secret=$(openssl rand -base64 32) \
  algorithm=RS256 \
  issuer=iam.company

# 2. 서비스별 정책 설정
vault policy write oms-service - <<EOF
path "secret/data/arrakis/*" {
  capabilities = ["read"]
}
EOF

# 3. 서비스 인증 및 시크릿 조회
vault auth -method=kubernetes role=oms-service
vault kv get -field=secret secret/arrakis/jwt
```

### Option 3: AWS Parameter Store + IAM

```python
import boto3

class ConfigManager:
    def __init__(self):
        self.ssm = boto3.client('ssm')
    
    def get_secret(self, parameter_name: str) -> str:
        """IAM 권한으로 안전하게 시크릿 조회"""
        response = self.ssm.get_parameter(
            Name=f'/arrakis/{parameter_name}',
            WithDecryption=True
        )
        return response['Parameter']['Value']
    
    def get_jwt_config(self) -> dict:
        return {
            'secret': self.get_secret('jwt/secret'),
            'algorithm': self.get_secret('jwt/algorithm'),
            'issuer': self.get_secret('jwt/issuer')
        }
```

## 권장 구현 계획

### Phase 1: 즉시 조치 (완료됨)
- ✅ shared-config.env 파일 삭제
- ✅ .gitignore에 보안 파일 패턴 추가
- ✅ JWT_LOCAL_VALIDATION 플래그 제거

### Phase 2: 임시 보안 강화 (1-2일)
```python
# config/secure_config.py
import os
from typing import Dict, Any

class SecureConfigManager:
    """환경 변수 기반 안전한 설정 관리"""
    
    def __init__(self):
        self._validate_required_env_vars()
    
    def _validate_required_env_vars(self):
        required_vars = [
            'JWT_SECRET', 'JWT_ALGORITHM', 
            'USER_SERVICE_URL', 'OMS_SERVICE_URL'
        ]
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")
    
    @property
    def jwt_config(self) -> Dict[str, Any]:
        return {
            'secret': os.getenv('JWT_SECRET'),
            'algorithm': os.getenv('JWT_ALGORITHM', 'RS256'),
            'issuer': os.getenv('JWT_ISSUER', 'iam.company'),
            'audience': os.getenv('JWT_AUDIENCE', 'oms')
        }
```

### Phase 3: 진정한 중앙 관리 시스템 (1-2주)
1. **Kubernetes 환경**: ConfigMap + Secret 패턴 구현
2. **클라우드 환경**: 
   - AWS: Parameter Store + Secrets Manager
   - GCP: Secret Manager + Config Connector
   - Azure: Key Vault + App Configuration
3. **온프레미스**: HashiCorp Vault 클러스터 구축

### Phase 4: JWKS 패턴 완성 (1주)
```python
# User Service에서 JWKS 엔드포인트 제공
@app.get("/.well-known/jwks.json")
async def get_jwks():
    """RFC 7517 준수 JWKS 엔드포인트"""
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": "key-1",
                "use": "sig",
                "alg": "RS256",
                "n": "<public-key-modulus>",
                "e": "AQAB"
            }
        ]
    }

# OMS에서 JWKS로 토큰 검증
from jwt import PyJWKClient

class JWKSTokenValidator:
    def __init__(self, jwks_url: str):
        self.jwks_client = PyJWKClient(
            jwks_url,
            cache_keys=True,
            max_cached_keys=16,
            cache_jwks_for=300
        )
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        signing_key = self.jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token, 
            signing_key.key, 
            algorithms=["RS256"],
            options={"verify_signature": True}
        )
```

## 보안 원칙

1. **최소 권한 원칙**: 각 서비스는 필요한 설정만 접근 가능
2. **암호화**: 모든 비밀 정보는 저장 및 전송 시 암호화
3. **감사 로깅**: 모든 설정 변경 사항 로깅
4. **회전 정책**: JWT 키 정기 회전 자동화
5. **환경 분리**: 개발/스테이징/운영 환경별 완전 분리

## 마이그레이션 체크리스트

- [ ] 환경 변수 기반 임시 설정 관리 구현
- [ ] Kubernetes Secret/ConfigMap 구축
- [ ] JWKS 패턴 완성
- [ ] 서비스별 IAM 정책 수립
- [ ] 설정 변경 자동화 파이프라인 구축
- [ ] 모니터링 및 알림 시스템 연동
- [ ] 재해 복구 계획 수립

이 아키텍처를 통해 진정한 중앙집중식 설정 관리와 MSA의 민첩성을 동시에 달성할 수 있습니다.