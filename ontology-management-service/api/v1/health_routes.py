"""Health check routes"""

from datetime import datetime
from typing import Annotated

from core.health import HealthStatus, get_health_checker
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from middleware.auth_middleware import get_current_user

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Real system health check - no lies, only verified facts"""
    health_checker = get_health_checker()
    result = await health_checker.get_health(detailed=False)

    # Return appropriate HTTP status based on health
    if result["status"] == HealthStatus.UNHEALTHY.value:
        # Return 503 Service Unavailable for unhealthy
        return JSONResponse(content=result, status_code=503)
    elif result["status"] == HealthStatus.DEGRADED.value:
        # Return 200 but with degraded status (allows partial service)
        return JSONResponse(content=result, status_code=200)
    else:
        # Healthy - return 200
        return result


@router.get("/health/detailed")
async def health_check_detailed(
    current_user: Annotated[str, Depends(get_current_user)]
):
    """Detailed health check with auth required"""
    health_checker = get_health_checker()
    return await health_checker.get_health(detailed=True)


@router.get("/health/live")
async def liveness_probe():
    """Kubernetes liveness probe - basic check if service is running"""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@router.get("/health/ready")
async def readiness_probe():
    """Kubernetes readiness probe - check if ready to serve traffic"""
    health_checker = get_health_checker()
    result = await health_checker.get_health(detailed=False)

    # Only ready if healthy or degraded (not unhealthy)
    ready = result["status"] != HealthStatus.UNHEALTHY.value

    if not ready:
        return JSONResponse(
            content={"ready": False, "reason": "Critical services unavailable"},
            status_code=503,
        )

    return {"ready": True, "status": result["status"]}
