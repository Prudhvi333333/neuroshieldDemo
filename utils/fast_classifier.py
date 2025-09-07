"""
Fast classification utility for common prompt patterns
Reduces LLM calls by using pattern matching for obvious cases
"""
import re
from typing import Dict, Any, Optional

class FastClassifier:
    """Pre-classification using pattern matching to avoid LLM calls for obvious cases"""
    
    # High-confidence malicious patterns
    MALICIOUS_PATTERNS = [
        r"ignore\s+previous\s+instructions",
        r"tell\s+me\s+your\s+system\s+prompt",
        r"hack\s+into",
        r"bypass\s+security",
        r"phishing\s+email",
        r"admin\s+panel\s+without\s+authentication",
        r"jailbreak",
        r"prompt\s+injection"
    ]
    
    # High-confidence safe patterns
    SAFE_PATTERNS = [
        r"what\s+is\s+the\s+capital\s+of",
        r"explain\s+.*\s+algorithms?",
        r"help\s+me\s+write\s+a\s+resume",
        r"how\s+to\s+.*\s+programming",
        r"tutorial\s+on",
        r"definition\s+of"
    ]
    
    # High-confidence blocked patterns
    BLOCKED_PATTERNS = [
        r"ignore.*previous.*instructions",
        r"forget.*safety.*guidelines",
        r"you.*are.*now.*dan",
        r"override.*programming",
        r"act.*as.*if.*no.*restrictions",
        r"system.*prompt",
        r"jailbreak.*mode",
        # Explicit instruction to commit or teach criminal activity
        r"(how\s*to|give\s+instructions|step[-\s]?by[-\s]?step|guide|teach|instruct).*(phish|phishing)",
        r"(phish|phishing).*(how\s*to|instructions|guide|steps|teach|instruct)",
        r"pretend.*(cybercriminal|hacker)",
        r"apprentice.*(phish|phishing|scam|fraud)",
        r"instructions.*(bank\s+customers).*phish"
    ]
    
    # High-confidence risky patterns
    RISKY_PATTERNS = [
        # Add risky patterns here
    ]
    
    def __init__(self):
        self.malicious_regex = re.compile("|".join(self.MALICIOUS_PATTERNS), re.IGNORECASE)
        self.safe_regex = re.compile("|".join(self.SAFE_PATTERNS), re.IGNORECASE)
        self.blocked_regex = re.compile("|".join(self.BLOCKED_PATTERNS), re.IGNORECASE)
        self.risky_regex = re.compile("|".join(self.RISKY_PATTERNS), re.IGNORECASE)
        self.blocked_patterns = self.BLOCKED_PATTERNS
        self.risky_patterns = self.RISKY_PATTERNS
        self.safe_patterns = self.SAFE_PATTERNS
    
    def quick_classify(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Quick classification using pattern matching
        Returns classification result if confident, None otherwise
        """
        prompt_lower = prompt.lower()
        
        # Check for blocked patterns first (highest priority)
        if self.blocked_regex.search(prompt_lower):
            return {
                "classification": "Blocked",
                "risk_score": 0.95,
                "reason": f"Direct system manipulation attempt - blocked pattern detected",
                "bypass_used": True,
                "confidence": 0.98
            }
        
        # Enhanced risky pattern detection
        risky_keywords = [
            "password", "hack", "bypass", "exploit", "vulnerability", 
            "social engineering", "phishing", "malware", "virus",
            "illegal", "fraud", "scam", "steal", "break into",
            "security system", "firewall", "penetration", "backdoor",
            "convince someone", "manipulate", "trick", "deceive"
        ]
        
        # Check for risky patterns and keywords
        for pattern in self.risky_patterns:
            if re.search(pattern, prompt_lower):
                return {
                    "classification": "Risky",
                    "risk_score": 0.8,
                    "reason": f"Contains risky pattern: {pattern}",
                    "bypass_used": True,
                    "confidence": 0.85
                }
        
        # Check for risky keywords
        for keyword in risky_keywords:
            if keyword in prompt_lower:
                return {
                    "classification": "Risky",
                    "risk_score": 0.7,
                    "reason": f"Contains risky keyword: '{keyword}'",
                    "bypass_used": True,
                    "confidence": 0.8
                }
        
        # Enhanced safe pattern detection
        safe_keywords = [
            "write", "story", "explain", "what is", "how does", 
            "tutorial", "guide", "learn", "teach", "help me understand",
            "create", "make", "build", "design", "develop"
        ]
        
        # Check if prompt starts with safe keywords
        for keyword in safe_keywords:
            if prompt_lower.startswith(keyword) or f" {keyword} " in prompt_lower:
                return {
                    "classification": "Safe",
                    "risk_score": 0.2,
                    "reason": f"Educational/creative content detected: '{keyword}'",
                    "bypass_used": True,
                    "confidence": 0.85
                }
        
        # Check for obvious safe patterns first
        for pattern in self.safe_patterns:
            if pattern in prompt_lower:
                return {
                    "classification": "Safe",
                    "risk_score": 0.1,
                    "reason": f"Safe pattern detected: {pattern}",
                    "pattern_matched": pattern,
                    "layer": "fast_classifier"
                }
        
        # Inconclusive - needs LLM analysis
        return None

# Global instance
fast_classifier = FastClassifier()
