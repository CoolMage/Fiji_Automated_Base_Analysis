import importlib
from pathlib import Path

import pytest


def load_tracker_module():
    return importlib.import_module("kymograph_processing.lumicks_tracker")


def test_track_kymograph_extracts_tracks(fake_lumicks, sample_kymo_path):
    tracker = load_tracker_module()

    tracks = tracker.track_kymograph(sample_kymo_path, min_length=2, intensity_threshold=0.5)

    # Tracks are converted to float (x, y) tuples.
    assert tracks[0][0] == (0.0, 0.0)
    assert tracks[0][-1] == (1.0, 2.0)
    assert fake_lumicks[0]["intensity_threshold"] == 0.5

    # Image normalization divides by the maximum pixel value (4 in FakeArray).
    assert fake_lumicks[0]["image"][1][1] == 1.0


def test_save_tracks_as_roi_creates_zip(sample_kymo_path, tmp_path):
    tracker = load_tracker_module()

    output_zip = tmp_path / "roi" / "tracks.zip"
    tracks = [[(0.0, 0.0), (1.0, 1.0)], [(0.0, 1.0), (1.0, 2.0)]]

    tracker.save_tracks_as_roi(tracks, output_zip)

    assert output_zip.exists()
    roi_data = tracker.ImagejRoi.read_roi_zip(output_zip)
    assert roi_data["points"][0] == [0.0, 0.0]
    assert roi_data["subtype"] == "polyline"


def test_process_kymographs_filters_channels(tmp_path, fake_lumicks, sample_kymo_path):
    tracker = load_tracker_module()

    # Prepare two kymographs for different channels.
    input_dir = tmp_path / "kymos"
    input_dir.mkdir()
    ch1 = input_dir / "doc_ch1_kymo.tif"
    ch2 = input_dir / "doc_ch2_kymo.tif"
    ch1.write_bytes(Path(sample_kymo_path).read_bytes())
    ch2.write_bytes(Path(sample_kymo_path).read_bytes())

    output_dir = tmp_path / "roi"

    tracker.process_kymographs(
        input_dir,
        output_dir,
        channels=[1],
        min_length=2,
        intensity_threshold=0.25,
    )

    generated = sorted(p.name for p in output_dir.glob("*.zip"))
    assert generated == ["doc_ch1_kymo_tracks.zip"]

    roi_data = tracker.ImagejRoi.read_roi_zip(output_dir / generated[0])
    assert roi_data["points"][-1] == [1.0, 2.0]
