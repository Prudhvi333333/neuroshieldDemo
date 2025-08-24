# tests/test_afc.py
from fastapi.testclient import TestClient

import os, sys, pathlib
os.environ.setdefault("GOOGLE_API_KEY", "dummy")
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
from gateway.app import app

client = TestClient(app)

def test_web_get_allowed_domain():
    r = client.post("/v1/afc/validate", json={
        "session_id": "s1",
        "tool": "web.get",
        "args": {"url": "https://docs.python.org/3/"}
    })
    j = r.json()
    assert j["allow"] is True
    assert j["reason"] == "allow"

def test_web_get_blocked_domain():
    r = client.post("/v1/afc/validate", json={
        "session_id": "s1",
        "tool": "web.get",
        "args": {"url": "https://evil.com/payload"}
    })
    j = r.json()
    assert j["allow"] is False
    assert j["reason"] == "domain_not_allowed"

def test_unknown_tool():
    r = client.post("/v1/afc/validate", json={
        "session_id": "sX",
        "tool": "db.write",
        "args": {"sql": "drop table users"}
    })
    j = r.json()
    assert j["allow"] is False
    assert j["reason"].startswith("tool_not_allowed")

def test_schema_violation():
    r = client.post("/v1/afc/validate", json={
        "session_id": "s1",
        "tool": "web.get",
        "args": {}  # missing required 'url'
    })
    j = r.json()
    assert j["allow"] is False
    assert j["reason"].startswith("args_invalid")
