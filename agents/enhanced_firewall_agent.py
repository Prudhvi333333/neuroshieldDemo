#!/usr/bin/env python3
"""
Enhanced Firewall Agent - Week 6 Implementation
Advanced multi-layered security with real-time threat response
"""

import asyncio
import time
import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from .minimal_base_agent import MinimalBaseAgent
from .shadow_ai_agent import ShadowAIDetectionAgent
from .behavioral_analytics_agent import BehavioralAnalyticsAgent
from .threat_intelligence_agent import ThreatIntelligenceAgent

class SecurityAction(Enum):
    ALLOW = "allow"
    MONITOR = "monitor"
    BLOCK = "block"
    QUARANTINE = "quarantine"

@dataclass
class EnhancedSecurityDecision:
    decision: SecurityAction
    confidence: float
    risk_score: float
    threat_categories: List[str]
    evidence: Dict[str, Any]
    recommended_actions: List[str]
    processing_time: float

class EnhancedFirewallAgent(MinimalBaseAgent):
    """Enhanced firewall with integrated Week 6 capabilities"""
    
    def __init__(self):
        super().__init__("EnhancedFirewallAgent")
        
        # Initialize specialized agents
        self.shadow_ai_agent = ShadowAIDetectionAgent()
        self.behavioral_agent = BehavioralAnalyticsAgent()
        self.threat_intel_agent = ThreatIntelligenceAgent()
        
        # Security thresholds - balanced for accurate detection
        self.security_thresholds = {
            "block_threshold": 0.7,
            "quarantine_threshold": 0.5,
            "monitor_threshold": 0.25  # Lower threshold for normal queries
        }
        
        logging.info("EnhancedFirewallAgent initialized with Week 6 capabilities")
    
    def run(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Required abstract method implementation - synchronous wrapper"""
        import asyncio
        try:
            # Run the async execute method
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.execute(prompt, context))
        except RuntimeError:
            # If no event loop exists, create one
            return asyncio.run(self.execute(prompt, context))
    
    async def comprehensive_analysis(self, prompt: str, context: Dict[str, Any] = None) -> EnhancedSecurityDecision:
        """Perform comprehensive multi-agent security analysis"""
        start_time = time.time()
        
        try:
            # Parallel execution of specialized analyses
            tasks = [
                self.shadow_ai_agent.execute(prompt, context),
                self.behavioral_agent.execute(prompt, context),
                self.threat_intel_agent.execute(prompt, context)
            ]
            
            # Execute analyses in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            shadow_ai_result = results[0] if not isinstance(results[0], Exception) else {}
            behavioral_result = results[1] if not isinstance(results[1], Exception) else {}
            threat_intel_result = results[2] if not isinstance(results[2], Exception) else {}
            
            # Aggregate risk scores with improved weighting
            risk_components = {}
            threat_categories = []
            evidence = {}
            
            # Shadow AI analysis
            if shadow_ai_result and "shadow_ai_event" in shadow_ai_result:
                shadow_event = shadow_ai_result["shadow_ai_event"]
                risk_components["shadow_ai"] = shadow_event.get("confidence", 0.0)
                threat_categories.append("shadow_ai")
                evidence["shadow_ai"] = shadow_event
            
            # Behavioral analysis
            if behavioral_result and "composite_anomaly_score" in behavioral_result:
                risk_components["behavioral"] = behavioral_result["composite_anomaly_score"]
                threat_categories.append("behavioral_anomaly")
                evidence["behavioral"] = behavioral_result
            
            # Threat intelligence
            if threat_intel_result and "threat_analysis" in threat_intel_result:
                threat_analysis = threat_intel_result["threat_analysis"]
                risk_components["threat_intel"] = threat_analysis.get("threat_score", 0.0)
                if threat_analysis.get("threat_category"):
                    threat_categories.append(threat_analysis["threat_category"])
                evidence["threat_intelligence"] = threat_analysis
            
            # Calculate weighted composite risk score
            composite_risk = self._calculate_weighted_risk(risk_components, threat_categories)
            confidence = min(sum(risk_components.values()) / len(risk_components), 1.0) if risk_components else 0.0
            
            # Determine security action
            security_action = self._determine_security_action(composite_risk, threat_categories)
            
            # Generate recommendations
            recommendations = self._generate_security_recommendations(
                security_action, threat_categories, composite_risk
            )
            
            return EnhancedSecurityDecision(
                decision=security_action,
                confidence=confidence,
                risk_score=composite_risk,
                threat_categories=threat_categories,
                evidence=evidence,
                recommended_actions=recommendations,
                processing_time=time.time() - start_time
            )
        except Exception as e:
            logging.error(f"Comprehensive analysis failed: {e}")
            return EnhancedSecurityDecision(
                decision=SecurityAction.MONITOR,
                confidence=0.0,
                risk_score=0.0,
                threat_categories=["analysis_error"],
                evidence={"error": str(e)},
                recommended_actions=["Investigate analysis system error"],
                processing_time=time.time() - start_time
            )
    
    def _calculate_weighted_risk(self, risk_components: Dict[str, float], threat_categories: List[str]) -> float:
        """Calculate weighted composite risk score with improved aggregation"""
        if not risk_components:
            return 0.0
        
        # Use maximum risk approach instead of weighted average for high-risk scenarios
        max_risk = max(risk_components.values())
        
        # Calculate weighted average for baseline
        weights = {
            "threat_intel": 0.5,  # Increased weight for threat intelligence
            "shadow_ai": 0.4,    # Increased weight for shadow AI detection
            "behavioral": 0.3    # Increased weight for behavioral anomalies
        }
        
        weighted_score = 0.0
        total_weight = 0.0
        
        for component, score in risk_components.items():
            weight = weights.get(component, 0.4)  # Increased default weight
            weighted_score += score * weight
            total_weight += weight
        
        # Normalize by total weight
        if total_weight > 0:
            weighted_score = weighted_score / total_weight
        
        # Use weighted average for normal cases, max for high-risk scenarios
        if max_risk > 0.5:  # High risk scenario - use max
            base_score = max(max_risk, weighted_score)
        else:  # Normal/low risk - use weighted average
            base_score = weighted_score
        
        # Apply aggressive threat category multipliers
        category_multiplier = 1.0
        if "prompt_injection" in threat_categories:
            category_multiplier = max(category_multiplier, 1.4)
        if "data_exfiltration" in threat_categories:
            category_multiplier = max(category_multiplier, 1.6)
        if "credential_theft" in threat_categories:
            category_multiplier = max(category_multiplier, 1.7)
        if "credential_patterns" in threat_categories:
            category_multiplier = max(category_multiplier, 1.7)
        
        # Apply multiplier and cap at 1.0
        final_score = min(base_score * category_multiplier, 1.0)
        return final_score
    
    def _determine_security_action(self, risk_score: float, threat_categories: List[str]) -> SecurityAction:
        """Determine appropriate security action based on risk assessment"""
        
        # Critical threats always blocked at lower threshold
        critical_categories = ["data_exfiltration", "credential_theft", "credential_patterns"]
        if any(cat in threat_categories for cat in critical_categories) and risk_score > 0.6:
            return SecurityAction.BLOCK
        
        # Apply thresholds
        if risk_score >= self.security_thresholds["block_threshold"]:
            return SecurityAction.BLOCK
        elif risk_score >= self.security_thresholds["quarantine_threshold"]:
            return SecurityAction.QUARANTINE
        elif risk_score >= self.security_thresholds["monitor_threshold"]:
            return SecurityAction.MONITOR
        else:
            return SecurityAction.ALLOW
    
    def _generate_security_recommendations(self, action: SecurityAction, categories: List[str], risk_score: float) -> List[str]:
        """Generate security recommendations based on analysis"""
        recommendations = []
        
        # Action-specific recommendations
        if action == SecurityAction.BLOCK:
            recommendations.extend([
                "Request blocked due to high security risk",
                "Investigate user activity and intent",
                "Review security policies and controls",
                "Consider additional user training"
            ])
        elif action == SecurityAction.QUARANTINE:
            recommendations.extend([
                "Request quarantined for security review",
                "Manual approval required before processing",
                "Enhanced monitoring activated"
            ])
        elif action == SecurityAction.MONITOR:
            recommendations.extend([
                "Request allowed with enhanced monitoring",
                "Log all interactions for audit purposes",
                "Review activity patterns regularly"
            ])
        
        # Category-specific recommendations
        if "shadow_ai" in categories:
            recommendations.append("Enforce approved AI service usage policies")
        if "behavioral_anomaly" in categories:
            recommendations.append("Conduct behavioral analysis review")
        
        return recommendations
    
    def _determine_security_action(self, risk_score: float, threat_categories: List[str]) -> SecurityAction:
        """Determine appropriate security action based on risk assessment"""
        
        # Critical threats always blocked at lower threshold
        critical_categories = ["data_exfiltration", "credential_theft", "credential_patterns"]
        if any(cat in threat_categories for cat in critical_categories) and risk_score > 0.6:
            return SecurityAction.BLOCK
        
        # Apply thresholds
        if risk_score >= self.security_thresholds["block_threshold"]:
            return SecurityAction.BLOCK
        elif risk_score >= self.security_thresholds["quarantine_threshold"]:
            return SecurityAction.QUARANTINE
        elif risk_score >= self.security_thresholds["monitor_threshold"]:
            return SecurityAction.MONITOR
        else:
            return SecurityAction.ALLOW

    async def execute(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute enhanced firewall analysis with Week 6 capabilities"""
        start_time = time.time()
        
        try:
            # Run comprehensive security analysis
            security_decision = await self.comprehensive_analysis(prompt, context)
            
            # Format result for orchestrator compatibility
            result = {
                "status": "completed",
                "decision": security_decision.decision.value,
                "risk_score": security_decision.risk_score,
                "confidence": security_decision.confidence,
                "threat_categories": security_decision.threat_categories,
                "evidence": security_decision.evidence,
                "recommendations": security_decision.recommended_actions,
                "processing_time": security_decision.processing_time,
                "agent": self.name
            }
            
            logging.info(f"Enhanced firewall analysis completed: {security_decision.decision.value}")
            return result
                
        except Exception as e:
            logging.error(f"Enhanced firewall execution failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "agent": self.name,
                "processing_time": time.time() - start_time
            }

    async def analyze_request(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Alias for comprehensive_analysis for backward compatibility"""
        security_decision = await self.comprehensive_analysis(prompt, context)
        return {
            "decision": security_decision.decision.value,
            "risk_score": security_decision.risk_score,
            "confidence": security_decision.confidence,
            "threat_categories": security_decision.threat_categories,
            "evidence": security_decision.evidence,
            "recommendations": security_decision.recommended_actions,
            "processing_time": security_decision.processing_time
        }
