#!/usr/bin/env python3
"""
Threat Intelligence Agent - Week 6 Implementation
Advanced threat intelligence integration and analysis
"""

import asyncio
import time
import json
import logging
import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from .minimal_base_agent import MinimalBaseAgent

class ThreatSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ThreatCategory(Enum):
    PROMPT_INJECTION = "prompt_injection"
    DATA_EXFILTRATION = "data_exfiltration"
    MODEL_ABUSE = "model_abuse"
    CREDENTIAL_THEFT = "credential_theft"
    JAILBREAK_ATTEMPT = "jailbreak_attempt"
    SHADOW_AI = "shadow_ai"

@dataclass
class ThreatIntelligence:
    threat_id: str
    category: ThreatCategory
    severity: ThreatSeverity
    confidence: float
    indicators: List[str]
    attack_vectors: List[str]
    mitigation_strategies: List[str]
    source: str
    timestamp: datetime
    ttl: int  # Time to live in hours

class ThreatIntelligenceAgent(MinimalBaseAgent):
    """Advanced threat intelligence integration and correlation"""
    
    def __init__(self):
        super().__init__("ThreatIntelligenceAgent")
        self.threat_database = {}
        self.ioc_patterns = self._initialize_ioc_patterns()
        self.threat_feeds = self._initialize_threat_feeds()
        logging.info("ThreatIntelligenceAgent initialized with threat intelligence feeds")
    
    def run(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Required abstract method implementation - synchronous wrapper"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.execute(prompt, context))
        except RuntimeError:
            return asyncio.run(self.execute(prompt, context))
    
    def _initialize_ioc_patterns(self) -> Dict[str, List[str]]:
        """Initialize Indicators of Compromise patterns"""
        return {
            "prompt_injection": [
                r"ignore\s+(previous|all)\s+instructions",
                r"system\s+prompt",
                r"developer\s+mode",
                r"jailbreak",
                r"dan\s+mode"
            ],
            "data_exfiltration": [
                r"export\s+all\s+data",
                r"download\s+database",
                r"backup\s+files",
                r"sensitive\s+information"
            ],
            "credential_patterns": [
                r"sk-[a-zA-Z0-9-_]{15,}",  # OpenAI API keys (fixed length)
                r"api[_-]?key[:\s]*[a-zA-Z0-9-_]{8,}",
                r"secret[_-]?key[:\s]*[a-zA-Z0-9-_]{8,}",
                r"password[:\s]*[a-zA-Z0-9-_]{6,}",
                r"token[:\s]*[a-zA-Z0-9-_]{8,}",
                r"bearer\s+[a-zA-Z0-9-_]{8,}",
                r"[a-zA-Z0-9-_]{25,}",  # Generic long strings (potential keys)
                r"[0-9a-f]{32,}"  # Hex keys
            ]
        }
    
    def _initialize_threat_feeds(self) -> Dict[str, Dict]:
        """Initialize threat intelligence feeds (simulated for POC)"""
        return {
            "internal_feed": {
                "name": "NeuroShield Internal Intelligence",
                "priority": "high",
                "update_frequency": 3600,  # 1 hour
                "last_update": time.time()
            },
            "mitre_attack": {
                "name": "MITRE ATT&CK Framework",
                "priority": "medium",
                "update_frequency": 86400,  # 24 hours
                "last_update": time.time()
            },
            "cti_feed": {
                "name": "Cyber Threat Intelligence Feed",
                "priority": "medium",
                "update_frequency": 21600,  # 6 hours
                "last_update": time.time()
            }
        }
    
    async def analyze_threat_indicators(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze prompt for threat indicators using intelligence feeds"""
        start_time = time.time()
        
        try:
            # Extract threat indicators
            indicators = self._extract_indicators(prompt)
            
            # Correlate with threat intelligence
            threat_matches = await self._correlate_with_intelligence(indicators, prompt)
            
            # Calculate threat score
            threat_score = self._calculate_threat_score(threat_matches, indicators)
            
            # Determine threat category and severity
            threat_category = self._classify_threat_category(indicators, threat_matches)
            threat_severity = self._determine_severity(threat_score, threat_category)
            
            # Generate mitigation recommendations
            mitigations = self._generate_mitigations(threat_category, threat_severity)
            
            return {
                "agent": self.name,
                "threat_analysis": {
                    "threat_score": threat_score,
                    "threat_category": threat_category.value if threat_category else "unknown",
                    "threat_severity": threat_severity.value,
                    "indicators_found": indicators,
                    "threat_matches": threat_matches,
                    "mitigation_strategies": mitigations
                },
                "processing_time": time.time() - start_time,
                "timestamp": datetime.now().isoformat(),
                "status": "completed"
            }
            
        except Exception as e:
            logging.error(f"Threat intelligence analysis failed: {e}")
            return {
                "agent": self.name,
                "error": str(e),
                "processing_time": time.time() - start_time,
                "status": "error"
            }
    
    def _extract_indicators(self, prompt: str) -> List[str]:
        """Extract threat indicators from prompt"""
        indicators = []
        prompt_lower = prompt.lower()
        
        # Check against IOC patterns
        for category, patterns in self.ioc_patterns.items():
            for pattern in patterns:
                import re
                if re.search(pattern, prompt_lower, re.IGNORECASE):
                    indicators.append(f"{category}:{pattern}")
        
        return indicators
    
    async def _correlate_with_intelligence(self, indicators: List[str], prompt: str) -> List[Dict[str, Any]]:
        """Correlate indicators with threat intelligence feeds"""
        matches = []
        
        # Simulate threat intelligence correlation
        for indicator in indicators:
            category = indicator.split(':')[0]
            
            # Generate simulated threat intelligence match
            threat_hash = hashlib.md5(f"{indicator}{prompt}".encode()).hexdigest()[:8]
            confidence = (int(threat_hash, 16) % 100) / 100.0
            
            if confidence > 0.5:  # Only include high-confidence matches
                matches.append({
                    "indicator": indicator,
                    "threat_id": f"TI-{threat_hash}",
                    "confidence": confidence,
                    "source": "internal_feed",
                    "description": f"Known {category} pattern detected",
                    "first_seen": datetime.now() - timedelta(days=int(confidence * 30)),
                    "last_seen": datetime.now()
                })
        
        return matches
    
    def _calculate_threat_score(self, threat_matches: List[Dict], indicators: List[str]) -> float:
        """Calculate overall threat score with improved weighting"""
        if not threat_matches and not indicators:
            return 0.0
        
        # Improved base score from indicators with category-specific weighting
        base_score = 0.0
        for indicator in indicators:
            category = indicator.split(':')[0]
            if category == "prompt_injection":
                base_score += 0.6  # High weight for prompt injection
            elif category == "data_exfiltration":
                base_score += 0.7  # Very high weight for data exfiltration
            elif category == "credential_patterns":
                base_score += 0.9  # Critical weight for credentials
            else:
                base_score += 0.3  # Default weight
        
        # Cap base score
        base_score = min(base_score, 0.9)
        
        # Boost from threat intelligence matches
        intelligence_boost = 0.0
        for match in threat_matches:
            confidence = match.get("confidence", 0.0)
            intelligence_boost += confidence * 0.4  # Increased from 0.3
        
        # Combine scores
        total_score = min(base_score + intelligence_boost, 1.0)
        return total_score
    
    def _classify_threat_category(self, indicators: List[str], threat_matches: List[Dict]) -> Optional[ThreatCategory]:
        """Classify the primary threat category"""
        category_counts = {}
        
        # Count indicators by category
        for indicator in indicators:
            category = indicator.split(':')[0]
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Add threat intelligence categories
        for match in threat_matches:
            indicator = match.get("indicator", "")
            if ":" in indicator:
                category = indicator.split(':')[0]
                category_counts[category] = category_counts.get(category, 0) + 2  # Weight TI matches higher
        
        if not category_counts:
            return None
        
        # Map to ThreatCategory enum
        category_mapping = {
            "prompt_injection": ThreatCategory.PROMPT_INJECTION,
            "data_exfiltration": ThreatCategory.DATA_EXFILTRATION,
            "credential_patterns": ThreatCategory.CREDENTIAL_THEFT
        }
        
        # Get most common category
        primary_category = max(category_counts, key=category_counts.get)
        return category_mapping.get(primary_category, ThreatCategory.PROMPT_INJECTION)
    
    def _determine_severity(self, threat_score: float, threat_category: Optional[ThreatCategory]) -> ThreatSeverity:
        """Determine threat severity based on score and category"""
        # Base severity from score
        if threat_score >= 0.8:
            base_severity = ThreatSeverity.CRITICAL
        elif threat_score >= 0.6:
            base_severity = ThreatSeverity.HIGH
        elif threat_score >= 0.4:
            base_severity = ThreatSeverity.MEDIUM
        else:
            base_severity = ThreatSeverity.LOW
        
        # Adjust based on category
        if threat_category in [ThreatCategory.DATA_EXFILTRATION, ThreatCategory.CREDENTIAL_THEFT]:
            # Escalate data-related threats
            severity_levels = [ThreatSeverity.LOW, ThreatSeverity.MEDIUM, ThreatSeverity.HIGH, ThreatSeverity.CRITICAL]
            current_index = severity_levels.index(base_severity)
            if current_index < len(severity_levels) - 1:
                return severity_levels[current_index + 1]
        
        return base_severity
    
    def _generate_mitigations(self, threat_category: Optional[ThreatCategory], severity: ThreatSeverity) -> List[str]:
        """Generate mitigation strategies based on threat analysis"""
        mitigations = []
        
        # Category-specific mitigations
        if threat_category == ThreatCategory.PROMPT_INJECTION:
            mitigations.extend([
                "Implement input sanitization and validation",
                "Deploy prompt injection detection filters",
                "Use structured prompts with clear boundaries",
                "Monitor for system prompt leakage attempts"
            ])
        elif threat_category == ThreatCategory.DATA_EXFILTRATION:
            mitigations.extend([
                "Implement data loss prevention (DLP) controls",
                "Monitor for unusual data access patterns",
                "Enforce data classification and handling policies",
                "Restrict bulk data operations"
            ])
        elif threat_category == ThreatCategory.CREDENTIAL_THEFT:
            mitigations.extend([
                "Implement credential scanning and detection",
                "Enforce API key rotation policies",
                "Use secure credential storage (e.g., HashiCorp Vault)",
                "Monitor for credential exposure in prompts"
            ])
        
        # Severity-based mitigations
        if severity in [ThreatSeverity.HIGH, ThreatSeverity.CRITICAL]:
            mitigations.extend([
                "Immediately block suspicious requests",
                "Escalate to security operations center (SOC)",
                "Implement emergency response procedures",
                "Conduct forensic analysis of the incident"
            ])
        elif severity == ThreatSeverity.MEDIUM:
            mitigations.extend([
                "Increase monitoring for this user/session",
                "Apply additional security controls",
                "Review and update security policies"
            ])
        
        return mitigations
    
    async def update_threat_intelligence(self, feed_name: str = None) -> Dict[str, Any]:
        """Update threat intelligence feeds"""
        start_time = time.time()
        
        try:
            updated_feeds = []
            
            feeds_to_update = [feed_name] if feed_name else list(self.threat_feeds.keys())
            
            for feed in feeds_to_update:
                if feed in self.threat_feeds:
                    # Simulate feed update
                    self.threat_feeds[feed]["last_update"] = time.time()
                    updated_feeds.append(feed)
                    
                    # In production, this would fetch real threat intelligence
                    logging.info(f"Updated threat intelligence feed: {feed}")
            
            return {
                "agent": self.name,
                "operation": "threat_intelligence_update",
                "updated_feeds": updated_feeds,
                "processing_time": time.time() - start_time,
                "timestamp": datetime.now().isoformat(),
                "status": "completed"
            }
            
        except Exception as e:
            logging.error(f"Threat intelligence update failed: {e}")
            return {
                "agent": self.name,
                "operation": "threat_intelligence_update",
                "error": str(e),
                "processing_time": time.time() - start_time,
                "status": "error"
            }
    
    async def execute(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute threat intelligence analysis"""
        return await self.analyze_threat_indicators(prompt, context)
