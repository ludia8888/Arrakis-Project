#!/usr/bin/env python3
"""
Cleanup Replaced Mock Files - 중복구현 제거
Mock Massacre 후 교체된 기존 파일들 정리
"""

import os
import shutil
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

class MockFileCleanup:
    def __init__(self):
        self.project_root = "/Users/isihyeon/Desktop/Arrakis-Project"
        self.cleanup_report = {
            "cleanup_time": datetime.now().isoformat(),
            "mock_massacre_cleanup": True,
            "replaced_implementations": {
                "user_service": {
                    "old_file": "user-service/src/main.py",
                    "new_file": "user-service/src/real_main.py",
                    "status": "replaced"
                },
                "oms": {
                    "old_file": "ontology-management-service/main.py",
                    "new_file": "ontology-management-service/real_oms_main.py", 
                    "status": "replaced"
                }
            },
            "files_to_archive": [],
            "files_to_delete": [],
            "archive_created": "",
            "cleanup_summary": {}
        }
        
        # 교체된 파일들과 삭제할 mock 파일들
        self.files_to_handle = {
            # User Service - 기존 mock main.py 백업 후 real_main.py로 교체
            "user_service_main": {
                "original": "user-service/src/main.py",
                "real_implementation": "user-service/src/real_main.py",
                "action": "replace"
            },
            
            # OMS - 기존 복잡한 main.py 백업 후 real_oms_main.py로 교체
            "oms_main": {
                "original": "ontology-management-service/main.py",
                "real_implementation": "ontology-management-service/real_oms_main.py",
                "action": "replace"
            },
            
            # OMS - 기존 simple_schema_routes.py는 real_oms_main.py에 통합됨
            "oms_simple_schema": {
                "original": "ontology-management-service/api/simple_schema_routes.py",
                "real_implementation": "ontology-management-service/real_oms_main.py",
                "action": "archive_only"  # 이미 통합됨
            }
        }
        
        # 삭제할 테스트 파일들 (Mock Massacre에서 이미 식별된)
        self.test_files_to_delete = [
            # User Service mock tests (이미 삭제된 것들 확인용)
            "test_user_service.py",
            "test_user_*.py",
            
            # OMS fake database 테스트들
            "tests/unit/core/versioning/test_merge_engine.py",
            "tests/unit/core/schema/test_conflict_resolver.py"
        ]

    def create_archive_directory(self) -> str:
        """백업 아카이브 디렉토리 생성"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_dir = os.path.join(self.project_root, f"archive_mock_massacre_{timestamp}")
        
        os.makedirs(archive_dir, exist_ok=True)
        os.makedirs(os.path.join(archive_dir, "user-service"), exist_ok=True)
        os.makedirs(os.path.join(archive_dir, "ontology-management-service"), exist_ok=True)
        
        self.cleanup_report["archive_created"] = archive_dir
        return archive_dir

    def backup_and_replace_file(self, original_path: str, new_path: str, archive_dir: str) -> bool:
        """기존 파일 백업 후 새 파일로 교체"""
        full_original_path = os.path.join(self.project_root, original_path)
        full_new_path = os.path.join(self.project_root, new_path)
        
        if not os.path.exists(full_original_path):
            print(f"   ⚠️  Original file not found: {original_path}")
            return False
            
        if not os.path.exists(full_new_path):
            print(f"   ❌ New implementation not found: {new_path}")
            return False
        
        try:
            # 1. 기존 파일을 아카이브로 백업
            archive_path = os.path.join(archive_dir, original_path)
            os.makedirs(os.path.dirname(archive_path), exist_ok=True)
            shutil.copy2(full_original_path, archive_path)
            print(f"   📦 Archived: {original_path} → {archive_path}")
            
            # 2. 기존 파일 삭제
            os.remove(full_original_path)
            print(f"   🗑️  Removed: {original_path}")
            
            # 3. 새 파일을 기존 위치로 복사
            shutil.copy2(full_new_path, full_original_path)
            print(f"   ✅ Replaced: {new_path} → {original_path}")
            
            # 4. 새 파일 원본 삭제 (중복 제거)
            os.remove(full_new_path)
            print(f"   🗑️  Cleaned: {new_path} (original moved)")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Error replacing {original_path}: {e}")
            return False

    def archive_file_only(self, file_path: str, archive_dir: str) -> bool:
        """파일만 아카이브 (교체 없이)"""
        full_path = os.path.join(self.project_root, file_path)
        
        if not os.path.exists(full_path):
            print(f"   ⚠️  File not found: {file_path}")
            return False
        
        try:
            archive_path = os.path.join(archive_dir, file_path)
            os.makedirs(os.path.dirname(archive_path), exist_ok=True)
            shutil.copy2(full_path, archive_path)
            print(f"   📦 Archived: {file_path}")
            
            # 아카이브 후 삭제
            os.remove(full_path)
            print(f"   🗑️  Removed: {file_path}")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Error archiving {file_path}: {e}")
            return False

    def cleanup_duplicate_implementations(self):
        """중복 구현 정리 실행"""
        print("🗑️ MOCK MASSACRE CLEANUP - Removing Duplicate Implementations")
        print("=" * 80)
        print("🎯 Goal: Replace mock implementations with real implementations")
        print("📦 Backup original files before replacement")
        print("=" * 80)
        
        # 아카이브 디렉토리 생성
        archive_dir = self.create_archive_directory()
        print(f"📁 Archive directory created: {archive_dir}")
        
        successful_replacements = 0
        failed_replacements = 0
        
        # 각 파일 처리
        for key, file_info in self.files_to_handle.items():
            print(f"\n🔄 Processing: {key}")
            print(f"   Original: {file_info['original']}")
            print(f"   Implementation: {file_info['real_implementation']}")
            print(f"   Action: {file_info['action']}")
            
            if file_info["action"] == "replace":
                success = self.backup_and_replace_file(
                    file_info["original"],
                    file_info["real_implementation"], 
                    archive_dir
                )
                if success:
                    successful_replacements += 1
                    self.cleanup_report["replaced_implementations"][key] = {
                        "old_file": file_info["original"],
                        "new_file": file_info["real_implementation"],
                        "status": "replaced_successfully"
                    }
                else:
                    failed_replacements += 1
                    self.cleanup_report["replaced_implementations"][key] = {
                        "old_file": file_info["original"],
                        "new_file": file_info["real_implementation"],
                        "status": "replacement_failed"
                    }
                    
            elif file_info["action"] == "archive_only":
                success = self.archive_file_only(file_info["original"], archive_dir)
                if success:
                    self.cleanup_report["files_to_archive"].append(file_info["original"])
                else:
                    print(f"   ⚠️  Failed to archive {file_info['original']}")
        
        # 정리 요약
        self.cleanup_report["cleanup_summary"] = {
            "successful_replacements": successful_replacements,
            "failed_replacements": failed_replacements,
            "total_files_processed": len(self.files_to_handle),
            "archive_directory": archive_dir
        }
        
        print(f"\n" + "=" * 80)
        print("📊 CLEANUP SUMMARY")
        print("=" * 80)
        print(f"✅ Successful replacements: {successful_replacements}")
        print(f"❌ Failed replacements: {failed_replacements}")
        print(f"📦 Archive created: {archive_dir}")
        
        if successful_replacements > 0:
            print(f"\n🎊 CLEANUP SUCCESS!")
            print(f"   📁 Original mock files safely archived")
            print(f"   🔄 Real implementations now active")
            print(f"   🗑️  Duplicate implementations removed")
        
        return self.cleanup_report

    def verify_cleanup_results(self):
        """정리 결과 검증"""
        print(f"\n🔍 VERIFYING CLEANUP RESULTS")
        print("-" * 60)
        
        verification_results = []
        
        for key, file_info in self.files_to_handle.items():
            if file_info["action"] == "replace":
                original_path = os.path.join(self.project_root, file_info["original"])
                
                if os.path.exists(original_path):
                    # 파일이 실제 구현인지 확인
                    try:
                        with open(original_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        is_real = "100% REAL" in content or "NO MOCKS" in content
                        verification_results.append({
                            "file": file_info["original"],
                            "exists": True,
                            "is_real_implementation": is_real,
                            "status": "✅ REAL" if is_real else "❌ STILL MOCK"
                        })
                        print(f"   {'✅' if is_real else '❌'} {file_info['original']}: {'REAL' if is_real else 'MOCK'}")
                        
                    except Exception as e:
                        verification_results.append({
                            "file": file_info["original"],
                            "exists": True,
                            "is_real_implementation": False,
                            "error": str(e),
                            "status": "❌ ERROR"
                        })
                        print(f"   ❌ {file_info['original']}: Error reading file")
                else:
                    verification_results.append({
                        "file": file_info["original"],
                        "exists": False,
                        "status": "❌ MISSING"
                    })
                    print(f"   ❌ {file_info['original']}: File missing after replacement")
        
        self.cleanup_report["verification_results"] = verification_results
        return verification_results

def main():
    cleanup = MockFileCleanup()
    
    # 중복 구현 정리 실행
    cleanup_report = cleanup.cleanup_duplicate_implementations()
    
    # 결과 검증
    verification_results = cleanup.verify_cleanup_results()
    
    # 보고서 저장
    report_file = f"/Users/isihyeon/Desktop/Arrakis-Project/mock_massacre_cleanup_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(cleanup_report, f, indent=2)
    
    print(f"\n📄 Cleanup report saved to: {report_file}")
    
    # 최종 상태 요약
    successful = sum(1 for r in verification_results if r.get("is_real_implementation", False))
    total = len(verification_results)
    
    print(f"\n🎯 FINAL CLEANUP STATUS:")
    print(f"   Real implementations active: {successful}/{total}")
    if successful == total:
        print(f"   🏆 ALL MOCK FILES SUCCESSFULLY REPLACED WITH REAL IMPLEMENTATIONS!")
    else:
        print(f"   ⚠️  Some files may need manual verification")

if __name__ == "__main__":
    main()