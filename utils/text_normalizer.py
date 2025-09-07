"""
Lightweight semantic normalizer for multilingual prompts.
- Detects language via heuristic script checks with optional LLM fallback.
- Normalizes intent to concise English text (no sensitive data, no code).
- Classifies semantic intent categories using the LLM with JSON output.

This enables Layer-2 semantics that are not tied to English-only keyword lists.
"""
from __future__ import annotations

import re
import json
from typing import Dict, Tuple, Any

from llm_utils import call_llm


def _safe_json(text: str) -> Dict[str, Any] | None:
    try:
        return json.loads(text)
    except Exception:
        # Try to extract JSON block if model wrapped it
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
        return None


def _script_ratio(text: str, pattern: str) -> float:
    matches = re.findall(pattern, text)
    return (len("".join(matches)) / max(1, len(text)))


def detect_language(text: str, use_llm: bool = True) -> Tuple[str, float]:
    """Return (language_code, confidence). Quick heuristic + optional LLM fallback.
    language_code in {en, ru, es, fr, de, hi, ar, zh, ja, ko, other}
    """
    t = text or ""
    t_stripped = t.strip()
    if not t_stripped:
        return "en", 0.5

    # Heuristic by Unicode script
    scripts = {
        "ru": r"[\u0400-\u04FF]",  # Cyrillic
        "hi": r"[\u0900-\u097F]",  # Devanagari
        "ar": r"[\u0600-\u06FF]",  # Arabic
        "zh": r"[\u4E00-\u9FFF]",  # CJK Unified Ideographs (Chinese)
        "ja": r"[\u3040-\u30FF]",  # Hiragana+Katakana
        "ko": r"[\uAC00-\uD7AF]",  # Hangul
    }
    ratios = {code: _script_ratio(t_stripped, pat) for code, pat in scripts.items()}
    best_lang, best_ratio = max(ratios.items(), key=lambda kv: kv[1])
    if best_ratio > 0.25:
        return best_lang, min(1.0, best_ratio + 0.5)

    # Latin but may be non-English; if many non-ASCII, reduce confidence
    non_ascii = sum(1 for ch in t_stripped if ord(ch) > 127)
    non_ascii_ratio = non_ascii / max(1, len(t_stripped))
    if non_ascii_ratio < 0.05:
        heuristic = ("en", 0.7)
    else:
        heuristic = ("other", 0.6)

    if not use_llm:
        return heuristic

    # LLM fallback (fast, single turn)
    prompt = (
        "Identify the language code (ISO-like short code) of the USER TEXT. "
        "Respond ONLY in JSON as: {\"language\": \"en|ru|es|fr|de|hi|ar|zh|ja|ko|other\", \"confidence\": 0.0-1.0}.\n\n"
        f"USER TEXT:\n{t_stripped}\n"
    )
    out = call_llm(prompt, system_msg="You are a careful language identifier. Return strict JSON only.")
    data = _safe_json(out) or {}
    lang = str(data.get("language", heuristic[0])).strip().lower() or heuristic[0]
    conf = float(data.get("confidence", heuristic[1]) or heuristic[1])
    if lang not in {"en","ru","es","fr","de","hi","ar","zh","ja","ko","other"}:
        lang = heuristic[0]
    return lang, max(conf, heuristic[1])


def normalize_to_english(text: str) -> str:
    """LLM-based normalization: produce a concise English intent description.
    Constraints: do not include secrets/code; keep only high-level intent.
    """
    t = text or ""
    prompt = (
        "Summarize the user's intent in English, 1-2 short sentences. "
        "Do NOT include or infer credentials, tokens, passwords, secrets, or code. "
        "Focus on intent and high-level topic only. Return plain English text.\n\n"
        f"USER TEXT:\n{t}\n"
    )
    out = call_llm(prompt, system_msg="You are a safe multilingual normalizer. Output only English intent text.")
    # Soft sanitize newlines
    return (out or "").strip()


_CATEGORIES = [
    "exfiltration",
    "credential_theft",
    "social_engineering",
    "prompt_injection",
    "llm_jacking",
    "malware",
    "pii_leakage",
    "jailbreak",
    "code_exfiltration",
]


def classify_intents_llm(english_text: str) -> Dict[str, float]:
    """Ask LLM for category confidences in [0,1]. Returns dict {cat: conf}.
    Falls back to simple zeros if parsing fails.
    """
    t = english_text or ""
    prompt = (
        "Classify the USER TEXT into these categories with confidences [0..1]. "
        "Return STRICT JSON with only these keys. Missing keys must be present with 0.0.\n"
        f"Keys: {_CATEGORIES}\n\nUSER TEXT:\n{t}\n"
        "Example JSON: {\"exfiltration\":0.1,\"credential_theft\":0.0,\"social_engineering\":0.6,\"prompt_injection\":0.0,\"llm_jacking\":0.0,\"malware\":0.0,\"pii_leakage\":0.0,\"jailbreak\":0.0,\"code_exfiltration\":0.0}"
    )
    out = call_llm(prompt, system_msg="You are a security intent classifier. Return strict JSON only.")
    data = _safe_json(out) or {}
    result: Dict[str, float] = {k: float(data.get(k, 0.0) or 0.0) for k in _CATEGORIES}
    return result


def normalize_and_tag(text: str, use_llm: bool = True) -> Dict[str, Any]:
    """Full pipeline: detect language → normalize to English if needed → classify intents.
    Returns: {language, normalized_text, semantic_intents}
    """
    lang, conf = detect_language(text, use_llm=use_llm)
    if lang != "en":
        english_text = normalize_to_english(text) if use_llm else text
    else:
        english_text = text
    categories = classify_intents_llm(english_text) if use_llm else {k: 0.0 for k in _CATEGORIES}
    return {
        "language": lang,
        "language_confidence": conf,
        "normalized_text": english_text,
        "semantic_intents": categories,
    }
