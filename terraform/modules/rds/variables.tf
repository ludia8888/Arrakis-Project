# RDS Module Variables
# Input variables for the RDS module configuration

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

# Network Configuration
variable "vpc_id" {
  description = "VPC ID where RDS instances will be created"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for RDS subnet group"
  type        = list(string)
  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "At least 2 subnets are required for RDS subnet group."
  }
}

variable "allowed_cidr_blocks" {
  description = "List of CIDR blocks allowed to access RDS instances"
  type        = list(string)
  default     = ["10.0.0.0/8"]
}

# Database Configuration
variable "databases" {
  description = "Map of database configurations"
  type = map(object({
    identifier                            = string
    engine_version                        = string
    instance_class                        = string
    allocated_storage                     = number
    max_allocated_storage                 = number
    storage_type                          = string
    storage_encrypted                     = bool
    database_name                         = string
    master_username                       = string
    publicly_accessible                   = bool
    multi_az                              = bool
    availability_zone                     = string
    backup_retention_period               = number
    backup_window                         = string
    maintenance_window                    = string
    auto_minor_version_upgrade            = bool
    apply_immediately                     = bool
    deletion_protection                   = bool
    skip_final_snapshot                   = bool
    monitoring_interval                   = number
    performance_insights_enabled          = bool
    performance_insights_retention_period = number
    enabled_cloudwatch_logs_exports       = list(string)
    snapshot_identifier                   = string
    character_set_name                    = string
    license_model                         = string
    timezone                              = string
    ca_cert_identifier                    = string
    domain                                = string
    domain_iam_role_name                  = string
    replica_instance_class                = string
  }))
  default = {}
}

# Security Configuration
variable "enable_enhanced_monitoring" {
  description = "Enable enhanced monitoring for RDS instances"
  type        = bool
  default     = true
}

variable "enable_performance_insights" {
  description = "Enable Performance Insights for RDS instances"
  type        = bool
  default     = true
}

variable "performance_insights_retention_period" {
  description = "The amount of time in days to retain Performance Insights data"
  type        = number
  default     = 7
  validation {
    condition     = contains([7, 31, 62, 93, 124, 155, 186, 217, 248, 279, 310, 341, 372, 403, 434, 465, 496, 527, 558, 589, 620, 651, 682, 713, 731], var.performance_insights_retention_period)
    error_message = "Performance Insights retention period must be a valid value."
  }
}

# Backup Configuration
variable "enable_automated_backups" {
  description = "Enable automated backups using AWS Backup"
  type        = bool
  default     = true
}

variable "backup_retention_days" {
  description = "Number of days to retain automated backups"
  type        = number
  default     = 30
  validation {
    condition     = var.backup_retention_days >= 1 && var.backup_retention_days <= 35
    error_message = "Backup retention period must be between 1 and 35 days."
  }
}

variable "backup_window" {
  description = "Daily time range for automated backups"
  type        = string
  default     = "03:00-04:00"
}

variable "maintenance_window" {
  description = "Weekly time range for system maintenance"
  type        = string
  default     = "sun:04:00-sun:05:00"
}

variable "copy_tags_to_snapshot" {
  description = "Copy all instance tags to snapshots"
  type        = bool
  default     = true
}

# Read Replica Configuration
variable "enable_read_replicas" {
  description = "Enable read replicas for databases"
  type        = bool
  default     = false
}

variable "read_replica_count" {
  description = "Number of read replicas to create"
  type        = number
  default     = 1
  validation {
    condition     = var.read_replica_count >= 0 && var.read_replica_count <= 5
    error_message = "Read replica count must be between 0 and 5."
  }
}

# Monitoring Configuration
variable "monitoring_interval" {
  description = "Interval for collecting enhanced monitoring metrics"
  type        = number
  default     = 60
  validation {
    condition     = contains([0, 1, 5, 10, 15, 30, 60], var.monitoring_interval)
    error_message = "Monitoring interval must be one of: 0, 1, 5, 10, 15, 30, 60."
  }
}

variable "enabled_cloudwatch_logs_exports" {
  description = "List of log types to export to CloudWatch"
  type        = list(string)
  default     = ["postgresql"]
}

variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 30
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.log_retention_days)
    error_message = "Log retention must be a valid CloudWatch Logs retention period."
  }
}

variable "sns_topic_arn" {
  description = "SNS topic ARN for database notifications"
  type        = string
  default     = ""
}

# Storage Configuration
variable "storage_type" {
  description = "Storage type for RDS instances"
  type        = string
  default     = "gp3"
  validation {
    condition     = contains(["standard", "gp2", "gp3", "io1", "io2"], var.storage_type)
    error_message = "Storage type must be one of: standard, gp2, gp3, io1, io2."
  }
}

variable "storage_encrypted" {
  description = "Enable storage encryption"
  type        = bool
  default     = true
}

variable "storage_iops" {
  description = "IOPS for provisioned IOPS storage"
  type        = number
  default     = 0
}

variable "storage_throughput" {
  description = "Throughput for gp3 storage"
  type        = number
  default     = 125
}

# High Availability Configuration
variable "multi_az" {
  description = "Enable Multi-AZ deployment"
  type        = bool
  default     = true
}

variable "publicly_accessible" {
  description = "Make RDS instance publicly accessible"
  type        = bool
  default     = false
}

# Database Engine Configuration
variable "engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "16.1"
}

variable "auto_minor_version_upgrade" {
  description = "Enable automatic minor version upgrades"
  type        = bool
  default     = false
}

variable "apply_immediately" {
  description = "Apply changes immediately"
  type        = bool
  default     = false
}

# Security Configuration
variable "deletion_protection" {
  description = "Enable deletion protection"
  type        = bool
  default     = true
}

variable "skip_final_snapshot" {
  description = "Skip final snapshot when deleting"
  type        = bool
  default     = false
}

variable "ca_cert_identifier" {
  description = "Certificate authority certificate identifier"
  type        = string
  default     = "rds-ca-2019"
}

# Parameter Group Configuration
variable "parameter_group_family" {
  description = "Parameter group family"
  type        = string
  default     = "postgres16"
}

variable "custom_parameters" {
  description = "Custom database parameters"
  type = map(object({
    name  = string
    value = string
  }))
  default = {}
}

# Option Group Configuration
variable "option_group_name" {
  description = "Name of the option group"
  type        = string
  default     = ""
}

variable "custom_options" {
  description = "Custom database options"
  type = list(object({
    option_name = string
    option_settings = list(object({
      name  = string
      value = string
    }))
  }))
  default = []
}

# Snapshot Configuration
variable "snapshot_identifier" {
  description = "Snapshot identifier for restoring from snapshot"
  type        = string
  default     = ""
}

variable "restore_to_point_in_time" {
  description = "Restore to point in time configuration"
  type = object({
    source_db_instance_identifier = string
    restore_time                  = string
    use_latest_restorable_time    = bool
  })
  default = null
}

# Cross-Region Backup Configuration
variable "enable_cross_region_backup" {
  description = "Enable cross-region backup"
  type        = bool
  default     = false
}

variable "backup_region" {
  description = "Backup region for cross-region backups"
  type        = string
  default     = "us-east-1"
}

# Compliance Configuration
variable "compliance_standards" {
  description = "Compliance standards to adhere to"
  type        = list(string)
  default     = ["SOC2", "GDPR", "HIPAA"]
}

variable "enable_audit_logging" {
  description = "Enable audit logging"
  type        = bool
  default     = true
}

variable "audit_log_retention_days" {
  description = "Number of days to retain audit logs"
  type        = number
  default     = 90
}

# Cost Optimization Configuration
variable "enable_cost_optimization" {
  description = "Enable cost optimization features"
  type        = bool
  default     = true
}

variable "enable_reserved_instance_matching" {
  description = "Enable reserved instance matching"
  type        = bool
  default     = false
}

variable "enable_right_sizing" {
  description = "Enable right-sizing recommendations"
  type        = bool
  default     = true
}

# Performance Configuration
variable "enable_performance_tuning" {
  description = "Enable performance tuning parameters"
  type        = bool
  default     = true
}

variable "connection_pool_size" {
  description = "Connection pool size"
  type        = number
  default     = 100
}

variable "shared_memory_size" {
  description = "Shared memory size in MB"
  type        = string
  default     = "256MB"
}

# Disaster Recovery Configuration
variable "enable_disaster_recovery" {
  description = "Enable disaster recovery setup"
  type        = bool
  default     = false
}

variable "disaster_recovery_region" {
  description = "Region for disaster recovery"
  type        = string
  default     = "us-east-1"
}

# Maintenance Configuration
variable "maintenance_schedule" {
  description = "Maintenance schedule configuration"
  type = object({
    day_of_week = string
    start_time  = string
    duration    = number
  })
  default = {
    day_of_week = "sunday"
    start_time  = "04:00"
    duration    = 60
  }
}

variable "enable_automated_maintenance" {
  description = "Enable automated maintenance tasks"
  type        = bool
  default     = true
}

# Database Migration Configuration
variable "migration_configuration" {
  description = "Database migration configuration"
  type = object({
    source_engine      = string
    source_version     = string
    migration_type     = string
    enable_validation  = bool
  })
  default = null
}

# Development Configuration
variable "enable_development_features" {
  description = "Enable development-specific features"
  type        = bool
  default     = false
}

variable "development_mode" {
  description = "Enable development mode optimizations"
  type        = bool
  default     = false
}

# Custom Configuration
variable "custom_tags" {
  description = "Custom tags for resources"
  type        = map(string)
  default     = {}
}

variable "custom_security_groups" {
  description = "Additional security groups to attach"
  type        = list(string)
  default     = []
}

variable "custom_parameter_groups" {
  description = "Custom parameter groups to use"
  type        = map(string)
  default     = {}
}

# Tagging
variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "additional_tags" {
  description = "Additional tags to apply to specific resources"
  type        = map(string)
  default     = {}
}

# Domain Configuration
variable "domain_configuration" {
  description = "Active Directory domain configuration"
  type = object({
    domain_name     = string
    domain_iam_role = string
    domain_ou       = string
  })
  default = null
}

# Timezone Configuration
variable "timezone" {
  description = "Database timezone"
  type        = string
  default     = "UTC"
}

# Character Set Configuration
variable "character_set_name" {
  description = "Database character set"
  type        = string
  default     = "UTF8"
}

# License Configuration
variable "license_model" {
  description = "Database license model"
  type        = string
  default     = "postgresql-license"
}

# Resource Limits
variable "max_connections" {
  description = "Maximum number of database connections"
  type        = number
  default     = 100
}

variable "max_allocated_storage" {
  description = "Maximum allocated storage in GB"
  type        = number
  default     = 1000
}

# Networking Configuration
variable "port" {
  description = "Database port"
  type        = number
  default     = 5432
}

variable "network_type" {
  description = "Network type for RDS instance"
  type        = string
  default     = "IPV4"
  validation {
    condition     = contains(["IPV4", "DUAL"], var.network_type)
    error_message = "Network type must be either IPV4 or DUAL."
  }
}

# Blue/Green Deployment Configuration
variable "enable_blue_green_deployment" {
  description = "Enable blue/green deployment"
  type        = bool
  default     = false
}

variable "blue_green_update_policy" {
  description = "Blue/green update policy"
  type = object({
    terminate_blue_instances_on_deployment_success = bool
    deployment_policy_type                          = string
    maximum_execution_timeout_in_seconds           = number
  })
  default = null
}