#!/usr/bin/env python3
"""
OMS 서비스를 통합 설정으로 시작합니다.
"""
import os
import sys
from pathlib import Path

# 통합 설정 로드
sys.path.append(str(Path(__file__).parent))
from load_shared_config import load_shared_config


def main():
    print("🚀 OMS 서비스 시작 - 통합 설정 모드")

    # 1. 통합 설정 로드
    if not load_shared_config():
        print("❌ 통합 설정 로드 실패")
        sys.exit(1)

    # 2. OMS 디렉토리로 이동
    oms_dir = Path(__file__).parent / "ontology-management-service"
    if not oms_dir.exists():
        print(f"❌ OMS 디렉토리를 찾을 수 없습니다: {oms_dir}")
        sys.exit(1)

    os.chdir(oms_dir)
    print(f"📁 작업 디렉토리: {os.getcwd()}")

    # 3. OMS 서비스 시작
    print("🌟 OMS 서비스 시작 중...")
    os.system("python -m uvicorn main:app --port 8003 --host 0.0.0.0 --reload")


if __name__ == "__main__":
    main()
