# Arrakis Platform Infrastructure

Production-ready Infrastructure as Code for the Arrakis microservices platform using Terraform.

## 🏗️ Architecture Overview

This Terraform configuration deploys a comprehensive, production-ready infrastructure for the Arrakis platform including:

- **Amazon EKS** - Managed Kubernetes cluster with multiple node groups
- **Amazon RDS** - PostgreSQL databases for each microservice
- **Amazon ElastiCache** - Redis clusters for caching and session management
- **Amazon VPC** - Secure network isolation with public/private subnets
- **AWS Application Load Balancer** - Traffic distribution and SSL termination
- **AWS Secrets Manager** - Secure credential management
- **AWS KMS** - Encryption at rest and in transit
- **AWS Backup** - Automated backup strategies
- **CloudWatch** - Comprehensive monitoring and alerting
- **Route53** - DNS management (optional)

## 📋 Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform >= 1.6.0
- kubectl (for Kubernetes management)
- Helm (for application deployment)

## 🚀 Quick Start

1. **Clone the repository and navigate to the Terraform directory:**
   ```bash
   cd terraform
   ```

2. **Copy the example variables file:**
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   ```

3. **Edit the variables file with your specific configuration:**
   ```bash
   vim terraform.tfvars
   ```

4. **Initialize Terraform:**
   ```bash
   terraform init
   ```

5. **Plan the deployment:**
   ```bash
   terraform plan
   ```

6. **Apply the configuration:**
   ```bash
   terraform apply
   ```

7. **Configure kubectl to connect to your EKS cluster:**
   ```bash
   aws eks update-kubeconfig --region <your-region> --name arrakis-eks-<environment>
   ```

## 📁 Directory Structure

```
terraform/
├── main.tf                    # Main Terraform configuration
├── variables.tf               # Input variables
├── outputs.tf                 # Output values
├── terraform.tfvars.example   # Example configuration
├── README.md                  # This file
└── modules/
    ├── networking/            # VPC, subnets, security groups
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── eks/                   # EKS cluster and node groups
    │   ├── main.tf
    │   ├── variables.tf
    │   ├── outputs.tf
    │   └── user_data.sh
    ├── rds/                   # PostgreSQL databases
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── elasticache/           # Redis clusters
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    └── [other modules...]
```

## 🔧 Configuration

### Environment Variables

Set the following environment variables or configure them in `terraform.tfvars`:

```bash
# Core Configuration
export TF_VAR_environment="production"
export TF_VAR_aws_region="us-west-2"
export TF_VAR_project_name="arrakis"

# Domain Configuration
export TF_VAR_domain_name="arrakis.example.com"

# Security Configuration
export TF_VAR_jwt_secret="your-jwt-secret-here"
export TF_VAR_encryption_key="your-encryption-key-here"

# Database Configuration
export TF_VAR_database_master_password="your-strong-password-here"

# Monitoring Configuration
export TF_VAR_grafana_admin_password="your-grafana-password-here"
```

### Backend Configuration

Configure remote state storage by creating a backend configuration file:

```bash
# backend-config/production.hcl
bucket         = "arrakis-terraform-state-prod"
key            = "infrastructure/terraform.tfstate"
region         = "us-west-2"
encrypt        = true
dynamodb_table = "arrakis-terraform-locks"
```

Initialize with backend configuration:
```bash
terraform init -backend-config=backend-config/production.hcl
```

### Environment-Specific Configurations

#### Development Environment
```hcl
environment = "development"
kubernetes_version = "1.28"

# Smaller instance sizes for cost optimization
node_groups = {
  general = {
    instance_types = ["t3.small"]
    min_capacity = 1
    max_capacity = 3
    desired_capacity = 2
  }
}

# Single-AZ deployment for cost savings
enable_multi_az = false
backup_retention_days = 7
```

#### Staging Environment
```hcl
environment = "staging"
kubernetes_version = "1.28"

# Medium instance sizes
node_groups = {
  general = {
    instance_types = ["t3.medium"]
    min_capacity = 2
    max_capacity = 6
    desired_capacity = 3
  }
}

# Multi-AZ for testing production-like setup
enable_multi_az = true
backup_retention_days = 14
```

#### Production Environment
```hcl
environment = "production"
kubernetes_version = "1.28"

# Larger instance sizes for production workloads
node_groups = {
  general = {
    instance_types = ["t3.large"]
    min_capacity = 3
    max_capacity = 20
    desired_capacity = 6
  }
}

# Full high availability and compliance
enable_multi_az = true
backup_retention_days = 90
enable_encryption_at_rest = true
enable_encryption_in_transit = true
deletion_protection = true
```

## 🛡️ Security Features

### Network Security
- VPC with public/private subnet isolation
- Security groups with least-privilege access
- Network ACLs for additional layer of security
- VPC Flow Logs for network monitoring

### Encryption
- KMS encryption for all data at rest
- TLS encryption for all data in transit
- Secrets Manager for credential management
- Certificate Manager for SSL/TLS certificates

### Identity and Access Management
- IAM roles for service accounts (IRSA)
- Least privilege IAM policies
- Service account authentication
- Role-based access control (RBAC)

### Compliance
- SOC2 Type II compliance ready
- GDPR compliance features
- HIPAA compliance options
- Audit logging and monitoring

## 📊 Monitoring and Observability

### CloudWatch Integration
- Comprehensive metrics collection
- Custom dashboards for each service
- Automated alerting and notifications
- Log aggregation and analysis

### Prometheus and Grafana
- Kubernetes-native monitoring
- Custom metrics and dashboards
- Long-term metrics storage
- Advanced visualization

### Distributed Tracing
- Jaeger for request tracing
- Service dependency mapping
- Performance bottleneck identification
- Error tracking and debugging

## 🔄 Backup and Disaster Recovery

### Automated Backups
- RDS automated backups with point-in-time recovery
- ElastiCache snapshots
- EBS volume backups
- Cross-region backup replication

### Disaster Recovery
- Multi-AZ deployments
- Automated failover
- Backup restoration procedures
- Recovery time objectives (RTO) < 1 hour

## 📈 Scaling and Performance

### Auto Scaling
- Cluster autoscaler for Kubernetes nodes
- Horizontal pod autoscaler for applications
- Database read replicas
- Redis cluster mode support

### Performance Optimization
- Instance type recommendations
- Storage optimization
- Network performance tuning
- Caching strategies

## 💰 Cost Optimization

### Cost Control Features
- Spot instances for development
- Reserved instance recommendations
- Resource right-sizing
- Automated cost monitoring

### Cost Estimation
- Monthly cost estimates provided in outputs
- Cost breakdown by service
- Optimization recommendations
- Budget alerts and notifications

## 🔍 Troubleshooting

### Common Issues

1. **EKS Cluster Creation Fails**
   ```bash
   # Check IAM permissions
   aws sts get-caller-identity

   # Verify subnet configuration
   terraform plan -target=module.networking
   ```

2. **Database Connection Issues**
   ```bash
   # Check security groups
   aws ec2 describe-security-groups --group-ids sg-xxxxxx

   # Test database connectivity
   kubectl run -i --tty --rm debug --image=postgres:16 --restart=Never -- psql -h <endpoint> -U <username>
   ```

3. **Application Deployment Issues**
   ```bash
   # Check node readiness
   kubectl get nodes

   # Verify resource quotas
   kubectl describe resourcequota
   ```

### Debugging Commands

```bash
# Check Terraform state
terraform show

# Validate configuration
terraform validate

# Format code
terraform fmt -recursive

# Import existing resources
terraform import aws_instance.example i-1234567890abcdef0
```

## 🚀 Deployment Workflow

### CI/CD Integration

1. **GitHub Actions Workflow:**
   ```yaml
   name: Deploy Infrastructure
   on:
     push:
       branches: [main]
       paths: ['terraform/**']

   jobs:
     deploy:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v3
         - uses: hashicorp/setup-terraform@v2
         - name: Terraform Plan
           run: terraform plan
         - name: Terraform Apply
           run: terraform apply -auto-approve
   ```

2. **Pre-commit Hooks:**
   ```yaml
   repos:
     - repo: https://github.com/antonbabenko/pre-commit-terraform
       rev: v1.81.0
       hooks:
         - id: terraform_validate
         - id: terraform_fmt
         - id: terraform_tflint
   ```

### Deployment Best Practices

1. **Use workspaces for environments:**
   ```bash
   terraform workspace new production
   terraform workspace select production
   ```

2. **Plan before apply:**
   ```bash
   terraform plan -out=tfplan
   terraform apply tfplan
   ```

3. **Enable detailed logging:**
   ```bash
   export TF_LOG=DEBUG
   terraform apply
   ```

## 📚 Additional Resources

- [Terraform AWS Provider Documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Amazon EKS User Guide](https://docs.aws.amazon.com/eks/latest/userguide/)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and validation
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For support and questions:
- Create an issue in the GitHub repository
- Contact the platform team at platform-team@example.com
- Join the #arrakis-platform Slack channel

---

**Note**: This infrastructure configuration is designed for production use. Always review and test in a development environment before deploying to production.
