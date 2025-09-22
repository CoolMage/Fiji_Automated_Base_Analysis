"""
Core Fiji Document Processor - Database-driven document processing with measurements.
Focuses on keyword-based document selection, macro application, and measurement saving.
All other features are optional and customizable.
"""

import os
import json
import csv
from typing import List, Dict, Optional, Any, Union, Sequence
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

from config import ProcessingConfig, FileConfig, GroupConfig
from utils.general.fiji_utils import find_fiji, validate_fiji_path
from utils.general.file_utils import normalize_path, convert_path_for_fiji, is_bioformats_file
from utils.general.macro_builder import MacroBuilder, ImageData, MacroCommand
from utils.general.macros_operation import run_fiji_macro


@dataclass
class DocumentInfo:
    """Information about a document to be processed."""
    file_path: str
    filename: str
    keyword: Union[str, Sequence[str]]
    matched_keyword: Optional[str] = None
    secondary_key: Optional[str] = None
    roi_path: Optional[str] = None
    measurements: Optional[Dict[str, Any]] = None


@dataclass
class ProcessingOptions:
    """Optional processing options."""
    apply_roi: bool = False
    save_processed_files: bool = False
    custom_suffix: str = "processed"
    secondary_filter: Optional[str] = None
    measurements_folder: str = "Measurements"
    processed_folder: str = "Processed_Files"


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
            "parameters": {"output_path": "Path for CSV file"},
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
    
    def __init__(self,
                 fiji_path: Optional[str] = None,
                 processing_config: Optional[ProcessingConfig] = None,
                 file_config: Optional[FileConfig] = None,
                 group_config: Optional[GroupConfig] = None):
        """
        Initialize the core processor.
        
        Args:
            fiji_path: Path to Fiji executable (auto-detected if None)
            processing_config: Processing configuration
            file_config: File configuration
            group_config: Group configuration
        """
        self.processing_config = processing_config or ProcessingConfig()
        self.file_config = file_config or FileConfig()
        self.group_config = group_config or GroupConfig()
        
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
    def _normalize_keywords(keyword_input: Union[str, Sequence[str]]) -> List[str]:
        """Normalize keyword input into a list of strings for matching."""
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
            normalized_keywords.append(kw)

        return normalized_keywords

    @staticmethod
    def _format_keywords(keyword_input: Union[str, Sequence[str]]) -> str:
        """Return a human-friendly representation of keyword input."""
        if isinstance(keyword_input, str):
            return keyword_input
        return ", ".join(keyword_input)

    def find_documents_by_keyword(self,
                                  base_path: str,
                                  keyword: Union[str, Sequence[str]],
                                  secondary_filter: Optional[str] = None) -> List[DocumentInfo]:
        """
        Find documents by keyword with optional secondary filtering.

        Args:
            base_path: Base directory to search
            keyword: Primary keyword or sequence of keywords to search for
            secondary_filter: Optional secondary filter (e.g., "MIP", "processed", etc.)

        Returns:
            List of DocumentInfo objects
        """
        keyword_list = self._normalize_keywords(keyword)
        keyword_pairs = [(kw, kw.lower()) for kw in keyword_list]
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

                file_path = os.path.join(root, file)
                filename = os.path.splitext(file)[0]

                # Look for associated ROI file
                roi_path = None
                roi_candidates = [
                    os.path.join(root, f"{filename}.roi"),
                    os.path.join(root, f"{filename}.zip"),
                    os.path.join(root, f"RoiSet_{filename}.zip")
                ]

                for roi_candidate in roi_candidates:
                    if os.path.exists(roi_candidate):
                        roi_path = roi_candidate
                        break

                # Extract secondary key if present
                secondary_key = None
                if secondary_filter:
                    # Try to extract the secondary key from filename
                    for ext in self.file_config.supported_extensions:
                        if file_lower.endswith(ext.lower()):
                            base_name = file[:-len(ext)]
                            if secondary_filter.lower() in base_name.lower():
                                secondary_key = secondary_filter
                                break

                documents.append(DocumentInfo(
                    file_path=normalize_path(file_path),
                    filename=filename,
                    keyword=keyword,
                    matched_keyword=matched_keyword,
                    secondary_key=secondary_key,
                    roi_path=roi_path
                ))

        return documents

    def process_documents(self,
                         base_path: str,
                         keyword: Union[str, Sequence[str]],
                         macro_commands: Union[str, List[str], None] = None,
                         options: Optional[ProcessingOptions] = None,
                         verbose: bool = True) -> Dict[str, Any]:
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
        
        # Find documents
        documents = self.find_documents_by_keyword(
            base_path,
            keyword,
            options.secondary_filter
        )

        if not documents:
            return {
                "success": False,
                "error": f"No documents found with keyword(s): {self._format_keywords(keyword)}",
                "processed_documents": [],
                "failed_documents": [],
                "measurements": []
            }

        if verbose:
            keyword_display = self._format_keywords(keyword)
            print(f"Found {len(documents)} documents matching keyword(s): {keyword_display}")
            if options.secondary_filter:
                print(f"Secondary filter: '{options.secondary_filter}'")
        
        results = {
            "success": True,
            "processed_documents": [],
            "failed_documents": [],
            "measurements": []
        }
        
        # Create output directories
        measurements_dir = os.path.join(base_path, options.measurements_folder)
        if options.save_processed_files:
            processed_dir = os.path.join(base_path, options.processed_folder)
            os.makedirs(processed_dir, exist_ok=True)
        
        os.makedirs(measurements_dir, exist_ok=True)
        
        # Process each document
        for doc in documents:
            try:
                result = self._process_single_document(doc, macro_commands, options, verbose)
                
                if result["success"]:
                    results["processed_documents"].append(doc.filename)
                    if result.get("measurements"):
                        results["measurements"].append({
                            "filename": doc.filename,
                            "measurements": result["measurements"]
                        })
                else:
                    results["failed_documents"].append({
                        "filename": doc.filename,
                        "error": result["error"]
                    })
                    
            except Exception as e:
                error_msg = f"Unexpected error processing {doc.filename}: {str(e)}"
                if verbose:
                    print(f"❌ {error_msg}")
                results["failed_documents"].append({
                    "filename": doc.filename,
                    "error": error_msg
                })
        
        # Save measurements summary
        if results["measurements"]:
            self._save_measurements_summary(measurements_dir, results["measurements"])
        
        results["success"] = len(results["failed_documents"]) == 0
        return results
    
    def _process_single_document(self, 
                                doc: DocumentInfo,
                                macro_commands: Union[str, List[str], None],
                                options: ProcessingOptions,
                                verbose: bool) -> Dict[str, Any]:
        """Process a single document."""
        if verbose:
            match_info = f" (matched keyword: {doc.matched_keyword})" if doc.matched_keyword else ""
            print(f"Processing: {doc.filename}{match_info}")
        
        # Prepare image data
        image_data = ImageData(
            input_path=convert_path_for_fiji(doc.file_path),
            output_path="",  # Will be set if saving processed files
            file_extension=os.path.splitext(doc.file_path)[1].lower(),
            is_bioformats=is_bioformats_file(doc.file_path, self.file_config),
            roi_paths=[doc.roi_path] if doc.roi_path and options.apply_roi else None
        )
        
        # Set output path if saving processed files
        if options.save_processed_files:
            processed_dir = os.path.join(os.path.dirname(doc.file_path), "..", options.processed_folder)
            processed_dir = os.path.abspath(processed_dir)
            os.makedirs(processed_dir, exist_ok=True)
            
            output_filename = f"{doc.filename}_{options.custom_suffix}.tif"
            image_data.output_path = convert_path_for_fiji(os.path.join(processed_dir, output_filename))
        
        # Build macro
        if macro_commands is None:
            # Default: open, measure, save measurements, quit
            macro_commands = ["open_standard", "measure", "save_csv", "quit"]
        elif isinstance(macro_commands, str):
            # Parse command string
            macro_commands = macro_commands.split()
        
        # Build macro from commands
        commands = []
        for cmd_str in macro_commands:
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
        
        macro_code = self.macro_builder.build_macro_from_commands(commands)
        
        # Substitute template variables
        macro_code = macro_code.format(
            input_path=image_data.input_path,
            output_path=image_data.output_path
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
    
    def _save_measurements_summary(self, measurements_dir: str, measurements: List[Dict[str, Any]]):
        """Save measurements summary to CSV and JSON."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save as CSV
        csv_path = os.path.join(measurements_dir, f"measurements_summary_{timestamp}.csv")
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            if measurements:
                # Get all unique measurement keys
                all_keys = set()
                for m in measurements:
                    if isinstance(m.get("measurements"), dict):
                        all_keys.update(m["measurements"].keys())
                
                fieldnames = ["filename"] + sorted(all_keys)
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for m in measurements:
                    row = {"filename": m["filename"]}
                    if isinstance(m.get("measurements"), dict):
                        row.update(m["measurements"])
                    writer.writerow(row)
        
        # Save as JSON
        json_path = os.path.join(measurements_dir, f"measurements_summary_{timestamp}.json")
        with open(json_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(measurements, jsonfile, indent=2, default=str)
        
        print(f"Measurements saved to: {csv_path} and {json_path}")
    
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
