#!/usr/bin/env python3
"""모든 서비스를 함께 실행하는 스크립트"""

import subprocess
import time
import os
import sys
import signal

processes = []

def cleanup(signum, frame):
    """종료 시 모든 프로세스 정리"""
    print("\n\nStopping all services...")
    for proc, name in processes:
        if proc.poll() is None:
            print(f"Stopping {name}...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

print("Starting all services...\n")

# 1. User Service (Port 8101)
print("1. Starting User Service on port 8101...")
user_service_dir = "/Users/isihyeon/Desktop/Arrakis-Project/user-service"
user_proc = subprocess.Popen(
    [sys.executable, "run_user_service.py"],
    cwd=user_service_dir,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    universal_newlines=True,
    bufsize=1
)
processes.append((user_proc, "User Service"))
time.sleep(3)

# 2. Audit Service (Port 8002)  
print("2. Starting Audit Service on port 8002...")
audit_service_dir = "/Users/isihyeon/Desktop/Arrakis-Project/audit-service"
audit_proc = subprocess.Popen(
    [sys.executable, "main.py"],
    cwd=audit_service_dir,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    universal_newlines=True,
    bufsize=1
)
processes.append((audit_proc, "Audit Service"))
time.sleep(3)

# 3. OMS Monolith (Port 8000)
print("3. Starting OMS Monolith on port 8000...")
oms_service_dir = "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service"
oms_proc = subprocess.Popen(
    [sys.executable, "main.py"],
    cwd=oms_service_dir,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    universal_newlines=True,
    bufsize=1
)
processes.append((oms_proc, "OMS Monolith"))

print("\nAll services started!")
print("\nService URLs:")
print("- User Service: http://localhost:8101")
print("- Audit Service: http://localhost:8002")  
print("- OMS Monolith: http://localhost:8000")
print("\nPress Ctrl+C to stop all services\n")

# 실시간 로그 출력
import select

while True:
    for proc, name in processes:
        if proc.poll() is not None:
            print(f"\n{name} has stopped unexpectedly!")
            cleanup(None, None)
        
        # Non-blocking read
        if proc.stdout:
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                print(f"[{name}] {line.strip()}")
    
    time.sleep(0.1)