#!/usr/bin/env python3
"""
OMS Core 모듈 상태 검사 스크립트
모든 core 모듈들의 import 가능 여부와 기본 동작을 검증
"""

import os
import sys
import importlib
import traceback
from pathlib import Path
from datetime import datetime
import json

# OMS 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ontology-management-service'))


class CoreModuleHealthChecker:
    """Core 모듈 상태 검사기"""
    
    def __init__(self):
        self.core_path = Path("ontology-management-service/core")
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "modules": {},
            "summary": {
                "total": 0,
                "success": 0,
                "failed": 0,
                "warnings": 0
            }
        }
        
    def check_module_imports(self):
        """모든 core 모듈의 import 테스트"""
        print("\n🔍 Core 모듈 Import 검사 시작...")
        print("="*70)
        
        # 주요 모듈 목록
        modules_to_check = [
            "core.auth",
            "core.auth_utils",
            "core.auth_utils.database_context",
            "core.auth_utils.secure_author_provider",
            "core.branch.service",
            "core.branch.service_refactored",
            "core.document.service",
            "core.schema.service",
            "core.schema.repository",
            "core.property.service",
            "core.iam.iam_integration",
            "core.iam.scope_rbac_middleware",
            "core.validation.service",
            "core.validation.schema_validator",
            "core.time_travel.service",
            "core.health.health_checker",
            "core.audit.audit_service",
            "core.resilience.unified_circuit_breaker",
            "core.versioning.version_service",
            "core.shadow_index.manager",
            "core.integrations.user_service_client",
            "core.integrations.iam_service_client"
        ]
        
        for module_name in modules_to_check:
            self.results["summary"]["total"] += 1
            
            try:
                # 모듈 import 시도
                module = importlib.import_module(module_name)
                
                # 모듈 정보 수집
                module_info = {
                    "status": "success",
                    "path": getattr(module, "__file__", "unknown"),
                    "attributes": [],
                    "classes": [],
                    "functions": []
                }
                
                # 모듈 속성 검사
                for attr_name in dir(module):
                    if not attr_name.startswith("_"):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type):
                            module_info["classes"].append(attr_name)
                        elif callable(attr):
                            module_info["functions"].append(attr_name)
                        else:
                            module_info["attributes"].append(attr_name)
                
                self.results["modules"][module_name] = module_info
                self.results["summary"]["success"] += 1
                print(f"✅ {module_name} - OK")
                
            except ImportError as e:
                self.results["modules"][module_name] = {
                    "status": "import_error",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
                self.results["summary"]["failed"] += 1
                print(f"❌ {module_name} - Import Error: {e}")
                
            except Exception as e:
                self.results["modules"][module_name] = {
                    "status": "error",
                    "error": str(e),
                    "type": type(e).__name__,
                    "traceback": traceback.format_exc()
                }
                self.results["summary"]["failed"] += 1
                print(f"❌ {module_name} - Error: {type(e).__name__}: {e}")
                
    def check_critical_dependencies(self):
        """중요 의존성 확인"""
        print("\n🔧 중요 의존성 확인...")
        print("-"*70)
        
        critical_deps = {
            "terminusdb_client": "TerminusDB 클라이언트",
            "redis": "Redis (캐싱/분산 락)",
            "httpx": "HTTP 클라이언트 (서비스 간 통신)",
            "pydantic": "데이터 검증",
            "fastapi": "웹 프레임워크"
        }
        
        for package, description in critical_deps.items():
            try:
                module = importlib.import_module(package)
                version = getattr(module, "__version__", "unknown")
                print(f"✅ {package} ({description}): {version}")
            except ImportError:
                print(f"❌ {package} ({description}): 설치되지 않음")
                self.results["summary"]["warnings"] += 1
                
    def check_database_connection(self):
        """데이터베이스 연결 확인"""
        print("\n🗄️  데이터베이스 연결 확인...")
        print("-"*70)
        
        try:
            from database.clients.terminus_db import get_terminus_client
            from config.secure_config import secure_config
            
            # TerminusDB 연결 정보 확인
            terminus_config = secure_config.terminus
            print(f"TerminusDB Server: {terminus_config.server}")
            print(f"TerminusDB Database: {terminus_config.db}")
            
            # 실제 연결은 테스트하지 않음 (환경 의존적)
            print("⚠️  실제 연결 테스트는 수행하지 않음 (환경 설정 필요)")
            
        except Exception as e:
            print(f"❌ 데이터베이스 설정 확인 실패: {e}")
            self.results["summary"]["warnings"] += 1
            
    def check_service_integration(self):
        """서비스 통합 확인"""
        print("\n🔗 서비스 통합 설정 확인...")
        print("-"*70)
        
        try:
            from config.secure_config import secure_config
            
            services = {
                "user_service": secure_config.get_service_url("user_service"),
                "iam_service": secure_config.get_service_url("iam_service"),
                "audit_service": secure_config.get_service_url("audit_service")
            }
            
            for service_name, url in services.items():
                print(f"✅ {service_name}: {url}")
                
        except Exception as e:
            print(f"❌ 서비스 통합 설정 확인 실패: {e}")
            self.results["summary"]["warnings"] += 1
            
    def analyze_problems(self):
        """문제점 분석 및 권장사항"""
        print("\n📊 분석 결과")
        print("="*70)
        
        # 실패한 모듈 분석
        failed_modules = {k: v for k, v in self.results["modules"].items() 
                         if v.get("status") != "success"}
        
        if failed_modules:
            print("\n❌ 실패한 모듈들:")
            for module_name, info in failed_modules.items():
                print(f"\n  {module_name}:")
                print(f"    상태: {info.get('status')}")
                print(f"    오류: {info.get('error')}")
                
                # 일반적인 문제 패턴 확인
                error_msg = str(info.get('error', ''))
                if "No module named" in error_msg:
                    print("    💡 권장: 필요한 패키지 설치 확인")
                elif "circular import" in error_msg:
                    print("    💡 권장: 순환 import 문제 해결 필요")
                elif "AttributeError" in info.get('type', ''):
                    print("    💡 권장: 모듈 구조 또는 속성 확인 필요")
                    
        # 성공한 주요 모듈 확인
        success_modules = {k: v for k, v in self.results["modules"].items() 
                          if v.get("status") == "success"}
        
        if success_modules:
            print(f"\n✅ 성공적으로 로드된 모듈: {len(success_modules)}개")
            
            # 주요 서비스 모듈 확인
            key_services = ["core.schema.service", "core.document.service", 
                           "core.branch.service", "core.validation.service"]
            loaded_services = [s for s in key_services if s in success_modules]
            
            if len(loaded_services) == len(key_services):
                print("  ✅ 모든 핵심 서비스 모듈이 정상 로드됨")
            else:
                missing = set(key_services) - set(loaded_services)
                print(f"  ⚠️  일부 핵심 서비스 모듈 로드 실패: {missing}")
                
    def generate_report(self):
        """최종 보고서 생성"""
        print("\n" + "="*70)
        print("📋 최종 요약")
        print("="*70)
        
        summary = self.results["summary"]
        print(f"전체 모듈: {summary['total']}")
        print(f"성공: {summary['success']} ({summary['success']/summary['total']*100:.1f}%)")
        print(f"실패: {summary['failed']} ({summary['failed']/summary['total']*100:.1f}%)")
        print(f"경고: {summary['warnings']}")
        
        # 상태 판정
        if summary['failed'] == 0:
            print("\n🎉 모든 Core 모듈이 정상적으로 작동합니다!")
        elif summary['success'] / summary['total'] >= 0.8:
            print("\n⚠️  대부분의 Core 모듈이 작동하지만 일부 문제가 있습니다.")
        else:
            print("\n❌ Core 모듈에 심각한 문제가 있습니다.")
            
        # 결과 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"core_module_health_report_{timestamp}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
            
        print(f"\n💾 상세 보고서 저장됨: {filename}")
        
        return summary['failed'] == 0
        
    def run(self):
        """전체 검사 실행"""
        print("🚀 OMS Core 모듈 상태 검사 시작")
        print("="*70)
        
        # 각 검사 수행
        self.check_module_imports()
        self.check_critical_dependencies()
        self.check_database_connection()
        self.check_service_integration()
        self.analyze_problems()
        
        # 최종 보고서
        return self.generate_report()


def main():
    """메인 함수"""
    checker = CoreModuleHealthChecker()
    all_healthy = checker.run()
    
    if not all_healthy:
        print("\n💡 문제 해결을 위한 일반적인 단계:")
        print("1. requirements.txt 확인 및 패키지 설치")
        print("2. 환경 변수 설정 확인 (.env 파일)")
        print("3. 순환 import 문제 확인")
        print("4. 데이터베이스 연결 설정 확인")
        

if __name__ == "__main__":
    main()