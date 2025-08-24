# audit/replay.py
"""
Minimal replay helper:
- Reads sbom.jsonl line(s)
- Prints the stored inputs and decision/signals so you can re-submit manually.

(We keep it simple and offline-friendly.)
"""
from __future__ import annotations
import json, sys

def main():
    path = "logs/sbom.jsonl"
    if len(sys.argv) > 1:
        path = sys.argv[1]
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            print("—"*60)
            print("request_id:", obj.get("request_id"))
            print("policy_version:", obj.get("policy_version"))
            print("inputs:", obj.get("replay_hint", {}).get("inputs"))
            print("decision:", obj.get("decision"))
            print("signals:", obj.get("signals"))
            print("curl -s -X POST http://localhost:8000/v1/watchman/check -H 'Content-Type: application/json' -d @- <<'JSON'\n" +
            json.dumps(obj.get("replay_hint", {}).get("inputs", {}), ensure_ascii=False) +
            "\nJSON\n")


if __name__ == "__main__":
    main()
