# Backup Terraform Module

Comprehensive backup infrastructure for the Arrakis platform with enterprise-grade backup strategies, automated validation, cross-region replication, and compliance monitoring.

## Features

- **AWS Backup Service**: Centralized backup management with automated scheduling
- **Multi-Resource Support**: RDS, EBS, EFS backup with intelligent resource selection
- **Cross-Region Backup**: Disaster recovery with automated replication
- **Backup Validation**: Automated verification with Lambda-based validation
- **Compliance Monitoring**: Built-in compliance checks and reporting
- **Cost Optimization**: Intelligent tiering and lifecycle management
- **Security**: End-to-end encryption with customer-managed KMS keys
- **Monitoring & Alerting**: CloudWatch alarms and SNS notifications

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Backup Architecture                      │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │
│  │   Primary     │  │   Cross-      │  │   Backup      │   │
│  │   Backup      │  │   Region      │  │   Plans &     │   │
│  │   Vault       │  │   Vault       │  │   Schedules   │   │
│  │               │  │               │  │               │   │
│  │ • KMS         │  │ • Replica     │  │ • Daily       │   │
│  │   Encryption  │  │   Backup      │  │ • Weekly      │   │
│  │ • Vault Lock  │  │ • DR Ready    │  │ • Monthly     │   │
│  │ • Monitoring  │  │ • Compliance  │  │ • Lifecycle   │   │
│  └───────────────┘  └───────────────┘  └───────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │
│  │   Resource    │  │   Validation  │  │   Monitoring  │   │
│  │   Selection   │  │   & Testing   │  │   & Alerts    │   │
│  │               │  │               │  │               │   │
│  │ • RDS DBs     │  │ • Lambda      │  │ • CloudWatch  │   │
│  │ • EBS Vols    │  │   Validator   │  │   Alarms      │   │
│  │ • EFS Files   │  │ • Automated   │  │ • SNS Topics  │   │
│  │ • Tag-based   │  │   Reports     │  │ • EventBridge │   │
│  └───────────────┘  └───────────────┘  └───────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

```hcl
module "backup" {
  source = "./modules/backup"

  project_name = "arrakis"
  environment  = "production"

  backup_vault_name = "arrakis-backup-vault-production"
  backup_plan_name  = "arrakis-backup-plan-production"

  # RDS instances to backup
  rds_instances = [
    {
      identifier = "arrakis-oms-production"
      arn        = "arn:aws:rds:us-west-2:123456789012:db:arrakis-oms-production"
    }
  ]

  # Notifications
  notification_email = "ops@company.com"

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
| `backup_vault_name` | Name of the AWS Backup vault | `string` | - | yes |
| `backup_plan_name` | Name of the AWS Backup plan | `string` | - | yes |

### Backup Scheduling

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `backup_schedule` | Daily backup cron expression | `string` | Environment-based |
| `weekly_backup_schedule` | Weekly backup cron expression | `string` | `"cron(0 1 ? * SUN *)"` |
| `monthly_backup_schedule` | Monthly backup cron expression | `string` | `"cron(0 1 1 * ? *)"` |

### Retention Configuration

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `delete_after_days` | Daily backup retention (days) | `number` | Environment-based |
| `move_to_cold_storage_after_days` | Cold storage transition (days) | `number` | Environment-based |
| `long_term_retention_days` | Weekly backup retention (days) | `number` | `365` |
| `archival_retention_days` | Monthly backup retention (days) | `number` | `2555` (7 years) |

### Security Configuration

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `enable_backup_encryption` | Enable encryption for backups | `bool` | `true` |
| `kms_deletion_window` | KMS key deletion window (days) | `number` | `7` |
| `compliance_mode` | Backup vault compliance mode | `string` | `"GOVERNANCE"` |

### Monitoring Configuration

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `enable_backup_notifications` | Enable SNS notifications | `bool` | `true` |
| `notification_email` | Email for backup notifications | `string` | `""` |
| `enable_backup_monitoring` | Enable CloudWatch monitoring | `bool` | `true` |
| `enable_backup_validation` | Enable Lambda validation | `bool` | `true` |

## Environment-Specific Defaults

The module automatically configures backup strategies based on environment:

### Development
- **Schedule**: Daily at 3 AM
- **Retention**: 7 days
- **Cold Storage**: Disabled
- **Cross-Region**: Disabled
- **Vault Lock**: Disabled

### Staging
- **Schedule**: Daily at 2 AM
- **Retention**: 30 days
- **Cold Storage**: 7 days
- **Cross-Region**: Enabled
- **Vault Lock**: Disabled

### Production
- **Schedule**: Daily at 1 AM
- **Retention**: 90 days
- **Cold Storage**: 30 days
- **Cross-Region**: Enabled
- **Vault Lock**: Enabled (WORM compliance)

## Backup Strategies

### Daily Backups
- **Purpose**: Operational recovery
- **Schedule**: Configurable (default: environment-based)
- **Retention**: 7-90 days based on environment
- **Storage**: Standard → Cold storage transition

### Weekly Backups
- **Purpose**: Business continuity
- **Schedule**: Every Sunday at 1 AM
- **Retention**: 365 days (1 year)
- **Storage**: Cold storage after 90 days

### Monthly Backups
- **Purpose**: Long-term archival
- **Schedule**: First day of month at 1 AM
- **Retention**: 2,555 days (7 years)
- **Storage**: Cold storage after 30 days

## Resource Selection

### RDS Instances
```hcl
rds_instances = [
  {
    identifier = "arrakis-oms-production"
    arn        = "arn:aws:rds:us-west-2:123456789012:db:arrakis-oms-production"
  }
]
```

### EBS Volumes
Automatically backs up EBS volumes tagged with:
- `KubernetesCluster`: `${project_name}-${environment}`
- `Environment`: `${environment}`
- Excludes volumes tagged with `VolumeType`: `temporary`

### EFS File Systems
```hcl
backup_efs_enabled = true
```

## Cross-Region Backup

For disaster recovery, the module supports cross-region backup replication:

```hcl
# Enabled automatically for staging/production
# Primary region: Current region
# Replica region: us-east-1 (configurable)

replica_region = "us-east-1"
```

### Cross-Region Features
- **Automatic Replication**: Copy jobs to replica region
- **Independent KMS Keys**: Separate encryption keys per region
- **Same Retention**: Identical lifecycle policies
- **Production Only**: Monthly backups replicated only in production

## Backup Validation

### Automated Validation
The module includes a Lambda function that validates:

- **Backup Job Success**: Monitors job completion status
- **Performance Issues**: Identifies long-running or stuck jobs
- **Recovery Point Integrity**: Validates availability and encryption
- **Compliance**: Checks RPO/RTO requirements

### Validation Schedule
```hcl
backup_validation_schedule = "cron(0 6 * * ? *)"  # Daily at 6 AM
```

### Validation Reports
The validator generates comprehensive reports including:
- Job success/failure rates
- Performance metrics
- Compliance status
- Resource coverage
- Issue identification

## Security Features

### Encryption
- **Customer-Managed KMS Keys**: Separate keys for backup and cross-region
- **Key Rotation**: Automatic annual rotation
- **Access Control**: Principle of least privilege

### Vault Lock (Production)
```hcl
# Automatically enabled for production
backup_vault_lock_enabled = true
min_retention_days = 30
max_retention_days = 36500  # 100 years
```

### Compliance
- **WORM Compliance**: Write-Once-Read-Many for immutable backups
- **Audit Logging**: Integration with CloudTrail
- **Access Controls**: IAM policies and resource-based policies

## Monitoring & Alerting

### CloudWatch Alarms
- **Failed Backup Jobs**: Alert on any failed backups
- **Backup Vault Size**: Monitor concurrent backup limits
- **Performance**: Track backup duration and throughput

### SNS Notifications
```hcl
enable_backup_notifications = true
notification_email = "ops@company.com"
```

### EventBridge Integration
- **Job State Changes**: Monitor backup job lifecycle
- **Validation Triggers**: Automated validation scheduling
- **Custom Actions**: Extensible event handling

## Cost Optimization

### Storage Tiering
```hcl
enable_intelligent_tiering = true
move_to_cold_storage_after_days = 30
```

### Optimization Features
- **Intelligent Tiering**: Automatic storage class transitions
- **Deduplication**: Reduce storage costs
- **Compression**: Minimize backup sizes
- **Lifecycle Management**: Automated cleanup

### Cost Allocation
```hcl
backup_cost_allocation_tags = {
  CostCenter = "backup-operations"
  Owner      = "platform-team"
}
```

## Disaster Recovery

### Recovery Objectives
```hcl
rpo_target_hours = 24  # Recovery Point Objective
rto_target_hours = 4   # Recovery Time Objective
```

### DR Capabilities
- **Cross-Region Replication**: Automated backup copies
- **Point-in-Time Recovery**: Granular recovery options
- **Continuous Backup**: Real-time protection for supported resources
- **Validation Testing**: Automated recovery verification

## Usage Examples

### Production Environment

```hcl
module "backup" {
  source = "./modules/backup"

  project_name = "arrakis"
  environment  = "production"

  backup_vault_name = "arrakis-backup-vault-production"
  backup_plan_name  = "arrakis-backup-plan-production"

  # All RDS instances
  rds_instances = [
    {
      identifier = "arrakis-oms-production"
      arn        = module.databases.database_instances["oms_db"].arn
    },
    {
      identifier = "arrakis-user-production"
      arn        = module.databases.database_instances["user_db"].arn
    }
  ]

  # Enhanced security
  compliance_mode = "COMPLIANCE"
  enable_backup_encryption = true

  # Monitoring
  enable_backup_notifications = true
  notification_email = "ops@company.com"
  enable_backup_monitoring = true
  enable_backup_validation = true

  # Cost optimization
  enable_intelligent_tiering = true
  enable_backup_deduplication = true
  backup_compression_enabled = true

  # Disaster recovery
  replica_region = "us-east-1"
  rpo_target_hours = 24
  rto_target_hours = 4

  tags = {
    Environment     = "production"
    Project         = "arrakis"
    BusinessUnit    = "platform"
    CostCenter      = "infrastructure"
    SecurityLevel   = "high"
    ComplianceReq   = "soc2,gdpr"
  }
}
```

### Multi-Environment Setup

```hcl
locals {
  environments = {
    development = {
      backup_schedule = "cron(0 3 * * ? *)"
      retention_days = 7
      enable_cross_region = false
      notification_level = "errors_only"
    }
    staging = {
      backup_schedule = "cron(0 2 * * ? *)"
      retention_days = 30
      enable_cross_region = true
      notification_level = "warnings_and_errors"
    }
    production = {
      backup_schedule = "cron(0 1 * * ? *)"
      retention_days = 90
      enable_cross_region = true
      notification_level = "all"
    }
  }
}

module "backup" {
  source = "./modules/backup"

  project_name = "arrakis"
  environment  = var.environment

  backup_vault_name = "arrakis-backup-vault-${var.environment}"
  backup_plan_name  = "arrakis-backup-plan-${var.environment}"

  # Environment-specific configuration
  backup_schedule = local.environments[var.environment].backup_schedule
  delete_after_days = local.environments[var.environment].retention_days

  # Cross-region based on environment
  replica_region = local.environments[var.environment].enable_cross_region ? "us-east-1" : null

  # Monitoring based on environment
  notification_email = var.notification_email
  enable_backup_notifications = true

  tags = merge(local.common_tags, {
    Environment = var.environment
  })
}
```

## Operations

### Monitoring Backup Status

```bash
# Check backup jobs
aws backup list-backup-jobs \
  --by-backup-vault-name arrakis-backup-vault-production

# Check recovery points
aws backup list-recovery-points-by-backup-vault \
  --backup-vault-name arrakis-backup-vault-production

# View backup vault details
aws backup describe-backup-vault \
  --backup-vault-name arrakis-backup-vault-production
```

### Manual Backup Operations

```bash
# Start on-demand backup
aws backup start-backup-job \
  --backup-vault-name arrakis-backup-vault-production \
  --resource-arn arn:aws:rds:us-west-2:123456789012:db:arrakis-oms-production \
  --iam-role-arn arn:aws:iam::123456789012:role/arrakis-backup-role-production

# Restore from backup
aws backup start-restore-job \
  --recovery-point-arn arn:aws:backup:us-west-2:123456789012:recovery-point:12345678-1234-1234-1234-123456789012 \
  --metadata OriginalInstanceClass=db.t3.medium \
  --iam-role-arn arn:aws:iam::123456789012:role/arrakis-backup-role-production
```

### Validation and Testing

```bash
# Invoke backup validator manually
aws lambda invoke \
  --function-name arrakis-backup-validator-production \
  --payload '{"send_full_report": true}' \
  response.json

# Check validation logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/arrakis-backup-validator-production \
  --start-time $(date -d '1 hour ago' +%s)000
```

## Troubleshooting

### Common Issues

1. **Backup Jobs Failing**
   ```bash
   # Check IAM permissions
   aws iam simulate-principal-policy \
     --policy-source-arn arn:aws:iam::123456789012:role/arrakis-backup-role-production \
     --action-names backup:StartBackupJob \
     --resource-arns arn:aws:rds:us-west-2:123456789012:db:arrakis-oms-production
   ```

2. **Cross-Region Backup Issues**
   ```bash
   # Check KMS key permissions
   aws kms describe-key \
     --key-id alias/arrakis-backup-replica-production \
     --region us-east-1
   ```

3. **Validation Function Errors**
   ```bash
   # Check Lambda logs
   aws logs describe-log-groups \
     --log-group-name-prefix /aws/lambda/arrakis-backup-validator
   ```

### Performance Optimization

1. **Backup Window Optimization**
   - Adjust backup schedules to avoid peak hours
   - Distribute backup times across resources
   - Monitor backup duration and performance

2. **Storage Cost Optimization**
   - Review cold storage transition settings
   - Implement intelligent tiering
   - Regular cleanup of old recovery points

3. **Network Optimization**
   - Consider backup bandwidth requirements
   - Schedule backups during low-traffic periods
   - Monitor cross-region transfer costs

## Compliance and Governance

### Supported Standards
- **SOC 2**: Automated backup and retention controls
- **GDPR**: Data protection and retention policies
- **HIPAA**: Healthcare data backup requirements
- **PCI DSS**: Payment data protection standards

### Audit Features
- **CloudTrail Integration**: All backup operations logged
- **Config Rules**: Compliance monitoring and reporting
- **Access Logging**: Detailed backup access tracking
- **Retention Policies**: Automated data lifecycle management

## Security Best Practices

### 1. Encryption Everywhere
- Customer-managed KMS keys for all backups
- Separate keys for primary and cross-region backups
- Regular key rotation and access review

### 2. Access Controls
- Principle of least privilege for backup roles
- Resource-based policies for backup vaults
- Multi-factor authentication for critical operations

### 3. Network Security
- VPC endpoints for backup API calls
- Private subnets for backup infrastructure
- Network access controls and monitoring

### 4. Incident Response
- Automated alerting for backup failures
- Runbooks for common backup scenarios
- Regular disaster recovery testing

## Contributing

When contributing to this module:

1. **Testing**: Validate backup and restore operations
2. **Documentation**: Update README for new features
3. **Security**: Follow security best practices
4. **Compliance**: Ensure compliance requirements are met
5. **Performance**: Test backup performance and costs

## Support

For backup-related issues:

1. **Operational Issues**: Check CloudWatch alarms and SNS notifications
2. **Performance Issues**: Review backup job duration and resource utilization
3. **Compliance Questions**: Consult with compliance and security teams
4. **Cost Optimization**: Analyze backup storage costs and lifecycle policies

---

**Backup Notice**: This module implements enterprise-grade backup strategies with automated validation and compliance monitoring. Regular testing and validation of backup and restore procedures is essential for maintaining data protection and business continuity.
