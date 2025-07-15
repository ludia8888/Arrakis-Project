"""
Auto-generated Pydantic models for oms-event-sdk
Generated at: 2025-06-25T11:15:14.778517
DO NOT EDIT - This file is auto-generated
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class PublishResult(BaseModel):
 """Result of publishing an event"""
 success: bool
 message_id: Optional[str] = None
 error: Optional[str] = None


class Subscription:
 """Event subscription handle"""

 async def unsubscribe(self) -> None:
 """Unsubscribe from events"""
 pass


# Generated Models
class CloudEvent(BaseModel):
 """Generated model for CloudEvent"""
 specversion: str
 type: str
 source: str
 id: str
 time: Optional[datetime] = None
 datacontenttype: Optional[str] = None
 subject: Optional[str] = None
 data: Optional[Dict[str, Any]] = None
class OMSContext(BaseModel):
 """Generated model for OMSContext"""
 branch: Optional[str] = None
 commit: Optional[str] = None
 author: Optional[str] = None
 tenant: Optional[str] = None
 correlationId: Optional[str] = None
 causationId: Optional[str] = None
EntityType = str
