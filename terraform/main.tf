# Arrakis Platform - Main Terraform Configuration
# Production-ready Infrastructure as Code for complete microservices stack

terraform {
  required_version = ">= 1.6.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.24"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # Remote state configuration
  backend "s3" {
    # These values should be provided via backend config file or CLI
    # Example: terraform init -backend-config=backend-config/production.hcl
    # bucket         = "arrakis-terraform-state-prod"
    # key            = "infrastructure/terraform.tfstate"
    # region         = "us-west-2"
    # encrypt        = true
    # dynamodb_table = "arrakis-terraform-locks"
  }
}

# Local variables for common configuration
locals {
  project_name = "arrakis"
  environment  = var.environment
  region      = var.aws_region
  
  # Common tags applied to all resources
  common_tags = {
    Project             = local.project_name
    Environment         = local.environment
    ManagedBy          = "terraform"
    Owner              = "platform-team"
    CostCenter         = "platform-engineering"
    Backup             = "required"
    MonitoringEnabled  = "true"
    SecurityScanning   = "enabled"
    ComplianceRequired = "gdpr,soc2"
    CreatedBy          = "terraform"
    LastModified       = timestamp()
  }

  # Environment-specific configuration
  environment_config = {
    development = {
      instance_sizes = {
        small  = "t3.small"
        medium = "t3.medium"
        large  = "t3.large"
      }
      min_capacity = 1
      max_capacity = 3
      desired_capacity = 2
      enable_deletion_protection = false
      backup_retention_days = 7
      log_retention_days = 14
    }
    staging = {
      instance_sizes = {
        small  = "t3.medium"
        medium = "t3.large"
        large  = "t3.xlarge"
      }
      min_capacity = 2
      max_capacity = 6
      desired_capacity = 3
      enable_deletion_protection = true
      backup_retention_days = 30
      log_retention_days = 30
    }
    production = {
      instance_sizes = {
        small  = "t3.large"
        medium = "t3.xlarge"
        large  = "t3.2xlarge"
      }
      min_capacity = 3
      max_capacity = 20
      desired_capacity = 6
      enable_deletion_protection = true
      backup_retention_days = 90
      log_retention_days = 90
    }
  }

  config = local.environment_config[local.environment]
}

# Data sources for existing AWS resources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

# Generate random suffix for unique resource naming
resource "random_id" "suffix" {
  byte_length = 4
}

# Networking Module - VPC, Subnets, Security Groups
module "networking" {
  source = "./modules/networking"

  project_name        = local.project_name
  environment        = local.environment
  availability_zones = data.aws_availability_zones.available.names
  
  # VPC Configuration
  vpc_cidr = var.vpc_cidr
  
  # Subnet Configuration
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  database_subnet_cidrs = var.database_subnet_cidrs
  
  # Security Configuration
  enable_nat_gateway = true
  enable_vpn_gateway = var.enable_vpn_gateway
  enable_dns_hostnames = true
  enable_dns_support = true
  
  # Flow logs for security monitoring
  enable_flow_logs = true
  flow_logs_destination = "cloudwatch"
  
  tags = local.common_tags
}

# EKS Cluster Module - Kubernetes infrastructure
module "eks_cluster" {
  source = "./modules/eks"

  project_name     = local.project_name
  environment     = local.environment
  cluster_version = var.kubernetes_version
  
  # Network configuration
  vpc_id          = module.networking.vpc_id
  subnet_ids      = module.networking.private_subnet_ids
  control_plane_subnet_ids = module.networking.public_subnet_ids
  
  # Node groups configuration
  node_groups = {
    general = {
      instance_types = [local.config.instance_sizes.medium]
      min_capacity   = local.config.min_capacity
      max_capacity   = local.config.max_capacity
      desired_capacity = local.config.desired_capacity
      
      # Taints and labels for general workloads
      labels = {
        role = "general"
        environment = local.environment
      }
    }
    
    compute_intensive = {
      instance_types = [local.config.instance_sizes.large]
      min_capacity   = 1
      max_capacity   = 5
      desired_capacity = 2
      
      # For data processing workloads
      labels = {
        role = "compute"
        workload = "data-processing"
      }
      
      taints = [{
        key    = "workload"
        value  = "compute-intensive"
        effect = "NO_SCHEDULE"
      }]
    }
    
    monitoring = {
      instance_types = [local.config.instance_sizes.small]
      min_capacity   = 1
      max_capacity   = 3
      desired_capacity = 2
      
      # Dedicated nodes for monitoring stack
      labels = {
        role = "monitoring"
        environment = local.environment
      }
      
      taints = [{
        key    = "workload"
        value  = "monitoring"
        effect = "NO_SCHEDULE"
      }]
    }
  }
  
  # Security configuration
  enable_cluster_encryption = true
  cluster_encryption_resources = ["secrets"]
  
  # Logging configuration
  cluster_enabled_log_types = [
    "api", "audit", "authenticator", "controllerManager", "scheduler"
  ]
  
  # IRSA (IAM Roles for Service Accounts)
  enable_irsa = true
  
  tags = local.common_tags
}

# RDS Module - Managed PostgreSQL databases
module "databases" {
  source = "./modules/rds"

  project_name = local.project_name
  environment = local.environment
  
  # Network configuration
  vpc_id = module.networking.vpc_id
  subnet_ids = module.networking.database_subnet_ids
  
  # Database configurations for each service
  databases = {
    # Main application database
    oms_db = {
      identifier = "${local.project_name}-oms-${local.environment}"
      engine_version = "16.1"
      instance_class = "db.t3.medium"
      allocated_storage = 100
      max_allocated_storage = 1000
      storage_encrypted = true
      
      database_name = "oms_db"
      master_username = "oms_admin"
      
      backup_retention_period = local.config.backup_retention_days
      backup_window = "03:00-04:00"
      maintenance_window = "sun:04:00-sun:05:00"
      
      deletion_protection = local.config.enable_deletion_protection
      
      monitoring_interval = 60
      performance_insights_enabled = true
      
      # Multi-AZ for production
      multi_az = local.environment == "production"
    }
    
    # User service database
    user_db = {
      identifier = "${local.project_name}-user-${local.environment}"
      engine_version = "16.1"
      instance_class = "db.t3.small"
      allocated_storage = 50
      max_allocated_storage = 200
      storage_encrypted = true
      
      database_name = "user_service_db"
      master_username = "user_admin"
      
      backup_retention_period = local.config.backup_retention_days
      backup_window = "03:00-04:00"
      maintenance_window = "sun:04:00-sun:05:00"
      
      deletion_protection = local.config.enable_deletion_protection
      
      monitoring_interval = 60
      performance_insights_enabled = true
      
      multi_az = local.environment == "production"
    }
    
    # Audit service database
    audit_db = {
      identifier = "${local.project_name}-audit-${local.environment}"
      engine_version = "16.1"
      instance_class = "db.t3.small"
      allocated_storage = 100
      max_allocated_storage = 500
      storage_encrypted = true
      
      database_name = "audit_db"
      master_username = "audit_admin"
      
      backup_retention_period = local.config.backup_retention_days
      backup_window = "03:00-04:00"
      maintenance_window = "sun:04:00-sun:05:00"
      
      deletion_protection = local.config.enable_deletion_protection
      
      monitoring_interval = 60
      performance_insights_enabled = true
      
      multi_az = local.environment == "production"
    }
    
    # Scheduler service database
    scheduler_db = {
      identifier = "${local.project_name}-scheduler-${local.environment}"
      engine_version = "16.1"
      instance_class = "db.t3.small"
      allocated_storage = 50
      max_allocated_storage = 200
      storage_encrypted = true
      
      database_name = "scheduler_db"
      master_username = "scheduler_admin"
      
      backup_retention_period = local.config.backup_retention_days
      backup_window = "03:00-04:00"
      maintenance_window = "sun:04:00-sun:05:00"
      
      deletion_protection = local.config.enable_deletion_protection
      
      monitoring_interval = 60
      performance_insights_enabled = true
      
      multi_az = local.environment == "production"
    }
  }
  
  tags = local.common_tags
}

# ElastiCache Module - Redis cluster
module "redis" {
  source = "./modules/elasticache"

  project_name = local.project_name
  environment = local.environment
  
  # Network configuration
  vpc_id = module.networking.vpc_id
  subnet_ids = module.networking.private_subnet_ids
  
  # Redis cluster configuration
  clusters = {
    main = {
      cluster_id = "${local.project_name}-redis-${local.environment}"
      node_type = "cache.t3.micro"
      num_cache_nodes = local.environment == "production" ? 3 : 1
      
      engine_version = "7.0"
      port = 6379
      
      # Security
      at_rest_encryption_enabled = true
      transit_encryption_enabled = true
      auth_token_enabled = true
      
      # Backup
      snapshot_retention_limit = local.config.backup_retention_days
      snapshot_window = "03:00-05:00"
      
      # Maintenance
      maintenance_window = "sun:05:00-sun:06:00"
      
      # Monitoring
      notification_topic_arn = module.monitoring.sns_topic_arn
    }
  }
  
  tags = local.common_tags
}

# NATS Module - Message broker infrastructure
module "nats" {
  source = "./modules/nats"

  project_name = local.project_name
  environment = local.environment
  
  # Kubernetes configuration
  namespace = "nats-system"
  
  # Cluster configuration
  cluster_size = local.environment == "production" ? 3 : 1
  
  # JetStream configuration
  jetstream_enabled = true
  jetstream_max_memory = "1Gi"
  jetstream_max_storage = "10Gi"
  
  # Monitoring
  monitoring_enabled = true
  prometheus_operator_enabled = true
  
  # Security
  tls_enabled = true
  auth_enabled = true
  
  depends_on = [module.eks_cluster]
  
  tags = local.common_tags
}

# Monitoring Module - Prometheus, Grafana, Jaeger
module "monitoring" {
  source = "./modules/monitoring"

  project_name = local.project_name
  environment = local.environment
  
  # Kubernetes configuration
  namespace = "monitoring"
  
  # Prometheus configuration
  prometheus = {
    enabled = true
    retention = "${local.config.log_retention_days}d"
    storage_class = "gp3"
    storage_size = "100Gi"
    
    # High availability for production
    replicas = local.environment == "production" ? 2 : 1
    
    # Resource requests/limits
    resources = {
      requests = {
        memory = "2Gi"
        cpu = "1000m"
      }
      limits = {
        memory = "4Gi"
        cpu = "2000m"
      }
    }
  }
  
  # Grafana configuration
  grafana = {
    enabled = true
    admin_password = var.grafana_admin_password
    
    # Persistence
    persistence_enabled = true
    storage_class = "gp3"
    storage_size = "10Gi"
    
    # OIDC/OAuth integration
    oauth_enabled = var.grafana_oauth_enabled
    oauth_client_id = var.grafana_oauth_client_id
    oauth_client_secret = var.grafana_oauth_client_secret
    
    # Resources
    resources = {
      requests = {
        memory = "256Mi"
        cpu = "250m"
      }
      limits = {
        memory = "512Mi"
        cpu = "500m"
      }
    }
  }
  
  # Jaeger configuration
  jaeger = {
    enabled = true
    strategy = "production" # vs "allInOne" for dev
    
    # Elasticsearch backend for production
    elasticsearch_enabled = true
    elasticsearch_storage_class = "gp3"
    elasticsearch_storage_size = "100Gi"
    
    # Resources
    collector_resources = {
      requests = {
        memory = "512Mi"
        cpu = "500m"
      }
      limits = {
        memory = "1Gi"
        cpu = "1000m"
      }
    }
  }
  
  # AlertManager configuration
  alertmanager = {
    enabled = true
    config = file("${path.module}/configs/alertmanager.yml")
    
    # High availability
    replicas = local.environment == "production" ? 3 : 1
    
    # Persistence
    storage_class = "gp3"
    storage_size = "10Gi"
    
    # Resources
    resources = {
      requests = {
        memory = "256Mi"
        cpu = "250m"
      }
      limits = {
        memory = "512Mi"
        cpu = "500m"
      }
    }
  }
  
  depends_on = [module.eks_cluster]
  
  tags = local.common_tags
}

# Application Module - Arrakis microservices deployment
module "arrakis_services" {
  source = "./modules/arrakis-services"

  project_name = local.project_name
  environment = local.environment
  
  # Kubernetes configuration
  namespace = "arrakis"
  
  # Image configuration
  image_registry = var.image_registry
  image_tag = var.image_tag
  
  # Database connections
  database_endpoints = {
    oms_db       = module.databases.database_endpoints["oms_db"]
    user_db      = module.databases.database_endpoints["user_db"]
    audit_db     = module.databases.database_endpoints["audit_db"]
    scheduler_db = module.databases.database_endpoints["scheduler_db"]
  }
  
  # Redis connection
  redis_endpoint = module.redis.primary_endpoint
  redis_auth_token = module.redis.auth_token
  
  # NATS connection
  nats_endpoint = module.nats.cluster_endpoint
  
  # Service configurations
  services = {
    ontology_management_service = {
      replicas = local.environment == "production" ? 3 : 2
      resources = {
        requests = {
          memory = "1Gi"
          cpu = "500m"
        }
        limits = {
          memory = "2Gi"
          cpu = "1000m"
        }
      }
      autoscaling = {
        enabled = true
        min_replicas = local.config.min_capacity
        max_replicas = local.config.max_capacity
        target_cpu_utilization = 70
        target_memory_utilization = 80
      }
    }
    
    user_service = {
      replicas = local.environment == "production" ? 2 : 1
      resources = {
        requests = {
          memory = "512Mi"
          cpu = "250m"
        }
        limits = {
          memory = "1Gi"
          cpu = "500m"
        }
      }
      autoscaling = {
        enabled = true
        min_replicas = 1
        max_replicas = 5
        target_cpu_utilization = 70
        target_memory_utilization = 80
      }
    }
    
    audit_service = {
      replicas = local.environment == "production" ? 2 : 1
      resources = {
        requests = {
          memory = "512Mi"
          cpu = "250m"
        }
        limits = {
          memory = "1Gi"
          cpu = "500m"
        }
      }
      autoscaling = {
        enabled = true
        min_replicas = 1
        max_replicas = 5
        target_cpu_utilization = 70
        target_memory_utilization = 80
      }
    }
    
    data_kernel_service = {
      replicas = local.environment == "production" ? 2 : 1
      resources = {
        requests = {
          memory = "1Gi"
          cpu = "500m"
        }
        limits = {
          memory = "2Gi"
          cpu = "1000m"
        }
      }
      node_selector = {
        role = "compute"
      }
      tolerations = [{
        key = "workload"
        value = "compute-intensive"
        effect = "NoSchedule"
      }]
    }
    
    embedding_service = {
      replicas = local.environment == "production" ? 2 : 1
      resources = {
        requests = {
          memory = "2Gi"
          cpu = "1000m"
        }
        limits = {
          memory = "4Gi"
          cpu = "2000m"
        }
      }
      node_selector = {
        role = "compute"
      }
      tolerations = [{
        key = "workload"
        value = "compute-intensive"
        effect = "NoSchedule"
      }]
    }
    
    scheduler_service = {
      replicas = local.environment == "production" ? 2 : 1
      resources = {
        requests = {
          memory = "512Mi"
          cpu = "250m"
        }
        limits = {
          memory = "1Gi"
          cpu = "500m"
        }
      }
    }
    
    event_gateway = {
      replicas = local.environment == "production" ? 2 : 1
      resources = {
        requests = {
          memory = "512Mi"
          cpu = "250m"
        }
        limits = {
          memory = "1Gi"
          cpu = "500m"
        }
      }
    }
  }
  
  # Ingress configuration
  ingress = {
    enabled = true
    class_name = "nginx"
    host = var.domain_name
    tls_enabled = true
    cert_manager_cluster_issuer = "letsencrypt-prod"
  }
  
  depends_on = [
    module.eks_cluster,
    module.databases,
    module.redis,
    module.nats
  ]
  
  tags = local.common_tags
}

# Security Module - IAM, Secrets, Policies
module "security" {
  source = "./modules/security"

  project_name = local.project_name
  environment = local.environment
  
  # EKS cluster information
  cluster_name = module.eks_cluster.cluster_name
  cluster_oidc_issuer_url = module.eks_cluster.cluster_oidc_issuer_url
  
  # Service account configurations
  service_accounts = {
    oms_service = {
      namespace = "arrakis"
      policies = [
        "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",
        "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
      ]
    }
    
    audit_service = {
      namespace = "arrakis"
      policies = [
        "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
        "arn:aws:iam::aws:policy/AmazonS3FullAccess"
      ]
    }
    
    monitoring = {
      namespace = "monitoring"
      policies = [
        "arn:aws:iam::aws:policy/CloudWatchReadOnlyAccess"
      ]
    }
  }
  
  # Secrets configuration
  secrets = {
    database_credentials = {
      description = "Database credentials for Arrakis services"
      secret_data = {
        for db_name, db_config in module.databases.database_credentials :
        db_name => jsonencode(db_config)
      }
    }
    
    redis_credentials = {
      description = "Redis authentication token"
      secret_data = {
        auth_token = module.redis.auth_token
      }
    }
    
    jwt_secrets = {
      description = "JWT signing secrets"
      secret_data = {
        jwt_secret = var.jwt_secret
        encryption_key = var.encryption_key
      }
    }
  }
  
  tags = local.common_tags
}

# Backup Module - Automated backup strategies
module "backup" {
  source = "./modules/backup"

  project_name = local.project_name
  environment = local.environment
  
  # RDS backup configuration
  rds_instances = [
    for db_name, db in module.databases.database_instances :
    {
      identifier = db.identifier
      arn = db.arn
    }
  ]
  
  # EBS volumes backup (for EKS persistent volumes)
  backup_vault_name = "${local.project_name}-backup-vault-${local.environment}"
  backup_plan_name = "${local.project_name}-backup-plan-${local.environment}"
  
  # Backup schedule
  backup_schedule = local.environment == "production" ? "cron(0 2 * * ? *)" : "cron(0 3 * * ? *)"
  
  # Retention periods
  delete_after_days = local.config.backup_retention_days
  move_to_cold_storage_after_days = local.environment == "production" ? 30 : null
  
  tags = local.common_tags
}

# DNS Module - Route53 configuration
module "dns" {
  source = "./modules/dns"
  count = var.domain_name != "" ? 1 : 0

  project_name = local.project_name
  environment = local.environment
  
  domain_name = var.domain_name
  
  # Load balancer for ingress
  load_balancer_dns_name = module.arrakis_services.ingress_load_balancer_dns_name
  load_balancer_zone_id = module.arrakis_services.ingress_load_balancer_zone_id
  
  # Subdomains
  subdomains = {
    api = {
      type = "A"
      alias = true
    }
    monitoring = {
      type = "A"
      alias = true
    }
    docs = {
      type = "A"
      alias = true
    }
  }
  
  tags = local.common_tags
}