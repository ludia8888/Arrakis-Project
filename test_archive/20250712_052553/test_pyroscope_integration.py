#!/usr/bin/env python3
"""
Pyroscope Integration Test
Tests continuous profiling integration with OMS
"""

import json
import time
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, Any, List

class PyroscopeIntegrationTester:
    """Test Pyroscope continuous profiling integration"""
    
    def __init__(self):
        self.base_urls = {
            'pyroscope': 'http://localhost:4040',
            'prometheus': 'http://localhost:9091',
            'grafana': 'http://localhost:3000'
        }
        
    def test_pyroscope_health(self) -> Dict[str, Any]:
        """Test Pyroscope service health"""
        try:
            # Check readiness
            req = urllib.request.Request(f"{self.base_urls['pyroscope']}/ready")
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    content = response.read().decode()
                    ready = content.strip() == "ready"
                    
                    # Get version info
                    version_req = urllib.request.Request(f"{self.base_urls['pyroscope']}/version")
                    try:
                        with urllib.request.urlopen(version_req, timeout=10) as version_resp:
                            version_data = json.loads(version_resp.read().decode())
                            return {
                                "status": "healthy" if ready else "initializing",
                                "ready": ready,
                                "version": version_data.get("version", "unknown"),
                                "build_time": version_data.get("buildTime", "unknown")
                            }
                    except:
                        return {
                            "status": "healthy" if ready else "initializing",
                            "ready": ready
                        }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def test_pyroscope_api(self) -> Dict[str, Any]:
        """Test Pyroscope API endpoints"""
        results = {}
        
        # Test various API endpoints
        endpoints = {
            'status': '/api/v1/status/buildinfo',
            'apps': '/api/v1/apps',
            'label_names': '/api/v1/label-names',
            'label_values': '/api/v1/label-values?label=__name__'
        }
        
        for name, endpoint in endpoints.items():
            try:
                req = urllib.request.Request(f"{self.base_urls['pyroscope']}{endpoint}")
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode())
                        results[name] = {
                            "status": "success",
                            "data_received": True,
                            "sample": str(data)[:100] + "..." if len(str(data)) > 100 else str(data)
                        }
                    else:
                        results[name] = {"status": "error", "status_code": response.status}
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}
        
        return results
    
    def test_prometheus_pyroscope_target(self) -> Dict[str, Any]:
        """Test if Prometheus is scraping Pyroscope metrics"""
        try:
            # Query Prometheus for Pyroscope target
            query = 'up{job="pyroscope"}'
            url = f"{self.base_urls['prometheus']}/api/v1/query?query={query}"
            req = urllib.request.Request(url)
            
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    results = data.get('data', {}).get('result', [])
                    
                    if results:
                        value = float(results[0].get('value', [0, 0])[1])
                        return {
                            "status": "success",
                            "pyroscope_up": value == 1.0,
                            "scraping_active": True
                        }
                    else:
                        return {
                            "status": "not_found",
                            "pyroscope_up": False,
                            "scraping_active": False
                        }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def test_pyroscope_metrics(self) -> Dict[str, Any]:
        """Test Pyroscope metrics endpoint"""
        try:
            req = urllib.request.Request(f"{self.base_urls['pyroscope']}/metrics")
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    metrics_text = response.read().decode()
                    
                    # Count various metric types
                    pyroscope_metrics = [line for line in metrics_text.split('\n') 
                                       if line.startswith('pyroscope_') and not line.startswith('#')]
                    go_metrics = [line for line in metrics_text.split('\n') 
                                if line.startswith('go_') and not line.startswith('#')]
                    process_metrics = [line for line in metrics_text.split('\n') 
                                     if line.startswith('process_') and not line.startswith('#')]
                    
                    return {
                        "status": "success",
                        "total_metrics": len(pyroscope_metrics) + len(go_metrics) + len(process_metrics),
                        "pyroscope_metrics": len(pyroscope_metrics),
                        "go_metrics": len(go_metrics),
                        "process_metrics": len(process_metrics),
                        "sample_metrics": pyroscope_metrics[:3] if pyroscope_metrics else []
                    }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def run_integration_test(self) -> Dict[str, Any]:
        """Run complete Pyroscope integration test"""
        print("🔥 Pyroscope Continuous Profiling Integration Test")
        print("=" * 60)
        
        start_time = datetime.now()
        
        # Test 1: Pyroscope Health
        print("\n🏥 Testing Pyroscope Health...")
        health_result = self.test_pyroscope_health()
        
        # Test 2: Pyroscope API
        print("📡 Testing Pyroscope API Endpoints...")
        api_result = self.test_pyroscope_api()
        
        # Test 3: Prometheus Integration
        print("📊 Testing Prometheus Integration...")
        prometheus_result = self.test_prometheus_pyroscope_target()
        
        # Test 4: Metrics Export
        print("📈 Testing Metrics Export...")
        metrics_result = self.test_pyroscope_metrics()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Calculate overall status
        all_tests = [
            health_result.get('status') == 'healthy',
            all(r.get('status') == 'success' for r in api_result.values()),
            prometheus_result.get('pyroscope_up', False),
            metrics_result.get('status') == 'success'
        ]
        
        success_count = sum(all_tests)
        total_count = len(all_tests)
        success_rate = (success_count / total_count) * 100
        
        # Compile results
        final_results = {
            "test_metadata": {
                "timestamp": start_time.isoformat(),
                "duration_seconds": round(duration, 2),
                "test_type": "pyroscope_integration"
            },
            "pyroscope_health": health_result,
            "api_endpoints": api_result,
            "prometheus_integration": prometheus_result,
            "metrics_export": metrics_result,
            "summary": {
                "tests_passed": f"{success_count}/{total_count}",
                "success_rate": round(success_rate, 1),
                "integration_status": "complete" if success_rate == 100 else 
                                    "partial" if success_rate >= 50 else "failed",
                "ready_for_profiling": health_result.get('ready', False) and success_rate >= 75
            }
        }
        
        return final_results
    
    def print_results(self, results: Dict[str, Any]):
        """Print formatted test results"""
        print("\n" + "=" * 60)
        print("🎯 PYROSCOPE INTEGRATION TEST RESULTS")
        print("=" * 60)
        
        summary = results['summary']
        print(f"📊 Integration Status: {summary['integration_status'].upper()}")
        print(f"✅ Tests Passed: {summary['tests_passed']}")
        print(f"📈 Success Rate: {summary['success_rate']}%")
        print(f"🔥 Ready for Profiling: {'YES' if summary['ready_for_profiling'] else 'NO'}")
        
        # Health Status
        health = results['pyroscope_health']
        print(f"\n🏥 Pyroscope Health:")
        print(f"  Status: {health.get('status', 'unknown')}")
        if 'version' in health:
            print(f"  Version: {health['version']}")
        
        # API Status
        print(f"\n📡 API Endpoints:")
        for endpoint, status in results['api_endpoints'].items():
            icon = "✅" if status.get('status') == 'success' else "❌"
            print(f"  {icon} {endpoint}: {status.get('status', 'unknown')}")
        
        # Prometheus Integration
        prom = results['prometheus_integration']
        print(f"\n📊 Prometheus Integration:")
        print(f"  Status: {prom.get('status', 'unknown')}")
        print(f"  Pyroscope Up: {'YES' if prom.get('pyroscope_up') else 'NO'}")
        print(f"  Scraping Active: {'YES' if prom.get('scraping_active') else 'NO'}")
        
        # Metrics
        metrics = results['metrics_export']
        if metrics.get('status') == 'success':
            print(f"\n📈 Metrics Export:")
            print(f"  Total Metrics: {metrics['total_metrics']}")
            print(f"  Pyroscope Metrics: {metrics['pyroscope_metrics']}")
            print(f"  Go Runtime Metrics: {metrics['go_metrics']}")
            print(f"  Process Metrics: {metrics['process_metrics']}")
        
        print(f"\n🌐 Pyroscope UI: http://localhost:4040")
        print(f"📊 View profiles in real-time at the Pyroscope dashboard")

def main():
    """Main test runner"""
    tester = PyroscopeIntegrationTester()
    results = tester.run_integration_test()
    
    # Print results
    tester.print_results(results)
    
    # Save results
    filename = f"pyroscope_integration_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: {filename}")
    return results

if __name__ == "__main__":
    main()