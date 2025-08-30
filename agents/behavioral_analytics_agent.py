#!/usr/bin/env python3
"""
Behavioral Analytics Agent - Week 6 Implementation
Advanced behavioral pattern analysis for threat detection
"""

import asyncio
import time
import json
import logging
import numpy as np
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from .minimal_base_agent import MinimalBaseAgent

@dataclass
class BehavioralPattern:
    pattern_id: str
    user_id: str
    pattern_type: str
    anomaly_score: float
    confidence: float
    evidence: Dict[str, Any]
    timestamp: datetime

class BehavioralAnalyticsAgent(MinimalBaseAgent):
    """Advanced behavioral analytics for insider threat detection"""
    
    def __init__(self):
        super().__init__("BehavioralAnalyticsAgent")
        self.user_baselines = {}
        self.anomaly_thresholds = {
            "access_pattern": 0.7,
            "data_usage": 0.6,
            "time_pattern": 0.5,
            "collaboration": 0.8
        }
        logging.info("BehavioralAnalyticsAgent initialized")
    
    def run(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Required abstract method implementation - synchronous wrapper"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.execute(prompt, context))
        except RuntimeError:
            return asyncio.run(self.execute(prompt, context))
    
    async def analyze_user_patterns(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze user behavioral patterns for anomalies"""
        start_time = time.time()
        
        try:
            user_id = user_data.get("user_id", "unknown")
            activities = user_data.get("activities", [])
            
            # Analyze different behavioral dimensions
            access_analysis = self._analyze_access_patterns(activities)
            temporal_analysis = self._analyze_temporal_patterns(activities)
            data_analysis = self._analyze_data_usage_patterns(activities)
            
            # Calculate composite anomaly score
            composite_score = max(
                access_analysis.get("anomaly_score", 0),
                temporal_analysis.get("anomaly_score", 0),
                data_analysis.get("anomaly_score", 0)
            )
            
            # Generate behavioral patterns
            patterns = []
            if access_analysis.get("anomaly_score", 0) > self.anomaly_thresholds["access_pattern"]:
                patterns.append(BehavioralPattern(
                    pattern_id=f"access_{user_id}_{int(time.time())}",
                    user_id=user_id,
                    pattern_type="access_anomaly",
                    anomaly_score=access_analysis["anomaly_score"],
                    confidence=0.8,
                    evidence=access_analysis,
                    timestamp=datetime.now()
                ))
            
            return {
                "agent": self.name,
                "user_id": user_id,
                "composite_anomaly_score": composite_score,
                "access_analysis": access_analysis,
                "temporal_analysis": temporal_analysis,
                "data_analysis": data_analysis,
                "behavioral_patterns": [pattern.__dict__ for pattern in patterns],
                "processing_time": time.time() - start_time,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Behavioral analysis failed: {e}")
            return {
                "agent": self.name,
                "error": str(e),
                "processing_time": time.time() - start_time
            }
    
    def _analyze_access_patterns(self, activities: List[Dict]) -> Dict[str, Any]:
        """Analyze access patterns for anomalies"""
        if not activities:
            return {"anomaly_score": 0.0, "details": "No activities"}
        
        # Extract access events
        access_events = [a for a in activities if a.get("type") == "file_access"]
        
        if not access_events:
            return {"anomaly_score": 0.0, "details": "No access events"}
        
        # Analyze access frequency and patterns
        access_count = len(access_events)
        unique_files = len(set(event.get("file_path", "") for event in access_events))
        
        # Check for sensitive database access
        sensitive_files = [e for e in access_events if any(pattern in e.get("file_path", "").lower() 
                          for pattern in ["database", "customers", "financial", "confidential"])]
        
        # Calculate anomaly indicators
        access_diversity = unique_files / max(access_count, 1)
        sensitive_access_ratio = len(sensitive_files) / max(access_count, 1)
        
        # High risk if accessing multiple sensitive files
        anomaly_score = 0.0
        if sensitive_access_ratio > 0.5:  # More than half are sensitive files
            anomaly_score += 0.8
        elif len(sensitive_files) > 1:  # Multiple sensitive files
            anomaly_score += 0.6
        elif len(sensitive_files) > 0:  # Any sensitive file access
            anomaly_score += 0.4
            
        # Additional penalty for rapid sequential access
        if access_count > 3:
            anomaly_score += 0.3
        
        return {
            "anomaly_score": min(anomaly_score, 1.0),
            "access_count": access_count,
            "unique_files": unique_files,
            "sensitive_files": len(sensitive_files),
            "access_diversity": access_diversity,
            "details": "Access pattern analysis completed"
        }
    
    def _analyze_temporal_patterns(self, activities: List[Dict]) -> Dict[str, Any]:
        """Analyze temporal patterns for anomalies"""
        if len(activities) < 2:
            return {"anomaly_score": 0.0, "details": "Insufficient data"}
        
        # Extract timestamps
        timestamps = [a.get("timestamp", 0) for a in activities]
        timestamps.sort()
        
        # Calculate time intervals
        intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
        
        if not intervals:
            return {"anomaly_score": 0.0, "details": "No intervals"}
        
        # Analyze timing patterns
        avg_interval = np.mean(intervals)
        interval_variance = np.var(intervals)
        
        # High variance might indicate unusual activity patterns
        anomaly_score = min(interval_variance / (avg_interval + 1), 1.0)
        
        return {
            "anomaly_score": anomaly_score,
            "avg_interval": avg_interval,
            "interval_variance": interval_variance,
            "total_activities": len(activities),
            "details": "Temporal pattern analysis completed"
        }
    
    def _analyze_data_usage_patterns(self, activities: List[Dict]) -> Dict[str, Any]:
        """Analyze data usage patterns"""
        data_activities = [a for a in activities if a.get("type") in ["download", "upload", "copy"]]
        
        if not data_activities:
            return {"anomaly_score": 0.0, "details": "No data activities"}
        
        # Calculate data volume
        total_volume = sum(a.get("size", 0) for a in data_activities)
        avg_size = total_volume / len(data_activities)
        
        # Check for external uploads (data exfiltration)
        external_uploads = [a for a in data_activities if a.get("type") == "upload" and 
                           a.get("destination", "").endswith(".com")]
        
        # Calculate anomaly score with improved logic
        anomaly_score = 0.0
        
        # Large volume penalty (100MB+ is very suspicious)
        if total_volume > 100000000:  # 100MB
            anomaly_score += 0.9
        elif total_volume > 50000000:  # 50MB
            anomaly_score += 0.7
        elif total_volume > 10000000:  # 10MB
            anomaly_score += 0.5
        
        # External upload penalty
        if external_uploads:
            anomaly_score += 0.8  # High penalty for external uploads
        
        # Multiple large transfers
        large_transfers = [a for a in data_activities if a.get("size", 0) > 10000000]
        if len(large_transfers) > 1:
            anomaly_score += 0.6
        
        return {
            "anomaly_score": min(anomaly_score, 1.0),
            "total_volume": total_volume,
            "avg_size": avg_size,
            "data_activity_count": len(data_activities),
            "external_uploads": len(external_uploads),
            "large_transfers": len(large_transfers),
            "details": "Data usage analysis completed"
        }
    
    async def execute(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute behavioral analytics"""
        if not context or "user_data" not in context:
            return {
                "agent": self.name,
                "error": "No user data provided for behavioral analysis",
                "status": "error"
            }
        
        return await self.analyze_user_patterns(context["user_data"])
