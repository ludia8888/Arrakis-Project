#!/bin/bash
# Unified Arrakis Project Status Script
# Shows comprehensive status of all services

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to check service health
check_service() {
    local name=$1
    local url=$2
    local type=$3
    
    printf "%-20s" "$name"
    
    if [ "$type" = "docker" ]; then
        # Check Docker container
        if docker ps --format "table {{.Names}}" | grep -q "$url"; then
            local status=$(docker inspect -f '{{.State.Status}}' "$url" 2>/dev/null)
            if [ "$status" = "running" ]; then
                print_status "$GREEN" "[RUNNING]"
            else
                print_status "$YELLOW" "[${status^^}]"
            fi
        else
            print_status "$RED" "[NOT FOUND]"
        fi
    elif [ "$type" = "process" ]; then
        # Check process
        if pgrep -f "$url" > /dev/null; then
            print_status "$GREEN" "[RUNNING]"
        else
            print_status "$RED" "[STOPPED]"
        fi
    else
        # Check HTTP endpoint
        if curl -f -s "$url" > /dev/null 2>&1; then
            local response_time=$(curl -o /dev/null -s -w '%{time_total}' "$url")
            print_status "$GREEN" "[HEALTHY] ${response_time}s"
        else
            print_status "$RED" "[UNREACHABLE]"
        fi
    fi
}

# Function to check port
check_port_status() {
    local port=$1
    local service=$2
    
    if lsof -i:$port > /dev/null 2>&1; then
        echo -e "   Port $port: ${GREEN}✓ In use${NC} ($service)"
    else
        echo -e "   Port $port: ${RED}✗ Free${NC} ($service)"
    fi
}

# Header
print_status "$BLUE" "╔════════════════════════════════════════════════════════════╗"
print_status "$BLUE" "║             Arrakis Project Service Status                 ║"
print_status "$BLUE" "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check Docker status
print_status "$CYAN" "🐳 Docker Services:"
if command -v docker > /dev/null 2>&1 && docker ps > /dev/null 2>&1; then
    # Check Docker containers
    check_service "PostgreSQL" "arrakis-postgres" "docker"
    check_service "Redis" "arrakis-redis" "docker"
    check_service "NATS" "arrakis-nats" "docker"
    check_service "TerminusDB" "arrakis-terminusdb" "docker"
    check_service "Jaeger" "arrakis-jaeger" "docker"
    check_service "Prometheus" "arrakis-prometheus" "docker"
    check_service "Grafana" "arrakis-grafana" "docker"
else
    print_status "$YELLOW" "Docker not running or not accessible"
fi

echo ""
print_status "$CYAN" "🚀 Application Services:"
check_service "OMS API" "http://localhost:8000/health" "http"
check_service "User Service" "http://localhost:8010/health" "http"
check_service "Audit Service" "http://localhost:8011/health" "http"
check_service "Event Gateway" "http://localhost:8003/health" "http"
check_service "GraphQL" "http://localhost:8006/graphql" "http"

echo ""
print_status "$CYAN" "🔌 Port Status:"
check_port_status 5432 "PostgreSQL"
check_port_status 6379 "Redis"
check_port_status 4222 "NATS"
check_port_status 6363 "TerminusDB"
check_port_status 8000 "OMS"
check_port_status 8010 "User Service"
check_port_status 8011 "Audit Service"

echo ""
print_status "$CYAN" "💾 Resource Usage:"
if command -v docker > /dev/null 2>&1 && docker ps > /dev/null 2>&1; then
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep -E "arrakis|CONTAINER" || echo "No containers running"
fi

echo ""
print_status "$CYAN" "📊 Quick Metrics:"
# Check Redis
if redis-cli ping > /dev/null 2>&1; then
    keys=$(redis-cli dbsize | awk '{print $2}')
    echo "   Redis Keys: $keys"
fi

# Check recent logs
if [ -d logs ] && [ "$(ls -A logs 2>/dev/null)" ]; then
    echo ""
    print_status "$CYAN" "📋 Recent Log Activity:"
    for log in logs/*.log; do
        if [ -f "$log" ]; then
            service=$(basename "$log" .log)
            last_line=$(tail -1 "$log" 2>/dev/null | cut -c1-60)
            echo "   $service: $last_line..."
        fi
    done
fi

echo ""
print_status "$CYAN" "🔗 Service Endpoints:"
echo "   API Documentation:  http://localhost:8000/docs"
echo "   GraphQL Playground: http://localhost:8006/graphql"
echo "   Grafana Dashboard:  http://localhost:3000"
echo "   Jaeger UI:         http://localhost:16686"
echo "   Prometheus:        http://localhost:9090"

echo ""
print_status "$BLUE" "💡 Quick Commands:"
echo "   View logs:     docker-compose logs -f [service]"
echo "   Restart:       ./start.sh --mode=docker"
echo "   Run tests:     ./test.sh --type=smoke"
echo "   Stop all:      ./stop.sh"