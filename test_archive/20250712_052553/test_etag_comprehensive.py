#!/usr/bin/env python3
"""
E-Tag 캐싱 포괄적 테스트
"""
import asyncio
import httpx
import json
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OMS_URL = "http://localhost:8091"

async def test_etag_caching():
    """E-Tag 캐싱 포괄적 테스트"""
    
    # 토큰 로드
    with open("service_token_write.json", "r") as f:
        creds = json.load(f)
        token = creds["access_token"]
    
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        logger.info("=== E-Tag 캐싱 포괄적 테스트 ===")
        
        # 1. 초기 요청으로 E-Tag 획득
        logger.info("1. 초기 요청으로 E-Tag 획득")
        resp1 = await client.get(
            f"{OMS_URL}/api/v1/schemas/main/object-types",
            headers=headers
        )
        
        etag1 = resp1.headers.get("ETag")
        logger.info(f"초기 응답: {resp1.status_code}, E-Tag: {etag1}")
        
        # 2. 동일한 E-Tag로 조건부 요청 (304 기대)
        logger.info("2. 조건부 요청 테스트 (304 기대)")
        resp2 = await client.get(
            f"{OMS_URL}/api/v1/schemas/main/object-types",
            headers={**headers, "If-None-Match": etag1}
        )
        
        logger.info(f"조건부 요청 응답: {resp2.status_code}")
        if resp2.status_code == 304:
            logger.info("✅ E-Tag 캐시 히트! 304 Not Modified")
        else:
            logger.warning(f"⚠️ 캐시 미스: {resp2.status_code}")
        
        # 3. 연속 조건부 요청 테스트
        logger.info("3. 연속 조건부 요청 테스트 (10회)")
        cache_hits = 0
        cache_misses = 0
        
        for i in range(10):
            resp = await client.get(
                f"{OMS_URL}/api/v1/schemas/main/object-types",
                headers={**headers, "If-None-Match": etag1}
            )
            
            if resp.status_code == 304:
                cache_hits += 1
                logger.info(f"요청 {i+1}: ✅ 캐시 히트 (304)")
            else:
                cache_misses += 1
                logger.info(f"요청 {i+1}: ❌ 캐시 미스 ({resp.status_code})")
                # 새로운 E-Tag 업데이트
                new_etag = resp.headers.get("ETag")
                if new_etag and new_etag != etag1:
                    logger.info(f"E-Tag 변경됨: {etag1} → {new_etag}")
                    etag1 = new_etag
            
            await asyncio.sleep(0.1)
        
        hit_rate = (cache_hits / 10) * 100
        logger.info(f"캐시 히트율: {hit_rate}% ({cache_hits}/10)")
        
        # 4. 다른 엔드포인트 E-Tag 테스트
        logger.info("4. 특정 객체 타입 E-Tag 테스트")
        try:
            resp3 = await client.get(
                f"{OMS_URL}/api/v1/schemas/main/object-types/nonexistent",
                headers=headers
            )
            
            if resp3.status_code == 404:
                logger.info("404 엔드포인트 정상 응답")
                etag_404 = resp3.headers.get("ETag")
                if etag_404:
                    logger.info(f"404 응답에도 E-Tag 존재: {etag_404}")
                    
                    # 404 응답에 대한 조건부 요청
                    resp4 = await client.get(
                        f"{OMS_URL}/api/v1/schemas/main/object-types/nonexistent",
                        headers={**headers, "If-None-Match": etag_404}
                    )
                    
                    if resp4.status_code == 304:
                        logger.info("✅ 404 응답도 E-Tag 캐싱 작동")
                    else:
                        logger.info(f"404 응답 캐시 미스: {resp4.status_code}")
                else:
                    logger.info("404 응답에 E-Tag 없음")
        except Exception as e:
            logger.error(f"404 테스트 실패: {e}")
        
        # 5. 성능 측정
        logger.info("5. E-Tag 성능 측정")
        
        # 일반 요청 시간 측정
        start_time = time.time()
        resp_normal = await client.get(
            f"{OMS_URL}/api/v1/schemas/main/object-types",
            headers=headers
        )
        normal_time = time.time() - start_time
        
        etag_current = resp_normal.headers.get("ETag")
        
        # 조건부 요청 시간 측정 (304 기대)
        start_time = time.time()
        resp_conditional = await client.get(
            f"{OMS_URL}/api/v1/schemas/main/object-types",
            headers={**headers, "If-None-Match": etag_current}
        )
        conditional_time = time.time() - start_time
        
        logger.info(f"일반 요청 시간: {normal_time*1000:.2f}ms")
        logger.info(f"조건부 요청 시간: {conditional_time*1000:.2f}ms")
        
        if resp_conditional.status_code == 304:
            speedup = normal_time / conditional_time if conditional_time > 0 else 0
            logger.info(f"✅ 캐시로 인한 성능 향상: {speedup:.2f}x")
        else:
            logger.warning("조건부 요청이 캐시 미스")
        
        # 결과 요약
        logger.info("\n=== 테스트 결과 요약 ===")
        logger.info(f"캐시 히트율: {hit_rate}%")
        logger.info(f"일반 요청: {normal_time*1000:.2f}ms")
        logger.info(f"캐시된 요청: {conditional_time*1000:.2f}ms")
        
        if hit_rate >= 80:
            logger.info("✅ E-Tag 캐싱 우수")
        elif hit_rate >= 50:
            logger.info("⚠️ E-Tag 캐싱 보통")
        else:
            logger.info("❌ E-Tag 캐싱 개선 필요")

if __name__ == "__main__":
    asyncio.run(test_etag_caching())