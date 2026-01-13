"""Utilities for tracking kymographs and exporting ImageJ ROI files.

This module wraps lumicks.pylake's greedy tracker to extract line tracks
from kymograph TIFF images and exports them as ImageJ ROIs for further
analysis in Fiji or other tools.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import numpy as np
try:
    from roifile import ImagejRoi, roiwrite, roiread
except ImportError:  # pragma: no cover - optional import variant
    from roifile import ImagejRoi, roiwrite
    roiread = None
from skimage import io

try:
    from lumicks import pylake as kt
    from lumicks.pylake import kymo as kt_kymo
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError(
        "lumicks.pylake is required for kymograph tracking. "
        "Install via `pip install lumicks.pylake`."
    ) from exc

# Track type alias for readability: list of (x, y) coordinate tuples
Track = List[Tuple[float, float]]


def track_kymograph(
    image_path: Path | str, min_length: int = 5, intensity_threshold: float = 0.0
) -> List[Track]:
    """Track lines in a kymograph image using lumicks.pylake.

    Parameters
    ----------
    image_path:
        Path to the kymograph TIFF image.
    min_length:
        Minimum number of points a track must contain to be returned.
    intensity_threshold:
        Minimum normalized intensity for accepting track pixels.

    Returns
    -------
    List[Track]
        A list of tracks, where each track is a list of (x, y) coordinates.
    """

    image_path = Path(image_path)

    # Load and normalize the image to [0, 1] for consistent thresholding.
    image = io.imread(image_path)
    if image.ndim > 2:
        # Collapse RGB/RGBA or multi-plane stacks to 2D for the tracker.
        if image.ndim == 3 and image.shape[-1] in (3, 4):
            image = image[..., :3].mean(axis=-1)
        else:
            image = image.mean(axis=0)
    image = image.astype(np.float32)
    max_val = image.max()
    if max_val > 0:
        image /= max_val

    kymo_obj = kt_kymo._kymo_from_array(
        image,
        "r",
        line_time_seconds=1.0,
        pixel_size_um=1.0,
        name=str(image_path),
    )

    # Run the greedy tracker from lumicks.pylake.
    tracks: List[Track] = []
    pixel_threshold = intensity_threshold if intensity_threshold > 0 else None
    iterator = kt.track_greedy(kymo_obj, "red", pixel_threshold=pixel_threshold)
    for track in iterator:
        if len(track.time_idx) < min_length:
            continue
        xy_track: Track = [
            (float(t), float(c)) for t, c in zip(track.time_idx, track.coordinate_idx)
        ]
        tracks.append(xy_track)

    return tracks


def save_tracks_as_roi(tracks: Iterable[Track], output_zip: Path | str) -> None:
    """Save tracks to an ImageJ ROI ZIP file as polylines.

    Parameters
    ----------
    tracks:
        Iterable of tracks, each as a sequence of (x, y) coordinates.
    output_zip:
        Path to the output ZIP file containing the ROI definitions.
    """

    output_zip = Path(output_zip)
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    rois: List[ImagejRoi] = []
    for track in tracks:
        # ImagejRoi.frompoints expects points in (x, y) order.
        roi = ImagejRoi.frompoints(track)
        rois.append(roi)

    # Save all ROIs into a single ZIP archive for easy import into Fiji.
    roiwrite(output_zip, rois)


def _roi_data_to_tracks(roi_data: object) -> List[Track]:
    rois: List[object]
    if roi_data is None:
        return []
    if isinstance(roi_data, dict):
        if "points" in roi_data:
            rois = [roi_data]
        else:
            rois = list(roi_data.values())
    elif isinstance(roi_data, (list, tuple)):
        rois = list(roi_data)
    else:
        rois = [roi_data]

    tracks: List[Track] = []
    for roi in rois:
        points: Iterable
        if isinstance(roi, dict):
            points = roi.get("points") or []
        elif hasattr(roi, "points"):
            points = getattr(roi, "points")
        elif hasattr(roi, "coordinates"):
            coords = roi.coordinates()
            points = coords.tolist() if hasattr(coords, "tolist") else coords
        else:
            points = []

        track: Track = []
        for point in points:
            if len(point) < 2:
                continue
            track.append((float(point[0]), float(point[1])))
        if track:
            tracks.append(track)

    return tracks


def _load_target_tracks(roi_path: Path | str) -> List[Track]:
    roi_path = Path(roi_path)
    if not roi_path.exists():
        raise FileNotFoundError(f"ROI file not found: {roi_path}")

    if roi_path.suffix.lower() == ".zip":
        if hasattr(ImagejRoi, "read_roi_zip"):
            roi_data = ImagejRoi.read_roi_zip(roi_path)
        elif roiread is not None:
            roi_data = roiread(roi_path)
        else:
            raise ValueError("ROI ZIP loading is not available in the roifile version.")
    else:
        if hasattr(ImagejRoi, "fromfile"):
            roi_data = ImagejRoi.fromfile(roi_path)
        elif roiread is not None:
            roi_data = roiread(roi_path)
        else:
            raise ValueError("ROI loading is not available in the roifile version.")

    tracks = _roi_data_to_tracks(roi_data)
    if not tracks:
        raise ValueError(f"No ROI tracks found in {roi_path}")
    return tracks


def _tracks_to_point_set(tracks: Iterable[Track]) -> set[tuple[int, int]]:
    points: set[tuple[int, int]] = set()
    for track in tracks:
        for x_val, y_val in track:
            points.add((int(round(x_val)), int(round(y_val))))
    return points


def _score_tracks(predicted: Iterable[Track], target_points: set[tuple[int, int]]) -> float:
    predicted_points = _tracks_to_point_set(predicted)
    if not predicted_points or not target_points:
        return 0.0
    overlap = len(predicted_points & target_points)
    precision = overlap / len(predicted_points)
    recall = overlap / len(target_points)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def optimize_lumicks_parameters(
    image_path: Path | str,
    roi_path: Path | str,
    *,
    min_length_values: Sequence[int] | None = None,
    intensity_threshold_values: Sequence[float] | None = None,
    max_evaluations: int | None = None,
    max_seconds: float | None = None,
) -> dict:
    """Grid search Lumicks tracker parameters against a target ROI."""
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Kymograph not found: {image_path}")

    target_tracks = _load_target_tracks(roi_path)
    target_points = _tracks_to_point_set(target_tracks)

    if min_length_values is None:
        min_length_values = list(range(2, 21))
    if intensity_threshold_values is None:
        intensity_threshold_values = [
            0.0,
            0.05,
            0.1,
            0.15,
            0.2,
            0.25,
            0.3,
            0.35,
            0.4,
            0.45,
            0.5,
            0.6,
            0.7,
            0.8,
            0.9,
        ]

    best_score = -1.0
    best_min_length = None
    best_threshold = None
    best_tracks: List[Track] = []
    last_error: str | None = None

    perfect_score = 0.999
    start_time = time.monotonic()
    evaluations = 0
    stop_search = False
    for min_len in min_length_values:
        for threshold in intensity_threshold_values:
            if max_evaluations is not None and evaluations >= max_evaluations:
                stop_search = True
                break
            if max_seconds is not None and (time.monotonic() - start_time) >= max_seconds:
                stop_search = True
                break
            try:
                tracks = track_kymograph(
                    image_path, min_length=min_len, intensity_threshold=threshold
                )
            except Exception as exc:
                last_error = str(exc)
                evaluations += 1
                continue
            score = _score_tracks(tracks, target_points)
            evaluations += 1
            if score > best_score:
                best_score = score
                best_min_length = min_len
                best_threshold = float(threshold)
                best_tracks = tracks
                if best_score >= perfect_score:
                    break
        if best_score >= perfect_score:
            break
        if stop_search:
            break

    if best_min_length is None or best_threshold is None:
        raise RuntimeError(
            "Optimization failed to evaluate any parameter sets."
            + (f" Last error: {last_error}" if last_error else "")
        )

    return {
        "min_length": best_min_length,
        "intensity_threshold": best_threshold,
        "score": best_score,
        "tracks": best_tracks,
        "target_points": len(target_points),
        "predicted_points": len(_tracks_to_point_set(best_tracks)),
        "evaluations": evaluations,
        "elapsed_seconds": time.monotonic() - start_time,
    }


def _channel_allows(path: Path, channels: Sequence[int] | None) -> bool:
    """Return True if the kymograph belongs to an allowed channel."""

    if not channels:
        return True

    match = re.search(r"_ch(\d+)_", path.stem)
    if match is None:
        return True

    try:
        channel_idx = int(match.group(1))
    except ValueError:
        return True

    return channel_idx in channels


def process_kymographs(
    kymo_dir: Path | str,
    output_dir: Path | str,
    *,
    channels: Sequence[int] | None = None,
    min_length: int = 5,
    intensity_threshold: float = 0.0,
) -> None:
    """Process all TIFF kymographs in a directory and export their tracks as ROI ZIPs.

    Parameters
    ----------
    kymo_dir:
        Directory containing kymograph TIFF files.
    output_dir:
        Directory where ROI ZIP files will be written. Filenames match input TIFFs.
    channels:
        Optional subset of channels (1-based indices) to process. If omitted, all
        detected channels are processed.
    min_length:
        Minimum number of points for a track to be exported.
    intensity_threshold:
        Minimum normalized intensity passed to the greedy tracker.
    """

    kymo_dir = Path(kymo_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for tif_path in sorted(kymo_dir.glob("*.tif")):
        if tif_path.name.startswith("._"):
            continue
        if not _channel_allows(tif_path, channels):
            continue

        try:
            tracks = track_kymograph(
                tif_path, min_length=min_length, intensity_threshold=intensity_threshold
            )
            output_zip = output_dir / f"{tif_path.stem}_tracks.zip"
            save_tracks_as_roi(tracks, output_zip)
        except Exception as exc:  # pragma: no cover - logging side effect only
            # Print instead of logging to avoid dependency on logging setup.
            print(f"Failed to process {tif_path}: {exc}")
