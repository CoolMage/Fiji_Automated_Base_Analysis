"""Utilities for tracking kymographs and exporting ImageJ ROI files.

This module wraps lumicks.pylake's greedy tracker to extract line tracks
from kymograph TIFF images and exports them as ImageJ ROIs for further
analysis in Fiji or other tools.
"""

from pathlib import Path
from typing import Iterable, List, Tuple

import numpy as np
from roifile import ImagejRoi
from skimage import io

try:
    from lumicks import pylake as kt
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
    image = image.astype(np.float32)
    max_val = image.max()
    if max_val > 0:
        image /= max_val

    # Run the greedy tracker from lumicks.pylake.
    tracks: List[Track] = []
    for track in kt.track_greedy(image, min_len=min_length, intensity_threshold=intensity_threshold):
        # kt.track_greedy returns tracks as arrays of (row, col); convert to (x, y).
        xy_track: Track = [(float(col), float(row)) for row, col in track]
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
        roi = ImagejRoi.frompoints(track, subtype=ImagejRoi.POLYLINE)
        rois.append(roi)

    # Save all ROIs into a single ZIP archive for easy import into Fiji.
    ImagejRoi.write_roi_zip(output_zip, rois)


def process_kymographs(kymo_dir: Path | str, output_dir: Path | str) -> None:
    """Process all TIFF kymographs in a directory and export their tracks as ROI ZIPs.

    Parameters
    ----------
    kymo_dir:
        Directory containing kymograph TIFF files.
    output_dir:
        Directory where ROI ZIP files will be written. Filenames match input TIFFs.
    """

    kymo_dir = Path(kymo_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for tif_path in sorted(kymo_dir.glob("*.tif")):
        try:
            tracks = track_kymograph(tif_path)
            output_zip = output_dir / f\"{tif_path.stem}_tracks.zip\"
            save_tracks_as_roi(tracks, output_zip)
        except Exception as exc:  # pragma: no cover - logging side effect only
            # Print instead of logging to avoid dependency on logging setup.
            print(f\"Failed to process {tif_path}: {exc}\")
