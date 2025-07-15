"""
Time Travel Service Interface
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

from core.time_travel.models import (
    ResourceTimeline,
    TemporalComparisonQuery,
    TemporalComparisonResult,
    TemporalQuery,
    TemporalQueryResult,
    TemporalSnapshot,
)


class ITimeTravelService(Protocol):
 """Interface for time travel query operations"""

 async def query_at_time(
 self,
 query: TemporalQuery
 ) -> TemporalQueryResult:
 """Execute a temporal query at a specific point in time"""
 ...

 async def get_resource_at_time(
 self,
 resource_type: str,
 resource_id: str,
 timestamp: datetime,
 branch_name: Optional[str] = None
 ) -> Optional[Dict[str, Any]]:
 """Get a specific resource at a point in time"""
 ...

 async def create_snapshot(
 self,
 branch_name: str,
 timestamp: datetime,
 name: str,
 description: Optional[str] = None
 ) -> TemporalSnapshot:
 """Create a snapshot of branch state at a specific time"""
 ...

 async def compare_timepoints(
 self,
 query: TemporalComparisonQuery
 ) -> TemporalComparisonResult:
 """Compare states between two points in time"""
 ...

 async def get_resource_timeline(
 self,
 resource_type: str,
 resource_id: str,
 start_time: Optional[datetime] = None,
 end_time: Optional[datetime] = None,
 branch_name: Optional[str] = None
 ) -> ResourceTimeline:
 """Get timeline of changes for a resource"""
 ...

 async def restore_to_time(
 self,
 branch_name: str,
 timestamp: datetime,
 target_branch: str,
 user_id: str
 ) -> Dict[str, Any]:
 """Restore branch state to a specific point in time"""
 ...
