# DNS Module Variables
# Input variables for the DNS module configuration

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

# Domain Configuration
variable "domain_name" {
  description = "Primary domain name"
  type        = string
  validation {
    condition     = can(regex("^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]*\\.[a-zA-Z]{2,}$", var.domain_name))
    error_message = "Domain name must be a valid domain format."
  }
}

variable "create_hosted_zone" {
  description = "Whether to create a new hosted zone or use existing one"
  type        = bool
  default     = true
}

variable "certificate_sans" {
  description = "Subject Alternative Names for the SSL certificate"
  type        = list(string)
  default     = []
}

variable "create_www_redirect" {
  description = "Create www subdomain redirect to main domain"
  type        = bool
  default     = true
}

# Load Balancer Configuration
variable "load_balancer_dns_name" {
  description = "DNS name of the load balancer"
  type        = string
  default     = ""
}

variable "load_balancer_zone_id" {
  description = "Zone ID of the load balancer"
  type        = string
  default     = ""
}

# Subdomains Configuration
variable "subdomains" {
  description = "Map of subdomains and their configuration"
  type = map(object({
    type         = string
    alias        = optional(bool, false)
    records      = optional(list(string), [])
    ttl          = optional(number, 3600)
    health_check = optional(bool, true)
  }))
  default = {}
}

# Health Check Configuration
variable "enable_health_checks" {
  description = "Enable Route53 health checks"
  type        = bool
  default     = true
}

variable "health_check_port" {
  description = "Port for health checks"
  type        = number
  default     = 443
  validation {
    condition     = var.health_check_port >= 1 && var.health_check_port <= 65535
    error_message = "Health check port must be between 1 and 65535."
  }
}

variable "health_check_path" {
  description = "Path for health checks"
  type        = string
  default     = "/health"
}

variable "enable_health_check_alarms" {
  description = "Enable CloudWatch alarms for health checks"
  type        = bool
  default     = true
}

variable "health_check_alarm_actions" {
  description = "List of alarm actions for health check failures"
  type        = list(string)
  default     = []
}

# Failover Configuration
variable "enable_failover" {
  description = "Enable DNS failover routing"
  type        = bool
  default     = false
}

variable "failover_load_balancer_dns_name" {
  description = "DNS name of the failover load balancer"
  type        = string
  default     = ""
}

variable "failover_load_balancer_zone_id" {
  description = "Zone ID of the failover load balancer"
  type        = string
  default     = ""
}

variable "failover_records" {
  description = "Failover records for non-alias subdomains"
  type        = map(list(string))
  default     = {}
}

# Email Configuration
variable "mx_records" {
  description = "List of MX records for email"
  type        = list(string)
  default     = []
  validation {
    condition = alltrue([
      for record in var.mx_records :
      can(regex("^[0-9]+\\s+[a-zA-Z0-9.-]+\\.$", record))
    ])
    error_message = "MX records must be in format 'priority hostname.' (e.g., '10 mail.example.com.')."
  }
}

variable "spf_record" {
  description = "SPF record for email security"
  type        = string
  default     = ""
}

variable "dmarc_record" {
  description = "DMARC record for email security"
  type        = string
  default     = ""
}

variable "dkim_records" {
  description = "Map of DKIM records for email authentication"
  type        = map(string)
  default     = {}
}

# DNS Security
variable "caa_records" {
  description = "List of CAA records for certificate authority authorization"
  type        = list(string)
  default     = []
  validation {
    condition = alltrue([
      for record in var.caa_records :
      can(regex("^[0-9]+\\s+(issue|issuewild|iodef)\\s+\".*\"$", record))
    ])
    error_message = "CAA records must be in format 'flags tag value' (e.g., '0 issue \"letsencrypt.org\"')."
  }
}

# Other DNS Records
variable "txt_records" {
  description = "Map of TXT records (key is subdomain, value is list of TXT values)"
  type        = map(list(string))
  default     = {}
}

variable "cname_records" {
  description = "Map of CNAME records (key is subdomain, value is target)"
  type        = map(string)
  default     = {}
}

variable "ns_records" {
  description = "Map of NS records for subdomain delegation"
  type        = map(list(string))
  default     = {}
}

# Private DNS Configuration
variable "enable_private_dns" {
  description = "Enable private DNS with Route53 Resolver"
  type        = bool
  default     = false
}

variable "vpc_id" {
  description = "VPC ID for private DNS configuration"
  type        = string
  default     = ""
}

variable "resolver_subnet_ids" {
  description = "List of subnet IDs for Route53 Resolver endpoints"
  type        = list(string)
  default     = []
}

variable "resolver_security_group_ids" {
  description = "List of security group IDs for Route53 Resolver endpoints"
  type        = list(string)
  default     = []
}

variable "private_domain_name" {
  description = "Private domain name for internal services"
  type        = string
  default     = ""
}

variable "private_dns_rules" {
  description = "Map of private DNS resolver rules"
  type = map(object({
    domain_name = string
    rule_type   = string
    target_ips = optional(list(object({
      ip   = string
      port = optional(number, 53)
    })), [])
  }))
  default = {}
}

variable "internal_service_records" {
  description = "Map of internal service DNS records"
  type = map(object({
    type    = string
    records = list(string)
    ttl     = optional(number, 300)
  }))
  default = {}
}

# Advanced Features
variable "enable_advanced_features" {
  description = "Enable advanced Route53 features via CloudFormation"
  type        = bool
  default     = false
}

variable "enable_query_logging" {
  description = "Enable Route53 query logging"
  type        = bool
  default     = false
}

variable "query_log_retention_days" {
  description = "Retention period for Route53 query logs"
  type        = number
  default     = 30
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.query_log_retention_days)
    error_message = "Query log retention days must be a valid CloudWatch log retention value."
  }
}

# Monitoring Configuration
variable "enable_dns_monitoring" {
  description = "Enable DNS monitoring and alerting"
  type        = bool
  default     = true
}

variable "dns_query_threshold" {
  description = "Threshold for DNS query rate alarms"
  type        = number
  default     = 1000
  validation {
    condition     = var.dns_query_threshold > 0
    error_message = "DNS query threshold must be greater than 0."
  }
}

variable "enable_dnssec" {
  description = "Enable DNSSEC for the hosted zone"
  type        = bool
  default     = false
}

# Traffic Policy Configuration
variable "enable_traffic_policies" {
  description = "Enable Route53 traffic policies for advanced routing"
  type        = bool
  default     = false
}

variable "traffic_policies" {
  description = "Map of traffic policies configuration"
  type = map(object({
    name           = string
    type           = string
    version        = number
    comment        = optional(string, "")
    document       = string
  }))
  default = {}
}

# Geolocation Routing
variable "enable_geolocation_routing" {
  description = "Enable geolocation-based routing"
  type        = bool
  default     = false
}

variable "geolocation_records" {
  description = "Map of geolocation routing records"
  type = map(object({
    continent   = optional(string)
    country     = optional(string)
    subdivision = optional(string)
    records     = list(string)
    ttl         = optional(number, 300)
  }))
  default = {}
}

# Latency Routing
variable "enable_latency_routing" {
  description = "Enable latency-based routing"
  type        = bool
  default     = false
}

variable "latency_records" {
  description = "Map of latency routing records"
  type = map(object({
    region  = string
    records = list(string)
    ttl     = optional(number, 300)
  }))
  default = {}
}

# Weighted Routing
variable "enable_weighted_routing" {
  description = "Enable weighted routing"
  type        = bool
  default     = false
}

variable "weighted_records" {
  description = "Map of weighted routing records"
  type = map(object({
    weight  = number
    records = list(string)
    ttl     = optional(number, 300)
  }))
  default = {}
}

# Multi-Value Routing
variable "enable_multivalue_routing" {
  description = "Enable multi-value answer routing"
  type        = bool
  default     = false
}

variable "multivalue_records" {
  description = "Map of multi-value routing records"
  type = map(object({
    records          = list(string)
    ttl              = optional(number, 300)
    health_check_id  = optional(string)
  }))
  default = {}
}

# Cost Optimization
variable "enable_cost_optimization" {
  description = "Enable DNS cost optimization features"
  type        = bool
  default     = true
}

variable "optimize_health_check_regions" {
  description = "Optimize health check regions to reduce costs"
  type        = bool
  default     = true
}

variable "health_check_regions" {
  description = "List of regions for health checks (empty for all regions)"
  type        = list(string)
  default     = []
}

# Backup and Recovery
variable "enable_dns_backup" {
  description = "Enable automated DNS configuration backup"
  type        = bool
  default     = true
}

variable "backup_schedule" {
  description = "Cron expression for DNS configuration backup"
  type        = string
  default     = "cron(0 2 * * ? *)"  # Daily at 2 AM
}

# Integration Configuration
variable "enable_cloudwatch_integration" {
  description = "Enable CloudWatch integration for DNS metrics"
  type        = bool
  default     = true
}

variable "enable_sns_notifications" {
  description = "Enable SNS notifications for DNS events"
  type        = bool
  default     = false
}

variable "sns_topic_arn" {
  description = "SNS topic ARN for DNS notifications"
  type        = string
  default     = ""
}

# Performance Configuration
variable "resolver_endpoint_type" {
  description = "Type of resolver endpoint (IPV4 or DUALSTACK)"
  type        = string
  default     = "IPV4"
  validation {
    condition     = contains(["IPV4", "DUALSTACK"], var.resolver_endpoint_type)
    error_message = "Resolver endpoint type must be either IPV4 or DUALSTACK."
  }
}

variable "dns_cache_ttl" {
  description = "Default TTL for DNS caching"
  type        = number
  default     = 300
  validation {
    condition     = var.dns_cache_ttl >= 60 && var.dns_cache_ttl <= 86400
    error_message = "DNS cache TTL must be between 60 and 86400 seconds."
  }
}

# Security Configuration
variable "enable_dns_firewall" {
  description = "Enable Route53 Resolver DNS Firewall"
  type        = bool
  default     = false
}

variable "dns_firewall_rules" {
  description = "Map of DNS firewall rules"
  type = map(object({
    name           = string
    action         = string
    block_response = optional(string, "NODATA")
    block_override_domain = optional(string)
    block_override_ttl    = optional(number, 300)
    domains        = list(string)
    priority       = number
  }))
  default = {}
}

# Resource Tagging
variable "tags" {
  description = "Tags to apply to all DNS resources"
  type        = map(string)
  default     = {}
}

variable "additional_dns_tags" {
  description = "Additional tags specific to DNS resources"
  type        = map(string)
  default = {
    Service = "dns"
    Type    = "infrastructure"
  }
}