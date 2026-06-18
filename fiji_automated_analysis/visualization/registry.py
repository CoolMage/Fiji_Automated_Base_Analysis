"""Registry of approved plot types for microscopy measurement outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple


@dataclass(frozen=True)
class PlotSpec:
    """Stable contract for one approved plot type."""

    plot_id: str
    title: str
    description: str
    required_columns: Tuple[str, ...]
    optional_columns: Tuple[str, ...] = ()
    preferred_grain: str = "biological_replicate"


class UnknownPlotError(ValueError):
    """Raised when a requested plot type is not in the approved registry."""


PLOT_REGISTRY: Dict[str, PlotSpec] = {
    "group_box_strip": PlotSpec(
        plot_id="group_box_strip",
        title="Group box-and-strip plot",
        description=(
            "Compare one numeric measurement across experimental groups while "
            "showing individual biological replicates."
        ),
        required_columns=("group", "value"),
        optional_columns=("subject", "metric", "unit"),
    ),
    "group_bar_stat": PlotSpec(
        plot_id="group_bar_stat",
        title="Group bar plot with statistical annotations",
        description=(
            "Compare one numeric measurement across experimental groups as "
            "mean bars with replicate points, SEM error bars, assumption "
            "checks, selected statistical tests, and significance brackets."
        ),
        required_columns=("group", "value"),
        optional_columns=("subject", "metric", "unit"),
    ),
    "paired_before_after": PlotSpec(
        plot_id="paired_before_after",
        title="Paired before/after plot",
        description=(
            "Show within-subject changes across two or more ordered conditions."
        ),
        required_columns=("subject", "condition", "value"),
        optional_columns=("group", "metric", "unit"),
    ),
    "metric_scatter": PlotSpec(
        plot_id="metric_scatter",
        title="Metric scatter plot",
        description=(
            "Inspect the relationship between two numeric measurements at a "
            "consistent observation grain."
        ),
        required_columns=("x", "y"),
        optional_columns=("label", "group", "x_metric", "y_metric"),
    ),
    "distribution_histogram": PlotSpec(
        plot_id="distribution_histogram",
        title="Distribution histogram",
        description="Show the distribution of one numeric measurement.",
        required_columns=("value",),
        optional_columns=("group", "metric", "unit"),
        preferred_grain="observation",
    ),
    "stacked_composition": PlotSpec(
        plot_id="stacked_composition",
        title="Stacked composition plot",
        description=(
            "Show how a total measurement breaks down across components within "
            "each category."
        ),
        required_columns=("category", "component", "value"),
        optional_columns=("unit",),
    ),
    "qc_bar_counts": PlotSpec(
        plot_id="qc_bar_counts",
        title="QC count bar plot",
        description="Show file, image, ROI, row, or failure counts by category.",
        required_columns=("category", "count"),
        optional_columns=("group",),
        preferred_grain="quality_control",
    ),
}


def list_plot_specs() -> Iterable[PlotSpec]:
    """Return approved plot specifications sorted by plot id."""

    return [PLOT_REGISTRY[key] for key in sorted(PLOT_REGISTRY)]


def get_plot_spec(plot_id: str) -> PlotSpec:
    """Return a plot specification or raise with the required approval message."""

    try:
        return PLOT_REGISTRY[plot_id]
    except KeyError as exc:
        known = ", ".join(sorted(PLOT_REGISTRY))
        raise UnknownPlotError(
            f"Unknown plot type '{plot_id}'. Approved plot types are: {known}. "
            "Do not add a new plot type without explicit user approval."
        ) from exc
