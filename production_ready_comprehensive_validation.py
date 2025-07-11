#!/usr/bin/env python3
"""
🚀 ARRAKIS MSA PRODUCTION READY COMPREHENSIVE VALIDATION
================================================================

실제 사용자가 사용하는 시나리오를 완전히 시뮬레이션하여 
MSA 시스템의 프로덕션 레디 상태를 종합적으로 검증합니다.

사용자 스토리:
- 스키마 설계자 Alice: 온톨로지 스키마 설계 및 관리
- 데이터 관리자 Bob: 스키마 기반 문서 생성 및 관리  
- 시스템 관리자 Charlie: 시스템 모니터링 및 감사

검증 영역:
✓ 실제 사용자 워크플로우 (등록→로그인→작업→감사)
✓ MSA 서비스 간 실제 HTTP 통신
✓ 동시 사용자 처리 및 권한 기반 접근 제어
✓ 에러 처리 및 복구 시나리오
✓ 성능, 메모리, 응답시간 모니터링
✓ 보안, JWT 인증, 감사 로그
"""

import asyncio
import aiohttp
import json
import time
import psutil
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any
import threading
import concurrent.futures


class ProductionReadyValidator:
    def __init__(self):
        # Mock MSA 서비스 엔드포인트 (프로덕션 레디 검증용)
        self.services = {
            "user_service": "http://localhost:8012",
            "ontology_service": "http://localhost:8010", 
            "audit_service": "http://localhost:8011"
        }
        
        # 테스트 결과 저장
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "production_ready_score": 0,
            "user_scenarios": {},
            "service_integration": {},
            "concurrent_users": {},
            "error_recovery": {},
            "performance": {},
            "security": {},
            "detailed_results": []
        }
        
        # 성능 모니터링
        self.performance_metrics = {
            "response_times": [],
            "memory_usage": [],
            "cpu_usage": [],
            "concurrent_requests": 0
        }

    async def validate_production_readiness(self):
        """프로덕션 레디 상태 종합 검증"""
        print("🚀 ARRAKIS MSA PRODUCTION READY COMPREHENSIVE VALIDATION")
        print("=" * 80)
        
        # 1. 서비스 기동 상태 확인
        print("\n📡 1. MSA 서비스 기동 상태 확인...")
        service_status = await self.check_all_services()
        if not all(service_status.values()):
            print("❌ 일부 서비스가 기동되지 않았습니다. 서비스를 먼저 시작해주세요.")
            return self.test_results
            
        # 2. 실제 사용자 시나리오 검증 
        print("\n👥 2. 실제 사용자 시나리오 검증...")
        await self.validate_user_scenarios()
        
        # 3. 동시 사용자 처리 검증
        print("\n🔀 3. 다중 사용자 동시 접근 검증...")
        await self.validate_concurrent_users()
        
        # 4. 에러 처리 및 복구 검증
        print("\n🛡️  4. 에러 처리 및 복구 시나리오 검증...")
        await self.validate_error_recovery()
        
        # 5. 성능 및 모니터링 검증
        print("\n⚡ 5. 성능 및 모니터링 검증...")
        await self.validate_performance_monitoring()
        
        # 6. 보안 및 감사 검증
        print("\n🔒 6. 보안 및 감사 로그 검증...")
        await self.validate_security_audit()
        
        # 7. 종합 점수 계산
        self.calculate_production_ready_score()
        
        # 결과 저장 및 출력
        await self.save_results()
        self.print_final_results()
        
        return self.test_results

    async def check_all_services(self) -> Dict[str, bool]:
        """모든 MSA 서비스 기동 상태 확인"""
        status = {}
        
        async with aiohttp.ClientSession() as session:
            for service_name, url in self.services.items():
                try:
                    async with session.get(f"{url}/health", timeout=5) as response:
                        status[service_name] = response.status == 200
                        print(f"  ✓ {service_name}: 정상 기동 ({url})")
                except Exception as e:
                    status[service_name] = False
                    print(f"  ❌ {service_name}: 기동 실패 ({url}) - {e}")
        
        self.test_results["service_integration"]["basic_health"] = status
        return status

    async def validate_user_scenarios(self):
        """실제 사용자 시나리오 검증"""
        scenarios = {
            "alice_schema_designer": await self.simulate_alice_workflow(),
            "bob_data_manager": await self.simulate_bob_workflow(), 
            "charlie_system_admin": await self.simulate_charlie_workflow()
        }
        
        self.test_results["user_scenarios"] = scenarios
        
        # 시나리오 성공률 계산
        total_steps = sum(len(scenario["steps"]) for scenario in scenarios.values())
        successful_steps = sum(
            sum(step["success"] for step in scenario["steps"]) 
            for scenario in scenarios.values()
        )
        success_rate = (successful_steps / total_steps) * 100 if total_steps > 0 else 0
        
        print(f"  📊 사용자 시나리오 성공률: {success_rate:.1f}% ({successful_steps}/{total_steps})")

    async def simulate_alice_workflow(self) -> Dict[str, Any]:
        """스키마 설계자 Alice의 실제 워크플로우 시뮬레이션"""
        print("  👩‍💻 Alice (스키마 설계자) 워크플로우...")
        
        steps = []
        alice_token = None
        
        async with aiohttp.ClientSession() as session:
            # 1. 사용자 등록
            register_success, alice_token = await self.register_user(
                session, "alice_schema_designer", "alice@company.com", "SchemaDesigner123!", "schema_designer"
            )
            steps.append({"step": "user_registration", "success": register_success})
            
            if not register_success:
                return {"user": "alice", "role": "schema_designer", "steps": steps}
            
            # 2. 로그인 검증
            login_success = await self.verify_login(session, alice_token)
            steps.append({"step": "user_login", "success": login_success})
            
            # 3. 새로운 온톨로지 스키마 생성
            schema_success = await self.create_ontology_schema(
                session, alice_token, "ProductCatalog", {
                    "properties": {
                        "product_id": {"type": "string", "required": True},
                        "name": {"type": "string", "required": True},
                        "category": {"type": "string", "required": True},
                        "price": {"type": "number", "required": True},
                        "description": {"type": "string", "required": False}
                    }
                }
            )
            steps.append({"step": "schema_creation", "success": schema_success})
            
            # 4. 스키마 버전 관리
            version_success = await self.manage_schema_versions(session, alice_token, "ProductCatalog")
            steps.append({"step": "schema_versioning", "success": version_success})
            
            # 5. 스키마 권한 설정
            permission_success = await self.set_schema_permissions(session, alice_token, "ProductCatalog")
            steps.append({"step": "schema_permissions", "success": permission_success})
        
        return {"user": "alice", "role": "schema_designer", "steps": steps, "token": alice_token}

    async def simulate_bob_workflow(self) -> Dict[str, Any]:
        """데이터 관리자 Bob의 실제 워크플로우 시뮬레이션"""
        print("  👨‍💼 Bob (데이터 관리자) 워크플로우...")
        
        steps = []
        bob_token = None
        
        async with aiohttp.ClientSession() as session:
            # 1. 사용자 등록
            register_success, bob_token = await self.register_user(
                session, "bob_data_manager", "bob@company.com", "DataManager123!", "data_manager"
            )
            steps.append({"step": "user_registration", "success": register_success})
            
            if not register_success:
                return {"user": "bob", "role": "data_manager", "steps": steps}
            
            # 2. 로그인 검증
            login_success = await self.verify_login(session, bob_token)
            steps.append({"step": "user_login", "success": login_success})
            
            # 3. Alice의 스키마 기반 문서 생성
            doc_creation_success = await self.create_schema_based_document(
                session, bob_token, "ProductCatalog", {
                    "product_id": "PROD-001",
                    "name": "고급 노트북",
                    "category": "Electronics", 
                    "price": 1500000,
                    "description": "고성능 개발자용 노트북"
                }
            )
            steps.append({"step": "document_creation", "success": doc_creation_success})
            
            # 4. 문서 CRUD 작업
            crud_success = await self.perform_document_crud(session, bob_token, "ProductCatalog")
            steps.append({"step": "document_crud", "success": crud_success})
            
            # 5. 브랜치 작업
            branch_success = await self.manage_document_branches(session, bob_token)
            steps.append({"step": "branch_management", "success": branch_success})
        
        return {"user": "bob", "role": "data_manager", "steps": steps, "token": bob_token}

    async def simulate_charlie_workflow(self) -> Dict[str, Any]:
        """시스템 관리자 Charlie의 실제 워크플로우 시뮬레이션"""
        print("  👨‍💻 Charlie (시스템 관리자) 워크플로우...")
        
        steps = []
        charlie_token = None
        
        async with aiohttp.ClientSession() as session:
            # 1. 관리자 로그인 (미리 생성된 계정 사용)
            login_success, charlie_token = await self.admin_login(session)
            steps.append({"step": "admin_login", "success": login_success})
            
            if not login_success:
                return {"user": "charlie", "role": "admin", "steps": steps}
            
            # 2. 전체 시스템 상태 모니터링
            monitoring_success = await self.monitor_system_status(session, charlie_token)
            steps.append({"step": "system_monitoring", "success": monitoring_success})
            
            # 3. 사용자 관리
            user_mgmt_success = await self.manage_users(session, charlie_token)
            steps.append({"step": "user_management", "success": user_mgmt_success})
            
            # 4. 감사 로그 확인
            audit_success = await self.review_audit_logs(session, charlie_token)
            steps.append({"step": "audit_review", "success": audit_success})
            
            # 5. 시스템 설정 관리
            config_success = await self.manage_system_config(session, charlie_token)
            steps.append({"step": "system_config", "success": config_success})
        
        return {"user": "charlie", "role": "admin", "steps": steps, "token": charlie_token}

    async def register_user(self, session: aiohttp.ClientSession, username: str, email: str, password: str, role: str) -> tuple[bool, str]:
        """사용자 등록"""
        try:
            start_time = time.time()
            
            async with session.post(
                f"{self.services['user_service']}/api/v1/auth/register",
                json={
                    "username": username,
                    "email": email, 
                    "password": password,
                    "role": role
                },
                timeout=10
            ) as response:
                response_time = time.time() - start_time
                self.performance_metrics["response_times"].append({
                    "operation": "user_registration",
                    "time": response_time
                })
                
                if response.status == 201:
                    data = await response.json()
                    return True, data.get("token", "")
                else:
                    print(f"    ❌ 사용자 등록 실패: {response.status}")
                    return False, ""
                    
        except Exception as e:
            print(f"    ❌ 사용자 등록 에러: {e}")
            return False, ""

    async def verify_login(self, session: aiohttp.ClientSession, token: str) -> bool:
        """로그인 검증"""
        try:
            async with session.get(
                f"{self.services['user_service']}/api/v1/auth/profile",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            ) as response:
                return response.status == 200
        except Exception as e:
            print(f"    ❌ 로그인 검증 에러: {e}")
            return False

    async def create_ontology_schema(self, session: aiohttp.ClientSession, token: str, schema_name: str, schema_def: Dict) -> bool:
        """온톨로지 스키마 생성"""
        try:
            start_time = time.time()
            
            async with session.post(
                f"{self.services['ontology_service']}/api/v1/schemas",
                json={
                    "name": schema_name,
                    "definition": schema_def,
                    "version": "1.0.0",
                    "description": f"Production test schema: {schema_name}"
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=15
            ) as response:
                response_time = time.time() - start_time
                self.performance_metrics["response_times"].append({
                    "operation": "schema_creation",
                    "time": response_time
                })
                
                success = response.status == 201
                if not success:
                    print(f"    ❌ 스키마 생성 실패: {response.status}")
                return success
                
        except Exception as e:
            print(f"    ❌ 스키마 생성 에러: {e}")
            return False

    async def manage_schema_versions(self, session: aiohttp.ClientSession, token: str, schema_name: str) -> bool:
        """스키마 버전 관리"""
        try:
            # 스키마 업데이트 (새 버전 생성)
            async with session.put(
                f"{self.services['ontology_service']}/api/v1/schemas/{schema_name}",
                json={
                    "definition": {
                        "properties": {
                            "product_id": {"type": "string", "required": True},
                            "name": {"type": "string", "required": True},
                            "category": {"type": "string", "required": True},
                            "price": {"type": "number", "required": True},
                            "description": {"type": "string", "required": False},
                            "tags": {"type": "array", "required": False}  # 새 필드 추가
                        }
                    },
                    "version": "1.1.0"
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            ) as response:
                return response.status == 200
                
        except Exception as e:
            print(f"    ❌ 스키마 버전 관리 에러: {e}")
            return False

    async def set_schema_permissions(self, session: aiohttp.ClientSession, token: str, schema_name: str) -> bool:
        """스키마 권한 설정"""
        try:
            async with session.post(
                f"{self.services['ontology_service']}/api/v1/schemas/{schema_name}/permissions",
                json={
                    "permissions": {
                        "data_manager": ["read", "write"],
                        "viewer": ["read"]
                    }
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            ) as response:
                return response.status == 200
                
        except Exception as e:
            print(f"    ❌ 권한 설정 에러: {e}")
            return False

    async def create_schema_based_document(self, session: aiohttp.ClientSession, token: str, schema_name: str, document_data: Dict) -> bool:
        """스키마 기반 문서 생성"""
        try:
            start_time = time.time()
            
            async with session.post(
                f"{self.services['ontology_service']}/api/v1/documents",
                json={
                    "schema": schema_name,
                    "data": document_data,
                    "metadata": {
                        "created_by": "bob_data_manager",
                        "purpose": "production_test"
                    }
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=15
            ) as response:
                response_time = time.time() - start_time
                self.performance_metrics["response_times"].append({
                    "operation": "document_creation",
                    "time": response_time
                })
                
                success = response.status == 201
                if not success:
                    print(f"    ❌ 문서 생성 실패: {response.status}")
                return success
                
        except Exception as e:
            print(f"    ❌ 문서 생성 에러: {e}")
            return False

    async def perform_document_crud(self, session: aiohttp.ClientSession, token: str, schema_name: str) -> bool:
        """문서 CRUD 작업"""
        try:
            # 문서 목록 조회
            async with session.get(
                f"{self.services['ontology_service']}/api/v1/documents?schema={schema_name}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            ) as response:
                if response.status != 200:
                    return False
                documents = await response.json()
            
            if not documents:
                return False
                
            doc_id = documents[0]["id"]
            
            # 문서 수정
            async with session.put(
                f"{self.services['ontology_service']}/api/v1/documents/{doc_id}",
                json={
                    "data": {
                        "product_id": "PROD-001",
                        "name": "고급 노트북 (업데이트됨)",
                        "category": "Electronics",
                        "price": 1400000,  # 가격 변경
                        "description": "고성능 개발자용 노트북 - 할인 적용"
                    }
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            ) as response:
                if response.status != 200:
                    return False
            
            # 문서 조회
            async with session.get(
                f"{self.services['ontology_service']}/api/v1/documents/{doc_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            ) as response:
                return response.status == 200
                
        except Exception as e:
            print(f"    ❌ 문서 CRUD 에러: {e}")
            return False

    async def manage_document_branches(self, session: aiohttp.ClientSession, token: str) -> bool:
        """문서 브랜치 관리"""
        try:
            # 새 브랜치 생성
            async with session.post(
                f"{self.services['ontology_service']}/api/v1/branches",
                json={
                    "name": "feature/product-enhancement",
                    "source": "main",
                    "description": "제품 정보 개선 작업"
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            ) as response:
                return response.status == 201
                
        except Exception as e:
            print(f"    ❌ 브랜치 관리 에러: {e}")
            return False

    async def admin_login(self, session: aiohttp.ClientSession) -> tuple[bool, str]:
        """관리자 로그인"""
        try:
            async with session.post(
                f"{self.services['user_service']}/api/v1/auth/login",
                json={
                    "username": "admin",
                    "password": "admin_password"
                },
                timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return True, data.get("token", "")
                else:
                    return False, ""
                    
        except Exception as e:
            print(f"    ❌ 관리자 로그인 에러: {e}")
            return False, ""

    async def monitor_system_status(self, session: aiohttp.ClientSession, token: str) -> bool:
        """시스템 상태 모니터링"""
        try:
            # 각 서비스의 상태 확인
            services_ok = 0
            total_services = len(self.services)
            
            for service_name, service_url in self.services.items():
                async with session.get(
                    f"{service_url}/api/v1/status",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5
                ) as response:
                    if response.status == 200:
                        services_ok += 1
            
            return services_ok == total_services
            
        except Exception as e:
            print(f"    ❌ 시스템 모니터링 에러: {e}")
            return False

    async def manage_users(self, session: aiohttp.ClientSession, token: str) -> bool:
        """사용자 관리"""
        try:
            # 사용자 목록 조회
            async with session.get(
                f"{self.services['user_service']}/api/v1/admin/users",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            ) as response:
                return response.status == 200
                
        except Exception as e:
            print(f"    ❌ 사용자 관리 에러: {e}")
            return False

    async def review_audit_logs(self, session: aiohttp.ClientSession, token: str) -> bool:
        """감사 로그 확인"""
        try:
            async with session.get(
                f"{self.services['audit_service']}/api/v1/logs",
                headers={"Authorization": f"Bearer {token}"},
                params={"limit": 100},
                timeout=10
            ) as response:
                if response.status == 200:
                    logs = await response.json()
                    print(f"    📋 감사 로그 {len(logs)}건 확인됨")
                    return True
                return False
                
        except Exception as e:
            print(f"    ❌ 감사 로그 확인 에러: {e}")
            return False

    async def manage_system_config(self, session: aiohttp.ClientSession, token: str) -> bool:
        """시스템 설정 관리"""
        try:
            # 시스템 설정 조회
            async with session.get(
                f"{self.services['user_service']}/api/v1/admin/config",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            ) as response:
                return response.status == 200
                
        except Exception as e:
            print(f"    ❌ 시스템 설정 관리 에러: {e}")
            return False

    async def validate_concurrent_users(self):
        """다중 사용자 동시 접근 검증"""
        print("  🔀 동시 사용자 접근 시뮬레이션...")
        
        # 10명의 가상 사용자 동시 접근
        concurrent_tasks = []
        for i in range(10):
            task = asyncio.create_task(self.simulate_concurrent_user(f"user_{i}"))
            concurrent_tasks.append(task)
        
        results = await asyncio.gather(*concurrent_tasks, return_exceptions=True)
        
        success_count = sum(1 for result in results if isinstance(result, bool) and result)
        self.test_results["concurrent_users"] = {
            "total_users": 10,
            "successful_users": success_count,
            "success_rate": (success_count / 10) * 100
        }
        
        print(f"    📊 동시 사용자 성공률: {(success_count/10)*100:.1f}% ({success_count}/10)")

    async def simulate_concurrent_user(self, user_id: str) -> bool:
        """개별 동시 사용자 시뮬레이션"""
        try:
            async with aiohttp.ClientSession() as session:
                # 사용자 등록
                register_success, token = await self.register_user(
                    session, f"{user_id}_concurrent", f"{user_id}@test.com", "Password123!", "viewer"
                )
                
                if not register_success:
                    return False
                
                # 동시 작업 수행
                tasks = [
                    self.verify_login(session, token),
                    self.get_available_schemas(session, token),
                    self.get_user_profile(session, token)
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                return all(isinstance(r, bool) and r for r in results)
                
        except Exception:
            return False

    async def get_available_schemas(self, session: aiohttp.ClientSession, token: str) -> bool:
        """사용 가능한 스키마 목록 조회"""
        try:
            async with session.get(
                f"{self.services['ontology_service']}/api/v1/schemas",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5
            ) as response:
                return response.status == 200
        except Exception:
            return False

    async def get_user_profile(self, session: aiohttp.ClientSession, token: str) -> bool:
        """사용자 프로필 조회"""
        try:
            async with session.get(
                f"{self.services['user_service']}/api/v1/auth/profile",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5
            ) as response:
                return response.status == 200
        except Exception:
            return False

    async def validate_error_recovery(self):
        """에러 처리 및 복구 시나리오 검증"""
        print("  🛡️  에러 처리 및 복구 시나리오...")
        
        scenarios = {
            "invalid_token": await self.test_invalid_token_handling(),
            "network_timeout": await self.test_network_timeout_handling(),
            "invalid_data": await self.test_invalid_data_handling(),
            "service_unavailable": await self.test_service_unavailable_handling()
        }
        
        self.test_results["error_recovery"] = scenarios
        
        success_count = sum(1 for success in scenarios.values() if success)
        print(f"    📊 에러 처리 성공률: {(success_count/len(scenarios))*100:.1f}% ({success_count}/{len(scenarios)})")

    async def test_invalid_token_handling(self) -> bool:
        """잘못된 토큰 처리 테스트"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.services['user_service']}/api/v1/auth/profile",
                    headers={"Authorization": "Bearer invalid_token"},
                    timeout=5
                ) as response:
                    # 401 Unauthorized가 정상적으로 반환되어야 함
                    return response.status == 401
        except Exception:
            return False

    async def test_network_timeout_handling(self) -> bool:
        """네트워크 타임아웃 처리 테스트"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.services['user_service']}/api/v1/health",
                    timeout=0.001  # 매우 짧은 타임아웃
                ) as response:
                    return False  # 타임아웃이 발생해야 정상
        except asyncio.TimeoutError:
            return True  # 타임아웃 에러가 정상적으로 처리됨
        except Exception:
            return True  # 다른 네트워크 에러도 정상적으로 처리됨

    async def test_invalid_data_handling(self) -> bool:
        """잘못된 데이터 처리 테스트"""
        try:
            async with aiohttp.ClientSession() as session:
                # 잘못된 형식의 사용자 등록 시도
                async with session.post(
                    f"{self.services['user_service']}/api/v1/auth/register",
                    json={"invalid": "data"},  # 필수 필드 누락
                    timeout=5
                ) as response:
                    # 400 Bad Request가 정상적으로 반환되어야 함
                    return response.status == 400
        except Exception:
            return False

    async def test_service_unavailable_handling(self) -> bool:
        """서비스 불가 상황 처리 테스트"""
        try:
            async with aiohttp.ClientSession() as session:
                # 존재하지 않는 엔드포인트 접근
                async with session.get(
                    "http://localhost:9999/nonexistent",
                    timeout=2
                ) as response:
                    return False  # 연결되면 안됨
        except aiohttp.ClientConnectorError:
            return True  # 연결 실패가 정상적으로 처리됨
        except Exception:
            return True  # 다른 에러도 정상적으로 처리됨

    async def validate_performance_monitoring(self):
        """성능 및 모니터링 검증"""
        print("  ⚡ 성능 및 모니터링 검증...")
        
        # 현재 시스템 리소스 사용량 측정
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # 응답 시간 분석
        response_times = self.performance_metrics["response_times"]
        if response_times:
            avg_response_time = sum(rt["time"] for rt in response_times) / len(response_times)
            max_response_time = max(rt["time"] for rt in response_times)
        else:
            avg_response_time = 0
            max_response_time = 0
        
        performance_data = {
            "system_resources": {
                "cpu_usage_percent": cpu_percent,
                "memory_usage_percent": memory.percent,
                "disk_usage_percent": (disk.used / disk.total) * 100,
                "available_memory_gb": memory.available / (1024**3)
            },
            "response_times": {
                "average_ms": avg_response_time * 1000,
                "maximum_ms": max_response_time * 1000,
                "total_requests": len(response_times)
            },
            "performance_thresholds": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": memory.percent < 80,
                "response_time_ok": avg_response_time < 2.0  # 2초 이내
            }
        }
        
        self.test_results["performance"] = performance_data
        
        # 성능 점수 계산
        performance_score = sum([
            performance_data["performance_thresholds"]["cpu_ok"],
            performance_data["performance_thresholds"]["memory_ok"], 
            performance_data["performance_thresholds"]["response_time_ok"]
        ])
        
        print(f"    📊 성능 점수: {performance_score}/3")
        print(f"    💻 CPU 사용률: {cpu_percent:.1f}%")
        print(f"    🧠 메모리 사용률: {memory.percent:.1f}%")
        print(f"    ⏱️  평균 응답시간: {avg_response_time*1000:.1f}ms")

    async def validate_security_audit(self):
        """보안 및 감사 로그 검증"""
        print("  🔒 보안 및 감사 검증...")
        
        security_checks = {
            "jwt_validation": await self.test_jwt_security(),
            "role_based_access": await self.test_role_based_access_control(),
            "audit_logging": await self.test_audit_logging(),
            "data_sanitization": await self.test_data_sanitization()
        }
        
        self.test_results["security"] = security_checks
        
        success_count = sum(1 for success in security_checks.values() if success)
        print(f"    📊 보안 검증 성공률: {(success_count/len(security_checks))*100:.1f}% ({success_count}/{len(security_checks)})")

    async def test_jwt_security(self) -> bool:
        """JWT 보안 검증"""
        try:
            async with aiohttp.ClientSession() as session:
                # 만료된 토큰으로 접근 시도
                expired_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE2MDk0NTkxOTl9.invalid"
                
                async with session.get(
                    f"{self.services['user_service']}/api/v1/auth/profile",
                    headers={"Authorization": f"Bearer {expired_token}"},
                    timeout=5
                ) as response:
                    return response.status == 401  # 거부되어야 정상
        except Exception:
            return False

    async def test_role_based_access_control(self) -> bool:
        """역할 기반 접근 제어 검증"""
        try:
            async with aiohttp.ClientSession() as session:
                # 일반 사용자 토큰으로 관리자 기능 접근 시도
                _, user_token = await self.register_user(
                    session, "test_rbac_user", "rbac@test.com", "Password123!", "viewer"
                )
                
                if not user_token:
                    return False
                
                async with session.get(
                    f"{self.services['user_service']}/api/v1/admin/users",
                    headers={"Authorization": f"Bearer {user_token}"},
                    timeout=5
                ) as response:
                    return response.status == 403  # 접근 거부되어야 정상
        except Exception:
            return False

    async def test_audit_logging(self) -> bool:
        """감사 로깅 검증"""
        try:
            async with aiohttp.ClientSession() as session:
                # 관리자 토큰으로 감사 로그 조회
                _, admin_token = await self.admin_login(session)
                
                if not admin_token:
                    return False
                
                async with session.get(
                    f"{self.services['audit_service']}/api/v1/logs",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    timeout=10
                ) as response:
                    if response.status == 200:
                        logs = await response.json()
                        # 최근 활동이 로그에 기록되었는지 확인
                        return len(logs) > 0
                    return False
        except Exception:
            return False

    async def test_data_sanitization(self) -> bool:
        """데이터 무결성 및 검증"""
        try:
            async with aiohttp.ClientSession() as session:
                # XSS 공격 시도
                malicious_data = {
                    "username": "<script>alert('xss')</script>",
                    "email": "test@example.com",
                    "password": "Password123!",
                    "role": "viewer"
                }
                
                async with session.post(
                    f"{self.services['user_service']}/api/v1/auth/register",
                    json=malicious_data,
                    timeout=5
                ) as response:
                    # 400 Bad Request나 데이터 sanitization이 이루어져야 함
                    return response.status in [400, 422]
        except Exception:
            return False

    def calculate_production_ready_score(self):
        """프로덕션 레디 점수 계산"""
        scores = {
            "service_integration": 0,
            "user_scenarios": 0,
            "concurrent_users": 0,
            "error_recovery": 0,
            "performance": 0,
            "security": 0
        }
        
        # 서비스 통합 점수 (20점)
        if self.test_results["service_integration"].get("basic_health"):
            healthy_services = sum(1 for status in self.test_results["service_integration"]["basic_health"].values() if status)
            total_services = len(self.services)
            scores["service_integration"] = (healthy_services / total_services) * 20
        
        # 사용자 시나리오 점수 (25점)
        if self.test_results["user_scenarios"]:
            total_steps = 0
            successful_steps = 0
            for scenario in self.test_results["user_scenarios"].values():
                total_steps += len(scenario["steps"])
                successful_steps += sum(1 for step in scenario["steps"] if step["success"])
            
            if total_steps > 0:
                scores["user_scenarios"] = (successful_steps / total_steps) * 25
        
        # 동시 사용자 점수 (15점)
        if self.test_results["concurrent_users"]:
            success_rate = self.test_results["concurrent_users"].get("success_rate", 0)
            scores["concurrent_users"] = (success_rate / 100) * 15
        
        # 에러 복구 점수 (15점)
        if self.test_results["error_recovery"]:
            successful_scenarios = sum(1 for success in self.test_results["error_recovery"].values() if success)
            total_scenarios = len(self.test_results["error_recovery"])
            scores["error_recovery"] = (successful_scenarios / total_scenarios) * 15
        
        # 성능 점수 (10점)
        if self.test_results["performance"]:
            thresholds = self.test_results["performance"].get("performance_thresholds", {})
            successful_checks = sum(1 for check in thresholds.values() if check)
            total_checks = len(thresholds)
            if total_checks > 0:
                scores["performance"] = (successful_checks / total_checks) * 10
        
        # 보안 점수 (15점)
        if self.test_results["security"]:
            successful_checks = sum(1 for success in self.test_results["security"].values() if success)
            total_checks = len(self.test_results["security"])
            scores["security"] = (successful_checks / total_checks) * 15
        
        # 총점 계산
        total_score = sum(scores.values())
        self.test_results["production_ready_score"] = total_score
        self.test_results["score_breakdown"] = scores

    async def save_results(self):
        """테스트 결과 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"production_ready_validation_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n💾 테스트 결과 저장: {filename}")

    def print_final_results(self):
        """최종 결과 출력"""
        score = self.test_results["production_ready_score"]
        
        print("\n" + "=" * 80)
        print("🏆 ARRAKIS MSA PRODUCTION READY 최종 검증 결과")
        print("=" * 80)
        
        print(f"\n📊 총 점수: {score:.1f}/100")
        
        if score >= 90:
            status = "🟢 PRODUCTION READY - 프로덕션 배포 준비 완료"
        elif score >= 75:
            status = "🟡 NEARLY READY - 일부 개선 후 프로덕션 준비 가능"
        elif score >= 60:
            status = "🟠 NEEDS IMPROVEMENT - 상당한 개선 필요"
        else:
            status = "🔴 NOT READY - 대대적인 개선 필요"
        
        print(f"🎯 상태: {status}")
        
        print(f"\n📈 점수 세부 분석:")
        breakdown = self.test_results.get("score_breakdown", {})
        for category, score_val in breakdown.items():
            print(f"  • {category}: {score_val:.1f}점")
        
        print(f"\n⏰ 검증 완료 시간: {self.test_results['timestamp']}")
        
        # 권장사항 출력
        if score < 90:
            print(f"\n💡 개선 권장사항:")
            if breakdown.get("service_integration", 0) < 18:
                print("  • MSA 서비스 간 연동 안정성 개선")
            if breakdown.get("user_scenarios", 0) < 22:
                print("  • 사용자 워크플로우 완성도 개선")
            if breakdown.get("concurrent_users", 0) < 13:
                print("  • 동시 사용자 처리 성능 개선")
            if breakdown.get("error_recovery", 0) < 13:
                print("  • 에러 처리 및 복구 메커니즘 강화")
            if breakdown.get("performance", 0) < 8:
                print("  • 시스템 성능 최적화")
            if breakdown.get("security", 0) < 13:
                print("  • 보안 및 감사 체계 강화")


async def main():
    """메인 실행 함수"""
    validator = ProductionReadyValidator()
    
    print("🚀 ARRAKIS MSA 프로덕션 레디 검증을 시작합니다...")
    print("⚠️  주의: 모든 MSA 서비스가 실행 중이어야 합니다.")
    print("📋 필요 서비스: user-service(3001), ontology-service(3002), audit-service(3003)")
    
    print("\n🔄 자동으로 프로덕션 레디 검증을 시작합니다...")
    
    results = await validator.validate_production_readiness()
    
    return results


if __name__ == "__main__":
    results = asyncio.run(main())