#!/bin/bash

# Infrastructure Diagram Generation Script
# Automatically generates infrastructure diagrams from Terraform state
# Ultra production-ready with comprehensive error handling and validation

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TERRAFORM_DIR="${PROJECT_ROOT}/terraform"
DOCS_DIR="${PROJECT_ROOT}/docs"
DIAGRAMS_DIR="${DOCS_DIR}/diagrams"
LOG_FILE="${PROJECT_ROOT}/infrastructure-diagrams.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "${LOG_FILE}"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "${LOG_FILE}"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "${LOG_FILE}"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "${LOG_FILE}"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "${LOG_FILE}"
}

# Error handling
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        error "Script failed with exit code $exit_code"
        error "Check log file: ${LOG_FILE}"
    fi
    exit $exit_code
}

trap cleanup EXIT

# Check dependencies
check_dependencies() {
    info "Checking dependencies..."
    
    local deps=("terraform" "dot" "python3" "pip3")
    local missing_deps=()
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            missing_deps+=("$dep")
        fi
    done
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        error "Missing dependencies: ${missing_deps[*]}"
        error "Please install missing dependencies before running this script"
        return 1
    fi
    
    success "All dependencies found"
}

# Install inframap if not present
install_inframap() {
    info "Checking inframap installation..."
    
    if ! command -v inframap &> /dev/null; then
        info "Installing inframap..."
        
        local os_type=""
        case "$(uname -s)" in
            Darwin*) os_type="darwin" ;;
            Linux*)  os_type="linux" ;;
            *)       error "Unsupported OS: $(uname -s)"; return 1 ;;
        esac
        
        local arch_type=""
        case "$(uname -m)" in
            x86_64) arch_type="amd64" ;;
            arm64)  arch_type="arm64" ;;
            *)      error "Unsupported architecture: $(uname -m)"; return 1 ;;
        esac
        
        local inframap_version="v0.6.7"
        local download_url="https://github.com/cycloidio/inframap/releases/download/${inframap_version}/inframap-${os_type}-${arch_type}.tar.gz"
        
        info "Downloading inframap from: ${download_url}"
        
        local temp_dir=$(mktemp -d)
        pushd "${temp_dir}" > /dev/null
        
        curl -sL "${download_url}" | tar xz
        sudo mv inframap /usr/local/bin/
        
        popd > /dev/null
        rm -rf "${temp_dir}"
        
        success "Inframap installed successfully"
    else
        success "Inframap already installed"
    fi
    
    # Verify installation
    local version=$(inframap version 2>/dev/null || echo "unknown")
    info "Inframap version: ${version}"
}

# Install Python dependencies for additional diagram generation
install_python_deps() {
    info "Installing Python dependencies for diagram generation..."
    
    cat > "${SCRIPT_DIR}/requirements.txt" << 'EOF'
diagrams==0.23.3
boto3==1.34.34
graphviz==0.20.1
pydot==1.4.2
matplotlib==3.8.2
pillow==10.2.0
jinja2==3.1.3
pyyaml==6.0.1
requests==2.31.0
EOF
    
    python3 -m pip install --quiet -r "${SCRIPT_DIR}/requirements.txt"
    success "Python dependencies installed"
}

# Create directories
create_directories() {
    info "Creating directory structure..."
    
    local dirs=(
        "${DOCS_DIR}"
        "${DIAGRAMS_DIR}"
        "${DIAGRAMS_DIR}/infrastructure"
        "${DIAGRAMS_DIR}/architecture"
        "${DIAGRAMS_DIR}/network"
        "${DIAGRAMS_DIR}/security"
        "${DIAGRAMS_DIR}/monitoring"
        "${DIAGRAMS_DIR}/services"
    )
    
    for dir in "${dirs[@]}"; do
        mkdir -p "$dir"
    done
    
    success "Directory structure created"
}

# Generate Terraform state diagrams using inframap
generate_terraform_diagrams() {
    info "Generating Terraform infrastructure diagrams..."
    
    if [[ ! -d "${TERRAFORM_DIR}" ]]; then
        error "Terraform directory not found: ${TERRAFORM_DIR}"
        return 1
    fi
    
    pushd "${TERRAFORM_DIR}" > /dev/null
    
    # Initialize Terraform if needed
    if [[ ! -d ".terraform" ]]; then
        info "Initializing Terraform..."
        terraform init -backend=false
    fi
    
    # Generate plan for diagram
    info "Generating Terraform plan..."
    terraform plan -out=inframap.tfplan > /dev/null 2>&1 || {
        warn "Terraform plan failed, using configuration files instead"
    }
    
    # Generate infrastructure diagram from plan
    if [[ -f "inframap.tfplan" ]]; then
        info "Generating infrastructure diagram from Terraform plan..."
        inframap generate --tfplan inframap.tfplan --output "${DIAGRAMS_DIR}/infrastructure/terraform-plan.dot"
        
        # Convert to PNG and SVG
        dot -Tpng "${DIAGRAMS_DIR}/infrastructure/terraform-plan.dot" -o "${DIAGRAMS_DIR}/infrastructure/terraform-plan.png"
        dot -Tsvg "${DIAGRAMS_DIR}/infrastructure/terraform-plan.dot" -o "${DIAGRAMS_DIR}/infrastructure/terraform-plan.svg"
        
        # Cleanup
        rm -f inframap.tfplan
    fi
    
    # Generate diagrams from Terraform configuration
    info "Generating diagrams from Terraform configuration..."
    
    local modules=("networking" "eks" "rds" "elasticache" "nats" "monitoring" "security" "backup" "dns")
    
    for module in "${modules[@]}"; do
        if [[ -d "modules/${module}" ]]; then
            info "Processing module: ${module}"
            
            pushd "modules/${module}" > /dev/null
            
            # Generate module diagram
            inframap generate --raw --output "${DIAGRAMS_DIR}/infrastructure/${module}.dot" . || {
                warn "Failed to generate diagram for module: ${module}"
                continue
            }
            
            # Convert to multiple formats
            if [[ -f "${DIAGRAMS_DIR}/infrastructure/${module}.dot" ]]; then
                dot -Tpng "${DIAGRAMS_DIR}/infrastructure/${module}.dot" -o "${DIAGRAMS_DIR}/infrastructure/${module}.png"
                dot -Tsvg "${DIAGRAMS_DIR}/infrastructure/${module}.dot" -o "${DIAGRAMS_DIR}/infrastructure/${module}.svg"
                
                success "Generated diagram for module: ${module}"
            fi
            
            popd > /dev/null
        fi
    done
    
    popd > /dev/null
    
    success "Terraform diagrams generated"
}

# Generate custom architecture diagrams using Python
generate_architecture_diagrams() {
    info "Generating custom architecture diagrams..."
    
    cat > "${SCRIPT_DIR}/generate_architecture.py" << 'EOF'
#!/usr/bin/env python3
"""
Generate comprehensive architecture diagrams for Arrakis platform
Ultra production-ready with detailed infrastructure visualization
"""

import os
import sys
from pathlib import Path
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import EKS, EC2
from diagrams.aws.database import RDS, ElastiCache
from diagrams.aws.network import VPC, ALB, Route53, CloudFront
from diagrams.aws.security import IAM, KMS, GuardDuty, SecurityHub
from diagrams.aws.storage import S3
from diagrams.aws.management import CloudWatch, Backup
from diagrams.aws.integration import SNS, SQS
from diagrams.onprem.monitoring import Prometheus, Grafana
from diagrams.onprem.tracing import Jaeger
from diagrams.onprem.queue import Nats
from diagrams.generic.blank import Blank

def create_overall_architecture():
    """Create overall platform architecture diagram"""
    with Diagram("Arrakis Platform - Overall Architecture", 
                 filename="../docs/diagrams/architecture/overall-architecture",
                 show=False, direction="TB"):
        
        # External users and services
        users = Blank("Users")
        
        with Cluster("AWS Cloud"):
            # DNS and CDN
            with Cluster("Edge Services"):
                dns = Route53("Route53")
                cdn = CloudFront("CloudFront")
                alb = ALB("Application Load Balancer")
            
            # Network layer
            with Cluster("Networking"):
                vpc = VPC("VPC")
            
            # Compute layer
            with Cluster("Compute"):
                eks = EKS("EKS Cluster")
                
                with Cluster("Node Groups"):
                    general_nodes = EC2("General Workloads")
                    compute_nodes = EC2("Compute Intensive")
                    monitoring_nodes = EC2("Monitoring")
            
            # Data layer
            with Cluster("Data Services"):
                with Cluster("Databases"):
                    oms_db = RDS("OMS Database")
                    user_db = RDS("User Database")
                    audit_db = RDS("Audit Database")
                    scheduler_db = RDS("Scheduler Database")
                
                with Cluster("Cache"):
                    redis = ElastiCache("Redis Cluster")
                
                with Cluster("Message Broker"):
                    nats = Nats("NATS JetStream")
            
            # Security layer
            with Cluster("Security Services"):
                iam = IAM("IAM/IRSA")
                kms = KMS("KMS Encryption")
                guardduty = GuardDuty("GuardDuty")
                security_hub = SecurityHub("Security Hub")
            
            # Monitoring layer
            with Cluster("Monitoring & Observability"):
                prometheus = Prometheus("Prometheus")
                grafana = Grafana("Grafana")
                jaeger = Jaeger("Jaeger")
                cloudwatch = CloudWatch("CloudWatch")
            
            # Backup and recovery
            with Cluster("Backup & Recovery"):
                backup_service = Backup("AWS Backup")
                s3_backup = S3("Backup Storage")
        
        # Connections
        users >> dns >> alb >> eks
        eks >> [oms_db, user_db, audit_db, scheduler_db]
        eks >> redis
        eks >> nats
        eks >> [prometheus, cloudwatch]
        prometheus >> grafana
        eks >> jaeger
        backup_service >> [oms_db, user_db, audit_db, scheduler_db]
        backup_service >> s3_backup

def create_microservices_architecture():
    """Create microservices architecture diagram"""
    with Diagram("Arrakis Platform - Microservices Architecture",
                 filename="../docs/diagrams/architecture/microservices-architecture", 
                 show=False, direction="TB"):
        
        # API Gateway
        api_gateway = ALB("API Gateway")
        
        with Cluster("Microservices"):
            # Core services
            with Cluster("Core Services"):
                oms = Blank("Ontology Management\nService")
                user_svc = Blank("User Service")
                audit_svc = Blank("Audit Service")
            
            # Data services
            with Cluster("Data Services"):
                data_kernel = Blank("Data Kernel\nService")
                embedding_svc = Blank("Embedding\nService")
            
            # Infrastructure services
            with Cluster("Infrastructure Services"):
                scheduler_svc = Blank("Scheduler\nService")
                event_gateway = Blank("Event Gateway")
        
        # Data layer
        with Cluster("Data Layer"):
            databases = RDS("PostgreSQL\nDatabases")
            cache = ElastiCache("Redis Cache")
            message_broker = Nats("NATS JetStream")
        
        # External integrations
        with Cluster("External Systems"):
            external_apis = Blank("External APIs")
            webhooks = Blank("Webhooks")
        
        # Connections
        api_gateway >> [oms, user_svc, audit_svc, data_kernel, embedding_svc, scheduler_svc]
        [oms, user_svc, audit_svc, scheduler_svc] >> databases
        [oms, data_kernel, embedding_svc] >> cache
        [oms, scheduler_svc, event_gateway] >> message_broker
        event_gateway >> external_apis
        event_gateway >> webhooks

def create_security_architecture():
    """Create security architecture diagram"""
    with Diagram("Arrakis Platform - Security Architecture",
                 filename="../docs/diagrams/security/security-architecture",
                 show=False, direction="TB"):
        
        with Cluster("Security Layers"):
            # Network security
            with Cluster("Network Security"):
                vpc_security = VPC("VPC Security Groups")
                waf = Blank("AWS WAF")
                nacl = Blank("Network ACLs")
            
            # Identity and access
            with Cluster("Identity & Access Management"):
                iam_roles = IAM("IAM Roles")
                irsa = Blank("IRSA for Services")
                service_accounts = Blank("K8s Service Accounts")
            
            # Data protection
            with Cluster("Data Protection"):
                kms_encryption = KMS("KMS Encryption")
                secrets_manager = Blank("Secrets Manager")
                backup_encryption = Blank("Backup Encryption")
            
            # Threat detection
            with Cluster("Threat Detection"):
                guardduty_detect = GuardDuty("GuardDuty")
                security_hub_central = SecurityHub("Security Hub")
                config_compliance = Blank("AWS Config")
            
            # Audit and compliance
            with Cluster("Audit & Compliance"):
                cloudtrail = Blank("CloudTrail")
                audit_logs = Blank("Audit Logging")
                compliance_reports = Blank("Compliance Reports")
        
        # Security data flow
        irsa >> service_accounts
        service_accounts >> kms_encryption
        guardduty_detect >> security_hub_central
        cloudtrail >> audit_logs

def create_network_architecture():
    """Create network architecture diagram"""
    with Diagram("Arrakis Platform - Network Architecture",
                 filename="../docs/diagrams/network/network-architecture",
                 show=False, direction="TB"):
        
        # Internet and edge
        internet = Blank("Internet")
        
        with Cluster("AWS Region"):
            # DNS and load balancing
            route53 = Route53("Route53")
            alb_public = ALB("Public ALB")
            
            with Cluster("VPC (10.0.0.0/16)"):
                # Public subnets
                with Cluster("Public Subnets"):
                    public_1a = Blank("Public-1A\n10.0.1.0/24")
                    public_1b = Blank("Public-1B\n10.0.2.0/24")
                    public_1c = Blank("Public-1C\n10.0.3.0/24")
                
                # Private subnets
                with Cluster("Private Subnets"):
                    private_1a = Blank("Private-1A\n10.0.10.0/24")
                    private_1b = Blank("Private-1B\n10.0.11.0/24")
                    private_1c = Blank("Private-1C\n10.0.12.0/24")
                
                # Database subnets
                with Cluster("Database Subnets"):
                    db_1a = Blank("DB-1A\n10.0.20.0/24")
                    db_1b = Blank("DB-1B\n10.0.21.0/24")
                    db_1c = Blank("DB-1C\n10.0.22.0/24")
                
                # Network components
                nat_gateway = Blank("NAT Gateway")
                igw = Blank("Internet Gateway")
        
        # Connections
        internet >> route53 >> alb_public
        alb_public >> [public_1a, public_1b, public_1c]
        [private_1a, private_1b, private_1c] >> nat_gateway >> igw

def create_monitoring_architecture():
    """Create monitoring architecture diagram"""
    with Diagram("Arrakis Platform - Monitoring Architecture",
                 filename="../docs/diagrams/monitoring/monitoring-architecture",
                 show=False, direction="TB"):
        
        with Cluster("Data Collection"):
            # Metrics collection
            with Cluster("Metrics"):
                prometheus_server = Prometheus("Prometheus")
                node_exporters = Blank("Node Exporters")
                app_metrics = Blank("Application Metrics")
            
            # Logs collection
            with Cluster("Logs"):
                cloudwatch_logs = CloudWatch("CloudWatch Logs")
                fluent_bit = Blank("Fluent Bit")
                app_logs = Blank("Application Logs")
            
            # Traces collection
            with Cluster("Traces"):
                jaeger_collector = Jaeger("Jaeger")
                otel_collector = Blank("OpenTelemetry\nCollector")
                app_traces = Blank("Application Traces")
        
        with Cluster("Visualization & Alerting"):
            # Dashboards
            grafana_dash = Grafana("Grafana")
            cloudwatch_dash = CloudWatch("CloudWatch\nDashboards")
            
            # Alerting
            alert_manager = Blank("AlertManager")
            sns_alerts = SNS("SNS Alerts")
            
            # Analysis
            jaeger_ui = Blank("Jaeger UI")
        
        # Data flow
        [node_exporters, app_metrics] >> prometheus_server >> grafana_dash
        [fluent_bit, app_logs] >> cloudwatch_logs >> cloudwatch_dash
        [otel_collector, app_traces] >> jaeger_collector >> jaeger_ui
        prometheus_server >> alert_manager >> sns_alerts

def main():
    """Generate all architecture diagrams"""
    print("Generating architecture diagrams...")
    
    try:
        create_overall_architecture()
        print("✓ Overall architecture diagram generated")
        
        create_microservices_architecture()
        print("✓ Microservices architecture diagram generated")
        
        create_security_architecture()
        print("✓ Security architecture diagram generated")
        
        create_network_architecture()
        print("✓ Network architecture diagram generated")
        
        create_monitoring_architecture()
        print("✓ Monitoring architecture diagram generated")
        
        print("\nAll architecture diagrams generated successfully!")
        
    except Exception as e:
        print(f"Error generating diagrams: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF
    
    # Run the Python script
    python3 "${SCRIPT_DIR}/generate_architecture.py"
    
    success "Architecture diagrams generated"
}

# Generate diagram index and documentation
generate_diagram_documentation() {
    info "Generating diagram documentation..."
    
    cat > "${DIAGRAMS_DIR}/README.md" << 'EOF'
# Infrastructure Diagrams

This directory contains automatically generated infrastructure diagrams for the Arrakis platform.

## Architecture Diagrams

### Overall Architecture
- **File**: `architecture/overall-architecture.png`
- **Description**: Complete overview of the Arrakis platform architecture
- **Components**: All major AWS services, microservices, and data flow

### Microservices Architecture  
- **File**: `architecture/microservices-architecture.png`
- **Description**: Detailed view of the microservices architecture
- **Components**: All 7 microservices and their interactions

### Security Architecture
- **File**: `security/security-architecture.png` 
- **Description**: Security controls and compliance architecture
- **Components**: IAM, encryption, monitoring, and threat detection

### Network Architecture
- **File**: `network/network-architecture.png`
- **Description**: Network topology and connectivity
- **Components**: VPC, subnets, routing, and security groups

### Monitoring Architecture
- **File**: `monitoring/monitoring-architecture.png`
- **Description**: Observability and monitoring stack
- **Components**: Prometheus, Grafana, Jaeger, and alerting

## Infrastructure Diagrams

### Terraform Plan Diagram
- **File**: `infrastructure/terraform-plan.png`
- **Description**: Visual representation of Terraform infrastructure plan
- **Generated from**: Terraform plan output

### Module Diagrams
Individual diagrams for each Terraform module:

- `infrastructure/networking.png` - VPC and networking components
- `infrastructure/eks.png` - Kubernetes cluster infrastructure  
- `infrastructure/rds.png` - Database infrastructure
- `infrastructure/elasticache.png` - Redis cache infrastructure
- `infrastructure/security.png` - Security services and IAM
- `infrastructure/backup.png` - Backup and recovery infrastructure
- `infrastructure/dns.png` - DNS and certificate management
- `infrastructure/monitoring.png` - Monitoring infrastructure
- `infrastructure/nats.png` - Message broker infrastructure

## Diagram Formats

All diagrams are available in multiple formats:
- **PNG**: For documentation and presentations
- **SVG**: For web display and scalable viewing
- **DOT**: Source files for GraphViz (where applicable)

## Automatic Updates

These diagrams are automatically updated when:
1. Terraform configuration changes are committed
2. GitHub Actions workflow runs
3. Manual regeneration via `scripts/infrastructure-diagrams/generate-diagrams.sh`

## Last Generated

Generated on: $(date '+%Y-%m-%d %H:%M:%S UTC')

## Usage

### View Diagrams
Simply open the PNG or SVG files in any image viewer or web browser.

### Regenerate Diagrams
```bash
# Run from project root
./scripts/infrastructure-diagrams/generate-diagrams.sh
```

### Integration
These diagrams are automatically embedded in:
- Project documentation
- Architecture Decision Records (ADRs)
- System design documents
- Incident response runbooks

## Tools Used

- **InfraMap**: Terraform state visualization
- **Diagrams**: Python-based architecture diagrams  
- **GraphViz**: DOT file rendering
- **GitHub Actions**: Automated generation
EOF
    
    success "Diagram documentation generated"
}

# Create diagram index HTML
create_diagram_index() {
    info "Creating diagram index page..."
    
    cat > "${DIAGRAMS_DIR}/index.html" << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Arrakis Platform - Infrastructure Diagrams</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .header {
            text-align: center;
            margin-bottom: 40px;
            padding: 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
        }
        .diagram-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        .diagram-card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s;
        }
        .diagram-card:hover {
            transform: translateY(-5px);
        }
        .diagram-title {
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 10px;
            color: #333;
        }
        .diagram-description {
            color: #666;
            margin-bottom: 15px;
            line-height: 1.5;
        }
        .diagram-links {
            display: flex;
            gap: 10px;
        }
        .diagram-link {
            padding: 8px 16px;
            text-decoration: none;
            border-radius: 5px;
            font-size: 0.9em;
            transition: background-color 0.2s;
        }
        .png-link {
            background-color: #e3f2fd;
            color: #1976d2;
        }
        .png-link:hover {
            background-color: #bbdefb;
        }
        .svg-link {
            background-color: #f3e5f5;
            color: #7b1fa2;
        }
        .svg-link:hover {
            background-color: #e1bee7;
        }
        .section-title {
            font-size: 1.5em;
            font-weight: bold;
            margin: 30px 0 20px 0;
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        .last-updated {
            text-align: center;
            color: #666;
            font-style: italic;
            margin-top: 40px;
            padding: 20px;
            background: white;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏗️ Arrakis Platform</h1>
        <h2>Infrastructure Diagrams</h2>
        <p>Comprehensive visualization of our production infrastructure</p>
    </div>

    <div class="section-title">🏛️ Architecture Diagrams</div>
    <div class="diagram-grid">
        <div class="diagram-card">
            <div class="diagram-title">Overall Architecture</div>
            <div class="diagram-description">
                Complete overview of the Arrakis platform including all AWS services, microservices, and data flow.
            </div>
            <div class="diagram-links">
                <a href="architecture/overall-architecture.png" class="diagram-link png-link">PNG</a>
                <a href="architecture/overall-architecture.svg" class="diagram-link svg-link">SVG</a>
            </div>
        </div>

        <div class="diagram-card">
            <div class="diagram-title">Microservices Architecture</div>
            <div class="diagram-description">
                Detailed view of all 7 microservices and their interactions within the platform.
            </div>
            <div class="diagram-links">
                <a href="architecture/microservices-architecture.png" class="diagram-link png-link">PNG</a>
                <a href="architecture/microservices-architecture.svg" class="diagram-link svg-link">SVG</a>
            </div>
        </div>

        <div class="diagram-card">
            <div class="diagram-title">Security Architecture</div>
            <div class="diagram-description">
                Security controls, IAM roles, encryption, and compliance monitoring architecture.
            </div>
            <div class="diagram-links">
                <a href="security/security-architecture.png" class="diagram-link png-link">PNG</a>
                <a href="security/security-architecture.svg" class="diagram-link svg-link">SVG</a>
            </div>
        </div>

        <div class="diagram-card">
            <div class="diagram-title">Network Architecture</div>
            <div class="diagram-description">
                VPC topology, subnets, routing tables, and network security configuration.
            </div>
            <div class="diagram-links">
                <a href="network/network-architecture.png" class="diagram-link png-link">PNG</a>
                <a href="network/network-architecture.svg" class="diagram-link svg-link">SVG</a>
            </div>
        </div>

        <div class="diagram-card">
            <div class="diagram-title">Monitoring Architecture</div>
            <div class="diagram-description">
                Observability stack with Prometheus, Grafana, Jaeger, and comprehensive alerting.
            </div>
            <div class="diagram-links">
                <a href="monitoring/monitoring-architecture.png" class="diagram-link png-link">PNG</a>
                <a href="monitoring/monitoring-architecture.svg" class="diagram-link svg-link">SVG</a>
            </div>
        </div>
    </div>

    <div class="section-title">🔧 Infrastructure Diagrams</div>
    <div class="diagram-grid">
        <div class="diagram-card">
            <div class="diagram-title">Terraform Plan</div>
            <div class="diagram-description">
                Visual representation of the complete Terraform infrastructure plan.
            </div>
            <div class="diagram-links">
                <a href="infrastructure/terraform-plan.png" class="diagram-link png-link">PNG</a>
                <a href="infrastructure/terraform-plan.svg" class="diagram-link svg-link">SVG</a>
            </div>
        </div>

        <div class="diagram-card">
            <div class="diagram-title">Networking Module</div>
            <div class="diagram-description">
                VPC, subnets, security groups, and networking components.
            </div>
            <div class="diagram-links">
                <a href="infrastructure/networking.png" class="diagram-link png-link">PNG</a>
                <a href="infrastructure/networking.svg" class="diagram-link svg-link">SVG</a>
            </div>
        </div>

        <div class="diagram-card">
            <div class="diagram-title">EKS Module</div>
            <div class="diagram-description">
                Kubernetes cluster infrastructure with node groups and security.
            </div>
            <div class="diagram-links">
                <a href="infrastructure/eks.png" class="diagram-link png-link">PNG</a>
                <a href="infrastructure/eks.svg" class="diagram-link svg-link">SVG</a>
            </div>
        </div>

        <div class="diagram-card">
            <div class="diagram-title">Database Module</div>
            <div class="diagram-description">
                RDS PostgreSQL databases with backup and monitoring configuration.
            </div>
            <div class="diagram-links">
                <a href="infrastructure/rds.png" class="diagram-link png-link">PNG</a>
                <a href="infrastructure/rds.svg" class="diagram-link svg-link">SVG</a>
            </div>
        </div>

        <div class="diagram-card">
            <div class="diagram-title">Cache Module</div>
            <div class="diagram-description">
                ElastiCache Redis clusters with high availability configuration.
            </div>
            <div class="diagram-links">
                <a href="infrastructure/elasticache.png" class="diagram-link png-link">PNG</a>
                <a href="infrastructure/elasticache.svg" class="diagram-link svg-link">SVG</a>
            </div>
        </div>

        <div class="diagram-card">
            <div class="diagram-title">Security Module</div>
            <div class="diagram-description">
                IAM roles, KMS encryption, secrets management, and security monitoring.
            </div>
            <div class="diagram-links">
                <a href="infrastructure/security.png" class="diagram-link png-link">PNG</a>
                <a href="infrastructure/security.svg" class="diagram-link svg-link">SVG</a>
            </div>
        </div>
    </div>

    <div class="last-updated">
        <p><strong>Last Updated:</strong> <span id="lastUpdated"></span></p>
        <p>Diagrams are automatically generated from Terraform state and updated on every commit.</p>
    </div>

    <script>
        document.getElementById('lastUpdated').textContent = new Date().toLocaleString();
    </script>
</body>
</html>
EOF
    
    success "Diagram index page created"
}

# Main execution
main() {
    info "Starting infrastructure diagram generation..."
    info "Project root: ${PROJECT_ROOT}"
    
    # Create log file
    touch "${LOG_FILE}"
    
    # Execute all steps
    check_dependencies
    install_inframap
    install_python_deps
    create_directories
    generate_terraform_diagrams
    generate_architecture_diagrams
    generate_diagram_documentation
    create_diagram_index
    
    success "Infrastructure diagram generation completed successfully!"
    info "Diagrams available at: ${DIAGRAMS_DIR}"
    info "View index page: ${DIAGRAMS_DIR}/index.html"
    info "Log file: ${LOG_FILE}"
}

# Execute main function
main "$@"