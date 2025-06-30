# ADR-012: Scheduler Modularization

## Status
Accepted

## Context
The advanced scheduler component was initially implemented as a monolithic class combining multiple responsibilities:
- Trigger parsing and schedule calculation
- Job execution and lifecycle management
- State persistence
- Worker coordination
- Notification handling

This design led to:
- High coupling between components
- Difficulty in testing individual components
- Limited flexibility in extending functionality
- Code duplication across different scheduling scenarios

## Decision
We have modularized the scheduler into discrete, focused components following the Single Responsibility Principle:

### 1. **ScheduleCalculator** (`schedule_calculator.py`)
- **Responsibility**: Pure schedule calculation logic
- **Key Functions**:
  - Parse trigger strings into APScheduler trigger objects
  - Calculate next run times
  - Implement retry delay strategies (exponential, linear, fixed, fibonacci)
  - Business hours validation
  - Cron expression validation

### 2. **JobExecutor** (`job_executor.py`)
- **Responsibility**: Job execution and lifecycle management
- **Key Functions**:
  - Execute jobs with proper error handling
  - Manage job lifecycle (start, complete, fail)
  - Track running jobs
  - Handle job cancellation
  - Emit execution metrics

### 3. **StateManager** (`state_manager.py`)
- **Responsibility**: Persistent state management
- **Key Functions**:
  - Save/retrieve job metadata
  - Track job execution history
  - Manage job dependencies
  - Clean up old executions

### 4. **NotificationService** (`notification_service.py`)
- **Responsibility**: Event notification and alerting
- **Key Functions**:
  - Send job completion notifications
  - Alert on job failures
  - Handle webhook notifications
  - Log-only implementation for testing

### 5. **EnterpriseScheduler** (`advanced_scheduler.py`)
- **Responsibility**: Facade/orchestrator for all components
- **Key Functions**:
  - Initialize and coordinate components
  - Provide unified scheduling API
  - Handle APScheduler integration
  - Manage worker lifecycle

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    EnterpriseScheduler                       │
│                      (Facade/Orchestrator)                   │
└─────────────┬────────────┬────────────┬────────────┬────────┘
              │            │            │            │
              ▼            ▼            ▼            ▼
┌──────────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
│ScheduleCalculator│ │JobExecutor│ │StateManager│ │Notification │
│                  │ │          │ │          │ │   Service    │
│ • Parse triggers │ │• Execute │ │• Persist │ │ • Send alerts│
│ • Calculate next │ │  jobs    │ │  state   │ │ • Webhooks   │
│ • Retry delays   │ │• Lifecycle│ │• History │ │ • Logging    │
│ • Business hours │ │• Metrics │ │• Cleanup │ │              │
└──────────────────┘ └──────────┘ └──────────┘ └──────────────┘
```

## Benefits

1. **Testability**: Each component can be tested in isolation with mock dependencies
2. **Flexibility**: Components can be replaced with alternative implementations
3. **Maintainability**: Clear separation of concerns makes code easier to understand
4. **Extensibility**: New features can be added without modifying existing components
5. **Reusability**: Components can be used independently in other contexts

## Implementation Details

### Protocol-Based Design
Each component implements a protocol (abstract base class) defining its interface:
- `ScheduleCalculatorProtocol`
- `JobExecutorProtocol`
- `StateManagerProtocol`
- `NotificationServiceProtocol`

This allows for:
- Easy mocking in tests
- Alternative implementations
- Clear contracts between components

### Dependency Injection
The `EnterpriseScheduler` accepts component implementations via constructor parameters:

```python
scheduler = EnterpriseScheduler(
    redis_client=redis_client,
    job_executor=custom_executor,  # Optional custom implementation
    state_manager=custom_state_manager,  # Optional custom implementation
    notification_service=custom_notifier,  # Optional custom implementation
    schedule_calculator=custom_calculator  # Optional custom implementation
)
```

### Backward Compatibility
The facade maintains the same public API as the original monolithic scheduler, ensuring existing code continues to work without modification.

## Consequences

### Positive
- Improved code organization and readability
- Enhanced testability with isolated components
- Greater flexibility for customization
- Reduced coupling between components
- Easier to add new scheduling features

### Negative
- Slightly increased complexity due to more files
- Need to understand component interactions
- Potential for misconfiguration if components are not properly initialized

## Migration Path

1. Existing code using `EnterpriseScheduler` continues to work without changes
2. New features should be added to appropriate components
3. Tests should be written at the component level
4. Custom implementations can be gradually introduced as needed

## References
- [Single Responsibility Principle](https://en.wikipedia.org/wiki/Single-responsibility_principle)
- [Dependency Injection](https://en.wikipedia.org/wiki/Dependency_injection)
- [Facade Pattern](https://en.wikipedia.org/wiki/Facade_pattern)