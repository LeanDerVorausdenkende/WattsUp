"""
Business dashboard v3 - "Forecast for a chosen date" + "Historical Validation".

Run (after `pip install plotly`):
    streamlit run src/06b_dashboard_business.py

SECTION 1 - Forecast for a chosen date:
  Pick ANY date after the last available data point. Internally this uses
  RECURSIVE forecasting (src/forecast_utils.py):
    - The pre-trained model is NOT retrained for each request.
    - Day 1 (and day 2, if within REAL_WEATHER_HORIZON_DAYS) use real
      weather-forecast data and real recent actuals for lag features.
    - Any days beyond that use "typical for this time of year" weather
      (climatology) and the model's OWN earlier predictions as if they
      were actuals, feeding forward day by day until the requested date.
  A confidence banner makes clear which regime applies, plus a trajectory
  chart shows the daily-average path and where climatology kicks in.

SECTION 2 - Historical Validation:
  Pick any past day and see forecast vs. actual vs. naive baseline.

Requires:
  - data/merged.csv, data/weather.xlsx, data/features.csv,
    data/features_with_pegel.csv, src/forecast_utils.py
  - output/model_without_pegel.pkl, output/model_with_pegel.pkl
  - output/test_predictions_without_pegel.csv / _with_pegel.csv
  - output/06_feature_importance_with_pegel.png / _without_pegel.png
"""
import importlib.util

import joblib
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sklearn.metrics import mean_absolute_error

TARGET = "power_plant_1_kW"
PREFIX = "p1"

st.set_page_config(page_title="WattsUp - Day-Ahead Forecast", layout="wide")
st.title("Day-Ahead Power Forecast")
st.caption("Wasserkraftanlage - Saale river, Jena/Rudolstadt area - 15-minute resolution")

# ============================================================
# Plant location
# ============================================================
with st.expander("Plant location", expanded=False):
    st.markdown(
        "This forecast covers a hydropower plant on the **Saale river** in "
        "the Jena / Rudolstadt area (Thuringia). The hackathon dataset "
        "includes two plants - **Saalekraftwerk Burgau** (Jena) and "
        "**Saalekraftwerk Unterpreilipp** (Rudolstadt). This dashboard "
        "shows **Plant 1** from the dataset - the exact column-to-plant "
        "mapping should be confirmed with Stadtwerke."
    )
    st.map(pd.DataFrame({"lat": [50.927, 50.718], "lon": [11.586, 11.339]}),
           zoom=9)

st.divider()

# ============================================================
# SECTION 1 - Forecast for a chosen date (recursive)
# ============================================================
st.header("Forecast for a chosen date")

spec = importlib.util.spec_from_file_location("fu", "src/forecast_utils.py")
fu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fu)

try:
    merged_dates = pd.read_csv("data/merged.csv", parse_dates=["from"])["from"].dt.date
except FileNotFoundError as e:
    st.error(f"Missing file: {e.filename}")
    st.stop()

last_power_date = merged_dates.max()
min_target = last_power_date + pd.Timedelta(days=1)

st.caption(
    f"Our data ends **{last_power_date.strftime('%d %B %Y')}**. Pick any "
    f"date from {min_target.strftime('%d %B %Y')} onwards. Forecasts more "
    f"than {fu.REAL_WEATHER_HORIZON_DAYS} day(s) out use typical seasonal "
    "weather (no real forecast exists that far ahead) and build on the "
    "model's own earlier predictions - so confidence decreases the "
    "further ahead you go."
)

selected_target = st.date_input("Forecast date", value=min_target, min_value=min_target)

try:
    results, _, _ = fu.recursive_forecast(
        selected_target, model_path="output/model_without_pegel.pkl"
    )
except FileNotFoundError as e:
    st.warning(
        f"Missing file: {e.filename}\n\n"
        "Run `python src/04_train_model.py` with `USE_PEGEL = False` "
        "(output-suffix edit applied) to generate "
        "`output/model_without_pegel.pkl`."
    )
    results = None

if results:
    t_result = results[selected_target]
    t = t_result["day_rows"]
    forecast = t_result["forecast_kW"]
    baseline = t_result["baseline_kW"]
    time_labels = t_result["time"]
    horizon = t_result["step"]

    # --- Confidence banner ---
    if t_result["weather_source"] == "forecast":
        st.success(
            f"Day **{horizon}** of the forecast - based on a **real weather "
            "forecast** for this date and (for day 1) actual recent output."
        )
    else:
        extra_days = horizon - fu.REAL_WEATHER_HORIZON_DAYS
        st.warning(
            f"Day **{horizon}** of the forecast - {extra_days} day(s) beyond "
            "our real weather-forecast horizon. This estimate uses "
            "**typical weather for this time of year** and builds on the "
            "model's own predictions for the days in between. Treat it as "
            "an indicative trend, not a precise day-ahead forecast."
        )

    # --- KPI cards ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Expected average output", f"{forecast.mean():.0f} kW")
    col2.metric("Expected peak", f"{forecast.max():.0f} kW",
                f"at {time_labels.iloc[forecast.idxmax()]}")
    col3.metric("Expected low", f"{forecast.min():.0f} kW",
                f"at {time_labels.iloc[forecast.idxmin()]}")
    diff = (forecast.mean() - baseline.mean()) / baseline.mean() * 100
    col4.metric("vs. previous day", f"{diff:+.0f}%")

    # --- Main chart ---
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=time_labels, y=forecast, name="Forecast",
                              line=dict(color="#1f77b4", width=3)))
    fig.add_trace(go.Scatter(x=time_labels, y=baseline, name="If same as previous day",
                              line=dict(color="gray", width=1.5, dash="dash")))
    fig.update_layout(
        title=f"Forecast for {selected_target.strftime('%A, %d %B %Y')} (15-minute intervals)",
        xaxis_title="Time of day", yaxis_title="Power output (kW)",
        height=420, template="plotly_white",
        legend=dict(orientation="h", y=-0.25), margin=dict(t=60, b=40),
    )
    fig.update_xaxes(tickmode="array", tickvals=time_labels[::8], tickangle=45)
    st.plotly_chart(fig, use_container_width=True)

    # --- Trajectory chart: daily average across the whole path ---
    traj_dates = sorted(results.keys())
    traj_avg = [results[d]["forecast_kW"].mean() for d in traj_dates]
    traj_source = [results[d]["weather_source"] for d in traj_dates]

    fig_traj = go.Figure()
    for src, color, label in [("forecast", "#1f77b4", "Real weather forecast"),
                               ("climatology", "#ff7f0e", "Typical-season estimate")]:
        xs = [d for d, s in zip(traj_dates, traj_source) if s == src]
        ys = [a for a, s in zip(traj_avg, traj_source) if s == src]
        if xs:
            fig_traj.add_trace(go.Scatter(
                x=xs, y=ys, mode="markers+lines", name=label,
                marker=dict(size=8, color=color), line=dict(color=color, width=2),
            ))
    fig_traj.update_layout(
        title="Forecast trajectory: daily average output up to your selected date",
        xaxis_title="Date", yaxis_title="Average kW",
        height=300, template="plotly_white", margin=dict(t=50, b=30),
    )
    st.plotly_chart(fig_traj, use_container_width=True)

    # --- Drivers panel ---
    st.subheader("What's driving this forecast?")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric(
        "Weather temperature", f"{t['temperature_C'].mean():.1f} \u00b0C",
        f"{t['temperature_C'].min():.0f} to {t['temperature_C'].max():.0f} \u00b0C range",
    )
    d2.metric("Wind speed (avg)", f"{t['wind_speed_ms'].mean():.1f} m/s")
    d3.metric("Solar radiation (avg)", f"{t['global_radiation_Wm2'].mean():.0f} W/m\u00b2")
    trend_word = ("rising" if t["p1_trend_24h"].mean() > 0
                   else "falling" if t["p1_trend_24h"].mean() < 0 else "stable")
    d4.metric("Basis: previous day's output", f"{t['p1_lag_24h'].mean():.0f} kW",
              f"{trend_word} trend")
    if t_result["weather_source"] == "climatology":
        st.caption("Note: temperature/wind/radiation above are **historical "
                   "averages for this time of year**, not a real forecast.")

    # --- Accuracy caveat from backtested validation ---
    try:
        bt = pd.read_csv("output/test_predictions_without_pegel.csv")
        bt_mae = mean_absolute_error(bt["actual"], bt["model_pred"])
        bt_note = f"typically within **~{bt_mae:.0f} kW** of the actual output for **1-day-ahead** forecasts"
    except FileNotFoundError:
        bt_note = "validated separately - see Historical Validation below"

    st.info(
        "**How accurate is this?** We can't check this forecast against "
        f"reality yet. Based on past validation, our 1-day-ahead forecasts "
        f"were {bt_note}. Accuracy is expected to **decrease for dates "
        "further ahead**, especially once climatology-based weather is "
        "used. See **Historical Validation** below for the proven, "
        "1-day-ahead numbers."
    )

st.divider()

# ============================================================
# SECTION 2 - Historical validation
# ============================================================
st.header("Historical Validation")
st.caption("Pick a past day to see the forecast we'd have produced for it, "
           "compared to what actually happened.")

try:
    df = pd.read_csv("data/features_with_pegel.csv", parse_dates=["from", "to"])
    bundle = joblib.load("output/model_with_pegel.pkl")
except FileNotFoundError as e:
    st.warning(
        f"Missing file: {e.filename}\n\n"
        "Run the full pipeline (03_feature_engineering.py, "
        "05_add_pegel_data.py, 04_train_model.py with USE_PEGEL = True) "
        "to enable this section."
    )
    df = None

if df is not None:
    df = df[~df[f"{TARGET}_maintenance"]].reset_index(drop=True)
    model, feature_cols = bundle["model"], bundle["feature_cols"]

    day_counts = df.groupby(df["from"].dt.date).size()
    full_dates = sorted(day_counts[day_counts == 96].index)

    selected_date = st.selectbox(
        "Select a day",
        options=full_dates, index=len(full_dates) - 1,
        format_func=lambda d: d.strftime("%A, %d %B %Y"),
    )

    day_df = df[df["from"].dt.date == selected_date].sort_values("from").reset_index(drop=True)
    X = day_df[feature_cols]
    baseline = day_df[f"{PREFIX}_lag_24h"]
    forecast = (baseline + model.predict(X)).clip(lower=0)
    actual = day_df[TARGET]
    time_labels = day_df["from"].dt.strftime("%H:%M")

    mae_model = (forecast - actual).abs().mean()
    mae_baseline = (baseline - actual).abs().mean()

    col1, col2, col3 = st.columns(3)
    col1.metric("This day's forecast MAE", f"{mae_model:.1f} kW")
    col2.metric("Naive 'same as yesterday' MAE", f"{mae_baseline:.1f} kW")
    better = mae_model < mae_baseline
    col3.metric("Result", "Forecast better" if better else "About the same",
                f"{(1 - mae_model / mae_baseline) * 100:+.1f}%")

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=time_labels, y=actual, name="Actual",
                               line=dict(color="#2ca02c", width=2)))
    fig2.add_trace(go.Scatter(x=time_labels, y=forecast, name="Forecast",
                               line=dict(color="#1f77b4", width=3)))
    fig2.add_trace(go.Scatter(x=time_labels, y=baseline, name="If that day = previous day",
                               line=dict(color="gray", width=1.5, dash="dash")))
    fig2.update_layout(
        title=f"{selected_date.strftime('%A, %d %B %Y')}: forecast vs. actual",
        xaxis_title="Time of day", yaxis_title="Power output (kW)",
        height=420, template="plotly_white",
        legend=dict(orientation="h", y=-0.25), margin=dict(t=60, b=40),
    )
    fig2.update_xaxes(tickmode="array", tickvals=time_labels[::8], tickangle=45)
    st.plotly_chart(fig2, use_container_width=True)

    with st.expander("Why does adding water-level data help? (feature importance)"):
        c1, c2 = st.columns(2)
        try:
            c1.image("output/06_feature_importance_without_pegel.png",
                     caption="Without water-level data")
            c2.image("output/06_feature_importance_with_pegel.png",
                     caption="With water-level data")
        except Exception:
            st.write("Run 04_train_model.py with both USE_PEGEL settings to "
                     "generate these plots.")