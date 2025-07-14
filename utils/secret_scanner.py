import math
import re
from pathlib import Path
from typing import List
 
# Shannon-entropy catch-all
def _entropy(s: str) -> float:
    if not s:
        return 0.0
    prob = [float(s.count(chr(x))) / len(s) for x in range(256)]
    return -sum(p * math.log2(p) for p in prob if p)
 
_SECRET_RE = re.compile(r"[A-Za-z0-9+/=_\-]{20,64}")
 
def scan(path: Path) -> List[str]:
    data = path.read_bytes().decode("utf-8", "ignore")
    tokens = _SECRET_RE.findall(data)
    return [t for t in tokens if _entropy(t) > 4.5][:10]