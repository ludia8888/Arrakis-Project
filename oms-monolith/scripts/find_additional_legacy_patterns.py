#!/usr/bin/env python3
"""
Find additional legacy code patterns not caught in initial cleanup.
"""

import os
import re
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

class LegacyPatternFinder:
    def __init__(self, root_path):
        self.root_path = Path(root_path)
        self.findings = defaultdict(list)
        self.excluded_dirs = {
            '__pycache__', '.git', '.pytest_cache', 'node_modules',
            'venv', 'env', '.venv', 'dist', 'build', '.tox',
            'validation_backup', 'versioning_backup', 'backups',
            'validation_terminus_backup_20250629_140147',
            'legacy_cleanup_backup_20250629_014625'
        }
        
    def is_excluded_path(self, path):
        """Check if path should be excluded from analysis."""
        path_parts = set(path.parts)
        return bool(path_parts.intersection(self.excluded_dirs))
    
    def find_python_files(self):
        """Find all Python files in the project."""
        python_files = []
        for file_path in self.root_path.rglob('*.py'):
            if not self.is_excluded_path(file_path):
                python_files.append(file_path)
        return python_files
    
    def analyze_file(self, file_path):
        """Analyze a single file for legacy patterns."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.splitlines()
                
            relative_path = file_path.relative_to(self.root_path)
            
            # 1. Deprecated imports
            deprecated_imports = [
                (r'from __future__ import', 'Python 2 compatibility import'),
                (r'import imp\b', 'Deprecated imp module'),
                (r'from imp import', 'Deprecated imp module'),
                (r'import compiler\b', 'Deprecated compiler module'),
                (r'from compiler import', 'Deprecated compiler module'),
                (r'import asyncore', 'Deprecated asyncore module'),
                (r'import asynchat', 'Deprecated asynchat module'),
                (r'import smtpd', 'Deprecated smtpd module'),
                (r'import distutils', 'Deprecated distutils module'),
            ]
            
            for pattern, description in deprecated_imports:
                if re.search(pattern, content):
                    self.findings['deprecated_imports'].append({
                        'file': str(relative_path),
                        'pattern': pattern,
                        'description': description
                    })
            
            # 2. Dead code indicators
            dead_code_patterns = [
                (r'^\s*#\s*(TODO|FIXME|HACK|XXX|BUG|DEPRECATED|LEGACY|OLD)', 'Technical debt comment'),
                (r'^\s*pass\s*$', 'Empty implementation'),
                (r'^\s*\.\.\.\s*$', 'Ellipsis placeholder'),
                (r'raise NotImplementedError', 'Not implemented method'),
            ]
            
            for i, line in enumerate(lines, 1):
                for pattern, description in dead_code_patterns:
                    if re.search(pattern, line):
                        self.findings['dead_code'].append({
                            'file': str(relative_path),
                            'line': i,
                            'content': line.strip(),
                            'description': description
                        })
            
            # 3. Hardcoded values
            hardcoded_patterns = [
                (r'localhost:|127\.0\.0\.1', 'Hardcoded localhost'),
                (r'0\.0\.0\.0', 'Hardcoded bind address'),
                (r'port\s*=\s*\d{4,5}', 'Hardcoded port number'),
                (r'PASSWORD\s*=\s*["\'][^"\']+["\']', 'Hardcoded password'),
                (r'SECRET\s*=\s*["\'][^"\']+["\']', 'Hardcoded secret'),
                (r'API_KEY\s*=\s*["\'][^"\']+["\']', 'Hardcoded API key'),
                (r'TOKEN\s*=\s*["\'][^"\']+["\']', 'Hardcoded token'),
                (r'/tmp/', 'Hardcoded temp directory'),
                (r'http://[^/]+/', 'Hardcoded URL'),
            ]
            
            for i, line in enumerate(lines, 1):
                for pattern, description in hardcoded_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        # Skip if it's in a comment
                        if not line.strip().startswith('#'):
                            self.findings['hardcoded_values'].append({
                                'file': str(relative_path),
                                'line': i,
                                'content': line.strip(),
                                'description': description
                            })
            
            # 4. Old error handling
            error_patterns = [
                (r'except\s*:', 'Bare except clause'),
                (r'except\s+Exception\s*:', 'Broad exception handling'),
                (r'sys\.exc_info', 'Old-style exception info'),
                (r'raise\s+\w+,\s*', 'Python 2 style raise'),
            ]
            
            for i, line in enumerate(lines, 1):
                for pattern, description in error_patterns:
                    if re.search(pattern, line):
                        self.findings['old_error_handling'].append({
                            'file': str(relative_path),
                            'line': i,
                            'content': line.strip(),
                            'description': description
                        })
            
            # 5. Old logging patterns
            logging_patterns = [
                (r'\bprint\s*\(', 'Print statement instead of logging'),
                (r'logging\.basicConfig', 'Basic logging config in module'),
                (r'logger\s*=\s*logging\.getLogger\(\s*\)', 'Logger without name'),
            ]
            
            for i, line in enumerate(lines, 1):
                for pattern, description in logging_patterns:
                    if re.search(pattern, line):
                        # Skip if it's in tests or scripts
                        if 'test' not in str(relative_path) and 'script' not in str(relative_path):
                            self.findings['old_logging'].append({
                                'file': str(relative_path),
                                'line': i,
                                'content': line.strip(),
                                'description': description
                            })
            
            # 6. Legacy naming conventions
            naming_patterns = [
                (r'^class\s+[a-z]', 'Class name not in PascalCase'),
                (r'^def\s+[A-Z]', 'Function name not in snake_case'),
                (r'^\s*[A-Z][a-z]+\s*=', 'Constant not in UPPER_CASE'),
            ]
            
            for i, line in enumerate(lines, 1):
                for pattern, description in naming_patterns:
                    if re.search(pattern, line):
                        self.findings['naming_conventions'].append({
                            'file': str(relative_path),
                            'line': i,
                            'content': line.strip(),
                            'description': description
                        })
            
            # 7. Unused imports (simple check)
            import_lines = []
            for i, line in enumerate(lines, 1):
                if re.match(r'^import\s+(\w+)|^from\s+(\w+)', line):
                    import_lines.append((i, line.strip()))
            
            # Check if imported names are used
            for line_num, import_line in import_lines:
                if 'import' in import_line:
                    # Extract imported name
                    match = re.search(r'import\s+(\w+)(?:\s+as\s+(\w+))?', import_line)
                    if match:
                        imported_name = match.group(2) or match.group(1)
                        # Simple check: is the name used elsewhere in the file?
                        if content.count(imported_name) == 1:  # Only in import
                            self.findings['unused_imports'].append({
                                'file': str(relative_path),
                                'line': line_num,
                                'import': import_line,
                                'name': imported_name
                            })
            
            # 8. Deprecated decorators/functions
            deprecated_usage = [
                (r'@unittest\.skipIf', 'Consider using pytest markers'),
                (r'assertEquals', 'Deprecated unittest assertion'),
                (r'assertRegexpMatches', 'Deprecated unittest assertion'),
                (r'urllib\.urlopen', 'Deprecated urllib function'),
                (r'datetime\.utcnow', 'Deprecated datetime method'),
                (r'loop\.run_until_complete', 'Consider using asyncio.run'),
            ]
            
            for pattern, description in deprecated_usage:
                if re.search(pattern, content):
                    self.findings['deprecated_usage'].append({
                        'file': str(relative_path),
                        'pattern': pattern,
                        'description': description
                    })
                    
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
    
    def analyze_requirements(self):
        """Analyze requirements files for outdated dependencies."""
        req_files = list(self.root_path.rglob('requirements*.txt'))
        
        outdated_packages = [
            'nose',  # Use pytest instead
            'mock',  # Built into Python 3
            'configparser',  # Built into Python 3
            'futures',  # Built into Python 3
            'enum34',  # Built into Python 3
            'pathlib2',  # Built into Python 3
            'trollius',  # Old async library
            'tornado<6',  # Old tornado versions
            'django<2',  # Old Django versions
        ]
        
        for req_file in req_files:
            if self.is_excluded_path(req_file):
                continue
                
            try:
                with open(req_file, 'r') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if line and not line.startswith('#'):
                            for pkg in outdated_packages:
                                if pkg in line.lower():
                                    self.findings['outdated_dependencies'].append({
                                        'file': str(req_file.relative_to(self.root_path)),
                                        'line': line_num,
                                        'package': line,
                                        'reason': f'Outdated package: {pkg}'
                                    })
            except Exception as e:
                print(f"Error analyzing {req_file}: {e}")
    
    def analyze_configuration(self):
        """Find configuration files that might contain legacy settings."""
        config_patterns = ['*.ini', '*.cfg', '*.conf', '*.yaml', '*.yml', '*.json']
        
        for pattern in config_patterns:
            for config_file in self.root_path.rglob(pattern):
                if self.is_excluded_path(config_file):
                    continue
                    
                relative_path = config_file.relative_to(self.root_path)
                
                # Check if it's an old or backup config
                if any(x in config_file.name.lower() for x in ['old', 'backup', 'deprecated', 'legacy']):
                    self.findings['legacy_configs'].append({
                        'file': str(relative_path),
                        'reason': 'Config file with legacy naming'
                    })
    
    def run(self):
        """Run the complete analysis."""
        print("Finding Python files...")
        python_files = self.find_python_files()
        print(f"Found {len(python_files)} Python files to analyze")
        
        print("\nAnalyzing Python files...")
        for i, file_path in enumerate(python_files):
            if i % 50 == 0:
                print(f"Progress: {i}/{len(python_files)}")
            self.analyze_file(file_path)
        
        print("\nAnalyzing requirements files...")
        self.analyze_requirements()
        
        print("\nAnalyzing configuration files...")
        self.analyze_configuration()
        
        return self.findings
    
    def generate_report(self):
        """Generate a detailed report of findings."""
        report = {
            'scan_date': datetime.now().isoformat(),
            'root_path': str(self.root_path),
            'summary': {},
            'details': {}
        }
        
        # Generate summary
        for category, items in self.findings.items():
            report['summary'][category] = len(items)
            report['details'][category] = items
        
        # Save JSON report
        report_path = self.root_path / 'legacy_patterns_analysis.json'
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Generate markdown report
        md_report = f"# Additional Legacy Code Pattern Analysis\n\n"
        md_report += f"**Scan Date:** {report['scan_date']}\n\n"
        md_report += "## Summary\n\n"
        
        total_issues = sum(report['summary'].values())
        md_report += f"**Total Issues Found:** {total_issues}\n\n"
        
        for category, count in sorted(report['summary'].items()):
            if count > 0:
                md_report += f"- **{category.replace('_', ' ').title()}:** {count} issues\n"
        
        md_report += "\n## Detailed Findings\n\n"
        
        # Detail sections
        for category, items in sorted(report['details'].items()):
            if items:
                md_report += f"### {category.replace('_', ' ').title()}\n\n"
                
                if category in ['deprecated_imports', 'deprecated_usage', 'legacy_configs']:
                    # Group by file
                    by_file = defaultdict(list)
                    for item in items:
                        by_file[item['file']].append(item)
                    
                    for file_path, file_items in sorted(by_file.items()):
                        md_report += f"**{file_path}**\n"
                        for item in file_items:
                            if 'description' in item:
                                md_report += f"- {item['description']}"
                                if 'pattern' in item:
                                    md_report += f" (pattern: `{item['pattern']}`)"
                            elif 'reason' in item:
                                md_report += f"- {item['reason']}"
                            md_report += "\n"
                        md_report += "\n"
                
                elif category in ['dead_code', 'hardcoded_values', 'old_error_handling', 
                                  'old_logging', 'naming_conventions']:
                    # Group by file and show line numbers
                    by_file = defaultdict(list)
                    for item in items:
                        by_file[item['file']].append(item)
                    
                    for file_path, file_items in sorted(by_file.items()):
                        md_report += f"**{file_path}**\n"
                        for item in sorted(file_items, key=lambda x: x.get('line', 0)):
                            md_report += f"- Line {item['line']}: {item['description']}\n"
                            md_report += f"  ```python\n  {item['content']}\n  ```\n"
                        md_report += "\n"
                
                elif category == 'unused_imports':
                    # Group by file
                    by_file = defaultdict(list)
                    for item in items:
                        by_file[item['file']].append(item)
                    
                    for file_path, file_items in sorted(by_file.items()):
                        md_report += f"**{file_path}**\n"
                        for item in sorted(file_items, key=lambda x: x['line']):
                            md_report += f"- Line {item['line']}: `{item['import']}` "
                            md_report += f"(unused: `{item['name']}`)\n"
                        md_report += "\n"
                
                elif category == 'outdated_dependencies':
                    # Group by file
                    by_file = defaultdict(list)
                    for item in items:
                        by_file[item['file']].append(item)
                    
                    for file_path, file_items in sorted(by_file.items()):
                        md_report += f"**{file_path}**\n"
                        for item in file_items:
                            md_report += f"- Line {item['line']}: `{item['package']}` - {item['reason']}\n"
                        md_report += "\n"
        
        # Add recommendations
        md_report += "\n## Recommendations\n\n"
        
        if report['summary'].get('deprecated_imports', 0) > 0:
            md_report += "### Deprecated Imports\n"
            md_report += "- Remove Python 2 compatibility imports (__future__)\n"
            md_report += "- Replace deprecated modules with modern alternatives\n\n"
        
        if report['summary'].get('hardcoded_values', 0) > 0:
            md_report += "### Hardcoded Values\n"
            md_report += "- Move hardcoded values to configuration files or environment variables\n"
            md_report += "- Use configuration management libraries like python-decouple or pydantic\n\n"
        
        if report['summary'].get('old_error_handling', 0) > 0:
            md_report += "### Error Handling\n"
            md_report += "- Replace bare except clauses with specific exception types\n"
            md_report += "- Use modern exception handling with context managers where appropriate\n\n"
        
        if report['summary'].get('old_logging', 0) > 0:
            md_report += "### Logging\n"
            md_report += "- Replace print statements with proper logging\n"
            md_report += "- Use named loggers: `logging.getLogger(__name__)`\n"
            md_report += "- Configure logging at application entry point, not in modules\n\n"
        
        if report['summary'].get('unused_imports', 0) > 0:
            md_report += "### Unused Imports\n"
            md_report += "- Remove unused imports to improve code clarity\n"
            md_report += "- Use tools like autoflake or isort to manage imports\n\n"
        
        # Save markdown report
        md_path = self.root_path / 'ADDITIONAL_LEGACY_PATTERNS_REPORT.md'
        with open(md_path, 'w') as f:
            f.write(md_report)
        
        print(f"\nReports generated:")
        print(f"- JSON: {report_path}")
        print(f"- Markdown: {md_path}")
        
        return report


def main():
    # Get the project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    print(f"Analyzing legacy patterns in: {project_root}")
    
    finder = LegacyPatternFinder(project_root)
    findings = finder.run()
    report = finder.generate_report()
    
    # Print summary
    print("\n" + "="*60)
    print("SUMMARY OF FINDINGS")
    print("="*60)
    
    total_issues = sum(report['summary'].values())
    print(f"\nTotal issues found: {total_issues}")
    
    for category, count in sorted(report['summary'].items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            print(f"{category.replace('_', ' ').title():.<40} {count:>5}")
    
    print("\nDetailed reports have been generated. Please review:")
    print("- ADDITIONAL_LEGACY_PATTERNS_REPORT.md")
    print("- legacy_patterns_analysis.json")


if __name__ == "__main__":
    main()