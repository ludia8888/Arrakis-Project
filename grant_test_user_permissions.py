#!/usr/bin/env python3
"""
Grant necessary permissions to the test user for integration testing
"""
import psycopg2
import uuid
from datetime import datetime

def grant_test_user_permissions():
    # User Service PostgreSQL connection
    conn = psycopg2.connect(
        host="localhost",
        port=5434,  # User Service PostgreSQL port
        database="user_db",
        user="user_user",
        password="user_password"
    )
    
    cursor = conn.cursor()
    
    try:
        # Get the test user ID
        cursor.execute("SELECT id FROM users WHERE username = %s", ("testuser_integration",))
        user_result = cursor.fetchone()
        
        if not user_result:
            print("❌ Test user not found")
            return False
            
        user_id = user_result[0]
        print(f"✅ Found test user: {user_id}")
        
        # Check if permissions table exists and see what's in it
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name LIKE '%permission%'
        """)
        perm_tables = cursor.fetchall()
        print(f"📋 Permission-related tables: {[t[0] for t in perm_tables]}")
        
        # Check if roles table exists
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name LIKE '%role%'
        """)
        role_tables = cursor.fetchall()
        print(f"📋 Role-related tables: {[t[0] for t in role_tables]}")
        
        # Let's see what permissions exist
        if any('permissions' in t[0] for t in perm_tables):
            cursor.execute("SELECT id, name, resource_type, permission_type FROM permissions LIMIT 10")
            existing_perms = cursor.fetchall()
            print(f"📋 Existing permissions: {existing_perms}")
        
        # Use existing ontology permissions
        cursor.execute("SELECT id FROM permissions WHERE name = %s", ("ontology:*:write",))
        write_perm_result = cursor.fetchone()
        if write_perm_result:
            write_perm_id = write_perm_result[0]
            
            # Grant write permission to user
            cursor.execute("""
                INSERT INTO user_permissions (user_id, permission_id, granted_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, permission_id) DO NOTHING
            """, (user_id, write_perm_id, datetime.utcnow()))
            print(f"✅ Granted write permission: {write_perm_id}")
        else:
            print("❌ Write permission not found")
            
        cursor.execute("SELECT id FROM permissions WHERE name = %s", ("ontology:*:read",))
        read_perm_result = cursor.fetchone()
        if read_perm_result:
            read_perm_id = read_perm_result[0]
            
            # Grant read permission to user
            cursor.execute("""
                INSERT INTO user_permissions (user_id, permission_id, granted_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, permission_id) DO NOTHING
            """, (user_id, read_perm_id, datetime.utcnow()))
            print(f"✅ Granted read permission: {read_perm_id}")
        else:
            print("❌ Read permission not found")
        
        conn.commit()
        print("✅ Permissions granted successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to grant permissions: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    grant_test_user_permissions()