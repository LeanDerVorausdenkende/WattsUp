# WattsUp — Smart forecasts for hydropower

> **Hack the paradise! 2026** · Smart City Forum Jena (JEDI) · Build day: 13.06.2026  
> Client: Stadtwerke Energie Jena-Pößneck

Day-ahead power production forecast for two run-of-river hydropower plants on the Saale river, at **15-minute resolution** (96 slots/day). Better forecasts → better EPEX Spot bidding → lower balancing-energy cost (reBAP).

---

## Plants

| Plant | Location | Capacity |
|---|---|---|
| Saalekraftwerk **Unterpreilipp** | Rudolstadt | up to 872 kW |
| Saalekraftwerk **Burgau** | Jena | up to 951 kW |

---

## Results (60-day walk-forward test, Mar–May 2026)

| Plant | MAE | RMSE | Skill vs persistence |
|---|---|---|---|
| Unterpreilipp | 10.5 kW | 20.4 kW | **+63%** |
| Burgau | 6.7 kW | 15.4 kW | **+80%** |

Skill score = how much the model beats the naive "same as yesterday" baseline. Never negative across all 61 test days.

---

## Repo structure

```
WattsUp/
├── data/
│   ├── raw/                          # Excel power + weather files, discharge CSV
│   └── preprocessed/
│       ├── train.parquet             # canonical feature table (47,516 rows × 20 cols)
│       ├── predictions.parquet       # model output (shared format for UI group)
│       ├── shap_unterpreilipp.png    # SHAP feature importance plot
│       └── shap_burgau.png
├── src/
│   ├── data/
│   │   ├── fetch_data.py             # download gauge data from Thuringia FROST-Server
│   │   └── preprocess.py             # build train.parquet from raw Excel + CSV
│   └── model/
│       └── train.py                  # persistence baseline + LightGBM + SHAP + Optuna
├── notebooks/
│   ├── 01_eda_power.ipynb            # EDA: production coverage, zeros, autocorrelation
│   └── 02_eda_features.ipynb         # EDA: timezone audit, Q vs power, weather correlations
├── forecast_viewer.html              # interactive forecast viewer (open in browser)
├── requirements.txt
├── setup.bat
└── .env.example
```

---

## Quickstart

```bash

# 1. Build the feature table from raw data
python src/data/preprocess.py

# 2. Train and evaluate (default: last 60 days as test, with Optuna tuning)
python src/model/train.py

# Fast run without tuning (~30 sec):
python src/model/train.py --no-tune

# Custom options:
python src/model/train.py --test-days 90 --trials 50
python src/model/train.py --plant Burgau_kW --no-tune
```

---


## Pipeline

```
Raw Excel (power + weather)
    └─► preprocess.py ──► train.parquet
                               │
          ┌────────────────────┤
          ▼                    ▼
  Persistence baseline    LightGBM + SHAP
  (lag_96 = yesterday)    (Optuna-tuned)
          │                    │
          └─────────┬──────────┘
                    ▼
           predictions.parquet
           (timestamp, plant, actual,
            predicted_persistence,
            predicted_lgbm)
```

---

## Model

**Strategy:** direct multi-step — one model predicts all 96 slots simultaneously.  
**Validation:** walk-forward only (train on past, test on future — never shuffle).  
**Tuning:** Optuna + TimeSeriesSplit (50 trials, 3 folds).

### Features (17 total)

| Group | Features |
|---|---|
| Lags | lag_1, lag_4, lag_96 for each plant (U/B) |
| Discharge | Q_m3s (NaN-safe — LightGBM handles missing natively) |
| Weather forecasts | temp_C, solar_W_m2, wind_ms, wind_dir_deg |
| Calendar | hour, minute, weekday, month, season |
| Offline flags | Unterpreilipp_offline, Burgau_offline |

**Key insight:** `lag_96` (same time yesterday) is the single strongest signal — hydropower has high day-to-day autocorrelation (ACF ≈ 0.96). When `Q_m3s` is available (r = 0.918 with power), it further tightens predictions.

### Why LightGBM

Gradient boosting on tabular data. Handles NaN natively (critical — `Q_m3s` is absent for the entire Mar–May 2026 test period). Fast, explainable via SHAP, robust without feature scaling.

### Baseline

Seasonal persistence: `tomorrow[t] = today[t]` (lag_96). Strong on rivers due to high autocorrelation. Every model must beat this to be useful.

### Minimum data required to run a forecast

To predict tomorrow you need exactly two things:

1. **Today's power readings** — to compute lag_1 (15 min ago), lag_4 (1 hour ago), lag_96 (same time yesterday). As long as the plant has been running, these are always available.
2. **Tomorrow's weather forecast** — temp_C, solar_W_m2, wind_ms, wind_dir_deg. Available from DWD the evening before.

Calendar features (hour, minute, weekday, month, season) are derived from the timestamp itself and require nothing extra.

### Potential improvements

| What | Impact | Effort |
|---|---|---|
| Extend river discharge feed (Q_m3s) beyond Jan 2026 | High — Q correlates at r = 0.918 with power; currently NaN for the entire test period | Re-run `fetch_data.py` + `preprocess.py` |
| Wider weather forecast coverage (rain, upstream precipitation) | Medium — helps anticipate sudden flow events that lag features miss | Add columns to preprocess.py |
| More weather variables missing gracefully | Low risk — if any weather column is NaN, LightGBM routes it down a learned "missing" branch and keeps predicting; performance drops slightly but the model never crashes | Already handled |

---

## Data sources

| Source | Content | Period |
|---|---|---|
| `Zeitreihen_WKA_2025_2026.xlsx` | Power production (targets) | Jan 2025 – May 2026 |
| `Zeitreihen_Wetterprognosen_2025_2026.xlsx` | Weather forecasts (DWD) | Jan 2025 – May 2026 |
| Thuringia FROST-Server (SensorThings API) | River discharge Q at Rothenstein (15 minutes in our case) | Jun 2025 – Jan 2026 |

**Timezone:** all raw timestamps are UTC+1 fixed offset (Lokale Zeit: Nein — no DST). Stored internally as UTC.

---

## Original challenge

> Wie lässt sich erneuerbare Energie zuverlässig vorhersagen, obwohl sie von Wetter und Umweltfaktoren abhängt? Die Stadtwerke Jena stehen vor der Herausforderung, für Wasserkraftanlagen möglichst genaue viertelstündliche Erzeugungsprognosen für den Folgetag zu erstellen.

> How can renewable energy be reliably predicted, even though it depends on weather and environmental factors? Stadtwerke Jena faces the challenge of generating the most accurate possible quarter-hourly production forecasts for the following day for its hydropower plants. These forecasts are crucial for ensuring grid stability and fairly distributing costs within the energy system.
# About the project

[Challenge](Challenge.md) on Hack the Paradise 2026 Hackathon.


# Installation

## Python venv

* navigate to repository root
* activate venv
* `pip install .` to install the package
-> this will also install dependencies
    * use ` pip install -e .` to continuously refresh package during development
* `from watts_up import data, model, dashboard` in python

## Conda

* to be done
