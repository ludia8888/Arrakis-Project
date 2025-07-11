"""디버깅용 앱 - 단계별로 문제 추적"""

import uvicorn
from fastapi import FastAPI
from bootstrap.config import get_config
from bootstrap.dependencies import init_container
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_debug_app() -> FastAPI:
    """단계별로 앱 생성하며 문제 추적"""
    logger.info("Step 1: Getting config...")
    try:
        config = get_config()
        logger.info("Config loaded successfully")
    except Exception as e:
        logger.error(f"Failed to get config: {e}", exc_info=True)
        raise
    
    logger.info("Step 2: Creating basic FastAPI app...")
    try:
        app = FastAPI(title="Debug App", version="1.0.0", debug=True)
        logger.info("Basic app created successfully")
    except Exception as e:
        logger.error(f"Failed to create app: {e}", exc_info=True)
        raise
    
    logger.info("Step 3: Adding test endpoint...")
    @app.get("/")
    async def root():
        return {"message": "Debug app working"}
    
    logger.info("Step 4: Initializing container...")
    try:
        container = init_container(config)
        logger.info("Container initialized successfully")
        app.state.container = container
    except Exception as e:
        logger.error(f"Failed to init container: {e}", exc_info=True)
        # Continue without container to see if app can still run
        logger.warning("Continuing without container...")
    
    logger.info("Debug app created successfully")
    return app

if __name__ == "__main__":
    try:
        app = create_debug_app()
        logger.info("Starting debug app on port 8003...")
        uvicorn.run(app, host="0.0.0.0", port=8904, log_level="debug")
    except Exception as e:
        logger.error(f"Failed to start app: {e}", exc_info=True)