"""Static analysis to detect dangerous Python constructs in snippets."""
from __future__ import annotations
import ast
from typing import List

_FORBIDDEN_FUNCS = {
    ("os", "system"),
    ("os", "popen"),
    ("subprocess", "Popen"),
    ("subprocess", "call"),
    ("subprocess", "run"),
    ("socket", None),  # any use of socket module
}

_FORBIDDEN_NAMES = {"open"}


def _is_forbidden_call(node: ast.Call) -> bool:
    # handle simple Name or Attribute chain
    if isinstance(node.func, ast.Name):
        if node.func.id in _FORBIDDEN_NAMES:
            return True
    elif isinstance(node.func, ast.Attribute):
        attr = node.func.attr
        value = node.func.value
        if isinstance(value, ast.Name):
            mod = value.id
            for m, f in _FORBIDDEN_FUNCS:
                if mod == m and (f is None or f == attr):
                    return True
    return False


def check_code_snippet(code: str) -> List[str]:
    """Return list of reasons if snippet contains dangerous usage."""
    reasons: List[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ["syntax_error"]

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call):
            if _is_forbidden_call(node):
                reasons.append("forbidden_call")
            self.generic_visit(node)

        def visit_Import(self, node: ast.Import):
            for alias in node.names:
                if alias.name in {m for m, _ in _FORBIDDEN_FUNCS}:
                    reasons.append("forbidden_import")
            self.generic_visit(node)

        def visit_ImportFrom(self, node: ast.ImportFrom):
            if node.module in {m for m, _ in _FORBIDDEN_FUNCS}:
                reasons.append("forbidden_import")
            self.generic_visit(node)

    Visitor().visit(tree)
    return list(set(reasons))
