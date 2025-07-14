# context/context_builder.py
"""
Placeholder context builder.
Keeps the firewall graph happy until you wire Firestore / BigQuery / RAG.
"""
 
import datetime as dt
from typing import Dict, Any
 
async def build(user_id: str, raw_prompt: str) -> Dict[str, Any]:
    return {
        "generated_at": dt.datetime.utcnow().isoformat(),
        "user_id": user_id,
        "note": "empty context – upgrade later",
        "digest": "noctx",
    }
 