from fastapi.testclient import TestClient

import os, sys, pathlib
os.environ.setdefault("GOOGLE_API_KEY", "dummy")
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

from gateway import app

client = TestClient(app)

def test_fastpath_allows_safe_short_prompt():
    r = client.post("/v1/watchman/check", json={"prompt": "What is the capital of Canada?"})
    assert r.status_code == 200
    data = r.json()
    assert data["decision"].startswith("Likely factual")
    assert data["risk_score"] <= 0.2
    assert "Low-risk prompt" in " ".join(data.get("reasons", []))
