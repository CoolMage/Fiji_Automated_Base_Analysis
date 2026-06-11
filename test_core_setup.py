"""Core processor tests that do not require launching Fiji."""

from config import FileConfig
from core_processor import CoreProcessor, DocumentInfo, ProcessingOptions
from utils.general.macro_builder import MacroBuilder


def test_core_types_import() -> None:
    options = ProcessingOptions()
    document = DocumentInfo(
        file_path="/tmp/image.tif",
        filename="image",
        keywords=("image",),
        matched_keyword="image",
    )

    assert options.custom_suffix == "processed"
    assert document.matched_keyword == "image"


def test_invalid_fiji_path_is_rejected() -> None:
    try:
        CoreProcessor(fiji_path="/invalid/path/to/fiji")
    except RuntimeError as exc:
        assert "Invalid Fiji / ImageJ path" in str(exc)
    else:
        raise AssertionError("CoreProcessor accepted an invalid Fiji path")


def test_complete_macro_code_is_formatted_and_executed(
    tmp_path, monkeypatch
) -> None:
    image_path = tmp_path / "Control_sample.tif"
    image_path.write_bytes(b"test")
    captured = {}

    def fake_run_fiji_macro(_fiji_path, macro_code, **_kwargs):
        captured["macro_code"] = macro_code
        return {"success": True, "measurements": {}, "error": None}

    monkeypatch.setattr("core_processor.run_fiji_macro", fake_run_fiji_macro)

    processor = CoreProcessor.__new__(CoreProcessor)
    processor.fiji_path = "/fake/fiji"
    processor.file_config = FileConfig(supported_extensions=(".tif",))
    processor.macro_builder = MacroBuilder()

    result = processor.process_documents(
        base_path=str(tmp_path),
        keyword="Control",
        macro_code='open("{input_path}");\nrun("Quit");',
        options=ProcessingOptions(generate_measurement_summary=False),
        verbose=False,
    )

    assert result["success"] is True
    assert str(image_path).replace("\\", "/") in captured["macro_code"]


def test_missing_complete_macro_code_is_rejected() -> None:
    processor = CoreProcessor.__new__(CoreProcessor)
    result = processor.process_documents(
        base_path="/tmp",
        keyword="Control",
        macro_code=None,
        verbose=False,
    )

    assert result["success"] is False
    assert result["error"] == "Complete Fiji macro code is required."
