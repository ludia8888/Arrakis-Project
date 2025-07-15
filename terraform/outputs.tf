# Terraform Outputs for Arrakis Platform Infrastructure
# Output values from the main Terraform configuration

# Environment Information
output "environment" {
  description = "Environment name"
  value       = var.environment
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "project_name" {
  description = "Project name"
  value       = local.project_name
}

# Network Outputs
output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "vpc_cidr" {
  description = "VPC CIDR block"
  value       = module.networking.vpc_cidr_block
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.networking.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.networking.private_subnet_ids
}

output "database_subnet_ids" {
  description = "Database subnet IDs"
  value       = module.networking.database_subnet_ids
}

output "nat_gateway_ips" {
  description = "NAT Gateway public IPs"
  value       = module.networking.nat_gateway_public_ips
}

# Security Group Outputs
output "security_groups" {
  description = "Security group IDs"
  value = {
    eks_cluster   = module.networking.eks_cluster_security_group_id
    eks_nodes     = module.networking.eks_nodes_security_group_id
    rds           = module.networking.rds_security_group_id
    redis         = module.networking.redis_security_group_id
    load_balancer = module.networking.load_balancer_security_group_id
  }
}

# EKS Cluster Outputs
output "eks_cluster_id" {
  description = "EKS cluster ID"
  value       = module.eks_cluster.cluster_id
}

output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks_cluster.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks_cluster.cluster_endpoint
}

output "eks_cluster_version" {
  description = "EKS cluster version"
  value       = module.eks_cluster.cluster_version
}

output "eks_cluster_certificate_authority" {
  description = "EKS cluster certificate authority"
  value       = module.eks_cluster.cluster_certificate_authority_data
  sensitive   = true
}

output "eks_cluster_arn" {
  description = "EKS cluster ARN"
  value       = module.eks_cluster.cluster_arn
}

output "eks_cluster_security_group_id" {
  description = "EKS cluster security group ID"
  value       = module.eks_cluster.cluster_security_group_id
}

output "eks_cluster_oidc_issuer_url" {
  description = "EKS cluster OIDC issuer URL"
  value       = module.eks_cluster.cluster_oidc_issuer_url
}

# EKS Node Groups Outputs
output "eks_node_groups" {
  description = "EKS node groups information"
  value       = module.eks_cluster.node_groups
}

output "eks_node_group_arns" {
  description = "EKS node group ARNs"
  value       = module.eks_cluster.node_group_arns
}

output "eks_node_group_status" {
  description = "EKS node group status"
  value       = module.eks_cluster.node_group_status
}

# Database Outputs
output "database_endpoints" {
  description = "Database endpoints"
  value       = module.databases.database_endpoints
}

output "database_ports" {
  description = "Database ports"
  value       = module.databases.database_ports
}

output "database_arns" {
  description = "Database ARNs"
  value       = module.databases.database_arns
}

output "database_identifiers" {
  description = "Database identifiers"
  value       = module.databases.database_identifiers
}

output "database_security_group_id" {
  description = "Database security group ID"
  value       = module.databases.security_group_id
}

# Redis Outputs
output "redis_primary_endpoint" {
  description = "Redis primary endpoint"
  value       = module.redis.primary_endpoint
}

output "redis_port" {
  description = "Redis port"
  value       = module.redis.port
}

output "redis_auth_token" {
  description = "Redis auth token"
  value       = module.redis.auth_token
  sensitive   = true
}

output "redis_cluster_id" {
  description = "Redis cluster ID"
  value       = module.redis.cluster_id
}

output "redis_security_group_id" {
  description = "Redis security group ID"
  value       = module.redis.security_group_id
}

# NATS Outputs
output "nats_cluster_endpoint" {
  description = "NATS cluster endpoint"
  value       = module.nats.cluster_endpoint
}

output "nats_cluster_port" {
  description = "NATS cluster port"
  value       = module.nats.cluster_port
}

output "nats_namespace" {
  description = "NATS namespace"
  value       = module.nats.namespace
}

output "nats_service_name" {
  description = "NATS service name"
  value       = module.nats.service_name
}

# Monitoring Outputs
output "prometheus_endpoint" {
  description = "Prometheus endpoint"
  value       = module.monitoring.prometheus_endpoint
}

output "grafana_endpoint" {
  description = "Grafana endpoint"
  value       = module.monitoring.grafana_endpoint
}

output "jaeger_endpoint" {
  description = "Jaeger endpoint"
  value       = module.monitoring.jaeger_endpoint
}

output "alertmanager_endpoint" {
  description = "AlertManager endpoint"
  value       = module.monitoring.alertmanager_endpoint
}

output "monitoring_namespace" {
  description = "Monitoring namespace"
  value       = module.monitoring.namespace
}

# Application Outputs
output "application_namespace" {
  description = "Application namespace"
  value       = module.arrakis_services.namespace
}

output "application_services" {
  description = "Application services"
  value       = module.arrakis_services.services
}

output "ingress_load_balancer_dns" {
  description = "Ingress load balancer DNS name"
  value       = module.arrakis_services.ingress_load_balancer_dns_name
}

output "ingress_load_balancer_zone_id" {
  description = "Ingress load balancer zone ID"
  value       = module.arrakis_services.ingress_load_balancer_zone_id
}

output "application_endpoints" {
  description = "Application service endpoints"
  value       = module.arrakis_services.service_endpoints
}

# DNS Outputs
output "dns_zone_id" {
  description = "DNS zone ID"
  value       = length(module.dns) > 0 ? module.dns[0].zone_id : null
}

output "dns_name_servers" {
  description = "DNS name servers"
  value       = length(module.dns) > 0 ? module.dns[0].name_servers : null
}

output "dns_records" {
  description = "DNS records"
  value       = length(module.dns) > 0 ? module.dns[0].records : null
}

# Security Outputs
output "iam_roles" {
  description = "IAM roles created"
  value       = module.security.iam_roles
}

output "service_accounts" {
  description = "Kubernetes service accounts"
  value       = module.security.service_accounts
}

output "secrets_manager_secrets" {
  description = "Secrets Manager secrets"
  value       = module.security.secrets_manager_secrets
}

# Backup Outputs
output "backup_vault_id" {
  description = "Backup vault ID"
  value       = module.backup.vault_id
}

output "backup_plan_id" {
  description = "Backup plan ID"
  value       = module.backup.plan_id
}

output "backup_schedule" {
  description = "Backup schedule"
  value       = module.backup.schedule
}

# Cost Information
output "estimated_monthly_cost" {
  description = "Estimated monthly cost (approximate)"
  value = {
    eks_cluster      = "~$150"
    rds_instances    = "~$200-500"
    redis_cache      = "~$50-100"
    nat_gateways     = "~$45-135"
    load_balancers   = "~$25-50"
    data_transfer    = "Variable"
    storage          = "Variable"
    total_estimate   = "~$500-1000+ per month"
    note            = "Actual costs depend on usage, data transfer, and resource utilization"
  }
}

# Configuration Summary
output "infrastructure_summary" {
  description = "Infrastructure configuration summary"
  value = {
    environment           = var.environment
    region               = var.aws_region
    kubernetes_version   = var.kubernetes_version
    vpc_cidr            = var.vpc_cidr
    availability_zones   = data.aws_availability_zones.available.names
    nat_gateways        = length(module.networking.nat_gateway_ids)
    public_subnets      = length(module.networking.public_subnet_ids)
    private_subnets     = length(module.networking.private_subnet_ids)
    database_subnets    = length(module.networking.database_subnet_ids)
    database_count      = length(module.databases.database_endpoints)
    redis_enabled       = true
    nats_enabled        = true
    monitoring_enabled  = true
    backup_enabled      = true
    encryption_enabled  = var.enable_encryption_at_rest
    multi_az_enabled    = var.enable_multi_az
  }
}

# Networking Summary
output "networking_summary" {
  description = "Networking configuration summary"
  value = module.networking.network_configuration
}

# Security Summary
output "security_summary" {
  description = "Security configuration summary"
  value = module.networking.security_configuration
}

# Monitoring Summary
output "monitoring_summary" {
  description = "Monitoring configuration summary"
  value = module.networking.monitoring_configuration
}

# Compliance Summary
output "compliance_summary" {
  description = "Compliance configuration summary"
  value = module.networking.compliance_information
}

# Health Check URLs
output "health_check_urls" {
  description = "Health check URLs for services"
  value = {
    cluster_health      = "${module.eks_cluster.cluster_endpoint}/healthz"
    prometheus_health   = "${module.monitoring.prometheus_endpoint}/-/healthy"
    grafana_health      = "${module.monitoring.grafana_endpoint}/api/health"
    jaeger_health       = "${module.monitoring.jaeger_endpoint}/api/health"
    application_health  = "${module.arrakis_services.ingress_load_balancer_dns_name}/health"
  }
}

# Kubeconfig Information
output "kubeconfig_command" {
  description = "Command to update kubeconfig"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks_cluster.cluster_name}"
}

# Connection Information
output "connection_info" {
  description = "Connection information for services"
  value = {
    kubernetes = {
      endpoint = module.eks_cluster.cluster_endpoint
      version  = module.eks_cluster.cluster_version
    }
    databases = {
      endpoints = module.databases.database_endpoints
      ports     = module.databases.database_ports
    }
    redis = {
      endpoint = module.redis.primary_endpoint
      port     = module.redis.port
    }
    nats = {
      endpoint = module.nats.cluster_endpoint
      port     = module.nats.cluster_port
    }
    monitoring = {
      prometheus   = module.monitoring.prometheus_endpoint
      grafana      = module.monitoring.grafana_endpoint
      jaeger       = module.monitoring.jaeger_endpoint
      alertmanager = module.monitoring.alertmanager_endpoint
    }
  }
}

# Deployment Information
output "deployment_info" {
  description = "Deployment information and next steps"
  value = {
    terraform_version = ">=1.6.0"
    kubernetes_version = var.kubernetes_version
    deployment_time = timestamp()
    next_steps = [
      "Update kubeconfig: aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks_cluster.cluster_name}",
      "Verify cluster: kubectl get nodes",
      "Deploy applications: kubectl apply -f k8s/",
      "Access Grafana: ${module.monitoring.grafana_endpoint}",
      "Access Jaeger: ${module.monitoring.jaeger_endpoint}",
      "Check application health: ${module.arrakis_services.ingress_load_balancer_dns_name}/health"
    ]
  }
}
