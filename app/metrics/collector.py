#!/usr/bin/env python3
"""
Metrics Collector: In-memory histogram collector with percentile calculations.

Provides thread-safe timing metrics collection with fixed-size ring buffers
to avoid unbounded memory growth.
"""

import time
import threading
from typing import Dict, List, Optional, Any
from contextlib import contextmanager
from collections import deque
import statistics


class MetricsCollector:
    """Thread-safe in-memory histogram collector with ring buffers."""
    
    def __init__(self, buffer_size: int = 1000):
        """Initialize metrics collector with fixed buffer size."""
        self.buffer_size = buffer_size
        self._lock = threading.Lock()
        self._histograms: Dict[str, deque] = {}
        self._counters: Dict[str, int] = {}
    
    def record(self, name: str, value_ms: float):
        """Record a timing value for the given metric."""
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = deque(maxlen=self.buffer_size)
            
            self._histograms[name].append(value_ms)
    
    def increment(self, name: str, count: int = 1):
        """Increment a counter metric."""
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + count
    
    def summary(self, name: str) -> Dict[str, float]:
        """Get summary statistics for a metric."""
        with self._lock:
            if name not in self._histograms or len(self._histograms[name]) == 0:
                return {
                    "count": 0,
                    "min": 0.0,
                    "max": 0.0,
                    "p50": 0.0,
                    "p95": 0.0,
                    "avg": 0.0
                }
            
            values = list(self._histograms[name])
            sorted_values = sorted(values)
            count = len(values)
            
            return {
                "count": count,
                "min": float(min(values)),
                "max": float(max(values)),
                "p50": float(self._percentile(sorted_values, 50)),
                "p95": float(self._percentile(sorted_values, 95)),
                "avg": float(statistics.mean(values))
            }
    
    def get_counter(self, name: str) -> int:
        """Get counter value."""
        with self._lock:
            return self._counters.get(name, 0)
    
    def all_summaries(self) -> Dict[str, Dict[str, float]]:
        """Get summaries for all metrics."""
        with self._lock:
            return {name: self.summary(name) for name in self._histograms.keys()}
    
    def all_counters(self) -> Dict[str, int]:
        """Get all counter values."""
        with self._lock:
            return dict(self._counters)
    
    def reset(self):
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._histograms.clear()
            self._counters.clear()
    
    @staticmethod
    def _percentile(sorted_values: List[float], percentile: float) -> float:
        """Calculate percentile from sorted values."""
        if not sorted_values:
            return 0.0
        
        if percentile <= 0:
            return sorted_values[0]
        if percentile >= 100:
            return sorted_values[-1]
        
        # Linear interpolation method
        n = len(sorted_values)
        index = (percentile / 100.0) * (n - 1)
        
        if index == int(index):
            return sorted_values[int(index)]
        
        lower_index = int(index)
        upper_index = min(lower_index + 1, n - 1)
        weight = index - lower_index
        
        return sorted_values[lower_index] * (1 - weight) + sorted_values[upper_index] * weight


# Global metrics collector instance
_global_collector = MetricsCollector()


def record_metric(name: str, value_ms: float):
    """Record a timing metric to the global collector."""
    _global_collector.record(name, value_ms)


def increment_counter(name: str, count: int = 1):
    """Increment a counter in the global collector."""
    _global_collector.increment(name, count)


def get_summary(name: str) -> Dict[str, float]:
    """Get summary for a metric from the global collector."""
    return _global_collector.summary(name)


def get_counter(name: str) -> int:
    """Get counter value from the global collector."""
    return _global_collector.get_counter(name)


def get_all_metrics() -> Dict[str, Any]:
    """Get all metrics and counters from the global collector."""
    return {
        "metrics": _global_collector.all_summaries(),
        "counters": _global_collector.all_counters()
    }


@contextmanager
def time_block(name: str):
    """Context manager to time a block of code and record the metric."""
    start_time = time.perf_counter()
    try:
        yield
    finally:
        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000
        record_metric(name, duration_ms)


class TimingContext:
    """Helper class for nested timing contexts."""
    
    def __init__(self):
        self.timers = {}
    
    def start(self, name: str):
        """Start timing for a named operation."""
        self.timers[name] = time.perf_counter()
    
    def end(self, name: str) -> float:
        """End timing and record metric, return duration in ms."""
        if name not in self.timers:
            return 0.0
        
        duration_ms = (time.perf_counter() - self.timers[name]) * 1000
        record_metric(name, duration_ms)
        del self.timers[name]
        return duration_ms
    
    def end_all(self) -> Dict[str, float]:
        """End all active timers and return durations."""
        results = {}
        for name in list(self.timers.keys()):
            results[name] = self.end(name)
        return results


# Convenience functions for common patterns
def time_stage0_total(func):
    """Decorator to time Stage-0 total execution."""
    def wrapper(*args, **kwargs):
        with time_block("stage0.total"):
            return func(*args, **kwargs)
    return wrapper


def time_stage2_total(func):
    """Decorator to time Stage-2 total execution."""
    def wrapper(*args, **kwargs):
        with time_block("stage2.total"):
            return func(*args, **kwargs)
    return wrapper


# Path tracking helpers
def record_path_taken(path: str):
    """Record which path was taken through the system."""
    path_counter_name = f"paths.{path}"
    increment_counter(path_counter_name)


def get_path_stats() -> Dict[str, int]:
    """Get statistics for all paths taken."""
    all_counters = _global_collector.all_counters()
    return {
        key.replace("paths.", ""): value 
        for key, value in all_counters.items() 
        if key.startswith("paths.")
    }
