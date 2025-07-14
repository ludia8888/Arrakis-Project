# Backup Module Outputs
# Output values for use by other modules and main configuration

# Backup Vault Information
output "backup_vault_name" {
  description = "Name of the primary backup vault"
  value       = aws_backup_vault.main.name
}

output "backup_vault_arn" {
  description = "ARN of the primary backup vault"
  value       = aws_backup_vault.main.arn
}

output "backup_vault_recovery_points" {
  description = "Number of recovery points in the backup vault"
  value       = aws_backup_vault.main.recovery_points
}

output "cross_region_backup_vault_name" {
  description = "Name of the cross-region backup vault"
  value       = local.config.cross_region_backup_enabled ? aws_backup_vault.cross_region[0].name : null
}

output "cross_region_backup_vault_arn" {
  description = "ARN of the cross-region backup vault"
  value       = local.config.cross_region_backup_enabled ? aws_backup_vault.cross_region[0].arn : null
}

# Backup Plan Information
output "backup_plan_id" {
  description = "ID of the backup plan"
  value       = aws_backup_plan.main.id
}

output "backup_plan_arn" {
  description = "ARN of the backup plan"
  value       = aws_backup_plan.main.arn
}

output "backup_plan_version" {
  description = "Version of the backup plan"
  value       = aws_backup_plan.main.version
}

output "backup_plan_name" {
  description = "Name of the backup plan"
  value       = aws_backup_plan.main.name
}

# KMS Key Information
output "backup_kms_key_id" {
  description = "ID of the KMS key used for backup encryption"
  value       = aws_kms_key.backup.key_id
}

output "backup_kms_key_arn" {
  description = "ARN of the KMS key used for backup encryption"
  value       = aws_kms_key.backup.arn
}

output "backup_kms_alias_name" {
  description = "Name of the KMS key alias"
  value       = aws_kms_alias.backup.name
}

output "backup_kms_alias_arn" {
  description = "ARN of the KMS key alias"
  value       = aws_kms_alias.backup.arn
}

output "cross_region_kms_key_id" {
  description = "ID of the cross-region KMS key"
  value       = local.config.cross_region_backup_enabled ? aws_kms_key.backup_replica[0].key_id : null
}

output "cross_region_kms_key_arn" {
  description = "ARN of the cross-region KMS key"
  value       = local.config.cross_region_backup_enabled ? aws_kms_key.backup_replica[0].arn : null
}

# IAM Role Information
output "backup_role_arn" {
  description = "ARN of the IAM role used by AWS Backup service"
  value       = aws_iam_role.backup.arn
}

output "backup_role_name" {
  description = "Name of the IAM role used by AWS Backup service"
  value       = aws_iam_role.backup.name
}

output "backup_validator_role_arn" {
  description = "ARN of the backup validator Lambda role"
  value       = var.enable_backup_validation ? aws_iam_role.backup_validator[0].arn : null
}

# Backup Selection Information
output "rds_backup_selection_id" {
  description = "ID of the RDS backup selection"
  value       = length(var.rds_instances) > 0 ? aws_backup_selection.rds[0].id : null
}

output "ebs_backup_selection_id" {
  description = "ID of the EBS backup selection"
  value       = aws_backup_selection.ebs.id
}

output "efs_backup_selection_id" {
  description = "ID of the EFS backup selection"
  value       = var.backup_efs_enabled ? aws_backup_selection.efs[0].id : null
}

# Notification Information
output "backup_notifications_topic_arn" {
  description = "ARN of the SNS topic for backup notifications"
  value       = var.enable_backup_notifications ? aws_sns_topic.backup_notifications[0].arn : null
}

output "backup_notifications_topic_name" {
  description = "Name of the SNS topic for backup notifications"
  value       = var.enable_backup_notifications ? aws_sns_topic.backup_notifications[0].name : null
}

# Lambda Function Information
output "backup_validator_function_arn" {
  description = "ARN of the backup validator Lambda function"
  value       = var.enable_backup_validation ? aws_lambda_function.backup_validator[0].arn : null
}

output "backup_validator_function_name" {
  description = "Name of the backup validator Lambda function"
  value       = var.enable_backup_validation ? aws_lambda_function.backup_validator[0].function_name : null
}

# CloudWatch Alarms
output "backup_failed_alarm_arn" {
  description = "ARN of the backup job failed CloudWatch alarm"
  value       = var.enable_backup_monitoring ? aws_cloudwatch_metric_alarm.backup_job_failed[0].arn : null
}

output "backup_vault_size_alarm_arn" {
  description = "ARN of the backup vault size CloudWatch alarm"
  value       = var.enable_backup_monitoring ? aws_cloudwatch_metric_alarm.backup_vault_size[0].arn : null
}

# EventBridge Rules
output "backup_job_success_rule_arn" {
  description = "ARN of the backup job success EventBridge rule"
  value       = var.enable_backup_notifications ? aws_cloudwatch_event_rule.backup_job_success[0].arn : null
}

output "backup_job_failed_rule_arn" {
  description = "ARN of the backup job failed EventBridge rule"
  value       = var.enable_backup_notifications ? aws_cloudwatch_event_rule.backup_job_failed[0].arn : null
}

output "backup_validation_rule_arn" {
  description = "ARN of the backup validation EventBridge rule"
  value       = var.enable_backup_validation ? aws_cloudwatch_event_rule.backup_validation[0].arn : null
}

# Backup Configuration Summary
output "backup_configuration" {
  description = "Summary of backup configuration"
  value = {
    vault_name                     = aws_backup_vault.main.name
    plan_name                     = aws_backup_plan.main.name
    daily_schedule                = local.final_schedule
    weekly_schedule               = var.weekly_backup_schedule
    monthly_schedule              = var.monthly_backup_schedule
    daily_retention_days          = local.final_delete_after_days
    weekly_retention_days         = var.long_term_retention_days
    monthly_retention_days        = var.archival_retention_days
    cold_storage_days             = local.final_cold_storage_days
    cross_region_backup_enabled   = local.config.cross_region_backup_enabled
    encryption_enabled            = var.enable_backup_encryption
    notifications_enabled         = var.enable_backup_notifications
    monitoring_enabled            = var.enable_backup_monitoring
    validation_enabled            = var.enable_backup_validation
    vault_lock_enabled            = local.config.backup_vault_lock_enabled
  }
}

# Resource Counts
output "backup_resource_counts" {
  description = "Count of backup-related resources created"
  value = {
    backup_vaults           = local.config.cross_region_backup_enabled ? 2 : 1
    backup_plans           = 1
    backup_selections      = length(var.rds_instances) > 0 ? (var.backup_efs_enabled ? 3 : 2) : (var.backup_efs_enabled ? 2 : 1)
    kms_keys              = local.config.cross_region_backup_enabled ? 2 : 1
    iam_roles             = var.enable_backup_validation ? 2 : 1
    lambda_functions      = var.enable_backup_validation ? 1 : 0
    sns_topics            = var.enable_backup_notifications ? 1 : 0
    cloudwatch_alarms     = var.enable_backup_monitoring ? 2 : 0
    eventbridge_rules     = var.enable_backup_notifications ? (var.enable_backup_validation ? 3 : 2) : (var.enable_backup_validation ? 1 : 0)
  }
}

# Backup Schedule Information
output "backup_schedules" {
  description = "Backup schedule configuration"
  value = {
    daily = {
      schedule = local.final_schedule
      retention_days = local.final_delete_after_days
      cold_storage_days = local.final_cold_storage_days
    }
    weekly = {
      schedule = var.weekly_backup_schedule
      retention_days = var.long_term_retention_days
      cold_storage_days = var.weekly_cold_storage_days
    }
    monthly = {
      schedule = var.monthly_backup_schedule
      retention_days = var.archival_retention_days
      cold_storage_days = 30
    }
  }
}

# Compliance and Security Status
output "compliance_status" {
  description = "Backup compliance and security status"
  value = {
    encryption_at_rest            = var.enable_backup_encryption
    vault_lock_enabled           = local.config.backup_vault_lock_enabled
    cross_region_backup          = local.config.cross_region_backup_enabled
    point_in_time_recovery       = var.enable_point_in_time_recovery
    continuous_backup            = var.enable_continuous_backup
    compliance_mode              = var.compliance_mode
    min_retention_days           = var.min_retention_days
    max_retention_days           = var.max_retention_days
    aws_config_integration       = var.enable_aws_config_integration
    cloudtrail_integration       = var.enable_cloudtrail_integration
    backup_deduplication         = var.enable_backup_deduplication
    backup_compression           = var.backup_compression_enabled
  }
}

# Recovery Objectives
output "recovery_objectives" {
  description = "Recovery Point and Time Objectives"
  value = {
    rpo_target_hours = var.rpo_target_hours
    rto_target_hours = var.rto_target_hours
    backup_window_start = var.backup_window_start_hour
    backup_window_duration = var.backup_window_duration_hours
    backup_job_timeout_minutes = var.backup_job_timeout_minutes
  }
}

# Cost Information
output "cost_optimization" {
  description = "Cost optimization configuration"
  value = {
    intelligent_tiering_enabled = var.enable_intelligent_tiering
    cold_storage_transition_days = local.final_cold_storage_days
    weekly_cold_storage_days = var.weekly_cold_storage_days
    compression_enabled = var.backup_compression_enabled
    deduplication_enabled = var.enable_backup_deduplication
    performance_mode = var.backup_performance_mode
    cost_allocation_tags = var.backup_cost_allocation_tags
  }
}

# Cross-Account Information
output "cross_account_configuration" {
  description = "Cross-account backup sharing configuration"
  value = {
    enabled = var.enable_cross_account_backup
    shared_accounts = var.cross_account_backup_accounts
  }
}

# Resource Filters
output "backup_resource_filters" {
  description = "Backup resource selection filters"
  value = var.backup_resource_filters
}

# Monitoring and Alerting
output "monitoring_configuration" {
  description = "Monitoring and alerting configuration"
  value = {
    notifications_enabled = var.enable_backup_notifications
    notification_email = var.notification_email
    monitoring_enabled = var.enable_backup_monitoring
    max_concurrent_backups = var.max_concurrent_backups
    validation_enabled = var.enable_backup_validation
    validation_schedule = var.backup_validation_schedule
  }
}

# Integration Status
output "integration_status" {
  description = "Status of integrations with other AWS services"
  value = {
    aws_config = var.enable_aws_config_integration
    cloudtrail = var.enable_cloudtrail_integration
    systems_manager = var.enable_systems_manager_integration
  }
}

# Account and Region Information
output "account_id" {
  description = "AWS Account ID"
  value       = data.aws_caller_identity.current.account_id
}

output "primary_region" {
  description = "Primary AWS Region"
  value       = data.aws_region.current.name
}

output "replica_region" {
  description = "Replica AWS Region for cross-region backups"
  value       = var.replica_region
}

# Tags Information
output "backup_tags" {
  description = "Tags applied to backup resources"
  value = merge(
    var.tags,
    var.additional_backup_tags,
    var.backup_cost_allocation_tags,
    {
      Project = var.project_name
      Environment = var.environment
      Module = "backup"
    }
  )
}

# Backup Protection Status
output "backup_protection_status" {
  description = "Status of backup protection for resources"
  value = {
    rds_instances_protected = length(var.rds_instances)
    ebs_volumes_protected = true
    efs_filesystems_protected = var.backup_efs_enabled
    total_backup_selections = length(var.rds_instances) > 0 ? (var.backup_efs_enabled ? 3 : 2) : (var.backup_efs_enabled ? 2 : 1)
  }
}