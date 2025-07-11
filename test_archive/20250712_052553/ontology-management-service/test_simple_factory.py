"""단순화된 app factory 테스트"""

import uvicorn
from fastapi import FastAPI
from bootstrap.config import get_config
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_simple_app() -> FastAPI:
    """미들웨어 없이 최소한의 앱만 생성"""
    logger.info("Creating simple app...")
    
    config = get_config()
    logger.info(f"Config loaded: debug={config.service.debug}")
    
    app = FastAPI(
        title="Simple Test App",
        version="1.0.0",
        debug=True
    )
    
    @app.get("/")
    async def root():
        return {"message": "Hello from simple app"}
    
    @app.get("/health")
    async def health():
        return {"status": "ok"}
    
    logger.info("Simple app created successfully")
    return app

if __name__ == "__main__":
    app = create_simple_app()
    logger.info("Starting simple app...")
    uvicorn.run(app, host="0.0.0.0", port=8902, log_level="debug")