"""Reusable visualization helpers for Fiji Automated Base Analysis outputs."""

from fiji_automated_analysis.visualization.registry import (
    PlotSpec,
    UnknownPlotError,
    get_plot_spec,
    list_plot_specs,
)
from fiji_automated_analysis.visualization.tables import prepare_plot_table
from fiji_automated_analysis.visualization.renderers import render_plot
from fiji_automated_analysis.visualization.statistics import (
    compare_groups,
    control_first_order,
    summarize_groups,
)

__all__ = [
    "PlotSpec",
    "UnknownPlotError",
    "get_plot_spec",
    "list_plot_specs",
    "prepare_plot_table",
    "render_plot",
    "compare_groups",
    "control_first_order",
    "summarize_groups",
]
