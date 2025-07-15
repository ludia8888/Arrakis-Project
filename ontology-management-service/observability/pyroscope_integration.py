"""
Pyroscope Integration for Continuous Profiling
실시간 성능 프로파일링을 위한 Pyroscope 통합
"""

import logging
import os
import platform
import sys
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import psutil

logger = logging.getLogger(__name__)

import py_spy

# Production imports - profiling libraries must be available
import pyroscope


@dataclass
class PyroscopeConfig:
 """Pyroscope configuration"""

 server_address: str = "http://localhost:4040"
 application_name: str = "oms-service"
 tags: Dict[str, str] = None
 sample_rate: int = 100 # Hz
 upload_rate: int = 10 # seconds
 auth_token: Optional[str] = None
 enable_logging: bool = True

 def __post_init__(self):
 if self.tags is None:
 self.tags = self._default_tags()

 def _default_tags(self) -> Dict[str, str]:
 """Generate default tags"""
 return {
 "service": self.application_name,
 "environment": os.getenv("ENVIRONMENT", "development"),
 "hostname": platform.node(),
 "python_version": platform.python_version(),
 "platform": platform.system().lower(),
 "cpu_count": str(psutil.cpu_count()),
 }


class PyroscopeProfiler:
 """
 Enterprise-grade Pyroscope profiler integration
 """

 def __init__(self, config: PyroscopeConfig):
 self.config = config
 self.profiling_started = False
 self._profiler = None
 self._custom_labels = {}

 def start_profiling(self) -> bool:
 """Start continuous profiling with Pyroscope"""
 if self.profiling_started:
 logger.warning("Profiling already started")
 return True

 try:
 # Configure Pyroscope
 pyroscope.configure(
 app_name = self.config.application_name,
 server_address = self.config.server_address,
 auth_token = self.config.auth_token,
 sample_rate = self.config.sample_rate,
 upload_rate = self.config.upload_rate,
 tags = self.config.tags,
 enable_logging = self.config.enable_logging,
 )

 # Start profiling
 pyroscope.start()
 self.profiling_started = True

 logger.info(
 f"🔥 Pyroscope profiling started: {self.config.application_name} "
 f"→ {self.config.server_address}"
 )

 # Log configuration details
 logger.info(f" 📊 Sample rate: {self.config.sample_rate} Hz")
 logger.info(f" 📤 Upload interval: {self.config.upload_rate} seconds")
 logger.info(f" 🏷️ Tags: {self.config.tags}")

 return True

 except Exception as e:
 logger.error(f"Failed to start Pyroscope profiling: {e}")
 return False

 def stop_profiling(self):
 """Stop profiling"""
 if self.profiling_started:
 try:
 pyroscope.stop()
 self.profiling_started = False
 logger.info("Pyroscope profiling stopped")
 except Exception as e:
 logger.error(f"Error stopping profiling: {e}")

 def tag(self, **tags) -> "TagContext":
 """Create a context manager for custom tags"""
 return TagContext(tags)

 def profile_function(self, func: Callable) -> Callable:
 """Decorator to profile specific functions"""

 def wrapper(*args, **kwargs):
 if self.profiling_started:
 with pyroscope.tag_wrapper(
 {
 "function": func.__name__,
 "module": func.__module__,
 }
 ):
 return func(*args, **kwargs)
 else:
 return func(*args, **kwargs)

 wrapper.__name__ = func.__name__
 wrapper.__doc__ = func.__doc__
 return wrapper

 def add_global_label(self, key: str, value: str):
 """Add a global label that will be included in all profiles"""
 self._custom_labels[key] = value
 if self.profiling_started:
 # Update tags in running profiler
 new_tags = {**self.config.tags, **self._custom_labels}
 pyroscope.configure(tags = new_tags)

 def get_profiling_stats(self) -> Dict[str, Any]:
 """Get current profiling statistics"""
 stats = {
 "profiling_active": self.profiling_started,
 "server_address": self.config.server_address,
 "application_name": self.config.application_name,
 "sample_rate": self.config.sample_rate,
 "tags": {**self.config.tags, **self._custom_labels},
 }

 if self.profiling_started:
 # Add runtime stats
 process = psutil.Process()
 stats.update(
 {
 "cpu_percent": process.cpu_percent(),
 "memory_rss_mb": process.memory_info().rss / (1024 * 1024),
 "num_threads": process.num_threads(),
 "runtime_seconds": int(process.create_time()),
 }
 )

 return stats


class TagContext:
 """Context manager for Pyroscope tags"""

 def __init__(self, tags: Dict[str, str]):
 self.tags = tags
 self._token = None

 def __enter__(self):
 self._token = pyroscope.tag(self.tags).__enter__()
 return self

 def __exit__(self, exc_type, exc_val, exc_tb):
 if self._token:
 self._token.__exit__(exc_type, exc_val, exc_tb)


# FastAPI integration
def setup_fastapi_profiling(app, config: Optional[PyroscopeConfig] = None):
 """Setup Pyroscope profiling for FastAPI application"""
 if config is None:
 config = PyroscopeConfig()

 profiler = PyroscopeProfiler(config)

 @app.on_event("startup")
 async def startup_profiling():
 """Start profiling on app startup"""
 profiler.start_profiling()
 app.state.pyroscope_profiler = profiler

 @app.on_event("shutdown")
 async def shutdown_profiling():
 """Stop profiling on app shutdown"""
 profiler.stop_profiling()

 @app.middleware("http")
 async def profile_requests(request, call_next):
 """Profile each HTTP request"""
 if profiler.profiling_started:
 tags = {
 "endpoint": request.url.path,
 "method": request.method,
 }
 with profiler.tag(**tags):
 response = await call_next(request)
 tags["status_code"] = str(response.status_code)
 return response
 else:
 return await call_next(request)

 return profiler


# Standalone profiling utilities
def profile_code_block(name: str, **tags):
 """Profile a code block"""
 return pyroscope.tag_wrapper({"block": name, **tags})


def get_profiler_instance(
 config: Optional[PyroscopeConfig] = None,
) -> PyroscopeProfiler:
 """Get or create a profiler instance"""
 if config is None:
 config = PyroscopeConfig()
 return PyroscopeProfiler(config)


# Advanced profiling features
class AdvancedProfiler(PyroscopeProfiler):
 """Extended profiler with advanced features"""

 def __init__(self, config: PyroscopeConfig):
 super().__init__(config)
 self._profile_threads = {}

 def profile_thread(self, thread_name: str):
 """Profile a specific thread"""

 def decorator(func):
 def wrapper(*args, **kwargs):
 thread = threading.Thread(
 target = self._profiled_thread_target,
 args=(func, thread_name, args, kwargs),
 name = thread_name,
 )
 thread.start()
 self._profile_threads[thread_name] = thread
 return thread

 return wrapper

 return decorator

 def _profiled_thread_target(self, func, thread_name, args, kwargs):
 """Target function for profiled threads"""
 if self.profiling_started:
 with pyroscope.tag_wrapper({"thread": thread_name}):
 return func(*args, **kwargs)
 else:
 return func(*args, **kwargs)

 def profile_async_function(self, func: Callable) -> Callable:
 """Profile async functions"""

 async def wrapper(*args, **kwargs):
 if self.profiling_started:
 with pyroscope.tag_wrapper(
 {
 "async_function": func.__name__,
 "module": func.__module__,
 }
 ):
 return await func(*args, **kwargs)
 else:
 return await func(*args, **kwargs)

 wrapper.__name__ = func.__name__
 wrapper.__doc__ = func.__doc__
 return wrapper


# Export profiling metrics to Prometheus
class PyroscopeMetricsExporter:
 """Export Pyroscope metrics to Prometheus"""

 def __init__(self, profiler: PyroscopeProfiler):
 self.profiler = profiler
 self._setup_metrics()

 def _setup_metrics(self):
 """Setup Prometheus metrics"""
 try:
 from prometheus_client import Gauge, Info

 self.profiling_active = Gauge(
 "pyroscope_profiling_active", "Whether Pyroscope profiling is active"
 )

 self.profiling_info = Info(
 "pyroscope_profiling", "Pyroscope profiling information"
 )

 self.profile_upload_success = Gauge(
 "pyroscope_profile_upload_success_total",
 "Total successful profile uploads",
 )

 self.profile_upload_failures = Gauge(
 "pyroscope_profile_upload_failure_total", "Total failed profile uploads"
 )

 except ImportError:
 logger.warning("prometheus_client not available for metrics export")

 def update_metrics(self):
 """Update Prometheus metrics"""
 stats = self.profiler.get_profiling_stats()

 if hasattr(self, "profiling_active"):
 self.profiling_active.set(1 if stats["profiling_active"] else 0)

 if hasattr(self, "profiling_info"):
 self.profiling_info.info(
 {
 "server": stats["server_address"],
 "application": stats["application_name"],
 "sample_rate": str(stats["sample_rate"]),
 }
 )


# Default instance
_default_profiler: Optional[PyroscopeProfiler] = None


def get_default_profiler() -> PyroscopeProfiler:
 """Get the default profiler instance"""
 global _default_profiler
 if _default_profiler is None:
 _default_profiler = PyroscopeProfiler(PyroscopeConfig())
 return _default_profiler


def start_default_profiling():
 """Start profiling with default configuration"""
 profiler = get_default_profiler()
 return profiler.start_profiling()
