# Arrakis Platform Documentation

Welcome to the Arrakis Platform documentation. This directory contains comprehensive documentation for the entire platform.

## 📊 Architecture Diagrams

Auto-generated architecture diagrams are available in the [diagrams](./diagrams/) directory:

- [🏗️ System Overview](./diagrams/system-overview.md) - High-level system architecture
- [🔗 Service Dependencies](./diagrams/service-dependencies.md) - Detailed service relationships
- [🌊 Data Flow](./diagrams/data-flow.md) - Data flow through the system
- [⚡ Technology Stack](./diagrams/technology-stack.md) - Technology stack visualization

## 📚 API Documentation

OpenAPI specifications and API documentation:

- [📖 API Documentation](./build/index.html) - Interactive API documentation
- [📋 OpenAPI Specs](./openapi/) - Raw OpenAPI specifications
- [⚙️ Redocly Configuration](./redocly.yaml) - Documentation configuration

## 🔄 Event Documentation

Event-driven architecture documentation:

- [📡 Event Catalog](./eventcatalog/) - Comprehensive event documentation
- [🎯 Event Browser](./eventcatalog/events/) - Browse all platform events
- [🏗️ Service Event Maps](./eventcatalog/services/) - Service event relationships
- [📋 Event Standards](./eventcatalog/docs/index.md) - Event design guidelines

## 🔧 Developer Resources

- [🎯 Backstage Catalogs](../*/catalog-info.yaml) - Service catalog definitions
- [🐳 Docker Compose](../docker-compose.yml) - Local development setup
- [🔄 CI/CD Workflows](../.github/workflows/) - Automation workflows

## 📈 Monitoring & Observability

- **Prometheus**: Metrics collection and monitoring
- **Grafana**: Visualization and dashboards  
- **Jaeger**: Distributed tracing
- **AlertManager**: Alert routing and management

---

*Documentation automatically updated on $(date)*