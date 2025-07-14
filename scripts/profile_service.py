#!/usr/bin/env python3
"""
Production-ready performance profiling tool for Arrakis microservices.
Integrates with snakeviz for interactive visualization of performance bottlenecks.
"""

import os
import sys
import cProfile
import pstats
import io
import json
import argparse
import subprocess
import tempfile
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime
import importlib.util
import logging
import asyncio
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ServiceProfiler:
    """Performance profiler for microservices with snakeviz integration."""
    
    SERVICES = {
        'ontology-management-service': {
            'main_module': 'api.main',
            'startup_function': 'create_app',
            'test_endpoints': ['/docs', '/health', '/api/v1/schemas'],
            'async': True
        },
        'user-service': {
            'main_module': 'app.main',
            'startup_function': 'create_app',
            'test_endpoints': ['/docs', '/health', '/api/v1/users'],
            'async': True
        },
        'audit-service': {
            'main_module': 'app.main',
            'startup_function': 'create_app',
            'test_endpoints': ['/docs', '/health', '/api/v1/audit/logs'],
            'async': True
        },
        'data-kernel-service': {
            'main_module': 'app.main',
            'startup_function': 'create_app',
            'test_endpoints': ['/docs', '/health', '/api/v1/query'],
            'async': True
        },
        'embedding-service': {
            'main_module': 'app.main',
            'startup_function': 'create_app',
            'test_endpoints': ['/docs', '/health', '/api/v1/embeddings'],
            'async': True
        },
        'scheduler-service': {
            'main_module': 'app.main',
            'startup_function': 'create_app',
            'test_endpoints': ['/docs', '/health', '/api/v1/jobs'],
            'async': True
        },
        'event-gateway': {
            'main_module': 'app.main',
            'startup_function': 'create_app',
            'test_endpoints': ['/docs', '/health', '/api/v1/events'],
            'async': True
        }
    }
    
    def __init__(self, output_dir: str = 'docs/dependencies'):
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Check for snakeviz
        self._check_snakeviz()
    
    def _check_snakeviz(self):
        """Check if snakeviz is installed."""
        try:
            import snakeviz
        except ImportError:
            logger.warning("snakeviz not installed. Installing...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'snakeviz'], check=True)
    
    def profile_service(self, service: str, profile_type: str = 'startup') -> Dict:
        """Profile a specific service."""
        if service not in self.SERVICES:
            raise ValueError(f"Unknown service: {service}")
        
        logger.info(f"Profiling {service} ({profile_type})...")
        
        service_config = self.SERVICES[service]
        service_path = Path(service)
        
        if not service_path.exists():
            raise FileNotFoundError(f"Service directory not found: {service_path}")
        
        # Create output directory
        profile_dir = self.output_dir / service / 'profile'
        profile_dir.mkdir(parents=True, exist_ok=True)
        
        # Add service to Python path
        sys.path.insert(0, str(service_path))
        
        try:
            if profile_type == 'startup':
                return self._profile_startup(service, service_config, profile_dir)
            elif profile_type == 'endpoints':
                return self._profile_endpoints(service, service_config, profile_dir)
            elif profile_type == 'load':
                return self._profile_load(service, service_config, profile_dir)
            else:
                raise ValueError(f"Unknown profile type: {profile_type}")
        finally:
            # Clean up Python path
            sys.path.remove(str(service_path))
    
    def _profile_startup(self, service: str, config: Dict, output_dir: Path) -> Dict:
        """Profile service startup."""
        logger.info("Profiling service startup...")
        
        profiler = cProfile.Profile()
        profiler.enable()
        
        start_time = time.time()
        try:
            # Import main module
            module_spec = importlib.util.find_spec(config['main_module'])
            if module_spec is None:
                raise ImportError(f"Cannot find module: {config['main_module']}")
            
            module = importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(module)
            
            # Get startup function
            startup_func = getattr(module, config['startup_function'], None)
            if startup_func is None:
                raise AttributeError(f"Cannot find function: {config['startup_function']}")
            
            # Call startup function
            if config.get('async'):
                # Handle async startup
                async def run_startup():
                    if asyncio.iscoroutinefunction(startup_func):
                        return await startup_func()
                    else:
                        return startup_func()
                
                app = asyncio.run(run_startup())
            else:
                app = startup_func()
            
            startup_time = time.time() - start_time
            
        except Exception as e:
            logger.error(f"Error during startup profiling: {e}")
            startup_time = time.time() - start_time
            app = None
        finally:
            profiler.disable()
        
        # Save profile data
        profile_file = output_dir / 'startup.prof'
        profiler.dump_stats(str(profile_file))
        
        # Generate reports
        stats = pstats.Stats(profiler)
        
        # Text report
        text_report = output_dir / 'startup_report.txt'
        with open(text_report, 'w') as f:
            stats_stream = io.StringIO()
            stats.stream = stats_stream
            stats.strip_dirs()
            stats.sort_stats('cumulative')
            stats.print_stats(50)
            f.write(stats_stream.getvalue())
        
        # JSON report
        json_report = self._generate_json_report(stats, output_dir / 'startup_stats.json')
        
        # Generate flame graph data
        flame_data = self._generate_flame_graph_data(profile_file, output_dir / 'startup_flame.json')
        
        return {
            'profile_file': str(profile_file),
            'text_report': str(text_report),
            'json_report': str(json_report),
            'flame_data': str(flame_data),
            'startup_time': startup_time,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _profile_endpoints(self, service: str, config: Dict, output_dir: Path) -> Dict:
        """Profile service endpoints."""
        logger.info("Profiling service endpoints...")
        
        # This would require actually running the service
        # For now, we'll create a placeholder
        results = {
            'endpoints': {},
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Create endpoint profiling script
        script_path = output_dir / 'profile_endpoints.py'
        with open(script_path, 'w') as f:
            f.write(f"""#!/usr/bin/env python3
\"\"\"
Endpoint profiling script for {service}
\"\"\"

import asyncio
import aiohttp
import cProfile
import pstats
import time
from typing import List, Dict

async def profile_endpoint(session: aiohttp.ClientSession, url: str) -> Dict:
    \"\"\"Profile a single endpoint.\"\"\"
    profiler = cProfile.Profile()
    profiler.enable()
    
    start_time = time.time()
    try:
        async with session.get(url) as response:
            await response.text()
            status = response.status
    except Exception as e:
        status = -1
    finally:
        profiler.disable()
    
    response_time = time.time() - start_time
    
    stats = pstats.Stats(profiler)
    return {{
        'url': url,
        'status': status,
        'response_time': response_time,
        'stats': stats
    }}

async def main():
    \"\"\"Profile all endpoints.\"\"\"
    base_url = "http://localhost:8000"  # Adjust based on service
    endpoints = {config.get('test_endpoints', [])}
    
    async with aiohttp.ClientSession() as session:
        tasks = [profile_endpoint(session, f"{{base_url}}{{endpoint}}") for endpoint in endpoints]
        results = await asyncio.gather(*tasks)
    
    for result in results:
        print(f"Endpoint: {{result['url']}}")
        print(f"Status: {{result['status']}}")
        print(f"Response Time: {{result['response_time']:.3f}}s")
        print()

if __name__ == '__main__':
    asyncio.run(main())
""")
        
        results['profile_script'] = str(script_path)
        return results
    
    def _profile_load(self, service: str, config: Dict, output_dir: Path) -> Dict:
        """Profile service under load."""
        logger.info("Creating load testing profile configuration...")
        
        # Create locust configuration for load testing
        locust_file = output_dir / 'locustfile.py'
        with open(locust_file, 'w') as f:
            f.write(f"""#!/usr/bin/env python3
\"\"\"
Load testing profile for {service}
\"\"\"

from locust import HttpUser, task, between
import cProfile
import pstats
import io

class ServiceUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        \"\"\"Initialize profiler on start.\"\"\"
        self.profiler = cProfile.Profile()
        self.profiler.enable()
    
    def on_stop(self):
        \"\"\"Save profiling data on stop.\"\"\"
        self.profiler.disable()
        
        # Generate profile report
        stats = pstats.Stats(self.profiler)
        stats.strip_dirs()
        stats.sort_stats('cumulative')
        
        # Save to file
        with open(f'load_profile_{{self.user_id}}.txt', 'w') as f:
            stats.stream = f
            stats.print_stats(30)
    
    @task(3)
    def health_check(self):
        self.client.get("/health")
    
    @task(2)
    def api_docs(self):
        self.client.get("/docs")
""")
            
            # Add endpoint-specific tasks
            for endpoint in config.get('test_endpoints', []):
                if endpoint not in ['/health', '/docs']:
                    f.write(f"""
    @task(5)
    def test_{endpoint.replace('/', '_').strip('_')}(self):
        self.client.get("{endpoint}")
""")
        
        # Create load testing script
        load_script = output_dir / 'run_load_test.sh'
        with open(load_script, 'w') as f:
            f.write(f"""#!/bin/bash
# Load testing script for {service}

echo "Starting {service}..."
cd {service}
# Start service in background
# python -m {config['main_module']} &
# SERVICE_PID=$!

echo "Waiting for service to start..."
sleep 5

echo "Running load test..."
cd {output_dir}
locust -f locustfile.py --headless -u 10 -r 2 -t 60s --html load_test_report.html

echo "Load test complete. Generating profile visualization..."
for prof_file in load_profile_*.txt; do
    echo "Profile: $prof_file"
done

# Stop service
# kill $SERVICE_PID

echo "Done!"
""")
        
        load_script.chmod(0o755)
        
        return {
            'locust_file': str(locust_file),
            'load_script': str(load_script),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _generate_json_report(self, stats: pstats.Stats, output_file: Path) -> Path:
        """Generate JSON report from stats."""
        report_data = {
            'total_calls': stats.total_calls,
            'total_time': stats.total_tt,
            'functions': []
        }
        
        # Get top functions
        stats.sort_stats('cumulative')
        for func, (cc, nc, tt, ct, callers) in list(stats.stats.items())[:100]:
            report_data['functions'].append({
                'name': f"{func[0]}:{func[1]}:{func[2]}",
                'call_count': nc,
                'total_time': tt,
                'cumulative_time': ct,
                'callers': list(callers.keys()) if callers else []
            })
        
        with open(output_file, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        return output_file
    
    def _generate_flame_graph_data(self, profile_file: Path, output_file: Path) -> Path:
        """Generate flame graph data from profile."""
        try:
            # Use py-spy to generate flame graph data
            subprocess.run([
                'py-spy', 'report', str(profile_file),
                '--format', 'json',
                '--output', str(output_file)
            ], capture_output=True, text=True)
        except FileNotFoundError:
            logger.warning("py-spy not found. Creating placeholder flame graph data.")
            # Create placeholder
            with open(output_file, 'w') as f:
                json.dump({
                    'name': 'root',
                    'value': 1,
                    'children': []
                }, f)
        
        return output_file
    
    def visualize_profile(self, profile_file: str, open_browser: bool = True):
        """Open snakeviz visualization for profile file."""
        logger.info(f"Opening snakeviz for {profile_file}...")
        
        if open_browser:
            # Run snakeviz
            subprocess.Popen(['snakeviz', profile_file])
        else:
            # Just print the command
            print(f"To visualize the profile, run:")
            print(f"  snakeviz {profile_file}")
    
    def generate_comparison_report(self, service: str, profile_files: List[str]):
        """Generate comparison report between multiple profiles."""
        comparison_dir = self.output_dir / service / 'comparisons'
        comparison_dir.mkdir(parents=True, exist_ok=True)
        
        stats_list = []
        for profile_file in profile_files:
            stats = pstats.Stats(profile_file)
            stats_list.append(stats)
        
        # Compare top functions
        comparison_data = {
            'files': profile_files,
            'timestamp': datetime.utcnow().isoformat(),
            'comparisons': []
        }
        
        # Get unique functions from all profiles
        all_functions = set()
        for stats in stats_list:
            all_functions.update(stats.stats.keys())
        
        # Compare each function across profiles
        for func in sorted(all_functions)[:50]:  # Top 50 functions
            func_comparison = {
                'function': f"{func[0]}:{func[1]}:{func[2]}",
                'profiles': []
            }
            
            for i, stats in enumerate(stats_list):
                if func in stats.stats:
                    cc, nc, tt, ct, callers = stats.stats[func]
                    func_comparison['profiles'].append({
                        'file': profile_files[i],
                        'call_count': nc,
                        'total_time': tt,
                        'cumulative_time': ct
                    })
                else:
                    func_comparison['profiles'].append({
                        'file': profile_files[i],
                        'call_count': 0,
                        'total_time': 0,
                        'cumulative_time': 0
                    })
            
            comparison_data['comparisons'].append(func_comparison)
        
        # Save comparison report
        report_file = comparison_dir / f'comparison_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(report_file, 'w') as f:
            json.dump(comparison_data, f, indent=2)
        
        return report_file


def main():
    """Main entry point for service profiling."""
    parser = argparse.ArgumentParser(
        description='Profile Arrakis microservices performance'
    )
    parser.add_argument(
        'service',
        choices=list(ServiceProfiler.SERVICES.keys()),
        help='Service to profile'
    )
    parser.add_argument(
        '--type',
        choices=['startup', 'endpoints', 'load', 'all'],
        default='startup',
        help='Type of profiling to perform'
    )
    parser.add_argument(
        '--output',
        default='docs/dependencies',
        help='Output directory for profile data'
    )
    parser.add_argument(
        '--visualize',
        action='store_true',
        help='Open snakeviz visualization after profiling'
    )
    parser.add_argument(
        '--compare',
        nargs='+',
        help='Compare multiple profile files'
    )
    
    args = parser.parse_args()
    
    profiler = ServiceProfiler(output_dir=args.output)
    
    if args.compare:
        # Run comparison
        report = profiler.generate_comparison_report(args.service, args.compare)
        print(f"Comparison report saved to: {report}")
        return
    
    # Run profiling
    profile_types = ['startup', 'endpoints', 'load'] if args.type == 'all' else [args.type]
    
    for profile_type in profile_types:
        try:
            result = profiler.profile_service(args.service, profile_type)
            
            print(f"\n{profile_type.title()} Profiling Complete!")
            print(f"Service: {args.service}")
            
            if 'profile_file' in result:
                print(f"Profile data: {result['profile_file']}")
                
                if args.visualize:
                    profiler.visualize_profile(result['profile_file'])
            
            if 'startup_time' in result:
                print(f"Startup time: {result['startup_time']:.3f}s")
            
            print(f"\nReports generated:")
            for key, value in result.items():
                if key.endswith('_report') or key.endswith('_file'):
                    print(f"  - {key}: {value}")
            
        except Exception as e:
            logger.error(f"Error profiling {profile_type}: {e}")
            continue
    
    print(f"\nTo visualize profiles with snakeviz:")
    print(f"  snakeviz {args.output}/{args.service}/profile/startup.prof")
    
    print(f"\nTo compare profiles:")
    print(f"  python {__file__} {args.service} --compare file1.prof file2.prof")


if __name__ == '__main__':
    main()