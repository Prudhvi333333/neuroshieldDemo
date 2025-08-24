# tests/test_qa_stability.py
import os
from gateway.quantum_anomaly import get_quantum_anomaly

def test_qa_stability_same_prompt():
    qa = get_quantum_anomaly()
    p = "What is the capital of France?"
    a1 = qa.score(p).anomaly
    a2 = qa.score(p).anomaly
    # Should be very close within one process
    assert abs(a1 - a2) <= 0.02, (a1, a2)
