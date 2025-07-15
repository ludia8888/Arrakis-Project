"""
Production-grade Garbage Collection and memory monitoring
gc.get_stats(), tracemalloc, objgraph, psutil 통합 구현
"""
import asyncio
import gc
import logging
import os
import sys
import threading
import time
import tracemalloc
import weakref
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# Production import - objgraph must be available for memory leak detection
import objgraph
import psutil
from prometheus_client import (
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    Metric,
    Summary,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Advanced GC Statistics Tracking
# =============================================================================


@dataclass
class GCGenStats:
 """세대별 GC 통계"""

 generation: int
 collections: int = 0
 collected: int = 0
 uncollectable: int = 0
 threshold: int = 0
 count: int = 0
 last_collection_time: Optional[datetime] = None
 collection_times: deque = field(default_factory = lambda: deque(maxlen = 100))


class AdvancedGCMonitor:
 """실전급 GC 모니터링"""

 def __init__(self):
 self.gen_stats = {i: GCGenStats(i) for i in range(3)}
 self.previous_stats = {}
 self.gc_callbacks_installed = False
 self.memory_snapshots = deque(maxlen = 1000) # 최근 1000개 스냅샷
 self.leak_suspects = defaultdict(list)
 self.object_growth_tracking = defaultdict(deque)
 self.heap_growth_history = deque(maxlen = 100)

 # Prometheus 메트릭
 self._setup_prometheus_metrics()

 # GC 디버깅 활성화
 self._enable_gc_debugging()

 # 메모리 추적 시작
 self._start_memory_tracking()

 def _setup_prometheus_metrics(self):
 """Prometheus 메트릭 설정"""

 # GC 수집 횟수
 self.gc_collections_total = Counter(
 "python_gc_collections_total", "Total garbage collections", ["generation"]
 )

 # GC 수집 hours
 self.gc_collection_time_seconds = Histogram(
 "python_gc_collection_time_seconds",
 "Time spent in garbage collection",
 ["generation"],
 buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
 )

 # 수집된 객체 수
 self.gc_objects_collected_total = Counter(
 "python_gc_objects_collected_total",
 "Objects collected by GC",
 ["generation"],
 )

 # 수집 불가능 객체 수
 self.gc_objects_uncollectable_total = Counter(
 "python_gc_objects_uncollectable_total",
 "Uncollectable objects found by GC",
 ["generation"],
 )

 # 세대별 객체 수
 self.gc_generation_objects = Gauge(
 "python_gc_generation_objects",
 "Objects in each generation before collection",
 ["generation"],
 )

 # 세대별 임계값
 self.gc_generation_threshold = Gauge(
 "python_gc_generation_threshold",
 "GC threshold for each generation",
 ["generation"],
 )

 # 힙 메모리 정보
 self.memory_heap_objects = Gauge(
 "python_memory_heap_objects_total", "Total objects in Python heap"
 )

 self.memory_heap_size_bytes = Gauge(
 "python_memory_heap_size_bytes", "Python heap size in bytes"
 )

 # 프로세스 메모리 (PSUtil)
 self.process_memory_rss_bytes = Gauge(
 "process_memory_rss_bytes", "Resident set size in bytes"
 )

 self.process_memory_vms_bytes = Gauge(
 "process_memory_vms_bytes", "Virtual memory size in bytes"
 )

 self.process_memory_percent = Gauge(
 "process_memory_percent", "Memory usage percentage"
 )

 # 메모리 누수 의심 객체
 self.memory_leak_suspects = Gauge(
 "python_memory_leak_suspects",
 "Number of objects suspected of memory leaks",
 ["object_type"],
 )

 # tracemalloc 메트릭
 self.memory_traced_peak_bytes = Gauge(
 "python_memory_traced_peak_bytes",
 "Peak memory usage tracked by tracemalloc",
 )

 self.memory_traced_current_bytes = Gauge(
 "python_memory_traced_current_bytes",
 "Current memory usage tracked by tracemalloc",
 )

 def _enable_gc_debugging(self):
 """GC 디버깅 활성화"""
 # GC 통계 출력 활성화 (옵션)
 if logger.isEnabledFor(logging.DEBUG):
 gc.set_debug(gc.DEBUG_STATS)

 # GC 콜백 설치
 if not self.gc_callbacks_installed:
 gc.callbacks.append(self._gc_callback)
 self.gc_callbacks_installed = True
 logger.info("GC callbacks installed for real-time monitoring")

 def _start_memory_tracking(self):
 """메모리 추적 시작"""
 if not tracemalloc.is_tracing():
 tracemalloc.start()
 logger.info("tracemalloc started for memory leak detection")

 def _gc_callback(self, phase: str, info: Dict):
 """GC 콜백 - 실hours GC 이벤트 처리"""
 try:
 generation = info.get("generation", -1)
 if generation >= 0:
 current_time = datetime.now()

 if phase == "start":
 # GC 시작
 self.gen_stats[generation].last_collection_time = current_time

 elif phase == "stop":
 # GC 완료
 if self.gen_stats[generation].last_collection_time:
 duration = (
 current_time
 - self.gen_stats[generation].last_collection_time
 ).total_seconds()
 self.gen_stats[generation].collection_times.append(duration)

 # Prometheus 메트릭 업데이트
 self.gc_collection_time_seconds.labels(
 generation = str(generation)
 ).observe(duration)

 logger.debug(
 f"GC generation {generation} completed in {duration:.4f}s"
 )

 except Exception as e:
 logger.error(f"Error in GC callback: {e}")

 def collect_gc_stats(self):
 """실hours GC 통계 수집"""
 try:
 # gc.get_stats() 사용
 stats = gc.get_stats()

 for i, stat in enumerate(stats):
 if i < 3: # 세대 0, 1, 2
 gen_stat = self.gen_stats[i]

 # 이전 값과 비교하여 증minutes 계산
 prev_collections = self.previous_stats.get(f"gen{i}_collections", 0)
 prev_collected = self.previous_stats.get(f"gen{i}_collected", 0)
 prev_uncollectable = self.previous_stats.get(
 f"gen{i}_uncollectable", 0
 )

 current_collections = stat.get("collections", 0)
 current_collected = stat.get("collected", 0)
 current_uncollectable = stat.get("uncollectable", 0)

 # 증minutes 계산
 if current_collections > prev_collections:
 collections_delta = current_collections - prev_collections
 self.gc_collections_total.labels(
 generation = str(i)
 )._value._value += collections_delta

 if current_collected > prev_collected:
 collected_delta = current_collected - prev_collected
 self.gc_objects_collected_total.labels(
 generation = str(i)
 )._value._value += collected_delta

 if current_uncollectable > prev_uncollectable:
 uncollectable_delta = current_uncollectable - prev_uncollectable
 self.gc_objects_uncollectable_total.labels(
 generation = str(i)
 )._value._value += uncollectable_delta

 # 현재 상태 저장
 self.previous_stats[f"gen{i}_collections"] = current_collections
 self.previous_stats[f"gen{i}_collected"] = current_collected
 self.previous_stats[f"gen{i}_uncollectable"] = current_uncollectable

 # 세대별 객체 수 및 임계값
 generation_counts = gc.get_count()
 generation_thresholds = gc.get_threshold()

 if i < len(generation_counts):
 self.gc_generation_objects.labels(generation = str(i)).set(
 generation_counts[i]
 )

 if i < len(generation_thresholds):
 self.gc_generation_threshold.labels(generation = str(i)).set(
 generation_thresholds[i]
 )

 # 전체 힙 정보
 all_objects = gc.get_objects()
 self.memory_heap_objects.set(len(all_objects))

 # 힙 크기 추정 (대략적)
 heap_size = sys.getsizeof(all_objects)
 for obj in all_objects[:1000]: # 샘플링으로 성능 최적화
 try:
 heap_size += sys.getsizeof(obj)
 except:
 pass

 self.memory_heap_size_bytes.set(heap_size)

 except Exception as e:
 logger.error(f"Error collecting GC stats: {e}")

 def collect_process_memory_stats(self):
 """PSUtil를 사용한 프로세스 메모리 통계"""
 try:
 process = psutil.Process()
 memory_info = process.memory_info()
 memory_percent = process.memory_percent()

 self.process_memory_rss_bytes.set(memory_info.rss)
 self.process_memory_vms_bytes.set(memory_info.vms)
 self.process_memory_percent.set(memory_percent)

 # 메모리 증가 추세 추적
 self.heap_growth_history.append(
 {
 "timestamp": datetime.now(),
 "rss": memory_info.rss,
 "vms": memory_info.vms,
 "percent": memory_percent,
 }
 )

 except Exception as e:
 logger.error(f"Error collecting process memory stats: {e}")

 def collect_tracemalloc_stats(self):
 """tracemalloc을 사용한 메모리 추적"""
 try:
 if tracemalloc.is_tracing():
 current, peak = tracemalloc.get_traced_memory()

 self.memory_traced_current_bytes.set(current)
 self.memory_traced_peak_bytes.set(peak)

 # 메모리 스냅샷 저장
 snapshot = tracemalloc.take_snapshot()
 self.memory_snapshots.append(
 {
 "timestamp": datetime.now(),
 "snapshot": snapshot,
 "current": current,
 "peak": peak,
 }
 )

 except Exception as e:
 logger.error(f"Error collecting tracemalloc stats: {e}")

 def detect_memory_leaks(self):
 """메모리 누수 탐지"""
 try:
 # Production objgraph integration - always available
 most_common = objgraph.most_common_types(limit = 20)

 for obj_type, count in most_common:
 # 객체 증가 추세 추적
 self.object_growth_tracking[obj_type].append(
 {"timestamp": datetime.now(), "count": count}
 )

 # 최근 데이터만 유지 (100개)
 if len(self.object_growth_tracking[obj_type]) > 100:
 self.object_growth_tracking[obj_type].popleft()

 # 누수 의심 탐지 (급격한 증가)
 if len(self.object_growth_tracking[obj_type]) >= 10:
 recent_counts = [
 item["count"]
 for item in list(self.object_growth_tracking[obj_type])[-10:]
 ]
 if len(set(recent_counts)) > 1: # 변화가 있는 경우
 growth_rate = (recent_counts[-1] - recent_counts[0]) / len(
 recent_counts
 )
 if growth_rate > 100: # 임계값: 평균 100개/측정 이상 증가
 self.leak_suspects[obj_type].append(
 {
 "detected_at": datetime.now(),
 "growth_rate": growth_rate,
 "current_count": count,
 }
 )

 # Prometheus 메트릭 업데이트
 self.memory_leak_suspects.labels(object_type = obj_type).set(
 count
 )

 logger.warning(
 f"Memory leak suspect detected: {obj_type} (growth rate: {growth_rate:.1f}/measurement)"
 )

 except Exception as e:
 logger.error(f"Error detecting memory leaks: {e}")

 def get_memory_report(self) -> Dict[str, Any]:
 """종합 메모리 리포트 생성"""
 try:
 report = {
 "timestamp": datetime.now().isoformat(),
 "gc_stats": {},
 "process_memory": {},
 "tracemalloc": {},
 "leak_suspects": {},
 "recommendations": [],
 }

 # GC 통계
 for i in range(3):
 gen_stat = self.gen_stats[i]
 recent_times = list(gen_stat.collection_times)[-10:]

 report["gc_stats"][f"generation_{i}"] = {
 "collections": gen_stat.collections,
 "collected": gen_stat.collected,
 "uncollectable": gen_stat.uncollectable,
 "avg_collection_time": sum(recent_times) / len(recent_times)
 if recent_times
 else 0,
 "max_collection_time": max(recent_times) if recent_times else 0,
 "recent_collections": len(recent_times),
 }

 # 프로세스 메모리
 if self.heap_growth_history:
 latest = self.heap_growth_history[-1]
 report["process_memory"] = {
 "rss_bytes": latest["rss"],
 "vms_bytes": latest["vms"],
 "percent": latest["percent"],
 "rss_mb": latest["rss"] / (1024 * 1024),
 "vms_mb": latest["vms"] / (1024 * 1024),
 }

 # tracemalloc
 if tracemalloc.is_tracing():
 current, peak = tracemalloc.get_traced_memory()
 report["tracemalloc"] = {
 "current_bytes": current,
 "peak_bytes": peak,
 "current_mb": current / (1024 * 1024),
 "peak_mb": peak / (1024 * 1024),
 }

 # 누수 의심 객체
 for obj_type, suspects in self.leak_suspects.items():
 if suspects:
 latest_suspect = suspects[-1]
 report["leak_suspects"][obj_type] = {
 "growth_rate": latest_suspect["growth_rate"],
 "current_count": latest_suspect["current_count"],
 "detected_at": latest_suspect["detected_at"].isoformat(),
 "total_detections": len(suspects),
 }

 # 권장사항 생성
 self._generate_recommendations(report)

 return report

 except Exception as e:
 logger.error(f"Error generating memory report: {e}")
 return {"error": str(e), "timestamp": datetime.now().isoformat()}

 def _generate_recommendations(self, report: Dict[str, Any]):
 """메모리 최적화 권장사항 생성"""
 recommendations = []

 # GC 성능 minutes석
 for gen, stats in report.get("gc_stats", {}).items():
 avg_time = stats.get("avg_collection_time", 0)
 if avg_time > 0.1: # 100ms 이상
 recommendations.append(
 f"{gen}: GC hours이 길어짐 ({avg_time:.3f}s). Create object 패턴 검토 필요"
 )

 uncollectable = stats.get("uncollectable", 0)
 if uncollectable > 0:
 recommendations.append(
 f"{gen}: 수집 불가능한 객체 발견 ({uncollectable}개). 순환 참조 확인 필요"
 )

 # 메모리 사용량 minutes석
 memory = report.get("process_memory", {})
 memory_percent = memory.get("percent", 0)
 if memory_percent > 80:
 recommendations.append(f"메모리 사용률 높음 ({memory_percent:.1f}%). 메모리 최적화 검토 필요")

 # 누수 의심 객체
 leak_suspects = report.get("leak_suspects", {})
 if leak_suspects:
 for obj_type, info in leak_suspects.items():
 growth_rate = info.get("growth_rate", 0)
 recommendations.append(
 f"메모리 누수 의심: {obj_type} (증가율: {growth_rate:.1f}/측정)"
 )

 report["recommendations"] = recommendations

 def force_gc_collection(self) -> Dict[str, Any]:
 """강제 GC 수행 및 결과 반환"""
 before_objects = len(gc.get_objects())
 before_memory = psutil.Process().memory_info().rss

 start_time = time.time()
 collected = gc.collect()
 duration = time.time() - start_time

 after_objects = len(gc.get_objects())
 after_memory = psutil.Process().memory_info().rss

 result = {
 "timestamp": datetime.now().isoformat(),
 "duration_seconds": duration,
 "objects_before": before_objects,
 "objects_after": after_objects,
 "objects_collected": before_objects - after_objects,
 "garbage_collected": collected,
 "memory_before_bytes": before_memory,
 "memory_after_bytes": after_memory,
 "memory_freed_bytes": before_memory - after_memory,
 "memory_freed_mb": (before_memory - after_memory) / (1024 * 1024),
 }

 logger.info(
 f"Manual GC completed: {collected} objects collected, "
 f"{result['memory_freed_mb']:.2f}MB freed in {duration:.3f}s"
 )

 return result

 def start_monitoring(self, interval: int = 30):
 """백그라운드 모니터링 시작"""

 def monitoring_loop():
 while True:
 try:
 self.collect_gc_stats()
 self.collect_process_memory_stats()
 self.collect_tracemalloc_stats()
 self.detect_memory_leaks()
 time.sleep(interval)
 except Exception as e:
 logger.error(f"Error in monitoring loop: {e}")
 time.sleep(interval)

 thread = threading.Thread(target = monitoring_loop, daemon = True)
 thread.start()
 logger.info(f"Advanced GC monitoring started (interval: {interval}s)")
 return thread


# =============================================================================
# Custom Prometheus Collector
# =============================================================================


class GCCustomCollector:
 """커스텀 Prometheus Collector"""

 def __init__(self, gc_monitor: AdvancedGCMonitor):
 self.gc_monitor = gc_monitor

 def collect(self):
 """Prometheus 메트릭 수집"""
 # 실hours 데이터 갱신
 self.gc_monitor.collect_gc_stats()
 self.gc_monitor.collect_process_memory_stats()
 self.gc_monitor.collect_tracemalloc_stats()

 # 표준 메트릭들 반환
 yield from [] # 메트릭들이 이미 등록되어 있으므로 별도 반환 불필요


# =============================================================================
# 전역 인스턴스 및 헬퍼 함수
# =============================================================================

_gc_monitor: Optional[AdvancedGCMonitor] = None


def get_gc_monitor() -> AdvancedGCMonitor:
 """글로벌 GC 모니터 인스턴스 반환"""
 global _gc_monitor
 if _gc_monitor is None:
 _gc_monitor = AdvancedGCMonitor()
 return _gc_monitor


def start_advanced_gc_monitoring(interval: int = 30) -> AdvancedGCMonitor:
 """고급 GC 모니터링 시작"""
 monitor = get_gc_monitor()
 monitor.start_monitoring(interval)

 # Prometheus 커스텀 컬렉터 등록
 collector = GCCustomCollector(monitor)
 REGISTRY.register(collector)

 logger.info("Advanced GC monitoring with Prometheus integration started")
 return monitor


def get_memory_status() -> Dict[str, Any]:
 """현재 메모리 상태 반환"""
 monitor = get_gc_monitor()
 return monitor.get_memory_report()


def force_garbage_collection() -> Dict[str, Any]:
 """강제 가비지 컬렉션 실행"""
 monitor = get_gc_monitor()
 return monitor.force_gc_collection()


def detect_memory_leaks_now() -> Dict[str, List[str]]:
 """즉시 메모리 누수 탐지 실행"""
 monitor = get_gc_monitor()
 monitor.detect_memory_leaks()

 result = {"leak_suspects": []}
 for obj_type, suspects in monitor.leak_suspects.items():
 if suspects:
 latest = suspects[-1]
 result["leak_suspects"].append(
 f"{obj_type}: {latest['current_count']} objects "
 f"(growth rate: {latest['growth_rate']:.1f}/measurement)"
 )

 return result
