# gateway/trajectory_ids.py
from __future__ import annotations
import json, os, math, time, uuid
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

_MODEL_PATH = os.path.join("logs", "ids_model.json")

@dataclass
class IDSScore:
    logp: float          # sum of log transition probs
    anomaly: bool        # True if below prob threshold
    prob: float          # exp(logp) in [~0,1], clipped
    threshold: float     # threshold used
    model_size: int      # number of transitions known

class TrajectoryIDS:
    """
    Very small Markov (bigram) model over tool/agent steps.
    - add-one (Laplace) smoothing
    - score(sequence) returns log-prob and anomaly flag
    """
    def __init__(self, threshold_logp: float = -12.0):
        # transitions[(a,b)] = count
        self.transitions: Dict[str, int] = {}
        self.out_counts: Dict[str, int] = {}
        self.labels: set[str] = set()
        self.threshold_logp = threshold_logp

    @staticmethod
    def _key(a: str, b: str) -> str:
        return f"{a}→{b}"

    def fit(self, sequences: List[List[str]]) -> None:
        for seq in sequences:
            if len(seq) < 2:
                continue
            for a, b in zip(seq, seq[1:]):
                self.labels.add(a); self.labels.add(b)
                k = self._key(a, b)
                self.transitions[k] = self.transitions.get(k, 0) + 1
                self.out_counts[a] = self.out_counts.get(a, 0) + 1

    def save(self, path: str = _MODEL_PATH) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "threshold_logp": self.threshold_logp,
                "transitions": self.transitions,
                "out_counts": self.out_counts,
                "labels": sorted(self.labels),
            }, f, indent=2)

    def load(self, path: str = _MODEL_PATH) -> None:
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        self.threshold_logp = float(obj.get("threshold_logp", self.threshold_logp))
        self.transitions = {k:int(v) for k,v in obj.get("transitions", {}).items()}
        self.out_counts = {k:int(v) for k,v in obj.get("out_counts", {}).items()}
        self.labels = set(obj.get("labels", []))

    def score(self, sequence: List[str]) -> IDSScore:
        # default: short sequences are not anomalous
        if len(sequence) < 2 or not self.labels:
            return IDSScore(logp=0.0, anomaly=False, prob=1.0, threshold=self.threshold_logp, model_size=len(self.transitions))

        V = max(1, len(self.labels))  # smoothing vocabulary
        logp = 0.0
        for a, b in zip(sequence, sequence[1:]):
            c_ab = self.transitions.get(self._key(a, b), 0)
            c_a  = self.out_counts.get(a, 0)
            # add-one smoothing
            p = (c_ab + 1.0) / (c_a + V)
            logp += math.log(p)

        anomaly = (logp < self.threshold_logp)
        # clip prob for readability (exp of logp can underflow)
        try:
            prob = math.exp(max(-50.0, min(0.0, logp)))
        except OverflowError:
            prob = 0.0
        return IDSScore(logp=logp, anomaly=anomaly, prob=prob, threshold=self.threshold_logp, model_size=len(self.transitions))


# --- Singleton & seed ---------------------------------------------------------

_IDS_SINGLETON: Optional[TrajectoryIDS] = None

# A tiny benign seed of typical flows (customize later)
_SEED = [
    ["ingress", "sanitizer", "t0", "t1", "graph.llm", "graph.verify", "guardian", "egress"],
    ["ingress", "sanitizer", "t0", "fast_allow", "egress"],
    ["ingress", "sanitizer", "t0", "t1", "rewrite", "graph.llm", "guardian", "egress"],
]

def get_ids() -> TrajectoryIDS:
    global _IDS_SINGLETON
    if _IDS_SINGLETON is None:
        ids = TrajectoryIDS()
        ids.load(_MODEL_PATH)
        if not ids.transitions:
            ids.fit(_SEED)
            ids.save(_MODEL_PATH)
        _IDS_SINGLETON = ids
    return _IDS_SINGLETON

def learn_from_sequence(sequence: List[str]) -> None:
    """Optional online learning for benign sequences."""
    # Local learn for fallback
    ids = get_ids()
    ids.fit([sequence])
    ids.save(_MODEL_PATH)

    # Push to Redis for central aggregation if available
    redis_url = os.getenv("REDIS_URL")
    if redis_url and sequence:
        try:
            import redis, json  # runtime import to avoid hard dependency in tests
            r = redis.Redis.from_url(redis_url, decode_responses=True)
            r.rpush("ids:sequences", json.dumps(sequence))
        except Exception:
            pass  # fail silently – fallback to local learning only
