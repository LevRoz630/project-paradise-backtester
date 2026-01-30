from __future__ import annotations

from typing import Any, Dict, List, Optional

from .stores.file_store import FileStore, RunEntry


class Registry:
    """Public API for run registry."""

    def __init__(self, base_dir: str = "bt_runs"):
        self.store = FileStore(base_dir=base_dir)

    def create(self, config: Dict[str, Any], summary: Optional[Dict[str, Any]] = None, force: bool = False) -> RunEntry:
        return self.store.create_run(config=config, summary=summary, force=force)

    def list(self) -> List[RunEntry]:
        return self.store.list()

    def show(self, run_id: str) -> Dict[str, Any]:
        return self.store.show(run_id)