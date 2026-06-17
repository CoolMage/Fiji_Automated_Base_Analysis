from fiji_automated_analysis.macros_lib import MACROS_LIB
from fiji_automated_analysis.utils.general.macro_builder import ImageData, MacroBuilder


MACRO_NAME = "measure_iba1_cd206_cd86_3d_colocalization"


def test_iba1_cd206_cd86_macro_is_registered_with_outputs() -> None:
    macro = MACROS_LIB[MACRO_NAME]
    profile = MACROS_LIB.get_profile(MACRO_NAME)

    assert profile is not None
    assert profile.apply_roi_templates is True
    assert profile.save_processed_images is True
    assert profile.save_measurement_csv is True
    assert profile.generate_measurement_summary is True

    assert 'iba1Channel = 1;' in macro
    assert 'cd206Channel = 2;' in macro
    assert 'cd86Channel = 3;' in macro
    assert 'Stack.getStatistics(' in macro
    assert 'imageCalculator("AND create stack"' in macro
    assert '"Iba1CoveredByCD206_pct"' in macro
    assert '"Iba1CoveredByCD86_pct"' in macro
    assert '"CD206_LocalEnrichment_Iba1VsRing"' in macro
    assert '"CD86_LocalEnrichment_Iba1VsRing"' in macro
    assert 'PILOT_VALUES_NOT_NEGATIVE_CONTROL_CALIBRATED' in macro


def test_iba1_cd206_cd86_macro_formats_project_placeholders() -> None:
    macro = MacroBuilder().build_macro(
        MACROS_LIB[MACRO_NAME],
        ImageData(
            input_path="/converted/input.ims",
            output_path="/converted/processed/output.tif",
            output_path_native="/native/processed/output.tif",
            measurements_path="/converted/measurements/results.csv",
            measurements_path_native="/native/measurements/results.csv",
            file_extension=".ims",
            source_path="/native/input.ims",
            roi_paths=["/converted/roi.zip"],
            roi_paths_native=["/native/roi.zip"],
            document_name="sample",
        ),
    )

    assert 'inputPath = "/converted/input.ims";' in macro
    assert 'resultsPath = "/converted/measurements/results.csv";' in macro
    assert 'roiManager("Open", "/converted/roi.zip");' in macro
    assert "{{" not in macro
    assert "}}" not in macro
