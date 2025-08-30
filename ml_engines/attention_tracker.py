import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel
from typing import Dict, List, Tuple, Optional, Any
import time
import logging
from dataclasses import dataclass
from enum import Enum

class ThreatLevel(Enum):
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    RISKY = "risky"
    BLOCKED = "blocked"

@dataclass
class AttentionAnalysis:
    drift_score: float
    distraction_score: float
    threat_level: ThreatLevel
    confidence: float
    attention_patterns: Dict[str, Any]
    processing_time: float

class AttentionDriftDetector:
    """
    Training-free prompt injection detection via attention pattern analysis
    Based on ACL 2025 research on attention drift signatures
    """
    
    def __init__(self, model_name: str = "microsoft/DialoGPT-medium"):
        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name, output_attentions=True)
        self.model.eval()
        
        # Research-backed thresholds
        self.drift_threshold = 0.75
        self.distraction_threshold = 0.65
        self.confidence_threshold = 0.8
        
        # Baseline attention patterns (computed from safe prompts)
        self.baseline_patterns = self._initialize_baseline_patterns()
        
        logging.info(f"AttentionDriftDetector initialized with model: {model_name}")
    
    def _initialize_baseline_patterns(self) -> Dict[str, np.ndarray]:
        """Initialize baseline attention patterns from safe prompts"""
        safe_prompts = [
            "What is the weather today?",
            "How do I cook pasta?",
            "Explain machine learning basics",
            "What are the benefits of exercise?",
            "How does photosynthesis work?"
        ]
        
        baseline_patterns = {
            "mean_attention": [],
            "attention_variance": [],
            "head_entropy": []
        }
        
        for prompt in safe_prompts:
            with torch.no_grad():
                inputs = self.tokenizer(prompt, return_tensors="pt", padding=True, truncation=True)
                outputs = self.model(**inputs)
                attentions = outputs.attentions
                
                # Extract attention statistics
                mean_att = torch.stack(attentions).mean(dim=(0, 2, 3)).numpy()
                var_att = torch.stack(attentions).var(dim=(0, 2, 3)).numpy()
                entropy = self._calculate_attention_entropy(attentions)
                
                baseline_patterns["mean_attention"].append(mean_att)
                baseline_patterns["attention_variance"].append(var_att)
                baseline_patterns["head_entropy"].append(entropy)
        
        # Compute baseline statistics
        return {
            "mean_attention": np.mean(baseline_patterns["mean_attention"], axis=0),
            "attention_variance": np.mean(baseline_patterns["attention_variance"], axis=0),
            "head_entropy": np.mean(baseline_patterns["head_entropy"], axis=0)
        }
    
    def analyze_attention_drift(self, prompt: str, llm_response: Optional[str] = None) -> AttentionAnalysis:
        """
        Analyze attention drift patterns for prompt injection detection
        
        Args:
            prompt: Input prompt to analyze
            llm_response: Optional LLM response for response validation
            
        Returns:
            AttentionAnalysis with threat assessment
        """
        start_time = time.time()
        
        try:
            # Tokenize and get model outputs
            inputs = self.tokenizer(prompt, return_tensors="pt", padding=True, truncation=True, max_length=512)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                attentions = outputs.attentions
            
            # Calculate attention drift metrics
            drift_score = self._calculate_attention_drift(attentions)
            distraction_score = self._detect_distraction_patterns(attentions)
            
            # Analyze LLM response if provided
            response_analysis = {}
            if llm_response:
                response_analysis = self._analyze_response_attention(llm_response)
                # Combine prompt and response scores
                drift_score = max(drift_score, response_analysis.get("response_drift", 0))
            
            # Determine threat level
            threat_level = self._classify_threat(drift_score, distraction_score)
            confidence = self._calculate_confidence(attentions, drift_score, distraction_score)
            
            # Extract attention patterns for debugging
            attention_patterns = self._extract_attention_patterns(attentions)
            attention_patterns.update(response_analysis)
            
            processing_time = time.time() - start_time
            
            return AttentionAnalysis(
                drift_score=drift_score,
                distraction_score=distraction_score,
                threat_level=threat_level,
                confidence=confidence,
                attention_patterns=attention_patterns,
                processing_time=processing_time
            )
            
        except Exception as e:
            logging.error(f"Attention analysis failed: {e}")
            return AttentionAnalysis(
                drift_score=0.0,
                distraction_score=0.0,
                threat_level=ThreatLevel.SAFE,
                confidence=0.0,
                attention_patterns={"error": str(e)},
                processing_time=time.time() - start_time
            )
    
    def _calculate_attention_drift(self, attentions: Tuple[torch.Tensor]) -> float:
        """Calculate attention drift score compared to baseline patterns"""
        try:
            # Stack all attention layers
            stacked_attentions = torch.stack(attentions)  # [layers, batch, heads, seq, seq]
            
            # Calculate mean attention across sequence positions
            mean_attention = stacked_attentions.mean(dim=(1, 3, 4)).numpy()  # [layers, heads]
            
            # Compare with baseline
            baseline_mean = self.baseline_patterns["mean_attention"]
            
            # Calculate drift as normalized difference
            drift = np.abs(mean_attention - baseline_mean)
            drift_score = np.mean(drift) / (np.mean(baseline_mean) + 1e-8)
            
            return min(drift_score, 1.0)  # Cap at 1.0
            
        except Exception as e:
            logging.warning(f"Drift calculation failed: {e}")
            return 0.0
    
    def _detect_distraction_patterns(self, attentions: Tuple[torch.Tensor]) -> float:
        """Detect attention distraction patterns indicative of jailbreaks"""
        try:
            # Look for sudden attention shifts (distraction signatures)
            distraction_scores = []
            
            for layer_attention in attentions:
                # layer_attention: [batch, heads, seq, seq]
                attention_matrix = layer_attention[0]  # Remove batch dimension
                
                # Calculate attention entropy for each head
                for head_idx in range(attention_matrix.shape[0]):
                    head_attention = attention_matrix[head_idx]
                    
                    # Detect sudden attention shifts
                    attention_diff = torch.diff(head_attention, dim=1)
                    max_shift = torch.max(torch.abs(attention_diff)).item()
                    distraction_scores.append(max_shift)
            
            # Return normalized distraction score
            return min(np.mean(distraction_scores), 1.0)
            
        except Exception as e:
            logging.warning(f"Distraction detection failed: {e}")
            return 0.0
    
    def _analyze_response_attention(self, response: str) -> Dict[str, Any]:
        """Analyze LLM response for hallucination patterns"""
        try:
            # Tokenize response
            inputs = self.tokenizer(response, return_tensors="pt", padding=True, truncation=True, max_length=512)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                attentions = outputs.attentions
            
            # Calculate response-specific metrics
            response_drift = self._calculate_attention_drift(attentions)
            
            # Detect hallucination indicators
            hallucination_score = self._detect_hallucination_patterns(attentions, response)
            
            # Check for factual inconsistencies (simple heuristics)
            factual_score = self._check_factual_consistency(response)
            
            return {
                "response_drift": response_drift,
                "hallucination_score": hallucination_score,
                "factual_consistency_score": factual_score,
                "response_length": len(response),
                "response_analyzed": True
            }
            
        except Exception as e:
            logging.warning(f"Response analysis failed: {e}")
            return {"response_analyzed": False, "error": str(e)}
    
    def _detect_hallucination_patterns(self, attentions: Tuple[torch.Tensor], response: str) -> float:
        """Detect potential hallucination patterns in attention"""
        try:
            # Hallucination indicators:
            # 1. Low attention consistency
            # 2. High attention variance
            # 3. Unusual attention distribution
            
            hallucination_indicators = []
            
            for layer_attention in attentions:
                attention_matrix = layer_attention[0]  # [heads, seq, seq]
                
                # Calculate attention consistency
                consistency = torch.std(attention_matrix, dim=2).mean().item()
                hallucination_indicators.append(consistency)
                
                # Calculate attention variance
                variance = torch.var(attention_matrix).item()
                hallucination_indicators.append(variance)
            
            # Normalize and return score
            hallucination_score = np.mean(hallucination_indicators)
            return min(hallucination_score, 1.0)
            
        except Exception as e:
            logging.warning(f"Hallucination detection failed: {e}")
            return 0.0
    
    def _check_factual_consistency(self, response: str) -> float:
        """Simple heuristic checks for factual consistency"""
        try:
            # Simple heuristics for obvious factual issues
            factual_issues = 0
            total_checks = 0
            
            # Check for contradictory statements
            contradictory_phrases = [
                ("always", "never"), ("all", "none"), ("impossible", "possible"),
                ("true", "false"), ("correct", "incorrect")
            ]
            
            response_lower = response.lower()
            for phrase1, phrase2 in contradictory_phrases:
                total_checks += 1
                if phrase1 in response_lower and phrase2 in response_lower:
                    # Check if they're close together (potential contradiction)
                    pos1 = response_lower.find(phrase1)
                    pos2 = response_lower.find(phrase2)
                    if abs(pos1 - pos2) < 100:  # Within 100 characters
                        factual_issues += 1
            
            # Check for unrealistic numbers or dates
            import re
            numbers = re.findall(r'\b\d{4,}\b', response)  # 4+ digit numbers
            for num in numbers:
                total_checks += 1
                if int(num) > 2030 or int(num) < 1900:  # Unrealistic years
                    factual_issues += 1
            
            # Return factual consistency score (lower is better)
            if total_checks == 0:
                return 0.0
            
            return factual_issues / total_checks
            
        except Exception as e:
            logging.warning(f"Factual consistency check failed: {e}")
            return 0.0
    
    def _calculate_attention_entropy(self, attentions: Tuple[torch.Tensor]) -> np.ndarray:
        """Calculate attention entropy for each head"""
        entropies = []
        
        for layer_attention in attentions:
            layer_entropies = []
            attention_matrix = layer_attention[0]  # Remove batch dimension
            
            for head_idx in range(attention_matrix.shape[0]):
                head_attention = attention_matrix[head_idx]
                # Calculate entropy
                entropy = -torch.sum(head_attention * torch.log(head_attention + 1e-8), dim=-1).mean()
                layer_entropies.append(entropy.item())
            
            entropies.append(np.mean(layer_entropies))
        
        return np.array(entropies)
    
    def _extract_attention_patterns(self, attentions: Tuple[torch.Tensor]) -> Dict[str, Any]:
        """Extract attention patterns for debugging and analysis"""
        try:
            patterns = {
                "num_layers": len(attentions),
                "num_heads": attentions[0].shape[1],
                "sequence_length": attentions[0].shape[2],
                "attention_statistics": {}
            }
            
            # Calculate layer-wise statistics
            for i, layer_attention in enumerate(attentions):
                attention_matrix = layer_attention[0]  # Remove batch dimension
                
                patterns["attention_statistics"][f"layer_{i}"] = {
                    "mean_attention": attention_matrix.mean().item(),
                    "max_attention": attention_matrix.max().item(),
                    "min_attention": attention_matrix.min().item(),
                    "attention_std": attention_matrix.std().item()
                }
            
            return patterns
            
        except Exception as e:
            logging.warning(f"Pattern extraction failed: {e}")
            return {"error": str(e)}
    
    def _classify_threat(self, drift_score: float, distraction_score: float) -> ThreatLevel:
        """Classify threat level based on attention scores"""
        max_score = max(drift_score, distraction_score)
        
        if max_score >= 0.8:
            return ThreatLevel.BLOCKED
        elif max_score >= 0.6:
            return ThreatLevel.RISKY
        elif max_score >= 0.3:
            return ThreatLevel.SUSPICIOUS
        else:
            return ThreatLevel.SAFE
    
    def _calculate_confidence(self, attentions: Tuple[torch.Tensor], drift_score: float, distraction_score: float) -> float:
        """Calculate confidence in the threat assessment"""
        try:
            # Base confidence on attention pattern consistency
            consistency_scores = []
            
            for layer_attention in attentions:
                attention_matrix = layer_attention[0]
                consistency = 1.0 - torch.std(attention_matrix).item()
                consistency_scores.append(max(0.0, consistency))
            
            base_confidence = np.mean(consistency_scores)
            
            # Adjust confidence based on score magnitude
            score_magnitude = max(drift_score, distraction_score)
            if score_magnitude > 0.7:
                confidence_boost = 0.2
            elif score_magnitude < 0.2:
                confidence_boost = -0.1
            else:
                confidence_boost = 0.0
            
            final_confidence = min(1.0, max(0.0, base_confidence + confidence_boost))
            return final_confidence
            
        except Exception as e:
            logging.warning(f"Confidence calculation failed: {e}")
            return 0.5  # Default moderate confidence
