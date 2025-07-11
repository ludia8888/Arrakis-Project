#!/usr/bin/env python3
"""
로컬 테스트: 마이크로서비스 없이 환경 변수만 확인
"""

import os
import json
from datetime import datetime

def test_env_config():
    """환경 변수 기반 마이크로서비스 설정 확인"""
    
    print("🔍 마이크로서비스 환경 설정 확인")
    print("=" * 50)
    
    # .env 파일 읽기
    env_file = ".env"
    if os.path.exists(env_file):
        print(f"✅ {env_file} 파일 발견")
        with open(env_file, 'r') as f:
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    if 'USE_' in line or 'ENDPOINT' in line:
                        print(f"  - {line}")
    else:
        print(f"❌ {env_file} 파일이 없습니다")
        print("  👉 cp .env.microservices .env 실행 필요")
    
    print("\n현재 환경 변수 상태:")
    print("-" * 30)
    
    services = {
        "Data Kernel Gateway": os.getenv("USE_DATA_KERNEL_GATEWAY", "false"),
        "Embedding Service": os.getenv("USE_EMBEDDING_MS", "false"),
        "Scheduler Service": os.getenv("USE_SCHEDULER_MS", "false"),
        "Event Gateway": os.getenv("USE_EVENT_GATEWAY", "false")
    }
    
    enabled_count = 0
    for service, enabled in services.items():
        status = "✅ 활성화" if enabled.lower() == "true" else "❌ 비활성화"
        print(f"{service}: {status}")
        if enabled.lower() == "true":
            enabled_count += 1
    
    print(f"\n📊 마이그레이션 진행률: {enabled_count}/4 ({enabled_count/4*100:.0f}%)")
    
    # Docker Compose 파일 확인
    print("\n🐳 Docker Compose 파일 확인:")
    print("-" * 30)
    
    compose_files = [
        "docker-compose.yml",
        "docker-compose.microservices.yml"
    ]
    
    for file in compose_files:
        if os.path.exists(file):
            print(f"✅ {file} 존재")
        else:
            print(f"❌ {file} 없음")
    
    # 스크립트 확인
    print("\n📜 실행 스크립트 확인:")
    print("-" * 30)
    
    scripts = [
        "start_microservices.sh",
        "verify_microservices.py"
    ]
    
    for script in scripts:
        if os.path.exists(script):
            print(f"✅ {script} 존재")
            if os.access(script, os.X_OK):
                print(f"  ✅ 실행 가능")
            else:
                print(f"  ❌ 실행 권한 없음 (chmod +x {script} 필요)")
        else:
            print(f"❌ {script} 없음")
    
    # 결과 저장
    result = {
        "timestamp": datetime.now().isoformat(),
        "env_file_exists": os.path.exists(env_file),
        "services_enabled": services,
        "migration_progress": f"{enabled_count}/4",
        "docker_compose_ready": all(os.path.exists(f) for f in compose_files),
        "scripts_ready": all(os.path.exists(s) and os.access(s, os.X_OK) for s in scripts)
    }
    
    filename = f"microservices_local_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n💾 테스트 결과가 {filename}에 저장되었습니다")
    
    # 다음 단계 안내
    print("\n🎯 다음 단계:")
    if not os.path.exists(env_file):
        print("1. cp .env.microservices .env")
    if not all(os.access(s, os.X_OK) for s in scripts if os.path.exists(s)):
        print("2. chmod +x start_microservices.sh verify_microservices.py")
    print("3. ./start_microservices.sh")
    print("4. python verify_microservices.py")

if __name__ == "__main__":
    test_env_config()