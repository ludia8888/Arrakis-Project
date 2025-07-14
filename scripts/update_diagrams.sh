#!/bin/bash
set -e

# Quick script to update architecture diagrams locally
# This script can be used as a pre-commit hook or for manual updates

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

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

# Check if Python is available
check_python() {
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not installed"
        exit 1
    fi
    
    # Check for required Python packages
    if ! python3 -c "import yaml" &> /dev/null; then
        log_warning "PyYAML not installed. Installing..."
        pip3 install pyyaml
    fi
}

# Generate diagrams
generate_diagrams() {
    log_info "🎨 Generating architecture diagrams..."
    
    cd "$PROJECT_ROOT"
    
    # Create output directory
    mkdir -p docs/diagrams
    
    # Run the diagram generator
    if python3 scripts/generate_architecture_diagrams.py \
        --project-root . \
        --output-dir docs/diagrams; then
        log_success "✅ Architecture diagrams generated successfully"
    else
        log_error "❌ Failed to generate architecture diagrams"
        exit 1
    fi
}

# Validate generated diagrams
validate_diagrams() {
    log_info "🔍 Validating generated diagrams..."
    
    # Check if all expected files exist
    expected_files=(
        "docs/diagrams/README.md"
        "docs/diagrams/system-overview.md"
        "docs/diagrams/service-dependencies.md"
        "docs/diagrams/data-flow.md"
        "docs/diagrams/technology-stack.md"
        "docs/diagrams/metadata.json"
    )
    
    all_files_exist=true
    for file in "${expected_files[@]}"; do
        if [ ! -f "$file" ]; then
            log_error "❌ Missing file: $file"
            all_files_exist=false
        else
            log_success "✅ Found: $file"
        fi
    done
    
    if [ "$all_files_exist" = false ]; then
        log_error "❌ Some expected files are missing"
        exit 1
    fi
    
    # Check for valid Mermaid syntax
    mermaid_found=false
    for md_file in docs/diagrams/*.md; do
        if [ -f "$md_file" ] && grep -q '```mermaid' "$md_file"; then
            mermaid_found=true
            log_success "✅ Mermaid diagram found in $(basename "$md_file")"
        fi
    done
    
    if [ "$mermaid_found" = false ]; then
        log_warning "⚠️  No Mermaid diagrams found in generated files"
    fi
    
    log_success "✅ Diagram validation completed"
}

# Show diagram summary
show_summary() {
    log_info "📊 Diagram Summary:"
    
    if [ -f "docs/diagrams/metadata.json" ]; then
        services_count=$(python3 -c "
import json
try:
    with open('docs/diagrams/metadata.json', 'r') as f:
        data = json.load(f)
        print(data.get('services_count', 0))
except:
    print('0')
")
        
        dependencies_count=$(python3 -c "
import json
try:
    with open('docs/diagrams/metadata.json', 'r') as f:
        data = json.load(f)
        print(data.get('dependencies_count', 0))
except:
    print('0')
")
        
        echo "  📈 Services analyzed: $services_count"
        echo "  🔗 Dependencies mapped: $dependencies_count"
    fi
    
    echo "  📋 Diagrams generated: 4"
    echo "  📁 Output directory: docs/diagrams/"
    
    log_info "🔗 Available diagrams:"
    for md_file in docs/diagrams/*.md; do
        if [ -f "$md_file" ] && [ "$(basename "$md_file")" != "README.md" ]; then
            filename=$(basename "$md_file" .md)
            title=$(echo "$filename" | tr '-' ' ' | sed 's/\b\w/\U&/g')
            echo "  - $title: docs/diagrams/$(basename "$md_file")"
        fi
    done
}

# Check for changes
check_changes() {
    if command -v git &> /dev/null && git rev-parse --git-dir > /dev/null 2>&1; then
        if git diff --quiet docs/diagrams/ 2>/dev/null; then
            log_info "ℹ️  No changes detected in diagrams"
        else
            log_warning "📝 Changes detected in diagrams:"
            git diff --name-only docs/diagrams/ 2>/dev/null | while read -r file; do
                echo "  - $file"
            done
            
            log_info "💡 To commit changes, run:"
            echo "  git add docs/diagrams/"
            echo "  git commit -m \"📊 Update architecture diagrams\""
        fi
    fi
}

# Main function
main() {
    log_info "🏜️  Arrakis Architecture Diagram Updater"
    echo "=================================="
    
    # Check prerequisites
    check_python
    
    # Generate diagrams
    generate_diagrams
    
    # Validate output
    validate_diagrams
    
    # Show summary
    show_summary
    
    # Check for Git changes
    check_changes
    
    echo "=================================="
    log_success "🎉 Diagram update completed successfully!"
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "Arrakis Architecture Diagram Updater"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h          Show this help message"
        echo "  --validate-only     Only validate existing diagrams"
        echo "  --summary-only      Only show diagram summary"
        echo ""
        echo "Examples:"
        echo "  $0                  Generate and validate diagrams"
        echo "  $0 --validate-only  Validate existing diagrams"
        echo "  $0 --summary-only   Show summary of existing diagrams"
        exit 0
        ;;
    --validate-only)
        check_python
        validate_diagrams
        exit 0
        ;;
    --summary-only)
        show_summary
        exit 0
        ;;
esac

# Run main function
main "$@"