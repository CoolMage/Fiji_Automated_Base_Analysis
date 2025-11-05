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

from config import FileConfig, ProcessingConfig
from utils.general.fiji_utils import find_fiji, validate_fiji_path
from utils.general.file_utils import normalize_path, convert_path_for_fiji, is_bioformats_file, extract_by_mask
from utils.general.macro_builder import MacroBuilder, ImageData, MacroCommand
from utils.general.macros_operation import run_fiji_macro


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


class CommandLibrary:
    """Library of available macro commands with descriptions."""
    
    COMMANDS = {
        # File operations
        "open_standard": {
            "description": "Open image with standard ImageJ method",
            "parameters": {"input_path": "Path to input file"},
            "example": "open_standard"
        },
        "open_bioformats": {
            "description": "Open image using Bio-Formats importer",
            "parameters": {"input_path": "Path to input file"},
            "example": "open_bioformats"
        },
        "save_tiff": {
            "description": "Save current image as TIFF",
            "parameters": {"output_path": "Path for output file"},
            "example": "save_tiff"
        },
        "save_csv": {
            "description": "Save measurements as CSV",
            "parameters": {"measurements_path": "Path for CSV file"},
            "example": "save_csv"
        },
        
        # Image processing
        "convert_8bit": {
            "description": "Convert image to 8-bit",
            "parameters": {},
            "example": "convert_8bit"
        },
        "convert_16bit": {
            "description": "Convert image to 16-bit",
            "parameters": {},
            "example": "convert_16bit"
        },
        "subtract_background": {
            "description": "Subtract background using rolling ball algorithm",
            "parameters": {"radius": "Rolling ball radius (default: 30)"},
            "example": "subtract_background radius=50"
        },
        "median_filter": {
            "description": "Apply median filter",
            "parameters": {"radius": "Filter radius (default: 2)"},
            "example": "median_filter radius=3"
        },
        "gaussian_blur": {
            "description": "Apply Gaussian blur",
            "parameters": {"sigma": "Blur sigma (default: 2.0)"},
            "example": "gaussian_blur sigma=1.5"
        },
        "enhance_contrast": {
            "description": "Enhance contrast using histogram equalization",
            "parameters": {"saturated": "Saturated pixel percentage (default: 0.35)"},
            "example": "enhance_contrast saturated=0.4"
        },
        "threshold": {
            "description": "Apply threshold",
            "parameters": {"method": "Threshold method (default: 'Default')"},
            "example": "threshold method='Otsu'"
        },
        
        # Measurements
        "measure": {
            "description": "Measure current selection or entire image",
            "parameters": {"measurements": "Comma-separated list of measurements"},
            "example": "measure measurements='area,mean,std'"
        },
        "set_measurements": {
            "description": "Set which measurements to record",
            "parameters": {"measurements": "Comma-separated list of measurements"},
            "example": "set_measurements measurements='area,mean,std,min,max'"
        },
        "clear_measurements": {
            "description": "Clear all measurements",
            "parameters": {},
            "example": "clear_measurements"
        },
        
        # ROI operations
        "roi_manager_reset": {
            "description": "Reset ROI Manager",
            "parameters": {},
            "example": "roi_manager_reset"
        },
        "roi_manager_open": {
            "description": "Open ROI file",
            "parameters": {"roi_path": "Path to ROI file"},
            "example": "roi_manager_open roi_path='/path/to/roi.zip'"
        },
        "roi_manager_select": {
            "description": "Select ROI by index",
            "parameters": {"index": "ROI index (0-based)"},
            "example": "roi_manager_select index=0"
        },
        "roi_manager_measure": {
            "description": "Measure all ROIs in manager",
            "parameters": {},
            "example": "roi_manager_measure"
        },
        "make_inverse": {
            "description": "Create inverse of current selection",
            "parameters": {},
            "example": "make_inverse"
        },
        "roi_manager_add": {
            "description": "Add current selection to ROI Manager",
            "parameters": {},
            "example": "roi_manager_add"
        },
        "roi_manager_save": {
            "description": "Save ROIs to file",
            "parameters": {"roi_path": "Path to save ROIs"},
            "example": "roi_manager_save roi_path='/path/to/save.zip'"
        },
        
        # Utility operations
        "duplicate": {
            "description": "Duplicate current image",
            "parameters": {"title": "Title for duplicate", "channels": "Channels to duplicate", "slices": "Slices to duplicate", "frames": "Frames to duplicate"},
            "example": "duplicate title='Copy' channels=1 slices=1-end frames=1-end"
        },
        "close_all": {
            "description": "Close all open windows",
            "parameters": {},
            "example": "close_all"
        },
        "quit": {
            "description": "Quit ImageJ/Fiji",
            "parameters": {},
            "example": "quit"
        },
        
        # Display operations
        "set_option_show_all": {
            "description": "Set 'Show All' option to false",
            "parameters": {},
            "example": "set_option_show_all"
        },
        "remove_overlay": {
            "description": "Remove any overlays",
            "parameters": {},
            "example": "remove_overlay"
        },
        "roi_manager_show_none": {
            "description": "Hide all ROIs",
            "parameters": {},
            "example": "roi_manager_show_none"
        },
        "roi_manager_deselect": {
            "description": "Deselect all ROIs",
            "parameters": {},
            "example": "roi_manager_deselect"
        }
    }
    
    @classmethod
    def get_command_info(cls, command_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific command."""
        return cls.COMMANDS.get(command_name)
    
    @classmethod
    def list_commands(cls) -> Dict[str, Dict[str, Any]]:
        """Get all available commands."""
        return cls.COMMANDS.copy()
    
    @classmethod
    def validate_command(cls, command_name: str) -> bool:
        """Check if a command exists."""
        return command_name in cls.COMMANDS


class CoreProcessor:
    """
    Core document processor for database-driven Fiji operations.
    Focuses on keyword-based processing with optional features.
    """
    

    def __init__(
        self,
        fiji_path: Optional[str] = None,
        processing_config: Optional[ProcessingConfig] = None,
        file_config: Optional[FileConfig] = None,
    ):
        """
        Initialize the core processor.
        
        Args:
            fiji_path: Path to Fiji executable (auto-detected if None)
            processing_config: Processing configuration used by the macro builder
            file_config: File configuration used for matching and ROI discovery
        """
        self.processing_config = processing_config or ProcessingConfig()
        self.file_config = file_config or FileConfig()
        
        # Find Fiji executable
        if fiji_path is None:
            fiji_path = find_fiji()
            if fiji_path is None:
                raise RuntimeError("Fiji not found. Please install Fiji or provide the path manually.")
        
        if not validate_fiji_path(fiji_path):
            raise RuntimeError(f"Invalid Fiji path: {fiji_path}")
        
        self.fiji_path = fiji_path
        self.macro_builder = MacroBuilder(self.processing_config, self.file_config)
        self.command_library = CommandLibrary()

        print(f"Core Processor initialized with Fiji at: {self.fiji_path}")

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

        # Search for files with the keyword
        for root, dirs, files in os.walk(base_path):
            for file in files:
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
        macro_commands: Union[str, List[str], None] = None,
        options: Optional[ProcessingOptions] = None,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        Process documents by keyword with specified macro commands.
        
        Args:
            base_path: Base directory containing documents
            keyword: Keyword or sequence of keywords to search for in filenames
            macro_commands: Macro commands to apply (string, list, or None for default)
            options: Optional processing options
            verbose: Whether to print detailed output
            
        Returns:
            Dictionary with processing results
        """
        if options is None:
            options = ProcessingOptions()

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
            expected_csv_path: Optional[str] = None
            if options.save_measurements_csv:
                expected_csv_path = os.path.join(
                    measurements_dir, f"{doc.filename}_{options.custom_suffix}.csv"
                )
            try:
                result = self._process_single_document(
                    doc,
                    macro_commands,
                    options,
                    verbose,
                    processed_dir,
                    measurements_dir,
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
            self._save_measurements_summary(
                measurements_dir,
                results["measurements"],
                options.measurement_summary_prefix,
                csv_entries=generated_csv_entries,
            )

        results["success"] = len(results["failed_documents"]) == 0
        return results
    
    def _process_single_document(
        self,
        doc: DocumentInfo,
        macro_commands: Union[str, List[str], None],
        options: ProcessingOptions,
        verbose: bool,
        processed_dir: Optional[str] = None,
        measurements_dir: Optional[str] = None,
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

        # Build macro
        custom_macro_template: Optional[str] = None
        macro_sequence: Union[List[Any], List[MacroCommand]]

        if macro_commands is None:
            # Default: open, measure, optionally save outputs, quit
            macro_sequence = ["open_standard", "measure"]
            if options.save_processed_files:
                macro_sequence.append("save_tiff")
            if options.save_measurements_csv:
                macro_sequence.append("save_csv")
            macro_sequence.append("quit")
        elif isinstance(macro_commands, str):
            stripped_macro = macro_commands.strip()
            if "\n" in stripped_macro or ";" in stripped_macro:
                custom_macro_template = stripped_macro
                macro_sequence = []
            else:
                macro_sequence = stripped_macro.split()
        else:
            macro_sequence = list(macro_commands)

        if custom_macro_template is None:
            # Build macro from command list or MacroCommand objects
            commands: List[MacroCommand] = []
            for item in macro_sequence:
                if isinstance(item, MacroCommand):
                    commands.append(item)
                    continue

                cmd_str = str(item)
                if " " in cmd_str and "=" in cmd_str:
                    # Command with parameters (e.g., "subtract_background radius=50")
                    parts = cmd_str.split(" ", 1)
                    cmd_name = parts[0]
                    params = {}
                    if len(parts) > 1:
                        for param in parts[1].split():
                            if "=" in param:
                                key, value = param.split("=", 1)
                                params[key.strip()] = value.strip()
                    commands.append(MacroCommand(cmd_name.strip(), params))
                else:
                    commands.append(MacroCommand(cmd_str.strip()))

            # Ensure quit command is present to close Fiji
            if not any(cmd.command == "quit" for cmd in commands):
                commands.append(MacroCommand("quit"))
            
            # Ensure BatchMode command is present to close Fiji
            if not any(cmd.command == "BatchMode" for cmd in commands):
                commands.insert(0, MacroCommand("BatchMode"))

            needs_processed_output = any(cmd.command == "save_tiff" for cmd in commands)
            needs_measurement_output = any(cmd.command == "save_csv" for cmd in commands)

            if needs_processed_output and not image_data.output_path:
                target_dir = processed_dir or os.path.join(
                    os.path.dirname(doc.file_path), options.processed_folder
                )
                target_dir = os.path.abspath(target_dir)
                os.makedirs(target_dir, exist_ok=True)

                output_filename = f"{doc.filename}_{options.custom_suffix}.tif"
                output_native_path = os.path.join(target_dir, output_filename)
                image_data.output_path_native = output_native_path
                image_data.output_path = convert_path_for_fiji(output_native_path)

            if needs_measurement_output and not image_data.measurements_path:
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

            macro_code = self.macro_builder.build_macro_from_commands(commands)

            # Substitute template variables
            macro_code = macro_code.format(
                input_path=image_data.input_path,
                output_path=image_data.output_path,
                measurements_path=image_data.measurements_path
            )
        else:
            macro_code = self.macro_builder.build_custom_macro(
                custom_macro_template, image_data
            )
        
        if verbose:
            print("Generated macro:")
            print(macro_code)
            print("-" * 50)
        
        # Run macro
        result = run_fiji_macro(self.fiji_path, macro_code, verbose=verbose)
        
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
    ) -> None:
        """Save measurements summary compiled from per-document exports."""

        summary_rows, fieldnames = self._prepare_summary_rows(measurements, csv_entries)

        if not summary_rows:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = prefix or "measurements_summary"

        # Save as CSV
        csv_path = os.path.join(measurements_dir, f"{prefix}_{timestamp}.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in summary_rows:
                writer.writerow(row)

        print(f"Measurements saved to: {csv_path}")

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
    
    def get_available_commands(self) -> Dict[str, Dict[str, Any]]:
        """Get all available commands with descriptions."""
        return self.command_library.list_commands()
    
    def validate_setup(self) -> Dict[str, Any]:
        """Validate the current setup."""
        return {
            "fiji_path": self.fiji_path,
            "fiji_valid": validate_fiji_path(self.fiji_path),
            "available_commands": len(self.command_library.COMMANDS),
            "supported_extensions": self.file_config.supported_extensions
        }
