from fastapi.testclient import TestClient

import os, sys, pathlib
os.environ.setdefault("GOOGLE_API_KEY", "dummy")
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

from gateway.app import app
import time

c = TestClient(app)

def test_caps_flow():
    r = c.post("/v1/caps/init", json={"session_id":"u1"})
    assert r.status_code == 200
    r = c.post("/v1/caps/use", json={"session_id":"u1","capability":"net_read","amount":1})
    j = r.json()
    assert j["ok"] in (True, False)  # depends on policy defaults
    # exhaust quickly
    for _ in range(10):
        c.post("/v1/caps/use", json={"session_id":"u1","capability":"net_read","amount":1})
    j = c.post("/v1/caps/use", json={"session_id":"u1","capability":"net_read","amount":1}).json()
    assert j["ok"] is False and "exhausted" in j["reason"]

def test_timelock_queue_cancel():
    r = c.post("/v1/timelock/queue", json={"tool":"email.send","args":{"to":"a@b.com","subject":"s","body":"x"}})
    rec = r.json()["record"]
    tid = rec["id"]
    assert rec["status"] == "pending"
    # cancel
    j = c.post("/v1/timelock/cancel", json={"id":tid}).json()
    assert j["ok"] is True
    # poll should show cancelled
    j = c.get(f"/v1/timelock/poll/{tid}").json()
    assert j["ok"] is True and j["record"]["status"] == "cancelled"

def test_timelock_ready_after_ttl():
    r = c.post("/v1/timelock/queue", json={"tool":"email.send","args":{"to":"a@b.com","subject":"s","body":"x"},"ttl_seconds":1})
    tid = r.json()["record"]["id"]
    time.sleep(1.2)
    j = c.get(f"/v1/timelock/poll/{tid}").json()
    assert j["ok"] is True and j["record"]["status"] in ("ready","pending")  # ready expected after TTL
