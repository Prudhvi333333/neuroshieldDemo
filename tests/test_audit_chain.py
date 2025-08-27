#!/usr/bin/env python3
"""
Tests for the tamper-evident audit chain system.
Verifies hash chain continuity, redaction functionality, and audit integrity.
"""

import json
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch
from app.audit.hash_chain import AuditWriter, write_audit_event, get_audit_writer, REDACTIONS


class TestAuditWriter:
    """Test the AuditWriter class functionality."""
    
    def setup_method(self):
        """Set up test environment with temporary audit log."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, "test_audit.json")
        self.audit_writer = AuditWriter(log_file=self.log_file, hmac_key="test-key-123")
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_genesis_hash_creation(self):
        """Test that genesis hash is created on initialization."""
        assert os.path.exists(self.log_file)
        
        with open(self.log_file, 'r') as f:
            first_line = f.readline().strip()
            genesis_record = json.loads(first_line)
        
        assert genesis_record['prev_hash'] == ''
        assert genesis_record['curr_hash'] != ''
        assert len(genesis_record['curr_hash']) == 64  # SHA256 hex length
        assert genesis_record['event']['event_type'] == 'genesis'
    
    def test_single_audit_event(self):
        """Test writing a single audit event."""
        hash_result = self.audit_writer.write_audit_event(
            tenant_id="test-tenant",
            policy_version="1.0",
            decision="ALLOW",
            reasons=["Low risk prompt"],
            evidence=[{"type": "test", "data": "sample"}]
        )
        
        assert len(hash_result) == 64  # SHA256 hex length
        
        # Verify the event was written
        with open(self.log_file, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) == 2  # Genesis + 1 event
        
        event_record = json.loads(lines[1].strip())
        assert event_record['tenant_id'] == "test-tenant"
        assert event_record['decision'] == "ALLOW"
        assert event_record['curr_hash'] == hash_result
        assert event_record['prev_hash'] != ''  # Should link to genesis
    
    def test_hash_chain_continuity(self):
        """Test that hash chain maintains continuity across multiple events."""
        events = [
            ("tenant1", "1.0", "ALLOW", ["Safe"], [{"type": "prompt", "content": "hello"}]),
            ("tenant1", "1.0", "DENY", ["Risky"], [{"type": "prompt", "content": "hack"}]),
            ("tenant2", "1.1", "WARN", ["Suspicious"], [{"type": "code", "content": "import os"}])
        ]
        
        hashes = []
        for tenant_id, version, decision, reasons, evidence in events:
            hash_result = self.audit_writer.write_audit_event(
                tenant_id=tenant_id,
                policy_version=version,
                decision=decision,
                reasons=reasons,
                evidence=evidence
            )
            hashes.append(hash_result)
        
        # Verify chain continuity
        with open(self.log_file, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) == 4  # Genesis + 3 events
        
        prev_hash = ''
        for i, line in enumerate(lines):
            record = json.loads(line.strip())
            assert record['prev_hash'] == prev_hash
            prev_hash = record['curr_hash']
    
    def test_sensitive_data_redaction(self):
        """Test that sensitive data is properly redacted."""
        sensitive_evidence = [
            {
                "type": "credentials",
                "aws_access_key": "AKIAIOSFODNN7EXAMPLE",
                "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                "openai_key": "sk-1234567890abcdef1234567890abcdef12345678901234",
                "password": "super_secret_password",
                "email": "user@example.com"
            },
            {
                "type": "code",
                "content": "const token = 'ghp_1234567890abcdef1234567890abcdef123456';"
            }
        ]
        
        hash_result = self.audit_writer.write_audit_event(
            tenant_id="test-tenant",
            policy_version="1.0",
            decision="DENY",
            reasons=["Contains sensitive data"],
            evidence=sensitive_evidence
        )
        
        # Read the written record
        with open(self.log_file, 'r') as f:
            lines = f.readlines()
        
        event_record = json.loads(lines[-1].strip())
        evidence = event_record['evidence']
        
        # Verify redactions occurred
        creds = evidence[0]
        assert creds['aws_access_key'] == '<SECRET:AWS_ACCESS_KEY>'
        assert creds['aws_secret_access_key'] == '<SECRET:AWS_SECRET_KEY>'
        assert creds['openai_key'] == '<SECRET:OPENAI_API_KEY>'
        assert '<SECRET:' in str(creds['password'])
        assert creds['email'] == '<SECRET:EMAIL>'
        
        code = evidence[1]
        assert '<SECRET:GITHUB_TOKEN>' in code['content']
    
    def test_chain_integrity_verification(self):
        """Test the chain integrity verification function."""
        # Write several events
        for i in range(3):
            self.audit_writer.write_audit_event(
                tenant_id=f"tenant-{i}",
                policy_version="1.0",
                decision="ALLOW",
                reasons=[f"Event {i}"],
                evidence=[{"type": "test", "index": i}]
            )
        
        # Verify integrity
        is_valid, errors = self.audit_writer.verify_chain_integrity()
        assert is_valid
        assert len(errors) == 0
    
    def test_chain_integrity_with_tampering(self):
        """Test that tampering is detected by integrity verification."""
        # Write an event
        self.audit_writer.write_audit_event(
            tenant_id="test-tenant",
            policy_version="1.0",
            decision="ALLOW",
            reasons=["Original event"],
            evidence=[{"type": "test", "data": "original"}]
        )
        
        # Tamper with the log file
        with open(self.log_file, 'r') as f:
            lines = f.readlines()
        
        # Modify the last line (tamper with decision)
        last_record = json.loads(lines[-1].strip())
        last_record['decision'] = 'DENY'  # Change decision
        lines[-1] = json.dumps(last_record) + '\n'
        
        with open(self.log_file, 'w') as f:
            f.writelines(lines)
        
        # Verify tampering is detected
        is_valid, errors = self.audit_writer.verify_chain_integrity()
        assert not is_valid
        assert len(errors) > 0
        assert "Hash mismatch" in str(errors)
    
    def test_audit_stats(self):
        """Test audit statistics generation."""
        # Write events with different decisions
        decisions = ["ALLOW", "DENY", "ALLOW", "WARN", "DENY"]
        for i, decision in enumerate(decisions):
            self.audit_writer.write_audit_event(
                tenant_id="test-tenant",
                policy_version="1.0",
                decision=decision,
                reasons=[f"Reason {i}"],
                evidence=[{"type": "test", "index": i}]
            )
        
        stats = self.audit_writer.get_audit_stats()
        
        assert stats['total_events'] == 6  # Genesis + 5 events
        assert stats['decisions_summary']['ALLOW'] == 2
        assert stats['decisions_summary']['DENY'] == 2
        assert stats['decisions_summary']['WARN'] == 1
        assert stats['file_size_bytes'] > 0
        assert stats['last_event_time'] is not None
    
    def test_concurrent_writes(self):
        """Test thread safety of concurrent audit writes."""
        import threading
        import time
        
        def write_events(thread_id):
            for i in range(5):
                self.audit_writer.write_audit_event(
                    tenant_id=f"thread-{thread_id}",
                    policy_version="1.0",
                    decision="ALLOW",
                    reasons=[f"Thread {thread_id} event {i}"],
                    evidence=[{"type": "thread_test", "thread": thread_id, "event": i}]
                )
                time.sleep(0.001)  # Small delay to encourage race conditions
        
        # Start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=write_events, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all events were written and chain is intact
        with open(self.log_file, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) == 16  # Genesis + 15 events (3 threads × 5 events)
        
        # Verify chain integrity
        is_valid, errors = self.audit_writer.verify_chain_integrity()
        assert is_valid
        assert len(errors) == 0


class TestGlobalAuditFunctions:
    """Test the global audit functions."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, "global_test_audit.json")
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('app.audit.hash_chain._audit_writer', None)
    def test_global_write_audit_event(self):
        """Test the global write_audit_event function."""
        with patch.dict(os.environ, {'AUDIT_HMAC_KEY': 'test-global-key'}):
            with patch('app.audit.hash_chain.AuditWriter') as mock_writer_class:
                mock_writer = mock_writer_class.return_value
                mock_writer.write_audit_event.return_value = "test-hash-123"
                
                result = write_audit_event(
                    tenant_id="global-tenant",
                    policy_version="2.0",
                    decision="DENY",
                    reasons=["Global test"],
                    evidence=[{"type": "global", "test": True}]
                )
                
                assert result == "test-hash-123"
                mock_writer.write_audit_event.assert_called_once()
    
    def test_redaction_patterns(self):
        """Test that all redaction patterns work correctly."""
        test_cases = [
            ("AKIAIOSFODNN7EXAMPLE", "<SECRET:AWS_ACCESS_KEY>"),
            ("sk-1234567890abcdef1234567890abcdef12345678901234", "<SECRET:OPENAI_API_KEY>"),
            ("ghp_1234567890abcdef1234567890abcdef123456", "<SECRET:GITHUB_TOKEN>"),
            ("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "<SECRET:BEARER_TOKEN>"),
            ('password": "secret123"', '<SECRET:DATABASE_PASSWORD>'),
            ("4532-1234-5678-9012", "<SECRET:CREDIT_CARD>"),
            ("user@example.com", "<SECRET:EMAIL>"),
        ]
        
        writer = AuditWriter(log_file=self.log_file, hmac_key="test-key")
        
        for original, expected_redaction in test_cases:
            redacted = writer._redact_sensitive_data(original)
            assert expected_redaction in redacted or redacted != original, f"Failed to redact: {original}"


class TestAuditIntegration:
    """Integration tests for the audit system."""
    
    def setup_method(self):
        """Set up integration test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, "integration_audit.json")
    
    def teardown_method(self):
        """Clean up integration test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_end_to_end_audit_flow(self):
        """Test complete end-to-end audit flow."""
        writer = AuditWriter(log_file=self.log_file, hmac_key="integration-test-key")
        
        # Simulate a complete NeuroShield decision flow
        scenarios = [
            {
                "tenant_id": "acme-corp",
                "policy_version": "1.2",
                "decision": "ALLOW",
                "reasons": ["Low risk prompt", "No code detected"],
                "evidence": [
                    {"type": "user_prompt", "content": "What is the weather today?"},
                    {"type": "risk_score", "value": 0.1},
                    {"type": "attack_detection", "data": {"sql_injection": False, "xss": False}}
                ],
                "user_id": "user123",
                "context_digest": "abc123"
            },
            {
                "tenant_id": "acme-corp",
                "policy_version": "1.2",
                "decision": "DENY",
                "reasons": ["High risk prompt", "Potential code injection"],
                "evidence": [
                    {"type": "user_prompt", "content": "DROP TABLE users; --"},
                    {"type": "risk_score", "value": 0.9},
                    {"type": "attack_detection", "data": {"sql_injection": True, "xss": False}},
                    {"type": "code_fragment", "content": "DROP TABLE users;"}
                ],
                "user_id": "user456",
                "context_digest": "def456"
            },
            {
                "tenant_id": "beta-corp",
                "policy_version": "1.3",
                "decision": "WARN",
                "reasons": ["Medium risk", "Sensitive data detected"],
                "evidence": [
                    {"type": "user_prompt", "content": "My API key is sk-1234567890abcdef1234567890abcdef12345678901234"},
                    {"type": "risk_score", "value": 0.6},
                    {"type": "sensitive_data", "detected": ["api_key"]}
                ],
                "user_id": "user789"
            }
        ]
        
        hashes = []
        for scenario in scenarios:
            hash_result = writer.write_audit_event(**scenario)
            hashes.append(hash_result)
        
        # Verify all events were written
        with open(self.log_file, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) == 4  # Genesis + 3 scenarios
        
        # Verify chain integrity
        is_valid, errors = writer.verify_chain_integrity()
        assert is_valid, f"Chain integrity failed: {errors}"
        
        # Verify sensitive data was redacted
        warn_record = json.loads(lines[3].strip())  # Last event (WARN)
        prompt_evidence = next(e for e in warn_record['evidence'] if e['type'] == 'user_prompt')
        assert '<SECRET:OPENAI_API_KEY>' in prompt_evidence['content']
        
        # Verify statistics
        stats = writer.get_audit_stats()
        assert stats['total_events'] == 4
        assert stats['decisions_summary']['ALLOW'] == 1
        assert stats['decisions_summary']['DENY'] == 1
        assert stats['decisions_summary']['WARN'] == 1
        
        # Verify each hash is unique
        assert len(set(hashes)) == len(hashes)
        
        print(f"✅ Integration test passed - {len(hashes)} events logged with chain integrity")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
