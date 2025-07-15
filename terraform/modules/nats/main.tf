# NATS Module - Production-ready NATS cluster on Kubernetes
# Event streaming infrastructure with JetStream, monitoring, and high availability

# Data sources
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# Helm provider configuration
provider "helm" {
  kubernetes {
    host                   = var.cluster_endpoint
    cluster_ca_certificate = base64decode(var.cluster_ca_certificate)
    token                  = var.cluster_auth_token
  }
}

# Create NATS namespace
resource "kubernetes_namespace" "nats" {
  metadata {
    name = var.namespace
    labels = {
      name                         = var.namespace
      "pod-security.kubernetes.io/enforce" = "baseline"
      "pod-security.kubernetes.io/audit"   = "restricted"
      "pod-security.kubernetes.io/warn"    = "restricted"
      "istio-injection"            = var.enable_istio ? "enabled" : "disabled"
    }
    annotations = {
      "field.cattle.io/projectId" = var.project_name
      description                 = "NATS event streaming infrastructure"
    }
  }
}

# NATS Operator deployment
resource "helm_release" "nats_operator" {
  name       = "nats-operator"
  repository = "https://nats-io.github.io/k8s/helm/charts/"
  chart      = "nats-operator"
  version    = var.nats_operator_version
  namespace  = kubernetes_namespace.nats.metadata[0].name

  values = [
    yamlencode({
      operator = {
        image = {
          repository = "nats-io/nats-operator"
          tag        = var.nats_operator_version
          pullPolicy = "IfNotPresent"
        }
        resources = {
          requests = {
            cpu    = "100m"
            memory = "128Mi"
          }
          limits = {
            cpu    = "500m"
            memory = "512Mi"
          }
        }
        serviceAccount = {
          create = true
          name   = "nats-operator"
        }
      }
      rbac = {
        create = true
      }
      securityContext = {
        runAsNonRoot = true
        runAsUser    = 1000
        fsGroup      = 1000
      }
    })
  ]

  wait = true
  wait_for_jobs = true
}

# TLS Certificate for NATS
resource "kubernetes_secret" "nats_tls" {
  count = var.tls_enabled ? 1 : 0

  metadata {
    name      = "nats-server-tls"
    namespace = kubernetes_namespace.nats.metadata[0].name
  }

  type = "kubernetes.io/tls"

  data = {
    "tls.crt" = var.tls_cert
    "tls.key" = var.tls_key
    "ca.crt"  = var.tls_ca_cert
  }
}

# NATS Server ConfigMap
resource "kubernetes_config_map" "nats_config" {
  metadata {
    name      = "nats-config"
    namespace = kubernetes_namespace.nats.metadata[0].name
  }

  data = {
    "nats.conf" = templatefile("${path.module}/nats.conf.tpl", {
      cluster_name              = "${var.project_name}-nats-${var.environment}"
      cluster_size              = var.cluster_size
      jetstream_enabled         = var.jetstream_enabled
      jetstream_max_memory      = var.jetstream_max_memory
      jetstream_max_storage     = var.jetstream_max_storage
      jetstream_storage_class   = var.jetstream_storage_class
      auth_enabled              = var.auth_enabled
      tls_enabled               = var.tls_enabled
      monitoring_enabled        = var.monitoring_enabled
      prometheus_port           = var.prometheus_port
      max_connections           = var.max_connections
      max_payload               = var.max_payload
      max_pending               = var.max_pending
      write_deadline            = var.write_deadline
      max_control_line          = var.max_control_line
      ping_interval             = var.ping_interval
      ping_max                  = var.ping_max
      leafnode_enabled          = var.leafnode_enabled
      gateway_enabled           = var.gateway_enabled
      websocket_enabled         = var.websocket_enabled
      mqtt_enabled              = var.mqtt_enabled
    })
  }
}

# NATS Auth Secret
resource "kubernetes_secret" "nats_auth" {
  count = var.auth_enabled ? 1 : 0

  metadata {
    name      = "nats-auth"
    namespace = kubernetes_namespace.nats.metadata[0].name
  }

  data = {
    "auth.conf" = base64encode(templatefile("${path.module}/auth.conf.tpl", {
      system_account   = var.system_account
      system_user      = var.system_user
      operator_jwt     = var.operator_jwt
      account_jwt      = var.account_jwt
      user_credentials = var.user_credentials
    }))
  }
}

# NATS StatefulSet
resource "kubernetes_stateful_set" "nats" {
  metadata {
    name      = "nats"
    namespace = kubernetes_namespace.nats.metadata[0].name
    labels = {
      app        = "nats"
      component  = "server"
      project    = var.project_name
      environment = var.environment
    }
  }

  spec {
    replicas = var.cluster_size
    service_name = "nats"
    pod_management_policy = "Parallel"

    selector {
      match_labels = {
        app = "nats"
      }
    }

    template {
      metadata {
        labels = {
          app        = "nats"
          component  = "server"
          project    = var.project_name
          environment = var.environment
        }
        annotations = {
          "prometheus.io/scrape" = var.monitoring_enabled ? "true" : "false"
          "prometheus.io/port"   = tostring(var.prometheus_port)
          "prometheus.io/path"   = "/metrics"
        }
      }

      spec {
        service_account_name = kubernetes_service_account.nats.metadata[0].name

        security_context {
          fs_group = 1000
          run_as_non_root = true
          run_as_user = 1000
        }

        affinity {
          pod_anti_affinity {
            required_during_scheduling_ignored_during_execution {
              label_selector {
                match_labels = {
                  app = "nats"
                }
              }
              topology_key = "kubernetes.io/hostname"
            }
          }
        }

        container {
          name  = "nats"
          image = "${var.nats_image}:${var.nats_version}"
          image_pull_policy = "IfNotPresent"

          command = ["/nats-server"]
          args = [
            "--config", "/etc/nats/nats.conf",
            "--name", "$(POD_NAME)"
          ]

          env {
            name = "POD_NAME"
            value_from {
              field_ref {
                field_path = "metadata.name"
              }
            }
          }

          env {
            name = "POD_NAMESPACE"
            value_from {
              field_ref {
                field_path = "metadata.namespace"
              }
            }
          }

          port {
            name           = "client"
            container_port = 4222
            protocol       = "TCP"
          }

          port {
            name           = "cluster"
            container_port = 6222
            protocol       = "TCP"
          }

          port {
            name           = "monitor"
            container_port = 8222
            protocol       = "TCP"
          }

          port {
            name           = "metrics"
            container_port = var.prometheus_port
            protocol       = "TCP"
          }

          dynamic "port" {
            for_each = var.leafnode_enabled ? [1] : []
            content {
              name           = "leafnode"
              container_port = 7422
              protocol       = "TCP"
            }
          }

          dynamic "port" {
            for_each = var.gateway_enabled ? [1] : []
            content {
              name           = "gateway"
              container_port = 7522
              protocol       = "TCP"
            }
          }

          dynamic "port" {
            for_each = var.websocket_enabled ? [1] : []
            content {
              name           = "websocket"
              container_port = 8080
              protocol       = "TCP"
            }
          }

          volume_mount {
            name       = "config"
            mount_path = "/etc/nats"
            read_only  = true
          }

          dynamic "volume_mount" {
            for_each = var.tls_enabled ? [1] : []
            content {
              name       = "tls"
              mount_path = "/etc/nats/tls"
              read_only  = true
            }
          }

          dynamic "volume_mount" {
            for_each = var.auth_enabled ? [1] : []
            content {
              name       = "auth"
              mount_path = "/etc/nats/auth"
              read_only  = true
            }
          }

          volume_mount {
            name       = "data"
            mount_path = "/data"
          }

          resources {
            requests = {
              cpu    = var.resources.requests.cpu
              memory = var.resources.requests.memory
            }
            limits = {
              cpu    = var.resources.limits.cpu
              memory = var.resources.limits.memory
            }
          }

          liveness_probe {
            http_get {
              path = "/healthz"
              port = "monitor"
            }
            initial_delay_seconds = 10
            timeout_seconds       = 5
            period_seconds        = 10
            failure_threshold     = 3
          }

          readiness_probe {
            http_get {
              path = "/healthz?js-enabled-only=true"
              port = "monitor"
            }
            initial_delay_seconds = 10
            timeout_seconds       = 5
            period_seconds        = 10
            failure_threshold     = 3
          }

          startup_probe {
            http_get {
              path = "/healthz"
              port = "monitor"
            }
            initial_delay_seconds = 5
            timeout_seconds       = 5
            period_seconds        = 10
            failure_threshold     = 30
          }

          lifecycle {
            pre_stop {
              exec {
                command = ["/bin/sh", "-c", "nats-server --signal ldm=/var/run/nats/nats.pid"]
              }
            }
          }
        }

        # Prometheus JetStream exporter sidecar
        dynamic "container" {
          for_each = var.monitoring_enabled && var.jetstream_enabled ? [1] : []
          content {
            name  = "jetstream-exporter"
            image = "natsio/prometheus-nats-exporter:latest"
            args = [
              "-varz",
              "-jsz=all",
              "-subz",
              "-connz",
              "-leafz",
              "-gatewayz",
              "-routez",
              "-serverz",
              "-http_addr=0.0.0.0:7777",
              "http://localhost:8222"
            ]

            port {
              name           = "exporter"
              container_port = 7777
              protocol       = "TCP"
            }

            resources {
              requests = {
                cpu    = "50m"
                memory = "64Mi"
              }
              limits = {
                cpu    = "100m"
                memory = "128Mi"
              }
            }
          }
        }

        volume {
          name = "config"
          config_map {
            name = kubernetes_config_map.nats_config.metadata[0].name
          }
        }

        dynamic "volume" {
          for_each = var.tls_enabled ? [1] : []
          content {
            name = "tls"
            secret {
              secret_name = kubernetes_secret.nats_tls[0].metadata[0].name
            }
          }
        }

        dynamic "volume" {
          for_each = var.auth_enabled ? [1] : []
          content {
            name = "auth"
            secret {
              secret_name = kubernetes_secret.nats_auth[0].metadata[0].name
            }
          }
        }

        volume {
          name = "data"
          empty_dir {}
        }
      }
    }

    volume_claim_template {
      metadata {
        name = "data"
      }
      spec {
        access_modes = ["ReadWriteOnce"]
        storage_class_name = var.storage_class
        resources {
          requests = {
            storage = var.storage_size
          }
        }
      }
    }

    update_strategy {
      type = "RollingUpdate"
      rolling_update {
        partition = 0
      }
    }
  }
}

# NATS Service
resource "kubernetes_service" "nats" {
  metadata {
    name      = "nats"
    namespace = kubernetes_namespace.nats.metadata[0].name
    labels = {
      app        = "nats"
      component  = "server"
      project    = var.project_name
      environment = var.environment
    }
  }

  spec {
    type = "ClusterIP"
    cluster_ip = "None"

    selector = {
      app = "nats"
    }

    port {
      name        = "client"
      port        = 4222
      target_port = "client"
    }

    port {
      name        = "cluster"
      port        = 6222
      target_port = "cluster"
    }

    port {
      name        = "monitor"
      port        = 8222
      target_port = "monitor"
    }

    port {
      name        = "metrics"
      port        = var.prometheus_port
      target_port = "metrics"
    }

    dynamic "port" {
      for_each = var.leafnode_enabled ? [1] : []
      content {
        name        = "leafnode"
        port        = 7422
        target_port = "leafnode"
      }
    }

    dynamic "port" {
      for_each = var.gateway_enabled ? [1] : []
      content {
        name        = "gateway"
        port        = 7522
        target_port = "gateway"
      }
    }

    dynamic "port" {
      for_each = var.websocket_enabled ? [1] : []
      content {
        name        = "websocket"
        port        = 8080
        target_port = "websocket"
      }
    }
  }
}

# NATS Client Service (LoadBalancer for external access)
resource "kubernetes_service" "nats_client" {
  count = var.enable_external_access ? 1 : 0

  metadata {
    name      = "nats-client"
    namespace = kubernetes_namespace.nats.metadata[0].name
    labels = {
      app        = "nats"
      component  = "client"
      project    = var.project_name
      environment = var.environment
    }
    annotations = var.service_annotations
  }

  spec {
    type = var.service_type
    load_balancer_source_ranges = var.load_balancer_source_ranges

    selector = {
      app = "nats"
    }

    port {
      name        = "client"
      port        = 4222
      target_port = "client"
    }

    dynamic "port" {
      for_each = var.websocket_enabled ? [1] : []
      content {
        name        = "websocket"
        port        = 8080
        target_port = "websocket"
      }
    }
  }
}

# Service Account
resource "kubernetes_service_account" "nats" {
  metadata {
    name      = "nats-server"
    namespace = kubernetes_namespace.nats.metadata[0].name
    labels = {
      app        = "nats"
      component  = "server"
      project    = var.project_name
      environment = var.environment
    }
  }
}

# RBAC Role
resource "kubernetes_role" "nats" {
  metadata {
    name      = "nats-server"
    namespace = kubernetes_namespace.nats.metadata[0].name
  }

  rule {
    api_groups = [""]
    resources  = ["configmaps"]
    verbs      = ["get", "list", "watch"]
  }

  rule {
    api_groups = [""]
    resources  = ["endpoints"]
    verbs      = ["get", "list", "watch"]
  }
}

# RBAC RoleBinding
resource "kubernetes_role_binding" "nats" {
  metadata {
    name      = "nats-server"
    namespace = kubernetes_namespace.nats.metadata[0].name
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role.nats.metadata[0].name
  }

  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account.nats.metadata[0].name
    namespace = kubernetes_namespace.nats.metadata[0].name
  }
}

# PodDisruptionBudget
resource "kubernetes_pod_disruption_budget" "nats" {
  metadata {
    name      = "nats-pdb"
    namespace = kubernetes_namespace.nats.metadata[0].name
  }

  spec {
    max_unavailable = var.cluster_size > 3 ? 1 : 0

    selector {
      match_labels = {
        app = "nats"
      }
    }
  }
}

# NetworkPolicy
resource "kubernetes_network_policy" "nats" {
  count = var.enable_network_policy ? 1 : 0

  metadata {
    name      = "nats-network-policy"
    namespace = kubernetes_namespace.nats.metadata[0].name
  }

  spec {
    pod_selector {
      match_labels = {
        app = "nats"
      }
    }

    policy_types = ["Ingress", "Egress"]

    ingress {
      from {
        namespace_selector {
          match_labels = {
            name = var.namespace
          }
        }
      }

      from {
        pod_selector {
          match_labels = {
            app = "nats"
          }
        }
      }

      dynamic "from" {
        for_each = var.allowed_namespaces
        content {
          namespace_selector {
            match_labels = {
              name = from.value
            }
          }
        }
      }

      ports {
        protocol = "TCP"
        port     = "4222"
      }

      ports {
        protocol = "TCP"
        port     = "6222"
      }

      ports {
        protocol = "TCP"
        port     = "8222"
      }
    }

    egress {
      to {
        pod_selector {
          match_labels = {
            app = "nats"
          }
        }
      }

      ports {
        protocol = "TCP"
        port     = "6222"
      }
    }

    egress {
      to {
        namespace_selector {}
      }

      ports {
        protocol = "TCP"
        port     = "53"
      }

      ports {
        protocol = "UDP"
        port     = "53"
      }
    }
  }
}

# ServiceMonitor for Prometheus
resource "kubernetes_manifest" "nats_service_monitor" {
  count = var.monitoring_enabled && var.prometheus_operator_enabled ? 1 : 0

  manifest = {
    apiVersion = "monitoring.coreos.com/v1"
    kind       = "ServiceMonitor"
    metadata = {
      name      = "nats-metrics"
      namespace = kubernetes_namespace.nats.metadata[0].name
      labels = {
        app        = "nats"
        component  = "metrics"
        release    = "prometheus"
      }
    }
    spec = {
      selector = {
        matchLabels = {
          app = "nats"
        }
      }
      endpoints = [
        {
          port     = "metrics"
          interval = "30s"
          path     = "/metrics"
        }
      ]
    }
  }
}

# HorizontalPodAutoscaler
resource "kubernetes_horizontal_pod_autoscaler_v2" "nats" {
  count = var.enable_autoscaling ? 1 : 0

  metadata {
    name      = "nats-hpa"
    namespace = kubernetes_namespace.nats.metadata[0].name
  }

  spec {
    scale_target_ref {
      api_version = "apps/v1"
      kind        = "StatefulSet"
      name        = kubernetes_stateful_set.nats.metadata[0].name
    }

    min_replicas = var.min_replicas
    max_replicas = var.max_replicas

    metric {
      type = "Resource"
      resource {
        name = "cpu"
        target {
          type                = "Utilization"
          average_utilization = var.target_cpu_utilization_percentage
        }
      }
    }

    metric {
      type = "Resource"
      resource {
        name = "memory"
        target {
          type                = "Utilization"
          average_utilization = var.target_memory_utilization_percentage
        }
      }
    }

    behavior {
      scale_up {
        stabilization_window_seconds = 60
        select_policy               = "Max"
        policy {
          type          = "Percent"
          value         = 100
          period_seconds = 60
        }
      }
      scale_down {
        stabilization_window_seconds = 300
        select_policy               = "Min"
        policy {
          type          = "Percent"
          value         = 50
          period_seconds = 60
        }
      }
    }
  }
}
