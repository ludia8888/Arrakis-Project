#!/usr/bin/env python3
"""
CI/CD 파이프라인용 미들웨어 의존성 검증 스크립트
- 미들웨어 순서 및 의존성 자동 검증
- CI 빌드 실패 조건 포함
"""

import sys
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set, Tuple


class MiddlewareDependencyChecker:
    """미들웨어 의존성 검증기"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.oms_path = self.project_root / "ontology-management-service"
        self.errors = []
        self.warnings = []
        
    def extract_middleware_info(self, file_path: Path) -> Dict[str, Dict]:
        """미들웨어 파일에서 의존성 정보 추출"""
        if not file_path.exists():
            return {}
            
        with open(file_path, "r") as f:
            content = f.read()
            
        # 의존성 패턴 추출
        requires_patterns = [
            r'request\.state\.(\w+)',
            r'hasattr\(request\.state,\s*["\'](\w+)["\']\)',
            r'getattr\(request\.state,\s*["\'](\w+)["\']\)'
        ]
        
        provides_patterns = [
            r'request\.state\.(\w+)\s*=',
            r'setattr\(request\.state,\s*["\'](\w+)["\']'
        ]
        
        requires = set()
        provides = set()
        
        for pattern in requires_patterns:
            matches = re.findall(pattern, content)
            requires.update(matches)
            
        for pattern in provides_patterns:
            matches = re.findall(pattern, content)
            provides.update(matches)
            
        # 자기 자신이 제공하는 것은 의존성에서 제외
        requires = requires - provides
        
        return {
            "requires": list(requires),
            "provides": list(provides)
        }
        
    def extract_middleware_order(self) -> List[str]:
        """app.py에서 미들웨어 실행 순서 추출"""
        app_file = self.oms_path / "bootstrap" / "app.py"
        
        if not app_file.exists():
            self.errors.append(f"app.py 파일을 찾을 수 없습니다: {app_file}")
            return []
            
        with open(app_file, "r") as f:
            content = f.read()
            
        # 미들웨어 추가 순서 추출
        pattern = r'app\.add_middleware\((\w+)'
        middlewares = re.findall(pattern, content)
        
        # FastAPI는 LIFO 순서로 실행 (나중에 추가된 것이 먼저 실행)
        # 따라서 파일에 나타난 순서를 그대로 반환 (인덱스가 클수록 먼저 실행)
        return middlewares
        
    def check_dependencies(self) -> bool:
        """미들웨어 의존성 검증"""
        print("🔍 미들웨어 의존성 검증 시작...")
        
        # 미들웨어 정보 수집
        middleware_info = {}
        middleware_dir = self.oms_path / "middleware"
        
        # 알려진 미들웨어 파일들
        known_middlewares = {
            "RequestIdMiddleware": "request_id.py",
            "AuditLogMiddleware": "audit_log.py",
            "AuthMiddleware": "auth_middleware.py",
            "ScopeRBACMiddleware": "../core/iam/scope_rbac_middleware.py"
        }
        
        for mw_name, mw_file in known_middlewares.items():
            file_path = middleware_dir / mw_file if not mw_file.startswith("..") else self.oms_path / mw_file.lstrip("../")
            info = self.extract_middleware_info(file_path)
            if info:
                middleware_info[mw_name] = info
                
        # 실행 순서 추출
        execution_order = self.extract_middleware_order()
        
        # 의존성 검증
        # FastAPI는 역순으로 실행하므로 뒤에서부터 검증
        provided_states = set()
        
        for i in range(len(execution_order) - 1, -1, -1):
            middleware = execution_order[i]
            if middleware not in middleware_info:
                continue
                
            info = middleware_info[middleware]
            
            # 필요한 상태가 제공되는지 확인
            for required in info["requires"]:
                if required not in provided_states:
                    self.errors.append(
                        f"{middleware}가 '{required}'를 필요로 하지만 아직 제공되지 않았습니다. "
                        f"(인덱스: {i}, 실행 순서: {len(execution_order) - i}/{len(execution_order)})"
                    )
                    
            # 제공하는 상태 추가
            provided_states.update(info["provides"])
            
        return len(self.errors) == 0
        
    def check_critical_rules(self) -> bool:
        """중요 규칙 검증"""
        print("\n📋 중요 규칙 검증 중...")
        
        rules_passed = True
        
        # 규칙 1: RequestIdMiddleware는 AuditLogMiddleware보다 먼저 실행되어야 함
        execution_order = self.extract_middleware_order()
        
        try:
            request_id_idx = execution_order.index("RequestIdMiddleware")
            audit_log_idx = execution_order.index("AuditLogMiddleware")
            
            # FastAPI는 나중에 추가된 것이 먼저 실행
            # RequestIdMiddleware가 먼저 실행되려면 더 뒤에(큰 인덱스) 있어야 함
            if request_id_idx < audit_log_idx:
                self.errors.append(
                    f"RequestIdMiddleware가 AuditLogMiddleware 이후에 실행됩니다. "
                    f"(RequestId 인덱스: {request_id_idx}, AuditLog 인덱스: {audit_log_idx})"
                )
                rules_passed = False
            else:
                print("✅ RequestIdMiddleware가 AuditLogMiddleware보다 먼저 실행됩니다.")
                
        except ValueError as e:
            self.warnings.append(f"미들웨어를 찾을 수 없습니다: {e}")
            
        # 규칙 2: AuthMiddleware가 user_context를 제공해야 함
        auth_file = self.oms_path / "middleware" / "auth_middleware.py"
        if auth_file.exists():
            with open(auth_file, "r") as f:
                content = f.read()
                
            if "request.state.user_context = user" in content:
                print("✅ AuthMiddleware가 user_context를 제공합니다.")
            else:
                self.errors.append("AuthMiddleware가 user_context를 제공하지 않습니다.")
                rules_passed = False
                
        return rules_passed
        
    def generate_report(self) -> Dict:
        """검증 보고서 생성"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "project_root": str(self.project_root),
            "errors": self.errors,
            "warnings": self.warnings,
            "passed": len(self.errors) == 0
        }
        
        return report
        
    def run(self) -> bool:
        """전체 검증 실행"""
        print("="*70)
        print("🚀 CI/CD 미들웨어 의존성 검증")
        print("="*70)
        
        # 의존성 검증
        dependencies_ok = self.check_dependencies()
        
        # 중요 규칙 검증
        rules_ok = self.check_critical_rules()
        
        # 보고서 생성
        report = self.generate_report()
        
        # 결과 출력
        print("\n" + "="*70)
        print("📊 검증 결과")
        print("="*70)
        
        if report["errors"]:
            print("\n❌ 오류:")
            for error in report["errors"]:
                print(f"  - {error}")
                
        if report["warnings"]:
            print("\n⚠️  경고:")
            for warning in report["warnings"]:
                print(f"  - {warning}")
                
        if report["passed"]:
            print("\n✅ 모든 검증을 통과했습니다!")
        else:
            print(f"\n❌ {len(report['errors'])}개의 오류가 발견되었습니다.")
            
        # CI 환경에서 실행 중인 경우 JSON 출력
        if self.is_ci_environment():
            output_file = "middleware_ci_report.json"
            with open(output_file, "w") as f:
                json.dump(report, f, indent=2)
            print(f"\n💾 CI 보고서 저장됨: {output_file}")
            
        return report["passed"]
        
    def is_ci_environment(self) -> bool:
        """CI 환경인지 확인"""
        import os
        ci_vars = ["CI", "CONTINUOUS_INTEGRATION", "GITHUB_ACTIONS", "JENKINS", "GITLAB_CI"]
        return any(os.environ.get(var) for var in ci_vars)


def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="미들웨어 의존성 CI/CD 검증")
    parser.add_argument(
        "--project-root",
        default=".",
        help="프로젝트 루트 디렉토리 (기본값: 현재 디렉토리)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="경고도 오류로 처리"
    )
    
    args = parser.parse_args()
    
    # 검증 실행
    checker = MiddlewareDependencyChecker(args.project_root)
    passed = checker.run()
    
    # strict 모드에서는 경고도 실패로 처리
    if args.strict and checker.warnings:
        print("\n❌ Strict 모드: 경고가 발견되어 실패 처리합니다.")
        passed = False
        
    # CI 환경에서는 실패 시 exit code 1 반환
    if not passed:
        sys.exit(1)
        

if __name__ == "__main__":
    main()