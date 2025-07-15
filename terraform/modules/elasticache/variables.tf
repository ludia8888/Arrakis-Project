# ElastiCache Module Variables
# Input variables for the ElastiCache module configuration

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
  description = "VPC ID where ElastiCache clusters will be created"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for ElastiCache subnet group"
  type        = list(string)
  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "At least 2 subnets are required for ElastiCache subnet group."
  }
}

variable "allowed_cidr_blocks" {
  description = "List of CIDR blocks allowed to access ElastiCache clusters"
  type        = list(string)
  default     = ["10.0.0.0/8"]
}

# Cluster Configuration
variable "clusters" {
  description = "Map of ElastiCache cluster configurations"
  type = map(object({
    cluster_id                     = string
    node_type                      = string
    port                           = number
    engine_version                 = string
    num_cache_nodes                = number
    num_node_groups                = number
    replicas_per_node_group        = number
    multi_az_enabled               = bool
    automatic_failover_enabled     = bool
    at_rest_encryption_enabled     = bool
    transit_encryption_enabled     = bool
    auth_token_enabled             = bool
    snapshot_retention_limit       = number
    snapshot_window                = string
    final_snapshot_identifier      = string
    maintenance_window             = string
    auto_minor_version_upgrade     = bool
    apply_immediately              = bool
    notification_topic_arn         = string
    data_tiering_enabled           = bool
    global_replication_group_id    = string
    preferred_cache_cluster_azs    = list(string)
    maxmemory_policy               = string
    custom_parameters = list(object({
      name  = string
      value = string
    }))
  }))
  default = {}
}

# Security Configuration
variable "enable_rbac" {
  description = "Enable Role-Based Access Control for Redis 6.0+"
  type        = bool
  default     = true
}

variable "enable_auth_token" {
  description = "Enable Redis AUTH token"
  type        = bool
  default     = true
}

variable "auth_token_length" {
  description = "Length of the AUTH token"
  type        = number
  default     = 32
  validation {
    condition     = var.auth_token_length >= 16 && var.auth_token_length <= 128
    error_message = "AUTH token length must be between 16 and 128 characters."
  }
}

# Encryption Configuration
variable "at_rest_encryption_enabled" {
  description = "Enable encryption at rest for all clusters"
  type        = bool
  default     = true
}

variable "transit_encryption_enabled" {
  description = "Enable encryption in transit for all clusters"
  type        = bool
  default     = true
}

variable "kms_key_id" {
  description = "KMS key ID for encryption (leave empty to create new key)"
  type        = string
  default     = ""
}

# High Availability Configuration
variable "multi_az_enabled" {
  description = "Enable Multi-AZ for all clusters"
  type        = bool
  default     = true
}

variable "automatic_failover_enabled" {
  description = "Enable automatic failover for all clusters"
  type        = bool
  default     = true
}

variable "num_cache_clusters" {
  description = "Default number of cache clusters"
  type        = number
  default     = 2
  validation {
    condition     = var.num_cache_clusters >= 1 && var.num_cache_clusters <= 6
    error_message = "Number of cache clusters must be between 1 and 6."
  }
}

# Global Replication Configuration
variable "enable_global_replication" {
  description = "Enable Global Replication for cross-region replication"
  type        = bool
  default     = false
}

variable "global_replication_regions" {
  description = "List of regions for global replication"
  type        = list(string)
  default     = []
}

# Cluster Mode Configuration
variable "cluster_mode_enabled" {
  description = "Enable cluster mode for Redis"
  type        = bool
  default     = false
}

variable "num_node_groups" {
  description = "Number of node groups (shards) for cluster mode"
  type        = number
  default     = 1
  validation {
    condition     = var.num_node_groups >= 1 && var.num_node_groups <= 500
    error_message = "Number of node groups must be between 1 and 500."
  }
}

variable "replicas_per_node_group" {
  description = "Number of replica nodes per node group"
  type        = number
  default     = 1
  validation {
    condition     = var.replicas_per_node_group >= 0 && var.replicas_per_node_group <= 5
    error_message = "Number of replicas per node group must be between 0 and 5."
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

variable "snapshot_retention_limit" {
  description = "Number of days to retain snapshots"
  type        = number
  default     = 7
  validation {
    condition     = var.snapshot_retention_limit >= 0 && var.snapshot_retention_limit <= 35
    error_message = "Snapshot retention limit must be between 0 and 35 days."
  }
}

variable "snapshot_window" {
  description = "Daily time range for taking snapshots"
  type        = string
  default     = "03:00-05:00"
}

variable "final_snapshot_identifier" {
  description = "Name of final snapshot when cluster is deleted"
  type        = string
  default     = ""
}

# Maintenance Configuration
variable "maintenance_window" {
  description = "Weekly time range for system maintenance"
  type        = string
  default     = "sun:05:00-sun:09:00"
}

variable "auto_minor_version_upgrade" {
  description = "Enable automatic minor version upgrades"
  type        = bool
  default     = true
}

variable "apply_immediately" {
  description = "Apply changes immediately"
  type        = bool
  default     = false
}

# Engine Configuration
variable "engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.0"
}

variable "node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "port" {
  description = "Redis port"
  type        = number
  default     = 6379
}

# Parameter Group Configuration
variable "parameter_group_family" {
  description = "Parameter group family"
  type        = string
  default     = "redis7"
}

variable "maxmemory_policy" {
  description = "Redis maxmemory policy"
  type        = string
  default     = "allkeys-lru"
  validation {
    condition = contains([
      "volatile-lru", "allkeys-lru", "volatile-lfu", "allkeys-lfu",
      "volatile-random", "allkeys-random", "volatile-ttl", "noeviction"
    ], var.maxmemory_policy)
    error_message = "Maxmemory policy must be a valid Redis policy."
  }
}

variable "custom_parameters" {
  description = "Custom Redis parameters"
  type = map(object({
    name  = string
    value = string
  }))
  default = {}
}

# Data Tiering Configuration
variable "data_tiering_enabled" {
  description = "Enable data tiering for supported node types"
  type        = bool
  default     = false
}

variable "supported_data_tiering_node_types" {
  description = "List of node types that support data tiering"
  type        = list(string)
  default     = ["cache.r6gd.xlarge", "cache.r6gd.2xlarge", "cache.r6gd.4xlarge", "cache.r6gd.8xlarge", "cache.r6gd.12xlarge", "cache.r6gd.16xlarge"]
}

# Monitoring Configuration
variable "enable_monitoring_dashboard" {
  description = "Enable CloudWatch dashboard for monitoring"
  type        = bool
  default     = true
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
  description = "SNS topic ARN for ElastiCache notifications"
  type        = string
  default     = ""
}

# Notification Configuration
variable "notification_topic_arn" {
  description = "SNS topic ARN for cluster notifications"
  type        = string
  default     = ""
}

variable "enable_notifications" {
  description = "Enable SNS notifications for cluster events"
  type        = bool
  default     = true
}

# Performance Configuration
variable "enable_performance_tuning" {
  description = "Enable performance tuning parameters"
  type        = bool
  default     = true
}

variable "connection_pooling_enabled" {
  description = "Enable connection pooling optimizations"
  type        = bool
  default     = true
}

variable "lazy_freeing_enabled" {
  description = "Enable lazy freeing for better performance"
  type        = bool
  default     = true
}

# Cost Optimization Configuration
variable "enable_cost_optimization" {
  description = "Enable cost optimization features"
  type        = bool
  default     = true
}

variable "enable_reserved_instances" {
  description = "Enable reserved instance recommendations"
  type        = bool
  default     = false
}

variable "enable_right_sizing" {
  description = "Enable right-sizing recommendations"
  type        = bool
  default     = true
}

# Security Configuration
variable "enable_security_hardening" {
  description = "Enable security hardening features"
  type        = bool
  default     = true
}

variable "allowed_security_groups" {
  description = "Additional security groups allowed to access clusters"
  type        = list(string)
  default     = []
}

variable "enable_vpc_security_groups" {
  description = "Enable VPC security groups"
  type        = bool
  default     = true
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

variable "cross_region_backup_enabled" {
  description = "Enable cross-region backups"
  type        = bool
  default     = false
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

variable "enable_debug_logging" {
  description = "Enable debug logging for development"
  type        = bool
  default     = false
}

# Advanced Configuration
variable "preferred_cache_cluster_azs" {
  description = "List of preferred availability zones for cache clusters"
  type        = list(string)
  default     = []
}

variable "availability_zones" {
  description = "List of availability zones to use"
  type        = list(string)
  default     = []
}

variable "enable_cloudwatch_logs" {
  description = "Enable CloudWatch logs for slow queries"
  type        = bool
  default     = true
}

variable "slow_log_enabled" {
  description = "Enable slow query logging"
  type        = bool
  default     = true
}

# User and User Group Configuration
variable "redis_users" {
  description = "Map of Redis users for RBAC"
  type = map(object({
    user_name     = string
    access_string = string
    passwords     = list(string)
  }))
  default = {}
}

variable "redis_user_groups" {
  description = "Map of Redis user groups"
  type = map(object({
    user_group_id = string
    user_ids      = list(string)
  }))
  default = {}
}

# Scaling Configuration
variable "enable_auto_scaling" {
  description = "Enable auto scaling for cluster mode"
  type        = bool
  default     = false
}

variable "auto_scaling_target_cpu" {
  description = "Target CPU utilization for auto scaling"
  type        = number
  default     = 70
  validation {
    condition     = var.auto_scaling_target_cpu >= 10 && var.auto_scaling_target_cpu <= 90
    error_message = "Auto scaling target CPU must be between 10 and 90."
  }
}

variable "auto_scaling_target_memory" {
  description = "Target memory utilization for auto scaling"
  type        = number
  default     = 80
  validation {
    condition     = var.auto_scaling_target_memory >= 10 && var.auto_scaling_target_memory <= 90
    error_message = "Auto scaling target memory must be between 10 and 90."
  }
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

# Logging Configuration
variable "log_delivery_configuration" {
  description = "Log delivery configuration for Redis"
  type = list(object({
    destination      = string
    destination_type = string
    log_format       = string
    log_type         = string
  }))
  default = []
}

variable "enable_slow_log" {
  description = "Enable slow query logging"
  type        = bool
  default     = true
}

variable "slow_log_max_len" {
  description = "Maximum length of slow log"
  type        = number
  default     = 1000
}

# Network Configuration
variable "preferred_availability_zones" {
  description = "Preferred availability zones for clusters"
  type        = list(string)
  default     = []
}

variable "az_mode" {
  description = "AZ mode for clusters (single-az or cross-az)"
  type        = string
  default     = "cross-az"
  validation {
    condition     = contains(["single-az", "cross-az"], var.az_mode)
    error_message = "AZ mode must be either 'single-az' or 'cross-az'."
  }
}

# Resource Limits
variable "max_memory_per_node" {
  description = "Maximum memory per node in GB"
  type        = number
  default     = 32
}

variable "max_connections_per_node" {
  description = "Maximum connections per node"
  type        = number
  default     = 10000
}

# Migration Configuration
variable "migration_configuration" {
  description = "Migration configuration for Redis"
  type = object({
    source_cluster_id = string
    migration_type    = string
    enable_validation = bool
  })
  default = null
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
