# agents/audit_chain_agent.py
 
from __future__ import annotations
 
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict
from app.audit.hash_chain import write_audit_event
 
 
class AuditChainAgent:
    def __init__(self):
        # Using new tamper-evident audit system
        pass
 
    def log_event(self, evt: Dict[str, Any]) -> None:
        """
        Logs an audit event using the tamper-evident hash chain system.
        
        Args:
            evt: The current State dictionary from the LangGraph.
        """
        if not self._should_log(evt):
            return

        # Extract data for the new audit system
        tenant_id = evt.get("tenant_id", "default")
        policy_version = evt.get("policy_version", "1.0")
        decision = evt.get("verdict", "UNKNOWN")
        
        # Build reasons list
        reasons = []
        if evt.get("classification"):
            reasons.append(f"Classification: {evt['classification']}")
        if evt.get("reason"):
            reasons.append(evt["reason"])
        
        # Build evidence list
        evidence = []
        if evt.get("user_prompt"):
            evidence.append({"type": "user_prompt", "content": evt["user_prompt"]})
        if evt.get("risk_score"):
            evidence.append({"type": "risk_score", "value": float(evt["risk_score"])})
        if evt.get("attack_detection"):
            evidence.append({"type": "attack_detection", "data": evt["attack_detection"]})
        if evt.get("code_fragment"):
            evidence.append({"type": "code_fragment", "content": evt["code_fragment"]})
        
        # Write to tamper-evident audit log
        try:
            hash_result = write_audit_event(
                tenant_id=tenant_id,
                policy_version=policy_version,
                decision=decision,
                reasons=reasons,
                evidence=evidence,
                user_id=evt.get("user_id"),
                context_digest=evt.get("context_digest")
            )
            logging.info(f"Audit event logged with hash: {hash_result[:16]}...")
        except Exception as e:
            logging.error(f"Failed to write tamper-evident audit event: {e}")
            # Fallback to old method if new system fails
            self._fallback_log(evt)
 
    @staticmethod
    def _should_log(e: Dict[str, Any]) -> bool:
        """Determines if a given event/state should be logged."""
        c = e.get("classification", "")
        v = (e.get("verdict") or "").lower()
        # Log if classified as Blocked/Risky, or if verdict contains "hallucinat"
        return c in ("Blocked", "Risky") or "hallucinat" in v

    def _fallback_log(self, evt: Dict[str, Any]) -> None:
        """Fallback to old logging method if new system fails."""
        attack_detection_data = evt.get("attack_detection", {})
        if not isinstance(attack_detection_data, dict):
            attack_detection_data = {}

        report_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": None,
            "prompt": evt.get("user_prompt", ""),
            "classification": evt.get("classification", ""),
            "risk_score": float(evt.get("risk_score", 0.0)),
            "attack_flags": json.dumps(attack_detection_data),
            "verdict": evt.get("verdict", ""),
            "context_digest": None
        }
        self._append_to_json(report_data)

    def _append_to_json(self, entry: Dict[str, Any]) -> None:
        """Append entry to logs/audit_log_fallback.json (maintains JSON array)."""
        try:
            logs_dir = os.path.join(os.getcwd(), "logs")
            os.makedirs(logs_dir, exist_ok=True)
            log_file_path = os.path.join(logs_dir, "audit_log_fallback.json")
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
            logging.info("Fallback audit entry appended to %s", log_file_path)
        except Exception as e:
            logging.error("Failed to write fallback audit log: %s", e)
