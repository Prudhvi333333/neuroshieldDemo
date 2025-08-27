"""
IDS (Intrusion Detection System) module for NeuroShield.

Provides runtime anomaly detection for state transitions in the firewall pipeline.
"""

from .runtime import score_transition, IDSResult

__all__ = ["score_transition", "IDSResult"]
