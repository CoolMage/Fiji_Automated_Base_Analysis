from __future__ import annotations

import pandas as pd
import pytest

from fiji_automated_analysis.visualization import (
    UnknownPlotError,
    compare_groups,
    control_first_order,
    get_plot_spec,
    list_plot_specs,
    prepare_plot_table,
    render_plot,
)


def test_plot_registry_lists_expected_plot_types() -> None:
    plot_ids = {spec.plot_id for spec in list_plot_specs()}

    assert {
        "group_box_strip",
        "group_bar_stat",
        "paired_before_after",
        "metric_scatter",
        "distribution_histogram",
        "stacked_composition",
        "qc_bar_counts",
    }.issubset(plot_ids)
    assert get_plot_spec("group_box_strip").required_columns == ("group", "value")
    assert get_plot_spec("group_bar_stat").required_columns == ("group", "value")


def test_unknown_plot_type_requires_user_approval() -> None:
    with pytest.raises(UnknownPlotError) as exc_info:
        get_plot_spec("raincloud_by_group")

    assert "explicit user approval" in str(exc_info.value)


def test_prepare_plot_table_uses_biological_group_and_metric(tmp_path) -> None:
    input_csv = tmp_path / "animal_summary.csv"
    output_csv = tmp_path / "plot_table.csv"
    pd.DataFrame(
        [
            {"matched_keyword": "Control", "animal_id": "Rat1", "Mean": 10.0},
            {"matched_keyword": "Treatment", "animal_id": "Rat2", "Mean": 18.5},
        ]
    ).to_csv(input_csv, index=False)

    prepared_path = prepare_plot_table(
        input_csv,
        output_csv,
        "group_bar_stat",
        metric="Mean",
    )

    prepared = pd.read_csv(prepared_path)
    assert list(prepared["group"]) == ["Control", "Treatment"]
    assert list(prepared["subject"]) == ["Rat1", "Rat2"]
    assert list(prepared["value"]) == [10.0, 18.5]
    assert list(prepared["metric"].unique()) == ["Mean"]


def test_control_group_is_ordered_first() -> None:
    assert control_first_order(["4MU", "Control", "Treatment"]) == [
        "Control",
        "4MU",
        "Treatment",
    ]


def test_prepare_qc_bar_counts_counts_categories(tmp_path) -> None:
    input_csv = tmp_path / "rows.csv"
    output_csv = tmp_path / "qc_counts.csv"
    pd.DataFrame(
        [
            {"matched_keyword": "Control", "filename": "a"},
            {"matched_keyword": "Control", "filename": "b"},
            {"matched_keyword": "Treatment", "filename": "c"},
        ]
    ).to_csv(input_csv, index=False)

    prepare_plot_table(input_csv, output_csv, "qc_bar_counts")

    prepared = pd.read_csv(output_csv)
    counts = dict(zip(prepared["category"], prepared["count"]))
    assert counts == {"Control": 2, "Treatment": 1}


def test_render_plot_writes_non_empty_png(tmp_path) -> None:
    table_csv = tmp_path / "plot_table.csv"
    image_path = tmp_path / "plot.png"
    pd.DataFrame(
        [
            {"group": "Control", "subject": "Rat1", "value": 10.0, "metric": "Mean"},
            {"group": "Treatment", "subject": "Rat2", "value": 18.5, "metric": "Mean"},
            {"group": "Treatment", "subject": "Rat3", "value": 21.0, "metric": "Mean"},
        ]
    ).to_csv(table_csv, index=False)

    rendered = render_plot(table_csv, image_path, "group_box_strip")

    assert rendered == image_path
    assert image_path.is_file()
    assert image_path.stat().st_size > 0


def test_group_bar_stat_selects_test_and_writes_stats_csv(tmp_path) -> None:
    table_csv = tmp_path / "plot_table.csv"
    image_path = tmp_path / "bar.png"
    stats_path = tmp_path / "bar_stats.csv"
    pd.DataFrame(
        [
            {"group": "4MU", "subject": "Rat5", "value": 18.0, "metric": "Mean"},
            {"group": "Control", "subject": "Rat1", "value": 9.0, "metric": "Mean"},
            {"group": "Control", "subject": "Rat2", "value": 10.0, "metric": "Mean"},
            {"group": "Control", "subject": "Rat3", "value": 11.0, "metric": "Mean"},
            {"group": "Control", "subject": "Rat4", "value": 12.0, "metric": "Mean"},
            {"group": "4MU", "subject": "Rat6", "value": 19.0, "metric": "Mean"},
            {"group": "4MU", "subject": "Rat7", "value": 20.0, "metric": "Mean"},
            {"group": "4MU", "subject": "Rat8", "value": 21.0, "metric": "Mean"},
        ]
    ).to_csv(table_csv, index=False)

    rendered = render_plot(
        table_csv,
        image_path,
        "group_bar_stat",
        stats_output_path=stats_path,
        title="Mean intensity by group",
    )

    assert rendered == image_path
    assert image_path.is_file()
    assert image_path.stat().st_size > 0
    stats_table = pd.read_csv(stats_path)
    pairwise = stats_table.loc[stats_table["section"] == "pairwise_comparison"].iloc[0]
    assert pairwise["group_a"] == "Control"
    assert pairwise["group_b"] == "4MU"
    assert "permutation" in pairwise["test"].lower()
    assert pairwise["significance"] in {"*", "**", "***", "****", "ns"}


def test_group_bar_stat_writes_non_empty_pdf(tmp_path) -> None:
    table_csv = tmp_path / "plot_table.csv"
    image_path = tmp_path / "bar.pdf"
    pd.DataFrame(
        [
            {"group": "Control", "subject": "Rat1", "value": 10.0, "metric": "Mean"},
            {"group": "Control", "subject": "Rat2", "value": 12.0, "metric": "Mean"},
            {"group": "4MU", "subject": "Rat3", "value": 18.5, "metric": "Mean"},
            {"group": "4MU", "subject": "Rat4", "value": 21.0, "metric": "Mean"},
        ]
    ).to_csv(table_csv, index=False)

    render_plot(table_csv, image_path, "group_bar_stat")

    assert image_path.is_file()
    assert image_path.stat().st_size > 0


def test_compare_groups_reports_normality_applicability() -> None:
    data = pd.DataFrame(
        [
            {"group": "Control", "value": 1.0},
            {"group": "Control", "value": 2.0},
            {"group": "Control", "value": 3.0},
            {"group": "4MU", "value": 6.0},
            {"group": "4MU", "value": 7.0},
            {"group": "4MU", "value": 8.0},
        ]
    )

    comparisons = compare_groups(data)

    assert comparisons[0].group_a == "Control"
    assert comparisons[0].group_b == "4MU"
    assert comparisons[0].normality_a_p == comparisons[0].normality_a_p
