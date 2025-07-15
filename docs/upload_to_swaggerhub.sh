#!/bin/bash
# SwaggerHub Upload Script for Arrakis Platform APIs

set -e

# Configuration
SWAGGERHUB_API_KEY="${SWAGGERHUB_API_KEY}"
SWAGGERHUB_OWNER="${SWAGGERHUB_OWNER:-arrakis-platform}"
API_VERSION="${API_VERSION:-2.0.0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENAPI_DIR="$SCRIPT_DIR/openapi"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    if [ -z "$SWAGGERHUB_API_KEY" ]; then
        log_error "SWAGGERHUB_API_KEY environment variable not set"
        log_info "Get your API key from: https://app.swaggerhub.com/settings/apiKey"
        log_info "Then run: export SWAGGERHUB_API_KEY=your_api_key"
        exit 1
    fi

    if ! command -v curl &> /dev/null; then
        log_error "curl is required but not installed"
        exit 1
    fi

    if ! command -v jq &> /dev/null; then
        log_warning "jq not found. Install for better JSON processing"
        log_info "On Ubuntu/Debian: sudo apt-get install jq"
        log_info "On macOS: brew install jq"
    fi
}

# Function to upload a single API to SwaggerHub
upload_api() {
    local spec_file="$1"
    local service_name=$(basename "$spec_file" .openapi.json)

    log_info "Uploading $service_name to SwaggerHub..."

    # Read the spec and extract basic info
    local api_title=$(jq -r '.info.title // "Unknown"' "$spec_file" 2>/dev/null || echo "Unknown")
    local api_version=$(jq -r '.info.version // "1.0.0"' "$spec_file" 2>/dev/null || echo "1.0.0")

    log_info "  Title: $api_title"
    log_info "  Version: $api_version"
    log_info "  File: $spec_file"

    # SwaggerHub API endpoint
    local api_endpoint="https://api.swaggerhub.com/apis/${SWAGGERHUB_OWNER}/${service_name}"

    # First, try to create the API
    local create_response=$(curl -s -w "%{http_code}" -o /tmp/swaggerhub_response.json \
        -X POST \
        "$api_endpoint" \
        -H "Authorization: $SWAGGERHUB_API_KEY" \
        -H "Content-Type: application/json" \
        -d @"$spec_file")

    local http_code="${create_response: -3}"

    if [ "$http_code" -eq "201" ]; then
        log_success "✅ Created new API: $service_name"
    elif [ "$http_code" -eq "409" ]; then
        # API already exists, try to update it
        log_info "API already exists, updating..."

        local update_response=$(curl -s -w "%{http_code}" -o /tmp/swaggerhub_response.json \
            -X PUT \
            "${api_endpoint}/${api_version}" \
            -H "Authorization: $SWAGGERHUB_API_KEY" \
            -H "Content-Type: application/json" \
            -d @"$spec_file")

        local update_http_code="${update_response: -3}"

        if [ "$update_http_code" -eq "200" ]; then
            log_success "✅ Updated existing API: $service_name"
        else
            log_error "❌ Failed to update API: $service_name (HTTP $update_http_code)"
            if command -v jq &> /dev/null && [ -f /tmp/swaggerhub_response.json ]; then
                jq '.' /tmp/swaggerhub_response.json
            fi
            return 1
        fi
    else
        log_error "❌ Failed to create API: $service_name (HTTP $http_code)"
        if command -v jq &> /dev/null && [ -f /tmp/swaggerhub_response.json ]; then
            jq '.' /tmp/swaggerhub_response.json
        fi
        return 1
    fi

    # Set API settings (public, auto-mock, etc.)
    log_info "Configuring API settings for $service_name..."

    local settings_response=$(curl -s -w "%{http_code}" -o /tmp/swaggerhub_settings.json \
        -X PUT \
        "${api_endpoint}/${api_version}/settings" \
        -H "Authorization: $SWAGGERHUB_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
            "private": false,
            "versioningScheme": "http://semver.org/",
            "lifecycle": {
                "published": {
                    "version": "'$api_version'"
                }
            },
            "mock": true,
            "autodoc": true
        }')

    local settings_http_code="${settings_response: -3}"

    if [ "$settings_http_code" -eq "200" ]; then
        log_success "✅ Configured settings for $service_name"
    else
        log_warning "⚠️  Could not configure settings for $service_name (HTTP $settings_http_code)"
    fi

    # Generate SwaggerHub URL
    local swaggerhub_url="https://app.swaggerhub.com/apis/${SWAGGERHUB_OWNER}/${service_name}/${api_version}"
    log_info "🔗 SwaggerHub URL: $swaggerhub_url"

    return 0
}

# Function to create API collection in SwaggerHub
create_api_collection() {
    log_info "Creating Arrakis Platform API collection..."

    local collection_data='{
        "name": "arrakis-platform-collection",
        "title": "Arrakis Platform APIs",
        "description": "Complete collection of Arrakis platform microservices APIs",
        "apis": []
    }'

    # Add each API to the collection
    for spec_file in "$OPENAPI_DIR"/*.openapi.json; do
        if [ -f "$spec_file" ]; then
            local service_name=$(basename "$spec_file" .openapi.json)
            local api_version=$(jq -r '.info.version // "1.0.0"' "$spec_file" 2>/dev/null || echo "1.0.0")

            collection_data=$(echo "$collection_data" | jq \
                --arg name "$service_name" \
                --arg version "$api_version" \
                '.apis += [{"name": $name, "version": $version}]')
        fi
    done

    # Create the collection
    local collection_response=$(curl -s -w "%{http_code}" -o /tmp/swaggerhub_collection.json \
        -X POST \
        "https://api.swaggerhub.com/apis/${SWAGGERHUB_OWNER}/collections" \
        -H "Authorization: $SWAGGERHUB_API_KEY" \
        -H "Content-Type: application/json" \
        -d "$collection_data")

    local http_code="${collection_response: -3}"

    if [ "$http_code" -eq "201" ] || [ "$http_code" -eq "200" ]; then
        log_success "✅ Created/updated API collection"
    else
        log_warning "⚠️  Could not create API collection (HTTP $http_code)"
    fi
}

# Main execution
main() {
    log_info "🚀 Starting SwaggerHub upload for Arrakis Platform APIs"
    echo "=========================================================="

    # Check prerequisites
    check_prerequisites

    # Check if OpenAPI directory exists
    if [ ! -d "$OPENAPI_DIR" ]; then
        log_error "OpenAPI directory not found: $OPENAPI_DIR"
        log_info "Run the OpenAPI extraction script first:"
        log_info "  python scripts/extract_openapi_specs.py"
        exit 1
    fi

    # Count available specifications
    local spec_count=$(find "$OPENAPI_DIR" -name "*.openapi.json" | wc -l)

    if [ "$spec_count" -eq 0 ]; then
        log_error "No OpenAPI specifications found in $OPENAPI_DIR"
        log_info "Run the OpenAPI extraction script first:"
        log_info "  python scripts/extract_openapi_specs.py"
        exit 1
    fi

    log_info "Found $spec_count OpenAPI specifications to upload"
    log_info "SwaggerHub Owner: $SWAGGERHUB_OWNER"
    echo ""

    # Upload each API
    local uploaded_count=0
    local failed_count=0

    for spec_file in "$OPENAPI_DIR"/*.openapi.json; do
        if [ -f "$spec_file" ]; then
            if upload_api "$spec_file"; then
                ((uploaded_count++))
            else
                ((failed_count++))
            fi
            echo ""
        fi
    done

    # Create API collection
    if [ "$uploaded_count" -gt 0 ]; then
        create_api_collection
    fi

    echo "=========================================================="
    log_info "📊 Upload Summary:"
    log_info "  Total APIs: $spec_count"
    log_success "  Uploaded: $uploaded_count"

    if [ "$failed_count" -gt 0 ]; then
        log_error "  Failed: $failed_count"
    fi

    if [ "$uploaded_count" -gt 0 ]; then
        echo ""
        log_success "🎉 APIs successfully uploaded to SwaggerHub!"
        log_info "📱 View your APIs at: https://app.swaggerhub.com/organizations/${SWAGGERHUB_OWNER}"
        log_info "🔗 API Collection: https://app.swaggerhub.com/apis/${SWAGGERHUB_OWNER}/arrakis-platform-collection"
    fi

    # Cleanup
    rm -f /tmp/swaggerhub_*.json

    exit $failed_count
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "SwaggerHub Upload Script for Arrakis Platform"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Environment Variables:"
        echo "  SWAGGERHUB_API_KEY    SwaggerHub API key (required)"
        echo "  SWAGGERHUB_OWNER      SwaggerHub organization name (default: arrakis-platform)"
        echo "  API_VERSION           API version to upload (default: 2.0.0)"
        echo ""
        echo "Options:"
        echo "  --help, -h            Show this help message"
        echo ""
        echo "Examples:"
        echo "  export SWAGGERHUB_API_KEY=your_api_key"
        echo "  $0"
        echo ""
        echo "  SWAGGERHUB_OWNER=my-org $0"
        exit 0
        ;;
esac

# Run main function
main "$@"
