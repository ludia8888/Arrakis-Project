#!/usr/bin/env python3
"""
Production-ready dependency analysis tool for Arrakis microservices.
Generates comprehensive dependency graphs, UML diagrams, and code metrics.
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import logging
from datetime import datetime
import concurrent.futures
import networkx as nx
import matplotlib.pyplot as plt
import seaborn as sns

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DependencyAnalyzer:
    """Comprehensive dependency analyzer for Python microservices."""
    
    SERVICES = [
        'ontology-management-service',
        'user-service',
        'audit-service',
        'data-kernel-service',
        'embedding-service',
        'scheduler-service',
        'event-gateway'
    ]
    
    VISUALIZATION_TOOLS = {
        'pydeps': {
            'command': 'pydeps',
            'required_packages': ['pydeps'],
            'output_formats': ['svg', 'png', 'json']
        },
        'pyreverse': {
            'command': 'pyreverse',
            'required_packages': ['pylint'],
            'output_formats': ['svg', 'png', 'dot']
        },
        'pipdeptree': {
            'command': 'pipdeptree',
            'required_packages': ['pipdeptree'],
            'output_formats': ['json', 'graph', 'tree']
        }
    }
    
    def __init__(self, root_path: str = '.', output_dir: str = 'docs/dependencies'):
        self.root_path = Path(root_path).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Check and install required tools
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check and install required visualization tools."""
        logger.info("Checking required dependencies...")
        
        required_packages = [
            'pydeps', 'snakeviz', 'pylint', 'pipdeptree',
            'graphviz', 'networkx', 'matplotlib', 'seaborn',
            'radon', 'vulture', 'bandit', 'safety', 'pip-audit'
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            logger.warning(f"Missing packages: {', '.join(missing_packages)}")
            logger.info("Installing missing packages...")
            subprocess.run([
                sys.executable, '-m', 'pip', 'install'
            ] + missing_packages, check=True)
    
    def analyze_service(self, service: str, analysis_types: List[str] = None) -> Dict:
        """Analyze dependencies for a single service."""
        if analysis_types is None:
            analysis_types = ['pydeps', 'pyreverse', 'imports', 'metrics']
        
        logger.info(f"Analyzing {service}...")
        service_path = self.root_path / service
        
        if not service_path.exists():
            logger.warning(f"Service path not found: {service_path}")
            return {}
        
        output_path = self.output_dir / service
        output_path.mkdir(parents=True, exist_ok=True)
        
        results = {
            'service': service,
            'timestamp': datetime.utcnow().isoformat(),
            'analyses': {}
        }
        
        # Run analyses
        if 'pydeps' in analysis_types:
            results['analyses']['pydeps'] = self._run_pydeps(service_path, output_path)
        
        if 'pyreverse' in analysis_types:
            results['analyses']['pyreverse'] = self._run_pyreverse(service_path, output_path)
        
        if 'imports' in analysis_types:
            results['analyses']['imports'] = self._analyze_imports(service_path, output_path)
        
        if 'metrics' in analysis_types:
            results['analyses']['metrics'] = self._calculate_metrics(service_path, output_path)
        
        # Generate report
        self._generate_service_report(service, results, output_path)
        
        return results
    
    def _run_pydeps(self, service_path: Path, output_path: Path) -> Dict:
        """Generate pydeps dependency graphs."""
        logger.info("Running pydeps analysis...")
        pydeps_dir = output_path / 'pydeps'
        pydeps_dir.mkdir(exist_ok=True)
        
        # Create pydeps configuration
        config_path = service_path / '.pydeps'
        with open(config_path, 'w') as f:
            f.write("""[pydeps]
max-bacon = 3
cluster = true
show-cycles = true
noise-level = 3
max-cluster-size = 10
keep-target-cluster = true
rankdir = TB
exclude = tests test conftest
""")
        
        results = {'graphs': []}
        
        try:
            # Main dependency graph
            output_file = pydeps_dir / 'main.svg'
            subprocess.run([
                'pydeps', str(service_path),
                '--max-bacon=3',
                '--cluster',
                '--show-cycles',
                '--noise-level=3',
                '-o', str(output_file),
                '-T', 'svg'
            ], check=True, capture_output=True, text=True)
            results['graphs'].append(str(output_file.relative_to(self.output_dir)))
            
            # Generate module-specific graphs
            for module in ['api', 'core', 'database', 'shared', 'middleware']:
                module_path = service_path / module
                if module_path.exists() and module_path.is_dir():
                    output_file = pydeps_dir / f'{module}.svg'
                    subprocess.run([
                        'pydeps', str(module_path),
                        '--max-bacon=2',
                        '--cluster',
                        '-o', str(output_file),
                        '-T', 'svg'
                    ], capture_output=True, text=True)
                    if output_file.exists():
                        results['graphs'].append(str(output_file.relative_to(self.output_dir)))
            
            # External dependencies
            output_file = pydeps_dir / 'external-deps.svg'
            subprocess.run([
                'pipdeptree',
                '--graph-output', 'svg'
            ], stdout=open(output_file, 'w'), check=True)
            results['graphs'].append(str(output_file.relative_to(self.output_dir)))
            
        except subprocess.CalledProcessError as e:
            logger.error(f"pydeps failed: {e}")
            results['error'] = str(e)
        finally:
            # Clean up config
            if config_path.exists():
                config_path.unlink()
        
        return results
    
    def _run_pyreverse(self, service_path: Path, output_path: Path) -> Dict:
        """Generate UML diagrams with pyreverse."""
        logger.info("Running pyreverse analysis...")
        pyreverse_dir = output_path / 'pyreverse'
        pyreverse_dir.mkdir(exist_ok=True)
        
        results = {'diagrams': []}
        
        try:
            # Change to service directory for proper module resolution
            original_cwd = os.getcwd()
            os.chdir(service_path)
            
            # Class diagram
            subprocess.run([
                'pyreverse',
                '-o', 'svg',
                '-p', service_path.name,
                '--colorized',
                '--all-ancestors',
                '--all-associated',
                '--filter-mode=ALL',
                '-d', str(pyreverse_dir),
                '.'
            ], check=True, capture_output=True, text=True)
            
            # Package diagram
            subprocess.run([
                'pyreverse',
                '-o', 'svg',
                '-p', f'{service_path.name}_packages',
                '--colorized',
                '-k',  # packages only
                '-d', str(pyreverse_dir),
                '.'
            ], capture_output=True, text=True)
            
            # Find generated files
            for file in pyreverse_dir.glob('*.svg'):
                results['diagrams'].append(str(file.relative_to(self.output_dir)))
            
        except subprocess.CalledProcessError as e:
            logger.error(f"pyreverse failed: {e}")
            results['error'] = str(e)
        finally:
            os.chdir(original_cwd)
        
        return results
    
    def _analyze_imports(self, service_path: Path, output_path: Path) -> Dict:
        """Analyze import relationships and generate custom visualizations."""
        logger.info("Analyzing import relationships...")
        import_dir = output_path / 'import-graph'
        import_dir.mkdir(exist_ok=True)
        
        import ast
        from collections import defaultdict
        
        import_graph = defaultdict(set)
        module_metrics = {}
        
        # Parse Python files
        for py_file in service_path.rglob('*.py'):
            if any(part in py_file.parts for part in ['test', '__pycache__', '.venv']):
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read())
                
                module_name = str(py_file.relative_to(service_path)).replace('/', '.').replace('.py', '')
                imports = []
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append(alias.name)
                            import_graph[module_name].add(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.append(node.module)
                            import_graph[module_name].add(node.module)
                
                module_metrics[module_name] = {
                    'imports': imports,
                    'import_count': len(imports),
                    'unique_imports': len(set(imports))
                }
                
            except Exception as e:
                logger.error(f"Error parsing {py_file}: {e}")
        
        # Create NetworkX graph
        G = nx.DiGraph()
        internal_prefix = service_path.name.replace('-', '_')
        
        for module, imports in import_graph.items():
            G.add_node(module)
            for imp in imports:
                # Only include internal imports for clarity
                if imp.startswith(internal_prefix) or module.startswith(imp.split('.')[0]):
                    G.add_edge(module, imp)
        
        # Generate visualization
        plt.figure(figsize=(20, 16))
        
        # Calculate layout
        try:
            pos = nx.spring_layout(G, k=3, iterations=50, seed=42)
        except:
            pos = nx.random_layout(G)
        
        # Color by module depth
        node_colors = [len(node.split('.')) for node in G.nodes()]
        
        # Draw graph
        nx.draw(G, pos,
                node_color=node_colors,
                cmap='viridis',
                with_labels=True,
                node_size=3000,
                font_size=8,
                font_weight='bold',
                arrows=True,
                edge_color='gray',
                alpha=0.7,
                arrowsize=10)
        
        plt.title(f"Import Dependency Graph - {service_path.name}", fontsize=16)
        plt.tight_layout()
        
        output_file = import_dir / 'imports.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        # Calculate metrics
        metrics = {
            'total_modules': G.number_of_nodes(),
            'total_imports': G.number_of_edges(),
            'avg_imports_per_module': G.number_of_edges() / max(G.number_of_nodes(), 1),
            'most_imported': sorted(
                [(node, degree) for node, degree in G.in_degree()],
                key=lambda x: x[1],
                reverse=True
            )[:10],
            'most_importing': sorted(
                [(node, degree) for node, degree in G.out_degree()],
                key=lambda x: x[1],
                reverse=True
            )[:10],
            'strongly_connected_components': list(nx.strongly_connected_components(G)),
            'cycles': []
        }
        
        # Find cycles (limit to prevent performance issues)
        try:
            cycles = list(nx.simple_cycles(G))
            metrics['cycles'] = cycles[:10] if cycles else []
        except:
            logger.warning("Could not compute cycles")
        
        # Save data
        data_file = import_dir / 'imports.json'
        with open(data_file, 'w') as f:
            json.dump({
                'import_graph': {k: list(v) for k, v in import_graph.items()},
                'module_metrics': module_metrics,
                'graph_metrics': metrics
            }, f, indent=2, default=str)
        
        return {
            'visualization': str(output_file.relative_to(self.output_dir)),
            'data': str(data_file.relative_to(self.output_dir)),
            'metrics': metrics
        }
    
    def _calculate_metrics(self, service_path: Path, output_path: Path) -> Dict:
        """Calculate code quality metrics."""
        logger.info("Calculating code metrics...")
        metrics_dir = output_path / 'metrics'
        metrics_dir.mkdir(exist_ok=True)
        
        results = {}
        
        # Radon - Cyclomatic Complexity
        try:
            complexity_output = subprocess.run([
                'radon', 'cc', str(service_path),
                '-a', '-j'
            ], capture_output=True, text=True, check=True)
            
            complexity_file = metrics_dir / 'complexity.json'
            with open(complexity_file, 'w') as f:
                f.write(complexity_output.stdout)
            results['complexity'] = str(complexity_file.relative_to(self.output_dir))
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Radon CC failed: {e}")
        
        # Radon - Maintainability Index
        try:
            mi_output = subprocess.run([
                'radon', 'mi', str(service_path), '-j'
            ], capture_output=True, text=True, check=True)
            
            mi_file = metrics_dir / 'maintainability.json'
            with open(mi_file, 'w') as f:
                f.write(mi_output.stdout)
            results['maintainability'] = str(mi_file.relative_to(self.output_dir))
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Radon MI failed: {e}")
        
        # Vulture - Dead code detection
        try:
            vulture_output = subprocess.run([
                'vulture', str(service_path),
                '--min-confidence', '80'
            ], capture_output=True, text=True)
            
            vulture_file = metrics_dir / 'vulture.txt'
            with open(vulture_file, 'w') as f:
                f.write(vulture_output.stdout)
            results['dead_code'] = str(vulture_file.relative_to(self.output_dir))
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Vulture failed: {e}")
        
        # Bandit - Security scanning
        try:
            bandit_output = subprocess.run([
                'bandit', '-r', str(service_path),
                '-f', 'json'
            ], capture_output=True, text=True)
            
            security_file = metrics_dir / 'security.json'
            with open(security_file, 'w') as f:
                f.write(bandit_output.stdout)
            results['security'] = str(security_file.relative_to(self.output_dir))
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Bandit failed: {e}")
        
        # Safety - Dependency vulnerabilities
        try:
            # Change to service directory for requirements.txt
            original_cwd = os.getcwd()
            os.chdir(service_path)
            
            safety_output = subprocess.run([
                'safety', 'check', '--json'
            ], capture_output=True, text=True)
            
            safety_file = metrics_dir / 'vulnerabilities.json'
            with open(safety_file, 'w') as f:
                f.write(safety_output.stdout)
            results['vulnerabilities'] = str(safety_file.relative_to(self.output_dir))
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Safety failed: {e}")
        finally:
            os.chdir(original_cwd)
        
        return results
    
    def _generate_service_report(self, service: str, results: Dict, output_path: Path):
        """Generate markdown report for service analysis."""
        report_path = output_path / 'README.md'
        
        with open(report_path, 'w') as f:
            f.write(f"""# Dependency Analysis: {service}

Generated on: {results['timestamp']}

## Table of Contents
1. [Dependency Graphs](#dependency-graphs)
2. [UML Diagrams](#uml-diagrams)
3. [Import Analysis](#import-analysis)
4. [Code Metrics](#code-metrics)
5. [Recommendations](#recommendations)

## Dependency Graphs

### Main Dependencies
""")
            
            # Add pydeps graphs
            if 'pydeps' in results['analyses']:
                pydeps = results['analyses']['pydeps']
                if 'graphs' in pydeps:
                    for graph in pydeps['graphs']:
                        name = Path(graph).stem
                        f.write(f"![{name}]({graph})\n\n")
            
            f.write("""## UML Diagrams

### Class Diagram
""")
            
            # Add pyreverse diagrams
            if 'pyreverse' in results['analyses']:
                pyreverse = results['analyses']['pyreverse']
                if 'diagrams' in pyreverse:
                    for diagram in pyreverse['diagrams']:
                        name = Path(diagram).stem
                        f.write(f"![{name}]({diagram})\n\n")
            
            f.write("""## Import Analysis

### Import Dependency Graph
""")
            
            # Add import analysis
            if 'imports' in results['analyses']:
                imports = results['analyses']['imports']
                if 'visualization' in imports:
                    f.write(f"![Import Graph]({imports['visualization']})\n\n")
                
                if 'metrics' in imports:
                    metrics = imports['metrics']
                    f.write(f"""### Import Metrics
- Total modules: {metrics.get('total_modules', 0)}
- Total imports: {metrics.get('total_imports', 0)}
- Average imports per module: {metrics.get('avg_imports_per_module', 0):.2f}

#### Most Imported Modules
""")
                    for module, count in metrics.get('most_imported', [])[:5]:
                        f.write(f"- `{module}`: {count} imports\n")
                    
                    if metrics.get('cycles'):
                        f.write("\n#### Circular Dependencies Detected\n")
                        for cycle in metrics['cycles'][:5]:
                            f.write(f"- {' → '.join(cycle)} → {cycle[0]}\n")
            
            f.write("""
## Code Metrics

### Quality Metrics
""")
            
            # Add metrics summary
            if 'metrics' in results['analyses']:
                metrics = results['analyses']['metrics']
                f.write(f"""
- [Cyclomatic Complexity]({metrics.get('complexity', 'N/A')})
- [Maintainability Index]({metrics.get('maintainability', 'N/A')})
- [Dead Code Analysis]({metrics.get('dead_code', 'N/A')})
- [Security Scan]({metrics.get('security', 'N/A')})
- [Dependency Vulnerabilities]({metrics.get('vulnerabilities', 'N/A')})
""")
            
            f.write("""
## Recommendations

Based on the analysis, here are key recommendations:

1. **Circular Dependencies**: Review and refactor any circular dependencies identified
2. **High Complexity**: Focus on modules with complexity > 10
3. **Security**: Address any high-severity security issues
4. **Dependencies**: Update vulnerable dependencies
5. **Dead Code**: Remove unused code identified by Vulture

## Running Analysis Locally

```bash
# Install dependencies
pip install pydeps snakeviz pyreverse-ng radon vulture bandit safety

# Run analysis
python scripts/analyze_dependencies.py --service {service}

# View profiling results
snakeviz docs/dependencies/{service}/profile/startup.prof
```
""")
    
    def analyze_all(self, parallel: bool = True) -> Dict[str, Dict]:
        """Analyze all services."""
        logger.info(f"Analyzing all services (parallel={parallel})...")
        
        results = {}
        
        if parallel:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                future_to_service = {
                    executor.submit(self.analyze_service, service): service
                    for service in self.SERVICES
                }
                
                for future in concurrent.futures.as_completed(future_to_service):
                    service = future_to_service[future]
                    try:
                        results[service] = future.result()
                    except Exception as e:
                        logger.error(f"Failed to analyze {service}: {e}")
                        results[service] = {'error': str(e)}
        else:
            for service in self.SERVICES:
                try:
                    results[service] = self.analyze_service(service)
                except Exception as e:
                    logger.error(f"Failed to analyze {service}: {e}")
                    results[service] = {'error': str(e)}
        
        # Generate combined report
        self._generate_combined_report(results)
        
        return results
    
    def _generate_combined_report(self, results: Dict[str, Dict]):
        """Generate combined report for all services."""
        report_path = self.output_dir / 'README.md'
        
        with open(report_path, 'w') as f:
            f.write(f"""# Arrakis Project - Dependency Analysis Dashboard

Generated on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

## Overview

This dashboard provides comprehensive dependency analysis for all microservices in the Arrakis project.

## Services

| Service | Status | Complexity | Security | Dependencies |
|---------|--------|------------|----------|--------------|
""")
            
            for service, result in results.items():
                status = "❌ Error" if 'error' in result else "✅ Success"
                complexity = "View Report"
                security = "View Report"
                deps = "View Report"
                
                f.write(f"| [{service}](./{service}/) | {status} | {complexity} | {security} | {deps} |\n")
            
            f.write("""
## Key Findings

### Circular Dependencies
""")
            
            # Aggregate circular dependencies
            all_cycles = []
            for service, result in results.items():
                if 'analyses' in result and 'imports' in result['analyses']:
                    imports = result['analyses']['imports']
                    if 'metrics' in imports and 'cycles' in imports['metrics']:
                        for cycle in imports['metrics']['cycles']:
                            all_cycles.append((service, cycle))
            
            if all_cycles:
                f.write("The following circular dependencies were detected:\n\n")
                for service, cycle in all_cycles[:10]:
                    f.write(f"- **{service}**: {' → '.join(cycle)} → {cycle[0]}\n")
            else:
                f.write("No circular dependencies detected.\n")
            
            f.write("""
## Visualization Guide

### PyDeps Graphs
- **Nodes**: Python modules
- **Edges**: Import relationships
- **Colors**: Module clusters
- **Red edges**: Circular dependencies

### UML Diagrams
- **Classes**: Python classes with methods and attributes
- **Inheritance**: Shown with arrows
- **Associations**: Shown with lines

### Import Analysis
- **Node size**: Number of imports
- **Edge thickness**: Frequency of imports
- **Colors**: Module depth

## Using This Analysis

1. **Identify Issues**: Look for red flags in complexity and security
2. **Plan Refactoring**: Use circular dependency information
3. **Track Progress**: Compare reports over time
4. **Automate Checks**: Integrate into CI/CD pipeline

## Automation

This analysis runs automatically on:
- Push to main branch
- Pull requests
- Manual workflow dispatch

To run locally:
```bash
python scripts/analyze_dependencies.py --all
```

## Next Steps

1. Address high-priority security vulnerabilities
2. Refactor circular dependencies
3. Reduce complexity in flagged modules
4. Update outdated dependencies
5. Improve test coverage for complex modules
""")


def main():
    """Main entry point for dependency analysis."""
    parser = argparse.ArgumentParser(
        description='Analyze dependencies for Arrakis microservices'
    )
    parser.add_argument(
        '--service',
        choices=DependencyAnalyzer.SERVICES + ['all'],
        default='all',
        help='Service to analyze (default: all)'
    )
    parser.add_argument(
        '--output',
        default='docs/dependencies',
        help='Output directory for reports'
    )
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Run analysis in parallel'
    )
    parser.add_argument(
        '--types',
        nargs='+',
        choices=['pydeps', 'pyreverse', 'imports', 'metrics'],
        default=['pydeps', 'pyreverse', 'imports', 'metrics'],
        help='Types of analysis to run'
    )
    
    args = parser.parse_args()
    
    analyzer = DependencyAnalyzer(output_dir=args.output)
    
    if args.service == 'all':
        results = analyzer.analyze_all(parallel=args.parallel)
        logger.info(f"Analysis complete. Results saved to {args.output}")
    else:
        result = analyzer.analyze_service(args.service, args.types)
        logger.info(f"Analysis complete for {args.service}. Results saved to {args.output}/{args.service}")
        
        # Print summary
        if 'error' not in result:
            print(f"\nAnalysis Summary for {args.service}:")
            if 'imports' in result.get('analyses', {}):
                metrics = result['analyses']['imports'].get('metrics', {})
                print(f"- Total modules: {metrics.get('total_modules', 0)}")
                print(f"- Total imports: {metrics.get('total_imports', 0)}")
                if metrics.get('cycles'):
                    print(f"- Circular dependencies: {len(metrics['cycles'])}")


if __name__ == '__main__':
    main()