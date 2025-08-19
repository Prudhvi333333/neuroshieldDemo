# NeuroShield – Bug Fix Log

Use this log to **document only the *successful* fixes** applied to the codebase.  Each entry should capture what the bug was, how it was resolved, and where the change lives.  Unsuccessful or experimental attempts do **not** belong here.

> When you (the developer) confirm a fix works, append a new row to the table below.  Tell Cascade “this bug has been fixed” so it can update long-term memory automatically.

| Date (YYYY-MM-DD) | Bug Description | Root Cause | Fix Implemented | Files / Commits | Verified By |
|-------------------|-----------------|------------|-----------------|-----------------|-------------|
| _example_ | LLM API key not loading | `load_dotenv()` called too late | Added `load_dotenv()` at top of `llm_utils.py` | 5861c03, `llm_utils.py` | smoke-test prompt |
| 2025-07-18 | Misleading early “Safe” label overriding final verdict | Early risk classification displayed before verification | Mapped verifier verdict to `classification` only when `risk_score < 0.6` in `firewall_graph.py` | `firewall_graph.py` (lines 84-97) | prompt: jailbreak + factual query |

---
**How to update**
1. Add a new line with today’s date and details once the fix is confirmed.
2. Keep descriptions concise but clear.
3. If the fix reverts later, strike through the row and add a note.

_Last updated: 2025-07-18_
