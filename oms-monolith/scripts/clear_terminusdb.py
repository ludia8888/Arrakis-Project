#!/usr/bin/env python3
"""
TerminusDB 데이터베이스 초기화 스크립트
모든 데이터베이스를 삭제하고 초기 상태로 되돌립니다.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from terminusdb_client import WOQLClient
from shared.config import get_config

def clear_all_databases():
    """모든 TerminusDB 데이터베이스를 삭제합니다."""
    config = get_config()
    
    # TerminusDB 클라이언트 설정
    client = WOQLClient(
        server_url=config.TERMINUS_SERVER_URL,
        account=config.TERMINUS_ORGANIZATION
    )
    # TerminusDB 인증 정보로 연결
    client.connect(user="admin", key="admin123")
    
    try:
        # 모든 데이터베이스 목록 가져오기
        databases = client.list_databases()
        
        print(f"Found {len(databases)} databases")
        
        # 각 데이터베이스 삭제
        for db in databases:
            # db가 문자열인 경우와 딕셔너리인 경우 모두 처리
            if isinstance(db, str):
                db_id = db
            else:
                db_id = db.get('id', db.get('name', ''))
            
            if db_id and db_id != '_system':  # _system 데이터베이스는 삭제하지 않음
                print(f"Deleting database: {db_id}")
                try:
                    client.delete_database(db_id)
                    print(f"  ✓ Deleted {db_id}")
                except Exception as e:
                    print(f"  ✗ Failed to delete {db_id}: {str(e)}")
        
        print("\nAll databases have been cleared.")
        
    except Exception as e:
        print(f"Error clearing databases: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    print("=== TerminusDB Clear Script ===")
    print("This will delete ALL databases in TerminusDB.")
    
    response = input("Are you sure you want to continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Operation cancelled.")
        sys.exit(0)
    
    success = clear_all_databases()
    sys.exit(0 if success else 1)