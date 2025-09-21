"""
Fiji Document Processor - Main Entry Point
Database-driven document processing with measurements and optional features.
"""

import os
import argparse
from typing import Optional, List

from core_processor import CoreProcessor, ProcessingOptions, CommandLibrary
from config import ProcessingConfig, FileConfig, GroupConfig
from utils.general.fiji_utils import find_fiji


def main():
    """Main entry point for the Fiji Document Processor."""
    parser = argparse.ArgumentParser(
        description="Fiji Document Processor - Database-driven document processing with measurements",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic processing - find documents with keyword and measure them
  python main.py /path/to/documents --keyword "experimental"

  # Process with secondary filter (e.g., MIP files)
  python main.py /path/to/documents --keyword "experimental" --secondary-filter "MIP"

  # Apply custom macro commands
  python main.py /path/to/documents --keyword "control" --commands "open_standard convert_8bit measure"

  # Process with ROI and save processed files
  python main.py /path/to/documents --keyword "treatment" --apply-roi --save-processed --suffix "analyzed"

  # Show available commands
  python main.py --list-commands

  # Validate setup
  python main.py --validate
        """
    )
    
    parser.add_argument("base_path", nargs="?", help="Base directory containing documents")
    parser.add_argument("--keyword", help="Keyword to search for in document names")
    parser.add_argument("--secondary-filter", help="Secondary filter (e.g., 'MIP', 'processed')")
    parser.add_argument("--commands", help="Space-separated macro commands to apply")
    parser.add_argument("--fiji-path", help="Path to Fiji executable (auto-detected if not provided)")
    parser.add_argument("--apply-roi", action="store_true", help="Apply ROI processing if ROI files found")
    parser.add_argument("--save-processed", action="store_true", help="Save processed files to separate directory")
    parser.add_argument("--suffix", default="processed", help="Suffix for processed files (default: 'processed')")
    parser.add_argument("--measurements-folder", default="Measurements", help="Folder for measurements (default: 'Measurements')")
    parser.add_argument("--processed-folder", default="Processed_Files", help="Folder for processed files (default: 'Processed_Files')")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--validate", action="store_true", help="Validate setup and exit")
    parser.add_argument("--list-commands", action="store_true", help="List all available commands and exit")
    
    args = parser.parse_args()
    
    try:
        if args.list_commands:
            # Show commands without initializing processor (no Fiji validation needed)
            from core_processor import CommandLibrary
            library = CommandLibrary()
            commands = library.list_commands()
            
            print("Available Commands:")
            print("=" * 50)
            for cmd_name, cmd_info in commands.items():
                print(f"\n{cmd_name}")
                print(f"  Description: {cmd_info['description']}")
                if cmd_info.get('parameters'):
                    print(f"  Parameters: {cmd_info['parameters']}")
                print(f"  Example: {cmd_info['example']}")
            return 0
        
        # Initialize processor
        processor = CoreProcessor(fiji_path=args.fiji_path)
        
        if args.validate:
            print("Validating setup...")
            validation = processor.validate_setup()
            print(f"Fiji path: {validation['fiji_path']}")
            print(f"Fiji valid: {validation['fiji_valid']}")
            print(f"Available commands: {validation['available_commands']}")
            print(f"Supported extensions: {validation['supported_extensions']}")
            return 0
        
        if not args.base_path or not args.keyword:
            print("Error: Both --base_path and --keyword are required for processing")
            print("Use --help for usage information")
            return 1
        
        # Create processing options
        options = ProcessingOptions(
            apply_roi=args.apply_roi,
            save_processed_files=args.save_processed,
            custom_suffix=args.suffix,
            secondary_filter=args.secondary_filter,
            measurements_folder=args.measurements_folder,
            processed_folder=args.processed_folder
        )
        
        # Process documents
        result = processor.process_documents(
            base_path=args.base_path,
            keyword=args.keyword,
            macro_commands=args.commands,
            options=options,
            verbose=args.verbose
        )
        
        # Print results
        if result["success"]:
            print(f"\n✅ Processing completed successfully!")
            print(f"Processed documents: {len(result['processed_documents'])}")
            print(f"Measurements: {len(result['measurements'])}")
            if result.get('failed_documents'):
                print(f"Failed documents: {len(result['failed_documents'])}")
                for failed in result['failed_documents']:
                    print(f"  - {failed['filename']}: {failed['error']}")
        else:
            print(f"\n❌ Processing failed: {result['error']}")
            return 1
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    
    return 0


def process_images_with_fiji(base_path: str, 
                           fiji_path: Optional[str] = None,
                           group_keywords: Optional[List[str]] = None, 
                           mip_only: bool = False,
                           custom_macro: Optional[str] = None,
                           simple_commands: Optional[str] = None) -> dict:
    """
    Legacy function for backward compatibility.
    
    Args:
        base_path: Base directory containing images
        fiji_path: Path to Fiji executable
        group_keywords: List of group keywords to search for
        mip_only: Whether to process only MIP files
        custom_macro: Custom macro code
        simple_commands: Space-separated simple command names
        
    Returns:
        Dictionary with processing results
    """
    processor = FijiProcessor(fiji_path=fiji_path)
    
    return processor.process_images(
        base_path=base_path,
        group_keywords=group_keywords,
        mip_only=mip_only,
        custom_macro=custom_macro,
        simple_commands=simple_commands,
        verbose=True
    )


if __name__ == "__main__":
    exit(main())


