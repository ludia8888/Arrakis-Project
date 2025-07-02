#!/usr/bin/env python3
"""
Analyze environment variable usage across the codebase
Generates a comprehensive report of all os.getenv() calls
"""

import os
import re
import ast
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import defaultdict
import json

class EnvVarAnalyzer(ast.NodeVisitor):
    """AST visitor to find os.getenv() calls"""
    
    def __init__(self):
        self.env_vars: List[Dict[str, any]] = []
        
    def visit_Call(self, node):
        """Find os.getenv() calls"""
        if (isinstance(node.func, ast.Attribute) and
            node.func.attr == 'getenv' and
            isinstance(node.func.value, ast.Name) and
            node.func.value.id == 'os'):
            
            env_info = {
                'line': node.lineno,
                'col': node.col_offset,
                'var_name': None,
                'default': None,
                'has_default': False
            }
            
            # Extract variable name
            if len(node.args) >= 1:
                if isinstance(node.args[0], ast.Constant):
                    env_info['var_name'] = node.args[0].value
                elif isinstance(node.args[0], ast.Str):  # Python < 3.8
                    env_info['var_name'] = node.args[0].s
                    
            # Extract default value
            if len(node.args) >= 2:
                env_info['has_default'] = True
                default_node = node.args[1]
                
                if isinstance(default_node, ast.Constant):
                    env_info['default'] = default_node.value
                elif isinstance(default_node, ast.Str):
                    env_info['default'] = default_node.s
                elif isinstance(default_node, ast.Num):
                    env_info['default'] = default_node.n
                else:
                    env_info['default'] = ast.unparse(default_node)
                    
            self.env_vars.append(env_info)
            
        self.generic_visit(node)


def analyze_file(filepath: Path) -> List[Dict[str, any]]:
    """Analyze a single Python file for environment variable usage"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        tree = ast.parse(content)
        analyzer = EnvVarAnalyzer()
        analyzer.visit(tree)
        
        # Add file context to each variable
        for var in analyzer.env_vars:
            var['file'] = str(filepath)
            
        return analyzer.env_vars
        
    except Exception as e:
        print(f"Error analyzing {filepath}: {e}")
        return []


def categorize_env_var(var_name: str) -> str:
    """Categorize environment variable by its name pattern"""
    if not var_name:
        return "unknown"
        
    var_upper = var_name.upper()
    
    # Database related
    if any(db in var_upper for db in ['TERMINUS', 'REDIS', 'POSTGRES', 'MONGO', 'DB']):
        return "database"
    
    # Authentication/Security
    if any(auth in var_upper for auth in ['JWT', 'SECRET', 'TOKEN', 'AUTH', 'PASSWORD', 'KEY']):
        return "security"
    
    # Service URLs
    if any(svc in var_upper for svc in ['_SERVICE_', 'SERVICE_URL', 'API_URL', 'ENDPOINT']):
        return "service"
    
    # Configuration
    if any(cfg in var_upper for cfg in ['CONFIG', 'SETTING', 'OPTION', 'ENABLE', 'DISABLE']):
        return "config"
    
    # Environment/Deployment
    if any(env in var_upper for env in ['ENVIRONMENT', 'ENV', 'DEBUG', 'LOG_LEVEL']):
        return "environment"
    
    # Performance/Limits
    if any(perf in var_upper for perf in ['TIMEOUT', 'RETRY', 'LIMIT', 'MAX', 'MIN', 'POOL']):
        return "performance"
    
    # Monitoring
    if any(mon in var_upper for mon in ['METRIC', 'TRACE', 'MONITOR', 'TELEMETRY']):
        return "monitoring"
    
    return "other"


def generate_report(all_vars: List[Dict[str, any]]) -> Dict[str, any]:
    """Generate comprehensive report of environment variable usage"""
    report = {
        'total_files': len(set(var['file'] for var in all_vars)),
        'total_vars': len(all_vars),
        'unique_vars': len(set(var['var_name'] for var in all_vars if var['var_name'])),
        'vars_with_defaults': sum(1 for var in all_vars if var['has_default']),
        'vars_without_defaults': sum(1 for var in all_vars if not var['has_default']),
        'by_category': defaultdict(list),
        'by_file': defaultdict(list),
        'unique_var_details': {},
        'migration_priority': []
    }
    
    # Group by category and file
    for var in all_vars:
        if var['var_name']:
            category = categorize_env_var(var['var_name'])
            report['by_category'][category].append(var)
            report['by_file'][var['file']].append(var)
            
            # Track unique variable details
            if var['var_name'] not in report['unique_var_details']:
                report['unique_var_details'][var['var_name']] = {
                    'name': var['var_name'],
                    'category': category,
                    'used_in_files': [],
                    'defaults': set(),
                    'always_has_default': True
                }
            
            var_detail = report['unique_var_details'][var['var_name']]
            var_detail['used_in_files'].append(var['file'])
            
            if var['has_default']:
                var_detail['defaults'].add(str(var['default']))
            else:
                var_detail['always_has_default'] = False
    
    # Convert sets to lists for JSON serialization
    for var_name, details in report['unique_var_details'].items():
        details['defaults'] = list(details['defaults'])
        details['used_in_files'] = list(set(details['used_in_files']))
        details['usage_count'] = len(details['used_in_files'])
    
    # Determine migration priority
    priority_vars = []
    for var_name, details in report['unique_var_details'].items():
        priority_score = 0
        
        # High priority for security variables
        if details['category'] == 'security':
            priority_score += 10
        
        # High priority for database variables
        if details['category'] == 'database':
            priority_score += 8
        
        # High priority for widely used variables
        priority_score += min(details['usage_count'], 5)
        
        # High priority for variables without defaults
        if not details['always_has_default']:
            priority_score += 5
        
        priority_vars.append({
            'name': var_name,
            'score': priority_score,
            'category': details['category'],
            'usage_count': details['usage_count'],
            'has_default': details['always_has_default']
        })
    
    # Sort by priority score
    priority_vars.sort(key=lambda x: x['score'], reverse=True)
    report['migration_priority'] = priority_vars[:20]  # Top 20
    
    return report


def print_report(report: Dict[str, any]):
    """Print human-readable report"""
    print("=" * 80)
    print("ENVIRONMENT VARIABLE USAGE REPORT")
    print("=" * 80)
    print()
    
    print(f"Total Files Analyzed: {report['total_files']}")
    print(f"Total os.getenv() Calls: {report['total_vars']}")
    print(f"Unique Environment Variables: {report['unique_vars']}")
    print(f"Variables with Defaults: {report['vars_with_defaults']}")
    print(f"Variables without Defaults: {report['vars_without_defaults']}")
    print()
    
    print("USAGE BY CATEGORY:")
    print("-" * 40)
    for category, vars in sorted(report['by_category'].items()):
        unique_vars = set(var['var_name'] for var in vars if var['var_name'])
        print(f"{category.upper()}: {len(unique_vars)} unique variables, {len(vars)} total uses")
    print()
    
    print("TOP 20 MIGRATION PRIORITIES:")
    print("-" * 40)
    print(f"{'Variable Name':<30} {'Category':<12} {'Priority':<10} {'Uses':<6} {'Default'}")
    print("-" * 80)
    for var in report['migration_priority']:
        default_str = "Yes" if var['has_default'] else "No"
        print(f"{var['name']:<30} {var['category']:<12} {var['score']:<10} {var['usage_count']:<6} {default_str}")
    print()
    
    print("FILES WITH MOST ENV VARS:")
    print("-" * 40)
    files_by_count = sorted(
        [(file, len(vars)) for file, vars in report['by_file'].items()],
        key=lambda x: x[1],
        reverse=True
    )[:10]
    
    for file, count in files_by_count:
        short_file = file.replace('/Users/sihyun/Desktop/ARRAKIS/SPICE/oms-monolith/', '')
        print(f"{short_file}: {count} uses")


def main():
    """Main analysis function"""
    # Directories to analyze
    directories = [
        'api',
        'core',
        'middleware',
        'shared',
        'services',
        'migrations',
        'scripts'
    ]
    
    # Find all Python files
    all_vars = []
    
    for directory in directories:
        if os.path.exists(directory):
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.endswith('.py') and not file.startswith('test_'):
                        filepath = Path(root) / file
                        
                        # Skip the unified_env file itself
                        if 'unified_env.py' in str(filepath):
                            continue
                            
                        vars = analyze_file(filepath)
                        all_vars.extend(vars)
    
    # Also check main files
    for main_file in ['main.py', 'main_secure.py']:
        if os.path.exists(main_file):
            vars = analyze_file(Path(main_file))
            all_vars.extend(vars)
    
    # Generate report
    report = generate_report(all_vars)
    
    # Print human-readable report
    print_report(report)
    
    # Save detailed JSON report
    with open('env_usage_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nDetailed report saved to: env_usage_report.json")
    
    # Generate migration checklist
    print("\n" + "=" * 80)
    print("MIGRATION CHECKLIST")
    print("=" * 80)
    
    for category in ['security', 'database', 'service', 'environment', 'config']:
        vars_in_category = [
            name for name, details in report['unique_var_details'].items()
            if details['category'] == category
        ]
        
        if vars_in_category:
            print(f"\n{category.upper()} Variables:")
            for var in sorted(vars_in_category):
                details = report['unique_var_details'][var]
                print(f"  [ ] {var} (used in {details['usage_count']} files)")


if __name__ == "__main__":
    main()