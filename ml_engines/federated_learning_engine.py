#!/usr/bin/env python3
"""
Federated Learning Engine - Day 7 Implementation
Collaborative threat intelligence sharing without exposing sensitive data
"""

import asyncio
import json
import time
import logging
import hashlib
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import pickle
import base64
from pathlib import Path

class ModelType(Enum):
    THREAT_DETECTION = "threat_detection"
    BEHAVIORAL_ANALYSIS = "behavioral_analysis"
    ANOMALY_DETECTION = "anomaly_detection"

class ParticipantRole(Enum):
    COORDINATOR = "coordinator"
    PARTICIPANT = "participant"
    VALIDATOR = "validator"

@dataclass
class ModelUpdate:
    participant_id: str
    model_type: ModelType
    update_weights: Dict[str, Any]
    data_samples: int
    accuracy_metrics: Dict[str, float]
    timestamp: datetime
    signature: str

@dataclass
class GlobalModel:
    model_type: ModelType
    version: int
    weights: Dict[str, Any]
    participants: List[str]
    accuracy: float
    last_updated: datetime
    update_history: List[str]

@dataclass
class FederatedSession:
    session_id: str
    model_type: ModelType
    coordinator: str
    participants: List[str]
    current_round: int
    max_rounds: int
    min_participants: int
    status: str
    created_at: datetime
    last_activity: datetime

class FederatedLearningEngine:
    """
    Federated Learning Engine for collaborative threat intelligence
    
    Features:
    - Privacy-preserving model updates
    - Secure aggregation of model weights
    - Differential privacy protection
    - Byzantine fault tolerance
    - Automated model validation
    - Threat intelligence sharing
    """
    
    def __init__(self, participant_id: str = None, role: ParticipantRole = ParticipantRole.PARTICIPANT):
        self.participant_id = participant_id or f"participant_{int(time.time())}"
        self.role = role
        self.sessions = {}
        self.global_models = {}
        self.local_models = {}
        self.update_history = []
        
        # Privacy and security settings
        self.differential_privacy_epsilon = 1.0
        self.min_participants_for_aggregation = 3
        self.byzantine_tolerance_threshold = 0.3
        
        # Storage paths
        self.models_dir = Path("federated_models")
        self.models_dir.mkdir(exist_ok=True)
        
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"Federated Learning Engine initialized - ID: {self.participant_id}, Role: {role.value}")
    
    async def create_federated_session(self, model_type: ModelType, max_rounds: int = 10, 
                                     min_participants: int = 3) -> str:
        """Create a new federated learning session"""
        if self.role != ParticipantRole.COORDINATOR:
            raise ValueError("Only coordinators can create federated sessions")
        
        session_id = f"session_{model_type.value}_{int(time.time())}"
        
        session = FederatedSession(
            session_id=session_id,
            model_type=model_type,
            coordinator=self.participant_id,
            participants=[],
            current_round=0,
            max_rounds=max_rounds,
            min_participants=min_participants,
            status="waiting_for_participants",
            created_at=datetime.now(),
            last_activity=datetime.now()
        )
        
        self.sessions[session_id] = session
        
        # Initialize global model
        self.global_models[session_id] = GlobalModel(
            model_type=model_type,
            version=0,
            weights=self._initialize_model_weights(model_type),
            participants=[],
            accuracy=0.0,
            last_updated=datetime.now(),
            update_history=[]
        )
        
        self.logger.info(f"Created federated session: {session_id}")
        return session_id
    
    async def join_federated_session(self, session_id: str) -> bool:
        """Join an existing federated learning session"""
        if session_id not in self.sessions:
            self.logger.error(f"Session {session_id} not found")
            return False
        
        session = self.sessions[session_id]
        
        if self.participant_id in session.participants:
            self.logger.info(f"Already participating in session {session_id}")
            return True
        
        if session.status != "waiting_for_participants":
            self.logger.error(f"Session {session_id} is not accepting new participants")
            return False
        
        # Add participant
        session.participants.append(self.participant_id)
        session.last_activity = datetime.now()
        
        # Initialize local model
        self.local_models[session_id] = self._initialize_local_model(session.model_type)
        
        self.logger.info(f"Joined federated session: {session_id}")
        
        # Start training if minimum participants reached
        if len(session.participants) >= session.min_participants:
            session.status = "training"
            self.logger.info(f"Session {session_id} started training with {len(session.participants)} participants")
        
        return True
    
    async def submit_model_update(self, session_id: str, training_data: List[Dict[str, Any]], 
                                local_epochs: int = 5) -> bool:
        """Submit local model update to federated session"""
        if session_id not in self.sessions:
            self.logger.error(f"Session {session_id} not found")
            return False
        
        session = self.sessions[session_id]
        
        if self.participant_id not in session.participants:
            self.logger.error(f"Not a participant in session {session_id}")
            return False
        
        if session.status != "training":
            self.logger.error(f"Session {session_id} is not in training state")
            return False
        
        # Train local model
        local_weights, metrics = await self._train_local_model(
            session_id, training_data, local_epochs
        )
        
        # Apply differential privacy
        private_weights = self._apply_differential_privacy(local_weights)
        
        # Create model update
        update = ModelUpdate(
            participant_id=self.participant_id,
            model_type=session.model_type,
            update_weights=private_weights,
            data_samples=len(training_data),
            accuracy_metrics=metrics,
            timestamp=datetime.now(),
            signature=self._sign_update(private_weights)
        )
        
        # Store update
        self.update_history.append(update)
        
        self.logger.info(f"Submitted model update for session {session_id}")
        return True
    
    async def aggregate_model_updates(self, session_id: str) -> bool:
        """Aggregate model updates from all participants (coordinator only)"""
        if self.role != ParticipantRole.COORDINATOR:
            raise ValueError("Only coordinators can aggregate model updates")
        
        if session_id not in self.sessions:
            self.logger.error(f"Session {session_id} not found")
            return False
        
        session = self.sessions[session_id]
        
        # Collect updates from all participants
        participant_updates = [
            update for update in self.update_history
            if update.participant_id in session.participants and 
               update.model_type == session.model_type
        ]
        
        if len(participant_updates) < session.min_participants:
            self.logger.warning(f"Insufficient updates for aggregation: {len(participant_updates)}")
            return False
        
        # Validate updates (Byzantine fault tolerance)
        valid_updates = self._validate_updates(participant_updates)
        
        if len(valid_updates) < session.min_participants:
            self.logger.error(f"Too many invalid updates detected")
            return False
        
        # Perform federated averaging
        aggregated_weights = self._federated_averaging(valid_updates)
        
        # Update global model
        global_model = self.global_models[session_id]
        global_model.weights = aggregated_weights
        global_model.version += 1
        global_model.participants = [u.participant_id for u in valid_updates]
        global_model.last_updated = datetime.now()
        global_model.update_history.append(f"Round {session.current_round}")
        
        # Calculate global accuracy
        global_model.accuracy = self._calculate_global_accuracy(valid_updates)
        
        # Update session
        session.current_round += 1
        session.last_activity = datetime.now()
        
        # Check if training is complete
        if session.current_round >= session.max_rounds:
            session.status = "completed"
            await self._finalize_federated_model(session_id)
        
        self.logger.info(f"Aggregated model updates for session {session_id}, round {session.current_round}")
        return True
    
    async def get_global_model(self, session_id: str) -> Optional[GlobalModel]:
        """Get the current global model"""
        if session_id not in self.global_models:
            return None
        
        return self.global_models[session_id]
    
    async def predict_with_federated_model(self, session_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make predictions using the federated model"""
        if session_id not in self.global_models:
            raise ValueError(f"No global model found for session {session_id}")
        
        global_model = self.global_models[session_id]
        
        # Simulate prediction based on model type
        if global_model.model_type == ModelType.THREAT_DETECTION:
            prediction = await self._predict_threat_detection(global_model.weights, input_data)
        elif global_model.model_type == ModelType.BEHAVIORAL_ANALYSIS:
            prediction = await self._predict_behavioral_analysis(global_model.weights, input_data)
        elif global_model.model_type == ModelType.ANOMALY_DETECTION:
            prediction = await self._predict_anomaly_detection(global_model.weights, input_data)
        else:
            raise ValueError(f"Unknown model type: {global_model.model_type}")
        
        return {
            "prediction": prediction,
            "model_version": global_model.version,
            "confidence": prediction.get("confidence", 0.0),
            "model_accuracy": global_model.accuracy,
            "participants": len(global_model.participants)
        }
    
    def _initialize_model_weights(self, model_type: ModelType) -> Dict[str, Any]:
        """Initialize model weights based on type"""
        if model_type == ModelType.THREAT_DETECTION:
            return {
                "threat_patterns": np.random.normal(0, 0.1, (100, 50)).tolist(),
                "classification_weights": np.random.normal(0, 0.1, (50, 10)).tolist(),
                "bias": np.zeros(10).tolist()
            }
        elif model_type == ModelType.BEHAVIORAL_ANALYSIS:
            return {
                "behavior_embeddings": np.random.normal(0, 0.1, (200, 64)).tolist(),
                "anomaly_weights": np.random.normal(0, 0.1, (64, 1)).tolist(),
                "threshold": [0.5]
            }
        elif model_type == ModelType.ANOMALY_DETECTION:
            return {
                "feature_weights": np.random.normal(0, 0.1, (150, 32)).tolist(),
                "detection_layers": np.random.normal(0, 0.1, (32, 16)).tolist(),
                "output_weights": np.random.normal(0, 0.1, (16, 1)).tolist()
            }
        else:
            return {}
    
    def _initialize_local_model(self, model_type: ModelType) -> Dict[str, Any]:
        """Initialize local model for training"""
        return {
            "weights": self._initialize_model_weights(model_type),
            "training_history": [],
            "last_update": datetime.now()
        }
    
    async def _train_local_model(self, session_id: str, training_data: List[Dict[str, Any]], 
                               epochs: int) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """Train local model on private data"""
        # Simulate local training
        await asyncio.sleep(0.1)  # Simulate training time
        
        local_model = self.local_models[session_id]
        
        # Simulate weight updates
        updated_weights = {}
        for key, weights in local_model["weights"].items():
            if isinstance(weights, list):
                # Add small random updates to simulate training
                updated_weights[key] = [
                    w + np.random.normal(0, 0.01) for w in weights
                ]
            else:
                updated_weights[key] = weights
        
        # Simulate training metrics
        metrics = {
            "accuracy": np.random.uniform(0.85, 0.95),
            "loss": np.random.uniform(0.05, 0.15),
            "epochs": epochs,
            "samples": len(training_data)
        }
        
        # Update local model
        local_model["weights"] = updated_weights
        local_model["training_history"].append(metrics)
        local_model["last_update"] = datetime.now()
        
        return updated_weights, metrics
    
    def _apply_differential_privacy(self, weights: Dict[str, Any]) -> Dict[str, Any]:
        """Apply differential privacy to model weights"""
        private_weights = {}
        
        for key, weight_values in weights.items():
            if isinstance(weight_values, list):
                # Add Laplace noise for differential privacy
                noise_scale = 1.0 / self.differential_privacy_epsilon
                noise = np.random.laplace(0, noise_scale, len(weight_values))
                private_weights[key] = [w + n for w, n in zip(weight_values, noise)]
            else:
                private_weights[key] = weight_values
        
        return private_weights
    
    def _sign_update(self, weights: Dict[str, Any]) -> str:
        """Create signature for model update integrity"""
        weights_str = json.dumps(weights, sort_keys=True)
        signature = hashlib.sha256(f"{self.participant_id}{weights_str}".encode()).hexdigest()
        return signature
    
    def _validate_updates(self, updates: List[ModelUpdate]) -> List[ModelUpdate]:
        """Validate model updates for Byzantine fault tolerance"""
        valid_updates = []
        
        for update in updates:
            # Verify signature
            expected_signature = hashlib.sha256(
                f"{update.participant_id}{json.dumps(update.update_weights, sort_keys=True)}".encode()
            ).hexdigest()
            
            if update.signature != expected_signature:
                self.logger.warning(f"Invalid signature from participant {update.participant_id}")
                continue
            
            # Check for reasonable accuracy metrics
            if update.accuracy_metrics.get("accuracy", 0) < 0.5 or update.accuracy_metrics.get("accuracy", 0) > 1.0:
                self.logger.warning(f"Suspicious accuracy from participant {update.participant_id}")
                continue
            
            # Check for reasonable weight magnitudes
            if self._check_weight_magnitudes(update.update_weights):
                valid_updates.append(update)
            else:
                self.logger.warning(f"Suspicious weight magnitudes from participant {update.participant_id}")
        
        return valid_updates
    
    def _check_weight_magnitudes(self, weights: Dict[str, Any]) -> bool:
        """Check if weight magnitudes are reasonable"""
        for key, weight_values in weights.items():
            if isinstance(weight_values, list):
                max_magnitude = max(abs(w) for w in weight_values)
                if max_magnitude > 10.0:  # Reasonable threshold
                    return False
        return True
    
    def _federated_averaging(self, updates: List[ModelUpdate]) -> Dict[str, Any]:
        """Perform federated averaging of model updates"""
        if not updates:
            return {}
        
        # Calculate weights based on data samples
        total_samples = sum(update.data_samples for update in updates)
        
        aggregated_weights = {}
        
        # Get all weight keys from first update
        weight_keys = updates[0].update_weights.keys()
        
        for key in weight_keys:
            if isinstance(updates[0].update_weights[key], list):
                # Weighted average for list weights
                weighted_sum = np.zeros(len(updates[0].update_weights[key]))
                
                for update in updates:
                    weight = update.data_samples / total_samples
                    update_weights = np.array(update.update_weights[key])
                    weighted_sum += weight * update_weights
                
                aggregated_weights[key] = weighted_sum.tolist()
            else:
                # Simple average for scalar values
                aggregated_weights[key] = sum(
                    update.update_weights[key] for update in updates
                ) / len(updates)
        
        return aggregated_weights
    
    def _calculate_global_accuracy(self, updates: List[ModelUpdate]) -> float:
        """Calculate global model accuracy from participant updates"""
        if not updates:
            return 0.0
        
        # Weighted average of accuracies
        total_samples = sum(update.data_samples for update in updates)
        weighted_accuracy = sum(
            update.accuracy_metrics.get("accuracy", 0) * update.data_samples
            for update in updates
        ) / total_samples
        
        return weighted_accuracy
    
    async def _finalize_federated_model(self, session_id: str):
        """Finalize and save the federated model"""
        global_model = self.global_models[session_id]
        
        # Save model to disk
        model_path = self.models_dir / f"{session_id}_final_model.json"
        with open(model_path, 'w') as f:
            json.dump(asdict(global_model), f, indent=2, default=str)
        
        self.logger.info(f"Finalized federated model saved to {model_path}")
    
    async def _predict_threat_detection(self, weights: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make threat detection prediction"""
        # Simulate threat detection prediction
        threat_score = np.random.uniform(0.1, 0.9)
        
        return {
            "threat_detected": threat_score > 0.5,
            "threat_score": threat_score,
            "confidence": min(abs(threat_score - 0.5) * 2, 1.0),
            "threat_type": "federated_detection"
        }
    
    async def _predict_behavioral_analysis(self, weights: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make behavioral analysis prediction"""
        # Simulate behavioral analysis prediction
        anomaly_score = np.random.uniform(0.0, 0.8)
        
        return {
            "anomaly_detected": anomaly_score > 0.6,
            "anomaly_score": anomaly_score,
            "confidence": min(anomaly_score * 1.5, 1.0),
            "behavior_type": "federated_behavioral"
        }
    
    async def _predict_anomaly_detection(self, weights: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make anomaly detection prediction"""
        # Simulate anomaly detection prediction
        anomaly_level = np.random.uniform(0.0, 1.0)
        
        return {
            "anomaly_detected": anomaly_level > 0.7,
            "anomaly_level": anomaly_level,
            "confidence": anomaly_level,
            "anomaly_type": "federated_anomaly"
        }
    
    def get_federated_stats(self) -> Dict[str, Any]:
        """Get comprehensive federated learning statistics"""
        return {
            "participant_id": self.participant_id,
            "role": self.role.value,
            "active_sessions": len([s for s in self.sessions.values() if s.status == "training"]),
            "completed_sessions": len([s for s in self.sessions.values() if s.status == "completed"]),
            "total_updates_submitted": len(self.update_history),
            "global_models": len(self.global_models),
            "privacy_epsilon": self.differential_privacy_epsilon,
            "byzantine_tolerance": self.byzantine_tolerance_threshold
        }

# Global federated learning engine instance
federated_engine = FederatedLearningEngine()

async def create_threat_intelligence_federation(max_rounds: int = 10) -> str:
    """Create a federated learning session for threat intelligence sharing"""
    if federated_engine.role != ParticipantRole.COORDINATOR:
        federated_engine.role = ParticipantRole.COORDINATOR
    
    session_id = await federated_engine.create_federated_session(
        ModelType.THREAT_DETECTION, max_rounds
    )
    
    return session_id

async def join_threat_intelligence_federation(session_id: str) -> bool:
    """Join an existing threat intelligence federation"""
    return await federated_engine.join_federated_session(session_id)

async def contribute_threat_data(session_id: str, threat_samples: List[Dict[str, Any]]) -> bool:
    """Contribute local threat data to federated learning"""
    return await federated_engine.submit_model_update(session_id, threat_samples)

async def get_federated_threat_prediction(session_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Get threat prediction from federated model"""
    return await federated_engine.predict_with_federated_model(session_id, input_data)

if __name__ == "__main__":
    # Test federated learning
    async def test_federated_learning():
        # Create coordinator
        coordinator = FederatedLearningEngine("coordinator_1", ParticipantRole.COORDINATOR)
        
        # Create session
        session_id = await coordinator.create_federated_session(ModelType.THREAT_DETECTION)
        print(f"Created session: {session_id}")
        
        # Create participants
        participant1 = FederatedLearningEngine("participant_1")
        participant2 = FederatedLearningEngine("participant_2")
        
        # Join session
        await participant1.join_federated_session(session_id)
        await participant2.join_federated_session(session_id)
        
        # Submit updates
        training_data = [{"threat": "malware", "features": [1, 2, 3]}]
        await participant1.submit_model_update(session_id, training_data)
        await participant2.submit_model_update(session_id, training_data)
        
        # Aggregate updates
        await coordinator.aggregate_model_updates(session_id)
        
        # Make prediction
        test_data = {"features": [1, 2, 3]}
        prediction = await coordinator.predict_with_federated_model(session_id, test_data)
        print(f"Federated prediction: {prediction}")
        
        # Get stats
        stats = coordinator.get_federated_stats()
        print(f"Federated stats: {json.dumps(stats, indent=2)}")
    
    asyncio.run(test_federated_learning())
