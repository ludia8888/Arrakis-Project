# Arrakis Platform Event Catalog

This directory contains the EventCatalog documentation for the Arrakis platform's event-driven architecture. EventCatalog provides a comprehensive view of all events, services, and their relationships in our system.

## 🚀 Quick Start

### Prerequisites
```bash
# Install Node.js (16+ required)
npm install -g @eventcatalog/cli

# Install dependencies
cd docs/eventcatalog
npm install
```

### Development
```bash
# Start development server
npm run dev
# or from project root
npm run eventcatalog:dev

# Visit http://localhost:3000
```

### Building
```bash
# Build static site
npm run build

# Serve built site
npm run serve
```

## 📁 Directory Structure

```
docs/eventcatalog/
├── eventcatalog.config.js     # EventCatalog configuration
├── docs/                      # Main documentation
│   └── index.md              # Landing page
├── events/                    # Event definitions
│   ├── ontology-schema-created/
│   ├── terminus-commit-created/
│   └── ...
├── services/                  # Service documentation
│   ├── ontology-management-service/
│   ├── event-gateway/
│   └── ...
└── package.json              # Dependencies
```

## 📚 Documentation Standards

### Event Documentation
Each event should include:
- **Schema Definition** - JSON Schema for event payload
- **Example Events** - Real examples with realistic data
- **Producers** - Services that publish the event
- **Consumers** - Services that consume the event
- **Processing Guidelines** - How consumers should handle the event
- **Error Handling** - Retry and failure strategies

### Service Documentation
Each service should include:
- **Event Publishing** - What events the service publishes
- **Event Consumption** - What events the service consumes
- **Event Flow Diagrams** - Visual representation of event flows
- **Configuration** - NATS and event-related configuration
- **Monitoring** - Metrics and alerting for event processing

## 🔄 Event Patterns

### Naming Conventions
- **Domain Events**: `domain.entity.action`
  - Example: `ontology.schema.created`
- **Integration Events**: `system.entity.action`
  - Example: `terminus.commit.created`
- **System Events**: `service.category.action`
  - Example: `gateway.webhook.failed`

### Event Categories
- **Domain Events** - Core business events
- **Integration Events** - Cross-system integration
- **System Events** - Infrastructure and operational events
- **Audit Events** - Compliance and security events

## 🛠️ Event Governance

### Schema Evolution
- **Additive Changes** - Add optional fields only
- **Breaking Changes** - Require new event type with version
- **Deprecation** - 6-month deprecation period for old events
- **Validation** - All events must pass JSON Schema validation

### Documentation Requirements
- **All Events** must be documented before production use
- **Breaking Changes** require architecture review
- **New Services** must document event patterns
- **Consumer Changes** require impact analysis

## 📊 Event Monitoring

### Key Metrics
- **Event Throughput** - Events published/consumed per service
- **Processing Latency** - End-to-end event processing time
- **Error Rates** - Failed event processing by service
- **Schema Violations** - Invalid events by type

### Dashboards
- **Event Flow Dashboard** - Real-time event streaming
- **Service Health Dashboard** - Event processing health per service
- **Schema Compliance Dashboard** - Schema validation metrics

## 🔧 Tools & Integration

### AsyncAPI Generation
EventCatalog can generate documentation from AsyncAPI specifications:

```bash
# Generate from AsyncAPI specs
npm run generate
```

### CI/CD Integration
The EventCatalog is automatically updated via GitHub Actions:
- **On Event Changes** - Regenerate documentation
- **On Service Changes** - Update service event patterns
- **On Schema Changes** - Validate and update schemas

### Local Development
```bash
# Watch for changes and auto-reload
npm run dev

# Validate all event documentation
npm run validate

# Export static documentation
npm run export
```

## 🎯 Event Scenarios

### New Service Integration
1. **Document Events** - Add service and event definitions
2. **Define Schemas** - Create JSON schemas for events
3. **Add Examples** - Provide realistic event examples
4. **Update Flows** - Add to event flow diagrams
5. **Configure Monitoring** - Set up metrics and alerts

### Event Schema Changes
1. **Impact Analysis** - Identify affected consumers
2. **Schema Validation** - Ensure backward compatibility
3. **Documentation Update** - Update event documentation
4. **Consumer Testing** - Verify consumer compatibility
5. **Rollout Plan** - Coordinate deployment across services

## 🔗 Related Documentation

- [Architecture Diagrams](../diagrams/) - System architecture visualization
- [API Documentation](../build/) - REST and GraphQL API documentation
- [Service Catalog](../../*/catalog-info.yaml) - Backstage service definitions
- [Monitoring Setup](../monitoring/) - Observability configuration

## 🎮 Interactive Features

EventCatalog provides:
- **Event Browser** - Search and explore all events
- **Service Map** - Visual service-to-event relationships
- **Schema Registry** - Event schema validation and versioning
- **Flow Diagrams** - Interactive event flow visualization
- **API Integration** - REST API for programmatic access

## 🚀 Getting Started Guides

### For Developers
1. [Publishing Your First Event](./guides/publishing-events.md)
2. [Consuming Events Safely](./guides/consuming-events.md)
3. [Error Handling Best Practices](./guides/error-handling.md)

### For Architects
1. [Event Design Patterns](./guides/event-patterns.md)
2. [Schema Evolution Strategy](./guides/schema-evolution.md)
3. [Service Integration Patterns](./guides/integration-patterns.md)

### For Operations
1. [Monitoring Event Systems](./guides/monitoring.md)
2. [Troubleshooting Event Issues](./guides/troubleshooting.md)
3. [Performance Optimization](./guides/performance.md)
