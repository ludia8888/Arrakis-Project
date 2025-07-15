# RDS Module Outputs
# Output values for use by other modules and main configuration

# Database Instance Information
output "database_instances" {
  description = "Map of RDS database instances"
  value = {
    for k, v in aws_db_instance.main : k => {
      id                      = v.id
      arn                     = v.arn
      identifier              = v.identifier
      endpoint                = v.endpoint
      port                    = v.port
      status                  = v.status
      engine                  = v.engine
      engine_version          = v.engine_version
      instance_class          = v.instance_class
      allocated_storage       = v.allocated_storage
      max_allocated_storage   = v.max_allocated_storage
      storage_type            = v.storage_type
      storage_encrypted       = v.storage_encrypted
      kms_key_id              = v.kms_key_id
      database_name           = v.db_name
      username                = v.username
      multi_az                = v.multi_az
      publicly_accessible     = v.publicly_accessible
      vpc_security_group_ids  = v.vpc_security_group_ids
      db_subnet_group_name    = v.db_subnet_group_name
      backup_retention_period = v.backup_retention_period
      backup_window           = v.backup_window
      maintenance_window      = v.maintenance_window
      deletion_protection     = v.deletion_protection
      monitoring_interval     = v.monitoring_interval
      performance_insights_enabled = v.performance_insights_enabled
      enabled_cloudwatch_logs_exports = v.enabled_cloudwatch_logs_exports
      availability_zone       = v.availability_zone
      hosted_zone_id          = v.hosted_zone_id
      resource_id             = v.resource_id
      ca_cert_identifier      = v.ca_cert_identifier
      tags                    = v.tags
    }
  }
}

# Database Endpoints
output "database_endpoints" {
  description = "Map of database endpoints"
  value = {
    for k, v in aws_db_instance.main : k => v.endpoint
  }
}

# Database Ports
output "database_ports" {
  description = "Map of database ports"
  value = {
    for k, v in aws_db_instance.main : k => v.port
  }
}

# Database ARNs
output "database_arns" {
  description = "Map of database ARNs"
  value = {
    for k, v in aws_db_instance.main : k => v.arn
  }
}

# Database Identifiers
output "database_identifiers" {
  description = "Map of database identifiers"
  value = {
    for k, v in aws_db_instance.main : k => v.identifier
  }
}

# Database Resource IDs
output "database_resource_ids" {
  description = "Map of database resource IDs"
  value = {
    for k, v in aws_db_instance.main : k => v.resource_id
  }
}

# Database Status
output "database_status" {
  description = "Map of database status"
  value = {
    for k, v in aws_db_instance.main : k => v.status
  }
}

# Database Engine Information
output "database_engine_info" {
  description = "Map of database engine information"
  value = {
    for k, v in aws_db_instance.main : k => {
      engine         = v.engine
      engine_version = v.engine_version
      instance_class = v.instance_class
    }
  }
}

# Database Storage Information
output "database_storage_info" {
  description = "Map of database storage information"
  value = {
    for k, v in aws_db_instance.main : k => {
      allocated_storage     = v.allocated_storage
      max_allocated_storage = v.max_allocated_storage
      storage_type          = v.storage_type
      storage_encrypted     = v.storage_encrypted
      kms_key_id            = v.kms_key_id
    }
  }
}

# Database Network Information
output "database_network_info" {
  description = "Map of database network information"
  value = {
    for k, v in aws_db_instance.main : k => {
      endpoint                = v.endpoint
      port                    = v.port
      publicly_accessible     = v.publicly_accessible
      vpc_security_group_ids  = v.vpc_security_group_ids
      db_subnet_group_name    = v.db_subnet_group_name
      availability_zone       = v.availability_zone
      hosted_zone_id          = v.hosted_zone_id
    }
  }
}

# Database Backup Information
output "database_backup_info" {
  description = "Map of database backup information"
  value = {
    for k, v in aws_db_instance.main : k => {
      backup_retention_period = v.backup_retention_period
      backup_window           = v.backup_window
      maintenance_window      = v.maintenance_window
      deletion_protection     = v.deletion_protection
    }
  }
}

# Database Monitoring Information
output "database_monitoring_info" {
  description = "Map of database monitoring information"
  value = {
    for k, v in aws_db_instance.main : k => {
      monitoring_interval               = v.monitoring_interval
      performance_insights_enabled     = v.performance_insights_enabled
      enabled_cloudwatch_logs_exports   = v.enabled_cloudwatch_logs_exports
      ca_cert_identifier               = v.ca_cert_identifier
    }
  }
}

# Read Replica Information
output "read_replica_instances" {
  description = "Map of read replica instances"
  value = var.enable_read_replicas ? {
    for k, v in aws_db_instance.read_replica : k => {
      id                              = v.id
      arn                             = v.arn
      identifier                      = v.identifier
      endpoint                        = v.endpoint
      port                            = v.port
      status                          = v.status
      instance_class                  = v.instance_class
      storage_encrypted               = v.storage_encrypted
      kms_key_id                      = v.kms_key_id
      monitoring_interval             = v.monitoring_interval
      performance_insights_enabled    = v.performance_insights_enabled
      enabled_cloudwatch_logs_exports = v.enabled_cloudwatch_logs_exports
      replicate_source_db             = v.replicate_source_db
      availability_zone               = v.availability_zone
      tags                            = v.tags
    }
  } : {}
}

output "read_replica_endpoints" {
  description = "Map of read replica endpoints"
  value = var.enable_read_replicas ? {
    for k, v in aws_db_instance.read_replica : k => v.endpoint
  } : {}
}

# Security Group Information
output "security_group_id" {
  description = "Security group ID for RDS instances"
  value       = aws_security_group.rds.id
}

output "security_group_arn" {
  description = "Security group ARN for RDS instances"
  value       = aws_security_group.rds.arn
}

output "security_group_name" {
  description = "Security group name for RDS instances"
  value       = aws_security_group.rds.name
}

# Database Subnet Group Information
output "db_subnet_group_id" {
  description = "Database subnet group ID"
  value       = aws_db_subnet_group.main.id
}

output "db_subnet_group_name" {
  description = "Database subnet group name"
  value       = aws_db_subnet_group.main.name
}

output "db_subnet_group_arn" {
  description = "Database subnet group ARN"
  value       = aws_db_subnet_group.main.arn
}

# Parameter Group Information
output "parameter_groups" {
  description = "Map of parameter groups"
  value = {
    for k, v in aws_db_parameter_group.main : k => {
      id     = v.id
      arn    = v.arn
      name   = v.name
      family = v.family
    }
  }
}

# Option Group Information
output "option_groups" {
  description = "Map of option groups"
  value = {
    for k, v in aws_db_option_group.main : k => {
      id                   = v.id
      arn                  = v.arn
      name                 = v.name
      engine_name          = v.engine_name
      major_engine_version = v.major_engine_version
    }
  }
}

# KMS Key Information
output "kms_key_id" {
  description = "KMS key ID for RDS encryption"
  value       = aws_kms_key.rds.key_id
}

output "kms_key_arn" {
  description = "KMS key ARN for RDS encryption"
  value       = aws_kms_key.rds.arn
}

output "kms_key_alias" {
  description = "KMS key alias for RDS encryption"
  value       = aws_kms_alias.rds.name
}

# CloudWatch Log Groups
output "cloudwatch_log_groups" {
  description = "Map of CloudWatch log groups"
  value = {
    for k, v in aws_cloudwatch_log_group.database_logs : k => {
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
      for k, v in aws_cloudwatch_metric_alarm.database_cpu : k => {
        alarm_name = v.alarm_name
        arn        = v.arn
      }
    }
    memory_utilization = {
      for k, v in aws_cloudwatch_metric_alarm.database_memory : k => {
        alarm_name = v.alarm_name
        arn        = v.arn
      }
    }
    database_connections = {
      for k, v in aws_cloudwatch_metric_alarm.database_connections : k => {
        alarm_name = v.alarm_name
        arn        = v.arn
      }
    }
    storage_space = {
      for k, v in aws_cloudwatch_metric_alarm.database_storage : k => {
        alarm_name = v.alarm_name
        arn        = v.arn
      }
    }
  }
}

# Event Subscriptions
output "event_subscriptions" {
  description = "Map of database event subscriptions"
  value = {
    for k, v in aws_db_event_subscription.main : k => {
      name            = v.name
      arn             = v.arn
      sns_topic       = v.sns_topic
      enabled         = v.enabled
      event_categories = v.event_categories
      source_type     = v.source_type
      source_ids      = v.source_ids
    }
  }
}

# Database Credentials (Secrets Manager)
output "database_credentials" {
  description = "Map of database credentials in Secrets Manager"
  value = {
    for k, v in aws_secretsmanager_secret.database_credentials : k => {
      secret_id   = v.id
      secret_arn  = v.arn
      secret_name = v.name
    }
  }
  sensitive = true
}

# IAM Roles
output "enhanced_monitoring_role_arn" {
  description = "Enhanced monitoring IAM role ARN"
  value       = var.enable_enhanced_monitoring ? aws_iam_role.rds_enhanced_monitoring[0].arn : null
}

output "backup_role_arn" {
  description = "Backup IAM role ARN"
  value       = var.enable_automated_backups ? aws_iam_role.backup[0].arn : null
}

# Backup Information
output "backup_plan_id" {
  description = "Backup plan ID"
  value       = var.enable_automated_backups ? aws_backup_plan.database[0].id : null
}

output "backup_plan_arn" {
  description = "Backup plan ARN"
  value       = var.enable_automated_backups ? aws_backup_plan.database[0].arn : null
}

output "backup_vault_name" {
  description = "Backup vault name"
  value       = var.enable_automated_backups ? aws_backup_vault.database[0].name : null
}

output "backup_vault_arn" {
  description = "Backup vault ARN"
  value       = var.enable_automated_backups ? aws_backup_vault.database[0].arn : null
}

# Connection Strings
output "connection_strings" {
  description = "Map of database connection strings"
  value = {
    for k, v in aws_db_instance.main : k => {
      jdbc_url = "jdbc:postgresql://${v.endpoint}:${v.port}/${v.db_name}"
      psql_url = "postgresql://${v.username}:${random_password.master_password[k].result}@${v.endpoint}:${v.port}/${v.db_name}"
    }
  }
  sensitive = true
}

# Database Summary
output "database_summary" {
  description = "Summary of database configuration"
  value = {
    total_databases        = length(aws_db_instance.main)
    read_replicas_enabled  = var.enable_read_replicas
    total_read_replicas    = var.enable_read_replicas ? length(aws_db_instance.read_replica) : 0
    multi_az_enabled       = [for db in aws_db_instance.main : db.multi_az]
    storage_encrypted      = [for db in aws_db_instance.main : db.storage_encrypted]
    backup_enabled         = var.enable_automated_backups
    monitoring_enabled     = var.enable_enhanced_monitoring
    performance_insights   = var.enable_performance_insights
    cloudwatch_logs        = var.enabled_cloudwatch_logs_exports
    security_group_id      = aws_security_group.rds.id
    subnet_group_name      = aws_db_subnet_group.main.name
    kms_key_id             = aws_kms_key.rds.key_id
  }
}

# Cost Information
output "cost_optimization_info" {
  description = "Cost optimization information"
  value = {
    cost_optimization_enabled = var.enable_cost_optimization
    reserved_instances        = var.enable_reserved_instance_matching
    right_sizing_enabled      = var.enable_right_sizing
    storage_types = {
      for k, v in aws_db_instance.main : k => v.storage_type
    }
    instance_classes = {
      for k, v in aws_db_instance.main : k => v.instance_class
    }
    estimated_monthly_cost = "Variable based on instance classes and storage"
  }
}

# Security Information
output "security_configuration" {
  description = "Security configuration information"
  value = {
    encryption_at_rest = {
      for k, v in aws_db_instance.main : k => v.storage_encrypted
    }
    encryption_in_transit = {
      for k, v in aws_db_instance.main : k => v.ca_cert_identifier
    }
    deletion_protection = {
      for k, v in aws_db_instance.main : k => v.deletion_protection
    }
    publicly_accessible = {
      for k, v in aws_db_instance.main : k => v.publicly_accessible
    }
    vpc_security_groups = {
      for k, v in aws_db_instance.main : k => v.vpc_security_group_ids
    }
    kms_key_arn             = aws_kms_key.rds.arn
    secrets_manager_enabled = true
    audit_logging_enabled   = var.enable_audit_logging
    compliance_standards    = var.compliance_standards
  }
}

# Performance Information
output "performance_configuration" {
  description = "Performance configuration information"
  value = {
    performance_insights_enabled = var.enable_performance_insights
    enhanced_monitoring_enabled  = var.enable_enhanced_monitoring
    monitoring_interval          = var.monitoring_interval
    parameter_groups = {
      for k, v in aws_db_parameter_group.main : k => v.name
    }
    option_groups = {
      for k, v in aws_db_option_group.main : k => v.name
    }
    read_replicas_count = var.enable_read_replicas ? length(aws_db_instance.read_replica) : 0
    connection_pool_size = var.connection_pool_size
  }
}

# Compliance Information
output "compliance_information" {
  description = "Compliance configuration information"
  value = {
    compliance_standards     = var.compliance_standards
    audit_logging_enabled    = var.enable_audit_logging
    audit_log_retention_days = var.audit_log_retention_days
    encryption_enabled       = var.storage_encrypted
    backup_retention_days    = var.backup_retention_days
    cross_region_backup      = var.enable_cross_region_backup
    deletion_protection      = var.deletion_protection
    network_isolation        = !var.publicly_accessible
  }
}

# Disaster Recovery Information
output "disaster_recovery_info" {
  description = "Disaster recovery information"
  value = {
    disaster_recovery_enabled = var.enable_disaster_recovery
    backup_region            = var.backup_region
    cross_region_backup      = var.enable_cross_region_backup
    multi_az_deployment      = var.multi_az
    point_in_time_recovery   = var.backup_retention_days > 0
    automated_backups        = var.enable_automated_backups
    read_replicas           = var.enable_read_replicas
  }
}

# Health Check Information
output "health_check_info" {
  description = "Health check information"
  value = {
    database_status = {
      for k, v in aws_db_instance.main : k => v.status
    }
    cloudwatch_alarms = {
      cpu_utilization      = [for alarm in aws_cloudwatch_metric_alarm.database_cpu : alarm.alarm_name]
      memory_utilization   = [for alarm in aws_cloudwatch_metric_alarm.database_memory : alarm.alarm_name]
      database_connections = [for alarm in aws_cloudwatch_metric_alarm.database_connections : alarm.alarm_name]
      storage_space        = [for alarm in aws_cloudwatch_metric_alarm.database_storage : alarm.alarm_name]
    }
    event_subscriptions_enabled = var.sns_topic_arn != ""
    performance_insights_enabled = var.enable_performance_insights
  }
}

# Connection Information
output "connection_info" {
  description = "Database connection information"
  value = {
    for k, v in aws_db_instance.main : k => {
      endpoint    = v.endpoint
      port        = v.port
      database    = v.db_name
      username    = v.username
      ssl_mode    = "require"
      ca_cert     = v.ca_cert_identifier
      secret_arn  = aws_secretsmanager_secret.database_credentials[k].arn
    }
  }
}
