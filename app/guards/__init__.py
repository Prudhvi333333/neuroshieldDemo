# app/guards/__init__.py
"""
Guards module for NeuroShield - fast deterministic security checks.
"""

from .stage0_guard import run_stage0_guard

__all__ = ['run_stage0_guard']
