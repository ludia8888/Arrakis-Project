# Microservices Architecture

**Generated:** 2025-07-15 01:00:53 UTC

```mermaid
graph TB
    %% External Layer
    Users[👥 Users] --> ALB[🔄 Application Load Balancer]
    ALB --> |HTTPS| Gateway[🚪 API Gateway]
    
    %% Microservices Layer
    subgraph "🏗️ Arrakis Microservices Platform"
        Gateway --> OMS[📊 Ontology Management<br/>Service]
        Gateway --> UserSvc[👤 User Service]
        Gateway --> AuditSvc[📋 Audit Service]
        Gateway --> DataKernel[⚙️ Data Kernel<br/>Service]
        Gateway --> EmbeddingSvc[🧠 Embedding<br/>Service]
        Gateway --> SchedulerSvc[⏰ Scheduler<br/>Service]
        Gateway --> EventGateway[🔄 Event Gateway]
        
        %% Service Dependencies
        OMS --> |queries| UserSvc
        OMS --> |logs| AuditSvc
        DataKernel --> |events| EventGateway
        SchedulerSvc --> |tasks| DataKernel
        EmbeddingSvc --> |vectors| DataKernel
    end
    
    %% Data Layer
    subgraph "💾 Data Layer"
        OMS --> OMSDB[(🗄️ OMS Database<br/>PostgreSQL)]
        UserSvc --> UserDB[(👤 User Database<br/>PostgreSQL)]
        AuditSvc --> AuditDB[(📋 Audit Database<br/>PostgreSQL)]
        SchedulerSvc --> SchedulerDB[(⏰ Scheduler Database<br/>PostgreSQL)]
        
        OMS --> Redis[(⚡ Redis Cache<br/>ElastiCache)]
        DataKernel --> Redis
        EmbeddingSvc --> Redis
        
        EventGateway --> NATS[(📨 NATS JetStream<br/>Message Broker)]
        SchedulerSvc --> NATS
        OMS --> NATS
    end
    
    %% External Integrations
    subgraph "🌐 External Systems"
        EventGateway --> ExtAPI[🔌 External APIs]
        EventGateway --> Webhooks[🔗 Webhooks]
    end
    
    %% Monitoring Layer
    subgraph "📊 Monitoring & Observability"
        AllServices[All Services] --> Prometheus[📈 Prometheus]
        Prometheus --> Grafana[📊 Grafana]
        AllServices --> Jaeger[🔍 Jaeger Tracing]
        AllServices --> CloudWatch[☁️ CloudWatch]
    end
    
    %% Styling
    classDef serviceClass fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef dataClass fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef monitorClass fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    classDef externalClass fill:#fff3e0,stroke:#e65100,stroke-width:2px
    
    class OMS,UserSvc,AuditSvc,DataKernel,EmbeddingSvc,SchedulerSvc,EventGateway serviceClass
    class OMSDB,UserDB,AuditDB,SchedulerDB,Redis,NATS dataClass
    class Prometheus,Grafana,Jaeger,CloudWatch monitorClass
    class ExtAPI,Webhooks externalClass
```

## Usage

This Mermaid diagram can be:
1. **Rendered in GitHub** - Automatically displayed in GitHub README files
2. **Used in Documentation** - Embedded in GitBook, Notion, or other docs
3. **Exported to Images** - Using Mermaid CLI or online tools
4. **Integrated in Presentations** - Copy the Mermaid code into presentation tools

## Live Editor

Edit this diagram at: [Mermaid Live Editor](https://mermaid.live/)

## Integration

This diagram is automatically updated when:
- Code changes are committed to the repository
- Infrastructure configuration is modified
- GitHub Actions workflows are triggered
