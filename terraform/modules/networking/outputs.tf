# Networking Module Outputs
# Output values for use by other modules

# VPC Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  value       = aws_vpc.main.cidr_block
}

output "vpc_arn" {
  description = "ARN of the VPC"
  value       = aws_vpc.main.arn
}

output "vpc_default_security_group_id" {
  description = "Default security group ID of the VPC"
  value       = aws_vpc.main.default_security_group_id
}

output "vpc_main_route_table_id" {
  description = "Main route table ID of the VPC"
  value       = aws_vpc.main.main_route_table_id
}

output "vpc_owner_id" {
  description = "Owner ID of the VPC"
  value       = aws_vpc.main.owner_id
}

# Internet Gateway Outputs
output "internet_gateway_id" {
  description = "ID of the Internet Gateway"
  value       = aws_internet_gateway.main.id
}

output "internet_gateway_arn" {
  description = "ARN of the Internet Gateway"
  value       = aws_internet_gateway.main.arn
}

# Public Subnet Outputs
output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = aws_subnet.public[*].id
}

output "public_subnet_arns" {
  description = "List of public subnet ARNs"
  value       = aws_subnet.public[*].arn
}

output "public_subnet_cidr_blocks" {
  description = "List of public subnet CIDR blocks"
  value       = aws_subnet.public[*].cidr_block
}

output "public_subnet_availability_zones" {
  description = "List of public subnet availability zones"
  value       = aws_subnet.public[*].availability_zone
}

# Private Subnet Outputs
output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = aws_subnet.private[*].id
}

output "private_subnet_arns" {
  description = "List of private subnet ARNs"
  value       = aws_subnet.private[*].arn
}

output "private_subnet_cidr_blocks" {
  description = "List of private subnet CIDR blocks"
  value       = aws_subnet.private[*].cidr_block
}

output "private_subnet_availability_zones" {
  description = "List of private subnet availability zones"
  value       = aws_subnet.private[*].availability_zone
}

# Database Subnet Outputs
output "database_subnet_ids" {
  description = "List of database subnet IDs"
  value       = aws_subnet.database[*].id
}

output "database_subnet_arns" {
  description = "List of database subnet ARNs"
  value       = aws_subnet.database[*].arn
}

output "database_subnet_cidr_blocks" {
  description = "List of database subnet CIDR blocks"
  value       = aws_subnet.database[*].cidr_block
}

output "database_subnet_availability_zones" {
  description = "List of database subnet availability zones"
  value       = aws_subnet.database[*].availability_zone
}

output "database_subnet_group_id" {
  description = "ID of the database subnet group"
  value       = aws_db_subnet_group.main.id
}

output "database_subnet_group_name" {
  description = "Name of the database subnet group"
  value       = aws_db_subnet_group.main.name
}

output "database_subnet_group_arn" {
  description = "ARN of the database subnet group"
  value       = aws_db_subnet_group.main.arn
}

# ElastiCache Subnet Group Outputs
output "elasticache_subnet_group_id" {
  description = "ID of the ElastiCache subnet group"
  value       = aws_elasticache_subnet_group.main.id
}

output "elasticache_subnet_group_name" {
  description = "Name of the ElastiCache subnet group"
  value       = aws_elasticache_subnet_group.main.name
}

# NAT Gateway Outputs
output "nat_gateway_ids" {
  description = "List of NAT Gateway IDs"
  value       = aws_nat_gateway.main[*].id
}

output "nat_gateway_public_ips" {
  description = "List of NAT Gateway public IPs"
  value       = aws_nat_gateway.main[*].public_ip
}

output "nat_gateway_private_ips" {
  description = "List of NAT Gateway private IPs"
  value       = aws_nat_gateway.main[*].private_ip
}

# Elastic IP Outputs
output "nat_eip_ids" {
  description = "List of NAT Gateway Elastic IP IDs"
  value       = aws_eip.nat[*].id
}

output "nat_eip_public_ips" {
  description = "List of NAT Gateway Elastic IP public IPs"
  value       = aws_eip.nat[*].public_ip
}

# Route Table Outputs
output "public_route_table_id" {
  description = "ID of the public route table"
  value       = aws_route_table.public.id
}

output "private_route_table_ids" {
  description = "List of private route table IDs"
  value       = aws_route_table.private[*].id
}

output "database_route_table_id" {
  description = "ID of the database route table"
  value       = aws_route_table.database.id
}

# Security Group Outputs
output "eks_cluster_security_group_id" {
  description = "ID of the EKS cluster security group"
  value       = aws_security_group.eks_cluster.id
}

output "eks_cluster_security_group_arn" {
  description = "ARN of the EKS cluster security group"
  value       = aws_security_group.eks_cluster.arn
}

output "eks_nodes_security_group_id" {
  description = "ID of the EKS nodes security group"
  value       = aws_security_group.eks_nodes.id
}

output "eks_nodes_security_group_arn" {
  description = "ARN of the EKS nodes security group"
  value       = aws_security_group.eks_nodes.arn
}

output "rds_security_group_id" {
  description = "ID of the RDS security group"
  value       = aws_security_group.rds.id
}

output "rds_security_group_arn" {
  description = "ARN of the RDS security group"
  value       = aws_security_group.rds.arn
}

output "redis_security_group_id" {
  description = "ID of the Redis security group"
  value       = aws_security_group.redis.id
}

output "redis_security_group_arn" {
  description = "ARN of the Redis security group"
  value       = aws_security_group.redis.arn
}

output "load_balancer_security_group_id" {
  description = "ID of the load balancer security group"
  value       = aws_security_group.load_balancer.id
}

output "load_balancer_security_group_arn" {
  description = "ARN of the load balancer security group"
  value       = aws_security_group.load_balancer.arn
}

output "vpc_endpoints_security_group_id" {
  description = "ID of the VPC endpoints security group"
  value       = aws_security_group.vpc_endpoints.id
}

output "vpc_endpoints_security_group_arn" {
  description = "ARN of the VPC endpoints security group"
  value       = aws_security_group.vpc_endpoints.arn
}

# VPC Endpoint Outputs
output "s3_vpc_endpoint_id" {
  description = "ID of the S3 VPC endpoint"
  value       = aws_vpc_endpoint.s3.id
}

output "ecr_api_vpc_endpoint_id" {
  description = "ID of the ECR API VPC endpoint"
  value       = aws_vpc_endpoint.ecr_api.id
}

output "ecr_dkr_vpc_endpoint_id" {
  description = "ID of the ECR DKR VPC endpoint"
  value       = aws_vpc_endpoint.ecr_dkr.id
}

# Flow Logs Outputs
output "flow_log_id" {
  description = "ID of the VPC Flow Log"
  value       = var.enable_flow_logs ? aws_flow_log.main[0].id : null
}

output "flow_log_arn" {
  description = "ARN of the VPC Flow Log"
  value       = var.enable_flow_logs ? aws_flow_log.main[0].arn : null
}

output "flow_log_cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group for VPC Flow Logs"
  value       = var.enable_flow_logs ? aws_cloudwatch_log_group.flow_logs[0].name : null
}

output "flow_log_cloudwatch_log_group_arn" {
  description = "ARN of the CloudWatch log group for VPC Flow Logs"
  value       = var.enable_flow_logs ? aws_cloudwatch_log_group.flow_logs[0].arn : null
}

# VPN Gateway Outputs
output "vpn_gateway_id" {
  description = "ID of the VPN Gateway"
  value       = var.enable_vpn_gateway ? aws_vpn_gateway.main[0].id : null
}

output "vpn_gateway_arn" {
  description = "ARN of the VPN Gateway"
  value       = var.enable_vpn_gateway ? aws_vpn_gateway.main[0].arn : null
}

# Availability Zones Output
output "availability_zones" {
  description = "List of availability zones used"
  value       = var.availability_zones
}

# Network Configuration Summary
output "network_configuration" {
  description = "Summary of network configuration"
  value = {
    vpc_id                = aws_vpc.main.id
    vpc_cidr              = aws_vpc.main.cidr_block
    public_subnets        = aws_subnet.public[*].id
    private_subnets       = aws_subnet.private[*].id
    database_subnets      = aws_subnet.database[*].id
    availability_zones    = var.availability_zones
    nat_gateway_enabled   = var.enable_nat_gateway
    vpn_gateway_enabled   = var.enable_vpn_gateway
    flow_logs_enabled     = var.enable_flow_logs
    internet_gateway_id   = aws_internet_gateway.main.id
    nat_gateway_count     = length(aws_nat_gateway.main)
  }
}

# Security Configuration Summary
output "security_configuration" {
  description = "Summary of security configuration"
  value = {
    security_groups = {
      eks_cluster    = aws_security_group.eks_cluster.id
      eks_nodes      = aws_security_group.eks_nodes.id
      rds            = aws_security_group.rds.id
      redis          = aws_security_group.redis.id
      load_balancer  = aws_security_group.load_balancer.id
      vpc_endpoints  = aws_security_group.vpc_endpoints.id
    }
    vpc_endpoints = {
      s3      = aws_vpc_endpoint.s3.id
      ecr_api = aws_vpc_endpoint.ecr_api.id
      ecr_dkr = aws_vpc_endpoint.ecr_dkr.id
    }
  }
}

# Cost Optimization Information
output "cost_optimization" {
  description = "Cost optimization information"
  value = {
    nat_gateway_count        = length(aws_nat_gateway.main)
    single_nat_gateway       = var.single_nat_gateway
    vpc_endpoints_enabled    = var.enable_vpc_endpoints
    flow_logs_enabled        = var.enable_flow_logs
    estimated_monthly_cost   = "Variable based on usage"
    cost_optimization_enabled = var.enable_cost_optimization
  }
}

# Monitoring Information
output "monitoring_configuration" {
  description = "Monitoring configuration information"
  value = {
    flow_logs_enabled           = var.enable_flow_logs
    enhanced_monitoring_enabled = var.enable_enhanced_monitoring
    performance_monitoring      = var.enable_performance_monitoring
    compliance_logging          = var.enable_compliance_logging
    monitoring_interval         = var.monitoring_interval
  }
}

# Compliance Information
output "compliance_information" {
  description = "Compliance configuration information"
  value = {
    compliance_standards    = var.compliance_standards
    compliance_logging      = var.enable_compliance_logging
    backup_tags_enabled     = var.enable_backup_tags
    cross_region_backup     = var.enable_cross_region_backup
    network_segmentation    = var.enable_network_segmentation
  }
}
