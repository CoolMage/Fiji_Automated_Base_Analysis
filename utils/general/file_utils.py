"""Utility helpers for dealing with file paths."""

from pathlib import Path
from typing import Optional

from config import FileConfig


def normalize_path(path: str) -> str:
    """Return an absolute, resolved version of *path*."""

    return str(Path(path).expanduser().resolve())


def get_file_extension(file_path: str) -> str:
    """Return the lowercase file extension for *file_path*."""

    return Path(file_path).suffix.lower()


def is_bioformats_file(file_path: str, file_config: Optional[FileConfig] = None) -> bool:
    """Determine whether the file should be opened with the Bio-Formats importer."""

    extensions = {".ims", ".czi", ".nd2", ".lsm", ".oib", ".oif"}
    if file_config is not None:
        extensions.update(ext.lower() for ext in file_config.bioformats_extensions)

    return get_file_extension(file_path) in extensions


def convert_path_for_fiji(path: str) -> str:
    """Convert a filesystem path into a Fiji-compatible string."""

    return path.replace("\\", "/")
