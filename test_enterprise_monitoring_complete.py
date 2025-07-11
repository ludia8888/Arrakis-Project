#!/usr/bin/env python3
"""
Complete Enterprise Monitoring Stack Integration Test
Tests all components: Prometheus, Grafana, Jaeger, AlertManager + Advanced GC Monitoring
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

class EnterpriseMonitoringTester:
    """Complete Enterprise Monitoring Stack Tester"""
    
    def __init__(self):
        self.base_urls = {
            'oms': 'http://localhost:8000',
            'prometheus': 'http://localhost:9091',
            'grafana': 'http://localhost:3000',
            'jaeger': 'http://localhost:16686',
            'alertmanager': 'http://localhost:9093',
            'node_exporter': 'http://localhost:9100'
        }
        self.results = {}
        
    async def test_monitoring_stack_health(self) -> Dict[str, Any]:
        """Test health of all monitoring components"""
        results = {}
        
        async with aiohttp.ClientSession() as session:
            for service, url in self.base_urls.items():
                try:
                    if service == 'oms':
                        # Test OMS health endpoint
                        async with session.get(f"{url}/health") as resp:
                            if resp.status == 200:
                                results[service] = {"status": "healthy", "status_code": resp.status}
                            else:
                                results[service] = {"status": "unhealthy", "status_code": resp.status}
                    
                    elif service == 'prometheus':
                        # Test Prometheus targets
                        async with session.get(f"{url}/api/v1/targets") as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                active_targets = len([t for t in data.get('data', {}).get('activeTargets', []) 
                                                    if t.get('health') == 'up'])
                                results[service] = {
                                    "status": "healthy", 
                                    "status_code": resp.status,
                                    "active_targets": active_targets
                                }
                            else:
                                results[service] = {"status": "unhealthy", "status_code": resp.status}
                    
                    elif service == 'grafana':
                        # Test Grafana API
                        async with session.get(f"{url}/api/health") as resp:
                            results[service] = {
                                "status": "healthy" if resp.status == 200 else "unhealthy",
                                "status_code": resp.status
                            }
                    
                    elif service == 'jaeger':
                        # Test Jaeger API
                        async with session.get(f"{url}/api/services") as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                services = data.get('data', [])
                                results[service] = {
                                    "status": "healthy",
                                    "status_code": resp.status,
                                    "traced_services": len(services)
                                }
                            else:
                                results[service] = {"status": "unhealthy", "status_code": resp.status}
                    
                    elif service == 'alertmanager':
                        # Test AlertManager status
                        async with session.get(f"{url}/api/v1/status") as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                results[service] = {
                                    "status": "healthy",
                                    "status_code": resp.status,
                                    "version": data.get('data', {}).get('versionInfo', {}).get('version', 'unknown')
                                }
                            else:
                                results[service] = {"status": "unhealthy", "status_code": resp.status}
                    
                    elif service == 'node_exporter':
                        # Test Node Exporter metrics
                        async with session.get(f"{url}/metrics") as resp:
                            if resp.status == 200:
                                text = await resp.text()
                                metric_count = len([line for line in text.split('\n') 
                                                  if line and not line.startswith('#')])
                                results[service] = {
                                    "status": "healthy",
                                    "status_code": resp.status,
                                    "metrics_exported": metric_count
                                }
                            else:
                                results[service] = {"status": "unhealthy", "status_code": resp.status}
                                
                except Exception as e:
                    results[service] = {"status": "error", "error": str(e)}
        
        return results
    
    async def test_advanced_gc_metrics(self) -> Dict[str, Any]:
        """Test Advanced GC Monitoring metrics availability"""
        results = {}
        
        try:
            async with aiohttp.ClientSession() as session:
                # Test OMS metrics endpoint
                async with session.get(f"{self.base_urls['oms']}/metrics") as resp:
                    if resp.status == 200:
                        metrics_text = await resp.text()
                        
                        # Check for advanced GC metrics
                        gc_metrics = [
                            'python_gc_collections_total',
                            'python_gc_collection_time_seconds',
                            'python_gc_objects_collected_total',
                            'python_gc_objects_uncollectable_total',
                            'python_memory_heap_objects_total',
                            'python_memory_heap_size_bytes',
                            'process_memory_rss_bytes',
                            'process_memory_vms_bytes',
                            'python_memory_traced_current_bytes',
                            'python_memory_traced_peak_bytes'
                        ]
                        
                        found_metrics = []
                        for metric in gc_metrics:
                            if metric in metrics_text:
                                found_metrics.append(metric)
                        
                        results = {
                            "status": "success",
                            "total_gc_metrics": len(gc_metrics),
                            "found_gc_metrics": len(found_metrics),
                            "coverage_percentage": (len(found_metrics) / len(gc_metrics)) * 100,
                            "found_metrics": found_metrics,
                            "missing_metrics": [m for m in gc_metrics if m not in found_metrics]
                        }
                    else:
                        results = {"status": "error", "error": f"HTTP {resp.status}"}
                        
        except Exception as e:
            results = {"status": "error", "error": str(e)}
        
        return results
    
    async def test_prometheus_gc_metrics_query(self) -> Dict[str, Any]:
        """Test querying GC metrics from Prometheus"""
        results = {}
        
        try:
            async with aiohttp.ClientSession() as session:
                # Query for GC collection rate
                query = 'rate(python_gc_collections_total[5m])'
                async with session.get(
                    f"{self.base_urls['prometheus']}/api/v1/query",
                    params={'query': query}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results['gc_collection_rate'] = {
                            "status": "success",
                            "query": query,
                            "result_count": len(data.get('data', {}).get('result', []))
                        }
                    else:
                        results['gc_collection_rate'] = {"status": "error", "status_code": resp.status}
                
                # Query for memory usage
                query = 'process_memory_rss_bytes'
                async with session.get(
                    f"{self.base_urls['prometheus']}/api/v1/query",
                    params={'query': query}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result = data.get('data', {}).get('result', [])
                        if result:
                            memory_bytes = float(result[0].get('value', [0, 0])[1])
                            memory_mb = memory_bytes / (1024 * 1024)
                            results['memory_usage'] = {
                                "status": "success",
                                "memory_bytes": memory_bytes,
                                "memory_mb": round(memory_mb, 2)
                            }
                        else:
                            results['memory_usage'] = {"status": "no_data"}
                    else:
                        results['memory_usage'] = {"status": "error", "status_code": resp.status}
                        
        except Exception as e:
            results = {"status": "error", "error": str(e)}
        
        return results
    
    async def test_grafana_dashboards_access(self) -> Dict[str, Any]:
        """Test Grafana dashboard accessibility"""
        results = {}
        
        try:
            async with aiohttp.ClientSession() as session:
                # Test dashboard search (without auth for now)
                async with session.get(f"{self.base_urls['grafana']}/api/search") as resp:
                    if resp.status == 200:
                        dashboards = await resp.json()
                        results = {
                            "status": "success",
                            "status_code": resp.status,
                            "dashboard_count": len(dashboards),
                            "dashboards": [{"title": d.get("title"), "uid": d.get("uid")} 
                                         for d in dashboards[:5]]  # First 5 dashboards
                        }
                    elif resp.status == 401:
                        results = {
                            "status": "auth_required",
                            "status_code": resp.status,
                            "message": "Authentication required - dashboard accessible via UI"
                        }
                    else:
                        results = {"status": "error", "status_code": resp.status}
                        
        except Exception as e:
            results = {"status": "error", "error": str(e)}
        
        return results
    
    async def test_resilience_metrics_integration(self) -> Dict[str, Any]:
        """Test resilience metrics are properly integrated"""
        results = {}
        
        try:
            async with aiohttp.ClientSession() as session:
                # Test circuit breaker metrics
                async with session.get(f"{self.base_urls['oms']}/metrics") as resp:
                    if resp.status == 200:
                        metrics_text = await resp.text()
                        
                        resilience_metrics = [
                            'circuit_breaker_calls_total',
                            'circuit_breaker_state',
                            'etag_cache_requests_total',
                            'redis_operations_total',
                            'backpressure_queue_size'
                        ]
                        
                        found_resilience = []
                        for metric in resilience_metrics:
                            if metric in metrics_text:
                                found_resilience.append(metric)
                        
                        results = {
                            "status": "success",
                            "resilience_metrics_found": found_resilience,
                            "resilience_coverage": len(found_resilience),
                            "total_resilience_metrics": len(resilience_metrics)
                        }
                    else:
                        results = {"status": "error", "status_code": resp.status}
                        
        except Exception as e:
            results = {"status": "error", "error": str(e)}
        
        return results
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run complete enterprise monitoring integration test"""
        print("🚀 Starting Enterprise Monitoring Stack Integration Test")
        print("=" * 70)
        
        start_time = datetime.now()
        
        # Test 1: Monitoring Stack Health
        print("\n🏥 Testing Monitoring Stack Health...")
        health_results = await self.test_monitoring_stack_health()
        
        # Test 2: Advanced GC Metrics
        print("\n🗑️ Testing Advanced GC Monitoring...")
        gc_results = await self.test_advanced_gc_metrics()
        
        # Test 3: Prometheus GC Queries
        print("\n📊 Testing Prometheus GC Metrics Queries...")
        prometheus_gc_results = await self.test_prometheus_gc_metrics_query()
        
        # Test 4: Grafana Dashboard Access
        print("\n📈 Testing Grafana Dashboard Access...")
        grafana_results = await self.test_grafana_dashboards_access()
        
        # Test 5: Resilience Metrics Integration
        print("\n🛡️ Testing Resilience Metrics Integration...")
        resilience_results = await self.test_resilience_metrics_integration()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Compile final results
        final_results = {
            "test_metadata": {
                "timestamp": start_time.isoformat(),
                "duration_seconds": duration,
                "test_type": "enterprise_monitoring_complete"
            },
            "monitoring_stack_health": health_results,
            "advanced_gc_monitoring": gc_results,
            "prometheus_gc_queries": prometheus_gc_results,
            "grafana_access": grafana_results,
            "resilience_integration": resilience_results,
            "overall_assessment": self._assess_overall_status(
                health_results, gc_results, prometheus_gc_results, 
                grafana_results, resilience_results
            )
        }
        
        return final_results
    
    def _assess_overall_status(self, health, gc, prometheus_gc, grafana, resilience) -> Dict[str, Any]:
        """Assess overall enterprise monitoring status"""
        
        # Count healthy services
        healthy_services = len([s for s in health.values() if s.get('status') == 'healthy'])
        total_services = len(health)
        
        # Calculate GC monitoring score
        gc_coverage = gc.get('coverage_percentage', 0)
        
        # Calculate resilience coverage
        resilience_coverage = resilience.get('resilience_coverage', 0)
        
        # Overall score calculation
        service_health_score = (healthy_services / total_services) * 100 if total_services > 0 else 0
        overall_score = (service_health_score + gc_coverage + (resilience_coverage * 10)) / 3
        
        status = "excellent" if overall_score >= 85 else \
                "good" if overall_score >= 70 else \
                "needs_improvement" if overall_score >= 50 else "critical"
        
        return {
            "status": status,
            "overall_score": round(overall_score, 1),
            "service_health_score": round(service_health_score, 1),
            "gc_monitoring_score": round(gc_coverage, 1),
            "resilience_monitoring_score": resilience_coverage * 10,
            "healthy_services": f"{healthy_services}/{total_services}",
            "recommendations": self._generate_recommendations(health, gc, resilience)
        }
    
    def _generate_recommendations(self, health, gc, resilience) -> List[str]:
        """Generate improvement recommendations"""
        recommendations = []
        
        # Check for unhealthy services
        unhealthy = [name for name, data in health.items() if data.get('status') != 'healthy']
        if unhealthy:
            recommendations.append(f"Fix unhealthy services: {', '.join(unhealthy)}")
        
        # Check GC monitoring coverage
        if gc.get('coverage_percentage', 0) < 80:
            missing = gc.get('missing_metrics', [])
            recommendations.append(f"Enable missing GC metrics: {', '.join(missing[:3])}")
        
        # Check resilience coverage
        if resilience.get('resilience_coverage', 0) < 4:
            recommendations.append("Activate more resilience monitoring mechanisms")
        
        if not recommendations:
            recommendations.append("All systems operational - consider Pyroscope integration for profiling")
        
        return recommendations

async def main():
    """Main test runner"""
    tester = EnterpriseMonitoringTester()
    results = await tester.run_comprehensive_test()
    
    # Save results
    filename = f"enterprise_monitoring_complete_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 70)
    print("🎯 ENTERPRISE MONITORING INTEGRATION TEST COMPLETE")
    print("=" * 70)
    
    assessment = results['overall_assessment']
    print(f"📊 Overall Status: {assessment['status'].upper()}")
    print(f"🎯 Overall Score: {assessment['overall_score']}/100")
    print(f"🏥 Service Health: {assessment['service_health_score']}/100")
    print(f"🗑️ GC Monitoring: {assessment['gc_monitoring_score']}/100")
    print(f"🛡️ Resilience: {assessment['resilience_monitoring_score']}/100")
    
    print(f"\n📋 Service Status:")
    for service, data in results['monitoring_stack_health'].items():
        status_icon = "✅" if data.get('status') == 'healthy' else "❌"
        print(f"  {status_icon} {service.upper()}: {data.get('status', 'unknown')}")
    
    print(f"\n🎯 GC Monitoring Coverage: {results['advanced_gc_monitoring'].get('coverage_percentage', 0):.1f}%")
    
    if assessment['recommendations']:
        print(f"\n💡 Recommendations:")
        for rec in assessment['recommendations']:
            print(f"  • {rec}")
    
    print(f"\n📄 Detailed results saved to: {filename}")
    return results

if __name__ == "__main__":
    asyncio.run(main())