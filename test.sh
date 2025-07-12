#!/bin/bash
# Unified Arrakis Project Test Script
# Consolidates all test scripts into one

set -e

# Activate virtual environment if it exists
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
elif [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
TEST_TYPE="smoke"
VERBOSE=false
REPORT=false
SERVICE=""

# Function to display usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --type=TYPE     Test type to run:"
    echo "                  - smoke: Quick health checks (default)"
    echo "                  - integration: Full integration tests"
    echo "                  - performance: Performance benchmarks"
    echo "                  - security: Security scans"
    echo "                  - all: Run all tests"
    echo "  --service=NAME  Test specific service only"
    echo "  --verbose       Enable verbose output"
    echo "  --report        Generate HTML report"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                           # Run smoke tests"
    echo "  $0 --type=integration        # Run integration tests"
    echo "  $0 --type=all --report       # Run all tests with report"
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --type=*)
            TEST_TYPE="${1#*=}"
            shift
            ;;
        --service=*)
            SERVICE="${1#*=}"
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --report)
            REPORT=true
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

# Function to run command with optional verbose output
run_test() {
    local test_name=$1
    local command=$2
    
    print_status "$YELLOW" "🧪 Running: $test_name"
    
    if [ "$VERBOSE" = true ]; then
        eval "$command"
    else
        if output=$(eval "$command" 2>&1); then
            print_status "$GREEN" "✅ $test_name passed"
            return 0
        else
            print_status "$RED" "❌ $test_name failed"
            echo "$output" | tail -20
            return 1
        fi
    fi
}

# Initialize test results
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
TEST_RESULTS=()

# Function to record test result
record_result() {
    local test_name=$1
    local status=$2
    local duration=$3
    
    TESTS_RUN=$((TESTS_RUN + 1))
    if [ "$status" = "passed" ]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    
    TEST_RESULTS+=("$test_name|$status|$duration")
}

# Smoke tests - Quick health checks
run_smoke_tests() {
    print_status "$BLUE" "🔍 Running smoke tests..."
    
    # Test service health endpoints
    local services=("localhost:8000" "localhost:8010" "localhost:8011")
    local names=("OMS" "User Service" "Audit Service")
    
    for i in "${!services[@]}"; do
        if [ -n "$SERVICE" ] && [ "${names[$i]}" != "$SERVICE" ]; then
            continue
        fi
        
        start_time=$(date +%s)
        if curl -f -s "http://${services[$i]}/health" > /dev/null; then
            end_time=$(date +%s)
            duration=$((end_time - start_time))
            record_result "${names[$i]} Health Check" "passed" "${duration}s"
            print_status "$GREEN" "✅ ${names[$i]} is healthy"
        else
            record_result "${names[$i]} Health Check" "failed" "N/A"
            print_status "$RED" "❌ ${names[$i]} is not responding"
        fi
    done
    
    # Test Redis
    if redis-cli ping > /dev/null 2>&1; then
        record_result "Redis Connection" "passed" "0s"
        print_status "$GREEN" "✅ Redis is running"
    else
        record_result "Redis Connection" "failed" "N/A"
        print_status "$RED" "❌ Redis is not running"
    fi
}

# Integration tests
run_integration_tests() {
    print_status "$BLUE" "🔗 Running integration tests..."
    
    # Create test user with unique email
    TEST_EMAIL="test_$(date +%s)@example.com"
    run_test "User Registration" "curl -X POST http://localhost:8010/auth/register \
        -H 'Content-Type: application/json' \
        -d '{\"email\":\"${TEST_EMAIL}\",\"password\":\"Test123!\",\"name\":\"Test User\"}'"
    
    # Login
    TOKEN=$(curl -s -X POST http://localhost:8010/auth/login \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=${TEST_EMAIL}&password=Test123!" | jq -r '.access_token' 2>/dev/null || echo "")
    
    if [ -n "$TOKEN" ] && [ "$TOKEN" != "null" ]; then
        record_result "User Login" "passed" "1s"
        print_status "$GREEN" "✅ Login successful"
        
        # Test authenticated endpoints
        run_test "Create Schema" "curl -X POST http://localhost:8000/api/v1/schemas \
            -H 'Authorization: Bearer $TOKEN' \
            -H 'Content-Type: application/json' \
            -d '{\"name\":\"TestSchema\",\"properties\":{\"field1\":\"string\"}}'"
        
        run_test "List Schemas" "curl -X GET http://localhost:8000/api/v1/schemas \
            -H 'Authorization: Bearer $TOKEN'"
    else
        record_result "User Login" "failed" "N/A"
        print_status "$RED" "❌ Login failed"
    fi
}

# Performance tests
run_performance_tests() {
    print_status "$BLUE" "⚡ Running performance tests..."
    
    # Simple performance test without external tools
    print_status "$YELLOW" "🏃 Running simple load test..."
    
    # Test OMS performance with curl in a loop
    start_time=$(date +%s)
    success_count=0
    for i in {1..50}; do
        if curl -s -f http://localhost:8000/health > /dev/null; then
            ((success_count++))
        fi
    done
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    
    if [ $success_count -eq 50 ]; then
        record_result "OMS Load Test (50 requests)" "passed" "${duration}s"
        print_status "$GREEN" "✅ All 50 requests succeeded in ${duration}s"
    else
        record_result "OMS Load Test (50 requests)" "failed" "${duration}s"
        print_status "$RED" "❌ Only $success_count/50 requests succeeded"
    fi
    
    # Test response times
    local response_time=$(curl -o /dev/null -s -w '%{time_total}' http://localhost:8000/health)
    if (( $(echo "$response_time < 0.1" | bc -l) )); then
        record_result "OMS Response Time" "passed" "${response_time}s"
        print_status "$GREEN" "✅ OMS response time: ${response_time}s (< 100ms)"
    else
        record_result "OMS Response Time" "failed" "${response_time}s"
        print_status "$RED" "❌ OMS response time: ${response_time}s (> 100ms)"
    fi
}

# Security tests
run_security_tests() {
    print_status "$BLUE" "🔒 Running security tests..."
    
    # Test for common security headers
    run_test "Security Headers Check" \
        "curl -I http://localhost:8000/health | grep -E 'X-Content-Type-Options|X-Frame-Options'"
    
    # Test authentication required
    local status=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/v1/schemas)
    if [ "$status" = "401" ] || [ "$status" = "403" ]; then
        record_result "Auth Required Check" "passed" "0s"
        print_status "$GREEN" "✅ Authentication properly required"
    else
        record_result "Auth Required Check" "failed" "0s"
        print_status "$RED" "❌ Endpoint accessible without auth (status: $status)"
    fi
}

# Generate HTML report
generate_report() {
    local report_file="test_report_$(date +%Y%m%d_%H%M%S).html"
    
    cat > "$report_file" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Arrakis Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; }
        .summary { background: #f0f0f0; padding: 20px; border-radius: 5px; margin: 20px 0; }
        .passed { color: green; }
        .failed { color: red; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #333; color: white; }
        tr:nth-child(even) { background: #f9f9f9; }
    </style>
</head>
<body>
    <h1>Arrakis Project Test Report</h1>
    <div class="summary">
        <h2>Summary</h2>
        <p>Generated: $(date)</p>
        <p>Test Type: $TEST_TYPE</p>
        <p>Total Tests: $TESTS_RUN</p>
        <p class="passed">Passed: $TESTS_PASSED</p>
        <p class="failed">Failed: $TESTS_FAILED</p>
        <p>Success Rate: $(( TESTS_PASSED * 100 / TESTS_RUN ))%</p>
    </div>
    <h2>Test Results</h2>
    <table>
        <tr>
            <th>Test Name</th>
            <th>Status</th>
            <th>Duration</th>
        </tr>
EOF
    
    for result in "${TEST_RESULTS[@]}"; do
        IFS='|' read -r name status duration <<< "$result"
        echo "<tr><td>$name</td><td class='$status'>$status</td><td>$duration</td></tr>" >> "$report_file"
    done
    
    echo "</table></body></html>" >> "$report_file"
    
    print_status "$GREEN" "📄 Test report generated: $report_file"
}

# Main execution
print_status "$BLUE" "🧪 Arrakis Project Test Suite"
print_status "$BLUE" "Test Type: $TEST_TYPE"
echo ""

# Check if at least one service is running
service_running=false
for port in 8000 8010 8011; do
    if curl -f -s http://localhost:$port/health > /dev/null 2>&1; then
        service_running=true
        break
    fi
done

if [ "$service_running" = false ]; then
    print_status "$RED" "❌ No services appear to be running!"
    print_status "$YELLOW" "💡 Start services first: ./start.sh"
    exit 1
fi

# Run tests based on type
case $TEST_TYPE in
    smoke)
        run_smoke_tests
        ;;
    integration)
        run_smoke_tests
        run_integration_tests
        ;;
    performance)
        run_smoke_tests
        run_performance_tests
        ;;
    security)
        run_smoke_tests
        run_security_tests
        ;;
    all)
        run_smoke_tests
        run_integration_tests
        run_performance_tests
        run_security_tests
        ;;
    *)
        print_status "$RED" "❌ Invalid test type: $TEST_TYPE"
        usage
        ;;
esac

# Generate report if requested
if [ "$REPORT" = true ]; then
    generate_report
fi

# Print summary
echo ""
print_status "$BLUE" "📊 Test Summary:"
echo "   Total Tests: $TESTS_RUN"
echo "   Passed: $TESTS_PASSED"
echo "   Failed: $TESTS_FAILED"

if [ $TESTS_FAILED -eq 0 ]; then
    print_status "$GREEN" "✅ All tests passed!"
    exit 0
else
    print_status "$RED" "❌ Some tests failed!"
    exit 1
fi