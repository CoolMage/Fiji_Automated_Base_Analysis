"""Render approved plot tables to static image files."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
import pandas as pd

from fiji_automated_analysis.visualization.registry import get_plot_spec
from fiji_automated_analysis.visualization.statistics import (
    control_first_order,
    statistical_report_frames,
)


INK = "#000000"
BAR_PALETTE = ("#FFFFFF", "#CFCFCF", "#7A7A7A", "#E8E8E8", "#4D4D4D", "#B5B5B5")


def render_plot(
    input_csv: str | Path,
    output_path: str | Path,
    plot_id: str,
    *,
    title: Optional[str] = None,
    stats_output_path: str | Path | None = None,
    group_order: Sequence[str] | None = None,
    control_label: str | None = None,
    comparisons: str = "control-vs-all",
    error: str = "sem",
) -> Path:
    """Render a registered plot from a canonical plot table."""

    spec = get_plot_spec(plot_id)
    data_path = Path(input_csv)
    image_path = Path(output_path)
    data = pd.read_csv(data_path)
    _validate_columns(data, spec.required_columns)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    if plot_id == "group_bar_stat":
        with plt.rc_context(_paper_rc_params()):
            fig, ax = plt.subplots(figsize=(4.8, 4.6))
            _render_group_bar_stat(
                data,
                ax,
                stats_output_path=stats_output_path,
                group_order=group_order,
                control_label=control_label,
                comparisons=comparisons,
                error=error,
            )
            ax.set_title(title or spec.title)
            fig.tight_layout()
            image_path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(image_path, dpi=600)
            plt.close(fig)
            _validate_rendered_file(image_path)
            return image_path

    sns.set_theme(style="whitegrid", context="notebook")
    fig, ax = plt.subplots(figsize=(7.5, 5.0))

    if plot_id == "group_box_strip":
        order = control_first_order(data["group"], control_label=control_label)
        sns.boxplot(data=data, x="group", y="value", order=order, color="#D8E6F3", ax=ax)
        sns.stripplot(data=data, x="group", y="value", order=order, color="#1F4E79", size=5, jitter=0.18, ax=ax)
        ax.set_xlabel("Group")
        ax.set_ylabel(_metric_label(data))
    elif plot_id == "paired_before_after":
        _render_paired_plot(data, ax)
    elif plot_id == "metric_scatter":
        hue = "group" if "group" in data.columns and data["group"].nunique() > 1 else None
        sns.scatterplot(data=data, x="x", y="y", hue=hue, s=55, color="#1F4E79" if hue is None else None, ax=ax)
        if "label" in data.columns and len(data) <= 20:
            for _, row in data.iterrows():
                ax.annotate(str(row["label"]), (row["x"], row["y"]), xytext=(4, 4), textcoords="offset points", fontsize=8)
        ax.set_xlabel(_single_value(data, "x_metric", "x"))
        ax.set_ylabel(_single_value(data, "y_metric", "y"))
    elif plot_id == "distribution_histogram":
        hue = "group" if "group" in data.columns and data["group"].nunique() > 1 else None
        sns.histplot(data=data, x="value", hue=hue, kde=False, bins="auto", color="#1F4E79" if hue is None else None, ax=ax)
        ax.set_xlabel(_metric_label(data))
        ax.set_ylabel("Count")
    elif plot_id == "stacked_composition":
        pivot = data.pivot_table(index="category", columns="component", values="value", aggfunc="sum", fill_value=0)
        pivot.plot(kind="bar", stacked=True, ax=ax, colormap="tab20c")
        ax.set_xlabel("Category")
        ax.set_ylabel(_metric_label(data))
        ax.legend(title="Component", bbox_to_anchor=(1.02, 1), loc="upper left")
    elif plot_id == "qc_bar_counts":
        sorted_data = data.sort_values("count", ascending=False)
        sns.barplot(data=sorted_data, x="count", y="category", color="#1F4E79", ax=ax)
        ax.set_xlabel("Count")
        ax.set_ylabel("Category")
    else:
        raise AssertionError(f"Renderer missing for registered plot type: {plot_id}")

    ax.set_title(title or spec.title)
    fig.tight_layout()
    image_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(image_path, dpi=160)
    plt.close(fig)

    _validate_rendered_file(image_path)
    return image_path


def _render_group_bar_stat(
    data: pd.DataFrame,
    ax,
    *,
    stats_output_path: str | Path | None,
    group_order: Sequence[str] | None,
    control_label: str | None,
    comparisons: str,
    error: str,
) -> None:
    data = data.copy()
    data["group"] = data["group"].astype(str)
    data["value"] = pd.to_numeric(data["value"], errors="coerce")
    data = data.dropna(subset=["group", "value"])
    if data.empty:
        raise ValueError("The group_bar_stat table has no numeric values.")

    order = list(group_order or control_first_order(data["group"], control_label=control_label))
    data["group"] = pd.Categorical(data["group"], categories=order, ordered=True)
    data = data.sort_values("group")

    summary, pairwise = statistical_report_frames(
        data,
        group_order=order,
        control_label=control_label,
        comparisons=comparisons,
    )
    if stats_output_path:
        _write_stats_sidecar(stats_output_path, summary, pairwise)

    positions = np.arange(len(order), dtype=float)
    centers = [float(summary.loc[summary["group"] == group, "mean"].iloc[0]) for group in order]
    errors = [_error_for_group(summary, group, error) for group in order]
    colors = [BAR_PALETTE[i % len(BAR_PALETTE)] for i in range(len(order))]

    ax.bar(
        positions,
        centers,
        yerr=errors,
        width=0.62,
        color=colors,
        edgecolor=INK,
        linewidth=1.6,
        capsize=4,
        error_kw={"elinewidth": 1.4, "capthick": 1.4, "ecolor": INK},
        zorder=2,
    )

    rng = np.random.default_rng(42)
    for index, group in enumerate(order):
        values = data.loc[data["group"].astype(str) == group, "value"].to_numpy(dtype=float)
        if values.size == 0:
            continue
        jitter = rng.uniform(-0.09, 0.09, size=values.size)
        ax.scatter(
            np.full(values.size, positions[index]) + jitter,
            values,
            s=28,
            facecolor="#FFFFFF",
            edgecolor=INK,
            linewidth=1.0,
            alpha=0.95,
            zorder=3,
        )

    ax.set_xlabel("Group")
    ax.set_ylabel(_metric_label(data))
    ax.set_xticks(positions)
    ax.set_xticklabels(order, rotation=30 if _has_long_labels(order) else 0, ha="right")
    ax.grid(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    _annotate_pairwise(ax, order, summary, pairwise)


def _annotate_pairwise(ax, order: Sequence[str], summary: pd.DataFrame, pairwise: pd.DataFrame) -> None:
    if pairwise.empty:
        return

    group_to_x = {group: index for index, group in enumerate(order)}
    y_candidates: list[float] = []
    for group in order:
        row = summary.loc[summary["group"] == group].iloc[0]
        y_candidates.append(float(row["mean"]) + _nan_to_zero(float(row["sem"])))
    current_ymin, current_ymax = ax.get_ylim()
    y_candidates.append(current_ymax)

    y_max = max(y_candidates)
    y_min = min(0.0, current_ymin, min(y_candidates))
    y_range = y_max - y_min
    if y_range <= 0:
        y_range = max(abs(y_max), 1.0)
    bracket_height = y_range * 0.035
    bracket_gap = y_range * 0.08
    y = y_max + bracket_gap

    for _, comparison in pairwise.iterrows():
        group_a = str(comparison["group_a"])
        group_b = str(comparison["group_b"])
        if group_a not in group_to_x or group_b not in group_to_x:
            continue
        x1 = group_to_x[group_a]
        x2 = group_to_x[group_b]
        label = str(comparison["significance"])
        ax.plot(
            [x1, x1, x2, x2],
            [y, y + bracket_height, y + bracket_height, y],
            color=INK,
            linewidth=1.1,
            clip_on=False,
        )
        ax.text(
            (x1 + x2) / 2,
            y + bracket_height,
            label,
            ha="center",
            va="bottom",
            color=INK,
            fontsize=11,
        )
        y += bracket_gap

    ax.set_ylim(y_min, y + bracket_gap)


def _write_stats_sidecar(stats_output_path: str | Path, summary: pd.DataFrame, pairwise: pd.DataFrame) -> None:
    output = Path(stats_output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    summary = summary.copy()
    summary.insert(0, "section", "group_summary")
    pairwise = pairwise.copy()
    pairwise.insert(0, "section", "pairwise_comparison")
    combined = pd.concat([summary, pairwise], ignore_index=True, sort=False)
    combined.to_csv(output, index=False)


def _error_for_group(summary: pd.DataFrame, group: str, error: str) -> float:
    row = summary.loc[summary["group"] == group].iloc[0]
    if error == "none":
        return 0.0
    if error == "sd":
        return _nan_to_zero(float(row["sd"]))
    if error == "sem":
        return _nan_to_zero(float(row["sem"]))
    if error == "ci95":
        return 1.96 * _nan_to_zero(float(row["sem"]))
    raise ValueError("error must be one of: none, sd, sem, ci95.")


def _render_paired_plot(data: pd.DataFrame, ax) -> None:
    conditions = list(dict.fromkeys(data["condition"].astype(str)))
    for _, subject_rows in data.groupby("subject", sort=False):
        subject_rows = subject_rows.copy()
        subject_rows["condition"] = pd.Categorical(subject_rows["condition"].astype(str), categories=conditions, ordered=True)
        subject_rows = subject_rows.sort_values("condition")
        ax.plot(subject_rows["condition"].astype(str), subject_rows["value"], color="#9AA8B5", linewidth=1.2, alpha=0.8)
        ax.scatter(subject_rows["condition"].astype(str), subject_rows["value"], color="#1F4E79", s=32, zorder=3)
    ax.set_xlabel("Condition")
    ax.set_ylabel(_metric_label(data))


def _metric_label(data: pd.DataFrame) -> str:
    metric = _single_value(data, "metric", "Value")
    unit = _single_value(data, "unit", "")
    return f"{metric} ({unit})" if unit else metric


def _single_value(data: pd.DataFrame, column: str, fallback: str) -> str:
    if column not in data.columns:
        return fallback
    values = [str(value) for value in data[column].dropna().unique() if str(value)]
    return values[0] if len(values) == 1 else fallback


def _validate_columns(data: pd.DataFrame, required_columns: tuple[str, ...]) -> None:
    missing = [column for column in required_columns if column not in data.columns]
    if missing:
        raise ValueError(f"Plot table is missing required column(s): {', '.join(missing)}")
    if data.empty:
        raise ValueError("Plot table has no rows.")


def _paper_rc_params() -> dict[str, object]:
    return {
        "figure.dpi": 140,
        "savefig.dpi": 600,
        "figure.facecolor": "#FFFFFF",
        "axes.facecolor": "#FFFFFF",
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.titlesize": 12,
        "axes.labelsize": 12,
        "axes.edgecolor": INK,
        "axes.linewidth": 1.6,
        "xtick.color": INK,
        "ytick.color": INK,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 5,
        "ytick.major.size": 5,
        "xtick.major.width": 1.3,
        "ytick.major.width": 1.3,
        "axes.grid": False,
        "legend.frameon": False,
    }


def _has_long_labels(labels: Sequence[str]) -> bool:
    return any(len(str(label)) > 9 for label in labels)


def _nan_to_zero(value: float) -> float:
    return 0.0 if math.isnan(value) else value


def _validate_rendered_file(image_path: Path) -> None:
    if not image_path.is_file() or image_path.stat().st_size == 0:
        raise RuntimeError(f"Plot rendering did not create a valid file: {image_path}")
