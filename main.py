"""Command-line interface for the Fiji document processor."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List, Optional, Union

from core_processor import CoreProcessor, ProcessingOptions
from examples.macros_lib import MACROS_LIB
from utils.general.macro_builder import DEFAULT_MACRO_CODE


def _collect_keywords(keyword_args: List[str]) -> List[str]:
    """Expand keyword arguments into individual values."""

    keywords: List[str] = []
    for raw_value in keyword_args:
        keywords.extend(
            part.strip() for part in raw_value.split(",") if part.strip()
        )
    return keywords


def _collect_roi_templates(template_args: List[str]) -> List[str]:
    """Expand ROI template arguments into individual templates."""

    templates: List[str] = []
    for raw_value in template_args:
        templates.extend(
            part.strip() for part in raw_value.split(",") if part.strip()
        )
    return templates


def _resolve_macro_code(
    *,
    macro_code: Optional[str] = None,
    macro_file: Optional[str] = None,
    macro_library: Optional[str] = None,
) -> str:
    """Resolve custom code or a bundled library macro to complete Fiji code."""

    if macro_code is not None:
        value = macro_code.strip()
        if not value:
            raise ValueError("--macro-code must not be empty.")
        return value

    if macro_file is not None:
        path = Path(macro_file).expanduser()
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError(f"Unable to read macro file '{path}': {exc}") from exc
        if not value:
            raise ValueError(f"Macro file '{path}' is empty.")
        return value

    if macro_library is not None:
        if macro_library not in MACROS_LIB:
            raise ValueError(
                f"Macro '{macro_library}' was not found in the bundled library."
            )
        return MACROS_LIB[macro_library]

    return DEFAULT_MACRO_CODE


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Process files by filename keyword and run either complete Fiji macro "
            "code or a bundled library macro."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python main.py /data/study --keyword Exp
  python main.py /data/study --keyword Control --macro-file analysis.ijm
  python main.py /data/study --keyword Control \
      --macro-library measure_matching_roi_per_channel_after_mip --apply-roi
        """,
    )

    parser.add_argument(
        "base_path",
        nargs="?",
        help="Base directory containing the documents to scan.",
    )
    parser.add_argument(
        "--keyword",
        "--keywords",
        dest="keyword",
        action="append",
        help=(
            "Keyword or comma-separated keywords to match in filenames. "
            "Repeat for additional entries."
        ),
    )
    parser.add_argument(
        "--secondary-filter",
        help="Optional secondary substring that must also be present.",
    )

    macro_group = parser.add_mutually_exclusive_group()
    macro_group.add_argument(
        "--macro-code",
        help="Complete Fiji macro code, optionally using project placeholders.",
    )
    macro_group.add_argument(
        "--macro-file",
        help="Path to a complete Fiji .ijm macro file.",
    )
    macro_group.add_argument(
        "--macro-library",
        help="Name of a bundled macro. Use --list-macros to inspect names.",
    )

    parser.add_argument(
        "--fiji-path",
        help="Path to Fiji or ImageJ (Fiji is preferred during auto-detection).",
    )
    parser.add_argument(
        "--apply-roi",
        action="store_true",
        help="Apply ROI files found through the configured templates.",
    )
    parser.add_argument(
        "--save-processed",
        action="store_true",
        help="Save processed images using the configured suffix.",
    )
    parser.add_argument(
        "--save-measurements",
        action="store_true",
        help="Save per-document measurement CSV exports.",
    )
    parser.add_argument(
        "--suffix",
        default="processed",
        help="Suffix appended to processed filenames.",
    )
    parser.add_argument(
        "--measurements-folder",
        default="Measurements",
        help="Folder under the base path for measurement exports.",
    )
    parser.add_argument(
        "--processed-folder",
        default="Processed_Files",
        help="Folder under the base path for processed files.",
    )
    parser.add_argument(
        "--measurement-prefix",
        default="measurements_summary",
        help="Prefix for generated measurement summary files.",
    )
    parser.add_argument(
        "--skip-measurement-summary",
        action="store_true",
        help="Disable creation of the combined measurement summary table.",
    )
    parser.add_argument(
        "--roi-template",
        action="append",
        help=(
            "ROI filename template using {name} for the document stem. "
            "Repeat or comma-separate values."
        ),
    )
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the Fiji / ImageJ setup and exit.",
    )
    parser.add_argument(
        "--list-macros",
        action="store_true",
        help="List bundled macro names and exit.",
    )
    return parser


def main() -> int:
    """Run the command-line interface."""

    args = _build_parser().parse_args()

    try:
        if args.list_macros:
            print("Bundled macros:")
            for name in sorted(MACROS_LIB.keys()):
                print(f"  {name}")
            return 0

        processor = CoreProcessor(fiji_path=args.fiji_path)

        if args.validate:
            validation = processor.validate_setup()
            print(f"Fiji / ImageJ path: {validation['fiji_path']}")
            print(f"Executable valid: {validation['fiji_valid']}")
            print(
                "Supported extensions: "
                + ", ".join(validation["supported_extensions"])
            )
            return 0

        if not args.base_path:
            print("Error: base_path is required unless --validate or --list-macros is used.")
            return 1
        if not args.keyword:
            print("Error: provide at least one --keyword entry.")
            return 1

        parsed_keywords = _collect_keywords(args.keyword)
        if not parsed_keywords:
            print("Error: no usable keyword values were provided.")
            return 1

        keyword_input: Union[List[str], str]
        keyword_input = (
            parsed_keywords[0] if len(parsed_keywords) == 1 else parsed_keywords
        )

        roi_templates: Optional[List[str]] = None
        if args.roi_template:
            roi_templates = _collect_roi_templates(args.roi_template) or None

        macro_code = _resolve_macro_code(
            macro_code=args.macro_code,
            macro_file=args.macro_file,
            macro_library=args.macro_library,
        )
        options = ProcessingOptions(
            apply_roi=args.apply_roi,
            save_processed_files=args.save_processed,
            save_measurements_csv=args.save_measurements,
            custom_suffix=args.suffix,
            secondary_filter=args.secondary_filter,
            measurements_folder=args.measurements_folder,
            processed_folder=args.processed_folder,
            measurement_summary_prefix=args.measurement_prefix,
            generate_measurement_summary=not args.skip_measurement_summary,
            roi_search_templates=roi_templates,
        )

        result = processor.process_documents(
            base_path=os.path.abspath(os.path.expanduser(args.base_path)),
            keyword=keyword_input,
            macro_code=macro_code,
            options=options,
            verbose=args.verbose,
        )

        if not result["success"]:
            print(f"Processing failed: {result['error']}")
            return 1

        print("Processing completed successfully.")
        print(f"Processed documents: {len(result['processed_documents'])}")
        if result.get("measurements"):
            print(
                "Measurements recorded for "
                f"{len(result['measurements'])} document(s)."
            )
        return 0
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
