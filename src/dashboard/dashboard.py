"""
WattsUp - Final Pitch Dashboard (Rescue Mode)
Run: streamlit run src/dashboard/dashboard.py
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sklearn.ensemble import RandomForestRegressor
import os

# ==========================================
# FILE PATHS (Point these to your CSV files)
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))

BURGAU_PATH = os.path.join(project_root, "data", "preprocessed", "upstream_burgau_final.csv")
UNTER_PATH = os.path.join(project_root, "data", "preprocessed", "upstream_unterpreilipp_final.csv")

st.set_page_config(page_title="WattsUp - Hydropower Forecast", layout="wide")
st.title("⚡ WattsUp: Next-Day Hydropower Forecast")
st.caption("Stadtwerke Jena - Saale River Hydropower Prediction")

# --- 1. Sidebar: Select Location ---
st.sidebar.header("1. Select Power Plant")
plant_choice = st.sidebar.radio("Choose the hydropower location:", ("Burgau (Jena)", "Unterpreilipp (Rudolstadt)"))

ACTIVE_PATH = BURGAU_PATH if plant_choice == "Burgau (Jena)" else UNTER_PATH
TARGET_COL = "power_burgau" if plant_choice == "Burgau (Jena)" else "power_rudolstadt"

# --- 2. Load Data ---
@st.cache_data
def load_data(filepath):
    # Fallback to local directory if project root fails
    if not os.path.exists(filepath):
        filepath = os.path.basename(filepath)
        if not os.path.exists(filepath):
            st.error(f"⚠️ Cannot find {filepath}. Put the CSV files right next to this script or in the root folder!")
            st.stop()
            
    df = pd.read_csv(filepath)
    df['time'] = pd.to_datetime(df['time']).dt.tz_localize(None) # Strip timezones
    return df.sort_values('time').dropna().reset_index(drop=True)

df = load_data(ACTIVE_PATH)

# --- 3. Sidebar: Select Dates ---
st.sidebar.header("2. Forecast Settings")
df['date'] = df['time'].dt.date
valid_dates = sorted(df['date'].unique())

cutoff_date = st.sidebar.selectbox(
    "Select Cut-off Date (Today):",
    options=valid_dates[:-1], 
    index=len(valid_dates) - 2 if len(valid_dates) > 1 else 0
)

target_date = cutoff_date + pd.Timedelta(days=1)

# --- 4. Split Data & Train Model ON-THE-FLY ---
train_df = df[df['date'] <= cutoff_date]
target_df = df[df['date'] == target_date]

if target_df.empty:
    st.warning("No future data available to verify prediction for this date.")
    st.stop()

# Feature Engineering
feature_cols = [col for col in df.columns if col not in ['time', 'date', TARGET_COL]]
X_train = train_df[feature_cols]
y_train = train_df[TARGET_COL]

# Fast AI Training
with st.spinner("Initializing AI Model..."):
    model = RandomForestRegressor(n_estimators=50, random_state=42)
    model.fit(X_train, y_train)

# Predict
X_target = target_df[feature_cols]
forecast = model.predict(X_target)
forecast = [max(0, val) for val in forecast] # No negative power

# --- 5. Visualization ---
st.markdown(f"### 📊 24-Hour Forecast for {target_date.strftime('%A, %d %b %Y')} ({plant_choice})")

history_df = train_df[train_df['date'] == cutoff_date].copy()
history_df["Moving_Avg"] = history_df[TARGET_COL].rolling(window=16, min_periods=1).mean()

fig = go.Figure()
# History
fig.add_trace(go.Scatter(x=history_df["time"], y=history_df[TARGET_COL], name="Actual (Cut-off Day)", line=dict(color="#2ca02c", width=2)))
fig.add_trace(go.Scatter(x=history_df["time"], y=history_df["Moving_Avg"], name="Moving Avg (Trend)", line=dict(color="rgba(44, 160, 44, 0.4)", width=2, dash="dot")))
# Future
fig.add_trace(go.Scatter(x=target_df["time"], y=target_df[TARGET_COL], name="Actual (Next Day)", line=dict(color="#2ca02c", width=2)))
fig.add_trace(go.Scatter(x=target_df["time"], y=forecast, name="AI Prediction", line=dict(color="#1f77b4", width=3)))

# Divider
midnight = target_df["time"].iloc[0]
fig.add_vline(x=midnight, line_width=2, line_dash="dash", line_color="red")
fig.add_annotation(x=midnight, y=max(target_df[TARGET_COL].max(), max(forecast)), text="Start of Forecast ->", showarrow=False, xanchor="left", font=dict(color="red"))

fig.update_layout(xaxis_title="Time of Day", yaxis_title="Power Output (kW)", height=450, template="plotly_white", legend=dict(orientation="h", y=-0.2), margin=dict(t=10, b=40), hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

# --- 6. Explainability ---
st.divider()
st.subheader("🧠 What is driving this prediction?")
importances = model.feature_importances_
feat_df = pd.DataFrame({"Feature": feature_cols, "Importance": importances}).sort_values(by="Importance", ascending=True).tail(10)

fig_feat = go.Figure(go.Bar(x=feat_df["Importance"], y=feat_df["Feature"], orientation='h', marker=dict(color="#ff7f0e")))
fig_feat.update_layout(title="Top Drivers for Power Prediction", xaxis_title="Relative Importance", yaxis_title="Data Feature", height=300, template="plotly_white", margin=dict(l=10, r=20, t=40, b=10))
st.plotly_chart(fig_feat, use_container_width=True)