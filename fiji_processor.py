"""
Universal Fiji Image Processor for automated image analysis.
Supports cross-platform operation and flexible configuration.
"""

import os
from typing import Optional, List, Dict, Any, Union
from pathlib import Path

from config import ProcessingConfig, FileConfig, GroupConfig, DEFAULT_PROCESSING_CONFIG, DEFAULT_FILE_CONFIG, DEFAULT_GROUP_CONFIG
from utils.general.fiji_utils import find_fiji, validate_fiji_path, get_platform_info
from utils.general.file_utils import (
    find_image_files, find_roi_files, extract_cut_number, 
    create_output_directory, is_bioformats_file, validate_input_directory,
    convert_path_for_fiji
)
from utils.general.macro_builder import MacroBuilder, ImageData, MacroCommand
from utils.general.macros_operation import run_fiji_macro, run_fiji_macro_batch


class FijiProcessor:
    """
    Universal Fiji Image Processor with cross-platform support.
    """
    
    def __init__(self, 
                 fiji_path: Optional[str] = None,
                 processing_config: Optional[ProcessingConfig] = None,
                 file_config: Optional[FileConfig] = None,
                 group_config: Optional[GroupConfig] = None):
        """
        Initialize the Fiji processor.
        
        Args:
            fiji_path: Path to Fiji executable (auto-detected if None)
            processing_config: Processing configuration
            file_config: File configuration
            group_config: Group configuration
        """
        self.processing_config = processing_config or DEFAULT_PROCESSING_CONFIG
        self.file_config = file_config or DEFAULT_FILE_CONFIG
        self.group_config = group_config or DEFAULT_GROUP_CONFIG
        
        # Find Fiji executable
        if fiji_path is None:
            fiji_path = find_fiji()
            if fiji_path is None:
                raise RuntimeError("Fiji not found. Please install Fiji or provide the path manually.")
        
        if not validate_fiji_path(fiji_path):
            raise RuntimeError(f"Invalid Fiji path: {fiji_path}")
        
        self.fiji_path = fiji_path
        self.macro_builder = MacroBuilder(self.processing_config, self.file_config)
        
        print(f"Fiji Processor initialized with Fiji at: {self.fiji_path}")
        print(f"Platform: {get_platform_info()['system']}")
    
    def process_images(self, 
                      base_path: str,
                      group_keywords: Optional[List[str]] = None,
                      mip_only: bool = False,
                      custom_macro: Optional[Union[str, List[str]]] = None,
                      simple_commands: Optional[str] = None,
                      verbose: bool = True) -> Dict[str, Any]:
        """
        Process images with Fiji using various macro options.
        
        Args:
            base_path: Base directory containing images
            group_keywords: List of group keywords to search for
            mip_only: Whether to process only MIP files
            custom_macro: Custom macro code or list of commands
            simple_commands: Space-separated simple command names
            verbose: Whether to print detailed output
            
        Returns:
            Dictionary with processing results
        """
        if not validate_input_directory(base_path):
            return {"success": False, "error": "Invalid input directory"}
        
        if group_keywords is None:
            group_keywords = self.group_config.group_keywords
        
        # Find image files
        image_files = find_image_files(base_path, group_keywords, self.file_config, mip_only)
        
        if not image_files:
            return {"success": False, "error": "No image files found"}
        
        if verbose:
            print(f"Found {len(image_files)} image files to process")
        
        results = {
            "success": True,
            "processed_files": [],
            "failed_files": [],
            "total_files": len(image_files)
        }
        
        # Process each image
        for img_file in image_files:
            try:
                result = self._process_single_image(
                    img_file, custom_macro, simple_commands, verbose
                )
                
                if result["success"]:
                    results["processed_files"].append(img_file)
                else:
                    results["failed_files"].append({"file": img_file, "error": result["error"]})
                    
            except Exception as e:
                error_msg = f"Unexpected error processing {img_file}: {str(e)}"
                if verbose:
                    print(error_msg)
                results["failed_files"].append({"file": img_file, "error": error_msg})
        
        results["success"] = len(results["failed_files"]) == 0
        return results
    
    def process_rois(self, 
                    base_path: str,
                    group_keywords: Optional[List[str]] = None,
                    roi_name_pattern: str = "roi_cut",
                    verbose: bool = True) -> Dict[str, Any]:
        """
        Process ROIs for found images.
        
        Args:
            base_path: Base directory containing images
            group_keywords: List of group keywords to search for
            roi_name_pattern: Pattern for ROI naming
            verbose: Whether to print detailed output
            
        Returns:
            Dictionary with processing results
        """
        if not validate_input_directory(base_path):
            return {"success": False, "error": "Invalid input directory"}
        
        if group_keywords is None:
            group_keywords = self.group_config.group_keywords
        
        # Find image files
        image_files = find_image_files(base_path, group_keywords, self.file_config)
        
        if not image_files:
            return {"success": False, "error": "No image files found"}
        
        if verbose:
            print(f"Found {len(image_files)} image files for ROI processing")
        
        results = {
            "success": True,
            "processed_files": [],
            "failed_files": [],
            "total_files": len(image_files)
        }
        
        # Process ROIs for each image
        for img_file in image_files:
            try:
                result = self._process_single_roi(img_file, roi_name_pattern, verbose)
                
                if result["success"]:
                    results["processed_files"].append(img_file)
                else:
                    results["failed_files"].append({"file": img_file, "error": result["error"]})
                    
            except Exception as e:
                error_msg = f"Unexpected error processing ROIs for {img_file}: {str(e)}"
                if verbose:
                    print(error_msg)
                results["failed_files"].append({"file": img_file, "error": error_msg})
        
        results["success"] = len(results["failed_files"]) == 0
        return results
    
    def _process_single_image(self, 
                             img_file: str,
                             custom_macro: Optional[Union[str, List[str]]] = None,
                             simple_commands: Optional[str] = None,
                             verbose: bool = True) -> Dict[str, Any]:
        """Process a single image file."""
        img_name = os.path.splitext(os.path.basename(img_file))[0]
        
        if verbose:
            print(f"Processing: {img_name}")
        
        # Create output directory and file
        out_dir = create_output_directory(os.path.dirname(img_file), img_name)
        out_file = os.path.join(out_dir, f"{img_name}_processed.tif")
        
        # Prepare image data
        image_data = ImageData(
            input_path=convert_path_for_fiji(img_file),
            output_path=convert_path_for_fiji(out_file),
            file_extension=os.path.splitext(img_file)[1].lower(),
            is_bioformats=is_bioformats_file(img_file, self.file_config)
        )
        
        # Build macro
        if custom_macro:
            macro_code = self.macro_builder.build_custom_macro(custom_macro, image_data)
        elif simple_commands:
            commands = self.macro_builder.parse_simple_commands(simple_commands)
            macro_code = self.macro_builder.build_macro_from_commands(commands)
        else:
            macro_code = self.macro_builder.build_standard_processing_macro(image_data)
        
        if verbose:
            print("Generated macro:")
            print(macro_code)
            print("-" * 50)
        
        # Run macro
        result = run_fiji_macro(self.fiji_path, macro_code, verbose=verbose)
        
        return {
            "success": result["success"],
            "output_file": out_file if result["success"] else None,
            "error": result.get("error", None)
        }
    
    def _process_single_roi(self, 
                           img_file: str,
                           roi_name_pattern: str,
                           verbose: bool = True) -> Dict[str, Any]:
        """Process ROIs for a single image file."""
        img_name = os.path.splitext(os.path.basename(img_file))[0]
        
        if verbose:
            print(f"Processing ROIs for: {img_name}")
        
        # Extract cut number
        cut_number = extract_cut_number(img_name)
        if not cut_number:
            return {"success": False, "error": f"No cut number found in {img_name}"}
        
        # Find ROI files
        roi_paths, roi_names = find_roi_files(img_file, cut_number, self.file_config)
        
        if not roi_paths:
            return {"success": False, "error": f"No ROI files found for cut {cut_number}"}
        
        if verbose:
            print(f"Found {len(roi_paths)} ROI files for cut {cut_number}")
        
        # Prepare image data
        image_data = ImageData(
            input_path=convert_path_for_fiji(img_file),
            output_path="",  # Not needed for ROI processing
            file_extension=os.path.splitext(img_file)[1].lower(),
            is_bioformats=is_bioformats_file(img_file, self.file_config),
            roi_paths=roi_paths
        )
        
        # Build ROI processing macro
        macro_code = self.macro_builder.build_roi_processing_macro(image_data)
        
        if verbose:
            print("Generated ROI macro:")
            print(macro_code)
            print("-" * 50)
        
        # Run macro
        result = run_fiji_macro(self.fiji_path, macro_code, verbose=verbose)
        
        return {
            "success": result["success"],
            "processed_rois": roi_paths if result["success"] else [],
            "error": result.get("error", None)
        }
    
    def update_config(self, 
                     processing_config: Optional[ProcessingConfig] = None,
                     file_config: Optional[FileConfig] = None,
                     group_config: Optional[GroupConfig] = None):
        """Update processor configuration."""
        if processing_config:
            self.processing_config = processing_config
        if file_config:
            self.file_config = file_config
        if group_config:
            self.group_config = group_config
        
        # Recreate macro builder with new config
        self.macro_builder = MacroBuilder(self.processing_config, self.file_config)
    
    def get_available_commands(self) -> List[str]:
        """Get list of available macro commands."""
        return list(self.macro_builder.command_templates.keys())
    
    def validate_setup(self) -> Dict[str, Any]:
        """Validate the current setup."""
        return {
            "fiji_path": self.fiji_path,
            "fiji_valid": validate_fiji_path(self.fiji_path),
            "platform_info": get_platform_info(),
            "available_commands": len(self.get_available_commands()),
            "supported_extensions": self.file_config.supported_extensions,
            "group_keywords": self.group_config.group_keywords
        }
