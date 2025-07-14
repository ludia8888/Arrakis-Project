# RDS Module - Production-ready PostgreSQL databases
# Comprehensive managed database infrastructure with high availability, security, and monitoring

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# KMS Key for RDS encryption
resource "aws_kms_key" "rds" {
  description             = "KMS key for RDS encryption"
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
        Sid    = "Allow RDS Service"
        Effect = "Allow"
        Principal = {
          Service = "rds.amazonaws.com"
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
    Name = "${var.project_name}-rds-kms-${var.environment}"
    Type = "kms-key"
  })
}

resource "aws_kms_alias" "rds" {
  name          = "alias/${var.project_name}-rds-${var.environment}"
  target_key_id = aws_kms_key.rds.key_id
}

# Random password generation for master passwords
resource "random_password" "master_password" {
  for_each = var.databases

  length  = 16
  special = true
}

# AWS Secrets Manager secrets for database credentials
resource "aws_secretsmanager_secret" "database_credentials" {
  for_each = var.databases

  name                    = "${var.project_name}-${each.key}-credentials-${var.environment}"
  description             = "Database credentials for ${each.key}"
  kms_key_id              = aws_kms_key.rds.arn
  recovery_window_in_days = 7

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-credentials-${var.environment}"
    Type = "database-secret"
    Database = each.key
  })
}

resource "aws_secretsmanager_secret_version" "database_credentials" {
  for_each = var.databases

  secret_id = aws_secretsmanager_secret.database_credentials[each.key].id
  secret_string = jsonencode({
    username = each.value.master_username
    password = random_password.master_password[each.key].result
    endpoint = aws_db_instance.main[each.key].endpoint
    port     = aws_db_instance.main[each.key].port
    dbname   = each.value.database_name
  })
}

# Parameter groups for database optimization
resource "aws_db_parameter_group" "main" {
  for_each = var.databases

  family = "postgres${split(".", each.value.engine_version)[0]}"
  name   = "${var.project_name}-${each.key}-params-${var.environment}"

  # Performance optimization parameters
  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements,pg_hint_plan"
  }

  parameter {
    name  = "log_statement"
    value = "all"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }

  parameter {
    name  = "log_checkpoints"
    value = "1"
  }

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_lock_waits"
    value = "1"
  }

  parameter {
    name  = "log_temp_files"
    value = "0"
  }

  parameter {
    name  = "track_activity_query_size"
    value = "2048"
  }

  parameter {
    name  = "track_io_timing"
    value = "1"
  }

  parameter {
    name  = "wal_buffers"
    value = "16MB"
  }

  parameter {
    name  = "effective_cache_size"
    value = "{DBInstanceClassMemory*3/4}"
  }

  parameter {
    name  = "maintenance_work_mem"
    value = "{DBInstanceClassMemory/16}"
  }

  parameter {
    name  = "checkpoint_completion_target"
    value = "0.9"
  }

  parameter {
    name  = "wal_level"
    value = "replica"
  }

  parameter {
    name  = "max_wal_senders"
    value = "3"
  }

  parameter {
    name  = "archive_mode"
    value = "on"
  }

  parameter {
    name  = "archive_command"
    value = "/bin/true"
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-params-${var.environment}"
    Type = "db-parameter-group"
    Database = each.key
  })
}

# Option groups for additional database features
resource "aws_db_option_group" "main" {
  for_each = var.databases

  name                     = "${var.project_name}-${each.key}-options-${var.environment}"
  option_group_description = "Option group for ${each.key}"
  engine_name              = "postgres"
  major_engine_version     = split(".", each.value.engine_version)[0]

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-options-${var.environment}"
    Type = "db-option-group"
    Database = each.key
  })
}

# CloudWatch Log Groups for database logs
resource "aws_cloudwatch_log_group" "database_logs" {
  for_each = var.databases

  name              = "/aws/rds/instance/${var.project_name}-${each.key}-${var.environment}/postgresql"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-logs-${var.environment}"
    Type = "log-group"
    Database = each.key
  })
}

# Enhanced monitoring IAM role
resource "aws_iam_role" "rds_enhanced_monitoring" {
  count = var.enable_enhanced_monitoring ? 1 : 0

  name = "${var.project_name}-rds-enhanced-monitoring-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${var.project_name}-rds-enhanced-monitoring-${var.environment}"
    Type = "iam-role"
  })
}

resource "aws_iam_role_policy_attachment" "rds_enhanced_monitoring" {
  count = var.enable_enhanced_monitoring ? 1 : 0

  role       = aws_iam_role.rds_enhanced_monitoring[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# RDS Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-group-${var.environment}"
  subnet_ids = var.subnet_ids

  tags = merge(var.tags, {
    Name = "${var.project_name}-db-subnet-group-${var.environment}"
    Type = "db-subnet-group"
  })
}

# Security Group for RDS
resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg-${var.environment}"
  description = "Security group for RDS databases"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
    description = "PostgreSQL access from allowed networks"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-rds-sg-${var.environment}"
    Type = "security-group"
  })
}

# RDS Database Instances
resource "aws_db_instance" "main" {
  for_each = var.databases

  # Basic Configuration
  identifier     = each.value.identifier
  engine         = "postgres"
  engine_version = each.value.engine_version
  instance_class = each.value.instance_class

  # Storage Configuration
  allocated_storage     = each.value.allocated_storage
  max_allocated_storage = each.value.max_allocated_storage
  storage_type          = each.value.storage_type
  storage_encrypted     = each.value.storage_encrypted
  kms_key_id            = each.value.storage_encrypted ? aws_kms_key.rds.arn : null

  # Database Configuration
  db_name  = each.value.database_name
  username = each.value.master_username
  password = random_password.master_password[each.key].result
  port     = 5432

  # Network Configuration
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = each.value.publicly_accessible

  # High Availability Configuration
  multi_az               = each.value.multi_az
  availability_zone      = each.value.multi_az ? null : each.value.availability_zone

  # Backup Configuration
  backup_retention_period = each.value.backup_retention_period
  backup_window          = each.value.backup_window
  copy_tags_to_snapshot  = true
  delete_automated_backups = false

  # Maintenance Configuration
  maintenance_window         = each.value.maintenance_window
  auto_minor_version_upgrade = each.value.auto_minor_version_upgrade
  apply_immediately          = each.value.apply_immediately

  # Deletion Protection
  deletion_protection = each.value.deletion_protection
  skip_final_snapshot = each.value.skip_final_snapshot
  final_snapshot_identifier = each.value.skip_final_snapshot ? null : "${each.value.identifier}-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"

  # Parameter and Option Groups
  parameter_group_name = aws_db_parameter_group.main[each.key].name
  option_group_name    = aws_db_option_group.main[each.key].name

  # Monitoring Configuration
  monitoring_interval = each.value.monitoring_interval
  monitoring_role_arn = var.enable_enhanced_monitoring ? aws_iam_role.rds_enhanced_monitoring[0].arn : null

  # Performance Insights
  performance_insights_enabled          = each.value.performance_insights_enabled
  performance_insights_kms_key_id       = each.value.performance_insights_enabled ? aws_kms_key.rds.arn : null
  performance_insights_retention_period = each.value.performance_insights_retention_period

  # Logging Configuration
  enabled_cloudwatch_logs_exports = each.value.enabled_cloudwatch_logs_exports

  # Snapshot Configuration
  snapshot_identifier = each.value.snapshot_identifier

  # Character Set
  character_set_name = each.value.character_set_name

  # License Model
  license_model = each.value.license_model

  # Timezone
  timezone = each.value.timezone

  # CA Certificate
  ca_cert_identifier = each.value.ca_cert_identifier

  # Domain Configuration
  domain               = each.value.domain
  domain_iam_role_name = each.value.domain_iam_role_name

  # Lifecycle Management
  lifecycle {
    ignore_changes = [
      password,
      snapshot_identifier,
      final_snapshot_identifier
    ]
  }

  # Dependencies
  depends_on = [
    aws_db_subnet_group.main,
    aws_security_group.rds,
    aws_db_parameter_group.main,
    aws_db_option_group.main,
    aws_cloudwatch_log_group.database_logs
  ]

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-${var.environment}"
    Type = "rds-instance"
    Database = each.key
  })
}

# Read Replicas for production workloads
resource "aws_db_instance" "read_replica" {
  for_each = var.enable_read_replicas ? var.databases : {}

  # Basic Configuration
  identifier                = "${each.value.identifier}-read-replica"
  replicate_source_db       = aws_db_instance.main[each.key].id
  instance_class            = each.value.replica_instance_class
  publicly_accessible       = false
  auto_minor_version_upgrade = true

  # Storage Configuration
  storage_encrypted = each.value.storage_encrypted
  kms_key_id        = each.value.storage_encrypted ? aws_kms_key.rds.arn : null

  # Monitoring Configuration
  monitoring_interval = each.value.monitoring_interval
  monitoring_role_arn = var.enable_enhanced_monitoring ? aws_iam_role.rds_enhanced_monitoring[0].arn : null

  # Performance Insights
  performance_insights_enabled          = each.value.performance_insights_enabled
  performance_insights_kms_key_id       = each.value.performance_insights_enabled ? aws_kms_key.rds.arn : null
  performance_insights_retention_period = each.value.performance_insights_retention_period

  # Logging Configuration
  enabled_cloudwatch_logs_exports = each.value.enabled_cloudwatch_logs_exports

  # Deletion Protection
  deletion_protection = each.value.deletion_protection
  skip_final_snapshot = true

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-read-replica-${var.environment}"
    Type = "rds-read-replica"
    Database = each.key
  })
}

# CloudWatch Alarms for database monitoring
resource "aws_cloudwatch_metric_alarm" "database_cpu" {
  for_each = var.databases

  alarm_name          = "${var.project_name}-${each.key}-cpu-utilization-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors RDS CPU utilization"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main[each.key].id
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-cpu-alarm-${var.environment}"
    Type = "cloudwatch-alarm"
    Database = each.key
  })
}

resource "aws_cloudwatch_metric_alarm" "database_memory" {
  for_each = var.databases

  alarm_name          = "${var.project_name}-${each.key}-memory-utilization-${var.environment}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "FreeableMemory"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "268435456" # 256 MB in bytes
  alarm_description   = "This metric monitors RDS free memory"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main[each.key].id
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-memory-alarm-${var.environment}"
    Type = "cloudwatch-alarm"
    Database = each.key
  })
}

resource "aws_cloudwatch_metric_alarm" "database_connections" {
  for_each = var.databases

  alarm_name          = "${var.project_name}-${each.key}-connections-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "100"
  alarm_description   = "This metric monitors RDS database connections"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main[each.key].id
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-connections-alarm-${var.environment}"
    Type = "cloudwatch-alarm"
    Database = each.key
  })
}

resource "aws_cloudwatch_metric_alarm" "database_storage" {
  for_each = var.databases

  alarm_name          = "${var.project_name}-${each.key}-storage-space-${var.environment}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "2147483648" # 2 GB in bytes
  alarm_description   = "This metric monitors RDS free storage space"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main[each.key].id
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-storage-alarm-${var.environment}"
    Type = "cloudwatch-alarm"
    Database = each.key
  })
}

# Database event subscriptions
resource "aws_db_event_subscription" "main" {
  for_each = var.databases

  name      = "${var.project_name}-${each.key}-events-${var.environment}"
  sns_topic = var.sns_topic_arn

  source_type = "db-instance"
  source_ids  = [aws_db_instance.main[each.key].id]

  event_categories = [
    "availability",
    "backup",
    "configuration change",
    "creation",
    "deletion",
    "failover",
    "failure",
    "low storage",
    "maintenance",
    "notification",
    "recovery",
    "restoration"
  ]

  enabled = var.sns_topic_arn != ""

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-events-${var.environment}"
    Type = "db-event-subscription"
    Database = each.key
  })
}

# Automated backups with AWS Backup
resource "aws_backup_selection" "database_backup" {
  count = var.enable_automated_backups ? 1 : 0

  iam_role_arn = aws_iam_role.backup[0].arn
  name         = "${var.project_name}-database-backup-${var.environment}"
  plan_id      = aws_backup_plan.database[0].id

  resources = [
    for db in aws_db_instance.main : db.arn
  ]

  condition {
    string_equals {
      key   = "aws:ResourceTag/BackupEnabled"
      value = "true"
    }
  }
}

resource "aws_backup_plan" "database" {
  count = var.enable_automated_backups ? 1 : 0

  name = "${var.project_name}-database-backup-plan-${var.environment}"

  rule {
    rule_name         = "daily_backup"
    target_vault_name = aws_backup_vault.database[0].name
    schedule          = "cron(0 5 ? * * *)"
    start_window      = 480  # 8 hours
    completion_window = 10080 # 7 days

    lifecycle {
      cold_storage_after = 30
      delete_after       = var.backup_retention_days
    }

    copy_action {
      destination_vault_arn = aws_backup_vault.database[0].arn

      lifecycle {
        cold_storage_after = 30
        delete_after       = var.backup_retention_days
      }
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-database-backup-plan-${var.environment}"
    Type = "backup-plan"
  })
}

resource "aws_backup_vault" "database" {
  count = var.enable_automated_backups ? 1 : 0

  name        = "${var.project_name}-database-backup-vault-${var.environment}"
  kms_key_arn = aws_kms_key.rds.arn

  tags = merge(var.tags, {
    Name = "${var.project_name}-database-backup-vault-${var.environment}"
    Type = "backup-vault"
  })
}

resource "aws_iam_role" "backup" {
  count = var.enable_automated_backups ? 1 : 0

  name = "${var.project_name}-backup-role-${var.environment}"

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
    Name = "${var.project_name}-backup-role-${var.environment}"
    Type = "iam-role"
  })
}

resource "aws_iam_role_policy_attachment" "backup" {
  count = var.enable_automated_backups ? 1 : 0

  role       = aws_iam_role.backup[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}