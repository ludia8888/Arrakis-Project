#!/usr/bin/env python3
"""
Create a test user directly in the User Service database
This bypasses the audit service connection issue
"""
import psycopg2
import bcrypt
import uuid
from datetime import datetime

def create_test_user():
    # User Service PostgreSQL connection
    conn = psycopg2.connect(
        host="localhost",
        port=5434,  # User Service PostgreSQL port
        database="user_db",
        user="user_user",
        password="user_password"
    )
    
    cursor = conn.cursor()
    
    # Test user details
    user_id = str(uuid.uuid4())
    username = "testuser_integration"
    password = "TestPassword123!"
    email = "testuser_integration@example.com"
    
    # Hash password
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    try:
        # Insert user
        cursor.execute("""
            INSERT INTO users (id, username, email, password_hash, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (username) DO NOTHING
        """, (
            user_id,
            username,
            email,
            hashed_password,
            'active',
            datetime.utcnow(),
            datetime.utcnow()
        ))
        
        conn.commit()
        print(f"✅ Test user created successfully:")
        print(f"   Username: {username}")
        print(f"   Password: {password}")
        print(f"   Email: {email}")
        
    except Exception as e:
        print(f"❌ Failed to create test user: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    create_test_user()