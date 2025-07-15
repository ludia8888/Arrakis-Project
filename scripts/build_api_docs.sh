#!/bin/bash
set -e

# Arrakis Platform API Documentation Builder
# This script extracts OpenAPI specs and builds comprehensive documentation

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCS_DIR="$PROJECT_ROOT/docs"
OPENAPI_DIR="$DOCS_DIR/openapi"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
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

# Function to check if command exists
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is not installed. Please install it first."
        return 1
    fi
    return 0
}

# Function to check if services are running
check_services() {
    log_info "Checking if Arrakis services are running..."

    local services=(
        "localhost:8000"  # OMS
        "localhost:8010"  # User Service
        "localhost:8011"  # Audit Service
        "localhost:8080"  # Data Kernel
        "localhost:8001"  # Embedding Service
        "localhost:8002"  # Scheduler Service
        "localhost:8003"  # Event Gateway
    )

    local running_services=0
    for service in "${services[@]}"; do
        if curl -s --connect-timeout 5 "http://$service/health" > /dev/null 2>&1; then
            log_success "✓ Service at $service is running"
            ((running_services++))
        else
            log_warning "✗ Service at $service is not responding"
        fi
    done

    log_info "Found $running_services running services out of ${#services[@]}"
    return 0
}

# Function to extract OpenAPI specs
extract_openapi_specs() {
    log_info "Extracting OpenAPI specifications..."

    # Create output directory
    mkdir -p "$OPENAPI_DIR"

    # Run the extraction script
    if python3 "$SCRIPT_DIR/extract_openapi_specs.py" --output-dir "$OPENAPI_DIR"; then
        log_success "OpenAPI specifications extracted successfully"
    else
        log_warning "Some OpenAPI specifications could not be extracted (services may not be running)"
    fi
}

# Function to validate OpenAPI specs
validate_specs() {
    log_info "Validating OpenAPI specifications..."

    if check_command "redocly"; then
        cd "$PROJECT_ROOT"

        # Lint all API specifications
        for spec_file in "$OPENAPI_DIR"/*.openapi.yaml; do
            if [ -f "$spec_file" ]; then
                local service_name=$(basename "$spec_file" .openapi.yaml)
                log_info "Validating $service_name..."

                if redocly lint "$spec_file"; then
                    log_success "✓ $service_name OpenAPI spec is valid"
                else
                    log_warning "✗ $service_name OpenAPI spec has validation issues"
                fi
            fi
        done
    else
        log_warning "Redocly CLI not found. Skipping validation."
    fi
}

# Function to build Redocly documentation
build_redocly_docs() {
    log_info "Building Redocly documentation..."

    if check_command "redocly"; then
        cd "$PROJECT_ROOT"

        # Build multi-API documentation
        local output_dir="$DOCS_DIR/build"
        mkdir -p "$output_dir"

        # Build each API separately
        for spec_file in "$OPENAPI_DIR"/*.openapi.yaml; do
            if [ -f "$spec_file" ]; then
                local service_name=$(basename "$spec_file" .openapi.yaml)
                log_info "Building documentation for $service_name..."

                redocly build-docs "$spec_file" \
                    --output "$output_dir/$service_name.html" \
                    --theme.openapi.theme custom \
                    --theme.openapi.hideDownloadButton false

                if [ $? -eq 0 ]; then
                    log_success "✓ Built documentation for $service_name"
                else
                    log_warning "✗ Failed to build documentation for $service_name"
                fi
            fi
        done

        # Create index page
        create_index_page "$output_dir"

        log_success "Redocly documentation built in $output_dir"
    else
        log_warning "Redocly CLI not found. Install with: npm install -g @redocly/cli"
    fi
}

# Function to create documentation index page
create_index_page() {
    local output_dir="$1"
    local index_file="$output_dir/index.html"

    log_info "Creating documentation index page..."

    cat > "$index_file" << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Arrakis Platform API Documentation</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 50px;
        }
        .header h1 {
            font-size: 3rem;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .header p {
            font-size: 1.2rem;
            opacity: 0.9;
        }
        .services-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
            margin-top: 40px;
        }
        .service-card {
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            border: 1px solid rgba(255,255,255,0.2);
        }
        .service-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 40px rgba(0,0,0,0.15);
        }
        .service-card h3 {
            color: #333;
            margin-bottom: 15px;
            font-size: 1.4rem;
        }
        .service-card p {
            color: #666;
            margin-bottom: 20px;
            line-height: 1.6;
        }
        .service-card a {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-weight: 500;
            transition: opacity 0.3s ease;
        }
        .service-card a:hover {
            opacity: 0.9;
        }
        .footer {
            text-align: center;
            color: white;
            margin-top: 60px;
            opacity: 0.8;
        }
        .platform-info {
            background: rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 40px;
            color: white;
            backdrop-filter: blur(10px);
        }
        .platform-info h2 {
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏜️ Arrakis Platform</h1>
            <p>Comprehensive API Documentation</p>
        </div>

        <div class="platform-info">
            <h2>About Arrakis</h2>
            <p>
                Arrakis is an enterprise-grade microservices platform for ontology management,
                data processing, and knowledge graph operations. This documentation provides
                comprehensive API references for all platform services.
            </p>
        </div>

        <div class="services-grid">
            <div class="service-card">
                <h3>🎯 Ontology Management Service</h3>
                <p>Core service for managing ontologies, schemas, and data models. Includes REST, GraphQL, and WebSocket APIs.</p>
                <a href="ontology-management-service.html">View Documentation</a>
            </div>

            <div class="service-card">
                <h3>👤 User Service</h3>
                <p>Authentication, authorization, and user profile management with JWT-based security.</p>
                <a href="user-service.html">View Documentation</a>
            </div>

            <div class="service-card">
                <h3>📋 Audit Service</h3>
                <p>Comprehensive audit logging, compliance tracking, and security event monitoring.</p>
                <a href="audit-service.html">View Documentation</a>
            </div>

            <div class="service-card">
                <h3>⚡ Data Kernel Service</h3>
                <p>High-performance data processing core with TerminusDB graph database integration.</p>
                <a href="data-kernel-service.html">View Documentation</a>
            </div>

            <div class="service-card">
                <h3>🧠 Embedding Service</h3>
                <p>Machine learning service for vector embeddings, similarity search, and NLP operations.</p>
                <a href="embedding-service.html">View Documentation</a>
            </div>

            <div class="service-card">
                <h3>⏰ Scheduler Service</h3>
                <p>Distributed job scheduling, cron management, and workflow orchestration.</p>
                <a href="scheduler-service.html">View Documentation</a>
            </div>

            <div class="service-card">
                <h3>🔄 Event Gateway</h3>
                <p>Event streaming, webhook management, and pub/sub messaging with NATS integration.</p>
                <a href="event-gateway.html">View Documentation</a>
            </div>
        </div>

        <div class="footer">
            <p>Generated automatically from OpenAPI specifications</p>
            <p>© 2024 Arrakis Platform. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
EOF

    log_success "Created documentation index page: $index_file"
}

# Function to upload to SwaggerHub
upload_to_swaggerhub() {
    log_info "Uploading APIs to SwaggerHub..."

    if [ -z "$SWAGGERHUB_API_KEY" ]; then
        log_warning "SWAGGERHUB_API_KEY not set. Skipping SwaggerHub upload."
        log_info "To upload to SwaggerHub, set SWAGGERHUB_API_KEY and run:"
        log_info "  export SWAGGERHUB_API_KEY=your_api_key"
        log_info "  $SCRIPT_DIR/upload_to_swaggerhub.sh"
        return 0
    fi

    # Check if upload script exists
    local upload_script="$DOCS_DIR/upload_to_swaggerhub.sh"
    if [ -f "$upload_script" ]; then
        chmod +x "$upload_script"
        "$upload_script"
    else
        log_warning "SwaggerHub upload script not found. Run extract_openapi_specs.py first."
    fi
}

# Function to generate additional documentation assets
generate_additional_assets() {
    log_info "Generating additional documentation assets..."

    # Create a comprehensive README for the docs
    cat > "$DOCS_DIR/README.md" << 'EOF'
# Arrakis Platform API Documentation

This directory contains comprehensive API documentation for the Arrakis platform.

## 📁 Directory Structure

```
docs/
├── openapi/                    # OpenAPI specifications (JSON & YAML)
├── build/                      # Generated documentation files
├── redocly.yaml               # Redocly configuration
├── upload_to_swaggerhub.sh    # SwaggerHub upload script
└── README.md                  # This file
```

## 🚀 Quick Start

### Prerequisites

```bash
# Install required tools
npm install -g @redocly/cli
pip install httpx pyyaml
```

### Generate Documentation

```bash
# Extract OpenAPI specs from running services
./scripts/extract_openapi_specs.py

# Build complete documentation site
./scripts/build_api_docs.sh

# Validate all specifications
redocly lint docs/openapi/*.openapi.yaml
```

### View Documentation

Open `docs/build/index.html` in your browser to access the documentation portal.

## 📚 Available APIs

- **Ontology Management Service** - Core ontology and schema management
- **User Service** - Authentication and user management
- **Audit Service** - Audit logging and compliance
- **Data Kernel Service** - High-performance data processing
- **Embedding Service** - ML embeddings and similarity search
- **Scheduler Service** - Job scheduling and workflow management
- **Event Gateway** - Event streaming and webhook management

## 🔧 Integration

### SwaggerHub

Set your API key and upload:

```bash
export SWAGGERHUB_API_KEY="your_api_key"
./docs/upload_to_swaggerhub.sh
```

### Redocly

The documentation is optimized for Redocly with:
- Multi-API organization
- Custom theming
- Validation rules
- Code samples

## 🔄 Automation

The documentation is automatically updated through:
- CI/CD pipelines
- Pre-commit hooks
- Service deployment workflows

## 📝 Contributing

When adding new endpoints:
1. Follow OpenAPI 3.0 specifications
2. Include comprehensive descriptions
3. Add examples and schemas
4. Update integration tests

## 🎯 Best Practices

- Use consistent naming conventions
- Include security schemes
- Provide comprehensive examples
- Document error responses
- Tag operations appropriately
EOF

    log_success "Generated documentation README"
}

# Main execution
main() {
    log_info "🏜️  Starting Arrakis Platform API Documentation Build"
    echo "=================================================="

    # Create docs directory structure
    mkdir -p "$DOCS_DIR"
    mkdir -p "$OPENAPI_DIR"
    mkdir -p "$DOCS_DIR/build"

    # Check if services are running (optional)
    check_services

    # Extract OpenAPI specifications
    extract_openapi_specs

    # Validate specifications
    validate_specs

    # Build documentation
    build_redocly_docs

    # Generate additional assets
    generate_additional_assets

    # Upload to SwaggerHub (if configured)
    # upload_to_swaggerhub

    echo "=================================================="
    log_success "🎉 API Documentation build completed!"
    log_info "📖 Documentation available at: $DOCS_DIR/build/index.html"
    log_info "🔍 OpenAPI specs available in: $OPENAPI_DIR"

    # Show next steps
    echo ""
    log_info "Next steps:"
    log_info "  1. Open $DOCS_DIR/build/index.html in your browser"
    log_info "  2. Review generated OpenAPI specifications"
    log_info "  3. Configure SwaggerHub integration (optional)"
    log_info "  4. Set up CI/CD automation"
}

# Parse command line arguments
SKIP_VALIDATION=false
SKIP_BUILD=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-validation)
            SKIP_VALIDATION=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --skip-validation    Skip OpenAPI validation"
            echo "  --skip-build        Skip documentation build"
            echo "  --help, -h          Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main function
main
