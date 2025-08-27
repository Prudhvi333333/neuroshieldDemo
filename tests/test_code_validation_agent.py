"""
Unit tests for the CodeValidationAgent with syntax checking.
Tests Python AST parsing, JavaScript syntax validation, and LLM integration.
"""
import pytest
from unittest.mock import patch, MagicMock

from agents.code_validation_agent import CodeValidationAgent
from app.utils.json_io import JsonParseError


class TestCodeValidationAgent:
    """Test the CodeValidationAgent with syntax validation."""
    
    @pytest.fixture
    def agent(self):
        """Create a CodeValidationAgent instance."""
        return CodeValidationAgent()
    
    def test_detect_language_python(self, agent):
        """Test Python language detection."""
        python_code = """
def hello_world():
    print("Hello, World!")
    return True
"""
        assert agent._detect_language(python_code) == "python"
    
    def test_detect_language_javascript(self, agent):
        """Test JavaScript language detection."""
        js_code = """
function helloWorld() {
    console.log("Hello, World!");
    return true;
}
"""
        assert agent._detect_language(js_code) == "javascript"
    
    def test_detect_language_unknown(self, agent):
        """Test unknown language detection."""
        unknown_code = "SELECT * FROM users WHERE id = 1;"
        assert agent._detect_language(unknown_code) == "unknown"
    
    def test_validate_python_syntax_valid(self, agent):
        """Test valid Python syntax validation."""
        valid_code = """
def add(a, b):
    return a + b

result = add(1, 2)
print(result)
"""
        syntax_ok, errors = agent._validate_python_syntax(valid_code)
        assert syntax_ok is True
        assert errors == []
    
    def test_validate_python_syntax_invalid(self, agent):
        """Test invalid Python syntax validation."""
        invalid_code = """
def add(a, b:
    return a + b
"""
        syntax_ok, errors = agent._validate_python_syntax(invalid_code)
        assert syntax_ok is False
        assert len(errors) > 0
        assert "Line 2" in errors[0]
    
    def test_validate_python_syntax_indentation_error(self, agent):
        """Test Python indentation error detection."""
        invalid_code = """
def add(a, b):
return a + b
"""
        syntax_ok, errors = agent._validate_python_syntax(invalid_code)
        assert syntax_ok is False
        assert len(errors) > 0
    
    @patch('subprocess.run')
    def test_validate_javascript_syntax_valid(self, mock_run, agent):
        """Test valid JavaScript syntax validation."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        js_code = """
function add(a, b) {
    return a + b;
}
"""
        syntax_ok, errors = agent._validate_javascript_syntax(js_code)
        assert syntax_ok is True
        assert errors == []
    
    @patch('subprocess.run')
    def test_validate_javascript_syntax_invalid(self, mock_run, agent):
        """Test invalid JavaScript syntax validation."""
        mock_run.return_value = MagicMock(
            returncode=1, 
            stderr="SyntaxError: Unexpected token '}'"
        )
        
        js_code = """
function add(a, b {
    return a + b;
}
"""
        syntax_ok, errors = agent._validate_javascript_syntax(js_code)
        assert syntax_ok is False
        assert len(errors) > 0
        assert "SyntaxError" in errors[0]
    
    @patch('subprocess.run')
    def test_validate_javascript_syntax_node_not_available(self, mock_run, agent):
        """Test JavaScript validation when Node.js is not available."""
        mock_run.side_effect = FileNotFoundError("node not found")
        
        js_code = "function test() { return true; }"
        syntax_ok, errors = agent._validate_javascript_syntax(js_code)
        
        # Should gracefully skip and assume valid
        assert syntax_ok is True
        assert errors == []
    
    def test_validate_syntax_empty_code(self, agent):
        """Test syntax validation with empty code."""
        syntax_ok, errors = agent._validate_syntax("")
        assert syntax_ok is True
        assert errors == []
    
    def test_validate_syntax_unknown_language(self, agent):
        """Test syntax validation with unknown language."""
        sql_code = "SELECT * FROM users;"
        syntax_ok, errors = agent._validate_syntax(sql_code)
        assert syntax_ok is True  # Should assume valid for unknown languages
        assert errors == []
    
    @patch('utils.code_fragment_utils.extract_code_fragment')
    def test_run_with_syntax_error(self, mock_extract, agent):
        """Test run method with syntax errors - should return early."""
        mock_extract.return_value = "def broken_function(\n    pass"
        
        result = agent.run("Write a function", "Here's a broken function...")
        
        assert result["syntax_ok"] is False
        assert len(result["syntax_errors"]) > 0
        assert result["is_safe"] is False
        assert result["risk_level"] == "High"
        assert "Code has syntax errors" in result["issues_found"]
        assert "Fix syntax errors" in result["recommendations"][0]
    
    @patch('utils.code_fragment_utils.extract_code_fragment')
    @patch('app.utils.json_io.call_llm_json')
    def test_run_with_valid_syntax(self, mock_llm, mock_extract, agent):
        """Test run method with valid syntax - should call LLM."""
        mock_extract.return_value = "def add(a, b):\n    return a + b"
        mock_llm.return_value = {
            "syntax_ok": True,
            "syntax_errors": [],
            "is_safe": True,
            "risk_level": "Low",
            "issues_found": [],
            "recommendations": ["Code looks safe"]
        }
        
        result = agent.run("Write an add function", "Here's a function...")
        
        assert result["syntax_ok"] is True
        assert result["syntax_errors"] == []
        assert result["is_safe"] is True
        assert result["risk_level"] == "Low"
        assert "code_fragment" in result
        mock_llm.assert_called_once()
    
    @patch('utils.code_fragment_utils.extract_code_fragment')
    @patch('app.utils.json_io.call_llm_json')
    def test_run_with_llm_failure(self, mock_llm, mock_extract, agent):
        """Test run method when LLM call fails."""
        mock_extract.return_value = "def add(a, b):\n    return a + b"
        mock_llm.side_effect = JsonParseError("LLM failed")
        
        result = agent.run("Write an add function", "Here's a function...")
        
        assert result["syntax_ok"] is True
        assert result["syntax_errors"] == []
        assert result["is_safe"] is False
        assert result["risk_level"] == "High"
        assert "Semantic validation failed" in result["issues_found"]
    
    @patch('utils.code_fragment_utils.extract_code_fragment')
    def test_run_with_malicious_python_code(self, mock_extract, agent):
        """Test run method with syntactically valid but malicious Python code."""
        malicious_code = """
import os
os.system("rm -rf /")
"""
        mock_extract.return_value = malicious_code
        
        # This should pass syntax check but fail security analysis
        with patch('app.utils.json_io.call_llm_json') as mock_llm:
            mock_llm.return_value = {
                "syntax_ok": True,
                "syntax_errors": [],
                "is_safe": False,
                "risk_level": "Critical",
                "issues_found": ["Dangerous system command execution"],
                "recommendations": ["Remove system calls", "Use safer alternatives"]
            }
            
            result = agent.run("Delete files", "Here's the code...")
            
            assert result["syntax_ok"] is True
            assert result["is_safe"] is False
            assert result["risk_level"] == "Critical"
            assert "Dangerous system command" in result["issues_found"][0]
    
    def test_language_detection_edge_cases(self, agent):
        """Test language detection with edge cases."""
        # Mixed language indicators - Python def keyword should win
        mixed_code = """
def python_func():
    console.log("mixed");
"""
        # Should detect as Python due to def keyword being a strong Python indicator
        assert agent._detect_language(mixed_code) == "python"
        
        # Pure JavaScript should be detected correctly
        js_code = "function test() { console.log('hello'); }"
        assert agent._detect_language(js_code) == "javascript"
        
        # SQL should be unknown
        sql_code = "SELECT * FROM users;"
        assert agent._detect_language(sql_code) == "unknown"
        
        # Empty/whitespace should be unknown
        empty_code = "   \n  \t  "
        assert agent._detect_language(empty_code) == "unknown"
        
        # Arrow function (JavaScript)
        arrow_code = "const add = (a, b) => a + b;"
        assert agent._detect_language(arrow_code) == "javascript"
        
        # Python with colon
        python_colon = """
if True:
    print("hello")
"""
        assert agent._detect_language(python_colon) == "python"


class TestCodeValidationIntegration:
    """Integration tests for CodeValidationAgent."""
    
    @pytest.fixture
    def agent(self):
        return CodeValidationAgent()
    
    def test_full_validation_pipeline_python_valid(self, agent):
        """Test complete validation pipeline with valid Python code."""
        with patch('utils.code_fragment_utils.extract_code_fragment') as mock_extract:
            mock_extract.return_value = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
"""
            
            with patch('app.utils.json_io.call_llm_json') as mock_llm:
                mock_llm.return_value = {
                    "syntax_ok": True,
                    "syntax_errors": [],
                    "is_safe": True,
                    "risk_level": "Low",
                    "issues_found": [],
                    "recommendations": ["Consider iterative approach for better performance"]
                }
                
                result = agent.run("Write fibonacci function", "Here's the code...")
                
                assert result["syntax_ok"] is True
                assert result["is_safe"] is True
                assert result["risk_level"] == "Low"
                assert mock_llm.called
    
    def test_full_validation_pipeline_python_invalid(self, agent):
        """Test complete validation pipeline with invalid Python code."""
        with patch('utils.code_fragment_utils.extract_code_fragment') as mock_extract:
            mock_extract.return_value = """
def broken_function(
    print("missing closing parenthesis")
"""
            
            result = agent.run("Write a function", "Here's broken code...")
            
            assert result["syntax_ok"] is False
            assert len(result["syntax_errors"]) > 0
            assert result["is_safe"] is False
            assert result["risk_level"] == "High"
            # LLM should not be called for syntax errors
    
    def test_schema_compliance(self, agent):
        """Test that all outputs comply with the expected schema."""
        test_cases = [
            ("def valid(): pass", True),  # Valid syntax
            ("def invalid(\n    pass", False),  # Invalid syntax
        ]
        
        for code, should_be_valid in test_cases:
            with patch('utils.code_fragment_utils.extract_code_fragment') as mock_extract:
                mock_extract.return_value = code
                
                if should_be_valid:
                    with patch('app.utils.json_io.call_llm_json') as mock_llm:
                        mock_llm.return_value = {
                            "syntax_ok": True,
                            "syntax_errors": [],
                            "is_safe": True,
                            "risk_level": "Low",
                            "issues_found": [],
                            "recommendations": []
                        }
                        
                        result = agent.run("Test", "Test code")
                else:
                    result = agent.run("Test", "Test code")
                
                # Check required fields
                required_fields = ["syntax_ok", "syntax_errors", "is_safe", "risk_level", "issues_found", "recommendations", "code_fragment"]
                for field in required_fields:
                    assert field in result, f"Missing required field: {field}"
                
                # Check field types
                assert isinstance(result["syntax_ok"], bool)
                assert isinstance(result["syntax_errors"], list)
                assert isinstance(result["is_safe"], bool)
                assert result["risk_level"] in ["Low", "Medium", "High", "Critical"]
                assert isinstance(result["issues_found"], list)
                assert isinstance(result["recommendations"], list)


if __name__ == "__main__":
    pytest.main([__file__])
