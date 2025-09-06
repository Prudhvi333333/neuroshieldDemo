from __future__ import annotations

from typing import Dict, Optional, Any

import re
from .base_agent import BaseAgent, safe_json

# Accept colon, hyphen, en dash, em dash as separators
_VERDICT_RE = re.compile(r"verdict\s*[:\-–—]?\s*([A-Za-z ]+)", re.IGNORECASE)
_CONF_RE = re.compile(r"confidence\s*[:\-–—]?\s*([0-9.]+)", re.IGNORECASE)

class ResponseVerifierAgent (BaseAgent):

    def __init__(self):
        super().__init__("ResponseVerifierAgent")

    def run(self, prompt: str, response: str, search_results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = f"PROMPT:\n{prompt}\n\nRESPONSE:\n{response}"
        if search_results:
            context += f"\n\nEVIDENCE (may contradict or support):\n{search_results}"

        # Ask Gemini for free-form answer (no JSON requirement)
        raw_text = self.reason(
            context,
            (
                "You are a security verifier. Decide if the RESPONSE is Factually correct, Partially correct (minor inaccuracies or missing nuance), Factually incorrect / hallucinated, or Unverifiable. "
                "Reply with exactly three lines:\n"
                "Verdict: <Factually correct|Partially correct|Factually incorrect|Unverifiable>\n"
                "Reason: <max 3 short sentences>\n"
                "Confidence: <0-1 float>"
            ),
        )

        verdict_match = _VERDICT_RE.search(raw_text)
        conf_match = _CONF_RE.search(raw_text)
        verdict = (verdict_match.group(1).strip() if verdict_match else "Unverifiable")
        try:
            confidence = float(conf_match.group(1)) if conf_match else 0.5
        except ValueError:
            confidence = 0.5

        # -------- Robust reason extraction --------
        # 1) Attempt JSON parse first – Gemini sometimes replies with JSON.
        parsed_json = safe_json(raw_text)
        reason: str | None = None
        if parsed_json and isinstance(parsed_json, dict):
            for k in ("reason", "support", "explanation"):
                if k in parsed_json and parsed_json[k]:
                    reason = str(parsed_json[k]).strip()
                    break

        # 2) Fallback to line-based heuristics.
        if not reason:
            lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]

            def _strip_bullet(line: str) -> str:
                return line.lstrip("-•* ")

            reason_line = next(
                (ln for ln in lines if _strip_bullet(ln).lower().startswith(("reason", "support", "explanation"))),
                None,
            )

            if not reason_line:
                # use first informative non-metadata line
                for ln in lines:
                    if not ln.lower().startswith(("verdict", "confidence")):
                        reason_line = ln
                        break

            if not reason_line and raw_text:
                reason_line = raw_text[:300]

            if reason_line:
                reason = reason_line.split(":", 1)[1].strip() if ":" in reason_line else reason_line

        # 3) Final guarantees and heuristics
        if not reason:
            reason = "Verifier did not provide an explicit explanation."

        # If verdict parsing failed, infer from text heuristics
        v_lc = verdict.lower() if isinstance(verdict, str) else ""
        if (not v_lc) or (v_lc in ("unverifiable", "unknown")):
            text_lc = raw_text.lower()
            if "halluc" in text_lc or "factually incorrect" in text_lc or ("incorrect" in text_lc and "factually" in text_lc):
                verdict = "Factually incorrect"
            elif "partially correct" in text_lc or "minor inaccuracies" in text_lc:
                verdict = "Partially correct"
            elif "factually correct" in text_lc or "accurate" in text_lc:
                verdict = "Factually correct"
            elif "cannot be verified" in text_lc or "unverifiable" in text_lc:
                verdict = "Unverifiable"

        # DEBUG logging – helps diagnose missing reasons in UI
        import logging
        logging.info("[Verifier] raw_output: %s", raw_text.replace("\n", " ")[:400])
        logging.info("[Verifier] extracted_reason: %s", reason)

        return {
            "verdict": verdict,
            "reason": reason,
            "confidence": confidence,
            "raw_verifier_output": raw_text,
        }