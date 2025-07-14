---
name: Terminus Commit Created
version: 1.0.0
summary: |
  Event published when a new commit is created in the TerminusDB graph database.
  This event captures all data changes and triggers downstream processing workflows.
producers:
  - data-kernel-service
consumers:
  - ontology-management-service
  - audit-service
  - embedding-service
  - event-gateway
owners:
  - platform-team
tags:
  - terminus
  - commit
  - data-change
  - graph-database
externalLinks:
  - label: Data Kernel API
    url: /docs/openapi/data-kernel-service.html
  - label: TerminusDB Documentation
    url: https://terminusdb.com/docs/
---

# Terminus Commit Created Event

This event is published whenever a new commit is successfully created in the TerminusDB graph database. It represents atomic changes to the knowledge graph and triggers various downstream processing workflows.

## Event Details

- **Event Type**: `terminus.commit.created`
- **Source**: `data-kernel-service`
- **Subject Pattern**: `commit/{database_id}/{commit_id}`
- **Content Type**: `application/cloudevents+json`
- **Stream**: `terminus.commit.*`

## Event Flow

```mermaid
sequenceDiagram
    participant Client
    participant DK as Data Kernel Service
    participant TDB as TerminusDB
    participant NATS as NATS Broker
    participant OMS as Ontology Management Service
    participant ES as Embedding Service
    participant AS as Audit Service
    participant EG as Event Gateway

    Client->>DK: Submit data changes
    DK->>TDB: Execute transaction
    TDB->>DK: Return commit info
    DK->>NATS: Publish terminus.commit.created
    
    NATS->>OMS: Notify data changes
    NATS->>ES: Update embeddings
    NATS->>AS: Log data change
    NATS->>EG: Route to webhooks
    
    parallel
        OMS->>OMS: Update schema stats
    and
        ES->>ES: Recompute embeddings
    and
        AS->>AS: Record compliance data
    and
        EG->>EG: Trigger webhooks
    end
```

## Event Schema

```json
{
  "type": "object",
  "properties": {
    "specversion": {
      "type": "string",
      "const": "1.0"
    },
    "type": {
      "type": "string",
      "const": "terminus.commit.created"
    },
    "source": {
      "type": "string",
      "const": "data-kernel-service"
    },
    "subject": {
      "type": "string",
      "pattern": "^commit/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$"
    },
    "id": {
      "type": "string",
      "format": "uuid"
    },
    "time": {
      "type": "string",
      "format": "date-time"
    },
    "datacontenttype": {
      "type": "string",
      "const": "application/json"
    },
    "data": {
      "type": "object",
      "properties": {
        "commit_id": {
          "type": "string",
          "description": "Unique commit identifier"
        },
        "database_id": {
          "type": "string", 
          "description": "Target database identifier"
        },
        "branch": {
          "type": "string",
          "description": "Branch where commit was created",
          "default": "main"
        },
        "author": {
          "type": "string",
          "description": "User who created the commit"
        },
        "message": {
          "type": "string",
          "description": "Commit message describing changes"
        },
        "parent_commit": {
          "type": "string",
          "description": "Parent commit ID (null for initial commit)"
        },
        "changes": {
          "type": "object",
          "description": "Summary of changes in this commit",
          "properties": {
            "insertions": {
              "type": "integer",
              "description": "Number of triples inserted"
            },
            "deletions": {
              "type": "integer", 
              "description": "Number of triples deleted"
            },
            "document_changes": {
              "type": "array",
              "description": "List of changed documents",
              "items": {
                "type": "object",
                "properties": {
                  "document_id": { "type": "string" },
                  "operation": { 
                    "type": "string",
                    "enum": ["create", "update", "delete"]
                  },
                  "document_type": { "type": "string" }
                }
              }
            }
          }
        },
        "metadata": {
          "type": "object",
          "description": "Additional commit metadata",
          "properties": {
            "triggered_by": {
              "type": "string",
              "description": "What triggered this commit (user, api, system)"
            },
            "source_system": {
              "type": "string",
              "description": "System that originated the changes"
            },
            "transaction_id": {
              "type": "string",
              "description": "Associated transaction identifier"
            }
          }
        }
      },
      "required": ["commit_id", "database_id", "author", "message", "changes"]
    }
  },
  "required": ["specversion", "type", "source", "subject", "id", "time", "data"]
}
```

## Example Event

```json
{
  "specversion": "1.0",
  "type": "terminus.commit.created",
  "source": "data-kernel-service", 
  "subject": "commit/knowledge-base/abc123def456",
  "id": "7f9c8e7d-4b2a-4d8f-9e1c-3a5b7c9d1e2f",
  "time": "2024-01-15T14:23:45Z",
  "datacontenttype": "application/json",
  "data": {
    "commit_id": "abc123def456",
    "database_id": "knowledge-base",
    "branch": "main",
    "author": "user456",
    "message": "Add new product documents and update categories",
    "parent_commit": "def456abc123",
    "changes": {
      "insertions": 127,
      "deletions": 23,
      "document_changes": [
        {
          "document_id": "product-001",
          "operation": "create",
          "document_type": "Product"
        },
        {
          "document_id": "category-electronics",
          "operation": "update", 
          "document_type": "Category"
        }
      ]
    },
    "metadata": {
      "triggered_by": "api",
      "source_system": "product-management-portal",
      "transaction_id": "txn-789012345"
    }
  }
}
```

## Processing Guidelines

### For Ontology Management Service
1. **Schema Validation**: Verify changes comply with current schemas
2. **Stats Update**: Update document count and type statistics
3. **Consistency Check**: Ensure referential integrity

### For Embedding Service
1. **Document Analysis**: Analyze changed documents for embedding updates
2. **Vector Update**: Recompute embeddings for modified content
3. **Index Refresh**: Update vector similarity indexes

### For Audit Service
1. **Change Logging**: Record all document changes with timestamps
2. **Compliance Tracking**: Check changes against compliance policies
3. **Data Lineage**: Track data lineage and dependencies

### For Event Gateway
1. **Webhook Routing**: Route to registered webhooks based on filters
2. **External Notifications**: Notify external systems of data changes
3. **Event Replay**: Support event replay for system recovery

## Performance Considerations

- **Batch Processing**: Group small commits to reduce event volume
- **Change Filtering**: Only publish events for significant changes
- **Async Processing**: All downstream processing should be asynchronous
- **Rate Limiting**: Implement rate limiting for high-volume scenarios

## Error Handling

### Retry Strategy
- **Exponential Backoff**: Use exponential backoff for retries
- **Dead Letter Queue**: Send failed events to DLQ after max retries
- **Circuit Breaker**: Implement circuit breaker for downstream services

### Monitoring
- **Commit Rate**: Track commits per second/minute
- **Processing Latency**: Monitor end-to-end processing time
- **Error Rates**: Track failure rates by consumer service
- **Data Volume**: Monitor data volume changes over time

## Related Events

- [`terminus.commit.failed`](../terminus-commit-failed/) - Failed commit attempts
- [`ontology.schema.updated`](../ontology-schema-updated/) - Schema change events
- [`audit.data.changed`](../audit-data-changed/) - Audit trail events
- [`embedding.vector.updated`](../embedding-vector-updated/) - Embedding updates