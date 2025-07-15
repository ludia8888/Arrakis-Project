# Backup Module Variables
# Input variables for the backup module configuration

variable "project_name" {
  description = "Name of the project"
  type        = string
  validation {
    condition     = can(regex("^[a-zA-Z0-9-]+$", var.project_name))
    error_message = "Project name must contain only alphanumeric characters and hyphens."
  }
}

variable "environment" {
  description = "Environment name (development, staging, production)"
  type        = string
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be one of: development, staging, production."
  }
}

# Backup Configuration
variable "backup_vault_name" {
  description = "Name of the AWS Backup vault"
  type        = string
}

variable "backup_plan_name" {
  description = "Name of the AWS Backup plan"
  type        = string
}

variable "backup_schedule" {
  description = "Cron expression for backup schedule (overrides environment defaults)"
  type        = string
  default     = ""
  validation {
    condition = var.backup_schedule == "" || can(regex("^cron\\(.*\\)$", var.backup_schedule))
    error_message = "Backup schedule must be a valid cron expression in format 'cron(...)'."
  }
}

variable "weekly_backup_schedule" {
  description = "Cron expression for weekly backup schedule"
  type        = string
  default     = "cron(0 1 ? * SUN *)"  # Every Sunday at 1 AM
  validation {
    condition     = can(regex("^cron\\(.*\\)$", var.weekly_backup_schedule))
    error_message = "Weekly backup schedule must be a valid cron expression."
  }
}

variable "monthly_backup_schedule" {
  description = "Cron expression for monthly backup schedule"
  type        = string
  default     = "cron(0 1 1 * ? *)"  # First day of every month at 1 AM
  validation {
    condition     = can(regex("^cron\\(.*\\)$", var.monthly_backup_schedule))
    error_message = "Monthly backup schedule must be a valid cron expression."
  }
}

# Retention Configuration
variable "delete_after_days" {
  description = "Number of days to retain daily backups (0 uses environment defaults)"
  type        = number
  default     = 0
  validation {
    condition     = var.delete_after_days >= 0 && var.delete_after_days <= 35000
    error_message = "Delete after days must be between 0 and 35000 (approximately 100 years)."
  }
}

variable "move_to_cold_storage_after_days" {
  description = "Number of days after which backups are moved to cold storage (null disables)"
  type        = number
  default     = null
  validation {
    condition = var.move_to_cold_storage_after_days == null || (
      var.move_to_cold_storage_after_days >= 30 && var.move_to_cold_storage_after_days <= 35000
    )
    error_message = "Cold storage transition must be null or between 30 and 35000 days."
  }
}

variable "long_term_retention_days" {
  description = "Number of days to retain weekly backups"
  type        = number
  default     = 365
  validation {
    condition     = var.long_term_retention_days >= 30 && var.long_term_retention_days <= 35000
    error_message = "Long term retention must be between 30 and 35000 days."
  }
}

variable "weekly_cold_storage_days" {
  description = "Number of days after which weekly backups are moved to cold storage"
  type        = number
  default     = 90
  validation {
    condition     = var.weekly_cold_storage_days >= 30 && var.weekly_cold_storage_days <= 35000
    error_message = "Weekly cold storage transition must be between 30 and 35000 days."
  }
}

variable "archival_retention_days" {
  description = "Number of days to retain monthly archival backups"
  type        = number
  default     = 2555  # 7 years
  validation {
    condition     = var.archival_retention_days >= 90 && var.archival_retention_days <= 35000
    error_message = "Archival retention must be between 90 and 35000 days."
  }
}

# Backup Vault Security
variable "min_retention_days" {
  description = "Minimum retention days for backup vault lock"
  type        = number
  default     = 30
  validation {
    condition     = var.min_retention_days >= 1 && var.min_retention_days <= 35000
    error_message = "Minimum retention days must be between 1 and 35000."
  }
}

variable "max_retention_days" {
  description = "Maximum retention days for backup vault lock"
  type        = number
  default     = 36500  # 100 years
  validation {
    condition     = var.max_retention_days >= 1 && var.max_retention_days <= 36500
    error_message = "Maximum retention days must be between 1 and 36500."
  }
}

# KMS Configuration
variable "kms_deletion_window" {
  description = "Number of days after which KMS key is deleted"
  type        = number
  default     = 7
  validation {
    condition     = var.kms_deletion_window >= 7 && var.kms_deletion_window <= 30
    error_message = "KMS deletion window must be between 7 and 30 days."
  }
}

# Resource Selection
variable "rds_instances" {
  description = "List of RDS instances to include in backup"
  type = list(object({
    identifier = string
    arn        = string
  }))
  default = []
}

variable "backup_efs_enabled" {
  description = "Enable backup for EFS file systems"
  type        = bool
  default     = false
}

# Cross-Region Configuration
variable "replica_region" {
  description = "AWS region for cross-region backup replication"
  type        = string
  default     = "us-east-1"
}

# Notifications and Monitoring
variable "enable_backup_notifications" {
  description = "Enable SNS notifications for backup events"
  type        = bool
  default     = true
}

variable "notification_email" {
  description = "Email address for backup notifications"
  type        = string
  default     = ""
  validation {
    condition = var.notification_email == "" || can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.notification_email))
    error_message = "Notification email must be a valid email address."
  }
}

variable "enable_backup_monitoring" {
  description = "Enable CloudWatch alarms for backup monitoring"
  type        = bool
  default     = true
}

variable "max_concurrent_backups" {
  description = "Maximum number of concurrent backup jobs"
  type        = number
  default     = 10
  validation {
    condition     = var.max_concurrent_backups >= 1 && var.max_concurrent_backups <= 100
    error_message = "Max concurrent backups must be between 1 and 100."
  }
}

# Backup Validation
variable "enable_backup_validation" {
  description = "Enable automated backup validation with Lambda"
  type        = bool
  default     = true
}

variable "backup_validation_schedule" {
  description = "Cron expression for backup validation schedule"
  type        = string
  default     = "cron(0 6 * * ? *)"  # Daily at 6 AM
  validation {
    condition     = can(regex("^cron\\(.*\\)$", var.backup_validation_schedule))
    error_message = "Backup validation schedule must be a valid cron expression."
  }
}

# Cost Optimization
variable "enable_intelligent_tiering" {
  description = "Enable S3 Intelligent Tiering for backup storage cost optimization"
  type        = bool
  default     = true
}

variable "backup_cost_allocation_tags" {
  description = "Additional tags for backup cost allocation"
  type        = map(string)
  default = {
    CostCenter = "backup-operations"
    Owner      = "platform-team"
  }
}

# Compliance and Security
variable "enable_backup_encryption" {
  description = "Enable encryption for all backup resources"
  type        = bool
  default     = true
}

variable "compliance_mode" {
  description = "Compliance mode for backup retention (GOVERNANCE or COMPLIANCE)"
  type        = string
  default     = "GOVERNANCE"
  validation {
    condition     = contains(["GOVERNANCE", "COMPLIANCE"], var.compliance_mode)
    error_message = "Compliance mode must be either GOVERNANCE or COMPLIANCE."
  }
}

variable "enable_point_in_time_recovery" {
  description = "Enable point-in-time recovery for supported resources"
  type        = bool
  default     = true
}

# Advanced Configuration
variable "backup_window_start_hour" {
  description = "Start hour for backup window (0-23)"
  type        = number
  default     = 1
  validation {
    condition     = var.backup_window_start_hour >= 0 && var.backup_window_start_hour <= 23
    error_message = "Backup window start hour must be between 0 and 23."
  }
}

variable "backup_window_duration_hours" {
  description = "Duration of backup window in hours"
  type        = number
  default     = 4
  validation {
    condition     = var.backup_window_duration_hours >= 1 && var.backup_window_duration_hours <= 12
    error_message = "Backup window duration must be between 1 and 12 hours."
  }
}

variable "enable_continuous_backup" {
  description = "Enable continuous backup for supported resources (DynamoDB, RDS)"
  type        = bool
  default     = true
}

variable "backup_job_timeout_minutes" {
  description = "Timeout for backup jobs in minutes"
  type        = number
  default     = 480  # 8 hours
  validation {
    condition     = var.backup_job_timeout_minutes >= 60 && var.backup_job_timeout_minutes <= 1440
    error_message = "Backup job timeout must be between 60 and 1440 minutes (1-24 hours)."
  }
}

# Resource Tagging
variable "tags" {
  description = "Tags to apply to all backup resources"
  type        = map(string)
  default     = {}
}

variable "additional_backup_tags" {
  description = "Additional tags specific to backup resources"
  type        = map(string)
  default = {
    BackupEnabled = "true"
    Automated     = "true"
    Critical      = "true"
  }
}

# Resource Filters
variable "backup_resource_filters" {
  description = "Resource filters for backup selection"
  type = object({
    include_volume_types = optional(list(string), ["gp2", "gp3", "io1", "io2"])
    exclude_volume_types = optional(list(string), ["standard"])
    min_volume_size_gb   = optional(number, 1)
    max_volume_size_gb   = optional(number, 16384)
  })
  default = {}
}

# Disaster Recovery Configuration
variable "enable_cross_account_backup" {
  description = "Enable cross-account backup sharing"
  type        = bool
  default     = false
}

variable "cross_account_backup_accounts" {
  description = "List of AWS account IDs to share backups with"
  type        = list(string)
  default     = []
  validation {
    condition = alltrue([
      for account_id in var.cross_account_backup_accounts :
      can(regex("^[0-9]{12}$", account_id))
    ])
    error_message = "All account IDs must be 12-digit AWS account numbers."
  }
}

variable "rpo_target_hours" {
  description = "Recovery Point Objective (RPO) target in hours"
  type        = number
  default     = 24
  validation {
    condition     = var.rpo_target_hours >= 1 && var.rpo_target_hours <= 168
    error_message = "RPO target must be between 1 and 168 hours (1 week)."
  }
}

variable "rto_target_hours" {
  description = "Recovery Time Objective (RTO) target in hours"
  type        = number
  default     = 4
  validation {
    condition     = var.rto_target_hours >= 1 && var.rto_target_hours <= 72
    error_message = "RTO target must be between 1 and 72 hours."
  }
}

# Performance Configuration
variable "backup_performance_mode" {
  description = "Performance mode for backup operations (STANDARD or HIGH_PERFORMANCE)"
  type        = string
  default     = "STANDARD"
  validation {
    condition     = contains(["STANDARD", "HIGH_PERFORMANCE"], var.backup_performance_mode)
    error_message = "Performance mode must be either STANDARD or HIGH_PERFORMANCE."
  }
}

variable "enable_backup_deduplication" {
  description = "Enable backup deduplication to reduce storage costs"
  type        = bool
  default     = true
}

variable "backup_compression_enabled" {
  description = "Enable backup compression"
  type        = bool
  default     = true
}

# Integration Configuration
variable "enable_aws_config_integration" {
  description = "Enable AWS Config integration for backup compliance monitoring"
  type        = bool
  default     = true
}

variable "enable_cloudtrail_integration" {
  description = "Enable CloudTrail integration for backup audit logging"
  type        = bool
  default     = true
}

variable "enable_systems_manager_integration" {
  description = "Enable Systems Manager integration for backup automation"
  type        = bool
  default     = true
}
