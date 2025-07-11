"""
테스트용 라우트 - 백프레셔 테스트를 위한 임시 API
"""
import asyncio
import time
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from middleware.auth_middleware import get_current_user
from middleware.circuit_breaker_http import http_circuit_breaker
from core.auth_utils import UserContext
from core.iam.dependencies import require_scope
from core.iam.iam_integration import IAMScope

router = APIRouter(
    prefix="/test",
    tags=["Test API"]
)


class LoadTestRequest(BaseModel):
    """부하 테스트 요청"""
    cpu_load: float = 0.1  # CPU 부하 시간 (초)
    io_delay: float = 0.05  # I/O 지연 시간 (초)
    payload_size: int = 1000  # 응답 페이로드 크기 (바이트)


@router.get("/health")
async def test_health():
    """테스트용 헬스체크 (인증 불필요)"""
    return {"status": "ok", "timestamp": time.time()}


@router.post(
    "/load",
    dependencies=[Depends(require_scope([IAMScope.ONTOLOGIES_READ]))]  # 읽기 권한만 필요
)
async def create_load(
    request: Request,
    load_request: LoadTestRequest,
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    백프레셔 테스트용 API - 인위적인 부하를 생성합니다.
    읽기 권한만 있으면 사용 가능합니다.
    """
    start_time = time.time()
    
    # CPU 부하 생성
    if load_request.cpu_load > 0:
        cpu_start = time.time()
        while time.time() - cpu_start < load_request.cpu_load:
            # CPU 집약적 연산
            _ = sum(i * i for i in range(1000))
    
    # I/O 지연 시뮬레이션
    if load_request.io_delay > 0:
        await asyncio.sleep(load_request.io_delay)
    
    # 큰 페이로드 생성
    payload = "x" * load_request.payload_size
    
    processing_time = time.time() - start_time
    
    return {
        "status": "completed",
        "user_id": current_user.user_id,
        "processing_time": round(processing_time, 3),
        "cpu_load": load_request.cpu_load,
        "io_delay": load_request.io_delay,
        "payload_size": len(payload),
        "payload": payload,
        "timestamp": time.time()
    }


@router.get(
    "/slow",
    dependencies=[Depends(require_scope([IAMScope.ONTOLOGIES_READ]))]
)
async def slow_endpoint(
    delay: float = 2.0,
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    느린 응답을 위한 테스트 엔드포인트
    """
    await asyncio.sleep(delay)
    return {
        "status": "slow_response_completed",
        "delay": delay,
        "user_id": current_user.user_id,
        "timestamp": time.time()
    }


@router.get(
    "/error",
    dependencies=[Depends(require_scope([IAMScope.ONTOLOGIES_READ]))]
)
@http_circuit_breaker(
    name="test_error_endpoint", 
    failure_threshold=3,  # 더 민감하게 설정
    timeout_seconds=60,   # 더 긴 타임아웃
    error_status_codes={404, 500, 503}
)
async def error_endpoint(
    error_code: int = 500,
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    에러를 발생시키는 테스트 엔드포인트
    """
    if error_code == 404:
        raise HTTPException(status_code=404, detail="Test 404 error")
    elif error_code == 500:
        raise HTTPException(status_code=500, detail="Test internal server error")
    elif error_code == 503:
        raise HTTPException(status_code=503, detail="Test service unavailable")
    else:
        raise HTTPException(status_code=error_code, detail=f"Test error {error_code}")


@router.get(
    "/memory",
    dependencies=[Depends(require_scope([IAMScope.ONTOLOGIES_READ]))]
)
async def memory_intensive(
    size_mb: int = 10,
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    메모리 집약적 연산을 수행하는 테스트 엔드포인트
    """
    # size_mb 제한 (최대 100MB)
    size_mb = min(size_mb, 100)
    
    # 메모리 할당
    data = "x" * (1024 * 1024 * size_mb)  # size_mb MB 데이터
    
    return {
        "status": "memory_test_completed",
        "allocated_mb": size_mb,
        "data_length": len(data),
        "user_id": current_user.user_id,
        "timestamp": time.time()
    }