# Security Module Outputs
# Output values for use by other modules and main configuration

# IAM Roles and Policies
output "iam_roles" {
  description = "Map of service account IAM roles"
  value = {
    for sa_name, sa_config in local.service_accounts :
    sa_name => {
      role_arn  = aws_iam_role.service_account[sa_name].arn
      role_name = aws_iam_role.service_account[sa_name].name
      namespace = sa_config.namespace
    }
  }
}

output "service_account_role_arns" {
  description = "ARNs of all service account IAM roles"
  value = {
    for name, role in aws_iam_role.service_account : name => role.arn
  }
}

output "irsa_roles" {
  description = "IRSA role mapping for Kubernetes service accounts"
  value = {
    for sa_name, sa_config in local.service_accounts :
    sa_name => {
      role_arn                = aws_iam_role.service_account[sa_name].arn
      service_account_name    = sa_name
      namespace              = sa_config.namespace
      annotation_key         = "eks.amazonaws.com/role-arn"
      annotation_value       = aws_iam_role.service_account[sa_name].arn
    }
  }
}

# KMS and Encryption
output "kms_key_id" {
  description = "ID of the KMS key for secrets encryption"
  value       = aws_kms_key.secrets.key_id
}

output "kms_key_arn" {
  description = "ARN of the KMS key for secrets encryption"
  value       = aws_kms_key.secrets.arn
}

output "kms_alias_name" {
  description = "Name of the KMS key alias"
  value       = aws_kms_alias.secrets.name
}

output "kms_alias_arn" {
  description = "ARN of the KMS key alias"
  value       = aws_kms_alias.secrets.arn
}

# Secrets Management
output "secrets" {
  description = "Map of created secrets and their metadata"
  value = {
    for name, secret in aws_secretsmanager_secret.secrets :
    name => {
      arn          = secret.arn
      name         = secret.name
      version_id   = aws_secretsmanager_secret_version.secrets[name].version_id
      kms_key_id   = secret.kms_key_id
    }
  }
}

output "secret_arns" {
  description = "ARNs of all created secrets"
  value = {
    for name, secret in aws_secretsmanager_secret.secrets : name => secret.arn
  }
}

output "secret_names" {
  description = "Names of all created secrets"
  value = {
    for name, secret in aws_secretsmanager_secret.secrets : name => secret.name
  }
}

# Security Groups
output "microservices_security_group_id" {
  description = "Security group ID for microservices"
  value       = aws_security_group.microservices.id
}

output "microservices_security_group_arn" {
  description = "Security group ARN for microservices"
  value       = aws_security_group.microservices.arn
}

output "database_access_security_group_id" {
  description = "Security group ID for database access"
  value       = aws_security_group.database_access.id
}

output "database_access_security_group_arn" {
  description = "Security group ARN for database access"
  value       = aws_security_group.database_access.arn
}

output "security_groups" {
  description = "Map of all security groups"
  value = {
    microservices    = {
      id  = aws_security_group.microservices.id
      arn = aws_security_group.microservices.arn
    }
    database_access = {
      id  = aws_security_group.database_access.id
      arn = aws_security_group.database_access.arn
    }
  }
}

# CloudTrail and Audit Logging
output "cloudtrail_arn" {
  description = "ARN of the CloudTrail"
  value       = var.enable_cloudtrail ? aws_cloudtrail.security_audit[0].arn : null
}

output "cloudtrail_bucket_name" {
  description = "Name of the CloudTrail S3 bucket"
  value       = var.enable_cloudtrail ? aws_s3_bucket.cloudtrail_logs[0].bucket : null
}

output "cloudtrail_bucket_arn" {
  description = "ARN of the CloudTrail S3 bucket"
  value       = var.enable_cloudtrail ? aws_s3_bucket.cloudtrail_logs[0].arn : null
}

# AWS Config
output "config_recorder_name" {
  description = "Name of the AWS Config recorder"
  value       = var.enable_aws_config ? aws_config_configuration_recorder.security[0].name : null
}

output "config_delivery_channel_name" {
  description = "Name of the AWS Config delivery channel"
  value       = var.enable_aws_config ? aws_config_delivery_channel.security[0].name : null
}

output "config_bucket_name" {
  description = "Name of the AWS Config S3 bucket"
  value       = var.enable_aws_config ? aws_s3_bucket.config_logs[0].bucket : null
}

# GuardDuty
output "guardduty_detector_id" {
  description = "ID of the GuardDuty detector"
  value       = var.enable_guardduty ? aws_guardduty_detector.security[0].id : null
}

output "guardduty_detector_arn" {
  description = "ARN of the GuardDuty detector"
  value       = var.enable_guardduty ? aws_guardduty_detector.security[0].arn : null
}

# Security Hub
output "security_hub_account_id" {
  description = "Account ID for Security Hub"
  value       = var.enable_security_hub ? aws_securityhub_account.security[0].id : null
}

# Security Configuration Summary
output "security_configuration" {
  description = "Summary of security configuration"
  value = {
    kms_encryption_enabled      = true
    secrets_management_enabled  = true
    cloudtrail_enabled         = var.enable_cloudtrail
    aws_config_enabled         = var.enable_aws_config
    guardduty_enabled          = var.enable_guardduty
    security_hub_enabled       = var.enable_security_hub
    kubernetes_audit_enabled   = var.enable_kubernetes_audit_logs
    compliance_standards       = var.compliance_standards
    encryption_at_rest         = var.enable_encryption_at_rest
    encryption_in_transit      = var.enable_encryption_in_transit
  }
}

# Service Account Annotations for Kubernetes
output "service_account_annotations" {
  description = "Annotations to be applied to Kubernetes service accounts"
  value = {
    for sa_name, sa_config in local.service_accounts :
    sa_name => {
      "eks.amazonaws.com/role-arn" = aws_iam_role.service_account[sa_name].arn
    }
  }
}

# Security Policies
output "security_policies" {
  description = "Map of security policies and their ARNs"
  value = {
    for sa_name in keys(local.service_accounts) :
    sa_name => {
      custom_policy_arn = lookup(aws_iam_role_policy.service_account_custom, sa_name, null) != null ? 
                         aws_iam_role_policy.service_account_custom[sa_name].arn : null
      managed_policies  = lookup(local.service_accounts, sa_name, {}).policies
    }
  }
}

# Account and Region Information
output "account_id" {
  description = "AWS Account ID"
  value       = data.aws_caller_identity.current.account_id
}

output "region" {
  description = "AWS Region"
  value       = data.aws_region.current.name
}

# Security Monitoring Status
output "security_monitoring_status" {
  description = "Status of security monitoring services"
  value = {
    cloudtrail = {
      enabled      = var.enable_cloudtrail
      bucket_name  = var.enable_cloudtrail ? aws_s3_bucket.cloudtrail_logs[0].bucket : null
      trail_arn    = var.enable_cloudtrail ? aws_cloudtrail.security_audit[0].arn : null
    }
    guardduty = {
      enabled     = var.enable_guardduty
      detector_id = var.enable_guardduty ? aws_guardduty_detector.security[0].id : null
    }
    config = {
      enabled           = var.enable_aws_config
      recorder_name     = var.enable_aws_config ? aws_config_configuration_recorder.security[0].name : null
      delivery_channel  = var.enable_aws_config ? aws_config_delivery_channel.security[0].name : null
    }
    security_hub = {
      enabled    = var.enable_security_hub
      account_id = var.enable_security_hub ? aws_securityhub_account.security[0].id : null
    }
  }
}

# Compliance Information
output "compliance_status" {
  description = "Compliance standards and their status"
  value = {
    enabled_standards = var.compliance_standards
    security_hub_standards = var.enable_security_hub ? {
      cis_enabled = contains(var.compliance_standards, "cis")
      pci_enabled = contains(var.compliance_standards, "pci-dss")
    } : {}
    encryption_compliance = {
      at_rest    = var.enable_encryption_at_rest
      in_transit = var.enable_encryption_in_transit
      kms_key_rotation = true
    }
  }
}

# Backup and Recovery
output "backup_configuration" {
  description = "Backup and recovery configuration"
  value = {
    cross_region_backup_enabled = var.enable_cross_region_backup
    secret_recovery_window      = var.secret_recovery_window
    backup_retention_days       = var.backup_retention_days
    replica_region             = var.replica_region
    kms_deletion_window        = var.kms_deletion_window
  }
}

# Cost and Resource Information
output "resource_counts" {
  description = "Count of security resources created"
  value = {
    iam_roles          = length(aws_iam_role.service_account)
    secrets            = length(aws_secretsmanager_secret.secrets)
    security_groups    = 2  # microservices + database_access
    kms_keys          = 1
    cloudtrail_trails = var.enable_cloudtrail ? 1 : 0
    guardduty_detectors = var.enable_guardduty ? 1 : 0
    config_recorders   = var.enable_aws_config ? 1 : 0
  }
}

# Network Security Information
output "network_security" {
  description = "Network security configuration"
  value = {
    vpc_id                = var.vpc_id
    vpc_cidr             = var.vpc_cidr
    microservices_sg_id  = aws_security_group.microservices.id
    database_access_sg_id = aws_security_group.database_access.id
    allowed_ports = {
      http_range    = "${var.microservices_ports.http_start}-${var.microservices_ports.http_end}"
      grpc_range    = "${var.microservices_ports.grpc_start}-${var.microservices_ports.grpc_end}"
      metrics_port  = var.microservices_ports.metrics_port
    }
  }
}

# Service-Specific Role Information
output "ontology_management_service_role" {
  description = "Role information for ontology-management-service"
  value = {
    arn       = aws_iam_role.service_account["ontology-management-service"].arn
    name      = aws_iam_role.service_account["ontology-management-service"].name
    namespace = "arrakis"
  }
}

output "user_service_role" {
  description = "Role information for user-service"
  value = {
    arn       = aws_iam_role.service_account["user-service"].arn
    name      = aws_iam_role.service_account["user-service"].name
    namespace = "arrakis"
  }
}

output "audit_service_role" {
  description = "Role information for audit-service"
  value = {
    arn       = aws_iam_role.service_account["audit-service"].arn
    name      = aws_iam_role.service_account["audit-service"].name
    namespace = "arrakis"
  }
}

output "data_kernel_service_role" {
  description = "Role information for data-kernel-service"
  value = {
    arn       = aws_iam_role.service_account["data-kernel-service"].arn
    name      = aws_iam_role.service_account["data-kernel-service"].name
    namespace = "arrakis"
  }
}

output "embedding_service_role" {
  description = "Role information for embedding-service"
  value = {
    arn       = aws_iam_role.service_account["embedding-service"].arn
    name      = aws_iam_role.service_account["embedding-service"].name
    namespace = "arrakis"
  }
}

output "scheduler_service_role" {
  description = "Role information for scheduler-service"
  value = {
    arn       = aws_iam_role.service_account["scheduler-service"].arn
    name      = aws_iam_role.service_account["scheduler-service"].name
    namespace = "arrakis"
  }
}

output "event_gateway_role" {
  description = "Role information for event-gateway"
  value = {
    arn       = aws_iam_role.service_account["event-gateway"].arn
    name      = aws_iam_role.service_account["event-gateway"].name
    namespace = "arrakis"
  }
}

# Integration Information
output "kubernetes_integration" {
  description = "Information for Kubernetes integration"
  value = {
    cluster_name           = var.cluster_name
    oidc_issuer_url       = var.cluster_oidc_issuer_url
    service_account_roles = {
      for sa_name in keys(local.service_accounts) :
      sa_name => {
        namespace     = local.service_accounts[sa_name].namespace
        role_arn      = aws_iam_role.service_account[sa_name].arn
        annotations   = {
          "eks.amazonaws.com/role-arn" = aws_iam_role.service_account[sa_name].arn
        }
      }
    }
  }
}

# Security Best Practices Status
output "security_best_practices" {
  description = "Status of security best practices implementation"
  value = {
    principle_of_least_privilege = true
    defense_in_depth            = true
    encryption_everywhere       = var.enable_encryption_at_rest && var.enable_encryption_in_transit
    audit_logging              = var.enable_cloudtrail
    threat_detection           = var.enable_guardduty
    compliance_monitoring      = var.enable_aws_config
    centralized_security       = var.enable_security_hub
    key_rotation               = true
    cross_region_backup        = var.enable_cross_region_backup
    network_segmentation       = true
  }
}