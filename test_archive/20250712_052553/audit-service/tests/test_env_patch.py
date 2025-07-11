"""
Test environment patch to set default environment variables
"""
import os

# Set default environment variables for testing
DEFAULT_TEST_ENV = {
    'SIEM_TYPE': 'elasticsearch',
    'ELASTICSEARCH_HOST': 'localhost:9200',
    'ELASTICSEARCH_INDEX': 'test-audit-events',
    'EVENT_BROKER_TYPE': 'nats',
    'NATS_URL': 'nats://localhost:4222',
    'KAFKA_SERVERS': 'localhost:9092',
    'RABBITMQ_URL': 'amqp://guest:guest@localhost/',
    'REDIS_URL': 'redis://localhost:6379',
    'DATABASE_URL': 'postgresql+asyncpg://test:test@localhost/audit_test',
    'JWT_SECRET': 'test-secret-key-for-testing-only'
}

def patch_test_env():
    """Patch environment variables for testing"""
    for key, value in DEFAULT_TEST_ENV.items():
        if key not in os.environ:
            os.environ[key] = value

# Apply patches when imported
patch_test_env()