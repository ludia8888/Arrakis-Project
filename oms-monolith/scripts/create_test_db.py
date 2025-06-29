#!/usr/bin/env python3
"""
TerminusDB 테스트 데이터베이스 생성 스크립트
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from terminusdb_client import WOQLClient
from shared.config import get_config

def create_test_database():
    """테스트 데이터베이스를 생성합니다."""
    config = get_config()
    
    # TerminusDB 클라이언트 설정
    client = WOQLClient(
        server_url=config.TERMINUS_SERVER_URL,
        account=config.TERMINUS_ORGANIZATION
    )
    # TerminusDB 인증 정보로 연결
    client.connect(
        user=os.getenv("TERMINUS_DB_USER", "admin"), 
        key=os.getenv("TERMINUS_DB_KEY", "admin123")
    )
    
    try:
        # 데이터베이스 생성
        db_name = config.TERMINUS_DB
        print(f"Creating database: {db_name}")
        
        client.create_database(
            db_name,
            label=f"OMS Test Database",
            description="Test database for Ontology Management System"
        )
        
        print(f"✓ Database '{db_name}' created successfully")
        return True
        
    except Exception as e:
        if "already exists" in str(e):
            print(f"Database '{db_name}' already exists")
            return True
        else:
            print(f"Error creating database: {str(e)}")
            return False

if __name__ == "__main__":
    print("=== TerminusDB Create Test Database ===")
    success = create_test_database()
    sys.exit(0 if success else 1)