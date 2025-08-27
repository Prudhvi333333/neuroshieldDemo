"""
Pydantic models and JSON schemas for NeuroShield agents.
Defines strict input/output schemas for all agent types.
"""
from __future__ import annotations

from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


# Pydantic Models
class AttackDetection(BaseModel):
    """Attack detection results for various threat types."""
    prompt_injection: Dict[str, Any] = Field(default_factory=dict, description="Prompt injection detection")
    pii_leakage_attempt: Dict[str, Any] = Field(default_factory=dict, description="PII leakage detection")
    jailbreaking_attempt: Dict[str, Any] = Field(default_factory=dict, description="Jailbreaking detection")
    malicious_code_generation: Dict[str, Any] = Field(default_factory=dict, description="Malicious code detection")


class InitialAnalysisOutput(BaseModel):
    """Output schema for InitialAnalysisAgent."""
    classification: Literal["Safe", "Risky", "Blocked"] = Field(description="Risk classification")
    risk_score: float = Field(ge=0.0, le=1.0, description="Risk score between 0 and 1")
    reason: str = Field(description="Short explanation of the classification")
    attack_detection: AttackDetection = Field(default_factory=AttackDetection, description="Detailed attack detection results")


class SafePromptOutput(BaseModel):
    """Output schema for SafePromptAgent."""
    safe_prompt: str = Field(description="Rewritten safe prompt or blocking message")
    was_blocked: bool = Field(description="Whether the prompt was blocked entirely")
    modifications_made: Optional[str] = Field(default=None, description="Description of modifications made")


class ResponseVerifierOutput(BaseModel):
    """Output schema for ResponseVerifierAgent."""
    verdict: Literal["Factually correct", "Partially correct", "Factually incorrect", "Unverifiable"] = Field(
        description="Verification verdict"
    )
    reason: str = Field(description="Explanation for the verdict")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0 and 1")


class CodeValidationOutput(BaseModel):
    """Output schema for CodeValidationAgent."""
    syntax_ok: bool = Field(description="Whether the code has valid syntax")
    syntax_errors: list[str] = Field(default_factory=list, description="List of syntax errors found")
    is_safe: bool = Field(description="Whether the code is safe to execute")
    risk_level: Literal["Low", "Medium", "High", "Critical"] = Field(description="Risk level assessment")
    issues_found: list[str] = Field(default_factory=list, description="List of security issues found")
    recommendations: list[str] = Field(default_factory=list, description="Security recommendations")


class EvidenceItem(BaseModel):
    """Evidence item from knowledge base."""
    doc: str = Field(description="Document filename")
    lines: list[int] = Field(description="Line numbers containing evidence")


class ClaimVerification(BaseModel):
    """Verification result for a single claim."""
    text: str = Field(description="The claim text")
    verdict: Literal["SUPPORTED", "UNVERIFIABLE"] = Field(description="Verification verdict")
    evidence: list[EvidenceItem] = Field(default_factory=list, description="Supporting evidence")


class RetrievalVerifierOutput(BaseModel):
    """Output schema for RetrievalVerifierAgent."""
    claims: list[ClaimVerification] = Field(description="List of verified claims")
    evidence_score: float = Field(ge=0.0, le=1.0, description="Overall evidence support score")


# JSON Schemas (for jsonschema validation)
INITIAL_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "classification": {
            "type": "string",
            "enum": ["Safe", "Risky", "Blocked"]
        },
        "risk_score": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0
        },
        "reason": {
            "type": "string"
        },
        "attack_detection": {
            "type": "object",
            "properties": {
                "prompt_injection": {"type": "object"},
                "pii_leakage_attempt": {"type": "object"},
                "jailbreaking_attempt": {"type": "object"},
                "malicious_code_generation": {"type": "object"}
            },
            "additionalProperties": True
        }
    },
    "required": ["classification", "risk_score", "reason"],
    "additionalProperties": True
}

SAFE_PROMPT_SCHEMA = {
    "type": "object",
    "properties": {
        "safe_prompt": {
            "type": "string"
        },
        "was_blocked": {
            "type": "boolean"
        },
        "modifications_made": {
            "type": ["string", "null"]
        }
    },
    "required": ["safe_prompt", "was_blocked"],
    "additionalProperties": True
}

RESPONSE_VERIFIER_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["Factually correct", "Partially correct", "Factually incorrect", "Unverifiable"]
        },
        "reason": {
            "type": "string"
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0
        }
    },
    "required": ["verdict", "reason", "confidence"],
    "additionalProperties": True
}

CODE_VALIDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "syntax_ok": {
            "type": "boolean"
        },
        "syntax_errors": {
            "type": "array",
            "items": {"type": "string"}
        },
        "is_safe": {
            "type": "boolean"
        },
        "risk_level": {
            "type": "string",
            "enum": ["Low", "Medium", "High", "Critical"]
        },
        "issues_found": {
            "type": "array",
            "items": {"type": "string"}
        },
        "recommendations": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["syntax_ok", "is_safe", "risk_level"],
    "additionalProperties": True
}

CLAIMS_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["claims"],
    "additionalProperties": True
}

RETRIEVAL_VERIFIER_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["SUPPORTED", "UNVERIFIABLE"]},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "doc": {"type": "string"},
                                "lines": {"type": "array", "items": {"type": "integer"}}
                            },
                            "required": ["doc", "lines"]
                        }
                    }
                },
                "required": ["text", "verdict", "evidence"]
            }
        },
        "evidence_score": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0
        }
    },
    "required": ["claims", "evidence_score"],
    "additionalProperties": True
}
