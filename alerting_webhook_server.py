#!/opt/homebrew/bin/python3.12
"""
🚨 ALERTING WEBHOOK SERVER
웹훅을 통한 실시간 알림 처리
"""

from fastapi import FastAPI, Request
import uvicorn
import json
import logging
from datetime import datetime
import asyncio
import smtplib
from email.mime.text import MIMEText

app = FastAPI(title="Arrakis Alerting Webhook")

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.post("/webhook/alerts")
async def handle_alerts(request: Request):
    """Alertmanager 웹훅 처리"""
    try:
        data = await request.json()
        
        for alert in data.get('alerts', []):
            alert_name = alert.get('labels', {}).get('alertname', 'Unknown')
            severity = alert.get('labels', {}).get('severity', 'unknown')
            status = alert.get('status', 'unknown')
            
            logger.info(f"🚨 Alert: {alert_name} | Severity: {severity} | Status: {status}")
            
            # 콘솔에 실시간 출력
            print(f"""
{'='*60}
🚨 ARRAKIS PRODUCTION ALERT
{'='*60}
Alert: {alert_name}
Severity: {severity.upper()}
Status: {status.upper()}
Time: {datetime.now().isoformat()}
Summary: {alert.get('annotations', {}).get('summary', 'N/A')}
Description: {alert.get('annotations', {}).get('description', 'N/A')}
{'='*60}
            """)
            
            # Slack 시뮬레이션 (실제로는 Slack API 호출)
            await send_slack_notification(alert_name, severity, status)
            
            # 이메일 알림 (선택적)
            if severity == 'critical':
                await send_email_alert(alert_name, alert)
        
        return {"status": "ok", "processed": len(data.get('alerts', []))}
        
    except Exception as e:
        logger.error(f"웹훅 처리 오류: {e}")
        return {"status": "error", "message": str(e)}

async def send_slack_notification(alert_name: str, severity: str, status: str):
    """Slack 알림 시뮬레이션"""
    emoji = "🔴" if severity == "critical" else "🟡" if severity == "warning" else "🔵"
    print(f"📱 Slack 알림: {emoji} {alert_name} - {severity.upper()}")

async def send_email_alert(alert_name: str, alert: dict):
    """이메일 알림 (중요 알람만)"""
    print(f"📧 이메일 알림: {alert_name} - CRITICAL ALERT")

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "alerting-webhook"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
