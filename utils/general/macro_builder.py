"""Format complete Fiji macro templates with per-document values."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


DEFAULT_MACRO_CODE = """\
setBatchMode(true);
open("{input_path}");
run("Measure");
run("Close All");
run("Quit");
"""


@dataclass
class ImageData:
    """Paths and metadata available while formatting a Fiji macro."""

    input_path: str
    output_path: str
    file_extension: str
    is_bioformats: bool = False
    roi_paths: Optional[List[str]] = None
    processing_params: Optional[Dict[str, Any]] = None
    measurements_path: str = ""
    source_path: str = ""
    roi_paths_native: Optional[List[str]] = None
    output_path_native: str = ""
    measurements_path_native: str = ""
    document_name: Optional[str] = None
    custom_placeholders: Optional[Dict[str, Any]] = None


class MacroBuilder:
    """Apply document placeholders to complete Fiji macro code."""

    def build_macro(self, macro_code: str, image_data: Optional[ImageData] = None) -> str:
        if not isinstance(macro_code, str):
            raise TypeError("macro_code must be a string")
        if not macro_code.strip():
            raise ValueError("macro_code must not be empty")
        if image_data is None:
            return macro_code

        context = self._build_template_context(image_data)
        placeholder_names = set(
            re.findall(
                r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})",
                macro_code,
            )
        )
        unknown = sorted(placeholder_names.difference(context))
        if unknown:
            available = ", ".join(sorted(context))
            raise ValueError(
                f"Unknown placeholder '{{{unknown[0]}}}' in macro code. "
                f"Available keys: {available}"
            )

        formatted = macro_code
        for name in placeholder_names:
            formatted = formatted.replace(f"{{{name}}}", str(context[name]))

        # Bundled templates historically escaped Fiji block braces for
        # str.format(). Keep those templates compatible while allowing pasted
        # Fiji code to use normal single braces.
        return formatted.replace("{{", "{").replace("}}", "}")

    def _build_template_context(self, image_data: ImageData) -> Dict[str, Any]:
        """Return template variables available to complete macros."""

        def _to_fiji_path(path: str) -> str:
            return (path or "").replace("\\", "/")

        def _ensure_trailing_slash(path: str) -> str:
            return path if not path or path.endswith("/") else path + "/"

        roi_paths = image_data.roi_paths or []
        roi_paths_native = image_data.roi_paths_native or []

        roi_manager_open_block = "\n".join(
            f'roiManager("Open", "{path}");' for path in roi_paths
        )
        roi_manager_open_native_block = "\n".join(
            f'roiManager("Open", "{path}");' for path in roi_paths_native
        )

        input_native = image_data.source_path or image_data.input_path
        input_dir_native = os.path.dirname(input_native)
        input_dir_fiji = _to_fiji_path(input_dir_native)

        output_dir_native = os.path.dirname(
            image_data.output_path_native or image_data.output_path
        )
        output_dir_fiji = _to_fiji_path(output_dir_native)

        measurements_dir_native = os.path.dirname(
            image_data.measurements_path_native or image_data.measurements_path
        )
        measurements_dir_fiji = _to_fiji_path(measurements_dir_native)

        stem_original = image_data.document_name or ""
        stem_normalized = stem_original.replace(".", "_").replace(" ", "_")
        source_filename = os.path.basename(input_native) if input_native else ""

        context: Dict[str, Any] = {
            "input_path": image_data.input_path,
            "input_path_fiji": image_data.input_path,
            "input_path_native": input_native,
            "img_path_fiji": image_data.input_path,
            "img_path": input_native,
            "img_path_native": input_native,
            "IMG": image_data.input_path,
            "output_path": image_data.output_path,
            "output_path_fiji": image_data.output_path,
            "output_path_native": image_data.output_path_native or image_data.output_path,
            "out_tiff": image_data.output_path,
            "out_image": image_data.output_path,
            "OUT": image_data.output_path,
            "measurements_path": image_data.measurements_path,
            "measurements_path_fiji": image_data.measurements_path,
            "measurements_path_native": (
                image_data.measurements_path_native or image_data.measurements_path
            ),
            "out_csv": image_data.measurements_path,
            "CSV": image_data.measurements_path,
            "document_name": stem_normalized,
            "file_stem": stem_normalized,
            "document_name_raw": stem_original,
            "file_stem_raw": stem_original,
            "document_filename_raw": source_filename,
            "roi_paths": roi_paths,
            "roi_paths_native": roi_paths_native,
            "roi_paths_joined": "\n".join(roi_paths),
            "roi_paths_native_joined": "\n".join(roi_paths_native),
            "roi_manager_open_block": roi_manager_open_block,
            "roi_manager_open_native_block": roi_manager_open_native_block,
            "img_dir_fiji": input_dir_fiji,
            "img_dir_fiji_slash": _ensure_trailing_slash(input_dir_fiji),
            "img_dir_native": input_dir_native,
            "output_dir_fiji": output_dir_fiji,
            "output_dir_fiji_slash": _ensure_trailing_slash(output_dir_fiji),
            "output_dir_native": output_dir_native,
            "measurements_dir_fiji": measurements_dir_fiji,
            "measurements_dir_fiji_slash": _ensure_trailing_slash(
                measurements_dir_fiji
            ),
            "measurements_dir_native": measurements_dir_native,
        }

        if image_data.custom_placeholders:
            context.update(image_data.custom_placeholders)

        return context
