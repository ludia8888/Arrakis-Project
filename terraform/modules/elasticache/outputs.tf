# ElastiCache Module Outputs
# Output values for use by other modules and main configuration

# Cluster Information
output "clusters" {
  description = "Map of ElastiCache cluster information"
  value = {
    for k, v in aws_elasticache_replication_group.main : k => {
      id                          = v.id
      arn                         = v.arn
      replication_group_id        = v.replication_group_id
      description                 = v.description
      primary_endpoint_address    = v.primary_endpoint_address
      reader_endpoint_address     = v.reader_endpoint_address
      configuration_endpoint_address = v.configuration_endpoint_address
      port                        = v.port
      engine                      = v.engine
      engine_version              = v.engine_version
      node_type                   = v.node_type
      num_cache_clusters          = v.num_cache_clusters
      num_node_groups             = v.num_node_groups
      replicas_per_node_group     = v.replicas_per_node_group
      multi_az_enabled            = v.multi_az_enabled
      automatic_failover_enabled  = v.automatic_failover_enabled
      at_rest_encryption_enabled  = v.at_rest_encryption_enabled
      transit_encryption_enabled  = v.transit_encryption_enabled
      auth_token_enabled          = v.auth_token_enabled
      kms_key_id                  = v.kms_key_id
      snapshot_retention_limit    = v.snapshot_retention_limit
      snapshot_window             = v.snapshot_window
      maintenance_window          = v.maintenance_window
      auto_minor_version_upgrade  = v.auto_minor_version_upgrade
      parameter_group_name        = v.parameter_group_name
      subnet_group_name           = v.subnet_group_name
      security_group_ids          = v.security_group_ids
      data_tiering_enabled        = v.data_tiering_enabled
      global_replication_group_id = v.global_replication_group_id
      member_clusters             = v.member_clusters
      tags                        = v.tags
    }
  }
}

# Primary Endpoints
output "primary_endpoints" {
  description = "Map of primary endpoints for clusters"
  value = {
    for k, v in aws_elasticache_replication_group.main : k => v.primary_endpoint_address
  }
}

# Reader Endpoints
output "reader_endpoints" {
  description = "Map of reader endpoints for clusters"
  value = {
    for k, v in aws_elasticache_replication_group.main : k => v.reader_endpoint_address
  }
}

# Configuration Endpoints
output "configuration_endpoints" {
  description = "Map of configuration endpoints for clusters"
  value = {
    for k, v in aws_elasticache_replication_group.main : k => v.configuration_endpoint_address
  }
}

# Cluster Ports
output "cluster_ports" {
  description = "Map of cluster ports"
  value = {
    for k, v in aws_elasticache_replication_group.main : k => v.port
  }
}

# Cluster ARNs
output "cluster_arns" {
  description = "Map of cluster ARNs"
  value = {
    for k, v in aws_elasticache_replication_group.main : k => v.arn
  }
}

# Cluster IDs
output "cluster_ids" {
  description = "Map of cluster IDs"
  value = {
    for k, v in aws_elasticache_replication_group.main : k => v.replication_group_id
  }
}

# Member Clusters
output "member_clusters" {
  description = "Map of member clusters"
  value = {
    for k, v in aws_elasticache_replication_group.main : k => v.member_clusters
  }
}

# Security Group Information
output "security_group_id" {
  description = "Security group ID for ElastiCache clusters"
  value       = aws_security_group.elasticache.id
}

output "security_group_arn" {
  description = "Security group ARN for ElastiCache clusters"
  value       = aws_security_group.elasticache.arn
}

output "security_group_name" {
  description = "Security group name for ElastiCache clusters"
  value       = aws_security_group.elasticache.name
}

# Subnet Group Information
output "subnet_group_id" {
  description = "ElastiCache subnet group ID"
  value       = aws_elasticache_subnet_group.main.id
}

output "subnet_group_name" {
  description = "ElastiCache subnet group name"
  value       = aws_elasticache_subnet_group.main.name
}

# Parameter Group Information
output "parameter_groups" {
  description = "Map of parameter groups"
  value = {
    for k, v in aws_elasticache_parameter_group.main : k => {
      id     = v.id
      name   = v.name
      family = v.family
      arn    = v.arn
    }
  }
}

# KMS Key Information
output "kms_key_id" {
  description = "KMS key ID for ElastiCache encryption"
  value       = aws_kms_key.elasticache.key_id
}

output "kms_key_arn" {
  description = "KMS key ARN for ElastiCache encryption"
  value       = aws_kms_key.elasticache.arn
}

output "kms_key_alias" {
  description = "KMS key alias for ElastiCache encryption"
  value       = aws_kms_alias.elasticache.name
}

# CloudWatch Log Groups
output "cloudwatch_log_groups" {
  description = "Map of CloudWatch log groups"
  value = {
    for k, v in aws_cloudwatch_log_group.redis_slow_log : k => {
      name = v.name
      arn  = v.arn
    }
  }
}

# CloudWatch Alarms
output "cloudwatch_alarms" {
  description = "Map of CloudWatch alarms"
  value = {
    cpu_utilization = {
      for k, v in aws_cloudwatch_metric_alarm.redis_cpu : k => {
        alarm_name = v.alarm_name
        arn        = v.arn
      }
    }
    memory_utilization = {
      for k, v in aws_cloudwatch_metric_alarm.redis_memory : k => {
        alarm_name = v.alarm_name
        arn        = v.arn
      }
    }
    evictions = {
      for k, v in aws_cloudwatch_metric_alarm.redis_evictions : k => {
        alarm_name = v.alarm_name
        arn        = v.arn
      }
    }
    connections = {
      for k, v in aws_cloudwatch_metric_alarm.redis_connections : k => {
        alarm_name = v.alarm_name
        arn        = v.arn
      }
    }
    replication_lag = {
      for k, v in aws_cloudwatch_metric_alarm.redis_replication_lag : k => {
        alarm_name = v.alarm_name
        arn        = v.arn
      }
    }
  }
}

# Auth Tokens (Secrets Manager)
output "auth_tokens" {
  description = "Map of auth tokens in Secrets Manager"
  value = {
    for k, v in aws_secretsmanager_secret.redis_credentials : k => {
      secret_id   = v.id
      secret_arn  = v.arn
      secret_name = v.name
    }
  }
  sensitive = true
}

# Redis Users (for RBAC)
output "redis_users" {
  description = "Map of Redis users"
  value = var.enable_rbac ? {
    for k, v in aws_elasticache_user.main : k => {
      user_id       = v.user_id
      user_name     = v.user_name
      access_string = v.access_string
      engine        = v.engine
      arn           = v.arn
    }
  } : {}
}

# Redis User Groups (for RBAC)
output "redis_user_groups" {
  description = "Map of Redis user groups"
  value = var.enable_rbac ? {
    for k, v in aws_elasticache_user_group.main : k => {
      user_group_id = v.user_group_id
      engine        = v.engine
      user_ids      = v.user_ids
      arn           = v.arn
    }
  } : {}
}

# Global Replication Groups
output "global_replication_groups" {
  description = "Map of global replication groups"
  value = var.enable_global_replication ? {
    for k, v in aws_elasticache_global_replication_group.main : k => {
      global_replication_group_id = v.global_replication_group_id
      arn                         = v.arn
      at_rest_encryption_enabled  = v.at_rest_encryption_enabled
      transit_encryption_enabled  = v.transit_encryption_enabled
      cache_node_type             = v.cache_node_type
      engine_version              = v.engine_version
      primary_replication_group_id = v.primary_replication_group_id
    }
  } : {}
}

# Backup Information
output "backup_plan_id" {
  description = "Backup plan ID"
  value       = var.enable_automated_backups ? aws_backup_plan.elasticache[0].id : null
}

output "backup_plan_arn" {
  description = "Backup plan ARN"
  value       = var.enable_automated_backups ? aws_backup_plan.elasticache[0].arn : null
}

output "backup_vault_name" {
  description = "Backup vault name"
  value       = var.enable_automated_backups ? aws_backup_vault.elasticache[0].name : null
}

output "backup_vault_arn" {
  description = "Backup vault ARN"
  value       = var.enable_automated_backups ? aws_backup_vault.elasticache[0].arn : null
}

# IAM Roles
output "backup_role_arn" {
  description = "Backup IAM role ARN"
  value       = var.enable_automated_backups ? aws_iam_role.backup[0].arn : null
}

# CloudWatch Dashboard
output "cloudwatch_dashboard_url" {
  description = "CloudWatch dashboard URL"
  value       = var.enable_monitoring_dashboard ? "https://console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.current.name}#dashboards:name=${aws_cloudwatch_dashboard.redis_dashboard[0].dashboard_name}" : null
}

# Connection Strings
output "connection_strings" {
  description = "Map of Redis connection strings"
  value = {
    for k, v in aws_elasticache_replication_group.main : k => {
      primary_endpoint = v.primary_endpoint_address != null ? "redis://${v.primary_endpoint_address}:${v.port}" : null
      reader_endpoint  = v.reader_endpoint_address != null ? "redis://${v.reader_endpoint_address}:${v.port}" : null
      config_endpoint  = v.configuration_endpoint_address != null ? "redis://${v.configuration_endpoint_address}:${v.port}" : null
    }
  }
}

# Cluster Summary
output "cluster_summary" {
  description = "Summary of ElastiCache cluster configuration"
  value = {
    total_clusters           = length(aws_elasticache_replication_group.main)
    cluster_mode_enabled     = var.cluster_mode_enabled
    multi_az_enabled         = var.multi_az_enabled
    encryption_at_rest       = var.at_rest_encryption_enabled
    encryption_in_transit    = var.transit_encryption_enabled
    auth_token_enabled       = var.enable_auth_token
    rbac_enabled             = var.enable_rbac
    global_replication       = var.enable_global_replication
    backup_enabled           = var.enable_automated_backups
    monitoring_enabled       = var.enable_monitoring_dashboard
    security_group_id        = aws_security_group.elasticache.id
    subnet_group_name        = aws_elasticache_subnet_group.main.name
    kms_key_id               = aws_kms_key.elasticache.key_id
    parameter_group_family   = var.parameter_group_family
  }
}

# Cost Information
output "cost_optimization_info" {
  description = "Cost optimization information"
  value = {
    cost_optimization_enabled = var.enable_cost_optimization
    reserved_instances        = var.enable_reserved_instances
    right_sizing_enabled      = var.enable_right_sizing
    node_types = {
      for k, v in aws_elasticache_replication_group.main : k => v.node_type
    }
    cluster_sizes = {
      for k, v in aws_elasticache_replication_group.main : k => v.num_cache_clusters
    }
    estimated_monthly_cost = "Variable based on node types and cluster sizes"
  }
}

# Security Information
output "security_configuration" {
  description = "Security configuration information"
  value = {
    encryption_at_rest = {
      for k, v in aws_elasticache_replication_group.main : k => v.at_rest_encryption_enabled
    }
    encryption_in_transit = {
      for k, v in aws_elasticache_replication_group.main : k => v.transit_encryption_enabled
    }
    auth_token_enabled = {
      for k, v in aws_elasticache_replication_group.main : k => v.auth_token_enabled
    }
    rbac_enabled            = var.enable_rbac
    security_group_id       = aws_security_group.elasticache.id
    kms_key_arn             = aws_kms_key.elasticache.arn
    secrets_manager_enabled = true
    vpc_security_groups = {
      for k, v in aws_elasticache_replication_group.main : k => v.security_group_ids
    }
    subnet_group_name = aws_elasticache_subnet_group.main.name
  }
}

# Performance Information
output "performance_configuration" {
  description = "Performance configuration information"
  value = {
    cluster_mode_enabled = var.cluster_mode_enabled
    multi_az_enabled     = var.multi_az_enabled
    automatic_failover   = var.automatic_failover_enabled
    data_tiering_enabled = var.data_tiering_enabled
    parameter_groups = {
      for k, v in aws_elasticache_parameter_group.main : k => v.name
    }
    maxmemory_policy = var.maxmemory_policy
    node_types = {
      for k, v in aws_elasticache_replication_group.main : k => v.node_type
    }
    num_node_groups = {
      for k, v in aws_elasticache_replication_group.main : k => v.num_node_groups
    }
    replicas_per_node_group = {
      for k, v in aws_elasticache_replication_group.main : k => v.replicas_per_node_group
    }
  }
}

# Compliance Information
output "compliance_information" {
  description = "Compliance configuration information"
  value = {
    compliance_standards     = var.compliance_standards
    audit_logging_enabled    = var.enable_audit_logging
    audit_log_retention_days = var.audit_log_retention_days
    encryption_enabled       = var.at_rest_encryption_enabled
    backup_retention_days    = var.backup_retention_days
    cross_region_backup      = var.cross_region_backup_enabled
    security_hardening       = var.enable_security_hardening
    vpc_isolation            = true
  }
}

# Disaster Recovery Information
output "disaster_recovery_info" {
  description = "Disaster recovery information"
  value = {
    disaster_recovery_enabled = var.enable_disaster_recovery
    backup_region            = var.disaster_recovery_region
    cross_region_backup      = var.cross_region_backup_enabled
    multi_az_deployment      = var.multi_az_enabled
    automatic_failover       = var.automatic_failover_enabled
    global_replication       = var.enable_global_replication
    automated_backups        = var.enable_automated_backups
    snapshot_retention       = var.snapshot_retention_limit
  }
}

# Health Check Information
output "health_check_info" {
  description = "Health check information"
  value = {
    cloudwatch_alarms = {
      cpu_utilization  = [for alarm in aws_cloudwatch_metric_alarm.redis_cpu : alarm.alarm_name]
      memory_utilization = [for alarm in aws_cloudwatch_metric_alarm.redis_memory : alarm.alarm_name]
      evictions        = [for alarm in aws_cloudwatch_metric_alarm.redis_evictions : alarm.alarm_name]
      connections      = [for alarm in aws_cloudwatch_metric_alarm.redis_connections : alarm.alarm_name]
      replication_lag  = [for alarm in aws_cloudwatch_metric_alarm.redis_replication_lag : alarm.alarm_name]
    }
    monitoring_dashboard_enabled = var.enable_monitoring_dashboard
    slow_log_enabled            = var.enable_slow_log
    notifications_enabled       = var.enable_notifications
  }
}

# Connection Information
output "connection_info" {
  description = "Redis connection information"
  value = {
    for k, v in aws_elasticache_replication_group.main : k => {
      primary_endpoint = v.primary_endpoint_address
      reader_endpoint  = v.reader_endpoint_address
      config_endpoint  = v.configuration_endpoint_address
      port             = v.port
      auth_required    = v.auth_token_enabled
      ssl_enabled      = v.transit_encryption_enabled
      secret_arn       = aws_secretsmanager_secret.redis_credentials[k].arn
    }
  }
}

# Endpoint Information for Load Balancing
output "endpoint_info" {
  description = "Endpoint information for load balancing"
  value = {
    for k, v in aws_elasticache_replication_group.main : k => {
      primary_endpoint = {
        address = v.primary_endpoint_address
        port    = v.port
      }
      reader_endpoint = {
        address = v.reader_endpoint_address
        port    = v.port
      }
      configuration_endpoint = {
        address = v.configuration_endpoint_address
        port    = v.port
      }
      member_clusters = v.member_clusters
    }
  }
}

# Network Information
output "network_info" {
  description = "Network configuration information"
  value = {
    vpc_id                = var.vpc_id
    subnet_group_name     = aws_elasticache_subnet_group.main.name
    security_group_id     = aws_security_group.elasticache.id
    allowed_cidr_blocks   = var.allowed_cidr_blocks
    availability_zones    = var.availability_zones
    preferred_azs         = var.preferred_cache_cluster_azs
  }
}

# Backup and Maintenance Information
output "backup_maintenance_info" {
  description = "Backup and maintenance information"
  value = {
    backup_enabled           = var.enable_automated_backups
    snapshot_retention_limit = var.snapshot_retention_limit
    snapshot_window         = var.snapshot_window
    maintenance_window      = var.maintenance_window
    auto_minor_version_upgrade = var.auto_minor_version_upgrade
    backup_retention_days   = var.backup_retention_days
    final_snapshot_identifier = var.final_snapshot_identifier
  }
}

# Monitoring Information
output "monitoring_info" {
  description = "Monitoring configuration information"
  value = {
    dashboard_enabled        = var.enable_monitoring_dashboard
    cloudwatch_logs_enabled  = var.enable_cloudwatch_logs
    slow_log_enabled         = var.enable_slow_log
    audit_logging_enabled    = var.enable_audit_logging
    log_retention_days       = var.log_retention_days
    sns_notifications        = var.enable_notifications
  }
}
