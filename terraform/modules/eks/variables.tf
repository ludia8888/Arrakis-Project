# EKS Module Variables
# Input variables for the EKS module configuration

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

# Cluster Configuration
variable "cluster_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string
  default     = "1.28"
  validation {
    condition     = can(regex("^1\\.(2[4-9]|[3-9][0-9])$", var.cluster_version))
    error_message = "Kubernetes version must be 1.24 or higher."
  }
}

variable "cluster_encryption_resources" {
  description = "List of strings with resources to be encrypted"
  type        = list(string)
  default     = ["secrets"]
}

variable "enable_cluster_encryption" {
  description = "Enable encryption for the EKS cluster"
  type        = bool
  default     = true
}

variable "cluster_enabled_log_types" {
  description = "List of control plane logging to enable"
  type        = list(string)
  default     = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
}

variable "log_retention_days" {
  description = "Number of days to retain log events"
  type        = number
  default     = 30
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.log_retention_days)
    error_message = "Log retention must be a valid CloudWatch Logs retention period."
  }
}

# Network Configuration
variable "vpc_id" {
  description = "VPC ID where the cluster will be created"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for the EKS cluster"
  type        = list(string)
  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "At least 2 subnets are required for EKS cluster."
  }
}

variable "control_plane_subnet_ids" {
  description = "List of subnet IDs for the EKS control plane"
  type        = list(string)
  default     = []
}

variable "endpoint_private_access" {
  description = "Enable private API server endpoint"
  type        = bool
  default     = true
}

variable "endpoint_public_access" {
  description = "Enable public API server endpoint"
  type        = bool
  default     = true
}

variable "public_access_cidrs" {
  description = "List of CIDR blocks that can access the public API server endpoint"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "additional_security_group_ids" {
  description = "Additional security group IDs to attach to the cluster"
  type        = list(string)
  default     = []
}

variable "workstation_cidrs" {
  description = "List of CIDR blocks for workstation access"
  type        = list(string)
  default     = []
}

# Kubernetes Network Configuration
variable "service_ipv4_cidr" {
  description = "The CIDR block to assign Kubernetes service IP addresses from"
  type        = string
  default     = "172.20.0.0/16"
}

variable "ip_family" {
  description = "The IP family used to assign Kubernetes pod and service addresses"
  type        = string
  default     = "ipv4"
  validation {
    condition     = contains(["ipv4", "ipv6"], var.ip_family)
    error_message = "IP family must be either ipv4 or ipv6."
  }
}

# Node Groups Configuration
variable "node_groups" {
  description = "Map of EKS node group configurations"
  type = map(object({
    instance_types             = list(string)
    ami_type                   = string
    capacity_type              = string
    disk_size                  = number
    min_capacity               = number
    max_capacity               = number
    desired_capacity           = number
    max_unavailable_percentage = number
    labels                     = map(string)
    taints = list(object({
      key    = string
      value  = string
      effect = string
    }))
  }))
  default = {
    general = {
      instance_types             = ["t3.medium"]
      ami_type                   = "AL2_x86_64"
      capacity_type              = "ON_DEMAND"
      disk_size                  = 20
      min_capacity               = 1
      max_capacity               = 10
      desired_capacity           = 3
      max_unavailable_percentage = 25
      labels                     = {}
      taints                     = []
    }
  }
}

# Launch Template Configuration
variable "ami_id" {
  description = "AMI ID for the EKS nodes (leave empty for latest EKS optimized AMI)"
  type        = string
  default     = ""
}

variable "bootstrap_arguments" {
  description = "Additional arguments for the EKS bootstrap script"
  type        = string
  default     = ""
}

variable "block_device_mappings" {
  description = "Block device mappings for the launch template"
  type = list(object({
    device_name           = string
    volume_size           = number
    volume_type           = string
    encrypted             = bool
    delete_on_termination = bool
  }))
  default = [
    {
      device_name           = "/dev/xvda"
      volume_size           = 20
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  ]
}

# IRSA Configuration
variable "enable_irsa" {
  description = "Enable IAM Roles for Service Accounts"
  type        = bool
  default     = true
}

# Add-ons Configuration
variable "vpc_cni_version" {
  description = "Version of the VPC CNI add-on"
  type        = string
  default     = "v1.15.1-eksbuild.1"
}

variable "coredns_version" {
  description = "Version of the CoreDNS add-on"
  type        = string
  default     = "v1.10.1-eksbuild.4"
}

variable "kube_proxy_version" {
  description = "Version of the kube-proxy add-on"
  type        = string
  default     = "v1.28.2-eksbuild.2"
}

variable "ebs_csi_driver_version" {
  description = "Version of the EBS CSI driver add-on"
  type        = string
  default     = "v1.24.0-eksbuild.1"
}

# Auto Scaling Configuration
variable "enable_cluster_autoscaler" {
  description = "Enable cluster autoscaler tags"
  type        = bool
  default     = true
}

variable "cluster_autoscaler_version" {
  description = "Version of the cluster autoscaler"
  type        = string
  default     = "1.28.2"
}

# Monitoring Configuration
variable "enable_container_insights" {
  description = "Enable CloudWatch Container Insights"
  type        = bool
  default     = true
}

variable "enable_prometheus_metrics" {
  description = "Enable Prometheus metrics collection"
  type        = bool
  default     = true
}

variable "enable_fluent_bit" {
  description = "Enable Fluent Bit for log collection"
  type        = bool
  default     = true
}

# Security Configuration
variable "enable_pod_security_policy" {
  description = "Enable Pod Security Policy"
  type        = bool
  default     = false
}

variable "enable_network_policy" {
  description = "Enable Network Policy support"
  type        = bool
  default     = true
}

variable "enable_secrets_encryption" {
  description = "Enable encryption of Kubernetes secrets"
  type        = bool
  default     = true
}

# Performance Configuration
variable "enable_enhanced_networking" {
  description = "Enable enhanced networking features"
  type        = bool
  default     = true
}

variable "enable_spot_instances" {
  description = "Enable spot instances for cost optimization"
  type        = bool
  default     = false
}

variable "spot_instance_percentage" {
  description = "Percentage of spot instances to use"
  type        = number
  default     = 50
  validation {
    condition     = var.spot_instance_percentage >= 0 && var.spot_instance_percentage <= 100
    error_message = "Spot instance percentage must be between 0 and 100."
  }
}

# Backup Configuration
variable "enable_backup_tags" {
  description = "Enable backup tags for EKS resources"
  type        = bool
  default     = true
}

variable "backup_retention_days" {
  description = "Number of days to retain backups"
  type        = number
  default     = 30
}

# Compliance Configuration
variable "enable_compliance_scanning" {
  description = "Enable compliance scanning"
  type        = bool
  default     = true
}

variable "compliance_standards" {
  description = "Compliance standards to adhere to"
  type        = list(string)
  default     = ["CIS", "PCI-DSS", "SOC2"]
}

# Development Configuration
variable "enable_development_tools" {
  description = "Enable development tools and debugging"
  type        = bool
  default     = false
}

variable "enable_kubectl_access" {
  description = "Enable kubectl access from nodes"
  type        = bool
  default     = true
}

# Cost Optimization
variable "enable_cost_optimization" {
  description = "Enable cost optimization features"
  type        = bool
  default     = true
}

variable "enable_right_sizing" {
  description = "Enable right-sizing recommendations"
  type        = bool
  default     = true
}

# Networking Performance
variable "enable_network_performance_monitoring" {
  description = "Enable network performance monitoring"
  type        = bool
  default     = true
}

variable "network_performance_metrics" {
  description = "Network performance metrics to collect"
  type        = list(string)
  default     = ["NetworkPacketsIn", "NetworkPacketsOut", "NetworkIn", "NetworkOut"]
}

# Custom Configuration
variable "custom_user_data" {
  description = "Custom user data script to run on nodes"
  type        = string
  default     = ""
}

variable "custom_node_labels" {
  description = "Custom labels to apply to all nodes"
  type        = map(string)
  default     = {}
}

variable "custom_node_taints" {
  description = "Custom taints to apply to all nodes"
  type = list(object({
    key    = string
    value  = string
    effect = string
  }))
  default = []
}

# Maintenance Configuration
variable "maintenance_window" {
  description = "Maintenance window for EKS cluster updates"
  type        = string
  default     = "sun:03:00-sun:04:00"
}

variable "enable_automatic_upgrades" {
  description = "Enable automatic cluster upgrades"
  type        = bool
  default     = false
}

variable "upgrade_policy" {
  description = "Upgrade policy for EKS cluster"
  type        = string
  default     = "rolling"
  validation {
    condition     = contains(["rolling", "blue-green", "canary"], var.upgrade_policy)
    error_message = "Upgrade policy must be one of: rolling, blue-green, canary."
  }
}

# Disaster Recovery
variable "enable_cross_region_backup" {
  description = "Enable cross-region backup for EKS configuration"
  type        = bool
  default     = false
}

variable "backup_region" {
  description = "Backup region for disaster recovery"
  type        = string
  default     = "us-east-1"
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

# Advanced Configuration
variable "enable_fargate" {
  description = "Enable Fargate profiles for serverless containers"
  type        = bool
  default     = false
}

variable "fargate_profiles" {
  description = "Fargate profiles configuration"
  type = map(object({
    namespace = string
    selectors = list(object({
      namespace = string
      labels    = map(string)
    }))
  }))
  default = {}
}

variable "enable_windows_support" {
  description = "Enable Windows node support"
  type        = bool
  default     = false
}

variable "windows_node_groups" {
  description = "Windows node groups configuration"
  type = map(object({
    instance_types   = list(string)
    min_capacity     = number
    max_capacity     = number
    desired_capacity = number
  }))
  default = {}
}

# Resource Limits
variable "max_pods_per_node" {
  description = "Maximum number of pods per node"
  type        = number
  default     = 110
  validation {
    condition     = var.max_pods_per_node >= 10 && var.max_pods_per_node <= 250
    error_message = "Max pods per node must be between 10 and 250."
  }
}

variable "max_nodes_per_zone" {
  description = "Maximum number of nodes per availability zone"
  type        = number
  default     = 100
}

# DNS Configuration
variable "cluster_dns_ip" {
  description = "IP address for the cluster DNS service"
  type        = string
  default     = "169.254.20.10"
}

variable "enable_dns_caching" {
  description = "Enable DNS caching for improved performance"
  type        = bool
  default     = true
}

# Storage Configuration
variable "enable_ebs_optimization" {
  description = "Enable EBS optimization for nodes"
  type        = bool
  default     = true
}

variable "default_storage_class" {
  description = "Default storage class for the cluster"
  type        = string
  default     = "gp3"
}

variable "enable_efs_support" {
  description = "Enable EFS support for shared storage"
  type        = bool
  default     = false
}

# Load Balancer Configuration
variable "enable_load_balancer_controller" {
  description = "Enable AWS Load Balancer Controller"
  type        = bool
  default     = true
}

variable "load_balancer_controller_version" {
  description = "Version of the AWS Load Balancer Controller"
  type        = string
  default     = "v2.6.2"
}

# Service Mesh Configuration
variable "enable_istio" {
  description = "Enable Istio service mesh"
  type        = bool
  default     = false
}

variable "istio_version" {
  description = "Version of Istio to install"
  type        = string
  default     = "1.19.3"
}

variable "enable_app_mesh" {
  description = "Enable AWS App Mesh"
  type        = bool
  default     = false
}

# Certificate Management
variable "enable_cert_manager" {
  description = "Enable cert-manager for certificate automation"
  type        = bool
  default     = true
}

variable "cert_manager_version" {
  description = "Version of cert-manager to install"
  type        = string
  default     = "v1.13.2"
}