#!/usr/bin/env python3
"""
AWS Backup Validator Lambda Function
Validates backup jobs and recovery points for Arrakis platform
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
backup_client = boto3.client('backup')
sns_client = boto3.client('sns')

# Environment variables
BACKUP_VAULT_NAME = os.environ.get('BACKUP_VAULT_NAME', '${backup_vault_name}')
PROJECT_NAME = os.environ.get('PROJECT_NAME', '${project_name}')
ENVIRONMENT = os.environ.get('ENVIRONMENT', '${environment}')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')


class BackupValidator:
    """Validates AWS backup jobs and recovery points"""

    def __init__(self):
        self.backup_client = backup_client
        self.sns_client = sns_client
        self.vault_name = BACKUP_VAULT_NAME
        self.project_name = PROJECT_NAME
        self.environment = ENVIRONMENT
        self.sns_topic_arn = SNS_TOPIC_ARN

    def get_recent_backup_jobs(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get backup jobs from the last N hours"""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours = hours)

            response = self.backup_client.list_backup_jobs(
                ByBackupVaultName = self.vault_name,
                ByCreatedAfter = start_time,
                ByCreatedBefore = end_time
            )

            return response.get('BackupJobs', [])

        except Exception as e:
            logger.error(f"Error retrieving backup jobs: {str(e)}")
            return []

    def get_recovery_points(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recovery points from the last N days"""
        try:
            response = self.backup_client.list_recovery_points_by_backup_vault(
                BackupVaultName = self.vault_name
            )

            recovery_points = response.get('RecoveryPoints', [])

            # Filter by creation date
            cutoff_date = datetime.utcnow() - timedelta(days = days)
            recent_points = []

            for point in recovery_points:
                creation_date = point.get('CreationDate')
                if creation_date and creation_date.replace(tzinfo = None) >= cutoff_date:
                    recent_points.append(point)

            return recent_points

        except Exception as e:
            logger.error(f"Error retrieving recovery points: {str(e)}")
            return []

    def validate_backup_jobs(self, backup_jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate backup job status and performance"""
        validation_results = {
            'total_jobs': len(backup_jobs),
            'successful_jobs': 0,
            'failed_jobs': 0,
            'in_progress_jobs': 0,
            'expired_jobs': 0,
            'aborted_jobs': 0,
            'failed_job_details': [],
            'performance_issues': [],
            'validation_status': 'PASS'
        }

        for job in backup_jobs:
            state = job.get('State', 'UNKNOWN')
            job_id = job.get('BackupJobId', 'UNKNOWN')
            resource_arn = job.get('ResourceArn', 'UNKNOWN')

            if state == 'COMPLETED':
                validation_results['successful_jobs'] += 1

                # Check backup performance
                start_time = job.get('CreationDate')
                completion_time = job.get('CompletionDate')

                if start_time and completion_time:
                    duration = completion_time - start_time
                    duration_hours = duration.total_seconds() / 3600

                    # Flag jobs that took longer than 8 hours
                    if duration_hours > 8:
                        validation_results['performance_issues'].append({
                            'job_id': job_id,
                            'resource_arn': resource_arn,
                            'duration_hours': duration_hours,
                            'issue': 'Long backup duration'
                        })

            elif state in ['FAILED', 'PARTIAL']:
                validation_results['failed_jobs'] += 1
                validation_results['failed_job_details'].append({
                    'job_id': job_id,
                    'resource_arn': resource_arn,
                    'state': state,
                    'status_message': job.get('StatusMessage', 'No message'),
                    'creation_date': job.get('CreationDate',
                        '').isoformat() if job.get('CreationDate') else ''
                })
                validation_results['validation_status'] = 'FAIL'

            elif state == 'RUNNING':
                validation_results['in_progress_jobs'] += 1

                # Check for stuck jobs (running for more than 12 hours)
                start_time = job.get('CreationDate')
                if start_time:
                    duration = datetime.utcnow().replace(tzinfo = start_time.tzinfo) - start_time
                    duration_hours = duration.total_seconds() / 3600

                    if duration_hours > 12:
                        validation_results['performance_issues'].append({
                            'job_id': job_id,
                            'resource_arn': resource_arn,
                            'duration_hours': duration_hours,
                            'issue': 'Backup job stuck (running too long)'
                        })
                        validation_results['validation_status'] = 'WARNING'

            elif state == 'EXPIRED':
                validation_results['expired_jobs'] += 1
            elif state == 'ABORTED':
                validation_results['aborted_jobs'] += 1

        return validation_results

    def validate_recovery_points(self, recovery_points: List[Dict[str,
        Any]]) -> Dict[str, Any]:
        """Validate recovery point integrity and accessibility"""
        validation_results = {
            'total_recovery_points': len(recovery_points),
            'available_points': 0,
            'unavailable_points': 0,
            'encrypted_points': 0,
            'unencrypted_points': 0,
            'resource_coverage': {},
            'validation_status': 'PASS',
            'issues': []
        }

        resource_types = {}

        for point in recovery_points:
            status = point.get('Status', 'UNKNOWN')
            resource_arn = point.get('ResourceArn', 'UNKNOWN')
            encryption_key_arn = point.get('EncryptionKeyArn')

            # Count by status
            if status == 'COMPLETED':
                validation_results['available_points'] += 1
            else:
                validation_results['unavailable_points'] += 1
                validation_results['issues'].append({
                    'recovery_point_arn': point.get('RecoveryPointArn', 'UNKNOWN'),
                    'resource_arn': resource_arn,
                    'status': status,
                    'issue': f"Recovery point not available: {status}"
                })
                if status in ['PARTIAL', 'DELETING', 'EXPIRED']:
                    validation_results['validation_status'] = 'FAIL'

            # Count by encryption
            if encryption_key_arn:
                validation_results['encrypted_points'] += 1
            else:
                validation_results['unencrypted_points'] += 1
                validation_results['issues'].append({
                    'recovery_point_arn': point.get('RecoveryPointArn', 'UNKNOWN'),
                    'resource_arn': resource_arn,
                    'issue': 'Recovery point not encrypted'
                })
                validation_results['validation_status'] = 'WARNING'

            # Track resource coverage
            resource_type = self._extract_resource_type(resource_arn)
            if resource_type not in resource_types:
                resource_types[resource_type] = 0
            resource_types[resource_type] += 1

        validation_results['resource_coverage'] = resource_types

        return validation_results

    def _extract_resource_type(self, resource_arn: str) -> str:
        """Extract resource type from ARN"""
        try:
            # ARN format: arn:aws:service:region:account:resource-type/resource-id
            parts = resource_arn.split(':')
            if len(parts) >= 6:
                service = parts[2]
                resource_part = parts[5]

                if '/' in resource_part:
                    resource_type = resource_part.split('/')[0]
                else:
                    resource_type = resource_part

                return f"{service}:{resource_type}"

            return 'unknown'

        except Exception:
            return 'unknown'

    def check_backup_compliance(self) -> Dict[str, Any]:
        """Check backup compliance requirements"""
        compliance_results = {
            'rpo_compliance': True,
            'retention_compliance': True,
            'encryption_compliance': True,
            'cross_region_compliance': True,
            'issues': [],
            'validation_status': 'PASS'
        }

        try:
            # Check if daily backups are happening (RPO compliance)
            recent_jobs = self.get_recent_backup_jobs(hours = 25)  # Allow 1 hour buffer

            if not recent_jobs:
                compliance_results['rpo_compliance'] = False
                compliance_results['issues'].append('No backup jobs found in the last 24 hours')
                compliance_results['validation_status'] = 'FAIL'

            # Check recovery points for retention compliance
            recovery_points = self.get_recovery_points(days = 1)

            if not recovery_points:
                compliance_results['retention_compliance'] = False
                compliance_results['issues'].append('No recovery points found from recent backups')
                compliance_results['validation_status'] = 'FAIL'

            return compliance_results

        except Exception as e:
            logger.error(f"Error checking backup compliance: {str(e)}")
            compliance_results['validation_status'] = 'ERROR'
            compliance_results['issues'].append(f"Error during compliance check: {str(e)}")
            return compliance_results

    def generate_report(self, backup_validation: Dict[str, Any],
                       recovery_validation: Dict[str, Any],
                       compliance_check: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive backup validation report"""
        overall_status = 'PASS'

        # Determine overall status
        if (backup_validation['validation_status'] == 'FAIL' or
            recovery_validation['validation_status'] == 'FAIL' or
            compliance_check['validation_status'] == 'FAIL'):
            overall_status = 'FAIL'
        elif (backup_validation['validation_status'] == 'WARNING' or
              recovery_validation['validation_status'] == 'WARNING' or
              compliance_check['validation_status'] == 'WARNING'):
            overall_status = 'WARNING'
        elif (backup_validation['validation_status'] == 'ERROR' or
              recovery_validation['validation_status'] == 'ERROR' or
              compliance_check['validation_status'] == 'ERROR'):
            overall_status = 'ERROR'

        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'project_name': self.project_name,
            'environment': self.environment,
            'backup_vault': self.vault_name,
            'overall_status': overall_status,
            'backup_jobs': backup_validation,
            'recovery_points': recovery_validation,
            'compliance': compliance_check,
            'summary': {
                'total_backup_jobs': backup_validation['total_jobs'],
                'successful_backup_jobs': backup_validation['successful_jobs'],
                'failed_backup_jobs': backup_validation['failed_jobs'],
                'total_recovery_points': recovery_validation['total_recovery_points'],
                'available_recovery_points': recovery_validation['available_points'],
                'encrypted_recovery_points': recovery_validation['encrypted_points'],
                'total_issues': (len(backup_validation.get('failed_job_details', [])) +
                               len(backup_validation.get('performance_issues', [])) +
                               len(recovery_validation.get('issues', [])) +
                               len(compliance_check.get('issues', [])))
            }
        }

        return report

    def send_notification(self, report: Dict[str, Any]) -> bool:
        """Send backup validation report via SNS"""
        if not self.sns_topic_arn:
            logger.info("No SNS topic configured, skipping notification")
            return True

        try:
            subject = f"Backup Validation Report - {self.project_name} ({self.environment}) - {report['overall_status']}"

            # Create human-readable message
            message = self._format_notification_message(report)

            self.sns_client.publish(
                TopicArn = self.sns_topic_arn,
                Subject = subject,
                Message = message
            )

            logger.info(f"Notification sent successfully to {self.sns_topic_arn}")
            return True

        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            return False

    def _format_notification_message(self, report: Dict[str, Any]) -> str:
        """Format backup validation report for SNS notification"""
        status_emoji = {
            'PASS': '✅',
            'WARNING': '⚠️',
            'FAIL': '❌',
            'ERROR': '🚨'
        }

        emoji = status_emoji.get(report['overall_status'], '❓')

        message = """
{emoji} Backup Validation Report for {report['project_name']} ({report['environment']})

Overall Status: {report['overall_status']}
Timestamp: {report['timestamp']}
Backup Vault: {report['backup_vault']}

📊 Summary:
• Total Backup Jobs (24h): {report['summary']['total_backup_jobs']}
• Successful Jobs: {report['summary']['successful_backup_jobs']}
• Failed Jobs: {report['summary']['failed_backup_jobs']}
• Total Recovery Points: {report['summary']['total_recovery_points']}
• Available Recovery Points: {report['summary']['available_recovery_points']}
• Encrypted Recovery Points: {report['summary']['encrypted_recovery_points']}
• Total Issues Found: {report['summary']['total_issues']}

"""

        # Add failed job details if any
        if report['backup_jobs']['failed_job_details']:
            message += "\n❌ Failed Backup Jobs:\n"
            for job in report['backup_jobs']['failed_job_details'][:5]:  # Limit to 5 jobs
                message += f"• Job ID: {job['job_id'][:8]}... | Resource: {job['resource_arn'].split('/')[-1]} | Status: {job['state']}\n"

        # Add performance issues if any
        if report['backup_jobs']['performance_issues']:
            message += "\n⚠️ Performance Issues:\n"
            for issue in report['backup_jobs']['performance_issues'][:3]:  # Limit to 3 issues
                message += f"• {issue['issue']} | Duration: {issue['duration_hours']:.1f}h | Resource: {issue['resource_arn'].split('/')[-1]}\n"

        # Add compliance issues if any
        if report['compliance']['issues']:
            message += "\n🔍 Compliance Issues:\n"
            for issue in report['compliance']['issues'][:3]:  # Limit to 3 issues
                message += f"• {issue}\n"

        message += f"\nFor detailed information,
            check CloudWatch Logs for function: {PROJECT_NAME}-backup-validator-{ENVIRONMENT}"

        return message


def lambda_handler(event, context):
    """Lambda function entry point"""
    logger.info(f"Starting backup validation for {PROJECT_NAME} ({ENVIRONMENT})")

    try:
        validator = BackupValidator()

        # Get recent backup jobs and recovery points
        backup_jobs = validator.get_recent_backup_jobs(hours = 24)
        recovery_points = validator.get_recovery_points(days = 7)

        logger.info(f"Found {len(backup_jobs)} backup jobs and {len(recovery_points)} recovery points")

        # Perform validations
        backup_validation = validator.validate_backup_jobs(backup_jobs)
        recovery_validation = validator.validate_recovery_points(recovery_points)
        compliance_check = validator.check_backup_compliance()

        # Generate comprehensive report
        report = validator.generate_report(backup_validation, recovery_validation,
            compliance_check)

        # Log the report
        logger.info(f"Backup validation completed with status: {report['overall_status']}")
        logger.info(f"Report summary: {json.dumps(report['summary'], indent = 2)}")

        # Send notification if there are issues or if it's a scheduled full report
        should_notify = (
            report['overall_status'] in ['FAIL', 'ERROR'] or
            report['summary']['total_issues'] > 0 or
            event.get('send_full_report', False)
        )

        if should_notify:
            notification_sent = validator.send_notification(report)
            logger.info(f"Notification sent: {notification_sent}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'success',
                'validation_status': report['overall_status'],
                'summary': report['summary'],
                'timestamp': report['timestamp']
            })
        }

    except Exception as e:
        logger.error(f"Error during backup validation: {str(e)}")

        # Send error notification
        try:
            if SNS_TOPIC_ARN:
                sns_client.publish(
                    TopicArn = SNS_TOPIC_ARN,
                    Subject = f"Backup Validation Error - {PROJECT_NAME} ({ENVIRONMENT})",


                    Message = f"Backup validation failed with error: {str(e)}"
                )
        except Exception as sns_error:
            logger.error(f"Failed to send error notification: {str(sns_error)}")

        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })
        }
