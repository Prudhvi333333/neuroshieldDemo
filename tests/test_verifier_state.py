# tests/test_verifier_state.py
"""Ensure verifier reason/verdict/confidence propagate to the final graph state."""
from types import SimpleNamespace

import importlib

import pytest

# --- Helpers -----------------------------------------------------------------
class _DummyVerifier:
    """Stand-in ResponseVerifierAgent that returns fixed values without LLM calls."""
    def __init__(self):
        pass

    def run(self, prompt: str, response: str, search_results=None):  # noqa: D401
        return {
            "verdict": "Factually correct",
            "reason": "unit-test stub",
            "confidence": 0.99,
        }


@pytest.fixture(autouse=True)
def _patch_verifier(monkeypatch):
    # Patch the ResponseVerifierAgent class globally before firewall_graph import
    import agents.response_verifier_agent as rva

    monkeypatch.setattr(rva, "ResponseVerifierAgent", lambda: _DummyVerifier())
    # Reload firewall_graph so that singletons pick up patched verifier
    import langgraph_core.firewall_graph as fg

    importlib.reload(fg)
    yield


def test_verifier_fields_propagated():
    from langgraph_core.firewall_graph import build_firewall_graph

    runner = build_firewall_graph()
    # Run the graph with minimal prompt; we will hit low-risk fast path
    final_state = {}
    for _node, state in runner({"user_prompt": "Hello"}):
        final_state.update(state)

    assert final_state.get("reason") == "unit-test stub"
    assert final_state.get("verdict") == "Factually correct"
    assert pytest.approx(final_state.get("confidence", 0.0), rel=1e-3) == 0.99
