# Backup Module - AWS Backup Service Configuration
# Production-ready backup strategies for RDS, EBS, and configuration data

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Local variables
locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name

  # Backup configuration based on environment
  backup_config = {
    development = {
      backup_schedule = "cron(0 3 * * ? *)"  # Daily at 3 AM
      delete_after_days = 7
      move_to_cold_storage_after_days = null
      cross_region_backup_enabled = false
      backup_vault_lock_enabled = false
    }
    staging = {
      backup_schedule = "cron(0 2 * * ? *)"  # Daily at 2 AM
      delete_after_days = 30
      move_to_cold_storage_after_days = 7
      cross_region_backup_enabled = true
      backup_vault_lock_enabled = false
    }
    production = {
      backup_schedule = "cron(0 1 * * ? *)"  # Daily at 1 AM
      delete_after_days = 90
      move_to_cold_storage_after_days = 30
      cross_region_backup_enabled = true
      backup_vault_lock_enabled = true
    }
  }

  config = local.backup_config[var.environment]

  # Override with variable values if provided
  final_schedule = var.backup_schedule != "" ? var.backup_schedule : local.config.backup_schedule
  final_delete_after_days = var.delete_after_days != 0 ? var.delete_after_days : local.config.delete_after_days
  final_cold_storage_days = var.move_to_cold_storage_after_days != null ? var.move_to_cold_storage_after_days : local.config.move_to_cold_storage_after_days
}

# KMS key for backup encryption
resource "aws_kms_key" "backup" {
  description             = "KMS key for ${var.project_name} backup encryption"
  deletion_window_in_days = var.kms_deletion_window
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${local.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Effect = "Allow"
        Principal = {
          Service = [
            "backup.amazonaws.com",
            "rds.amazonaws.com",
            "ec2.amazonaws.com"
          ]
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:ReEncrypt*",
          "kms:CreateGrant",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-backup-kms-${var.environment}"
    Type        = "kms-key"
    Purpose     = "backup-encryption"
  })
}

resource "aws_kms_alias" "backup" {
  name          = "alias/${var.project_name}-backup-${var.environment}"
  target_key_id = aws_kms_key.backup.key_id
}

# AWS Backup Vault
resource "aws_backup_vault" "main" {
  name        = var.backup_vault_name
  kms_key_arn = aws_kms_key.backup.arn

  tags = merge(var.tags, {
    Name = var.backup_vault_name
    Type = "backup-vault"
  })
}

# Backup vault lock policy for production (WORM compliance)
resource "aws_backup_vault_lock_configuration" "main" {
  count = local.config.backup_vault_lock_enabled ? 1 : 0

  backup_vault_name   = aws_backup_vault.main.name
  changeable_for_days = 3
  max_retention_days  = var.max_retention_days
  min_retention_days  = var.min_retention_days
}

# Cross-region backup vault for disaster recovery
resource "aws_backup_vault" "cross_region" {
  count = local.config.cross_region_backup_enabled ? 1 : 0

  provider = aws.replica
  name     = "${var.backup_vault_name}-replica"
  kms_key_arn = aws_kms_key.backup_replica[0].arn

  tags = merge(var.tags, {
    Name = "${var.backup_vault_name}-replica"
    Type = "backup-vault"
    Purpose = "cross-region-backup"
  })
}

# KMS key for cross-region backup
resource "aws_kms_key" "backup_replica" {
  count = local.config.cross_region_backup_enabled ? 1 : 0

  provider                = aws.replica
  description             = "KMS key for ${var.project_name} cross-region backup encryption"
  deletion_window_in_days = var.kms_deletion_window
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${local.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Effect = "Allow"
        Principal = {
          Service = "backup.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:ReEncrypt*",
          "kms:CreateGrant",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(var.tags, {
    Name    = "${var.project_name}-backup-replica-kms-${var.environment}"
    Type    = "kms-key"
    Purpose = "cross-region-backup-encryption"
  })
}

resource "aws_kms_alias" "backup_replica" {
  count = local.config.cross_region_backup_enabled ? 1 : 0

  provider      = aws.replica
  name          = "alias/${var.project_name}-backup-replica-${var.environment}"
  target_key_id = aws_kms_key.backup_replica[0].key_id
}

# IAM role for AWS Backup service
resource "aws_iam_role" "backup" {
  name = "${var.project_name}-backup-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "backup.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${var.project_name}-backup-role-${var.environment}"
    Type = "iam-role"
  })
}

# Attach AWS managed backup policy
resource "aws_iam_role_policy_attachment" "backup" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

# Additional policy for cross-region backup
resource "aws_iam_role_policy" "backup_cross_region" {
  count = local.config.cross_region_backup_enabled ? 1 : 0

  name = "${var.project_name}-backup-cross-region-policy-${var.environment}"
  role = aws_iam_role.backup.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "backup:CopyIntoBackupVault",
          "backup:CreateBackupVault",
          "backup:DescribeBackupVault",
          "backup:PutBackupVaultAccessPolicy"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey",
          "kms:ReEncrypt*"
        ]
        Resource = [
          aws_kms_key.backup.arn,
          aws_kms_key.backup_replica[0].arn
        ]
      }
    ]
  })
}

# Main backup plan
resource "aws_backup_plan" "main" {
  name = var.backup_plan_name

  # Daily backup rule
  rule {
    rule_name         = "${var.project_name}-daily-backup-${var.environment}"
    target_vault_name = aws_backup_vault.main.name
    schedule          = local.final_schedule

    lifecycle {
      delete_after = local.final_delete_after_days
      cold_storage_after = local.final_cold_storage_days
    }

    recovery_point_tags = merge(var.tags, {
      BackupPlan = var.backup_plan_name
      BackupRule = "daily"
    })

    # Copy to cross-region vault for production
    dynamic "copy_action" {
      for_each = local.config.cross_region_backup_enabled ? [1] : []
      content {
        destination_vault_arn = aws_backup_vault.cross_region[0].arn

        lifecycle {
          delete_after = local.final_delete_after_days
          cold_storage_after = local.final_cold_storage_days
        }
      }
    }
  }

  # Weekly backup rule for long-term retention
  rule {
    rule_name         = "${var.project_name}-weekly-backup-${var.environment}"
    target_vault_name = aws_backup_vault.main.name
    schedule          = var.weekly_backup_schedule

    lifecycle {
      delete_after = var.long_term_retention_days
      cold_storage_after = var.weekly_cold_storage_days
    }

    recovery_point_tags = merge(var.tags, {
      BackupPlan = var.backup_plan_name
      BackupRule = "weekly"
    })

    dynamic "copy_action" {
      for_each = local.config.cross_region_backup_enabled ? [1] : []
      content {
        destination_vault_arn = aws_backup_vault.cross_region[0].arn

        lifecycle {
          delete_after = var.long_term_retention_days
          cold_storage_after = var.weekly_cold_storage_days
        }
      }
    }
  }

  # Monthly backup rule for archival
  rule {
    rule_name         = "${var.project_name}-monthly-backup-${var.environment}"
    target_vault_name = aws_backup_vault.main.name
    schedule          = var.monthly_backup_schedule

    lifecycle {
      delete_after = var.archival_retention_days
      cold_storage_after = 30  # Move to cold storage after 30 days
    }

    recovery_point_tags = merge(var.tags, {
      BackupPlan = var.backup_plan_name
      BackupRule = "monthly"
    })

    dynamic "copy_action" {
      for_each = local.config.cross_region_backup_enabled && var.environment == "production" ? [1] : []
      content {
        destination_vault_arn = aws_backup_vault.cross_region[0].arn

        lifecycle {
          delete_after = var.archival_retention_days
          cold_storage_after = 30
        }
      }
    }
  }

  tags = merge(var.tags, {
    Name = var.backup_plan_name
    Type = "backup-plan"
  })
}

# Backup selection for RDS instances
resource "aws_backup_selection" "rds" {
  count = length(var.rds_instances) > 0 ? 1 : 0

  iam_role_arn = aws_iam_role.backup.arn
  name         = "${var.project_name}-rds-backup-selection-${var.environment}"
  plan_id      = aws_backup_plan.main.id

  resources = [
    for instance in var.rds_instances : instance.arn
  ]

  # Conditions for more granular selection
  condition {
    string_equals {
      key   = "aws:ResourceTag/Environment"
      value = var.environment
    }
  }

  condition {
    string_equals {
      key   = "aws:ResourceTag/Project"
      value = var.project_name
    }
  }
}

# Backup selection for EBS volumes (EKS persistent volumes)
resource "aws_backup_selection" "ebs" {
  iam_role_arn = aws_iam_role.backup.arn
  name         = "${var.project_name}-ebs-backup-selection-${var.environment}"
  plan_id      = aws_backup_plan.main.id

  resources = ["arn:aws:ec2:*:*:volume/*"]

  condition {
    string_equals {
      key   = "aws:ResourceTag/KubernetesCluster"
      value = "${var.project_name}-${var.environment}"
    }
  }

  condition {
    string_equals {
      key   = "aws:ResourceTag/Environment"
      value = var.environment
    }
  }

  # Exclude temporary volumes
  condition {
    string_not_equals {
      key   = "aws:ResourceTag/VolumeType"
      value = "temporary"
    }
  }
}

# Backup selection for EFS file systems (if any)
resource "aws_backup_selection" "efs" {
  count = var.backup_efs_enabled ? 1 : 0

  iam_role_arn = aws_iam_role.backup.arn
  name         = "${var.project_name}-efs-backup-selection-${var.environment}"
  plan_id      = aws_backup_plan.main.id

  resources = ["arn:aws:elasticfilesystem:*:*:file-system/*"]

  condition {
    string_equals {
      key   = "aws:ResourceTag/Environment"
      value = var.environment
    }
  }

  condition {
    string_equals {
      key   = "aws:ResourceTag/Project"
      value = var.project_name
    }
  }
}

# SNS topic for backup notifications
resource "aws_sns_topic" "backup_notifications" {
  count = var.enable_backup_notifications ? 1 : 0

  name = "${var.project_name}-backup-notifications-${var.environment}"

  kms_master_key_id = aws_kms_key.backup.arn

  tags = merge(var.tags, {
    Name = "${var.project_name}-backup-notifications-${var.environment}"
    Type = "sns-topic"
  })
}

resource "aws_sns_topic_subscription" "backup_email" {
  count = var.enable_backup_notifications && var.notification_email != "" ? 1 : 0

  topic_arn = aws_sns_topic.backup_notifications[0].arn
  protocol  = "email"
  endpoint  = var.notification_email
}

# EventBridge rules for backup job monitoring
resource "aws_cloudwatch_event_rule" "backup_job_success" {
  count = var.enable_backup_notifications ? 1 : 0

  name        = "${var.project_name}-backup-job-success-${var.environment}"
  description = "Capture successful backup jobs"

  event_pattern = jsonencode({
    source      = ["aws.backup"]
    detail-type = ["Backup Job State Change"]
    detail = {
      state = ["COMPLETED"]
    }
  })

  tags = merge(var.tags, {
    Name = "${var.project_name}-backup-job-success-${var.environment}"
    Type = "eventbridge-rule"
  })
}

resource "aws_cloudwatch_event_target" "backup_job_success" {
  count = var.enable_backup_notifications ? 1 : 0

  rule      = aws_cloudwatch_event_rule.backup_job_success[0].name
  target_id = "SendToSNS"
  arn       = aws_sns_topic.backup_notifications[0].arn
}

resource "aws_cloudwatch_event_rule" "backup_job_failed" {
  count = var.enable_backup_notifications ? 1 : 0

  name        = "${var.project_name}-backup-job-failed-${var.environment}"
  description = "Capture failed backup jobs"

  event_pattern = jsonencode({
    source      = ["aws.backup"]
    detail-type = ["Backup Job State Change"]
    detail = {
      state = ["FAILED", "ABORTED", "EXPIRED"]
    }
  })

  tags = merge(var.tags, {
    Name = "${var.project_name}-backup-job-failed-${var.environment}"
    Type = "eventbridge-rule"
  })
}

resource "aws_cloudwatch_event_target" "backup_job_failed" {
  count = var.enable_backup_notifications ? 1 : 0

  rule      = aws_cloudwatch_event_rule.backup_job_failed[0].name
  target_id = "SendToSNS"
  arn       = aws_sns_topic.backup_notifications[0].arn
}

# CloudWatch alarms for backup monitoring
resource "aws_cloudwatch_metric_alarm" "backup_job_failed" {
  count = var.enable_backup_monitoring ? 1 : 0

  alarm_name          = "${var.project_name}-backup-job-failed-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "NumberOfBackupJobsFailed"
  namespace           = "AWS/Backup"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "This metric monitors failed backup jobs"
  alarm_actions       = var.enable_backup_notifications ? [aws_sns_topic.backup_notifications[0].arn] : []

  dimensions = {
    BackupVaultName = aws_backup_vault.main.name
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-backup-job-failed-alarm-${var.environment}"
    Type = "cloudwatch-alarm"
  })
}

resource "aws_cloudwatch_metric_alarm" "backup_vault_size" {
  count = var.enable_backup_monitoring ? 1 : 0

  alarm_name          = "${var.project_name}-backup-vault-size-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "NumberOfBackupJobsRunning"
  namespace           = "AWS/Backup"
  period              = "300"
  statistic           = "Average"
  threshold           = var.max_concurrent_backups
  alarm_description   = "This metric monitors running backup jobs to prevent resource exhaustion"
  alarm_actions       = var.enable_backup_notifications ? [aws_sns_topic.backup_notifications[0].arn] : []

  dimensions = {
    BackupVaultName = aws_backup_vault.main.name
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-backup-vault-size-alarm-${var.environment}"
    Type = "cloudwatch-alarm"
  })
}

# Lambda function for backup validation and reporting
resource "aws_lambda_function" "backup_validator" {
  count = var.enable_backup_validation ? 1 : 0

  filename         = "backup_validator.zip"
  function_name    = "${var.project_name}-backup-validator-${var.environment}"
  role            = aws_iam_role.backup_validator[0].arn
  handler         = "index.handler"
  source_code_hash = data.archive_file.backup_validator[0].output_base64sha256
  runtime         = "python3.9"
  timeout         = 300

  environment {
    variables = {
      BACKUP_VAULT_NAME = aws_backup_vault.main.name
      PROJECT_NAME      = var.project_name
      ENVIRONMENT       = var.environment
      SNS_TOPIC_ARN     = var.enable_backup_notifications ? aws_sns_topic.backup_notifications[0].arn : ""
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-backup-validator-${var.environment}"
    Type = "lambda-function"
  })
}

# Archive file for Lambda function
data "archive_file" "backup_validator" {
  count = var.enable_backup_validation ? 1 : 0

  type        = "zip"
  output_path = "backup_validator.zip"

  source {
    content = templatefile("${path.module}/templates/backup_validator.py", {
      backup_vault_name = aws_backup_vault.main.name
      project_name      = var.project_name
      environment       = var.environment
    })
    filename = "index.py"
  }
}

# IAM role for backup validator Lambda
resource "aws_iam_role" "backup_validator" {
  count = var.enable_backup_validation ? 1 : 0

  name = "${var.project_name}-backup-validator-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${var.project_name}-backup-validator-role-${var.environment}"
    Type = "iam-role"
  })
}

resource "aws_iam_role_policy" "backup_validator" {
  count = var.enable_backup_validation ? 1 : 0

  name = "${var.project_name}-backup-validator-policy-${var.environment}"
  role = aws_iam_role.backup_validator[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "backup:DescribeBackupVault",
          "backup:ListBackupJobs",
          "backup:DescribeBackupJob",
          "backup:ListRecoveryPoints",
          "backup:DescribeRecoveryPoint"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = var.enable_backup_notifications ? aws_sns_topic.backup_notifications[0].arn : "*"
      }
    ]
  })
}

# EventBridge rule to trigger backup validation
resource "aws_cloudwatch_event_rule" "backup_validation" {
  count = var.enable_backup_validation ? 1 : 0

  name                = "${var.project_name}-backup-validation-${var.environment}"
  description         = "Trigger backup validation daily"
  schedule_expression = var.backup_validation_schedule

  tags = merge(var.tags, {
    Name = "${var.project_name}-backup-validation-${var.environment}"
    Type = "eventbridge-rule"
  })
}

resource "aws_cloudwatch_event_target" "backup_validation" {
  count = var.enable_backup_validation ? 1 : 0

  rule      = aws_cloudwatch_event_rule.backup_validation[0].name
  target_id = "BackupValidatorLambda"
  arn       = aws_lambda_function.backup_validator[0].arn
}

resource "aws_lambda_permission" "backup_validation" {
  count = var.enable_backup_validation ? 1 : 0

  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.backup_validator[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.backup_validation[0].arn
}
