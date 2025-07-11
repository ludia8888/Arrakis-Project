# Arrakis MSA - 마이크로서비스 마이그레이션 가이드

## 📌 개요

Arrakis 프로젝트의 점진적 마이크로서비스 전환이 시작되었습니다!

### 현재 상태
- ✅ 모든 마이크로서비스 Docker 이미지 준비 완료
- ✅ Data Kernel Gateway 구현 완료
- ✅ 환경 변수 기반 전환 메커니즘 구현
- ✅ 마이크로서비스 실행 스크립트 준비
- ✅ 검증 도구 준비

## 🚀 빠른 시작

### 1. 마이크로서비스 모드 시작
```bash
cd ontology-management-service

# 환경 설정 복사 (최초 1회)
cp .env.microservices .env

# 마이크로서비스 시작
./start_microservices.sh

# 모니터링 포함 시작
./start_microservices.sh --clean --monitoring
```

### 2. 상태 확인
```bash
# 마이크로서비스 검증
python verify_microservices.py

# Docker 상태 확인
docker-compose -f docker-compose.yml -f docker-compose.microservices.yml ps

# 로그 확인
docker-compose -f docker-compose.yml -f docker-compose.microservices.yml logs -f
```

## 📊 마이크로서비스 아키텍처

### 활성화된 서비스들

1. **Data Kernel Gateway** (포트: 8082, gRPC: 50051)
   - TerminusDB 접근 중앙화
   - REST 및 gRPC 인터페이스 제공
   - 모든 데이터베이스 작업 프록시

2. **Embedding Service** (포트: 8001, gRPC: 50055)
   - 텍스트 임베딩 생성
   - 다양한 모델 지원
   - 캐싱 메커니즘 포함

3. **Scheduler Service** (포트: 8002, gRPC: 50056)
   - 작업 스케줄링
   - Cron 기반 실행
   - 분산 작업 관리

4. **Event Gateway** (포트: 8003, gRPC: 50057)
   - 이벤트 라우팅
   - Webhook 지원
   - NATS 기반 메시징

## 🔧 환경 설정

### 핵심 환경 변수

```env
# 마이크로서비스 활성화
USE_DATA_KERNEL_GATEWAY=true
USE_EMBEDDING_MS=true
USE_SCHEDULER_MS=true
USE_EVENT_GATEWAY=true

# 서비스 엔드포인트
DATA_KERNEL_GRPC_ENDPOINT=data-kernel:50051
EMBEDDING_SERVICE_ENDPOINT=embedding-service:50055
SCHEDULER_SERVICE_ENDPOINT=scheduler-service:50056
EVENT_GATEWAY_ENDPOINT=event-gateway:50057
```

## 📈 마이그레이션 진행 상황

### API 엔드포인트로 확인
```bash
# Gateway 모드 상태
curl http://localhost:8083/api/v1/config/gateway-mode

# 마이크로서비스 상태
curl http://localhost:8083/api/v1/config/microservices-status

# 마이그레이션 진행률
curl http://localhost:8083/api/v1/config/migration-progress
```

## 🔍 문제 해결

### 서비스가 시작되지 않을 때
```bash
# 기존 컨테이너 정리
docker-compose -f docker-compose.yml -f docker-compose.microservices.yml down

# 볼륨 정리 (주의: 데이터 손실)
docker volume prune

# 네트워크 재생성
docker network rm oms-network
docker network create oms-network
```

### 포트 충돌 시
```bash
# 사용 중인 포트 확인
lsof -ti:8001,8002,8003,8082 | xargs kill -9
```

### 로그 분석
```bash
# 특정 서비스 로그
docker logs oms-data-kernel -f
docker logs oms-embedding-service -f

# 전체 로그
docker-compose -f docker-compose.yml -f docker-compose.microservices.yml logs -f
```

## 📊 모니터링

### Prometheus (http://localhost:9091)
- 모든 마이크로서비스 메트릭 수집
- 자동 타겟 발견

### Grafana (http://localhost:3000)
- 실시간 대시보드
- 서비스별 성능 지표
- 알림 설정

### Jaeger (http://localhost:16686)
- 분산 추적
- 서비스 간 호출 분석
- 성능 병목 지점 파악

## 🎯 다음 단계

1. **성능 최적화**
   - 서비스 간 통신 최적화
   - 캐싱 전략 개선
   - 연결 풀링 조정

2. **확장성**
   - Kubernetes 배포 준비
   - 서비스 메시 도입 검토
   - Auto-scaling 설정

3. **보안 강화**
   - mTLS 인증 추가
   - API Gateway 도입
   - 세분화된 권한 관리

## 🚨 주의사항

1. **데이터 일관성**: 마이그레이션 중 데이터 일관성 모니터링 필수
2. **백업**: 마이그레이션 전 전체 백업 권장
3. **단계적 전환**: 한 번에 모든 서비스를 전환하지 말고 점진적으로 진행
4. **롤백 계획**: 문제 발생 시 즉시 모놀리스 모드로 전환 가능

## 📞 지원

문제 발생 시:
1. `verify_microservices.py` 실행 결과 확인
2. 로그 분석
3. GitHub Issues에 문제 제기

---

🎉 **축하합니다! Arrakis 프로젝트가 마이크로서비스 아키텍처로 진화하고 있습니다!**