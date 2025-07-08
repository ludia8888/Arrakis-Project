#!/usr/bin/env python3
"""
간단한 아키텍처 테스트
서비스 시작 없이 코드 구조만 검증
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# OMS 경로 추가
oms_path = Path(__file__).parent / "ontology-management-service"
sys.path.insert(0, str(oms_path))

# 환경 변수 설정
os.environ.update({
    "USER_SERVICE_URL": "http://localhost:8001",
    "OMS_SERVICE_URL": "http://localhost:8000",
    "USER_SERVICE_JWKS_URL": "http://localhost:8001/.well-known/jwks.json",
    "JWT_ISSUER": "user-service",
    "JWT_AUDIENCE": "oms",
    "ENVIRONMENT": "development"
})

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ArchitectureUnitTest:
    """아키텍처 단위 테스트"""
    
    def __init__(self):
        self.test_results = []
        
    async def test_di_container_setup(self):
        """의존성 주입 컨테이너 테스트"""
        logger.info("🔌 의존성 주입 컨테이너 테스트")
        
        try:
            from bootstrap.containers import Container
            from bootstrap.dependencies import get_branch_service
            
            # 컨테이너 초기화
            container = Container()
            
            # BranchService provider 확인
            if hasattr(container, 'branch_service_provider'):
                self.test_results.append("✅ BranchService DI Container 설정 완료")
                logger.info("✅ BranchService DI Container 설정 완료")
                return True
            else:
                self.test_results.append("❌ BranchService DI Container 설정 누락")
                return False
                
        except Exception as e:
            self.test_results.append(f"❌ DI Container 테스트 실패: {e}")
            logger.error(f"❌ DI Container 테스트 실패: {e}")
            return False
            
    async def test_branch_service_instantiation(self):
        """BranchService 인스턴스 생성 테스트"""
        logger.info("🏗️ BranchService 인스턴스 생성 테스트")
        
        try:
            from core.branch.service_refactored import BranchService
            from database.clients.unified_database_client import UnifiedDatabaseClient
            
            # Mock DB client 생성
            mock_db_client = type('MockDBClient', (), {
                'terminus_client': None
            })()
            
            # BranchService 인스턴스 생성
            branch_service = BranchService(
                db_client=mock_db_client,
                event_gateway=None
            )
            
            if branch_service:
                self.test_results.append("✅ BranchService 인스턴스 생성 성공")
                logger.info("✅ BranchService 인스턴스 생성 성공")
                return True
            else:
                self.test_results.append("❌ BranchService 인스턴스 생성 실패")
                return False
                
        except Exception as e:
            self.test_results.append(f"❌ BranchService 인스턴스 생성 실패: {e}")
            logger.error(f"❌ BranchService 인스턴스 생성 실패: {e}")
            return False
            
    async def test_auth_middleware_import(self):
        """AuthMiddleware 임포트 테스트"""
        logger.info("🔐 AuthMiddleware 임포트 테스트")
        
        try:
            from middleware.auth_middleware import AuthMiddleware
            
            # AuthMiddleware에 _validate_token_with_jwks 메서드 존재 확인
            if hasattr(AuthMiddleware, '_validate_token_with_jwks'):
                self.test_results.append("✅ AuthMiddleware JWKS 검증 메서드 존재")
                logger.info("✅ AuthMiddleware JWKS 검증 메서드 존재")
                return True
            else:
                self.test_results.append("❌ AuthMiddleware JWKS 검증 메서드 누락")
                return False
                
        except Exception as e:
            self.test_results.append(f"❌ AuthMiddleware 임포트 실패: {e}")
            logger.error(f"❌ AuthMiddleware 임포트 실패: {e}")
            return False
            
    async def test_secure_config_import(self):
        """SecureConfig 임포트 테스트"""
        logger.info("⚙️ SecureConfig 임포트 테스트")
        
        try:
            from config.secure_config import SecureConfigManager, JWTConfig
            
            # SecureConfigManager 인스턴스 생성
            config_manager = SecureConfigManager()
            
            # JWT 설정 확인
            jwt_config = config_manager.jwt_config
            
            if jwt_config and hasattr(jwt_config, 'jwks_url'):
                self.test_results.append("✅ SecureConfig JWT 설정 완료")
                logger.info("✅ SecureConfig JWT 설정 완료")
                return True
            else:
                self.test_results.append("❌ SecureConfig JWT 설정 오류")
                return False
                
        except Exception as e:
            self.test_results.append(f"❌ SecureConfig 임포트 실패: {e}")
            logger.error(f"❌ SecureConfig 임포트 실패: {e}")
            return False
            
    async def test_api_routes_import(self):
        """API 라우트 임포트 테스트 (간소화)"""
        logger.info("🛤️ API 라우트 임포트 테스트")
        
        try:
            # API 라우트 파일이 DI 패턴을 사용하는지 확인 (파일 읽기 방식)
            import pathlib
            branch_routes_path = oms_path / "api" / "v1" / "branch_routes.py"
            
            if branch_routes_path.exists():
                content = branch_routes_path.read_text()
                
                # DI 패턴 확인
                if "Depends(get_branch_service)" in content and "from bootstrap.dependencies import get_branch_service" in content:
                    self.test_results.append("✅ Branch API 라우트 DI 설정 완료")
                    logger.info("✅ Branch API 라우트 DI 설정 완료")
                    return True
                else:
                    self.test_results.append("❌ Branch API 라우트 DI 설정 누락")
                    return False
            else:
                self.test_results.append("❌ Branch API 라우트 파일 없음")
                return False
                
        except Exception as e:
            self.test_results.append(f"❌ API 라우트 테스트 실패: {e}")
            logger.error(f"❌ API 라우트 테스트 실패: {e}")
            return False
            
    async def test_no_security_vulnerabilities(self):
        """보안 취약점 제거 확인"""
        logger.info("🔒 보안 취약점 제거 확인")
        
        # shared-config.env 파일이 없는지 확인
        shared_config_path = Path(__file__).parent / "shared-config.env"
        if shared_config_path.exists():
            self.test_results.append("❌ shared-config.env 보안 취약점 파일 여전히 존재")
            return False
            
        # load_shared_config.py 파일이 없는지 확인  
        load_config_path = Path(__file__).parent / "load_shared_config.py"
        if load_config_path.exists():
            self.test_results.append("❌ load_shared_config.py 보안 취약점 파일 여전히 존재")
            return False
            
        self.test_results.append("✅ 보안 취약점 파일 모두 제거됨")
        logger.info("✅ 보안 취약점 파일 모두 제거됨")
        return True
        
    async def run_all_tests(self):
        """모든 테스트 실행"""
        logger.info("🎯 아키텍처 단위 테스트 시작")
        
        tests = [
            ("보안 취약점 제거 확인", self.test_no_security_vulnerabilities),
            ("DI Container 설정", self.test_di_container_setup),
            ("BranchService 인스턴스 생성", self.test_branch_service_instantiation),
            ("AuthMiddleware 임포트", self.test_auth_middleware_import),
            ("SecureConfig 임포트", self.test_secure_config_import),
            ("API 라우트 임포트", self.test_api_routes_import)
        ]
        
        all_passed = True
        for test_name, test_func in tests:
            logger.info(f"\n📋 {test_name} 테스트 중...")
            try:
                result = await test_func()
                if not result:
                    all_passed = False
                    logger.error(f"❌ {test_name} 테스트 실패")
                else:
                    logger.info(f"✅ {test_name} 테스트 통과")
            except Exception as e:
                all_passed = False
                logger.error(f"❌ {test_name} 테스트 중 예외: {e}")
                self.test_results.append(f"❌ {test_name} 테스트 중 예외: {e}")
                
        return all_passed
        
    def print_test_report(self):
        """테스트 결과 보고서"""
        logger.info("\n" + "="*60)
        logger.info("🎯 아키텍처 단위 테스트 결과")
        logger.info("="*60)
        
        success_count = len([r for r in self.test_results if r.startswith("✅")])
        total_count = len(self.test_results)
        
        for result in self.test_results:
            logger.info(f"  {result}")
            
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        logger.info(f"\n📊 성공률: {success_rate:.1f}% ({success_count}/{total_count})")
        
        if success_count == total_count:
            logger.info("\n🎉 모든 아키텍처 단위 테스트 통과!")
        else:
            logger.error("\n⚠️ 일부 테스트 실패.")
            
        return success_count == total_count

async def main():
    """메인 실행 함수"""
    tester = ArchitectureUnitTest()
    
    try:
        success = await tester.run_all_tests()
        final_result = tester.print_test_report()
        
        if final_result:
            logger.info("\n🏆 아키텍처 단위 테스트 성공!")
            return 0
        else:
            logger.error("\n🚨 아키텍처 단위 테스트 실패!")
            return 1
            
    except Exception as e:
        logger.error(f"\n🔥 테스트 중 치명적 오류: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)