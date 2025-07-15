# Security Terraform Module

Comprehensive security infrastructure for the Arrakis platform with enterprise-grade security controls, IAM roles for service accounts (IRSA), secrets management, and compliance monitoring.

## Features

- **IAM Roles for Service Accounts (IRSA)**: Fine-grained AWS permissions for Kubernetes services
- **Secrets Management**: Encrypted secrets with cross-region replication and rotation
- **Security Monitoring**: CloudTrail, GuardDuty, Security Hub, and AWS Config integration
- **Network Security**: Security groups and network policies for micro-segmentation
- **Compliance**: CIS, PCI-DSS, and AWS Foundational Security Standard support
- **Threat Detection**: Real-time threat detection and automated response capabilities
- **Audit Logging**: Comprehensive audit trails for all security events

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Architecture                     │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │
│  │   IAM/IRSA    │  │   Secrets     │  │   Network     │   │
│  │   Management  │  │   Manager     │  │   Security    │   │
│  │               │  │               │  │               │   │
│  │ • Service     │  │ • KMS         │  │ • Security    │   │
│  │   Accounts    │  │   Encryption  │  │   Groups      │   │
│  │ • Custom      │  │ • Cross-      │  │ • Network     │   │
│  │   Policies    │  │   Region      │  │   Policies    │   │
│  │ • OIDC        │  │   Backup      │  │ • Micro-      │   │
│  │   Integration │  │ • Rotation    │  │   segmentation│   │
│  └───────────────┘  └───────────────┘  └───────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │
│  │   Monitoring  │  │   Compliance  │  │   Threat      │   │
│  │   & Logging   │  │   Standards   │  │   Detection   │   │
│  │               │  │               │  │               │   │
│  │ • CloudTrail  │  │ • CIS         │  │ • GuardDuty   │   │
│  │ • Config      │  │ • PCI-DSS     │  │ • Security    │   │
│  │ • VPC Logs    │  │ • AWS Found.  │  │   Hub         │   │
│  │ • Audit Logs  │  │ • NIST        │  │ • Detective   │   │
│  └───────────────┘  └───────────────┘  └───────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

```hcl
module "security" {
  source = "./modules/security"

  project_name            = "arrakis"
  environment            = "production"
  cluster_name           = "arrakis-prod"
  cluster_oidc_issuer_url = "https://oidc.eks.us-west-2.amazonaws.com/id/EXAMPLE"

  # VPC Configuration
  vpc_id   = "vpc-12345678"
  vpc_cidr = "10.0.0.0/16"

  # Service Accounts (automatically includes all 7 microservices)
  service_accounts = {
    monitoring = {
      namespace = "monitoring"
      policies = [
        "arn:aws:iam::aws:policy/CloudWatchReadOnlyAccess"
      ]
    }
  }

  # Secrets Configuration
  secrets = {
    database_credentials = {
      description = "Database credentials"
      secret_data = {
        username = "admin"
        password = "secure-password"
      }
    }
  }

  # Security Features
  enable_cloudtrail   = true
  enable_guardduty    = true
  enable_security_hub = true

  tags = {
    Environment = "production"
    Project     = "arrakis"
  }
}
```

## Configuration

### Core Configuration

| Variable | Description | Type | Default | Required |
|----------|-------------|------|---------|----------|
| `project_name` | Name of the project | `string` | - | yes |
| `environment` | Environment (development, staging, production) | `string` | - | yes |
| `cluster_name` | EKS cluster name | `string` | - | yes |
| `cluster_oidc_issuer_url` | EKS OIDC issuer URL | `string` | - | yes |

### Network Security

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `vpc_id` | VPC ID for security groups | `string` | `""` |
| `vpc_cidr` | VPC CIDR block | `string` | `"10.0.0.0/16"` |
| `microservices_ports` | Port configuration | `object` | See variables.tf |
| `allowed_cidr_blocks` | Allowed CIDR blocks | `list(string)` | `[]` |

### Security Monitoring

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `enable_cloudtrail` | Enable AWS CloudTrail | `bool` | `true` |
| `enable_aws_config` | Enable AWS Config | `bool` | `true` |
| `enable_guardduty` | Enable AWS GuardDuty | `bool` | `true` |
| `enable_security_hub` | Enable AWS Security Hub | `bool` | `true` |
| `enable_kubernetes_audit_logs` | Enable K8s audit logs in GuardDuty | `bool` | `true` |

### Secrets Management

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `kms_deletion_window` | KMS key deletion window (days) | `number` | `7` |
| `secret_recovery_window` | Secret recovery window (days) | `number` | `7` |
| `replica_region` | Region for secret replication | `string` | `"us-east-1"` |
| `enable_cross_region_backup` | Enable cross-region backup | `bool` | `true` |

### Compliance

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `compliance_standards` | Compliance standards to enable | `list(string)` | `["cis", "pci-dss", "aws-foundational"]` |
| `enable_encryption_at_rest` | Enable encryption at rest | `bool` | `true` |
| `enable_encryption_in_transit` | Enable encryption in transit | `bool` | `true` |

## Service Account Roles (IRSA)

The module automatically creates IRSA roles for all 7 Arrakis microservices:

### Core Services

- **ontology-management-service**: S3 read access, CloudWatch, SSM, Secrets Manager
- **user-service**: CloudWatch, Secrets Manager, KMS decryption
- **audit-service**: CloudWatch Logs, S3 full access for audit data
- **data-kernel-service**: CloudWatch, Secrets Manager, RDS describe
- **embedding-service**: CloudWatch, S3 for ML models
- **scheduler-service**: CloudWatch, EventBridge, SQS
- **event-gateway**: CloudWatch, EventBridge, SNS, SQS

Each service gets:
- **Least privilege access** with service-specific permissions
- **Custom IAM policies** for service requirements
- **OIDC trust relationship** with EKS cluster
- **Proper annotations** for Kubernetes integration

## Secrets Management

### Automatic KMS Encryption

```hcl
# All secrets are encrypted with customer-managed KMS key
secrets = {
  database_credentials = {
    description = "RDS credentials"
    secret_data = {
      username = "admin"
      password = var.db_password
    }
  }

  jwt_secrets = {
    description = "JWT signing keys"
    secret_data = {
      private_key = var.jwt_private_key
      public_key  = var.jwt_public_key
    }
  }
}
```

### Cross-Region Replication

- **Automatic replication** to secondary region
- **Same KMS encryption** in replica region
- **Disaster recovery** capabilities

## Security Monitoring

### CloudTrail Configuration

```hcl
# Comprehensive API logging
enable_cloudtrail = true

# Logs include:
# - All API calls to AWS services
# - S3 object-level events
# - Secrets Manager access
# - KMS key usage
```

### GuardDuty Integration

```hcl
# Advanced threat detection
enable_guardduty = true

# Features:
# - Malware detection
# - Kubernetes audit log analysis
# - S3 threat detection
# - Network traffic analysis
```

### Security Hub

```hcl
# Centralized security findings
enable_security_hub = true

# Standards enabled:
# - AWS Foundational Security Standard
# - CIS AWS Foundations Benchmark
# - PCI DSS
```

## Network Security

### Security Groups

```hcl
# Microservices security group
# - HTTP ports: 8000-8010
# - gRPC ports: 50050-50060
# - Metrics port: 9090
# - Internal VPC communication only

# Database access security group
# - PostgreSQL: 5432
# - Redis: 6379
# - Restricted to VPC CIDR
```

### Micro-segmentation

The module implements defense-in-depth with:
- **Application-level** security groups
- **Database-level** access controls
- **Network-level** policies
- **Pod-level** security contexts

## Compliance Standards

### Supported Standards

| Standard | Description | Enabled |
|----------|-------------|---------|
| **CIS** | CIS AWS Foundations Benchmark | ✅ |
| **PCI-DSS** | Payment Card Industry Data Security Standard | ✅ |
| **AWS Foundational** | AWS Foundational Security Standard | ✅ |
| **NIST** | NIST Cybersecurity Framework | Optional |
| **SOC2** | Service Organization Control 2 | Optional |

### Compliance Features

- **Encryption everywhere** (at rest and in transit)
- **Audit logging** for all actions
- **Access controls** with least privilege
- **Key rotation** and management
- **Vulnerability scanning**
- **Configuration compliance**

## Usage Examples

### Production Environment

```hcl
module "security" {
  source = "./modules/security"

  project_name            = "arrakis"
  environment            = "production"
  cluster_name           = "arrakis-prod"
  cluster_oidc_issuer_url = data.aws_eks_cluster.main.identity[0].oidc[0].issuer

  vpc_id   = module.networking.vpc_id
  vpc_cidr = module.networking.vpc_cidr

  # Production security configuration
  enable_cloudtrail   = true
  enable_guardduty    = true
  enable_security_hub = true
  enable_aws_config   = true
  enable_detective    = true
  enable_macie        = true

  # Compliance requirements
  compliance_standards = [
    "cis",
    "pci-dss",
    "aws-foundational",
    "soc2"
  ]

  # Enhanced monitoring
  security_notification_email = "security@company.com"
  enable_real_time_notifications = true
  security_alert_severity_threshold = "MEDIUM"

  # Backup and recovery
  enable_cross_region_backup = true
  backup_retention_days      = 90
  secret_recovery_window     = 30

  # Custom service account
  service_accounts = {
    backup_service = {
      namespace = "backup"
      policies = [
        "arn:aws:iam::aws:policy/AWSBackupServiceRolePolicyForBackup"
      ]
      custom_policy_statements = [
        {
          effect = "Allow"
          actions = [
            "s3:ListBucket",
            "s3:GetObject",
            "s3:PutObject"
          ]
          resources = [
            "arn:aws:s3:::backup-bucket/*"
          ]
        }
      ]
    }
  }

  tags = {
    Environment     = "production"
    Project         = "arrakis"
    SecurityLevel   = "high"
    ComplianceReq   = "pci-dss,soc2"
    DataClass       = "confidential"
  }
}
```

### Development Environment

```hcl
module "security" {
  source = "./modules/security"

  project_name            = "arrakis"
  environment            = "development"
  cluster_name           = "arrakis-dev"
  cluster_oidc_issuer_url = data.aws_eks_cluster.dev.identity[0].oidc[0].issuer

  vpc_id   = module.networking.vpc_id
  vpc_cidr = module.networking.vpc_cidr

  # Reduced monitoring for cost optimization
  enable_cloudtrail   = true
  enable_guardduty    = false  # Disabled for cost savings
  enable_security_hub = false  # Disabled for cost savings
  enable_aws_config   = false  # Disabled for cost savings

  # Basic compliance
  compliance_standards = ["aws-foundational"]

  # Reduced retention for cost optimization
  backup_retention_days = 30
  secret_recovery_window = 7
  security_log_retention_days = 90

  tags = {
    Environment = "development"
    Project     = "arrakis"
    CostCenter  = "development"
  }
}
```

### Multi-Environment Setup

```hcl
# Variables for environment-specific configuration
locals {
  environments = {
    development = {
      enable_advanced_security = false
      retention_days = 30
      compliance_standards = ["aws-foundational"]
    }
    staging = {
      enable_advanced_security = true
      retention_days = 60
      compliance_standards = ["aws-foundational", "cis"]
    }
    production = {
      enable_advanced_security = true
      retention_days = 90
      compliance_standards = ["aws-foundational", "cis", "pci-dss"]
    }
  }
}

module "security" {
  source = "./modules/security"

  project_name            = "arrakis"
  environment            = var.environment
  cluster_name           = "arrakis-${var.environment}"
  cluster_oidc_issuer_url = data.aws_eks_cluster.main.identity[0].oidc[0].issuer

  vpc_id   = module.networking.vpc_id
  vpc_cidr = module.networking.vpc_cidr

  # Environment-specific configuration
  enable_guardduty    = local.environments[var.environment].enable_advanced_security
  enable_security_hub = local.environments[var.environment].enable_advanced_security
  enable_detective    = local.environments[var.environment].enable_advanced_security

  compliance_standards = local.environments[var.environment].compliance_standards
  backup_retention_days = local.environments[var.environment].retention_days

  tags = merge(local.common_tags, {
    Environment = var.environment
  })
}
```

## Operations

### Monitoring Security Events

```bash
# Check CloudTrail logs
aws logs filter-log-events \
  --log-group-name /aws/cloudtrail/security-audit \
  --start-time $(date -d '1 hour ago' +%s)000

# Check GuardDuty findings
aws guardduty list-findings \
  --detector-id $(aws guardduty list-detectors --query 'DetectorIds[0]' --output text)

# Check Security Hub findings
aws securityhub get-findings \
  --filters '{"SeverityLabel":[{"Value":"HIGH","Comparison":"EQUALS"}]}'
```

### Managing Secrets

```bash
# Retrieve secret
aws secretsmanager get-secret-value \
  --secret-id arrakis/database_credentials-production

# Update secret
aws secretsmanager update-secret \
  --secret-id arrakis/jwt_secrets-production \
  --secret-string '{"key":"new-value"}'

# List all secrets
aws secretsmanager list-secrets \
  --filters Key=name,Values=arrakis/
```

### Service Account Integration

```yaml
# Kubernetes service account with IRSA
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ontology-management-service
  namespace: arrakis
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/arrakis-ontology-management-service-irsa-production
```

## Security Best Practices

### 1. Principle of Least Privilege
- Service accounts have minimal required permissions
- Custom policies for specific service needs
- Regular access reviews and audits

### 2. Defense in Depth
- Multiple layers of security controls
- Network, application, and data-level protection
- Monitoring at every layer

### 3. Encryption Everywhere
- KMS customer-managed keys
- Encryption at rest for all data
- TLS for all communications

### 4. Continuous Monitoring
- Real-time threat detection
- Automated security scanning
- Compliance monitoring

### 5. Incident Response
- Automated alerting and notifications
- Security playbooks and runbooks
- Forensic capabilities with CloudTrail

## Troubleshooting

### Common Issues

1. **IRSA Role Not Working**
   ```bash
   # Check OIDC provider
   aws iam list-open-id-connect-providers

   # Verify service account annotation
   kubectl get sa ontology-management-service -n arrakis -o yaml
   ```

2. **Secret Access Denied**
   ```bash
   # Check IAM permissions
   aws iam simulate-principal-policy \
     --policy-source-arn arn:aws:iam::123456789012:role/arrakis-user-service-irsa-production \
     --action-names secretsmanager:GetSecretValue \
     --resource-arns arn:aws:secretsmanager:us-west-2:123456789012:secret:arrakis/database_credentials-production
   ```

3. **KMS Access Issues**
   ```bash
   # Check KMS key policy
   aws kms describe-key --key-id alias/arrakis-secrets-production

   # Test decryption
   aws kms decrypt --ciphertext-blob fileb://encrypted-data
   ```

### Performance Optimization

1. **Cost Optimization**
   - Disable unnecessary services in development
   - Use appropriate log retention periods
   - Regular cleanup of unused resources

2. **Monitoring Optimization**
   - Filter CloudTrail events to reduce costs
   - Configure appropriate GuardDuty scanning
   - Use Config rules for specific compliance needs

## Security Scanning

### Automated Scanning

```bash
# Run security scanning
terraform plan -target=module.security

# Validate security configuration
aws configservice get-compliance-details-by-config-rule \
  --config-rule-name encrypted-volumes
```

### Manual Security Review

1. **IAM Policy Review**
   - Verify least privilege access
   - Check for overly permissive policies
   - Review cross-service access

2. **Network Security Review**
   - Validate security group rules
   - Check for open ports
   - Verify VPC configuration

3. **Encryption Review**
   - Confirm KMS key usage
   - Verify encryption at rest
   - Check TLS configuration

## Contributing

When contributing to this module:

1. **Security Testing**: Test all security configurations thoroughly
2. **Compliance**: Ensure changes meet compliance requirements
3. **Documentation**: Update README for any new features
4. **Validation**: Add proper variable validation
5. **Examples**: Provide usage examples for new features

## Support

For security-related issues:

1. **Security Incidents**: Follow your organization's incident response procedures
2. **Configuration Issues**: Check the troubleshooting section
3. **Compliance Questions**: Consult with your compliance team
4. **Feature Requests**: Open an issue in the project repository

---

**Security Notice**: This module implements defense-in-depth security controls for production workloads. Regular security reviews and updates are recommended to maintain security posture.
