from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SKILL_PROFILE_SCRIPT = (
    Path.home()
    / ".codex"
    / "skills"
    / "fiji-image-analysis"
    / "scripts"
    / "profile_dataset.py"
)


def _load_profile_module():
    if not SKILL_PROFILE_SCRIPT.is_file():
        pytest.skip("fiji-image-analysis skill profiler is not installed")
    spec = importlib.util.spec_from_file_location("fiji_skill_profile_dataset", SKILL_PROFILE_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_skill_profile_dataset_reports_images_rois_and_groups(tmp_path) -> None:
    module = _load_profile_module()
    exp_dir = tmp_path / "Treatment"
    control_dir = tmp_path / "Control"
    exp_dir.mkdir()
    control_dir.mkdir()
    (exp_dir / "Iba1_CD86_Treatment_Rat1_cut1.tif").write_bytes(b"fake")
    (exp_dir / "Iba1_CD86_Treatment_Rat1_cut1.roi").write_bytes(b"fake")
    (control_dir / "Iba1_CD86_Control_Rat2_cut1.czi").write_bytes(b"fake")

    profile = module.profile_dataset(tmp_path)

    assert profile["image_file_count"] == 2
    assert profile["roi_file_count"] == 1
    assert profile["extension_counts"][".tif"] == 1
    assert profile["extension_counts"][".czi"] == 1
    assert any(group["token"] == "Treatment" for group in profile["candidate_groups"])
    assert any(item["token"] == "Rat1" for item in profile["candidate_replicate_tokens"])


def test_skill_profile_dataset_flags_sequencing_like_inputs(tmp_path) -> None:
    module = _load_profile_module()
    (tmp_path / "SampleSheet.csv").write_text("sample,fastq\n", encoding="utf-8")
    (tmp_path / "reads.fastq.gz").write_bytes(b"fake")

    profile = module.profile_dataset(tmp_path)

    assert profile["sequencing_like_file_count"] == 2
    assert any("ngs-analysis" in warning for warning in profile["warnings"])
