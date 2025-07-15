# NATS Authentication Configuration
# Production-ready auth configuration with JWT-based authentication

# Operator Configuration
operator: ${operator_jwt}

# System Account
system_account: ${system_account}

# Resolver configuration for decentralized JWT auth
resolver: {
  type: full
  dir: "/data/jwt"
  allow_delete: false
  interval: "2m"
  timeout: "1.9s"
}

# Resolver preload
resolver_preload: {
  ${system_account}: "${account_jwt}"
}

# Authorization configuration
authorization {
  # System user for internal operations
  users: [
    {
      user: "${system_user}"
      password: "$SYSTEM_PASSWORD"
      permissions: {
        publish: ">"
        subscribe: ">"
      }
    }
  ]

  # Default permissions
  default_permissions: {
    publish: {
      deny: ">"
    }
    subscribe: {
      allow: ["_INBOX.>", "_INBOX.*"]
    }
  }

  # Auth timeout
  timeout: 1
}

# Accounts configuration
accounts: {
  # System account
  ${system_account}: {
    jetstream: enabled
    users: [
      {nkey: "${system_user}"}
    ]
  }

  # Default account for applications
  $APP_ACCOUNT: {
    jetstream: {
      max_memory: 1GB
      max_storage: 10GB
      max_streams: 100
      max_consumers: 1000
    }
    users: [
      {nkey: "$APP_USER"}
    ]
    exports: [
      {stream: "app.>", accounts: ["${system_account}"]}
      {service: "app.api.>", accounts: ["${system_account}"]}
    ]
    imports: [
      {stream: {account: "${system_account}", subject: "system.>"}, prefix: "imported.system"}
      {service: {account: "${system_account}", subject: "system.api.>"}}
    ]
  }
}

# No auth block - using operator mode with JWT
