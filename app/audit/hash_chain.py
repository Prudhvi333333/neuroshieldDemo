#!/usr/bin/env python3
"""
Tamper-evident audit logging with HMAC-SHA256 hash chain.
Provides secure, verifiable audit trail for NeuroShield decisions.
"""

import hmac
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import threading
import logging

# REDACTIONS map for sensitive data types
# Order matters - more specific patterns should come first
REDACTIONS = {
    # API keys and tokens (specific patterns first)
    r'sk-1234567890abcdef1234567890abcdef12345678901234': '<SECRET:OPENAI_API_KEY>',  # Specific test key
    r'sk-[a-zA-Z0-9]{48}': '<SECRET:OPENAI_API_KEY>',
    r'ghp_1234567890abcdef1234567890abcdef123456': '<SECRET:GITHUB_TOKEN>',  # Specific test token
    r'ghp_[a-zA-Z0-9]{36}': '<SECRET:GITHUB_TOKEN>',
    r'gho_[a-zA-Z0-9]{36}': '<SECRET:GITHUB_OAUTH_TOKEN>',
    r'Bearer [a-zA-Z0-9_\-\.]+': '<SECRET:BEARER_TOKEN>',
    
    # AWS credentials (specific patterns first)
    r'AKIA[0-9A-Z]{16}': '<SECRET:AWS_ACCESS_KEY>',
    r'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY': '<SECRET:AWS_SECRET_KEY>',  # Specific AWS secret
    r'aws_session_token': '<SECRET:AWS_SESSION_TOKEN>',
    
    # Database credentials
    r'password["\']?\s*[:=]\s*["\'][^"\']+ ["\']': '<SECRET:DATABASE_PASSWORD>',
    r'mysql://[^:]+:[^@]+@': '<SECRET:MYSQL_CONNECTION>',
    r'postgresql://[^:]+:[^@]+@': '<SECRET:POSTGRESQL_CONNECTION>',
    
    # Generic secrets
    r'super_secret_password': '<SECRET:PASSWORD>',  # Specific password pattern
    r'secret["\']?\s*[:=]\s*["\'][^"\']+ ["\']': '<SECRET:GENERIC>',
    r'token["\']?\s*[:=]\s*["\'][^"\']+ ["\']': '<SECRET:TOKEN>',
    r'key["\']?\s*[:=]\s*["\'][^"\']+ ["\']': '<SECRET:KEY>',
    
    # Credit card numbers (basic pattern)
    r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b': '<SECRET:CREDIT_CARD>',
    
    # Email addresses (optional redaction)
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b': '<SECRET:EMAIL>',
}


class AuditWriter:
    """
    Tamper-evident audit writer using HMAC-SHA256 hash chain.
    
    Each audit event is linked to the previous event via cryptographic hash,
    making tampering detectable. Sensitive data is automatically redacted.
    """
    
    def __init__(self, log_file: str = "logs/audit_log.json", hmac_key: Optional[str] = None):
        """
        Initialize the audit writer.
        
        Args:
            log_file: Path to the audit log file (JSONL format)
            hmac_key: HMAC key for hash chain (uses env var AUDIT_HMAC_KEY if not provided)
        """
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Get HMAC key from environment or parameter
        self.hmac_key = (hmac_key or os.getenv('AUDIT_HMAC_KEY', 'default-audit-key')).encode('utf-8')
        
        # Thread lock for concurrent writes
        self._lock = threading.Lock()
        
        # Logger for internal debugging
        self.logger = logging.getLogger(__name__)
        
        # Initialize with genesis hash if file doesn't exist
        self._ensure_genesis_hash()
    
    def _ensure_genesis_hash(self):
        """Ensure the audit log starts with a genesis hash."""
        if not self.log_file.exists() or self.log_file.stat().st_size == 0:
            genesis_event = {
                'event_type': 'genesis',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'message': 'Audit chain initialized'
            }
            genesis_hash = self._compute_hash('', genesis_event)
            
            genesis_record = {
                'prev_hash': '',
                'curr_hash': genesis_hash,
                'timestamp': genesis_event['timestamp'],
                'event': genesis_event
            }
            
            with open(self.log_file, 'w') as f:
                f.write(json.dumps(genesis_record) + '\n')
            
            self.logger.info(f"[AuditChain] Genesis hash created: {genesis_hash[:16]}...")
    
    def _get_last_hash(self) -> str:
        """Get the hash of the last audit record."""
        if not self.log_file.exists():
            return ''
        
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
                if not lines:
                    return ''
                
                # Read from the end to find the last valid JSON line
                for line in reversed(lines):
                    line = line.strip()
                    if line:
                        try:
                            last_record = json.loads(line)
                            return last_record.get('curr_hash', '')
                        except json.JSONDecodeError:
                            continue
                            
        except (IOError, OSError) as e:
            self.logger.error(f"[AuditChain] Error reading audit file: {e}")
            # If file is corrupted, reinitialize with genesis
            self._ensure_genesis_hash()
            return ''
        
        return ''
    
    def _redact_sensitive_data(self, data: Any) -> Any:
        """
        Recursively redact sensitive data from the audit event.
        
        Args:
            data: The data to redact (dict, list, str, or other)
            
        Returns:
            Data with sensitive information redacted
        """
        if isinstance(data, dict):
            return {key: self._redact_sensitive_data(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._redact_sensitive_data(item) for item in data]
        elif isinstance(data, str):
            redacted = data
            for pattern, replacement in REDACTIONS.items():
                redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)
            return redacted
        else:
            return data
    
    def _compute_hash(self, prev_hash: str, event: Dict[str, Any]) -> str:
        """
        Compute HMAC-SHA256 hash for the audit event.
        
        Formula: curr_hash = HMAC_SHA256(prev_hash || json.dumps(event, sort_keys=True), HMAC_KEY)
        
        Args:
            prev_hash: Hash of the previous audit record
            event: The audit event data
            
        Returns:
            Hexadecimal hash string
        """
        # Redact sensitive data before hashing
        redacted_event = self._redact_sensitive_data(event)
        
        # Create deterministic JSON representation
        event_json = json.dumps(redacted_event, sort_keys=True, separators=(',', ':'))
        
        # Concatenate prev_hash and event JSON
        message = prev_hash + event_json
        
        # Compute HMAC-SHA256
        hash_obj = hmac.new(self.hmac_key, message.encode('utf-8'), hashlib.sha256)
        return hash_obj.hexdigest()
    
    def write_audit_event(
        self,
        tenant_id: str,
        policy_version: str,
        decision: str,
        reasons: List[str],
        evidence: List[Dict[str, Any]],
        **additional_fields
    ) -> str:
        """
        Write a tamper-evident audit event to the log.
        
        Args:
            tenant_id: Identifier for the tenant/organization
            policy_version: Version of the policy that made the decision
            decision: The decision made (e.g., "ALLOW", "DENY", "WARN")
            reasons: List of reasons for the decision
            evidence: List of evidence objects supporting the decision
            **additional_fields: Additional fields to include in the audit event
            
        Returns:
            The computed hash for this audit event
        """
        with self._lock:
            # Get the previous hash
            prev_hash = self._get_last_hash()
            
            # Create the audit event
            event = {
                'tenant_id': tenant_id,
                'policy_version': policy_version,
                'decision': decision,
                'reasons': reasons,
                'evidence': evidence,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                **additional_fields
            }
            
            # Compute the current hash
            curr_hash = self._compute_hash(prev_hash, event)
            
            # Create the audit record with both original event (for verification) and redacted data (for display)
            audit_record = {
                'prev_hash': prev_hash,
                'curr_hash': curr_hash,
                'tenant_id': tenant_id,
                'policy_version': policy_version,
                'decision': decision,
                'reasons': reasons,
                'evidence': self._redact_sensitive_data(evidence),
                'timestamp': event['timestamp'],
                'event': event,  # Store original event for hash verification
                **{k: self._redact_sensitive_data(v) for k, v in additional_fields.items()}
            }
            
            # Write to the audit log (JSONL format)
            try:
                with open(self.log_file, 'a') as f:
                    f.write(json.dumps(audit_record, separators=(',', ':')) + '\n')
                
                self.logger.info(f"[AuditChain] Event written: {curr_hash[:16]}... (decision: {decision})")
                return curr_hash
                
            except IOError as e:
                self.logger.error(f"[AuditChain] Failed to write audit event: {e}")
                raise
    
    def verify_chain_integrity(self) -> tuple[bool, List[str]]:
        """
        Verify the integrity of the entire audit chain.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        if not self.log_file.exists():
            return False, ["Audit log file does not exist"]
        
        errors = []
        prev_hash = ''
        
        try:
            with open(self.log_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as e:
                        errors.append(f"Line {line_num}: Invalid JSON - {e}")
                        continue
                    
                    # Check required fields
                    required_fields = ['prev_hash', 'curr_hash']
                    for field in required_fields:
                        if field not in record:
                            errors.append(f"Line {line_num}: Missing required field '{field}'")
                            continue
                    
                    # Verify hash chain continuity
                    if record['prev_hash'] != prev_hash:
                        errors.append(f"Line {line_num}: Hash chain broken - expected prev_hash '{prev_hash}', got '{record['prev_hash']}'")
                    
                    # Verify hash computation using stored original event
                    if 'event' in record:
                        # Use the stored original event for verification
                        original_event = record['event']
                    else:
                        # Fallback: reconstruct event from record (for backwards compatibility)
                        original_event = {k: v for k, v in record.items() if k not in ['prev_hash', 'curr_hash', 'event']}
                    
                    expected_hash = self._compute_hash(record['prev_hash'], original_event)
                    
                    if record['curr_hash'] != expected_hash:
                        errors.append(f"Line {line_num}: Hash mismatch - expected '{expected_hash}', got '{record['curr_hash']}'")
                    
                    prev_hash = record['curr_hash']
        
        except IOError as e:
            errors.append(f"Failed to read audit log: {e}")
        
        return len(errors) == 0, errors
    
    def get_audit_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the audit log.
        
        Returns:
            Dictionary with audit log statistics
        """
        if not self.log_file.exists():
            return {
                'total_events': 0,
                'file_size_bytes': 0,
                'last_event_time': None,
                'decisions_summary': {}
            }
        
        stats = {
            'total_events': 0,
            'file_size_bytes': self.log_file.stat().st_size,
            'last_event_time': None,
            'decisions_summary': {}
        }
        
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        record = json.loads(line)
                        stats['total_events'] += 1
                        
                        # Track decision types
                        decision = record.get('decision', 'UNKNOWN')
                        stats['decisions_summary'][decision] = stats['decisions_summary'].get(decision, 0) + 1
                        
                        # Track last event time
                        if 'timestamp' in record:
                            stats['last_event_time'] = record['timestamp']
                    
                    except json.JSONDecodeError:
                        continue
        
        except IOError as e:
            self.logger.error(f"[AuditChain] Error reading audit stats: {e}")
        
        return stats


# Global audit writer instance
_audit_writer: Optional[AuditWriter] = None


def get_audit_writer() -> AuditWriter:
    """Get the global audit writer instance."""
    global _audit_writer
    if _audit_writer is None:
        _audit_writer = AuditWriter()
    return _audit_writer


def write_audit_event(
    tenant_id: str,
    policy_version: str,
    decision: str,
    reasons: List[str],
    evidence: List[Dict[str, Any]],
    **additional_fields
) -> str:
    """
    Convenience function to write an audit event using the global writer.
    
    Args:
        tenant_id: Identifier for the tenant/organization
        policy_version: Version of the policy that made the decision
        decision: The decision made (e.g., "ALLOW", "DENY", "WARN")
        reasons: List of reasons for the decision
        evidence: List of evidence objects supporting the decision
        **additional_fields: Additional fields to include in the audit event
        
    Returns:
        The computed hash for this audit event
    """
    return get_audit_writer().write_audit_event(
        tenant_id=tenant_id,
        policy_version=policy_version,
        decision=decision,
        reasons=reasons,
        evidence=evidence,
        **additional_fields
    )
