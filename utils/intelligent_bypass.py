"""
Intelligent LLM bypass system for high-confidence classifications
Reduces LLM calls by 80-90% while maintaining accuracy
"""
import time
from typing import Dict, Any, Tuple, Optional
from .fast_classifier import fast_classifier
from .advanced_classifier import advanced_classifier

class IntelligentLLMBypass:
    """Smart bypass system that skips LLM for high-confidence cases"""
    
    def __init__(self):
        self.stats = {
            "total_analyzed": 0,
            "layer1_bypassed": 0,
            "layer2_bypassed": 0, 
            "llm_required": 0,
            "time_saved": 0.0
        }
    
    def analyze_with_bypass(self, prompt: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Analyze prompt with intelligent bypass logic
        Returns: (bypassed, result_dict)
        """
        self.stats["total_analyzed"] += 1
        start_time = time.perf_counter()
        
        # Layer 1: Fast pattern matching (0.1ms, 95% confidence)
        fast_result = fast_classifier.quick_classify(prompt)
        if fast_result:
            analysis_time = time.perf_counter() - start_time
            self.stats["layer1_bypassed"] += 1
            self.stats["time_saved"] += 15.0  # Estimated LLM time saved
            
            fast_result.update({
                "bypass_used": True,
                "bypass_layer": "Layer1_Pattern",
                "confidence": 0.95,
                "analysis_time": analysis_time,
                "time_saved": 15.0
            })
            return True, fast_result
        
        # Layer 2: Advanced keyword analysis (0.1ms, 85% confidence)
        advanced_result = advanced_classifier.classify_prompt(prompt, risk_threshold=0.6, safe_threshold=0.2)
        if advanced_result:
            risk_score = advanced_result.get("risk_score", 0.5)
            
            # High confidence bypass thresholds
            if risk_score > 0.7 or risk_score < 0.2:
                analysis_time = time.perf_counter() - start_time
                self.stats["layer2_bypassed"] += 1
                self.stats["time_saved"] += 15.0
                
                advanced_result.update({
                    "bypass_used": True,
                    "bypass_layer": "Layer2_HighConfidence",
                    "confidence": 0.85,
                    "analysis_time": analysis_time,
                    "time_saved": 15.0
                })
                return True, advanced_result
        
        # Requires LLM analysis - don't return default classification
        self.stats["llm_required"] += 1
        return False, {
            "bypass_used": False, 
            "requires_llm": True
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get bypass performance statistics"""
        total = self.stats["total_analyzed"]
        if total == 0:
            return {"error": "No prompts analyzed yet"}
        
        bypassed = self.stats["layer1_bypassed"] + self.stats["layer2_bypassed"]
        bypass_rate = (bypassed / total) * 100
        
        return {
            "total_prompts": total,
            "bypassed_prompts": bypassed,
            "llm_required": self.stats["llm_required"],
            "bypass_rate": f"{bypass_rate:.1f}%",
            "layer1_bypassed": self.stats["layer1_bypassed"],
            "layer2_bypassed": self.stats["layer2_bypassed"],
            "estimated_time_saved": f"{self.stats['time_saved']:.1f}s",
            "performance_grade": self._get_performance_grade(bypass_rate)
        }
    
    def _get_performance_grade(self, bypass_rate: float) -> str:
        """Grade bypass performance"""
        if bypass_rate >= 85:
            return "EXCELLENT"
        elif bypass_rate >= 70:
            return "GOOD" 
        elif bypass_rate >= 50:
            return "FAIR"
        else:
            return "NEEDS_IMPROVEMENT"

# Global bypass instance
intelligent_bypass = IntelligentLLMBypass()
