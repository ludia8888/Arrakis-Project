# 백업 디렉토리 정보

레거시 코드 정리 과정에서 생성된 백업 디렉토리들입니다.
안전한 롤백을 위해 보관 중이며, 시스템이 안정화된 후 삭제 가능합니다.

## 백업 디렉토리 목록

### 1. backups/
- **생성일**: 2025-06-29 01:32
- **내용**: 초기 백업
- **보관 권장 기간**: 1개월

### 2. legacy_cleanup_backup_20250629_014617/
- **생성일**: 2025-06-29 01:46:17
- **내용**: 레거시 코드 정리 초기 백업
- **포함 파일**: 초기 정리 대상 파일들
- **보관 권장 기간**: 2주

### 3. legacy_cleanup_backup_20250629_014625/
- **생성일**: 2025-06-29 01:46:25
- **내용**: merge_strategies.py, conflict_resolver.py 백업
- **이유**: TerminusDB로 이전된 버전 관리 기능
- **보관 권장 기간**: 1개월 (중요 기능)

### 4. validation_backup/
- **생성일**: 2025-06-29 02:25
- **내용**: 전체 validation 및 traversal 모듈 백업
- **포함 내용**:
  - core/validation/ 전체
  - core/traversal/ 전체
  - middleware/enterprise_validation.py
- **보관 권장 기간**: 3개월 (핵심 비즈니스 로직)

### 5. validation_terminus_backup_20250629_140147/
- **생성일**: 2025-06-29 14:01:47
- **내용**: TerminusDB 중복 validation 제거 전 백업
- **포함 파일**: 구조적 validation 관련 파일들
- **보관 권장 기간**: 1개월

### 6. versioning_backup/
- **생성일**: 2025-06-29 14:05
- **내용**: 커스텀 버전 관리 시스템 백업
- **포함 내용**:
  - core/versioning/
  - core/history/
  - version_manager.py
  - naming_history.py
- **보관 권장 기간**: 3개월 (중요 기능)

## 삭제 가이드

### 즉시 삭제 가능 (시스템 안정 확인 후)
- legacy_cleanup_backup_20250629_014617/

### 2주 후 삭제 권장
- validation_terminus_backup_20250629_140147/

### 1개월 후 삭제 권장
- backups/
- legacy_cleanup_backup_20250629_014625/

### 3개월 후 삭제 권장
- validation_backup/
- versioning_backup/

## 백업 복원 방법

특정 기능에 문제가 발생한 경우:

```bash
# 예: validation 복원
cp -r validation_backup/validation/* core/validation/

# 예: 특정 파일 복원
cp versioning_backup/version_manager.py core/validation/
```

## 주의사항

1. 백업을 삭제하기 전에 반드시 시스템 안정성을 확인하세요.
2. 프로덕션 배포 후 최소 1주일은 백업을 유지하세요.
3. 중요 기능(validation, versioning)의 백업은 더 오래 보관하세요.