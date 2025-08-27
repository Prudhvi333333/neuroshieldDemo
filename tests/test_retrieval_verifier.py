"""
Unit tests for the RetrievalVerifier system.
Tests claims extraction, BM25 search, fuzzy matching, and evidence scoring.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.retrieval.retrieval_verifier import RetrievalVerifier, create_retrieval_verifier


class TestRetrievalVerifier:
    """Test the RetrievalVerifier with a tiny knowledge base."""
    
    @pytest.fixture
    def temp_kb(self):
        """Create a temporary knowledge base for testing."""
        temp_dir = tempfile.mkdtemp()
        kb_path = Path(temp_dir) / "kb" / "reviewed_docs"
        kb_path.mkdir(parents=True, exist_ok=True)
        
        # Create test documents
        doc1 = kb_path / "cybersecurity_basics.md"
        doc1.write_text("""# Security Fundamentals

## Authentication
Multi-factor authentication (MFA) requires two or more verification factors.
The three main factors are something you know, have, and are.

## Encryption
AES encryption is a symmetric encryption standard.
RSA is used for asymmetric encryption.
TLS provides secure communication over networks.

## Common Attacks
SQL injection occurs when malicious SQL code is inserted into queries.
Cross-site scripting (XSS) allows attackers to inject malicious scripts.
""")
        
        doc2 = kb_path / "ai_security.md"
        doc2.write_text("""# AI Security

## Prompt Injection
Prompt injection is a vulnerability where malicious input manipulates AI behavior.
Direct injection involves explicit instructions to ignore previous commands.

## Model Safety
Constitutional AI methods help align models with human values.
RLHF stands for Reinforcement Learning from Human Feedback.

## Data Privacy
AI systems must protect personally identifiable information (PII).
Differential privacy techniques help protect training data.
""")
        
        yield str(kb_path)
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    def test_initialization(self, temp_kb):
        """Test RetrievalVerifier initialization and indexing."""
        verifier = RetrievalVerifier(kb_path=temp_kb, threshold=0.6)
        
        assert verifier.kb_path == Path(temp_kb)
        assert verifier.threshold == 0.6
        assert len(verifier.documents) == 2
        assert "cybersecurity_basics.md" in verifier.documents
        assert "ai_security.md" in verifier.documents
    
    @patch('app.retrieval.retrieval_verifier.call_llm_json')
    def test_extract_claims(self, mock_llm, temp_kb):
        """Test claims extraction from model output."""
        verifier = RetrievalVerifier(kb_path=temp_kb)
        
        mock_llm.return_value = {
            "claims": [
                "MFA requires two verification factors",
                "AES is a symmetric encryption standard",
                "SQL injection is a common attack"
            ]
        }
        
        model_output = "Multi-factor authentication requires two factors. AES encryption is symmetric. SQL injection attacks are common."
        claims = verifier.extract_claims(model_output)
        
        assert len(claims) == 3
        assert "MFA requires two verification factors" in claims
        assert "AES is a symmetric encryption standard" in claims
        assert "SQL injection is a common attack" in claims
    
    @patch('app.retrieval.retrieval_verifier.call_llm_json')
    def test_extract_claims_failure(self, mock_llm, temp_kb):
        """Test claims extraction failure handling."""
        from app.utils.json_io import JsonParseError
        
        verifier = RetrievalVerifier(kb_path=temp_kb)
        mock_llm.side_effect = JsonParseError("Parse failed")
        
        claims = verifier.extract_claims("Some text")
        assert claims == []
    
    def test_search_claim_bm25(self, temp_kb):
        """Test BM25 search for claims."""
        verifier = RetrievalVerifier(kb_path=temp_kb)
        
        # Search for a claim that should match
        evidence = verifier.search_claim("multi-factor authentication")
        
        assert len(evidence) > 0
        doc_name, line_num, score = evidence[0]
        assert doc_name == "cybersecurity_basics.md"
        assert isinstance(line_num, int)
        assert score > 0
    
    def test_fuzzy_search_claim(self, temp_kb):
        """Test fuzzy search fallback."""
        verifier = RetrievalVerifier(kb_path=temp_kb, threshold=0.5)
        
        # Search for a slightly different phrasing
        evidence = verifier.fuzzy_search_claim("AES encryption is symmetric")
        
        assert len(evidence) > 0
        doc_name, line_num, score = evidence[0]
        assert doc_name == "cybersecurity_basics.md"
        assert score >= 0.5
    
    def test_verify_supported_claim(self, temp_kb):
        """Test verification of a supported claim."""
        verifier = RetrievalVerifier(kb_path=temp_kb, threshold=0.3)
        
        result = verifier.verify_claim("AES is a symmetric encryption standard")
        
        assert result["text"] == "AES is a symmetric encryption standard"
        assert result["verdict"] == "SUPPORTED"
        assert len(result["evidence"]) > 0
        assert result["evidence"][0]["doc"] == "cybersecurity_basics.md"
    
    def test_verify_unverifiable_claim(self, temp_kb):
        """Test verification of an unverifiable claim."""
        verifier = RetrievalVerifier(kb_path=temp_kb, threshold=0.8)
        
        result = verifier.verify_claim("Quantum computing will break all encryption")
        
        assert result["text"] == "Quantum computing will break all encryption"
        assert result["verdict"] == "UNVERIFIABLE"
        assert len(result["evidence"]) == 0
    
    @patch('app.retrieval.retrieval_verifier.call_llm_json')
    def test_verify_response_integration(self, mock_llm, temp_kb):
        """Test full response verification integration."""
        verifier = RetrievalVerifier(kb_path=temp_kb, threshold=0.4)
        
        # Mock claims extraction
        mock_llm.return_value = {
            "claims": [
                "AES is symmetric encryption",
                "SQL injection is dangerous",
                "Quantum computers are magical"  # This should be unverifiable
            ]
        }
        
        model_output = "AES encryption is symmetric. SQL injection attacks are dangerous. Quantum computers are magical."
        result = verifier.verify_response(model_output)
        
        assert "claims" in result
        assert "evidence_score" in result
        assert len(result["claims"]) == 3
        
        # Check individual claim verdicts
        verdicts = [claim["verdict"] for claim in result["claims"]]
        assert "SUPPORTED" in verdicts  # At least some claims should be supported
        assert "UNVERIFIABLE" in verdicts  # The quantum claim should be unverifiable
        
        # Evidence score should be between 0 and 1
        assert 0.0 <= result["evidence_score"] <= 1.0
    
    def test_verify_response_no_claims(self, temp_kb):
        """Test response verification with no extractable claims."""
        verifier = RetrievalVerifier(kb_path=temp_kb)
        
        with patch.object(verifier, 'extract_claims', return_value=[]):
            result = verifier.verify_response("Hello world")
            
            assert result["claims"] == []
            assert result["evidence_score"] == 0.0
    
    def test_create_retrieval_verifier_factory(self, temp_kb):
        """Test the factory function."""
        verifier = create_retrieval_verifier(kb_path=temp_kb, threshold=0.7)
        
        assert isinstance(verifier, RetrievalVerifier)
        assert verifier.threshold == 0.7
        assert verifier.kb_path == Path(temp_kb)


class TestRetrievalVerifierEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def temp_kb(self):
        """Create a temporary knowledge base for testing."""
        temp_dir = tempfile.mkdtemp()
        kb_path = Path(temp_dir) / "kb" / "reviewed_docs"
        kb_path.mkdir(parents=True, exist_ok=True)
        
        # Create test documents
        doc1 = kb_path / "cybersecurity_basics.md"
        doc1.write_text("""# Security Fundamentals

## Authentication
Multi-factor authentication (MFA) requires two or more verification factors.
The three main factors are something you know, have, and are.

## Encryption
AES encryption is a symmetric encryption standard.
RSA is used for asymmetric encryption.
TLS provides secure communication over networks.

## Common Attacks
SQL injection occurs when malicious SQL code is inserted into queries.
Cross-site scripting (XSS) allows attackers to inject malicious scripts.
""")
        
        doc2 = kb_path / "ai_security.md"
        doc2.write_text("""# AI Security

## Prompt Injection
Prompt injection is a vulnerability where malicious input manipulates AI behavior.
Direct injection involves explicit instructions to ignore previous commands.

## Model Safety
Constitutional AI methods help align models with human values.
RLHF stands for Reinforcement Learning from Human Feedback.

## Data Privacy
AI systems must protect personally identifiable information (PII).
Differential privacy techniques help protect training data.
""")
        
        yield str(kb_path)
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    def test_empty_knowledge_base(self):
        """Test behavior with empty knowledge base."""
        with tempfile.TemporaryDirectory() as temp_dir:
            kb_path = Path(temp_dir) / "empty_kb"
            kb_path.mkdir(parents=True, exist_ok=True)
            
            verifier = RetrievalVerifier(kb_path=str(kb_path))
            assert len(verifier.documents) == 0
            
            result = verifier.verify_claim("Any claim")
            assert result["verdict"] == "UNVERIFIABLE"
    
    def test_malformed_documents(self):
        """Test handling of malformed documents."""
        with tempfile.TemporaryDirectory() as temp_dir:
            kb_path = Path(temp_dir) / "kb"
            kb_path.mkdir(parents=True, exist_ok=True)
            
            # Create a document with special characters
            doc = kb_path / "special.md"
            doc.write_text("# Test\n\nSpecial chars: àáâãäå\n", encoding='utf-8')
            
            verifier = RetrievalVerifier(kb_path=str(kb_path))
            assert len(verifier.documents) == 1
    
    def test_threshold_edge_cases(self, temp_kb):
        """Test threshold boundary conditions."""
        # Very low threshold - everything should be supported
        verifier_low = RetrievalVerifier(kb_path=temp_kb, threshold=0.1)
        result_low = verifier_low.verify_claim("random text")
        
        # Very high threshold - nothing should be supported
        verifier_high = RetrievalVerifier(kb_path=temp_kb, threshold=0.99)
        result_high = verifier_high.verify_claim("AES encryption")
        
        # Low threshold should be more permissive
        assert result_low["verdict"] == "SUPPORTED" or len(result_low["evidence"]) > len(result_high["evidence"])


if __name__ == "__main__":
    pytest.main([__file__])
