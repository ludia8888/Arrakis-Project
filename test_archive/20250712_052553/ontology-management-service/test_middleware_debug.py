"""미들웨어를 하나씩 추가하며 문제 찾기"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from bootstrap.config import get_config
from bootstrap.dependencies import init_container
import logging

# Middleware imports
from middleware.error_handler import ErrorHandlerMiddleware
from middleware.etag_middleware import ETagMiddleware
from middleware.auth_middleware import AuthMiddleware
from middleware.terminus_context_middleware import TerminusContextMiddleware
from core.auth_utils.database_context import DatabaseContextMiddleware as CoreDatabaseContextMiddleware
from core.iam.scope_rbac_middleware import ScopeRBACMiddleware

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_test_app(middleware_level=0):
    """미들웨어를 단계별로 추가"""
    logger.info(f"Creating app with middleware level {middleware_level}")
    
    config = get_config()
    container = init_container(config)
    
    app = FastAPI(title="Middleware Test", version="1.0.0", debug=True)
    app.state.container = container
    
    # Redis와 Circuit Breaker 설정 (미들웨어가 필요로 함)
    try:
        app.state.redis_client = container.redis_provider()
        app.state.circuit_breaker_group = container.circuit_breaker_provider()
    except:
        app.state.redis_client = None
        app.state.circuit_breaker_group = None
    
    @app.get("/test")
    async def test():
        return {"middleware_level": middleware_level, "status": "ok"}
    
    # 미들웨어를 단계별로 추가
    if middleware_level >= 1:
        logger.info("Adding ErrorHandlerMiddleware...")
        app.add_middleware(ErrorHandlerMiddleware)
        
    if middleware_level >= 2:
        logger.info("Adding CORS...")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
    if middleware_level >= 3:
        logger.info("Adding ETagMiddleware...")
        app.add_middleware(ETagMiddleware)
        
    if middleware_level >= 4:
        logger.info("Adding AuthMiddleware...")
        app.add_middleware(AuthMiddleware)
        
    if middleware_level >= 5:
        logger.info("Adding TerminusContextMiddleware...")
        app.add_middleware(TerminusContextMiddleware)
        
    if middleware_level >= 6:
        logger.info("Adding CoreDatabaseContextMiddleware...")
        app.add_middleware(CoreDatabaseContextMiddleware)
        
    if middleware_level >= 7:
        logger.info("Adding ScopeRBACMiddleware...")
        app.add_middleware(ScopeRBACMiddleware)
    
    logger.info(f"App created with {middleware_level} middleware(s)")
    return app

if __name__ == "__main__":
    import sys
    level = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    
    app = create_test_app(middleware_level=level)
    logger.info(f"Starting app with middleware level {level}...")
    uvicorn.run(app, host="0.0.0.0", port=8905, log_level="debug")