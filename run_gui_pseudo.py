"""Pseudo-GUI runner for kymograph optimization range suggestions."""
from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path


def _install_fake_lumicks() -> None:
    kymo_module = types.ModuleType("lumicks.pylake.kymo")
    kymo_module._kymo_from_array = lambda *args, **kwargs: object()

    pylake_module = types.ModuleType("lumicks.pylake")
    pylake_module.kymo = kymo_module
    pylake_module.track_greedy = lambda *args, **kwargs: []

    lumicks_module = types.ModuleType("lumicks")
    lumicks_module.pylake = pylake_module

    sys.modules["lumicks"] = lumicks_module
    sys.modules["lumicks.pylake"] = pylake_module
    sys.modules["lumicks.pylake.kymo"] = kymo_module


def main() -> None:
    _install_fake_lumicks()

    from kymograph_processing import lumicks_tracker as tracker

    tmp_dir = Path(tempfile.mkdtemp(prefix="kymo_pseudo_"))
    kymo_path = tmp_dir / "sample_kymo.tif"
    kymo_path.write_bytes(b"FAKE_KYMO_DATA")

    target_tracks = [
        [(0.0, 0.0), (1.0, 1.0), (2.0, 1.0)],
        [(0.0, 1.0), (1.0, 2.0)],
    ]
    roi_path = tmp_dir / "target.zip"
    tracker.save_tracks_as_roi(target_tracks, roi_path)

    def fake_track_kymograph(_image_path, min_length=5, intensity_threshold=0.0):
        if 3 <= min_length <= 6 and 0.4 <= intensity_threshold <= 0.6:
            return target_tracks
        if 3 <= min_length <= 6:
            return [target_tracks[0]]
        return []

    tracker.track_kymograph = fake_track_kymograph

    result = tracker.optimize_lumicks_parameters(
        kymo_path,
        roi_path,
        min_length_values=list(range(2, 11)),
        intensity_threshold_values=[round(x * 0.05, 2) for x in range(0, 21)],
        stop_on_perfect=False,
    )

    summary = tracker.suggest_optimization_ranges(result["evaluation_results"])
    print("Best:", result["min_length"], result["intensity_threshold"], f"{result['score']:.3f}")
    print(
        "Suggested ranges:",
        summary["min_length_min"],
        summary["min_length_max"],
        summary["intensity_threshold_min"],
        summary["intensity_threshold_max"],
        summary["intensity_threshold_step"],
    )


if __name__ == "__main__":
    main()
