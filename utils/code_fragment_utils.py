# utils/code_fragment_utils.py

import re
from typing import Optional


def extract_code_fragment(text: str) -> Optional[str]:
    """
    Extract code fragments from LLM response text.
    Looks for code blocks marked with ``` or indented code.
    """
    if not text:
        return None

    # Pattern for markdown code blocks
    code_block_pattern = r'```(?:python|py|javascript|js|java|cpp|c\+\+|c#|cs|php|ruby|go|rust|swift|kotlin|scala|r|matlab|sql|html|css|bash|shell|sh|powershell|ps1|yaml|yml|json|xml|markdown|md)?\n(.*?)```'

    # Pattern for inline code blocks
    inline_code_pattern = r'`([^`]+)`'

    # Pattern for indented code (4 spaces or tab)
    indented_pattern = r'^(?:\s{4}|\t)(.+)$'

    # Try to find markdown code blocks first
    code_blocks = re.findall(code_block_pattern, text, re.DOTALL | re.MULTILINE)
    if code_blocks:
        return '\n'.join(code_blocks)

    # Try to find inline code
    inline_codes = re.findall(inline_code_pattern, text)
    if inline_codes:
        return '\n'.join(inline_codes)

    # Try to find indented code
    lines = text.split('\n')
    code_lines = []
    in_code_block = False

    for line in lines:
        if re.match(indented_pattern, line):
            if not in_code_block:
                in_code_block = True
            code_lines.append(line)
        elif in_code_block:
            # If we were in a code block but this line isn't indented, stop
            in_code_block = False

    if code_lines:
        return '\n'.join(code_lines)

    # If no code found, return None
    return None


def is_code_likely(text: str) -> bool:
    """
    Check if the text is likely to contain code.
    """
    if not text:
        return False

    # Common code indicators
    code_indicators = [
        'def ', 'class ', 'import ', 'from ', 'return ',
        'if __name__', 'print(', 'for ', 'while ',
        'try:', 'except:', 'finally:', 'with ',
        'async def', 'await ', 'yield ',
        'const ', 'let ', 'var ', 'function ',
        'public ', 'private ', 'protected ',
        '<?php', '<?=', '<?=',
        '<script>', '</script>',
        'package ', 'namespace ',
        'using ', 'namespace ',
        'fn ', 'impl ', 'struct ', 'enum ',
        'func ', 'type ', 'interface ',
        'SELECT ', 'INSERT ', 'UPDATE ', 'DELETE ',
        'CREATE ', 'ALTER ', 'DROP '
    ]

    text_lower = text.lower()
    return any(indicator.lower() in text_lower for indicator in code_indicators)
