# Security Module - IAM, IRSA, Secrets Management
# Production-ready security infrastructure for Arrakis microservices

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Local variables
locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name

  # Service account configurations with IRSA roles
  service_accounts = merge(var.service_accounts, {
    # Core microservices IRSA roles
    "ontology-management-service" = {
      namespace = "arrakis"
      policies = [
        "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",
        "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy",
        "arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess"
      ]
      custom_policy_statements = [
        {
          effect = "Allow"
          actions = [
            "secretsmanager:GetSecretValue",
            "secretsmanager:DescribeSecret"
          ]
          resources = [
            "arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:arrakis/*"
          ]
        }
      ]
    }

    "user-service" = {
      namespace = "arrakis"
      policies = [
        "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
      ]
      custom_policy_statements = [
        {
          effect = "Allow"
          actions = [
            "secretsmanager:GetSecretValue",
            "kms:Decrypt"
          ]
          resources = [
            "arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:arrakis/user-service/*",
            "arn:aws:kms:${local.region}:${local.account_id}:key/*"
          ]
        }
      ]
    }

    "audit-service" = {
      namespace = "arrakis"
      policies = [
        "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
        "arn:aws:iam::aws:policy/AmazonS3FullAccess"
      ]
      custom_policy_statements = [
        {
          effect = "Allow"
          actions = [
            "s3:PutObject",
            "s3:PutObjectAcl",
            "s3:GetObject",
            "s3:ListBucket"
          ]
          resources = [
            "arn:aws:s3:::arrakis-audit-logs-${var.environment}",
            "arn:aws:s3:::arrakis-audit-logs-${var.environment}/*"
          ]
        }
      ]
    }

    "data-kernel-service" = {
      namespace = "arrakis"
      policies = [
        "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
      ]
      custom_policy_statements = [
        {
          effect = "Allow"
          actions = [
            "secretsmanager:GetSecretValue",
            "rds:DescribeDBInstances"
          ]
          resources = [
            "arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:arrakis/data-kernel/*",
            "arn:aws:rds:${local.region}:${local.account_id}:db:*"
          ]
        }
      ]
    }

    "embedding-service" = {
      namespace = "arrakis"
      policies = [
        "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
      ]
      custom_policy_statements = [
        {
          effect = "Allow"
          actions = [
            "s3:GetObject",
            "s3:PutObject"
          ]
          resources = [
            "arn:aws:s3:::arrakis-ml-models-${var.environment}",
            "arn:aws:s3:::arrakis-ml-models-${var.environment}/*"
          ]
        }
      ]
    }

    "scheduler-service" = {
      namespace = "arrakis"
      policies = [
        "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
      ]
      custom_policy_statements = [
        {
          effect = "Allow"
          actions = [
            "events:PutEvents",
            "sqs:SendMessage",
            "sqs:ReceiveMessage"
          ]
          resources = [
            "arn:aws:events:${local.region}:${local.account_id}:event-bus/arrakis-*",
            "arn:aws:sqs:${local.region}:${local.account_id}:arrakis-*"
          ]
        }
      ]
    }

    "event-gateway" = {
      namespace = "arrakis"
      policies = [
        "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
      ]
      custom_policy_statements = [
        {
          effect = "Allow"
          actions = [
            "events:PutEvents",
            "sns:Publish",
            "sqs:SendMessage"
          ]
          resources = [
            "arn:aws:events:${local.region}:${local.account_id}:event-bus/*",
            "arn:aws:sns:${local.region}:${local.account_id}:arrakis-*",
            "arn:aws:sqs:${local.region}:${local.account_id}:arrakis-*"
          ]
        }
      ]
    }
  })
}

# IAM Role for Service Accounts (IRSA)
resource "aws_iam_role" "service_account" {
  for_each = local.service_accounts

  name = "${var.project_name}-${each.key}-irsa-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = "arn:aws:iam::${local.account_id}:oidc-provider/${replace(var.cluster_oidc_issuer_url, "https://", "")}"
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(var.cluster_oidc_issuer_url, "https://", "")}:sub" = "system:serviceaccount:${each.value.namespace}:${each.key}"
            "${replace(var.cluster_oidc_issuer_url, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${each.key}-irsa-${var.environment}"
    ServiceName = each.key
    Namespace   = each.value.namespace
    Type        = "irsa-role"
  })
}

# Attach AWS managed policies to service account roles
resource "aws_iam_role_policy_attachment" "service_account_managed" {
  for_each = merge([
    for sa_name, sa_config in local.service_accounts : {
      for policy in sa_config.policies : "${sa_name}-${basename(policy)}" => {
        role_name  = aws_iam_role.service_account[sa_name].name
        policy_arn = policy
      }
    }
  ]...)

  role       = each.value.role_name
  policy_arn = each.value.policy_arn
}

# Custom IAM policies for service accounts
resource "aws_iam_role_policy" "service_account_custom" {
  for_each = {
    for sa_name, sa_config in local.service_accounts :
    sa_name => sa_config
    if lookup(sa_config, "custom_policy_statements", null) != null
  }

  name = "${var.project_name}-${each.key}-custom-policy-${var.environment}"
  role = aws_iam_role.service_account[each.key].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = each.value.custom_policy_statements
  })
}

# KMS Key for secrets encryption
resource "aws_kms_key" "secrets" {
  description             = "KMS key for Arrakis secrets encryption"
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
          AWS = [
            for role in aws_iam_role.service_account : role.arn
          ]
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-secrets-${var.environment}"
    Type        = "kms-key"
    Purpose     = "secrets-encryption"
  })
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/${var.project_name}-secrets-${var.environment}"
  target_key_id = aws_kms_key.secrets.key_id
}

# AWS Secrets Manager secrets
resource "aws_secretsmanager_secret" "secrets" {
  for_each = var.secrets

  name        = "${var.project_name}/${each.key}-${var.environment}"
  description = each.value.description
  kms_key_id  = aws_kms_key.secrets.arn

  # Recovery window for secret deletion
  recovery_window_in_days = var.secret_recovery_window

  replica {
    region     = var.replica_region
    kms_key_id = aws_kms_key.secrets.arn
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${each.key}-${var.environment}"
    Type = "secret"
  })
}

resource "aws_secretsmanager_secret_version" "secrets" {
  for_each = var.secrets

  secret_id     = aws_secretsmanager_secret.secrets[each.key].id
  secret_string = jsonencode(each.value.secret_data)

  version_stages = ["AWSCURRENT"]
}

# Security Groups for additional network security
resource "aws_security_group" "microservices" {
  name_prefix = "${var.project_name}-microservices-${var.environment}"
  description = "Security group for Arrakis microservices"
  vpc_id      = var.vpc_id

  # Ingress rules for internal communication
  ingress {
    description = "HTTP from ALB"
    from_port   = 8000
    to_port     = 8010
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  ingress {
    description = "gRPC communication"
    from_port   = 50050
    to_port     = 50060
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  ingress {
    description = "Metrics collection"
    from_port   = 9090
    to_port     = 9090
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  # Egress rules
  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-microservices-sg-${var.environment}"
    Type = "security-group"
  })
}

# Security Group for database access
resource "aws_security_group" "database_access" {
  name_prefix = "${var.project_name}-db-access-${var.environment}"
  description = "Security group for database access from microservices"
  vpc_id      = var.vpc_id

  egress {
    description = "PostgreSQL"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    description = "Redis"
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-db-access-sg-${var.environment}"
    Type = "security-group"
  })
}

# CloudTrail for API logging and security monitoring
resource "aws_cloudtrail" "security_audit" {
  count = var.enable_cloudtrail ? 1 : 0

  name           = "${var.project_name}-security-audit-${var.environment}"
  s3_bucket_name = aws_s3_bucket.cloudtrail_logs[0].bucket

  # Event selectors for detailed logging
  event_selector {
    read_write_type                 = "All"
    include_management_events       = true
    exclude_management_event_sources = ["kms.amazonaws.com", "rdsdata.amazonaws.com"]

    data_resource {
      type   = "AWS::S3::Object"
      values = ["arn:aws:s3:::arrakis-*/*"]
    }

    data_resource {
      type   = "AWS::SecretsManager::Secret"
      values = ["arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:arrakis/*"]
    }
  }

  # Insight selectors for advanced monitoring
  insight_selector {
    insight_type = "ApiCallRateInsight"
  }

  depends_on = [aws_s3_bucket_policy.cloudtrail_logs]

  tags = merge(var.tags, {
    Name = "${var.project_name}-security-audit-${var.environment}"
    Type = "cloudtrail"
  })
}

# S3 bucket for CloudTrail logs
resource "aws_s3_bucket" "cloudtrail_logs" {
  count = var.enable_cloudtrail ? 1 : 0

  bucket        = "${var.project_name}-cloudtrail-logs-${var.environment}-${random_id.bucket_suffix[0].hex}"
  force_destroy = var.environment != "production"

  tags = merge(var.tags, {
    Name = "${var.project_name}-cloudtrail-logs-${var.environment}"
    Type = "s3-bucket"
  })
}

resource "random_id" "bucket_suffix" {
  count = var.enable_cloudtrail ? 1 : 0
  byte_length = 4
}

resource "aws_s3_bucket_versioning" "cloudtrail_logs" {
  count = var.enable_cloudtrail ? 1 : 0

  bucket = aws_s3_bucket.cloudtrail_logs[0].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_encryption" "cloudtrail_logs" {
  count = var.enable_cloudtrail ? 1 : 0

  bucket = aws_s3_bucket.cloudtrail_logs[0].id

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        kms_master_key_id = aws_kms_key.secrets.arn
        sse_algorithm     = "aws:kms"
      }
      bucket_key_enabled = true
    }
  }
}

resource "aws_s3_bucket_public_access_block" "cloudtrail_logs" {
  count = var.enable_cloudtrail ? 1 : 0

  bucket = aws_s3_bucket.cloudtrail_logs[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "cloudtrail_logs" {
  count = var.enable_cloudtrail ? 1 : 0

  bucket = aws_s3_bucket.cloudtrail_logs[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.cloudtrail_logs[0].arn}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      },
      {
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.cloudtrail_logs[0].arn
      }
    ]
  })
}

# AWS Config for compliance monitoring
resource "aws_config_configuration_recorder" "security" {
  count = var.enable_aws_config ? 1 : 0

  name     = "${var.project_name}-security-recorder-${var.environment}"
  role_arn = aws_iam_role.config[0].arn

  recording_group {
    all_supported                 = true
    include_global_resource_types = true
  }

  depends_on = [aws_config_delivery_channel.security]
}

resource "aws_config_delivery_channel" "security" {
  count = var.enable_aws_config ? 1 : 0

  name           = "${var.project_name}-security-delivery-${var.environment}"
  s3_bucket_name = aws_s3_bucket.config_logs[0].bucket
}

resource "aws_s3_bucket" "config_logs" {
  count = var.enable_aws_config ? 1 : 0

  bucket        = "${var.project_name}-config-logs-${var.environment}-${random_id.config_bucket_suffix[0].hex}"
  force_destroy = var.environment != "production"

  tags = merge(var.tags, {
    Name = "${var.project_name}-config-logs-${var.environment}"
    Type = "s3-bucket"
  })
}

resource "random_id" "config_bucket_suffix" {
  count = var.enable_aws_config ? 1 : 0
  byte_length = 4
}

resource "aws_iam_role" "config" {
  count = var.enable_aws_config ? 1 : 0

  name = "${var.project_name}-config-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "config.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${var.project_name}-config-role-${var.environment}"
    Type = "iam-role"
  })
}

resource "aws_iam_role_policy_attachment" "config" {
  count = var.enable_aws_config ? 1 : 0

  role       = aws_iam_role.config[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWS_ConfigRole"
}

# GuardDuty for threat detection
resource "aws_guardduty_detector" "security" {
  count = var.enable_guardduty ? 1 : 0

  enable = true

  datasources {
    s3_logs {
      enable = true
    }
    kubernetes {
      audit_logs {
        enable = var.enable_kubernetes_audit_logs
      }
    }
    malware_protection {
      scan_ec2_instance_with_findings {
        ebs_volumes {
          enable = true
        }
      }
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-guardduty-${var.environment}"
    Type = "guardduty-detector"
  })
}

# Security Hub for centralized security findings
resource "aws_securityhub_account" "security" {
  count = var.enable_security_hub ? 1 : 0

  enable_default_standards = true
}

resource "aws_securityhub_standards_subscription" "cis" {
  count         = var.enable_security_hub ? 1 : 0
  standards_arn = "arn:aws:securityhub:::ruleset/finding-format/aws-foundational-security-standard/v/1.0.0"
  depends_on    = [aws_securityhub_account.security]
}

resource "aws_securityhub_standards_subscription" "pci" {
  count         = var.enable_security_hub ? 1 : 0
  standards_arn = "arn:aws:securityhub:${local.region}::standard/pci-dss/v/3.2.1"
  depends_on    = [aws_securityhub_account.security]
}
