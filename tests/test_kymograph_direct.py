import importlib
from pathlib import Path

import pytest


def load_direct_module():
    return importlib.import_module("kymograph_processing.kymograph_direct")


def test_run_kymograph_direct_missing_executable(tmp_path, monkeypatch):
    kymo_file = tmp_path / "input.tif"
    kymo_file.write_bytes(b"content")

    direct = load_direct_module()
    monkeypatch.setattr(direct, "validate_kymograph_direct_path", lambda path: False)

    with pytest.raises(FileNotFoundError):
        direct.run_kymograph_direct(kymo_file, tmp_path / "missing_exe", tmp_path / "out")


def test_process_kymographs_direct_handles_missing_executable(tmp_path, monkeypatch, caplog):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    kymo_file = input_dir / "doc_kymo.tif"
    kymo_file.write_bytes(b"content")

    direct = load_direct_module()
    monkeypatch.setattr(direct, "validate_kymograph_direct_path", lambda path: False)

    caplog.set_level("WARNING")
    direct.process_kymographs_direct(
        kymo_dir=input_dir,
        exe_path=tmp_path / "missing_exe",
        output_dir=tmp_path / "output",
    )

    assert "Failed to run KymographDirect" in "\n".join(caplog.messages)
    assert not list((tmp_path / "output").rglob("*.zip"))
