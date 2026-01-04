"""Interfaces for running KymographDirect in batch mode and exporting ROI files."""

from __future__ import annotations

import csv
import logging
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple

from config import KYMOGRAPH_FORMATS
from kymograph_processing.lumicks_tracker import Track, save_tracks_as_roi
from utils.general.kymo_utils import validate_kymograph_direct_path

LOG = logging.getLogger(__name__)


def _extend_command_with_params(command: list[str], params: object) -> list[str]:
    """Append parameter flags to the command list."""

    if params is None:
        return command

    if isinstance(params, Mapping):
        for key, value in params.items():
            command.append(str(key))
            if value is not None:
                command.append(str(value))
        return command

    if isinstance(params, (str, bytes)):
        command.append(str(params))
        return command

    try:
        iterable_params: Iterable[object] = params  # type: ignore[assignment]
    except TypeError:
        raise TypeError("params must be a mapping, iterable, string, or None") from None

    command.extend(str(param) for param in iterable_params)
    return command


def run_kymograph_direct(
    kymograph_path: Path | str,
    exe_path: Path | str,
    output_dir: Path | str,
    params: object | None = None,
) -> Path:
    """Execute KymographDirect on a single kymograph file.

    The command is constructed with the executable path, input file, output
    directory, and the ``-auto`` flag for unattended processing. Additional
    parameters can be supplied via ``params`` as a mapping (flag/value pairs) or
    iterable of CLI arguments.
    """

    kymograph_path = Path(kymograph_path)
    exe_path = Path(exe_path)
    output_dir = Path(output_dir)

    if not kymograph_path.exists():
        raise FileNotFoundError(f"Kymograph not found: {kymograph_path}")

    if not validate_kymograph_direct_path(str(exe_path)):
        raise FileNotFoundError(f"Invalid KymographDirect executable: {exe_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    command: list[str] = [
        str(exe_path),
        "-i",
        str(kymograph_path),
        "-o",
        str(output_dir),
        "-auto",
    ]

    command = _extend_command_with_params(command, params)
    subprocess.run(command, check=True)

    return output_dir


def _coerce_float(value: str | float | int | None) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _lookup_first(row: MutableMapping[str, str], keys: Sequence[str]) -> str | None:
    for key in keys:
        if key in row and row[key] != "":
            return row[key]
    return None


def _load_track_table(output_dir: Path) -> Path | None:
    candidates = sorted(output_dir.glob("*.csv"))
    if not candidates:
        return None

    for candidate in candidates:
        if "track" in candidate.name.lower():
            return candidate

    return candidates[0]


def parse_kymograph_direct_output(output_dir: Path | str) -> List[Track]:
    """Parse KymographDirect CSV output into grouped tracks."""

    output_dir = Path(output_dir)
    table_path = _load_track_table(output_dir)
    if table_path is None:
        return []

    tracks: Dict[str, Track] = {}
    with table_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return []

        for row in reader:
            track_id = _lookup_first(
                row,
                (
                    "track_id",
                    "track",
                    "trackid",
                    "track_id",
                    "id",
                    "track_number",
                ),
            )
            if track_id is None:
                continue

            x_val = _lookup_first(row, ("x", "X", "column", "col", "position"))
            y_val = _lookup_first(row, ("y", "Y", "row", "time", "frame"))

            x = _coerce_float(x_val)
            y = _coerce_float(y_val)

            if x is None or y is None:
                continue

            tracks.setdefault(str(track_id), []).append((x, y))

    def _sort_key(key: str) -> Tuple[int, str]:
        try:
            return (0, str(int(key)))
        except ValueError:
            return (1, key)

    return [tracks[key] for key in sorted(tracks, key=_sort_key)]


def process_kymographs_direct(
    kymo_dir: Path | str,
    exe_path: Path | str,
    output_dir: Path | str,
    params: object | None = None,
) -> None:
    """Process kymographs with KymographDirect and export ROIs."""

    kymo_dir = Path(kymo_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for extension in KYMOGRAPH_FORMATS:
        for kymo_path in sorted(kymo_dir.glob(f"*{extension}")):
            kymo_output_dir = output_dir / kymo_path.stem

            try:
                run_kymograph_direct(kymo_path, exe_path, kymo_output_dir, params)
            except Exception as exc:  # pragma: no cover - logging side effect only
                LOG.warning("Failed to run KymographDirect for %s: %s", kymo_path, exc)
                continue

            tracks = parse_kymograph_direct_output(kymo_output_dir)
            if not tracks:
                LOG.warning(
                    "No KymographDirect output found for %s in %s",
                    kymo_path,
                    kymo_output_dir,
                )
                continue

            roi_path = kymo_output_dir / f"{kymo_path.stem}_tracks.zip"
            save_tracks_as_roi(tracks, roi_path)
