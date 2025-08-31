"""
API Client for NeuroShield FastAPI endpoints
Provides easy integration with the existing Streamlit UI
"""

import requests
import json
from typing import Dict, Any, Optional
import time

class NeuroShieldAPIClient:
    """Client for interacting with NeuroShield FastAPI endpoints"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health status"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    def analyze_prompt(self, prompt: str, llm_response: Optional[str] = None) -> Dict[str, Any]:
        """Analyze prompt for security threats"""
        try:
            payload = {"prompt": prompt}
            if llm_response:
                payload["llm_response"] = llm_response
            
            response = self.session.post(
                f"{self.base_url}/api/v1/analyze-prompt",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {
                "classification": "Error",
                "risk_score": 1.0,
                "reason": f"API Error: {str(e)}",
                "analysis_time": 0.0,
                "audit_id": "error",
                "error": True
            }
    
    def scan_document(self, filename: str, content: str) -> Dict[str, Any]:
        """Scan document content for sensitive information"""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/scan-document",
                json={"filename": filename, "content": content},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {
                "filename": filename,
                "is_safe": False,
                "sensitive_patterns": {},
                "scan_time": 0.0,
                "report_id": "error",
                "error": True
            }
    
    def get_audit_logs(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Retrieve audit logs with pagination"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/audit-logs",
                params={"limit": limit, "offset": offset},
                timeout=15
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"logs": [], "total": 0, "error": str(e)}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get security statistics and metrics"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/statistics", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {
                "total_requests": 0,
                "blocked_requests": 0,
                "risky_requests": 0,
                "safe_requests": 0,
                "average_risk_score": 0.0,
                "error": str(e)
            }

# Singleton instance for use across the application
api_client = NeuroShieldAPIClient()
