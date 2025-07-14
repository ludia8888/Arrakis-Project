# EKS Module Outputs
# Output values for use by other modules and main configuration

# Cluster Information
output "cluster_id" {
  description = "EKS cluster ID"
  value       = aws_eks_cluster.main.id
}

output "cluster_name" {
  description = "EKS cluster name"
  value       = aws_eks_cluster.main.name
}

output "cluster_arn" {
  description = "EKS cluster ARN"
  value       = aws_eks_cluster.main.arn
}

output "cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = aws_eks_cluster.main.endpoint
}

output "cluster_version" {
  description = "EKS cluster Kubernetes version"
  value       = aws_eks_cluster.main.version
}

output "cluster_platform_version" {
  description = "EKS cluster platform version"
  value       = aws_eks_cluster.main.platform_version
}

output "cluster_status" {
  description = "EKS cluster status"
  value       = aws_eks_cluster.main.status
}

output "cluster_created_at" {
  description = "EKS cluster creation timestamp"
  value       = aws_eks_cluster.main.created_at
}

# Certificate Authority
output "cluster_certificate_authority_data" {
  description = "Base64 encoded certificate data required to communicate with the cluster"
  value       = aws_eks_cluster.main.certificate_authority[0].data
  sensitive   = true
}

# OIDC Information
output "cluster_oidc_issuer_url" {
  description = "The URL on the EKS cluster for the OpenID Connect identity provider"
  value       = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

output "oidc_provider_arn" {
  description = "ARN of the OIDC provider for the EKS cluster"
  value       = var.enable_irsa ? aws_iam_openid_connect_provider.eks_oidc[0].arn : null
}

# Security Groups
output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
}

output "cluster_primary_security_group_id" {
  description = "Primary security group ID of the EKS cluster"
  value       = aws_eks_cluster.main.vpc_config[0].security_group_ids[0]
}

# Node Groups
output "node_groups" {
  description = "EKS node groups"
  value = {
    for k, v in aws_eks_node_group.main : k => {
      arn           = v.arn
      status        = v.status
      capacity_type = v.capacity_type
      instance_types = v.instance_types
      ami_type      = v.ami_type
      disk_size     = v.disk_size
      scaling_config = v.scaling_config
      labels        = v.labels
      taints        = v.taint
    }
  }
}

output "node_group_arns" {
  description = "ARNs of the EKS node groups"
  value = {
    for k, v in aws_eks_node_group.main : k => v.arn
  }
}

output "node_group_status" {
  description = "Status of the EKS node groups"
  value = {
    for k, v in aws_eks_node_group.main : k => v.status
  }
}

output "node_group_resources" {
  description = "Resources associated with the EKS node groups"
  value = {
    for k, v in aws_eks_node_group.main : k => v.resources
  }
}

# IAM Roles
output "cluster_iam_role_name" {
  description = "IAM role name associated with EKS cluster"
  value       = aws_iam_role.eks_cluster.name
}

output "cluster_iam_role_arn" {
  description = "IAM role ARN associated with EKS cluster"
  value       = aws_iam_role.eks_cluster.arn
}

output "node_groups_iam_role_name" {
  description = "IAM role name associated with EKS node groups"
  value       = aws_iam_role.eks_node_group.name
}

output "node_groups_iam_role_arn" {
  description = "IAM role ARN associated with EKS node groups"
  value       = aws_iam_role.eks_node_group.arn
}

# IRSA IAM Roles
output "vpc_cni_iam_role_arn" {
  description = "IAM role ARN for VPC CNI IRSA"
  value       = var.enable_irsa ? aws_iam_role.vpc_cni[0].arn : null
}

output "ebs_csi_driver_iam_role_arn" {
  description = "IAM role ARN for EBS CSI driver IRSA"
  value       = var.enable_irsa ? aws_iam_role.ebs_csi_driver[0].arn : null
}

# Add-ons
output "cluster_addons" {
  description = "Map of cluster add-ons"
  value = {
    vpc_cni = {
      arn     = aws_eks_addon.vpc_cni.arn
      status  = aws_eks_addon.vpc_cni.status
      version = aws_eks_addon.vpc_cni.addon_version
    }
    coredns = {
      arn     = aws_eks_addon.coredns.arn
      status  = aws_eks_addon.coredns.status
      version = aws_eks_addon.coredns.addon_version
    }
    kube_proxy = {
      arn     = aws_eks_addon.kube_proxy.arn
      status  = aws_eks_addon.kube_proxy.status
      version = aws_eks_addon.kube_proxy.addon_version
    }
    ebs_csi_driver = {
      arn     = aws_eks_addon.ebs_csi_driver.arn
      status  = aws_eks_addon.ebs_csi_driver.status
      version = aws_eks_addon.ebs_csi_driver.addon_version
    }
  }
}

# KMS Key
output "cluster_encryption_key_arn" {
  description = "ARN of the KMS key used for cluster encryption"
  value       = aws_kms_key.eks.arn
}

output "cluster_encryption_key_id" {
  description = "ID of the KMS key used for cluster encryption"
  value       = aws_kms_key.eks.key_id
}

# CloudWatch Log Group
output "cluster_cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group for cluster logs"
  value       = aws_cloudwatch_log_group.eks_cluster.name
}

output "cluster_cloudwatch_log_group_arn" {
  description = "ARN of the CloudWatch log group for cluster logs"
  value       = aws_cloudwatch_log_group.eks_cluster.arn
}

# Launch Templates
output "launch_template_ids" {
  description = "IDs of the launch templates"
  value = {
    for k, v in aws_launch_template.eks_node_group : k => v.id
  }
}

output "launch_template_arns" {
  description = "ARNs of the launch templates"
  value = {
    for k, v in aws_launch_template.eks_node_group : k => v.arn
  }
}

output "launch_template_latest_versions" {
  description = "Latest versions of the launch templates"
  value = {
    for k, v in aws_launch_template.eks_node_group : k => v.latest_version
  }
}

# Network Configuration
output "cluster_vpc_config" {
  description = "VPC configuration of the EKS cluster"
  value = {
    vpc_id                   = aws_eks_cluster.main.vpc_config[0].vpc_id
    subnet_ids               = aws_eks_cluster.main.vpc_config[0].subnet_ids
    security_group_ids       = aws_eks_cluster.main.vpc_config[0].security_group_ids
    endpoint_private_access  = aws_eks_cluster.main.vpc_config[0].endpoint_private_access
    endpoint_public_access   = aws_eks_cluster.main.vpc_config[0].endpoint_public_access
    public_access_cidrs      = aws_eks_cluster.main.vpc_config[0].public_access_cidrs
  }
}

output "cluster_kubernetes_network_config" {
  description = "Kubernetes network configuration of the EKS cluster"
  value = {
    service_ipv4_cidr = aws_eks_cluster.main.kubernetes_network_config[0].service_ipv4_cidr
    ip_family         = aws_eks_cluster.main.kubernetes_network_config[0].ip_family
  }
}

# Cluster Tags
output "cluster_tags" {
  description = "Tags applied to the EKS cluster"
  value       = aws_eks_cluster.main.tags
}

# Connection Information
output "cluster_connection_info" {
  description = "Connection information for the EKS cluster"
  value = {
    cluster_name             = aws_eks_cluster.main.name
    cluster_endpoint         = aws_eks_cluster.main.endpoint
    cluster_version          = aws_eks_cluster.main.version
    cluster_arn              = aws_eks_cluster.main.arn
    cluster_security_group_id = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
    oidc_issuer_url          = aws_eks_cluster.main.identity[0].oidc[0].issuer
    vpc_id                   = aws_eks_cluster.main.vpc_config[0].vpc_id
  }
}

# Kubeconfig Information
output "kubeconfig_command" {
  description = "Command to update kubeconfig for the EKS cluster"
  value       = "aws eks update-kubeconfig --region ${data.aws_region.current.name} --name ${aws_eks_cluster.main.name}"
}

output "kubeconfig_context" {
  description = "Kubectl context name for the EKS cluster"
  value       = "arn:aws:eks:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:cluster/${aws_eks_cluster.main.name}"
}

# Monitoring Information
output "cluster_monitoring_config" {
  description = "Monitoring configuration for the EKS cluster"
  value = {
    enabled_log_types           = aws_eks_cluster.main.enabled_cluster_log_types
    cloudwatch_log_group_name   = aws_cloudwatch_log_group.eks_cluster.name
    container_insights_enabled  = var.enable_container_insights
    prometheus_metrics_enabled  = var.enable_prometheus_metrics
    fluent_bit_enabled          = var.enable_fluent_bit
  }
}

# Security Information
output "cluster_security_config" {
  description = "Security configuration for the EKS cluster"
  value = {
    cluster_encryption_enabled = var.enable_cluster_encryption
    encryption_resources       = var.cluster_encryption_resources
    kms_key_arn                = aws_kms_key.eks.arn
    irsa_enabled               = var.enable_irsa
    oidc_provider_arn          = var.enable_irsa ? aws_iam_openid_connect_provider.eks_oidc[0].arn : null
    pod_security_policy_enabled = var.enable_pod_security_policy
    network_policy_enabled      = var.enable_network_policy
    secrets_encryption_enabled  = var.enable_secrets_encryption
  }
}

# Cost Information
output "cluster_cost_information" {
  description = "Cost-related information for the EKS cluster"
  value = {
    cluster_cost_per_hour        = "$0.10"
    estimated_node_cost_per_hour = "Variable based on instance types"
    cost_optimization_enabled    = var.enable_cost_optimization
    spot_instances_enabled       = var.enable_spot_instances
    spot_instance_percentage     = var.spot_instance_percentage
    right_sizing_enabled         = var.enable_right_sizing
  }
}

# Performance Information
output "cluster_performance_config" {
  description = "Performance configuration for the EKS cluster"
  value = {
    enhanced_networking_enabled = var.enable_enhanced_networking
    max_pods_per_node          = var.max_pods_per_node
    network_performance_monitoring = var.enable_network_performance_monitoring
    dns_caching_enabled        = var.enable_dns_caching
    ebs_optimization_enabled   = var.enable_ebs_optimization
  }
}

# Compliance Information
output "cluster_compliance_config" {
  description = "Compliance configuration for the EKS cluster"
  value = {
    compliance_scanning_enabled = var.enable_compliance_scanning
    compliance_standards       = var.compliance_standards
    backup_enabled             = var.enable_backup_tags
    cross_region_backup        = var.enable_cross_region_backup
  }
}

# Maintenance Information
output "cluster_maintenance_config" {
  description = "Maintenance configuration for the EKS cluster"
  value = {
    maintenance_window      = var.maintenance_window
    automatic_upgrades      = var.enable_automatic_upgrades
    upgrade_policy          = var.upgrade_policy
    backup_retention_days   = var.backup_retention_days
  }
}

# Deployment Information
output "deployment_info" {
  description = "Deployment information and next steps"
  value = {
    cluster_ready          = aws_eks_cluster.main.status == "ACTIVE"
    node_groups_ready      = [for k, v in aws_eks_node_group.main : v.status == "ACTIVE"]
    deployment_region      = data.aws_region.current.name
    deployment_account     = data.aws_caller_identity.current.account_id
    cluster_creation_time  = aws_eks_cluster.main.created_at
    recommended_next_steps = [
      "Update kubeconfig: aws eks update-kubeconfig --region ${data.aws_region.current.name} --name ${aws_eks_cluster.main.name}",
      "Verify cluster: kubectl get nodes",
      "Deploy AWS Load Balancer Controller: kubectl apply -f https://github.com/kubernetes-sigs/aws-load-balancer-controller/releases/download/v${var.load_balancer_controller_version}/v${var.load_balancer_controller_version}_full.yaml",
      "Configure monitoring: kubectl apply -f https://github.com/aws-samples/amazon-cloudwatch-container-insights/releases/latest/download/cwagent-fluentd-quickstart.yaml",
      "Deploy applications: kubectl apply -f your-application-manifests/",
      "Set up ingress: kubectl apply -f ingress-configuration.yaml"
    ]
  }
}

# Health Check URLs
output "health_check_endpoints" {
  description = "Health check endpoints for the EKS cluster"
  value = {
    cluster_health = "${aws_eks_cluster.main.endpoint}/healthz"
    metrics        = "${aws_eks_cluster.main.endpoint}/metrics"
    version        = "${aws_eks_cluster.main.endpoint}/version"
  }
}

# Summary Information
output "cluster_summary" {
  description = "Summary of the EKS cluster configuration"
  value = {
    cluster_name       = aws_eks_cluster.main.name
    cluster_version    = aws_eks_cluster.main.version
    cluster_endpoint   = aws_eks_cluster.main.endpoint
    cluster_arn        = aws_eks_cluster.main.arn
    cluster_status     = aws_eks_cluster.main.status
    node_groups_count  = length(aws_eks_node_group.main)
    total_nodes_desired = sum([for ng in aws_eks_node_group.main : ng.scaling_config[0].desired_size])
    addons_enabled     = length(aws_eks_cluster.main.enabled_cluster_log_types)
    encryption_enabled = var.enable_cluster_encryption
    irsa_enabled       = var.enable_irsa
    monitoring_enabled = var.enable_container_insights
    vpc_id            = aws_eks_cluster.main.vpc_config[0].vpc_id
    subnets           = aws_eks_cluster.main.vpc_config[0].subnet_ids
    security_groups   = aws_eks_cluster.main.vpc_config[0].security_group_ids
  }
}