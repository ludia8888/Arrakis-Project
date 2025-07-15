"""
Maintenance Tasks
Background jobs for system cleanup and monitoring
"""
import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp
from celery import Task
from arrakis_common import get_logger
from services.job_service import JobService
from workers.celery_app import app

logger = get_logger(__name__)


# Alert and monitoring functions
async def send_alert(
 alert_type: str,
 title: str,
 message: str,
 severity: str = "info",
 data: Optional[Dict[str, Any]] = None,
) -> None:
 """Send alert to various monitoring systems"""
 alert_data = {
 "type": alert_type,
 "title": title,
 "message": message,
 "severity": severity,
 "timestamp": datetime.utcnow().isoformat(),
 "service": "oms",
 "component": "maintenance",
 "data": data or {},
 }

 # Send to Slack if configured
 slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
 if slack_webhook:
 await _send_slack_alert(slack_webhook, alert_data)

 # Send to PagerDuty if configured
 pagerduty_key = os.getenv("PAGERDUTY_INTEGRATION_KEY")
 if pagerduty_key and severity in ["critical", "error", "warning"]:
 await _send_pagerduty_alert(pagerduty_key, alert_data)

 # Send to email if configured
 email_config = {
 "smtp_host": os.getenv("SMTP_HOST"),
 "smtp_port": os.getenv("SMTP_PORT", "587"),
 "smtp_user": os.getenv("SMTP_USER"),
 "smtp_pass": os.getenv("SMTP_PASS"),
 "alert_email": os.getenv("ALERT_EMAIL"),
 }
 if all(email_config.values()):
 await _send_email_alert(email_config, alert_data)

 # Log alert
 logger.info(f"Alert sent: {alert_type}", alert_data = alert_data)


async def send_metrics(
 metric_name: str, data: Dict[str, Any], tags: Optional[Dict[str, str]] = None
) -> None:
 """Send metrics to monitoring systems"""
 metric_data = {
 "metric": metric_name,
 "timestamp": datetime.utcnow().isoformat(),
 "tags": tags or {},
 "data": data,
 }

 # Send to Prometheus if configured
 prometheus_gateway = os.getenv("PROMETHEUS_PUSHGATEWAY_URL")
 if prometheus_gateway:
 await _send_prometheus_metrics(prometheus_gateway, metric_data)

 # Send to DataDog if configured
 datadog_api_key = os.getenv("DATADOG_API_KEY")
 if datadog_api_key:
 await _send_datadog_metrics(datadog_api_key, metric_data)

 # Send to custom monitoring endpoint if configured
 monitoring_endpoint = os.getenv("MONITORING_ENDPOINT")
 if monitoring_endpoint:
 await _send_custom_metrics(monitoring_endpoint, metric_data)

 # Log metrics
 logger.info(f"Metrics sent: {metric_name}", metric_data = metric_data)


async def _send_slack_alert(webhook_url: str, alert_data: Dict[str, Any]) -> None:
 """Send alert to Slack"""
 try:
 color_map = {
 "critical": "#FF0000",
 "error": "#FF6600",
 "warning": "#FFAA00",
 "info": "#0066FF",
 }

 payload = {
 "text": f"🚨 {alert_data['title']}",
 "attachments": [
 {
 "color": color_map.get(alert_data["severity"], "#808080"),
 "fields": [
 {
 "title": "Message",
 "value": alert_data["message"],
 "short": False,
 },
 {
 "title": "Severity",
 "value": alert_data["severity"],
 "short": True,
 },
 {
 "title": "Service",
 "value": alert_data["service"],
 "short": True,
 },
 {
 "title": "Timestamp",
 "value": alert_data["timestamp"],
 "short": True,
 },
 ],
 }
 ],
 }

 async with aiohttp.ClientSession() as session:
 async with session.post(webhook_url, json = payload) as response:
 if response.status != 200:
 logger.error(f"Failed to send Slack alert: {response.status}")
 else:
 logger.debug("Slack alert sent successfully")
 except Exception as e:
 logger.error(f"Error sending Slack alert: {e}")


async def _send_pagerduty_alert(
 integration_key: str, alert_data: Dict[str, Any]
) -> None:
 """Send alert to PagerDuty"""
 try:
 payload = {
 "routing_key": integration_key,
 "event_action": "trigger",
 "payload": {
 "summary": alert_data["title"],
 "source": f"{alert_data['service']}.{alert_data['component']}",
 "severity": alert_data["severity"],
 "custom_details": {
 "message": alert_data["message"],
 "data": alert_data["data"],
 },
 },
 }

 async with aiohttp.ClientSession() as session:
 async with session.post(
 "https://events.pagerduty.com/v2/enqueue",
 json = payload,
 headers={"Content-Type": "application/json"},
 ) as response:
 if response.status != 202:
 logger.error(f"Failed to send PagerDuty alert: {response.status}")
 else:
 logger.debug("PagerDuty alert sent successfully")
 except Exception as e:
 logger.error(f"Error sending PagerDuty alert: {e}")


async def _send_email_alert(config: Dict[str, str], alert_data: Dict[str, Any]) -> None:
 """Send alert via email"""
 try:
 import smtplib
 from email.mime.multipart import MIMEMultipart
 from email.mime.text import MIMEText

 msg = MIMEMultipart()
 msg["From"] = config["smtp_user"]
 msg["To"] = config["alert_email"]
 msg["Subject"] = f"[{alert_data['severity'].upper()}] {alert_data['title']}"

 body = f"""
 Alert: {alert_data['title']}
 Severity: {alert_data['severity']}
 Message: {alert_data['message']}
 Service: {alert_data['service']}
 Component: {alert_data['component']}
 Timestamp: {alert_data['timestamp']}

 Data: {json.dumps(alert_data['data'], indent = 2)}
 """

 msg.attach(MIMEText(body, "plain"))

 # Send email in thread pool to avoid blocking
 def send_email():
 server = smtplib.SMTP(config["smtp_host"], int(config["smtp_port"]))
 server.starttls()
 server.login(config["smtp_user"], config["smtp_pass"])
 server.send_message(msg)
 server.quit()

 loop = asyncio.get_event_loop()
 await loop.run_in_executor(None, send_email)
 logger.debug("Email alert sent successfully")

 except Exception as e:
 logger.error(f"Error sending email alert: {e}")


async def _send_prometheus_metrics(
 gateway_url: str, metric_data: Dict[str, Any]
) -> None:
 """Send metrics to Prometheus Pushgateway"""
 try:
 # Convert metrics to Prometheus format
 metrics_text = f"# TYPE {metric_data['metric']} gauge\n"

 # Add main metrics
 if isinstance(metric_data["data"], dict):
 for key, value in metric_data["data"].items():
 if isinstance(value, (int, float)):
 labels = ",".join(
 [f'{k}="{v}"' for k, v in metric_data["tags"].items()]
 )
 metrics_text += (
 f"{metric_data['metric']}_{key}{{{labels}}} {value}\n"
 )

 async with aiohttp.ClientSession() as session:
 async with session.post(
 f"{gateway_url}/metrics/job/oms_maintenance",
 data = metrics_text,
 headers={"Content-Type": "text/plain"},
 ) as response:
 if response.status not in [200, 202]:
 logger.error(
 f"Failed to send Prometheus metrics: {response.status}"
 )
 else:
 logger.debug("Prometheus metrics sent successfully")
 except Exception as e:
 logger.error(f"Error sending Prometheus metrics: {e}")


async def _send_datadog_metrics(api_key: str, metric_data: Dict[str, Any]) -> None:
 """Send metrics to DataDog"""
 try:
 timestamp = int(datetime.utcnow().timestamp())
 series = []

 if isinstance(metric_data["data"], dict):
 for key, value in metric_data["data"].items():
 if isinstance(value, (int, float)):
 series.append(
 {
 "metric": f"oms.{metric_data['metric']}.{key}",
 "points": [[timestamp, value]],
 "tags": [
 f"{k}:{v}" for k, v in metric_data["tags"].items()
 ],
 }
 )

 payload = {"series": series}

 async with aiohttp.ClientSession() as session:
 async with session.post(
 "https://api.datadoghq.com/api/v1/series",
 json = payload,
 headers={"Content-Type": "application/json", "DD-API-KEY": api_key},
 ) as response:
 if response.status != 202:
 logger.error(f"Failed to send DataDog metrics: {response.status}")
 else:
 logger.debug("DataDog metrics sent successfully")
 except Exception as e:
 logger.error(f"Error sending DataDog metrics: {e}")


async def _send_custom_metrics(endpoint_url: str, metric_data: Dict[str, Any]) -> None:
 """Send metrics to custom monitoring endpoint"""
 try:
 async with aiohttp.ClientSession() as session:
 async with session.post(
 endpoint_url,
 json = metric_data,
 headers={"Content-Type": "application/json"},
 ) as response:
 if response.status not in [200, 201, 202]:
 logger.error(f"Failed to send custom metrics: {response.status}")
 else:
 logger.debug("Custom metrics sent successfully")
 except Exception as e:
 logger.error(f"Error sending custom metrics: {e}")


class MaintenanceTask(Task):
 """Base class for maintenance tasks"""

 def __init__(self):
 self.job_service: JobService = None

 async def initialize(self):
 """Initialize services"""
 if not self.job_service:
 self.job_service = JobService()
 await self.job_service.initialize()


@app.task(
 bind = True,
 base = MaintenanceTask,
 name = "workers.tasks.maintenance.cleanup_expired_jobs",
)
def cleanup_expired_jobs_task(self, batch_size: int = 100):
 """Clean up expired jobs"""
 return asyncio.run(_async_cleanup_expired_jobs(self, batch_size))


async def _async_cleanup_expired_jobs(task: MaintenanceTask, batch_size: int):
 """Async implementation of cleanup"""
 await task.initialize()

 cleaned_count = await task.job_service.cleanup_expired_jobs(batch_size)

 logger.info(f"Cleaned up {cleaned_count} expired jobs")

 return {"cleaned_count": cleaned_count, "timestamp": datetime.utcnow().isoformat()}


@app.task(
 bind = True, base = MaintenanceTask, name = "workers.tasks.maintenance.check_stuck_jobs"
)
def check_stuck_jobs_task(self, timeout_minutes: int = 60):
 """Check for stuck jobs and alert"""
 return asyncio.run(_async_check_stuck_jobs(self, timeout_minutes))


async def _async_check_stuck_jobs(task: MaintenanceTask, timeout_minutes: int):
 """Async implementation of stuck job checking"""
 await task.initialize()

 stuck_jobs = await task.job_service.check_stuck_jobs(timeout_minutes)

 if stuck_jobs:
 logger.warning(f"Found {len(stuck_jobs)} stuck jobs", stuck_jobs = stuck_jobs)

 # Send alerts to monitoring system
 await send_alert(
 alert_type = "stuck_jobs",
 title = "Stuck Jobs Detected",
 message = f"Found {len(stuck_jobs)} stuck jobs that have been running for more than {timeout_minutes} minutes",
 severity = "warning",
 data={"job_ids": stuck_jobs, "timeout_minutes": timeout_minutes},
 )

 return {
 "stuck_job_count": len(stuck_jobs),
 "stuck_job_ids": stuck_jobs,
 "timestamp": datetime.utcnow().isoformat(),
 }


@app.task(
 bind = True, base = MaintenanceTask, name = "workers.tasks.maintenance.generate_job_stats"
)
def generate_job_stats_task(self):
 """Generate job statistics for monitoring"""
 return asyncio.run(_async_generate_job_stats(self))


async def _async_generate_job_stats(task: MaintenanceTask):
 """Generate comprehensive job statistics"""
 await task.initialize()

 # Get overall stats
 stats = await task.job_service.get_job_stats()

 # Get recent activity (last 24 hours)
 from models.job import JobFilter

 recent_filter = JobFilter(created_after = datetime.utcnow() - timedelta(hours = 24))
 recent_stats = await task.job_service.get_job_stats(recent_filter)

 result = {
 "overall": stats.model_dump(),
 "last_24h": recent_stats.model_dump(),
 "timestamp": datetime.utcnow().isoformat(),
 }

 logger.info("Generated job statistics", stats = result)

 # Send to monitoring system
 await send_metrics(
 metric_name = "job_stats",
 data = result,
 tags={"service": "oms", "component": "job_service"},
 )

 return result


@app.task(bind = True, name = "workers.tasks.maintenance.cleanup_redis_data")
def cleanup_redis_data_task(self, max_age_hours: int = 24):
 """Clean up old Redis data"""
 return asyncio.run(_async_cleanup_redis_data(self, max_age_hours))


async def _async_cleanup_redis_data(task, max_age_hours: int):
 """Clean up old Redis progress and event data"""
 from bootstrap.providers import RedisProvider

 provider = RedisProvider()
 redis_client = await provider.provide()

 import time

 cutoff_time = time.time() - (max_age_hours * 60 * 60)
 cleaned_keys = 0

 # Clean up job progress data
 progress_keys = await redis_client.keys("job:progress:*")
 for key in progress_keys:
 key_age = await redis_client.object("idletime", key)
 if key_age and key_age > cutoff_time:
 await redis_client.delete(key)
 cleaned_keys += 1

 # Clean up job event data
 event_keys = await redis_client.keys("job:events:*")
 for key in event_keys:
 key_age = await redis_client.object("idletime", key)
 if key_age and key_age > cutoff_time:
 await redis_client.delete(key)
 cleaned_keys += 1

 # Clean up job logs older than 7 days
 log_cutoff = time.time() - (7 * 24 * 60 * 60) # 7 days
 log_keys = await redis_client.keys("job:logs:*")
 for key in log_keys:
 key_age = await redis_client.object("idletime", key)
 if key_age and key_age > log_cutoff:
 await redis_client.delete(key)
 cleaned_keys += 1

 logger.info(f"Cleaned up {cleaned_keys} Redis keys")

 return {"cleaned_keys": cleaned_keys, "timestamp": datetime.utcnow().isoformat()}


@app.task(bind = True, name = "workers.tasks.maintenance.health_check")
def health_check_task(self):
 """Worker health check task"""
 return asyncio.run(_async_health_check(self))


async def _async_health_check(task):
 """Perform worker health check"""
 try:
 # Check database connectivity
 job_service = JobService()
 await job_service.initialize()

 # Test Redis connectivity
 from bootstrap.providers import RedisProvider

 provider = RedisProvider()
 redis_client = await provider.provide()
 await redis_client.ping()

 # Test basic job operations
 from models.job import JobType

 test_job = await job_service.create_job(
 job_type = JobType.SCHEMA_VALIDATION,
 created_by = "health_check",
 metadata={"test": True},
 )

 # Clean up test job
 await job_service._delete_job(test_job.id)

 result = {
 "status": "healthy",
 "timestamp": datetime.utcnow().isoformat(),
 "checks": {"database": "ok", "redis": "ok", "job_service": "ok"},
 }

 logger.info("Worker health check passed")
 return result

 except Exception as e:
 result = {
 "status": "unhealthy",
 "timestamp": datetime.utcnow().isoformat(),
 "error": str(e),
 }

 logger.error("Worker health check failed", error = str(e), exc_info = True)
 return result
