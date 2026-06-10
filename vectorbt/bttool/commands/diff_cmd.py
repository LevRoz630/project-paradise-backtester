"""bt diff — compare two backtest runs side-by-side."""
from __future__ import annotations

import sys


def add_args(parser):
    parser.add_argument("run_id_1", help="First run ID (or unique prefix)")
    parser.add_argument("run_id_2", help="Second run ID (or unique prefix)")
    parser.add_argument("--runs-dir", default="bt_runs", help="Registry directory (default: bt_runs)")


def run(args):
    from vectorbt.registry import Registry

    reg = Registry(base_dir=args.runs_dir)

    run_id_1 = _resolve_run_id(reg, args.run_id_1)
    run_id_2 = _resolve_run_id(reg, args.run_id_2)

    if not run_id_1:
        print(f"Error: no run found matching '{args.run_id_1}'", file=sys.stderr)
        sys.exit(1)
    if not run_id_2:
        print(f"Error: no run found matching '{args.run_id_2}'", file=sys.stderr)
        sys.exit(1)

    diff = reg.compare(run_id_1, run_id_2)

    r1_short = run_id_1[:12] + "..."
    r2_short = run_id_2[:12] + "..."

    col = {"field": 20, "v": 16, "diff": 12}
    header = (
        f"{'':>{col['field']}}  "
        f"{'RUN 1':<{col['v']}}  "
        f"{'RUN 2':<{col['v']}}  "
        f"{'DIFF':<{col['diff']}}"
    )
    separator = "─" * len(header)
    print(header)
    print(separator)

    for row in diff["rows"]:
        field = row["field"]
        v1 = _fmt(row["run1"])
        v2 = _fmt(row["run2"])
        d = _fmt(row["diff"])

        print(
            f"{field:>{col['field']}}  "
            f"{v1:<{col['v']}}  "
            f"{v2:<{col['v']}}  "
            f"{d:<{col['diff']}}"
        )


def _resolve_run_id(reg, query: str) -> str:
    runs = reg.list()
    matches = [r.run_id for r in runs if r.run_id.startswith(query)]
    if len(matches) == 1:
        return matches[0]
    if query in [r.run_id for r in runs]:
        return query
    return ""


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:+.3f}" if abs(value) < 1000 else f"{value:+.1f}"
    return str(value)
