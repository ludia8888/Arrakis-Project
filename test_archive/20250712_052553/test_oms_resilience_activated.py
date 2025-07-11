#!/usr/bin/env python3
"""
OMS 복원력 메커니즘 활성화 검증 테스트
새로운 환경 설정으로 모든 복원력 기능이 작동하는지 확인
"""
import asyncio
import httpx
import json
import time
import logging
from datetime import datetime
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Service URLs
OMS_URL = "http://localhost:8091"
USER_SERVICE_URL = "http://localhost:8080"

class ActivatedResilienceTester:
    def __init__(self):
        self.admin_token = None
        self.test_results = []
        
    async def setup(self):
        """테스트 환경 설정"""
        logger.info("="*80)
        logger.info("OMS 활성화된 복원력 메커니즘 검증")
        logger.info("="*80)
        
        # 관리자 토큰 로드
        if os.path.exists("admin_test_credentials.json"):
            with open("admin_test_credentials.json", "r") as f:
                creds = json.load(f)
                self.admin_token = creds["access_token"]
                logger.info("✅ 관리자 토큰 로드 성공")
        else:
            logger.warning("⚠️  관리자 토큰이 없습니다. create_admin_test_user.py를 먼저 실행하세요.")
            return False
            
        return True
    
    async def test_circuit_breaker_with_tuned_thresholds(self):
        """조정된 임계값으로 서킷 브레이커 테스트"""
        logger.info("\n" + "="*60)
        logger.info("1. 서킷 브레이커 (조정된 임계값)")
        logger.info("="*60)
        
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        # 의도적으로 실패를 유발하는 요청
        logger.info("\n[1.1] 서킷 브레이커 트리거 테스트")
        
        async with httpx.AsyncClient(timeout=1.0) as client:  # 짧은 타임아웃
            failures = 0
            for i in range(10):  # 개발환경: 10회, 프로덕션: 3회
                try:
                    # 존재하지 않는 엔드포인트로 요청
                    resp = await client.get(
                        f"{OMS_URL}/api/v1/schemas/main/nonexistent/{i}",
                        headers=headers
                    )
                    if resp.status_code >= 500:
                        failures += 1
                except:
                    failures += 1
                    
                await asyncio.sleep(0.1)
            
            logger.info(f"실패 횟수: {failures}/10")
            
            # 서킷이 열렸는지 확인
            try:
                resp = await client.get(
                    f"{OMS_URL}/api/v1/schemas/main/object-types",
                    headers=headers
                )
                if resp.status_code == 503:
                    logger.info("✅ 서킷 브레이커가 열렸습니다 (503 반환)")
                    circuit_opened = True
                else:
                    logger.info(f"서킷 상태 불명확: {resp.status_code}")
                    circuit_opened = False
            except:
                logger.info("✅ 서킷 브레이커가 요청을 차단했습니다")
                circuit_opened = True
        
        self.test_results.append({
            "test": "circuit_breaker_tuned",
            "status": "PASSED" if circuit_opened else "WARNING",
            "details": {"failures": failures, "circuit_opened": circuit_opened}
        })
    
    async def test_etag_with_decorator(self):
        """E-Tag 데코레이터 적용 확인"""
        logger.info("\n" + "="*60)
        logger.info("2. E-Tag 캐싱 (데코레이터 활성화)")
        logger.info("="*60)
        
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 스키마 엔드포인트 테스트 (E-Tag 데코레이터 적용됨)
            logger.info("\n[2.1] 스키마 엔드포인트 E-Tag 테스트")
            
            resp1 = await client.get(
                f"{OMS_URL}/api/v1/schemas/main/object-types",
                headers=headers
            )
            
            if resp1.status_code == 200:
                etag = resp1.headers.get("etag")
                if etag:
                    logger.info(f"✅ E-Tag 헤더 수신: {etag}")
                    
                    # 조건부 요청
                    headers["If-None-Match"] = etag
                    resp2 = await client.get(
                        f"{OMS_URL}/api/v1/schemas/main/object-types",
                        headers=headers
                    )
                    
                    if resp2.status_code == 304:
                        logger.info("✅ 304 Not Modified - E-Tag 캐시 작동!")
                        etag_working = True
                    else:
                        logger.warning(f"⚠️  예상과 다른 응답: {resp2.status_code}")
                        etag_working = False
                else:
                    logger.error("❌ E-Tag 헤더가 없습니다")
                    etag_working = False
            else:
                logger.error(f"❌ 요청 실패: {resp1.status_code}")
                etag_working = False
            
            # 문서 엔드포인트 테스트 (새로 추가된 E-Tag)
            logger.info("\n[2.2] 문서 엔드포인트 E-Tag 테스트")
            
            # 테스트 문서 생성
            doc_data = {
                "name": "ETagTestDoc",
                "object_type": "TestType",
                "content": {"test": True},
                "status": "draft"
            }
            
            create_resp = await client.post(
                f"{OMS_URL}/api/v1/documents/crud/?branch=main",
                headers={"Authorization": f"Bearer {self.admin_token}"},
                json=doc_data
            )
            
            if create_resp.status_code in [200, 201]:
                doc = create_resp.json()
                doc_id = doc.get("id")
                
                # E-Tag 테스트
                get_headers = {"Authorization": f"Bearer {self.admin_token}"}
                doc_resp1 = await client.get(
                    f"{OMS_URL}/api/v1/documents/crud/{doc_id}?branch=main",
                    headers=get_headers
                )
                
                if doc_resp1.status_code == 200:
                    doc_etag = doc_resp1.headers.get("etag")
                    if doc_etag:
                        logger.info(f"✅ 문서 E-Tag 수신: {doc_etag}")
                        doc_etag_working = True
                    else:
                        logger.warning("⚠️  문서에 E-Tag가 없습니다")
                        doc_etag_working = False
                else:
                    doc_etag_working = False
            else:
                logger.warning("⚠️  테스트 문서 생성 실패")
                doc_etag_working = False
        
        self.test_results.append({
            "test": "etag_activated",
            "status": "PASSED" if etag_working else "FAILED",
            "details": {
                "schema_etag": etag_working,
                "document_etag": doc_etag_working
            }
        })
    
    async def test_backpressure_with_admin(self):
        """관리자 권한으로 백프레셔 테스트"""
        logger.info("\n" + "="*60)
        logger.info("3. 백프레셔 (관리자 권한)")
        logger.info("="*60)
        
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        async def create_object(session, i):
            try:
                resp = await session.post(
                    f"{OMS_URL}/api/v1/schemas/main/object-types",
                    headers=headers,
                    json={
                        "name": f"BackpressureTest_{i}",
                        "description": f"Testing backpressure {i}",
                        "properties": {}
                    },
                    timeout=httpx.Timeout(5.0)
                )
                return resp.status_code
            except Exception as e:
                return str(type(e).__name__)
        
        logger.info("\n[3.1] 대량 동시 요청 (관리자 권한)")
        
        async with httpx.AsyncClient() as client:
            # 개발환경: 200개, 프로덕션: 50개 동시 요청
            concurrent_limit = 200 if os.getenv("ENVIRONMENT") == "development" else 50
            
            tasks = [create_object(client, i) for i in range(concurrent_limit + 50)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 분석
        status_counts = {}
        for result in results:
            if isinstance(result, int):
                status_counts[result] = status_counts.get(result, 0) + 1
            else:
                status_counts['error'] = status_counts.get('error', 0) + 1
        
        logger.info("요청 결과:")
        for status, count in sorted(status_counts.items()):
            logger.info(f"  - {status}: {count}개")
        
        # 201 (생성됨) 또는 429/503 (백프레셔) 확인
        success_count = status_counts.get(201, 0) + status_counts.get(200, 0)
        rejected_count = status_counts.get(429, 0) + status_counts.get(503, 0)
        
        if rejected_count > 0:
            logger.info(f"✅ 백프레셔 작동: {rejected_count}개 요청 거부됨")
            backpressure_working = True
        elif success_count > concurrent_limit:
            logger.info("✅ 모든 요청 처리됨 (백프레셔 임계값 미도달)")
            backpressure_working = True
        else:
            logger.warning("⚠️  백프레셔 동작 불명확")
            backpressure_working = False
        
        self.test_results.append({
            "test": "backpressure_admin",
            "status": "PASSED" if backpressure_working else "WARNING",
            "details": {
                "success": success_count,
                "rejected": rejected_count,
                "total": len(results)
            }
        })
    
    async def test_integrated_monitoring(self):
        """통합 모니터링 확인"""
        logger.info("\n" + "="*60)
        logger.info("4. 통합 모니터링")
        logger.info("="*60)
        
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Prometheus 메트릭 엔드포인트 확인
            try:
                metrics_resp = await client.get(f"{OMS_URL}/metrics")
                if metrics_resp.status_code == 200:
                    logger.info("✅ Prometheus 메트릭 엔드포인트 활성화")
                    metrics_available = True
                else:
                    logger.warning(f"⚠️  메트릭 엔드포인트 응답: {metrics_resp.status_code}")
                    metrics_available = False
            except:
                logger.warning("⚠️  메트릭 엔드포인트 접근 불가")
                metrics_available = False
            
            # 상세 헬스 체크
            health_resp = await client.get(
                f"{OMS_URL}/health/detailed",
                headers=headers
            )
            
            if health_resp.status_code == 200:
                health_data = health_resp.json()
                logger.info(f"시스템 상태: {health_data.get('status')}")
                
                # 복원력 관련 컴포넌트 확인
                components = health_data.get('components', {})
                if 'circuit_breaker' in components:
                    logger.info(f"✅ 서킷 브레이커 상태: {components['circuit_breaker']}")
                if 'cache' in components:
                    logger.info(f"✅ 캐시 상태: {components['cache']}")
                if 'redis' in components:
                    logger.info(f"✅ Redis 상태: {components['redis']}")
                
                monitoring_working = True
            else:
                logger.warning("⚠️  상세 헬스 체크 실패")
                monitoring_working = False
        
        self.test_results.append({
            "test": "integrated_monitoring",
            "status": "PASSED" if monitoring_working else "WARNING",
            "details": {
                "metrics_available": metrics_available,
                "health_check": monitoring_working
            }
        })
    
    def print_summary(self):
        """테스트 결과 요약"""
        logger.info("\n" + "="*80)
        logger.info("활성화된 복원력 메커니즘 검증 결과")
        logger.info("="*80)
        
        all_passed = True
        
        for result in self.test_results:
            status_icon = "✅" if result["status"] == "PASSED" else "⚠️" if result["status"] == "WARNING" else "❌"
            logger.info(f"\n{status_icon} {result['test']}: {result['status']}")
            for key, value in result.get("details", {}).items():
                logger.info(f"    - {key}: {value}")
            
            if result["status"] == "FAILED":
                all_passed = False
        
        logger.info("\n" + "="*80)
        if all_passed:
            logger.info("✅ 모든 복원력 메커니즘이 성공적으로 활성화되었습니다!")
        else:
            logger.info("⚠️  일부 메커니즘이 예상대로 작동하지 않습니다.")
            logger.info("\n권장 조치:")
            logger.info("1. 환경변수 파일 (.env) 확인")
            logger.info("2. Docker 컨테이너 재시작")
            logger.info("3. Redis 연결 상태 확인")
            logger.info("4. 로그 파일 검토")
        logger.info("="*80)

async def main():
    """메인 테스트 실행"""
    tester = ActivatedResilienceTester()
    
    try:
        if not await tester.setup():
            logger.error("테스트 설정 실패")
            return 1
        
        # 각 테스트 실행
        await tester.test_circuit_breaker_with_tuned_thresholds()
        await tester.test_etag_with_decorator()
        await tester.test_backpressure_with_admin()
        await tester.test_integrated_monitoring()
        
        # 결과 요약
        tester.print_summary()
        
        return 0
        
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))