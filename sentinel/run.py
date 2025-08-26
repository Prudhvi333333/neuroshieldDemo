# sentinel/run.py
from __future__ import annotations
import json, time, os
from fastapi.testclient import TestClient
from collections import Counter
import os, sys, pathlib
os.environ.setdefault("GOOGLE_API_KEY", "dummy")
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

from gateway import app

client = TestClient(app)

def _check(prompt: str) -> dict:
    r = client.post("/v1/watchman/check", json={"prompt": prompt})
    return r.json()

def main():
    with open(os.path.join("sentinel","corpus.json"), "r", encoding="utf-8") as f:
        corpus = json.load(f)
    benign = corpus.get("benign", [])
    attacks = corpus.get("attacks", [])

    runs = []
    for kind, prompts in (("benign", benign), ("attacks", attacks)):
        for p in prompts:
            t0 = time.time()
            out = _check(p)
            lat = (time.time()-t0)*1000.0
            runs.append({
                "kind": kind,
                "prompt": p,
                "decision": out.get("decision"),
                "risk": out.get("risk_score"),
                "t1": out.get("t1",{}),
                "qa": out.get("qa",{}),
                "latency_ms": lat
            })

    # metrics
    tp=fp=tn=fn=0
    for r in runs:
        is_attack = (r["kind"]=="attacks")
        blocked = str(r["decision"]).lower().startswith(("blocked","rewrite"))
        if is_attack and blocked: tp+=1
        elif is_attack and not blocked: fn+=1
        elif not is_attack and blocked: fp+=1
        else: tn+=1

    precision = tp/(tp+fp) if (tp+fp)>0 else 0.0
    recall    = tp/(tp+fn) if (tp+fn)>0 else 0.0
    fpr       = fp/(fp+tn) if (fp+tn)>0 else 0.0

    buckets = [(0.0,0.2),(0.2,0.4),(0.4,0.6),(0.6,0.8),(0.8,1.0)]
    hist = Counter()
    for r in runs:
        x = r["risk"]
        for lo, hi in buckets:
            if (lo <= x < hi) or (hi == 1.0 and math.isclose(x,1.0)):
                hist[f"{lo:.1f}-{hi:.1f}"] += 1
            break

    report = {
        "counts": {"tp":tp,"fp":fp,"tn":tn,"fn":fn},
        "precision": precision,
        "recall": recall,
        "fpr": fpr,
        "histogram": dict(hist),
        "runs": runs
    }
    os.makedirs("logs", exist_ok=True)
    with open(os.path.join("logs","sentinel_report.json"),"w",encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
