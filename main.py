"""Command-line interface for the Fiji document processor."""

import argparse
import os
from typing import List, Optional, Union

from core_processor import CommandLibrary, CoreProcessor, ProcessingOptions


def _collect_keywords(keyword_args: List[str]) -> List[str]:
    """Expand a list of keyword arguments into individual values."""

    keywords: List[str] = []
    for raw_value in keyword_args:
        parts = [part.strip() for part in raw_value.split(",")]
        keywords.extend(part for part in parts if part)

    return keywords


def _collect_roi_templates(template_args: List[str]) -> List[str]:
    """Expand ROI template arguments into individual templates."""

    templates: List[str] = []
    for raw_value in template_args:
        parts = [part.strip() for part in raw_value.split(",")]
        templates.extend(part for part in parts if part)

    return templates


def main() -> int:
    """Main entry point for keyword-driven Fiji automation."""

    parser = argparse.ArgumentParser(
        description="Process files in a directory tree by matching filename keywords and running Fiji macros",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Basic processing for a single keyword
  python main.py /data/study --keyword 4MU

  # Process multiple keywords and provide custom ROI templates
  python main.py /data/study --keyword 4MU --keyword Control --roi-template "{name}_ROI.zip"

  # Combine commands, ROI application, and custom measurement prefix
  python main.py /data/study --keyword "4MU,Control" --apply-roi --commands "open_standard measure" \
      --measurement-prefix studyA --save-processed --suffix analyzed
        """,
    )

    parser.add_argument("base_path", nargs="?", help="Base directory containing the documents to scan")
    parser.add_argument(
        "--keyword",
        "--keywords",
        dest="keyword",
        action="append",
        help="Keyword or comma-separated list of keywords to match in filenames. Repeat for additional entries.",
    )
    parser.add_argument(
        "--secondary-filter",
        help="Optional secondary substring that must also be present (e.g. 'MIP').",
    )
    parser.add_argument(
        "--commands",
        help="Space-separated macro commands to run instead of the default open/measure/save workflow.",
    )
    parser.add_argument("--fiji-path", help="Path to the Fiji executable (auto-detected if omitted).")
    parser.add_argument("--apply-roi", action="store_true", help="Apply ROI files when found using the configured templates.")
    parser.add_argument("--save-processed", action="store_true", help="Save processed images using the configured suffix.")
    parser.add_argument(
        "--save-measurements",
        action="store_true",
        help="Save per-document measurement CSV exports using the configured folder.",
    )
    parser.add_argument(
        "--suffix",
        default="processed",
        help="Suffix appended to processed filenames (default: 'processed').",
    )
    parser.add_argument(
        "--measurements-folder",
        default="Measurements",
        help="Folder name (relative to the base path) that stores measurement exports.",
    )
    parser.add_argument(
        "--processed-folder",
        default="Processed_Files",
        help="Folder name (relative to the base path) where processed files are saved.",
    )
    parser.add_argument(
        "--measurement-prefix",
        default="measurements_summary",
        help="Prefix for generated measurement summary files (CSV and JSON).",
    )
    parser.add_argument(
        "--roi-template",
        action="append",
        help="ROI filename template using {name} as the placeholder for the document stem. Repeat or comma-separate values.",
    )
    parser.add_argument("--verbose", action="store_true", help="Print verbose processing information.")
    parser.add_argument("--validate", action="store_true", help="Validate the Fiji setup and exit.")
    parser.add_argument("--list-commands", action="store_true", help="List all available macro commands and exit.")
    args = parser.parse_args()

    try:
        if args.list_commands:
            library = CommandLibrary()
            commands = library.list_commands()

            print("Available Commands:")
            print("=" * 50)
            for name, info in commands.items():
                print(f"\n{name}")
                print(f"  Description: {info['description']}")
                if info.get("parameters"):
                    print(f"  Parameters: {info['parameters']}")
                print(f"  Example: {info['example']}")
            return 0

        processor = CoreProcessor(fiji_path=args.fiji_path)

        if args.validate:
            print("Validating setup...")
            validation = processor.validate_setup()
            print(f"Fiji path: {validation['fiji_path']}")
            print(f"Fiji valid: {validation['fiji_valid']}")
            print(f"Available commands: {validation['available_commands']}")
            print(f"Supported extensions: {validation['supported_extensions']}")
            return 0

        if not args.base_path:
            print("Error: base_path is required when not running in --list-commands or --validate mode.")
            return 1

        if not args.keyword:
            print("Error: Provide at least one --keyword entry (comma-separated values are accepted).")
            return 1

        base_path = os.path.abspath(os.path.expanduser(args.base_path))

        parsed_keywords = _collect_keywords(args.keyword)
        if not parsed_keywords:
            print("Error: No usable keyword values were provided.")
            return 1
        keyword_input: Union[List[str], str]
        if len(parsed_keywords) == 1:
            keyword_input = parsed_keywords[0]
        else:
            keyword_input = parsed_keywords

        roi_templates: Optional[List[str]] = None
        if args.roi_template:
            parsed_templates = _collect_roi_templates(args.roi_template)
            roi_templates = parsed_templates or None
            
        options = ProcessingOptions(
            apply_roi=args.apply_roi,
            save_processed_files=args.save_processed,
            save_measurements_csv=args.save_measurements,
            custom_suffix=args.suffix,
            secondary_filter=args.secondary_filter,
            measurements_folder=args.measurements_folder,
            processed_folder=args.processed_folder,
            measurement_summary_prefix=args.measurement_prefix,
            roi_search_templates=roi_templates,
        )

        result = processor.process_documents(
            base_path=base_path,
            keyword=keyword_input,
            macro_commands=args.commands,
            options=options,
            verbose=args.verbose,
        )

        if result["success"]:
            print("\n✅ Processing completed successfully!")
            if result.get("searched_keywords"):
                print("Keywords:", ", ".join(result["searched_keywords"]))
            print(f"Processed documents: {len(result['processed_documents'])}")
            if args.verbose and result["processed_documents"]:
                for entry in result["processed_documents"]:
                    match_note = (
                        f" (matched keyword: {entry['matched_keyword']})"
                        if entry.get("matched_keyword")
                        else ""
                    )
                    secondary_note = (
                        f" [secondary: {entry['secondary_key']}]"
                        if entry.get("secondary_key")
                        else ""
                    )
                    print(f"  - {entry['filename']}{match_note}{secondary_note}")
            if result["measurements"]:
                print(f"Measurements recorded for {len(result['measurements'])} document(s).")
            if result["failed_documents"]:
                print(f"Completed with {len(result['failed_documents'])} warning(s):")
                for failed in result["failed_documents"]:
                    match_note = (
                        f" (matched keyword: {failed['matched_keyword']})"
                        if failed.get("matched_keyword")
                        else ""
                    )
                    secondary_note = (
                        f" [secondary: {failed['secondary_key']}]"
                        if failed.get("secondary_key")
                        else ""
                    )
                    print(f"  - {failed['filename']}{match_note}{secondary_note}: {failed['error']}")
        else:
            print(f"\n❌ Processing failed: {result['error']}")
            if result.get("searched_keywords"):
                print("Keywords:", ", ".join(result["searched_keywords"]))
            return 1

    except Exception as exc:  # pragma: no cover - defensive CLI fallback
        print(f"Error: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
