"""Serve a trained power-forecast model: load it and predict for a given date.

Standalone, production-facing companion to the training script. Loads the
artifact (model + preprocessing metadata) and exposes :func:`predict_for_date`,
which returns the ``N_HOURS`` power forecast launched at ``demo_hour`` (10:00 by
default) of the requested date.

This module has no dependency on the training code: the feature construction is
re-implemented here from the metadata saved in the artifact (discharge columns,
causal power moving-average, column order), so it must stay in lock-step with the
trainer's ``load_series``. The check ``feature_cols == meta["feature_cols"]``
guards against silent drift. Only data up to the cutoff is used (no leakage).

Intended to be imported by a backend::

    from src.forecast.serve import predict_for_date
    forecast = predict_for_date("2025-12-05")   # DataFrame: index=time, power_pred

or run as a CLI for a quick check::

    python -m src.forecast.serve --date 2025-12-05
"""

import argparse
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

#: Artifacts live next to this module for simple, self-contained serving.
MODEL_DIR = Path(__file__).resolve().parent
DEFAULT_ARTIFACT = MODEL_DIR / "model_random_forest_quick.joblib"


def load_artifact(artifact_path=DEFAULT_ARTIFACT) -> dict:
    """Load a saved ``{"model", "meta"}`` bundle.

    Args:
        artifact_path: Path to the joblib artifact written during training.

    Returns:
        The unpickled bundle dict.

    Raises:
        FileNotFoundError: If the artifact does not exist.
    """
    if not Path(artifact_path).exists():
        raise FileNotFoundError(
            f"No model artifact at {artifact_path}. Train one first, e.g.:\n"
            f"  python -m src.forecast.forecast_power --model random_forest"
        )
    return joblib.load(artifact_path)


def build_features(
    parquet, meta: dict
) -> tuple[pd.DatetimeIndex, np.ndarray, list[str]]:
    """Reconstruct the model's input features from a wide per-station table.

    Mirrors the training-time feature construction using only the saved
    metadata: keep the discharge columns (``feature_prefix``), optionally append
    the causal (trailing, past-only) power moving average, in the same order. The
    moving average at index ``t`` uses only the target up to ``t``
    (``min_periods=1``), so it is always available at forecast time.

    Args:
        parquet: Path to the parquet data source.
        meta: Artifact metadata (``feature_prefix``, ``target_col``,
            ``time_col``, ``ma_hours``, ``steps_per_hour``).

    Returns:
        Tuple ``(time, features, feature_cols)`` where ``features`` has shape
        ``(T, n_features)`` and ``feature_cols`` is the ordered column list.
    """
    df = pd.read_parquet(parquet)
    df = df.sort_values(meta["time_col"]).reset_index(drop=True)
    time = pd.DatetimeIndex(df[meta["time_col"]])

    feature_cols = [c for c in df.columns if c.startswith(meta["feature_prefix"])]
    feature_frame = df[feature_cols].copy()

    if meta["ma_hours"] > 0:
        ma_window = meta["ma_hours"] * meta["steps_per_hour"]
        ma_col = f"power_ma_{meta['ma_hours']}h"
        feature_frame[ma_col] = (
            df[meta["target_col"]].rolling(window=ma_window, min_periods=1).mean()
        )
        feature_cols = [*feature_cols, ma_col]

    return time, feature_frame.to_numpy(dtype=float), feature_cols


def predict_for_date(
    date: str | datetime | pd.Timestamp,
    artifact_path=DEFAULT_ARTIFACT,
    parquet=None,
) -> pd.DataFrame:
    """Forecast power for ``N_HOURS`` after ``demo_hour`` of ``date``.

    Builds the look-back window ending at ``date`` ``demo_hour``:00 from data up
    to (and including) that cutoff, then returns the model's multi-step forecast.

    Args:
        date: Calendar date of the forecast cutoff (any pandas-parseable date,
            or a datetime/Timestamp). The time-of-day component is ignored; the
            cutoff is fixed to ``meta["demo_hour"]``:00 of that date.
        artifact_path: Path to the saved model bundle.
        parquet: Optional override of the data source; defaults to the parquet
            recorded in the artifact metadata.

    Returns:
        DataFrame indexed by forecast timestamp with a single ``power_pred``
        column, of length ``meta["horizon_steps"]``.

    Raises:
        ValueError: If the cutoff is absent from the data, the feature columns
            no longer match the trained model, or history is too short.
    """
    bundle = load_artifact(artifact_path)
    model, meta = bundle["model"], bundle["meta"]
    source = parquet or meta["parquet"]

    time, features, feature_cols = build_features(source, meta)
    if feature_cols != meta["feature_cols"]:
        raise ValueError(
            "Feature columns in the data do not match the trained model.\n"
            f"  expected: {meta['feature_cols']}\n  found:    {feature_cols}"
        )

    cutoff = pd.Timestamp(date).normalize() + pd.Timedelta(hours=meta["demo_hour"])
    matches = np.flatnonzero(time == cutoff)
    if matches.size == 0:
        raise ValueError(f"Cutoff {cutoff} is not present in the data source.")
    idx = int(matches[0])

    window, horizon = meta["window_steps"], meta["horizon_steps"]
    if idx - window + 1 < 0:
        raise ValueError(
            f"Not enough history before {cutoff}: need {window} steps, have {idx + 1}."
        )

    x_row = features[idx - window + 1 : idx + 1].ravel().reshape(1, -1)
    pred = model.predict(x_row)[0]

    step = pd.Timedelta(hours=1) / meta["steps_per_hour"]
    forecast_index = pd.date_range(cutoff + step, periods=horizon, freq=step)
    return pd.DataFrame({"power_pred": pred}, index=forecast_index)


def main() -> None:
    """CLI entry point: print the forecast for a date."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", required=True, help="Forecast date, e.g. 2025-12-05.")
    p.add_argument(
        "--artifact", default=str(DEFAULT_ARTIFACT), help="Path to model .joblib."
    )
    p.add_argument("--parquet", default=None, help="Override data source parquet.")
    a = p.parse_args()

    forecast = predict_for_date(a.date, artifact_path=a.artifact, parquet=a.parquet)
    cutoff = forecast.index[0] - (forecast.index[1] - forecast.index[0])
    print(f"Forecast launched at {cutoff:%Y-%m-%d %H:%M}  ({len(forecast)} steps):")
    print(forecast.to_string(float_format=lambda v: f"{v:7.1f}"))


if __name__ == "__main__":
    main()
