"""
Train and evaluate models for day-ahead hydropower forecasting.

Models
------
1. Seasonal Persistence  — baseline: tomorrow[t] = today[t] (lag_96)
2. LightGBM              — main model, direct multi-step strategy + SHAP

Validation
----------
Walk-forward split: train on past, test on the last N days.
Never shuffle — this is a time series.

Output
------
- Prints MAE, RMSE, MAPE, skill score vs persistence for each model
- Saves SHAP summary plot to data/preprocessed/shap_summary.png
- Saves predictions to data/preprocessed/predictions.parquet

Usage
-----
    python src/model/train.py                   # default: last 60 days as test
    python src/model/train.py --test-days 90    # custom test window
    python src/model/train.py --plant Burgau_kW # single plant
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import lightgbm as lgb
import optuna
import shap
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit

optuna.logging.set_verbosity(optuna.logging.WARNING)


# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT        = Path(__file__).resolve().parents[2]
TRAIN_PATH  = ROOT / "data" / "preprocessed" / "train.parquet"
OUT_DIR     = ROOT / "data" / "preprocessed"

FEATURE_COLS = [
    # Lag features — strongest signals
    "lag_96_U", "lag_96_B",
    "lag_4_U",  "lag_4_B",
    "lag_1_U",  "lag_1_B",
    # Discharge
    "Q_m3s",
    # Weather forecasts (no leakage — labeled Prognose)
    "temp_C", "solar_W_m2", "wind_ms", "wind_dir_deg",
    # Calendar
    "hour", "minute", "weekday", "month", "season",
    # Offline flags
    "Unterpreilipp_offline", "Burgau_offline",
]

PLANTS = ["Unterpreilipp_kW", "Burgau_kW"]


# ── Metrics ───────────────────────────────────────────────────────────────────

def evaluate(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_persistence: np.ndarray,
    label: str = "",
) -> dict:
    """Compute MAE, RMSE, MAPE, and skill score vs persistence.

    Parameters
    ----------
    y_true : np.ndarray
        Actual power values (kW).
    y_pred : np.ndarray
        Predicted power values (kW).
    y_persistence : np.ndarray
        Persistence baseline predictions (lag_96).
    label : str
        Label for printed output.

    Returns
    -------
    dict
        Keys: mae, rmse, mape, skill_score.

    Notes
    -----
    Skill score = 1 - MAE(model) / MAE(persistence).
    Positive = better than persistence. Negative = worse — reject model.
    MAPE excludes zero actuals to avoid division by zero.
    """
    mae  = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae_p = mean_absolute_error(y_true, y_persistence)

    # MAPE: skip zeros
    mask = y_true != 0
    mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100

    skill = 1 - mae / mae_p if mae_p > 0 else float("nan")

    if label:
        print(f"\n{'─'*50}")
        print(f"  {label}")
        print(f"{'─'*50}")
        print(f"  MAE          : {mae:>8.1f} kW")
        print(f"  RMSE         : {rmse:>8.1f} kW")
        print(f"  MAPE         : {mape:>8.1f} %")
        print(f"  Skill score  : {skill:>8.3f}  (vs persistence)")
        if skill > 0:
            print(f"  -> {skill*100:.1f}% better than persistence baseline")
        else:
            print("  -> WORSE than persistence — review features/params")

    return {"mae": mae, "rmse": rmse, "mape": mape, "skill_score": skill}


# ── Models ────────────────────────────────────────────────────────────────────

def persistence_predict(test: pd.DataFrame, target: str) -> np.ndarray:
    """Seasonal persistence: predict using lag_96 (same time yesterday).

    Parameters
    ----------
    test : pd.DataFrame
        Test set containing lag_96_U or lag_96_B.
    target : str
        'Unterpreilipp_kW' or 'Burgau_kW'.

    Returns
    -------
    np.ndarray
        Persistence predictions aligned with test index.
    """
    lag_col = "lag_96_U" if "Unterpreilipp" in target else "lag_96_B"
    return test[lag_col].fillna(0).values


def _prepare_train(
    train: pd.DataFrame,
    target: str,
    feature_cols: list[str],
) -> tuple[pd.DataFrame, pd.Series]:
    """Filter and return X_train, y_train (non-NaN, non-zero target rows).

    Parameters
    ----------
    train : pd.DataFrame
        Full training split.
    target : str
        Target column name.
    feature_cols : list of str
        Feature columns to keep.

    Returns
    -------
    tuple of (pd.DataFrame, pd.Series)
        Cleaned X_train and y_train.
    """
    df = train.dropna(subset=[target])
    df = df[df[target] > 0]
    return df[feature_cols], df[target]


def tune_lightgbm(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    n_trials: int = 50,
    n_splits: int = 3,
) -> dict:
    """Find the best LightGBM hyperparameters using Optuna + TimeSeriesSplit.

    How it works
    ------------
    Optuna tries `n_trials` different parameter combinations.
    For each combination it does `n_splits`-fold walk-forward cross-validation
    (train on past folds, validate on next fold — respects time order).
    It keeps the combination with the lowest average validation MAE.

    Parameters
    ----------
    X_train : pd.DataFrame
        Training features.
    y_train : pd.Series
        Training target.
    n_trials : int
        Number of parameter combinations to try. More = better but slower.
        50 trials takes ~2-4 minutes on this dataset.
    n_splits : int
        Number of walk-forward CV folds.

    Returns
    -------
    dict
        Best hyperparameters found.
    """
    tscv = TimeSeriesSplit(n_splits=n_splits)

    def objective(trial: optuna.Trial) -> float:
        params = {
            "objective":        "regression",
            "metric":           "mae",
            "verbose":          -1,
            "n_jobs":           -1,
            # ── Parameters Optuna will tune ───────────────────────────────
            "num_leaves":       trial.suggest_int("num_leaves", 20, 200),
            "learning_rate":    trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 20, 200),
            "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
            "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 1.0),
            "bagging_freq":     trial.suggest_int("bagging_freq", 1, 10),
            "lambda_l1":        trial.suggest_float("lambda_l1", 1e-4, 10.0, log=True),
            "lambda_l2":        trial.suggest_float("lambda_l2", 1e-4, 10.0, log=True),
        }
        fold_maes = []
        for train_idx, val_idx in tscv.split(X_train):
            X_tr, X_val = X_train.iloc[train_idx], X_train.iloc[val_idx]
            y_tr, y_val = y_train.iloc[train_idx], y_train.iloc[val_idx]
            ds = lgb.Dataset(X_tr, label=y_tr)
            ds_val = lgb.Dataset(X_val, label=y_val, reference=ds)
            m = lgb.train(
                params, ds,
                num_boost_round=500,
                valid_sets=[ds_val],
                callbacks=[lgb.early_stopping(30, verbose=False),
                           lgb.log_evaluation(period=-1)],
            )
            preds = np.clip(m.predict(X_val), 0, None)
            fold_maes.append(mean_absolute_error(y_val, preds))
        return float(np.mean(fold_maes))

    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    best = study.best_params
    best.update({"objective": "regression", "metric": "mae",
                 "verbose": -1, "n_jobs": -1})
    print(f"  Best params (val MAE = {study.best_value:.2f} kW):")
    for k, v in study.best_params.items():
        print(f"    {k:<22} = {v}")
    return best


def train_lightgbm(
    train: pd.DataFrame,
    test: pd.DataFrame,
    target: str,
    feature_cols: list[str],
    tune: bool = True,
    n_trials: int = 50,
) -> tuple[lgb.Booster, np.ndarray]:
    """Train a LightGBM model and return predictions on the test set.

    Parameters
    ----------
    train : pd.DataFrame
        Training data (past rows only — walk-forward).
    test : pd.DataFrame
        Test data (future rows).
    target : str
        Target column name.
    feature_cols : list of str
        Feature column names to use.
    tune : bool
        If True, run Optuna hyperparameter search before final training.
        If False, use sensible defaults (faster, good for quick iteration).
    n_trials : int
        Number of Optuna trials (ignored when tune=False).

    Returns
    -------
    tuple of (lgb.Booster, np.ndarray)
        Trained booster and test-set predictions.

    Notes
    -----
    Direct strategy: one model predicts all future slots at once.
    LightGBM handles NaN (Q_m3s is NaN before Jun 2025) natively.
    """
    X_train, y_train = _prepare_train(train, target, feature_cols)
    X_test = test[feature_cols]

    if tune:
        print(f"  Tuning hyperparameters ({n_trials} Optuna trials) ...")
        params = tune_lightgbm(X_train, y_train, n_trials=n_trials)
    else:
        print("  Using default hyperparameters (no tuning).")
        params = {
            "objective":        "regression",
            "metric":           "mae",
            "learning_rate":    0.05,
            "num_leaves":       63,
            "min_data_in_leaf": 50,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq":     5,
            "verbose":          -1,
            "n_jobs":           -1,
        }

    ds_train = lgb.Dataset(X_train, label=y_train)
    model = lgb.train(
        params,
        ds_train,
        num_boost_round=500,
        callbacks=[lgb.early_stopping(50, verbose=False),
                   lgb.log_evaluation(period=-1)],
        valid_sets=[ds_train],
    )
    preds = model.predict(X_test, num_iteration=model.best_iteration)
    preds = np.clip(preds, 0, None)
    return model, preds


def plot_shap(
    model: lgb.Booster,
    X_test: pd.DataFrame,
    target: str,
    out_path: Path,
) -> None:
    """Generate and save a SHAP summary plot.

    Parameters
    ----------
    model : lgb.Booster
        Trained LightGBM model.
    X_test : pd.DataFrame
        Test features (sample used for SHAP computation).
    target : str
        Plant name for the plot title.
    out_path : Path
        File path for the saved PNG.
    """
    explainer   = shap.TreeExplainer(model)
    # Fill NaN with 0 for SHAP (LightGBM handles NaN internally but SHAP needs clean input)
    X_filled    = X_test.fillna(0)
    sample      = X_filled.sample(min(500, len(X_filled)), random_state=42)
    shap_values = explainer.shap_values(sample)

    fig, ax = plt.subplots(figsize=(10, 6))
    shap.summary_plot(shap_values, sample, show=False, plot_size=None)
    plt.title(f"SHAP feature importance — {target}")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  SHAP plot saved -> {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run(test_days: int = 60, plants: list[str] | None = None,
        tune: bool = True, n_trials: int = 50) -> pd.DataFrame:
    """Run full training and evaluation pipeline.

    Parameters
    ----------
    test_days : int
        Number of trailing days to hold out as test set.
    plants : list of str, optional
        Plants to model. Defaults to both.
    tune : bool
        Whether to run Optuna hyperparameter tuning.
    n_trials : int
        Number of Optuna trials per plant.

    Returns
    -------
    pd.DataFrame
        Predictions table with columns:
        timestamp, plant, actual, predicted_persistence, predicted_lgbm.
    """
    if plants is None:
        plants = PLANTS

    print(f"Loading {TRAIN_PATH} ...")
    df = pd.read_parquet(TRAIN_PATH)
    print(f"  {len(df):,} rows  {df.index.min()} -> {df.index.max()}")

    # Walk-forward split
    cutoff = df.index.max() - pd.Timedelta(days=test_days)
    train  = df[df.index <= cutoff]
    test   = df[df.index >  cutoff]
    print(f"\nTrain: {len(train):,} rows  ({train.index.min().date()} -> {train.index.max().date()})")
    print(f"Test : {len(test):,} rows  ({test.index.min().date()} -> {test.index.max().date()})")

    all_results = []
    results_summary = {}

    for target in plants:
        print(f"\n{'='*55}")
        print(f"  Plant: {target}")
        print(f"{'='*55}")

        y_true        = test[target].values
        y_persistence = persistence_predict(test, target)

        # 1. Persistence baseline
        evaluate(y_true, y_persistence, y_persistence,
                 label=f"Persistence baseline — {target}")

        # 2. LightGBM
        feats   = [c for c in FEATURE_COLS if c in df.columns]
        model, y_lgbm = train_lightgbm(train, test, target, feats,
                                        tune=tune, n_trials=n_trials)

        metrics = evaluate(y_true, y_lgbm, y_persistence,
                           label=f"LightGBM — {target}")
        results_summary[target] = metrics

        # SHAP plot
        shap_path = OUT_DIR / f"shap_{target.replace('_kW','').lower()}.png"
        X_test_df = test[feats]
        plot_shap(model, X_test_df, target, shap_path)

        # Collect predictions
        for i, ts in enumerate(test.index):
            all_results.append({
                "timestamp":            ts,
                "plant":                target,
                "actual":               y_true[i],
                "predicted_persistence": y_persistence[i],
                "predicted_lgbm":       y_lgbm[i],
                "model_name":           "LightGBM",
            })

    # Save predictions in the shared output format expected by UI group
    pred_df = pd.DataFrame(all_results).set_index("timestamp")
    pred_path = OUT_DIR / "predictions.parquet"
    pred_df.to_parquet(pred_path)
    print(f"\nPredictions saved -> {pred_path}")

    # Final summary table
    print(f"\n{'='*55}")
    print("  Final comparison — Skill score vs persistence")
    print(f"{'='*55}")
    print(f"  {'Plant':<25}  {'MAE':>8}  {'RMSE':>8}  {'Skill':>8}")
    print(f"  {'-'*25}  {'-'*8}  {'-'*8}  {'-'*8}")
    for plant, m in results_summary.items():
        print(f"  {plant:<25}  {m['mae']:>8.1f}  {m['rmse']:>8.1f}  {m['skill_score']:>8.3f}")

    return pred_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train WattsUp models.")
    parser.add_argument("--test-days", type=int, default=60)
    parser.add_argument("--plant", type=str, default=None)
    parser.add_argument("--no-tune", action="store_true")
    parser.add_argument("--trials", type=int, default=50)
    args = parser.parse_args()
    plants = [args.plant] if args.plant else None
    run(test_days=args.test_days, plants=plants,
        tune=not args.no_tune, n_trials=args.trials)
