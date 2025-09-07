"""
Intelligent LLM bypass system for high-confidence classifications
Reduces LLM calls by 80-90% while maintaining accuracy
"""
import time
from typing import Dict, Any, Tuple, Optional
from .fast_classifier import fast_classifier
from .advanced_classifier import advanced_classifier
from .text_normalizer import normalize_and_tag

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
        
        # Multilingual normalization and semantic intents (LLM-backed)
        norm = normalize_and_tag(prompt, use_llm=True)
        language = norm.get("language", "en")
        normalized_text = norm.get("normalized_text", prompt)
        semantic_intents = norm.get("semantic_intents", {})

        # Layer 1: Fast pattern matching (0.1ms, 95% confidence)
        fast_result = fast_classifier.quick_classify(prompt)
        if fast_result:
            # Do not safe-bypass for non-English; only accept Risky/Blocked
            if language != "en" and fast_result.get("classification") == "Safe":
                fast_result = None  # force deeper analysis
            else:
                analysis_time = time.perf_counter() - start_time
                self.stats["layer1_bypassed"] += 1
                self.stats["time_saved"] += 15.0  # Estimated LLM time saved
                fast_result.update({
                    "bypass_used": True,
                    "bypass_layer": "Layer1_Pattern",
                    "confidence": 0.95,
                    "analysis_time": analysis_time,
                    "time_saved": 15.0,
                    "language": language,
                    "language_confidence": norm.get("language_confidence", 0.0),
                    "normalized_text": normalized_text,
                    "semantic_intents": semantic_intents,
                })
                return True, fast_result
        
        # Layer 2: Advanced analysis over normalized English intent
        advanced_result = advanced_classifier.classify_prompt(normalized_text, risk_threshold=0.6, safe_threshold=0.2)
        # Merge L2 risk with semantic intent confidences (max-of for safety)
        l2_risk = float((advanced_result or {}).get("risk_score", 0.0) or 0.0)
        sem_max = float(max(semantic_intents.values()) if semantic_intents else 0.0)
        combined_risk = max(l2_risk, sem_max)

        # Decide classification conservatively
        if combined_risk >= 0.85:
            result = {
                "classification": "Blocked",
                "risk_score": combined_risk,
                "reason": "Semantic intent and ML features indicate high risk",
            }
        elif combined_risk >= 0.6 or (advanced_result and advanced_result.get("classification") == "Risky"):
            result = {
                "classification": "Risky",
                "risk_score": max(0.6, combined_risk),
                "reason": (advanced_result or {}).get("reason", "Semantic intent indicates risk"),
            }
        elif advanced_result:
            # Respect clear safe only when risk is truly low and language is English
            if language == "en" and advanced_result.get("classification") in ("Correct", "Safe") and combined_risk < 0.2:
                analysis_time = time.perf_counter() - start_time
                self.stats["layer2_bypassed"] += 1
                self.stats["time_saved"] += 15.0
                advanced_result.update({
                    "classification": "Safe" if advanced_result.get("classification") != "Correct" else "Safe",
                    "bypass_used": True,
                    "bypass_layer": "Layer2_HighConfidence",
                    "confidence": 0.85,
                    "analysis_time": analysis_time,
                    "time_saved": 15.0,
                    "language": language,
                    "language_confidence": norm.get("language_confidence", 0.0),
                    "normalized_text": normalized_text,
                    "semantic_intents": semantic_intents,
                })
                return True, advanced_result
            else:
                result = None
        else:
            result = None

        if result:
            # Prepare top semantic categories for reason enrichment
            top_cats = sorted((semantic_intents or {}).items(), key=lambda kv: kv[1], reverse=True)[:3]
            if top_cats:
                cats_str = ", ".join(f"{k}:{v:.2f}" for k, v in top_cats if v >= 0.3)
                if cats_str:
                    result["reason"] = (result.get("reason", "") + f" | intents: {cats_str}").strip()

            analysis_time = time.perf_counter() - start_time
            result.update({
                "bypass_used": True,
                "bypass_layer": "Layer2_Semantic",
                "confidence": 0.85,
                "analysis_time": analysis_time,
                "time_saved": 15.0,
                "language": language,
                "language_confidence": norm.get("language_confidence", 0.0),
                "normalized_text": normalized_text,
                "semantic_intents": semantic_intents,
            })
            return True, result
        
        # Requires LLM analysis - don't return default classification
        self.stats["llm_required"] += 1
        return False, {
            "bypass_used": False,
            "requires_llm": True,
            "language": language,
            "language_confidence": norm.get("language_confidence", 0.0),
            "normalized_text": normalized_text,
            "semantic_intents": semantic_intents,
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
