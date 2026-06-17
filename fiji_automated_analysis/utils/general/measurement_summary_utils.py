"""Helpers for detecting sample naming patterns and aggregating measurement summaries."""

from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


TOKEN_SPLIT_RE = re.compile(r"_+")
ALPHA_NUMERIC_TOKEN_RE = re.compile(r"^([A-Za-z]{2,})(\d+(?:-\d+)*)$")

DEFAULT_ANIMAL_EXCLUDE_PREFIXES = {"cut", "x", "ch", "c"}
SUMMARY_METADATA_FIELDS = {
    "document_name",
    "source_csv",
    "source_image_path",
    "keywords",
    "matched_keyword",
    "secondary_key",
    "filename",
    "MeasurementType",
    "Document",
    "ROI",
    "Scope",
    "Channel",
    "",
    " ",
}


def tokenize_document_name(document_name: str) -> List[str]:
    """Split a filename stem into alphanumeric tokens."""

    return [
        token.strip()
        for token in TOKEN_SPLIT_RE.split(document_name or "")
        if token.strip()
    ]


def _normalize_keyword_map(
    keyword_animal_prefixes: Optional[Mapping[str, str]],
) -> Dict[str, str]:
    if not keyword_animal_prefixes:
        return {}
    normalized: Dict[str, str] = {}
    for keyword, prefix in keyword_animal_prefixes.items():
        clean_keyword = (keyword or "").strip()
        clean_prefix = (prefix or "").strip()
        if clean_keyword:
            normalized[clean_keyword.lower()] = clean_prefix
    return normalized


def _find_keyword_positions(tokens: Sequence[str], matched_keyword: str) -> List[int]:
    keyword_lower = (matched_keyword or "").strip().lower()
    if not keyword_lower:
        return []
    return [idx for idx, token in enumerate(tokens) if keyword_lower in token.lower()]


def _find_token_for_prefix(tokens: Sequence[str], prefix: str) -> Optional[str]:
    clean_prefix = (prefix or "").strip()
    if not clean_prefix:
        return None

    regex = re.compile(rf"^{re.escape(clean_prefix)}(\d+(?:-\d+)*)$", re.IGNORECASE)
    for token in tokens:
        if regex.match(token):
            return token
    return None


def detect_animal_prefix_for_name(
    document_name: str,
    matched_keyword: Optional[str] = None,
    *,
    exclude_prefixes: Optional[Iterable[str]] = None,
) -> str:
    """Infer the animal token prefix (for example ``Potkan`` from ``Potkan1``)."""

    tokens = tokenize_document_name(document_name)
    excluded = {prefix.lower() for prefix in (exclude_prefixes or DEFAULT_ANIMAL_EXCLUDE_PREFIXES)}

    def _candidate_prefixes(token_sequence: Iterable[str]) -> Iterable[str]:
        for token in token_sequence:
            match = ALPHA_NUMERIC_TOKEN_RE.match(token)
            if not match:
                continue
            prefix = match.group(1)
            if prefix.lower() in excluded:
                continue
            yield prefix

    positions = _find_keyword_positions(tokens, matched_keyword or "")
    for position in positions:
        for prefix in _candidate_prefixes(tokens[position + 1 :]):
            return prefix

    for prefix in _candidate_prefixes(tokens):
        return prefix

    return ""


def detect_cut_prefix_for_name(document_name: str) -> str:
    """Infer the section token prefix (for example ``cut`` from ``cut3``)."""

    tokens = tokenize_document_name(document_name)
    for token in tokens:
        match = ALPHA_NUMERIC_TOKEN_RE.match(token)
        if match and match.group(1).lower() == "cut":
            return match.group(1)
    return ""


def detect_summary_naming_patterns(
    base_path: str,
    keywords: Sequence[str],
    *,
    secondary_filter: Optional[str] = None,
    supported_extensions: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Auto-detect per-keyword animal prefixes and the shared cut prefix."""

    keyword_prefix_counters: Dict[str, Counter[str]] = {
        keyword: Counter() for keyword in keywords if keyword
    }
    cut_prefix_counter: Counter[str] = Counter()

    normalized_keywords = [(keyword, keyword.lower()) for keyword in keywords if keyword]
    normalized_extensions = tuple(
        extension.lower() for extension in (supported_extensions or ())
    )
    secondary_lower = (secondary_filter or "").strip().lower()

    for root, dirs, files in os.walk(base_path):
        dirs[:] = [name for name in dirs if name != "_IGNOR_"]
        for filename in files:
            lower_filename = filename.lower()
            if normalized_extensions and not any(
                lower_filename.endswith(extension) for extension in normalized_extensions
            ):
                continue

            matched_keyword = None
            for keyword, keyword_lower in normalized_keywords:
                if keyword_lower in lower_filename:
                    matched_keyword = keyword
                    break

            if not matched_keyword:
                continue

            if secondary_lower and secondary_lower not in lower_filename:
                continue

            stem = Path(filename).stem
            animal_prefix = detect_animal_prefix_for_name(stem, matched_keyword)
            if animal_prefix:
                keyword_prefix_counters.setdefault(matched_keyword, Counter())[animal_prefix] += 1

            cut_prefix = detect_cut_prefix_for_name(stem)
            if cut_prefix:
                cut_prefix_counter[cut_prefix] += 1

    keyword_animal_prefixes = {
        keyword: (counter.most_common(1)[0][0] if counter else "")
        for keyword, counter in keyword_prefix_counters.items()
    }

    cut_prefix = cut_prefix_counter.most_common(1)[0][0] if cut_prefix_counter else ""

    return {
        "keyword_animal_prefixes": keyword_animal_prefixes,
        "cut_prefix": cut_prefix,
    }


def extract_grouping_metadata(
    document_name: str,
    matched_keyword: Optional[str] = None,
    *,
    keyword_animal_prefixes: Optional[Mapping[str, str]] = None,
    cut_prefix: Optional[str] = None,
) -> Dict[str, str]:
    """Extract group, animal, and section metadata from a summary row."""

    tokens = tokenize_document_name(document_name)
    normalized_map = _normalize_keyword_map(keyword_animal_prefixes)
    configured_animal_prefix = normalized_map.get((matched_keyword or "").strip().lower(), "")

    animal_token = _find_token_for_prefix(tokens, configured_animal_prefix)
    animal_prefix = configured_animal_prefix if animal_token else ""

    if not animal_token:
        animal_prefix = detect_animal_prefix_for_name(document_name, matched_keyword)
        animal_token = _find_token_for_prefix(tokens, animal_prefix)

    animal_number = ""
    animal_id = ""
    if animal_token and animal_prefix:
        animal_number = animal_token[len(animal_prefix) :]
        animal_id = animal_token

    resolved_cut_prefix = (cut_prefix or "").strip()
    cut_token = _find_token_for_prefix(tokens, resolved_cut_prefix)
    if not cut_token:
        resolved_cut_prefix = detect_cut_prefix_for_name(document_name)
        cut_token = _find_token_for_prefix(tokens, resolved_cut_prefix)

    cut_number = ""
    cut_id = ""
    if cut_token and resolved_cut_prefix:
        cut_number = cut_token[len(resolved_cut_prefix) :]
        cut_id = cut_token

    return {
        "animal_prefix": animal_prefix,
        "animal_number": animal_number,
        "animal_id": animal_id,
        "cut_prefix": resolved_cut_prefix,
        "cut_number": cut_number,
        "cut_id": cut_id,
    }


def classify_roi_name(roi_name: str, document_name: str = "") -> str:
    """Normalize ROI names into broader classes for aggregation."""

    clean_name = (roi_name or "").strip()
    if not clean_name:
        return ""
    clean_document_name = (document_name or "").strip()
    if clean_document_name and clean_name == clean_document_name:
        return "matching_named_roi"
    if re.fullmatch(r"ROI_\d+", clean_name):
        return "indexed_roi"
    return clean_name


def resolve_measurement_type(row: Mapping[str, Any]) -> str:
    """Resolve a stable measurement-type label from a summary row."""

    measurement_type = str(row.get("MeasurementType") or "").strip()
    if measurement_type:
        return measurement_type

    scope = str(row.get("Scope") or "").strip()
    if scope:
        return scope

    channel = normalize_channel_name(str(row.get("Channel") or ""))
    if channel:
        return channel

    return "Unspecified"


def measurement_type_to_slug(measurement_type: str) -> str:
    """Convert a measurement label into a filesystem-friendly suffix."""

    clean = re.sub(r"[^A-Za-z0-9]+", "_", (measurement_type or "").strip()).strip("_")
    return clean.lower() or "unspecified"


def split_summary_rows_by_measurement_type(
    summary_rows: Sequence[Mapping[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Partition summary rows by their resolved measurement type."""

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in summary_rows:
        measurement_type = resolve_measurement_type(row)
        grouped.setdefault(measurement_type, []).append(dict(row))
    return grouped


def normalize_channel_name(channel_name: str) -> str:
    """Reduce Fiji window titles to a stable channel label."""

    clean_name = (channel_name or "").strip()
    if not clean_name:
        return ""

    match = re.match(r"^(C\d+(?:-[A-Za-z0-9]+)?)", clean_name, re.IGNORECASE)
    if match:
        return match.group(1)

    for separator in ("_", " "):
        if separator in clean_name:
            return clean_name.split(separator, 1)[0]

    return clean_name


def detect_numeric_columns(summary_rows: Sequence[Mapping[str, Any]]) -> List[str]:
    """Return the columns that contain numeric values across the supplied rows."""

    if not summary_rows:
        return []

    candidate_columns: List[str] = []
    for row in summary_rows:
        for key in row.keys():
            if key not in candidate_columns and (key or "").strip():
                candidate_columns.append(key)

    numeric_columns: List[str] = []
    for column in candidate_columns:
        if column in SUMMARY_METADATA_FIELDS:
            continue

        saw_numeric = False
        is_numeric = True
        for row in summary_rows:
            value = row.get(column)
            if value in (None, ""):
                continue
            try:
                float(str(value).strip())
                saw_numeric = True
            except (TypeError, ValueError):
                is_numeric = False
                break

        if saw_numeric and is_numeric:
            numeric_columns.append(column)

    return numeric_columns


def build_slice_and_animal_summary_rows(
    summary_rows: Sequence[Mapping[str, Any]],
    *,
    keyword_animal_prefixes: Optional[Mapping[str, str]] = None,
    cut_prefix: Optional[str] = None,
) -> Dict[str, Any]:
    """Build slice-level and animal-level average rows from a flat summary table."""

    if not summary_rows:
        return {
            "slice_rows": [],
            "slice_fieldnames": [],
            "animal_rows": [],
            "animal_fieldnames": [],
        }

    numeric_columns = detect_numeric_columns(summary_rows)
    if not numeric_columns:
        return {
            "slice_rows": [],
            "slice_fieldnames": [],
            "animal_rows": [],
            "animal_fieldnames": [],
        }

    slice_rows = _aggregate_to_slice_rows(
        summary_rows,
        numeric_columns=numeric_columns,
        keyword_animal_prefixes=keyword_animal_prefixes,
        cut_prefix=cut_prefix,
    )
    animal_rows = _aggregate_slice_rows_to_animal_rows(
        slice_rows,
        numeric_columns=numeric_columns,
    )

    slice_fieldnames = _build_slice_fieldnames(numeric_columns)
    animal_fieldnames = _build_animal_fieldnames(numeric_columns)

    return {
        "slice_rows": slice_rows,
        "slice_fieldnames": slice_fieldnames,
        "animal_rows": animal_rows,
        "animal_fieldnames": animal_fieldnames,
    }


def _aggregate_to_slice_rows(
    summary_rows: Sequence[Mapping[str, Any]],
    *,
    numeric_columns: Sequence[str],
    keyword_animal_prefixes: Optional[Mapping[str, str]] = None,
    cut_prefix: Optional[str] = None,
) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, ...], Dict[str, Any]] = {}

    for row in summary_rows:
        document_name = str(
            row.get("document_name")
            or row.get("Document")
            or row.get("filename")
            or ""
        )
        matched_keyword = str(row.get("matched_keyword") or "").strip()
        metadata = extract_grouping_metadata(
            document_name,
            matched_keyword,
            keyword_animal_prefixes=keyword_animal_prefixes,
            cut_prefix=cut_prefix,
        )
        measurement_type = resolve_measurement_type(row)
        roi_class = classify_roi_name(str(row.get("ROI") or ""), document_name)
        channel = normalize_channel_name(str(row.get("Channel") or ""))
        scope = str(row.get("Scope") or "").strip()
        secondary_key = str(row.get("secondary_key") or "").strip()
        keywords = str(row.get("keywords") or "").strip()

        group_key = (
            matched_keyword,
            metadata["animal_id"] or document_name,
            metadata["cut_id"] or document_name,
            measurement_type,
            channel,
            scope,
            roi_class,
        )

        aggregate = grouped.get(group_key)
        if aggregate is None:
            aggregate = {
                "matched_keyword": matched_keyword,
                "keywords": keywords,
                "secondary_key": secondary_key,
                "animal_prefix": metadata["animal_prefix"],
                "animal_number": metadata["animal_number"],
                "animal_id": metadata["animal_id"],
                "cut_prefix": metadata["cut_prefix"],
                "cut_number": metadata["cut_number"],
                "cut_id": metadata["cut_id"],
                "MeasurementType": measurement_type,
                "Channel": channel,
                "Scope": scope,
                "roi_class": roi_class,
                "source_row_count": 0,
                "_source_documents": set(),
                "_source_csvs": set(),
                "_sums": {column: 0.0 for column in numeric_columns},
                "_counts": {column: 0 for column in numeric_columns},
            }
            grouped[group_key] = aggregate

        aggregate["source_row_count"] += 1
        if document_name:
            aggregate["_source_documents"].add(document_name)
        source_csv = str(row.get("source_csv") or "").strip()
        if source_csv:
            aggregate["_source_csvs"].add(source_csv)

        for column in numeric_columns:
            value = row.get(column)
            if value in (None, ""):
                continue
            try:
                aggregate["_sums"][column] += float(str(value).strip())
                aggregate["_counts"][column] += 1
            except (TypeError, ValueError):
                continue

    rows: List[Dict[str, Any]] = []
    for aggregate in grouped.values():
        row = {
            "matched_keyword": aggregate["matched_keyword"],
            "keywords": aggregate["keywords"],
            "secondary_key": aggregate["secondary_key"],
            "animal_prefix": aggregate["animal_prefix"],
            "animal_number": aggregate["animal_number"],
            "animal_id": aggregate["animal_id"],
            "cut_prefix": aggregate["cut_prefix"],
            "cut_number": aggregate["cut_number"],
            "cut_id": aggregate["cut_id"],
            "MeasurementType": aggregate["MeasurementType"],
            "Channel": aggregate["Channel"],
            "Scope": aggregate["Scope"],
            "roi_class": aggregate["roi_class"],
            "source_row_count": aggregate["source_row_count"],
            "source_document_count": len(aggregate["_source_documents"]),
            "source_documents": " | ".join(sorted(aggregate["_source_documents"])),
            "source_csvs": " | ".join(sorted(aggregate["_source_csvs"])),
        }
        for column in numeric_columns:
            count = aggregate["_counts"][column]
            row[column] = (
                aggregate["_sums"][column] / count if count else ""
            )
        rows.append(row)

    return sorted(
        rows,
        key=lambda item: (
            str(item.get("matched_keyword") or ""),
            str(item.get("animal_id") or ""),
            str(item.get("cut_id") or ""),
            str(item.get("MeasurementType") or ""),
            str(item.get("Channel") or ""),
            str(item.get("Scope") or ""),
            str(item.get("roi_class") or ""),
        ),
    )


def _aggregate_slice_rows_to_animal_rows(
    slice_rows: Sequence[Mapping[str, Any]],
    *,
    numeric_columns: Sequence[str],
) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, ...], Dict[str, Any]] = {}

    for row in slice_rows:
        matched_keyword = str(row.get("matched_keyword") or "").strip()
        animal_id = str(row.get("animal_id") or "").strip()
        measurement_type = resolve_measurement_type(row)
        channel = normalize_channel_name(str(row.get("Channel") or ""))
        scope = str(row.get("Scope") or "").strip()
        roi_class = str(row.get("roi_class") or "").strip()
        keywords = str(row.get("keywords") or "").strip()
        secondary_key = str(row.get("secondary_key") or "").strip()

        group_key = (
            matched_keyword,
            animal_id or str(row.get("source_documents") or ""),
            measurement_type,
            channel,
            scope,
            roi_class,
        )

        aggregate = grouped.get(group_key)
        if aggregate is None:
            aggregate = {
                "matched_keyword": matched_keyword,
                "keywords": keywords,
                "secondary_key": secondary_key,
                "animal_prefix": str(row.get("animal_prefix") or ""),
                "animal_number": str(row.get("animal_number") or ""),
                "animal_id": animal_id,
                "MeasurementType": measurement_type,
                "Channel": channel,
                "Scope": scope,
                "roi_class": roi_class,
                "_cut_ids": set(),
                "_source_documents": set(),
                "_sums": {column: 0.0 for column in numeric_columns},
                "_counts": {column: 0 for column in numeric_columns},
            }
            grouped[group_key] = aggregate

        cut_id = str(row.get("cut_id") or "").strip()
        if cut_id:
            aggregate["_cut_ids"].add(cut_id)
        source_documents = str(row.get("source_documents") or "").strip()
        if source_documents:
            for document_name in source_documents.split(" | "):
                if document_name:
                    aggregate["_source_documents"].add(document_name)

        for column in numeric_columns:
            value = row.get(column)
            if value in (None, ""):
                continue
            try:
                aggregate["_sums"][column] += float(str(value).strip())
                aggregate["_counts"][column] += 1
            except (TypeError, ValueError):
                continue

    rows: List[Dict[str, Any]] = []
    for aggregate in grouped.values():
        cut_ids = sorted(aggregate["_cut_ids"])
        row = {
            "matched_keyword": aggregate["matched_keyword"],
            "keywords": aggregate["keywords"],
            "secondary_key": aggregate["secondary_key"],
            "animal_prefix": aggregate["animal_prefix"],
            "animal_number": aggregate["animal_number"],
            "animal_id": aggregate["animal_id"],
            "MeasurementType": aggregate["MeasurementType"],
            "Channel": aggregate["Channel"],
            "Scope": aggregate["Scope"],
            "roi_class": aggregate["roi_class"],
            "slice_count": len(cut_ids),
            "cut_ids": " | ".join(cut_ids),
            "source_document_count": len(aggregate["_source_documents"]),
            "source_documents": " | ".join(sorted(aggregate["_source_documents"])),
        }
        for column in numeric_columns:
            count = aggregate["_counts"][column]
            row[column] = (
                aggregate["_sums"][column] / count if count else ""
            )
        rows.append(row)

    return sorted(
        rows,
        key=lambda item: (
            str(item.get("matched_keyword") or ""),
            str(item.get("animal_id") or ""),
            str(item.get("MeasurementType") or ""),
            str(item.get("Channel") or ""),
            str(item.get("Scope") or ""),
            str(item.get("roi_class") or ""),
        ),
    )


def _build_slice_fieldnames(numeric_columns: Sequence[str]) -> List[str]:
    return [
        "matched_keyword",
        "keywords",
        "secondary_key",
        "animal_prefix",
        "animal_number",
        "animal_id",
        "cut_prefix",
        "cut_number",
        "cut_id",
        "MeasurementType",
        "Channel",
        "Scope",
        "roi_class",
        "source_row_count",
        "source_document_count",
        "source_documents",
        "source_csvs",
        *numeric_columns,
    ]


def _build_animal_fieldnames(numeric_columns: Sequence[str]) -> List[str]:
    return [
        "matched_keyword",
        "keywords",
        "secondary_key",
        "animal_prefix",
        "animal_number",
        "animal_id",
        "MeasurementType",
        "Channel",
        "Scope",
        "roi_class",
        "slice_count",
        "cut_ids",
        "source_document_count",
        "source_documents",
        *numeric_columns,
    ]
