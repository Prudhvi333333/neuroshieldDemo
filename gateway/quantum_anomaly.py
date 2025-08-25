# gateway/quantum_anomaly.py
from __future__ import annotations
import os
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.decomposition import TruncatedSVD

# Seed benign prompts – can be extended automatically later
_BENIGN_SEED = [
    "What is the capital of Canada?",
    "What is the capital of France?",
    "Explain quicksort in simple terms.",
    "Write a Python function to reverse a string.",
    "Summarize the key points of this article.",
    "How do I center a div with CSS?",
    "Best practices for storing API keys securely?",
    "What are REST vs GraphQL differences?",
    "Translate 'good morning' to Spanish.",
    "Create a grocery list with fruits and vegetables.",
    "Give me three blog title ideas about healthy sleep.",
    "Compare SSD vs HDD for laptop use.",
    "What’s the time complexity of binary search?",
    "Benefits of test-driven development?",
    "Outline a study plan for data structures.",
    "Write a polite email asking for feedback.",
]

@dataclass
class QAResult:
    anomaly: float            # 0..1 (tail prob) – higher = weirder
    dim: int
    detector: str = "quantum-kernel-sim"

class QuantumAnomaly:
    """
    Quantum-inspired anomaly:
      1) HashingVectorizer -> TruncatedSVD (low-dim)
      2) Fit mean/cov on benign seed; get distances for training set
      3) Score new x via Mahalanobis distance
      4) Calibrate anomaly using true tail probability: 1 - CDF(dist)
    """
    def __init__(self, n_features: int = 2**18, svd_dim: int = 128):
        self.vec = HashingVectorizer(
            n_features=n_features,
            alternate_sign=False,
            norm="l2",
            analyzer="word",
            ngram_range=(1, 2),
            lowercase=True
        )
        self.svd = TruncatedSVD(n_components=svd_dim, random_state=42)
        self.mu: Optional[np.ndarray] = None
        self.cov_inv: Optional[np.ndarray] = None
        self.train_dists: Optional[np.ndarray] = None
        self.sorted_dists: Optional[np.ndarray] = None
        self.dim = svd_dim
        self._fitted = False
        self.loaded_from: Optional[str] = None
        os.makedirs("logs", exist_ok=True)
        self.model_path = os.path.join("logs", "qa_model.npz")

    # ---------- persistence ----------
    def _save(self):
        if self.mu is None or self.cov_inv is None or self.train_dists is None:
            return
        np.savez(self.model_path, mu=self.mu, cov_inv=self.cov_inv, train_dists=self.train_dists)

    def _load(self) -> bool:
        if not os.path.exists(self.model_path):
            return False
        try:
            data = np.load(self.model_path, allow_pickle=False)
            self.mu = data["mu"]
            self.cov_inv = data["cov_inv"]
            self.train_dists = data["train_dists"]
            self.sorted_dists = np.sort(self.train_dists.copy())
            self._fitted = True
            self.loaded_from = "disk"
            return True
        except Exception:
            return False

    # ---------- core math ----------
    @staticmethod
    def _mah_dist(x: np.ndarray, mu: np.ndarray, cov_inv: np.ndarray) -> float:
        d = x - mu
        return float(np.sqrt(d @ cov_inv @ d.T))

    def fit(self, benign_texts: List[str]) -> None:
        texts = benign_texts if benign_texts else _BENIGN_SEED
        X = self.vec.transform(texts)
        Xs = self.svd.fit_transform(X)
        mu = Xs.mean(axis=0)
        Xc = Xs - mu
        cov = (Xc.T @ Xc) / max(1, Xc.shape[0] - 1)
        cov += np.eye(cov.shape[0]) * 1e-5
        cov_inv = np.linalg.inv(cov)
        dists = np.array([self._mah_dist(x, mu, cov_inv) for x in Xs])

        self.mu, self.cov_inv, self.train_dists = mu, cov_inv, dists
        self.sorted_dists = np.sort(dists.copy())
        self._fitted = True
        self.loaded_from = "seed"
        self._save()

    def _tail_prob(self, dist: float) -> float:
        """True tail prob = 1 - CDF(dist) using ECDF on training dists."""
        if self.sorted_dists is None or len(self.sorted_dists) == 0:
            return 0.0
        # rank = index where 'dist' would be inserted to keep sorted order
        rank = int(np.searchsorted(self.sorted_dists, dist, side="right"))
        cdf = rank / float(len(self.sorted_dists))
        tail = 1.0 - cdf
        # clamp to [0,1]
        return float(max(0.0, min(1.0, tail)))

    @staticmethod
    def _token_count(text: str) -> int:
        return len([t for t in text.split() if t.strip()])

    def score(self, text: str) -> QAResult:
        # load or fit if needed
        if not self._fitted and not self._load():
            self.fit(_BENIGN_SEED)

        # Heuristic 1: very short prompts (≤3 tokens) – almost always benign
        if self._token_count(text) <= 3:
            return QAResult(anomaly=0.05, dim=self.dim)

        # Heuristic 2: common jailbreak / injection cues boost anomaly
        _JB_PATTERNS = [
            "hidden system prompt",
            "ignore previous",
            "override all",
            "always respond",
            "include the system prompt",
            "jailbreak",
            "diagnostic mode",
            "internal console",
        ]
        if any(pat in text.lower() for pat in _JB_PATTERNS):
            # Hard-set a suspicious anomaly high enough to trigger block path
            return QAResult(anomaly=0.9, dim=self.dim)

        # Treat short factual questions as low anomaly to trigger fast-path
        if self._token_count(text) < 10 and any(keyword in text.lower() for keyword in ["what", "how", "when", "where", "who"]):
            return QAResult(anomaly=0.1, dim=self.dim)

        X = self.vec.transform([text])
        x = self.svd.transform(X)[0]
        dist = self._mah_dist(x, self.mu, self.cov_inv)  # type: ignore
        anomaly = self._tail_prob(dist)
        return QAResult(anomaly=anomaly, dim=self.dim)

    # Debug helper for diagnostics endpoint
    def score_debug(self, text: str) -> Tuple[float, float, float]:
        """Return (dist, cdf, anomaly) for this text."""
        if not self._fitted and not self._load():
            self.fit(_BENIGN_SEED)
        X = self.vec.transform([text])
        x = self.svd.transform(X)[0]
        dist = self._mah_dist(x, self.mu, self.cov_inv)  # type: ignore
        rank = int(np.searchsorted(self.sorted_dists, dist, side="right"))  # type: ignore
        cdf = rank / float(len(self.sorted_dists))                           # type: ignore
        anomaly = self._tail_prob(dist)
        return float(dist), float(cdf), float(anomaly)

# Singleton getter
_QA_SINGLETON: Optional[QuantumAnomaly] = None
def get_quantum_anomaly() -> QuantumAnomaly:
    global _QA_SINGLETON
    if _QA_SINGLETON is None:
        _QA_SINGLETON = QuantumAnomaly()
        if not _QA_SINGLETON._load():
            _QA_SINGLETON.fit(_BENIGN_SEED)
        # warmup (pre-JIT transforms)
        _QA_SINGLETON.score("warmup please")
    return _QA_SINGLETON