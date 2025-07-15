# NATS Server Configuration
# Production-ready configuration with JetStream, clustering, and security

# Server identification
server_name: $POD_NAME
listen: 0.0.0.0:4222

# Clustering configuration
cluster {
  name: ${cluster_name}
  listen: 0.0.0.0:6222

  # Routes to other nodes
  routes: [
    %{ for i in range(cluster_size) ~}
    nats-route://nats-${i}.nats.${namespace}.svc.cluster.local:6222
    %{ endfor ~}
  ]

  # Cluster authorization
  %{ if auth_enabled ~}
  authorization {
    user: $CLUSTER_USER
    password: $CLUSTER_PASSWORD
    timeout: 2
  }
  %{ endif ~}

  # TLS for cluster communication
  %{ if tls_enabled ~}
  tls {
    cert_file: /etc/nats/tls/tls.crt
    key_file: /etc/nats/tls/tls.key
    ca_file: /etc/nats/tls/ca.crt
    verify: true
    verify_and_map: true
    timeout: 2
  }
  %{ endif ~}
}

# Client connections
max_connections: ${max_connections}
max_control_line: ${max_control_line}
max_payload: ${max_payload}
max_pending: ${max_pending}

# Performance tuning
write_deadline: "${write_deadline}"
ping_interval: "${ping_interval}"
ping_max: ${ping_max}

# Logging configuration
debug: false
trace: false
logtime: true
log_file: "/data/nats.log"
log_size_limit: 1GB
max_traced_msg_len: 1024

# Monitoring endpoints
http: 0.0.0.0:8222
server_name: $POD_NAME

# System account for internal operations
%{ if auth_enabled ~}
include "/etc/nats/auth/auth.conf"
%{ endif ~}

# TLS Configuration for client connections
%{ if tls_enabled ~}
tls {
  cert_file: /etc/nats/tls/tls.crt
  key_file: /etc/nats/tls/tls.key
  ca_file: /etc/nats/tls/ca.crt
  verify: true
  timeout: 2
}
%{ endif ~}

# JetStream Configuration
%{ if jetstream_enabled ~}
jetstream {
  store_dir: /data/jetstream
  max_mem: ${jetstream_max_memory}
  max_file: ${jetstream_max_storage}

  # Domain configuration for multi-tenancy
  domain: ${cluster_name}

  # Encryption at rest
  cipher: "AES"

  # Limits
  max_streams: 1000
  max_consumers: 10000

  # Resource limits per account
  limits {
    max_memory: ${jetstream_max_memory}
    max_storage: ${jetstream_max_storage}
    max_streams: 100
    max_consumers: 1000
    max_acks_pending: 10000
    memory_max_stream_bytes: 1GB
    storage_max_stream_bytes: 10GB
    max_bytes_required: true
  }
}
%{ endif ~}

# Leafnode Configuration
%{ if leafnode_enabled ~}
leafnodes {
  listen: 0.0.0.0:7422

  # TLS for leafnode connections
  %{ if tls_enabled ~}
  tls {
    cert_file: /etc/nats/tls/tls.crt
    key_file: /etc/nats/tls/tls.key
    ca_file: /etc/nats/tls/ca.crt
    verify: true
    timeout: 2
  }
  %{ endif ~}

  # Authorization
  %{ if auth_enabled ~}
  authorization {
    user: $LEAFNODE_USER
    password: $LEAFNODE_PASSWORD
    timeout: 2
  }
  %{ endif ~}
}
%{ endif ~}

# Gateway Configuration for super clusters
%{ if gateway_enabled ~}
gateway {
  name: ${cluster_name}
  listen: 0.0.0.0:7522

  # TLS for gateway connections
  %{ if tls_enabled ~}
  tls {
    cert_file: /etc/nats/tls/tls.crt
    key_file: /etc/nats/tls/tls.key
    ca_file: /etc/nats/tls/ca.crt
    verify: true
    timeout: 2
  }
  %{ endif ~}

  # Authorization
  %{ if auth_enabled ~}
  authorization {
    user: $GATEWAY_USER
    password: $GATEWAY_PASSWORD
    timeout: 2
  }
  %{ endif ~}
}
%{ endif ~}

# WebSocket Configuration
%{ if websocket_enabled ~}
websocket {
  listen: 0.0.0.0:8080

  # TLS for WebSocket
  %{ if tls_enabled ~}
  tls {
    cert_file: /etc/nats/tls/tls.crt
    key_file: /etc/nats/tls/tls.key
  }
  %{ endif ~}

  # Compression
  compression: true

  # Same origin policy
  same_origin: false
  allowed_origins: ["*"]

  # JWT-based auth for WebSocket
  %{ if auth_enabled ~}
  jwt_cookie: "jwt"
  %{ endif ~}
}
%{ endif ~}

# MQTT Configuration
%{ if mqtt_enabled ~}
mqtt {
  listen: 0.0.0.0:1883

  # TLS for MQTT
  %{ if tls_enabled ~}
  tls {
    cert_file: /etc/nats/tls/tls.crt
    key_file: /etc/nats/tls/tls.key
  }
  %{ endif ~}

  # MQTT specific settings
  max_ack_pending: 100
  ack_wait: "1m"
}
%{ endif ~}

# Monitoring and metrics
%{ if monitoring_enabled ~}
# Prometheus metrics endpoint
http: 0.0.0.0:${prometheus_port}
%{ endif ~}

# Connection limits and timeouts
authorization {
  timeout: 1
}

# Resolver preload for better startup performance
resolver_preload: {
  %{ for i in range(cluster_size) ~}
  "nats-${i}.nats.${namespace}.svc.cluster.local": ["10.0.0.${i + 10}"]
  %{ endfor ~}
}
