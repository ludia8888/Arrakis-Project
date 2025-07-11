"""미들웨어 없는 최소 버전 실행"""

import uvicorn
from bootstrap.app_minimal import create_minimal_app
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 미들웨어와 컨테이너 모두 건너뛰기
app = create_minimal_app(skip_middleware=True, skip_container=True)

if __name__ == "__main__":
    logger.info("Starting minimal app without middleware...")
    uvicorn.run(
        "test_minimal_main:app",
        host="0.0.0.0",
        port=8903,
        reload=False,
        log_level="debug"
    )