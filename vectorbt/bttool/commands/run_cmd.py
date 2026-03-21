"""bt run — execute a backtest and save it to the registry."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict


def add_args(parser):
    parser.add_argument("--source", choices=["ccxt", "yfinance", "csv"], help="Data source")
    parser.add_argument("--exchange", help="Exchange name (CCXT only)")
    parser.add_argument("--symbol", help="Trading symbol, e.g. BTC/USDT")
    parser.add_argument("--file", help="Path to CSV file (csv source only)")
    parser.add_argument("--interval", default="1d", help="Bar interval: 1m 5m 15m 1h 4h 1d")
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--strategy", help="Path to strategy .py file")
    parser.add_argument("--config", help="Path to config JSON file")
    parser.add_argument("--runs-dir", default="bt_runs", help="Registry directory (default: bt_runs)")


def _load_config_file(path: str) -> Dict[str, Any]:
    with open(path) as f:
        return json.load(f)


def _build_config(args) -> Dict[str, Any]:
    """Merge config file (if any) with CLI flags. CLI flags take precedence."""
    cfg: Dict[str, Any] = {}
    if args.config:
        cfg = _load_config_file(args.config)

    data = cfg.setdefault("data", {})
    if args.source:
        data["source"] = args.source
    if args.exchange:
        data["exchange"] = args.exchange
    if args.symbol:
        data["symbol"] = args.symbol
    if args.file:
        data["file"] = args.file
    if args.interval:
        data["interval"] = args.interval
    if args.start:
        data["start"] = args.start
    if args.end:
        data["end"] = args.end

    strategy = cfg.setdefault("strategy", {})
    if args.strategy:
        strategy["file"] = args.strategy
        strategy["name"] = Path(args.strategy).stem

    return cfg


def run(args):
    from bttool.runner import fetch_data, load_strategy, extract_metrics, _hash_dataframe
    from vectorbt.registry import Registry

    cfg = _build_config(args)
    data_cfg = cfg.get("data", {})
    strategy_cfg = cfg.get("strategy", {})

    source = data_cfg.get("source")
    if not source:
        print("Error: --source is required (ccxt, yfinance, csv)", file=sys.stderr)
        sys.exit(2)

    strategy_file = strategy_cfg.get("file")
    if not strategy_file:
        print("Error: --strategy is required", file=sys.stderr)
        sys.exit(2)

    print(f"Fetching data: {data_cfg.get('symbol')} via {source} ...")
    try:
        df = fetch_data(
            source=source,
            symbol=data_cfg.get("symbol", ""),
            interval=data_cfg.get("interval", "1d"),
            start=data_cfg.get("start", ""),
            end=data_cfg.get("end", ""),
            exchange=data_cfg.get("exchange"),
            file=data_cfg.get("file"),
        )
    except Exception as e:
        print(f"Data source error: {e}", file=sys.stderr)
        sys.exit(3)

    # Record data hash for provenance tracking
    data_cfg["hash"] = _hash_dataframe(df)

    print(f"Running strategy: {strategy_file} ...")
    try:
        strategy_fn = load_strategy(strategy_file)
        portfolio = strategy_fn(df)
    except Exception as e:
        print(f"Strategy error: {e}", file=sys.stderr)
        sys.exit(1)

    print("Extracting metrics ...")
    try:
        from bttool.artifacts import extract_full_metrics
        metrics = extract_full_metrics(portfolio)
    except Exception as e:
        print(f"Metrics error: {e}", file=sys.stderr)
        sys.exit(1)

    reg = Registry(base_dir=args.runs_dir)
    entry = reg.create(cfg, summary=metrics)

    print("Saving artifacts ...")
    from bttool.artifacts import save_artifacts
    from pathlib import Path as _Path
    run_dir = _Path(args.runs_dir) / entry.path
    saved, errors = save_artifacts(run_dir, portfolio)
    if errors:
        print("\nVALIDATION WARNINGS:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)

    print()
    print(f"Run ID : {entry.run_id}")
    print(f"Symbol : {data_cfg.get('symbol')}")
    print(f"Period : {data_cfg.get('start')} → {data_cfg.get('end')}")
    print()
    _print_metrics(metrics)
    print()
    print(f"Saved  : {entry.path}")
    for name, path in saved.items():
        print(f"         {Path(path).name}")


def _print_metrics(metrics: Dict[str, Any]) -> None:
    fields = [
        ("Total Return", metrics.get("total_return"), "{:.2%}"),
        ("Sharpe Ratio", metrics.get("sharpe_ratio"), "{:.3f}"),
        ("Max Drawdown", metrics.get("max_drawdown"), "{:.2%}"),
        ("Win Rate",     metrics.get("win_rate"),     "{:.2%}"),
        ("Total Trades", metrics.get("total_trades"), "{}"),
    ]
    for label, value, fmt in fields:
        if value is not None:
            print(f"  {label:<14} {fmt.format(value)}")
