# Terraform Variables for Arrakis Platform Infrastructure
# Input variables for the main Terraform configuration

# Environment Configuration
variable "environment" {
  description = "Environment name (development, staging, production)"
  type        = string
  default     = "development"
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be one of: development, staging, production."
  }
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-west-2"
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "arrakis"
  validation {
    condition     = can(regex("^[a-zA-Z0-9-]+$", var.project_name))
    error_message = "Project name must contain only alphanumeric characters and hyphens."
  }
}

# Network Configuration
variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "VPC CIDR must be a valid IPv4 CIDR block."
  }
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"]
}

variable "database_subnet_cidrs" {
  description = "CIDR blocks for database subnets"
  type        = list(string)
  default     = ["10.0.21.0/24", "10.0.22.0/24", "10.0.23.0/24"]
}

variable "enable_vpn_gateway" {
  description = "Enable VPN Gateway for the VPC"
  type        = bool
  default     = false
}

# Kubernetes Configuration
variable "kubernetes_version" {
  description = "Kubernetes version for EKS cluster"
  type        = string
  default     = "1.28"
  validation {
    condition     = can(regex("^1\\.(2[4-9]|[3-9][0-9])$", var.kubernetes_version))
    error_message = "Kubernetes version must be 1.24 or higher."
  }
}

variable "node_groups" {
  description = "EKS node groups configuration"
  type = map(object({
    instance_types   = list(string)
    min_capacity     = number
    max_capacity     = number
    desired_capacity = number
    disk_size        = number
    labels           = map(string)
    taints = list(object({
      key    = string
      value  = string
      effect = string
    }))
  }))
  default = {}
}

# Application Configuration
variable "image_registry" {
  description = "Docker image registry URL"
  type        = string
  default     = "your-account.dkr.ecr.us-west-2.amazonaws.com"
}

variable "image_tag" {
  description = "Docker image tag for services"
  type        = string
  default     = "latest"
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = ""
}

# Database Configuration
variable "database_instances" {
  description = "Database instance configurations"
  type = map(object({
    engine_version     = string
    instance_class     = string
    allocated_storage  = number
    storage_encrypted  = bool
    backup_retention   = number
    multi_az          = bool
    deletion_protection = bool
  }))
  default = {}
}

variable "database_master_username" {
  description = "Master username for databases"
  type        = string
  default     = "admin"
  sensitive   = true
}

variable "database_master_password" {
  description = "Master password for databases"
  type        = string
  default     = ""
  sensitive   = true
}

# Redis Configuration
variable "redis_node_type" {
  description = "Redis node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "redis_num_cache_nodes" {
  description = "Number of Redis cache nodes"
  type        = number
  default     = 1
}

variable "redis_engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.0"
}

# Monitoring Configuration
variable "grafana_admin_password" {
  description = "Admin password for Grafana"
  type        = string
  default     = ""
  sensitive   = true
}

variable "grafana_oauth_enabled" {
  description = "Enable OAuth for Grafana"
  type        = bool
  default     = false
}

variable "grafana_oauth_client_id" {
  description = "OAuth client ID for Grafana"
  type        = string
  default     = ""
  sensitive   = true
}

variable "grafana_oauth_client_secret" {
  description = "OAuth client secret for Grafana"
  type        = string
  default     = ""
  sensitive   = true
}

# Security Configuration
variable "jwt_secret" {
  description = "JWT signing secret"
  type        = string
  default     = ""
  sensitive   = true
}

variable "encryption_key" {
  description = "Encryption key for sensitive data"
  type        = string
  default     = ""
  sensitive   = true
}

# Backup Configuration
variable "backup_retention_days" {
  description = "Number of days to retain backups"
  type        = number
  default     = 7
  validation {
    condition     = var.backup_retention_days >= 1 && var.backup_retention_days <= 365
    error_message = "Backup retention must be between 1 and 365 days."
  }
}

variable "backup_schedule" {
  description = "Backup schedule (cron expression)"
  type        = string
  default     = "cron(0 2 * * ? *)"
}

# Certificate Configuration
variable "certificate_arn" {
  description = "ARN of the SSL certificate"
  type        = string
  default     = ""
}

variable "certificate_domain" {
  description = "Domain name for the certificate"
  type        = string
  default     = ""
}

# Logging Configuration
variable "log_retention_days" {
  description = "Number of days to retain logs"
  type        = number
  default     = 30
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.log_retention_days)
    error_message = "Log retention must be a valid CloudWatch Logs retention period."
  }
}

variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"
  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], var.log_level)
    error_message = "Log level must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL."
  }
}

# Performance Configuration
variable "enable_performance_insights" {
  description = "Enable Performance Insights for RDS"
  type        = bool
  default     = true
}

variable "performance_insights_retention_period" {
  description = "Performance Insights retention period in days"
  type        = number
  default     = 7
  validation {
    condition     = contains([7, 31, 62, 93, 124, 155, 186, 217, 248, 279, 310, 341, 372, 403, 434, 465, 496, 527, 558, 589, 620, 651, 682, 713, 731], var.performance_insights_retention_period)
    error_message = "Performance Insights retention must be a valid period."
  }
}

# Cost Optimization
variable "enable_cost_optimization" {
  description = "Enable cost optimization features"
  type        = bool
  default     = true
}

variable "auto_scaling_enabled" {
  description = "Enable auto scaling for services"
  type        = bool
  default     = true
}

variable "spot_instances_enabled" {
  description = "Enable spot instances for cost savings"
  type        = bool
  default     = false
}

variable "spot_instances_percentage" {
  description = "Percentage of spot instances in node groups"
  type        = number
  default     = 30
  validation {
    condition     = var.spot_instances_percentage >= 0 && var.spot_instances_percentage <= 100
    error_message = "Spot instances percentage must be between 0 and 100."
  }
}

# Compliance Configuration
variable "compliance_standards" {
  description = "Compliance standards to adhere to"
  type        = list(string)
  default     = ["SOC2", "GDPR"]
}

variable "enable_encryption_at_rest" {
  description = "Enable encryption at rest for all services"
  type        = bool
  default     = true
}

variable "enable_encryption_in_transit" {
  description = "Enable encryption in transit for all services"
  type        = bool
  default     = true
}

# Disaster Recovery Configuration
variable "enable_multi_az" {
  description = "Enable multi-AZ deployment for high availability"
  type        = bool
  default     = true
}

variable "backup_cross_region" {
  description = "Enable cross-region backup for disaster recovery"
  type        = bool
  default     = false
}

variable "backup_region" {
  description = "Backup region for disaster recovery"
  type        = string
  default     = "us-east-1"
}

# Development Configuration
variable "enable_development_features" {
  description = "Enable development-specific features"
  type        = bool
  default     = false
}

variable "development_cidrs" {
  description = "CIDR blocks for development access"
  type        = list(string)
  default     = ["10.0.0.0/8"]
}

# Notification Configuration
variable "notification_email" {
  description = "Email for alerts and notifications"
  type        = string
  default     = "platform-team@arrakis.dev"
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for notifications"
  type        = string
  default     = ""
  sensitive   = true
}

# Feature Flags
variable "enable_debug_mode" {
  description = "Enable debug mode for troubleshooting"
  type        = bool
  default     = false
}

variable "enable_experimental_features" {
  description = "Enable experimental features"
  type        = bool
  default     = false
}

variable "enable_canary_deployments" {
  description = "Enable canary deployments"
  type        = bool
  default     = false
}

# Resource Limits
variable "max_pods_per_node" {
  description = "Maximum number of pods per node"
  type        = number
  default     = 110
}

variable "max_nodes_per_az" {
  description = "Maximum number of nodes per availability zone"
  type        = number
  default     = 10
}

# Service Configuration
variable "service_replicas" {
  description = "Number of replicas for each service"
  type        = map(number)
  default     = {}
}

variable "service_resources" {
  description = "Resource limits for each service"
  type = map(object({
    cpu_request    = string
    memory_request = string
    cpu_limit      = string
    memory_limit   = string
  }))
  default = {}
}

# Custom Configuration
variable "custom_tags" {
  description = "Custom tags to apply to resources"
  type        = map(string)
  default     = {}
}

variable "custom_annotations" {
  description = "Custom annotations for Kubernetes resources"
  type        = map(string)
  default     = {}
}

# External Dependencies
variable "external_dependencies" {
  description = "External service dependencies"
  type = map(object({
    endpoint = string
    port     = number
    protocol = string
    enabled  = bool
  }))
  default = {}
}

# Data Sources
variable "existing_security_groups" {
  description = "Existing security groups to use"
  type        = list(string)
  default     = []
}

variable "existing_subnets" {
  description = "Existing subnets to use"
  type        = list(string)
  default     = []
}

variable "existing_vpc_id" {
  description = "Existing VPC ID to use"
  type        = string
  default     = ""
}

# Migration Configuration
variable "migration_mode" {
  description = "Enable migration mode for gradual rollout"
  type        = bool
  default     = false
}

variable "migration_percentage" {
  description = "Percentage of traffic to migrate"
  type        = number
  default     = 0
  validation {
    condition     = var.migration_percentage >= 0 && var.migration_percentage <= 100
    error_message = "Migration percentage must be between 0 and 100."
  }
}
