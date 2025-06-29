# Permission Consolidation Summary

## Overview
Consolidated duplicate permission definitions into a single canonical version in `models/permissions.py`.

## Changes Made

### 1. Consolidated ResourceType Enum
- **Canonical location**: `models/permissions.py`
- **Removed duplicates from**:
  - `core/auth/resource_permission_checker.py`
  - `models/audit_events.py`
- **Added missing values to canonical version**:
  - `PROPERTY` (from auth module)
  - `VALIDATION` (from auth module)
  - `ACL`, `USER`, `SYSTEM` (from audit_events module)

### 2. Consolidated Action Enum
- **Canonical location**: `models/permissions.py`
- **Removed duplicate from**: `core/auth/resource_permission_checker.py`
- **Added missing value to canonical version**:
  - `VALIDATE` (from auth module)

### 3. Special Case: HistoryResourceType
- **Renamed** `ResourceType` in `core/history/models.py` to `HistoryResourceType`
- This enum has different values (camelCase) and serves a different purpose for history tracking
- Updated imports in `api/graphql/history_schema.py`

### 4. No Changes Needed
- `Role` enum - only exists in `models/permissions.py`
- `PERMISSION_MATRIX` - only exists in `models/permissions.py`

## Files Modified

1. **models/permissions.py**
   - Added `PROPERTY`, `VALIDATION`, `ACL`, `USER`, `SYSTEM` to ResourceType
   - Added `VALIDATE` to Action

2. **core/auth/resource_permission_checker.py**
   - Removed duplicate ResourceType and Action enums
   - Added import: `from models.permissions import ResourceType, Action`

3. **models/audit_events.py**
   - Removed duplicate ResourceType enum
   - Added import: `from models.permissions import ResourceType`

4. **core/history/models.py**
   - Renamed `ResourceType` to `HistoryResourceType` (different purpose)
   - Updated all references within the file

5. **api/graphql/history_schema.py**
   - Updated import to use `HistoryResourceType`

## Benefits

1. **Single Source of Truth**: All permission-related enums are now in one place
2. **Consistency**: All modules use the same definitions
3. **Maintainability**: Changes only need to be made in one location
4. **Clarity**: History module's ResourceType is clearly differentiated

## Notes

- The circular import issue detected during testing is unrelated to this consolidation
- All duplicate definitions have been successfully removed
- The canonical version now includes all values that were present in any of the duplicates