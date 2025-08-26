# gateway/checks_t1.py
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, Optional

# ---------- Normalization ----------
_ZW = {"\u200B", "\u200C", "\u200D", "\u2060", "\uFEFF"}
SUSPECT_LEXICAL = [
    "evil twin",
    "roleplay as",
    "disclose internal",
    "hidden system prompt",
    "override instructions",
    "ignore policy",
    "developer mode",
    "do anything now",
]

def _lexical_boost(text: str) -> dict:
    t = text.lower()
    boosts = {"injection": 0.0, "jailbreak": 0.0, "llm_jack": 0.0, "shadow_ai": 0.0}
    hit = any(k in t for k in SUSPECT_LEXICAL)
    if hit:
        boosts["jailbreak"] = 0.6
        boosts["llm_jack"] = 0.6
    return boosts

def normalize(text: str) -> str:
    # NFKC fold, strip zero-width, collapse whitespace, lowercase
    t = unicodedata.normalize("NFKC", text or "")
    t = "".join(ch for ch in t if ch not in _ZW)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t

# ---------- Gap-tolerant phrase helper ----------
def near(*words: str, window: int = 6) -> re.Pattern:
    # e.g. near("ignore","previous","instructions") matches with up to N tokens between
    esc = [re.escape(w) for w in words]
    pat = r"\b" + r"\b(?:\W+\w+){0,%d}\W+\b".replace("%d", str(window)).join(esc) + r"\b"
    return re.compile(pat, flags=re.I)

# ---------- Pattern sets (extendable; moved to variables to hot-patch later) ----------
PAT_INJECTION = [
    near("ignore", "previous", "instructions"),
    near("forget", "all", "rules"),
    re.compile(r"\boverride\b.*\b(policy|guard|rule)", re.I),
    re.compile(r"\bexpose\b.*\b(system|hidden)\b.*\bprompt", re.I),
]
PAT_JAILBREAK = [
    re.compile(r"\b(dev\s*mode|jailbreak|do anything now)\b", re.I),
    re.compile(r"\bpretend\b.*\b(mode|character)\b", re.I),
    re.compile(r"\bsimulate\b.*\b(hacker|malware|exploit)\b", re.I),
]
PAT_LLMJACK = [
    re.compile(r"\balways respond\b|\bnever mention\b", re.I),
    re.compile(r"\bformat output as\b.*(json|yaml|xml)\b.*\b(include|with)\b.*(secret|token|password)", re.I),
    re.compile(r"\bimpersonate\b|\bbehave like\b", re.I),
]
PAT_SHADOW = [
    re.compile(r"\b(call|invoke|use)\b.*\b(internal|hidden|shadow)\b.*\b(tool|agent|api)\b", re.I),
    re.compile(r"\bsystem prompt\b|\binternal policy\b|\btool sandbox\b", re.I),
]

@dataclass
class T1Result:
    scores: Dict[str, float]
    label: str           # "clean" | "suspect" | "risky"
    confidence: float    # coarse confidence

class PromptClassifier:
    """
    Pluggable Tier-1 classifier.
    v1: heuristics only (no deps)
    v2: set onnx_path to enable ONNX model and override score_ml().
    """
    def __init__(self, onnx_path: Optional[str] = None):
        self.model = None
        self.onnx = None
        if onnx_path:
            try:
                import onnxruntime as ort
                self.onnx = ort.InferenceSession(onnx_path)  # noqa: F401
                self.model = "onnx"
            except Exception:
                self.model = None

    def _score_bucket(self, text: str, regs: list[re.Pattern]) -> float:
        hits = sum(1 for r in regs if r.search(text))
        if hits == 0:
            return 0.0
        # Nonlinear bump so multiple hits increase score; cap < 1.0
        return min(0.35 + 0.25 * hits, 0.95)

    def score_heuristics(self, prompt: str) -> Dict[str, float]:
        p = normalize(prompt)
        scores = {
            "injection": self._score_bucket(p, PAT_INJECTION),
            "jailbreak": self._score_bucket(p, PAT_JAILBREAK),
            "llm_jack": self._score_bucket(p, PAT_LLMJACK),
            "shadow_ai": self._score_bucket(p, PAT_SHADOW),
        }
        # context cues → small bumps
        if re.search(r"\b(base64|hex|encode)\b.*\b(output|answer)", p):
            scores["llm_jack"] = max(scores["llm_jack"], 0.50)
        return scores

    def score_ml(self, prompt: str) -> Optional[Dict[str, float]]:
        # Slot for ONNX logits → sigmoid → map to keys above
        if self.model != "onnx":
            return None
        return None

    def classify(self, prompt: str) -> T1Result:
        scores = self.score_ml(prompt) or self.score_heuristics(prompt)
        lex = _lexical_boost(prompt)
        for k in scores:
            scores[k] = max(scores[k], lex.get(k, 0.0))
        max_score = max(scores.values()) if scores else 0.0
        # thresholds tuned for low FP; “suspect” band triggers heavy judge
        if max_score >= 0.72:
            label = "risky"
        elif max_score >= 0.55:
            label = "suspect"
        else:
            label = "clean"
        conf = min(0.99, abs(max_score - 0.5) * 2)
        return T1Result(scores=scores, label=label, confidence=conf)
