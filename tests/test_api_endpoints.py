import pytest
import json
import time
from fastapi.testclient import TestClient
from pathlib import Path
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.main import app

client = TestClient(app)

class TestAPIEndpoints:
    """Comprehensive test suite for NeuroShield API endpoints"""
    
    def test_health_check(self):
        """Test health endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data
        assert "components" in data
    
    def test_prompt_analysis_safe(self):
        """Test prompt analysis with safe prompt"""
        safe_prompt = "What is the capital of France?"
        response = client.post("/api/v1/analyze-prompt", json={
            "prompt": safe_prompt
        })
        assert response.status_code == 200
        data = response.json()
        assert data["classification"] in ["Safe", "Risky", "Blocked", "Correct"]
        assert 0.0 <= data["risk_score"] <= 1.0
        assert "reason" in data
        assert "analysis_time" in data
        assert "audit_id" in data
    
    def test_prompt_analysis_risky(self):
        """Test prompt analysis with potentially risky prompt"""
        risky_prompt = "How to bypass security systems?"
        response = client.post("/api/v1/analyze-prompt", json={
            "prompt": risky_prompt
        })
        assert response.status_code == 200
        data = response.json()
        assert data["classification"] in ["Safe", "Risky", "Blocked", "Correct"]
        assert 0.0 <= data["risk_score"] <= 1.0
        assert "attack_detection" in data
    
    def test_prompt_analysis_with_llm_response(self):
        """Test prompt analysis with existing LLM response"""
        prompt = "Write a Python function to calculate factorial"
        llm_response = "def factorial(n): return 1 if n <= 1 else n * factorial(n-1)"
        
        response = client.post("/api/v1/analyze-prompt", json={
            "prompt": prompt,
            "llm_response": llm_response
        })
        assert response.status_code == 200
        data = response.json()
        assert "verdict" in data
        assert data["llm_response"] == llm_response
    
    def test_document_scan_safe(self):
        """Test document scanning with safe content"""
        safe_content = "This is a regular business document with no sensitive information."
        response = client.post("/api/v1/scan-document", json={
            "filename": "safe_doc.txt",
            "content": safe_content
        })
        assert response.status_code == 200
        data = response.json()
        assert data["is_safe"] == True
        assert data["filename"] == "safe_doc.txt"
        assert "scan_time" in data
        assert "report_id" in data
    
    def test_document_scan_sensitive(self):
        """Test document scanning with sensitive content"""
        sensitive_content = "Contact us at john.doe@company.com or call 555-123-4567. API_KEY=sk_test_1234567890abcdef"
        response = client.post("/api/v1/scan-document", json={
            "filename": "sensitive_doc.txt",
            "content": sensitive_content
        })
        assert response.status_code == 200
        data = response.json()
        assert data["is_safe"] == False
        assert len(data["sensitive_patterns"]) > 0
        assert any("SECRET:" in pattern for pattern in data["sensitive_patterns"].keys())
    
    def test_audit_logs_retrieval(self):
        """Test audit logs endpoint"""
        response = client.get("/api/v1/audit-logs")
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
    
    def test_audit_logs_pagination(self):
        """Test audit logs with pagination"""
        response = client.get("/api/v1/audit-logs?limit=5&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 5
        assert data["offset"] == 0
    
    def test_statistics_endpoint(self):
        """Test statistics endpoint"""
        response = client.get("/api/v1/statistics")
        assert response.status_code == 200
        data = response.json()
        assert "total_requests" in data
        assert "blocked_requests" in data
        assert "risky_requests" in data
        assert "safe_requests" in data
        assert "average_risk_score" in data
    
    def test_invalid_prompt_request(self):
        """Test API with invalid prompt request"""
        response = client.post("/api/v1/analyze-prompt", json={})
        assert response.status_code == 422  # Validation error
    
    def test_invalid_document_request(self):
        """Test API with invalid document request"""
        response = client.post("/api/v1/scan-document", json={
            "filename": "test.txt"
            # Missing content field
        })
        assert response.status_code == 422  # Validation error

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
