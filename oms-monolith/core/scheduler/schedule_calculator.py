"""
Schedule Calculator - Pure calculation logic for job scheduling
"""
import croniter
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Union
from abc import ABC, abstractmethod

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from .models import JobPriority
from utils import logging

logger = logging.get_logger(__name__)


class ScheduleCalculatorProtocol(ABC):
    """Protocol for schedule calculations"""
    
    @abstractmethod
    def parse_trigger(
        self, trigger: Union[str, CronTrigger, IntervalTrigger, DateTrigger]
    ) -> Union[CronTrigger, IntervalTrigger, DateTrigger]:
        """Parse trigger from string or return as-is"""
        pass
    
    @abstractmethod
    def calculate_next_run(
        self, trigger: Union[CronTrigger, IntervalTrigger, DateTrigger]
    ) -> Optional[datetime]:
        """Calculate next run time for trigger"""
        pass
    
    @abstractmethod
    def calculate_retry_delay(
        self, base_delay: int, retry_count: int, strategy: str = "exponential"
    ) -> int:
        """Calculate retry delay with backoff strategy"""
        pass
    
    @abstractmethod
    def is_business_hours(
        self, dt: datetime, business_start: int = 9, business_end: int = 17
    ) -> bool:
        """Check if datetime is within business hours"""
        pass


class DefaultScheduleCalculator(ScheduleCalculatorProtocol):
    """Default implementation of schedule calculator"""
    
    def __init__(self, timezone_str: str = "UTC"):
        self.timezone_str = timezone_str
    
    def parse_trigger(
        self, trigger: Union[str, CronTrigger, IntervalTrigger, DateTrigger]
    ) -> Union[CronTrigger, IntervalTrigger, DateTrigger]:
        """Parse trigger from string or return as-is"""
        if isinstance(trigger, (CronTrigger, IntervalTrigger, DateTrigger)):
            return trigger
        
        if not isinstance(trigger, str):
            raise ValueError(f"Invalid trigger type: {type(trigger)}")
        
        trigger = trigger.strip()
        
        # Parse different trigger formats
        if trigger.startswith("cron:"):
            cron_expr = trigger[5:].strip()
            return CronTrigger.from_crontab(cron_expr, timezone=self.timezone_str)
        
        elif trigger.startswith("interval:"):
            # Format: interval:unit:value (e.g., interval:seconds:30, interval:minutes:5)
            parts = trigger[9:].split(":")
            if len(parts) != 2:
                raise ValueError(f"Invalid interval format: {trigger}")
            
            unit, value = parts
            try:
                value = int(value)
            except ValueError:
                raise ValueError(f"Invalid interval value: {value}")
            
            kwargs = {unit: value}
            return IntervalTrigger(**kwargs)
        
        elif trigger.startswith("date:"):
            # Format: date:ISO_DATETIME
            date_str = trigger[5:].strip()
            try:
                run_date = datetime.fromisoformat(date_str)
            except ValueError:
                raise ValueError(f"Invalid date format: {date_str}")
            
            return DateTrigger(run_date=run_date)
        
        else:
            # Try to parse as cron expression directly
            try:
                return CronTrigger.from_crontab(trigger, timezone=self.timezone_str)
            except ValueError:
                raise ValueError(f"Unable to parse trigger: {trigger}")
    
    def calculate_next_run(
        self, trigger: Union[CronTrigger, IntervalTrigger, DateTrigger]
    ) -> Optional[datetime]:
        """Calculate next run time for trigger"""
        try:
            now = datetime.now(timezone.utc)
            return trigger.get_next_fire_time(None, now)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid trigger configuration: {e}")
            return None
        except AttributeError as e:
            logger.error(f"Trigger missing required method: {e}")
            return None
    
    def calculate_retry_delay(
        self, base_delay: int, retry_count: int, strategy: str = "exponential"
    ) -> int:
        """Calculate retry delay with backoff strategy"""
        if strategy == "exponential":
            # Exponential backoff: delay = base_delay * (2 ^ retry_count)
            return base_delay * (2 ** retry_count)
        
        elif strategy == "linear":
            # Linear backoff: delay = base_delay * (retry_count + 1)
            return base_delay * (retry_count + 1)
        
        elif strategy == "fixed":
            # Fixed delay
            return base_delay
        
        elif strategy == "fibonacci":
            # Fibonacci backoff
            return base_delay * self._fibonacci(retry_count + 1)
        
        else:
            logger.warning(f"Unknown retry strategy: {strategy}, using exponential")
            return self.calculate_retry_delay(base_delay, retry_count, "exponential")
    
    def is_business_hours(
        self, dt: datetime, business_start: int = 9, business_end: int = 17
    ) -> bool:
        """Check if datetime is within business hours (Mon-Fri, 9-17)"""
        # Check if it's a weekday (0=Monday, 6=Sunday)
        if dt.weekday() >= 5:  # Saturday or Sunday
            return False
        
        # Check if it's within business hours
        hour = dt.hour
        return business_start <= hour < business_end
    
    def calculate_business_hours_delay(
        self, current_time: datetime, business_start: int = 9
    ) -> Optional[datetime]:
        """Calculate delay to next business hours"""
        if self.is_business_hours(current_time):
            return current_time
        
        # If it's weekend, move to next Monday
        if current_time.weekday() >= 5:  # Weekend
            days_to_monday = 7 - current_time.weekday()
            next_monday = current_time + timedelta(days=days_to_monday)
            return next_monday.replace(hour=business_start, minute=0, second=0, microsecond=0)
        
        # If it's before business hours on weekday
        if current_time.hour < business_start:
            return current_time.replace(hour=business_start, minute=0, second=0, microsecond=0)
        
        # If it's after business hours on weekday, move to next day
        next_day = current_time + timedelta(days=1)
        return next_day.replace(hour=business_start, minute=0, second=0, microsecond=0)
    
    def validate_cron_expression(self, cron_expr: str) -> bool:
        """Validate cron expression"""
        try:
            croniter.croniter(cron_expr)
            return True
        except (croniter.CroniterBadCronError, ValueError, TypeError):
            return False
    
    def get_next_n_runs(
        self, trigger: Union[CronTrigger, IntervalTrigger, DateTrigger], n: int = 5
    ) -> List[datetime]:
        """Get next N run times for a trigger"""
        runs = []
        try:
            current_time = datetime.now(timezone.utc)
            
            for _ in range(n):
                next_run = trigger.get_next_fire_time(None, current_time)
                if next_run:
                    runs.append(next_run)
                    current_time = next_run
                else:
                    break
            
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid trigger configuration for next runs: {e}")
        except AttributeError as e:
            logger.error(f"Trigger missing required method for next runs: {e}")
        
        return runs
    
    def calculate_job_priority_weight(self, priority: JobPriority) -> float:
        """Calculate numeric weight for job priority"""
        weights = {
            JobPriority.LOW: 0.25,
            JobPriority.NORMAL: 1.0,
            JobPriority.HIGH: 2.0,
            JobPriority.CRITICAL: 4.0
        }
        return weights.get(priority, 1.0)
    
    def should_skip_execution(
        self,
        trigger: Union[CronTrigger, IntervalTrigger, DateTrigger],
        current_time: datetime,
        business_hours_only: bool = False
    ) -> bool:
        """Check if execution should be skipped based on conditions"""
        if business_hours_only and not self.is_business_hours(current_time):
            return True
        
        # Add more skip conditions as needed
        return False
    
    def _fibonacci(self, n: int) -> int:
        """Calculate fibonacci number"""
        if n <= 1:
            return 1
        elif n == 2:
            return 1
        else:
            a, b = 1, 1
            for _ in range(3, n + 1):
                a, b = b, a + b
            return b