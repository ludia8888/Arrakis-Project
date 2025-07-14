# NATS Terraform Module

Production-ready NATS cluster deployment on Kubernetes with JetStream, high availability, security, and comprehensive monitoring.

## Features

- **High Availability**: Multi-node NATS cluster with automatic failover
- **JetStream**: Persistent messaging with at-least-once delivery guarantees
- **Security**: TLS encryption, JWT-based authentication, network policies
- **Monitoring**: Prometheus metrics, health checks, ServiceMonitor integration
- **Scalability**: Horizontal pod autoscaling and resource management
- **Backup & Recovery**: Automated backups and disaster recovery
- **Multi-Protocol**: Core NATS, WebSocket, MQTT, Leafnode, and Gateway support

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    NATS Cluster                             │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────┐  ┌───────────┐  ┌───────────┐              │
│  │  nats-0   │  │  nats-1   │  │  nats-2   │              │
│  │           │  │           │  │           │              │
│  │ JetStream │  │ JetStream │  │ JetStream │              │
│  │   Core    │  │   Core    │  │   Core    │              │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘              │
│        │              │              │                     │
│        └──────────────┼──────────────┘                     │
│                       │                                     │
├───────────────────────┼─────────────────────────────────────┤
│                   Cluster Network (6222)                   │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Client    │  │  WebSocket  │  │ Monitoring  │        │
│  │ Service     │  │  Service    │  │  Service    │        │
│  │   (4222)    │  │   (8080)    │  │   (8222)    │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

```hcl
module "nats" {
  source = "./modules/nats"

  project_name           = "arrakis"
  environment           = "production"
  cluster_endpoint      = data.aws_eks_cluster.main.endpoint
  cluster_ca_certificate = data.aws_eks_cluster.main.certificate_authority[0].data
  cluster_auth_token    = data.aws_eks_cluster_auth.main.token

  # Cluster Configuration
  cluster_size    = 3
  jetstream_enabled = true
  
  # Security
  auth_enabled = true
  tls_enabled  = true
  
  # Storage
  storage_class = "gp3"
  storage_size  = "20Gi"
  
  # Resources
  resources = {
    requests = {
      cpu    = "200m"
      memory = "512Mi"
    }
    limits = {
      cpu    = "1000m"
      memory = "2Gi"
    }
  }
}
```

## Configuration

### Basic Configuration

| Variable | Description | Type | Default | Required |
|----------|-------------|------|---------|----------|
| `project_name` | Name of the project | `string` | - | yes |
| `environment` | Environment (development, staging, production) | `string` | - | yes |
| `cluster_endpoint` | Kubernetes cluster endpoint | `string` | - | yes |
| `cluster_ca_certificate` | Kubernetes cluster CA certificate | `string` | - | yes |
| `cluster_auth_token` | Kubernetes cluster auth token | `string` | - | yes |

### Cluster Configuration

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `cluster_size` | Number of NATS server instances | `number` | `3` |
| `namespace` | Kubernetes namespace | `string` | `"nats-system"` |
| `nats_image` | NATS server image | `string` | `"nats"` |
| `nats_version` | NATS server version | `string` | `"2.10.7-alpine"` |

### JetStream Configuration

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `jetstream_enabled` | Enable JetStream | `bool` | `true` |
| `jetstream_max_memory` | Maximum memory for JetStream | `string` | `"1Gi"` |
| `jetstream_max_storage` | Maximum storage for JetStream | `string` | `"10Gi"` |
| `jetstream_storage_class` | Storage class for JetStream | `string` | `"gp3"` |

### Security Configuration

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `auth_enabled` | Enable authentication | `bool` | `true` |
| `tls_enabled` | Enable TLS encryption | `bool` | `true` |
| `enable_network_policy` | Enable NetworkPolicy | `bool` | `true` |
| `allowed_namespaces` | Allowed namespaces to connect | `list(string)` | `["default", "arrakis"]` |

### Performance Configuration

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `max_connections` | Maximum client connections | `number` | `10000` |
| `max_payload` | Maximum message payload | `string` | `"1MB"` |
| `max_pending` | Maximum pending messages | `string` | `"10MB"` |
| `write_deadline` | Write deadline for connections | `string` | `"10s"` |

### Protocol Support

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `websocket_enabled` | Enable WebSocket protocol | `bool` | `true` |
| `mqtt_enabled` | Enable MQTT protocol | `bool` | `false` |
| `leafnode_enabled` | Enable Leafnode protocol | `bool` | `false` |
| `gateway_enabled` | Enable Gateway protocol | `bool` | `false` |

### Monitoring

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `monitoring_enabled` | Enable monitoring endpoints | `bool` | `true` |
| `prometheus_port` | Prometheus metrics port | `number` | `7777` |
| `prometheus_operator_enabled` | Enable ServiceMonitor | `bool` | `true` |

### Auto Scaling

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `enable_autoscaling` | Enable HPA | `bool` | `false` |
| `min_replicas` | Minimum replicas | `number` | `3` |
| `max_replicas` | Maximum replicas | `number` | `7` |
| `target_cpu_utilization_percentage` | Target CPU for scaling | `number` | `70` |

### External Access

| Variable | Description | Type | Default |
|----------|-------------|------|---------|
| `enable_external_access` | Enable external access | `bool` | `false` |
| `service_type` | Service type for external access | `string` | `"LoadBalancer"` |
| `load_balancer_source_ranges` | Source IP ranges | `list(string)` | `["0.0.0.0/0"]` |

## Outputs

### Connection Information

| Output | Description |
|--------|-------------|
| `cluster_endpoint` | Internal NATS cluster endpoint |
| `cluster_endpoints` | List of all cluster endpoints |
| `connection_info` | Complete connection information |
| `external_endpoint` | External endpoint (if enabled) |

### Service Information

| Output | Description |
|--------|-------------|
| `namespace` | Kubernetes namespace |
| `service_name` | Main NATS service name |
| `statefulset_name` | StatefulSet name |
| `cluster_summary` | Complete cluster configuration |

### Security Information

| Output | Description |
|--------|-------------|
| `auth_enabled` | Authentication status |
| `tls_enabled` | TLS status |
| `security_summary` | Security configuration summary |

### Health Checks

| Output | Description |
|--------|-------------|
| `health_check_urls` | Health check URLs for all pods |
| `jetstream_health_check_urls` | JetStream health check URLs |

## Usage Examples

### Basic Production Deployment

```hcl
module "nats_production" {
  source = "./modules/nats"

  project_name = "arrakis"
  environment  = "production"
  
  cluster_endpoint       = var.eks_cluster_endpoint
  cluster_ca_certificate = var.eks_cluster_ca_cert
  cluster_auth_token     = var.eks_cluster_token

  # Production cluster
  cluster_size = 5
  
  # High-performance storage
  storage_class = "gp3"
  storage_size  = "100Gi"
  
  # JetStream configuration
  jetstream_enabled     = true
  jetstream_max_memory  = "4Gi"
  jetstream_max_storage = "100Gi"
  
  # Security hardening
  auth_enabled            = true
  tls_enabled             = true
  enable_network_policy   = true
  enable_audit_logging    = true
  
  # Resource allocation
  resources = {
    requests = {
      cpu    = "500m"
      memory = "1Gi"
    }
    limits = {
      cpu    = "2000m"
      memory = "4Gi"
    }
  }
  
  # Auto scaling
  enable_autoscaling = true
  min_replicas      = 3
  max_replicas      = 10
  
  # Backup and DR
  enable_backup          = true
  backup_schedule        = "0 2 * * *"
  enable_disaster_recovery = true
  
  tags = {
    Environment = "production"
    Project     = "arrakis"
    Owner       = "platform-team"
  }
}
```

### Development Environment

```hcl
module "nats_development" {
  source = "./modules/nats"

  project_name = "arrakis"
  environment  = "development"
  
  cluster_endpoint       = var.eks_cluster_endpoint
  cluster_ca_certificate = var.eks_cluster_ca_cert
  cluster_auth_token     = var.eks_cluster_token

  # Minimal cluster for development
  cluster_size = 1
  
  # Basic storage
  storage_size = "10Gi"
  
  # Reduced security for easier development
  auth_enabled          = false
  tls_enabled           = false
  enable_network_policy = false
  
  # Allow external access for testing
  enable_external_access = true
  service_type          = "LoadBalancer"
  
  # Minimal resources
  resources = {
    requests = {
      cpu    = "100m"
      memory = "256Mi"
    }
    limits = {
      cpu    = "500m"
      memory = "1Gi"
    }
  }
}
```

### Multi-Protocol Gateway

```hcl
module "nats_gateway" {
  source = "./modules/nats"

  project_name = "arrakis"
  environment  = "production"
  
  cluster_endpoint       = var.eks_cluster_endpoint
  cluster_ca_certificate = var.eks_cluster_ca_cert
  cluster_auth_token     = var.eks_cluster_token

  # Gateway configuration
  cluster_size = 3
  
  # Enable all protocols
  websocket_enabled = true
  mqtt_enabled      = true
  leafnode_enabled  = true
  gateway_enabled   = true
  
  # External access for clients
  enable_external_access = true
  service_type          = "LoadBalancer"
  
  # Security with external access
  auth_enabled = true
  tls_enabled  = true
}
```

## Operations

### Monitoring

The module sets up comprehensive monitoring:

- **Prometheus Metrics**: Exposed on port 7777
- **Health Checks**: Available at `/healthz` endpoint
- **JetStream Metrics**: Stream and consumer metrics
- **ServiceMonitor**: Automatic Prometheus discovery

### Health Checks

```bash
# Check cluster health
kubectl get pods -n nats-system

# Check individual node health
curl http://nats-0.nats.nats-system.svc.cluster.local:8222/healthz

# Check JetStream health
curl http://nats-0.nats.nats-system.svc.cluster.local:8222/healthz?js-enabled-only=true
```

### Backup and Recovery

When backup is enabled, the module creates:

- **Scheduled Backups**: Daily backups of JetStream data
- **Retention Policy**: Configurable retention period
- **Disaster Recovery**: Cross-region backup capabilities

### Scaling

```bash
# Manual scaling
kubectl scale statefulset nats -n nats-system --replicas=5

# Auto scaling (if enabled)
kubectl get hpa nats-hpa -n nats-system
```

### Security

The module implements multiple security layers:

- **TLS Encryption**: All communication encrypted
- **JWT Authentication**: Operator-based authentication
- **Network Policies**: Restricted network access
- **Pod Security**: Non-root containers with security contexts
- **RBAC**: Minimal required permissions

## Troubleshooting

### Common Issues

1. **Pods Not Starting**
   ```bash
   kubectl describe pod nats-0 -n nats-system
   kubectl logs nats-0 -n nats-system
   ```

2. **Cluster Not Forming**
   ```bash
   # Check cluster routes
   kubectl exec nats-0 -n nats-system -- nats-server --signal ldm=/var/run/nats/nats.pid
   ```

3. **JetStream Issues**
   ```bash
   # Check JetStream status
   curl http://nats-0.nats.nats-system.svc.cluster.local:8222/jsz
   ```

4. **Authentication Problems**
   ```bash
   # Check auth configuration
   kubectl get secret nats-auth -n nats-system -o yaml
   ```

### Performance Tuning

For high-throughput scenarios:

```hcl
# Increase resources
resources = {
  requests = {
    cpu    = "1000m"
    memory = "2Gi"
  }
  limits = {
    cpu    = "4000m"
    memory = "8Gi"
  }
}

# Tune performance parameters
max_connections = 50000
max_payload     = "8MB"
max_pending     = "100MB"
write_deadline  = "5s"
```

## Security Considerations

1. **TLS Certificates**: Use proper CA-signed certificates in production
2. **Authentication**: Enable JWT-based authentication for all environments
3. **Network Policies**: Restrict access to required namespaces only
4. **Secrets Management**: Use external secret management systems
5. **Regular Updates**: Keep NATS version updated for security patches

## Contributing

When contributing to this module:

1. **Testing**: Test all configurations thoroughly
2. **Documentation**: Update README for any new features
3. **Validation**: Add proper variable validation
4. **Examples**: Provide usage examples for new features

## License

This module is part of the Arrakis project and follows the project's licensing terms.

## Support

For support:

1. Check the troubleshooting section
2. Review NATS documentation: https://docs.nats.io/
3. Open an issue in the project repository
4. Contact the platform team

---

**Production Ready**: This module is designed for production use with comprehensive security, monitoring, and operational features.