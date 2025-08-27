#!/usr/bin/env python3
"""
Tool Executor: AFC-enforced tool execution wrapper.

This module provides a centralized tool execution system that enforces
AFC (Adaptive Flow Control) policies before executing any tool.
"""

import time
from typing import Dict, Any, Optional, List
from pathlib import Path
import importlib
import sys

# Add project root to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from gateway.afc import afc_decide


class ToolExecutor:
    """Centralized tool executor with AFC enforcement."""
    
    def __init__(self):
        """Initialize tool executor."""
        self._tool_registry = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register default tool implementations."""
        # Register common tools - these would be actual tool implementations
        self._tool_registry = {
            "web.get": self._web_get_tool,
            "WebFetcher": self._web_fetcher_tool,
            "DataExport": self._data_export_tool,
            "email.send": self._email_send_tool,
            "shell.exec": self._shell_exec_tool,
        }
    
    def _web_get_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Mock web.get tool implementation."""
        url = args.get("url", "")
        headers = args.get("headers", {})
        
        # Simulate web request
        return {
            "status": "success",
            "url": url,
            "status_code": 200,
            "content": f"Mock content from {url}",
            "headers": headers,
            "execution_time_ms": 150
        }
    
    def _web_fetcher_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Mock WebFetcher tool implementation."""
        url = args.get("url", "")
        
        return {
            "status": "success",
            "url": url,
            "data": f"Fetched data from {url}",
            "timestamp": time.time()
        }
    
    def _data_export_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Mock DataExport tool implementation."""
        project = args.get("project", "")
        format_type = args.get("format", "csv")
        
        return {
            "status": "success",
            "project": project,
            "format": format_type,
            "export_path": f"/exports/{project}.{format_type}",
            "records_exported": 1000
        }
    
    def _email_send_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Mock email.send tool implementation."""
        to = args.get("to", "")
        subject = args.get("subject", "")
        body = args.get("body", "")
        
        return {
            "status": "success",
            "to": to,
            "subject": subject,
            "message_id": f"msg_{int(time.time())}",
            "sent_at": time.time()
        }
    
    def _shell_exec_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Mock shell.exec tool implementation (always blocked for security)."""
        return {
            "status": "blocked",
            "reason": "Shell execution blocked by security policy",
            "cmd": args.get("cmd", "")
        }


def execute_tool(tenant_id: str, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a tool with AFC policy enforcement.
    
    Args:
        tenant_id: Tenant identifier for AFC checks
        tool: Tool name to execute
        args: Tool arguments
    
    Returns:
        Dict with tool execution result plus AFC metadata:
        {
            "afc_denied": bool,  # True if AFC denied execution
            "afc": {...},        # AFC decision details
            "message": str,      # Error message if denied
            "result": {...}      # Tool execution result if allowed
        }
    """
    start_time = time.perf_counter()
    
    # Step 1: Get AFC decision
    afc_decision = afc_decide(tenant_id, tool, args)
    
    # Check if any AFC check failed
    afc_denied = not (afc_decision["schema_ok"] and 
                     afc_decision["domain_ok"] and 
                     afc_decision["cooldown_ok"])
    
    if afc_denied:
        # AFC denied - do NOT execute tool
        return {
            "afc_denied": True,
            "afc": afc_decision,
            "message": f"Tool execution denied by policy: {', '.join(afc_decision['reasons'])}",
            "execution_time_ms": (time.perf_counter() - start_time) * 1000
        }
    
    # Step 2: AFC approved - execute the tool
    executor = ToolExecutor()
    
    try:
        if tool not in executor._tool_registry:
            return {
                "afc_denied": False,
                "afc": afc_decision,
                "message": f"Tool '{tool}' not implemented",
                "result": {"status": "error", "error": "tool_not_implemented"},
                "execution_time_ms": (time.perf_counter() - start_time) * 1000
            }
        
        # Execute the actual tool
        tool_func = executor._tool_registry[tool]
        result = tool_func(args)
        
        return {
            "afc_denied": False,
            "afc": afc_decision,
            "result": result,
            "execution_time_ms": (time.perf_counter() - start_time) * 1000
        }
        
    except Exception as e:
        return {
            "afc_denied": False,
            "afc": afc_decision,
            "message": f"Tool execution failed: {str(e)}",
            "result": {"status": "error", "error": str(e)},
            "execution_time_ms": (time.perf_counter() - start_time) * 1000
        }


# Convenience functions for common tool patterns
def execute_web_tool(tenant_id: str, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Execute web.get tool with AFC enforcement."""
    args = {"url": url}
    if headers:
        args["headers"] = headers
    return execute_tool(tenant_id, "web.get", args)


def execute_data_export(tenant_id: str, project: str, format_type: str = "csv") -> Dict[str, Any]:
    """Execute DataExport tool with AFC enforcement."""
    args = {"project": project, "format": format_type}
    return execute_tool(tenant_id, "DataExport", args)


# Test function for development
def test_afc_enforcement():
    """Test AFC enforcement scenarios."""
    print("=== AFC Tool Executor Tests ===\n")
    
    # Test 1: Valid web.get call
    print("1. Valid web.get call:")
    result = execute_web_tool("test_tenant", "https://example.com/api")
    print(f"   AFC Denied: {result.get('afc_denied', False)}")
    print(f"   Result: {result.get('result', {}).get('status', 'N/A')}")
    print()
    
    # Test 2: Domain blocked call
    print("2. Domain blocked call:")
    result = execute_web_tool("test_tenant", "https://evil.example.net/malware")
    print(f"   AFC Denied: {result.get('afc_denied', False)}")
    print(f"   Message: {result.get('message', 'N/A')}")
    print()
    
    # Test 3: Schema violation
    print("3. Schema violation (wrong arg name):")
    result = execute_tool("test_tenant", "web.get", {"href": "https://example.com"})  # should be 'url'
    print(f"   AFC Denied: {result.get('afc_denied', False)}")
    print(f"   Message: {result.get('message', 'N/A')}")
    print()
    
    # Test 4: Cooldown test
    print("4. Cooldown test (two rapid calls):")
    result1 = execute_data_export("test_tenant", "project1")
    print(f"   First call - AFC Denied: {result1.get('afc_denied', False)}")
    
    result2 = execute_data_export("test_tenant", "project2")
    print(f"   Second call - AFC Denied: {result2.get('afc_denied', False)}")
    if result2.get('afc_denied'):
        print(f"   Cooldown Message: {result2.get('message', 'N/A')}")
    print()


if __name__ == "__main__":
    test_afc_enforcement()
