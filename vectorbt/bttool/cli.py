"""bt — Backtest Runner CLI entry point."""
from __future__ import annotations

import argparse
import sys

from bttool.commands import run_cmd, list_cmd, show_cmd, diff_cmd, report_cmd


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bt",
        description="Backtest Runner — run, list, inspect, and compare backtests.",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    run_cmd.add_args(sub.add_parser("run", help="Execute a backtest"))
    list_cmd.add_args(sub.add_parser("list", help="List all stored runs"))
    show_cmd.add_args(sub.add_parser("show", help="Display run details"))
    diff_cmd.add_args(sub.add_parser("diff", help="Compare two runs side-by-side"))
    report_cmd.add_args(sub.add_parser("report", help="Generate HTML report for a run"))

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "run":    run_cmd.run,
        "list":   list_cmd.run,
        "show":   show_cmd.run,
        "diff":   diff_cmd.run,
        "report": report_cmd.run,
    }
    try:
        dispatch[args.command](args)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
