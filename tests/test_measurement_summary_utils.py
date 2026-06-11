from __future__ import annotations

from pathlib import Path

from utils.general.measurement_summary_utils import (
    build_slice_and_animal_summary_rows,
    detect_summary_naming_patterns,
    split_summary_rows_by_measurement_type,
)


def test_detect_summary_naming_patterns(tmp_path: Path) -> None:
    (tmp_path / "Exp").mkdir()
    (tmp_path / "Control").mkdir()

    (tmp_path / "Exp" / "RECA1_GFAP_S100A10_Exp_Potkan1_sc_overview_cut3_x20.ims").write_text("")
    (tmp_path / "Exp" / "RECA1_GFAP_S100A10_Exp_Potkan2_sc_overview_cut1_x20.ims").write_text("")
    (tmp_path / "Control" / "RECA1_GFAP_S100A10_Control_DIRECTaav4_sc_overview_cut2_x20.ims").write_text("")

    detected = detect_summary_naming_patterns(
        str(tmp_path),
        ["Exp", "Control"],
        supported_extensions=[".ims"],
    )

    assert detected["cut_prefix"] == "cut"
    assert detected["keyword_animal_prefixes"]["Exp"] == "Potkan"
    assert detected["keyword_animal_prefixes"]["Control"] == "DIRECTaav"


def test_build_slice_and_animal_summary_rows_average_animal_over_slice_means() -> None:
    summary_rows = [
        {
            "document_name": "RECA1_GFAP_S100A10_Exp_Potkan1_sc_overview_cut1_x20",
            "matched_keyword": "Exp",
            "keywords": "Exp, Control",
            "Channel": "C2",
            "Scope": "Particles",
            "ROI": "ROI_1",
            "Area": "10",
            "Mean": "100",
        },
        {
            "document_name": "RECA1_GFAP_S100A10_Exp_Potkan1_sc_overview_cut1_x20",
            "matched_keyword": "Exp",
            "keywords": "Exp, Control",
            "Channel": "C2",
            "Scope": "Particles",
            "ROI": "ROI_2",
            "Area": "30",
            "Mean": "300",
        },
        {
            "document_name": "RECA1_GFAP_S100A10_Exp_Potkan1_sc_overview_cut2_x20",
            "matched_keyword": "Exp",
            "keywords": "Exp, Control",
            "Channel": "C2",
            "Scope": "Particles",
            "ROI": "ROI_1",
            "Area": "50",
            "Mean": "500",
        },
    ]

    aggregated = build_slice_and_animal_summary_rows(
        summary_rows,
        keyword_animal_prefixes={"Exp": "Potkan"},
        cut_prefix="cut",
    )

    slice_rows = aggregated["slice_rows"]
    animal_rows = aggregated["animal_rows"]

    assert len(slice_rows) == 2
    assert slice_rows[0]["animal_id"] == "Potkan1"
    assert slice_rows[0]["cut_id"] == "cut1"
    assert slice_rows[0]["Area"] == 20.0
    assert slice_rows[0]["Mean"] == 200.0
    assert slice_rows[0]["roi_class"] == "indexed_roi"

    assert len(animal_rows) == 1
    assert animal_rows[0]["animal_id"] == "Potkan1"
    assert animal_rows[0]["slice_count"] == 2
    assert animal_rows[0]["Area"] == 35.0
    assert animal_rows[0]["Mean"] == 350.0


def test_detect_and_aggregate_hyphenated_animal_ids() -> None:
    summary_rows = [
        {
            "document_name": "RECA1_GFAP_S100A10_Control_DIRECTaav9-1_sc_overview_cut1_x20",
            "matched_keyword": "Control",
            "keywords": "Exp, Control",
            "Channel": "C2",
            "Scope": "Particles",
            "ROI": "RECA1_GFAP_S100A10_Control_DIRECTaav9-1_sc_overview_cut1_x20",
            "Area": "10",
            "Mean": "100",
        },
        {
            "document_name": "RECA1_GFAP_S100A10_Control_DIRECTaav9-1_sc_overview_cut2_x20",
            "matched_keyword": "Control",
            "keywords": "Exp, Control",
            "Channel": "C2",
            "Scope": "Particles",
            "ROI": "RECA1_GFAP_S100A10_Control_DIRECTaav9-1_sc_overview_cut2_x20",
            "Area": "30",
            "Mean": "300",
        },
        {
            "document_name": "RECA1_GFAP_S100A10_Control_DIRECTaav9-2_sc_overview_cut1_x20",
            "matched_keyword": "Control",
            "keywords": "Exp, Control",
            "Channel": "C2",
            "Scope": "Particles",
            "ROI": "RECA1_GFAP_S100A10_Control_DIRECTaav9-2_sc_overview_cut1_x20",
            "Area": "50",
            "Mean": "500",
        },
    ]

    aggregated = build_slice_and_animal_summary_rows(
        summary_rows,
        keyword_animal_prefixes={"Control": "DIRECTaav"},
        cut_prefix="cut",
    )

    slice_rows = aggregated["slice_rows"]
    animal_rows = aggregated["animal_rows"]

    assert len(slice_rows) == 3
    assert {row["animal_id"] for row in slice_rows} == {"DIRECTaav9-1", "DIRECTaav9-2"}
    assert {row["roi_class"] for row in slice_rows} == {"matching_named_roi"}

    assert len(animal_rows) == 2
    rows_by_animal = {row["animal_id"]: row for row in animal_rows}

    assert rows_by_animal["DIRECTaav9-1"]["animal_number"] == "9-1"
    assert rows_by_animal["DIRECTaav9-1"]["slice_count"] == 2
    assert rows_by_animal["DIRECTaav9-1"]["Area"] == 20.0
    assert rows_by_animal["DIRECTaav9-1"]["Mean"] == 200.0

    assert rows_by_animal["DIRECTaav9-2"]["animal_number"] == "9-2"
    assert rows_by_animal["DIRECTaav9-2"]["slice_count"] == 1
    assert rows_by_animal["DIRECTaav9-2"]["Area"] == 50.0
    assert rows_by_animal["DIRECTaav9-2"]["Mean"] == 500.0


def test_animal_summary_keeps_measurement_types_separate() -> None:
    summary_rows = [
        {
            "document_name": "Exp_Potkan1_cut1",
            "matched_keyword": "Exp",
            "keywords": "Exp, Control",
            "MeasurementType": "RawIntensity",
            "Channel": "C1",
            "Scope": "RawROI",
            "ROI": "Exp_Potkan1_cut1",
            "Area": "10",
            "Mean": "100",
        },
        {
            "document_name": "Exp_Potkan1_cut2",
            "matched_keyword": "Exp",
            "keywords": "Exp, Control",
            "MeasurementType": "RawIntensity",
            "Channel": "C1",
            "Scope": "RawROI",
            "ROI": "Exp_Potkan1_cut2",
            "Area": "30",
            "Mean": "300",
        },
        {
            "document_name": "Exp_Potkan1_cut1",
            "matched_keyword": "Exp",
            "keywords": "Exp, Control",
            "MeasurementType": "ThresholdedIntensity",
            "Channel": "C1",
            "Scope": "ThresholdedROI",
            "ROI": "Exp_Potkan1_cut1",
            "Area": "4",
            "Mean": "200",
        },
        {
            "document_name": "Exp_Potkan1_cut2",
            "matched_keyword": "Exp",
            "keywords": "Exp, Control",
            "MeasurementType": "ThresholdedIntensity",
            "Channel": "C1",
            "Scope": "ThresholdedROI",
            "ROI": "Exp_Potkan1_cut2",
            "Area": "8",
            "Mean": "220",
        },
    ]

    grouped = split_summary_rows_by_measurement_type(summary_rows)
    assert set(grouped) == {"RawIntensity", "ThresholdedIntensity"}

    aggregated = build_slice_and_animal_summary_rows(
        summary_rows,
        keyword_animal_prefixes={"Exp": "Potkan"},
        cut_prefix="cut",
    )

    assert len(aggregated["animal_rows"]) == 2
    rows_by_type = {
        row["MeasurementType"]: row for row in aggregated["animal_rows"]
    }

    assert rows_by_type["RawIntensity"]["animal_id"] == "Potkan1"
    assert rows_by_type["RawIntensity"]["slice_count"] == 2
    assert rows_by_type["RawIntensity"]["Area"] == 20.0
    assert rows_by_type["RawIntensity"]["Mean"] == 200.0

    assert rows_by_type["ThresholdedIntensity"]["animal_id"] == "Potkan1"
    assert rows_by_type["ThresholdedIntensity"]["slice_count"] == 2
    assert rows_by_type["ThresholdedIntensity"]["Area"] == 6.0
    assert rows_by_type["ThresholdedIntensity"]["Mean"] == 210.0
