# DNS Module - Route53 Configuration
# Production-ready DNS management for Arrakis platform

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Local variables
locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name

  # Extract domain components
  domain_parts = split(".", var.domain_name)
  root_domain  = length(local.domain_parts) > 2 ? join(".", slice(local.domain_parts, 1, length(local.domain_parts))) : var.domain_name
  subdomain    = length(local.domain_parts) > 2 ? local.domain_parts[0] : null

  # DNS configuration
  ttl_config = {
    short  = 300   # 5 minutes
    medium = 3600  # 1 hour
    long   = 86400 # 24 hours
  }

  # Health check configuration
  health_check_config = {
    type                            = "HTTPS"
    resource_path                   = "/health"
    failure_threshold               = 3
    request_interval                = 30
    cloudwatch_alarm_region         = local.region
    insufficient_data_health_status = "Failure"
  }
}

# Route53 Hosted Zone
resource "aws_route53_zone" "main" {
  count = var.create_hosted_zone ? 1 : 0

  name    = var.domain_name
  comment = "Hosted zone for ${var.project_name} ${var.environment} environment"

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-zone"
    Type        = "hosted-zone"
    Environment = var.environment
    Project     = var.project_name
  })
}

# Data source for existing hosted zone
data "aws_route53_zone" "existing" {
  count = var.create_hosted_zone ? 0 : 1

  name         = var.domain_name
  private_zone = false
}

# Local reference to hosted zone
locals {
  hosted_zone_id = var.create_hosted_zone ? aws_route53_zone.main[0].zone_id : data.aws_route53_zone.existing[0].zone_id
  name_servers   = var.create_hosted_zone ? aws_route53_zone.main[0].name_servers : data.aws_route53_zone.existing[0].name_servers
}

# SSL Certificate for the main domain
resource "aws_acm_certificate" "main" {
  domain_name               = var.domain_name
  subject_alternative_names = var.certificate_sans
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-cert"
    Type = "ssl-certificate"
  })
}

# DNS validation records for SSL certificate
resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.main.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = local.ttl_config.short
  type            = each.value.type
  zone_id         = local.hosted_zone_id
}

# SSL Certificate validation
resource "aws_acm_certificate_validation" "main" {
  certificate_arn         = aws_acm_certificate.main.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]

  timeouts {
    create = "5m"
  }
}

# Main domain A record (apex domain)
resource "aws_route53_record" "main" {
  count = var.load_balancer_dns_name != "" ? 1 : 0

  zone_id = local.hosted_zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = var.load_balancer_dns_name
    zone_id                = var.load_balancer_zone_id
    evaluate_target_health = var.enable_health_checks
  }

  set_identifier = var.enable_failover ? "primary" : null

  dynamic "failover_routing_policy" {
    for_each = var.enable_failover ? [1] : []
    content {
      type = "PRIMARY"
    }
  }

  dynamic "health_check_id" {
    for_each = var.enable_health_checks ? [aws_route53_health_check.main[0].id] : []
    content {
      value = health_check_id.value
    }
  }
}

# WWW subdomain redirect
resource "aws_route53_record" "www" {
  count = var.create_www_redirect && var.load_balancer_dns_name != "" ? 1 : 0

  zone_id = local.hosted_zone_id
  name    = "www.${var.domain_name}"
  type    = "A"

  alias {
    name                   = var.load_balancer_dns_name
    zone_id                = var.load_balancer_zone_id
    evaluate_target_health = var.enable_health_checks
  }
}

# Subdomain records
resource "aws_route53_record" "subdomains" {
  for_each = var.subdomains

  zone_id = local.hosted_zone_id
  name    = "${each.key}.${var.domain_name}"
  type    = each.value.type

  # Conditional alias configuration
  dynamic "alias" {
    for_each = lookup(each.value, "alias", false) && var.load_balancer_dns_name != "" ? [1] : []
    content {
      name                   = var.load_balancer_dns_name
      zone_id                = var.load_balancer_zone_id
      evaluate_target_health = var.enable_health_checks
    }
  }

  # Conditional simple records
  ttl     = lookup(each.value, "alias", false) ? null : lookup(each.value, "ttl", local.ttl_config.medium)
  records = lookup(each.value, "alias", false) ? null : lookup(each.value, "records", [])

  set_identifier = var.enable_failover ? "${each.key}-primary" : null

  dynamic "failover_routing_policy" {
    for_each = var.enable_failover ? [1] : []
    content {
      type = "PRIMARY"
    }
  }

  dynamic "health_check_id" {
    for_each = var.enable_health_checks && lookup(each.value, "health_check", true) ? [aws_route53_health_check.subdomains[each.key].id] : []
    content {
      value = health_check_id.value
    }
  }
}

# Health checks for main domain
resource "aws_route53_health_check" "main" {
  count = var.enable_health_checks && var.load_balancer_dns_name != "" ? 1 : 0

  fqdn                            = var.domain_name
  port                            = var.health_check_port
  type                            = local.health_check_config.type
  resource_path                   = var.health_check_path
  failure_threshold               = local.health_check_config.failure_threshold
  request_interval                = local.health_check_config.request_interval
  cloudwatch_alarm_region         = local.health_check_config.cloudwatch_alarm_region
  insufficient_data_health_status = local.health_check_config.insufficient_data_health_status

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-main-health-check"
    Type = "health-check"
  })
}

# Health checks for subdomains
resource "aws_route53_health_check" "subdomains" {
  for_each = var.enable_health_checks ? {
    for k, v in var.subdomains : k => v
    if lookup(v, "health_check", true) && lookup(v, "alias", false)
  } : {}

  fqdn                            = "${each.key}.${var.domain_name}"
  port                            = var.health_check_port
  type                            = local.health_check_config.type
  resource_path                   = var.health_check_path
  failure_threshold               = local.health_check_config.failure_threshold
  request_interval                = local.health_check_config.request_interval
  cloudwatch_alarm_region         = local.health_check_config.cloudwatch_alarm_region
  insufficient_data_health_status = local.health_check_config.insufficient_data_health_status

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-${each.key}-health-check"
    Type = "health-check"
  })
}

# Failover records for disaster recovery
resource "aws_route53_record" "failover_main" {
  count = var.enable_failover && var.failover_load_balancer_dns_name != "" ? 1 : 0

  zone_id = local.hosted_zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = var.failover_load_balancer_dns_name
    zone_id                = var.failover_load_balancer_zone_id
    evaluate_target_health = false
  }

  set_identifier = "secondary"

  failover_routing_policy {
    type = "SECONDARY"
  }
}

resource "aws_route53_record" "failover_subdomains" {
  for_each = var.enable_failover && var.failover_load_balancer_dns_name != "" ? var.subdomains : {}

  zone_id = local.hosted_zone_id
  name    = "${each.key}.${var.domain_name}"
  type    = each.value.type

  dynamic "alias" {
    for_each = lookup(each.value, "alias", false) ? [1] : []
    content {
      name                   = var.failover_load_balancer_dns_name
      zone_id                = var.failover_load_balancer_zone_id
      evaluate_target_health = false
    }
  }

  ttl     = lookup(each.value, "alias", false) ? null : lookup(each.value, "ttl", local.ttl_config.medium)
  records = lookup(each.value, "alias", false) ? null : var.failover_records[each.key]

  set_identifier = "${each.key}-secondary"

  failover_routing_policy {
    type = "SECONDARY"
  }
}

# MX records for email
resource "aws_route53_record" "mx" {
  count = length(var.mx_records) > 0 ? 1 : 0

  zone_id = local.hosted_zone_id
  name    = var.domain_name
  type    = "MX"
  ttl     = local.ttl_config.long
  records = var.mx_records
}

# TXT records for domain verification and security
resource "aws_route53_record" "txt" {
  for_each = var.txt_records

  zone_id = local.hosted_zone_id
  name    = each.key == "@" ? var.domain_name : "${each.key}.${var.domain_name}"
  type    = "TXT"
  ttl     = local.ttl_config.medium
  records = each.value
}

# SPF record for email security
resource "aws_route53_record" "spf" {
  count = var.spf_record != "" ? 1 : 0

  zone_id = local.hosted_zone_id
  name    = var.domain_name
  type    = "TXT"
  ttl     = local.ttl_config.medium
  records = [var.spf_record]
}

# DMARC record for email security
resource "aws_route53_record" "dmarc" {
  count = var.dmarc_record != "" ? 1 : 0

  zone_id = local.hosted_zone_id
  name    = "_dmarc.${var.domain_name}"
  type    = "TXT"
  ttl     = local.ttl_config.medium
  records = [var.dmarc_record]
}

# DKIM records for email authentication
resource "aws_route53_record" "dkim" {
  for_each = var.dkim_records

  zone_id = local.hosted_zone_id
  name    = "${each.key}._domainkey.${var.domain_name}"
  type    = "TXT"
  ttl     = local.ttl_config.medium
  records = [each.value]
}

# CAA records for certificate authority authorization
resource "aws_route53_record" "caa" {
  count = length(var.caa_records) > 0 ? 1 : 0

  zone_id = local.hosted_zone_id
  name    = var.domain_name
  type    = "CAA"
  ttl     = local.ttl_config.long
  records = var.caa_records
}

# CNAME records for external services
resource "aws_route53_record" "cname" {
  for_each = var.cname_records

  zone_id = local.hosted_zone_id
  name    = "${each.key}.${var.domain_name}"
  type    = "CNAME"
  ttl     = local.ttl_config.medium
  records = [each.value]
}

# NS records for subdomain delegation
resource "aws_route53_record" "ns" {
  for_each = var.ns_records

  zone_id = local.hosted_zone_id
  name    = "${each.key}.${var.domain_name}"
  type    = "NS"
  ttl     = local.ttl_config.long
  records = each.value
}

# CloudWatch alarms for health checks
resource "aws_cloudwatch_metric_alarm" "health_check_main" {
  count = var.enable_health_checks && var.enable_health_check_alarms && var.load_balancer_dns_name != "" ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-main-domain-health"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HealthCheckStatus"
  namespace           = "AWS/Route53"
  period              = "60"
  statistic           = "Minimum"
  threshold           = "1"
  alarm_description   = "This metric monitors the health of the main domain"
  alarm_actions       = var.health_check_alarm_actions

  dimensions = {
    HealthCheckId = aws_route53_health_check.main[0].id
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-main-domain-health-alarm"
    Type = "cloudwatch-alarm"
  })
}

resource "aws_cloudwatch_metric_alarm" "health_check_subdomains" {
  for_each = var.enable_health_checks && var.enable_health_check_alarms ? {
    for k, v in var.subdomains : k => v
    if lookup(v, "health_check", true) && lookup(v, "alias", false)
  } : {}

  alarm_name          = "${var.project_name}-${var.environment}-${each.key}-domain-health"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HealthCheckStatus"
  namespace           = "AWS/Route53"
  period              = "60"
  statistic           = "Minimum"
  threshold           = "1"
  alarm_description   = "This metric monitors the health of the ${each.key} subdomain"
  alarm_actions       = var.health_check_alarm_actions

  dimensions = {
    HealthCheckId = aws_route53_health_check.subdomains[each.key].id
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-${each.key}-domain-health-alarm"
    Type = "cloudwatch-alarm"
  })
}

# Route53 Resolver for private DNS
resource "aws_route53_resolver_endpoint" "inbound" {
  count = var.enable_private_dns ? 1 : 0

  name      = "${var.project_name}-${var.environment}-resolver-inbound"
  direction = "INBOUND"

  security_group_ids = var.resolver_security_group_ids

  dynamic "ip_address" {
    for_each = var.resolver_subnet_ids
    content {
      subnet_id = ip_address.value
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-resolver-inbound"
    Type = "resolver-endpoint"
  })
}

resource "aws_route53_resolver_endpoint" "outbound" {
  count = var.enable_private_dns ? 1 : 0

  name      = "${var.project_name}-${var.environment}-resolver-outbound"
  direction = "OUTBOUND"

  security_group_ids = var.resolver_security_group_ids

  dynamic "ip_address" {
    for_each = var.resolver_subnet_ids
    content {
      subnet_id = ip_address.value
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-resolver-outbound"
    Type = "resolver-endpoint"
  })
}

# Route53 Resolver rules for private DNS
resource "aws_route53_resolver_rule" "private" {
  for_each = var.enable_private_dns ? var.private_dns_rules : {}

  domain_name          = each.value.domain_name
  name                 = "${var.project_name}-${var.environment}-${each.key}-rule"
  rule_type            = each.value.rule_type
  resolver_endpoint_id = each.value.rule_type == "FORWARD" ? aws_route53_resolver_endpoint.outbound[0].id : null

  dynamic "target_ip" {
    for_each = lookup(each.value, "target_ips", [])
    content {
      ip   = target_ip.value.ip
      port = lookup(target_ip.value, "port", 53)
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-${each.key}-resolver-rule"
    Type = "resolver-rule"
  })
}

# Associate resolver rules with VPC
resource "aws_route53_resolver_rule_association" "private" {
  for_each = var.enable_private_dns && var.vpc_id != "" ? var.private_dns_rules : {}

  resolver_rule_id = aws_route53_resolver_rule.private[each.key].id
  vpc_id           = var.vpc_id
}

# Private hosted zone for internal services
resource "aws_route53_zone" "private" {
  count = var.enable_private_dns && var.private_domain_name != "" ? 1 : 0

  name    = var.private_domain_name
  comment = "Private hosted zone for ${var.project_name} ${var.environment} internal services"

  vpc {
    vpc_id = var.vpc_id
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-private-zone"
    Type = "private-hosted-zone"
  })
}

# Internal service records
resource "aws_route53_record" "internal_services" {
  for_each = var.enable_private_dns && var.private_domain_name != "" ? var.internal_service_records : {}

  zone_id = aws_route53_zone.private[0].zone_id
  name    = "${each.key}.${var.private_domain_name}"
  type    = each.value.type
  ttl     = lookup(each.value, "ttl", local.ttl_config.medium)
  records = each.value.records
}

# CloudFormation stack for advanced Route53 features
resource "aws_cloudformation_stack" "route53_advanced" {
  count = var.enable_advanced_features ? 1 : 0

  name = "${var.project_name}-${var.environment}-route53-advanced"

  template_body = jsonencode({
    AWSTemplateFormatVersion = "2010-09-09"
    Description = "Advanced Route53 features for ${var.project_name}"

    Resources = {
      QueryLoggingConfig = {
        Type = "AWS::Route53::QueryLoggingConfig"
        Properties = {
          HostedZoneId = local.hosted_zone_id
          CloudWatchLogsLogGroupArn = "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/route53/${var.domain_name}:*"
        }
      }
    }

    Outputs = {
      QueryLoggingConfigId = {
        Value = { Ref = "QueryLoggingConfig" }
        Export = { Name = "${var.project_name}-${var.environment}-query-logging-id" }
      }
    }
  })

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-route53-advanced"
    Type = "cloudformation-stack"
  })
}

# CloudWatch log group for Route53 query logging
resource "aws_cloudwatch_log_group" "route53_queries" {
  count = var.enable_query_logging ? 1 : 0

  name              = "/aws/route53/${var.domain_name}"
  retention_in_days = var.query_log_retention_days

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-route53-queries"
    Type = "log-group"
  })
}
