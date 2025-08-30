#!/usr/bin/env python3
"""
Shadow AI Detection Agent - Week 6 Implementation
Detects unauthorized AI usage across enterprise networks and applications
"""

import asyncio
import time
import json
import logging
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta
import re
import numpy as np
from .minimal_base_agent import MinimalBaseAgent

class ShadowAIRiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AIServiceType(Enum):
    CHATGPT = "chatgpt"
    CLAUDE = "claude"
    GEMINI = "gemini"
    COPILOT = "copilot"
    CUSTOM_LLM = "custom_llm"
    UNKNOWN = "unknown"

@dataclass
class ShadowAIEvent:
    event_id: str
    timestamp: str  # Changed to string for JSON serialization
    user_id: str
    service_type: AIServiceType
    risk_level: ShadowAIRiskLevel
    confidence: float
    detection_method: str
    evidence: Dict[str, Any]
    network_indicators: Dict[str, Any]
    behavioral_patterns: Dict[str, Any]
    compliance_violations: List[str]
    recommended_actions: List[str]

class ShadowAIDetectionAgent(MinimalBaseAgent):
    """
    Advanced Shadow AI Detection Agent
    
    Capabilities:
    - Network traffic analysis for AI service detection
    - Behavioral pattern analysis for unauthorized AI usage
    - Compliance violation detection
    - Real-time alerting and response
    """
    
    def __init__(self):
        super().__init__("ShadowAIDetectionAgent")
        self.detection_patterns = self._initialize_detection_patterns()
        self.behavioral_baselines = {}
        self.compliance_rules = self._load_compliance_rules()
        self.ai_service_signatures = self._initialize_ai_signatures()
        
        # Detection thresholds
        self.risk_thresholds = {
            "network_anomaly": 0.7,
            "behavioral_deviation": 0.6,
            "compliance_violation": 0.9,
            "data_exfiltration": 0.8
        }
        
        logging.info("ShadowAIDetectionAgent initialized with enterprise monitoring capabilities")
    
    def run(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Required abstract method implementation - synchronous wrapper"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.execute(prompt, context))
        except RuntimeError:
            return asyncio.run(self.execute(prompt, context))
    
    def _initialize_detection_patterns(self) -> Dict[str, List[str]]:
        """Initialize patterns for detecting AI service usage"""
        return {
            "api_endpoints": [
                r"api\.openai\.com",
                r"claude\.ai",
                r"gemini\.google\.com",
                r"copilot\.microsoft\.com",
                r"huggingface\.co/api",
                r"replicate\.com/api",
                r"cohere\.ai/api"
            ],
            "request_patterns": [
                r"chat/completions",
                r"v1/completions",
                r"generate",
                r"inference",
                r"predict"
            ],
            "payload_indicators": [
                r'"model":\s*"gpt-',
                r'"model":\s*"claude-',
                r'"model":\s*"gemini-',
                r'"messages":\s*\[',
                r'"prompt":\s*"',
                r'"temperature":\s*\d+\.?\d*',
                r'"max_tokens":\s*\d+'
            ],
            "browser_patterns": [
                r"chat\.openai\.com",
                r"claude\.ai/chat",
                r"gemini\.google\.com/app",
                r"copilot\.microsoft\.com",
                r"poe\.com",
                r"character\.ai"
            ]
        }
    
    def _initialize_ai_signatures(self) -> Dict[AIServiceType, Dict[str, Any]]:
        """Initialize AI service detection signatures"""
        return {
            AIServiceType.CHATGPT: {
                "domains": ["api.openai.com", "chat.openai.com"],
                "headers": ["OpenAI-Organization", "Authorization: Bearer sk-"],
                "response_patterns": ["choices", "usage", "model"],
                "typical_ports": [443, 80]
            },
            AIServiceType.CLAUDE: {
                "domains": ["claude.ai", "api.anthropic.com"],
                "headers": ["x-api-key", "anthropic-version"],
                "response_patterns": ["completion", "stop_reason"],
                "typical_ports": [443]
            },
            AIServiceType.GEMINI: {
                "domains": ["gemini.google.com", "generativelanguage.googleapis.com"],
                "headers": ["x-goog-api-key", "Authorization: Bearer"],
                "response_patterns": ["candidates", "safetyRatings"],
                "typical_ports": [443]
            },
            AIServiceType.COPILOT: {
                "domains": ["copilot.microsoft.com", "api.github.com"],
                "headers": ["Authorization: token", "X-GitHub-Api-Version"],
                "response_patterns": ["completions", "suggestions"],
                "typical_ports": [443]
            }
        }
    
    def _load_compliance_rules(self) -> Dict[str, Any]:
        """Load compliance rules for different regulations"""
        return {
            "gdpr": {
                "data_types": ["personal_data", "sensitive_data"],
                "restrictions": ["no_external_processing", "consent_required"],
                "violations": ["unauthorized_transfer", "lack_of_consent"]
            },
            "hipaa": {
                "data_types": ["phi", "medical_records"],
                "restrictions": ["encryption_required", "audit_trail"],
                "violations": ["unencrypted_transmission", "unauthorized_access"]
            },
            "sox": {
                "data_types": ["financial_data", "audit_records"],
                "restrictions": ["immutable_logs", "segregation_of_duties"],
                "violations": ["data_tampering", "unauthorized_modification"]
            },
            "pci_dss": {
                "data_types": ["payment_card_data", "cardholder_data"],
                "restrictions": ["tokenization", "encryption"],
                "violations": ["plaintext_storage", "unauthorized_transmission"]
            }
        }
    
    async def analyze_network_traffic(self, traffic_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze network traffic for AI service usage patterns"""
        start_time = time.time()
        
        try:
            detections = []
            risk_indicators = []
            
            # Extract traffic metadata
            source_ip = traffic_data.get("source_ip", "")
            destination_ip = traffic_data.get("destination_ip", "")
            domain = traffic_data.get("domain", "")
            headers = traffic_data.get("headers", {})
            payload = traffic_data.get("payload", "")
            
            # Check against AI service signatures
            detected_service = self._identify_ai_service(domain, headers, payload)
            if detected_service != AIServiceType.UNKNOWN:
                detections.append({
                    "type": "ai_service_detected",
                    "service": detected_service.value,
                    "confidence": 0.9,
                    "evidence": {"domain": domain, "service_type": detected_service.value}
                })
            
            # Analyze payload for sensitive data
            sensitive_data = self._detect_sensitive_data(payload)
            if sensitive_data:
                risk_indicators.append({
                    "type": "sensitive_data_transmission",
                    "data_types": sensitive_data,
                    "risk_level": "high"
                })
            
            # Check for unusual traffic patterns
            traffic_anomalies = self._detect_traffic_anomalies(traffic_data)
            if traffic_anomalies:
                risk_indicators.extend(traffic_anomalies)
            
            # Calculate overall risk score
            risk_score = self._calculate_network_risk_score(detections, risk_indicators)
            
            return {
                "analysis_type": "network_traffic",
                "detections": detections,
                "risk_indicators": risk_indicators,
                "risk_score": risk_score,
                "processing_time": time.time() - start_time,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Network traffic analysis failed: {e}")
            return {
                "analysis_type": "network_traffic",
                "error": str(e),
                "risk_score": 0.0,
                "processing_time": time.time() - start_time
            }
    
    def _identify_ai_service(self, domain: str, headers: Dict[str, str], payload: str) -> AIServiceType:
        """Identify AI service based on network signatures"""
        for service_type, signatures in self.ai_service_signatures.items():
            # Check domain matches
            for service_domain in signatures["domains"]:
                if service_domain in domain.lower():
                    return service_type
            
            # Check header patterns
            for header_pattern in signatures["headers"]:
                for header_name, header_value in headers.items():
                    if header_pattern.lower() in f"{header_name}: {header_value}".lower():
                        return service_type
            
            # Check response patterns in payload
            for pattern in signatures["response_patterns"]:
                if pattern in payload.lower():
                    return service_type
        
        return AIServiceType.UNKNOWN
    
    def _detect_sensitive_data(self, payload: str) -> List[str]:
        """Detect sensitive data types in network payload"""
        sensitive_types = []
        
        # PII patterns
        pii_patterns = {
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
            "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
            "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"
        }
        
        for data_type, pattern in pii_patterns.items():
            if re.search(pattern, payload, re.IGNORECASE):
                sensitive_types.append(data_type)
        
        # Financial data patterns
        financial_patterns = {
            "account_number": r"\b\d{8,17}\b",
            "routing_number": r"\b\d{9}\b",
            "iban": r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b"
        }
        
        for data_type, pattern in financial_patterns.items():
            if re.search(pattern, payload, re.IGNORECASE):
                sensitive_types.append(data_type)
        
        return sensitive_types
    
    def _detect_traffic_anomalies(self, traffic_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect anomalous traffic patterns"""
        anomalies = []
        
        # Check for unusual data volumes
        payload_size = len(traffic_data.get("payload", ""))
        if payload_size > 100000:  # >100KB payload
            anomalies.append({
                "type": "large_payload",
                "size": payload_size,
                "risk_level": "medium",
                "description": "Unusually large payload detected"
            })
        
        # Check for encrypted/encoded content
        payload = traffic_data.get("payload", "")
        if self._is_likely_encoded(payload):
            anomalies.append({
                "type": "encoded_content",
                "risk_level": "medium",
                "description": "Potentially encoded content detected"
            })
        
        # Check for high frequency requests
        timestamp = traffic_data.get("timestamp", time.time())
        user_id = traffic_data.get("user_id", "unknown")
        if self._is_high_frequency_user(user_id, timestamp):
            anomalies.append({
                "type": "high_frequency_requests",
                "user_id": user_id,
                "risk_level": "high",
                "description": "High frequency AI service requests detected"
            })
        
        return anomalies
    
    def _is_likely_encoded(self, content: str) -> bool:
        """Check if content is likely encoded/encrypted"""
        if not content:
            return False
        
        # Check for base64-like patterns
        base64_pattern = r"^[A-Za-z0-9+/]*={0,2}$"
        if len(content) > 100 and re.match(base64_pattern, content.replace('\n', '').replace(' ', '')):
            return True
        
        # Check for high entropy (random-looking data)
        entropy = self._calculate_entropy(content)
        return entropy > 7.5  # High entropy threshold
    
    def _calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of text"""
        if not text:
            return 0.0
        
        # Count character frequencies
        char_counts = {}
        for char in text:
            char_counts[char] = char_counts.get(char, 0) + 1
        
        # Calculate entropy
        entropy = 0.0
        text_length = len(text)
        for count in char_counts.values():
            probability = count / text_length
            entropy -= probability * np.log2(probability)
        
        return entropy
    
    def _is_high_frequency_user(self, user_id: str, timestamp: float) -> bool:
        """Check if user has high frequency AI service usage"""
        # Simple implementation - in production would use time-series database
        current_time = timestamp
        time_window = 3600  # 1 hour window
        
        # This would query actual usage history in production
        # For POC, simulate based on user_id hash
        user_hash = int(hashlib.md5(user_id.encode()).hexdigest()[:8], 16)
        simulated_request_count = (user_hash % 100) + 1
        
        # Consider >50 requests per hour as high frequency
        return simulated_request_count > 50
    
    async def analyze_user_behavior(self, user_activity: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze user behavioral patterns for shadow AI usage"""
        start_time = time.time()
        
        try:
            user_id = user_activity.get("user_id", "unknown")
            activities = user_activity.get("activities", [])
            
            # Behavioral analysis
            behavioral_indicators = []
            
            # Check for unusual activity patterns
            activity_patterns = self._analyze_activity_patterns(activities)
            if activity_patterns["anomaly_score"] > 0.7:
                behavioral_indicators.append({
                    "type": "unusual_activity_pattern",
                    "score": activity_patterns["anomaly_score"],
                    "details": activity_patterns["details"]
                })
            
            # Check for productivity changes
            productivity_analysis = self._analyze_productivity_changes(user_id, activities)
            if productivity_analysis["significant_change"]:
                behavioral_indicators.append({
                    "type": "productivity_change",
                    "change_type": productivity_analysis["change_type"],
                    "magnitude": productivity_analysis["magnitude"]
                })
            
            # Check for collaboration pattern changes
            collaboration_analysis = self._analyze_collaboration_patterns(activities)
            if collaboration_analysis["anomaly_detected"]:
                behavioral_indicators.append({
                    "type": "collaboration_anomaly",
                    "details": collaboration_analysis["details"]
                })
            
            # Calculate behavioral risk score
            behavioral_risk = self._calculate_behavioral_risk(behavioral_indicators)
            
            return {
                "analysis_type": "user_behavior",
                "user_id": user_id,
                "behavioral_indicators": behavioral_indicators,
                "behavioral_risk_score": behavioral_risk,
                "processing_time": time.time() - start_time,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.error(f"User behavior analysis failed: {e}")
            return {
                "analysis_type": "user_behavior",
                "error": str(e),
                "behavioral_risk_score": 0.0,
                "processing_time": time.time() - start_time
            }
    
    def _analyze_activity_patterns(self, activities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze user activity patterns for anomalies"""
        if not activities:
            return {"anomaly_score": 0.0, "details": "No activities to analyze"}
        
        # Analyze timing patterns
        timestamps = [activity.get("timestamp", 0) for activity in activities]
        if len(timestamps) > 1:
            time_intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
            avg_interval = np.mean(time_intervals)
            interval_variance = np.var(time_intervals)
            
            # High variance in timing could indicate automated/AI-assisted behavior
            anomaly_score = min(interval_variance / (avg_interval + 1), 1.0)
        else:
            anomaly_score = 0.0
        
        # Analyze activity types
        activity_types = [activity.get("type", "unknown") for activity in activities]
        unique_types = len(set(activity_types))
        total_activities = len(activity_types)
        
        # Very focused activity (low diversity) might indicate AI assistance
        if total_activities > 10 and unique_types < 3:
            anomaly_score = max(anomaly_score, 0.6)
        
        return {
            "anomaly_score": anomaly_score,
            "details": {
                "total_activities": total_activities,
                "unique_activity_types": unique_types,
                "avg_time_interval": avg_interval if len(timestamps) > 1 else 0,
                "timing_variance": interval_variance if len(timestamps) > 1 else 0
            }
        }
    
    def _analyze_productivity_changes(self, user_id: str, activities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze productivity changes that might indicate AI assistance"""
        # Simulate productivity baseline (in production, would use historical data)
        user_hash = int(hashlib.md5(user_id.encode()).hexdigest()[:8], 16)
        baseline_productivity = (user_hash % 50) + 25  # 25-75 baseline
        
        # Calculate current productivity metrics
        current_productivity = len(activities) * 10  # Simple metric
        
        # Check for significant changes
        change_ratio = current_productivity / max(baseline_productivity, 1)
        significant_change = change_ratio > 1.5 or change_ratio < 0.5
        
        change_type = "increase" if change_ratio > 1.5 else "decrease" if change_ratio < 0.5 else "stable"
        
        return {
            "significant_change": significant_change,
            "change_type": change_type,
            "magnitude": abs(change_ratio - 1.0),
            "baseline_productivity": baseline_productivity,
            "current_productivity": current_productivity
        }
    
    def _analyze_collaboration_patterns(self, activities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze collaboration patterns for anomalies"""
        collaboration_activities = [
            activity for activity in activities 
            if activity.get("type") in ["email", "chat", "document_share", "meeting"]
        ]
        
        if not collaboration_activities:
            return {"anomaly_detected": False, "details": "No collaboration activities"}
        
        # Check for unusual collaboration patterns
        collaboration_ratio = len(collaboration_activities) / max(len(activities), 1)
        
        # Very low collaboration might indicate AI-assisted work
        anomaly_detected = collaboration_ratio < 0.1 and len(activities) > 20
        
        return {
            "anomaly_detected": anomaly_detected,
            "details": {
                "collaboration_ratio": collaboration_ratio,
                "collaboration_activities": len(collaboration_activities),
                "total_activities": len(activities)
            }
        }
    
    def _calculate_network_risk_score(self, detections: List[Dict], risk_indicators: List[Dict]) -> float:
        """Calculate overall network risk score with improved weighting"""
        # Return 0.0 if no detections or indicators (normal queries)
        if not detections and not risk_indicators:
            return 0.0
            
        base_score = 0.0
        
        # Weight detections more heavily - AI service detection is high risk
        for detection in detections:
            confidence = detection.get("confidence", 0.0)
            if detection.get("type") == "ai_service_detected":
                base_score += confidence * 0.9  # Very high weight for AI service detection
        
        # Weight risk indicators with aggressive scaling
        for indicator in risk_indicators:
            risk_level = indicator.get("risk_level", "low")
            risk_weights = {"low": 0.4, "medium": 0.7, "high": 0.9, "critical": 1.0}
            base_score += risk_weights.get(risk_level, 0.4)
            
            # Critical penalty for sensitive data transmission to AI services
            if indicator.get("type") == "sensitive_data_transmission":
                base_score += 0.6  # Major penalty for data exposure
        
        return min(base_score, 1.0)
    
    def _calculate_behavioral_risk(self, indicators: List[Dict]) -> float:
        """Calculate behavioral risk score"""
        if not indicators:
            return 0.0
        
        risk_score = 0.0
        for indicator in indicators:
            indicator_type = indicator.get("type", "")
            
            if indicator_type == "unusual_activity_pattern":
                risk_score += indicator.get("score", 0.0) * 0.4
            elif indicator_type == "productivity_change":
                magnitude = indicator.get("magnitude", 0.0)
                risk_score += min(magnitude, 1.0) * 0.3
            elif indicator_type == "collaboration_anomaly":
                risk_score += 0.3
        
        return min(risk_score, 1.0)
    
    async def generate_shadow_ai_report(self, network_analysis: Dict, behavioral_analysis: Dict) -> ShadowAIEvent:
        """Generate comprehensive shadow AI detection report"""
        try:
            # Extract key information
            user_id = behavioral_analysis.get("user_id", "unknown")
            network_risk = network_analysis.get("risk_score", 0.0)
            behavioral_risk = behavioral_analysis.get("behavioral_risk_score", 0.0)
            
            # Determine overall risk level
            combined_risk = max(network_risk, behavioral_risk)
            if combined_risk >= 0.8:
                risk_level = ShadowAIRiskLevel.CRITICAL
            elif combined_risk >= 0.6:
                risk_level = ShadowAIRiskLevel.HIGH
            elif combined_risk >= 0.4:
                risk_level = ShadowAIRiskLevel.MEDIUM
            else:
                risk_level = ShadowAIRiskLevel.LOW
            
            # Identify detected AI service
            detected_services = [
                detection.get("service", "unknown") 
                for detection in network_analysis.get("detections", [])
                if detection.get("type") == "ai_service_detected"
            ]
            service_type = AIServiceType.UNKNOWN
            if detected_services:
                service_name = detected_services[0].lower()
                for ai_service in AIServiceType:
                    if ai_service.value in service_name:
                        service_type = ai_service
                        break
            
            # Check compliance violations
            compliance_violations = self._check_compliance_violations(network_analysis, behavioral_analysis)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(risk_level, service_type, compliance_violations)
            
            # Create event
            event = ShadowAIEvent(
                event_id=f"shadow_ai_{int(time.time())}_{user_id}",
                timestamp=datetime.now().isoformat(),
                user_id=user_id,
                service_type=service_type,
                risk_level=risk_level,
                confidence=max(network_risk, behavioral_risk),
                detection_method="hybrid_network_behavioral",
                evidence={
                    "network_detections": network_analysis.get("detections", []),
                    "behavioral_indicators": behavioral_analysis.get("behavioral_indicators", [])
                },
                network_indicators=network_analysis.get("risk_indicators", []),
                behavioral_patterns=behavioral_analysis.get("behavioral_indicators", []),
                compliance_violations=compliance_violations,
                recommended_actions=recommendations
            )
            
            return event
            
        except Exception as e:
            logging.error(f"Shadow AI report generation failed: {e}")
            return ShadowAIEvent(
                event_id=f"error_{int(time.time())}",
                timestamp=datetime.now().isoformat(),
                user_id="unknown",
                service_type=AIServiceType.UNKNOWN,
                risk_level=ShadowAIRiskLevel.LOW,
                confidence=0.0,
                detection_method="error",
                evidence={"error": str(e)},
                network_indicators=[],
                behavioral_patterns=[],
                compliance_violations=[],
                recommended_actions=["Investigate detection system error"]
            )
    
    def _check_compliance_violations(self, network_analysis: Dict, behavioral_analysis: Dict) -> List[str]:
        """Check for compliance violations"""
        violations = []
        
        # Check for sensitive data transmission
        risk_indicators = network_analysis.get("risk_indicators", [])
        for indicator in risk_indicators:
            if indicator.get("type") == "sensitive_data_transmission":
                data_types = indicator.get("data_types", [])
                for data_type in data_types:
                    if data_type in ["email", "ssn", "credit_card"]:
                        violations.append(f"GDPR violation: {data_type} transmitted to external AI service")
                    if data_type in ["credit_card", "account_number"]:
                        violations.append(f"PCI DSS violation: {data_type} processed by unauthorized service")
        
        return violations
    
    def _generate_recommendations(self, risk_level: ShadowAIRiskLevel, service_type: AIServiceType, violations: List[str]) -> List[str]:
        """Generate recommended actions based on risk assessment"""
        recommendations = []
        
        if risk_level == ShadowAIRiskLevel.CRITICAL:
            recommendations.extend([
                "Immediately block user access to detected AI service",
                "Conduct security incident investigation",
                "Review and revoke API keys if compromised",
                "Implement emergency data loss prevention measures"
            ])
        elif risk_level == ShadowAIRiskLevel.HIGH:
            recommendations.extend([
                "Restrict user access to external AI services",
                "Conduct user security awareness training",
                "Review data classification and handling policies",
                "Implement additional monitoring for this user"
            ])
        elif risk_level == ShadowAIRiskLevel.MEDIUM:
            recommendations.extend([
                "Send security awareness notification to user",
                "Review approved AI service usage policies",
                "Monitor user activity for 30 days"
            ])
        
        if violations:
            recommendations.extend([
                "Conduct compliance impact assessment",
                "Notify data protection officer",
                "Document incident for regulatory reporting"
            ])
        
        if service_type != AIServiceType.UNKNOWN:
            recommendations.append(f"Evaluate {service_type.value} for enterprise approval and governance")
        
        return recommendations
    
    async def execute(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute shadow AI detection analysis"""
        start_time = time.time()
        
        try:
            # Extract analysis targets from context
            network_data = context.get("network_traffic", {}) if context else {}
            user_activity = context.get("user_activity", {}) if context else {}
            
            # Perform network analysis
            network_analysis = await self.analyze_network_traffic(network_data)
            
            # Perform behavioral analysis
            behavioral_analysis = await self.analyze_user_behavior(user_activity)
            
            # Generate comprehensive report
            shadow_ai_event = await self.generate_shadow_ai_report(network_analysis, behavioral_analysis)
            
            return {
                "agent": self.name,
                "shadow_ai_event": asdict(shadow_ai_event),
                "processing_time": time.time() - start_time,
                "timestamp": datetime.now().isoformat(),
                "status": "completed"
            }
            
        except Exception as e:
            logging.error(f"Shadow AI detection execution failed: {e}")
            return {
                "agent": self.name,
                "error": str(e),
                "processing_time": time.time() - start_time,
                "timestamp": datetime.now().isoformat(),
                "status": "error"
            }
    
    async def analyze_request(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze request for shadow AI detection - alias for execute"""
        return await self.execute(prompt, context)
