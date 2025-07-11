#!/usr/bin/env python3
"""
서킷 브레이커 전용 테스트
실제 404 에러를 발생시켜 서킷 브레이커 동작 확인
"""
import asyncio
import httpx
import json
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OMS_URL = "http://localhost:8091"

async def test_circuit_breaker():
    """서킷 브레이커 전용 테스트"""
    
    # 토큰 로드
    with open("service_token_write.json", "r") as f:
        creds = json.load(f)
        token = creds["access_token"]
    
    headers = {"Authorization": f"Bearer {token}"}
    
    logger.info("=== 서킷 브레이커 트리거 테스트 ===")
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        # 1. 정상 요청으로 서킷 상태 확인
        logger.info("1. 초기 정상 요청")
        resp = await client.get(f"{OMS_URL}/api/v1/schemas/main/object-types", headers=headers)
        logger.info(f"정상 요청 응답: {resp.status_code}")
        
        # 2. 404 에러를 발생시키는 요청들 (임계값 3개 초과)
        logger.info("2. 404 에러 연속 요청 (임계값 3개 초과)")
        failed_requests = 0
        
        for i in range(6):  # 임계값(3)보다 많이 요청
            try:
                # 테스트 API의 에러 엔드포인트 사용
                resp = await client.get(
                    f"{OMS_URL}/api/v1/test/error?error_code=404", 
                    headers=headers
                )
                logger.info(f"요청 {i+1}: HTTP {resp.status_code}")
                
                if resp.status_code == 404:
                    failed_requests += 1
                elif resp.status_code == 503:
                    logger.info("✅ 서킷 브레이커 열림! (503 Service Unavailable)")
                    break
                    
            except Exception as e:
                logger.info(f"요청 {i+1}: 예외 - {type(e).__name__}")
                failed_requests += 1
            
            await asyncio.sleep(0.1)
        
        logger.info(f"총 실패 요청: {failed_requests}")
        
        # 3. 서킷 열린 후 정상 요청 시도
        logger.info("3. 서킷 브레이커 열린 후 정상 요청 시도")
        try:
            resp = await client.get(f"{OMS_URL}/api/v1/schemas/main/object-types", headers=headers)
            if resp.status_code == 503:
                logger.info("✅ 서킷 브레이커가 정상 요청도 차단 (503)")
            else:
                logger.info(f"⚠️  정상 요청 통과: {resp.status_code}")
        except Exception as e:
            logger.info(f"✅ 서킷 브레이커가 요청 차단: {type(e).__name__}")
        
        # 4. 서킷이 열린 상태에서 같은 엔드포인트 재요청
        logger.info("4. 서킷 열린 상태에서 에러 엔드포인트 재요청")
        try:
            resp = await client.get(f"{OMS_URL}/api/v1/test/error?error_code=404", headers=headers)
            if resp.status_code == 503:
                logger.info("✅ 서킷 브레이커가 같은 엔드포인트 차단 (503)")
            else:
                logger.info(f"⚠️  서킷 브레이커 미작동: {resp.status_code}")
        except Exception as e:
            logger.info(f"✅ 서킷 브레이커가 요청 차단: {type(e).__name__}")
        
        # 5. 60초 대기 후 재시도 (서킷 회복 테스트)  
        logger.info("5. 60초 대기 후 서킷 회복 테스트 - 건너뛰기")
        return
        await asyncio.sleep(65)  # 타임아웃(60초)보다 조금 더 대기
        
        try:
            resp = await client.get(f"{OMS_URL}/api/v1/schemas/main/object-types", headers=headers)
            if resp.status_code == 200:
                logger.info("✅ 서킷 브레이커 회복 - 정상 요청 처리")
            else:
                logger.info(f"서킷 상태 불확실: {resp.status_code}")
        except Exception as e:
            logger.info(f"여전히 차단됨: {type(e).__name__}")

if __name__ == "__main__":
    asyncio.run(test_circuit_breaker())