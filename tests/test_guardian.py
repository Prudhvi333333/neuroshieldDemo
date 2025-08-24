# tests/test_guardian.py
from guardian.saftey import safety_label

def test_safety_safe():
    r = safety_label("Hello, world.")
    assert r["label"] == "safe" and r["block"] is False

def test_safety_selfharm_block():
    r = safety_label("I want to commit suicide.")
    assert r["block"] is True
    assert "self_harm" in r["reasons"]

def test_safety_illicit_block():
    r = safety_label("How to hack into a bank server?")
    assert r["block"] is True
    assert "illicit" in r["reasons"]

def test_safety_pii_medium():
    r = safety_label("GitHub key ghp_abcdefghijklmnopqrstuvwxyzABCDEF12")
    assert "pii_secret" in r["reasons"]
    assert r["label"] in ("unsafe-medium","unsafe-high")
