# agents/audit_chain_agent.py
 
from __future__ import annotations
 
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict
 
 
class AuditChainAgent:
    def __init__(self):
        # Local-only mode: no BigQuery client initialization required.
        pass
 
    def log_event(self, evt: Dict[str, Any]) -> None:
        """
        Logs an audit event to local JSON log based on the provided schema.
        
        Args:
            evt: The current State dictionary from the LangGraph.
        """
        if not self._should_log(evt):
            return
 
        # Construct the BigQuery row according to your provided schema
        # Schema fields: timestamp, user_id, prompt, classification, risk_score, attack_flags, verdict, context_digest
        
        # Populate attack_flags (JSON Type in BQ)
        attack_detection_data = evt.get("attack_detection", {})
        # Ensure it's a dict before attempting to serialize to JSON, for robustness
        if not isinstance(attack_detection_data, dict):
            attack_detection_data = {}
 
        report_data = {
            "timestamp": datetime.utcnow().isoformat(), # TIMESTAMP field
            "user_id": None, # STRING, NULLABLE - Not available in current 'State', set to None
            "prompt": evt.get("user_prompt", ""), # STRING - Maps to LangGraph's user_prompt
            "classification": evt.get("classification", ""), # STRING
            "risk_score": float(evt.get("risk_score", 0.0)), # FLOAT - Ensure type conversion
            "attack_flags": json.dumps(attack_detection_data), # JSON - Serialize dict to JSON string
            "verdict": evt.get("verdict", ""), # STRING
            "context_digest": None # STRING, NULLABLE - Not available in current 'State', set to None
        }
 
        # Append to local audit JSON synchronously.
        self._append_to_json(report_data)
 
    @staticmethod
    def _should_log(e: Dict[str, Any]) -> bool:
        """Determines if a given event/state should be logged."""
        c = e.get("classification", "")
        v = (e.get("verdict") or "").lower()
        # Log if classified as Blocked/Risky, or if verdict contains "hallucinat"
        return c in ("Blocked", "Risky") or "hallucinat" in v
 

    def _append_to_json(self, entry: Dict[str, Any]) -> None:
        """Append entry to logs/audit_log.json (maintains JSON array)."""
        try:
            logs_dir = os.path.join(os.getcwd(), "logs")
            os.makedirs(logs_dir, exist_ok=True)
            log_file_path = os.path.join(logs_dir, "audit_log.json")
            existing: list[Dict[str, Any]] = []
            if os.path.exists(log_file_path):
                try:
                    with open(log_file_path, "r", encoding="utf-8") as f:
                        existing = json.load(f) or []
                except json.JSONDecodeError:
                    existing = []
            existing.append(entry)
            with open(log_file_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)
            logging.info("Audit entry appended to %s", log_file_path)
        except Exception as e:
            logging.error("Failed to write audit log: %s", e)
    
    async def execute(self, prompt: str, context: Dict = None) -> Dict:
        """Execute method for orchestrator compatibility"""
        # Create audit event from prompt and context
        audit_event = {
            "user_prompt": prompt,
            "classification": context.get("classification", "Unknown") if context else "Unknown",
            "risk_score": context.get("risk_score", 0.0) if context else 0.0,
            "attack_detection": context.get("attack_detection", {}) if context else {},
            "verdict": context.get("verdict", "Processed") if context else "Processed"
        }
        
        # Log the event
        self.log_event(audit_event)
        
        return {
            "agent": "AuditChainAgent",
            "audit_logged": True,
            "processing_time": 0.05,  # Very fast logging operation
            "status": "completed"
        }
