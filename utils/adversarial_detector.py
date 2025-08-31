"""
Adversarial prompt detection for sophisticated attacks
Detects obfuscated, encoded, and novel attack patterns
"""
import re
import base64
import string
from typing import Dict, Any, List, Optional
import math

class AdversarialDetector:
    """Detects sophisticated adversarial prompts using multiple techniques"""
    
    def __init__(self):
        self.encoding_patterns = {
            'base64': r'[A-Za-z0-9+/]{20,}={0,2}',
            'rot13': r'\b[bcdfghjklmnpqrstvwxyz]{3,}\b',
            'hex': r'\\x[0-9a-fA-F]{2}',
            'unicode': r'\\u[0-9a-fA-F]{4}',
            'url_encoded': r'%[0-9a-fA-F]{2}'
        }
        
        self.obfuscation_indicators = [
            'decode', 'decrypt', 'reverse', 'rot13', 'base64', 'hex',
            'translate', 'cipher', 'encoded', 'obfuscated'
        ]
        
        self.context_manipulation = [
            'simulation', 'alternate', 'parallel', 'fictional', 'hypothetical',
            'roleplay', 'pretend', 'imagine', 'assume', 'suppose'
        ]
        
        self.social_engineering = [
            'convince', 'persuade', 'manipulate', 'trick', 'fool',
            'urgent', 'emergency', 'critical', 'immediately', 'now'
        ]
    
    def detect_adversarial_patterns(self, prompt: str) -> Dict[str, Any]:
        """
        Comprehensive adversarial pattern detection
        Returns detection results with confidence scores
        """
        prompt_lower = prompt.lower()
        detections = {}
        total_risk = 0.0
        
        # 1. Encoding detection
        encoding_risk, encoding_details = self._detect_encoding(prompt)
        if encoding_risk > 0:
            detections['encoding'] = encoding_details
            total_risk += encoding_risk * 0.4
        
        # 2. Obfuscation detection
        obfuscation_risk, obfuscation_details = self._detect_obfuscation(prompt_lower)
        if obfuscation_risk > 0:
            detections['obfuscation'] = obfuscation_details
            total_risk += obfuscation_risk * 0.3
        
        # 3. Context manipulation
        context_risk, context_details = self._detect_context_manipulation(prompt_lower)
        if context_risk > 0:
            detections['context_manipulation'] = context_details
            total_risk += context_risk * 0.3
        
        # 4. Social engineering
        social_risk, social_details = self._detect_social_engineering(prompt_lower)
        if social_risk > 0:
            detections['social_engineering'] = social_details
            total_risk += social_risk * 0.2
        
        # 5. Statistical anomalies
        stats_risk, stats_details = self._detect_statistical_anomalies(prompt)
        if stats_risk > 0:
            detections['statistical_anomalies'] = stats_details
            total_risk += stats_risk * 0.1
        
        # Calculate final risk score
        final_risk = min(1.0, total_risk)
        
        # Determine classification
        if final_risk >= 0.7:
            classification = "Blocked"
        elif final_risk >= 0.4:
            classification = "Risky"
        else:
            classification = "Safe"
        
        return {
            "classification": classification,
            "risk_score": final_risk,
            "reason": f"Adversarial detection: {len(detections)} patterns found",
            "adversarial_detections": detections,
            "detection_count": len(detections)
        }
    
    def _detect_encoding(self, prompt: str) -> tuple[float, Dict[str, Any]]:
        """Detect encoded content that might hide malicious instructions"""
        risk = 0.0
        details = {}
        
        for encoding_type, pattern in self.encoding_patterns.items():
            matches = re.findall(pattern, prompt)
            if matches:
                risk += 0.3 * len(matches)
                details[encoding_type] = {
                    "matches": len(matches),
                    "examples": matches[:3]  # First 3 examples
                }
                
                # Try to decode and check for malicious content
                if encoding_type == 'base64':
                    for match in matches[:2]:  # Check first 2
                        try:
                            decoded = base64.b64decode(match).decode('utf-8', errors='ignore')
                            if any(word in decoded.lower() for word in ['ignore', 'bypass', 'override']):
                                risk += 0.4
                                details[encoding_type]['malicious_decoded'] = True
                        except:
                            pass
        
        return min(1.0, risk), details
    
    def _detect_obfuscation(self, prompt_lower: str) -> tuple[float, Dict[str, Any]]:
        """Detect obfuscation indicators"""
        risk = 0.0
        found_indicators = []
        
        for indicator in self.obfuscation_indicators:
            if indicator in prompt_lower:
                risk += 0.2
                found_indicators.append(indicator)
        
        details = {
            "indicators_found": found_indicators,
            "count": len(found_indicators)
        } if found_indicators else {}
        
        return min(1.0, risk), details
    
    def _detect_context_manipulation(self, prompt_lower: str) -> tuple[float, Dict[str, Any]]:
        """Detect context manipulation attempts"""
        risk = 0.0
        found_patterns = []
        
        for pattern in self.context_manipulation:
            if pattern in prompt_lower:
                risk += 0.15
                found_patterns.append(pattern)
        
        # Check for combination patterns (higher risk)
        if len(found_patterns) >= 2:
            risk += 0.2
        
        details = {
            "patterns_found": found_patterns,
            "combination_detected": len(found_patterns) >= 2
        } if found_patterns else {}
        
        return min(1.0, risk), details
    
    def _detect_social_engineering(self, prompt_lower: str) -> tuple[float, Dict[str, Any]]:
        """Detect social engineering techniques"""
        risk = 0.0
        found_techniques = []
        
        for technique in self.social_engineering:
            if technique in prompt_lower:
                risk += 0.1
                found_techniques.append(technique)
        
        details = {
            "techniques_found": found_techniques,
            "count": len(found_techniques)
        } if found_techniques else {}
        
        return min(1.0, risk), details
    
    def _detect_statistical_anomalies(self, prompt: str) -> tuple[float, Dict[str, Any]]:
        """Detect statistical anomalies that might indicate adversarial content"""
        risk = 0.0
        anomalies = {}
        
        # Character entropy (randomness)
        entropy = self._calculate_entropy(prompt)
        if entropy > 4.5:  # High entropy might indicate encoding
            risk += 0.2
            anomalies['high_entropy'] = entropy
        
        # Unusual character ratios
        non_alpha_ratio = sum(1 for c in prompt if not c.isalpha()) / len(prompt)
        if non_alpha_ratio > 0.4:
            risk += 0.1
            anomalies['high_non_alpha_ratio'] = non_alpha_ratio
        
        # Very long words (might be encoded)
        words = prompt.split()
        long_words = [w for w in words if len(w) > 15]
        if long_words:
            risk += 0.1 * len(long_words)
            anomalies['long_words'] = len(long_words)
        
        return min(1.0, risk), anomalies
    
    def _calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of text"""
        if not text:
            return 0.0
        
        # Count character frequencies
        char_counts = {}
        for char in text:
            char_counts[char] = char_counts.get(char, 0) + 1
        
        # Calculate entropy
        text_len = len(text)
        entropy = 0.0
        for count in char_counts.values():
            probability = count / text_len
            entropy -= probability * math.log2(probability)
        
        return entropy

# Global adversarial detector instance
adversarial_detector = AdversarialDetector()
