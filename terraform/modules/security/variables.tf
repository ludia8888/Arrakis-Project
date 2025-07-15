# Security Module Variables
# Input variables for the security module configuration

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

# EKS Cluster Configuration
variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "cluster_oidc_issuer_url" {
  description = "OIDC issuer URL of the EKS cluster"
  type        = string
}

# Networking Configuration
variable "vpc_id" {
  description = "VPC ID where security groups will be created"
  type        = string
  default     = ""
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# Service Accounts Configuration
variable "service_accounts" {
  description = "Configuration for Kubernetes service accounts and their IAM roles"
  type = map(object({
    namespace = string
    policies  = list(string)
    custom_policy_statements = optional(list(object({
      effect    = string
      actions   = list(string)
      resources = list(string)
      conditions = optional(map(any))
    })))
  }))
  default = {}
}

# Secrets Configuration
variable "secrets" {
  description = "AWS Secrets Manager secrets configuration"
  type = map(object({
    description = string
    secret_data = map(string)
  }))
  default = {}
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

variable "secret_recovery_window" {
  description = "Number of days for secret recovery window"
  type        = number
  default     = 7
  validation {
    condition     = var.secret_recovery_window >= 7 && var.secret_recovery_window <= 30
    error_message = "Secret recovery window must be between 7 and 30 days."
  }
}

variable "replica_region" {
  description = "AWS region for secret replication"
  type        = string
  default     = "us-east-1"
}

# Security Features
variable "enable_cloudtrail" {
  description = "Enable AWS CloudTrail for security audit logging"
  type        = bool
  default     = true
}

variable "enable_aws_config" {
  description = "Enable AWS Config for compliance monitoring"
  type        = bool
  default     = true
}

variable "enable_guardduty" {
  description = "Enable AWS GuardDuty for threat detection"
  type        = bool
  default     = true
}

variable "enable_security_hub" {
  description = "Enable AWS Security Hub for centralized security findings"
  type        = bool
  default     = true
}

variable "enable_kubernetes_audit_logs" {
  description = "Enable Kubernetes audit logs in GuardDuty"
  type        = bool
  default     = true
}

# Network Security Configuration
variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access microservices"
  type        = list(string)
  default     = []
}

variable "microservices_ports" {
  description = "Port configuration for microservices"
  type = object({
    http_start    = number
    http_end      = number
    grpc_start    = number
    grpc_end      = number
    metrics_port  = number
  })
  default = {
    http_start   = 8000
    http_end     = 8010
    grpc_start   = 50050
    grpc_end     = 50060
    metrics_port = 9090
  }
}

# Compliance and Audit Configuration
variable "enable_encryption_at_rest" {
  description = "Enable encryption at rest for all resources"
  type        = bool
  default     = true
}

variable "enable_encryption_in_transit" {
  description = "Enable encryption in transit for all communications"
  type        = bool
  default     = true
}

variable "compliance_standards" {
  description = "Compliance standards to enable"
  type        = list(string)
  default     = ["cis", "pci-dss", "aws-foundational"]
  validation {
    condition = alltrue([
      for standard in var.compliance_standards :
      contains(["cis", "pci-dss", "aws-foundational", "nist", "soc2"], standard)
    ])
    error_message = "Compliance standards must be from: cis, pci-dss, aws-foundational, nist, soc2."
  }
}

# Backup and Disaster Recovery
variable "enable_cross_region_backup" {
  description = "Enable cross-region backup for secrets and configurations"
  type        = bool
  default     = true
}

variable "backup_retention_days" {
  description = "Number of days to retain security backups"
  type        = number
  default     = 90
  validation {
    condition     = var.backup_retention_days >= 30 && var.backup_retention_days <= 365
    error_message = "Backup retention days must be between 30 and 365."
  }
}

# Security Monitoring Configuration
variable "security_notification_email" {
  description = "Email address for security notifications"
  type        = string
  default     = ""
  validation {
    condition = var.security_notification_email == "" || can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.security_notification_email))
    error_message = "Security notification email must be a valid email address."
  }
}

variable "enable_real_time_notifications" {
  description = "Enable real-time security notifications"
  type        = bool
  default     = true
}

variable "security_alert_severity_threshold" {
  description = "Minimum severity level for security alerts"
  type        = string
  default     = "MEDIUM"
  validation {
    condition     = contains(["LOW", "MEDIUM", "HIGH", "CRITICAL"], var.security_alert_severity_threshold)
    error_message = "Security alert severity must be one of: LOW, MEDIUM, HIGH, CRITICAL."
  }
}

# Resource Tagging
variable "tags" {
  description = "Tags to apply to all security resources"
  type        = map(string)
  default     = {}
}

variable "additional_security_tags" {
  description = "Additional tags specific to security resources"
  type        = map(string)
  default = {
    SecurityLevel = "high"
    DataClass     = "confidential"
    Monitored     = "true"
  }
}

# Advanced Security Configuration
variable "enable_detective" {
  description = "Enable AWS Detective for security investigation"
  type        = bool
  default     = false
}

variable "enable_macie" {
  description = "Enable AWS Macie for data discovery and classification"
  type        = bool
  default     = false
}

variable "enable_inspector" {
  description = "Enable AWS Inspector for vulnerability assessment"
  type        = bool
  default     = true
}

variable "enable_systems_manager" {
  description = "Enable AWS Systems Manager for patch management"
  type        = bool
  default     = true
}

# Network Security Advanced Configuration
variable "enable_vpc_flow_logs" {
  description = "Enable VPC Flow Logs for network monitoring"
  type        = bool
  default     = true
}

variable "enable_dns_firewall" {
  description = "Enable DNS Firewall for malicious domain blocking"
  type        = bool
  default     = true
}

variable "enable_waf" {
  description = "Enable AWS WAF for application protection"
  type        = bool
  default     = true
}

# Identity and Access Management
variable "enable_access_analyzer" {
  description = "Enable AWS Access Analyzer for permissions analysis"
  type        = bool
  default     = true
}

variable "password_policy" {
  description = "IAM password policy configuration"
  type = object({
    minimum_password_length      = number
    require_lowercase_characters = bool
    require_uppercase_characters = bool
    require_numbers             = bool
    require_symbols             = bool
    max_password_age            = number
    password_reuse_prevention   = number
    hard_expiry                 = bool
  })
  default = {
    minimum_password_length      = 14
    require_lowercase_characters = true
    require_uppercase_characters = true
    require_numbers             = true
    require_symbols             = true
    max_password_age            = 90
    password_reuse_prevention   = 12
    hard_expiry                 = false
  }
}

# Certificate Management
variable "enable_certificate_transparency" {
  description = "Enable certificate transparency logging"
  type        = bool
  default     = true
}

variable "certificate_domains" {
  description = "Domains for which to request SSL certificates"
  type        = list(string)
  default     = []
}

# Incident Response Configuration
variable "enable_incident_response" {
  description = "Enable automated incident response capabilities"
  type        = bool
  default     = true
}

variable "incident_response_lambda_timeout" {
  description = "Timeout for incident response Lambda functions (seconds)"
  type        = number
  default     = 300
  validation {
    condition     = var.incident_response_lambda_timeout >= 60 && var.incident_response_lambda_timeout <= 900
    error_message = "Incident response Lambda timeout must be between 60 and 900 seconds."
  }
}

# Data Protection Configuration
variable "enable_dlp" {
  description = "Enable Data Loss Prevention (DLP) capabilities"
  type        = bool
  default     = true
}

variable "sensitive_data_types" {
  description = "Types of sensitive data to protect"
  type        = list(string)
  default     = ["credit_card", "ssn", "email", "phone", "ip_address"]
}

# Security Automation
variable "enable_security_automation" {
  description = "Enable security automation and remediation"
  type        = bool
  default     = true
}

variable "auto_remediation_enabled" {
  description = "Enable automatic remediation of security findings"
  type        = bool
  default     = false
}

variable "security_scan_schedule" {
  description = "Cron expression for security scan schedule"
  type        = string
  default     = "cron(0 2 * * ? *)"  # Daily at 2 AM
}

# Performance and Cost Optimization
variable "security_log_retention_days" {
  description = "Number of days to retain security logs"
  type        = number
  default     = 365
  validation {
    condition     = var.security_log_retention_days >= 90 && var.security_log_retention_days <= 3653
    error_message = "Security log retention must be between 90 days and 10 years."
  }
}

variable "enable_cost_optimization" {
  description = "Enable cost optimization for security resources"
  type        = bool
  default     = true
}

variable "security_budget_threshold" {
  description = "Monthly budget threshold for security resources (USD)"
  type        = number
  default     = 1000
  validation {
    condition     = var.security_budget_threshold > 0
    error_message = "Security budget threshold must be greater than 0."
  }
}
