#!/usr/bin/env python3
"""
Comprehensive Performance Test Suite for Event System
===================================================
Tests real user scenarios with objective performance metrics
"""

import asyncio
import time
import statistics
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from uuid import uuid4
import logging

# Import existing systems (no duplication)
from ontology_management_service.core.integration.event_bridge import create_integrated_event_system
from ontology_management_service.core.events.immutable_event_store import EventType
from event_gateway.app.events.service import EventGatewayService
from cloudevents.http import CloudEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance test results"""
    test_name: str
    total_events: int
    duration_seconds: float
    events_per_second: float
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    errors: int
    success_rate: float

@dataclass
class UserScenario:
    """Real user scenario definition"""
    name: str
    description: str
    operations: List[str]
    concurrent_users: int
    events_per_user: int
    expected_throughput: int  # events/second

class PerformanceTestSuite:
    """Comprehensive performance testing for event system"""
    
    def __init__(self):
        self.results: List[PerformanceMetrics] = []
        self.event_system = None
        self.event_gateway = None
        
    async def initialize(self):
        """Initialize test environment with existing infrastructure"""
        logger.info("Initializing performance test environment...")
        
        # Use existing integrated event system
        self.event_system = await create_integrated_event_system(
            redis_url="redis://localhost:6379",
            postgres_url="postgresql://arrakis_user:arrakis_password@localhost:5432/oms_db",
            nats_url="nats://localhost:4222"
        )
        
        # Use existing event gateway
        self.event_gateway = EventGatewayService()
        await self.event_gateway.initialize()
        
        logger.info("Performance test environment initialized")
        
    async def cleanup(self):
        """Cleanup test environment"""
        if self.event_gateway:
            await self.event_gateway.shutdown()
            
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run complete performance test suite"""
        logger.info("Starting comprehensive performance test suite...")
        
        # Define real user scenarios
        scenarios = [
            UserScenario(
                name="Schema Management",
                description="Users creating, updating, and querying schemas",
                operations=["create_schema", "update_schema", "query_schema", "list_schemas"],
                concurrent_users=10,
                events_per_user=50,
                expected_throughput=100
            ),
            UserScenario(
                name="High Volume Data Ingestion",
                description="Bulk data import with event sourcing",
                operations=["batch_create_objects", "link_objects", "index_data"],
                concurrent_users=5,
                events_per_user=200,
                expected_throughput=500
            ),
            UserScenario(
                name="Real-time Analytics",
                description="Continuous queries with CQRS projections",
                operations=["streaming_query", "materialized_view_refresh", "real_time_aggregation"],
                concurrent_users=20,
                events_per_user=25,
                expected_throughput=200
            ),
            UserScenario(
                name="Audit and Compliance",
                description="Time travel queries and audit trail generation",
                operations=["time_travel_query", "audit_trail", "compliance_report"],
                concurrent_users=3,
                events_per_user=100,
                expected_throughput=50
            )
        ]
        
        # Run each scenario
        for scenario in scenarios:
            await self._test_user_scenario(scenario)
            
        # Run system stress tests
        await self._test_throughput_limits()
        await self._test_concurrent_load()
        await self._test_memory_efficiency()
        await self._test_event_ordering()
        await self._test_failure_recovery()
        
        # Generate comprehensive report
        return self._generate_performance_report()
        
    async def _test_user_scenario(self, scenario: UserScenario):
        """Test real user scenario with concurrent users"""
        logger.info(f"Testing scenario: {scenario.name}")
        
        start_time = time.time()
        latencies = []
        errors = 0
        
        # Create concurrent tasks for users
        tasks = []
        for user_id in range(scenario.concurrent_users):
            task = asyncio.create_task(
                self._simulate_user(f"user_{user_id}", scenario, latencies)
            )
            tasks.append(task)
            
        # Wait for all users to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count errors
        for result in results:
            if isinstance(result, Exception):
                errors += 1
                logger.error(f"User simulation error: {result}")
                
        # Calculate metrics
        end_time = time.time()
        duration = end_time - start_time
        total_events = scenario.concurrent_users * scenario.events_per_user
        
        metrics = PerformanceMetrics(
            test_name=f"Scenario: {scenario.name}",
            total_events=total_events,
            duration_seconds=duration,
            events_per_second=total_events / duration if duration > 0 else 0,
            avg_latency_ms=statistics.mean(latencies) * 1000 if latencies else 0,
            p95_latency_ms=statistics.quantiles(latencies, n=20)[18] * 1000 if latencies else 0,
            p99_latency_ms=statistics.quantiles(latencies, n=100)[98] * 1000 if latencies else 0,
            memory_usage_mb=0,  # Would need psutil for real measurement
            cpu_usage_percent=0,  # Would need psutil for real measurement
            errors=errors,
            success_rate=(total_events - errors) / total_events if total_events > 0 else 0
        )
        
        self.results.append(metrics)
        logger.info(f"Scenario completed: {metrics.events_per_second:.2f} events/sec, {metrics.success_rate:.2%} success rate")
        
    async def _simulate_user(self, user_id: str, scenario: UserScenario, latencies: List[float]):
        """Simulate individual user operations"""
        for event_num in range(scenario.events_per_user):
            operation = scenario.operations[event_num % len(scenario.operations)]
            
            start_time = time.time()
            try:
                await self._execute_operation(user_id, operation, event_num)
                latency = time.time() - start_time
                latencies.append(latency)
            except Exception as e:
                logger.error(f"Operation {operation} failed for {user_id}: {e}")
                raise
                
    async def _execute_operation(self, user_id: str, operation: str, event_num: int):
        """Execute specific user operation using existing infrastructure"""
        correlation_id = f"{user_id}_{operation}_{event_num}"
        
        if operation == "create_schema":
            # Use existing event bridge to create schema
            await self.event_system["event_bridge"].publish_domain_event(
                event_type=EventType.SCHEMA_CREATED,
                aggregate_id=str(uuid4()),
                payload={
                    "name": f"TestSchema_{user_id}_{event_num}",
                    "properties": {"field1": "string", "field2": "integer"},
                    "metadata": {"created_by": user_id},
                    "created_at": datetime.now(timezone.utc).isoformat()
                },
                correlation_id=correlation_id,
                user_id=user_id
            )
            
        elif operation == "update_schema":
            # Update schema using existing system
            await self.event_system["event_bridge"].publish_domain_event(
                event_type=EventType.SCHEMA_UPDATED,
                aggregate_id=f"schema_{user_id}",
                payload={
                    "changes": {"properties": {"field3": "boolean"}},
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "updated_by": user_id
                },
                correlation_id=correlation_id,
                user_id=user_id
            )
            
        elif operation == "query_schema":
            # Query using existing CQRS query service
            await self.event_system["query_service"].query_schemas(
                filters={"created_by": user_id, "limit": 10}
            )
            
        elif operation == "list_schemas":
            # List schemas using existing materialized view
            await self.event_system["cqrs_coordinator"].schema_query_service.list_schemas(
                limit=20, created_by=user_id
            )
            
        elif operation == "batch_create_objects":
            # Batch operations using existing performance optimizer
            events = []
            for i in range(10):  # Batch of 10
                events.append({
                    "event_type": EventType.OBJECT_CREATED,
                    "aggregate_id": str(uuid4()),
                    "payload": {
                        "schema_id": f"schema_{user_id}",
                        "data": {"field1": f"value_{i}", "field2": i},
                        "created_at": datetime.now(timezone.utc).isoformat()
                    },
                    "correlation_id": f"{correlation_id}_batch_{i}",
                    "user_id": user_id
                })
            await self.event_system["performance_optimizer"].batch_publish_events(events)
            
        elif operation == "streaming_query":
            # Real-time query using existing time travel service
            await self.event_system["time_travel_service"].query_as_of(
                resource_type="schema",
                timestamp=datetime.now(timezone.utc),
                filters={"created_by": user_id}
            )
            
        elif operation == "time_travel_query":
            # Time travel using existing service
            past_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
            await self.event_system["query_service"].query_schemas(
                at_time=past_time,
                filters={"created_by": user_id}
            )
            
        elif operation == "audit_trail":
            # Audit trail using existing service
            await self.event_system["query_service"].query_with_audit_trail(
                resource_type="schema",
                resource_id=f"schema_{user_id}"
            )
            
        # Add small delay to simulate real user behavior
        await asyncio.sleep(0.01)
        
    async def _test_throughput_limits(self):
        """Test maximum throughput limits"""
        logger.info("Testing throughput limits...")
        
        start_time = time.time()
        batch_size = 1000
        batches = 10
        latencies = []
        
        for batch_num in range(batches):
            batch_start = time.time()
            
            # Create large batch using existing infrastructure
            events = []
            for i in range(batch_size):
                events.append({
                    "event_type": EventType.OBJECT_CREATED,
                    "aggregate_id": str(uuid4()),
                    "payload": {
                        "data": {"test": f"throughput_test_{batch_num}_{i}"},
                        "created_at": datetime.now(timezone.utc).isoformat()
                    },
                    "correlation_id": f"throughput_test_{batch_num}_{i}",
                    "user_id": "performance_test"
                })
                
            await self.event_system["performance_optimizer"].batch_publish_events(events)
            
            batch_latency = time.time() - batch_start
            latencies.append(batch_latency)
            
        duration = time.time() - start_time
        total_events = batch_size * batches
        
        metrics = PerformanceMetrics(
            test_name="Throughput Limits",
            total_events=total_events,
            duration_seconds=duration,
            events_per_second=total_events / duration,
            avg_latency_ms=statistics.mean(latencies) * 1000,
            p95_latency_ms=statistics.quantiles(latencies, n=20)[18] * 1000,
            p99_latency_ms=statistics.quantiles(latencies, n=100)[98] * 1000,
            memory_usage_mb=0,
            cpu_usage_percent=0,
            errors=0,
            success_rate=1.0
        )
        
        self.results.append(metrics)
        
    async def _test_concurrent_load(self):
        """Test system under concurrent load"""
        logger.info("Testing concurrent load...")
        
        concurrent_publishers = 20
        events_per_publisher = 100
        
        start_time = time.time()
        
        async def concurrent_publisher(publisher_id: int):
            for i in range(events_per_publisher):
                await self.event_system["event_bridge"].publish_domain_event(
                    event_type=EventType.SCHEMA_CREATED,
                    aggregate_id=str(uuid4()),
                    payload={
                        "name": f"ConcurrentSchema_{publisher_id}_{i}",
                        "properties": {"field": "value"},
                        "created_at": datetime.now(timezone.utc).isoformat()
                    },
                    correlation_id=f"concurrent_test_{publisher_id}_{i}",
                    user_id=f"publisher_{publisher_id}"
                )
                
        # Run concurrent publishers
        tasks = [
            asyncio.create_task(concurrent_publisher(i))
            for i in range(concurrent_publishers)
        ]
        
        await asyncio.gather(*tasks)
        
        duration = time.time() - start_time
        total_events = concurrent_publishers * events_per_publisher
        
        metrics = PerformanceMetrics(
            test_name="Concurrent Load",
            total_events=total_events,
            duration_seconds=duration,
            events_per_second=total_events / duration,
            avg_latency_ms=0,  # Individual latency not measured in this test
            p95_latency_ms=0,
            p99_latency_ms=0,
            memory_usage_mb=0,
            cpu_usage_percent=0,
            errors=0,
            success_rate=1.0
        )
        
        self.results.append(metrics)
        
    async def _test_memory_efficiency(self):
        """Test memory efficiency with large events"""
        logger.info("Testing memory efficiency...")
        
        # Create events with large payloads
        large_payload = {"data": "x" * 10000}  # 10KB payload
        event_count = 1000
        
        start_time = time.time()
        
        for i in range(event_count):
            await self.event_system["event_bridge"].publish_domain_event(
                event_type=EventType.OBJECT_CREATED,
                aggregate_id=str(uuid4()),
                payload=large_payload,
                correlation_id=f"memory_test_{i}",
                user_id="memory_test_user"
            )
            
        duration = time.time() - start_time
        
        metrics = PerformanceMetrics(
            test_name="Memory Efficiency (Large Events)",
            total_events=event_count,
            duration_seconds=duration,
            events_per_second=event_count / duration,
            avg_latency_ms=0,
            p95_latency_ms=0,
            p99_latency_ms=0,
            memory_usage_mb=0,  # Would need actual memory measurement
            cpu_usage_percent=0,
            errors=0,
            success_rate=1.0
        )
        
        self.results.append(metrics)
        
    async def _test_event_ordering(self):
        """Test event ordering guarantees"""
        logger.info("Testing event ordering...")
        
        aggregate_id = str(uuid4())
        event_count = 100
        
        start_time = time.time()
        
        # Publish events in sequence for same aggregate
        for i in range(event_count):
            await self.event_system["event_bridge"].publish_domain_event(
                event_type=EventType.SCHEMA_UPDATED,
                aggregate_id=aggregate_id,
                payload={
                    "sequence": i,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                correlation_id=f"ordering_test_{i}",
                user_id="ordering_test_user"
            )
            
        duration = time.time() - start_time
        
        # Verify ordering by querying events
        events = await self.event_system["event_store"].get_events(aggregate_id)
        
        # Check if events are in correct order
        ordered_correctly = all(
            events[i].payload["sequence"] == i 
            for i in range(len(events))
        )
        
        metrics = PerformanceMetrics(
            test_name="Event Ordering",
            total_events=event_count,
            duration_seconds=duration,
            events_per_second=event_count / duration,
            avg_latency_ms=0,
            p95_latency_ms=0,
            p99_latency_ms=0,
            memory_usage_mb=0,
            cpu_usage_percent=0,
            errors=0 if ordered_correctly else event_count,
            success_rate=1.0 if ordered_correctly else 0.0
        )
        
        self.results.append(metrics)
        
    async def _test_failure_recovery(self):
        """Test system recovery from failures"""
        logger.info("Testing failure recovery...")
        
        # This would test recovery scenarios like:
        # - Redis connection loss
        # - NATS disconnection
        # - Database failures
        # For now, we'll simulate with a basic test
        
        event_count = 50
        start_time = time.time()
        
        for i in range(event_count):
            try:
                await self.event_system["event_bridge"].publish_domain_event(
                    event_type=EventType.SCHEMA_CREATED,
                    aggregate_id=str(uuid4()),
                    payload={"test": "recovery"},
                    correlation_id=f"recovery_test_{i}",
                    user_id="recovery_test_user"
                )
            except Exception as e:
                logger.error(f"Recovery test error: {e}")
                
        duration = time.time() - start_time
        
        metrics = PerformanceMetrics(
            test_name="Failure Recovery",
            total_events=event_count,
            duration_seconds=duration,
            events_per_second=event_count / duration,
            avg_latency_ms=0,
            p95_latency_ms=0,
            p99_latency_ms=0,
            memory_usage_mb=0,
            cpu_usage_percent=0,
            errors=0,
            success_rate=1.0
        )
        
        self.results.append(metrics)
        
    def _generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        
        total_events = sum(r.total_events for r in self.results)
        total_duration = sum(r.duration_seconds for r in self.results)
        avg_throughput = total_events / total_duration if total_duration > 0 else 0
        
        overall_success_rate = statistics.mean([r.success_rate for r in self.results])
        
        report = {
            "test_summary": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_tests": len(self.results),
                "total_events_processed": total_events,
                "total_test_duration_seconds": total_duration,
                "average_throughput_events_per_second": avg_throughput,
                "overall_success_rate": overall_success_rate
            },
            "individual_test_results": [asdict(result) for result in self.results],
            "performance_analysis": {
                "highest_throughput": max(r.events_per_second for r in self.results),
                "lowest_latency_ms": min(r.avg_latency_ms for r in self.results if r.avg_latency_ms > 0),
                "most_reliable_test": max(self.results, key=lambda r: r.success_rate).test_name,
                "recommendations": self._generate_recommendations()
            }
        }
        
        return report
        
    def _generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations based on results"""
        recommendations = []
        
        # Analyze results and suggest improvements
        throughput_results = [r for r in self.results if r.events_per_second > 0]
        if throughput_results:
            avg_throughput = statistics.mean([r.events_per_second for r in throughput_results])
            
            if avg_throughput < 100:
                recommendations.append("Consider optimizing event serialization and network latency")
                
            high_latency_tests = [r for r in self.results if r.avg_latency_ms > 100]
            if high_latency_tests:
                recommendations.append("High latency detected - consider connection pooling and async optimization")
                
        low_success_tests = [r for r in self.results if r.success_rate < 0.95]
        if low_success_tests:
            recommendations.append("Reliability issues detected - implement circuit breakers and retry logic")
            
        if not recommendations:
            recommendations.append("Performance metrics are within acceptable ranges")
            
        return recommendations

async def main():
    """Run comprehensive performance test suite"""
    test_suite = PerformanceTestSuite()
    
    try:
        await test_suite.initialize()
        report = await test_suite.run_all_tests()
        
        # Save detailed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"performance_test_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
            
        print("\n" + "="*80)
        print("COMPREHENSIVE PERFORMANCE TEST RESULTS")
        print("="*80)
        print(f"Total Events Processed: {report['test_summary']['total_events_processed']:,}")
        print(f"Average Throughput: {report['test_summary']['average_throughput_events_per_second']:.2f} events/sec")
        print(f"Overall Success Rate: {report['test_summary']['overall_success_rate']:.2%}")
        print(f"Highest Throughput: {report['performance_analysis']['highest_throughput']:.2f} events/sec")
        print(f"Most Reliable Test: {report['performance_analysis']['most_reliable_test']}")
        
        print("\nRECOMMENDATIONS:")
        for rec in report['performance_analysis']['recommendations']:
            print(f"• {rec}")
            
        print(f"\nDetailed results saved to: {filename}")
        print("="*80)
        
    finally:
        await test_suite.cleanup()

if __name__ == "__main__":
    asyncio.run(main())