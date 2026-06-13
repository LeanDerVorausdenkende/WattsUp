"""
Build the canonical 15-min feature table used by all models.

Reads
-----
- data/raw/Zeitreihen_WKA_2025_2026.xlsx        — power production (target)
- data/raw/Zeitreihen_Wetterprognosen_2025_2026.xlsx — weather forecasts
- data/raw/water_data/Q_Rothenstein_15min.csv   — discharge 15-min (optional, available from ~2025-06-12 only)

Writes
------
- data/preprocessed/train.parquet

Output columns
--------------
Targets:
    Unterpreilipp_kW, Burgau_kW

Lag features (anti-leakage: all computed from past values only):
    lag_1_U, lag_4_U, lag_96_U        — Unterpreilipp lags
    lag_1_B, lag_4_B, lag_96_B        — Burgau lags

Weather (forecast values — no leakage):
    solar_W_m2, temp_C, wind_ms, wind_dir_deg

Discharge:
    Q_m3s                              — NaN where 15-min data unavailable

Calendar:
    hour, minute, weekday, month, season

Flags:
    Unterpreilipp_offline, Burgau_offline  — 1 when production == 0

Notes
-----
- All timestamps are UTC.
- Raw Excel timestamps are UTC+1 fixed offset (Lokale Zeit: Nein).
  Fix: subtract 1 h then tz_localize('UTC'). Never use Europe/Berlin here.
- Lag features are built AFTER merging to avoid cross-source boundary leakage.
- Run from the project root: python src/data/preprocess.py
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd


# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[2]
RAW  = ROOT / "data" / "raw"
OUT  = ROOT / "data" / "preprocessed"

WKA_PATH  = RAW / "Zeitreihen_WKA_2025_2026.xlsx"
WX_PATH   = RAW / "Zeitreihen_Wetterprognosen_2025_2026.xlsx"
Q15_PATH  = RAW / "water_data" / "Q_Rothenstein_15min.csv"
OUT_PATH  = OUT / "train.parquet"


# ── Loaders ───────────────────────────────────────────────────────────────────

def _to_utc(series: pd.Series) -> pd.Series:
    """Convert a UTC+1 fixed-offset series (no DST) to UTC.

    Parameters
    ----------
    series : pd.Series
        String or object column of timestamps from the utility Excel files.
        Metadata states UTC+1 fixed offset (Lokale Zeit: Nein).

    Returns
    -------
    pd.Series
        Timezone-aware UTC DatetimeSeries.

    Notes
    -----
    Never use tz_localize('Europe/Berlin') on this data — the DST fall-back on
    2025-10-26 creates ambiguous timestamps that crash pandas.
    """
    return (
        (pd.to_datetime(series, dayfirst=True) - pd.Timedelta(hours=1))
        .dt.tz_localize("UTC")
    )


def load_power() -> pd.DataFrame:
    """Load and clean power production data.

    Returns
    -------
    pd.DataFrame
        Index: UTC DatetimeIndex (15-min).
        Columns: Unterpreilipp_kW, Burgau_kW (float).
    """
    raw = pd.read_excel(WKA_PATH, header=None)
    # Rows 0-4: metadata | Row 5: column headers | Row 6+: data
    df = raw.iloc[6:].copy()
    df.columns = ["Datum_von", "Datum_bis", "Unterpreilipp_kW", "Burgau_kW"]
    df["Datum_von"]        = _to_utc(df["Datum_von"])
    df["Unterpreilipp_kW"] = pd.to_numeric(df["Unterpreilipp_kW"], errors="coerce")
    df["Burgau_kW"]        = pd.to_numeric(df["Burgau_kW"],        errors="coerce")
    df = (df.drop_duplicates(subset="Datum_von")
            .set_index("Datum_von")
            .drop(columns=["Datum_bis"])
            .sort_index())
    return df


def load_weather() -> pd.DataFrame:
    """Load and clean weather forecast data.

    Returns
    -------
    pd.DataFrame
        Index: UTC DatetimeIndex (15-min).
        Columns: solar_W_m2, temp_C, wind_ms, wind_dir_deg (float).

    Notes
    -----
    All columns are labeled 'Prognose' in the source — no leakage risk.
    """
    raw = pd.read_excel(WX_PATH, header=None)
    df = raw.iloc[6:].copy()
    df.columns = ["Datum_von", "Datum_bis",
                  "solar_W_m2", "temp_C", "wind_ms", "wind_dir_deg"]
    df["Datum_von"] = _to_utc(df["Datum_von"])
    for col in ["solar_W_m2", "temp_C", "wind_ms", "wind_dir_deg"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = (df.drop_duplicates(subset="Datum_von")
            .set_index("Datum_von")
            .drop(columns=["Datum_bis"])
            .sort_index())
    return df


def load_q15() -> pd.DataFrame | None:
    """Load 15-min discharge data (Rothenstein gauge).

    Returns
    -------
    pd.DataFrame or None
        Index: UTC DatetimeIndex. Column: Q_m3s.
        Returns None if the file is not found.

    Notes
    -----
    Available from ~2025-06-12 only. Earlier rows will be NaN after merging.
    """
    if not Q15_PATH.exists():
        print(f"  [WARN] Q 15-min file not found: {Q15_PATH}. Skipping.")
        return None
    df = pd.read_csv(Q15_PATH)
    df["phenomenonTime"] = pd.to_datetime(df["phenomenonTime"], utc=True)
    df = df.set_index("phenomenonTime").sort_index()
    df.columns = ["Q_m3s"]
    return df


# ── Feature engineering ───────────────────────────────────────────────────────

def add_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add lag features for both plants.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain Unterpreilipp_kW and Burgau_kW on a regular 15-min index.

    Returns
    -------
    pd.DataFrame
        Original DataFrame with lag columns appended.

    Notes
    -----
    Anti-leakage: all lags look backward only. Never compute lags before
    merging datasets — the boundary between sources can introduce NaN gaps
    that silently corrupt lag values.

    Lags:
        lag_1  = t - 15 min  (last observation)
        lag_4  = t - 1 h
        lag_96 = t - 24 h    (same slot yesterday — key for persistence)
    """
    for suffix, col in [("U", "Unterpreilipp_kW"), ("B", "Burgau_kW")]:
        for lag in [1, 4, 96]:
            df[f"lag_{lag}_{suffix}"] = df[col].shift(lag)
    return df


def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add calendar features derived from the UTC index.

    Parameters
    ----------
    df : pd.DataFrame
        UTC DatetimeIndex required.

    Returns
    -------
    pd.DataFrame
        Columns added: hour, minute, weekday, month, season.
    """
    idx = df.index
    df["hour"]    = idx.hour
    df["minute"]  = idx.minute
    df["weekday"] = idx.dayofweek      # 0 = Monday
    df["month"]   = idx.month
    # Meteorological seasons: 1=DJF, 2=MAM, 3=JJA, 4=SON
    df["season"]  = (idx.month % 12 // 3 + 1).astype(int)
    return df


def add_offline_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Flag zero-production slots as plant offline.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain Unterpreilipp_kW and Burgau_kW.

    Returns
    -------
    pd.DataFrame
        Columns added: Unterpreilipp_offline, Burgau_offline (int 0/1).

    Notes
    -----
    Burgau has ~16.5% zeros vs ~1.9% for Unterpreilipp.
    Consider training separate models or filtering offline periods.
    """
    df["Unterpreilipp_offline"] = (df["Unterpreilipp_kW"] == 0).astype(int)
    df["Burgau_offline"]        = (df["Burgau_kW"]        == 0).astype(int)
    return df


# ── Main ──────────────────────────────────────────────────────────────────────

def build(verbose: bool = True) -> pd.DataFrame:
    """Build and save the canonical feature table.

    Parameters
    ----------
    verbose : bool
        Print progress messages.

    Returns
    -------
    pd.DataFrame
        The full feature table (also saved to OUT_PATH as parquet).
    """
    def log(msg: str) -> None:
        if verbose:
            print(msg)

    log("Loading power data ...")
    power = load_power()
    log(f"  {len(power):,} rows  {power.index.min()} -> {power.index.max()}")

    log("Loading weather forecasts ...")
    weather = load_weather()
    log(f"  {len(weather):,} rows  {weather.index.min()} -> {weather.index.max()}")

    log("Loading discharge Q (15-min) ...")
    q15 = load_q15()
    if q15 is not None:
        log(f"  {len(q15):,} rows  {q15.index.min()} -> {q15.index.max()}")

    # Merge on UTC index
    log("Merging ...")
    df = power.join(weather, how="inner")
    if q15 is not None:
        df = df.join(q15, how="left")   # left = keep all power rows, NaN where Q absent
    else:
        df["Q_m3s"] = np.nan

    log(f"  Merged shape: {df.shape}")

    # Feature engineering
    log("Adding offline flags ...")
    df = add_offline_flags(df)

    log("Adding lag features ...")
    df = add_lag_features(df)

    log("Adding calendar features ...")
    df = add_calendar_features(df)

    # Drop rows where targets are NaN
    before = len(df)
    df = df.dropna(subset=["Unterpreilipp_kW", "Burgau_kW"])
    log(f"  Dropped {before - len(df)} rows with NaN targets.")

    # Save
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH)
    log(f"\nSaved {len(df):,} rows x {df.shape[1]} columns -> {OUT_PATH}")
    log(f"Columns: {list(df.columns)}")
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build WattsUp feature table.")
    parser.add_argument("--quiet", action="store_true", help="Suppress output.")
    args = parser.parse_args()
    build(verbose=not args.quiet)
