"""
Core Fiji Document Processor - Database-driven document processing with measurements.
Focuses on keyword-based document selection, macro application, and measurement saving.
All other features are optional and customizable.
"""

import os
import json
import csv
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

from config import FileConfig
from utils.general.fiji_utils import find_fiji, validate_fiji_path
from utils.general.file_utils import normalize_path, convert_path_for_fiji, is_bioformats_file, extract_by_mask
from utils.general.macro_builder import MacroBuilder, ImageData
from utils.general.macros_operation import run_fiji_macro
from utils.general.measurement_summary_utils import (
    build_slice_and_animal_summary_rows,
    measurement_type_to_slug,
    split_summary_rows_by_measurement_type,
)


@dataclass
class DocumentInfo:
    """Information about a document scheduled for processing."""

    file_path: str
    filename: str
    keywords: Tuple[str, ...]
    matched_keyword: Optional[str] = None
    secondary_key: Optional[str] = None
    roi_path: Optional[str] = None
    measurements: Optional[Dict[str, Any]] = None


@dataclass
class ProcessingOptions:
    """Runtime options that control how matching documents are handled."""

    apply_roi: bool = False
    save_processed_files: bool = False
    save_measurements_csv: bool = False
    custom_suffix: str = "processed"
    secondary_filter: Optional[str] = None
    measurements_folder: str = "Measurements"
    processed_folder: str = "Processed_Files"
    measurement_summary_prefix: str = "measurements_summary"
    generate_measurement_summary: bool = True
    roi_search_templates: Optional[Sequence[str]] = None
    # Mapping of placeholder name -> X/Y mask string for filename extraction
    custom_name_patterns: Optional[Dict[str, str]] = None
    generate_slice_averages: bool = False
    generate_animal_averages: bool = False
    keyword_animal_prefixes: Optional[Dict[str, str]] = None
    cut_prefix: Optional[str] = None


class CoreProcessor:
    """
    Core document processor for database-driven Fiji operations.
    Focuses on keyword-based processing with optional features.
    """
    

    def __init__(
        self,
        fiji_path: Optional[str] = None,
        file_config: Optional[FileConfig] = None,
    ):
        """
        Initialize the core processor.
        
        Args:
            fiji_path: Path to a Fiji or ImageJ executable (auto-detected if None)
            file_config: File configuration used for matching and ROI discovery
        """
        self.file_config = file_config or FileConfig()
        
        # Find a Fiji or ImageJ executable, preferring Fiji.
        if fiji_path is None:
            fiji_path = find_fiji()
            if fiji_path is None:
                raise RuntimeError(
                    "Fiji or ImageJ not found. Install either application or "
                    "provide the executable path manually."
                )
        
        if not validate_fiji_path(fiji_path):
            raise RuntimeError(f"Invalid Fiji / ImageJ path: {fiji_path}")
        
        self.fiji_path = fiji_path
        self.macro_builder = MacroBuilder()

        print(f"Core Processor initialized with Fiji / ImageJ at: {self.fiji_path}")

    @staticmethod
    def _normalize_keywords(keyword_input: Union[str, Sequence[str]]) -> Tuple[str, ...]:
        """Normalize keyword input into a tuple of unique, non-empty strings."""
        if isinstance(keyword_input, str):
            keywords = [keyword_input]
        else:
            try:
                keywords = list(keyword_input)
            except TypeError as exc:
                raise TypeError("keyword must be a string or a sequence of strings") from exc

        normalized_keywords: List[str] = []
        for kw in keywords:
            if not isinstance(kw, str):
                raise TypeError("All keywords must be strings")

            cleaned = kw.strip()
            if cleaned:
                normalized_keywords.append(cleaned)

        if not normalized_keywords:
            raise ValueError("keyword must contain at least one non-empty string")

        # Preserve order while removing duplicates
        ordered_unique = list(dict.fromkeys(normalized_keywords))
        return tuple(ordered_unique)

    @staticmethod
    def _format_keywords(keyword_input: Union[str, Sequence[str]]) -> str:
        """Return a human-friendly representation of keyword input."""

        if isinstance(keyword_input, str):
            return keyword_input

        return ", ".join(str(kw) for kw in keyword_input)

    def find_documents_by_keyword(
        self,
        base_path: str,
        keyword: Union[str, Sequence[str]],
        options: Optional[ProcessingOptions] = None,
    ) -> List[DocumentInfo]:
        """
        Find documents by keyword with optional secondary filtering.

        Args:
            base_path: Base directory to search
            keyword: Primary keyword or sequence of keywords to search for
            options: Processing options that influence filtering and ROI lookup

        Returns:
            List of DocumentInfo objects
        """
        keyword_tuple = self._normalize_keywords(keyword)
        keyword_pairs = [(kw, kw.lower()) for kw in keyword_tuple]
        search_options = options or ProcessingOptions()
        secondary_filter = (
            search_options.secondary_filter.lower()
            if search_options.secondary_filter
            else None
        )
        roi_templates = list(
            search_options.roi_search_templates
            if search_options.roi_search_templates
            else self.file_config.roi_search_templates
        )
        documents: List[DocumentInfo] = []
        default_search_options = ProcessingOptions()
        ignored_dir_names = {
            "_IGNOR_",
            os.path.basename(os.path.normpath(default_search_options.measurements_folder)),
            os.path.basename(os.path.normpath(default_search_options.processed_folder)),
        }
        for folder_name in (
            search_options.measurements_folder,
            search_options.processed_folder,
        ):
            if folder_name:
                ignored_dir_names.add(os.path.basename(os.path.normpath(folder_name)))

        # Search for files with the keyword
        for root, dirs, files in os.walk(base_path):
            dirs[:] = [name for name in dirs if name not in ignored_dir_names]
            for file in files:
                if file.startswith(".") or file.startswith("._"):
                    continue
                file_lower = file.lower()
                matched_keyword = None
                for original_keyword, lowered_keyword in keyword_pairs:
                    if lowered_keyword in file_lower:
                        matched_keyword = original_keyword
                        break

                if not matched_keyword:
                    continue

                # Check secondary filter if specified
                if secondary_filter and secondary_filter.lower() not in file_lower:
                    continue

                allowed_exts = tuple(ext.lower() for ext in self.file_config.supported_extensions)
                matched_ext = next((ext for ext in allowed_exts if file_lower.endswith(ext)), None)
                if matched_ext is None:
                    continue

                file_path = os.path.join(root, file)
                filename = os.path.splitext(file)[0]

                # Look for associated ROI file
                roi_path = None
                for template in roi_templates:
                    try:
                        roi_candidate = os.path.join(root, template.format(name=filename))
                    except KeyError:
                        # Allow templates that use old-style formatting tokens
                        roi_candidate = os.path.join(root, template.replace("{name}", filename))
                    if os.path.exists(roi_candidate):
                        roi_path = roi_candidate
                        break

                # Extract secondary key if present
                secondary_key = None
                if secondary_filter and search_options.secondary_filter:
                    for ext in self.file_config.supported_extensions:
                        if file_lower.endswith(ext.lower()):
                            base_name = file[: -len(ext)] if ext else file
                            if secondary_filter in base_name.lower():
                                secondary_key = search_options.secondary_filter
                                break

                documents.append(DocumentInfo(
                    file_path=normalize_path(file_path),
                    filename=filename,
                    keywords=keyword_tuple,
                    matched_keyword=matched_keyword,
                    secondary_key=secondary_key,
                    roi_path=roi_path
                ))

        return documents

    def process_documents(
        self,
        base_path: str,
        keyword: Union[str, Sequence[str]],
        macro_code: Optional[str] = None,
        options: Optional[ProcessingOptions] = None,
        verbose: bool = True,
        cancel_event: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Process documents by keyword with complete Fiji macro code.
        
        Args:
            base_path: Base directory containing documents
            keyword: Keyword or sequence of keywords to search for in filenames
            macro_code: Complete Fiji macro code or a template with placeholders
            options: Optional processing options
            verbose: Whether to print detailed output
            
        Returns:
            Dictionary with processing results
        """
        if options is None:
            options = ProcessingOptions()

        if not isinstance(macro_code, str) or not macro_code.strip():
            return {
                "success": False,
                "error": "Complete Fiji macro code is required.",
                "processed_documents": [],
                "failed_documents": [],
                "measurements": [],
                "searched_keywords": [],
            }

        try:
            normalized_keywords = self._normalize_keywords(keyword)
        except (TypeError, ValueError) as exc:
            return {
                "success": False,
                "error": str(exc),
                "processed_documents": [],
                "failed_documents": [],
                "measurements": [],
                "searched_keywords": [],
            }

        # Find documents
        documents = self.find_documents_by_keyword(
            base_path,
            normalized_keywords,
            options,
        )

        if not documents:
            return {
                "success": False,
                "error": f"No documents found with keyword(s): {self._format_keywords(normalized_keywords)}",
                "processed_documents": [],
                "failed_documents": [],
                "measurements": [],
                "searched_keywords": list(normalized_keywords),
            }

        if verbose:
            keyword_display = self._format_keywords(normalized_keywords)
            print(f"Found {len(documents)} documents matching keyword(s): {keyword_display}")
            if options.secondary_filter:
                print(f"Secondary filter: '{options.secondary_filter}'")

        results = {
            "success": True,
            "processed_documents": [],
            "failed_documents": [],
            "measurements": [],
            "searched_keywords": list(normalized_keywords),
            "summary_outputs": {},
        }

        # Create output directories
        measurements_dir = os.path.join(base_path, options.measurements_folder)
        processed_dir: Optional[str] = None
        if options.save_processed_files:
            processed_dir = os.path.join(base_path, options.processed_folder)
            os.makedirs(processed_dir, exist_ok=True)

        os.makedirs(measurements_dir, exist_ok=True)
        generated_csv_entries: List[Tuple[str, DocumentInfo]] = []

        # Process each document
        for doc in documents:
            # Check cancellation before starting the next document
            if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                if verbose:
                    print("Processing cancelled by user.")
                break
            expected_csv_path: Optional[str] = None
            if options.save_measurements_csv:
                expected_csv_path = os.path.join(
                    measurements_dir, f"{doc.filename}_{options.custom_suffix}.csv"
                )
            try:
                result = self._process_single_document(
                    doc,
                    macro_code,
                    options,
                    verbose,
                    processed_dir,
                    measurements_dir,
                    cancel_event=cancel_event,
                )

                if result["success"]:
                    doc.measurements = result.get("measurements") or {}
                    results["processed_documents"].append(
                        {
                            "filename": doc.filename,
                            "matched_keyword": doc.matched_keyword,
                            "full_path": doc.file_path,
                            "secondary_key": doc.secondary_key,
                        }
                    )
                    if doc.measurements:
                        results["measurements"].append(
                            {
                                "filename": doc.filename,
                                "matched_keyword": doc.matched_keyword,
                                "secondary_key": doc.secondary_key,
                                "measurements": doc.measurements,
                            }
                        )
                    if (
                        options.save_measurements_csv
                        and expected_csv_path
                        and os.path.exists(expected_csv_path)
                    ):
                        generated_csv_entries.append((expected_csv_path, doc))
                else:
                    results["failed_documents"].append(
                        {
                            "filename": doc.filename,
                            "matched_keyword": doc.matched_keyword,
                            "secondary_key": doc.secondary_key,
                            "error": result["error"],
                        }
                    )
                    
            except Exception as e:
                error_msg = f"Unexpected error processing {doc.filename}: {str(e)}"
                if verbose:
                    print(f"❌ {error_msg}")
                results["failed_documents"].append({
                    "filename": doc.filename,
                    "matched_keyword": doc.matched_keyword,
                    "secondary_key": doc.secondary_key,
                    "error": error_msg
                })
        
        # Save measurements summary
        if (
            options.generate_measurement_summary
            and (generated_csv_entries or results["measurements"])
        ):
            results["summary_outputs"] = self._save_measurements_summary(
                measurements_dir,
                results["measurements"],
                options.measurement_summary_prefix,
                csv_entries=generated_csv_entries,
                options=options,
            )

        results["success"] = len(results["failed_documents"]) == 0
        return results
    
    def _process_single_document(
        self,
        doc: DocumentInfo,
        macro_template: str,
        options: ProcessingOptions,
        verbose: bool,
        processed_dir: Optional[str] = None,
        measurements_dir: Optional[str] = None,
        cancel_event: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Process a single document."""
        if verbose:
            match_info = f" (matched keyword: {doc.matched_keyword})" if doc.matched_keyword else ""
            print(f"Processing: {doc.filename}{match_info}")
        
        # Prepare image data
        roi_paths_native: Optional[List[str]] = None
        roi_paths: Optional[List[str]] = None
        if doc.roi_path and options.apply_roi:
            normalized_roi_path = normalize_path(doc.roi_path)
            roi_paths_native = [normalized_roi_path]
            roi_paths = [convert_path_for_fiji(normalized_roi_path)]

        image_data = ImageData(
            input_path=convert_path_for_fiji(doc.file_path),
            output_path="",  # Will be set if saving processed files
            file_extension=os.path.splitext(doc.file_path)[1].lower(),
            is_bioformats=is_bioformats_file(doc.file_path, self.file_config),
            roi_paths=roi_paths,
            measurements_path="",
            source_path=doc.file_path,
            roi_paths_native=roi_paths_native,
            document_name=doc.filename,
        )

        # Compute user-defined placeholders from filename using provided masks
        if options.custom_name_patterns:
            custom_values: Dict[str, Any] = {}
            for name, mask in options.custom_name_patterns.items():
                try:
                    value = extract_by_mask(doc.filename, mask)
                except Exception:
                    value = None
                if value is not None:
                    custom_values[name] = value
            if custom_values:
                image_data.custom_placeholders = custom_values

        # Set output path if saving processed files
        if options.save_processed_files:
            target_dir = processed_dir or os.path.join(
                os.path.dirname(doc.file_path), options.processed_folder
            )
            target_dir = os.path.abspath(target_dir)
            os.makedirs(target_dir, exist_ok=True)

            output_filename = f"{doc.filename}_{options.custom_suffix}.tif"
            output_native_path = os.path.join(target_dir, output_filename)
            image_data.output_path_native = output_native_path
            image_data.output_path = convert_path_for_fiji(output_native_path)

        if options.save_measurements_csv:
            csv_dir = measurements_dir or os.path.join(
                os.path.dirname(doc.file_path), options.measurements_folder
            )
            csv_dir = os.path.abspath(csv_dir)
            os.makedirs(csv_dir, exist_ok=True)

            csv_filename = f"{doc.filename}_{options.custom_suffix}.csv"
            measurements_native_path = os.path.join(csv_dir, csv_filename)
            image_data.measurements_path_native = measurements_native_path
            image_data.measurements_path = convert_path_for_fiji(
                measurements_native_path
            )

        macro_code = self.macro_builder.build_macro(macro_template, image_data)
        
        if verbose:
            print("Generated macro:")
            print(macro_code)
            print("-" * 50)
        
        # Run macro
        result = run_fiji_macro(self.fiji_path, macro_code, verbose=verbose, cancel_event=cancel_event)
        
        return {
            "success": result["success"],
            "measurements": result.get("measurements", {}),
            "error": result.get("error", None)
        }
    
    def _save_measurements_summary(
        self,
        measurements_dir: str,
        measurements: List[Dict[str, Any]],
        prefix: str,
        csv_entries: Optional[Sequence[Tuple[str, DocumentInfo]]] = None,
        options: Optional[ProcessingOptions] = None,
    ) -> Dict[str, str]:
        """Save measurements summary compiled from per-document exports."""

        summary_rows, fieldnames = self._prepare_summary_rows(measurements, csv_entries)

        if not summary_rows:
            return {}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = prefix or "measurements_summary"
        summary_outputs: Dict[str, str] = {}
        base_stem = f"{prefix}_{timestamp}"

        def _write_rows_csv(path: str, csv_fieldnames: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
            with open(path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=csv_fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)

        def _write_aggregated_outputs(
            rows: Sequence[Dict[str, Any]],
            stem: str,
            key_suffix: str = "",
        ) -> None:
            if not options or not (options.generate_slice_averages or options.generate_animal_averages):
                return

            aggregated = build_slice_and_animal_summary_rows(
                rows,
                keyword_animal_prefixes=options.keyword_animal_prefixes,
                cut_prefix=options.cut_prefix,
            )

            if options.generate_slice_averages and aggregated["slice_rows"]:
                slice_path = os.path.join(measurements_dir, f"{stem}_per_slice_mean.csv")
                _write_rows_csv(slice_path, aggregated["slice_fieldnames"], aggregated["slice_rows"])
                print(f"Per-slice averages saved to: {slice_path}")
                summary_outputs[f"slice_summary_csv{key_suffix}"] = slice_path

            if options.generate_animal_averages and aggregated["animal_rows"]:
                animal_path = os.path.join(measurements_dir, f"{stem}_per_animal_mean.csv")
                _write_rows_csv(animal_path, aggregated["animal_fieldnames"], aggregated["animal_rows"])
                print(f"Per-animal averages saved to: {animal_path}")
                summary_outputs[f"animal_summary_csv{key_suffix}"] = animal_path

        # Save as CSV
        csv_path = os.path.join(measurements_dir, f"{base_stem}.csv")
        _write_rows_csv(csv_path, fieldnames, summary_rows)
        print(f"Measurements saved to: {csv_path}")
        summary_outputs["summary_csv"] = csv_path
        _write_aggregated_outputs(summary_rows, base_stem)

        measurement_groups = split_summary_rows_by_measurement_type(summary_rows)
        if len(measurement_groups) > 1:
            for measurement_type, group_rows in sorted(measurement_groups.items()):
                slug = measurement_type_to_slug(measurement_type)
                group_stem = f"{base_stem}_{slug}"
                group_csv_path = os.path.join(measurements_dir, f"{group_stem}.csv")
                _write_rows_csv(group_csv_path, fieldnames, group_rows)
                print(f"Measurement-specific summary saved to: {group_csv_path}")
                summary_outputs[f"summary_csv_{slug}"] = group_csv_path
                _write_aggregated_outputs(group_rows, group_stem, key_suffix=f"_{slug}")

        return summary_outputs

    def _prepare_summary_rows(
        self,
        measurements: List[Dict[str, Any]],
        csv_entries: Optional[Sequence[Tuple[str, DocumentInfo]]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Create summary table rows from saved CSVs or in-memory measurements."""

        if csv_entries:
            summary_rows, fieldnames = self._build_summary_rows_from_csvs(csv_entries)
            if summary_rows:
                return summary_rows, fieldnames

        return self._build_summary_rows_from_measurements(measurements)

    def _build_summary_rows_from_csvs(
        self,
        csv_entries: Sequence[Tuple[str, DocumentInfo]],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Collect rows from saved measurement CSV files with metadata."""

        summary_rows: List[Dict[str, Any]] = []
        metadata_fields = [
            "document_name",
            "source_csv",
            "source_image_path",
            "keywords",
            "matched_keyword",
            "secondary_key",
        ]
        csv_fields: List[str] = []

        for csv_path, doc in csv_entries:
            if not csv_path or not os.path.exists(csv_path):
                continue

            try:
                with open(csv_path, newline="", encoding="utf-8-sig") as csvfile:
                    reader = csv.DictReader(csvfile)
                    if reader.fieldnames:
                        for field in reader.fieldnames:
                            if (
                                field
                                and field not in metadata_fields
                                and field not in csv_fields
                            ):
                                csv_fields.append(field)

                    for row in reader:
                        if row is None:
                            continue

                        cleaned_row = {
                            key: value for key, value in row.items() if key is not None
                        }

                        if not cleaned_row:
                            continue

                        metadata = {
                            "document_name": doc.filename,
                            "source_csv": os.path.basename(csv_path),
                            "source_image_path": doc.file_path,
                            "keywords": ", ".join(str(kw) for kw in doc.keywords),
                            "matched_keyword": doc.matched_keyword or "",
                            "secondary_key": doc.secondary_key or "",
                        }

                        summary_row = {**metadata, **cleaned_row}
                        summary_rows.append(summary_row)
            except (OSError, csv.Error):
                continue

        fieldnames = metadata_fields + csv_fields
        return summary_rows, fieldnames

    def _build_summary_rows_from_measurements(
        self,
        measurements: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Fallback summary rows using in-memory measurements."""

        if not measurements:
            return [], []

        all_keys: List[str] = []
        for measurement_entry in measurements:
            if isinstance(measurement_entry.get("measurements"), dict):
                for key in measurement_entry["measurements"].keys():
                    if key not in all_keys:
                        all_keys.append(key)

        fieldnames = ["filename", "matched_keyword", "secondary_key"] + all_keys
        summary_rows: List[Dict[str, Any]] = []

        for measurement_entry in measurements:
            row = {
                "filename": measurement_entry.get("filename"),
                "matched_keyword": measurement_entry.get("matched_keyword"),
                "secondary_key": measurement_entry.get("secondary_key"),
            }
            if isinstance(measurement_entry.get("measurements"), dict):
                row.update(measurement_entry["measurements"])
            summary_rows.append(row)

        return summary_rows, fieldnames
    
    def validate_setup(self) -> Dict[str, Any]:
        """Validate the current setup."""
        return {
            "fiji_path": self.fiji_path,
            "fiji_valid": validate_fiji_path(self.fiji_path),
            "supported_extensions": self.file_config.supported_extensions
        }
