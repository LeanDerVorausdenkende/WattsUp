# ⚡ WattsUp: Smart Forecasts for Hydropower

**Hack the Paradise! 2026 – Stadtwerke Jena Challenge** **Team:** LeanDerVorausdenkende  

## 📖 Overview
The "WattsUp" challenge, provided by Stadtwerke Energie Jena-Pößneck, asked for an intelligent solution to predict the electricity generation of hydropower plants. Because renewable energy relies heavily on weather and environmental factors, accurate 24-hour predictions are critical for ensuring grid stability and fair cost distribution.

Our team built an end-to-end Machine Learning pipeline and a **production-ready Streamlit Dashboard** that allows grid operators to visualize historical trends, predict next-day power output, and understand the "why" behind the AI's decisions.

## ✨ Features
* **Dual-Plant Support:** Toggle seamlessly between the Burgau (Jena) and Unterpreilipp (Rudolstadt) hydropower plants.
* **"Time Travel" Forecasting:** Select any historical cut-off date to simulate a "Today" state, predicting the next 24 hours of power generation in 15-minute intervals.
* **Trend Analysis:** Automatically calculates and visualizes a 4-hour moving average of historical actuals to provide context leading up to the forecast launch.
* **Explainable AI (XAI):** Extracts and graphs the model's feature importance (e.g., water flow vs. temperature) so the AI is never a "black box."
* **On-The-Fly Training:** Engineered with a resilient fallback mode that trains a Random Forest algorithm in seconds if pre-compiled model artifacts are missing.

---

## 📂 Project Structure

```text
WattsUp/
│
├── data/
│   └── preprocessed/
│       ├── upstream_burgau_final.csv         # Merged weather/water/power data (Burgau)
│       └── upstream_unterpreilipp_final.csv  # Merged weather/water/power data (Unterpreilipp)
│
├── model/
│   └── model_random_forest_quick.joblib      # Compiled ML model (if applicable)
│
├── src/
│   └── dashboard/
│       ├── dashboard.py                      # Main Streamlit application
│       └── serve.py                          # ML API wrapper (metadata handling)
│
└── README.md
🚀 Quickstart & Installation
To run this dashboard locally, ensure you have Python 3.9+ installed.

1. Clone the Repository
Bash
git clone [https://github.com/LeanDerVorausdenkende/WattsUp.git](https://github.com/LeanDerVorausdenkende/WattsUp.git)
cd WattsUp
2. Set Up a Virtual Environment (Recommended)
Bash
python -m venv venv

# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate
3. Install Dependencies
Make sure you have the required data science and UI libraries installed:

Bash
pip install pandas numpy scikit-learn plotly streamlit joblib
4. Run the Dashboard
Execute the following command from the root directory of the project:

Bash
streamlit run src/dashboard/dashboard.py
The dashboard will automatically open in your default web browser at http://localhost:8501.

🛠️ Technical Details & "Hackathon Magic"
During the final hours of the hackathon, we encountered deployment challenges when merging the Data Science team's .joblib model with the UI team's Streamlit application due to missing local module dependencies (src.forecast.models).

To ensure a robust, fail-safe presentation, we implemented a Rescue Mode Architecture inside dashboard.py:

Dynamic Pathing: The dashboard uses Python's os and sys modules to automatically locate the project root, preventing hardcoded path crashes.

Ghost Module Spoofing: We bypassed serialization errors by spoofing the missing ML environments directly in the sys.modules dictionary.

On-the-Fly ML: If the .joblib model fails to load, the dashboard automatically falls back to training a RandomForestRegressor(n_estimators=50) directly on the preprocessed CSV data in memory, taking < 3 seconds to guarantee a working prediction for the judges.

🚑 Git Troubleshooting (How we deployed)
If you are contributing to this project and encounter unresolvable merge conflicts when trying to push your final local version to GitHub, you can force the remote repository to match your local state using the following commands:

Bash
# 1. Abort any stuck merges
git merge --abort

# 2. Stage all local files
git add .

# 3. Commit your final version
git commit -m "Final Working Prototype"

# 4. Force push to overwrite the remote branch (Use with caution!)
git push -f origin main
Built with ❤️ and ☕ in Jena, Germany at Hack the Paradise! 2026