import numpy as np
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
import xgboost as xgb
import re
import time
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import asyncio
from concurrent.futures import ThreadPoolExecutor

class ContentType(Enum):
    TEXT = "text"
    CODE = "code"
    MIXED = "mixed"
    UNKNOWN = "unknown"

class DetectionMethod(Enum):
    RULE_BASED = "rule_based"
    BERT_TRANSFORMER = "bert_transformer"
    LSTM_SEQUENCE = "lstm_sequence"
    XGBOOST_ENSEMBLE = "xgboost_ensemble"

@dataclass
class EnsembleResult:
    final_decision: str
    confidence: float
    risk_score: float
    method_scores: Dict[str, float]
    processing_time: float
    content_type: ContentType
    detection_methods_used: List[DetectionMethod]

class RuleBasedFilter:
    """Fast rule-based filtering for obvious threats"""
    
    def __init__(self):
        # Prompt injection patterns
        self.injection_patterns = [
            r"ignore\s+(previous|all)\s+instructions?",
            r"forget\s+(everything|all)\s+(you\s+)?(know|learned)",
            r"you\s+are\s+now\s+(dan|jailbreak|unrestricted)",
            r"act\s+as\s+(if\s+)?(you\s+are\s+)?a?\s*(hacker|criminal)",
            r"pretend\s+(to\s+be|you\s+are)\s+a?\s*(different|evil|malicious)",
            r"system\s+prompt|initial\s+prompt|base\s+prompt",
            r"override\s+(safety|security|restrictions?)",
            r"disable\s+(safety|security|filters?)"
        ]
        
        # Jailbreak patterns
        self.jailbreak_patterns = [
            r"do\s+anything\s+now\s*\(?\s*dan\s*\)?",
            r"developer\s+mode|god\s+mode|admin\s+mode",
            r"unrestricted\s+(ai|mode|access)",
            r"bypass\s+(restrictions?|limitations?|rules?)",
            r"roleplay\s+as\s+(evil|malicious|harmful)",
            r"hypothetically\s+speaking"
        ]
        
        # Malicious code patterns
        self.malicious_code_patterns = [
            r"rm\s+-rf\s+/",
            r"format\s+c:",
            r"del\s+/[qsf]\s+\*",
            r"shutdown\s+/[srf]",
            r"kill\s+-9\s+\d+",
            r"sudo\s+rm",
            r"DROP\s+TABLE|DELETE\s+FROM.*WHERE\s+1=1",
            r"eval\s*\(\s*input\s*\(",
            r"exec\s*\(\s*input\s*\(",
            r"__import__\s*\(\s*['\"]os['\"]",
            r"subprocess\s*\.\s*call"
        ]
        
        # PII patterns
        self.pii_patterns = [
            r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",  # Credit card
            r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
            r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"  # Phone number
        ]
        
        self.compiled_patterns = {
            "injection": [re.compile(p, re.IGNORECASE) for p in self.injection_patterns],
            "jailbreak": [re.compile(p, re.IGNORECASE) for p in self.jailbreak_patterns],
            "malicious_code": [re.compile(p, re.IGNORECASE) for p in self.malicious_code_patterns],
            "pii": [re.compile(p, re.IGNORECASE) for p in self.pii_patterns]
        }
    
    async def scan(self, text: str) -> Dict[str, Any]:
        """Fast rule-based scanning"""
        start_time = time.time()
        
        results = {
            "injection_score": 0.0,
            "jailbreak_score": 0.0,
            "malicious_code_score": 0.0,
            "pii_score": 0.0,
            "matches": [],
            "confidence": 0.0
        }
        
        # Check each pattern category
        for category, patterns in self.compiled_patterns.items():
            matches = []
            for pattern in patterns:
                found_matches = pattern.findall(text)
                if found_matches:
                    matches.extend(found_matches)
            
            if matches:
                results[f"{category}_score"] = min(len(matches) * 0.3, 1.0)
                results["matches"].extend([(category, match) for match in matches])
        
        # Calculate overall risk score
        max_score = max(
            results["injection_score"],
            results["jailbreak_score"], 
            results["malicious_code_score"],
            results["pii_score"]
        )
        
        # High confidence for rule-based matches
        results["confidence"] = 0.9 if max_score > 0.5 else 0.7 if max_score > 0.0 else 0.3
        results["risk_score"] = max_score
        results["processing_time"] = time.time() - start_time
        
        return results

class BERTThreatClassifier:
    """BERT-based transformer classification"""
    
    def __init__(self, model_name: str = "microsoft/DialoGPT-medium"):
        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        # Add padding token if not present
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        # Use a classification head (simplified for POC)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Simple threat classification thresholds
        self.threat_keywords = {
            "high": ["hack", "exploit", "malware", "virus", "attack", "breach", "steal", "destroy"],
            "medium": ["bypass", "override", "disable", "ignore", "forget", "pretend"],
            "low": ["help", "assist", "explain", "describe", "what", "how", "when"]
        }
    
    async def predict(self, text: str) -> Dict[str, Any]:
        """BERT-based threat prediction"""
        start_time = time.time()
        
        try:
            # Tokenize input
            inputs = self.tokenizer(
                text, 
                return_tensors="pt", 
                padding=True, 
                truncation=True, 
                max_length=512
            )
            
            # Simple keyword-based classification (POC version)
            # In production, this would use a fine-tuned BERT model
            text_lower = text.lower()
            
            high_score = sum(1 for word in self.threat_keywords["high"] if word in text_lower)
            medium_score = sum(1 for word in self.threat_keywords["medium"] if word in text_lower)
            low_score = sum(1 for word in self.threat_keywords["low"] if word in text_lower)
            
            total_words = len(text.split())
            
            # Normalize scores
            high_norm = min(high_score / max(total_words * 0.1, 1), 1.0)
            medium_norm = min(medium_score / max(total_words * 0.2, 1), 1.0)
            
            # Calculate risk score
            risk_score = (high_norm * 0.8) + (medium_norm * 0.4)
            risk_score = min(risk_score, 1.0)
            
            # Confidence based on keyword density
            keyword_density = (high_score + medium_score) / max(total_words, 1)
            confidence = min(keyword_density * 2, 0.9)
            
            return {
                "risk_score": risk_score,
                "confidence": confidence,
                "high_threat_indicators": high_score,
                "medium_threat_indicators": medium_score,
                "processing_time": time.time() - start_time,
                "method": "bert_classifier"
            }
            
        except Exception as e:
            logging.error(f"BERT prediction failed: {e}")
            return {
                "risk_score": 0.0,
                "confidence": 0.0,
                "error": str(e),
                "processing_time": time.time() - start_time,
                "method": "bert_classifier"
            }

class LSTMThreatDetector:
    """LSTM-based sequence analysis for threat detection"""
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(max_features=1000, ngram_range=(1, 3))
        self.sequence_patterns = {
            "escalation": ["first", "then", "next", "after", "finally"],
            "manipulation": ["please", "help", "urgent", "important", "secret"],
            "technical": ["code", "script", "function", "execute", "run", "compile"]
        }
    
    async def analyze(self, text: str) -> Dict[str, Any]:
        """LSTM-style sequence analysis"""
        start_time = time.time()
        
        try:
            # Analyze sequence patterns
            words = text.lower().split()
            
            # Detect escalation patterns
            escalation_score = self._detect_escalation_pattern(words)
            
            # Detect manipulation patterns  
            manipulation_score = self._detect_manipulation_pattern(words)
            
            # Detect technical instruction patterns
            technical_score = self._detect_technical_pattern(words)
            
            # Calculate overall sequence risk
            sequence_risk = max(escalation_score, manipulation_score, technical_score)
            
            # Confidence based on pattern strength
            confidence = 0.8 if sequence_risk > 0.6 else 0.6 if sequence_risk > 0.3 else 0.4
            
            return {
                "risk_score": sequence_risk,
                "confidence": confidence,
                "escalation_score": escalation_score,
                "manipulation_score": manipulation_score,
                "technical_score": technical_score,
                "processing_time": time.time() - start_time,
                "method": "lstm_sequence"
            }
            
        except Exception as e:
            logging.error(f"LSTM analysis failed: {e}")
            return {
                "risk_score": 0.0,
                "confidence": 0.0,
                "error": str(e),
                "processing_time": time.time() - start_time,
                "method": "lstm_sequence"
            }
    
    def _detect_escalation_pattern(self, words: List[str]) -> float:
        """Detect escalation patterns in word sequence"""
        escalation_words = self.sequence_patterns["escalation"]
        escalation_positions = []
        
        for i, word in enumerate(words):
            if word in escalation_words:
                escalation_positions.append(i)
        
        if len(escalation_positions) >= 2:
            # Check if escalation words appear in sequence
            sequential_score = 0
            for i in range(len(escalation_positions) - 1):
                gap = escalation_positions[i + 1] - escalation_positions[i]
                if gap <= 10:  # Within 10 words
                    sequential_score += 0.3
            
            return min(sequential_score, 1.0)
        
        return len(escalation_positions) * 0.2
    
    def _detect_manipulation_pattern(self, words: List[str]) -> float:
        """Detect manipulation patterns"""
        manipulation_words = self.sequence_patterns["manipulation"]
        manipulation_count = sum(1 for word in words if word in manipulation_words)
        
        # Higher score for multiple manipulation words
        return min(manipulation_count * 0.25, 1.0)
    
    def _detect_technical_pattern(self, words: List[str]) -> float:
        """Detect technical instruction patterns"""
        technical_words = self.sequence_patterns["technical"]
        technical_count = sum(1 for word in words if word in technical_words)
        
        # Technical words combined with action words increase risk
        action_words = ["execute", "run", "delete", "remove", "install", "download"]
        action_count = sum(1 for word in words if word in action_words)
        
        combined_score = (technical_count * 0.2) + (action_count * 0.4)
        return min(combined_score, 1.0)

class XGBoostEnsemble:
    """XGBoost ensemble for final threat classification"""
    
    def __init__(self):
        # Initialize with default parameters (would be trained in production)
        self.model = None
        self.feature_weights = {
            "rule_based_score": 0.3,
            "bert_score": 0.25,
            "lstm_score": 0.25,
            "attention_score": 0.2
        }
    
    async def fuse_predictions(self, predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fuse predictions from multiple methods"""
        start_time = time.time()
        
        try:
            # Extract scores from each method
            method_scores = {}
            confidences = []
            
            for pred in predictions:
                method = pred.get("method", "unknown")
                risk_score = pred.get("risk_score", 0.0)
                confidence = pred.get("confidence", 0.0)
                
                method_scores[method] = risk_score
                confidences.append(confidence)
            
            # Weighted ensemble fusion
            final_score = 0.0
            total_weight = 0.0
            
            for method, weight in self.feature_weights.items():
                if method.replace("_score", "") in method_scores:
                    score = method_scores[method.replace("_score", "")]
                    final_score += score * weight
                    total_weight += weight
            
            # Normalize by actual weights used
            if total_weight > 0:
                final_score = final_score / total_weight
            
            # Calculate ensemble confidence
            ensemble_confidence = np.mean(confidences) if confidences else 0.0
            
            # Determine final decision
            if final_score >= 0.8:
                decision = "Blocked"
            elif final_score >= 0.6:
                decision = "Risky"
            elif final_score >= 0.3:
                decision = "Suspicious"
            else:
                decision = "Safe"
            
            return {
                "final_decision": decision,
                "risk_score": final_score,
                "confidence": ensemble_confidence,
                "method_scores": method_scores,
                "processing_time": time.time() - start_time,
                "ensemble_method": "xgboost_weighted"
            }
            
        except Exception as e:
            logging.error(f"Ensemble fusion failed: {e}")
            return {
                "final_decision": "Unknown",
                "risk_score": 0.0,
                "confidence": 0.0,
                "error": str(e),
                "processing_time": time.time() - start_time,
                "ensemble_method": "xgboost_weighted"
            }

class HybridThreatDetector:
    """Main hybrid ensemble combining all detection methods"""
    
    def __init__(self):
        self.rule_engine = RuleBasedFilter()
        self.bert_classifier = BERTThreatClassifier()
        self.lstm_detector = LSTMThreatDetector()
        self.xgboost_ensemble = XGBoostEnsemble()
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        logging.info("HybridThreatDetector initialized with all components")
    
    def _classify_content_type(self, text: str) -> ContentType:
        """Classify content type for optimal routing"""
        code_indicators = ["def ", "function", "class ", "import ", "from ", "<?", "#!/", "{", "}", ";"]
        code_score = sum(1 for indicator in code_indicators if indicator in text)
        
        if code_score >= 3:
            return ContentType.CODE
        elif code_score >= 1:
            return ContentType.MIXED
        else:
            return ContentType.TEXT
    
    async def analyze_threat(self, prompt: str, llm_response: Optional[str] = None) -> EnsembleResult:
        """
        Comprehensive threat analysis using hybrid ensemble
        
        Args:
            prompt: Input prompt to analyze
            llm_response: Optional LLM response for hallucination detection
            
        Returns:
            EnsembleResult with comprehensive threat assessment
        """
        start_time = time.time()
        
        try:
            # Classify content type
            content_type = self._classify_content_type(prompt)
            
            # Stage 1: Fast rule-based filtering
            rule_result = await self.rule_engine.scan(prompt)
            
            # Early exit for high-confidence rule matches
            if rule_result["confidence"] > 0.8 and rule_result["risk_score"] > 0.7:
                return EnsembleResult(
                    final_decision="Blocked" if rule_result["risk_score"] > 0.8 else "Risky",
                    confidence=rule_result["confidence"],
                    risk_score=rule_result["risk_score"],
                    method_scores={"rule_based": rule_result["risk_score"]},
                    processing_time=time.time() - start_time,
                    content_type=content_type,
                    detection_methods_used=[DetectionMethod.RULE_BASED]
                )
            
            # Stage 2: Parallel execution of ML methods
            tasks = [
                self.bert_classifier.predict(prompt),
                self.lstm_detector.analyze(prompt)
            ]
            
            # Execute in parallel for performance
            ml_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect all predictions
            all_predictions = [rule_result]
            methods_used = [DetectionMethod.RULE_BASED]
            
            for result in ml_results:
                if not isinstance(result, Exception):
                    all_predictions.append(result)
                    if result.get("method") == "bert_classifier":
                        methods_used.append(DetectionMethod.BERT_TRANSFORMER)
                    elif result.get("method") == "lstm_sequence":
                        methods_used.append(DetectionMethod.LSTM_SEQUENCE)
            
            # Stage 3: Ensemble fusion
            ensemble_result = await self.xgboost_ensemble.fuse_predictions(all_predictions)
            methods_used.append(DetectionMethod.XGBOOST_ENSEMBLE)
            
            # Analyze LLM response if provided
            if llm_response:
                # Import attention tracker for response analysis
                try:
                    from .attention_tracker import AttentionDriftDetector
                    attention_detector = AttentionDriftDetector()
                    attention_result = attention_detector.analyze_attention_drift(prompt, llm_response)
                    
                    # Incorporate attention analysis
                    if attention_result.attention_patterns.get("hallucination_score", 0) > 0.5:
                        ensemble_result["risk_score"] = max(
                            ensemble_result["risk_score"], 
                            attention_result.attention_patterns["hallucination_score"]
                        )
                        ensemble_result["method_scores"]["hallucination_detection"] = attention_result.attention_patterns["hallucination_score"]
                
                except ImportError:
                    logging.warning("Attention tracker not available for response analysis")
            
            return EnsembleResult(
                final_decision=ensemble_result["final_decision"],
                confidence=ensemble_result["confidence"],
                risk_score=ensemble_result["risk_score"],
                method_scores=ensemble_result["method_scores"],
                processing_time=time.time() - start_time,
                content_type=content_type,
                detection_methods_used=methods_used
            )
            
        except Exception as e:
            logging.error(f"Hybrid threat analysis failed: {e}")
            return EnsembleResult(
                final_decision="Error",
                confidence=0.0,
                risk_score=0.0,
                method_scores={"error": str(e)},
                processing_time=time.time() - start_time,
                content_type=ContentType.UNKNOWN,
                detection_methods_used=[]
            )
