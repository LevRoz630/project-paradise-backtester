"""bt report — generate HTML report for a run."""
from __future__ import annotations

import sys
from pathlib import Path


def add_args(parser):
    parser.add_argument("run_id", help="Run ID (or unique prefix)")
    parser.add_argument("--runs-dir", default="bt_runs", help="Registry directory (default: bt_runs)")
    parser.add_argument("--open", dest="open_browser", action="store_true",
                        help="Open report in browser after generating")


def run(args):
    from vectorbt.registry import Registry
    from bttool.report import generate_html_report
    from bttool.commands.show_cmd import _resolve_run_id

    reg = Registry(base_dir=args.runs_dir)
    run_id = _resolve_run_id(reg, args.run_id)
    if not run_id:
        print(f"Error: no run found matching '{args.run_id}'", file=sys.stderr)
        sys.exit(1)

    details = reg.show(run_id)
    run_dir = Path(args.runs_dir) / details["path"]

    print(f"Generating report for {run_id[:16]}...")
    report_path = generate_html_report(run_dir, details)
    print(f"Report saved: {report_path}")

    if args.open_browser:
        import webbrowser
        webbrowser.open(report_path.resolve().as_uri())
