# ElastiCache Module - Production-ready Redis clusters
# Comprehensive managed Redis cache infrastructure with high availability, security, and monitoring

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# KMS Key for ElastiCache encryption
resource "aws_kms_key" "elasticache" {
  description             = "KMS key for ElastiCache encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow ElastiCache Service"
        Effect = "Allow"
        Principal = {
          Service = "elasticache.amazonaws.com"
        }
        Action = [
          "kms:Describe*",
          "kms:Decrypt",
          "kms:CreateGrant",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${var.project_name}-elasticache-kms-${var.environment}"
    Type = "kms-key"
  })
}

resource "aws_kms_alias" "elasticache" {
  name          = "alias/${var.project_name}-elasticache-${var.environment}"
  target_key_id = aws_kms_key.elasticache.key_id
}

# Random password for Redis AUTH
resource "random_password" "auth_token" {
  for_each = var.clusters

  length  = 32
  special = false
  upper   = true
  lower   = true
  numeric = true
}

# AWS Secrets Manager secrets for Redis credentials
resource "aws_secretsmanager_secret" "redis_credentials" {
  for_each = var.clusters

  name                    = "${var.project_name}-${each.key}-redis-credentials-${var.environment}"
  description             = "Redis credentials for ${each.key}"
  kms_key_id              = aws_kms_key.elasticache.arn
  recovery_window_in_days = 7

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-redis-credentials-${var.environment}"
    Type = "redis-secret"
    Cluster = each.key
  })
}

resource "aws_secretsmanager_secret_version" "redis_credentials" {
  for_each = var.clusters

  secret_id = aws_secretsmanager_secret.redis_credentials[each.key].id
  secret_string = jsonencode({
    auth_token = random_password.auth_token[each.key].result
    endpoint   = aws_elasticache_replication_group.main[each.key].primary_endpoint_address
    port       = aws_elasticache_replication_group.main[each.key].port
    cluster_id = aws_elasticache_replication_group.main[each.key].replication_group_id
  })
}

# ElastiCache Subnet Group
resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project_name}-cache-subnet-group-${var.environment}"
  subnet_ids = var.subnet_ids

  tags = merge(var.tags, {
    Name = "${var.project_name}-cache-subnet-group-${var.environment}"
    Type = "elasticache-subnet-group"
  })
}

# Security Group for ElastiCache
resource "aws_security_group" "elasticache" {
  name        = "${var.project_name}-elasticache-sg-${var.environment}"
  description = "Security group for ElastiCache Redis clusters"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
    description = "Redis access from allowed networks"
  }

  # Allow Redis Cluster mode port range
  ingress {
    from_port   = 6379
    to_port     = 6399
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
    description = "Redis Cluster mode access from allowed networks"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-elasticache-sg-${var.environment}"
    Type = "security-group"
  })
}

# Parameter Group for Redis optimization
resource "aws_elasticache_parameter_group" "main" {
  for_each = var.clusters

  family = "redis${split(".", each.value.engine_version)[0]}"
  name   = "${var.project_name}-${each.key}-params-${var.environment}"

  # Performance optimization parameters
  parameter {
    name  = "maxmemory-policy"
    value = each.value.maxmemory_policy
  }

  parameter {
    name  = "timeout"
    value = "300"
  }

  parameter {
    name  = "tcp-keepalive"
    value = "60"
  }

  parameter {
    name  = "maxmemory-samples"
    value = "10"
  }

  parameter {
    name  = "lazyfree-lazy-eviction"
    value = "yes"
  }

  parameter {
    name  = "lazyfree-lazy-expire"
    value = "yes"
  }

  parameter {
    name  = "lazyfree-lazy-server-del"
    value = "yes"
  }

  parameter {
    name  = "replica-lazy-flush"
    value = "yes"
  }

  parameter {
    name  = "notify-keyspace-events"
    value = "Ex"
  }

  dynamic "parameter" {
    for_each = each.value.custom_parameters
    content {
      name  = parameter.value.name
      value = parameter.value.value
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-params-${var.environment}"
    Type = "elasticache-parameter-group"
    Cluster = each.key
  })
}

# CloudWatch Log Group for Redis logs
resource "aws_cloudwatch_log_group" "redis_slow_log" {
  for_each = var.clusters

  name              = "/aws/elasticache/${var.project_name}-${each.key}-${var.environment}/slow-log"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-slow-log-${var.environment}"
    Type = "log-group"
    Cluster = each.key
  })
}

# ElastiCache Replication Group (Redis Cluster)
resource "aws_elasticache_replication_group" "main" {
  for_each = var.clusters

  # Basic Configuration
  replication_group_id       = each.value.cluster_id
  description                = "Redis replication group for ${each.key}"
  node_type                  = each.value.node_type
  port                       = each.value.port
  parameter_group_name       = aws_elasticache_parameter_group.main[each.key].name

  # Engine Configuration
  engine               = "redis"
  engine_version       = each.value.engine_version
  num_cache_clusters   = each.value.num_cache_nodes

  # Network Configuration
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.elasticache.id]

  # High Availability Configuration
  multi_az_enabled           = each.value.multi_az_enabled
  automatic_failover_enabled = each.value.automatic_failover_enabled

  # Cluster Mode Configuration
  num_node_groups         = each.value.num_node_groups
  replicas_per_node_group = each.value.replicas_per_node_group

  # Security Configuration
  at_rest_encryption_enabled = each.value.at_rest_encryption_enabled
  transit_encryption_enabled = each.value.transit_encryption_enabled
  auth_token                 = each.value.auth_token_enabled ? random_password.auth_token[each.key].result : null
  kms_key_id                 = each.value.at_rest_encryption_enabled ? aws_kms_key.elasticache.arn : null

  # Backup Configuration
  snapshot_retention_limit = each.value.snapshot_retention_limit
  snapshot_window         = each.value.snapshot_window
  final_snapshot_identifier = each.value.final_snapshot_identifier

  # Maintenance Configuration
  maintenance_window       = each.value.maintenance_window
  auto_minor_version_upgrade = each.value.auto_minor_version_upgrade
  apply_immediately        = each.value.apply_immediately

  # Notification Configuration
  notification_topic_arn = each.value.notification_topic_arn

  # Data Tiering (for r6gd node types)
  data_tiering_enabled = each.value.data_tiering_enabled

  # Global Replication Configuration
  global_replication_group_id = each.value.global_replication_group_id

  # Log Configuration
  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_slow_log[each.key].name
    destination_type = "cloudwatch-logs"
    log_format       = "text"
    log_type         = "slow-log"
  }

  # Preferred Cache Cluster AZs
  preferred_cache_cluster_azs = each.value.preferred_cache_cluster_azs

  # Lifecycle Management
  lifecycle {
    ignore_changes = [
      auth_token,
      num_cache_clusters
    ]
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-${var.environment}"
    Type = "elasticache-replication-group"
    Cluster = each.key
  })
}

# CloudWatch Alarms for Redis monitoring
resource "aws_cloudwatch_metric_alarm" "redis_cpu" {
  for_each = var.clusters

  alarm_name          = "${var.project_name}-${each.key}-cpu-utilization-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors Redis CPU utilization"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    CacheClusterId = each.value.cluster_id
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-cpu-alarm-${var.environment}"
    Type = "cloudwatch-alarm"
    Cluster = each.key
  })
}

resource "aws_cloudwatch_metric_alarm" "redis_memory" {
  for_each = var.clusters

  alarm_name          = "${var.project_name}-${each.key}-memory-utilization-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors Redis memory utilization"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    CacheClusterId = each.value.cluster_id
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-memory-alarm-${var.environment}"
    Type = "cloudwatch-alarm"
    Cluster = each.key
  })
}

resource "aws_cloudwatch_metric_alarm" "redis_evictions" {
  for_each = var.clusters

  alarm_name          = "${var.project_name}-${each.key}-evictions-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Evictions"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors Redis evictions"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    CacheClusterId = each.value.cluster_id
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-evictions-alarm-${var.environment}"
    Type = "cloudwatch-alarm"
    Cluster = each.key
  })
}

resource "aws_cloudwatch_metric_alarm" "redis_connections" {
  for_each = var.clusters

  alarm_name          = "${var.project_name}-${each.key}-connections-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CurrConnections"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "500"
  alarm_description   = "This metric monitors Redis connections"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    CacheClusterId = each.value.cluster_id
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-connections-alarm-${var.environment}"
    Type = "cloudwatch-alarm"
    Cluster = each.key
  })
}

resource "aws_cloudwatch_metric_alarm" "redis_replication_lag" {
  for_each = var.clusters

  alarm_name          = "${var.project_name}-${each.key}-replication-lag-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ReplicationLag"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "30"
  alarm_description   = "This metric monitors Redis replication lag"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    CacheClusterId = each.value.cluster_id
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-replication-lag-alarm-${var.environment}"
    Type = "cloudwatch-alarm"
    Cluster = each.key
  })
}

# ElastiCache User for Redis 6.0+ AUTH
resource "aws_elasticache_user" "main" {
  for_each = var.enable_rbac ? var.clusters : {}

  user_id       = "${var.project_name}-${each.key}-user-${var.environment}"
  user_name     = "application-user"
  access_string = "on ~* &* +@all"
  engine        = "REDIS"
  passwords     = [random_password.auth_token[each.key].result]

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-user-${var.environment}"
    Type = "elasticache-user"
    Cluster = each.key
  })
}

# ElastiCache User Group for Redis 6.0+ AUTH
resource "aws_elasticache_user_group" "main" {
  for_each = var.enable_rbac ? var.clusters : {}

  engine        = "REDIS"
  user_group_id = "${var.project_name}-${each.key}-user-group-${var.environment}"
  user_ids      = [aws_elasticache_user.main[each.key].user_id]

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-user-group-${var.environment}"
    Type = "elasticache-user-group"
    Cluster = each.key
  })
}

# Global Replication Group for cross-region replication
resource "aws_elasticache_global_replication_group" "main" {
  for_each = var.enable_global_replication ? var.clusters : {}

  global_replication_group_id_suffix = "${var.project_name}-${each.key}-global-${var.environment}"
  primary_replication_group_id        = aws_elasticache_replication_group.main[each.key].replication_group_id

  global_replication_group_description = "Global replication group for ${each.key}"

  # Configuration
  cache_node_type                = each.value.node_type
  engine_version                 = each.value.engine_version
  at_rest_encryption_enabled     = each.value.at_rest_encryption_enabled
  transit_encryption_enabled     = each.value.transit_encryption_enabled
  auth_token_enabled             = each.value.auth_token_enabled
  automatic_failover_enabled     = each.value.automatic_failover_enabled

  # Parameter Group
  parameter_group_name = aws_elasticache_parameter_group.main[each.key].name

  # Global Datastore
  global_node_groups {
    global_node_group_id = "${var.project_name}-${each.key}-global-node-${var.environment}"
    slots                = "0-16383"
  }
}

# Backup configuration using AWS Backup
resource "aws_backup_selection" "elasticache_backup" {
  count = var.enable_automated_backups ? 1 : 0

  iam_role_arn = aws_iam_role.backup[0].arn
  name         = "${var.project_name}-elasticache-backup-${var.environment}"
  plan_id      = aws_backup_plan.elasticache[0].id

  resources = [
    for cluster in aws_elasticache_replication_group.main : cluster.arn
  ]

  condition {
    string_equals {
      key   = "aws:ResourceTag/BackupEnabled"
      value = "true"
    }
  }
}

resource "aws_backup_plan" "elasticache" {
  count = var.enable_automated_backups ? 1 : 0

  name = "${var.project_name}-elasticache-backup-plan-${var.environment}"

  rule {
    rule_name         = "daily_backup"
    target_vault_name = aws_backup_vault.elasticache[0].name
    schedule          = "cron(0 5 ? * * *)"
    start_window      = 480  # 8 hours
    completion_window = 10080 # 7 days

    lifecycle {
      cold_storage_after = 30
      delete_after       = var.backup_retention_days
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-elasticache-backup-plan-${var.environment}"
    Type = "backup-plan"
  })
}

resource "aws_backup_vault" "elasticache" {
  count = var.enable_automated_backups ? 1 : 0

  name        = "${var.project_name}-elasticache-backup-vault-${var.environment}"
  kms_key_arn = aws_kms_key.elasticache.arn

  tags = merge(var.tags, {
    Name = "${var.project_name}-elasticache-backup-vault-${var.environment}"
    Type = "backup-vault"
  })
}

resource "aws_iam_role" "backup" {
  count = var.enable_automated_backups ? 1 : 0

  name = "${var.project_name}-elasticache-backup-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "backup.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${var.project_name}-elasticache-backup-role-${var.environment}"
    Type = "iam-role"
  })
}

resource "aws_iam_role_policy_attachment" "backup" {
  count = var.enable_automated_backups ? 1 : 0

  role       = aws_iam_role.backup[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

# Custom CloudWatch Dashboard for Redis monitoring
resource "aws_cloudwatch_dashboard" "redis_dashboard" {
  count = var.enable_monitoring_dashboard ? 1 : 0

  dashboard_name = "${var.project_name}-redis-dashboard-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            for cluster_name, cluster in var.clusters : [
              "AWS/ElastiCache",
              "CPUUtilization",
              "CacheClusterId",
              cluster.cluster_id
            ]
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "Redis CPU Utilization"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            for cluster_name, cluster in var.clusters : [
              "AWS/ElastiCache",
              "DatabaseMemoryUsagePercentage",
              "CacheClusterId",
              cluster.cluster_id
            ]
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "Redis Memory Utilization"
          period  = 300
        }
      }
    ]
  })
}
