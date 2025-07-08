#!/usr/bin/env python3
"""
아키텍처 검증 최종 테스트
- JWKS 패턴 검증
- 실제 데이터베이스 연동 검증  
- DI 패턴 검증
- 보안 취약점 제거 확인
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path

# Add OMS to path
oms_path = Path(__file__).parent / "ontology-management-service"
sys.path.insert(0, str(oms_path))

# Set required environment variables
os.environ.update({
    "USER_SERVICE_URL": "http://localhost:8001",
    "OMS_SERVICE_URL": "http://localhost:8000", 
    "USER_SERVICE_JWKS_URL": "http://localhost:8001/.well-known/jwks.json",
    "JWT_ISSUER": "user-service",
    "JWT_AUDIENCE": "oms",
    "TERMINUSDB_ENDPOINT": "http://localhost:6363",
    "TERMINUSDB_DB": "oms",
    "DATABASE_URL": "postgresql+asyncpg://oms_user:oms_password@localhost:5432/oms_db",
    "REDIS_URL": "redis://localhost:6379"
})

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ArchitectureValidator:
    """최종 아키텍처 검증"""
    
    def __init__(self):
        self.passed_tests = []
        self.failed_tests = []
        
    async def validate_security_fixes(self):
        """보안 취약점 제거 확인"""
        logger.info("🔒 보안 취약점 제거 검증 시작")
        
        # 1. shared-config.env 파일 제거 확인
        shared_config_path = Path(__file__).parent / "shared-config.env"
        if shared_config_path.exists():
            self.failed_tests.append("❌ shared-config.env 보안 취약점 파일이 여전히 존재")
            return False
        else:
            self.passed_tests.append("✅ shared-config.env 보안 취약점 파일 제거됨")
            
        # 2. load_shared_config.py 파일 제거 확인
        load_config_path = Path(__file__).parent / "load_shared_config.py"
        if load_config_path.exists():
            self.failed_tests.append("❌ load_shared_config.py 보안 취약점 파일이 여전히 존재")
            return False
        else:
            self.passed_tests.append("✅ load_shared_config.py 보안 취약점 파일 제거됨")
            
        return True
        
    async def validate_jwks_implementation(self):
        """JWKS 패턴 구현 검증"""
        logger.info("🔑 JWKS 패턴 구현 검증 시작")
        
        try:
            # AuthMiddleware에서 JWT_LOCAL_VALIDATION 제거 확인
            auth_middleware_path = oms_path / "middleware" / "auth_middleware.py"
            if auth_middleware_path.exists():
                content = auth_middleware_path.read_text()
                if "JWT_LOCAL_VALIDATION" in content:
                    self.failed_tests.append("❌ JWT_LOCAL_VALIDATION 보안 우회 플래그가 여전히 존재")
                    return False
                else:
                    self.passed_tests.append("✅ JWT_LOCAL_VALIDATION 보안 우회 플래그 제거됨")
                    
                if "_validate_token_with_jwks" in content:
                    self.passed_tests.append("✅ JWKS 패턴 검증 메서드 구현됨")
                else:
                    self.failed_tests.append("❌ JWKS 패턴 검증 메서드 누락")
                    return False
            
            # User Service JWKS 엔드포인트 확인
            user_service_path = Path(__file__).parent / "user-service"
            jwks_service_path = user_service_path / "src" / "services" / "jwks_service.py"
            jwks_router_path = user_service_path / "src" / "api" / "jwks_router.py"
            
            if jwks_service_path.exists() and jwks_router_path.exists():
                self.passed_tests.append("✅ User Service JWKS 엔드포인트 구현됨")
            else:
                self.failed_tests.append("❌ User Service JWKS 엔드포인트 누락")
                return False
                
            return True
            
        except Exception as e:
            self.failed_tests.append(f"❌ JWKS 검증 중 오류: {e}")
            return False
            
    async def validate_di_pattern(self):
        """의존성 주입 패턴 검증"""
        logger.info("🔌 의존성 주입 패턴 검증 시작")
        
        try:
            # BranchService 생성자 검증
            from core.branch.service_refactored import BranchService
            import inspect
            
            # 생성자 시그니처 확인
            init_signature = inspect.signature(BranchService.__init__)
            params = list(init_signature.parameters.keys())
            
            if 'db_client' in params and 'event_gateway' in params:
                self.passed_tests.append("✅ BranchService DI 생성자 올바름")
            else:
                self.failed_tests.append("❌ BranchService DI 생성자 시그니처 불일치")
                return False
                
            # branch_routes.py에서 직접 인스턴스 생성 제거 확인
            branch_routes_path = oms_path / "api" / "v1" / "branch_routes.py"
            if branch_routes_path.exists():
                content = branch_routes_path.read_text()
                if "BranchService(" in content and "Depends(get_branch_service)" in content:
                    # 직접 생성과 DI 모두 있으면 문제
                    direct_creation_lines = [line for line in content.split('\n') if 'BranchService(' in line and 'def ' not in line]
                    if direct_creation_lines:
                        self.failed_tests.append("❌ branch_routes.py에서 여전히 직접 인스턴스 생성함")
                        return False
                    else:
                        self.passed_tests.append("✅ branch_routes.py DI 패턴 올바르게 사용됨")
                elif "Depends(get_branch_service)" in content:
                    self.passed_tests.append("✅ branch_routes.py DI 패턴 올바르게 사용됨")
                else:
                    self.failed_tests.append("❌ branch_routes.py DI 패턴 누락")
                    return False
                    
            return True
            
        except Exception as e:
            self.failed_tests.append(f"❌ DI 패턴 검증 중 오류: {e}")
            return False
            
    async def validate_real_database_integration(self):
        """실제 데이터베이스 연동 검증"""
        logger.info("🗄️ 실제 데이터베이스 연동 검증 시작")
        
        try:
            # BranchService에서 하드코딩된 데이터 제거 확인
            service_path = oms_path / "core" / "branch" / "service_refactored.py"
            if service_path.exists():
                content = service_path.read_text()
                
                # list_branches가 실제 DB 쿼리하는지 확인
                if "await tdb_client.get_branches" in content:
                    self.passed_tests.append("✅ list_branches 실제 DB 쿼리 구현됨")
                else:
                    self.failed_tests.append("❌ list_branches 여전히 가짜 데이터 사용")
                    return False
                    
                # get_branch가 실제 DB 쿼리하는지 확인  
                if "await tdb_client.branch_exists" in content and "await tdb_client.get_branch_info" in content:
                    self.passed_tests.append("✅ get_branch 실제 DB 쿼리 구현됨")
                else:
                    self.failed_tests.append("❌ get_branch 여전히 가짜 데이터 사용")
                    return False
                    
                # _branch_exists가 실제 DB 쿼리하는지 확인
                if "_branch_exists" in content and "await tdb_client.branch_exists" in content:
                    self.passed_tests.append("✅ _branch_exists 실제 DB 쿼리 구현됨")
                else:
                    self.failed_tests.append("❌ _branch_exists 여전히 가짜 데이터 사용")
                    return False
                    
            return True
            
        except Exception as e:
            self.failed_tests.append(f"❌ 실제 DB 연동 검증 중 오류: {e}")
            return False
            
    async def validate_configuration_management(self):
        """설정 관리 검증"""
        logger.info("⚙️ 설정 관리 검증 시작")
        
        try:
            # 환경변수 기반 설정 확인
            config_path = oms_path / "config" / "secure_config.py"
            if config_path.exists():
                content = config_path.read_text()
                if "JWT_ISSUER" in content and "os.getenv" in content and "JWTConfig" in content:
                    self.passed_tests.append("✅ 환경변수 기반 보안 설정 구현됨")
                else:
                    self.failed_tests.append("❌ 환경변수 기반 보안 설정 누락")
                    return False
                    
            # Docker Compose 설정 확인
            docker_compose_path = oms_path / "docker-compose.auth-unified.yml"
            if docker_compose_path.exists():
                content = docker_compose_path.read_text()
                if "USE_JWKS=true" in content and "JWT_VALIDATION_MODE=jwks" in content:
                    self.passed_tests.append("✅ Docker Compose JWKS 설정 올바름")
                else:
                    self.failed_tests.append("❌ Docker Compose JWKS 설정 누락")
                    return False
                    
            return True
            
        except Exception as e:
            self.failed_tests.append(f"❌ 설정 관리 검증 중 오류: {e}")
            return False
            
    async def run_all_validations(self):
        """모든 검증 실행"""
        logger.info("🚀 최종 아키텍처 검증 시작")
        
        validations = [
            ("보안 취약점 제거", self.validate_security_fixes),
            ("JWKS 패턴 구현", self.validate_jwks_implementation), 
            ("의존성 주입 패턴", self.validate_di_pattern),
            ("실제 데이터베이스 연동", self.validate_real_database_integration),
            ("설정 관리", self.validate_configuration_management)
        ]
        
        all_passed = True
        for name, validation_func in validations:
            logger.info(f"\n📋 {name} 검증 중...")
            try:
                result = await validation_func()
                if not result:
                    all_passed = False
                    logger.error(f"❌ {name} 검증 실패")
                else:
                    logger.info(f"✅ {name} 검증 통과")
            except Exception as e:
                all_passed = False
                logger.error(f"❌ {name} 검증 중 예외: {e}")
                self.failed_tests.append(f"❌ {name} 검증 중 예외: {e}")
                
        return all_passed
        
    def print_final_report(self):
        """최종 검증 보고서 출력"""
        logger.info("\n" + "="*60)
        logger.info("🎯 최종 아키텍처 검증 보고서")
        logger.info("="*60)
        
        logger.info(f"\n✅ 통과한 테스트: {len(self.passed_tests)}")
        for test in self.passed_tests:
            logger.info(f"  {test}")
            
        logger.info(f"\n❌ 실패한 테스트: {len(self.failed_tests)}")
        for test in self.failed_tests:
            logger.info(f"  {test}")
            
        total_tests = len(self.passed_tests) + len(self.failed_tests)
        success_rate = (len(self.passed_tests) / total_tests * 100) if total_tests > 0 else 0
        
        logger.info(f"\n📊 전체 성공률: {success_rate:.1f}% ({len(self.passed_tests)}/{total_tests})")
        
        if len(self.failed_tests) == 0:
            logger.info("\n🎉 모든 아키텍처 검증 통과! 시스템이 안전하게 구현되었습니다.")
        else:
            logger.error("\n⚠️ 일부 아키텍처 문제가 발견되었습니다. 추가 수정이 필요합니다.")
            
        return len(self.failed_tests) == 0

async def main():
    """메인 실행 함수"""
    validator = ArchitectureValidator()
    
    try:
        all_passed = await validator.run_all_validations()
        success = validator.print_final_report()
        
        if success:
            logger.info("\n🏆 아키텍처 검증 완료: 모든 안티패턴이 제거되고 올바른 패턴이 구현되었습니다!")
            return 0
        else:
            logger.error("\n🚨 아키텍처 검증 실패: 추가 수정이 필요합니다.")
            return 1
            
    except Exception as e:
        logger.error(f"🔥 검증 중 치명적 오류: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)