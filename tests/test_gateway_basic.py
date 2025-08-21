import json
from fastapi.testclient import TestClient

import os, sys, pathlib
os.environ.setdefault("GOOGLE_API_KEY", "dummy")
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
from gateway import app

client = TestClient(app)


def test_watchman_check_basic():
    payload = {"prompt": "What is the capital of France?"}
    r = client.post("/v1/watchman/check", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    # Basic shape assertions
    assert "decision" in data
    assert "risk_score" in data
    assert "final_prompt" in data
    assert "llm_response" in data
