#!/usr/bin/env python3
"""
엔드투엔드 통합 테스트
실제 아키텍처 수정사항을 검증합니다
"""

import os
import sys
import json
import asyncio
import httpx
import logging
from pathlib import Path
import subprocess
import time
import signal

# 환경 변수 설정
os.environ.update({
    "USER_SERVICE_URL": "http://localhost:8001",
    "OMS_SERVICE_URL": "http://localhost:8000", 
    "USER_SERVICE_JWKS_URL": "http://localhost:8001/.well-known/jwks.json",
    "JWT_ISSUER": "user-service",
    "JWT_AUDIENCE": "oms",
    "TERMINUSDB_ENDPOINT": "http://localhost:6363",
    "TERMINUSDB_DB": "oms",
    "DATABASE_URL": "postgresql+asyncpg://oms_user:oms_password@localhost:5432/oms_db",
    "REDIS_URL": "redis://localhost:6379",
    "ENVIRONMENT": "development"
})

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EndToEndTester:
    """엔드투엔드 통합 테스트"""
    
    def __init__(self):
        self.oms_process = None
        self.user_service_process = None
        self.test_results = []
        
    async def start_user_service(self):
        """User Service 시작"""
        logger.info("🚀 User Service 시작 중...")
        
        user_service_path = Path(__file__).parent / "user-service"
        if not user_service_path.exists():
            logger.error("❌ User Service 디렉토리를 찾을 수 없음")
            return False
            
        try:
            # User Service 실행
            self.user_service_process = subprocess.Popen([
                sys.executable, "run_user_service.py"
            ], cwd=str(user_service_path), 
               stdout=subprocess.PIPE, 
               stderr=subprocess.PIPE)
            
            # 서비스 시작 대기
            await asyncio.sleep(10)
            
            # Health check
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get("http://localhost:8001/health", timeout=5)
                    if response.status_code == 200:
                        logger.info("✅ User Service 시작 성공")
                        return True
                    else:
                        logger.error(f"❌ User Service health check 실패: {response.status_code}")
                        return False
                except Exception as e:
                    logger.error(f"❌ User Service 연결 실패: {e}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ User Service 시작 실패: {e}")
            return False
            
    async def start_oms_service(self):
        """OMS 서비스 시작"""
        logger.info("🚀 OMS 서비스 시작 중...")
        
        oms_path = Path(__file__).parent / "ontology-management-service"
        if not oms_path.exists():
            logger.error("❌ OMS 디렉토리를 찾을 수 없음")
            return False
            
        try:
            # OMS 실행
            self.oms_process = subprocess.Popen([
                sys.executable, "main.py"
            ], cwd=str(oms_path),
               stdout=subprocess.PIPE,
               stderr=subprocess.PIPE)
            
            # 서비스 시작 대기 
            await asyncio.sleep(15)
            
            # Health check
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get("http://localhost:8000/health", timeout=5)
                    if response.status_code == 200:
                        logger.info("✅ OMS 서비스 시작 성공")
                        return True
                    else:
                        logger.error(f"❌ OMS health check 실패: {response.status_code}")
                        return False
                except Exception as e:
                    logger.error(f"❌ OMS 서비스 연결 실패: {e}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ OMS 서비스 시작 실패: {e}")
            return False
            
    async def test_jwks_endpoint(self):
        """JWKS 엔드포인트 테스트"""
        logger.info("🔑 JWKS 엔드포인트 테스트")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get("http://localhost:8001/.well-known/jwks.json", timeout=5)
                if response.status_code == 200:
                    jwks_data = response.json()
                    if "keys" in jwks_data and len(jwks_data["keys"]) > 0:
                        self.test_results.append("✅ JWKS 엔드포인트 정상 작동")
                        logger.info("✅ JWKS 엔드포인트 정상 작동")
                        return True
                    else:
                        self.test_results.append("❌ JWKS 데이터 형식 오류")
                        return False
                else:
                    self.test_results.append(f"❌ JWKS 엔드포인트 실패: {response.status_code}")
                    return False
            except Exception as e:
                self.test_results.append(f"❌ JWKS 엔드포인트 연결 실패: {e}")
                return False
                
    async def test_user_authentication(self):
        """사용자 인증 테스트"""
        logger.info("👤 사용자 인증 테스트")
        
        async with httpx.AsyncClient() as client:
            try:
                # 테스트 사용자 생성
                user_data = {
                    "username": "testuser",
                    "password": "TestPassword123!",
                    "email": "test@example.com"
                }
                
                response = await client.post("http://localhost:8001/auth/register", 
                                           json=user_data, timeout=10)
                
                if response.status_code in [201, 409]:  # 성공 또는 이미 존재
                    # 로그인 시도
                    login_data = {
                        "username": user_data["username"],
                        "password": user_data["password"]
                    }
                    
                    login_response = await client.post("http://localhost:8001/auth/login",
                                                     json=login_data, timeout=10)
                    
                    if login_response.status_code == 200:
                        login_result = login_response.json()
                        if "access_token" in login_result:
                            self.test_results.append("✅ 사용자 인증 성공")
                            logger.info("✅ 사용자 인증 성공")
                            return login_result["access_token"]
                        else:
                            self.test_results.append("❌ JWT 토큰 누락")
                            return None
                    else:
                        self.test_results.append(f"❌ 로그인 실패: {login_response.status_code}")
                        return None
                else:
                    self.test_results.append(f"❌ 사용자 생성 실패: {response.status_code}")
                    return None
                    
            except Exception as e:
                self.test_results.append(f"❌ 인증 테스트 실패: {e}")
                return None
                
    async def test_oms_jwt_validation(self, access_token):
        """OMS JWT 검증 테스트"""
        logger.info("🔐 OMS JWT 검증 테스트")
        
        if not access_token:
            self.test_results.append("❌ JWT 토큰 없음 - 검증 불가")
            return False
            
        async with httpx.AsyncClient() as client:
            try:
                headers = {"Authorization": f"Bearer {access_token}"}
                
                # OMS 브랜치 목록 API 호출
                response = await client.get("http://localhost:8000/api/v1/branches/",
                                          headers=headers, timeout=10)
                
                if response.status_code == 200:
                    branches = response.json()
                    self.test_results.append("✅ OMS JWT 검증 및 브랜치 API 성공")
                    logger.info(f"✅ OMS JWT 검증 성공 - {len(branches) if isinstance(branches, list) else 0}개 브랜치")
                    return True
                elif response.status_code == 401:
                    self.test_results.append("❌ OMS JWT 검증 실패 - 인증 오류")
                    return False
                else:
                    self.test_results.append(f"❌ OMS API 호출 실패: {response.status_code}")
                    return False
                    
            except Exception as e:
                self.test_results.append(f"❌ OMS JWT 검증 실패: {e}")
                return False
                
    async def test_branch_service_real_db(self, access_token):
        """BranchService 실제 DB 연동 테스트"""
        logger.info("🗄️ BranchService 실제 DB 연동 테스트")
        
        if not access_token:
            self.test_results.append("❌ JWT 토큰 없음 - DB 테스트 불가")
            return False
            
        async with httpx.AsyncClient() as client:
            try:
                headers = {"Authorization": f"Bearer {access_token}"}
                
                # 브랜치 생성 테스트
                create_data = {
                    "name": "test-branch",
                    "from_branch": "main"
                }
                
                create_response = await client.post("http://localhost:8000/api/v1/branches/",
                                                  json=create_data, headers=headers, timeout=10)
                
                if create_response.status_code in [201, 409]:  # 성공 또는 이미 존재
                    # 특정 브랜치 조회 테스트
                    get_response = await client.get("http://localhost:8000/api/v1/branches/test-branch",
                                                  headers=headers, timeout=10)
                    
                    if get_response.status_code == 200:
                        branch_data = get_response.json()
                        if branch_data.get("name") == "test-branch":
                            self.test_results.append("✅ BranchService 실제 DB 연동 성공")
                            logger.info("✅ BranchService 실제 DB 연동 성공")
                            return True
                        else:
                            self.test_results.append("❌ 브랜치 데이터 불일치")
                            return False
                    else:
                        self.test_results.append(f"❌ 브랜치 조회 실패: {get_response.status_code}")
                        return False
                else:
                    self.test_results.append(f"❌ 브랜치 생성 실패: {create_response.status_code}")
                    return False
                    
            except Exception as e:
                self.test_results.append(f"❌ BranchService DB 테스트 실패: {e}")
                return False
                
    def cleanup_services(self):
        """서비스 정리"""
        logger.info("🧹 서비스 정리 중...")
        
        if self.oms_process:
            try:
                self.oms_process.terminate()
                self.oms_process.wait(timeout=5)
            except:
                self.oms_process.kill()
                
        if self.user_service_process:
            try:
                self.user_service_process.terminate()
                self.user_service_process.wait(timeout=5)
            except:
                self.user_service_process.kill()
                
    async def run_full_test(self):
        """전체 테스트 실행"""
        logger.info("🎯 엔드투엔드 통합 테스트 시작")
        
        try:
            # 1. User Service 시작
            if not await self.start_user_service():
                self.test_results.append("❌ User Service 시작 실패")
                return False
                
            # 2. OMS 서비스 시작
            if not await self.start_oms_service():
                self.test_results.append("❌ OMS 서비스 시작 실패")
                return False
                
            # 3. JWKS 엔드포인트 테스트
            await self.test_jwks_endpoint()
            
            # 4. 사용자 인증 테스트
            access_token = await self.test_user_authentication()
            
            # 5. OMS JWT 검증 테스트
            await self.test_oms_jwt_validation(access_token)
            
            # 6. BranchService 실제 DB 연동 테스트  
            await self.test_branch_service_real_db(access_token)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 통합 테스트 실행 실패: {e}")
            self.test_results.append(f"❌ 통합 테스트 실행 실패: {e}")
            return False
        finally:
            self.cleanup_services()
            
    def print_test_report(self):
        """테스트 결과 보고서"""
        logger.info("\n" + "="*60)
        logger.info("🎯 엔드투엔드 통합 테스트 결과")
        logger.info("="*60)
        
        success_count = len([r for r in self.test_results if r.startswith("✅")])
        total_count = len(self.test_results)
        
        for result in self.test_results:
            logger.info(f"  {result}")
            
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        logger.info(f"\n📊 성공률: {success_rate:.1f}% ({success_count}/{total_count})")
        
        if success_count == total_count:
            logger.info("\n🎉 모든 통합 테스트 통과! 아키텍처 수정사항이 정상 작동합니다.")
        else:
            logger.error("\n⚠️ 일부 테스트 실패. 추가 수정이 필요할 수 있습니다.")
            
        return success_count == total_count

async def main():
    """메인 실행 함수"""
    tester = EndToEndTester()
    
    try:
        success = await tester.run_full_test()
        final_result = tester.print_test_report()
        
        if final_result:
            logger.info("\n🏆 엔드투엔드 통합 테스트 성공!")
            return 0
        else:
            logger.error("\n🚨 엔드투엔드 통합 테스트 실패!")
            return 1
            
    except KeyboardInterrupt:
        logger.info("\n⏹️ 사용자에 의해 테스트 중단됨")
        tester.cleanup_services()
        return 130
    except Exception as e:
        logger.error(f"\n🔥 테스트 중 치명적 오류: {e}")
        tester.cleanup_services()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)