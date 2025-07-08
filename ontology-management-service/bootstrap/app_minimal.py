"""미들웨어 없는 최소한의 app factory - 문제 격리용"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from bootstrap.config import get_config
from bootstrap.dependencies import init_container

# Router imports
from api.v1 import health_routes

logger = logging.getLogger(__name__)

def create_minimal_app(skip_middleware=True, skip_container=False) -> FastAPI:
    """최소한의 앱 생성 - 문제 격리를 위해"""
    
    logger.info("Creating minimal app...")
    config = get_config()
    
    if not skip_container:
        try:
            container = init_container(config)
            logger.info("Container initialized")
        except Exception as e:
            logger.error(f"Container init failed: {e}")
            container = None
    else:
        container = None
        logger.info("Skipping container initialization")
    
    api_prefix = "/api/v1"
    
    app = FastAPI(
        title="OMS Minimal",
        version="1.0.0",
        debug=True,
        openapi_url=f"{api_prefix}/openapi.json",
        docs_url=f"{api_prefix}/docs"
    )
    
    if container:
        app.state.container = container
    
    # 최소한의 라우터만 추가
    app.include_router(health_routes.router, prefix=api_prefix, tags=["Health"])
    
    # 간단한 테스트 엔드포인트
    @app.get("/test")
    async def test_endpoint():
        return {"status": "minimal app working"}
    
    if not skip_middleware:
        # CORS만 추가 (가장 기본적인 미들웨어)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        logger.info("Added CORS middleware only")
    else:
        logger.info("Skipped all middleware")
    
    logger.info("Minimal app created successfully")
    return app