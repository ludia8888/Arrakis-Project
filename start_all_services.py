#!/usr/bin/env python3
"""
Arrakis Project - Ultimate Service Starter
통합 환경에서 모든 서비스를 순차적으로 시작하고 검증
"""

import subprocess
import time
import asyncio
import httpx
import sys
from pathlib import Path

class ServiceStarter:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.venv_path = self.base_dir / "venv_ultimate"
        self.services = [
            {
                "name": "OMS",
                "port": 8000,
                "path": "ontology-management-service",
                "module": "api.main:app",
                "health_endpoint": "/health"
            },
            {
                "name": "User Service", 
                "port": 8010,
                "path": "user-service",
                "module": "src.main:app",
                "health_endpoint": "/health"
            },
            {
                "name": "Audit Service",
                "port": 8011, 
                "path": "audit-service",
                "module": "main:app",
                "health_endpoint": "/health"
            }
        ]
        self.processes = {}

    def kill_existing_processes(self):
        """기존 프로세스 종료"""
        print("🛑 Killing existing processes...")
        for service in self.services:
            try:
                subprocess.run(
                    ["lsof", "-ti", f":{service['port']}"], 
                    capture_output=True,
                    text=True
                )
                subprocess.run(
                    f"lsof -ti:{service['port']} | xargs kill -9 2>/dev/null || true",
                    shell=True
                )
            except:
                pass
        time.sleep(2)

    def start_service(self, service):
        """개별 서비스 시작"""
        print(f"🚀 Starting {service['name']} on port {service['port']}...")
        
        service_path = self.base_dir / service['path']
        
        # 환경 활성화 및 서비스 시작 명령
        cmd = [
            "bash", "-c", 
            f"cd {service_path} && "
            f"source {self.venv_path}/bin/activate && "
            f"uvicorn {service['module']} --host 0.0.0.0 --port {service['port']} --reload"
        ]
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.processes[service['name']] = process
            
            # 서비스 시작 대기
            time.sleep(3)
            
            return process
        except Exception as e:
            print(f"❌ Failed to start {service['name']}: {e}")
            return None

    async def check_health(self, service):
        """서비스 헬스 체크"""
        url = f"http://localhost:{service['port']}{service['health_endpoint']}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=5.0)
                if response.status_code == 200:
                    print(f"✅ {service['name']} is healthy")
                    return True
                else:
                    print(f"⚠️  {service['name']} returned {response.status_code}")
                    return False
            except Exception as e:
                print(f"❌ {service['name']} health check failed: {e}")
                return False

    async def verify_all_services(self):
        """모든 서비스 검증"""
        print("\n📊 Verifying all services...")
        
        results = []
        for service in self.services:
            is_healthy = await self.check_health(service)
            results.append((service['name'], is_healthy))
            
        print("\n" + "="*50)
        print("🏥 Service Health Report")
        print("="*50)
        
        healthy_count = 0
        for name, is_healthy in results:
            status = "✅ HEALTHY" if is_healthy else "❌ UNHEALTHY"
            print(f"{name:15} {status}")
            if is_healthy:
                healthy_count += 1
                
        print(f"\n📈 Overall Status: {healthy_count}/{len(self.services)} services healthy")
        
        if healthy_count == len(self.services):
            print("🎉 All services are running successfully!")
            return True
        else:
            print("⚠️  Some services need attention")
            return False

    def get_service_logs(self, service_name):
        """서비스 로그 출력"""
        if service_name in self.processes:
            process = self.processes[service_name]
            if process.poll() is None:  # Process is still running
                return "Service is running"
            else:
                stdout, stderr = process.communicate()
                return f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
        return "Process not found"

    def print_service_urls(self):
        """서비스 URL 출력"""
        print("\n🔗 Service URLs:")
        for service in self.services:
            print(f"  {service['name']:15} http://localhost:{service['port']}")
            
        print("\n📋 API Documentation:")
        for service in self.services:
            print(f"  {service['name']:15} http://localhost:{service['port']}/docs")

    async def run_basic_integration_test(self):
        """기본 통합 테스트 실행"""
        print("\n🧪 Running Basic Integration Test...")
        
        async with httpx.AsyncClient() as client:
            # Test OMS
            try:
                response = await client.get("http://localhost:8000/api/v1/schemas/status")
                if response.status_code == 200:
                    print("✅ OMS Schema API responding")
                else:
                    print(f"⚠️  OMS Schema API returned {response.status_code}")
            except Exception as e:
                print(f"❌ OMS Schema API test failed: {e}")

            # Test User Service
            try:
                response = await client.get("http://localhost:8010/health")
                if response.status_code == 200:
                    print("✅ User Service responding")
                else:
                    print(f"⚠️  User Service returned {response.status_code}")
            except Exception as e:
                print(f"❌ User Service test failed: {e}")

            # Test Audit Service  
            try:
                response = await client.get("http://localhost:8011/health")
                if response.status_code == 200:
                    print("✅ Audit Service responding")
                else:
                    print(f"⚠️  Audit Service returned {response.status_code}")
            except Exception as e:
                print(f"❌ Audit Service test failed: {e}")

    async def main(self):
        """메인 실행 함수"""
        print("🎯 Arrakis Project - Ultimate Service Starter")
        print("="*60)
        
        # 1. 기존 프로세스 종료
        self.kill_existing_processes()
        
        # 2. 각 서비스 시작
        for service in self.services:
            process = self.start_service(service)
            if not process:
                print(f"💥 Failed to start {service['name']}, aborting...")
                return False
        
        # 3. 서비스 시작 대기
        print("\n⏳ Waiting for services to initialize...")
        time.sleep(10)
        
        # 4. 헬스 체크
        all_healthy = await self.verify_all_services()
        
        # 5. 서비스 URL 출력
        self.print_service_urls()
        
        # 6. 기본 통합 테스트
        await self.run_basic_integration_test()
        
        if all_healthy:
            print(f"\n🎉 SUCCESS: All {len(self.services)} services are running!")
            print("\n💡 Next steps:")
            print("  - Run: python deep_system_verification.py")
            print("  - Test API endpoints manually") 
            print("  - Execute end-to-end test scenarios")
            return True
        else:
            print(f"\n⚠️  WARNING: Some services failed to start properly")
            print("\n🔍 Debug info:")
            for service_name in self.processes.keys():
                print(f"\n--- {service_name} logs ---")
                print(self.get_service_logs(service_name)[:500])
            return False

if __name__ == "__main__":
    starter = ServiceStarter()
    
    try:
        result = asyncio.run(starter.main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
        starter.kill_existing_processes()
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        starter.kill_existing_processes()
        sys.exit(1)