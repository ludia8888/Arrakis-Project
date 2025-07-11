"""최소한의 FastAPI 앱 테스트"""

from fastapi import FastAPI
import uvicorn
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 가장 단순한 FastAPI 앱
app = FastAPI()

@app.get("/")
async def root():
    logger.info("Root endpoint called")
    return {"message": "Hello World"}

@app.get("/health")
async def health():
    logger.info("Health endpoint called")
    return {"status": "ok"}

if __name__ == "__main__":
    logger.info("Starting minimal test app...")
    uvicorn.run(app, host="0.0.0.0", port=8901, log_level="debug")