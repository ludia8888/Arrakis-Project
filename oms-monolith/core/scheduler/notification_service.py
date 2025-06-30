"""
Notification Service - Handles job notifications and alerts
"""
import json
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

from .models import JobExecution, JobMetadata
from utils import logging

logger = logging.get_logger(__name__)


class NotificationServiceProtocol(ABC):
    """Protocol for notification services"""
    
    @abstractmethod
    async def send_job_notification(
        self,
        recipients: List[str],
        subject: str,
        execution: JobExecution,
        metadata: Optional[JobMetadata] = None
    ):
        """Send job notification"""
        pass
    
    @abstractmethod
    async def send_alert(
        self,
        alert_type: str,
        message: str,
        details: Dict[str, Any]
    ):
        """Send system alert"""
        pass


class DefaultNotificationService(NotificationServiceProtocol):
    """Default implementation of notification service"""
    
    def __init__(
        self,
        email_service: Optional[Any] = None,
        slack_service: Optional[Any] = None,
        webhook_urls: Optional[List[str]] = None
    ):
        self.email_service = email_service
        self.slack_service = slack_service
        self.webhook_urls = webhook_urls or []
    
    async def send_job_notification(
        self,
        recipients: List[str],
        subject: str,
        execution: JobExecution,
        metadata: Optional[JobMetadata] = None
    ):
        """Send job notification"""
        try:
            # Prepare notification data
            notification_data = {
                "subject": subject,
                "execution_id": execution.execution_id,
                "job_id": execution.job_id,
                "status": execution.status.value,
                "started_at": execution.started_at.isoformat(),
                "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                "duration": execution.duration,
                "error": execution.error,
                "worker_id": execution.worker_id
            }
            
            if metadata:
                notification_data.update({
                    "job_name": metadata.name,
                    "job_category": metadata.category,
                    "job_owner": metadata.owner
                })
            
            # Send email notifications
            if self.email_service:
                await self._send_email_notifications(recipients, subject, notification_data)
            
            # Send Slack notifications
            if self.slack_service:
                await self._send_slack_notifications(recipients, subject, notification_data)
            
            # Send webhook notifications
            if self.webhook_urls:
                await self._send_webhook_notifications(subject, notification_data)
            
            # Fallback to logging
            if not any([self.email_service, self.slack_service, self.webhook_urls]):
                logger.info(f"Job notification: {subject} - {json.dumps(notification_data)}")
                
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Network error sending job notification: {e}")
        except ValueError as e:
            logger.error(f"Invalid notification data: {e}")
    
    async def send_alert(
        self,
        alert_type: str,
        message: str,
        details: Dict[str, Any]
    ):
        """Send system alert"""
        try:
            alert_data = {
                "alert_type": alert_type,
                "message": message,
                "details": details,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Send to appropriate channels based on alert type
            if alert_type in ["critical", "error"]:
                # High priority alerts
                if self.slack_service:
                    await self._send_slack_alert(message, alert_data)
                
                if self.webhook_urls:
                    await self._send_webhook_notifications(f"ALERT: {message}", alert_data)
            
            # Always log alerts
            logger.warning(f"System alert [{alert_type}]: {message} - {json.dumps(details)}")
            
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Network error sending system alert: {e}")
        except ValueError as e:
            logger.error(f"Invalid alert data: {e}")
    
    async def _send_email_notifications(
        self,
        recipients: List[str],
        subject: str,
        data: Dict[str, Any]
    ):
        """Send email notifications"""
        if not self.email_service:
            return
        
        try:
            # Format email content
            body = self._format_email_body(data)
            
            for recipient in recipients:
                if "@" in recipient:  # Email address
                    await self.email_service.send_email(
                        to=recipient,
                        subject=subject,
                        body=body
                    )
                    
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Email service connection failed: {e}")
        except ValueError as e:
            logger.error(f"Invalid email parameters: {e}")
        except AttributeError as e:
            logger.error(f"Email service not properly configured: {e}")
    
    async def _send_slack_notifications(
        self,
        recipients: List[str],
        subject: str,
        data: Dict[str, Any]
    ):
        """Send Slack notifications"""
        if not self.slack_service:
            return
        
        try:
            # Format Slack message
            message = self._format_slack_message(subject, data)
            
            for recipient in recipients:
                if recipient.startswith("#") or recipient.startswith("@"):  # Slack channel/user
                    await self.slack_service.send_message(
                        channel=recipient,
                        message=message
                    )
                    
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Slack service connection failed: {e}")
        except ValueError as e:
            logger.error(f"Invalid Slack parameters: {e}")
        except AttributeError as e:
            logger.error(f"Slack service not properly configured: {e}")
    
    async def _send_slack_alert(self, message: str, data: Dict[str, Any]):
        """Send Slack alert"""
        if not self.slack_service:
            return
        
        try:
            alert_message = f"🚨 *ALERT*: {message}\n```{json.dumps(data, indent=2)}```"
            await self.slack_service.send_message(
                channel="#alerts",  # Default alert channel
                message=alert_message
            )
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Slack alert connection failed: {e}")
        except ValueError as e:
            logger.error(f"Invalid Slack alert data: {e}")
        except AttributeError as e:
            logger.error(f"Slack service not configured for alerts: {e}")
    
    async def _send_webhook_notifications(
        self,
        subject: str,
        data: Dict[str, Any]
    ):
        """Send webhook notifications"""
        import aiohttp
        
        webhook_payload = {
            "subject": subject,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data
        }
        
        async with aiohttp.ClientSession() as session:
            for webhook_url in self.webhook_urls:
                try:
                    async with session.post(
                        webhook_url,
                        json=webhook_payload,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status != 200:
                            logger.warning(f"Webhook {webhook_url} returned status {response.status}")
                except aiohttp.ClientError as e:
                    logger.error(f"HTTP client error for webhook {webhook_url}: {e}")
                except asyncio.TimeoutError as e:
                    logger.error(f"Webhook timeout for {webhook_url}: {e}")
    
    def _format_email_body(self, data: Dict[str, Any]) -> str:
        """Format email body"""
        return f"""
Job Execution Report

Job ID: {data.get('job_id', 'Unknown')}
Job Name: {data.get('job_name', 'Unknown')}
Status: {data.get('status', 'Unknown')}
Started: {data.get('started_at', 'Unknown')}
Completed: {data.get('completed_at', 'N/A')}
Duration: {data.get('duration', 'N/A')} seconds
Worker: {data.get('worker_id', 'Unknown')}

{f"Error: {data['error']}" if data.get('error') else "Completed successfully"}

Execution ID: {data.get('execution_id', 'Unknown')}
        """.strip()
    
    def _format_slack_message(self, subject: str, data: Dict[str, Any]) -> str:
        """Format Slack message"""
        status_emoji = {
            "completed": "✅",
            "failed": "❌",
            "running": "🔄",
            "cancelled": "⛔"
        }.get(data.get('status', ''), "ℹ️")
        
        return f"""
{status_emoji} *{subject}*

• Job: `{data.get('job_name', data.get('job_id', 'Unknown'))}`
• Status: {data.get('status', 'Unknown')}
• Duration: {data.get('duration', 'N/A')} seconds
• Worker: {data.get('worker_id', 'Unknown')}
{f"• Error: `{data['error']}`" if data.get('error') else ""}
        """.strip()


class LogOnlyNotificationService(NotificationServiceProtocol):
    """Log-only notification service for testing/development"""
    
    async def send_job_notification(
        self,
        recipients: List[str],
        subject: str,
        execution: JobExecution,
        metadata: Optional[JobMetadata] = None
    ):
        """Log job notification"""
        logger.info(f"Job notification to {recipients}: {subject}")
        logger.info(f"Execution: {execution}")
    
    async def send_alert(
        self,
        alert_type: str,
        message: str,
        details: Dict[str, Any]
    ):
        """Log system alert"""
        logger.warning(f"System alert [{alert_type}]: {message}")
        logger.warning(f"Alert details: {details}")