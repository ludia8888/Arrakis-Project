#!/usr/bin/env python3
"""
Comprehensive migration script to convert os.getenv() to unified_env
Following SSOT (Single Source of Truth) principle
"""

import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
import argparse
import json


class EnvVarUsage:
    """Track environment variable usage details"""
    def __init__(self, var_name: str, has_default: bool, default_value: any, 
                 file_path: str, line_no: int, context: str):
        self.var_name = var_name
        self.has_default = has_default
        self.default_value = default_value
        self.file_path = file_path
        self.line_no = line_no
        self.context = context
        
    def __repr__(self):
        return f"EnvVarUsage({self.var_name}, default={self.default_value}, {self.file_path}:{self.line_no})"


class EnvMigrationTransformer(ast.NodeTransformer):
    """AST transformer to replace os.getenv with unified_env.get"""
    
    def __init__(self):
        self.imports_needed = set()
        self.env_vars_found = []
        self.has_os_import = False
        self.os_import_used_for_other = False
        
    def visit_Import(self, node):
        """Track os imports"""
        for alias in node.names:
            if alias.name == 'os':
                self.has_os_import = True
        return node
    
    def visit_ImportFrom(self, node):
        """Track from os imports"""
        if node.module == 'os':
            self.has_os_import = True
        return node
    
    def visit_Attribute(self, node):
        """Check if os is used for anything other than getenv"""
        if (isinstance(node.value, ast.Name) and 
            node.value.id == 'os' and 
            node.attr != 'getenv'):
            self.os_import_used_for_other = True
        return self.generic_visit(node)
    
    def visit_Call(self, node):
        """Transform os.getenv() calls to unified_env.get()"""
        # First check if this is os.getenv
        if (isinstance(node.func, ast.Attribute) and
            node.func.attr == 'getenv' and
            isinstance(node.func.value, ast.Name) and
            node.func.value.id == 'os'):
            
            # Extract variable name and default
            if len(node.args) >= 1:
                var_name = None
                default_value = None
                has_default = len(node.args) >= 2
                
                # Get variable name
                if isinstance(node.args[0], ast.Constant):
                    var_name = node.args[0].value
                elif isinstance(node.args[0], ast.Str):  # Python < 3.8
                    var_name = node.args[0].s
                
                # Get default value if present
                if has_default:
                    default_value = ast.unparse(node.args[1])
                
                if var_name:
                    # Record the usage
                    self.env_vars_found.append({
                        'name': var_name,
                        'has_default': has_default,
                        'default': default_value
                    })
                    
                    self.imports_needed.add('unified_env')
                    
                    # Create the replacement call
                    new_call = ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id='unified_env', ctx=ast.Load()),
                            attr='get',
                            ctx=ast.Load()
                        ),
                        args=[ast.Constant(value=var_name)],
                        keywords=[]
                    )
                    
                    # If there's a default and it's not registered in unified_env,
                    # we need to handle it with try/except
                    if has_default:
                        self.imports_needed.add('ConfigurationError')
                        # For now, just use unified_env.get() - the default should be
                        # registered in unified_env configuration
                    
                    return new_call
        
        return self.generic_visit(node)


def analyze_file(file_path: Path) -> List[EnvVarUsage]:
    """Analyze a file for os.getenv usage"""
    usages = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'os.getenv' not in content:
            return usages
            
        tree = ast.parse(content)
        
        # Find all os.getenv calls
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and
                isinstance(node.func, ast.Attribute) and
                node.func.attr == 'getenv' and
                isinstance(node.func.value, ast.Name) and
                node.func.value.id == 'os'):
                
                if len(node.args) >= 1:
                    var_name = None
                    default_value = None
                    has_default = len(node.args) >= 2
                    
                    # Get variable name
                    if isinstance(node.args[0], ast.Constant):
                        var_name = node.args[0].value
                    elif hasattr(ast, 'Str') and isinstance(node.args[0], ast.Str):
                        var_name = node.args[0].s
                    
                    # Get default value
                    if has_default:
                        default_value = ast.unparse(node.args[1])
                    
                    if var_name:
                        # Find line number
                        line_no = node.lineno
                        
                        # Get context (the line of code)
                        lines = content.splitlines()
                        context = lines[line_no - 1].strip() if line_no <= len(lines) else ""
                        
                        usage = EnvVarUsage(
                            var_name=var_name,
                            has_default=has_default,
                            default_value=default_value,
                            file_path=str(file_path),
                            line_no=line_no,
                            context=context
                        )
                        usages.append(usage)
                        
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        
    return usages


def migrate_file(file_path: Path, dry_run: bool = False) -> bool:
    """Migrate a single file from os.getenv to unified_env"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'os.getenv' not in content:
            return False
            
        # Parse and transform
        tree = ast.parse(content)
        transformer = EnvMigrationTransformer()
        new_tree = transformer.visit(tree)
        
        if not transformer.env_vars_found:
            return False
            
        # Fix missing locations in the AST
        for node in ast.walk(new_tree):
            if not hasattr(node, 'lineno'):
                node.lineno = 0
            if not hasattr(node, 'col_offset'):
                node.col_offset = 0
                
        # Add necessary imports
        imports_to_add = []
        
        # Check if we already have the imports
        has_unified_env_import = False
        has_config_error_import = False
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == 'shared.config.unified_env':
                    for alias in node.names:
                        if alias.name == 'unified_env':
                            has_unified_env_import = True
                        if alias.name == 'ConfigurationError':
                            has_config_error_import = True
                elif node.module == 'shared.config':
                    for alias in node.names:
                        if alias.name == 'unified_env':
                            has_unified_env_import = True
        
        # Add imports if needed
        if 'unified_env' in transformer.imports_needed and not has_unified_env_import:
            if 'ConfigurationError' in transformer.imports_needed and not has_config_error_import:
                imports_to_add.append(
                    ast.ImportFrom(
                        module='shared.config.unified_env',
                        names=[
                            ast.alias(name='unified_env', asname=None),
                            ast.alias(name='ConfigurationError', asname=None)
                        ],
                        level=0
                    )
                )
            else:
                imports_to_add.append(
                    ast.ImportFrom(
                        module='shared.config.unified_env',
                        names=[ast.alias(name='unified_env', asname=None)],
                        level=0
                    )
                )
        
        # Find where to insert imports (after docstring and other imports)
        insert_pos = 0
        for i, node in enumerate(tree.body):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Str):
                # Skip docstring
                insert_pos = i + 1
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                insert_pos = i + 1
            else:
                break
                
        # Insert new imports
        for imp in reversed(imports_to_add):
            tree.body.insert(insert_pos, imp)
            
        # Remove os import if it's not used for anything else
        if transformer.has_os_import and not transformer.os_import_used_for_other:
            tree.body = [node for node in tree.body 
                        if not (isinstance(node, ast.Import) and 
                               any(alias.name == 'os' for alias in node.names))]
            
        # Generate new code
        new_content = ast.unparse(new_tree)
        
        if dry_run:
            print(f"\n--- Would migrate {file_path} ---")
            print(f"Found {len(transformer.env_vars_found)} os.getenv calls")
            for var in transformer.env_vars_found:
                print(f"  - {var['name']} (default: {var.get('default', 'None')})")
        else:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"✅ Migrated {file_path}")
            
        return True
        
    except Exception as e:
        print(f"❌ Failed to migrate {file_path}: {e}")
        return False


def generate_env_var_registration(usages: List[EnvVarUsage]) -> str:
    """Generate code to register found environment variables"""
    # Group by variable name
    var_map: Dict[str, List[EnvVarUsage]] = {}
    for usage in usages:
        if usage.var_name not in var_map:
            var_map[usage.var_name] = []
        var_map[usage.var_name].append(usage)
    
    # Categorize variables
    categories = {
        'security': [],
        'database': [],
        'service': [],
        'config': [],
        'performance': [],
        'other': []
    }
    
    for var_name, usages_list in var_map.items():
        # Determine category
        if any(keyword in var_name.lower() for keyword in ['jwt', 'secret', 'key', 'password', 'token', 'auth']):
            category = 'security'
        elif any(keyword in var_name.lower() for keyword in ['db', 'database', 'redis', 'terminus']):
            category = 'database'
        elif any(keyword in var_name.lower() for keyword in ['service', 'url', 'endpoint']):
            category = 'service'
        elif any(keyword in var_name.lower() for keyword in ['enable', 'config', 'setting']):
            category = 'config'
        elif any(keyword in var_name.lower() for keyword in ['timeout', 'retry', 'cache', 'pool']):
            category = 'performance'
        else:
            category = 'other'
            
        # Determine if required (no default across all usages)
        required = not any(u.has_default for u in usages_list)
        
        # Get common default value
        defaults = [u.default_value for u in usages_list if u.has_default]
        default = defaults[0] if defaults else None
        
        # Guess type
        var_type = 'str'
        if default:
            if default.lower() in ['true', 'false']:
                var_type = 'bool'
            elif default.isdigit():
                var_type = 'int'
            elif '.' in default and default.replace('.', '').isdigit():
                var_type = 'float'
                
        categories[category].append({
            'name': var_name,
            'type': var_type,
            'required': required,
            'default': default,
            'usages': len(usages_list)
        })
    
    # Generate registration code
    code = """# Add these environment variable registrations to unified_env

def register_additional_env_vars():
    \"\"\"Register additional environment variables found during migration\"\"\"
    
"""
    
    for category, vars_list in categories.items():
        if not vars_list:
            continue
            
        code += f"    # {category.upper()} variables\n"
        code += f"    {category}_vars = [\n"
        
        for var in sorted(vars_list, key=lambda x: x['name']):
            default_str = f'default={var["default"]}' if var['default'] else ''
            if var['type'] == 'str' and var['default']:
                default_str = f'default={var["default"]}'
                
            code += f'        EnvVar("{var["name"]}", {var["type"]}, '
            code += f'{"True" if var["required"] else "False"}'
            if default_str:
                code += f', {default_str}'
            code += f',\n               description="{var["name"].replace("_", " ").title()}"'
            
            # Add validators for critical variables
            if category == 'security' and var['required']:
                code += ',\n               validator=validate_not_empty'
            elif 'URL' in var['name'] or 'ENDPOINT' in var['name']:
                code += ',\n               validator=lambda v: v.startswith(("http://", "https://")) if v else True'
                
            code += '),\n'
            
        code += "    ]\n\n"
        code += f"    for var in {category}_vars:\n"
        code += f"        unified_env.register_var(var, namespace='{category}')\n\n"
    
    return code


def main():
    parser = argparse.ArgumentParser(description='Migrate os.getenv to unified_env')
    parser.add_argument('--analyze', action='store_true', 
                       help='Only analyze files, don\'t migrate')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be changed without modifying files')
    parser.add_argument('--file', type=str,
                       help='Migrate specific file')
    parser.add_argument('--priority-only', action='store_true',
                       help='Only migrate priority files (security-critical)')
    
    args = parser.parse_args()
    
    # Priority files for Phase 2.1 Week 1
    priority_files = [
        'main_secure.py',
        'middleware/auth_secure.py',
        'core/iam/iam_integration.py',
        'shared/clients/iam_service_client.py',
        'shared/security/protection_facade.py',
        'shared/clients/unified_http_client.py'
    ]
    
    if args.file:
        # Migrate specific file
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File {file_path} not found")
            return 1
            
        if args.analyze:
            usages = analyze_file(file_path)
            print(f"\nFound {len(usages)} os.getenv calls in {file_path}:")
            for usage in usages:
                print(f"  L{usage.line_no}: {usage.var_name} "
                      f"{'(default: ' + usage.default_value + ')' if usage.has_default else '(required)'}")
        else:
            success = migrate_file(file_path, dry_run=args.dry_run)
            return 0 if success else 1
            
    else:
        # Find all Python files
        all_usages = []
        files_to_migrate = []
        
        if args.priority_only:
            files_to_check = priority_files
        else:
            files_to_check = []
            for root, _, files in os.walk('.'):
                # Skip virtual environments and test directories
                if any(skip in root for skip in ['venv', 'env', '.git', '__pycache__', 'test']):
                    continue
                    
                for file in files:
                    if file.endswith('.py'):
                        files_to_check.append(os.path.join(root, file))
        
        # Analyze files
        print("Analyzing files for os.getenv usage...")
        for file_path in files_to_check:
            path = Path(file_path)
            if path.exists():
                usages = analyze_file(path)
                if usages:
                    all_usages.extend(usages)
                    files_to_migrate.append(path)
                    
        if args.analyze:
            # Show analysis results
            print(f"\nFound {len(all_usages)} os.getenv calls in {len(files_to_migrate)} files")
            
            # Group by file
            by_file = {}
            for usage in all_usages:
                if usage.file_path not in by_file:
                    by_file[usage.file_path] = []
                by_file[usage.file_path].append(usage)
                
            for file_path, usages in sorted(by_file.items()):
                print(f"\n{file_path} ({len(usages)} calls):")
                for usage in sorted(usages, key=lambda x: x.line_no):
                    print(f"  L{usage.line_no}: {usage.var_name} "
                          f"{'(default: ' + usage.default_value + ')' if usage.has_default else '(required)'}")
                          
            # Generate registration code
            print("\n" + "="*80)
            print("ENVIRONMENT VARIABLE REGISTRATION CODE")
            print("="*80)
            print(generate_env_var_registration(all_usages))
            
        else:
            # Perform migration
            if not files_to_migrate:
                print("✅ No files need migration!")
                return 0
                
            print(f"\nFound {len(files_to_migrate)} files to migrate")
            
            if not args.dry_run:
                response = input("Proceed with migration? (y/n): ")
                if response.lower() != 'y':
                    print("Migration cancelled")
                    return 0
                    
            success_count = 0
            for file_path in files_to_migrate:
                if migrate_file(file_path, dry_run=args.dry_run):
                    success_count += 1
                    
            print(f"\n{'Would migrate' if args.dry_run else 'Migrated'} "
                  f"{success_count}/{len(files_to_migrate)} files successfully")
            
            if not args.dry_run and success_count > 0:
                print("\n⚠️  Don't forget to:")
                print("1. Register any new environment variables in unified_env")
                print("2. Update your .env files with required variables")
                print("3. Run tests to ensure everything works correctly")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())