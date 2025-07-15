#!/usr/bin/env python3
"""
GraphQL Service Startup Script
Starts the GraphQL service with proper configuration
"""

import os
import subprocess
import sys
from pathlib import Path

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def setup_environment():
    """Setup environment variables for GraphQL service"""
    os.environ.update(
        {
            # Service URLs
            "USER_SERVICE_URL": os.getenv("USER_SERVICE_URL", "http://localhost:8010"),
            "OMS_SERVICE_URL": os.getenv("OMS_SERVICE_URL", "http://localhost:8000"),
            "AUDIT_SERVICE_URL": os.getenv(
                "AUDIT_SERVICE_URL", "http://localhost:8011"
            ),
            # Redis
            "REDIS_URL": os.getenv("REDIS_URL", "redis://localhost:6379"),
            # JWT Configuration - Use environment variable in production
            "JWT_SECRET": os.getenv("JWT_SECRET", "CHANGE-ME-IN-PRODUCTION"),
            # GraphQL Configuration
            "GRAPHQL_PORT": "8006",
            "GRAPHQL_WS_PORT": "8004",
            # Feature Flags
            "ENABLE_GRAPHQL_TRACING": "true",
            "ENABLE_GRAPHQL_CACHING": "true",
            "ENABLE_GRAPHQL_VALIDATION": "true",
            # Monitoring
            "ENABLE_TELEMETRY": "true",
            "ENABLE_METRICS": "true",
            "PROMETHEUS_PORT": "8091",
            # Logging
            "LOG_LEVEL": "INFO",
        }
    )


def check_dependencies():
    """Check if required services are running"""
    print(f"{BOLD}{BLUE}Checking dependencies...{RESET}")

    # Check Redis
    try:
        result = subprocess.run(["redis-cli", "ping"], capture_output=True, text=True)
        if result.stdout.strip() == "PONG":
            print(f"{GREEN}✓ Redis is running{RESET}")
        else:
            print(f"{RED}✗ Redis is not running{RESET}")
            print("  Start with: brew services start redis")
            return False
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"{RED}✗ Redis CLI not found or failed: {e}{RESET}")
        return False

    return True


def setup_graphql_module():
    """Setup the GraphQL module in the OMS directory"""
    oms_dir = Path(
        "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service"
    )

    # Create virtual environment if it doesn't exist
    venv_path = oms_dir / "venv_graphql"
    if not venv_path.exists():
        print(f"{YELLOW}Creating GraphQL virtual environment...{RESET}")
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)])

    # Install requirements
    print(f"{YELLOW}Installing GraphQL requirements...{RESET}")
    pip_path = venv_path / "bin" / "pip"
    requirements_path = oms_dir / "requirements-graphql.txt"

    subprocess.run([str(pip_path), "install", "-r", str(requirements_path)])

    return venv_path


def start_graphql_services():
    """Start GraphQL services"""
    if not check_dependencies():
        print(
            f"{RED}Dependencies check failed. Please install required services.{RESET}"
        )
        return

    setup_environment()
    venv_path = setup_graphql_module()

    oms_dir = Path(
        "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service"
    )

    # Start GraphQL HTTP service
    print(f"\n{BOLD}{GREEN}Starting GraphQL HTTP Service on port 8006...{RESET}")
    graphql_cmd = [
        str(venv_path / "bin" / "python"),
        "-m",
        "uvicorn",
        "api.graphql.modular_main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8006",
        "--reload",
    ]

    graphql_process = subprocess.Popen(graphql_cmd, cwd=str(oms_dir), env=os.environ)

    # Start GraphQL WebSocket service
    print(f"\n{BOLD}{GREEN}Starting GraphQL WebSocket Service on port 8004...{RESET}")
    ws_cmd = [
        str(venv_path / "bin" / "python"),
        "-m",
        "uvicorn",
        "api.graphql.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8004",
        "--reload",
    ]

    ws_process = subprocess.Popen(ws_cmd, cwd=str(oms_dir), env=os.environ)

    print(f"\n{BOLD}{GREEN}GraphQL Services Started!{RESET}")
    print("  - GraphQL HTTP: http://localhost:8006/graphql")
    print("  - GraphQL Playground: http://localhost:8006/graphql")
    print("  - GraphQL WebSocket: ws://localhost:8004/ws")
    print("  - Health Check: http://localhost:8006/health")
    print(f"\n{YELLOW}Press Ctrl+C to stop the services{RESET}")

    try:
        graphql_process.wait()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Stopping GraphQL services...{RESET}")
        graphql_process.terminate()
        ws_process.terminate()
        print(f"{GREEN}Services stopped.{RESET}")


if __name__ == "__main__":
    start_graphql_services()
