"""Configuration and system information routes"""

from fastapi import APIRouter, Depends
from bootstrap.providers.terminus_gateway import get_terminus_provider
import os

router = APIRouter(prefix = "/config", tags = ["Configuration"])

@router.get("/gateway-mode")
async def get_gateway_mode():
 """Get current Data Kernel Gateway mode status"""
 provider = get_terminus_provider()

 return {
 "gateway_mode_enabled": provider.is_using_gateway,
 "mode": provider.get_mode(),
 "data_kernel_endpoint": os.getenv("DATA_KERNEL_GRPC_ENDPOINT", "not configured"),
 "microservices": {
 "embedding_service": os.getenv("USE_EMBEDDING_MS", "false").lower() == "true",
 "scheduler_service": os.getenv("USE_SCHEDULER_MS", "false").lower() == "true",
 "event_gateway": os.getenv("USE_EVENT_GATEWAY", "false").lower() == "true"
 },
 "endpoints": {
 "embedding": os.getenv("EMBEDDING_SERVICE_ENDPOINT", "not configured"),
 "scheduler": os.getenv("SCHEDULER_SERVICE_ENDPOINT", "not configured"),
 "event_gateway": os.getenv("EVENT_GATEWAY_ENDPOINT", "not configured")
 }
 }

@router.get("/microservices-status")
async def get_microservices_status():
 """Get detailed microservices configuration and status"""
 return {
 "architecture_mode": "microservices" if os.getenv("USE_DATA_KERNEL_GATEWAY", "false").lower() == "true" else "monolith",
 "services": {
 "data_kernel": {
 "enabled": os.getenv("USE_DATA_KERNEL_GATEWAY", "false").lower() == "true",
 "endpoint": os.getenv("DATA_KERNEL_GRPC_ENDPOINT", "not configured"),
 "type": "gateway"
 },
 "embedding_service": {
 "enabled": os.getenv("USE_EMBEDDING_MS", "false").lower() == "true",
 "endpoint": os.getenv("EMBEDDING_SERVICE_ENDPOINT", "not configured"),
 "type": "microservice"
 },
 "scheduler_service": {
 "enabled": os.getenv("USE_SCHEDULER_MS", "false").lower() == "true",
 "endpoint": os.getenv("SCHEDULER_SERVICE_ENDPOINT", "not configured"),
 "type": "microservice"
 },
 "event_gateway": {
 "enabled": os.getenv("USE_EVENT_GATEWAY", "false").lower() == "true",
 "endpoint": os.getenv("EVENT_GATEWAY_ENDPOINT", "not configured"),
 "type": "microservice"
 }
 },
 "environment": {
 "env": os.getenv("ENV", "development"),
 "log_level": os.getenv("LOG_LEVEL", "INFO"),
 "iam_validation": os.getenv("USE_IAM_VALIDATION", "false").lower() == "true",
 "telemetry": os.getenv("ENABLE_TELEMETRY", "false").lower() == "true"
 }
 }

@router.get("/migration-progress")
async def get_migration_progress():
 """Get microservices migration progress"""
 services_total = 4 # data_kernel, embedding, scheduler, event_gateway
 services_enabled = sum([
 os.getenv("USE_DATA_KERNEL_GATEWAY", "false").lower() == "true",
 os.getenv("USE_EMBEDDING_MS", "false").lower() == "true",
 os.getenv("USE_SCHEDULER_MS", "false").lower() == "true",
 os.getenv("USE_EVENT_GATEWAY", "false").lower() == "true"
 ])

 progress_percentage = (services_enabled / services_total) * 100

 return {
 "migration_phase": "점진적 마이그레이션 진행 중",
 "progress_percentage": progress_percentage,
 "services_migrated": services_enabled,
 "services_total": services_total,
 "current_status": {
 "data_kernel": "migrated" if os.getenv("USE_DATA_KERNEL_GATEWAY", "false").lower() == "true" else "pending",
 "embedding_service": "migrated" if os.getenv("USE_EMBEDDING_MS", "false").lower() == "true" else "pending",
 "scheduler_service": "migrated" if os.getenv("USE_SCHEDULER_MS", "false").lower() == "true" else "pending",
 "event_gateway": "migrated" if os.getenv("USE_EVENT_GATEWAY", "false").lower() == "true" else "pending"
 },
 "next_steps": [
 "Monitor microservices performance",
 "Validate data consistency",
 "Scale services as needed",
 "Complete remaining migrations"
 ] if services_enabled > 0 else [
 "Enable USE_DATA_KERNEL_GATEWAY",
 "Start microservices with docker-compose",
 "Run verification tests"
 ]
 }
