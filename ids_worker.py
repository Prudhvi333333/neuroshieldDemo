"""ids_worker.py
Periodic worker that pulls benign trajectory sequences from Redis, updates the
Markov IDS model, and persists the updated model to disk.

Run standalone or via docker-compose cron:  
    python ids_worker.py --interval 60
"""
from __future__ import annotations
import argparse, json, os, time, signal, sys
from typing import List

import redis  # type: ignore

from gateway.trajectory_ids import TrajectoryIDS, _MODEL_PATH

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_KEY = "ids:sequences"

stop = False

def _sigterm(_signo, _frame):
    global stop
    stop = True

signal.signal(signal.SIGINT, _sigterm)
signal.signal(signal.SIGTERM, _sigterm)


def main(interval: int = 60):
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

    ids = TrajectoryIDS()
    ids.load(_MODEL_PATH)

    while not stop:
        updated = False
        while True:
            seq_json = r.lpop(QUEUE_KEY)
            if seq_json is None:
                break
            try:
                seq: List[str] = json.loads(seq_json)
                ids.fit([seq])
                updated = True
            except Exception:
                continue  # skip malformed

        if updated:
            ids.save(_MODEL_PATH)
            print(f"[ids_worker] Model updated. Total transitions: {len(ids.transitions)}")

        time.sleep(interval)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=int(os.getenv("IDS_WORKER_INTERVAL", 60)), help="poll interval seconds")
    args = ap.parse_args()
    main(interval=args.interval)
