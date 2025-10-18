#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced plotting pipeline with polished styling + normality-aware stats.
(Это моя униформальная функция для создания граффиков из таблиц полученных этим приложением)
"""

import os
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib as mpl
import matplotlib.pyplot as plt
from scipy import stats
import textwrap
import re
from typing import Iterable, Mapping

def add_mapped_column_next_to(
    df: pd.DataFrame,
    source_col: str,
    new_col: str,
    a_from,
    a_to,
    b_from,
    b_to,
    *,
    case_insensitive: bool = True,
    substring: bool = False,          # <- НОВОЕ: искать подстроку вместо точного равенства
    overwrite: bool = True,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Создаёт рядом с `source_col` колонку `new_col` и заполняет её по правилам:
      режим exact (substring=False):
        - value == a_from -> a_to
        - value == b_from -> b_to
      режим substring=True:
        - если a_from встречается как подстрока -> a_to
        - иначе, если b_from встречается как подстрока -> b_to
        - иначе NaN

    Примечания:
      - case_insensitive=True: сравнение/поиск ведётся без учёта регистра (через .casefold()).
      - при substring=True: при одновременном совпадении с a_from и b_from приоритет у a_from.
      - overwrite: если new_col уже есть — перезаписать (True) или бросить ошибку (False).
    """
    if source_col not in df.columns:
        raise ValueError(f"Колонка '{source_col}' не найдена в датафрейме.")

    out = df if inplace else df.copy()

    if new_col in out.columns:
        if overwrite:
            del out[new_col]
        else:
            raise ValueError(f"Колонка '{new_col}' уже существует. Укажи overwrite=True, чтобы перезаписать.")

    # куда вставлять новую колонку — сразу после source_col
    insert_at = out.columns.get_loc(source_col)

    # подготовим серию для сравнения
    s = out[source_col]
    s_str = s.astype(str).str.strip()              # str-представление; NaN -> 'nan', ок для contains(False)
    if case_insensitive:
        s_cmp = s_str.str.casefold()
        a_key = str(a_from).casefold()
        b_key = str(b_from).casefold()
    else:
        s_cmp = s_str
        a_key = str(a_from)
        b_key = str(b_from)

    new_series = pd.Series(pd.NA, index=out.index, dtype="object")

    if not substring:
        # точное равенство
        mapped = s_cmp.map({a_key: a_to, b_key: b_to})
        new_series.loc[:] = mapped
    else:
        # поиск подстроки (буквально, без regex-метасимволов)
        idx_a = s_cmp.str.contains(a_key, na=False, regex=False)
        new_series.loc[idx_a] = a_to

        idx_b = s_cmp.str.contains(b_key, na=False, regex=False) & new_series.isna()
        new_series.loc[idx_b] = b_to
        # всё остальное остаётся NaN

    out.insert(insert_at + 1, new_col, new_series)
    return out


def filter_rows(
    df: pd.DataFrame,
    specs: Iterable[Mapping[str, object]],
    file_col: str,
    cut_col: str = "Cut",
    case_sensitive: bool = False,
) -> pd.DataFrame:
    """
    Return only rows where, for at least one spec:
        (file_col contains spec['file_contains']) AND (cut_col in spec['cuts'])

    specs example:
        [{"file_contains": "Potkan1", "cuts": ["cut3","cut4","cut6"]}, ...]

    Parameters
    ----------
    df : DataFrame
    specs : iterable of dicts with keys 'file_contains' (str) and 'cuts' (list/iterable of str)
    file_col : name of the file column (default "File")
    cut_col : name of the cut column (default "Cut")
    case_sensitive : match case in file_contains and cuts (default False)

    Returns
    -------
    DataFrame filtered by the union of all spec conditions.
    """
    if file_col not in df.columns:
        raise KeyError(f"Column '{file_col}' not found in dataframe")
    if cut_col not in df.columns:
        raise KeyError(f"Column '{cut_col}' not found in dataframe")

    ser_file = df[file_col].astype(str)
    ser_cut  = df[cut_col].astype(str)

    if not case_sensitive:
        ser_file = ser_file.str.lower()
        ser_cut  = ser_cut.str.lower()

    keep_mask = pd.Series(False, index=df.index)

    for spec in specs:
        fc = str(spec["file_contains"])
        cuts = list(spec["cuts"])

        if not case_sensitive:
            fc = fc.lower()
            cuts = [str(c).lower() for c in cuts]

        m = ser_file.str.contains(fc, na=False) & ser_cut.isin(cuts)
        keep_mask |= m

    return df.loc[keep_mask].copy()



# ========= Config (edit these) =========
BASE_PATH = "/Volumes/T7_Shield/Savva_SpinningDisk/HABP_CS56_CD44"
CSV_NAME = "HABP_CS56_CD44_PredMoz_AllSlise_Summary_Measurements_All_NOT_FINAL.csv"
CSV_PATH   = os.path.join(BASE_PATH, CSV_NAME)
BASE_OUT_DIR    = os.path.join(BASE_PATH, "Plots_Seaborn_2")

VALUE_COL   = "Mean"
CHANNEL_COL = "Channel"
SAMPLE_COL  = "Group"
AREA_COL    = "Area"
LR_COL      = "L/R"
UNIT        = "Arbitrary Units"
FILE_NAME_COL = "Sumple"

GROUP_A = "Control"
GROUP_B = "4MU"
COMPARE_GROUPS = [GROUP_A, GROUP_B]

# ========= Central naming for plots/files =========
PLOT_TITLE_PREFIX = "Iba ROI – Overview"
PLOT_TITLE_SUFFIX = ""  # e.g., "(Cerebellum)"

CHANNEL_NAME_MAP = {
    1: "CS56",
    2: "CD44",
    3: "HABP",
}




FILE_PREFIX = "sc_full_overview"
FILE_SUFFIX = ""  # e.g., "_pilot"
IMG_DPI     = 300

BOX_WIDTH     = 0.45   # было 0.5
BAR_WIDTH     = 0.45   # было 0.42
POINT_SIZE    = 4.0    # было 4.5
POINT_JITTER  = 0.12   # было 0.18
ERR_CAPSIZE   = 0.15   # было 0.2
ERR_WIDTH     = 1.2    # было 1.4

OUT_DIR = os.path.join(BASE_OUT_DIR, FILE_PREFIX)
os.makedirs(OUT_DIR, exist_ok=True)

# ========= Filtering =========
specs = [
    {"file_contains": "Potkan1", "cuts": ["cut3","cut4","cut7"]},
    {"file_contains": "Potkan2", "cuts": ["cut1","cut4","cut5"]},
    {"file_contains": "Potkan3", "cuts": ["cut3","cut5","cut6"]},
    {"file_contains": "Potkan4", "cuts": ["cut5","cut6","cut7"]},
    {"file_contains": "DIRECTaav1-1", "cuts": ["cut2","cut3","cut7"]},
    {"file_contains": "DIRECTaav1-2", "cuts": ["cut1","cut3","cut7"]},
    {"file_contains": "DIRECTaav9-1", "cuts": ["cut1","cut3","cut5"]},
    {"file_contains": "DIRECTaav9-2", "cuts": ["cut3","cut5","cut7"]},
]

'''
reca
specs = [
    {"file_contains": "Potkan1", "cuts": ["cut3","cut4","cut7"]},
    {"file_contains": "Potkan2", "cuts": ["cut1","cut4","cut5"]},
    {"file_contains": "Potkan3", "cuts": ["cut3","cut5","cut6"]},
    {"file_contains": "Potkan4", "cuts": ["cut5","cut6","cut7"]},
    {"file_contains": "DIRECTaav1-1", "cuts": ["cut2","cut3","cut7"]},
    {"file_contains": "DIRECTaav1-2", "cuts": ["cut1","cut3","cut7"]},
    {"file_contains": "DIRECTaav9-1", "cuts": ["cut1","cut3","cut5"]},
    {"file_contains": "DIRECTaav9-2", "cuts": ["cut3","cut5","cut7"]},
]

CHANNEL_NAME_MAP = {
    1: "GFAP",
    2: "RECA1",
    3: "S100A10",
}

'''

'''
mbp
specs = [
    {"file_contains": "Potkan1", "cuts": ["cut1","cut3","cut7"]},
    {"file_contains": "Potkan2", "cuts": ["cut2","cut4","cut5"]},
    {"file_contains": "Potkan3", "cuts": ["cut3","cut5","cut6"]},
    {"file_contains": "Potkan4", "cuts": ["cut5","cut6","cut7"]},
    {"file_contains": "DIRECTaav1-1", "cuts": ["cut2","cut3","cut7"]},
    {"file_contains": "DIRECTaav1-2", "cuts": ["cut1","cut3","cut7"]},
    {"file_contains": "DIRECTaav9-1", "cuts": ["cut1","cut3","cut7"]},
    {"file_contains": "DIRECTaav9-2", "cuts": ["cut3","cut5","cut7"]},
]

CHANNEL_NAME_MAP = {
    1: "DAPI",
    2: "MAG",
    3: "Olig2",
    4: "MBP",
}
'''


'''
HABP


CHANNEL_NAME_MAP = {
    1: "CS56",
    2: "CD44",
    3: "HABP",
}

'''

def filter_by_lr(df: pd.DataFrame, lr_col: str = "L/R") -> tuple[pd.DataFrame, pd.DataFrame]:
    if lr_col not in df.columns:
        raise ValueError(f"Column '{lr_col}' not found in dataframe")
    left_df = df[df[lr_col] == 'L'].copy()
    right_df = df[df[lr_col] == 'R'].copy()
    return left_df, right_df

# ========= Styling =========
TITLE_PAD = 50  # used for consistent title padding

mpl.rcParams.update({
    "figure.dpi": 110,
    "savefig.dpi": IMG_DPI,
    "figure.facecolor": "white",
    "axes.facecolor": "#fcfcfd",
    "axes.edgecolor": "#e5e7eb",
    "axes.linewidth": 1.0,
    "axes.grid": True,
    "grid.color": "#e5e7eb",
    "grid.linestyle": "-",
    "grid.linewidth": 0.8,
    "axes.titleweight": "semibold",
    "axes.titlesize": 16,
    "axes.labelsize": 14,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
    "legend.frameon": False,
    "figure.constrained_layout.use": True,
})

sns.set_theme(context="talk", style="whitegrid", font_scale=1.0)
PALETTE = sns.color_palette("Set2")
POINT_EDGE = dict(edgecolor="black", linewidth=0.6)

# === моя палитра для публикаций (мягкая, color-blind-safe) ===
PLOT_COLORS = {
    GROUP_A: "#F4A300",  # bluish green
    GROUP_B: "#2EC4B6",  # reddish purple
}
BOX_ALPHA = 0.35
BAR_WIDTH = 0.42
AX_EDGE = "#2b2b2b"
GRID_COLOR = "#e5e7eb"

# ========= Helpers =========

def ensure_cut_from_filename(
    df: pd.DataFrame,
    file_col: str = FILE_NAME_COL,   # например "File"
    cut_col: str = "Cut",
    inplace: bool = False
) -> pd.DataFrame:
    """
    Гарантирует наличие колонки `Cut`.
    Если её нет — парсит из `file_col` шаблоном (case-insensitive):
        (^|[_\\W-])cut\\s*\\d+([_\\W-]|$)
    Нормализует к форме 'cut<номер>' (lowercase, без пробелов).
    """
    if cut_col in df.columns:
        return df if inplace else df.copy()

    if file_col not in df.columns:
        raise KeyError(f"Колонка '{file_col}' не найдена, неоткуда извлечь Cut.")

    target = df if inplace else df.copy()

    # извлечь 'cut<digits>' с любыми разделителями/регистром (например: _cut1_, -CUT-2-, 'cut 3')
    extracted = (
        target[file_col].astype(str)
        .str.extract(r'(?:^|[_\W-])(cut\s*\d+)(?:[_\W-]|$)', flags=re.IGNORECASE, expand=True)
        .iloc[:, 0]
        .str.replace(r'\s+', '', regex=True)   # 'cut 1' -> 'cut1'
        .str.lower()
    )

    target[cut_col] = extracted  # где не нашли — будет NaN (это ок для groupby(dropna=False))

    return target


def set_y0_and_room(ax, series, frac=0.12):
    vals = pd.Series(series).dropna()
    if vals.empty:
        ax.set_ylim(0, 1)
        return 1.0
    ymax = float(vals.max())
    if not np.isfinite(ymax): 
        ymax = 1.0
    if ymax <= 0:
        ax.set_ylim(0, 1.0)
        return 1.0
    pad = max(ymax * frac, 1e-9)
    top = ymax + pad
    ax.set_ylim(0, top)
    return top

def extract_subject_token(file_val: str, subject_hint: str):
    if not isinstance(file_val, str) or not isinstance(subject_hint, str):
        return None
    tokens = re.findall(r"(?<=_)[^_]+(?=_)", "_" + file_val + "_")
    sh = subject_hint.casefold()
    for token in tokens:
        if token.casefold().startswith(sh):
            return token
    return None

def ensure_channel_renamed(df: pd.DataFrame) -> pd.DataFrame:
    """
    Если в таблице есть безымянная колонка ' ' (в ней настоящие номера каналов 1/2/3)
    и одновременно существует колонка CHANNEL_COL (обычно 'Channel'),
    то:
      1) удаляем существующую колонку CHANNEL_COL,
      2) переименовываем ' ' -> CHANNEL_COL.
    Иначе, если есть только ' ', просто переименовываем её.
    В остальных случаях — возвращаем как есть.
    """
    out = df.copy()
    if " " in out.columns:
        if CHANNEL_COL in out.columns and CHANNEL_COL != " ":
            out = out.drop(columns=[CHANNEL_COL])
        out = out.rename(columns={" ": CHANNEL_COL})
    return out

def ensure_channel_from_blank(df: pd.DataFrame, channel_col="Channel") -> pd.DataFrame:
    df = df.copy()
    cols = list(df.columns)
    if "ROI" in cols and "Area" in cols:
        i_roi, i_area = cols.index("ROI"), cols.index("Area")
        if i_area == i_roi + 2:
            mid = cols[i_roi + 1]
            if str(mid).strip() in ("", " "):
                return df.rename(columns={mid: channel_col})
    for blank in ("", " "):
        if blank in df.columns and channel_col not in df.columns:
            return df.rename(columns={blank: channel_col})
    return df

def build_subject_token(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["SubjectToken"] = [
        extract_subject_token(f, s) for f, s in zip(df.get(FILE_NAME_COL), df.get("Subject"))
    ]
    return df

def _coerce_numeric(df: pd.DataFrame, cols=("Mean","Area","Min","Max")) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def aggregate_with_lr(df: pd.DataFrame,
                      sample_col="Group", channel_col="Channel", lr_col="L/R",
                      num_cols=("Mean","Area","Min","Max")) -> pd.DataFrame:
    df = _coerce_numeric(build_subject_token(ensure_channel_from_blank(df, channel_col)))
    base_keys = ["SubjectToken"]
    if sample_col in df.columns:  base_keys.append(sample_col)
    if channel_col in df.columns: base_keys.append(channel_col)
    if "Cut" in df.columns:       base_keys.append("Cut")
    side_keys = base_keys + [lr_col]
    side_means = (df.groupby(side_keys, dropna=False)[list(num_cols)]
                    .mean().reset_index())
    cut_keys = base_keys
    cut_means = (side_means.groupby(cut_keys, dropna=False)[list(num_cols)]
                           .mean().reset_index())
    subj_keys = ["SubjectToken"]
    if sample_col in df.columns:  subj_keys.append(sample_col)
    if channel_col in df.columns: subj_keys.append(channel_col)
    final = (cut_means.groupby(subj_keys, dropna=False)[list(num_cols)]
                      .mean().reset_index())
    return final

def aggregate_without_lr(df: pd.DataFrame,
                        sample_col="Group", channel_col="Channel",
                        num_cols=("Mean","Area","Min","Max")) -> pd.DataFrame:
    df = _coerce_numeric(build_subject_token(ensure_channel_from_blank(df, channel_col)))
    df = normalize_lr(df, LR_COL)
    base_keys = ["SubjectToken"]
    if sample_col in df.columns:  base_keys.append(sample_col)
    if channel_col in df.columns: base_keys.append(channel_col)
    if "Cut" in df.columns:       base_keys.append("Cut")
    cut_means = (df.groupby(base_keys, dropna=False)[list(num_cols)]
                   .mean().reset_index())
    subj_keys = ["SubjectToken"]
    if sample_col in df.columns:  subj_keys.append(sample_col)
    if channel_col in df.columns: subj_keys.append(channel_col)
    final = (cut_means.groupby(subj_keys, dropna=False)[list(num_cols)]
                      .mean().reset_index())
    return final

def normalize_lr(df: pd.DataFrame, lr_col="L/R") -> pd.DataFrame:
    if lr_col in df.columns:
        df = df.copy()
        df[lr_col] = df[lr_col].astype(str).str.strip().str.upper()
    return df

def aggregate_bilateral_then_cuts(df: pd.DataFrame) -> pd.DataFrame:
    if "L/R" in df.columns:
        return aggregate_with_lr(df, sample_col=SAMPLE_COL, channel_col=CHANNEL_COL, lr_col=LR_COL)
    else:
        return aggregate_without_lr(df, sample_col=SAMPLE_COL, channel_col=CHANNEL_COL)

def add_treatment_col(df: pd.DataFrame, sample_col=SAMPLE_COL) -> pd.DataFrame:
    df = df.copy()
    A = GROUP_A.casefold()
    B = GROUP_B.casefold()
    def _map(x):
        s = str(x).casefold()
        if A in s: return GROUP_A
        if B in s: return GROUP_B
        return None
    df["Treatment"] = df[sample_col].apply(_map)
    return df

def set_wrapped_title(ax, title: str, width: int = 60, pad: int = TITLE_PAD):
    ax.set_title(textwrap.fill(str(title), width=width), pad=pad)

# ---------- Stats helpers ----------
def shapiro_safe(x: np.ndarray):
    x = np.asarray(x)
    x = x[np.isfinite(x)]
    if x.size < 3:
        return np.nan, np.nan
    n = min(x.size, 5000)
    stat, p = stats.shapiro(x[:n])
    return float(stat), float(p)

def welch_t(g1: np.ndarray, g2: np.ndarray):
    stat, p = stats.ttest_ind(g1, g2, equal_var=False, nan_policy="omit")
    return float(stat), float(p)

def mannwhitney(g1: np.ndarray, g2: np.ndarray):
    stat, p = stats.mannwhitneyu(g1, g2, alternative="two-sided")
    return float(stat), float(p)

def cohens_d(g1: np.ndarray, g2: np.ndarray):
    g1 = np.asarray(g1); g2 = np.asarray(g2)
    m1, m2 = np.nanmean(g1), np.nanmean(g2)
    s1, s2 = np.nanstd(g1, ddof=1), np.nanstd(g2, ddof=1)
    n1, n2 = np.sum(np.isfinite(g1)), np.sum(np.isfinite(g2))
    sp = np.sqrt(((n1-1)*s1**2 + (n2-1)*s2**2) / (n1 + n2 - 2)) if (n1+n2-2) > 0 else np.nan
    d = (m1 - m2) / sp if sp > 0 else np.nan
    if np.isfinite(d) and (n1 + n2) > 2:
        J = 1 - (3 / (4*(n1+n2) - 9))
        d = d * J
    return float(d)

def cliffs_delta(g1: np.ndarray, g2: np.ndarray):
    g1 = np.asarray(g1); g2 = np.asarray(g2)
    g1 = g1[np.isfinite(g1)]; g2 = g2[np.isfinite(g2)]
    if g1.size == 0 or g2.size == 0:
        return np.nan
    count = 0
    for a in g1:
        count += np.sum(a > g2) - np.sum(a < g2)
    delta = count / (g1.size * g2.size)
    return float(delta)

def p_to_stars(p):
    if not np.isfinite(p):
        return "n.s."
    return "****" if p < 1e-4 else "***" if p < 1e-3 else "**" if p < 1e-2 else "*" if p < 0.05 else "n.s."

def choose_test(g1: np.ndarray, g2: np.ndarray):
    g1 = np.asarray(g1); g2 = np.asarray(g2)
    g1 = g1[np.isfinite(g1)]; g2 = g2[np.isfinite(g2)]
    sh1, p1 = shapiro_safe(g1)
    sh2, p2 = shapiro_safe(g2)
    normal1 = np.isfinite(p1) and p1 >= 0.05
    normal2 = np.isfinite(p2) and p2 >= 0.05

    if normal1 and normal2 and g1.size >= 3 and g2.size >= 3:
        stat, p = welch_t(g1, g2)
        effect = cohens_d(g1, g2)
        return {
            "normality": {"p1": p1, "p2": p2},
            "test_name": "Welch t-test",
            "stat": stat,
            "p": p,
            "effect_name": "Hedges' g (≈Cohen's d)",
            "effect": effect,
        }
    else:
        stat, p = mannwhitney(g1, g2)
        effect = cliffs_delta(g1, g2)
        return {
            "normality": {"p1": p1, "p2": p2},
            "test_name": "Mann–Whitney U",
            "stat": stat,
            "p": p,
            "effect_name": "Cliff's Δ",
            "effect": effect,
        }

# ========= Title / filename helpers =========
def _make_title(plot_kind: str, channel: str, extra: str = "") -> str:
    channel_label = CHANNEL_NAME_MAP.get(channel, str(channel))
    parts = [PLOT_TITLE_PREFIX, plot_kind, f"{GROUP_A} vs {GROUP_B}", f"– {channel_label}"]
    if PLOT_TITLE_SUFFIX: parts.append(PLOT_TITLE_SUFFIX)
    if extra: parts.append(extra)
    return " — ".join([p for p in parts if p])

def make_title(plot_kind: str, channel: str, extra: str = "") -> str:
    channel_label = CHANNEL_NAME_MAP.get(channel, str(channel))
    parts = [f"{channel_label}"]
    if PLOT_TITLE_SUFFIX: parts.append(PLOT_TITLE_SUFFIX)
    if extra: parts.append(extra)
    return " — ".join([p for p in parts if p])

def make_fname(channel: str, stem: str) -> str:
    def _san(s):
        s = str(s)
        return "".join(ch if ch.isalnum() or ch in ("-", ".", "_") else "_" for ch in s)
    channel_label = CHANNEL_NAME_MAP.get(channel, str(channel))
    bits = [_san(FILE_PREFIX), _san(channel_label), _san(stem)]
    if FILE_SUFFIX:
        bits.append(_san(FILE_SUFFIX))
    return "_".join([b for b in bits if b]) + ".png"

# ========= ПЕРЕРАБОТАННЫЕ ФУНКЦИИ ПЛОТОВ =========
def boxplot_two_groups_signif(df: pd.DataFrame, channel="C1", value_col=VALUE_COL, unit=UNIT, save_path=None, summary_rows=None):
    """
    Боксплот с полупрозрачной заливкой в мягких цветах (Control=#009E73, 4MU=#CC79A7) + точки.
    """
    sub = df[df[CHANNEL_COL] == channel]
    if sub.empty:
        print(f"[skip] No data for channel {channel} (boxplot)")
        return summary_rows

    sub = add_treatment_col(sub)
    sub = sub[sub["Treatment"].isin(COMPARE_GROUPS)].copy()
    if sub.empty:
        plt.figure(figsize=(6, 3))
        plt.text(0.5, 0.5, f"No data for {COMPARE_GROUPS} in channel {channel}", ha="center", va="center")
        plt.axis("off")
        if save_path:
            plt.savefig(save_path, dpi=IMG_DPI, bbox_inches="tight", pad_inches=0.02); plt.close()
            print(f"Saved: {save_path} (empty groups)")
        return summary_rows

    present_groups = [g for g in COMPARE_GROUPS if g in sub["Treatment"].unique()]
    order = present_groups if present_groups else COMPARE_GROUPS
    pal = {g: PLOT_COLORS.get(g, "#777777") for g in order}

    plt.figure(figsize=(7.5, 6.5))
    ax = sns.boxplot(
        data=sub, x="Treatment", y=value_col, order=order,
        showcaps=True, showfliers=False, width=BOX_WIDTH,   # <- уже
        palette=pal,
        linewidth=1.2,
        boxprops={"edgecolor": AX_EDGE},
        medianprops={"color": AX_EDGE, "linewidth": 1.8},
        whiskerprops={"color": AX_EDGE, "linewidth": 1.2},
        capprops={"color": AX_EDGE, "linewidth": 1.2},
    )

    sns.stripplot(
        data=sub, x="Treatment", y=value_col, order=order,
        palette=pal, size=POINT_SIZE, jitter=POINT_JITTER,  # <- уже
        alpha=0.9, marker='o', **POINT_EDGE
    )
    # сделать коробки полупрозрачными
    for i, art in enumerate(ax.artists):
        g = order[i]
        art.set_facecolor(pal[g])
        art.set_alpha(BOX_ALPHA)
        art.set_edgecolor(AX_EDGE)

    set_wrapped_title(ax, make_title("Boxplot", channel))
    ax.set_ylabel(f"{value_col} ({unit})")
    ax.set_xlabel("")
    # сетка только по Y
    ax.grid(True, axis="y", color=GRID_COLOR, linewidth=0.8)
    ax.grid(False, axis="x")
    ax.tick_params(axis="both", length=3, width=1, colors=AX_EDGE)
    sns.despine(top=True, right=True)

    # разумные лимиты
    set_y0_and_room(ax, sub[value_col])

    # значимость
    if len(present_groups) == 2:
        g1 = sub.loc[sub["Treatment"] == present_groups[0], value_col].dropna().values
        g2 = sub.loc[sub["Treatment"] == present_groups[1], value_col].dropna().values
        res = choose_test(g1, g2)
        stars = p_to_stars(res["p"])
        ptxt = f"p = {res['p']:.2e}" if res["p"] < 1e-3 else f"p = {res['p']:.3f}"

        y0, y1 = ax.get_ylim()
        y_bar = y1 - (y1 - y0) * 0.06
        ax.plot([0, 1], [y_bar, y_bar], c=AX_EDGE, lw=1.3)
        ax.text(
            0.5, y_bar + (y1 - y0) * 0.01,
            f"{ptxt}  {stars}\n{res['effect_name']}: {res['effect']:.3g}",
            ha="center", va="bottom", fontsize=11,
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#cccccc", linewidth=0.6)
        )

        if summary_rows is not None:
            summary_rows.append({
                "Channel": channel,
                "Plot": "boxplot",
                "GroupA": present_groups[0],
                "GroupB": present_groups[1],
                "nA": int(np.isfinite(g1).sum()),
                "nB": int(np.isfinite(g2).sum()),
                "Shapiro_p_A": res["normality"]["p1"],
                "Shapiro_p_B": res["normality"]["p2"],
                "Test": res["test_name"],
                "Stat": res["stat"],
                "pval": res["p"],
                "Effect_name": res["effect_name"],
                "Effect": res["effect"],
            })
    else:
        ax.text(0.5, ax.get_ylim()[1], "Only one group present", ha="center", va="bottom")

    if save_path:
        plt.savefig(save_path, dpi=IMG_DPI, bbox_inches="tight", pad_inches=0.02)
        plt.close()
        print(f"Saved: {save_path}")
    else:
        plt.show()
    return summary_rows

def barplot_two_groups_signif(df: pd.DataFrame, channel="C1",
                              value_col=VALUE_COL, unit=UNIT,
                              save_path=None, summary_rows=None):
    """
    Барплот с более тонкими столбцами и точками-маркерами (●) поверх; контролируемые цвета.
    """
    sub = df[df[CHANNEL_COL] == channel].copy()
    if sub.empty:
        print(f"[skip] No data for channel {channel} (barplot)")
        return summary_rows

    present = [g for g in COMPARE_GROUPS if g in sub[SAMPLE_COL].unique()]
    if not present:
        print(f"[skip] No {COMPARE_GROUPS} in channel {channel} (barplot)")
        return summary_rows
    order = present
    pal = {g: PLOT_COLORS.get(g, "#777777") for g in order}

    plt.figure(figsize=(7.5, 6.0))
    try:
        ax = sns.barplot(
            data=sub, x=SAMPLE_COL, y=value_col, order=order,
            width=BAR_WIDTH,                                     # <- уже
            palette=pal, edgecolor=AX_EDGE, linewidth=1.2,
            errorbar=("ci", 95), errwidth=ERR_WIDTH, capsize=ERR_CAPSIZE, errcolor=AX_EDGE
        )
    except TypeError:
        ax = sns.barplot(
            data=sub, x=SAMPLE_COL, y=value_col, order=order,
            width=BAR_WIDTH,                                     # <- уже
            palette=pal, edgecolor=AX_EDGE, linewidth=1.2,
            ci=95, errwidth=ERR_WIDTH, capsize=ERR_CAPSIZE
        )

    sns.stripplot(
        data=sub, x=SAMPLE_COL, y=value_col, order=order,
        palette=pal, alpha=0.9, jitter=POINT_JITTER,            # <- уже
        size=POINT_SIZE, marker='o', **POINT_EDGE
    )

    set_wrapped_title(ax, make_title("Barplot", channel))
    ax.set_xlabel("")
    ax.set_ylabel(f"{value_col} ({unit})")
    ax.grid(True, axis="y", color=GRID_COLOR, linewidth=0.8)
    ax.grid(False, axis="x")
    ax.tick_params(axis="both", length=3, width=1, colors=AX_EDGE)
    sns.despine(top=True, right=True)

    set_y0_and_room(ax, sub[value_col])

    if len(order) == 2:
        g1 = sub.loc[sub[SAMPLE_COL] == order[0], value_col].dropna().values
        g2 = sub.loc[sub[SAMPLE_COL] == order[1], value_col].dropna().values
        res = choose_test(g1, g2)
        stars = p_to_stars(res["p"])
        ptxt = f"p = {res['p']:.2e}" if res["p"] < 1e-3 else f"p = {res['p']:.3f}"

        y0, y1 = ax.get_ylim()
        y_bar = y1 - (y1 - y0) * 0.06
        ax.plot([0, 1], [y_bar, y_bar], c=AX_EDGE, lw=1.3)
        ax.text(
            0.5, y_bar + (y1 - y0) * 0.01,
            f"{ptxt}  {stars}\n{res['effect_name']}: {res['effect']:.3g}",
            ha="center", va="bottom", fontsize=11,
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#cccccc", linewidth=0.6)
        )

        if summary_rows is not None:
            summary_rows.append({
                "Channel": channel,
                "Plot": "barplot",
                "GroupA": order[0],
                "GroupB": order[1],
                "nA": int(np.isfinite(g1).sum()),
                "nB": int(np.isfinite(g2).sum()),
                "Shapiro_p_A": res["normality"]["p1"],
                "Shapiro_p_B": res["normality"]["p2"],
                "Test": res["test_name"],
                "Stat": res["stat"],
                "pval": res["p"],
                "Effect_name": res["effect_name"],
                "Effect": res["effect"],
            })
    else:
        ax.text(0.5, ax.get_ylim()[1], "Only one group present", ha="center", va="bottom")

    if save_path:
        plt.savefig(save_path, dpi=IMG_DPI, bbox_inches="tight", pad_inches=0.02)
        plt.close()
        print(f"Saved: {save_path}")
    else:
        plt.show()

    return summary_rows

# ========= FD binning =========
def freedman_diaconis_bins(x: np.ndarray):
    x = np.asarray(x)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return 10, None, None
    q75, q25 = np.percentile(x, [75, 25])
    iqr = q75 - q25
    if iqr == 0:
        return 10, x.min(), x.max()
    h = 2 * iqr * (len(x) ** (-1/3))
    x_min, x_max = x.min(), x.max()
    n_bins = int(np.ceil((x_max - x_min) / h)) if h > 0 else 10
    return max(n_bins, 5), x_min, x_max

def replace_mean_with_document_sum(df: pd.DataFrame, doc_col: str = "document_name", mean_col: str = "Mean", inplace: bool = False) -> pd.DataFrame:
    if doc_col not in df.columns:
        raise KeyError(f"Колонка '{doc_col}' не найдена.")
    if mean_col not in df.columns:
        raise KeyError(f"Колонка '{mean_col}' не найдена.")
    target = df if inplace else df.copy()
    target[mean_col] = pd.to_numeric(target[mean_col], errors="coerce")
    target[mean_col] = (
        target.groupby(doc_col, dropna=False)[mean_col]
              .transform(lambda s: s.sum(min_count=1))
    )
    return target

# ========= Main =========
def main():
    df = pd.read_csv(CSV_PATH)
    df = add_mapped_column_next_to(df, FILE_NAME_COL, SAMPLE_COL,
                               a_from="potkan", a_to="4MU",
                               b_from="DIRECT", b_to="Control",
                               case_insensitive=True, substring=True)
    df = add_mapped_column_next_to(df=df, 
        source_col = SAMPLE_COL, 
        new_col = 'Subject', 
        a_from = GROUP_B,
        a_to = 'Potkan',
        b_from = GROUP_A,
        b_to = 'DIRECT')           # при необходимости
    df = ensure_channel_renamed(df)
    df = ensure_cut_from_filename(df, file_col=FILE_NAME_COL)              # при необходимости
    # df = replace_mean_with_document_sum(df)         # при необходимости
    # df = filter_rows(df, specs, file_col=FILE_NAME_COL)   
    df = aggregate_bilateral_then_cuts(df)
    mena_df_path = os.path.join(OUT_DIR, f"{FILE_PREFIX}_mena_table{FILE_SUFFIX if FILE_SUFFIX else ''}.csv")
    df.to_csv(mena_df_path, index=False)

    channels = df[CHANNEL_COL].dropna().unique()
    if len(channels) == 0:
        print("No channels found.")
        return

    summary_rows = []

    for ch in channels:
        summary_rows = boxplot_two_groups_signif(
            df, channel=ch,
            save_path=os.path.join(OUT_DIR, make_fname(ch, "boxplot")),
            summary_rows=summary_rows
        )

        summary_rows = barplot_two_groups_signif(
            df, channel=ch,
            save_path=os.path.join(OUT_DIR, make_fname(ch, "barplot")),
            summary_rows=summary_rows
        )

    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)
        summary_path = os.path.join(OUT_DIR, f"{FILE_PREFIX}_stats_summary{FILE_SUFFIX if FILE_SUFFIX else ''}.csv")
        summary_df.to_csv(summary_path, index=False)
        print(f"Saved stats summary: {summary_path}")

    print(f"Saved plots to: {OUT_DIR}")

if __name__ == "__main__":
    main()
