"""Command-line interface for approved microscopy plot rendering."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

from fiji_automated_analysis.visualization.registry import list_plot_specs
from fiji_automated_analysis.visualization.renderers import render_plot
from fiji_automated_analysis.visualization.tables import prepare_plot_table


def _parse_column_map(values: List[str] | None) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"Column mapping must use canonical=source format: {value}")
        canonical, source = value.split("=", 1)
        canonical = canonical.strip()
        source = source.strip()
        if not canonical or not source:
            raise ValueError(f"Column mapping must not be empty: {value}")
        mapping[canonical] = source
    return mapping


def _parse_group_order(value: str | None) -> List[str] | None:
    if not value:
        return None
    groups = [item.strip() for item in value.split(",") if item.strip()]
    return groups or None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare and render approved Fiji measurement visualizations.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-plots", help="List approved plot types.")

    prepare = subparsers.add_parser("prepare-tables", help="Prepare a canonical plot table.")
    prepare.add_argument("--input", required=True, help="Input measurement summary CSV.")
    prepare.add_argument("--output", required=True, help="Output canonical plot table CSV.")
    prepare.add_argument("--plot-id", required=True, help="Approved plot type id.")
    prepare.add_argument("--metric", help="Numeric measurement column to plot.")
    prepare.add_argument(
        "--column",
        action="append",
        help="Canonical-to-source mapping, for example --column group=Treatment.",
    )

    render = subparsers.add_parser("render", help="Render a prepared plot table.")
    render.add_argument("--input", required=True, help="Prepared plot table CSV.")
    render.add_argument("--output", required=True, help="Output image path, usually PNG or PDF.")
    render.add_argument("--plot-id", required=True, help="Approved plot type id.")
    render.add_argument("--title", help="Optional visible plot title.")
    render.add_argument(
        "--stats-output",
        help="Optional CSV path for statistical diagnostics and pairwise tests.",
    )
    render.add_argument(
        "--control-label",
        help="Exact control group label to place first and use for control-vs-all comparisons.",
    )
    render.add_argument(
        "--group-order",
        help="Comma-separated group order. If omitted, detected control is placed first.",
    )
    render.add_argument(
        "--comparisons",
        choices=("control-vs-all", "all-pairs"),
        default="control-vs-all",
        help="Pairwise comparisons used for statistical annotations.",
    )
    render.add_argument(
        "--error",
        choices=("sem", "sd", "ci95", "none"),
        default="sem",
        help="Error bars for group_bar_stat plots.",
    )

    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        if args.command == "list-plots":
            for spec in list_plot_specs():
                print(f"{spec.plot_id}\t{spec.title}\t{spec.description}")
            return 0

        if args.command == "prepare-tables":
            output = prepare_plot_table(
                Path(args.input),
                Path(args.output),
                args.plot_id,
                metric=args.metric,
                column_map=_parse_column_map(args.column),
            )
            print(f"Prepared plot table: {output}")
            return 0

        if args.command == "render":
            output = render_plot(
                Path(args.input),
                Path(args.output),
                args.plot_id,
                title=args.title,
                stats_output_path=args.stats_output,
                group_order=_parse_group_order(args.group_order),
                control_label=args.control_label,
                comparisons=args.comparisons,
                error=args.error,
            )
            print(f"Rendered plot: {output}")
            if args.stats_output:
                print(f"Statistical report: {args.stats_output}")
            return 0
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
