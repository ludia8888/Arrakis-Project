# Security Architecture

**Generated:** 2025-07-15 01:00:53 UTC

```mermaid
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
