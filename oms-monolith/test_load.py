#!/usr/bin/env python
"""
동시 요청 부하 테스트
"""
import requests
import jwt
import time
import threading
from datetime import datetime, timedelta, timezone

# JWT 토큰 생성
secret = "FDIRdP4Zu1q8yMt+qCpKaBBo6C937PWGtnW8E94dPA8="
payload = {
    "sub": "testuser",
    "user_id": "test-user-123", 
    "username": "testuser",
    "email": "test@example.com",
    "exp": datetime.now(timezone.utc) + timedelta(hours=1)
}
token = jwt.encode(payload, secret, algorithm="HS256")

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

results = []
lock = threading.Lock()

def make_request(i):
    start = time.time()
    try:
        response = requests.post(
            "http://localhost:8002/api/v1/schemas/main/object-types",
            json={"name": f"LoadTest{i}{int(time.time())}", "displayName": f"Load Test {i}"},
            headers=headers,
            timeout=10
        )
        elapsed = (time.time() - start) * 1000
        
        with lock:
            results.append({
                "id": i, 
                "status": response.status_code, 
                "time": elapsed,
                "success": response.status_code == 200
            })
            
        if response.status_code != 200:
            print(f"Request {i}: {response.status_code} - {response.text[:100]}")
            
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        with lock:
            results.append({
                "id": i,
                "status": "ERROR", 
                "time": elapsed,
                "success": False,
                "error": str(e)
            })
        print(f"Request {i}: ERROR - {e}")

def run_load_test(thread_count):
    print(f"=== 동시 {thread_count}개 요청 테스트 ===")
    
    global results
    results = []
    threads = []

    start_time = time.time()
    for i in range(thread_count):
        t = threading.Thread(target=make_request, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    total_time = (time.time() - start_time) * 1000

    # 결과 분석
    success_count = sum(1 for r in results if r["success"])
    response_times = [r["time"] for r in results]
    avg_time = sum(response_times) / len(response_times) if response_times else 0

    print(f"\n=== 결과 ===")
    print(f"총 요청: {thread_count}")
    print(f"성공: {success_count} ({success_count/thread_count*100:.1f}%)")
    print(f"실패: {thread_count - success_count}")
    print(f"총 소요 시간: {total_time:.2f}ms")
    print(f"평균 응답 시간: {avg_time:.2f}ms")

    if response_times:
        print(f"최대 응답 시간: {max(response_times):.2f}ms")
        print(f"최소 응답 시간: {min(response_times):.2f}ms")

    # 실패 원인 분석
    failures = [r for r in results if not r["success"]]
    if failures:
        print(f"\n=== 실패 원인 분석 ===")
        status_counts = {}
        for f in failures:
            status = f["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
        
        for status, count in status_counts.items():
            print(f"{status}: {count}건")
    
    print("=" * 50)
    return success_count, thread_count, avg_time

if __name__ == "__main__":
    # 점진적 부하 테스트
    for count in [5, 10, 20, 50]:
        success, total, avg_time = run_load_test(count)
        time.sleep(2)  # 2초 대기
        if success < total * 0.5:  # 50% 미만 성공시 중단
            print(f"⚠️  성공률이 50% 미만이므로 테스트 중단")
            break