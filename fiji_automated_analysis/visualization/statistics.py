"""Statistical helpers for group-level microscopy plots."""

from __future__ import annotations

import itertools
import math
import warnings
from dataclasses import asdict, dataclass
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


ALPHA = 0.05
MIN_PARAMETRIC_GROUP_N = 8
CONTROL_HINTS = ("control", "ctrl")


@dataclass(frozen=True)
class GroupSummary:
    """Descriptive and assumption-checking results for one group."""

    group: str
    n: int
    mean: float
    sd: float
    sem: float
    median: float
    q1: float
    q3: float
    normality_test: str
    normality_applicable: bool
    normality_p: float
    normality_passed: bool | None
    normality_note: str


@dataclass(frozen=True)
class PairwiseComparison:
    """Statistical comparison used for plot annotations."""

    group_a: str
    group_b: str
    n_a: int
    n_b: int
    test: str
    statistic_name: str
    statistic: float
    p_value: float
    p_value_adjusted: float
    p_adjustment: str
    significance: str
    alpha: float
    normality_a_p: float
    normality_b_p: float
    variance_test: str
    variance_p: float
    selection_reason: str


def control_first_order(
    groups: Iterable[object],
    *,
    control_label: str | None = None,
) -> list[str]:
    """Return groups with the detected control first and all others after it."""

    levels = [str(group) for group in groups if pd.notna(group)]
    unique_levels = list(dict.fromkeys(levels))
    if not unique_levels:
        return []

    control = _find_control_group(unique_levels, control_label)
    if control is None:
        return unique_levels
    return [control] + [group for group in unique_levels if group != control]


def summarize_groups(
    data: pd.DataFrame,
    *,
    group_col: str = "group",
    value_col: str = "value",
    group_order: Sequence[str] | None = None,
    alpha: float = ALPHA,
) -> list[GroupSummary]:
    """Compute descriptive statistics and normality checks by group."""

    stats = _scipy_stats()
    clean = _clean_group_values(data, group_col, value_col)
    order = list(group_order or control_first_order(clean[group_col]))
    summaries: list[GroupSummary] = []

    for group in order:
        values = clean.loc[clean[group_col] == group, value_col].to_numpy(dtype=float)
        n = int(values.size)
        if n == 0:
            continue

        sd = float(np.std(values, ddof=1)) if n > 1 else float("nan")
        sem = float(sd / math.sqrt(n)) if n > 1 else float("nan")
        normality = _normality(values, stats, alpha)
        summaries.append(
            GroupSummary(
                group=group,
                n=n,
                mean=float(np.mean(values)),
                sd=sd,
                sem=sem,
                median=float(np.median(values)),
                q1=float(np.percentile(values, 25)),
                q3=float(np.percentile(values, 75)),
                normality_test=normality["test"],
                normality_applicable=bool(normality["applicable"]),
                normality_p=float(normality["p"]),
                normality_passed=normality["passed"],
                normality_note=str(normality["note"]),
            )
        )
    return summaries


def compare_groups(
    data: pd.DataFrame,
    *,
    group_col: str = "group",
    value_col: str = "value",
    group_order: Sequence[str] | None = None,
    control_label: str | None = None,
    comparisons: str = "control-vs-all",
    alpha: float = ALPHA,
) -> list[PairwiseComparison]:
    """Run defensible pairwise tests for independent group comparisons."""

    stats = _scipy_stats()
    clean = _clean_group_values(data, group_col, value_col)
    order = list(group_order or control_first_order(clean[group_col], control_label=control_label))
    if len(order) < 2:
        return []

    summaries = {
        summary.group: summary
        for summary in summarize_groups(
            clean,
            group_col=group_col,
            value_col=value_col,
            group_order=order,
            alpha=alpha,
        )
    }

    pairs = _comparison_pairs(order, comparisons)
    raw_results: list[PairwiseComparison] = []
    for group_a, group_b in pairs:
        values_a = clean.loc[clean[group_col] == group_a, value_col].to_numpy(dtype=float)
        values_b = clean.loc[clean[group_col] == group_b, value_col].to_numpy(dtype=float)
        if values_a.size < 2 or values_b.size < 2:
            continue

        result = _choose_and_run_pairwise(
            values_a,
            values_b,
            summaries[group_a],
            summaries[group_b],
            stats,
            alpha,
        )
        raw_results.append(
            PairwiseComparison(
                group_a=group_a,
                group_b=group_b,
                n_a=int(values_a.size),
                n_b=int(values_b.size),
                test=result["test"],
                statistic_name=result["statistic_name"],
                statistic=float(result["statistic"]),
                p_value=float(result["p_value"]),
                p_value_adjusted=float(result["p_value"]),
                p_adjustment="none",
                significance=p_to_mark(float(result["p_value"]), alpha=alpha),
                alpha=alpha,
                normality_a_p=summaries[group_a].normality_p,
                normality_b_p=summaries[group_b].normality_p,
                variance_test=result["variance_test"],
                variance_p=float(result["variance_p"]),
                selection_reason=result["selection_reason"],
            )
        )

    adjusted = _holm_adjust([comparison.p_value for comparison in raw_results])
    adjustment = "Holm" if len(raw_results) > 1 else "none"
    return [
        PairwiseComparison(
            **{
                **asdict(comparison),
                "p_value_adjusted": adjusted_p,
                "p_adjustment": adjustment,
                "significance": p_to_mark(adjusted_p, alpha=alpha),
            }
        )
        for comparison, adjusted_p in zip(raw_results, adjusted)
    ]


def statistical_report_frames(
    data: pd.DataFrame,
    *,
    group_col: str = "group",
    value_col: str = "value",
    group_order: Sequence[str] | None = None,
    control_label: str | None = None,
    comparisons: str = "control-vs-all",
    alpha: float = ALPHA,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return group summaries and pairwise comparisons as data frames."""

    order = list(group_order or control_first_order(data[group_col], control_label=control_label))
    summaries = summarize_groups(
        data,
        group_col=group_col,
        value_col=value_col,
        group_order=order,
        alpha=alpha,
    )
    pairwise = compare_groups(
        data,
        group_col=group_col,
        value_col=value_col,
        group_order=order,
        control_label=control_label,
        comparisons=comparisons,
        alpha=alpha,
    )
    return (
        pd.DataFrame([asdict(summary) for summary in summaries]),
        pd.DataFrame([asdict(comparison) for comparison in pairwise]),
    )


def p_to_mark(p_value: float, *, alpha: float = ALPHA) -> str:
    """Convert a p-value to the conventional star label."""

    if not np.isfinite(p_value):
        return "n/a"
    if p_value < 0.0001:
        return "****"
    if p_value < 0.001:
        return "***"
    if p_value < 0.01:
        return "**"
    if p_value < alpha:
        return "*"
    return "ns"


def _choose_and_run_pairwise(
    values_a: np.ndarray,
    values_b: np.ndarray,
    summary_a: GroupSummary,
    summary_b: GroupSummary,
    stats,
    alpha: float,
) -> dict[str, object]:
    variance_test, variance_p = _levene(values_a, values_b, stats)
    min_n = min(values_a.size, values_b.size)

    if min_n < MIN_PARAMETRIC_GROUP_N:
        permutation = _permutation_pvalue_diff_means(values_a, values_b)
        return {
            "test": "Exact permutation test for difference in means (two-sided)"
            if permutation["mode"] == "exact"
            else "Permutation test for difference in means (two-sided)",
            "statistic_name": "delta_mean",
            "statistic": permutation["observed_difference"],
            "p_value": permutation["p_value"],
            "variance_test": variance_test,
            "variance_p": variance_p,
            "selection_reason": (
                "Very small group size; normality checks were reported but an "
                "assumption-light permutation test was selected."
            ),
        }

    normality_known = (
        summary_a.normality_applicable
        and summary_b.normality_applicable
        and summary_a.normality_passed is not None
        and summary_b.normality_passed is not None
    )
    if normality_known and summary_a.normality_passed and summary_b.normality_passed:
        statistic, p_value = stats.ttest_ind(values_a, values_b, equal_var=False)
        return {
            "test": "Welch's t-test (two-sided)",
            "statistic_name": "t",
            "statistic": statistic,
            "p_value": p_value,
            "variance_test": variance_test,
            "variance_p": variance_p,
            "selection_reason": (
                "Normality was not rejected in either group; Welch's t-test "
                "was selected because it does not require equal variances."
            ),
        }

    statistic, p_value = stats.mannwhitneyu(values_a, values_b, alternative="two-sided")
    return {
        "test": "Mann-Whitney U test (two-sided)",
        "statistic_name": "U",
        "statistic": statistic,
        "p_value": p_value,
        "variance_test": variance_test,
        "variance_p": variance_p,
        "selection_reason": (
            "Normality was rejected or could not be established for parametric "
            "testing at the selected sample size."
        ),
    }


def _normality(values: np.ndarray, stats, alpha: float) -> dict[str, object]:
    values = np.asarray(values, dtype=float)
    n = values.size
    if n < 3:
        return {
            "test": "Shapiro-Wilk",
            "applicable": False,
            "p": float("nan"),
            "passed": None,
            "note": "Not applicable: fewer than 3 observations.",
        }
    if n > 5000:
        return {
            "test": "Shapiro-Wilk",
            "applicable": False,
            "p": float("nan"),
            "passed": None,
            "note": "Not applicable: more than 5000 observations.",
        }
    if np.nanmax(values) == np.nanmin(values):
        return {
            "test": "Shapiro-Wilk",
            "applicable": False,
            "p": float("nan"),
            "passed": None,
            "note": "Not applicable: all observations are identical.",
        }

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        statistic, p_value = stats.shapiro(values)
    return {
        "test": "Shapiro-Wilk",
        "applicable": True,
        "p": float(p_value),
        "passed": bool(p_value >= alpha),
        "note": "Normality not rejected." if p_value >= alpha else "Normality rejected.",
    }


def _levene(values_a: np.ndarray, values_b: np.ndarray, stats) -> tuple[str, float]:
    if values_a.size < 2 or values_b.size < 2:
        return "Levene", float("nan")
    if np.nanmax(values_a) == np.nanmin(values_a) and np.nanmax(values_b) == np.nanmin(values_b):
        return "Levene", float("nan")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        _, p_value = stats.levene(values_a, values_b, center="median")
    p_value = float(p_value)
    if not np.isfinite(p_value):
        return "Levene", float("nan")
    return "Levene", p_value


def _permutation_pvalue_diff_means(
    values_a: np.ndarray,
    values_b: np.ndarray,
    *,
    max_partitions: int = 200_000,
    n_permutations: int = 20_000,
    seed: int = 42,
) -> dict[str, float | int | str]:
    values_a = np.asarray(values_a, dtype=float)
    values_b = np.asarray(values_b, dtype=float)
    observed = float(np.mean(values_b) - np.mean(values_a))
    pooled = np.concatenate([values_a, values_b])
    n_a = int(values_a.size)
    total_n = int(pooled.size)
    partitions = math.comb(total_n, n_a)

    if partitions <= max_partitions:
        count = 0
        indices = np.arange(total_n)
        for selected in itertools.combinations(indices, n_a):
            mask = np.zeros(total_n, dtype=bool)
            mask[list(selected)] = True
            perm_a = pooled[mask]
            perm_b = pooled[~mask]
            statistic = float(np.mean(perm_b) - np.mean(perm_a))
            if abs(statistic) >= abs(observed):
                count += 1
        p_value = float(count / partitions)
        mode = "exact"
    else:
        rng = np.random.default_rng(seed)
        count = 0
        for _ in range(n_permutations):
            order = rng.permutation(total_n)
            perm_a = pooled[order[:n_a]]
            perm_b = pooled[order[n_a:]]
            statistic = float(np.mean(perm_b) - np.mean(perm_a))
            if abs(statistic) >= abs(observed):
                count += 1
        p_value = float((count + 1) / (n_permutations + 1))
        mode = "monte_carlo"

    return {
        "observed_difference": observed,
        "p_value": p_value,
        "partitions": int(partitions),
        "mode": mode,
    }


def _holm_adjust(p_values: Sequence[float]) -> list[float]:
    if not p_values:
        return []

    finite = np.array([float(p) for p in p_values], dtype=float)
    order = np.argsort(finite)
    adjusted = np.full(len(finite), np.nan, dtype=float)
    running_max = 0.0
    total = len(finite)
    for rank, idx in enumerate(order):
        raw = finite[idx]
        value = min(1.0, (total - rank) * raw)
        running_max = max(running_max, value)
        adjusted[idx] = running_max
    return [float(value) for value in adjusted]


def _comparison_pairs(order: Sequence[str], comparisons: str) -> list[tuple[str, str]]:
    if comparisons == "control-vs-all":
        control = order[0]
        return [(control, group) for group in order[1:]]
    if comparisons == "all-pairs":
        return list(itertools.combinations(order, 2))
    raise ValueError("comparisons must be 'control-vs-all' or 'all-pairs'.")


def _find_control_group(groups: Sequence[str], control_label: str | None) -> str | None:
    if control_label:
        for group in groups:
            if group.casefold() == control_label.casefold():
                return group

    for group in groups:
        normalized = group.casefold()
        if any(hint in normalized for hint in CONTROL_HINTS):
            return group
    return None


def _clean_group_values(data: pd.DataFrame, group_col: str, value_col: str) -> pd.DataFrame:
    if group_col not in data.columns:
        raise ValueError(f"Missing required group column: {group_col}")
    if value_col not in data.columns:
        raise ValueError(f"Missing required value column: {value_col}")
    clean = data[[group_col, value_col]].copy()
    clean[group_col] = clean[group_col].astype(str)
    clean[value_col] = pd.to_numeric(clean[value_col], errors="coerce")
    clean = clean.dropna(subset=[group_col, value_col])
    if clean.empty:
        raise ValueError("No numeric group values are available for statistics.")
    return clean


def _scipy_stats():
    try:
        from scipy import stats
    except Exception as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "The group_bar_stat plot requires scipy for normality and "
            "statistical testing. Install scipy before rendering this plot."
        ) from exc
    return stats
