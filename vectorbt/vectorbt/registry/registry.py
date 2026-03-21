from __future__ import annotations

from typing import Any, Dict, List, Optional

from .stores.file_store import FileStore, RunEntry


class Registry:
    """Public API for the run registry."""

    def __init__(self, base_dir: str = "bt_runs"):
        self.store = FileStore(base_dir=base_dir)

    def create(
        self,
        config: Dict[str, Any],
        summary: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> RunEntry:
        """Register a backtest run. Returns existing entry if config already seen (dedup)."""
        return self.store.create_run(config=config, summary=summary, force=force)

    def list(
        self,
        sort_by: Optional[str] = None,
        filter_by: Optional[str] = None,
    ) -> List[RunEntry]:
        """List all runs.

        Args:
            sort_by: "date" (default), "sharpe", or "returns"
            filter_by: Substring match on symbol or strategy name
        """
        return self.store.list(sort_by=sort_by, filter_by=filter_by)

    def show(self, run_id: str) -> Dict[str, Any]:
        """Return full details for a run: config, metrics, versions."""
        return self.store.show(run_id)

    def delete(self, run_id: str) -> None:
        """Permanently remove a run from the registry and disk."""
        self.store.delete_run(run_id)

    def compare(self, run_id_1: str, run_id_2: str) -> Dict[str, Any]:
        """Compare two runs side-by-side. Returns structured diff dict."""
        return self.store.compare_runs(run_id_1, run_id_2)
