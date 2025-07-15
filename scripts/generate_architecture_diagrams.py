#!/usr/bin/env python3
"""
Architecture Diagram Generator for Arrakis Platform
Automatically generates Mermaid diagrams from codebase analysis
"""

import argparse
import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml

logging.basicConfig(level = logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ServiceInfo:
    name: str
    type: str  # 'service', 'database', 'cache', 'messaging'
    port: Optional[int] = None
    dependencies: List[str] = None
    apis: List[str] = None
    description: str = ""
    tech_stack: List[str] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.apis is None:
            self.apis = []
        if self.tech_stack is None:
            self.tech_stack = []

@dataclass
class ServiceDependency:
    from_service: str
    to_service: str
    type: str  # 'http', 'grpc', 'database', 'cache', 'messaging'
    description: str = ""

class ArchitectureDiagramGenerator:
    def __init__(self, project_root: str, output_dir: str = "docs/diagrams"):
        self.project_root = Path(project_root)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents = True, exist_ok = True)

        self.services: Dict[str, ServiceInfo] = {}
        self.dependencies: List[ServiceDependency] = []
        self.docker_compose_data = {}

    def analyze_project(self):
        """Analyze the entire project structure"""
        logger.info("🔍 Analyzing Arrakis project structure...")

        # Parse docker-compose files
        self._parse_docker_compose()

        # Analyze service directories
        self._analyze_services()

        # Extract dependencies from code
        self._extract_dependencies()

        # Parse catalog-info.yaml files
        self._parse_backstage_catalogs()

        logger.info(f"📊 Analysis complete: {len(self.services)} services,
            {len(self.dependencies)} dependencies")

    def _parse_docker_compose(self):
        """Parse docker-compose files to extract service information"""
        compose_files = [
            "docker-compose.yml",
            "docker-compose-simple.yml"
        ]

        for compose_file in compose_files:
            compose_path = self.project_root / compose_file
            if compose_path.exists():
                logger.info(f"📋 Parsing {compose_file}")
                with open(compose_path, 'r') as f:
                    data = yaml.safe_load(f)
                    self.docker_compose_data.update(data.get('services', {}))

        # Extract service information from docker-compose
        for service_name, config in self.docker_compose_data.items():
            ports = config.get('ports', [])
            port = None
            if ports:
                # Extract port from "8000:8000" format
                port_mapping = ports[0] if isinstance(ports[0], str) else str(ports[0])
                port = int(port_mapping.split(':')[0])

            # Determine service type
            service_type = self._determine_service_type(service_name, config)

            # Extract dependencies from depends_on and environment
            dependencies = []
            if 'depends_on' in config:
                if isinstance(config['depends_on'], list):
                    dependencies = config['depends_on']
                elif isinstance(config['depends_on'], dict):
                    dependencies = list(config['depends_on'].keys())

            # Extract tech stack information
            tech_stack = self._extract_tech_stack(service_name, config)

            service_info = ServiceInfo(
                name = service_name,
                type = service_type,
                port = port,
                dependencies = dependencies,
                tech_stack = tech_stack,
                description = self._generate_service_description(service_name, config)
            )

            self.services[service_name] = service_info

    def _determine_service_type(self, service_name: str, config: Dict) -> str:
        """Determine the type of service based on name and configuration"""
        if service_name in ['postgres', 'postgresql']:
            return 'database'
        elif service_name in ['redis']:
            return 'cache'
        elif service_name in ['nats']:
            return 'messaging'
        elif service_name in ['terminusdb']:
            return 'database'
        elif service_name in ['prometheus', 'grafana', 'jaeger', 'alertmanager']:
            return 'monitoring'
        elif service_name in ['nginx']:
            return 'gateway'
        else:
            return 'service'

    def _extract_tech_stack(self, service_name: str, config: Dict) -> List[str]:
        """Extract technology stack from service configuration"""
        tech_stack = []

        # Check image for technology hints
        image = config.get('image', '')
        if 'python' in image or service_name.endswith('-service'):
            tech_stack.extend(['Python', 'FastAPI'])
        if 'postgres' in image:
            tech_stack.append('PostgreSQL')
        if 'redis' in image:
            tech_stack.append('Redis')
        if 'nats' in image:
            tech_stack.append('NATS')

        # Check environment variables for additional tech
        env_vars = config.get('environment', [])
        if isinstance(env_vars, list):
            env_string = ' '.join(env_vars)
        else:
            env_string = ' '.join(f"{k}={v}" for k, v in env_vars.items())

        if 'TERMINUSDB' in env_string:
            tech_stack.append('TerminusDB')
        if 'GRPC' in env_string:
            tech_stack.append('gRPC')
        if 'PROMETHEUS' in env_string:
            tech_stack.append('Prometheus')

        return list(set(tech_stack))

    def _generate_service_description(self, service_name: str, config: Dict) -> str:
        """Generate a description for the service"""
        descriptions = {
            'oms': 'Core ontology management and schema service',
            'ontology-management-service': 'Core ontology management and schema service',


            'user-service': 'Authentication and user management',
            'audit-service': 'Audit logging and compliance tracking',
            'data-kernel-service': 'High-performance data processing',
            'embedding-service': 'ML embeddings and vector search',
            'scheduler-service': 'Job scheduling and task management',
            'event-gateway': 'Event streaming and webhook management',
            'postgres': 'PostgreSQL relational database',
            'redis': 'Redis in-memory cache',
            'nats': 'NATS message broker',
            'terminusdb': 'TerminusDB graph database',
            'prometheus': 'Metrics collection and monitoring',
            'grafana': 'Visualization and dashboards',
            'jaeger': 'Distributed tracing',
            'nginx': 'API gateway and reverse proxy'
        }

        return descriptions.get(service_name, f"{service_name} service")

    def _analyze_services(self):
        """Analyze individual service directories for detailed information"""
        service_dirs = [
            'ontology-management-service',
            'user-service',
            'audit-service',
            'data-kernel-service',
            'embedding-service',
            'scheduler-service',
            'event-gateway'
        ]

        for service_dir in service_dirs:
            service_path = self.project_root / service_dir
            if service_path.exists():
                self._analyze_service_directory(service_dir, service_path)

    def _analyze_service_directory(self, service_name: str, service_path: Path):
        """Analyze a single service directory"""
        logger.info(f"🔍 Analyzing {service_name}")

        # Look for API definitions
        apis = []

        # Check for FastAPI apps
        for py_file in service_path.rglob("*.py"):
            if self._is_fastapi_app(py_file):
                apis.append("REST API")

        # Check for gRPC services
        for proto_file in service_path.rglob("*.proto"):
            apis.append("gRPC API")

        # Check for GraphQL
        for py_file in service_path.rglob("*.py"):
            if self._has_graphql(py_file):
                apis.append("GraphQL API")

        # Check for WebSocket
        for py_file in service_path.rglob("*.py"):
            if self._has_websocket(py_file):
                apis.append("WebSocket API")

        # Update service info
        if service_name in self.services:
            self.services[service_name].apis = list(set(apis))

    def _is_fastapi_app(self, file_path: Path) -> bool:
        """Check if file contains FastAPI application"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                return 'FastAPI' in content and ('@app.' in content or 'app = FastAPI' in content)
        except (IOError, UnicodeDecodeError) as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return False

    def _has_graphql(self, file_path: Path) -> bool:
        """Check if file contains GraphQL code"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                return 'graphql' in content.lower() or 'subscription' in content
        except (IOError, UnicodeDecodeError) as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return False

    def _has_websocket(self, file_path: Path) -> bool:
        """Check if file contains WebSocket code"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                return 'websocket' in content.lower() or 'WebSocket' in content
        except (IOError, UnicodeDecodeError) as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return False

    def _extract_dependencies(self):
        """Extract service dependencies from code and configuration"""
        # Extract from docker-compose dependencies
        for service_name, service_info in self.services.items():
            for dep in service_info.dependencies:
                if dep in self.services:
                    dependency_type = self._determine_dependency_type(service_name, dep)
                    self.dependencies.append(ServiceDependency(
                        from_service = service_name,
                        to_service = dep,
                        type = dependency_type,
                        description = f"{service_name} depends on {dep}"
                    ))

        # Extract from environment variables (service URLs)
        for service_name, config in self.docker_compose_data.items():
            env_vars = config.get('environment', [])
            if isinstance(env_vars, dict):
                for key, value in env_vars.items():
                    if '_URL' in key or '_ENDPOINT' in key:
                        target_service = self._extract_service_from_url(str(value))
                        if target_service and target_service in self.services:
                            dep_type = self._determine_dependency_type_from_env(key,
                                value)
                            self.dependencies.append(ServiceDependency(
                                from_service = service_name,
                                to_service = target_service,
                                type = dep_type,
                                description = f"{service_name} connects to {target_service} via {key}"
                            ))

    def _determine_dependency_type(self, from_service: str, to_service: str) -> str:
        """Determine the type of dependency between services"""
        to_service_info = self.services.get(to_service, {})
        to_service_type = getattr(to_service_info, 'type', 'service')

        type_mapping = {
            'database': 'database',
            'cache': 'cache',
            'messaging': 'messaging',
            'monitoring': 'monitoring',
            'gateway': 'http',
            'service': 'http'
        }

        return type_mapping.get(to_service_type, 'http')

    def _determine_dependency_type_from_env(self, env_key: str, env_value: str) -> str:
        """Determine dependency type from environment variable"""
        if 'GRPC' in env_key:
            return 'grpc'
        elif 'DATABASE' in env_key or 'DB' in env_key:
            return 'database'
        elif 'REDIS' in env_key:
            return 'cache'
        elif 'NATS' in env_key:
            return 'messaging'
        else:
            return 'http'

    def _extract_service_from_url(self, url: str) -> Optional[str]:
        """Extract service name from URL"""
        # Handle service discovery format like "http://service-name:port"
        import re
        match = re.search(r'://([^:]+)', url)
        if match:
            return match.group(1)
        return None

    def _parse_backstage_catalogs(self):
        """Parse Backstage catalog-info.yaml files for additional service information"""
        for service_name in self.services.keys():
            catalog_path = self.project_root / service_name / "catalog-info.yaml"
            if catalog_path.exists():
                logger.info(f"📋 Parsing Backstage catalog for {service_name}")
                with open(catalog_path, 'r') as f:
                    try:
                        docs = list(yaml.safe_load_all(f))
                        for doc in docs:
                            if doc and doc.get('kind') == 'Component':
                                self._update_service_from_catalog(service_name, doc)
                    except Exception as e:
                        logger.warning(f"Could not parse catalog for {service_name}: {e}")

    def _update_service_from_catalog(self, service_name: str, catalog_doc: Dict):
        """Update service information from Backstage catalog"""
        if service_name in self.services:
            metadata = catalog_doc.get('metadata', {})
            spec = catalog_doc.get('spec', {})

            # Update description
            if 'description' in metadata:
                self.services[service_name].description = metadata['description']

            # Update APIs from provides/consumes
            provides_apis = spec.get('providesApis', [])
            consumes_apis = spec.get('consumesApis', [])

            if provides_apis:
                self.services[service_name].apis.extend(provides_apis)
                self.services[service_name].apis = list(set(self.services[service_name].apis))

    def generate_system_overview_diagram(self) -> str:
        """Generate high-level system overview diagram"""
        logger.info("🎨 Generating system overview diagram")

        mermaid = [
            "```mermaid",
            "graph TB",
            "    %% Arrakis Platform System Overview",
            ""
        ]

        # Define subgraphs for different layers
        mermaid.extend([
            "    subgraph \"🌐 API Gateway Layer\"",
            "        nginx[\"🔄 Nginx < br/>API Gateway\"]",
            "    end",
            "",
            "    subgraph \"🏗️ Application Services\"",
        ])

        # Add application services
        app_services = [s for s in self.services.values() if s.type == 'service']
        for service in app_services:
            icon = self._get_service_icon(service.name)
            tech_info = f"<br/>{',
                '.join(service.tech_stack[:2])}" if service.tech_stack else ""
            mermaid.append(f"        {service.name}[\"{icon} {service.name.replace('-',
                ' ').title()}{tech_info}\"]")

        mermaid.extend([
            "    end",
            "",
            "    subgraph \"💾 Data Layer\"",
        ])

        # Add data services
        data_services = [s for s in self.services.values() if s.type in ['database',
            'cache']]
        for service in data_services:
            icon = self._get_service_icon(service.name)
            mermaid.append(f"        {service.name}[\"{icon} {service.name.title()}\"]")

        mermaid.extend([
            "    end",
            "",
            "    subgraph \"📡 Infrastructure\"",
        ])

        # Add infrastructure services
        infra_services = [s for s in self.services.values() if s.type in ['messaging',
            'monitoring']]
        for service in infra_services:
            icon = self._get_service_icon(service.name)
            mermaid.append(f"        {service.name}[\"{icon} {service.name.title()}\"]")

        mermaid.extend([
            "    end",
            ""
        ])

        # Add connections
        mermaid.append("    %% Service Dependencies")
        for dep in self.dependencies:
            if dep.from_service in self.services and dep.to_service in self.services:
                arrow_style = self._get_arrow_style(dep.type)
                mermaid.append(f"    {dep.from_service} {arrow_style} {dep.to_service}")

        # Add styling
        mermaid.extend([
            "",
            "    %% Styling",
            "    classDef serviceClass fill:#e1f5fe,stroke:#01579b,stroke-width:2px",
            "    classDef databaseClass fill:#f3e5f5,stroke:#4a148c,stroke-width:2px",
            "    classDef cacheClass fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px",
            "    classDef messagingClass fill:#fff3e0,stroke:#e65100,stroke-width:2px",
            "    classDef monitoringClass fill:#fce4ec,stroke:#880e4f,stroke-width:2px",
            "    classDef gatewayClass fill:#e0f2f1,stroke:#004d40,stroke-width:2px",
            ""
        ])

        # Apply styling
        for service in self.services.values():
            class_name = f"{service.type}Class"
            mermaid.append(f"    class {service.name} {class_name}")

        mermaid.append("```")

        return "\n".join(mermaid)

    def generate_service_dependency_diagram(self) -> str:
        """Generate detailed service dependency diagram"""
        logger.info("🎨 Generating service dependency diagram")

        mermaid = [
            "```mermaid",
            "graph LR",
            "    %% Arrakis Platform Service Dependencies",
            ""
        ]

        # Add all services as nodes
        for service in self.services.values():
            if service.type == 'service':
                apis_info = f"<br/>APIs: {',
                    '.join(service.apis[:2])}" if service.apis else ""
                port_info = f"<br/>Port: {service.port}" if service.port else ""
                mermaid.append(f"    {service.name}[\"{service.name.replace('-',
                    ' ').title()}{apis_info}{port_info}\"]")

        mermaid.append("")

        # Add dependencies with labels
        for dep in self.dependencies:
            if (dep.from_service in self.services and
                dep.to_service in self.services and
                self.services[dep.from_service].type == 'service'):

                arrow_style = self._get_arrow_style(dep.type)
                label = self._get_dependency_label(dep.type)
                mermaid.append(f"    {dep.from_service} {arrow_style}|{label}| {dep.to_service}")

        mermaid.append("```")

        return "\n".join(mermaid)

    def generate_data_flow_diagram(self) -> str:
        """Generate data flow diagram"""
        logger.info("🎨 Generating data flow diagram")

        mermaid = [
            "```mermaid",
            "flowchart TD",
            "    %% Arrakis Platform Data Flow",
            "",
            "    User((\"👤 User\"))",
            "    nginx[\"🔄 API Gateway < br/>(Nginx)\"]",
            ""
        ]

        # Core services with data flows
        core_services = ['oms', 'user-service', 'audit-service', 'data-kernel-service']
        for service_name in core_services:
            if service_name in self.services:
                service = self.services[service_name]
                icon = self._get_service_icon(service_name)
                mermaid.append(f"    {service_name}[\"{icon} {service.name.replace('-',
                    ' ').title()}\"]")

        # Data stores
        data_stores = ['terminusdb', 'postgres', 'redis']
        for store_name in data_stores:
            if store_name in self.services:
                icon = self._get_service_icon(store_name)
                mermaid.append(f"    {store_name}[(\"{icon} {store_name.title()}\")]")

        mermaid.extend([
            "",
            "    %% Data Flow Connections",
            "    User --> nginx",
            "    nginx --> oms",
            "    nginx --> user-service",
            "    nginx --> audit-service",
            "",
            "    oms --> data-kernel-service",
            "    oms --> terminusdb",
            "    oms --> postgres",
            "    oms --> redis",
            "",
            "    user-service --> postgres",
            "    user-service --> redis",
            "    audit-service --> postgres",
            "    data-kernel-service --> terminusdb",
            ""
        ])

        # Add messaging flows if NATS exists
        if 'nats' in self.services:
            mermaid.extend([
                "    nats[(\"📡 NATS < br/>Message Broker\")]",
                "    oms -.-> nats",
                "    event-gateway --> nats",
                ""
            ])

        mermaid.append("```")

        return "\n".join(mermaid)

    def generate_technology_stack_diagram(self) -> str:
        """Generate technology stack diagram"""
        logger.info("🎨 Generating technology stack diagram")

        mermaid = [
            "```mermaid",
            "graph TB",
            "    %% Arrakis Platform Technology Stack",
            "",
            "    subgraph \"🌐 Frontend Layer\"",
            "        web[\"Web Applications\"]",
            "        mobile[\"Mobile Apps\"]",
            "    end",
            "",
            "    subgraph \"🔄 API Gateway\"",
            "        nginx[\"Nginx < br/>Load Balancer & Proxy\"]",
            "    end",
            "",
            "    subgraph \"🏗️ Microservices (Python/FastAPI)\"",
        ]

        # Group services by technology
        python_services = [s for s in self.services.values()
                          if s.type == 'service' and 'Python' in s.tech_stack]

        for service in python_services:
            apis = " + ".join(service.apis) if service.apis else "REST"
            mermaid.append(f"        {service.name}[\"{service.name.replace('-',
                ' ').title()}<br/>{apis}\"]")

        mermaid.extend([
            "    end",
            "",
            "    subgraph \"💾 Data Storage\"",
            "        terminusdb[\"TerminusDB < br/>Graph Database\"]",
            "        postgres[\"PostgreSQL < br/>Relational Database\"]",
            "        redis[\"Redis < br/>Cache & Sessions\"]",
            "    end",
            "",
            "    subgraph \"📡 Message Broker\"",
            "        nats[\"NATS < br/>Event Streaming\"]",
            "    end",
            "",
            "    subgraph \"📊 Observability\"",
            "        prometheus[\"Prometheus < br/>Metrics\"]",
            "        grafana[\"Grafana < br/>Dashboards\"]",
            "        jaeger[\"Jaeger < br/>Tracing\"]",
            "    end",
            "",
            "    %% Connections",
            "    web --> nginx",
            "    mobile --> nginx",
            "    nginx --> oms",
            "    nginx --> user-service",
            ""
        ])

        mermaid.append("```")

        return "\n".join(mermaid)

    def _get_service_icon(self, service_name: str) -> str:
        """Get emoji icon for service"""
        icons = {
            'oms': '🎯',
            'ontology-management-service': '🎯',
            'user-service': '👤',
            'audit-service': '📋',
            'data-kernel-service': '⚡',
            'embedding-service': '🧠',
            'scheduler-service': '⏰',
            'event-gateway': '🔄',
            'postgres': '🐘',
            'redis': '🔴',
            'nats': '📡',
            'terminusdb': '🕸️',
            'prometheus': '📊',
            'grafana': '📈',
            'jaeger': '🔍',
            'nginx': '🌐'
        }
        return icons.get(service_name, '🔧')

    def _get_arrow_style(self, dep_type: str) -> str:
        """Get Mermaid arrow style for dependency type"""
        styles = {
            'http': '-->',
            'grpc': '==>',
            'database': '-->',
            'cache': '-.->',
            'messaging': '~~>',
            'monitoring': '-.->',
            'gateway': '-->'
        }
        return styles.get(dep_type, '-->')

    def _get_dependency_label(self, dep_type: str) -> str:
        """Get label for dependency arrow"""
        labels = {
            'http': 'HTTP',
            'grpc': 'gRPC',
            'database': 'DB',
            'cache': 'Cache',
            'messaging': 'Events',
            'monitoring': 'Metrics'
        }
        return labels.get(dep_type, dep_type.upper())

    def generate_all_diagrams(self) -> Dict[str, str]:
        """Generate all architecture diagrams"""
        logger.info("🎨 Generating all architecture diagrams...")

        diagrams = {
            'system-overview': self.generate_system_overview_diagram(),
            'service-dependencies': self.generate_service_dependency_diagram(),
            'data-flow': self.generate_data_flow_diagram(),
            'technology-stack': self.generate_technology_stack_diagram()
        }

        return diagrams

    def save_diagrams(self, diagrams: Dict[str, str]):
        """Save all diagrams to markdown files"""
        logger.info(f"💾 Saving diagrams to {self.output_dir}")

        # Create README with all diagrams
        readme_content = [
            "# Arrakis Platform Architecture Diagrams",
            "",
            "This directory contains automatically generated architecture diagrams for the Arrakis platform.",


            "",
            "## 📊 Available Diagrams",
            "",
            "- [System Overview](#system-overview) - High-level system architecture",
            "- [Service Dependencies](#service-dependencies) - Detailed service relationships",


            "- [Data Flow](#data-flow) - Data flow through the system",
            "- [Technology Stack](#technology-stack) - Technology stack visualization",
            "",
            "---",
            ""
        ]

        for diagram_name, content in diagrams.items():
            # Save individual diagram file
            filename = f"{diagram_name}.md"
            filepath = self.output_dir / filename

            with open(filepath, 'w') as f:
                title = diagram_name.replace('-', ' ').title()
                f.write(f"# {title}\n\n{content}\n")

            logger.info(f"💾 Saved {filename}")

            # Add to README
            title = diagram_name.replace('-', ' ').title()
            readme_content.extend([
                f"## {title}",
                "",
                content,
                "",
                "---",
                ""
            ])

        # Save README
        readme_path = self.output_dir / "README.md"
        with open(readme_path, 'w') as f:
            f.write("\n".join(readme_content))

        logger.info("💾 Saved README.md with all diagrams")

        # Generate metadata file
        metadata = {
            'generated_at': '2024-01-01T00:00:00Z',
            'generator': 'arrakis-architecture-diagrams',
            'version': '1.0.0',
            'diagrams': list(diagrams.keys()),
            'services_count': len(self.services),
            'dependencies_count': len(self.dependencies),
            'services': {name: asdict(service) for name,
                service in self.services.items()}
        }

        metadata_path = self.output_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent = 2)

        logger.info("💾 Saved metadata.json")

def main():
    parser = argparse.ArgumentParser(description="Generate Arrakis architecture diagrams")
    parser.add_argument("--project-root", default=".",
                       help="Root directory of the Arrakis project")
    parser.add_argument("--output-dir", default="docs/diagrams",
                       help="Output directory for diagrams")
    parser.add_argument("--diagram", choices=['system-overview', 'service-dependencies',
                                             'data-flow', 'technology-stack'],
                       help="Generate specific diagram only")

    args = parser.parse_args()

    generator = ArchitectureDiagramGenerator(args.project_root, args.output_dir)

    try:
        # Analyze the project
        generator.analyze_project()

        # Generate diagrams
        if args.diagram:
            # Generate specific diagram
            if args.diagram == 'system-overview':
                diagram_content = generator.generate_system_overview_diagram()
            elif args.diagram == 'service-dependencies':
                diagram_content = generator.generate_service_dependency_diagram()
            elif args.diagram == 'data-flow':
                diagram_content = generator.generate_data_flow_diagram()
            elif args.diagram == 'technology-stack':
                diagram_content = generator.generate_technology_stack_diagram()

            diagrams = {args.diagram: diagram_content}
        else:
            # Generate all diagrams
            diagrams = generator.generate_all_diagrams()

        # Save diagrams
        generator.save_diagrams(diagrams)

        logger.info("🎉 Architecture diagrams generated successfully!")
        logger.info(f"📁 Output directory: {generator.output_dir.absolute()}")

    except Exception as e:
        logger.error(f"❌ Failed to generate diagrams: {e}")
        raise

if __name__ == "__main__":
    main()
