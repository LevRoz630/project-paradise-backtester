# Run Registry Implementation Guide

## Patrick's Question Answered

> "The directory has so much going on 😂 not really sure where to get started. Do I need to make a new folder to start working on this or is there already baseline in place?"

**TL;DR:** You'll need to create a **new module**, but you can leverage existing infrastructure. Start by creating `vectorbt/portfolio/registry/` - there's no baseline run registry yet, but the groundwork (serialization, records) is already there.

---

## 📋 Current State of the Repository

### What EXISTS Already

✅ **Serialization Infrastructure** (`vectorbt/utils/config.py`)
- `Pickleable` mixin with `.save()` and `.load()` methods
- Portfolio objects can already be saved/loaded individually
- Uses pickle/dill for Python object persistence

✅ **Portfolio Tracking** (`vectorbt/portfolio/`)
- `Portfolio` class captures complete backtest state
- `OrderRecords` - all orders with timestamps
- `TradeRecords` - entry/exit data for each trade
- `.stats()` method - comprehensive performance metrics

✅ **Record Management** (`vectorbt/records/`)
- `Records` base class for structured data arrays
- `MappedArray` for efficient array operations
- Decorators for field configuration

### What's MISSING (Your Opportunity!)

❌ **No Run Registry System**
- No way to save multiple backtest runs as a collection
- No metadata tracking (run name, parameters, timestamp)
- No query/filter capabilities for past runs
- No comparison tools between runs

❌ **No Persistent History**
- Runs only exist in memory during execution
- No centralized storage for results
- Can't retrieve old backtests for analysis

---

## 🎯 Recommended Implementation Plan

### Phase 1: Core Registry Structure

Create a new module: **`vectorbt/portfolio/registry/`**

```
vectorbt/portfolio/registry/
├── __init__.py              # Public API exports
├── run.py                   # RunRecord class (metadata + results)
├── registry.py              # RunRegistry main interface
├── store.py                 # Abstract base for storage backends
└── stores/                  # Concrete implementations
    ├── __init__.py
    ├── file_store.py        # JSON/Pickle filesystem storage
    └── sqlite_store.py      # SQLite for querying (optional Phase 2)
```

### Phase 2: Data Model (`run.py`)

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List
import uuid

@dataclass
class RunRecord:
    """Metadata for a single backtest run."""
    
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    strategy_name: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Summary stats (avoid storing full Portfolio here)
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    
    # Reference to saved Portfolio (file path or key)
    portfolio_path: Optional[str] = None
    
    # Optional metadata
    tags: List[str] = field(default_factory=list)
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            'run_id': self.run_id,
            'timestamp': self.timestamp.isoformat(),
            'strategy_name': self.strategy_name,
            'parameters': self.parameters,
            'stats': {
                'total_return': self.total_return,
                'sharpe_ratio': self.sharpe_ratio,
                'max_drawdown': self.max_drawdown,
                'total_trades': self.total_trades,
                'win_rate': self.win_rate,
            },
            'portfolio_path': self.portfolio_path,
            'tags': self.tags,
            'notes': self.notes,
        }
    
    @classmethod
    def from_portfolio(cls, 
                      pf, 
                      strategy_name: str = "",
                      parameters: Dict[str, Any] = None,
                      tags: List[str] = None,
                      notes: str = "") -> 'RunRecord':
        """Create RunRecord from a Portfolio object."""
        stats = pf.stats()
        
        return cls(
            strategy_name=strategy_name,
            parameters=parameters or {},
            total_return=float(stats.get('Total Return [%]', 0)),
            sharpe_ratio=float(stats.get('Sharpe Ratio', 0)),
            max_drawdown=float(stats.get('Max Drawdown [%]', 0)),
            total_trades=int(stats.get('Total Trades', 0)),
            win_rate=float(stats.get('Win Rate [%]', 0)),
            tags=tags or [],
            notes=notes,
        )
```

### Phase 3: Storage Backend (`stores/file_store.py`)

```python
import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from ..run import RunRecord
from ..store import RunStore

class FileStore(RunStore):
    """File-based storage for run records."""
    
    def __init__(self, base_dir: str = "./backtest_runs"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.base_dir / "runs_metadata.json"
        self.portfolios_dir = self.base_dir / "portfolios"
        self.portfolios_dir.mkdir(exist_ok=True)
        
    def save_run(self, run: RunRecord, portfolio=None) -> str:
        """Save a run record and optionally its portfolio."""
        # Save portfolio if provided
        if portfolio is not None:
            portfolio_filename = f"{run.run_id}.pkl"
            portfolio_path = self.portfolios_dir / portfolio_filename
            portfolio.save(str(portfolio_path))
            run.portfolio_path = str(portfolio_path)
        
        # Load existing metadata
        runs = self._load_metadata()
        
        # Add new run
        runs[run.run_id] = run.to_dict()
        
        # Save metadata
        self._save_metadata(runs)
        
        return run.run_id
    
    def get_run(self, run_id: str) -> Optional[RunRecord]:
        """Retrieve a run by ID."""
        runs = self._load_metadata()
        if run_id not in runs:
            return None
        return self._dict_to_record(runs[run_id])
    
    def list_runs(self, 
                  strategy_name: Optional[str] = None,
                  tags: Optional[List[str]] = None) -> List[RunRecord]:
        """List all runs, optionally filtered."""
        runs = self._load_metadata()
        records = [self._dict_to_record(r) for r in runs.values()]
        
        # Filter by strategy
        if strategy_name:
            records = [r for r in records if r.strategy_name == strategy_name]
        
        # Filter by tags
        if tags:
            records = [r for r in records if any(tag in r.tags for tag in tags)]
        
        # Sort by timestamp (newest first)
        records.sort(key=lambda r: r.timestamp, reverse=True)
        
        return records
    
    def load_portfolio(self, run_id: str):
        """Load the portfolio for a run."""
        run = self.get_run(run_id)
        if run is None or run.portfolio_path is None:
            return None
        
        # Use vectorbt's built-in load functionality
        from vectorbt import Portfolio
        return Portfolio.load(run.portfolio_path)
    
    def delete_run(self, run_id: str) -> bool:
        """Delete a run and its portfolio."""
        runs = self._load_metadata()
        if run_id not in runs:
            return False
        
        # Delete portfolio file
        portfolio_path = runs[run_id].get('portfolio_path')
        if portfolio_path and os.path.exists(portfolio_path):
            os.remove(portfolio_path)
        
        # Remove from metadata
        del runs[run_id]
        self._save_metadata(runs)
        
        return True
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load metadata from JSON file."""
        if not self.metadata_file.exists():
            return {}
        with open(self.metadata_file, 'r') as f:
            return json.load(f)
    
    def _save_metadata(self, runs: Dict[str, Any]):
        """Save metadata to JSON file."""
        with open(self.metadata_file, 'w') as f:
            json.dump(runs, f, indent=2)
    
    @staticmethod
    def _dict_to_record(data: Dict[str, Any]) -> RunRecord:
        """Convert dict to RunRecord."""
        from datetime import datetime
        return RunRecord(
            run_id=data['run_id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            strategy_name=data['strategy_name'],
            parameters=data['parameters'],
            total_return=data['stats']['total_return'],
            sharpe_ratio=data['stats']['sharpe_ratio'],
            max_drawdown=data['stats']['max_drawdown'],
            total_trades=data['stats']['total_trades'],
            win_rate=data['stats']['win_rate'],
            portfolio_path=data.get('portfolio_path'),
            tags=data.get('tags', []),
            notes=data.get('notes', ''),
        )
```

### Phase 4: Registry Interface (`registry.py`)

```python
from typing import List, Optional, Dict, Any
from .run import RunRecord
from .stores.file_store import FileStore

class RunRegistry:
    """Main interface for managing backtest runs."""
    
    def __init__(self, store=None):
        self.store = store or FileStore()
    
    def save_run(self,
                 portfolio,
                 strategy_name: str,
                 parameters: Dict[str, Any] = None,
                 tags: List[str] = None,
                 notes: str = "",
                 save_portfolio: bool = True) -> str:
        """
        Save a backtest run to the registry.
        
        Args:
            portfolio: The Portfolio object to save
            strategy_name: Name of the strategy
            parameters: Strategy parameters/config
            tags: List of tags for filtering
            notes: Optional notes about the run
            save_portfolio: Whether to save full Portfolio (default True)
            
        Returns:
            run_id: Unique ID for this run
        """
        # Create run record from portfolio
        run = RunRecord.from_portfolio(
            portfolio,
            strategy_name=strategy_name,
            parameters=parameters,
            tags=tags,
            notes=notes
        )
        
        # Save to store
        pf_to_save = portfolio if save_portfolio else None
        return self.store.save_run(run, pf_to_save)
    
    def get_run(self, run_id: str) -> Optional[RunRecord]:
        """Get metadata for a specific run."""
        return self.store.get_run(run_id)
    
    def load_portfolio(self, run_id: str):
        """Load the full Portfolio for a run."""
        return self.store.load_portfolio(run_id)
    
    def list_runs(self,
                  strategy_name: Optional[str] = None,
                  tags: Optional[List[str]] = None) -> List[RunRecord]:
        """
        List runs, optionally filtered.
        
        Args:
            strategy_name: Filter by strategy name
            tags: Filter by tags (matches any)
            
        Returns:
            List of RunRecords sorted by timestamp (newest first)
        """
        return self.store.list_runs(strategy_name, tags)
    
    def compare_runs(self, run_ids: List[str]) -> Dict[str, Any]:
        """
        Compare multiple runs side-by-side.
        
        Returns:
            Dict with comparison data suitable for DataFrame/table
        """
        runs = [self.get_run(rid) for rid in run_ids]
        runs = [r for r in runs if r is not None]
        
        comparison = {
            'run_id': [r.run_id for r in runs],
            'strategy': [r.strategy_name for r in runs],
            'timestamp': [r.timestamp for r in runs],
            'total_return': [r.total_return for r in runs],
            'sharpe_ratio': [r.sharpe_ratio for r in runs],
            'max_drawdown': [r.max_drawdown for r in runs],
            'total_trades': [r.total_trades for r in runs],
            'win_rate': [r.win_rate for r in runs],
        }
        
        return comparison
    
    def delete_run(self, run_id: str) -> bool:
        """Delete a run from the registry."""
        return self.store.delete_run(run_id)
    
    def get_best_runs(self, 
                     metric: str = 'sharpe_ratio',
                     n: int = 10,
                     strategy_name: Optional[str] = None) -> List[RunRecord]:
        """
        Get top N runs by a metric.
        
        Args:
            metric: Metric to sort by (sharpe_ratio, total_return, etc.)
            n: Number of runs to return
            strategy_name: Optional filter by strategy
            
        Returns:
            List of top RunRecords
        """
        runs = self.list_runs(strategy_name=strategy_name)
        
        # Sort by metric
        metric_key = {
            'sharpe_ratio': lambda r: r.sharpe_ratio,
            'total_return': lambda r: r.total_return,
            'win_rate': lambda r: r.win_rate,
            'total_trades': lambda r: r.total_trades,
        }.get(metric, lambda r: r.sharpe_ratio)
        
        runs.sort(key=metric_key, reverse=True)
        
        return runs[:n]
```

### Phase 5: API Exports (`__init__.py`)

```python
"""Run Registry for tracking backtest runs."""

from .run import RunRecord
from .registry import RunRegistry
from .store import RunStore
from .stores.file_store import FileStore

__all__ = [
    'RunRecord',
    'RunRegistry',
    'RunStore',
    'FileStore',
]
```

---

## 🚀 Usage Examples

### Basic Usage

```python
import vectorbt as vbt
from vectorbt.portfolio.registry import RunRegistry

# Create registry (uses ./backtest_runs by default)
registry = RunRegistry()

# Run a backtest
data = vbt.YFData.download("BTC-USD")
price = data.get("Close")
pf = vbt.Portfolio.from_holding(price, init_cash=100)

# Save the run
run_id = registry.save_run(
    portfolio=pf,
    strategy_name="buy_and_hold",
    parameters={"symbol": "BTC-USD", "init_cash": 100},
    tags=["crypto", "long-only"]
)

print(f"Saved run: {run_id}")
```

### List and Filter Runs

```python
# List all runs
all_runs = registry.list_runs()
for run in all_runs:
    print(f"{run.strategy_name}: {run.total_return:.2f}% return")

# Filter by strategy
sma_runs = registry.list_runs(strategy_name="dual_sma")

# Filter by tags
crypto_runs = registry.list_runs(tags=["crypto"])
```

### Load and Compare

```python
# Load a specific run's portfolio
pf = registry.load_portfolio(run_id)
pf.plot().show()

# Get best runs by Sharpe ratio
top_runs = registry.get_best_runs(metric='sharpe_ratio', n=5)

# Compare multiple runs
comparison = registry.compare_runs([run_id1, run_id2, run_id3])
import pandas as pd
df = pd.DataFrame(comparison)
print(df)
```

### Advanced: Parameter Sweep

```python
# Save results from a parameter sweep
symbols = ["BTC-USD", "ETH-USD"]
data = vbt.YFData.download(symbols)
price = data.get("Close")

for fast in [10, 20, 30]:
    for slow in [50, 100, 200]:
        if fast >= slow:
            continue
            
        fast_ma = vbt.MA.run(price, fast)
        slow_ma = vbt.MA.run(price, slow)
        entries = fast_ma.ma_crossed_above(slow_ma)
        exits = fast_ma.ma_crossed_below(slow_ma)
        
        pf = vbt.Portfolio.from_signals(price, entries, exits)
        
        registry.save_run(
            portfolio=pf,
            strategy_name="dual_sma",
            parameters={"fast": fast, "slow": slow},
            tags=["sma", "crossover"],
            notes=f"Testing {fast}/{slow} windows"
        )

# Find best parameter combo
best_runs = registry.get_best_runs(
    strategy_name="dual_sma",
    metric="sharpe_ratio",
    n=3
)

for run in best_runs:
    print(f"Fast: {run.parameters['fast']}, Slow: {run.parameters['slow']}")
    print(f"Sharpe: {run.sharpe_ratio:.3f}")
```

---

## 📁 Where Each File Goes

```
vectorbt/portfolio/registry/
├── __init__.py                    # START HERE - exports
├── run.py                         # RunRecord dataclass
├── store.py                       # Abstract base (if needed)
├── registry.py                    # RunRegistry main class
└── stores/
    ├── __init__.py
    └── file_store.py              # FileStore implementation
```

Then update `vectorbt/portfolio/__init__.py` to include:

```python
from vectorbt.portfolio.registry import RunRegistry, RunRecord
```

---

## 🎓 Why This Approach Works

1. **Leverages Existing Infrastructure**
   - Uses Portfolio's built-in `.save()` and `.load()`
   - Follows vectorbt's existing patterns (Records, configs)

2. **Loosely Coupled**
   - Registry is independent of Portfolio internals
   - Can add features without modifying core Portfolio

3. **Extensible**
   - Easy to add new storage backends (SQLite, cloud)
   - Can add more metadata fields without breaking existing runs

4. **Developer Friendly**
   - Simple API matches vectorbt's style
   - Minimal dependencies (just stdlib + existing vectorbt)

---

## 🛠️ Development Workflow

1. **Create the folder structure** (15 min)
2. **Implement `RunRecord` dataclass** (30 min)
3. **Build `FileStore`** (1-2 hours)
4. **Write `RunRegistry` interface** (1 hour)
5. **Add tests** (1-2 hours)
6. **Write documentation** (1 hour)
7. **Create examples** (30 min)

**Total estimated time: 6-8 hours of focused work**

---

## 📝 Next Steps for Patrick

1. **Create the folder**: `mkdir -p vectorbt/portfolio/registry/stores`

2. **Start with `run.py`**: Implement the RunRecord dataclass

3. **Build `file_store.py`**: Start simple with JSON metadata + pickle portfolios

4. **Create `registry.py`**: Implement the main API

5. **Test manually**: Write a quick script to test save/load/list

6. **Add unit tests**: Follow existing test patterns in `tests/`

7. **Document**: Add docstrings and usage examples

---

## 🤝 Integration with vectorbt

To make this feel native to vectorbt, consider adding a convenience method:

```python
# In vectorbt/portfolio/base.py
class Portfolio(Pickleable, ...):
    
    def save_to_registry(self,
                        strategy_name: str,
                        parameters: dict = None,
                        tags: list = None,
                        notes: str = "",
                        registry=None):
        """Save this portfolio to the run registry."""
        if registry is None:
            from vectorbt.portfolio.registry import RunRegistry
            registry = RunRegistry()
        
        return registry.save_run(
            portfolio=self,
            strategy_name=strategy_name,
            parameters=parameters,
            tags=tags,
            notes=notes
        )
```

Then users can simply:
```python
pf = vbt.Portfolio.from_signals(...)
run_id = pf.save_to_registry(strategy_name="my_strategy")
```

---

## 🎯 Summary

**To answer your question:**
- **Do you need a new folder?** → **YES**, create `vectorbt/portfolio/registry/`
- **Is there baseline?** → **Partial** - serialization exists, but no registry yet
- **Where to start?** → Begin with the `RunRecord` dataclass in `run.py`

The good news: You're building something NEW that fills a real gap, and you have solid infrastructure to build on (serialization, records). This is a greenfield feature that will add significant value!

Good luck! 🚀
