#!/usr/bin/env python3
"""
미들웨어 개선사항 검증 스크립트
- 코드 레벨에서 순서 및 의존성 수정 확인
"""

import json
from datetime import datetime
import re


def validate_middleware_order():
    """app.py에서 미들웨어 순서 검증"""
    print("\n🔍 미들웨어 순서 검증 중...")
    
    # app.py 파일 읽기
    with open("ontology-management-service/bootstrap/app.py", "r") as f:
        content = f.read()
    
    # 미들웨어 추가 순서 추출
    middleware_pattern = r'app\.add_middleware\((\w+)'
    middlewares = re.findall(middleware_pattern, content)
    
    # 순서 검증
    validations = []
    
    # RequestIdMiddleware가 AuditLogMiddleware 앞에 있는지 확인
    request_id_idx = None
    audit_log_idx = None
    
    for i, mw in enumerate(middlewares):
        if "RequestIdMiddleware" in mw:
            request_id_idx = i
        elif "AuditLogMiddleware" in mw:
            audit_log_idx = i
    
    if request_id_idx is not None and audit_log_idx is not None:
        if request_id_idx < audit_log_idx:
            validations.append({
                "check": "RequestIdMiddleware before AuditLogMiddleware",
                "passed": True,
                "details": f"RequestIdMiddleware (index {request_id_idx}) is before AuditLogMiddleware (index {audit_log_idx})"
            })
        else:
            validations.append({
                "check": "RequestIdMiddleware before AuditLogMiddleware",
                "passed": False,
                "details": f"RequestIdMiddleware (index {request_id_idx}) should be before AuditLogMiddleware (index {audit_log_idx})"
            })
    
    return validations


def validate_user_context_provision():
    """AuthMiddleware가 user_context를 제공하는지 검증"""
    print("\n🔍 user_context 제공 검증 중...")
    
    validations = []
    
    # auth_middleware.py 파일 읽기
    with open("ontology-management-service/middleware/auth_middleware.py", "r") as f:
        content = f.read()
    
    # user_context 설정 확인
    if "request.state.user_context = user" in content:
        validations.append({
            "check": "AuthMiddleware provides user_context",
            "passed": True,
            "details": "AuthMiddleware correctly sets request.state.user_context"
        })
    else:
        validations.append({
            "check": "AuthMiddleware provides user_context",
            "passed": False,
            "details": "AuthMiddleware does not set request.state.user_context"
        })
    
    return validations


def generate_report(all_validations):
    """검증 보고서 생성"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "validations": all_validations,
        "summary": {
            "total": len(all_validations),
            "passed": sum(1 for v in all_validations if v["passed"]),
            "failed": sum(1 for v in all_validations if not v["passed"])
        }
    }
    
    # 보고서 출력
    print("\n" + "="*70)
    print("📊 미들웨어 개선사항 검증 결과")
    print("="*70)
    
    for validation in all_validations:
        status = "✅" if validation["passed"] else "❌"
        print(f"{status} {validation['check']}")
        print(f"   {validation['details']}")
    
    print(f"\n📈 요약: {report['summary']['passed']}/{report['summary']['total']} 검증 통과")
    
    # 파일로 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"middleware_validation_report_{timestamp}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 검증 보고서 저장됨: {filename}")
    
    return report


def main():
    """메인 함수"""
    print("🚀 미들웨어 개선사항 검증 시작...")
    
    all_validations = []
    
    # 각 검증 수행
    all_validations.extend(validate_middleware_order())
    all_validations.extend(validate_user_context_provision())
    
    # 보고서 생성
    report = generate_report(all_validations)
    
    if report["summary"]["failed"] == 0:
        print("\n🎉 모든 미들웨어 개선사항이 성공적으로 적용되었습니다!")
    else:
        print(f"\n⚠️  {report['summary']['failed']}개의 검증이 실패했습니다.")


if __name__ == "__main__":
    main()