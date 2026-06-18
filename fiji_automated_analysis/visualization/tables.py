"""Prepare measurement summary CSV files for registered plot renderers."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Mapping, Optional

import pandas as pd

from fiji_automated_analysis.visualization.registry import get_plot_spec


DEFAULT_COLUMN_CANDIDATES: Mapping[str, tuple[str, ...]] = {
    "group": ("matched_keyword", "group", "Group", "condition", "Condition"),
    "subject": ("animal_id", "subject", "Subject", "sample_id", "Sample"),
    "condition": ("MeasurementType", "condition", "Condition", "timepoint", "Timepoint"),
    "category": ("matched_keyword", "category", "Category", "group", "Group"),
    "component": ("MeasurementType", "Channel", "component", "Component", "roi_class"),
    "label": ("animal_id", "document_name", "Document", "filename", "label"),
}


def prepare_plot_table(
    input_csv: str | Path,
    output_csv: str | Path,
    plot_id: str,
    *,
    metric: Optional[str] = None,
    column_map: Optional[Mapping[str, str]] = None,
) -> Path:
    """Create a canonical plot table for one registered plot type.

    The output keeps source columns and adds canonical columns required by the
    selected plot specification. Missing plot types fail through the registry.
    """

    spec = get_plot_spec(plot_id)
    input_path = Path(input_csv)
    output_path = Path(output_csv)
    data = pd.read_csv(input_path)
    if data.empty:
        raise ValueError(f"Input CSV has no rows: {input_path}")

    resolved_map = dict(column_map or {})
    prepared = data.copy()

    if plot_id in {
        "group_box_strip",
        "group_bar_stat",
        "paired_before_after",
        "distribution_histogram",
        "stacked_composition",
    }:
        metric_column = metric or resolved_map.get("value") or _first_numeric_column(data)
        prepared["value"] = _numeric_series(data, metric_column)
        prepared["metric"] = metric_column

    if plot_id == "metric_scatter":
        x_column = resolved_map.get("x")
        y_column = resolved_map.get("y")
        if not x_column or not y_column:
            numeric_columns = _numeric_columns(data)
            if len(numeric_columns) < 2:
                raise ValueError("metric_scatter requires two numeric columns or explicit x/y column mapping.")
            x_column = x_column or numeric_columns[0]
            y_column = y_column or numeric_columns[1]
        prepared["x"] = _numeric_series(data, x_column)
        prepared["y"] = _numeric_series(data, y_column)
        prepared["x_metric"] = x_column
        prepared["y_metric"] = y_column

    if plot_id == "qc_bar_counts":
        category_column = _resolve_column(data, "category", resolved_map)
        count_column = resolved_map.get("count")
        if count_column:
            prepared = data[[category_column, count_column]].copy()
            prepared["category"] = prepared[category_column].astype(str)
            prepared["count"] = _numeric_series(prepared, count_column)
        else:
            prepared = (
                data[category_column]
                .astype(str)
                .value_counts()
                .rename_axis("category")
                .reset_index(name="count")
            )

    for canonical in ("group", "subject", "condition", "category", "component", "label"):
        if canonical in spec.required_columns or canonical in spec.optional_columns:
            if canonical not in prepared:
                source = _resolve_column(data, canonical, resolved_map, required=canonical in spec.required_columns)
                if source:
                    prepared[canonical] = data[source].astype(str)

    _validate_required_columns(prepared, spec.required_columns)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prepared.to_csv(output_path, index=False)
    return output_path


def _resolve_column(
    data: pd.DataFrame,
    canonical: str,
    column_map: Mapping[str, str],
    *,
    required: bool = False,
) -> Optional[str]:
    explicit = column_map.get(canonical)
    if explicit:
        if explicit not in data.columns:
            raise ValueError(f"Mapped column '{explicit}' for '{canonical}' was not found.")
        return explicit

    for candidate in DEFAULT_COLUMN_CANDIDATES.get(canonical, ()):
        if candidate in data.columns:
            return candidate

    if required:
        raise ValueError(f"Could not resolve required column '{canonical}'.")
    return None


def _numeric_columns(data: pd.DataFrame) -> list[str]:
    numeric_columns: list[str] = []
    for column in data.columns:
        values = pd.to_numeric(data[column], errors="coerce")
        if values.notna().any():
            numeric_columns.append(column)
    return numeric_columns


def _first_numeric_column(data: pd.DataFrame) -> str:
    numeric_columns = _numeric_columns(data)
    if not numeric_columns:
        raise ValueError("No numeric measurement columns were found.")
    return numeric_columns[0]


def _numeric_series(data: pd.DataFrame, column: str) -> pd.Series:
    if column not in data.columns:
        raise ValueError(f"Numeric column '{column}' was not found.")
    values = pd.to_numeric(data[column], errors="coerce")
    if not values.notna().any():
        raise ValueError(f"Column '{column}' does not contain numeric values.")
    return values


def _validate_required_columns(data: pd.DataFrame, required_columns: tuple[str, ...]) -> None:
    missing = [column for column in required_columns if column not in data.columns]
    if missing:
        raise ValueError(f"Prepared table is missing required column(s): {', '.join(missing)}")
