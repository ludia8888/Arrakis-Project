# Infrastructure Architecture

**Generated:** 2025-07-15 01:00:53 UTC

```mermaid
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
