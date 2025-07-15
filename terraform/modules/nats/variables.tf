# NATS Module Variables
# Input variables for the NATS module configuration

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

# Kubernetes Configuration
variable "namespace" {
  description = "Kubernetes namespace for NATS deployment"
  type        = string
  default     = "nats-system"
}

variable "cluster_endpoint" {
  description = "Kubernetes cluster endpoint"
  type        = string
}

variable "cluster_ca_certificate" {
  description = "Kubernetes cluster CA certificate"
  type        = string
}

variable "cluster_auth_token" {
  description = "Kubernetes cluster auth token"
  type        = string
  sensitive   = true
}

# NATS Cluster Configuration
variable "cluster_size" {
  description = "Number of NATS server instances"
  type        = number
  default     = 3
  validation {
    condition     = var.cluster_size >= 1 && var.cluster_size <= 7
    error_message = "Cluster size must be between 1 and 7."
  }
}

variable "nats_image" {
  description = "NATS server image"
  type        = string
  default     = "nats"
}

variable "nats_version" {
  description = "NATS server version"
  type        = string
  default     = "2.10.7-alpine"
}

variable "nats_operator_version" {
  description = "NATS operator version"
  type        = string
  default     = "0.8.1"
}

# JetStream Configuration
variable "jetstream_enabled" {
  description = "Enable JetStream for persistence and streaming"
  type        = bool
  default     = true
}

variable "jetstream_max_memory" {
  description = "Maximum memory for JetStream storage"
  type        = string
  default     = "1Gi"
}

variable "jetstream_max_storage" {
  description = "Maximum disk storage for JetStream"
  type        = string
  default     = "10Gi"
}

variable "jetstream_storage_class" {
  description = "Storage class for JetStream persistence"
  type        = string
  default     = "gp3"
}

# Storage Configuration
variable "storage_class" {
  description = "Storage class for persistent volumes"
  type        = string
  default     = "gp3"
}

variable "storage_size" {
  description = "Storage size for each NATS instance"
  type        = string
  default     = "10Gi"
}

# Resources Configuration
variable "resources" {
  description = "Resource requests and limits for NATS containers"
  type = object({
    requests = object({
      cpu    = string
      memory = string
    })
    limits = object({
      cpu    = string
      memory = string
    })
  })
  default = {
    requests = {
      cpu    = "100m"
      memory = "256Mi"
    }
    limits = {
      cpu    = "500m"
      memory = "1Gi"
    }
  }
}

# Security Configuration
variable "auth_enabled" {
  description = "Enable authentication"
  type        = bool
  default     = true
}

variable "tls_enabled" {
  description = "Enable TLS encryption"
  type        = bool
  default     = true
}

variable "tls_cert" {
  description = "TLS certificate"
  type        = string
  default     = ""
  sensitive   = true
}

variable "tls_key" {
  description = "TLS private key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "tls_ca_cert" {
  description = "TLS CA certificate"
  type        = string
  default     = ""
  sensitive   = true
}

# Authentication Configuration
variable "system_account" {
  description = "System account for NATS"
  type        = string
  default     = ""
  sensitive   = true
}

variable "system_user" {
  description = "System user for NATS"
  type        = string
  default     = ""
  sensitive   = true
}

variable "operator_jwt" {
  description = "Operator JWT for NATS"
  type        = string
  default     = ""
  sensitive   = true
}

variable "account_jwt" {
  description = "Account JWT for NATS"
  type        = string
  default     = ""
  sensitive   = true
}

variable "user_credentials" {
  description = "User credentials for NATS"
  type        = string
  default     = ""
  sensitive   = true
}

# Monitoring Configuration
variable "monitoring_enabled" {
  description = "Enable monitoring endpoints"
  type        = bool
  default     = true
}

variable "prometheus_port" {
  description = "Port for Prometheus metrics"
  type        = number
  default     = 7777
}

variable "prometheus_operator_enabled" {
  description = "Enable ServiceMonitor for Prometheus Operator"
  type        = bool
  default     = true
}

# Performance Configuration
variable "max_connections" {
  description = "Maximum number of client connections"
  type        = number
  default     = 10000
}

variable "max_payload" {
  description = "Maximum message payload size"
  type        = string
  default     = "1MB"
}

variable "max_pending" {
  description = "Maximum pending messages"
  type        = string
  default     = "10MB"
}

variable "write_deadline" {
  description = "Write deadline for connections"
  type        = string
  default     = "10s"
}

variable "max_control_line" {
  description = "Maximum control line size"
  type        = number
  default     = 4096
}

variable "ping_interval" {
  description = "Ping interval for client connections"
  type        = string
  default     = "2m"
}

variable "ping_max" {
  description = "Maximum outstanding pings"
  type        = number
  default     = 2
}

# Protocol Configuration
variable "leafnode_enabled" {
  description = "Enable leafnode protocol"
  type        = bool
  default     = false
}

variable "gateway_enabled" {
  description = "Enable gateway protocol for super clusters"
  type        = bool
  default     = false
}

variable "websocket_enabled" {
  description = "Enable WebSocket protocol"
  type        = bool
  default     = true
}

variable "mqtt_enabled" {
  description = "Enable MQTT protocol"
  type        = bool
  default     = false
}

# Service Configuration
variable "service_type" {
  description = "Service type for external access"
  type        = string
  default     = "LoadBalancer"
  validation {
    condition     = contains(["ClusterIP", "LoadBalancer", "NodePort"], var.service_type)
    error_message = "Service type must be one of: ClusterIP, LoadBalancer, NodePort."
  }
}

variable "enable_external_access" {
  description = "Enable external access to NATS"
  type        = bool
  default     = false
}

variable "load_balancer_source_ranges" {
  description = "Source IP ranges for LoadBalancer service"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "service_annotations" {
  description = "Annotations for the service"
  type        = map(string)
  default     = {}
}

# Network Policy Configuration
variable "enable_network_policy" {
  description = "Enable NetworkPolicy for NATS"
  type        = bool
  default     = true
}

variable "allowed_namespaces" {
  description = "List of namespaces allowed to connect to NATS"
  type        = list(string)
  default     = ["default", "arrakis"]
}

# Auto Scaling Configuration
variable "enable_autoscaling" {
  description = "Enable horizontal pod autoscaling"
  type        = bool
  default     = false
}

variable "min_replicas" {
  description = "Minimum number of replicas for autoscaling"
  type        = number
  default     = 3
}

variable "max_replicas" {
  description = "Maximum number of replicas for autoscaling"
  type        = number
  default     = 7
}

variable "target_cpu_utilization_percentage" {
  description = "Target CPU utilization for autoscaling"
  type        = number
  default     = 70
}

variable "target_memory_utilization_percentage" {
  description = "Target memory utilization for autoscaling"
  type        = number
  default     = 80
}

# Istio Configuration
variable "enable_istio" {
  description = "Enable Istio service mesh integration"
  type        = bool
  default     = false
}

# Custom Configuration
variable "custom_config" {
  description = "Custom NATS configuration"
  type        = string
  default     = ""
}

variable "custom_annotations" {
  description = "Custom annotations for NATS resources"
  type        = map(string)
  default     = {}
}

variable "custom_labels" {
  description = "Custom labels for NATS resources"
  type        = map(string)
  default     = {}
}

# Tagging
variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# Backup Configuration
variable "enable_backup" {
  description = "Enable backup for JetStream data"
  type        = bool
  default     = true
}

variable "backup_schedule" {
  description = "Backup schedule for JetStream data"
  type        = string
  default     = "0 2 * * *"
}

variable "backup_retention_days" {
  description = "Number of days to retain backups"
  type        = number
  default     = 30
}

# High Availability Configuration
variable "enable_pod_disruption_budget" {
  description = "Enable PodDisruptionBudget"
  type        = bool
  default     = true
}

variable "topology_spread_constraints" {
  description = "Topology spread constraints for pod placement"
  type = list(object({
    max_skew           = number
    topology_key       = string
    when_unsatisfiable = string
  }))
  default = [
    {
      max_skew           = 1
      topology_key       = "kubernetes.io/hostname"
      when_unsatisfiable = "DoNotSchedule"
    }
  ]
}

# Development Configuration
variable "enable_debug" {
  description = "Enable debug logging"
  type        = bool
  default     = false
}

variable "enable_trace" {
  description = "Enable trace logging"
  type        = bool
  default     = false
}

# Disaster Recovery Configuration
variable "enable_disaster_recovery" {
  description = "Enable disaster recovery features"
  type        = bool
  default     = false
}

variable "dr_backup_region" {
  description = "Disaster recovery backup region"
  type        = string
  default     = "us-east-1"
}

# Compliance Configuration
variable "enable_audit_logging" {
  description = "Enable audit logging"
  type        = bool
  default     = true
}

variable "audit_log_retention_days" {
  description = "Audit log retention in days"
  type        = number
  default     = 90
}

# Cluster Mode Configuration
variable "cluster_advertise" {
  description = "Cluster advertise address"
  type        = string
  default     = ""
}

variable "no_advertise" {
  description = "Disable advertising of client connections"
  type        = bool
  default     = false
}

# Rate Limiting Configuration
variable "rate_limiting_enabled" {
  description = "Enable rate limiting"
  type        = bool
  default     = false
}

variable "rate_limit_config" {
  description = "Rate limiting configuration"
  type = object({
    max_msg_per_second = number
    max_bytes_per_second = number
    max_subscriptions = number
  })
  default = {
    max_msg_per_second = 10000
    max_bytes_per_second = 1048576
    max_subscriptions = 1000
  }
}
