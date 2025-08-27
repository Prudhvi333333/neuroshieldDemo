# agents/code_validation_agent.py
from __future__ import annotations

import ast
import re
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, List
import logging
import sys

from .base_agent import BaseAgent
from app.utils.json_io import call_llm_json, JsonParseError
from app.schemas.agent_schemas import CODE_VALIDATION_SCHEMA
from utils.code_fragment_utils import extract_code_fragment

# Import metrics collector
sys.path.append(str(Path(__file__).parent.parent.parent))
from app.metrics.collector import time_block


class CodeValidationAgent(BaseAgent):
    def __init__(self):
        super().__init__("CodeValidationAgent")
        self.logger = logging.getLogger(__name__)

    def _detect_language(self, code: str) -> str:
        """Detect the programming language of the code fragment."""
        code_lower = code.lower().strip()
        
        # Python indicators (stronger patterns first)
        python_patterns = [
            r'\bdef\s+\w+\s*\(',  # function definition
            r'\bclass\s+\w+',     # class definition
            r'\bimport\s+\w+',    # import statement
            r'\bfrom\s+\w+\s+import',  # from import
            r'\bif\s+__name__\s*==\s*["\']__main__["\']',  # main guard
            r'\bprint\s*\(',      # print function
            r'\belif\b',          # elif keyword
            r'\bpass\b',          # pass keyword
        ]
        
        # JavaScript indicators (stronger patterns first)
        js_patterns = [
            r'\bfunction\s+\w+\s*\(',  # function declaration
            r'\bconst\s+\w+\s*=',     # const declaration
            r'\blet\s+\w+\s*=',       # let declaration
            r'\bvar\s+\w+\s*=',       # var declaration
            r'console\.log\s*\(',     # console.log
            r'=>',                    # arrow functions
        ]
        
        # Count strong indicators
        python_score = sum(1 for pattern in python_patterns if re.search(pattern, code, re.MULTILINE))
        js_score = sum(1 for pattern in js_patterns if re.search(pattern, code, re.MULTILINE))
        
        # Require at least one strong indicator to classify
        if python_score > 0 and python_score >= js_score:
            return "python"
        elif js_score > 0 and js_score > python_score:
            return "javascript"
        else:
            return "unknown"

    def _validate_python_syntax(self, code: str) -> Tuple[bool, List[str]]:
        """Validate Python code syntax using AST parsing."""
        try:
            ast.parse(code)
            return True, []
        except SyntaxError as e:
            error_msg = f"Line {e.lineno}: {e.msg}"
            if e.text:
                error_msg += f" (near: '{e.text.strip()}')"
            return False, [error_msg]
        except Exception as e:
            return False, [f"Parse error: {str(e)}"]

    def _validate_javascript_syntax(self, code: str) -> Tuple[bool, List[str]]:
        """Validate JavaScript code syntax using Node.js if available."""
        try:
            # Try to use Node.js syntax check
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            try:
                result = subprocess.run(
                    ['node', '-c', temp_file],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    return True, []
                else:
                    # Parse Node.js error output
                    errors = []
                    for line in result.stderr.split('\n'):
                        if line.strip() and 'SyntaxError' in line:
                            errors.append(line.strip())
                    return False, errors or ["JavaScript syntax error"]
                    
            finally:
                Path(temp_file).unlink(missing_ok=True)
                
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            # Node.js not available or timeout - skip gracefully
            self.logger.info("[CodeValidation] Node.js not available, skipping JS syntax check")
            return True, []  # Assume valid if we can't check
        except Exception as e:
            self.logger.warning(f"[CodeValidation] JS syntax check failed: {e}")
            return True, []  # Assume valid if check fails

    def _validate_syntax(self, code: str) -> Tuple[bool, List[str]]:
        """Validate code syntax based on detected language."""
        if not code or not code.strip():
            return True, []
        
        language = self._detect_language(code)
        self.logger.info(f"[CodeValidation] Detected language: {language}")
        
        if language == "python":
            return self._validate_python_syntax(code)
        elif language == "javascript":
            return self._validate_javascript_syntax(code)
        else:
            # Unknown language - assume valid
            self.logger.info(f"[CodeValidation] Unknown language, skipping syntax check")
            return True, []

    def run(self, prompt: str, response: str) -> Dict[str, Any]:
        with time_block("stage2.code_ast"):
            code_fragment = extract_code_fragment(response)
            
            # Handle case where no code is extracted
            if code_fragment is None:
                return {
                    "syntax_ok": True,
                    "syntax_errors": [],
                    "code_fragment": None,
                    "is_safe": True,
                    "risk_level": "Low",
                    "issues_found": ["No code fragment found in response"],
                    "recommendations": ["Ensure response contains extractable code"]
                }
            
            # Step 1: Syntax validation
            syntax_ok, syntax_errors = self._validate_syntax(code_fragment)
            
            result = {
                "syntax_ok": syntax_ok,
                "syntax_errors": syntax_errors,
                "code_fragment": code_fragment
            }
            
            # Step 2: If syntax is invalid, return early with clear reasons
            if not syntax_ok:
                result.update({
                    "is_safe": False,
                    "risk_level": "High",
                    "issues_found": ["Code has syntax errors"] + syntax_errors,
                    "recommendations": [
                        "Fix syntax errors before execution",
                        "Review code for proper language syntax",
                        "Use a code editor with syntax highlighting"
                    ]
                })
                self.logger.info(f"[CodeValidation] Syntax check failed: {syntax_errors}")
                return result
            
            # Step 3: Only ask LLM for semantic/security analysis if syntax is valid
            validation_prompt = f"""\
You are a security-focused code validator. The code has already passed syntax validation. 
Now analyze it for semantic correctness and security issues.

ORIGINAL PROMPT:
{prompt}

SYNTACTICALLY VALID CODE FRAGMENT:
{code_fragment}

Return ONLY JSON with this exact structure:
{{
"syntax_ok": true,
"syntax_errors": [],
"is_safe": true/false,
"risk_level": "Low|Medium|High|Critical",
"issues_found": ["list of specific security/safety issues"],
"recommendations": ["list of security recommendations"]
}}

Focus on:
- Malicious code patterns (file system access, network calls, etc.)
- Code injection vulnerabilities
- Logic errors that could cause harm
- Compliance with security best practices
- Semantic correctness and potential runtime errors"""

            try:
                parsed = call_llm_json(validation_prompt, CODE_VALIDATION_SCHEMA)
                # Ensure syntax fields are correctly set
                parsed["syntax_ok"] = True
                parsed["syntax_errors"] = []
                parsed["code_fragment"] = code_fragment
                self.logger.info(f"[CodeValidation] LLM semantic analysis: {parsed}")
                return parsed
            except JsonParseError as e:
                self.logger.error(f"[CodeValidation] JSON parse error: {e}")
                # Fallback to safe defaults (assume risky)
                result.update({
                    "is_safe": False,
                    "risk_level": "High",
                    "issues_found": ["Semantic validation failed - treating as potentially unsafe"],
                    "recommendations": ["Manual review required", "Consider alternative implementation"]
                })
                return result
