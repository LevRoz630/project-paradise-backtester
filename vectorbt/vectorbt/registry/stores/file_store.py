from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
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
    strategy: str = ""  # strategy name or file path, for filtering


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
    """

    def __init__(self, base_dir: str = "bt_runs"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir = self.base_dir / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.base_dir / "registry.json"

    # ------------------------------------------------------------------ helpers

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _atomic_write_json(self, path: Path, obj: Any) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)

    def _load_registry(self) -> Dict[str, Any]:
        if not self.registry_path.exists():
            return {"runs": []}
        return json.loads(self.registry_path.read_text(encoding="utf-8"))

    def _extract_index_fields(self, config: Dict[str, Any], summary: Dict[str, Any]) -> Dict[str, Any]:
        data = config.get("data", {}) if isinstance(config, dict) else {}
        strategy = config.get("strategy", {}) if isinstance(config, dict) else {}
        strategy_name = strategy.get("name") or strategy.get("file") or ""
        return {
            "symbol": data.get("symbol"),
            "interval": data.get("interval"),
            "strategy": strategy_name,
            "total_return": summary.get("total_return"),
            "sharpe_ratio": summary.get("sharpe_ratio"),
        }

    # ------------------------------------------------------------------ public

    def exists(self, run_id: str) -> bool:
        return (self.runs_dir / run_id).exists()

    def create_run(
        self,
        config: Dict[str, Any],
        summary: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> RunEntry:
        summary = summary or {}
        run_id = compute_run_id(config)
        run_dir = self.runs_dir / run_id
        rel_path = f"runs/{run_id}"

        if run_dir.exists() and not force:
            for entry in self.list():
                if entry.run_id == run_id:
                    return entry
            entry = RunEntry(run_id=run_id, timestamp=self._now_iso(), path=rel_path, summary=summary)
            self._append_registry(entry, config=config)
            return entry

        run_dir.mkdir(parents=True, exist_ok=True)

        (run_dir / "config.json").write_text(canonical_config_json(config), encoding="utf-8")

        versions_txt = f"created_at={self._now_iso()}\n"
        (run_dir / "versions.txt").write_text(versions_txt, encoding="utf-8")

        self._atomic_write_json(run_dir / "metrics.json", summary)

        fields = self._extract_index_fields(config, summary)
        entry = RunEntry(
            run_id=run_id,
            timestamp=self._now_iso(),
            path=rel_path,
            summary=summary,
            strategy=fields["strategy"] or "",
        )
        self._append_registry(entry, config=config)
        return entry

    def list(
        self,
        sort_by: Optional[str] = None,
        filter_by: Optional[str] = None,
    ) -> List[RunEntry]:
        """Return all runs, with optional sorting and filtering.

        Args:
            sort_by: One of "date" (default), "sharpe", "returns"
            filter_by: Substring to match against symbol or strategy name
        """
        reg = self._load_registry()
        runs = reg.get("runs", [])

        if filter_by:
            q = filter_by.lower()
            runs = [
                r for r in runs
                if q in (r.get("symbol") or "").lower()
                or q in (r.get("strategy") or "").lower()
            ]

        entries = [
            RunEntry(
                run_id=r["run_id"],
                timestamp=r["timestamp"],
                path=r["path"],
                summary=r.get("summary", {}),
                strategy=r.get("strategy", ""),
            )
            for r in runs
        ]

        sort_key = sort_by or "date"
        if sort_key == "sharpe":
            entries.sort(key=lambda e: e.summary.get("sharpe_ratio") or float("-inf"), reverse=True)
        elif sort_key == "returns":
            entries.sort(key=lambda e: e.summary.get("total_return") or float("-inf"), reverse=True)
        else:
            entries.sort(key=lambda e: e.timestamp, reverse=True)

        return entries

    def show(self, run_id: str) -> Dict[str, Any]:
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

    def delete_run(self, run_id: str) -> None:
        """Remove a run's folder and its entry from the registry index."""
        run_dir = self.runs_dir / run_id
        if not run_dir.exists():
            raise FileNotFoundError(f"Run not found: {run_id}")

        shutil.rmtree(run_dir)

        reg = self._load_registry()
        reg["runs"] = [r for r in reg.get("runs", []) if r.get("run_id") != run_id]
        self._atomic_write_json(self.registry_path, reg)

    def compare_runs(self, run_id_1: str, run_id_2: str) -> Dict[str, Any]:
        """Return a structured diff of two runs' config and metrics."""
        r1 = self.show(run_id_1)
        r2 = self.show(run_id_2)

        def _get(d: Dict, *keys: str):
            for k in keys:
                if isinstance(d, dict):
                    d = d.get(k)
                else:
                    return None
            return d

        def _diff(v1, v2):
            if v1 is None and v2 is None:
                return None
            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                return round(v2 - v1, 6)
            return "changed" if v1 != v2 else "-"

        cfg_fields = [
            ("Symbol",   ("config", "data", "symbol")),
            ("Interval", ("config", "data", "interval")),
            ("Start",    ("config", "data", "start")),
            ("End",      ("config", "data", "end")),
            ("Strategy", ("config", "strategy", "name")),
            ("Exchange", ("config", "data", "exchange")),
        ]

        metric_fields = [
            ("Total Return",  ("metrics", "total_return")),
            ("Sharpe Ratio",  ("metrics", "sharpe_ratio")),
            ("Max Drawdown",  ("metrics", "max_drawdown")),
            ("Win Rate",      ("metrics", "win_rate")),
            ("Total Trades",  ("metrics", "total_trades")),
        ]

        rows = []
        for label, path in cfg_fields:
            v1 = _get(r1, *path)
            v2 = _get(r2, *path)
            if v1 is not None or v2 is not None:
                rows.append({"field": label, "run1": v1, "run2": v2, "diff": _diff(v1, v2)})

        for label, path in metric_fields:
            v1 = _get(r1, *path)
            v2 = _get(r2, *path)
            if v1 is not None or v2 is not None:
                rows.append({"field": label, "run1": v1, "run2": v2, "diff": _diff(v1, v2)})

        return {
            "run_id_1": run_id_1,
            "run_id_2": run_id_2,
            "rows": rows,
        }

    # ------------------------------------------------------------------ private

    def _append_registry(self, entry: RunEntry, config: Dict[str, Any]) -> None:
        reg = self._load_registry()
        runs = reg.get("runs", [])
        runs = [r for r in runs if r.get("run_id") != entry.run_id]

        fields = self._extract_index_fields(config, entry.summary)

        runs.append(
            {
                "run_id": entry.run_id,
                "timestamp": entry.timestamp,
                "symbol": fields["symbol"],
                "interval": fields["interval"],
                "strategy": fields["strategy"],
                "total_return": fields["total_return"],
                "sharpe_ratio": fields["sharpe_ratio"],
                "path": entry.path,
                "summary": entry.summary,
            }
        )

        runs.sort(key=lambda r: r["timestamp"], reverse=True)
        reg["runs"] = runs
        self._atomic_write_json(self.registry_path, reg)
