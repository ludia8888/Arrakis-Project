# DNS Module Outputs
# Output values for use by other modules and main configuration

# Hosted Zone Information
output "hosted_zone_id" {
  description = "ID of the Route53 hosted zone"
  value       = local.hosted_zone_id
}

output "hosted_zone_name_servers" {
  description = "Name servers for the hosted zone"
  value       = local.name_servers
}

output "hosted_zone_zone_id" {
  description = "Zone ID of the hosted zone (same as hosted_zone_id)"
  value       = local.hosted_zone_id
}

# SSL Certificate Information
output "certificate_arn" {
  description = "ARN of the SSL certificate"
  value       = aws_acm_certificate.main.arn
}

output "certificate_domain_name" {
  description = "Domain name of the SSL certificate"
  value       = aws_acm_certificate.main.domain_name
}

output "certificate_subject_alternative_names" {
  description = "Subject alternative names of the SSL certificate"
  value       = aws_acm_certificate.main.subject_alternative_names
}

output "certificate_validation_fqdns" {
  description = "FQDNs used for certificate validation"
  value       = [for record in aws_route53_record.cert_validation : record.fqdn]
}

# Main Domain Records
output "main_domain_fqdn" {
  description = "Fully qualified domain name of the main domain"
  value       = var.domain_name
}

output "main_domain_record_name" {
  description = "Name of the main domain A record"
  value       = var.load_balancer_dns_name != "" ? aws_route53_record.main[0].name : null
}

output "www_domain_record_name" {
  description = "Name of the www subdomain record"
  value       = var.create_www_redirect && var.load_balancer_dns_name != "" ? aws_route53_record.www[0].name : null
}

# Subdomain Information
output "subdomain_records" {
  description = "Map of subdomain record information"
  value = {
    for k, v in aws_route53_record.subdomains : k => {
      name = v.name
      fqdn = v.fqdn
      type = v.type
    }
  }
}

output "subdomain_fqdns" {
  description = "List of subdomain FQDNs"
  value = [
    for record in aws_route53_record.subdomains : record.fqdn
  ]
}

# Health Check Information
output "main_health_check_id" {
  description = "ID of the main domain health check"
  value       = var.enable_health_checks && var.load_balancer_dns_name != "" ? aws_route53_health_check.main[0].id : null
}

output "subdomain_health_check_ids" {
  description = "Map of subdomain health check IDs"
  value = {
    for k, v in aws_route53_health_check.subdomains : k => v.id
  }
}

output "health_check_cloudwatch_alarm_arns" {
  description = "Map of CloudWatch alarm ARNs for health checks"
  value = merge(
    var.enable_health_checks && var.enable_health_check_alarms && var.load_balancer_dns_name != "" ? {
      main = aws_cloudwatch_metric_alarm.health_check_main[0].arn
    } : {},
    {
      for k, v in aws_cloudwatch_metric_alarm.health_check_subdomains : k => v.arn
    }
  )
}

# Failover Configuration
output "failover_enabled" {
  description = "Whether failover routing is enabled"
  value       = var.enable_failover
}

output "failover_records" {
  description = "Map of failover record information"
  value = var.enable_failover && var.failover_load_balancer_dns_name != "" ? {
    main = {
      name = aws_route53_record.failover_main[0].name
      fqdn = aws_route53_record.failover_main[0].fqdn
    }
    subdomains = {
      for k, v in aws_route53_record.failover_subdomains : k => {
        name = v.name
        fqdn = v.fqdn
      }
    }
  } : {}
}

# Email Configuration
output "mx_records" {
  description = "MX records for email"
  value       = var.mx_records
}

output "spf_record" {
  description = "SPF record for email security"
  value       = var.spf_record
}

output "dmarc_record" {
  description = "DMARC record for email security"
  value       = var.dmarc_record
}

output "dkim_records" {
  description = "DKIM records for email authentication"
  value       = var.dkim_records
}

# Security Records
output "caa_records" {
  description = "CAA records for certificate authority authorization"
  value       = var.caa_records
}

output "txt_records" {
  description = "TXT records for domain verification"
  value       = var.txt_records
}

# Other DNS Records
output "cname_records" {
  description = "CNAME records for external services"
  value = {
    for k, v in aws_route53_record.cname : k => {
      name   = v.name
      fqdn   = v.fqdn
      target = v.records[0]
    }
  }
}

output "ns_records" {
  description = "NS records for subdomain delegation"
  value = {
    for k, v in aws_route53_record.ns : k => {
      name         = v.name
      fqdn         = v.fqdn
      name_servers = v.records
    }
  }
}

# Private DNS Information
output "private_dns_enabled" {
  description = "Whether private DNS is enabled"
  value       = var.enable_private_dns
}

output "private_hosted_zone_id" {
  description = "ID of the private hosted zone"
  value       = var.enable_private_dns && var.private_domain_name != "" ? aws_route53_zone.private[0].zone_id : null
}

output "private_domain_name" {
  description = "Private domain name for internal services"
  value       = var.private_domain_name
}

output "resolver_endpoint_ids" {
  description = "Map of Route53 Resolver endpoint IDs"
  value = var.enable_private_dns ? {
    inbound  = aws_route53_resolver_endpoint.inbound[0].id
    outbound = aws_route53_resolver_endpoint.outbound[0].id
  } : {}
}

output "resolver_rule_ids" {
  description = "Map of Route53 Resolver rule IDs"
  value = {
    for k, v in aws_route53_resolver_rule.private : k => v.id
  }
}

output "internal_service_records" {
  description = "Map of internal service DNS records"
  value = {
    for k, v in aws_route53_record.internal_services : k => {
      name = v.name
      fqdn = v.fqdn
      type = v.type
    }
  }
}

# Advanced Features
output "query_logging_enabled" {
  description = "Whether Route53 query logging is enabled"
  value       = var.enable_query_logging
}

output "query_log_group_name" {
  description = "CloudWatch log group name for Route53 queries"
  value       = var.enable_query_logging ? aws_cloudwatch_log_group.route53_queries[0].name : null
}

output "query_log_group_arn" {
  description = "CloudWatch log group ARN for Route53 queries"
  value       = var.enable_query_logging ? aws_cloudwatch_log_group.route53_queries[0].arn : null
}

# DNS Configuration Summary
output "dns_configuration" {
  description = "Summary of DNS configuration"
  value = {
    domain_name              = var.domain_name
    hosted_zone_id          = local.hosted_zone_id
    ssl_certificate_arn     = aws_acm_certificate.main.arn
    health_checks_enabled   = var.enable_health_checks
    failover_enabled        = var.enable_failover
    private_dns_enabled     = var.enable_private_dns
    query_logging_enabled   = var.enable_query_logging
    subdomains_count        = length(var.subdomains)
    mx_records_configured   = length(var.mx_records) > 0
    email_security_enabled  = var.spf_record != "" || var.dmarc_record != "" || length(var.dkim_records) > 0
    caa_records_configured  = length(var.caa_records) > 0
  }
}

# Resource Counts
output "dns_resource_counts" {
  description = "Count of DNS resources created"
  value = {
    hosted_zones          = var.create_hosted_zone ? 1 : 0
    private_hosted_zones  = var.enable_private_dns && var.private_domain_name != "" ? 1 : 0
    ssl_certificates      = 1
    a_records            = (var.load_balancer_dns_name != "" ? 1 : 0) + length(var.subdomains)
    cname_records        = length(var.cname_records)
    txt_records          = length(var.txt_records) + (var.spf_record != "" ? 1 : 0) + (var.dmarc_record != "" ? 1 : 0) + length(var.dkim_records)
    mx_records           = length(var.mx_records) > 0 ? 1 : 0
    ns_records           = length(var.ns_records)
    caa_records          = length(var.caa_records) > 0 ? 1 : 0
    health_checks        = var.enable_health_checks ? (var.load_balancer_dns_name != "" ? 1 : 0) + length([for k, v in var.subdomains : k if lookup(v, "health_check", true) && lookup(v, "alias", false)]) : 0
    cloudwatch_alarms    = var.enable_health_checks && var.enable_health_check_alarms ? (var.load_balancer_dns_name != "" ? 1 : 0) + length([for k, v in var.subdomains : k if lookup(v, "health_check", true) && lookup(v, "alias", false)]) : 0
    resolver_endpoints   = var.enable_private_dns ? 2 : 0
    resolver_rules       = length(var.private_dns_rules)
    internal_records     = length(var.internal_service_records)
  }
}

# Security Information
output "dns_security_features" {
  description = "DNS security features status"
  value = {
    ssl_certificate_validation = "dns"
    certificate_transparency   = true
    caa_records_enabled       = length(var.caa_records) > 0
    email_security = {
      spf_enabled   = var.spf_record != ""
      dmarc_enabled = var.dmarc_record != ""
      dkim_enabled  = length(var.dkim_records) > 0
    }
    health_monitoring = {
      health_checks_enabled = var.enable_health_checks
      cloudwatch_alarms     = var.enable_health_check_alarms
    }
    query_logging = {
      enabled           = var.enable_query_logging
      retention_days    = var.query_log_retention_days
    }
    private_dns = {
      enabled             = var.enable_private_dns
      resolver_configured = var.enable_private_dns
      internal_zone       = var.private_domain_name != ""
    }
  }
}

# Performance Metrics
output "dns_performance_config" {
  description = "DNS performance configuration"
  value = {
    default_ttl            = local.ttl_config.medium
    health_check_interval  = 30
    health_check_threshold = 3
    resolver_endpoint_type = var.resolver_endpoint_type
    cache_ttl             = var.dns_cache_ttl
  }
}

# Cost Optimization
output "dns_cost_optimization" {
  description = "DNS cost optimization settings"
  value = {
    cost_optimization_enabled    = var.enable_cost_optimization
    health_check_regions_optimized = var.optimize_health_check_regions
    health_check_regions_count     = length(var.health_check_regions) > 0 ? length(var.health_check_regions) : 15  # Default AWS regions
    query_logging_cost_impact      = var.enable_query_logging ? "enabled" : "disabled"
  }
}

# Integration Status
output "integration_status" {
  description = "Status of integrations with other AWS services"
  value = {
    cloudwatch_integration = var.enable_cloudwatch_integration
    sns_notifications     = var.enable_sns_notifications
    sns_topic_configured  = var.sns_topic_arn != ""
    advanced_features     = var.enable_advanced_features
    dns_firewall         = var.enable_dns_firewall
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

# Backup and Recovery
output "backup_configuration" {
  description = "DNS backup and recovery configuration"
  value = {
    backup_enabled = var.enable_dns_backup
    backup_schedule = var.backup_schedule
    hosted_zone_exportable = true
    records_exportable = true
  }
}

# Monitoring Configuration
output "monitoring_configuration" {
  description = "DNS monitoring configuration"
  value = {
    dns_monitoring_enabled = var.enable_dns_monitoring
    query_threshold       = var.dns_query_threshold
    health_checks = {
      enabled = var.enable_health_checks
      port    = var.health_check_port
      path    = var.health_check_path
      alarms  = var.enable_health_check_alarms
    }
  }
}

# Load Balancer Integration
output "load_balancer_integration" {
  description = "Load balancer integration details"
  value = {
    primary = {
      dns_name = var.load_balancer_dns_name
      zone_id  = var.load_balancer_zone_id
      configured = var.load_balancer_dns_name != ""
    }
    failover = {
      dns_name = var.failover_load_balancer_dns_name
      zone_id  = var.failover_load_balancer_zone_id
      configured = var.failover_load_balancer_dns_name != ""
      enabled = var.enable_failover
    }
  }
}

# Routing Policies
output "routing_policies" {
  description = "DNS routing policies configuration"
  value = {
    simple_routing      = !var.enable_failover && !var.enable_geolocation_routing && !var.enable_latency_routing && !var.enable_weighted_routing
    failover_routing    = var.enable_failover
    geolocation_routing = var.enable_geolocation_routing
    latency_routing     = var.enable_latency_routing
    weighted_routing    = var.enable_weighted_routing
    multivalue_routing  = var.enable_multivalue_routing
    traffic_policies    = var.enable_traffic_policies
  }
}

# Tags Information
output "dns_tags" {
  description = "Tags applied to DNS resources"
  value = merge(
    var.tags,
    var.additional_dns_tags,
    {
      Project = var.project_name
      Environment = var.environment
      Module = "dns"
    }
  )
}