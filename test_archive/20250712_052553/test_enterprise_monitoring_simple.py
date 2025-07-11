#!/usr/bin/env python3
"""
Simple Enterprise Monitoring Stack Integration Test
Tests all components using standard library only
"""

import json
import time
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, Any, List

class EnterpriseMonitoringTester:
    """Enterprise Monitoring Stack Tester"""
    
    def __init__(self):
        self.base_urls = {
            'prometheus': 'http://localhost:9091',
            'grafana': 'http://localhost:3000',
            'jaeger': 'http://localhost:16686',
            'alertmanager': 'http://localhost:9093',
            'node_exporter': 'http://localhost:9100'
        }
        
    def test_service_health(self, service: str, url: str) -> Dict[str, Any]:
        """Test individual service health"""
        try:
            if service == 'prometheus':
                # Test Prometheus targets
                req = urllib.request.Request(f"{url}/api/v1/targets")
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode())
                        active_targets = len([t for t in data.get('data', {}).get('activeTargets', []) 
                                            if t.get('health') == 'up'])
                        return {
                            "status": "healthy", 
                            "status_code": response.status,
                            "active_targets": active_targets
                        }
            
            elif service == 'grafana':
                # Test Grafana health
                req = urllib.request.Request(f"{url}/api/health")
                with urllib.request.urlopen(req, timeout=10) as response:
                    return {
                        "status": "healthy" if response.status == 200 else "unhealthy",
                        "status_code": response.status
                    }
            
            elif service == 'jaeger':
                # Test Jaeger services API
                req = urllib.request.Request(f"{url}/api/services")
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode())
                        services = data.get('data', [])
                        return {
                            "status": "healthy",
                            "status_code": response.status,
                            "traced_services": len(services)
                        }
            
            elif service == 'alertmanager':
                # Test AlertManager status
                req = urllib.request.Request(f"{url}/api/v1/status")
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode())
                        return {
                            "status": "healthy",
                            "status_code": response.status,
                            "version": data.get('data', {}).get('versionInfo', {}).get('version', 'unknown')
                        }
            
            elif service == 'node_exporter':
                # Test Node Exporter metrics
                req = urllib.request.Request(f"{url}/metrics")
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        text = response.read().decode()
                        metric_count = len([line for line in text.split('\n') 
                                          if line and not line.startswith('#')])
                        return {
                            "status": "healthy",
                            "status_code": response.status,
                            "metrics_exported": metric_count
                        }
            
            return {"status": "unknown", "error": "No test implemented"}
            
        except urllib.error.HTTPError as e:
            return {"status": "http_error", "status_code": e.code, "error": str(e)}
        except urllib.error.URLError as e:
            return {"status": "connection_error", "error": str(e)}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def test_prometheus_queries(self) -> Dict[str, Any]:
        """Test Prometheus query capabilities"""
        results = {}
        prometheus_url = self.base_urls['prometheus']
        
        # Test queries for GC and system metrics
        queries = {
            'up_targets': 'up',
            'gc_collections': 'python_gc_collections_total',
            'memory_usage': 'process_memory_rss_bytes',
            'cpu_usage': 'process_cpu_seconds_total'
        }
        
        for query_name, query in queries.items():
            try:
                url = f"{prometheus_url}/api/v1/query?query={query}"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode())
                        result_count = len(data.get('data', {}).get('result', []))
                        results[query_name] = {
                            "status": "success",
                            "result_count": result_count,
                            "query": query
                        }
                    else:
                        results[query_name] = {"status": "error", "status_code": response.status}
            except Exception as e:
                results[query_name] = {"status": "error", "error": str(e)}
        
        return results
    
    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run complete enterprise monitoring test"""
        print("🚀 Enterprise Monitoring Stack Integration Test")
        print("=" * 60)
        
        start_time = datetime.now()
        
        # Test 1: Service Health Check
        print("\n🏥 Testing Service Health...")
        health_results = {}
        for service, url in self.base_urls.items():
            print(f"  Testing {service}...")
            health_results[service] = self.test_service_health(service, url)
        
        # Test 2: Prometheus Query Capabilities
        print("\n📊 Testing Prometheus Queries...")
        prometheus_results = self.test_prometheus_queries()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Calculate overall status
        healthy_services = len([s for s in health_results.values() if s.get('status') == 'healthy'])
        total_services = len(health_results)
        health_percentage = (healthy_services / total_services) * 100 if total_services > 0 else 0
        
        successful_queries = len([q for q in prometheus_results.values() if q.get('status') == 'success'])
        total_queries = len(prometheus_results)
        query_success_rate = (successful_queries / total_queries) * 100 if total_queries > 0 else 0
        
        overall_score = (health_percentage + query_success_rate) / 2
        
        # Compile results
        final_results = {
            "test_metadata": {
                "timestamp": start_time.isoformat(),
                "duration_seconds": round(duration, 2),
                "test_type": "enterprise_monitoring_simple"
            },
            "service_health": health_results,
            "prometheus_queries": prometheus_results,
            "summary": {
                "healthy_services": f"{healthy_services}/{total_services}",
                "health_percentage": round(health_percentage, 1),
                "successful_queries": f"{successful_queries}/{total_queries}",
                "query_success_rate": round(query_success_rate, 1),
                "overall_score": round(overall_score, 1),
                "status": "excellent" if overall_score >= 85 else 
                         "good" if overall_score >= 70 else 
                         "needs_improvement" if overall_score >= 50 else "critical"
            }
        }
        
        return final_results
    
    def print_results(self, results: Dict[str, Any]):
        """Print formatted test results"""
        print("\n" + "=" * 60)
        print("🎯 ENTERPRISE MONITORING TEST RESULTS")
        print("=" * 60)
        
        summary = results['summary']
        print(f"📊 Overall Status: {summary['status'].upper()}")
        print(f"🎯 Overall Score: {summary['overall_score']}/100")
        print(f"🏥 Service Health: {summary['health_percentage']}/100 ({summary['healthy_services']})")
        print(f"📈 Query Success: {summary['query_success_rate']}/100 ({summary['successful_queries']})")
        
        print(f"\n📋 Detailed Service Status:")
        for service, data in results['service_health'].items():
            status = data.get('status', 'unknown')
            status_icon = "✅" if status == 'healthy' else "❌" if status in ['unhealthy', 'error'] else "⚠️"
            extra_info = ""
            
            if 'active_targets' in data:
                extra_info = f" ({data['active_targets']} targets)"
            elif 'traced_services' in data:
                extra_info = f" ({data['traced_services']} services)"
            elif 'metrics_exported' in data:
                extra_info = f" ({data['metrics_exported']} metrics)"
            elif 'version' in data:
                extra_info = f" (v{data['version']})"
            
            print(f"  {status_icon} {service.upper()}: {status}{extra_info}")
        
        print(f"\n📊 Prometheus Query Results:")
        for query_name, data in results['prometheus_queries'].items():
            status = data.get('status', 'unknown')
            result_count = data.get('result_count', 0)
            status_icon = "✅" if status == 'success' else "❌"
            print(f"  {status_icon} {query_name}: {status} ({result_count} results)")
        
        if summary['status'] != 'excellent':
            print(f"\n💡 Recommendations:")
            unhealthy = [name for name, data in results['service_health'].items() 
                        if data.get('status') != 'healthy']
            if unhealthy:
                print(f"  • Fix unhealthy services: {', '.join(unhealthy)}")
            
            failed_queries = [name for name, data in results['prometheus_queries'].items() 
                            if data.get('status') != 'success']
            if failed_queries:
                print(f"  • Check Prometheus configuration for: {', '.join(failed_queries)}")

def main():
    """Main test runner"""
    tester = EnterpriseMonitoringTester()
    results = tester.run_comprehensive_test()
    
    # Print results
    tester.print_results(results)
    
    # Save results
    filename = f"enterprise_monitoring_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: {filename}")
    return results

if __name__ == "__main__":
    main()