#!/usr/bin/env python3
"""
Automated script to migrate os.getenv() calls to unified_env
"""

import ast
import os
import re
from pathlib import Path
from typing import List, Tuple, Set


class GetEnvMigrator(ast.NodeTransformer):
    """AST transformer to replace os.getenv calls"""
    
    def __init__(self, namespace: str = "core"):
        self.namespace = namespace
        self.found_vars: Set[str] = set()
        self.needs_import = False
        
    def visit_Call(self, node):
        """Transform os.getenv() calls"""
        # Check if it's os.getenv
        if (isinstance(node.func, ast.Attribute) and
            node.func.attr == 'getenv' and
            isinstance(node.func.value, ast.Name) and
            node.func.value.id == 'os'):
            
            # Extract arguments
            if len(node.args) >= 1:
                env_var = None
                default = None
                
                # Get env var name
                if isinstance(node.args[0], ast.Constant):
                    env_var = node.args[0].value
                elif isinstance(node.args[0], ast.Str):  # Python < 3.8
                    env_var = node.args[0].s
                
                # Get default value if present
                if len(node.args) >= 2:
                    default = node.args[1]
                
                if env_var:
                    self.found_vars.add(env_var)
                    self.needs_import = True
                    
                    # Create unified_env.get() call
                    new_call = ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id='unified_env', ctx=ast.Load()),
                            attr='get',
                            ctx=ast.Load()
                        ),
                        args=[ast.Constant(value=env_var)],
                        keywords=[]
                    )
                    
                    # If there's a default, wrap in try/except
                    if default:
                        return ast.IfExp(
                            test=ast.Constant(value=True),
                            body=ast.Try(
                                body=[ast.Return(value=new_call)],
                                handlers=[
                                    ast.ExceptHandler(
                                        type=ast.Name(id='ConfigurationError', ctx=ast.Load()),
                                        name=None,
                                        body=[ast.Return(value=default)]
                                    )
                                ],
                                orelse=[],
                                finalbody=[]
                            ),
                            orelse=default
                        )
                    
                    return new_call
        
        return self.generic_visit(node)


def find_os_getenv_usage(directory: str) -> List[Tuple[str, int, str]]:
    """Find all os.getenv() usage in Python files"""
    usage = []
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py') and not file.startswith('test_'):
                filepath = Path(root) / file
                
                # Skip migration scripts and tests
                if 'migration' in str(filepath) or 'test' in str(filepath):
                    continue
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Quick regex check first
                    if 'os.getenv' in content:
                        lines = content.splitlines()
                        for i, line in enumerate(lines, 1):
                            if 'os.getenv' in line:
                                usage.append((str(filepath), i, line.strip()))
                                
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")
    
    return usage


def migrate_file(filepath: str, namespace: str = "core") -> bool:
    """Migrate a single file from os.getenv to unified_env"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse AST
        tree = ast.parse(content)
        
        # Transform
        migrator = GetEnvMigrator(namespace=namespace)
        new_tree = migrator.visit(tree)
        
        if migrator.needs_import:
            # Add import at the top
            import_stmt = ast.ImportFrom(
                module='shared.config',
                names=[
                    ast.alias(name='unified_env', asname=None),
                    ast.alias(name='ConfigurationError', asname=None)
                ],
                level=0
            )
            
            # Insert after module docstring and other imports
            insert_pos = 0
            for i, stmt in enumerate(tree.body):
                if not isinstance(stmt, (ast.Expr, ast.Import, ast.ImportFrom)):
                    insert_pos = i
                    break
            
            tree.body.insert(insert_pos, import_stmt)
            
            # Generate new code
            new_content = ast.unparse(new_tree)
            
            # Write back
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"✅ Migrated {filepath}")
            print(f"   Found vars: {', '.join(migrator.found_vars)}")
            return True
            
    except Exception as e:
        print(f"❌ Failed to migrate {filepath}: {e}")
        return False
    
    return False


def generate_namespace_config(found_vars: Set[str], namespace: str) -> str:
    """Generate namespace configuration for found variables"""
    config_code = f'''def register_{namespace}_config():
    """Register {namespace}-specific configuration"""
    ns = ConfigNamespace("{namespace}", "{namespace.title()} configuration")
    
    vars = [
'''
    
    for var in sorted(found_vars):
        # Guess type and default based on name
        var_type = "str"
        default = '""'
        
        if var.endswith('_PORT') or var.endswith('_COUNT') or 'TIMEOUT' in var:
            var_type = "int"
            default = "0"
        elif var.endswith('_ENABLED') or var.startswith('ENABLE_'):
            var_type = "bool"
            default = "False"
        elif var.endswith('_URL'):
            default = '""'
            
        config_code += f'''        EnvVar("{var}", {var_type}, False, {default},
               "{var.replace('_', ' ').title()}"),
'''
    
    config_code += '''    ]
    
    for var in vars:
        ns.add_var(var)
    
    unified_env.register_namespace(ns)
'''
    
    return config_code


def main():
    """Main migration script"""
    print("=== OS.GETENV MIGRATION TOOL ===\n")
    
    # Directories to check
    check_dirs = [
        'middleware',
        'core',
        'shared',
        'api'
    ]
    
    all_usage = []
    for directory in check_dirs:
        if os.path.exists(directory):
            usage = find_os_getenv_usage(directory)
            all_usage.extend(usage)
    
    if not all_usage:
        print("✅ No os.getenv() usage found!")
        return
    
    print(f"Found {len(all_usage)} os.getenv() calls:\n")
    
    # Group by file
    by_file = {}
    for filepath, line_no, line in all_usage:
        if filepath not in by_file:
            by_file[filepath] = []
        by_file[filepath].append((line_no, line))
    
    # Show usage
    for filepath, occurrences in by_file.items():
        print(f"\n{filepath}:")
        for line_no, line in occurrences:
            print(f"  L{line_no}: {line}")
    
    # Ask for confirmation
    response = input("\nMigrate these files? (y/n): ")
    if response.lower() != 'y':
        print("Migration cancelled.")
        return
    
    # Migrate files
    migrated = 0
    all_vars = set()
    
    for filepath in by_file.keys():
        # Determine namespace from path
        namespace = "core"
        if "middleware" in filepath:
            namespace = "middleware"
        elif "event" in filepath:
            namespace = "event"
        elif "scheduler" in filepath:
            namespace = "scheduler"
        
        if migrate_file(filepath, namespace):
            migrated += 1
    
    print(f"\n✅ Migrated {migrated}/{len(by_file)} files")
    
    # Generate namespace configs for new variables
    if all_vars:
        print("\n=== NEW VARIABLES FOUND ===")
        print("Add these to namespace_configs.py:")
        print(generate_namespace_config(all_vars, "additional"))


if __name__ == "__main__":
    main()