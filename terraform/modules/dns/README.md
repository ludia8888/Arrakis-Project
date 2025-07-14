# DNS Terraform Module

Comprehensive DNS infrastructure for the Arrakis platform with enterprise-grade Route53 configuration, SSL certificate management, health checks, failover routing, and advanced DNS features.

## Features

- **Route53 Hosted Zone**: Automated DNS zone management with delegation
- **SSL Certificate Management**: Automated ACM certificate provisioning and validation
- **Health Checks**: Route53 health monitoring with CloudWatch integration
- **Failover Routing**: Multi-region disaster recovery with automatic failover
- **Private DNS**: Internal service discovery with Route53 Resolver
- **Email Security**: SPF, DMARC, and DKIM record management
- **DNS Security**: CAA records and DNS firewall integration
- **Advanced Routing**: Geolocation, latency, weighted, and multi-value routing
- **Query Logging**: CloudWatch integration for DNS query analysis
- **Cost Optimization**: Intelligent health check region selection

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      DNS Architecture                       │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │
│  │   Public      │  │   SSL         │  │   Health      │   │
│  │   Hosted      │  │   Certificate │  │   Checks &    │   │
│  │   Zone        │  │   Management  │  │   Monitoring  │   │
│  │               │  │               │  │               │   │
│  │ • Domain      │  │ • ACM Cert    │  │ • Route53     │   │
│  │   Records     │  │ • DNS Valid   │  │   Health      │   │
│  │ • Subdomains  │  │ • Auto Renew  │  │ • CloudWatch  │   │
│  │ • Aliases     │  │ • Wildcard    │  │ • Failover    │   │
│  └───────────────┘  └───────────────┘  └───────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │
│  │   Private     │  │   Email       │  │   Advanced    │   │
│  │   DNS &       │  │   Security &  │  │   Routing &   │   │
│  │   Resolver    │  │   Records     │  │   Policies    │   │
│  │               │  │               │  │               │   │
│  │ • Internal    │  │ • MX Records  │  │ • Geolocation │   │
│  │   Services    │  │ • SPF/DMARC   │  │ • Latency     │   │
│  │ • VPC DNS     │  │ • DKIM Auth   │  │ • Weighted    │   │
│  │ • Resolver    │  │ • CAA Records │  │ • Multi-Value │   │
│  └───────────────┘  └───────────────┘  └───────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

```hcl
module "dns" {
  source = "./modules/dns"

  project_name = "arrakis"
  environment  = "production"
  
  domain_name = "arrakis.example.com"
  
  # Load balancer integration
  load_balancer_dns_name = "k8s-arrakis-ingress-12345678.us-west-2.elb.amazonaws.com"
  load_balancer_zone_id  = "Z1D633PJN98FT9"
  
  # Subdomains
  subdomains = {
    api = {
      type  = "A"
      alias = true
    }
    monitoring = {
      type  = "A"
      alias = true
    }
  }
  
  # Health checks
  enable_health_checks = true
  health_check_path    = "/health"
  
  tags = {
    Environment = "production"
    Project     = "arrakis"
  }
}
```

## Configuration

### Core Configuration

| Variable | Description | Type | Default | Required |
|----------|-------------|------|---------|----------|
| `project_name` | Name of the project | `string` | - | yes |
| `environment` | Environment (development, staging, production) | `string` | - | yes |
| `domain_name` | Primary domain name | `string` | - | yes |
| `create_hosted_zone` | Create new hosted zone or use existing | `bool` | `true` | no |

### Load Balancer Integration

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `load_balancer_dns_name` | DNS name of the load balancer | `string` | `""` |
| `load_balancer_zone_id` | Zone ID of the load balancer | `string` | `""` |

### SSL Certificate Configuration

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `certificate_sans` | Subject Alternative Names for SSL certificate | `list(string)` | `[]` |

### Subdomain Configuration

```hcl
subdomains = {
  api = {
    type         = "A"           # Record type: A, CNAME, etc.
    alias        = true          # Use alias record (for load balancers)
    records      = []            # For non-alias records
    ttl          = 300           # TTL in seconds
    health_check = true          # Enable health check
  }
  docs = {
    type    = "CNAME"
    alias   = false
    records = ["documentation.example.com"]
    ttl     = 3600
  }
}
```

### Health Check Configuration

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `enable_health_checks` | Enable Route53 health checks | `bool` | `true` |
| `health_check_port` | Port for health checks | `number` | `443` |
| `health_check_path` | Path for health checks | `string` | `"/health"` |
| `enable_health_check_alarms` | Enable CloudWatch alarms | `bool` | `true` |

### Failover Configuration

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `enable_failover` | Enable DNS failover routing | `bool` | `false` |
| `failover_load_balancer_dns_name` | Failover load balancer DNS name | `string` | `""` |
| `failover_load_balancer_zone_id` | Failover load balancer zone ID | `string` | `""` |

## SSL Certificate Management

### Automatic Certificate Provisioning
```hcl
# Certificate with multiple domains
certificate_sans = [
  "*.arrakis.example.com",    # Wildcard for all subdomains
  "api.arrakis.example.com",  # Specific subdomain
  "docs.arrakis.example.com"
]
```

### Features
- **DNS Validation**: Automated Route53 validation
- **Auto-Renewal**: AWS ACM handles renewal automatically
- **Wildcard Support**: Single certificate for all subdomains
- **Multi-Domain**: Support for multiple domain validation

## Health Checks and Monitoring

### Health Check Configuration
```hcl
enable_health_checks = true
health_check_port    = 443
health_check_path    = "/health"
enable_health_check_alarms = true
health_check_alarm_actions = [
  "arn:aws:sns:us-west-2:123456789012:dns-alerts"
]
```

### Monitoring Features
- **Endpoint Health**: HTTP/HTTPS health monitoring
- **CloudWatch Integration**: Metrics and alarms
- **Multi-Region Checks**: Global health validation
- **Custom Alarm Actions**: SNS notifications for failures

## Failover and Disaster Recovery

### Primary-Secondary Failover
```hcl
enable_failover = true

# Primary load balancer (us-west-2)
load_balancer_dns_name = "primary-lb.us-west-2.elb.amazonaws.com"
load_balancer_zone_id  = "Z1D633PJN98FT9"

# Secondary load balancer (us-east-1)
failover_load_balancer_dns_name = "secondary-lb.us-east-1.elb.amazonaws.com"
failover_load_balancer_zone_id  = "Z35SXDOTRQ7X7K"
```

### Failover Features
- **Automatic Failover**: Route53 health-based routing
- **Multi-Region**: Cross-region disaster recovery
- **Health Integration**: Seamless failover on health check failure
- **Subdomain Support**: Failover for all configured subdomains

## Email Configuration

### MX Records
```hcl
mx_records = [
  "10 mail.example.com.",
  "20 mail2.example.com."
]
```

### Email Security
```hcl
# SPF record
spf_record = "v=spf1 include:_spf.google.com ~all"

# DMARC record
dmarc_record = "v=DMARC1; p=quarantine; rua=mailto:dmarc@example.com"

# DKIM records
dkim_records = {
  "selector1" = "v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBA..."
  "selector2" = "v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBA..."
}
```

## DNS Security

### CAA Records
```hcl
caa_records = [
  "0 issue \"letsencrypt.org\"",
  "0 issue \"amazonaws.com\"",
  "0 iodef \"mailto:security@example.com\""
]
```

### Security Features
- **Certificate Authority Authorization**: Control which CAs can issue certificates
- **DNS Firewall**: Block malicious domains (when enabled)
- **Query Logging**: Monitor DNS queries for security analysis
- **DNSSEC**: Optional DNS Security Extensions support

## Private DNS and Service Discovery

### Internal Service Discovery
```hcl
enable_private_dns = true
vpc_id = "vpc-12345678"
private_domain_name = "internal.arrakis.local"

resolver_subnet_ids = [
  "subnet-12345678",
  "subnet-87654321"
]

resolver_security_group_ids = [
  "sg-12345678"
]

# Internal service records
internal_service_records = {
  "database" = {
    type    = "A"
    records = ["10.0.1.100"]
    ttl     = 300
  }
  "cache" = {
    type    = "A"
    records = ["10.0.1.200"]
    ttl     = 300
  }
}
```

### Private DNS Features
- **Route53 Resolver**: Hybrid DNS with on-premises integration
- **VPC Integration**: Private hosted zones for internal services
- **Service Discovery**: Dynamic service registration
- **Conditional Forwarding**: Forward specific domains to custom resolvers

## Advanced Routing Policies

### Geolocation Routing
```hcl
enable_geolocation_routing = true

geolocation_records = {
  "us-users" = {
    country = "US"
    records = ["1.2.3.4"]
    ttl     = 300
  }
  "eu-users" = {
    continent = "EU"
    records = ["5.6.7.8"]
    ttl     = 300
  }
}
```

### Latency-Based Routing
```hcl
enable_latency_routing = true

latency_records = {
  "us-west-2" = {
    region  = "us-west-2"
    records = ["1.2.3.4"]
    ttl     = 300
  }
  "eu-west-1" = {
    region  = "eu-west-1"
    records = ["5.6.7.8"]
    ttl     = 300
  }
}
```

### Weighted Routing
```hcl
enable_weighted_routing = true

weighted_records = {
  "version-a" = {
    weight  = 80
    records = ["1.2.3.4"]
    ttl     = 300
  }
  "version-b" = {
    weight  = 20
    records = ["5.6.7.8"]
    ttl     = 300
  }
}
```

## Query Logging and Analytics

### Enable Query Logging
```hcl
enable_query_logging = true
query_log_retention_days = 30
```

### Features
- **CloudWatch Integration**: All DNS queries logged
- **Security Analysis**: Monitor for suspicious queries
- **Performance Insights**: Query pattern analysis
- **Compliance**: Audit trail for DNS activities

## Cost Optimization

### Health Check Optimization
```hcl
enable_cost_optimization = true
optimize_health_check_regions = true

# Specify specific regions to reduce costs
health_check_regions = [
  "us-west-2",
  "us-east-1",
  "eu-west-1"
]
```

### Cost Features
- **Regional Optimization**: Limit health checks to specific regions
- **TTL Optimization**: Intelligent TTL configuration
- **Resource Consolidation**: Efficient record management
- **Usage Monitoring**: Cost tracking and alerts

## Usage Examples

### Production Environment

```hcl
module "dns" {
  source = "./modules/dns"

  project_name = "arrakis"
  environment  = "production"
  
  # Primary domain
  domain_name = "arrakis.example.com"
  certificate_sans = [
    "*.arrakis.example.com",
    "api.arrakis.example.com",
    "monitoring.arrakis.example.com"
  ]
  
  # Load balancer integration
  load_balancer_dns_name = module.eks_cluster.ingress_load_balancer_dns_name
  load_balancer_zone_id  = module.eks_cluster.ingress_load_balancer_zone_id
  
  # Subdomains with health checks
  subdomains = {
    api = {
      type         = "A"
      alias        = true
      health_check = true
    }
    monitoring = {
      type         = "A"
      alias        = true
      health_check = true
    }
    docs = {
      type    = "CNAME"
      alias   = false
      records = ["arrakis-docs.s3-website-us-west-2.amazonaws.com"]
      ttl     = 3600
      health_check = false
    }
  }
  
  # Disaster recovery
  enable_failover = true
  failover_load_balancer_dns_name = module.eks_cluster_dr.ingress_load_balancer_dns_name
  failover_load_balancer_zone_id  = module.eks_cluster_dr.ingress_load_balancer_zone_id
  
  # Health monitoring
  enable_health_checks = true
  enable_health_check_alarms = true
  health_check_alarm_actions = [
    module.monitoring.sns_topic_arn
  ]
  
  # Email configuration
  mx_records = [
    "10 aspmx.l.google.com.",
    "20 alt1.aspmx.l.google.com."
  ]
  spf_record = "v=spf1 include:_spf.google.com ~all"
  dmarc_record = "v=DMARC1; p=quarantine; rua=mailto:dmarc@arrakis.example.com"
  
  # Security
  caa_records = [
    "0 issue \"letsencrypt.org\"",
    "0 issue \"amazonaws.com\"",
    "0 iodef \"mailto:security@arrakis.example.com\""
  ]
  
  # Private DNS
  enable_private_dns = true
  vpc_id = module.networking.vpc_id
  private_domain_name = "arrakis.internal"
  resolver_subnet_ids = module.networking.private_subnet_ids
  resolver_security_group_ids = [module.networking.dns_security_group_id]
  
  internal_service_records = {
    database = {
      type    = "A"
      records = [module.databases.primary_endpoint_ip]
      ttl     = 300
    }
    cache = {
      type    = "A"
      records = [module.redis.primary_endpoint_ip]
      ttl     = 300
    }
    nats = {
      type    = "A"
      records = [module.nats.cluster_endpoint_ip]
      ttl     = 300
    }
  }
  
  # Monitoring and logging
  enable_query_logging = true
  query_log_retention_days = 90
  
  # Cost optimization
  enable_cost_optimization = true
  optimize_health_check_regions = true
  
  tags = {
    Environment     = "production"
    Project         = "arrakis"
    BusinessUnit    = "platform"
    CostCenter      = "infrastructure"
    SecurityLevel   = "high"
    ComplianceReq   = "soc2,gdpr"
  }
}
```

### Multi-Environment Setup

```hcl
locals {
  environments = {
    development = {
      domain_name = "dev.arrakis.example.com"
      enable_failover = false
      enable_private_dns = false
      health_check_regions = ["us-west-2"]
      query_log_retention = 7
    }
    staging = {
      domain_name = "staging.arrakis.example.com"
      enable_failover = true
      enable_private_dns = true
      health_check_regions = ["us-west-2", "us-east-1"]
      query_log_retention = 30
    }
    production = {
      domain_name = "arrakis.example.com"
      enable_failover = true
      enable_private_dns = true
      health_check_regions = ["us-west-2", "us-east-1", "eu-west-1"]
      query_log_retention = 90
    }
  }
}

module "dns" {
  source = "./modules/dns"

  project_name = "arrakis"
  environment  = var.environment
  
  domain_name = local.environments[var.environment].domain_name
  
  # Environment-specific configuration
  enable_failover    = local.environments[var.environment].enable_failover
  enable_private_dns = local.environments[var.environment].enable_private_dns
  health_check_regions = local.environments[var.environment].health_check_regions
  query_log_retention_days = local.environments[var.environment].query_log_retention
  
  # Common configuration
  load_balancer_dns_name = module.eks_cluster.ingress_load_balancer_dns_name
  load_balancer_zone_id  = module.eks_cluster.ingress_load_balancer_zone_id
  
  subdomains = {
    api = {
      type  = "A"
      alias = true
    }
    monitoring = {
      type  = "A"
      alias = true
    }
  }
  
  enable_health_checks = true
  
  tags = merge(local.common_tags, {
    Environment = var.environment
  })
}
```

## Operations

### DNS Management

```bash
# Check hosted zone information
aws route53 list-hosted-zones-by-name \
  --dns-name arrakis.example.com

# View DNS records
aws route53 list-resource-record-sets \
  --hosted-zone-id Z123456789012345678

# Check health check status
aws route53 get-health-check \
  --health-check-id 12345678-1234-1234-1234-123456789012
```

### Certificate Management

```bash
# Check certificate status
aws acm describe-certificate \
  --certificate-arn arn:aws:acm:us-west-2:123456789012:certificate/12345678-1234-1234-1234-123456789012

# List certificates
aws acm list-certificates \
  --certificate-statuses ISSUED
```

### Health Check Monitoring

```bash
# View health check metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Route53 \
  --metric-name HealthCheckStatus \
  --dimensions Name=HealthCheckId,Value=12345678-1234-1234-1234-123456789012 \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 300 \
  --statistics Average
```

### Query Log Analysis

```bash
# View DNS query logs
aws logs filter-log-events \
  --log-group-name /aws/route53/arrakis.example.com \
  --start-time $(date -d '1 hour ago' +%s)000
```

## Troubleshooting

### Common Issues

1. **Certificate Validation Hanging**
   ```bash
   # Check DNS validation records
   aws route53 list-resource-record-sets \
     --hosted-zone-id Z123456789012345678 \
     --query "ResourceRecordSets[?Type=='CNAME' && contains(Name, '_acm-challenge')]"
   ```

2. **Health Check Failures**
   ```bash
   # Test health check endpoint
   curl -I https://arrakis.example.com/health
   
   # Check security groups and NACLs
   # Ensure port 443/80 is accessible from Route53 health checkers
   ```

3. **Failover Not Working**
   ```bash
   # Verify health check configuration
   aws route53 get-health-check \
     --health-check-id 12345678-1234-1234-1234-123456789012
   
   # Check failover routing policy
   aws route53 list-resource-record-sets \
     --hosted-zone-id Z123456789012345678 \
     --query "ResourceRecordSets[?SetIdentifier=='primary' || SetIdentifier=='secondary']"
   ```

### Performance Optimization

1. **TTL Optimization**
   - Use appropriate TTL values based on record type
   - Short TTL (300s) for frequently changing records
   - Long TTL (86400s) for static records

2. **Health Check Optimization**
   - Limit health check regions to reduce costs
   - Use efficient health check endpoints
   - Configure appropriate thresholds

3. **Query Optimization**
   - Enable query logging for analysis
   - Monitor query patterns and optimize
   - Use Route53 Resolver for hybrid setups

## Security Best Practices

### 1. Domain Security
- Implement CAA records to control certificate issuance
- Use DNS Security Extensions (DNSSEC) where supported
- Monitor DNS queries for suspicious activity

### 2. Certificate Management
- Use DNS validation for automated certificate renewal
- Implement certificate transparency monitoring
- Regular certificate rotation and monitoring

### 3. Access Controls
- Restrict Route53 API access with IAM policies
- Use resource-based policies for hosted zones
- Monitor DNS configuration changes

### 4. Email Security
- Implement SPF, DKIM, and DMARC records
- Monitor email authentication failures
- Regular review of email security policies

## Compliance and Governance

### Supported Standards
- **SOC 2**: DNS security and monitoring controls
- **GDPR**: DNS query logging and data protection
- **HIPAA**: Healthcare data routing requirements
- **PCI DSS**: Payment data protection standards

### Audit Features
- **CloudTrail Integration**: All Route53 API calls logged
- **Query Logging**: DNS query audit trail
- **Change Tracking**: DNS record modification history
- **Access Monitoring**: Route53 access and permissions

## Contributing

When contributing to this module:

1. **Testing**: Validate DNS resolution and health checks
2. **Documentation**: Update README for new features
3. **Security**: Follow DNS security best practices
4. **Performance**: Test DNS resolution performance
5. **Compliance**: Ensure compliance requirements are met

## Support

For DNS-related issues:

1. **Resolution Issues**: Check DNS propagation and TTL settings
2. **Certificate Issues**: Verify DNS validation records
3. **Health Check Issues**: Check endpoint accessibility and security groups
4. **Performance Issues**: Analyze query patterns and optimize TTL

---

**DNS Notice**: This module implements enterprise-grade DNS infrastructure with automated SSL certificate management, health monitoring, and advanced routing capabilities. Regular monitoring and maintenance of DNS configuration is essential for optimal performance and security.