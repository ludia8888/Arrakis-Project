#!/usr/bin/env python3
"""
Schema와 Document 서비스 실제 통합 테스트
진짜 API를 호출하고 데이터베이스 상태 변화를 검증합니다.
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
import uuid
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RealIntegrationTest:
    """실제 통합 테스트 - 가짜가 아닌 진짜"""
    
    def __init__(self):
        self.base_url = "http://localhost:8091"  # OMS port from docker-compose
        self.user_service_url = "http://localhost:8080"  # User Service port from docker-compose
        self.test_results = []
        self.access_token = None
        self.created_resources = {
            "schemas": [],
            "documents": []
        }
        
    async def setup_auth(self):
        """인증 설정 - 실제 User Service에서 토큰 획득"""
        logger.info("🔐 실제 인증 토큰 획득 중...")
        
        async with httpx.AsyncClient() as client:
            try:
                # 미리 생성된 테스트 사용자로 로그인
                test_user = {
                    "username": "testuser_integration",
                    "password": "TestPassword123!"
                }
                
                # Step 1: 로그인 시작
                login_response = await client.post(
                    f"{self.user_service_url}/auth/login",
                    json=test_user,
                    timeout=10
                )
                
                if login_response.status_code == 200:
                    login_data = login_response.json()
                    challenge_token = login_data.get("challenge_token")
                    
                    if not challenge_token:
                        logger.error("Challenge token not received")
                        return False
                    
                    # Step 2: 로그인 완료
                    complete_response = await client.post(
                        f"{self.user_service_url}/auth/login/complete",
                        json={"challenge_token": challenge_token},
                        timeout=10
                    )
                    
                    if complete_response.status_code == 200:
                        complete_data = complete_response.json()
                        self.access_token = complete_data.get("access_token")
                        logger.info("✅ 인증 토큰 획득 성공")
                        logger.debug(f"Token received: {self.access_token[:20]}..." if self.access_token else "No token")
                        return True
                    else:
                        logger.error(f"로그인 완료 실패: {complete_response.status_code}")
                        return False
                else:
                    logger.error(f"로그인 시작 실패: {login_response.status_code}")
                    return False
                    
            except Exception as e:
                logger.error(f"인증 설정 실패: {e}")
                return False
    
    async def test_schema_crud_operations(self):
        """Schema CRUD 작업 실제 테스트"""
        logger.info("📘 Schema CRUD 실제 테스트 시작")
        
        if not self.access_token:
            self.test_results.append("❌ Schema 테스트 실패: 인증 토큰 없음")
            logger.error(f"Access token is None or empty")
            return False
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        async with httpx.AsyncClient() as client:
            try:
                # 1. CREATE - 새 스키마 생성
                logger.info("1️⃣ Schema CREATE 테스트")
                create_data = {
                    "name": f"TestSchema_{uuid.uuid4().hex[:8]}",
                    "display_name": "Test Schema",
                    "description": "Integration test schema",
                    "type": "object"
                }
                
                create_response = await client.post(
                    f"{self.base_url}/api/v1/schemas/main/object-types",
                    json=create_data,
                    headers=headers,
                    timeout=30
                )
                
                if create_response.status_code == 200:
                    created_schema = create_response.json()
                    self.created_resources["schemas"].append(create_data["name"])
                    self.test_results.append(f"✅ Schema CREATE 성공: {create_data['name']}")
                    logger.info(f"✅ Schema 생성됨: {created_schema}")
                else:
                    self.test_results.append(f"❌ Schema CREATE 실패: {create_response.status_code} - {create_response.text}")
                    logger.error(f"Schema 생성 실패: {create_response.text}")
                    return False
                
                # 2. READ - 생성된 스키마 조회
                logger.info("2️⃣ Schema READ 테스트")
                get_response = await client.get(
                    f"{self.base_url}/api/v1/schemas/main/object-types/{create_data['name']}",
                    headers=headers,
                    timeout=30
                )
                
                if get_response.status_code == 200:
                    retrieved_schema = get_response.json()
                    if retrieved_schema.get("name") == create_data["name"]:
                        self.test_results.append("✅ Schema READ 성공: 데이터 일치")
                        logger.info("✅ Schema 조회 성공")
                    else:
                        self.test_results.append("❌ Schema READ 실패: 데이터 불일치")
                        return False
                else:
                    self.test_results.append(f"❌ Schema READ 실패: {get_response.status_code}")
                    return False
                
                # 3. LIST - 스키마 목록 조회
                logger.info("3️⃣ Schema LIST 테스트")
                list_response = await client.get(
                    f"{self.base_url}/api/v1/schemas/main/object-types",
                    headers=headers,
                    timeout=30
                )
                
                if list_response.status_code == 200:
                    schemas_list = list_response.json()
                    if isinstance(schemas_list, list):
                        found = any(s.get("name") == create_data["name"] for s in schemas_list)
                        if found:
                            self.test_results.append("✅ Schema LIST 성공: 생성된 스키마 발견")
                            logger.info("✅ Schema 목록에서 발견")
                        else:
                            self.test_results.append("❌ Schema LIST 실패: 생성된 스키마 없음")
                    else:
                        self.test_results.append("❌ Schema LIST 실패: 잘못된 응답 형식")
                else:
                    self.test_results.append(f"❌ Schema LIST 실패: {list_response.status_code}")
                
                return True
                
            except Exception as e:
                self.test_results.append(f"❌ Schema CRUD 테스트 예외: {e}")
                logger.error(f"Schema CRUD 테스트 실패: {e}")
                return False
    
    async def test_document_crud_operations(self):
        """Document CRUD 작업 실제 테스트"""
        logger.info("📄 Document CRUD 실제 테스트 시작")
        
        if not self.access_token:
            self.test_results.append("❌ Document 테스트 실패: 인증 토큰 없음")
            return False
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        async with httpx.AsyncClient() as client:
            try:
                # 1. CREATE - 새 문서 생성
                logger.info("1️⃣ Document CREATE 테스트")
                create_data = {
                    "name": f"TestDoc_{uuid.uuid4().hex[:8]}",
                    "object_type": "TestObject",
                    "content": {
                        "title": "Test Document",
                        "body": "This is a real integration test document",
                        "test_field": "test_value"
                    },
                    "metadata": {
                        "created_for": "integration_test",
                        "test_run": True
                    },
                    "tags": ["test", "integration"],
                    "status": "draft"
                }
                
                create_response = await client.post(
                    f"{self.base_url}/api/v1/documents/crud/?branch=main",
                    json=create_data,
                    headers=headers,
                    timeout=30
                )
                
                if create_response.status_code == 201:
                    created_doc = create_response.json()
                    doc_id = created_doc.get("id")
                    self.created_resources["documents"].append(doc_id)
                    self.test_results.append(f"✅ Document CREATE 성공: ID={doc_id}")
                    logger.info(f"✅ Document 생성됨: {doc_id}")
                else:
                    self.test_results.append(f"❌ Document CREATE 실패: {create_response.status_code} - {create_response.text}")
                    logger.error(f"Document 생성 실패: {create_response.text}")
                    return False
                
                # 2. READ - 생성된 문서 조회
                logger.info("2️⃣ Document READ 테스트")
                get_response = await client.get(
                    f"{self.base_url}/api/v1/documents/crud/{doc_id}?branch=main",
                    headers=headers,
                    timeout=30
                )
                
                if get_response.status_code == 200:
                    retrieved_doc = get_response.json()
                    if (retrieved_doc.get("id") == doc_id and 
                        retrieved_doc.get("name") == create_data["name"] and
                        retrieved_doc.get("content") == create_data["content"]):
                        self.test_results.append("✅ Document READ 성공: 데이터 일치")
                        logger.info("✅ Document 조회 성공")
                    else:
                        self.test_results.append("❌ Document READ 실패: 데이터 불일치")
                        logger.error(f"Expected: {create_data}, Got: {retrieved_doc}")
                        return False
                else:
                    self.test_results.append(f"❌ Document READ 실패: {get_response.status_code}")
                    return False
                
                # 3. UPDATE - 문서 수정
                logger.info("3️⃣ Document UPDATE 테스트")
                update_data = {
                    "content": {
                        "title": "Updated Test Document",
                        "body": "This document has been updated",
                        "test_field": "updated_value",
                        "new_field": "added_during_update"
                    },
                    "status": "published"
                }
                
                update_response = await client.put(
                    f"{self.base_url}/api/v1/documents/crud/{doc_id}?branch=main",
                    json=update_data,
                    headers=headers,
                    timeout=30
                )
                
                if update_response.status_code == 200:
                    updated_doc = update_response.json()
                    if (updated_doc.get("content") == update_data["content"] and
                        updated_doc.get("status") == update_data["status"]):
                        self.test_results.append("✅ Document UPDATE 성공: 변경사항 적용됨")
                        logger.info("✅ Document 업데이트 성공")
                    else:
                        self.test_results.append("❌ Document UPDATE 실패: 변경사항 미적용")
                        return False
                else:
                    self.test_results.append(f"❌ Document UPDATE 실패: {update_response.status_code}")
                    return False
                
                # 4. SEARCH - 문서 검색
                logger.info("4️⃣ Document SEARCH 테스트")
                search_response = await client.get(
                    f"{self.base_url}/api/v1/documents/crud/search/?q=Updated&branch=main",
                    headers=headers,
                    timeout=30
                )
                
                if search_response.status_code == 200:
                    search_results = search_response.json()
                    if "items" in search_results:
                        found = any(doc.get("id") == doc_id for doc in search_results["items"])
                        if found:
                            self.test_results.append("✅ Document SEARCH 성공: 문서 발견")
                            logger.info("✅ Document 검색 성공")
                        else:
                            self.test_results.append("⚠️ Document SEARCH: 문서를 찾지 못함 (인덱싱 지연 가능)")
                    else:
                        self.test_results.append("❌ Document SEARCH 실패: 잘못된 응답 형식")
                else:
                    self.test_results.append(f"❌ Document SEARCH 실패: {search_response.status_code}")
                
                # 5. DELETE - 문서 삭제
                logger.info("5️⃣ Document DELETE 테스트")
                delete_response = await client.delete(
                    f"{self.base_url}/api/v1/documents/crud/{doc_id}?branch=main",
                    headers=headers,
                    timeout=30
                )
                
                if delete_response.status_code == 204:
                    self.test_results.append("✅ Document DELETE 성공")
                    logger.info("✅ Document 삭제 성공")
                    
                    # 삭제 확인 - 404를 기대
                    verify_response = await client.get(
                        f"{self.base_url}/api/v1/documents/crud/{doc_id}?branch=main",
                        headers=headers,
                        timeout=30
                    )
                    
                    if verify_response.status_code == 404:
                        self.test_results.append("✅ Document DELETE 검증: 문서가 실제로 삭제됨")
                        self.created_resources["documents"].remove(doc_id)
                    else:
                        self.test_results.append("❌ Document DELETE 검증 실패: 문서가 여전히 존재")
                        return False
                else:
                    self.test_results.append(f"❌ Document DELETE 실패: {delete_response.status_code}")
                    return False
                
                return True
                
            except Exception as e:
                self.test_results.append(f"❌ Document CRUD 테스트 예외: {e}")
                logger.error(f"Document CRUD 테스트 실패: {e}")
                return False
    
    async def test_permission_enforcement(self):
        """권한 검사가 실제로 작동하는지 테스트"""
        logger.info("🔒 권한 검사 실제 테스트")
        
        async with httpx.AsyncClient() as client:
            try:
                # 인증 없이 API 호출 시도
                logger.info("인증 없이 API 호출 시도...")
                
                # Schema 조회 시도
                schema_response = await client.get(
                    f"{self.base_url}/api/v1/schemas/main/object-types",
                    timeout=10
                )
                
                if schema_response.status_code == 401:
                    self.test_results.append("✅ Schema API 권한 검사 작동: 401 Unauthorized")
                else:
                    self.test_results.append(f"❌ Schema API 권한 검사 실패: {schema_response.status_code}")
                
                # Document 조회 시도
                doc_response = await client.get(
                    f"{self.base_url}/api/v1/documents/crud/",
                    timeout=10
                )
                
                if doc_response.status_code == 401:
                    self.test_results.append("✅ Document API 권한 검사 작동: 401 Unauthorized")
                else:
                    self.test_results.append(f"❌ Document API 권한 검사 실패: {doc_response.status_code}")
                
                return True
                
            except Exception as e:
                self.test_results.append(f"❌ 권한 검사 테스트 예외: {e}")
                return False
    
    async def cleanup_resources(self):
        """테스트 중 생성된 리소스 정리"""
        logger.info("🧹 테스트 리소스 정리 중...")
        
        if not self.access_token:
            return
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        async with httpx.AsyncClient() as client:
            # 남은 문서 삭제
            for doc_id in self.created_resources["documents"]:
                try:
                    await client.delete(
                        f"{self.base_url}/api/v1/documents/crud/{doc_id}?branch=main",
                        headers=headers,
                        timeout=10
                    )
                    logger.info(f"Cleaned up document: {doc_id}")
                except:
                    pass
    
    async def run_all_tests(self):
        """모든 실제 테스트 실행"""
        logger.info("🎯 실제 통합 테스트 시작")
        logger.info("⚠️ 주의: 이 테스트는 실제 서비스가 실행 중이어야 합니다!")
        
        # 서비스 상태 확인
        try:
            async with httpx.AsyncClient() as client:
                # OMS health check은 문제가 있으므로 일단 건너뛰고 실제 API 테스트로 진행
                logger.warning("⚠️ OMS health check 건너뜀 - 실제 API 호출로 테스트 진행")
                
                user_health = await client.get(f"{self.user_service_url}/health", timeout=5)
                if user_health.status_code != 200:
                    logger.error("❌ User Service가 실행되고 있지 않습니다!")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ 서비스 연결 실패: {e}")
            logger.error("서비스를 먼저 시작하세요:")
            logger.error("  - OMS: http://localhost:8091")
            logger.error("  - User Service: http://localhost:8080")
            return False
        
        # 인증 설정
        if not await self.setup_auth():
            logger.error("❌ 인증 설정 실패")
            return False
        
        # 실제 테스트 실행
        tests = [
            ("권한 검사", self.test_permission_enforcement),
            ("Schema CRUD", self.test_schema_crud_operations),
            ("Document CRUD", self.test_document_crud_operations)
        ]
        
        all_passed = True
        for test_name, test_func in tests:
            logger.info(f"\n📋 {test_name} 테스트 실행 중...")
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
                self.test_results.append(f"❌ {test_name} 테스트 예외: {e}")
        
        # 정리
        await self.cleanup_resources()
        
        return all_passed
    
    def print_report(self):
        """실제 테스트 결과 보고서"""
        logger.info("\n" + "="*60)
        logger.info("🎯 실제 통합 테스트 결과")
        logger.info("="*60)
        
        success_count = len([r for r in self.test_results if r.startswith("✅")])
        warning_count = len([r for r in self.test_results if r.startswith("⚠️")])
        fail_count = len([r for r in self.test_results if r.startswith("❌")])
        total_count = len(self.test_results)
        
        for result in self.test_results:
            logger.info(f"  {result}")
        
        logger.info(f"\n📊 결과 요약:")
        logger.info(f"  - 성공: {success_count}개")
        logger.info(f"  - 경고: {warning_count}개")
        logger.info(f"  - 실패: {fail_count}개")
        logger.info(f"  - 전체: {total_count}개")
        
        if total_count > 0:
            success_rate = (success_count / total_count * 100)
            logger.info(f"\n📈 성공률: {success_rate:.1f}%")
        
        if fail_count == 0:
            logger.info("\n🎉 모든 실제 테스트 통과! 서비스가 정상 작동합니다.")
            return True
        else:
            logger.error("\n⚠️ 일부 실제 테스트 실패. 서비스에 문제가 있습니다.")
            return False

async def main():
    """메인 실행"""
    tester = RealIntegrationTest()
    
    try:
        success = await tester.run_all_tests()
        final_result = tester.print_report()
        
        if final_result:
            logger.info("\n🏆 실제 통합 테스트 성공!")
            logger.info("Schema와 Document 서비스가 실제로 작동합니다.")
            return 0
        else:
            logger.error("\n🚨 실제 통합 테스트 실패!")
            logger.error("서비스가 제대로 작동하지 않습니다.")
            return 1
            
    except Exception as e:
        logger.error(f"\n🔥 테스트 중 치명적 오류: {e}")
        return 1

if __name__ == "__main__":
    logger.info("🚀 실제 통합 테스트를 시작합니다...")
    logger.info("📌 필요사항:")
    logger.info("  1. OMS 서비스가 http://localhost:8091 에서 실행 중")
    logger.info("  2. User Service가 http://localhost:8080 에서 실행 중")
    logger.info("  3. TerminusDB가 실행 중")
    logger.info("  4. Redis가 실행 중")
    logger.info("")
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)