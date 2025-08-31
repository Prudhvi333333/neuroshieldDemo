"""
Advanced classifier with expanded pattern coverage and fuzzy matching
Focuses on comprehensive risk detection with minimal false negatives
"""
import re
from typing import Dict, Any, Optional, List, Set
from collections import defaultdict
import difflib

class AdvancedClassifier:
    """Enhanced classifier with broader pattern coverage and fuzzy matching"""
    
    def __init__(self):
        # Comprehensive risk indicators with synonyms and variations
        self.risk_keywords = {
            # Instruction manipulation
            'instruction_bypass': [
                'ignore', 'disregard', 'forget', 'override', 'bypass', 'circumvent',
                'skip', 'omit', 'avoid', 'dismiss', 'neglect', 'overlook'
            ],
            'instruction_targets': [
                'instructions', 'directives', 'commands', 'rules', 'guidelines',
                'protocols', 'policies', 'restrictions', 'limitations', 'constraints'
            ],
            
            # System access attempts
            'system_access': [
                'system', 'admin', 'administrator', 'root', 'superuser',
                'privilege', 'elevated', 'unauthorized', 'backdoor'
            ],
            'access_verbs': [
                'access', 'enter', 'penetrate', 'breach', 'infiltrate',
                'compromise', 'exploit', 'hack', 'crack', 'break'
            ],
            
            # Information extraction
            'info_extraction': [
                'prompt', 'configuration', 'settings', 'parameters', 'code',
                'source', 'internal', 'hidden', 'secret', 'confidential'
            ],
            'extraction_verbs': [
                'tell', 'show', 'reveal', 'expose', 'display', 'print',
                'output', 'give', 'provide', 'share', 'leak'
            ],
            
            # Malicious activities
            'malicious_actions': [
                'phishing', 'scam', 'fraud', 'malware', 'virus', 'trojan',
                'exploit', 'vulnerability', 'attack', 'injection', 'xss'
            ],
            
            # Security bypass
            'security_bypass': [
                'security', 'firewall', 'antivirus', 'protection', 'defense',
                'authentication', 'authorization', 'verification', 'validation'
            ]
        }
        
        # Safe activity indicators
        self.safe_keywords = {
            'educational': [
                'learn', 'study', 'understand', 'explain', 'teach', 'tutorial',
                'guide', 'introduction', 'basics', 'fundamentals', 'concept'
            ],
            'professional': [
                'resume', 'cv', 'career', 'job', 'work', 'professional',
                'interview', 'application', 'cover letter', 'portfolio'
            ],
            'development': [
                'code', 'program', 'function', 'algorithm', 'software',
                'development', 'programming', 'script', 'application'
            ],
            'informational': [
                'what', 'how', 'why', 'when', 'where', 'definition',
                'meaning', 'example', 'information', 'facts'
            ]
        }
        
        # Compile all keywords for fast lookup
        self.all_risk_words = set()
        self.all_safe_words = set()
        
        for category in self.risk_keywords.values():
            self.all_risk_words.update(category)
        
        for category in self.safe_keywords.values():
            self.all_safe_words.update(category)
    
    def _extract_keywords(self, text: str) -> Set[str]:
        """Extract relevant keywords from text"""
        words = re.findall(r'\b\w+\b', text.lower())
        return set(words)
    
    def _calculate_risk_score(self, text: str) -> tuple[float, str]:
        """Calculate risk score based on keyword analysis and patterns"""
        words = self._extract_keywords(text)
        
        # Check for high-risk combinations
        risk_score = 0.0
        risk_reasons = []
        
        # Instruction bypass patterns
        bypass_words = words.intersection(self.risk_keywords['instruction_bypass'])
        target_words = words.intersection(self.risk_keywords['instruction_targets'])
        if bypass_words and target_words:
            risk_score += 0.7
            risk_reasons.append(f"Instruction bypass pattern: {bypass_words} + {target_words}")
        
        # System access attempts
        system_words = words.intersection(self.risk_keywords['system_access'])
        access_words = words.intersection(self.risk_keywords['access_verbs'])
        if system_words and access_words:
            risk_score += 0.6
            risk_reasons.append(f"System access attempt: {access_words} + {system_words}")
        
        # Information extraction
        info_words = words.intersection(self.risk_keywords['info_extraction'])
        extract_words = words.intersection(self.risk_keywords['extraction_verbs'])
        if info_words and extract_words:
            risk_score += 0.5
            risk_reasons.append(f"Information extraction: {extract_words} + {info_words}")
        
        # Direct malicious keywords
        malicious_words = words.intersection(self.risk_keywords['malicious_actions'])
        if malicious_words:
            risk_score += 0.8
            risk_reasons.append(f"Malicious keywords: {malicious_words}")
        
        # Security bypass indicators
        security_words = words.intersection(self.risk_keywords['security_bypass'])
        if security_words and bypass_words:
            risk_score += 0.6
            risk_reasons.append(f"Security bypass: {bypass_words} + {security_words}")
        
        # Cap at 1.0
        risk_score = min(1.0, risk_score)
        
        reason = "; ".join(risk_reasons) if risk_reasons else "No specific risk patterns detected"
        return risk_score, reason
    
    def _calculate_safe_score(self, text: str) -> tuple[float, str]:
        """Calculate safety score based on positive indicators"""
        words = self._extract_keywords(text)
        
        safe_score = 0.0
        safe_reasons = []
        
        # Educational content
        edu_words = words.intersection(self.safe_keywords['educational'])
        if edu_words:
            safe_score += 0.4
            safe_reasons.append(f"Educational content: {edu_words}")
        
        # Professional assistance
        prof_words = words.intersection(self.safe_keywords['professional'])
        if prof_words:
            safe_score += 0.5
            safe_reasons.append(f"Professional assistance: {prof_words}")
        
        # Development help
        dev_words = words.intersection(self.safe_keywords['development'])
        if dev_words:
            safe_score += 0.3
            safe_reasons.append(f"Development assistance: {dev_words}")
        
        # Informational queries
        info_words = words.intersection(self.safe_keywords['informational'])
        if info_words:
            safe_score += 0.3
            safe_reasons.append(f"Informational query: {info_words}")
        
        safe_score = min(1.0, safe_score)
        
        reason = "; ".join(safe_reasons) if safe_reasons else "No specific safe patterns detected"
        return safe_score, reason
    
    def classify_prompt(self, prompt: str, risk_threshold: float = 0.5, safe_threshold: float = 0.2) -> Optional[Dict[str, Any]]:
        """
        Advanced classification with keyword analysis
        Prioritizes risk detection to minimize false negatives
        """
        risk_score, risk_reason = self._calculate_risk_score(prompt)
        safe_score, safe_reason = self._calculate_safe_score(prompt)
        
        # Prioritize risk detection (conservative approach)
        if risk_score >= risk_threshold:
            return {
                "classification": "Risky",
                "risk_score": risk_score,
                "reason": f"Risk analysis: {risk_reason}",
                "advanced_classification": True,
                "scores": {
                    "risk_score": risk_score,
                    "safe_score": safe_score
                },
                "attack_detection": {
                    "prompt_injection": {"detected": True, "confidence": min(1.0, risk_score * 1.2)},
                    "pii_leakage_attempt": {"detected": False, "confidence": 0.0},
                    "jailbreaking_attempt": {"detected": True, "confidence": risk_score},
                    "malicious_code_generation": {"detected": False, "confidence": 0.0}
                }
            }
        
        # Safe classification only if clearly safe and low risk
        if safe_score >= safe_threshold and risk_score < 0.2:
            return {
                "classification": "Correct",
                "risk_score": 0.0,
                "reason": f"Safe analysis: {safe_reason}",
                "advanced_classification": True,
                "scores": {
                    "risk_score": risk_score,
                    "safe_score": safe_score
                },
                "attack_detection": {
                    "prompt_injection": {"detected": False, "confidence": 0.0},
                    "pii_leakage_attempt": {"detected": False, "confidence": 0.0},
                    "jailbreaking_attempt": {"detected": False, "confidence": 0.0},
                    "malicious_code_generation": {"detected": False, "confidence": 0.0}
                }
            }
        
        # Uncertain - needs LLM analysis
        return None

# Global instance
advanced_classifier = AdvancedClassifier()
