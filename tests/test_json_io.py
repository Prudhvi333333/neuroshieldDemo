"""
Unit tests for the strict JSON I/O system.
Tests validation, retry logic, and error handling.
"""
import pytest
import json
from unittest.mock import patch, MagicMock

from app.utils.json_io import call_llm_json, JsonParseError, _extract_json_block


class TestExtractJsonBlock:
    """Test JSON block extraction from various text formats."""
    
    def test_extract_plain_json(self):
        """Test extraction of plain JSON."""
        text = '{"key": "value", "number": 42}'
        result = _extract_json_block(text)
        assert result == '{"key": "value", "number": 42}'
    
    def test_extract_markdown_fenced_json(self):
        """Test extraction from markdown code blocks."""
        text = '```json\n{"key": "value"}\n```'
        result = _extract_json_block(text)
        assert result == '{"key": "value"}'
    
    def test_extract_generic_fenced_json(self):
        """Test extraction from generic code blocks."""
        text = '```\n{"key": "value"}\n```'
        result = _extract_json_block(text)
        assert result == '{"key": "value"}'
    
    def test_extract_json_from_mixed_text(self):
        """Test extraction of JSON from text with other content."""
        text = 'Here is the result: {"status": "success", "data": [1, 2, 3]} and that\'s it.'
        result = _extract_json_block(text)
        assert result == '{"status": "success", "data": [1, 2, 3]}'
    
    def test_extract_nested_json(self):
        """Test extraction of nested JSON objects."""
        text = '{"outer": {"inner": {"deep": "value"}}, "array": [{"item": 1}]}'
        result = _extract_json_block(text)
        assert result == '{"outer": {"inner": {"deep": "value"}}, "array": [{"item": 1}]}'


class TestCallLlmJson:
    """Test the main call_llm_json function."""
    
    @pytest.fixture
    def simple_schema(self):
        """Simple test schema."""
        return {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "value": {"type": "number"}
            },
            "required": ["status", "value"]
        }
    
    @patch('app.utils.json_io._call_llm_json')
    def test_valid_json_first_try(self, mock_llm, simple_schema):
        """Test successful parsing on first attempt."""
        mock_llm.return_value = '{"status": "success", "value": 42}'
        
        result = call_llm_json("test prompt", simple_schema)
        
        assert result == {"status": "success", "value": 42}
        mock_llm.assert_called_once()
    
    @patch('app.utils.json_io._call_llm_json')
    def test_invalid_then_valid_retry(self, mock_llm, simple_schema):
        """Test retry logic with invalid then valid JSON."""
        mock_llm.side_effect = [
            'invalid json {broken',  # First call fails
            '{"status": "success", "value": 42}'  # Second call succeeds
        ]
        
        result = call_llm_json("test prompt", simple_schema, retries=2)
        
        assert result == {"status": "success", "value": 42}
        assert mock_llm.call_count == 2
    
    @patch('app.utils.json_io._call_llm_json')
    def test_schema_validation_failure_then_success(self, mock_llm, simple_schema):
        """Test retry logic with schema validation failure then success."""
        mock_llm.side_effect = [
            '{"status": "success"}',  # Missing required "value" field
            '{"status": "success", "value": 42}'  # Valid JSON
        ]
        
        result = call_llm_json("test prompt", simple_schema, retries=2)
        
        assert result == {"status": "success", "value": 42}
        assert mock_llm.call_count == 2
    
    @patch('app.utils.json_io._call_llm_json')
    def test_final_failure_after_retries(self, mock_llm, simple_schema):
        """Test JsonParseError after all retries exhausted."""
        mock_llm.side_effect = [
            'invalid json',
            'still invalid',
            'nope, still broken'
        ]
        
        with pytest.raises(JsonParseError) as exc_info:
            call_llm_json("test prompt", simple_schema, retries=2)
        
        assert "Failed to parse JSON after 3 attempts" in str(exc_info.value)
        assert mock_llm.call_count == 3
    
    @patch('app.utils.json_io._call_llm_json')
    def test_markdown_fenced_json_parsing(self, mock_llm, simple_schema):
        """Test parsing of markdown-fenced JSON."""
        mock_llm.return_value = '```json\n{"status": "success", "value": 42}\n```'
        
        result = call_llm_json("test prompt", simple_schema)
        
        assert result == {"status": "success", "value": 42}
    
    @patch('app.utils.json_io._call_llm_json')
    def test_unexpected_exception_handling(self, mock_llm, simple_schema):
        """Test handling of unexpected exceptions."""
        mock_llm.side_effect = Exception("Network error")
        
        with pytest.raises(JsonParseError) as exc_info:
            call_llm_json("test prompt", simple_schema, retries=1)
        
        assert "Unexpected error after 2 attempts" in str(exc_info.value)
    
    @patch('app.utils.json_io._call_llm_json')
    def test_schema_hint_added_on_validation_failure(self, mock_llm, simple_schema):
        """Test that schema is added to prompt on validation failure."""
        mock_llm.side_effect = [
            '{"wrong": "format"}',  # Schema validation fails
            '{"status": "success", "value": 42}'  # Succeeds with schema hint
        ]
        
        result = call_llm_json("original prompt", simple_schema, retries=1)
        
        assert result == {"status": "success", "value": 42}
        # Check that second call includes schema information
        second_call_args = mock_llm.call_args_list[1][0]
        assert "schema" in second_call_args[0].lower()
    
    def test_zero_retries(self, simple_schema):
        """Test behavior with zero retries."""
        with patch('app.utils.json_io._call_llm_json') as mock_llm:
            mock_llm.return_value = 'invalid json'
            
            with pytest.raises(JsonParseError):
                call_llm_json("test prompt", simple_schema, retries=0)
            
            mock_llm.assert_called_once()


class TestIntegration:
    """Integration tests with real schema validation."""
    
    def test_complex_schema_validation(self):
        """Test with a complex nested schema."""
        complex_schema = {
            "type": "object",
            "properties": {
                "classification": {"type": "string", "enum": ["Safe", "Risky", "Blocked"]},
                "risk_score": {"type": "number", "minimum": 0, "maximum": 1},
                "attack_detection": {
                    "type": "object",
                    "properties": {
                        "prompt_injection": {
                            "type": "object",
                            "properties": {
                                "detected": {"type": "boolean"},
                                "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                            },
                            "required": ["detected", "confidence"]
                        }
                    }
                }
            },
            "required": ["classification", "risk_score"]
        }
        
        valid_json = {
            "classification": "Safe",
            "risk_score": 0.1,
            "attack_detection": {
                "prompt_injection": {
                    "detected": False,
                    "confidence": 0.2
                }
            }
        }
        
        with patch('app.utils.json_io._call_llm_json') as mock_llm:
            mock_llm.return_value = json.dumps(valid_json)
            
            result = call_llm_json("test prompt", complex_schema)
            
            assert result == valid_json


if __name__ == "__main__":
    pytest.main([__file__])
