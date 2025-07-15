#!/usr/bin/env python3
"""
OpenAPI Specification Extraction Script
Extracts OpenAPI specs from all FastAPI services in the Arrakis platform
"""

import argparse
import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import httpx
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ServiceConfig:
    name: str
    url: str
    port: int
    health_endpoint: str = "/health"
    openapi_endpoint: str = "/openapi.json"
    docs_endpoint: str = "/docs"


# Service configurations
SERVICES = [
    ServiceConfig(
        name="ontology-management-service", url="http://localhost", port=8000
    ),
    ServiceConfig(name="user-service", url="http://localhost", port=8010),
    ServiceConfig(name="audit-service", url="http://localhost", port=8011),
    ServiceConfig(name="data-kernel-service", url="http://localhost", port=8080),
    ServiceConfig(name="embedding-service", url="http://localhost", port=8001),
    ServiceConfig(name="scheduler-service", url="http://localhost", port=8002),
    ServiceConfig(name="event-gateway", url="http://localhost", port=8003),
]


class OpenAPIExtractor:
    def __init__(self, output_dir: str = "docs/openapi"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(timeout=30.0)

    async def check_service_health(self, service: ServiceConfig) -> bool:
        """Check if service is running and healthy"""
        try:
            url = f"{service.url}:{service.port}{service.health_endpoint}"
            logger.info(f"Checking health of {service.name} at {url}")

            response = await self.client.get(url)
            response.raise_for_status()

            logger.info(f"✅ {service.name} is healthy")
            return True

        except Exception as e:
            logger.warning(f"❌ {service.name} health check failed: {e}")
            return False

    async def extract_openapi_spec(self, service: ServiceConfig) -> Optional[Dict]:
        """Extract OpenAPI specification from service"""
        try:
            url = f"{service.url}:{service.port}{service.openapi_endpoint}"
            logger.info(f"Extracting OpenAPI spec from {service.name} at {url}")

            response = await self.client.get(url)
            response.raise_for_status()

            spec = response.json()

            # Enhance the spec with additional metadata
            self._enhance_openapi_spec(spec, service)

            logger.info(f"✅ Successfully extracted OpenAPI spec for {service.name}")
            return spec

        except Exception as e:
            logger.error(f"❌ Failed to extract OpenAPI spec for {service.name}: {e}")
            return None

    def _enhance_openapi_spec(self, spec: Dict, service: ServiceConfig):
        """Enhance OpenAPI spec with additional metadata"""
        # Add service-specific metadata
        spec["info"]["x-service-name"] = service.name
        spec["info"]["x-service-port"] = service.port
        spec["info"][
            "x-docs-url"
        ] = f"{service.url}:{service.port}{service.docs_endpoint}"

        # Add Arrakis platform metadata
        spec["info"]["x-platform"] = "Arrakis"
        spec["info"]["x-platform-version"] = "2.0.0"

        # Add server information
        if "servers" not in spec:
            spec["servers"] = []

        spec["servers"].insert(
            0,
            {
                "url": f"{service.url}:{service.port}",
                "description": f"{service.name} - Local Development",
            },
        )

    async def save_spec(self, service_name: str, spec: Dict):
        """Save OpenAPI spec in both JSON and YAML formats"""
        # Save as JSON
        json_path = self.output_dir / f"{service_name}.openapi.json"
        with open(json_path, "w") as f:
            json.dump(spec, f, indent=2)
        logger.info(f"💾 Saved {service_name} OpenAPI spec (JSON): {json_path}")

        # Save as YAML
        yaml_path = self.output_dir / f"{service_name}.openapi.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(spec, f, default_flow_style=False, sort_keys=False)
        logger.info(f"💾 Saved {service_name} OpenAPI spec (YAML): {yaml_path}")

    async def generate_api_inventory(self, extracted_specs: Dict[str, Dict]):
        """Generate a comprehensive API inventory"""
        inventory = {
            "platform": "Arrakis",
            "version": "2.0.0",
            "generated_at": "2024-01-01T00:00:00Z",
            "total_services": len(extracted_specs),
            "services": {},
        }

        for service_name, spec in extracted_specs.items():
            service_info = {
                "name": spec["info"]["title"],
                "version": spec["info"]["version"],
                "description": spec["info"]["description"],
                "docs_url": spec["info"].get("x-docs-url"),
                "port": spec["info"].get("x-service-port"),
                "paths": list(spec.get("paths", {}).keys()),
                "path_count": len(spec.get("paths", {})),
                "has_authentication": self._has_security_schemes(spec),
                "tags": [tag["name"] for tag in spec.get("tags", [])],
                "servers": spec.get("servers", []),
            }
            inventory["services"][service_name] = service_info

        # Save inventory
        inventory_path = self.output_dir / "api_inventory.json"
        with open(inventory_path, "w") as f:
            json.dump(inventory, f, indent=2)
        logger.info(f"📋 Generated API inventory: {inventory_path}")

        return inventory

    def _has_security_schemes(self, spec: Dict) -> bool:
        """Check if API has security schemes defined"""
        components = spec.get("components", {})
        security_schemes = components.get("securitySchemes", {})
        return len(security_schemes) > 0

    async def generate_redocly_config(self, extracted_specs: Dict[str, Dict]):
        """Generate Redocly configuration for multi-API documentation"""
        redocly_config = {
            "apis": {},
            "lint": {
                "extends": ["recommended"],
                "rules": {
                    "no-unused-components": "error",
                    "security-defined": "warn",
                    "tags-alphabetical": "warn",
                },
            },
            "referenceDocs": {
                "settings": {"theme": {"colors": {"primary": {"main": "#2196F3"}}}}
            },
        }

        for service_name in extracted_specs.keys():
            redocly_config["apis"][service_name] = {
                "root": f"docs/openapi/{service_name}.openapi.yaml",
                "definition": f"docs/openapi/{service_name}.openapi.yaml",
            }

        # Save Redocly config
        config_path = self.output_dir.parent / "redocly.yaml"
        with open(config_path, "w") as f:
            yaml.dump(redocly_config, f, default_flow_style=False)
        logger.info(f"🔧 Generated Redocly config: {config_path}")

    async def generate_swaggerhub_config(self, extracted_specs: Dict[str, Dict]):
        """Generate SwaggerHub integration scripts"""
        swaggerhub_script = """#!/bin/bash
# SwaggerHub Upload Script for Arrakis Platform APIs

set -e

# Configuration
SWAGGERHUB_API_KEY="${SWAGGERHUB_API_KEY}"
SWAGGERHUB_OWNER="${SWAGGERHUB_OWNER:-arrakis-platform}"
API_VERSION="${API_VERSION:-2.0.0}"

if [ -z "$SWAGGERHUB_API_KEY" ]; then
    echo "Error: SWAGGERHUB_API_KEY environment variable not set"
    exit 1
fi

echo "🚀 Uploading Arrakis APIs to SwaggerHub..."

"""

        for service_name in extracted_specs.keys():
            swaggerhub_script += """
# Upload {service_name}
echo "📤 Uploading {service_name}..."
curl -X POST \\
  "https://api.swaggerhub.com/apis/${{SWAGGERHUB_OWNER}}/{service_name}" \\
  -H "Authorization: ${{SWAGGERHUB_API_KEY}}" \\
  -H "Content-Type: application/json" \\
  -d @docs/openapi/{service_name}.openapi.json

"""

        swaggerhub_script += """
echo "✅ All APIs uploaded to SwaggerHub successfully!"
"""

        # Save SwaggerHub script
        script_path = self.output_dir.parent / "upload_to_swaggerhub.sh"
        with open(script_path, "w") as f:
            f.write(swaggerhub_script)

        # Make script executable
        os.chmod(script_path, 0o755)
        logger.info(f"📤 Generated SwaggerHub upload script: {script_path}")

    async def extract_all_specs(self, check_health: bool = True):
        """Extract OpenAPI specs from all services"""
        logger.info("🔍 Starting OpenAPI specification extraction for Arrakis platform")

        extracted_specs = {}
        healthy_services = []

        for service in SERVICES:
            if check_health:
                is_healthy = await self.check_service_health(service)
                if not is_healthy:
                    logger.warning(f"⚠️  Skipping {service.name} - service not healthy")
                    continue
                healthy_services.append(service)
            else:
                healthy_services.append(service)

        # Extract specs from healthy services
        for service in healthy_services:
            spec = await self.extract_openapi_spec(service)
            if spec:
                extracted_specs[service.name] = spec
                await self.save_spec(service.name, spec)

        if extracted_specs:
            # Generate additional documentation files
            await self.generate_api_inventory(extracted_specs)
            await self.generate_redocly_config(extracted_specs)
            await self.generate_swaggerhub_config(extracted_specs)

            logger.info(
                f"🎉 Successfully extracted {len(extracted_specs)} OpenAPI specifications!"
            )
            logger.info(f"📁 Output directory: {self.output_dir.absolute()}")
        else:
            logger.error("❌ No OpenAPI specifications were extracted")

        return extracted_specs

    async def close(self):
        """Cleanup resources"""
        await self.client.aclose()


async def main():
    parser = argparse.ArgumentParser(
        description="Extract OpenAPI specs from Arrakis services"
    )
    parser.add_argument(
        "--output-dir",
        default="docs/openapi",
        help="Output directory for OpenAPI specs",
    )
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip health checks (useful for extracting from static configs)",
    )
    parser.add_argument("--service", help="Extract spec for specific service only")

    args = parser.parse_args()

    extractor = OpenAPIExtractor(args.output_dir)

    try:
        if args.service:
            # Extract spec for specific service
            service_config = next((s for s in SERVICES if s.name == args.service), None)
            if not service_config:
                logger.error(f"❌ Service '{args.service}' not found")
                return

            if not args.skip_health_check:
                is_healthy = await extractor.check_service_health(service_config)
                if not is_healthy:
                    logger.error(f"❌ Service {args.service} is not healthy")
                    return

            spec = await extractor.extract_openapi_spec(service_config)
            if spec:
                await extractor.save_spec(service_config.name, spec)
                logger.info(f"✅ Extracted spec for {args.service}")
        else:
            # Extract all specs
            await extractor.extract_all_specs(check_health=not args.skip_health_check)

    finally:
        await extractor.close()


if __name__ == "__main__":
    asyncio.run(main())
