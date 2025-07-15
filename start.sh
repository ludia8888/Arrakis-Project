#!/bin/bash
# Unified Arrakis Project Startup Script
# Consolidates all start scripts into one with different modes

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
MODE="docker"
VERBOSE=false
SERVICES="all"

# Function to display usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --mode=MODE         Startup mode (docker|production|development|microservices)"
    echo "                      - docker: Use Docker Compose (default)"
    echo "                      - production: Production with health checks"
    echo "                      - development: Development with hot reload"
    echo "                      - microservices: Start only microservices"
    echo "  --services=LIST     Comma-separated list of services to start"
    echo "                      Default: all"
    echo "  --verbose           Enable verbose output"
    echo "  --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                              # Start all services with Docker"
    echo "  $0 --mode=production            # Start in production mode"
    echo "  $0 --mode=development           # Start in development mode"
    echo "  $0 --services=oms,user-service  # Start specific services"
    exit 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode=*)
            MODE="${1#*=}"
            shift
            ;;
        --services=*)
            SERVICES="${1#*=}"
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check port availability
check_port() {
    local port=$1
    if lsof -i:$port >/dev/null 2>&1; then
        return 1
    else
        return 0
    fi
}

# Function to wait for service health
wait_for_health() {
    local service=$1
    local url=$2
    local max_attempts=30
    local attempt=0

    print_status "$YELLOW" "⏳ Waiting for $service to be healthy..."

    while [ $attempt -lt $max_attempts ]; do
        if curl -f -s "$url" > /dev/null 2>&1; then
            print_status "$GREEN" "✅ $service is healthy!"
            return 0
        fi
        sleep 2
        ((attempt++))
    done

    print_status "$RED" "❌ $service failed to start after $max_attempts attempts"
    return 1
}

# Docker mode startup
start_docker() {
    print_status "$BLUE" "🐳 Starting services with Docker Compose..."

    if ! command_exists docker-compose && ! command_exists docker; then
        print_status "$RED" "❌ Docker or Docker Compose not found!"
        exit 1
    fi

    # Check if docker-compose.yml exists
    if [ ! -f docker-compose.yml ]; then
        print_status "$RED" "❌ docker-compose.yml not found!"
        exit 1
    fi

    # Create necessary directories and configs if they don't exist
    if [ ! -f .env ] && [ -f .env.example ]; then
        cp .env.example .env
        print_status "$YELLOW" "⚠️  Created .env from .env.example - please update values"
    fi

    # Start services based on selection
    if [ "$SERVICES" = "all" ]; then
        docker-compose up -d
    else
        docker-compose up -d $SERVICES
    fi

    # Show status
    sleep 5
    docker-compose ps

    print_status "$GREEN" "✅ Docker services started!"
    print_status "$BLUE" "📋 Check status: docker-compose ps"
    print_status "$BLUE" "📋 View logs: docker-compose logs -f [service]"
}

# Production mode startup
start_production() {
    print_status "$BLUE" "🚀 Starting services in production mode..."

    # Check Python availability
    if ! command_exists python3; then
        print_status "$RED" "❌ Python3 not found!"
        exit 1
    fi

    # Check required ports
    local required_ports=(8000 8010 8011)
    for port in "${required_ports[@]}"; do
        if ! check_port $port; then
            print_status "$YELLOW" "⚠️  Port $port is already in use. Attempting to stop existing service..."
            # Try to kill the process using the port
            lsof -ti:$port | xargs kill -9 2>/dev/null || true
            sleep 1
            if ! check_port $port; then
                print_status "$RED" "❌ Failed to free port $port!"
                exit 1
            fi
        fi
    done

    # Start Redis if not running
    if check_port 6379; then
        print_status "$YELLOW" "Starting Redis..."
        redis-server --daemonize yes
        sleep 2
    fi

    # Start PostgreSQL if not running
    if check_port 5432 && command_exists pg_ctl; then
        print_status "$YELLOW" "Starting PostgreSQL..."
        pg_ctl start -D /usr/local/var/postgres -l /usr/local/var/postgres/server.log
        sleep 3
    fi

    # Create log directory
    mkdir -p logs

    # Activate virtual environment if it exists
    if [ -f venv/bin/activate ]; then
        source venv/bin/activate
    elif [ -f .venv/bin/activate ]; then
        source .venv/bin/activate
    else
        print_status "$YELLOW" "⚠️  No virtual environment found. Running with system Python."
    fi

    # Start services with proper production settings
    print_status "$YELLOW" "Starting User Service..."
    cd user-service
    nohup python -m uvicorn src.main:app --host 0.0.0.0 --port 8010 --workers 4 > ../logs/user-service.log 2>&1 &
    echo $! > ../logs/user-service.pid
    cd ..

    print_status "$YELLOW" "Starting Audit Service..."
    cd audit-service
    nohup python -m uvicorn src.main:app --host 0.0.0.0 --port 8011 --workers 4 > ../logs/audit-service.log 2>&1 &
    echo $! > ../logs/audit-service.pid
    cd ..

    print_status "$YELLOW" "Starting OMS..."
    cd ontology-management-service
    nohup python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4 > ../logs/oms.log 2>&1 &
    echo $! > ../logs/oms.pid
    cd ..

    # Wait for services to be healthy
    wait_for_health "User Service" "http://localhost:8010/health"
    wait_for_health "Audit Service" "http://localhost:8011/health"
    wait_for_health "OMS" "http://localhost:8000/health"

    print_status "$GREEN" "✅ All services started in production mode!"
    print_status "$BLUE" "📋 Logs are in the logs/ directory"
}

# Development mode startup
start_development() {
    print_status "$BLUE" "💻 Starting services in development mode with hot reload..."

    # Check Python availability
    if ! command_exists python3; then
        print_status "$RED" "❌ Python3 not found!"
        exit 1
    fi

    # Start Redis if needed
    if check_port 6379; then
        print_status "$YELLOW" "Starting Redis..."
        redis-server &
        sleep 2
    fi

    # Start services in separate terminals if possible
    if command_exists gnome-terminal || command_exists xterm || command_exists osascript; then
        # Activate virtual environment if it exists
        ACTIVATE_CMD=""
        if [ -f venv/bin/activate ]; then
            ACTIVATE_CMD="source '$PWD/venv/bin/activate' && "
        elif [ -f .venv/bin/activate ]; then
            ACTIVATE_CMD="source '$PWD/.venv/bin/activate' && "
        fi

        # macOS
        if command_exists osascript; then
            osascript -e 'tell app "Terminal" to do script "cd '$PWD'/user-service && '"$ACTIVATE_CMD"'python -m uvicorn src.main:app --reload --port 8010"'
            osascript -e 'tell app "Terminal" to do script "cd '$PWD'/audit-service && '"$ACTIVATE_CMD"'python -m uvicorn src.main:app --reload --port 8011"'
            osascript -e 'tell app "Terminal" to do script "cd '$PWD'/ontology-management-service && '"$ACTIVATE_CMD"'python -m uvicorn api.main:app --reload --port 8000"'
        # Linux with gnome-terminal
        elif command_exists gnome-terminal; then
            gnome-terminal -- bash -c "cd user-service && uvicorn src.main:app --reload --port 8010; exec bash"
            gnome-terminal -- bash -c "cd audit-service && uvicorn src.main:app --reload --port 8011; exec bash"
            gnome-terminal -- bash -c "cd ontology-management-service && uvicorn bootstrap.app:app --reload --port 8000; exec bash"
        fi

        print_status "$GREEN" "✅ Services started in separate terminals with hot reload!"
    else
        # Fallback to background processes
        print_status "$YELLOW" "Starting services in background with reload..."

        # Activate virtual environment if it exists
        if [ -f venv/bin/activate ]; then
            source venv/bin/activate
        elif [ -f .venv/bin/activate ]; then
            source .venv/bin/activate
        fi

        cd user-service && python -m uvicorn src.main:app --reload --port 8010 &
        cd ../audit-service && python -m uvicorn src.main:app --reload --port 8011 &
        cd ../ontology-management-service && python -m uvicorn api.main:app --reload --port 8000 &

        print_status "$GREEN" "✅ Services started in development mode!"
        print_status "$YELLOW" "⚠️  Services are running in background. Use 'ps aux | grep uvicorn' to see them."
    fi
}

# Microservices mode startup
start_microservices() {
    print_status "$BLUE" "🎯 Starting microservices only..."

    if command_exists docker-compose; then
        docker-compose up -d data-kernel-service embedding-service scheduler-service event-gateway
    else
        print_status "$RED" "❌ Docker Compose required for microservices mode!"
        exit 1
    fi

    print_status "$GREEN" "✅ Microservices started!"
}

# Main execution
print_status "$BLUE" "🚀 Arrakis Project Unified Startup Script"
print_status "$BLUE" "Mode: $MODE"

case $MODE in
    docker)
        start_docker
        ;;
    production)
        start_production
        ;;
    development)
        start_development
        ;;
    microservices)
        start_microservices
        ;;
    *)
        print_status "$RED" "❌ Invalid mode: $MODE"
        usage
        ;;
esac

# Show service URLs
echo ""
print_status "$BLUE" "🔗 Service URLs:"
echo "   - OMS API: http://localhost:8000"
echo "   - User Service: http://localhost:8010"
echo "   - Audit Service: http://localhost:8011"

if [ "$MODE" = "docker" ]; then
    echo "   - GraphQL: http://localhost:8006/graphql"
    echo "   - Grafana: http://localhost:3000 (admin/admin)"
    echo "   - Prometheus: http://localhost:9090"
    echo "   - Jaeger: http://localhost:16686"
fi

echo ""
print_status "$GREEN" "✅ Startup complete!"
