"""Utility helpers for dealing with file paths."""

from pathlib import Path
from typing import Optional
import re

from config import FileConfig


def normalize_path(path: str) -> str:
    """Return an absolute, resolved version of *path*."""

    return str(Path(path).expanduser().resolve())


def get_file_extension(file_path: str) -> str:
    """Return the lowercase file extension for *file_path*."""

    return Path(file_path).suffix.lower()


def is_bioformats_file(file_path: str, file_config: Optional[FileConfig] = None) -> bool:
    """Determine whether the file should be opened with the Bio-Formats importer."""

    extensions = {".ims", ".czi", ".nd2", ".lsm", ".oib", ".oif", ".vsi"}
    if file_config is not None:
        extensions.update(ext.lower() for ext in file_config.bioformats_extensions)

    return get_file_extension(file_path) in extensions


def convert_path_for_fiji(path: str) -> str:
    """Convert a filesystem path into a Fiji-compatible string."""

    return path.replace("\\", "/")


def mask_to_regex(mask: str) -> str:
    """Convert a simple mask using X/Y to a regex.

    Rules:
    - 'X' matches one or more digits: [0-9]+
    - 'Y' matches one or more letters: [A-Za-z]+
    - All other characters are treated as literals and escaped.
    The resulting regex is not anchored; callers may add anchors as needed.
    """
    parts = []
    for ch in mask:
        if ch == 'X':
            parts.append(r"[0-9]+")
        elif ch == 'Y':
            parts.append(r"[A-Za-z]+")
        else:
            parts.append(re.escape(ch))
    return "".join(parts)


def extract_by_mask(filename_stem: str, mask: str) -> Optional[str]:
    """Extract the first substring from filename_stem that matches the X/Y mask.

    Returns the matched substring, or None if no match.
    Extraction is performed on the filename without extension.
    """
    pattern = mask_to_regex(mask)
    regex = re.compile(pattern)
    m = regex.search(filename_stem)
    if not m:
        return None
    return m.group(0)
