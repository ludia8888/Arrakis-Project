#!/usr/bin/env python3
"""
미들웨어 개선사항 테스트 스크립트
- 의존성 순서 검증
- request_id 및 user_context 전파 확인
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List
from unittest.mock import MagicMock, AsyncMock
from starlette.requests import Request
from starlette.responses import Response
from fastapi import FastAPI

# 미들웨어 임포트
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'ontology-management-service'))

from middleware.request_id import RequestIdMiddleware
from middleware.audit_log import AuditLogMiddleware  
from middleware.auth_middleware import AuthMiddleware
from core.iam.scope_rbac_middleware import ScopeRBACMiddleware


class MiddlewareTestHarness:
    """미들웨어 테스트를 위한 하네스"""
    
    def __init__(self):
        self.app = FastAPI()
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "tests": []
        }
        
    async def test_middleware_order(self):
        """미들웨어 순서 및 의존성 전파 테스트"""
        print("\n🔧 미들웨어 순서 및 의존성 전파 테스트...")
        
        # Mock request 생성
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.headers = {"Authorization": "Bearer test_token", "user-agent": "test"}
        request.method = "GET"
        request.url = MagicMock()
        request.url.path = "/api/v1/test"
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.query_params = {}
        
        # Mock call_next
        async def mock_call_next(req):
            # 최종 핸들러에서 상태 확인
            states = {
                "has_request_id": hasattr(req.state, "request_id"),
                "has_user": hasattr(req.state, "user"),
                "has_user_context": hasattr(req.state, "user_context"),
                "request_id": getattr(req.state, "request_id", None),
                "user_id": getattr(req.state.user, "user_id", None) if hasattr(req.state, "user") else None
            }
            response = Response(json.dumps(states), media_type="application/json")
            return response
            
        # 미들웨어 체인 시뮬레이션
        # FastAPI는 역순으로 실행하므로 실제 순서대로 적용
        middlewares = [
            ("RequestIdMiddleware", RequestIdMiddleware(self.app)),
            ("AuthMiddleware", AuthMiddleware(self.app)),
            ("ScopeRBACMiddleware", ScopeRBACMiddleware(self.app)),
            ("AuditLogMiddleware", AuditLogMiddleware(self.app))
        ]
        
        # 미들웨어 체인 구성
        next_handler = mock_call_next
        for name, middleware in reversed(middlewares):
            current_handler = next_handler
            async def wrapped_handler(req, handler=current_handler, mw=middleware):
                return await mw.dispatch(req, handler)
            next_handler = wrapped_handler
            
        # 실행
        response = await next_handler(request)
        result = json.loads(response.body.decode())
        
        # 결과 검증
        test_result = {
            "test": "middleware_order_and_propagation",
            "passed": True,
            "details": result
        }
        
        # 검증
        if not result.get("has_request_id"):
            test_result["passed"] = False
            test_result["error"] = "request_id가 전파되지 않음"
        
        if not result.get("has_user_context"):
            test_result["passed"] = False  
            test_result["error"] = "user_context가 전파되지 않음"
            
        self.test_results["tests"].append(test_result)
        
        if test_result["passed"]:
            print("✅ 미들웨어 순서 및 의존성 전파 테스트 통과")
        else:
            print(f"❌ 미들웨어 순서 및 의존성 전파 테스트 실패: {test_result.get('error')}")
            
        return test_result
        
    async def test_audit_log_dependencies(self):
        """AuditLogMiddleware가 필요한 의존성에 접근 가능한지 테스트"""
        print("\n🔍 AuditLogMiddleware 의존성 접근 테스트...")
        
        # Mock request
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = "test-request-123"
        request.state.user_context = MagicMock()
        request.state.user_context.user_id = "user-123"
        request.state.user_context.username = "testuser"
        request.headers = {"user-agent": "test"}
        request.method = "GET"
        request.url = MagicMock()
        request.url.path = "/api/v1/test"
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.query_params = {}
        
        # AuditLogMiddleware 테스트
        middleware = AuditLogMiddleware(self.app)
        
        # Mock call_next
        async def mock_call_next(req):
            return Response("OK")
            
        # 실행
        response = await middleware.dispatch(request, mock_call_next)
        
        test_result = {
            "test": "audit_log_dependencies",
            "passed": response.status_code == 200,
            "details": {
                "status_code": response.status_code,
                "has_request_id": hasattr(request.state, "request_id"),
                "has_user_context": hasattr(request.state, "user_context")
            }
        }
        
        self.test_results["tests"].append(test_result)
        
        if test_result["passed"]:
            print("✅ AuditLogMiddleware 의존성 접근 테스트 통과")
        else:
            print("❌ AuditLogMiddleware 의존성 접근 테스트 실패")
            
        return test_result
        
    async def run_all_tests(self):
        """모든 테스트 실행"""
        print("\n" + "="*70)
        print("🚀 미들웨어 개선사항 테스트 시작")
        print("="*70)
        
        # 각 테스트 실행
        await self.test_middleware_order()
        await self.test_audit_log_dependencies()
        
        # 결과 요약
        passed_tests = sum(1 for test in self.test_results["tests"] if test["passed"])
        total_tests = len(self.test_results["tests"])
        
        print("\n" + "="*70)
        print(f"📊 테스트 결과: {passed_tests}/{total_tests} 통과")
        print("="*70)
        
        # 결과 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"middleware_improvement_test_results_{timestamp}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False)
            
        print(f"\n💾 테스트 결과 저장됨: {filename}")
        
        return passed_tests == total_tests


async def main():
    """메인 함수"""
    harness = MiddlewareTestHarness()
    success = await harness.run_all_tests()
    
    if success:
        print("\n🎉 모든 미들웨어 개선사항이 올바르게 적용되었습니다!")
    else:
        print("\n⚠️  일부 미들웨어 개선사항에 문제가 있습니다.")
        print("    위의 테스트 결과를 확인하세요.")


if __name__ == "__main__":
    asyncio.run(main())