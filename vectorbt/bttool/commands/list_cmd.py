"""bt list — list all stored backtest runs."""
from __future__ import annotations


def add_args(parser):
    parser.add_argument("--limit", type=int, default=20, help="Max runs to show (default: 20)")
    parser.add_argument("--sort", choices=["date", "sharpe", "returns"], default="date",
                        help="Sort by: date (default), sharpe, returns")
    parser.add_argument("--filter", dest="filter_by", help="Filter by symbol or strategy name")
    parser.add_argument("--runs-dir", default="bt_runs", help="Registry directory (default: bt_runs)")


def run(args):
    from vectorbt.registry import Registry

    reg = Registry(base_dir=args.runs_dir)
    runs = reg.list(sort_by=args.sort, filter_by=args.filter_by)

    if not runs:
        print("No runs found.")
        return

    runs = runs[: args.limit]

    col_widths = {"run_id": 19, "date": 10, "symbol": 12, "sharpe": 8, "returns": 9}
    header = (
        f"{'RUN_ID':<{col_widths['run_id']}}  "
        f"{'DATE':<{col_widths['date']}}  "
        f"{'SYMBOL':<{col_widths['symbol']}}  "
        f"{'SHARPE':>{col_widths['sharpe']}}  "
        f"{'RETURNS':>{col_widths['returns']}}"
    )
    separator = "─" * len(header)
    print(header)
    print(separator)

    for entry in runs:
        run_id_short = entry.run_id[:16] + "..."
        date = entry.timestamp[:10] if entry.timestamp else "-"
        symbol = (entry.symbol or "-")[:col_widths["symbol"]]
        sharpe = entry.summary.get("sharpe_ratio")
        ret = entry.summary.get("total_return")

        sharpe_str = f"{sharpe:.2f}" if sharpe is not None else "-"
        ret_str = f"{ret:.1%}" if ret is not None else "-"

        print(
            f"{run_id_short:<{col_widths['run_id']}}  "
            f"{date:<{col_widths['date']}}  "
            f"{symbol:<{col_widths['symbol']}}  "
            f"{sharpe_str:>{col_widths['sharpe']}}  "
            f"{ret_str:>{col_widths['returns']}}"
        )
