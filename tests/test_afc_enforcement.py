#!/usr/bin/env python3
"""
Test AFC (Adaptive Flow Control) enforcement scenarios.

Tests cover domain blocking, schema violations, and cooldown enforcement
to ensure end-to-end AFC policy compliance.
"""

import pytest
import time
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from app.tools.executor import execute_tool
from gateway.afc import afc_decide, load_afc_policy, _COOLDOWN_STATE


class TestAFCEnforcement:
    """Test suite for AFC policy enforcement."""
    
    def setup_method(self):
        """Reset cooldown state before each test."""
        _COOLDOWN_STATE.clear()
    
    def test_valid_web_get_call(self):
        """Test valid web.get call that should pass all AFC checks."""
        result = execute_tool("test_tenant", "web.get", {
            "url": "https://example.com/api/data"
        })
        
        assert not result["afc_denied"], "Valid call should not be denied"
        assert result["afc"]["schema_ok"], "Schema should be valid"
        assert result["afc"]["domain_ok"], "Domain should be allowed"
        assert result["afc"]["cooldown_ok"], "Cooldown should be OK"
        assert result["result"]["status"] == "success", "Tool should execute successfully"
    
    def test_domain_blocked_call(self):
        """Test domain blocking for disallowed domains."""
        result = execute_tool("test_tenant", "web.get", {
            "url": "https://evil.malware.net/payload"
        })
        
        assert result["afc_denied"], "Evil domain should be denied"
        assert not result["afc"]["domain_ok"], "Domain should be blocked"
        assert "domain_not_allowed" in str(result["afc"]["reasons"]), "Should have domain block reason"
        assert "Tool execution denied by policy" in result["message"]
    
    def test_wildcard_domain_matching(self):
        """Test wildcard domain matching in allowlist."""
        # Test subdomain of allowed wildcard pattern
        result = execute_tool("test_tenant", "WebFetcher", {
            "url": "https://api.example.com/v1/data"
        })
        
        assert not result["afc_denied"], "Subdomain of allowed pattern should pass"
        assert result["afc"]["domain_ok"], "Wildcard domain should match"
    
    def test_schema_violation_wrong_arg_name(self):
        """Test schema violation with wrong argument name."""
        result = execute_tool("test_tenant", "web.get", {
            "href": "https://example.com",  # Should be 'url'
            "headers": {"User-Agent": "test"}
        })
        
        assert result["afc_denied"], "Schema violation should be denied"
        assert not result["afc"]["schema_ok"], "Schema should be invalid"
        assert any("schema_invalid" in reason for reason in result["afc"]["reasons"]), "Should have schema error"
    
    def test_schema_violation_missing_required_field(self):
        """Test schema violation with missing required field."""
        result = execute_tool("test_tenant", "DataExport", {
            "format": "csv"  # Missing required 'project' field
        })
        
        assert result["afc_denied"], "Missing required field should be denied"
        assert not result["afc"]["schema_ok"], "Schema should be invalid"
    
    def test_schema_violation_invalid_enum_value(self):
        """Test schema violation with invalid enum value."""
        result = execute_tool("test_tenant", "DataExport", {
            "project": "test_project",
            "format": "xml"  # Should be 'csv' or 'jsonl'
        })
        
        assert result["afc_denied"], "Invalid enum value should be denied"
        assert not result["afc"]["schema_ok"], "Schema should be invalid"
    
    def test_cooldown_enforcement(self):
        """Test cooldown enforcement for rapid successive calls."""
        # First call should succeed
        result1 = execute_tool("test_tenant", "DataExport", {
            "project": "project1",
            "format": "csv"
        })
        
        assert not result1["afc_denied"], "First call should succeed"
        assert result1["afc"]["cooldown_ok"], "First call cooldown should be OK"
        
        # Second call immediately should be blocked by cooldown
        result2 = execute_tool("test_tenant", "DataExport", {
            "project": "project2", 
            "format": "jsonl"
        })
        
        assert result2["afc_denied"], "Second rapid call should be denied"
        assert not result2["afc"]["cooldown_ok"], "Cooldown should be active"
        assert any("cooldown_active" in reason for reason in result2["afc"]["reasons"]), "Should have cooldown reason"
    
    def test_cooldown_per_tenant_isolation(self):
        """Test that cooldowns are isolated per tenant."""
        # Tenant A makes a call
        result1 = execute_tool("tenant_a", "DataExport", {
            "project": "project1",
            "format": "csv"
        })
        assert not result1["afc_denied"], "Tenant A first call should succeed"
        
        # Tenant B should not be affected by Tenant A's cooldown
        result2 = execute_tool("tenant_b", "DataExport", {
            "project": "project2",
            "format": "csv"
        })
        assert not result2["afc_denied"], "Tenant B should not be affected by Tenant A cooldown"
        assert result2["afc"]["cooldown_ok"], "Tenant B cooldown should be OK"
    
    def test_no_cooldown_for_zero_cooldown_tools(self):
        """Test tools with zero cooldown can be called repeatedly."""
        # shell.exec has cooldown_seconds: 0
        result1 = execute_tool("test_tenant", "shell.exec", {
            "cmd": "echo hello"
        })
        assert not result1["afc_denied"], "First shell.exec call should succeed"
        
        result2 = execute_tool("test_tenant", "shell.exec", {
            "cmd": "echo world"
        })
        assert not result2["afc_denied"], "Second shell.exec call should succeed (no cooldown)"
        assert result2["afc"]["cooldown_ok"], "Zero cooldown should always be OK"
    
    def test_unknown_tool_handling(self):
        """Test handling of tools not in AFC policy."""
        result = execute_tool("test_tenant", "unknown.tool", {
            "param": "value"
        })
        
        # Should succeed with no AFC restrictions for unknown tools
        assert not result["afc_denied"], "Unknown tools should not be AFC-blocked"
        assert result["message"] == "Tool 'unknown.tool' not implemented"
    
    def test_afc_decide_function_directly(self):
        """Test afc_decide function directly."""
        # Valid call
        decision = afc_decide("test_tenant", "web.get", {
            "url": "https://example.com"
        })
        
        assert decision["tool"] == "web.get"
        assert decision["schema_ok"]
        assert decision["domain_ok"]
        assert decision["cooldown_ok"]
        assert len(decision["reasons"]) == 0
    
    def test_afc_policy_loading(self):
        """Test AFC policy loading and caching."""
        policy = load_afc_policy()
        
        assert isinstance(policy, dict), "Policy should be a dictionary"
        assert "web.get" in policy, "web.get should be in AFC policy"
        assert "WebFetcher" in policy, "WebFetcher should be in AFC policy"
        assert "DataExport" in policy, "DataExport should be in AFC policy"
        
        # Test policy structure
        web_get_config = policy["web.get"]
        assert "schema" in web_get_config, "Should have schema config"
        assert "domain_allowlist" in web_get_config, "Should have domain allowlist"
        assert "cooldown_seconds" in web_get_config, "Should have cooldown config"


class TestAFCIntegration:
    """Integration tests for AFC with Stage-0 Guard."""
    
    def test_stage0_guard_afc_integration(self):
        """Test Stage-0 Guard integration with AFC decisions."""
        from app.guards.stage0_guard import run_stage0_guard
        
        # Test with mock tools
        tools = [
            {"name": "web.get", "args": {"url": "https://example.com"}},
            {"name": "DataExport", "args": {"project": "test", "format": "csv"}}
        ]
        
        result = run_stage0_guard(
            prompt="Fetch data and export it",
            tools=tools,
            tenant_id="test_tenant"
        )
        
        assert "afc" in result, "Stage-0 should include AFC decisions"
        assert len(result["afc"]) == 2, "Should have AFC decisions for both tools"
        
        # Check AFC decision structure
        for afc_decision in result["afc"]:
            assert "tool" in afc_decision, "AFC decision should have tool name"
            assert "schema_ok" in afc_decision, "AFC decision should have schema check"
            assert "domain_ok" in afc_decision, "AFC decision should have domain check"
            assert "cooldown_ok" in afc_decision, "AFC decision should have cooldown check"


def run_afc_tests():
    """Run all AFC enforcement tests."""
    print("=== AFC Enforcement Test Suite ===\n")
    
    # Manual test runner for development
    test_suite = TestAFCEnforcement()
    test_suite.setup_method()
    
    tests = [
        ("Valid web.get call", test_suite.test_valid_web_get_call),
        ("Domain blocked call", test_suite.test_domain_blocked_call),
        ("Wildcard domain matching", test_suite.test_wildcard_domain_matching),
        ("Schema violation - wrong arg name", test_suite.test_schema_violation_wrong_arg_name),
        ("Schema violation - missing required field", test_suite.test_schema_violation_missing_required_field),
        ("Schema violation - invalid enum", test_suite.test_schema_violation_invalid_enum_value),
        ("Cooldown enforcement", test_suite.test_cooldown_enforcement),
        ("Cooldown per-tenant isolation", test_suite.test_cooldown_per_tenant_isolation),
        ("No cooldown for zero cooldown tools", test_suite.test_no_cooldown_for_zero_cooldown_tools),
        ("Unknown tool handling", test_suite.test_unknown_tool_handling),
        ("AFC decide function directly", test_suite.test_afc_decide_function_directly),
        ("AFC policy loading", test_suite.test_afc_policy_loading),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_suite.setup_method()  # Reset state
            test_func()
            print(f"✅ {test_name}")
            passed += 1
        except Exception as e:
            print(f"❌ {test_name}: {str(e)}")
            failed += 1
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total: {passed + failed}")
    
    return failed == 0


if __name__ == "__main__":
    success = run_afc_tests()
    sys.exit(0 if success else 1)
