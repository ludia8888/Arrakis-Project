#!/usr/bin/env python3
"""
Cleanup Duplicate Validation Code
P1/P2 구현과 중복되는 validation 코드 정리 스크립트

이 스크립트는 중복된 검증 로직을 찾아서 리포트를 생성합니다.
실제 파일 수정은 수동으로 진행해야 합니다.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


class DuplicateValidationFinder:
    """중복 검증 코드 찾기"""
    
    def __init__(self):
        self.duplicates = {
            "remove_completely": [],
            "refactor_needed": [],
            "validation_patterns": {}
        }
        
        # 검증 패턴들
        self.validation_patterns = {
            "enum_validation": [
                r"@field_validator.*enum",
                r"validate.*enum",
                r"check.*allowed.*values",
                r"if.*not in.*allowed"
            ],
            "array_validation": [
                r"validate.*array",
                r"check.*list.*elements",
                r"unique.*elements",
                r"array.*constraint"
            ],
            "required_field": [
                r"required.*field",
                r"missing.*required",
                r"field.*is.*required",
                r"must.*provide"
            ],
            "foreign_key": [
                r"foreign.*key",
                r"reference.*integrity",
                r"referential.*constraint",
                r"validate.*reference"
            ],
            "data_type": [
                r"validate.*type",
                r"check.*type",
                r"isinstance.*check",
                r"type.*validation"
            ]
        }
    
    def find_duplicates(self):
        """중복 검증 코드 찾기"""
        
        # 1. middleware 폴더 검사
        print("🔍 Checking middleware folder...")
        self._check_middleware()
        
        # 2. models 폴더 검사
        print("🔍 Checking models folder...")
        self._check_models()
        
        # 3. 결과 리포트 생성
        self._generate_report()
    
    def _check_middleware(self):
        """middleware 폴더의 중복 검증 찾기"""
        middleware_path = PROJECT_ROOT / "middleware"
        
        # request_validation.py - 완전 제거 대상
        request_validation = middleware_path / "request_validation.py"
        if request_validation.exists():
            self.duplicates["remove_completely"].append({
                "file": str(request_validation),
                "reason": "Completely redundant with enterprise_validation.py",
                "duplicate_of": "core/validation/* and middleware/enterprise_validation.py"
            })
        
        # enterprise_validation.py - 리팩토링 필요
        enterprise_validation = middleware_path / "enterprise_validation.py"
        if enterprise_validation.exists():
            duplicates_found = self._find_patterns_in_file(enterprise_validation)
            if duplicates_found:
                self.duplicates["refactor_needed"].append({
                    "file": str(enterprise_validation),
                    "patterns_found": duplicates_found,
                    "recommendation": "Keep as integration layer but remove duplicate validation logic"
                })
    
    def _check_models(self):
        """models 폴더의 중복 검증 찾기"""
        models_path = PROJECT_ROOT / "models"
        
        # 검사할 파일들
        model_files = [
            "domain.py",
            "semantic_types.py", 
            "struct_types.py"
        ]
        
        for model_file in model_files:
            file_path = models_path / model_file
            if file_path.exists():
                duplicates_found = self._find_patterns_in_file(file_path)
                if duplicates_found:
                    self.duplicates["refactor_needed"].append({
                        "file": str(file_path),
                        "patterns_found": duplicates_found,
                        "recommendation": self._get_model_recommendation(model_file)
                    })
    
    def _find_patterns_in_file(self, file_path: Path) -> Dict[str, List[Tuple[int, str]]]:
        """파일에서 검증 패턴 찾기"""
        found_patterns = {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for pattern_name, patterns in self.validation_patterns.items():
                matches = []
                for i, line in enumerate(lines, 1):
                    for pattern in patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            matches.append((i, line.strip()))
                            break
                
                if matches:
                    found_patterns[pattern_name] = matches
        
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
        
        return found_patterns
    
    def _get_model_recommendation(self, model_file: str) -> str:
        """모델 파일별 권장사항"""
        recommendations = {
            "domain.py": "Remove custom validators, keep only Pydantic type definitions",
            "semantic_types.py": "Convert validation methods to use core validation rules", 
            "struct_types.py": "Remove validation logic, keep only structure definitions"
        }
        return recommendations.get(model_file, "Refactor to use core validation")
    
    def _generate_report(self):
        """중복 검증 리포트 생성"""
        print("\n" + "=" * 70)
        print("📊 Duplicate Validation Code Report")
        print("=" * 70)
        
        # 완전 제거 대상
        if self.duplicates["remove_completely"]:
            print("\n🗑️  Files to Remove Completely:")
            print("-" * 50)
            for item in self.duplicates["remove_completely"]:
                print(f"\n📄 {item['file']}")
                print(f"   Reason: {item['reason']}")
                print(f"   Duplicate of: {item['duplicate_of']}")
        
        # 리팩토링 필요
        if self.duplicates["refactor_needed"]:
            print("\n🔧 Files Needing Refactoring:")
            print("-" * 50)
            for item in self.duplicates["refactor_needed"]:
                print(f"\n📄 {item['file']}")
                print(f"   Recommendation: {item['recommendation']}")
                
                if item["patterns_found"]:
                    print("   Duplicate patterns found:")
                    for pattern_name, matches in item["patterns_found"].items():
                        print(f"   - {pattern_name}: {len(matches)} occurrences")
                        # Show first 3 examples
                        for line_no, line in matches[:3]:
                            print(f"     Line {line_no}: {line[:60]}...")
                        if len(matches) > 3:
                            print(f"     ... and {len(matches) - 3} more")
        
        # 요약
        print("\n📋 Summary:")
        print("-" * 50)
        print(f"Files to remove: {len(self.duplicates['remove_completely'])}")
        print(f"Files to refactor: {len(self.duplicates['refactor_needed'])}")
        
        # 아키텍처 권장사항
        print("\n🏗️  Recommended Architecture:")
        print("-" * 50)
        print("1. Models: Define structure and types only (using Pydantic for basic type safety)")
        print("2. Core/Validation: All business validation rules and logic")
        print("3. Middleware: Integration layer that calls core validation, no duplicate logic")
        
        # 액션 아이템
        print("\n✅ Action Items:")
        print("-" * 50)
        print("1. Remove middleware/request_validation.py")
        print("2. Refactor enterprise_validation.py to be a thin integration layer")
        print("3. Remove @field_validator decorators from models")
        print("4. Move all validation logic to core/validation/rules/")
        print("5. Update imports and dependencies")
        
        # 마이그레이션 스크립트 생성 제안
        print("\n💡 Next Steps:")
        print("-" * 50)
        print("1. Review this report with the team")
        print("2. Create migration plan for each file")
        print("3. Update tests to use core validation")
        print("4. Remove duplicate code in phases")
        print("5. Update documentation")


def main():
    """메인 실행 함수"""
    print("🧹 Duplicate Validation Code Cleanup Tool")
    print("This tool identifies duplicate validation logic between")
    print("middleware/models and core/validation implementation")
    print()
    
    finder = DuplicateValidationFinder()
    finder.find_duplicates()
    
    print("\n⚠️  Note: This script only generates a report.")
    print("Actual code changes should be made manually after team review.")


if __name__ == "__main__":
    main()