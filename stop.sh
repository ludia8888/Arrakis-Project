#!/bin/bash
# Unified Arrakis Project Stop Script
# Consolidates all stop scripts into one

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
CLEAN=false
SERVICE=""
MODE="auto"  # auto-detect based on what's running

# Function to display usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --clean         Stop services and clean logs/data"
    echo "  --service=NAME  Stop specific service only"
    echo "  --mode=MODE     Stop mode (docker|process|all)"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Stop all running services"
    echo "  $0 --clean            # Stop and clean everything"
    echo "  $0 --service=oms      # Stop only OMS service"
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN=true
            shift
            ;;
        --service=*)
            SERVICE="${1#*=}"
            shift
            ;;
        --mode=*)
            MODE="${1#*=}"
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

# Function to stop process-based services
stop_processes() {
    print_status "$YELLOW" "🛑 Stopping process-based services..."
    
    # Stop services using PID files
    if [ -d logs ]; then
        for pidfile in logs/*.pid; do
            if [ -f "$pidfile" ]; then
                PID=$(cat "$pidfile")
                SERVICE_NAME=$(basename "$pidfile" .pid)
                
                if [ -n "$SERVICE" ] && [ "$SERVICE_NAME" != "$SERVICE" ]; then
                    continue
                fi
                
                if kill -0 "$PID" 2>/dev/null; then
                    print_status "$YELLOW" "Stopping $SERVICE_NAME (PID: $PID)..."
                    kill "$PID"
                    rm "$pidfile"
                    print_status "$GREEN" "✅ $SERVICE_NAME stopped"
                else
                    print_status "$YELLOW" "⚠️  $SERVICE_NAME not running (stale PID file)"
                    rm "$pidfile"
                fi
            fi
        done
    fi
    
    # Stop any uvicorn processes
    if pgrep -f "uvicorn" > /dev/null 2>&1; then
        print_status "$YELLOW" "Stopping uvicorn processes..."
        pkill -f "uvicorn" || true
        sleep 2
    fi
    
    # Also kill processes on specific ports
    for port in 8000 8010 8011; do
        if lsof -ti:$port > /dev/null 2>&1; then
            print_status "$YELLOW" "Stopping process on port $port..."
            lsof -ti:$port | xargs kill -9 2>/dev/null || true
        fi
    done
    
    # Stop Redis if we started it
    if pgrep -x "redis-server" > /dev/null; then
        print_status "$YELLOW" "Stopping Redis..."
        redis-cli shutdown || true
    fi
}

# Function to stop Docker services
stop_docker() {
    print_status "$YELLOW" "🐳 Stopping Docker services..."
    
    if [ -n "$SERVICE" ]; then
        docker-compose stop "$SERVICE"
    else
        docker-compose down
        
        if [ "$CLEAN" = true ]; then
            print_status "$YELLOW" "🗑️  Removing volumes and images..."
            docker-compose down -v --rmi local
        fi
    fi
    
    print_status "$GREEN" "✅ Docker services stopped"
}

# Function to clean logs and temporary files
clean_files() {
    print_status "$YELLOW" "🧹 Cleaning logs and temporary files..."
    
    # Remove log files
    if [ -d logs ]; then
        rm -rf logs/*
        print_status "$GREEN" "✅ Logs cleaned"
    fi
    
    # Remove Python cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    
    # Remove .pytest_cache
    find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    
    print_status "$GREEN" "✅ Temporary files cleaned"
}

# Auto-detect what's running
detect_running_services() {
    local docker_running=false
    local process_running=false
    
    # Check Docker
    if command -v docker-compose >/dev/null 2>&1; then
        if docker-compose ps -q | grep -q .; then
            docker_running=true
        fi
    fi
    
    # Check processes
    if pgrep -f "uvicorn" > /dev/null 2>&1 || ps aux | grep -E "uvicorn|python.*main:app" | grep -v grep > /dev/null 2>&1; then
        process_running=true
    fi
    
    # Also check specific ports
    for port in 8000 8010 8011; do
        if lsof -i:$port > /dev/null 2>&1; then
            process_running=true
            break
        fi
    done
    
    if [ "$docker_running" = true ] && [ "$process_running" = true ]; then
        MODE="all"
    elif [ "$docker_running" = true ]; then
        MODE="docker"
    elif [ "$process_running" = true ]; then
        MODE="process"
    else
        print_status "$YELLOW" "⚠️  No running services detected"
        exit 0
    fi
}

# Main execution
print_status "$BLUE" "🛑 Arrakis Project Unified Stop Script"

# Auto-detect if needed
if [ "$MODE" = "auto" ]; then
    detect_running_services
    print_status "$BLUE" "Detected mode: $MODE"
fi

# Stop services based on mode
case $MODE in
    docker)
        stop_docker
        ;;
    process)
        stop_processes
        ;;
    all)
        stop_docker
        stop_processes
        ;;
    *)
        print_status "$RED" "❌ Invalid mode: $MODE"
        exit 1
        ;;
esac

# Clean if requested
if [ "$CLEAN" = true ]; then
    clean_files
fi

print_status "$GREEN" "✅ All requested services stopped successfully!"

# Show what to do next
echo ""
print_status "$BLUE" "💡 Next steps:"
echo "   - Start services: ./start.sh"
echo "   - Check status: ./status.sh"
echo "   - Run tests: ./test.sh"