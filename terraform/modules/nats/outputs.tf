# NATS Module Outputs
# Output values for use by other modules and main configuration

# Cluster Information
output "cluster_name" {
  description = "Name of the NATS cluster"
  value       = "${var.project_name}-nats-${var.environment}"
}

output "cluster_size" {
  description = "Number of NATS instances in the cluster"
  value       = var.cluster_size
}

output "namespace" {
  description = "Kubernetes namespace where NATS is deployed"
  value       = kubernetes_namespace.nats.metadata[0].name
}

# Service Endpoints
output "cluster_endpoint" {
  description = "NATS cluster endpoint for internal connections"
  value       = "nats://nats.${kubernetes_namespace.nats.metadata[0].name}.svc.cluster.local:4222"
}

output "cluster_endpoints" {
  description = "List of all NATS cluster endpoints"
  value = [
    for i in range(var.cluster_size) : 
    "nats://nats-${i}.nats.${kubernetes_namespace.nats.metadata[0].name}.svc.cluster.local:4222"
  ]
}

output "monitoring_endpoint" {
  description = "NATS monitoring endpoint"
  value       = "http://nats.${kubernetes_namespace.nats.metadata[0].name}.svc.cluster.local:8222"
}

output "websocket_endpoint" {
  description = "NATS WebSocket endpoint"
  value       = var.websocket_enabled ? "ws://nats.${kubernetes_namespace.nats.metadata[0].name}.svc.cluster.local:8080" : null
}

# External Access
output "external_endpoint" {
  description = "External NATS endpoint (if enabled)"
  value       = var.enable_external_access ? kubernetes_service.nats_client[0].status[0].load_balancer[0].ingress[0].hostname : null
}

output "external_ip" {
  description = "External IP address (if enabled)"
  value       = var.enable_external_access ? kubernetes_service.nats_client[0].status[0].load_balancer[0].ingress[0].ip : null
}

# Service Names
output "service_name" {
  description = "Name of the main NATS service"
  value       = kubernetes_service.nats.metadata[0].name
}

output "client_service_name" {
  description = "Name of the client service (if external access enabled)"
  value       = var.enable_external_access ? kubernetes_service.nats_client[0].metadata[0].name : null
}

# Service Account
output "service_account_name" {
  description = "Name of the NATS service account"
  value       = kubernetes_service_account.nats.metadata[0].name
}

# Ports
output "client_port" {
  description = "NATS client port"
  value       = 4222
}

output "cluster_port" {
  description = "NATS cluster port"
  value       = 6222
}

output "monitor_port" {
  description = "NATS monitoring port"
  value       = 8222
}

output "metrics_port" {
  description = "Prometheus metrics port"
  value       = var.prometheus_port
}

output "leafnode_port" {
  description = "NATS leafnode port"
  value       = var.leafnode_enabled ? 7422 : null
}

output "gateway_port" {
  description = "NATS gateway port"
  value       = var.gateway_enabled ? 7522 : null
}

output "websocket_port" {
  description = "NATS WebSocket port"
  value       = var.websocket_enabled ? 8080 : null
}

# JetStream Configuration
output "jetstream_enabled" {
  description = "Whether JetStream is enabled"
  value       = var.jetstream_enabled
}

output "jetstream_domain" {
  description = "JetStream domain name"
  value       = var.jetstream_enabled ? "${var.project_name}-nats-${var.environment}" : null
}

output "jetstream_max_memory" {
  description = "Maximum memory for JetStream"
  value       = var.jetstream_max_memory
}

output "jetstream_max_storage" {
  description = "Maximum storage for JetStream"
  value       = var.jetstream_max_storage
}

# Security Configuration
output "auth_enabled" {
  description = "Whether authentication is enabled"
  value       = var.auth_enabled
}

output "tls_enabled" {
  description = "Whether TLS is enabled"
  value       = var.tls_enabled
}

output "tls_secret_name" {
  description = "Name of the TLS secret"
  value       = var.tls_enabled ? kubernetes_secret.nats_tls[0].metadata[0].name : null
}

output "auth_secret_name" {
  description = "Name of the auth secret"
  value       = var.auth_enabled ? kubernetes_secret.nats_auth[0].metadata[0].name : null
}

# Monitoring Configuration
output "monitoring_enabled" {
  description = "Whether monitoring is enabled"
  value       = var.monitoring_enabled
}

output "service_monitor_name" {
  description = "Name of the ServiceMonitor (if Prometheus Operator enabled)"
  value       = var.monitoring_enabled && var.prometheus_operator_enabled ? "nats-metrics" : null
}

# StatefulSet Information
output "statefulset_name" {
  description = "Name of the NATS StatefulSet"
  value       = kubernetes_stateful_set.nats.metadata[0].name
}

output "pod_names" {
  description = "List of NATS pod names"
  value = [
    for i in range(var.cluster_size) : 
    "nats-${i}"
  ]
}

# ConfigMap and Secret Names
output "config_map_name" {
  description = "Name of the NATS configuration ConfigMap"
  value       = kubernetes_config_map.nats_config.metadata[0].name
}

# Network Policy
output "network_policy_enabled" {
  description = "Whether NetworkPolicy is enabled"
  value       = var.enable_network_policy
}

output "network_policy_name" {
  description = "Name of the NetworkPolicy"
  value       = var.enable_network_policy ? kubernetes_network_policy.nats[0].metadata[0].name : null
}

# PodDisruptionBudget
output "pdb_name" {
  description = "Name of the PodDisruptionBudget"
  value       = kubernetes_pod_disruption_budget.nats.metadata[0].name
}

# HorizontalPodAutoscaler
output "hpa_enabled" {
  description = "Whether HorizontalPodAutoscaler is enabled"
  value       = var.enable_autoscaling
}

output "hpa_name" {
  description = "Name of the HorizontalPodAutoscaler"
  value       = var.enable_autoscaling ? kubernetes_horizontal_pod_autoscaler_v2.nats[0].metadata[0].name : null
}

# Connection Information
output "connection_info" {
  description = "NATS connection information"
  value = {
    cluster_endpoint = "nats://nats.${kubernetes_namespace.nats.metadata[0].name}.svc.cluster.local:4222"
    urls = [
      for i in range(var.cluster_size) : 
      "nats://nats-${i}.nats.${kubernetes_namespace.nats.metadata[0].name}.svc.cluster.local:4222"
    ]
    websocket_url = var.websocket_enabled ? "ws://nats.${kubernetes_namespace.nats.metadata[0].name}.svc.cluster.local:8080" : null
    external_url = var.enable_external_access ? (
      kubernetes_service.nats_client[0].status[0].load_balancer[0].ingress[0].hostname != null ?
      "nats://${kubernetes_service.nats_client[0].status[0].load_balancer[0].ingress[0].hostname}:4222" :
      "nats://${kubernetes_service.nats_client[0].status[0].load_balancer[0].ingress[0].ip}:4222"
    ) : null
    tls_enabled = var.tls_enabled
    auth_enabled = var.auth_enabled
  }
}

# Health Check URLs
output "health_check_urls" {
  description = "Health check URLs for NATS"
  value = {
    for i in range(var.cluster_size) : 
    "nats-${i}" => "http://nats-${i}.nats.${kubernetes_namespace.nats.metadata[0].name}.svc.cluster.local:8222/healthz"
  }
}

# JetStream Health Check URLs
output "jetstream_health_check_urls" {
  description = "JetStream health check URLs"
  value = var.jetstream_enabled ? {
    for i in range(var.cluster_size) : 
    "nats-${i}" => "http://nats-${i}.nats.${kubernetes_namespace.nats.metadata[0].name}.svc.cluster.local:8222/healthz?js-enabled-only=true"
  } : {}
}

# Resource Information
output "resource_requests" {
  description = "Resource requests for NATS pods"
  value       = var.resources.requests
}

output "resource_limits" {
  description = "Resource limits for NATS pods"
  value       = var.resources.limits
}

output "storage_size" {
  description = "Storage size per NATS instance"
  value       = var.storage_size
}

output "storage_class" {
  description = "Storage class used for persistent volumes"
  value       = var.storage_class
}

# Protocol Status
output "protocols_enabled" {
  description = "Enabled protocols"
  value = {
    core       = true
    jetstream  = var.jetstream_enabled
    leafnode   = var.leafnode_enabled
    gateway    = var.gateway_enabled
    websocket  = var.websocket_enabled
    mqtt       = var.mqtt_enabled
  }
}

# Cluster Configuration Summary
output "cluster_summary" {
  description = "Summary of NATS cluster configuration"
  value = {
    cluster_name      = "${var.project_name}-nats-${var.environment}"
    cluster_size      = var.cluster_size
    namespace         = kubernetes_namespace.nats.metadata[0].name
    jetstream_enabled = var.jetstream_enabled
    auth_enabled      = var.auth_enabled
    tls_enabled       = var.tls_enabled
    monitoring_enabled = var.monitoring_enabled
    external_access   = var.enable_external_access
    autoscaling       = var.enable_autoscaling
    protocols = {
      leafnode  = var.leafnode_enabled
      gateway   = var.gateway_enabled
      websocket = var.websocket_enabled
      mqtt      = var.mqtt_enabled
    }
  }
}

# Security Summary
output "security_summary" {
  description = "Security configuration summary"
  value = {
    auth_enabled        = var.auth_enabled
    tls_enabled         = var.tls_enabled
    network_policy      = var.enable_network_policy
    pod_security_context = true
    audit_logging       = var.enable_audit_logging
    allowed_namespaces  = var.allowed_namespaces
  }
}

# Performance Configuration
output "performance_config" {
  description = "Performance configuration"
  value = {
    max_connections  = var.max_connections
    max_payload      = var.max_payload
    max_pending      = var.max_pending
    write_deadline   = var.write_deadline
    max_control_line = var.max_control_line
    ping_interval    = var.ping_interval
    ping_max         = var.ping_max
  }
}

# Backup Configuration
output "backup_config" {
  description = "Backup configuration"
  value = {
    enabled               = var.enable_backup
    schedule              = var.backup_schedule
    retention_days        = var.backup_retention_days
    disaster_recovery     = var.enable_disaster_recovery
    dr_backup_region      = var.dr_backup_region
  }
}

# Deployment Status
output "deployment_status" {
  description = "Deployment status information"
  value = {
    namespace_created    = true
    statefulset_created  = true
    service_created      = true
    configmap_created    = true
    rbac_configured      = true
    pdb_configured       = true
    monitoring_configured = var.monitoring_enabled
    external_access      = var.enable_external_access
  }
}