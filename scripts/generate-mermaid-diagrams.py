#!/usr/bin/env python3
"""
Mermaid Diagram Generator for Arrakis Platform
Automatically generates Mermaid diagrams for architecture visualization
Ultra production-ready with comprehensive diagram generation
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Optional import for YAML (not required for core functionality)
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

def create_microservices_architecture():
    """Generate Mermaid diagram for microservices architecture"""
    return """
graph TB
    %% External Layer
    Users[👥 Users] --> ALB[🔄 Application Load Balancer]
    ALB --> |HTTPS| Gateway[🚪 API Gateway]
    
    %% Microservices Layer
    subgraph "🏗️ Arrakis Microservices Platform"
        Gateway --> OMS[📊 Ontology Management<br/>Service]
        Gateway --> UserSvc[👤 User Service]
        Gateway --> AuditSvc[📋 Audit Service]
        Gateway --> DataKernel[⚙️ Data Kernel<br/>Service]
        Gateway --> EmbeddingSvc[🧠 Embedding<br/>Service]
        Gateway --> SchedulerSvc[⏰ Scheduler<br/>Service]
        Gateway --> EventGateway[🔄 Event Gateway]
        
        %% Service Dependencies
        OMS --> |queries| UserSvc
        OMS --> |logs| AuditSvc
        DataKernel --> |events| EventGateway
        SchedulerSvc --> |tasks| DataKernel
        EmbeddingSvc --> |vectors| DataKernel
    end
    
    %% Data Layer
    subgraph "💾 Data Layer"
        OMS --> OMSDB[(🗄️ OMS Database<br/>PostgreSQL)]
        UserSvc --> UserDB[(👤 User Database<br/>PostgreSQL)]
        AuditSvc --> AuditDB[(📋 Audit Database<br/>PostgreSQL)]
        SchedulerSvc --> SchedulerDB[(⏰ Scheduler Database<br/>PostgreSQL)]
        
        OMS --> Redis[(⚡ Redis Cache<br/>ElastiCache)]
        DataKernel --> Redis
        EmbeddingSvc --> Redis
        
        EventGateway --> NATS[(📨 NATS JetStream<br/>Message Broker)]
        SchedulerSvc --> NATS
        OMS --> NATS
    end
    
    %% External Integrations
    subgraph "🌐 External Systems"
        EventGateway --> ExtAPI[🔌 External APIs]
        EventGateway --> Webhooks[🔗 Webhooks]
    end
    
    %% Monitoring Layer
    subgraph "📊 Monitoring & Observability"
        AllServices[All Services] --> Prometheus[📈 Prometheus]
        Prometheus --> Grafana[📊 Grafana]
        AllServices --> Jaeger[🔍 Jaeger Tracing]
        AllServices --> CloudWatch[☁️ CloudWatch]
    end
    
    %% Styling
    classDef serviceClass fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef dataClass fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef monitorClass fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    classDef externalClass fill:#fff3e0,stroke:#e65100,stroke-width:2px
    
    class OMS,UserSvc,AuditSvc,DataKernel,EmbeddingSvc,SchedulerSvc,EventGateway serviceClass
    class OMSDB,UserDB,AuditDB,SchedulerDB,Redis,NATS dataClass
    class Prometheus,Grafana,Jaeger,CloudWatch monitorClass
    class ExtAPI,Webhooks externalClass
"""

def create_infrastructure_architecture():
    """Generate Mermaid diagram for infrastructure architecture"""
    return """
graph TB
    %% Internet and DNS
    Internet[🌐 Internet] --> Route53[🌐 Route53 DNS]
    Route53 --> CloudFront[⚡ CloudFront CDN]
    CloudFront --> ALB[🔄 Application Load Balancer]
    
    %% AWS Infrastructure
    subgraph "☁️ AWS Cloud - us-west-2"
        subgraph "🏗️ VPC (10.0.0.0/16)"
            %% Load Balancer
            ALB --> |HTTPS| EKS[☸️ EKS Cluster]
            
            %% Compute Layer
            subgraph "💻 Compute Layer"
                EKS --> GeneralNodes[🖥️ General Nodes<br/>t3.large]
                EKS --> ComputeNodes[⚡ Compute Nodes<br/>c5.xlarge]
                EKS --> MonitorNodes[📊 Monitor Nodes<br/>t3.medium]
            end
            
            %% Database Layer
            subgraph "🗄️ Database Layer"
                EKS --> |private| OMSRDS[(🗄️ OMS RDS<br/>PostgreSQL 16)]
                EKS --> |private| UserRDS[(👤 User RDS<br/>PostgreSQL 16)]
                EKS --> |private| AuditRDS[(📋 Audit RDS<br/>PostgreSQL 16)]
                EKS --> |private| SchedulerRDS[(⏰ Scheduler RDS<br/>PostgreSQL 16)]
                
                EKS --> |private| Redis[(⚡ ElastiCache Redis<br/>Cluster Mode)]
            end
            
            %% Network Architecture
            subgraph "🌐 Network Architecture"
                ALB --> PublicSubnet1[🌐 Public Subnet 1A<br/>10.0.1.0/24]
                ALB --> PublicSubnet2[🌐 Public Subnet 1B<br/>10.0.2.0/24]
                ALB --> PublicSubnet3[🌐 Public Subnet 1C<br/>10.0.3.0/24]
                
                EKS --> PrivateSubnet1[🔒 Private Subnet 1A<br/>10.0.10.0/24]
                EKS --> PrivateSubnet2[🔒 Private Subnet 1B<br/>10.0.11.0/24]
                EKS --> PrivateSubnet3[🔒 Private Subnet 1C<br/>10.0.12.0/24]
                
                OMSRDS --> DBSubnet1[🗄️ DB Subnet 1A<br/>10.0.20.0/24]
                UserRDS --> DBSubnet2[🗄️ DB Subnet 1B<br/>10.0.21.0/24]
                AuditRDS --> DBSubnet3[🗄️ DB Subnet 1C<br/>10.0.22.0/24]
            end
        end
        
        %% Security Services
        subgraph "🔒 Security Services"
            EKS --> IAM[🔐 IAM/IRSA Roles]
            EKS --> KMS[🔑 KMS Encryption]
            EKS --> SecretsManager[🔐 Secrets Manager]
            
            SecurityHub[🛡️ Security Hub]
            GuardDuty[👁️ GuardDuty]
            CloudTrail[📋 CloudTrail]
        end
        
        %% Backup and Recovery
        subgraph "💾 Backup & Recovery"
            AWSBackup[💾 AWS Backup]
            S3Backup[(📦 S3 Backup Storage)]
            AWSBackup --> S3Backup
            OMSRDS --> AWSBackup
            UserRDS --> AWSBackup
            AuditRDS --> AWSBackup
            SchedulerRDS --> AWSBackup
        end
    end
    
    %% Styling
    classDef awsClass fill:#ff9900,color:#fff,stroke:#232f3e,stroke-width:2px
    classDef vpcClass fill:#f0f8ff,stroke:#4169e1,stroke-width:2px
    classDef computeClass fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef dataClass fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef securityClass fill:#ffebee,stroke:#c62828,stroke-width:2px
    classDef backupClass fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    
    class Route53,CloudFront,ALB awsClass
    class EKS,GeneralNodes,ComputeNodes,MonitorNodes computeClass
    class OMSRDS,UserRDS,AuditRDS,SchedulerRDS,Redis dataClass
    class IAM,KMS,SecretsManager,SecurityHub,GuardDuty,CloudTrail securityClass
    class AWSBackup,S3Backup backupClass
"""

def create_data_flow_diagram():
    """Generate Mermaid diagram for data flow"""
    return """
sequenceDiagram
    participant U as 👥 User
    participant ALB as 🔄 Load Balancer
    participant OMS as 📊 OMS Service
    participant User as 👤 User Service
    participant Audit as 📋 Audit Service
    participant Data as ⚙️ Data Kernel
    participant DB as 🗄️ Database
    participant Cache as ⚡ Redis
    participant NATS as 📨 NATS
    participant Monitor as 📊 Monitoring
    
    %% Authentication Flow
    U->>+ALB: 1. HTTPS Request
    ALB->>+OMS: 2. Route to Service
    OMS->>+User: 3. Validate Token
    User->>+DB: 4. User Lookup
    DB-->>-User: 5. User Data
    User-->>-OMS: 6. Auth Result
    
    %% Business Logic Flow
    OMS->>+Cache: 7. Check Cache
    Cache-->>-OMS: 8. Cache Hit/Miss
    
    alt Cache Miss
        OMS->>+DB: 9. Database Query
        DB-->>-OMS: 10. Data Response
        OMS->>Cache: 11. Update Cache
    end
    
    %% Audit Logging
    OMS->>+Audit: 12. Log Request
    Audit->>+DB: 13. Store Audit
    DB-->>-Audit: 14. Confirm
    Audit-->>-OMS: 15. Logged
    
    %% Event Publishing
    OMS->>+NATS: 16. Publish Event
    NATS->>+Data: 17. Event Delivery
    Data->>+DB: 18. Process Data
    DB-->>-Data: 19. Result
    Data-->>-NATS: 20. Ack
    NATS-->>-OMS: 21. Published
    
    %% Response
    OMS-->>-ALB: 22. Response
    ALB-->>-U: 23. HTTPS Response
    
    %% Monitoring
    Note over OMS,Monitor: Continuous Monitoring
    OMS->>Monitor: Metrics & Traces
    User->>Monitor: Metrics & Traces
    Audit->>Monitor: Metrics & Traces
    Data->>Monitor: Metrics & Traces
"""

def create_cicd_flow_diagram():
    """Generate Mermaid diagram for CI/CD flow"""
    return """
graph TD
    %% Developer Flow
    Dev[👨‍💻 Developer] --> |1. git commit| PreCommit[🔍 Pre-commit Hooks]
    PreCommit --> |2. Code Quality| Checks{✅ All Checks Pass?}
    Checks --> |❌ No| Fix[🔧 Fix Issues]
    Fix --> PreCommit
    Checks --> |✅ Yes| Push[📤 git push]
    
    %% CI/CD Pipeline
    Push --> |3. Triggers| GitHubActions[🤖 GitHub Actions]
    
    subgraph "🔄 CI/CD Pipeline"
        GitHubActions --> CodeQuality[🔍 Code Quality & Security]
        CodeQuality --> UnitTests[🧪 Unit Tests]
        UnitTests --> Build[🏗️ Build Docker Images]
        Build --> SecurityScan[🔒 Security Scanning]
        SecurityScan --> IntegrationTests[🔗 Integration Tests]
        IntegrationTests --> TerraformValidation[🏗️ Terraform Validation]
        TerraformValidation --> K8sValidation[☸️ Kubernetes Validation]
        K8sValidation --> Deploy[🚀 Deploy to Staging]
    end
    
    %% Deployment Validation
    Deploy --> |4. Auto Validate| Validation[✅ Deployment Validation]
    Validation --> HealthChecks[🏥 Health Checks]
    HealthChecks --> MonitoringSetup[📊 Setup Monitoring]
    
    %% Documentation Update
    MonitoringSetup --> |5. Auto Generate| DocUpdate[📚 Update Documentation]
    DocUpdate --> DiagramGen[🎨 Generate Diagrams]
    DiagramGen --> |6. Auto Commit| DocCommit[📝 Commit Documentation]
    
    %% Production Flow
    DocCommit --> |7. Manual Approval| ProdApproval{🚨 Production Approval}
    ProdApproval --> |✅ Approved| ProdDeploy[🚀 Deploy to Production]
    ProdApproval --> |❌ Rejected| Review[👀 Review Required]
    
    %% GitOps
    ProdDeploy --> |8. Infrastructure| GitOps[🔄 GitOps Workflow]
    GitOps --> TerraformApply[🏗️ Terraform Apply]
    TerraformApply --> InfraValidation[✅ Infrastructure Validation]
    InfraValidation --> |9. Success| Monitoring[📊 Production Monitoring]
    InfraValidation --> |❌ Failure| Rollback[⏪ Automated Rollback]
    
    %% Notification
    Monitoring --> Alerts[🔔 Alerts & Notifications]
    Rollback --> Alerts
    
    %% Styling
    classDef devClass fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef cicdClass fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef deployClass fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef prodClass fill:#ffebee,stroke:#c62828,stroke-width:2px
    classDef opsClass fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    
    class Dev,PreCommit,Checks,Fix,Push devClass
    class GitHubActions,CodeQuality,UnitTests,Build,SecurityScan,IntegrationTests,TerraformValidation,K8sValidation cicdClass
    class Deploy,Validation,HealthChecks,MonitoringSetup,DocUpdate,DiagramGen,DocCommit deployClass
    class ProdApproval,ProdDeploy,Review prodClass
    class GitOps,TerraformApply,InfraValidation,Monitoring,Rollback,Alerts opsClass
"""

def create_security_architecture():
    """Generate Mermaid diagram for security architecture"""
    return """
graph TB
    %% External Threats
    Internet[🌐 Internet] --> WAF[🛡️ AWS WAF]
    WAF --> CloudFront[⚡ CloudFront]
    CloudFront --> ALB[🔄 Load Balancer]
    
    %% Network Security
    subgraph "🌐 Network Security Layer"
        ALB --> VPC[🏗️ VPC]
        VPC --> SecurityGroups[🔒 Security Groups]
        SecurityGroups --> NACLs[🛡️ Network ACLs]
        NACLs --> PrivateSubnets[🔒 Private Subnets]
    end
    
    %% Identity & Access Management
    subgraph "🔐 Identity & Access Management"
        Users[👥 Users] --> Cognito[🆔 AWS Cognito]
        Services[🚀 Microservices] --> IRSA[🔑 IRSA Roles]
        IRSA --> ServiceAccounts[☸️ K8s Service Accounts]
        ServiceAccounts --> IAMRoles[🔐 IAM Roles]
        IAMRoles --> LeastPrivilege[⚖️ Least Privilege Policies]
    end
    
    %% Data Protection
    subgraph "🔒 Data Protection Layer"
        TLS[🔐 TLS 1.3] --> DataInTransit[📡 Data in Transit]
        KMS[🔑 AWS KMS] --> DataAtRest[💾 Data at Rest]
        SecretsManager[🔐 Secrets Manager] --> CredentialRotation[🔄 Credential Rotation]
        
        KMS --> DatabaseEncryption[🗄️ Database Encryption]
        KMS --> VolumeEncryption[💽 EBS Volume Encryption]
        KMS --> BackupEncryption[💾 Backup Encryption]
    end
    
    %% Threat Detection
    subgraph "👁️ Threat Detection & Response"
        GuardDuty[🕵️ GuardDuty] --> ThreatDetection[⚠️ Threat Detection]
        SecurityHub[🛡️ Security Hub] --> CentralizedSecurity[📊 Centralized Security]
        Config[⚙️ AWS Config] --> ComplianceMonitoring[📋 Compliance Monitoring]
        
        ThreatDetection --> AutoResponse[🤖 Automated Response]
        CentralizedSecurity --> SecurityAlerts[🚨 Security Alerts]
        ComplianceMonitoring --> ComplianceReports[📄 Compliance Reports]
    end
    
    %% Audit & Compliance
    subgraph "📋 Audit & Compliance"
        CloudTrail[📋 CloudTrail] --> APILogging[📝 API Logging]
        AuditLogs[📊 Application Audit Logs] --> ComplianceDB[(🗄️ Compliance Database)]
        VPCFlowLogs[🌊 VPC Flow Logs] --> NetworkMonitoring[🌐 Network Monitoring]
        
        APILogging --> SOC2[📜 SOC2 Compliance]
        ComplianceDB --> PCI[💳 PCI DSS]
        NetworkMonitoring --> GDPR[🛡️ GDPR Compliance]
    end
    
    %% Security Monitoring
    subgraph "📊 Security Monitoring"
        SIEM[🔍 SIEM Integration] --> SecurityMetrics[📈 Security Metrics]
        Splunk[📊 Splunk] --> LogAnalysis[🔍 Log Analysis]
        Prometheus[📈 Prometheus] --> SecurityAlerts2[🚨 Security Alerts]
        
        SecurityMetrics --> Dashboards[📊 Security Dashboards]
        LogAnalysis --> ThreatHunting[🎯 Threat Hunting]
        SecurityAlerts2 --> IncidentResponse[🚨 Incident Response]
    end
    
    %% Container Security
    subgraph "📦 Container Security"
        ImageScanning[🔍 Image Vulnerability Scanning] --> ECR[📦 ECR Registry]
        PodSecurityPolicies[🔒 Pod Security Policies] --> K8s[☸️ Kubernetes]
        NetworkPolicies[🌐 Network Policies] --> Istio[🕸️ Service Mesh]
        
        ECR --> TrustedImages[✅ Trusted Images]
        K8s --> SecureDeployments[🔒 Secure Deployments]
        Istio --> mTLS[🔐 Mutual TLS]
    end
    
    %% Styling
    classDef networkClass fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef iamClass fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef dataClass fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef threatClass fill:#ffebee,stroke:#c62828,stroke-width:2px
    classDef auditClass fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef monitorClass fill:#fce4ec,stroke:#ad1457,stroke-width:2px
    classDef containerClass fill:#e0f2f1,stroke:#00695c,stroke-width:2px
    
    class WAF,CloudFront,ALB,VPC,SecurityGroups,NACLs,PrivateSubnets networkClass
    class Cognito,IRSA,ServiceAccounts,IAMRoles,LeastPrivilege iamClass
    class TLS,DataInTransit,KMS,DataAtRest,SecretsManager,CredentialRotation,DatabaseEncryption,VolumeEncryption,BackupEncryption dataClass
    class GuardDuty,ThreatDetection,SecurityHub,CentralizedSecurity,Config,ComplianceMonitoring,AutoResponse,SecurityAlerts threatClass
    class CloudTrail,APILogging,AuditLogs,ComplianceDB,VPCFlowLogs,NetworkMonitoring,SOC2,PCI,GDPR auditClass
    class SIEM,SecurityMetrics,Splunk,LogAnalysis,Prometheus,SecurityAlerts2,Dashboards,ThreatHunting,IncidentResponse monitorClass
    class ImageScanning,ECR,PodSecurityPolicies,K8s,NetworkPolicies,Istio,TrustedImages,SecureDeployments,mTLS containerClass
"""

def generate_all_diagrams():
    """Generate all Mermaid diagrams"""
    
    # Ensure docs/diagrams/mermaid directory exists
    diagrams_dir = Path("docs/diagrams/mermaid")
    diagrams_dir.mkdir(parents=True, exist_ok=True)
    
    diagrams = {
        "microservices-architecture.md": {
            "title": "Microservices Architecture",
            "diagram": create_microservices_architecture()
        },
        "infrastructure-architecture.md": {
            "title": "Infrastructure Architecture", 
            "diagram": create_infrastructure_architecture()
        },
        "data-flow.md": {
            "title": "Data Flow Diagram",
            "diagram": create_data_flow_diagram()
        },
        "cicd-flow.md": {
            "title": "CI/CD Flow",
            "diagram": create_cicd_flow_diagram()
        },
        "security-architecture.md": {
            "title": "Security Architecture",
            "diagram": create_security_architecture()
        }
    }
    
    # Generate each diagram file
    for filename, content in diagrams.items():
        file_path = diagrams_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"""# {content['title']}

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

```mermaid
{content['diagram'].strip()}
```

## Usage

This Mermaid diagram can be:
1. **Rendered in GitHub** - Automatically displayed in GitHub README files
2. **Used in Documentation** - Embedded in GitBook, Notion, or other docs
3. **Exported to Images** - Using Mermaid CLI or online tools
4. **Integrated in Presentations** - Copy the Mermaid code into presentation tools

## Live Editor

Edit this diagram at: [Mermaid Live Editor](https://mermaid.live/)

## Integration

This diagram is automatically updated when:
- Code changes are committed to the repository
- Infrastructure configuration is modified
- GitHub Actions workflows are triggered
""")
    
    # Create index file
    index_content = f"""# 🎨 Mermaid Diagrams Index

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

This directory contains automatically generated Mermaid diagrams for the Arrakis Platform.

## 📊 Available Diagrams

### 🏗️ Architecture Diagrams
- **[Microservices Architecture](microservices-architecture.md)** - Overview of all 7 microservices and their interactions
- **[Infrastructure Architecture](infrastructure-architecture.md)** - Complete AWS infrastructure layout
- **[Security Architecture](security-architecture.md)** - Security controls and compliance

### 🔄 Process Diagrams  
- **[Data Flow](data-flow.md)** - Request/response flow through the system
- **[CI/CD Flow](cicd-flow.md)** - Development to production pipeline

## 🚀 Features

### GitHub Integration
All diagrams are automatically rendered in GitHub:
- ✅ Native Mermaid support in GitHub README files
- ✅ Real-time rendering in pull requests
- ✅ Version control for diagram changes

### Automated Updates
Diagrams are automatically updated when:
- 🔄 Code changes are committed
- 🏗️ Infrastructure is modified  
- 📝 Documentation is updated
- 🤖 GitHub Actions workflows run

### Multiple Output Formats
- **Mermaid Code** - For embedding in documentation
- **PNG/SVG Export** - Using Mermaid CLI
- **Live Editing** - Mermaid Live Editor integration
- **PDF Export** - For presentations and reports

## 🛠️ Usage

### Embed in README
```markdown
```mermaid
graph TB
    A[Start] --> B[Process]
    B --> C[End]
```\```

### Export to Image
```bash
# Install Mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# Export to PNG
mmdc -i diagram.md -o diagram.png

# Export to SVG  
mmdc -i diagram.md -o diagram.svg
```

### Live Editing
1. Copy Mermaid code from any `.md` file
2. Open [Mermaid Live Editor](https://mermaid.live/)
3. Paste and edit the diagram
4. Export in desired format

## 📈 Diagram Statistics

| Diagram Type | Complexity | Auto-Update | GitHub Render |
|--------------|------------|-------------|---------------|
| Microservices | High | ✅ | ✅ |
| Infrastructure | Very High | ✅ | ✅ |
| Security | High | ✅ | ✅ |
| Data Flow | Medium | ✅ | ✅ |
| CI/CD Flow | High | ✅ | ✅ |

## 🔗 Related Documentation

- **[Infrastructure Diagrams](../infrastructure/)** - Generated infrastructure diagrams
- **[Architecture Diagrams](../architecture/)** - Python-generated architecture diagrams  
- **[API Documentation](../../api/)** - Service API documentation
- **[Monitoring Documentation](../../monitoring/)** - Observability setup

---
*Diagrams automatically generated by GitHub Actions*
"""
    
    with open(diagrams_dir / "README.md", 'w', encoding='utf-8') as f:
        f.write(index_content)
    
    print(f"✅ Generated {len(diagrams)} Mermaid diagrams in {diagrams_dir}")
    
    # Create GitHub Pages integration
    create_github_pages_integration(diagrams_dir)
    
    return len(diagrams)

def create_github_pages_integration(diagrams_dir):
    """Create GitHub Pages integration for Mermaid diagrams"""
    
    # Create _config.yml for GitHub Pages
    config_content = """# GitHub Pages Configuration for Mermaid Diagrams
title: "Arrakis Platform - Architecture Diagrams"
description: "Interactive Mermaid diagrams for the Arrakis microservices platform"

# Enable Mermaid support
markdown: kramdown
kramdown:
  input: GFM
  syntax_highlighter: rouge

# Mermaid configuration
mermaid:
  theme: default
  startOnLoad: true

# GitHub Pages settings
remote_theme: pages-themes/minimal
plugins:
  - jekyll-remote-theme

# Navigation
nav:
  - name: "Home"
    url: "/"
  - name: "Microservices"
    url: "/microservices-architecture"
  - name: "Infrastructure" 
    url: "/infrastructure-architecture"
  - name: "Security"
    url: "/security-architecture"
  - name: "Data Flow"
    url: "/data-flow"
  - name: "CI/CD"
    url: "/cicd-flow"
"""
    
    with open(diagrams_dir / "_config.yml", 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    # Create index.html for GitHub Pages
    index_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Arrakis Platform - Architecture Diagrams</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .diagram-card { background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin: 20px 0; padding: 20px; }
        .diagram-title { font-size: 1.5em; margin-bottom: 10px; color: #333; }
        .mermaid { text-align: center; }
        nav { background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        nav a { margin: 0 15px; text-decoration: none; color: #007bff; }
        nav a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🏗️ Arrakis Platform - Architecture Diagrams</h1>
            <p>Interactive Mermaid diagrams for comprehensive system visualization</p>
        </header>
        
        <nav>
            <a href="#microservices">Microservices</a>
            <a href="#infrastructure">Infrastructure</a>
            <a href="#security">Security</a>
            <a href="#dataflow">Data Flow</a>
            <a href="#cicd">CI/CD</a>
        </nav>
        
        <div class="diagram-card" id="microservices">
            <div class="diagram-title">🚀 Microservices Architecture</div>
            <div class="mermaid" id="microservices-diagram">
                <!-- Microservices diagram will be loaded here -->
            </div>
        </div>
        
        <div class="diagram-card" id="infrastructure">
            <div class="diagram-title">🏗️ Infrastructure Architecture</div>
            <div class="mermaid" id="infrastructure-diagram">
                <!-- Infrastructure diagram will be loaded here -->
            </div>
        </div>
        
        <div class="diagram-card" id="security">
            <div class="diagram-title">🔒 Security Architecture</div>
            <div class="mermaid" id="security-diagram">
                <!-- Security diagram will be loaded here -->
            </div>
        </div>
        
        <div class="diagram-card" id="dataflow">
            <div class="diagram-title">🔄 Data Flow</div>
            <div class="mermaid" id="dataflow-diagram">
                <!-- Data flow diagram will be loaded here -->
            </div>
        </div>
        
        <div class="diagram-card" id="cicd">
            <div class="diagram-title">⚡ CI/CD Flow</div>
            <div class="mermaid" id="cicd-diagram">
                <!-- CI/CD diagram will be loaded here -->
            </div>
        </div>
    </div>
    
    <script>
        mermaid.initialize({ startOnLoad: true, theme: 'default' });
        
        // Load diagram content from markdown files
        async function loadDiagrams() {
            // This would load the actual Mermaid content from the .md files
            // For GitHub Pages, the diagrams are rendered automatically
        }
        
        // Initialize on page load
        document.addEventListener('DOMContentLoaded', loadDiagrams);
    </script>
</body>
</html>"""
    
    with open(diagrams_dir / "index.html", 'w', encoding='utf-8') as f:
        f.write(index_html)
    
    print(f"✅ Created GitHub Pages integration in {diagrams_dir}")

if __name__ == "__main__":
    print("🎨 Generating Mermaid diagrams for Arrakis Platform...")
    
    try:
        diagram_count = generate_all_diagrams()
        print(f"✅ Successfully generated {diagram_count} Mermaid diagrams")
        print("🌐 GitHub Pages integration created")
        print("🔗 Diagrams will be automatically rendered in GitHub")
        
    except Exception as e:
        print(f"❌ Error generating diagrams: {e}")
        sys.exit(1)