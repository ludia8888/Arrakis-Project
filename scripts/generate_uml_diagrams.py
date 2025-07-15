#!/usr/bin/env python3
"""
Production-ready UML diagram generator using pyreverse for Arrakis microservices.
Generates comprehensive class diagrams, package diagrams, and architectural views.
"""

import argparse
import concurrent.futures
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class UMLGenerator:
    """Generate comprehensive UML diagrams for Python microservices."""

    SERVICES = [
        "ontology-management-service",
        "user-service",
        "audit-service",
        "data-kernel-service",
        "embedding-service",
        "scheduler-service",
        "event-gateway",
    ]

    # Pyreverse configuration templates
    DIAGRAM_CONFIGS = {
        "overview": {
            "options": [
                "--colorized",
                "--all-ancestors",
                "--all-associated",
                "--filter-mode = ALL",
                "--max-color-depth = 5",
            ],
            "description": "Complete overview with all relationships",
        },
        "core": {
            "options": [
                "--colorized",
                "--show-builtin",
                "--module-names = y",
                "--max-color-depth = 3",
            ],
            "modules": ["core", "api", "models"],
            "description": "Core business logic and models",
        },
        "api": {
            "options": ["--colorized", "--all-associated", "--show-associated = 2"],
            "modules": ["api", "routes", "endpoints"],
            "description": "API layer and endpoints",
        },
        "database": {
            "options": ["--colorized", "--all-ancestors", "--show-builtin"],
            "modules": ["database", "models", "repositories"],
            "description": "Database models and repositories",
        },
        "services": {
            "options": ["--colorized", "--all-associated", "--show-associated = 1"],
            "modules": ["services", "core", "shared"],
            "description": "Service layer architecture",
        },
        "packages": {
            "options": ["--colorized", "-k"],  # packages only
            "description": "Package structure overview",
        },
    }

    # PlantUML templates for custom diagrams
    PLANTUML_TEMPLATES = {
        "component": """@startuml {title}
!theme cerulean
skinparam componentStyle rectangle

title {title}

package "{service}" {{
{components}
}}

{relationships}

@enduml
""",
        "sequence": """@startuml {title}
!theme cerulean
skinparam sequenceMessageAlign center

title {title}

{participants}

{interactions}

@enduml
""",
        "deployment": """@startuml {title}
!theme cerulean

title {title} - Deployment Architecture

node "Kubernetes Cluster" {{
  node "Namespace: {service}" {{
    component [Service] as svc
    component [Deployment] as dep
    component [ConfigMap] as cm
    component [Secret] as sec

    database "PostgreSQL" as db
    queue "Redis Cache" as cache
    queue "NATS" as nats
  }}
}}

cloud "AWS Services" {{
  storage "S3 Bucket" as s3
  component "RDS Instance" as rds
  component "ElastiCache" as ec
}}

svc --> dep
dep --> cm
dep --> sec
dep --> db
dep --> cache
dep --> nats
dep --> s3
db --> rds
cache --> ec

@enduml
""",
    }

    def __init__(self, root_path: str = ".", output_dir: str = "docs/uml"):
        self.root_path = Path(root_path).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Check dependencies
        self._check_dependencies()

    def _check_dependencies(self):
        """Check and install required tools."""
        logger.info("Checking required dependencies...")

        # Check for pyreverse (part of pylint)
        try:
            subprocess.run(["pyreverse", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("pyreverse not found. Installing pylint...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "pylint"], check=True
            )

        # Check for PlantUML (optional)
        self.plantuml_available = False
        try:
            subprocess.run(["plantuml", "-version"], capture_output=True, check=True)
            self.plantuml_available = True
            logger.info("PlantUML found - will generate additional diagrams")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.info("PlantUML not found - skipping PlantUML diagrams")

        # Check for graphviz
        try:
            subprocess.run(["dot", "-V"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("Graphviz not found! Please install graphviz.")
            raise RuntimeError("Graphviz is required for diagram generation")

    def generate_service_diagrams(
        self, service: str, diagram_types: List[str] = None
    ) -> Dict:
        """Generate UML diagrams for a single service."""
        if diagram_types is None:
            diagram_types = list(self.DIAGRAM_CONFIGS.keys())

        logger.info(f"Generating UML diagrams for {service}...")
        service_path = self.root_path / service

        if not service_path.exists():
            logger.warning(f"Service path not found: {service_path}")
            return {}

        output_path = self.output_dir / service
        output_path.mkdir(parents=True, exist_ok=True)

        results = {
            "service": service,
            "timestamp": datetime.utcnow().isoformat(),
            "diagrams": {},
        }

        # Change to service directory
        original_cwd = os.getcwd()
        os.chdir(service_path)

        try:
            # Generate pyreverse diagrams
            for diagram_type in diagram_types:
                if diagram_type in self.DIAGRAM_CONFIGS:
                    result = self._generate_pyreverse_diagram(
                        service, diagram_type, output_path
                    )
                    results["diagrams"][diagram_type] = result

            # Generate custom diagrams if PlantUML is available
            if self.plantuml_available:
                custom_results = self._generate_custom_diagrams(
                    service, service_path, output_path
                )
                results["diagrams"].update(custom_results)

            # Generate architecture overview
            self._generate_architecture_overview(service, service_path, output_path)

            # Generate documentation
            self._generate_diagram_documentation(service, results, output_path)

        finally:
            os.chdir(original_cwd)

        return results

    def _generate_pyreverse_diagram(
        self, service: str, diagram_type: str, output_path: Path
    ) -> Dict:
        """Generate a specific type of pyreverse diagram."""
        config = self.DIAGRAM_CONFIGS[diagram_type]
        diagram_path = output_path / diagram_type
        diagram_path.mkdir(exist_ok=True)

        result = {
            "type": diagram_type,
            "description": config["description"],
            "files": [],
        }

        try:
            # Build command
            cmd = [
                "pyreverse",
                "-o",
                "svg",
                "-p",
                f"{service}_{diagram_type}",
                "-d",
                str(diagram_path),
            ]
            cmd.extend(config["options"])

            # Add specific modules if configured
            if "modules" in config:
                modules = []
                for module in config["modules"]:
                    if Path(module).exists():
                        modules.append(module)
                if modules:
                    cmd.extend(modules)
                else:
                    cmd.append(".")  # Use entire service if no modules found
            else:
                cmd.append(".")

            # Run pyreverse
            logger.info(f"Running: {' '.join(cmd)}")
            process = subprocess.run(cmd, capture_output=True, text=True)

            if process.returncode != 0:
                logger.warning(f"pyreverse warning: {process.stderr}")

            # Find generated files
            for file in diagram_path.glob("*.svg"):
                result["files"].append(str(file.relative_to(self.output_dir)))

            # Convert to PNG for better compatibility
            for svg_file in diagram_path.glob("*.svg"):
                png_file = svg_file.with_suffix(".png")
                try:
                    subprocess.run(
                        ["convert", str(svg_file), str(png_file)],
                        capture_output=True,
                        check=True,
                    )
                    result["files"].append(str(png_file.relative_to(self.output_dir)))
                except:
                    pass  # ImageMagick not available

        except Exception as e:
            logger.error(f"Error generating {diagram_type} diagram: {e}")
            result["error"] = str(e)

        return result

    def _generate_custom_diagrams(
        self, service: str, service_path: Path, output_path: Path
    ) -> Dict:
        """Generate custom PlantUML diagrams."""
        custom_path = output_path / "custom"
        custom_path.mkdir(exist_ok=True)

        results = {}

        # Component diagram
        component_uml = self.PLANTUML_TEMPLATES["component"].format(
            title=f"{service} Component Architecture",
            service=service,
            components=self._extract_components(service_path),
            relationships=self._extract_relationships(service_path),
        )

        component_file = custom_path / "component.puml"
        with open(component_file, "w") as f:
            f.write(component_uml)

        # Generate SVG
        try:
            subprocess.run(
                ["plantuml", "-tsvg", str(component_file)],
                capture_output=True,
                check=True,
            )
            results["component"] = {
                "type": "component",
                "description": "Component architecture diagram",
                "files": [
                    str((custom_path / "component.svg").relative_to(self.output_dir))
                ],
            }
        except Exception as e:
            logger.error(f"Error generating component diagram: {e}")

        # Deployment diagram
        deployment_uml = self.PLANTUML_TEMPLATES["deployment"].format(
            title=f"{service} Deployment", service=service
        )

        deployment_file = custom_path / "deployment.puml"
        with open(deployment_file, "w") as f:
            f.write(deployment_uml)

        try:
            subprocess.run(
                ["plantuml", "-tsvg", str(deployment_file)],
                capture_output=True,
                check=True,
            )
            results["deployment"] = {
                "type": "deployment",
                "description": "Deployment architecture diagram",
                "files": [
                    str((custom_path / "deployment.svg").relative_to(self.output_dir))
                ],
            }
        except Exception as e:
            logger.error(f"Error generating deployment diagram: {e}")

        return results

    def _extract_components(self, service_path: Path) -> str:
        """Extract components from service structure."""
        components = []

        # Standard components
        standard_dirs = ["api", "core", "models", "services", "database", "middleware"]

        for dir_name in standard_dirs:
            dir_path = service_path / dir_name
            if dir_path.exists() and dir_path.is_dir():
                components.append(f"  component [{dir_name.title()}] as {dir_name}")

        return "\n".join(components)

    def _extract_relationships(self, service_path: Path) -> str:
        """Extract relationships between components."""
        relationships = []

        # Common relationships
        if (service_path / "api").exists() and (service_path / "core").exists():
            relationships.append("api --> core : uses")

        if (service_path / "core").exists() and (service_path / "database").exists():
            relationships.append("core --> database : queries")

        if (service_path / "api").exists() and (service_path / "middleware").exists():
            relationships.append("api --> middleware : applies")

        return "\n".join(relationships)

    def _generate_architecture_overview(
        self, service: str, service_path: Path, output_path: Path
    ):
        """Generate architecture overview diagram using code analysis."""
        arch_path = output_path / "architecture"
        arch_path.mkdir(exist_ok=True)

        # Analyze service structure
        structure = self._analyze_service_structure(service_path)

        # Create Graphviz diagram
        dot_content = self._create_architecture_dot(service, structure)

        dot_file = arch_path / "architecture.dot"
        with open(dot_file, "w") as f:
            f.write(dot_content)

        # Generate SVG
        try:
            subprocess.run(
                [
                    "dot",
                    "-Tsvg",
                    str(dot_file),
                    "-o",
                    str(arch_path / "architecture.svg"),
                ],
                check=True,
            )
        except Exception as e:
            logger.error(f"Error generating architecture diagram: {e}")

    def _analyze_service_structure(self, service_path: Path) -> Dict:
        """Analyze service code structure."""
        structure = {"modules": {}, "dependencies": {}, "patterns": []}

        # Analyze Python files
        for py_file in service_path.rglob("*.py"):
            if any(part in py_file.parts for part in ["test", "__pycache__", ".venv"]):
                continue

            module_path = py_file.relative_to(service_path).parent
            module_name = str(module_path).replace("/", ".")

            if module_name not in structure["modules"]:
                structure["modules"][module_name] = {
                    "files": [],
                    "classes": [],
                    "functions": [],
                }

            structure["modules"][module_name]["files"].append(py_file.name)

            # Simple pattern detection
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                    # Detect patterns
                    if "Repository" in content:
                        structure["patterns"].append("Repository")
                    if "Service" in content:
                        structure["patterns"].append("Service")
                    if "@router" in content or "APIRouter" in content:
                        structure["patterns"].append("API Router")
                    if "Base" in content and "declarative_base" in content:
                        structure["patterns"].append("SQLAlchemy")
            except:
                pass

        return structure

    def _create_architecture_dot(self, service: str, structure: Dict) -> str:
        """Create Graphviz DOT content for architecture diagram."""
        dot_lines = [
            f'digraph "{service}_architecture" {{',
            "  rankdir = TB;",
            "  node [shape = box, style = rounded];",
            "  edge [color = gray];",
            "",
            "  // Service layers",
            "  subgraph cluster_0 {",
            f'    label="{service}";',
            "    style = filled;",
            "    fillcolor = lightgray;",
            "",
        ]

        # Add modules as nodes
        for module, info in structure["modules"].items():
            if module:  # Skip root module
                file_count = len(info["files"])
                label = f"{module}\\n({file_count} files)"
                dot_lines.append(f'    "{module}" [label="{label}"];')

        dot_lines.extend(["  }", "", "  // Dependencies"])

        # Add common dependencies
        if "api" in structure["modules"] and "core" in structure["modules"]:
            dot_lines.append('  "api" -> "core";')

        if "core" in structure["modules"] and "database" in structure["modules"]:
            dot_lines.append('  "core" -> "database";')

        dot_lines.append("}")

        return "\n".join(dot_lines)

    def _generate_diagram_documentation(
        self, service: str, results: Dict, output_path: Path
    ):
        """Generate documentation for all diagrams."""
        doc_path = output_path / "README.md"

        with open(doc_path, "w") as f:
            f.write(
                """# UML Diagrams: {service}

Generated on: {results['timestamp']}

## Available Diagrams

"""
            )

            # Document each diagram type
            for diagram_type, result in results["diagrams"].items():
                if "error" not in result:
                    f.write(f"### {diagram_type.title()} Diagram\n\n")
                    f.write(f"**Description:** {result.get('description', 'N/A')}\n\n")

                    if "files" in result:
                        for file in result["files"]:
                            if file.endswith(".svg"):
                                f.write(f"![{diagram_type}]({file})\n\n")
                            else:
                                f.write(f"- [{file}]({file})\n")

                    f.write("\n")

            f.write(
                """## Diagram Types Explained

### Overview Diagrams
Complete class hierarchy with all relationships, inheritance, and associations.

### Core Diagrams
Focus on core business logic, domain models, and essential services.

### API Diagrams
Show API endpoints, routers, and request/response flow.

### Database Diagrams
Database models, repositories, and data access patterns.

### Package Diagrams
High-level package structure and dependencies.

### Architecture Diagrams
Custom architectural views showing component relationships.

## Reading the Diagrams

### Class Diagrams
- **Boxes**: Classes with attributes and methods
- **Arrows**: Inheritance (empty triangle) or associations
- **Colors**: Module grouping or inheritance depth

### Package Diagrams
- **Boxes**: Python packages/modules
- **Arrows**: Import dependencies
- **Clusters**: Related packages grouped together

## Generating Diagrams Locally

```bash
# Generate all diagrams
python scripts/generate_uml_diagrams.py --service {service}

# Generate specific diagram type
python scripts/generate_uml_diagrams.py --service {service} --types overview core

# Generate for all services
python scripts/generate_uml_diagrams.py --all
```

## Customizing Diagrams

Edit `scripts/generate_uml_diagrams.py` to:
- Add new diagram types
- Customize colors and styles
- Filter specific modules or classes
- Add custom PlantUML templates

## Integration with CI/CD

These diagrams are automatically regenerated on:
- Code changes to Python files
- Pull requests
- Nightly builds

See `.github/workflows/dependency-visualization.yml` for details.
"""
            )

    def generate_all_services(self, parallel: bool = True) -> Dict[str, Dict]:
        """Generate diagrams for all services."""
        logger.info(
            f"Generating UML diagrams for all services (parallel={parallel})..."
        )

        results = {}

        if parallel:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                future_to_service = {
                    executor.submit(self.generate_service_diagrams, service): service
                    for service in self.SERVICES
                }

                for future in concurrent.futures.as_completed(future_to_service):
                    service = future_to_service[future]
                    try:
                        results[service] = future.result()
                    except Exception as e:
                        logger.error(f"Failed to generate diagrams for {service}: {e}")
                        results[service] = {"error": str(e)}
        else:
            for service in self.SERVICES:
                try:
                    results[service] = self.generate_service_diagrams(service)
                except Exception as e:
                    logger.error(f"Failed to generate diagrams for {service}: {e}")
                    results[service] = {"error": str(e)}

        # Generate index
        self._generate_index(results)

        return results

    def _generate_index(self, results: Dict[str, Dict]):
        """Generate index page for all UML diagrams."""
        index_path = self.output_dir / "README.md"

        with open(index_path, "w") as f:
            f.write(
                """# Arrakis Project - UML Diagrams

Generated on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

## Services

| Service | Status | Diagram Types | View |
|---------|--------|---------------|------|
"""
            )

            for service, result in results.items():
                status = "❌ Error" if "error" in result else "✅ Success"
                diagram_count = len(result.get("diagrams", {}))
                f.write(
                    f"| {service} | {status} | {diagram_count} types | [View](./{service}/) |\n"
                )

            f.write(
                """
## Quick Links

### By Diagram Type

#### Overview Diagrams
"""
            )

            for service in self.SERVICES:
                f.write(f"- [{service}](./{service}/overview/)\n")

            f.write(
                """
#### Core Logic Diagrams
"""
            )

            for service in self.SERVICES:
                f.write(f"- [{service}](./{service}/core/)\n")

            f.write(
                """
#### API Layer Diagrams
"""
            )

            for service in self.SERVICES:
                f.write(f"- [{service}](./{service}/api/)\n")

            f.write(
                """
## Viewing Tips

1. **SVG files**: Best for web viewing, scalable
2. **PNG files**: Best for documentation, fixed size
3. **Architecture diagrams**: Show high-level component relationships
4. **Class diagrams**: Show detailed class structures

## Regenerating Diagrams

```bash
# Regenerate all
python scripts/generate_uml_diagrams.py --all

# Regenerate specific service
python scripts/generate_uml_diagrams.py --service <service-name>
```

## CI/CD Integration

These diagrams are automatically updated via GitHub Actions when:
- Python code changes are pushed
- Pull requests are created
- Manual workflow dispatch is triggered

## Tools Used

- **pyreverse**: Part of pylint, generates class and package diagrams
- **PlantUML**: Custom architectural diagrams (if available)
- **Graphviz**: Graph visualization for architecture diagrams
"""
            )


def main():
    """Main entry point for UML generation."""
    parser = argparse.ArgumentParser(
        description="Generate UML diagrams for Arrakis microservices"
    )
    parser.add_argument(
        "--service",
        choices=UMLGenerator.SERVICES + ["all"],
        help="Service to generate diagrams for",
    )
    parser.add_argument(
        "--all", action="store_true", help="Generate diagrams for all services"
    )
    parser.add_argument(
        "--types",
        nargs="+",
        choices=list(UMLGenerator.DIAGRAM_CONFIGS.keys()),
        help="Specific diagram types to generate",
    )
    parser.add_argument(
        "--output", default="docs/uml", help="Output directory for diagrams"
    )
    parser.add_argument(
        "--parallel", action="store_true", help="Generate diagrams in parallel"
    )

    args = parser.parse_args()

    if not args.service and not args.all:
        parser.error("Either --service or --all must be specified")

    generator = UMLGenerator(output_dir=args.output)

    if args.all or args.service == "all":
        results = generator.generate_all_services(parallel=args.parallel)
        logger.info(f"Generated diagrams for {len(results)} services")
        logger.info(f"View all diagrams at: {args.output}/")
    else:
        result = generator.generate_service_diagrams(
            args.service, diagram_types=args.types
        )

        if "error" not in result:
            logger.info(f"Successfully generated diagrams for {args.service}")
            logger.info(f"View diagrams at: {args.output}/{args.service}/")

            # Print summary
            print(f"\nGenerated diagrams for {args.service}:")
            for diagram_type, info in result["diagrams"].items():
                if "files" in info:
                    print(f"  - {diagram_type}: {len(info['files'])} files")
        else:
            logger.error(f"Failed to generate diagrams: {result['error']}")


if __name__ == "__main__":
    main()
