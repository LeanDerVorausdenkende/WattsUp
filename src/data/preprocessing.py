"""
preprocessing.py
================
Data preprocessing pipeline for Wasserkraft (hydropower) time series forecasting.
Covers the Saalekraftwerk plants (Burgau / Jena & Unterpreilipp / Rudolstadt)
on the Saale river in Thuringia.

Pipeline steps
--------------
1. Load raw power data (15-min resolution, Excel/CSV)
2. Load weather data (temperature, wind, radiation, precipitation)
3. Load Pegel data (river discharge Q m³/s, water level)
4. Parse & align timestamps (UTC+1 → UTC-naive)
5. Reindex to a gapless 15-min grid
6. Detect & flag maintenance windows (zero-output blocks)
7. Interpolate / forward-fill short gaps
8. Outlier detection (IQR & physical limits)
9. Merge all sources on a common timeline
10. Engineer lag & calendar features
11. Save outputs:
      data/merged.csv          – aligned raw signals
      data/features.csv        – feature matrix (without Pegel)
      data/features_with_pegel.csv – feature matrix (with Pegel)

Usage
-----
    python preprocessing.py

Expected input files
--------------------
    data/raw/wka_power.xlsx        – power export from Stadtwerke
    data/raw/weather.xlsx          – DWD / open-meteo weather data
    data/raw/Q_Rothenstein_1D.csv  – daily discharge at Rothenstein (Saale)
    data/raw/Q_Rudolstadt_1D.csv   – daily discharge at Rudolstadt (Saale)
    (any additional pegel CSVs in data/raw/ matching Q_*.csv)
"""

from __future__ import annotations

import os
import glob
import logging
from pathlib import Path

import numpy as np
import pandas as pd

# ─── Configuration ────────────────────────────────────────────────────────────

RAW_DIR   = Path("data/raw")
OUT_DIR   = Path("../../data/preprocessed")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Column names in the raw power file (after stripping the 5-row header)
POWER_DATE_COL = "Datum_von"
POWER_P1_COL   = "el"    # Plant 1 – Saalekraftwerk Burgau (Jena)
POWER_P2_COL   = "el1"   # Plant 2 – Saalekraftwerk Unterpreilipp (Rudolstadt)
POWER_DATE_FMT = "%d.%m.%Y %H:%M:%S"

FREQ = "15min"           # native resolution of power data
RESAMPLE_PEGEL = "15min" # pegel is daily → forward-fill to 15-min

# Physical upper bound for each plant (kW) – adjust if you know exact ratings
MAX_POWER_P1 = 2_000
MAX_POWER_P2 = 2_000

# Maintenance detection: consecutive zero-power slots ≥ this → flag as maintenance
MAINTENANCE_ZERO_MIN_SLOTS = 4 * 2  # 2 hours (4 slots × 15 min)

# Short-gap interpolation limit (slots): gaps larger than this stay NaN
MAX_INTERP_SLOTS = 4 * 6  # 6 hours

# Lag windows to create (in 15-min slots)
LAG_24H  = 4 * 24   # 96 slots
LAG_7D   = 4 * 24 * 7
LAG_168H = LAG_7D   # alias

# Rolling statistics windows (slots)
ROLL_WINDOWS = {
    "roll_24h":  4 * 24,
    "roll_7d":   4 * 24 * 7,
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ─── Helper functions ─────────────────────────────────────────────────────────

def _strip_tz(dt_index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Remove timezone info (convert to UTC-naive)."""
    if dt_index.tz is not None:
        return dt_index.tz_localize(None)
    return dt_index


def _gapless_index(df: pd.DataFrame, freq: str) -> pd.DatetimeIndex:
    """Return a complete, gapless DatetimeIndex spanning df's range at *freq*."""
    return pd.date_range(df.index.min(), df.index.max(), freq=freq)


def flag_maintenance(series: pd.Series, min_slots: int) -> pd.Series:
    """
    Return a boolean Series that is True wherever consecutive zero (or NaN)
    values form a block at least *min_slots* wide.  Such blocks are assumed to
    be planned maintenance / shutdown rather than genuine zero generation.
    """
    is_zero = (series == 0) | series.isna()
    # Label contiguous runs
    group = (is_zero != is_zero.shift()).cumsum()
    run_lengths = is_zero.groupby(group).transform("sum")
    return is_zero & (run_lengths >= min_slots)


# ─── Step 1 – Load power data ─────────────────────────────────────────────────

def load_power(path: Path) -> pd.DataFrame:
    """
    Read the Stadtwerke power export.
    The file has 5 metadata rows before the actual header.
    Returns a DataFrame indexed by UTC-naive timestamp at 15-min resolution,
    with columns: power_plant_1_kW, power_plant_2_kW.
    """
    log.info("Loading power data from %s", path)
    raw = pd.read_excel(path, header=None)

    # Row 4 (0-indexed) contains column names; data starts at row 5
    raw.columns = raw.iloc[4].tolist()
    raw = raw.iloc[5:].copy()

    # Rename to standard names
    raw = raw.rename(columns={
        POWER_DATE_COL: "timestamp",
        POWER_P1_COL:   "power_plant_1_kW",
        POWER_P2_COL:   "power_plant_2_kW",
    })[["timestamp", "power_plant_1_kW", "power_plant_2_kW"]]

    raw["timestamp"] = pd.to_datetime(raw["timestamp"], format=POWER_DATE_FMT)
    raw["power_plant_1_kW"] = pd.to_numeric(raw["power_plant_1_kW"], errors="coerce")
    raw["power_plant_2_kW"] = pd.to_numeric(raw["power_plant_2_kW"], errors="coerce")

    raw = raw.set_index("timestamp").sort_index()
    raw.index = _strip_tz(raw.index)

    log.info("  Power data shape: %s  |  %s → %s",
             raw.shape, raw.index.min().date(), raw.index.max().date())
    return raw


# ─── Step 2 – Load weather data ───────────────────────────────────────────────

def load_weather(path: Path) -> pd.DataFrame:
    """
    Read weather data (temperature_C, wind_speed_ms, global_radiation_Wm2,
    precipitation_mm).  Expected to be at 15-min or hourly resolution.
    Returns UTC-naive, 15-min resampled DataFrame.
    """
    log.info("Loading weather data from %s", path)
    try:
        raw = pd.read_excel(path, parse_dates=["from"])
    except Exception:
        raw = pd.read_csv(path, parse_dates=["from"])

    raw = raw.rename(columns={"from": "timestamp"})
    raw = raw.set_index("timestamp").sort_index()
    raw.index = _strip_tz(raw.index)

    # Resample to 15-min if needed (forward-fill short stretches, interp longer)
    if raw.index.freq != pd.tseries.frequencies.to_offset(FREQ):
        raw = raw.resample(FREQ).interpolate(method="time", limit=8)

    # Keep only the columns we care about (rename if necessary)
    keep = {}
    for col in raw.columns:
        lc = col.lower()
        if "temp" in lc:
            keep[col] = "temperature_C"
        elif "wind" in lc and "speed" in lc:
            keep[col] = "wind_speed_ms"
        elif "radiation" in lc or "solar" in lc or "strahlung" in lc:
            keep[col] = "global_radiation_Wm2"
        elif "prec" in lc or "regen" in lc or "niederschlag" in lc:
            keep[col] = "precipitation_mm"

    raw = raw.rename(columns=keep)
    weather_cols = [c for c in
                    ["temperature_C", "wind_speed_ms",
                     "global_radiation_Wm2", "precipitation_mm"]
                    if c in raw.columns]
    raw = raw[weather_cols]

    log.info("  Weather columns: %s  |  %s → %s",
             list(raw.columns), raw.index.min().date(), raw.index.max().date())
    return raw


# ─── Step 3 – Load Pegel (discharge / water-level) data ──────────────────────

def load_pegel(pattern: str = "data/raw/Q_*.csv") -> pd.DataFrame:
    """
    Load one or more daily discharge CSV files from the Thüringen FROST server
    (columns: phenomenonTime, Q_m³/s) and merge them.
    Returns a UTC-naive 15-min DataFrame (forward-filled from daily).
    """
    files = sorted(glob.glob(pattern))
    if not files:
        log.warning("No Pegel files matching %s – skipping.", pattern)
        return pd.DataFrame()

    frames = []
    for fp in files:
        station = Path(fp).stem  # e.g. "Q_Rothenstein_1D"
        col_name = f"pegel_{station}"
        log.info("  Loading %s → column %s", fp, col_name)
        df = pd.read_csv(fp, parse_dates=["phenomenonTime"])
        df = df.rename(columns={"phenomenonTime": "timestamp", "Q_m³/s": col_name})
        df = df.set_index("timestamp").sort_index()[[col_name]]
        df.index = _strip_tz(df.index)
        frames.append(df)

    pegel = pd.concat(frames, axis=1)
    log.info("  Pegel shape (daily): %s", pegel.shape)
    return pegel


# ─── Step 4-6 – Clean & align ─────────────────────────────────────────────────

def clean_power(power: pd.DataFrame) -> pd.DataFrame:
    """
    Reindex to gapless 15-min grid, detect maintenance, interpolate short gaps,
    clip to physical limits, flag outliers.
    """
    log.info("Cleaning power data …")
    full_idx = _gapless_index(power, FREQ)
    power = power.reindex(full_idx)

    for plant, col, max_kw in [
        (1, "power_plant_1_kW", MAX_POWER_P1),
        (2, "power_plant_2_kW", MAX_POWER_P2),
    ]:
        maint_col = f"power_plant_{plant}_kW_maintenance"

        # Flag maintenance windows (long zero / NaN blocks)
        power[maint_col] = flag_maintenance(power[col], MAINTENANCE_ZERO_MIN_SLOTS)

        # Clip negative values to 0 (can happen due to rounding in raw export)
        power[col] = power[col].clip(lower=0)

        # Physical upper limit → NaN (sensor fault)
        too_high = power[col] > max_kw
        if too_high.any():
            log.warning("  Plant %d: %d readings above %d kW – set to NaN",
                        plant, too_high.sum(), max_kw)
            power.loc[too_high, col] = np.nan

        # IQR outlier detection (skip maintenance windows)
        non_maint = ~power[maint_col]
        q1 = power.loc[non_maint, col].quantile(0.01)
        q3 = power.loc[non_maint, col].quantile(0.99)
        iqr = q3 - q1
        low_bound  = q1 - 3 * iqr
        high_bound = q3 + 3 * iqr
        outlier_mask = non_maint & (
            (power[col] < low_bound) | (power[col] > high_bound)
        )
        if outlier_mask.any():
            log.warning("  Plant %d: %d IQR outliers → NaN", plant, outlier_mask.sum())
            power.loc[outlier_mask, col] = np.nan

        # Interpolate short gaps (skip maintenance)
        power[col] = (
            power[col]
            .where(power[maint_col], power[col])   # keep maintenance as NaN
            .interpolate(method="time", limit=MAX_INTERP_SLOTS)
        )

        missing_pct = power[col].isna().mean() * 100
        log.info("  Plant %d: %.1f%% missing after cleaning", plant, missing_pct)

    return power


def align_and_merge(power: pd.DataFrame,
                    weather: pd.DataFrame,
                    pegel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Merge power + weather (+ optional pegel) on a common 15-min index.
    Returns (merged_no_pegel, merged_with_pegel).
    """
    log.info("Merging power + weather …")
    merged = power.join(weather, how="left")

    # Forward-fill weather for short outages (e.g. 1 h)
    weather_cols = [c for c in weather.columns]
    merged[weather_cols] = merged[weather_cols].fillna(method="ffill", limit=4)

    missing_weather = merged[weather_cols].isna().mean() * 100
    for col, pct in missing_weather.items():
        if pct > 0:
            log.warning("  Weather column '%s': %.1f%% still missing after ffill", col, pct)

    if pegel.empty:
        log.info("  No Pegel data – returning merged without Pegel.")
        return merged, merged.copy()

    log.info("Merging Pegel data (daily → 15-min forward-fill) …")
    # Upsample pegel from daily to 15-min by forward-fill
    pegel_15min = pegel.reindex(merged.index, method="ffill")
    merged_with_pegel = merged.join(pegel_15min, how="left")

    return merged, merged_with_pegel


# ─── Step 10 – Feature engineering ───────────────────────────────────────────

def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add time-based features: hour, weekday, month, season, etc."""
    idx = df.index
    df["hour"]        = idx.hour
    df["minute"]      = idx.minute
    df["slot_of_day"] = idx.hour * 4 + idx.minute // 15   # 0–95
    df["weekday"]     = idx.dayofweek                      # 0=Mon
    df["month"]       = idx.month
    df["day_of_year"] = idx.dayofyear
    df["week"]        = idx.isocalendar().week.astype(int)

    # Season (meteorological)
    df["season"] = pd.cut(
        idx.month,
        bins=[0, 2, 5, 8, 11, 12],
        labels=["Winter", "Spring", "Summer", "Autumn", "Winter2"],
        ordered=False,
    ).astype(str).replace("Winter2", "Winter")

    # Cyclical encoding of hour & day-of-year to capture periodicity
    df["hour_sin"]    = np.sin(2 * np.pi * df["slot_of_day"] / 96)
    df["hour_cos"]    = np.cos(2 * np.pi * df["slot_of_day"] / 96)
    df["doy_sin"]     = np.sin(2 * np.pi * df["day_of_year"] / 365.25)
    df["doy_cos"]     = np.cos(2 * np.pi * df["day_of_year"] / 365.25)

    return df


def add_lag_features(df: pd.DataFrame, prefix: str, col: str) -> pd.DataFrame:
    """Add lag and rolling features for a given power column."""
    log.info("  Adding lag features for %s …", col)

    # Lag: same slot yesterday (24 h back)
    df[f"{prefix}_lag_24h"] = df[col].shift(LAG_24H)
    # Lag: same slot last week (7 days back)
    df[f"{prefix}_lag_7d"]  = df[col].shift(LAG_7D)

    # 24-h trend (current minus 24-h-ago daily mean)
    df[f"{prefix}_trend_24h"] = df[col] - df[f"{prefix}_lag_24h"]

    # Rolling means (non-overlapping with future → .shift(1) to avoid leakage)
    for name, window in ROLL_WINDOWS.items():
        df[f"{prefix}_{name}_mean"] = (
            df[col].shift(1).rolling(window, min_periods=window // 4).mean()
        )
        df[f"{prefix}_{name}_std"] = (
            df[col].shift(1).rolling(window, min_periods=window // 4).std()
        )

    return df


def build_features(merged: pd.DataFrame,
                   with_pegel: bool = False) -> pd.DataFrame:
    """
    Full feature engineering pass on the merged DataFrame.
    Returns a copy with all engineered columns appended.
    Also adds 'from' and 'to' timestamp columns for compatibility with dashboard.
    """
    df = merged.copy()

    # Timestamp columns (dashboard compatibility)
    df.insert(0, "from", df.index)
    df.insert(1, "to",   df.index + pd.Timedelta(minutes=15))

    df = add_calendar_features(df)

    for plant_num, prefix, col in [
        (1, "p1", "power_plant_1_kW"),
        (2, "p2", "power_plant_2_kW"),
    ]:
        if col in df.columns:
            df = add_lag_features(df, prefix, col)

    # Drop rows without the mandatory lag (first 7 days have no lag_7d)
    before = len(df)
    df = df.dropna(subset=["p1_lag_7d"] if "p1_lag_7d" in df.columns else [])
    log.info("  Dropped %d rows without full lag history", before - len(df))

    if not with_pegel:
        pegel_cols = [c for c in df.columns if c.startswith("pegel_")]
        df = df.drop(columns=pegel_cols)

    return df


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    # 1. Load raw data
    power_path   = RAW_DIR / "Zeitreihen_WKA_2025_2026.xlsx"
    weather_path = RAW_DIR / "Zeitreihen_Wetterprognosen_2025_2026.xlsx"
    pegel_glob   = str(RAW_DIR / "Q_*.csv")

    power   = load_power(power_path)
    weather = load_weather(weather_path)
    pegel   = load_pegel(pegel_glob)

    # 2–6. Clean & align
    power = clean_power(power)
    merged_no_pegel, merged_with_pegel = align_and_merge(power, weather, pegel)

    # 7. Save merged (raw aligned) output
    merged_path = OUT_DIR / "merged.csv"
    merged_no_pegel.to_csv(merged_path)
    log.info("Saved merged data → %s  (%d rows)", merged_path, len(merged_no_pegel))

    # 8–10. Feature engineering
    features_no_pegel   = build_features(merged_no_pegel,   with_pegel=False)
    features_with_pegel = build_features(merged_with_pegel, with_pegel=True)

    feat_path       = OUT_DIR / "features.csv"
    feat_pegel_path = OUT_DIR / "features_with_pegel.csv"

    features_no_pegel.to_csv(feat_path, index=False)
    features_with_pegel.to_csv(feat_pegel_path, index=False)

    log.info("Saved features            → %s  (%d rows, %d cols)",
             feat_path, *features_no_pegel.shape)
    log.info("Saved features with Pegel → %s  (%d rows, %d cols)",
             feat_pegel_path, *features_with_pegel.shape)

    # 11. Quick sanity summary
    for label, df in [("No Pegel", features_no_pegel),
                      ("With Pegel", features_with_pegel)]:
        p1_miss = df["power_plant_1_kW"].isna().mean() * 100
        p2_miss = df["power_plant_2_kW"].isna().mean() * 100 if "power_plant_2_kW" in df else None
        log.info("[%s]  Plant 1 missing: %.2f%%  |  Plant 2 missing: %s",
                 label, p1_miss,
                 f"{p2_miss:.2f}%" if p2_miss is not None else "N/A")

    log.info("Preprocessing complete.")


if __name__ == "__main__":
    main()