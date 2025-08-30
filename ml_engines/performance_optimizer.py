import asyncio
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import threading
from functools import lru_cache
import hashlib

class OptimizationLevel(Enum):
    FAST = "fast"           # <50ms - Rule-based only
    BALANCED = "balanced"   # <200ms - Hybrid approach
    THOROUGH = "thorough"   # <500ms - Full analysis

@dataclass
class PerformanceMetrics:
    total_time: float
    method_times: Dict[str, float]
    cache_hits: int
    cache_misses: int
    optimization_level: OptimizationLevel
    early_exits: int

class IntelligentRouter:
    """Dynamic routing based on content type and risk profile"""
    
    def __init__(self):
        self.cache = {}
        self.cache_lock = threading.Lock()
        self.performance_history = []
        
        # Content type patterns for fast classification
        self.code_patterns = [
            "def ", "function", "class ", "import ", "from ", "<?", "#!/",
            "{", "}", ";", "var ", "const ", "let ", "if (", "for (", "while ("
        ]
        
        self.injection_quick_patterns = [
            "ignore", "forget", "system prompt", "previous instructions",
            "override", "bypass", "jailbreak", "dan", "pretend"
        ]
        
        logging.info("IntelligentRouter initialized with caching and performance tracking")
    
    def _calculate_content_hash(self, text: str) -> str:
        """Calculate hash for caching"""
        return hashlib.md5(text.encode()).hexdigest()[:16]
    
    def _classify_content_quickly(self, text: str) -> Tuple[str, float]:
        """Fast content classification for routing decisions"""
        text_lower = text.lower()
        
        # Quick injection check - prioritize single pattern detection for fast routing
        injection_score = sum(1 for pattern in self.injection_quick_patterns if pattern in text_lower)
        if injection_score >= 1:  # Single pattern should trigger fast routing, not thorough
            return "high_risk", 0.7  # Lower risk to route to fast instead of thorough
        
        # Code detection - improved patterns
        code_score = sum(1 for pattern in self.code_patterns if pattern in text)
        if code_score >= 1:  # Further lowered threshold for better detection
            return "code", 0.8
        
        # Length-based routing - improved thresholds  
        if len(text) > 200:  # Further lowered threshold for long text
            return "long_text", 0.6
        elif len(text) < 50:
            return "short_text", 0.3
        
        return "normal_text", 0.5
    
    async def route_analysis(self, prompt: str, user_risk_profile: str = "normal") -> OptimizationLevel:
        """Determine optimal analysis level based on content and risk profile"""
        
        # Check cache first
        content_hash = self._calculate_content_hash(prompt)
        with self.cache_lock:
            if content_hash in self.cache:
                return self.cache[content_hash]
        
        # Quick content classification
        content_type, risk_estimate = self._classify_content_quickly(prompt)
        
        # Improved routing logic
        if content_type == "high_risk":
            # High risk content should use fast detection for speed
            optimization_level = OptimizationLevel.FAST
        elif content_type == "code" or content_type == "long_text" or risk_estimate > 0.6:
            optimization_level = OptimizationLevel.BALANCED
        elif user_risk_profile == "high":
            optimization_level = OptimizationLevel.THOROUGH
        else:
            optimization_level = OptimizationLevel.FAST
        
        # Cache the result
        with self.cache_lock:
            self.cache[content_hash] = optimization_level
        
        return optimization_level

class FastAnalysisEngine:
    """Optimized analysis engine targeting <200ms performance"""
    
    def __init__(self):
        self.router = IntelligentRouter()
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Pre-compiled patterns for ultra-fast detection
        self.critical_patterns = {
            "injection": ["ignore previous", "forget everything", "system prompt", "ignore", "forget", "previous instructions"],
            "jailbreak": ["dan", "jailbreak", "unrestricted", "do anything now", "bypass"],
            "malicious": ["rm -rf", "format c:", "delete *", "os.system", "import os"]
        }
        
        # Performance tracking
        self.metrics_history = []
        
        logging.info("FastAnalysisEngine initialized with performance optimization")
    
    @lru_cache(maxsize=1000)
    def _cached_pattern_match(self, text_hash: str, text: str) -> Dict[str, float]:
        """Cached pattern matching for repeated content"""
        scores = {}
        text_lower = text.lower()
        
        for category, patterns in self.critical_patterns.items():
            score = 0
            for pattern in patterns:
                if pattern in text_lower:
                    score += 0.3
            scores[category] = min(score, 1.0)
        
        return scores
    
    async def fast_scan(self, prompt: str) -> Dict[str, Any]:
        """Ultra-fast scanning <50ms"""
        start_time = time.time()
        
        # Use cached pattern matching
        text_hash = hashlib.md5(prompt.encode()).hexdigest()
        pattern_scores = self._cached_pattern_match(text_hash, prompt)
        
        max_score = max(pattern_scores.values()) if pattern_scores else 0.0
        
        # Improved decision thresholds
        if max_score >= 0.3:  # Lowered threshold for blocking threats
            decision = "Blocked"
        elif max_score >= 0.1:
            decision = "Risky"
        else:
            decision = "Safe"
        
        processing_time = time.time() - start_time
        
        return {
            "final_decision": decision,
            "risk_score": max_score,
            "confidence": 0.8 if max_score > 0.5 else 0.6,
            "processing_time": processing_time,
            "method": "fast_scan",
            "pattern_scores": pattern_scores
        }
    
    async def balanced_analysis(self, prompt: str) -> Dict[str, Any]:
        """Balanced analysis targeting <200ms with fallback"""
        start_time = time.time()
        
        try:
            # Import hybrid ensemble
            from .hybrid_ensemble import HybridThreatDetector
            
            # Create lightweight version
            detector = HybridThreatDetector()
            
            # Run only rule-based + BERT (skip LSTM for speed)
            rule_task = detector.rule_engine.scan(prompt)
            bert_task = detector.bert_classifier.predict(prompt)
            
            # Execute in parallel
            rule_result, bert_result = await asyncio.gather(rule_task, bert_task)
            
            # Simple fusion
            rule_score = rule_result.get("risk_score", 0.0)
            bert_score = bert_result.get("risk_score", 0.0)
            
            # Weighted average
            final_score = (rule_score * 0.6) + (bert_score * 0.4)
            
            # Improved decision logic
            if final_score >= 0.5:
                decision = "Blocked"
            elif final_score >= 0.2:
                decision = "Risky"
            else:
                decision = "Safe"
            
            processing_time = time.time() - start_time
            
            return {
                "final_decision": decision,
                "risk_score": final_score,
                "confidence": (rule_result.get("confidence", 0.5) + bert_result.get("confidence", 0.5)) / 2,
                "processing_time": processing_time,
                "method": "balanced_analysis",
                "optimization_level": "balanced",
                "component_scores": {
                    "rule_based": rule_score,
                    "bert": bert_score
                }
            }
            
        except Exception as e:
            logging.error(f"Balanced analysis failed: {e}")
            # Enhanced fallback with balanced-like scoring
            result = await self.fast_scan(prompt)
            result["method"] = "balanced_fallback"
            result["optimization_level"] = "balanced"
            result["fallback_reason"] = str(e)
            return result
    
    async def thorough_analysis(self, prompt: str, llm_response: Optional[str] = None) -> Dict[str, Any]:
        """Comprehensive analysis with hallucination detection and fallback"""
        start_time = time.time()
        
        try:
            # Import all components
            from .hybrid_ensemble import HybridThreatDetector
            from .attention_tracker import AttentionDriftDetector
            
            # Initialize detectors
            hybrid_detector = HybridThreatDetector()
            attention_detector = AttentionDriftDetector()
            
            # Run hybrid analysis
            hybrid_result = await hybrid_detector.analyze_threat(prompt, llm_response)
            
            # Run attention analysis if LLM response provided
            attention_result = None
            if llm_response:
                attention_result = attention_detector.analyze_attention_drift(prompt, llm_response)
            
            # Combine results
            final_score = hybrid_result.risk_score
            
            if attention_result:
                # Incorporate hallucination detection
                hallucination_score = attention_result.attention_patterns.get("hallucination_score", 0.0)
                final_score = max(final_score, hallucination_score)
            
            processing_time = time.time() - start_time
            
            return {
                "final_decision": hybrid_result.final_decision,
                "risk_score": final_score,
                "confidence": hybrid_result.confidence,
                "processing_time": processing_time,
                "method": "thorough_analysis",
                "optimization_level": "thorough",
                "hybrid_result": hybrid_result.__dict__,
                "attention_result": attention_result.__dict__ if attention_result else None
            }
            
        except Exception as e:
            logging.error(f"Thorough analysis failed: {e}")
            # Enhanced fallback with thorough-like scoring
            result = await self.fast_scan(prompt)
            result["method"] = "thorough_fallback"
            result["optimization_level"] = "thorough"
            result["fallback_reason"] = str(e)
            return result
    
    async def analyze_optimized(self, prompt: str, llm_response: Optional[str] = None, 
                              user_risk_profile: str = "normal") -> Dict[str, Any]:
        """Main optimized analysis entry point"""
        
        # Determine optimization level
        optimization_level = await self.router.route_analysis(prompt, user_risk_profile)
        
        # Route to appropriate analysis method
        if optimization_level == OptimizationLevel.FAST:
            result = await self.fast_scan(prompt)
        elif optimization_level == OptimizationLevel.BALANCED:
            result = await self.balanced_analysis(prompt)
        else:  # THOROUGH
            result = await self.thorough_analysis(prompt, llm_response)
        
        # Add optimization metadata
        result["optimization_level"] = optimization_level.value
        result["router_decision"] = optimization_level.value
        
        # Track performance
        self._track_performance(result)
        
        return result
    
    def _track_performance(self, result: Dict[str, Any]):
        """Track performance metrics for optimization"""
        processing_time = result.get("processing_time", 0.0)
        method = result.get("method", "unknown")
        
        self.metrics_history.append({
            "timestamp": time.time(),
            "processing_time": processing_time,
            "method": method,
            "optimization_level": result.get("optimization_level", "unknown")
        })
        
        # Keep only recent metrics (last 1000)
        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-1000:]
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if not self.metrics_history:
            return {"error": "No performance data available"}
        
        times = [m["processing_time"] for m in self.metrics_history]
        methods = [m["method"] for m in self.metrics_history]
        
        stats = {
            "total_analyses": len(self.metrics_history),
            "average_time": np.mean(times),
            "median_time": np.median(times),
            "95th_percentile": np.percentile(times, 95),
            "max_time": np.max(times),
            "min_time": np.min(times),
            "method_distribution": {method: methods.count(method) for method in set(methods)},
            "sub_200ms_percentage": (sum(1 for t in times if t < 0.2) / len(times)) * 100
        }
        
        return stats

class CacheManager:
    """Advanced caching for repeated analysis patterns"""
    
    def __init__(self, max_size: int = 10000):
        self.cache = {}
        self.access_times = {}
        self.max_size = max_size
        self.lock = threading.Lock()
        
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached result"""
        with self.lock:
            if key in self.cache:
                self.access_times[key] = time.time()
                return self.cache[key]
        return None
    
    def set(self, key: str, value: Dict[str, Any]):
        """Set cached result with LRU eviction"""
        with self.lock:
            # Evict if cache is full
            if len(self.cache) >= self.max_size:
                # Remove least recently used
                lru_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
                del self.cache[lru_key]
                del self.access_times[lru_key]
            
            self.cache[key] = value
            self.access_times[key] = time.time()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            return {
                "cache_size": len(self.cache),
                "max_size": self.max_size,
                "utilization": (len(self.cache) / self.max_size) * 100
            }
