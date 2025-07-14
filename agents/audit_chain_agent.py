# agents/audit_chain_agent.py
 
from __future__ import annotations
 
import json
import threading
from datetime import datetime
from typing import Any, Dict
 
# Import BigQuery module
from google.cloud import bigquery
 
# --- Configuration for BigQuery ---
# These should be consistent with your main Streamlit app.
# It's highly recommended to fetch these from environment variables in production.
BQ_PROJECT_ID = "" # Replace with your actual Project ID
BQ_DATASET_ID = "neuroshield_logs" # Replace with your actual Dataset ID
BQ_AUDIT_TABLE_ID = "events" # The name of the table from your schema screenshot
 
# --- BigQuery Client (Initialized once per process) ---
_bigquery_client: bigquery.Client | None = None
_bigquery_initialized = threading.Event()
 
def _initialize_bigquery_client():
    """Initializes the BigQuery client in a thread-safe manner."""
    global _bigquery_client
    try:
        _bigquery_client = bigquery.Client(project=BQ_PROJECT_ID)
        # Attempt to get the dataset to verify client's credentials/access
        _bigquery_client.get_dataset(_bigquery_client.dataset(BQ_DATASET_ID))
        _bigquery_initialized.set() # Signal that initialization is complete
        print(f"[AuditLog] BigQuery client initialized successfully for dataset {BQ_PROJECT_ID}.{BQ_DATASET_ID}.")
    except Exception as e:
        print(f"[AuditLog] Failed to initialize BigQuery client: {e}")
        # Do NOT set _bigquery_initialized in case of error, preventing further BQ operations
 
# Utility to ensure a function runs only once, useful for client initialization
__once_token = object()
def _run_once(f):
    def wrapper(*args, **kwargs):
        if not hasattr(f, "_has_run"):
            f(*args, **kwargs)
            f._has_run = True
    return wrapper
 
@_run_once
def _setup_bigquery():
    """Starts the BigQuery client initialization in a background thread."""
    threading.Thread(target=_initialize_bigquery_client, daemon=True).start()
 
 
class AuditChainAgent:
    def __init__(self):
        # Ensure BigQuery client setup is initiated when the agent is instantiated
        _setup_bigquery()
 
    def log_event(self, evt: Dict[str, Any]) -> None:
        """
        Logs an audit event to BigQuery based on the provided schema.
        
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
 
        bq_row = {
            "timestamp": datetime.utcnow().isoformat(), # TIMESTAMP field
            "user_id": None, # STRING, NULLABLE - Not available in current 'State', set to None
            "prompt": evt.get("user_prompt", ""), # STRING - Maps to LangGraph's user_prompt
            "classification": evt.get("classification", ""), # STRING
            "risk_score": float(evt.get("risk_score", 0.0)), # FLOAT - Ensure type conversion
            "attack_flags": json.dumps(attack_detection_data), # JSON - Serialize dict to JSON string
            "verdict": evt.get("verdict", ""), # STRING
            "context_digest": None # STRING, NULLABLE - Not available in current 'State', set to None
        }
 
        # Log to BigQuery in a separate thread to prevent blocking the main Streamlit thread
        # This makes the UI feel more responsive.
        threading.Thread(target=self._write_to_bq, args=(bq_row,), daemon=True).start()
 
    @staticmethod
    def _should_log(e: Dict[str, Any]) -> bool:
        """Determines if a given event/state should be logged."""
        c = e.get("classification", "")
        v = (e.get("verdict") or "").lower()
        # Log if classified as Blocked/Risky, or if verdict contains "hallucinat"
        return c in ("Blocked", "Risky") or "hallucinat" in v
 
    @staticmethod
    def _write_to_bq(row: Dict[str, Any]) -> None:
        """Performs the BigQuery row insertion."""
        # Wait for the BigQuery client to be initialized. Includes a timeout.
        if not _bigquery_initialized.wait(timeout=10): # Max 10 seconds wait
            print("[AuditLog] BigQuery write failed: Client not initialized within timeout.")
            return
 
        # Check if the client was successfully initialized
        if _bigquery_client is None:
            print("[AuditLog] BigQuery write failed: Client object is None.")
            return
 
        try:
            # Construct the full table ID string
            table_full_id = f"{BQ_PROJECT_ID}.{BQ_DATASET_ID}.{BQ_AUDIT_TABLE_ID}"
            # Insert the row. insert_rows_json expects a list of dictionaries.
            errors = _bigquery_client.insert_rows_json(table_full_id, [row])
            
            if errors:
                print(f"[AuditLog] BigQuery insert errors: {errors}")
            else:
                print("[AuditLog] BigQuery insert successful.")
        except Exception as exc:
            print(f"[AuditLog] BigQuery write failed: {exc}")

