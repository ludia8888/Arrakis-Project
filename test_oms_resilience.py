#!/usr/bin/env python3
"""
OMS 복원력 메커니즘 종합 검증 테스트
- 서킷 브레이커
- E-Tag 캐싱
- 분산 캐싱 (Redis)
- 백프레셔
"""
import asyncio
import httpx
import json
import time
import logging
from datetime import datetime
import redis.asyncio as redis
from typing import Dict, Any, List
import random

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Service URLs
OMS_URL = "http://localhost:8091"
USER_SERVICE_URL = "http://localhost:8080"
REDIS_URL = "redis://localhost:6381"  # OMS Redis port

class OMSResilienceTester:
    def __init__(self):
        self.user_token = None
        self.redis_client = None
        self.test_results = []
        
    async def setup(self):
        """테스트 환경 설정"""
        logger.info("="*80)
        logger.info("OMS 복원력 메커니즘 검증 시작")
        logger.info("="*80)
        
        # Redis 클라이언트 설정
        try:
            self.redis_client = await redis.from_url(REDIS_URL)
            await self.redis_client.ping()
            logger.info("✅ Redis 연결 성공")
        except Exception as e:
            logger.warning(f"⚠️  Redis 연결 실패: {e}")
            logger.info("ℹ️  Redis 없이 계속 진행합니다 (일부 테스트 제한됨)")
            self.redis_client = None
            
        # 테스트 사용자 토큰 획득
        if not await self._get_test_token():
            return False
            
        return True
    
    async def _get_test_token(self) -> bool:
        """테스트용 사용자 토큰 획득"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 테스트 사용자 생성
            user_data = {
                "username": f"oms_test_{int(time.time())}",
                "password": "Test123!@#",
                "email": f"oms_test_{int(time.time())}@test.com",
                "full_name": "OMS Resilience Test"
            }
            
            resp = await client.post(f"{USER_SERVICE_URL}/auth/register", json=user_data)
            if resp.status_code != 201:
                logger.error(f"사용자 생성 실패: {resp.status_code}")
                return False
                
            # 로그인
            resp = await client.post(
                f"{USER_SERVICE_URL}/auth/login",
                json={"username": user_data["username"], "password": user_data["password"]}
            )
            
            if resp.status_code == 200:
                login_data = resp.json()
                if login_data.get("step") == "complete":
                    complete_resp = await client.post(
                        f"{USER_SERVICE_URL}/auth/login/complete",
                        json={"challenge_token": login_data["challenge_token"]}
                    )
                    if complete_resp.status_code == 200:
                        self.user_token = complete_resp.json()["access_token"]
                else:
                    self.user_token = login_data.get("access_token")
                    
            if self.user_token:
                logger.info("✅ 테스트 토큰 획득 성공")
                return True
            else:
                logger.error("❌ 테스트 토큰 획득 실패")
                return False
    
    async def test_circuit_breaker(self):
        """서킷 브레이커 테스트"""
        logger.info("\n" + "="*60)
        logger.info("1. 서킷 브레이커 테스트")
        logger.info("="*60)
        
        headers = {"Authorization": f"Bearer {self.user_token}"}
        
        # 1. 정상 상태 테스트
        logger.info("\n[1.1] 정상 상태 테스트")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OMS_URL}/api/v1/schemas/main/object-types", headers=headers)
            if resp.status_code == 200:
                logger.info("✅ 정상 상태: 스키마 조회 성공")
            else:
                logger.warning(f"⚠️  스키마 조회 실패: {resp.status_code}")
        
        # 2. 부하 테스트 (서킷 브레이커 트리거)
        logger.info("\n[1.2] 부하 테스트 - 동시 요청으로 서킷 브레이커 테스트")
        async with httpx.AsyncClient(timeout=2.0) as client:
            tasks = []
            for i in range(50):  # 50개 동시 요청
                task = client.get(
                    f"{OMS_URL}/api/v1/schemas/main/object-types/{i}",
                    headers=headers
                )
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            success_count = sum(1 for r in responses 
                              if not isinstance(r, Exception) and r.status_code < 500)
            error_count = len(responses) - success_count
            
            logger.info(f"동시 요청 결과: 성공 {success_count}, 실패 {error_count}")
            
            if error_count > 10:
                logger.info("✅ 서킷 브레이커가 과부하를 감지하고 일부 요청을 차단했습니다")
            else:
                logger.warning("⚠️  서킷 브레이커가 예상대로 작동하지 않았습니다")
        
        # 3. 서킷 브레이커 상태 확인
        logger.info("\n[1.3] 서킷 브레이커 상태 확인")
        await asyncio.sleep(2)  # 잠시 대기
        
        # Redis에서 서킷 브레이커 상태 확인
        if self.redis_client:
            keys = await self.redis_client.keys("circuit_breaker:*")
            if keys:
                logger.info(f"✅ Redis에 서킷 브레이커 상태 저장됨: {len(keys)}개 키")
                for key in keys[:3]:  # 처음 3개만 출력
                    state = await self.redis_client.get(key)
                    if state:
                        logger.info(f"  - {key.decode()}: {state.decode()}")
            else:
                logger.info("ℹ️  Redis에 서킷 브레이커 상태가 없습니다")
        
        self.test_results.append({
            "test": "circuit_breaker",
            "status": "PASSED" if error_count > 10 else "WARNING",
            "details": {"success": success_count, "errors": error_count}
        })
    
    async def test_etag_caching(self):
        """E-Tag 캐싱 테스트"""
        logger.info("\n" + "="*60)
        logger.info("2. E-Tag 캐싱 테스트")
        logger.info("="*60)
        
        headers = {"Authorization": f"Bearer {self.user_token}"}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. 첫 번째 요청 - ETag 받기
            logger.info("\n[2.1] 첫 번째 요청 - ETag 생성")
            resp1 = await client.get(f"{OMS_URL}/api/v1/schemas/main/object-types", headers=headers)
            
            if resp1.status_code == 200:
                etag = resp1.headers.get("etag")
                if etag:
                    logger.info(f"✅ ETag 수신: {etag}")
                else:
                    logger.warning("⚠️  ETag 헤더가 없습니다")
                    self.test_results.append({
                        "test": "etag_caching",
                        "status": "FAILED",
                        "details": {"reason": "No ETag header"}
                    })
                    return
            else:
                logger.error(f"❌ 첫 번째 요청 실패: {resp1.status_code}")
                return
            
            # 2. 두 번째 요청 - If-None-Match 헤더와 함께
            logger.info("\n[2.2] 두 번째 요청 - 조건부 요청")
            headers["If-None-Match"] = etag
            resp2 = await client.get(f"{OMS_URL}/api/v1/schemas/main/object-types", headers=headers)
            
            if resp2.status_code == 304:
                logger.info("✅ 304 Not Modified - ETag 캐시 히트!")
                cache_hit = True
            elif resp2.status_code == 200:
                logger.warning("⚠️  200 OK - 캐시 미스 (데이터가 변경되었을 수 있음)")
                cache_hit = False
            else:
                logger.error(f"❌ 예상치 못한 응답: {resp2.status_code}")
                cache_hit = False
            
            # 3. 캐시 효과 측정
            logger.info("\n[2.3] 캐시 효과 측정")
            
            # 캐시 없이 10회 요청
            del headers["If-None-Match"]
            start_no_cache = time.time()
            for _ in range(10):
                await client.get(f"{OMS_URL}/api/v1/schemas/main/object-types", headers=headers)
            time_no_cache = time.time() - start_no_cache
            
            # 캐시 있이 10회 요청
            headers["If-None-Match"] = etag
            start_with_cache = time.time()
            for _ in range(10):
                await client.get(f"{OMS_URL}/api/v1/schemas/main/object-types", headers=headers)
            time_with_cache = time.time() - start_with_cache
            
            improvement = ((time_no_cache - time_with_cache) / time_no_cache) * 100
            logger.info(f"캐시 없이: {time_no_cache:.2f}초")
            logger.info(f"캐시 있이: {time_with_cache:.2f}초")
            logger.info(f"성능 향상: {improvement:.1f}%")
            
            self.test_results.append({
                "test": "etag_caching",
                "status": "PASSED" if cache_hit else "WARNING",
                "details": {
                    "cache_hit": cache_hit,
                    "performance_improvement": f"{improvement:.1f}%"
                }
            })
    
    async def test_distributed_caching(self):
        """분산 캐싱 (Redis) 테스트"""
        logger.info("\n" + "="*60)
        logger.info("3. 분산 캐싱 (Redis) 테스트")
        logger.info("="*60)
        
        if not self.redis_client:
            logger.error("❌ Redis 클라이언트가 없습니다")
            return
        
        # 1. 캐시 키 패턴 확인
        logger.info("\n[3.1] Redis 캐시 키 확인")
        cache_keys = await self.redis_client.keys("cache:*")
        logger.info(f"캐시 키 개수: {len(cache_keys)}")
        
        if cache_keys:
            # 캐시 키 샘플 출력
            for key in cache_keys[:5]:
                ttl = await self.redis_client.ttl(key)
                logger.info(f"  - {key.decode()} (TTL: {ttl}초)")
        
        # 2. 캐시 작동 테스트
        logger.info("\n[3.2] 캐시 작동 테스트")
        headers = {"Authorization": f"Bearer {self.user_token}"}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 첫 번째 요청 (캐시 미스)
            start = time.time()
            resp1 = await client.get(f"{OMS_URL}/api/v1/schemas/main/object-types", headers=headers)
            time1 = time.time() - start
            
            # 두 번째 요청 (캐시 히트 예상)
            start = time.time()
            resp2 = await client.get(f"{OMS_URL}/api/v1/schemas/main/object-types", headers=headers)
            time2 = time.time() - start
            
            logger.info(f"첫 번째 요청: {time1:.3f}초")
            logger.info(f"두 번째 요청: {time2:.3f}초")
            
            if time2 < time1 * 0.5:  # 50% 이상 빠르면 캐시 히트로 판단
                logger.info("✅ 캐시 히트 확인 - 두 번째 요청이 훨씬 빠름")
                cache_working = True
            else:
                logger.warning("⚠️  캐시 효과가 명확하지 않음")
                cache_working = False
        
        # 3. 캐시 통계 확인
        logger.info("\n[3.3] 캐시 통계")
        info = await self.redis_client.info("stats")
        logger.info(f"총 명령 수행: {info.get('total_commands_processed', 'N/A')}")
        logger.info(f"키스페이스 히트: {info.get('keyspace_hits', 'N/A')}")
        logger.info(f"키스페이스 미스: {info.get('keyspace_misses', 'N/A')}")
        
        # 히트율 계산
        hits = info.get('keyspace_hits', 0)
        misses = info.get('keyspace_misses', 0)
        if hits + misses > 0:
            hit_rate = (hits / (hits + misses)) * 100
            logger.info(f"캐시 히트율: {hit_rate:.1f}%")
        
        self.test_results.append({
            "test": "distributed_caching",
            "status": "PASSED" if cache_working else "WARNING",
            "details": {
                "cache_keys": len(cache_keys),
                "cache_working": cache_working
            }
        })
    
    async def test_backpressure(self):
        """백프레셔 메커니즘 테스트"""
        logger.info("\n" + "="*60)
        logger.info("4. 백프레셔 메커니즘 테스트")
        logger.info("="*60)
        
        headers = {"Authorization": f"Bearer {self.user_token}"}
        
        # 1. 대량 동시 요청으로 백프레셔 트리거
        logger.info("\n[4.1] 대량 동시 요청 테스트")
        
        async def make_request(session, i):
            try:
                resp = await session.post(
                    f"{OMS_URL}/api/v1/schemas/main/object-types",
                    headers=headers,
                    json={
                        "name": f"TestObject_{i}",
                        "description": f"Backpressure test object {i}",
                        "properties": {}
                    },
                    timeout=httpx.Timeout(5.0)
                )
                return resp.status_code
            except Exception as e:
                return str(type(e).__name__)
        
        async with httpx.AsyncClient() as client:
            # 100개의 동시 요청
            tasks = [make_request(client, i) for i in range(100)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 분석
        status_counts = {}
        for result in results:
            if isinstance(result, int):
                status_counts[result] = status_counts.get(result, 0) + 1
            else:
                status_counts['error'] = status_counts.get('error', 0) + 1
        
        logger.info("요청 결과 분포:")
        for status, count in sorted(status_counts.items()):
            logger.info(f"  - {status}: {count}개")
        
        # 429 (Too Many Requests) 또는 503 (Service Unavailable) 확인
        backpressure_triggered = status_counts.get(429, 0) > 0 or status_counts.get(503, 0) > 0
        
        if backpressure_triggered:
            logger.info("✅ 백프레셔가 작동하여 일부 요청을 거부했습니다")
        else:
            logger.warning("⚠️  백프레셔가 트리거되지 않았습니다")
        
        # 2. 점진적 부하 테스트
        logger.info("\n[4.2] 점진적 부하 증가 테스트")
        
        rejection_started = False
        for batch_size in [10, 20, 50, 100]:
            logger.info(f"\n배치 크기: {batch_size}")
            
            async with httpx.AsyncClient() as client:
                tasks = [make_request(client, i) for i in range(batch_size)]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                rejected = sum(1 for r in results if r == 429 or r == 503)
                success = sum(1 for r in results if r == 200 or r == 201)
                
                logger.info(f"  성공: {success}, 거부: {rejected}")
                
                if rejected > 0 and not rejection_started:
                    logger.info(f"  ✅ 백프레셔 시작점: {batch_size}개 동시 요청")
                    rejection_started = True
            
            await asyncio.sleep(2)  # 시스템 회복 대기
        
        self.test_results.append({
            "test": "backpressure",
            "status": "PASSED" if backpressure_triggered else "WARNING",
            "details": {
                "triggered": backpressure_triggered,
                "status_distribution": status_counts
            }
        })
    
    async def test_integrated_resilience(self):
        """통합 복원력 테스트"""
        logger.info("\n" + "="*60)
        logger.info("5. 통합 복원력 테스트")
        logger.info("="*60)
        
        headers = {"Authorization": f"Bearer {self.user_token}"}
        
        # 1. 정상 작동 확인
        logger.info("\n[5.1] 시스템 정상 작동 확인")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OMS_URL}/health/detailed", headers=headers)
            if resp.status_code == 200:
                health = resp.json()
                logger.info(f"✅ 시스템 상태: {health.get('status', 'unknown')}")
                for component, status in health.get('components', {}).items():
                    logger.info(f"  - {component}: {status}")
            else:
                logger.warning(f"⚠️  헬스 체크 실패: {resp.status_code}")
        
        # 2. 장애 시뮬레이션 및 복구
        logger.info("\n[5.2] 장애 복구 시나리오")
        
        # 부하 발생
        logger.info("높은 부하 발생 중...")
        async with httpx.AsyncClient(timeout=2.0) as client:
            tasks = []
            for i in range(200):
                task = client.get(
                    f"{OMS_URL}/api/v1/schemas/main/object-types",
                    headers=headers
                )
                tasks.append(task)
                if i % 50 == 0:
                    await asyncio.sleep(0.1)  # 점진적 부하
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            success = sum(1 for r in responses 
                         if not isinstance(r, Exception) and r.status_code < 500)
            logger.info(f"부하 중 성공률: {success}/{len(responses)} ({success/len(responses)*100:.1f}%)")
        
        # 시스템 회복 대기
        logger.info("\n시스템 회복 대기 중...")
        await asyncio.sleep(5)
        
        # 회복 확인
        logger.info("\n회복 후 요청")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OMS_URL}/api/v1/schemas/main/object-types", headers=headers)
            if resp.status_code == 200:
                logger.info("✅ 시스템이 정상적으로 회복되었습니다")
                recovery_success = True
            else:
                logger.error(f"❌ 회복 실패: {resp.status_code}")
                recovery_success = False
        
        self.test_results.append({
            "test": "integrated_resilience",
            "status": "PASSED" if recovery_success else "FAILED",
            "details": {
                "load_success_rate": f"{success/len(responses)*100:.1f}%",
                "recovery": recovery_success
            }
        })
    
    async def cleanup(self):
        """테스트 정리"""
        if self.redis_client:
            await self.redis_client.aclose()
    
    def print_summary(self):
        """테스트 결과 요약"""
        logger.info("\n" + "="*80)
        logger.info("테스트 결과 요약")
        logger.info("="*80)
        
        for result in self.test_results:
            status_icon = "✅" if result["status"] == "PASSED" else "⚠️" if result["status"] == "WARNING" else "❌"
            logger.info(f"{status_icon} {result['test']}: {result['status']}")
            for key, value in result.get("details", {}).items():
                logger.info(f"    - {key}: {value}")
        
        # 전체 결과
        passed = sum(1 for r in self.test_results if r["status"] == "PASSED")
        total = len(self.test_results)
        
        logger.info(f"\n총 {total}개 테스트 중 {passed}개 통과")
        
        # 권장사항
        logger.info("\n" + "="*80)
        logger.info("권장사항")
        logger.info("="*80)
        
        if any(r["status"] != "PASSED" for r in self.test_results):
            logger.info("일부 복원력 메커니즘이 예상대로 작동하지 않았습니다:")
            
            for result in self.test_results:
                if result["status"] != "PASSED":
                    if result["test"] == "circuit_breaker":
                        logger.info("- 서킷 브레이커: 임계값 조정이 필요할 수 있습니다")
                    elif result["test"] == "etag_caching":
                        logger.info("- E-Tag: 캐시 정책 확인이 필요합니다")
                    elif result["test"] == "distributed_caching":
                        logger.info("- 분산 캐싱: Redis 연결 및 설정 확인이 필요합니다")
                    elif result["test"] == "backpressure":
                        logger.info("- 백프레셔: 동시 요청 제한 설정 확인이 필요합니다")
        else:
            logger.info("✅ 모든 복원력 메커니즘이 정상적으로 작동하고 있습니다!")


async def main():
    """메인 테스트 실행"""
    tester = OMSResilienceTester()
    
    try:
        # 설정
        if not await tester.setup():
            logger.error("테스트 설정 실패")
            return 1
        
        # 각 테스트 실행
        await tester.test_circuit_breaker()
        await tester.test_etag_caching()
        await tester.test_distributed_caching()
        await tester.test_backpressure()
        await tester.test_integrated_resilience()
        
        # 결과 요약
        tester.print_summary()
        
        return 0
        
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}")
        return 1
        
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))