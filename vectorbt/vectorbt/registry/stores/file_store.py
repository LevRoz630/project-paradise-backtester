from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..run_id import canonical_config_json, compute_run_id


@dataclass(frozen=True)
class RunEntry:
    run_id: str
    timestamp: str
    path: str  # relative path, e.g. "runs/<run_id>"
    summary: Dict[str, Any]


class FileStore:
    """Filesystem-backed run registry.

    Layout:
      <base_dir>/
        registry.json
        runs/
          <run_id>/
            config.json
            versions.txt
            metrics.json
            ... artifacts (later)
    """

    def __init__(self, base_dir: str = "runs"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # NEW: keep all run folders inside base_dir/runs/
        self.runs_dir = self.base_dir / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)

        # registry index stays at top level
        self.registry_path = self.base_dir / "registry.json"

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _atomic_write_json(self, path: Path, obj: Dict[str, Any]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)

    def _load_registry(self) -> Dict[str, Any]:
        if not self.registry_path.exists():
            return {"runs": []}
        return json.loads(self.registry_path.read_text(encoding="utf-8"))

    def _extract_index_fields(self, config: Dict[str, Any], summary: Dict[str, Any]) -> Dict[str, Any]:
        data = config.get("data", {}) if isinstance(config, dict) else {}
        return {
            "symbol": data.get("symbol"),
            "interval": data.get("interval"),
            "total_return": summary.get("total_return"),
            "sharpe_ratio": summary.get("sharpe_ratio"),
        }

    def list(self) -> List[RunEntry]:
        reg = self._load_registry()
        out: List[RunEntry] = []
        for item in reg.get("runs", []):
            out.append(
                RunEntry(
                    run_id=item["run_id"],
                    timestamp=item["timestamp"],
                    path=item["path"],
                    summary=item.get("summary", {}),
                )
            )
        return out

    def exists(self, run_id: str) -> bool:
        return (self.runs_dir / run_id).exists()

    def create_run(
        self,
        config: Dict[str, Any],
        summary: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> RunEntry:
        """Create run folder + update registry index."""
        summary = summary or {}

        run_id = compute_run_id(config)
        run_dir = self.runs_dir / run_id
        rel_path = f"runs/{run_id}"

        if run_dir.exists() and not force:
            # Return existing entry if present in registry; else create minimal entry.
            for entry in self.list():
                if entry.run_id == run_id:
                    return entry
            entry = RunEntry(run_id=run_id, timestamp=self._now_iso(), path=rel_path, summary=summary)
            self._append_registry(entry, config=config)
            return entry

        run_dir.mkdir(parents=True, exist_ok=True)

        # Write config.json (canonical)
        (run_dir / "config.json").write_text(canonical_config_json(config), encoding="utf-8")

        # Write versions.txt (minimal, can expand later)
        versions_txt = f"created_at={self._now_iso()}\n"
        (run_dir / "versions.txt").write_text(versions_txt, encoding="utf-8")

        # Write metrics.json (summary)
        (run_dir / "metrics.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        entry = RunEntry(run_id=run_id, timestamp=self._now_iso(), path=rel_path, summary=summary)
        self._append_registry(entry, config=config)
        return entry

    def show(self, run_id: str) -> Dict[str, Any]:
        """Load run details (config, metrics, versions) from disk."""
        run_dir = self.runs_dir / run_id
        if not run_dir.exists():
            raise FileNotFoundError(f"Run not found: {run_id}")

        config_path = run_dir / "config.json"
        metrics_path = run_dir / "metrics.json"
        versions_path = run_dir / "versions.txt"

        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
        metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
        versions = versions_path.read_text(encoding="utf-8") if versions_path.exists() else ""

        return {
            "run_id": run_id,
            "path": f"runs/{run_id}",
            "config": config,
            "metrics": metrics,
            "versions": versions,
        }

    def _append_registry(self, entry: RunEntry, config: Dict[str, Any]) -> None:
        reg = self._load_registry()
        runs = reg.get("runs", [])

        # de-dup by run_id
        runs = [r for r in runs if r.get("run_id") != entry.run_id]

        fields = self._extract_index_fields(config, entry.summary)

        runs.append(
            {
                "run_id": entry.run_id,
                "timestamp": entry.timestamp,
                "symbol": fields["symbol"],
                "interval": fields["interval"],
                "total_return": fields["total_return"],
                "sharpe_ratio": fields["sharpe_ratio"],
                "path": entry.path,
                "summary": entry.summary,  # keep full summary too
            }
        )

        # newest first
        runs.sort(key=lambda r: r["timestamp"], reverse=True)
        reg["runs"] = runs
        self._atomic_write_json(self.registry_path, reg)