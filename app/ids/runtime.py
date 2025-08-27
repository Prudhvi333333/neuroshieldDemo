#!/usr/bin/env python3
"""
IDS Runtime: Intrusion Detection System for NeuroShield state transitions.

Provides anomaly detection for firewall pipeline state transitions using
a simple Markov-based model to identify unusual sequences.
"""

from typing import Dict, Optional, NamedTuple
from collections import defaultdict
import threading


class IDSResult(NamedTuple):
    """Result of IDS transition scoring."""
    anomalous: bool
    transition: Optional[str]
    prob: float


class IDSRuntime:
    """Thread-safe IDS runtime for scoring state transitions."""
    
    def __init__(self):
        """Initialize IDS with known good transitions."""
        self._lock = threading.Lock()
        
        # Known good transitions (simplified Markov model)
        # Format: {from_state: {to_state: probability}}
        self._transition_probs = {
            # Normal flow patterns
            "start": {"Stage0Guard": 0.9, "InitialAnalysis": 0.1},
            "Stage0Guard": {"FinalVerdict": 0.3, "SafePromptAgent": 0.2, "RiskScorer": 0.5},
            "SafePromptAgent": {"RiskScorer": 0.8, "ModelCall": 0.2},
            "RiskScorer": {"ModelCall": 0.7, "ResponseVerifier": 0.3},
            "ModelCall": {"ResponseVerifier": 0.9, "FinalVerdict": 0.1},
            "ResponseVerifier": {"RetrievalVerifier": 0.6, "CodeValidation": 0.3, "FinalVerdict": 0.1},
            "RetrievalVerifier": {"CodeValidation": 0.7, "FinalVerdict": 0.3},
            "CodeValidation": {"FinalVerdict": 0.9, "Audit": 0.1},
            "InitialAnalysis": {"SafePromptAgent": 0.4, "RiskScorer": 0.6},
            "FinalVerdict": {"Audit": 1.0},
            "Audit": {"end": 1.0},
            
            # Less common but valid transitions
            "Stage0Guard": {"InitialAnalysis": 0.05},  # Fallback to full analysis
            "ResponseVerifier": {"Audit": 0.05},       # Direct to audit on block
            "RetrievalVerifier": {"Audit": 0.05},      # Direct to audit on block
        }
        
        # Anomalous patterns to specifically flag
        self._anomalous_patterns = {
            # Direct jumps that bypass security checks
            ("RiskScorer", "FinalVerdict"): "Bypass→Verdict",
            ("ModelCall", "Audit"): "Model→Audit",
            ("SafePromptAgent", "FinalVerdict"): "Rewrite→Verdict",
            
            # Suspicious tool-related transitions
            ("ResponseVerifier", "ShellTool"): "Verify→Shell",
            ("CodeValidation", "ShellTool"): "Code→Shell", 
            ("RetrievalVerifier", "ShellTool"): "Retrieval→Shell",
            ("RiskScorer", "ShellTool"): "Risk→Shell",
            ("SafePromptAgent", "ShellTool"): "Rewrite→Shell",
            
            # Backwards flow (potential attack)
            ("FinalVerdict", "ModelCall"): "Verdict→Model",
            ("Audit", "ModelCall"): "Audit→Model",
            ("FinalVerdict", "ResponseVerifier"): "Verdict→Verify",
        }
        
        # Transition history for learning (limited size)
        self._history = []
        self._max_history = 1000
    
    def score_transition(self, prev_state: str, next_state: str) -> IDSResult:
        """
        Score a state transition for anomaly detection.
        
        Args:
            prev_state: Previous pipeline state
            next_state: Next pipeline state
            
        Returns:
            IDSResult with anomaly flag, transition name, and probability
        """
        with self._lock:
            # Handle start/end cases
            if prev_state is None or prev_state == "":
                prev_state = "start"
            if next_state is None or next_state == "":
                next_state = "end"
            
            transition_key = (prev_state, next_state)
            transition_name = f"{prev_state}→{next_state}"
            
            # Check for explicitly anomalous patterns
            if transition_key in self._anomalous_patterns:
                anomaly_name = self._anomalous_patterns[transition_key]
                self._record_transition(prev_state, next_state, anomalous=True)
                return IDSResult(
                    anomalous=True,
                    transition=anomaly_name,
                    prob=0.0
                )
            
            # Check known good transitions
            if prev_state in self._transition_probs:
                next_states = self._transition_probs[prev_state]
                if next_state in next_states:
                    prob = next_states[next_state]
                    self._record_transition(prev_state, next_state, anomalous=False)
                    return IDSResult(
                        anomalous=False,
                        transition=None,
                        prob=prob
                    )
            
            # Unknown transition - flag as anomalous with low probability
            self._record_transition(prev_state, next_state, anomalous=True)
            return IDSResult(
                anomalous=True,
                transition=f"Unknown→{transition_name}",
                prob=0.0
            )
    
    def _record_transition(self, prev_state: str, next_state: str, anomalous: bool):
        """Record transition in history for potential learning."""
        self._history.append({
            "from": prev_state,
            "to": next_state,
            "anomalous": anomalous,
            "count": 1
        })
        
        # Keep history bounded
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history//2:]
    
    def get_stats(self) -> Dict:
        """Get IDS statistics for monitoring."""
        with self._lock:
            total = len(self._history)
            anomalous = sum(1 for h in self._history if h["anomalous"])
            
            return {
                "total_transitions": total,
                "anomalous_count": anomalous,
                "anomaly_rate": anomalous / total if total > 0 else 0.0,
                "known_patterns": len(self._transition_probs),
                "anomalous_patterns": len(self._anomalous_patterns)
            }


# Global IDS instance
_ids_runtime = IDSRuntime()


def score_transition(prev_state: str, next_state: str) -> IDSResult:
    """
    Score a state transition for anomaly detection.
    
    Args:
        prev_state: Previous pipeline state  
        next_state: Next pipeline state
        
    Returns:
        IDSResult with anomaly flag, transition name, and probability
    """
    return _ids_runtime.score_transition(prev_state, next_state)


def get_ids_stats() -> Dict:
    """Get IDS runtime statistics."""
    return _ids_runtime.get_stats()
