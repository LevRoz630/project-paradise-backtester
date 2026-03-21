"""bt show — display detailed information about a specific run."""
from __future__ import annotations

import sys


def add_args(parser):
    parser.add_argument("run_id", help="Run ID (or unique prefix)")
    parser.add_argument("--runs-dir", default="bt_runs", help="Registry directory (default: bt_runs)")


def run(args):
    from vectorbt.registry import Registry

    reg = Registry(base_dir=args.runs_dir)

    # Support prefix matching
    run_id = _resolve_run_id(reg, args.run_id)
    if not run_id:
        print(f"Error: no run found matching '{args.run_id}'", file=sys.stderr)
        sys.exit(1)

    details = reg.show(run_id)
    cfg = details.get("config", {})
    metrics = details.get("metrics", {})
    data = cfg.get("data", {})
    strategy = cfg.get("strategy", {})

    print(f"Run ID  : {run_id}")
    print(f"Date    : {details.get('versions', '').split('=')[-1].strip()[:19] or '-'}")
    print(f"Status  : Complete")
    print()

    print("Configuration:")
    _show_field("Source",   data.get("source"))
    _show_field("Exchange", data.get("exchange"))
    _show_field("Symbol",   data.get("symbol"))
    _show_field("Interval", data.get("interval"))
    start = data.get("start") or data.get("date_range", {}).get("start")
    end   = data.get("end")   or data.get("date_range", {}).get("end")
    if start or end:
        print(f"  Period         {start} to {end}")
    _show_field("Strategy", strategy.get("name") or strategy.get("file"))
    _show_field("Data hash", data.get("hash", "")[:12] + "..." if data.get("hash") else None)
    print()

    print("Metrics:")
    _show_metric("Total Return",  metrics.get("total_return"),  "{:.2%}")
    _show_metric("Sharpe Ratio",  metrics.get("sharpe_ratio"),  "{:.3f}")
    _show_metric("Max Drawdown",  metrics.get("max_drawdown"),  "{:.2%}")
    _show_metric("Win Rate",      metrics.get("win_rate"),      "{:.2%}")
    _show_metric("Total Trades",  metrics.get("total_trades"),  "{}")


def _resolve_run_id(reg, query: str) -> str:
    """Return full run_id matching query exactly or as a unique prefix."""
    runs = reg.list()
    matches = [r.run_id for r in runs if r.run_id.startswith(query)]
    if len(matches) == 1:
        return matches[0]
    if query in [r.run_id for r in runs]:
        return query
    return ""


def _show_field(label: str, value) -> None:
    if value is not None:
        print(f"  {label:<14} {value}")


def _show_metric(label: str, value, fmt: str) -> None:
    if value is not None:
        print(f"  {label:<14} {fmt.format(value)}")
