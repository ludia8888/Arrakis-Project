"""Refactored main entry point using dependency injection"""

import uvicorn
import sys
import os
from pathlib import Path

# CRITICAL: 통합 설정 먼저 로드
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
try:
    from load_shared_config import load_shared_config
    print("🔧 OMS: 통합 설정 로드 중...")
    load_shared_config()
    print("✅ OMS: 통합 설정 로드 완료")
except Exception as e:
    print(f"⚠️  OMS: 통합 설정 로드 실패 (계속 진행): {e}")

from bootstrap.app import create_app
from bootstrap.config import get_config

app = create_app()

if __name__ == "__main__":
    config = get_config()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=config.service.debug,
        log_level=config.service.log_level.lower()
    )