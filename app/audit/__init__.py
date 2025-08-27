# app/audit/__init__.py
"""Audit module for tamper-evident logging."""

from .hash_chain import AuditWriter

__all__ = ['AuditWriter']
