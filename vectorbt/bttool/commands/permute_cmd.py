"""bt permute — run permutation test on a saved backtest run."""
from __future__ import annotations

import sys
from pathlib import Path


def add_args(parser):
    parser.add_argument("run_id", help="Run ID (or unique prefix)")
    parser.add_argument("--n", type=int, default=1000, dest="n_permutations",
                        help="Number of permutations (default: 1000)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--correction", choices=["bonferroni", "holm", "none"],
                        default="bonferroni", help="Multiple testing correction (default: bonferroni)")
    parser.add_argument("--runs-dir", default="bt_runs", help="Registry directory (default: bt_runs)")


def run(args):
    from vectorbt.registry import Registry
    from bttool.runner import fetch_data, load_strategy
    from bttool.permutation import run_permutation_test, compute_stats, save_permutation_results, significance_stars
    from bttool.commands.show_cmd import _resolve_run_id

    reg = Registry(base_dir=args.runs_dir)
    run_id = _resolve_run_id(reg, args.run_id)
    if not run_id:
        print(f"Error: no run found matching '{args.run_id}'", file=sys.stderr)
        sys.exit(1)

    details = reg.show(run_id)
    cfg = details.get("config", {})
    data_cfg = cfg.get("data", {})
    strategy_cfg = cfg.get("strategy", {})

    strategy_file = strategy_cfg.get("file")
    if not strategy_file:
        print("Error: run config has no strategy file path — cannot permute.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading strategy: {strategy_file}")
    try:
        strategy_fn = load_strategy(strategy_file)
    except Exception as e:
        print(f"Error loading strategy: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching data for {data_cfg.get('symbol')} ...")
    try:
        df = fetch_data(
            source=data_cfg.get("source", ""),
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

    print("Running original strategy ...")
    try:
        original_portfolio = strategy_fn(df)
    except Exception as e:
        print(f"Strategy error: {e}", file=sys.stderr)
        sys.exit(1)

    correction = args.correction if args.correction != "none" else None
    print(f"Running {args.n_permutations} permutations (seed={args.seed}) ...")

    results = run_permutation_test(
        strategy_fn=strategy_fn,
        data=df,
        original_portfolio=original_portfolio,
        n_permutations=args.n_permutations,
        seed=args.seed,
    )

    stats = compute_stats(results, correction=correction or "none")

    run_dir = Path(args.runs_dir) / details["path"]
    saved_path = save_permutation_results(run_dir, results, stats)

    # Print results table
    print()
    print(f"{'Metric':<20}  {'Observed':>10}  {'Null Mean':>10}  {'Null Std':>9}  {'Percentile':>10}  {'p-value':>9}  {'Sig':>4}")
    print("─" * 85)
    for metric, s in stats.items():
        if s.get("observed") is None:
            continue
        p = s.get("p_value_adjusted")
        if p is None:
            p = s.get("p_value")
        stars = significance_stars(p)
        print(
            f"{metric:<20}  "
            f"{s['observed']:>10.4f}  "
            f"{(s['null_mean'] or 0):>10.4f}  "
            f"{(s['null_std'] or 0):>9.4f}  "
            f"{(s['percentile'] or 0):>9.1f}%  "
            f"{(p or 0):>9.4f}  "
            f"{stars:>4}"
        )

    print()
    print("Significance: *** p<0.01  ** p<0.05  * p<0.10")
    if correction:
        print(f"Correction: {correction}")
    print()
    print(f"Saved: {saved_path}")
