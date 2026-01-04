"""High-level kymograph processing pipeline built on top of Fiji macros."""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from config import FileConfig, ProcessingConfig
from core_processor import CoreProcessor, DocumentInfo, ProcessingOptions
from kymograph_processing.kymograph_direct import process_kymographs_direct
from kymograph_processing.lumicks_tracker import process_kymographs
from utils.general.file_utils import (
    convert_path_for_fiji,
    is_bioformats_file,
    normalize_path,
)
from utils.general.fiji_utils import find_fiji, validate_fiji_path
from utils.general.kymo_utils import find_kymograph_direct, validate_kymograph_direct_path
from utils.general.macro_builder import ImageData
from utils.general.macros_operation import run_fiji_macro

LOG = logging.getLogger(__name__)


@dataclass
class KymographProcessingOptions:
    """Runtime options for kymograph generation and ROI export."""

    method: str = "lumicks"
    channels: Optional[Sequence[int]] = None
    tracker_min_length: int = 5
    tracker_intensity_threshold: float = 0.0
    save_intermediate_kymographs: bool = True
    kymograph_macro_path: Optional[str] = None
    kymograph_output_folder: str = "Kymographs"
    roi_output_folder: str = "Kymograph_ROIs"
    kymograph_direct_params: object | None = None
    kymograph_direct_path: Optional[str] = None
    roi_search_templates: Optional[Sequence[str]] = None
    secondary_filter: Optional[str] = None


class KymographProcessor:
    """Pipeline for generating and tracking kymographs."""

    def __init__(
        self,
        fiji_path: Optional[str] = None,
        kymograph_method: str = "lumicks",
        kymograph_direct_path: Optional[str] = None,
        processing_config: Optional[ProcessingConfig] = None,
        file_config: Optional[FileConfig] = None,
    ) -> None:
        self.processing_config = processing_config or ProcessingConfig()
        self.file_config = file_config or FileConfig()

        if fiji_path is None:
            fiji_path = find_fiji()
            if fiji_path is None:
                raise RuntimeError("Fiji not found. Please install Fiji or provide the path manually.")
        if not validate_fiji_path(fiji_path):
            raise RuntimeError(f"Invalid Fiji path: {fiji_path}")

        self.core = CoreProcessor(
            fiji_path=fiji_path,
            processing_config=self.processing_config,
            file_config=self.file_config,
        )
        self.fiji_path = self.core.fiji_path
        self.kymograph_method = kymograph_method
        self.kymograph_direct_path = kymograph_direct_path

        LOG.info("KymographProcessor initialized with Fiji at %s", self.fiji_path)

    def process_documents(
        self,
        base_path: str,
        keyword: Union[str, Sequence[str]],
        options: Optional[KymographProcessingOptions] = None,
        verbose: bool = True,
        cancel_event: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Generate kymographs for matching documents and convert tracks to ROIs."""

        opts = options or KymographProcessingOptions()
        method = (opts.method or self.kymograph_method).lower()

        if method not in {"lumicks", "direct"}:
            return {
                "success": False,
                "error": f"Unsupported kymograph method: {opts.method}",
                "processed_documents": [],
                "failed_documents": [],
                "roi_outputs": [],
            }

        direct_path = opts.kymograph_direct_path or self.kymograph_direct_path
        if method == "direct" and not validate_kymograph_direct_path(direct_path or ""):
            direct_path = find_kymograph_direct(list(self.processing_config.kymograph_direct_paths))
            if not validate_kymograph_direct_path(direct_path or ""):
                return {
                    "success": False,
                    "error": "Valid KymographDirect executable not found.",
                    "processed_documents": [],
                    "failed_documents": [],
                    "roi_outputs": [],
                }

        search_options = ProcessingOptions(
            roi_search_templates=opts.roi_search_templates or self.file_config.roi_search_templates,
            secondary_filter=opts.secondary_filter,
        )
        documents = self.core.find_documents_by_keyword(base_path, keyword, search_options)
        if not documents:
            return {
                "success": False,
                "error": "No documents found for supplied keywords.",
                "processed_documents": [],
                "failed_documents": [],
                "roi_outputs": [],
            }

        kymo_root = Path(base_path) / opts.kymograph_output_folder
        roi_root = Path(base_path) / opts.roi_output_folder
        macro_template = self._load_macro_template(opts)

        results = {
            "success": True,
            "processed_documents": [],
            "failed_documents": [],
            "roi_outputs": [],
        }

        for doc in documents:
            if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                break

            try:
                doc_result = self._process_single_document(
                    doc=doc,
                    kymo_root=kymo_root,
                    roi_root=roi_root,
                    method=method,
                    macro_template=macro_template,
                    options=opts,
                    kymo_direct_path=direct_path,
                    verbose=verbose,
                    cancel_event=cancel_event,
                )
            except Exception as exc:  # pragma: no cover - logging side-effect only
                LOG.error("Failed to process %s: %s", doc.filename, exc)
                results["failed_documents"].append(
                    {"filename": doc.filename, "matched_keyword": doc.matched_keyword, "error": str(exc)}
                )
                results["success"] = False
                continue

            if doc_result["success"]:
                results["processed_documents"].append(
                    {"filename": doc.filename, "matched_keyword": doc.matched_keyword, "roi_outputs": doc_result["roi_outputs"]}
                )
                results["roi_outputs"].extend(doc_result["roi_outputs"])
            else:
                results["failed_documents"].append(
                    {"filename": doc.filename, "matched_keyword": doc.matched_keyword, "error": doc_result["error"]}
                )
                results["success"] = False

        return results

    def _load_macro_template(self, options: KymographProcessingOptions) -> str:
        if options.kymograph_macro_path:
            macro_path = Path(options.kymograph_macro_path)
        else:
            macro_path = Path(__file__).resolve().parent.parent / "examples" / "macros_lib" / "fiji_kymograph_macro.ijm"

        if not macro_path.exists():
            raise FileNotFoundError(f"Kymograph macro not found: {macro_path}")

        return macro_path.read_text(encoding="utf-8")

    def _process_single_document(
        self,
        doc: DocumentInfo,
        kymo_root: Path,
        roi_root: Path,
        method: str,
        macro_template: str,
        options: KymographProcessingOptions,
        kymo_direct_path: Optional[str],
        verbose: bool,
        cancel_event: Optional[Any],
    ) -> Dict[str, Any]:
        if not doc.roi_path:
            return {
                "success": False,
                "error": f"No ROI file found for {doc.filename}. Kymograph generation requires ROIs.",
                "roi_outputs": [],
            }

        if method == "direct" and not kymo_direct_path:
            raise ValueError("KymographDirect path is required when using the 'direct' method.")

        kymo_dir = kymo_root / doc.filename
        roi_dir = roi_root / doc.filename
        kymo_dir.mkdir(parents=True, exist_ok=True)
        roi_dir.mkdir(parents=True, exist_ok=True)

        output_path_native = kymo_dir / f"{doc.filename}_kymo.tif"
        image_data = ImageData(
            input_path=convert_path_for_fiji(doc.file_path),
            output_path=convert_path_for_fiji(str(output_path_native)),
            file_extension=os.path.splitext(doc.file_path)[1].lower(),
            is_bioformats=is_bioformats_file(doc.file_path, self.file_config),
            roi_paths=[convert_path_for_fiji(normalize_path(doc.roi_path))],
            roi_paths_native=[normalize_path(doc.roi_path)],
            source_path=doc.file_path,
            document_name=doc.filename,
        )

        macro_code = self.core.macro_builder.build_custom_macro(macro_template, image_data)
        if verbose:
            LOG.info("Running kymograph macro for %s", doc.filename)
            print(macro_code)

        macro_result = run_fiji_macro(self.fiji_path, macro_code, verbose=verbose, cancel_event=cancel_event)
        if not macro_result.get("success", False):
            return {
                "success": False,
                "error": macro_result.get("error") or "Fiji macro failed",
                "roi_outputs": [],
            }

        if method == "lumicks":
            process_kymographs(
                kymo_dir,
                roi_dir,
                channels=options.channels,
                min_length=options.tracker_min_length,
                intensity_threshold=float(options.tracker_intensity_threshold),
            )
        else:
            process_kymographs_direct(
                kymo_dir,
                kymo_direct_path,
                roi_dir,
                params=options.kymograph_direct_params,
                channels=options.channels,
            )

        roi_outputs = [str(path) for path in sorted(roi_dir.rglob("*.zip"))]

        if not options.save_intermediate_kymographs:
            shutil.rmtree(kymo_dir, ignore_errors=True)

        return {"success": True, "roi_outputs": roi_outputs}
