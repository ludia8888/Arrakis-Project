#!/usr/bin/env python3
"""Create test user directly in database"""
import psycopg2
from passlib.context import CryptContext
import uuid

# Password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash password
password_hash = pwd_context.hash("admin123")

# Connect to database
conn = psycopg2.connect(
    host="user-postgres",
    port=5432,
    database="user_db",
    user="user_user", 
    password="user_password"
)

try:
    with conn.cursor() as cur:
        # Check if admin exists
        cur.execute("SELECT id FROM users WHERE username = %s", ("admin",))
        if cur.fetchone():
            print("Admin user already exists")
        else:
            # Create admin user
            user_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO users (
                    id, username, email, password_hash, 
                    status, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, NOW(), NOW()
                )
            """, (user_id, "admin", "admin@example.com", password_hash, "active"))
            conn.commit()
            print(f"Admin user created with ID: {user_id}")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()