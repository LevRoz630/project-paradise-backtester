from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def _canonicalize(obj: Any) -> Any:
    """Convert config object into a deterministic, JSON-serializable form."""
    if isinstance(obj, dict):
        return {str(k): _canonicalize(obj[k]) for k in sorted(obj.keys(), key=str)}
    if isinstance(obj, (list, tuple)):
        return [_canonicalize(x) for x in obj]
    # Basic JSON types are fine; everything else should be stringified
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


def canonical_config_json(config: Dict[str, Any]) -> str:
    """Return canonical JSON string (stable ordering, no whitespace)."""
    canonical = _canonicalize(config)
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_run_id(config: Dict[str, Any]) -> str:
    """Deterministic run id: sha256(canonical_config.json)."""
    s = canonical_config_json(config)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()