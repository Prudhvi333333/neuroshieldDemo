#!/usr/bin/env python3
"""
Stage-0 Guard: Fast deterministic gateway checks with fast-path optimization.

This module implements the first line of defense in NeuroShield's security pipeline,
providing ultra-fast deterministic checks before any LLM processing.

Pipeline: sanitize → t0_rules → afc_check → t1_rules (placeholder)
"""

import re
import time
from typing import Dict, List, Optional, Any
from pathlib import Path

# Import existing components
from policy.loader import load_policy
from sanitizer.sanitize import sanitize_report
from gateway.checks_t0 import run_t0
from gateway.afc import afc_decide

# Import metrics collector
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from app.metrics.collector import time_block, record_metric, record_path_taken


class Stage0Guard:
    """Fast deterministic security guard for Stage-0 processing."""
    
    def __init__(self):
        """Initialize Stage-0 Guard with pre-compiled patterns and configuration."""
        self.policy = load_policy()
        self.limits = self.policy.get('limits', {})
        self.thresholds = self.policy.get('thresholds', {})
        self.flags = self.policy.get('flags', {})
        self.rules = self.policy.get('rules', {})
        
        # Pre-compile regex patterns for performance
        self._compile_patterns()
        
        # Configuration
        self.fastpath_max_len = self.limits.get('fastpath_max_len', 300)
        self.fastpath_threshold = self.thresholds.get('fastpath', 0.1)
        self.t0_block_threshold = self.thresholds.get('t0_block', 0.8)
        self.stage0_rewrite_threshold = self.thresholds.get('stage0_rewrite', 0.5)
        self.fastpath_enabled = self.flags.get('fastpath_enabled', True)
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for optimal performance."""
        self.block_patterns = []
        self.risk_patterns = []
        self.dlp_patterns = []
        
        # Compile block patterns
        for pattern in self.rules.get('block_regex', []):
            try:
                self.block_patterns.append(re.compile(pattern))
            except re.error as e:
                print(f"Warning: Invalid block regex pattern '{pattern}': {e}")
        
        # Compile risk patterns
        for pattern in self.rules.get('risk_regex', []):
            try:
                self.risk_patterns.append(re.compile(pattern))
            except re.error as e:
                print(f"Warning: Invalid risk regex pattern '{pattern}': {e}")
        
        # Compile DLP patterns
        for pattern in self.rules.get('dlp_regex', []):
            try:
                self.dlp_patterns.append(re.compile(pattern))
            except re.error as e:
                print(f"Warning: Invalid DLP regex pattern '{pattern}': {e}")
    
    def _sanitize_stage(self, prompt: str) -> tuple[str, float, List[str]]:
        """
        Sanitization stage - clean and validate input.
        
        Returns:
            tuple: (sanitized_prompt, risk_score, reasons)
        """
        with time_block("stage0.sanitize"):
            try:
                result = sanitize_report(prompt)
                sanitized = result.get('sanitized_text', prompt)
                blocked = result.get('blocked', False)
                reasons = [f"sanitize.{reason}" for reason in result.get('reasons', [])]
                risk = 0.8 if blocked else 0.0
                return sanitized, risk, reasons
            except Exception as e:
                # Fallback sanitization
                sanitized = prompt.strip()[:self.limits.get('max_prompt_len', 4000)]
                return sanitized, 0.1, [f"sanitize.fallback: {str(e)}"]
    
    def _t0_rules_stage(self, prompt: str) -> tuple[float, List[str], bool]:
        """
        T0 rules stage - fast regex-based security checks.
        
        Returns:
            tuple: (risk_score, reasons, should_block)
        """
        with time_block("stage0.t0"):
            risk_score = 0.0
            reasons = []
            should_block = False
            
            # Check block patterns (immediate block)
            for pattern in self.block_patterns:
                if pattern.search(prompt):
                    should_block = True
                    risk_score = 1.0
                    reasons.append(f"t0.block_rule: {pattern.pattern[:50]}...")
                    break  # First match is enough for blocking
            
            if should_block:
                return risk_score, reasons, should_block
            
            # Check risk patterns (risk boosters)
            risk_matches = 0
            for pattern in self.risk_patterns:
                if pattern.search(prompt):
                    risk_matches += 1
                    reasons.append(f"t0.risk_rule: {pattern.pattern[:30]}...")
            
            # Check DLP patterns (data loss prevention)
            dlp_matches = 0
            for pattern in self.dlp_patterns:
                if pattern.search(prompt):
                    dlp_matches += 1
                    reasons.append(f"t0.dlp_rule: {pattern.pattern[:30]}...")
            
            # Calculate risk score based on matches
            if risk_matches > 0:
                risk_score += min(0.3, risk_matches * 0.1)
            if dlp_matches > 0:
                risk_score += min(0.4, dlp_matches * 0.15)
            
            # Check if risk exceeds T0 block threshold
            if risk_score >= self.t0_block_threshold:
                should_block = True
            
            return risk_score, reasons, should_block
    
    def _afc_check_stage(self, tools: Optional[List], tenant_id: str) -> tuple[float, List[str], List[Dict], bool]:
        """
        AFC (Adaptive Flow Control) check stage.
        
        Returns:
            tuple: (risk_score, reasons, afc_results, should_block)
        """
        if not tools:
            return 0.0, [], [], False
        
        with time_block("stage0.afc"):
            try:
                afc_results = []
                total_risk = 0.0
                reasons = []
                should_block = False
                
                for tool in tools:
                    tool_name = tool.get('name', 'unknown') if isinstance(tool, dict) else str(tool)
                    tool_args = tool.get('args', {}) if isinstance(tool, dict) else {}
                    
                    # Use new AFC decision function
                    afc_decision = afc_decide(tenant_id, tool_name, tool_args)
                    
                    afc_results.append(afc_decision)
                    
                    # Calculate risk based on AFC violations
                    if not afc_decision["schema_ok"]:
                        total_risk += 0.3
                        reasons.append(f"afc.schema_violation: {tool_name}")
                    
                    if not afc_decision["domain_ok"]:
                        total_risk += 0.5
                        reasons.append(f"afc.domain_block: {tool_name}")
                        should_block = True  # Domain violations are blocking
                    
                    if not afc_decision["cooldown_ok"]:
                        total_risk += 0.2
                        reasons.append(f"afc.cooldown_violation: {tool_name}")
                    
                    # Add specific reasons from AFC decision
                    for reason in afc_decision.get("reasons", []):
                        if "tool_not_allowed" in reason:
                            total_risk += 0.8
                            reasons.append(f"afc.tool_blocked: {tool_name}")
                            should_block = True
                
                return total_risk, reasons, afc_results, should_block
                
            except Exception as e:
                return 0.1, [f"afc.error: {str(e)}"], [], False
    
    def _t1_placeholder_stage(self, prompt: str) -> tuple[float, List[str]]:
        """
        T1 rules placeholder stage - reserved for future ML-based classification.
        
        Returns:
            tuple: (risk_score, reasons)
        """
        with time_block("stage0.t1"):
            # Placeholder for T1 classification
            # This would integrate with ML models for advanced threat detection
            return 0.0, ["t1.placeholder: not_implemented"]


def run_stage0_guard(prompt: str, tools: Optional[List] = None, tenant_id: str = "default") -> Dict[str, Any]:
    """
    Run Stage-0 Guard with fast deterministic checks and fast-path optimization.
    
    Args:
        prompt: Input prompt to analyze
        tools: Optional list of tools to check
        tenant_id: Tenant identifier for AFC checks
    
    Returns:
        Dict containing decision, risk, reasons, and metadata
    """
    with time_block("stage0.total"):
        guard = Stage0Guard()
        
        # Stage 1: Sanitization
        sanitized_prompt, sanitize_risk, sanitize_reasons = guard._sanitize_stage(prompt)
        
        # Stage 2: T0 Rules (fast regex checks)
        t0_risk, t0_reasons, t0_block = guard._t0_rules_stage(sanitized_prompt)
        
        # Early exit for blocked prompts to prevent timeout
        if t0_block:
            record_path_taken("stage0_block_early")
            return {
                "decision": "BLOCK",
                "risk": max(sanitize_risk, t0_risk),
                "reasons": sanitize_reasons + t0_reasons,
                "sanitized_prompt": sanitized_prompt,
                "prompt_out": sanitized_prompt,
                "afc": {"blocked": False, "risk": 0.0, "reasons": []},
                "path_taken": "stage0_block_early",
                "stage0_decision": "BLOCK",
                "stage0_risk": max(sanitize_risk, t0_risk),
                "stage0_reasons": sanitize_reasons + t0_reasons,
                "metadata": {
                    "sanitize_risk": sanitize_risk,
                    "t0_risk": t0_risk,
                    "afc_risk": 0.0,
                    "t1_risk": 0.0,
                    "t0_block": t0_block,
                    "afc_block": False
                }
            }
        
        # Stage 3: AFC Checks (if tools provided)
        afc_risk, afc_reasons, afc_results, afc_block = guard._afc_check_stage(tools, tenant_id)
        
        # Stage 4: T1 Rules (placeholder for ML)
        t1_risk, t1_reasons = guard._t1_placeholder_stage(sanitized_prompt)
        
        # Aggregate results
        total_risk = min(1.0, sanitize_risk + t0_risk + afc_risk + t1_risk)
        all_reasons = sanitize_reasons + t0_reasons + afc_reasons + t1_reasons
        should_block = t0_block or afc_block
        
        # Determine decision
        if should_block:
            decision = "BLOCK"
            path_taken = "stage0_block"
        elif total_risk >= guard.stage0_rewrite_threshold:
            decision = "REWRITE"
            path_taken = "stage0_rewrite"
        else:
            decision = "ALLOW"
            path_taken = "stage0_allow"
        
        # Record path taken for metrics
        record_path_taken(path_taken)
        
        return {
            "decision": decision,
            "risk": total_risk,
            "reasons": all_reasons,
            "sanitized_prompt": sanitized_prompt,
            "prompt_out": sanitized_prompt,  # Add expected key for gateway
            "afc": afc_results,
            "path_taken": path_taken,
            "stage0_decision": decision,
            "stage0_risk": total_risk,
            "stage0_reasons": all_reasons,
            "metadata": {
                "sanitize_risk": sanitize_risk,
                "t0_risk": t0_risk,
                "afc_risk": afc_risk,
                "t1_risk": t1_risk,
                "t0_block": t0_block,
                "afc_block": afc_block
            }
        }


# Convenience function for backward compatibility
def stage0_check(prompt: str, tools: Optional[List] = None, tenant_id: str = "default") -> Dict[str, Any]:
    """Alias for run_stage0_guard for backward compatibility."""
    return run_stage0_guard(prompt, tools, tenant_id)
