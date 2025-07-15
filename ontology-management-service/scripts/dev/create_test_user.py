#!/usr/bin/env python3
"""
Create a test user for integration testing
"""
import asyncio
import json
import os
import uuid
from datetime import datetime

import argon2
import asyncpg


async def create_test_user():
    """Create a test user in the User Service database"""

    # Connect to database
    conn = await asyncpg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "15433")),
        user=os.getenv("DB_USER", "user_user"),
        password=os.getenv("DB_PASSWORD", "user_pass"),
        database=os.getenv("DB_NAME", "user_db"),
    )

    try:
        # Check if user already exists
        existing = await conn.fetchrow(
            "SELECT id FROM users WHERE username = $1", "test_user"
        )

        if existing:
            print("Test user already exists")
            return

        # Hash password using Argon2
        ph = argon2.PasswordHasher()
        password_hash = ph.hash(os.getenv("TEST_USER_PASSWORD", "test_password"))

        # Create user
        user_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO users (
                id, username, email, full_name, password_hash,
                status, roles, permissions, teams,
                mfa_enabled, failed_login_attempts,
                created_at, created_by
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8, $9,
                $10, $11,
                $12, $13
            )
        """,
            user_id,
            "test_user",
            "test@example.com",
            "Test User",
            password_hash,
            "active",
            json.dumps(["user"]),
            json.dumps([]),
            json.dumps([]),
            False,
            0,
            datetime.utcnow(),
            "system",
        )

        print(f"Test user created successfully!")
        print(f"User ID: {user_id}")
        print(f"Username: test_user")
        print(f"Password: {os.getenv('TEST_USER_PASSWORD', 'test_password')}")

    except Exception as e:
        print(f"Error creating test user: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(create_test_user())
