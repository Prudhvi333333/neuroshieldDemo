"""
Metrics module: Performance monitoring and timing collection.
"""

from .collector import MetricsCollector, time_block, record_metric, get_summary

__all__ = ["MetricsCollector", "time_block", "record_metric", "get_summary"]
