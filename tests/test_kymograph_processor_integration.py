def test_macro_output_and_tracker_chain(
    monkeypatch, tmp_path, fake_lumicks, sample_kymo_path, sample_roi_zip
):
    from pathlib import Path

    from config import FileConfig, ProcessingConfig
    from core_processor import DocumentInfo
    from kymograph_processing.processor import KymographProcessingOptions, KymographProcessor

    class DummyMacroBuilder:
        def __init__(self):
            self.last_image_data = None

        def build_custom_macro(self, template, image_data):
            self.last_image_data = image_data
            return "// dummy macro"

    class DummyCore:
        def __init__(self, builder):
            self.macro_builder = builder

    builder = DummyMacroBuilder()
    processor = KymographProcessor.__new__(KymographProcessor)
    processor.core = DummyCore(builder)
    processor.fiji_path = "/path/to/fiji"
    processor.processing_config = ProcessingConfig()
    processor.file_config = FileConfig()

    def fake_run_fiji_macro(_fiji_path, _macro_code, verbose=True, cancel_event=None):
        output_path = Path(builder.last_image_data.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(Path(sample_kymo_path).read_bytes())
        return {"success": True}

    monkeypatch.setattr("kymograph_processing.processor.run_fiji_macro", fake_run_fiji_macro)

    doc = DocumentInfo(
        file_path=str(sample_kymo_path),
        filename="DocA",
        keywords=("k",),
        roi_path=str(sample_roi_zip),
    )

    result = KymographProcessor._process_single_document(
        processor,
        doc=doc,
        kymo_root=tmp_path / "kymos",
        roi_root=tmp_path / "rois",
        method="lumicks",
        macro_template="template",
        options=KymographProcessingOptions(),
        kymo_direct_path=None,
        verbose=False,
        cancel_event=None,
    )

    assert result["success"] is True
    assert builder.last_image_data.output_path.endswith("DocA_kymo.tif")
    assert len(result["roi_outputs"]) == 1
    roi_path = Path(result["roi_outputs"][0])
    assert roi_path.name == "DocA_kymo_tracks.zip"
    assert roi_path.exists()
