import { useEffect, useState } from "react";
import type { DashboardData } from "./types/forecast";
import { loadDashboardData } from "./data/dataAdapter";
import TopBar from "./components/TopBar";
import StatsBar from "./components/StatsBar";
import ForecastChart from "./components/ForecastChart";
import PlantsList from "./components/PlantsList";
import WeatherPanel from "./components/WeatherPanel";

export default function App() {
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    loadDashboardData().then(setData).catch(console.error);
  }, []);

  if (!data) {
    return (
      <div
        style={{
          minHeight: "100dvh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#F1F5F9",
          color: "#64748B",
          fontSize: 14,
          gap: 10,
        }}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            backgroundColor: "#1D9E75",
            display: "inline-block",
            animation: "live-pulse 1.8s ease-in-out infinite",
          }}
        />
        Lade Prognosedaten…
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100dvh", backgroundColor: "#F1F5F9" }}>
      <TopBar forecastDate={data.forecastDate} />

      <main
        style={{
          maxWidth: 1600,
          margin: "0 auto",
          padding: "1.25rem 1.25rem 2.5rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.875rem",
        }}
      >
        <StatsBar metrics={data.metrics} totalForecast={data.totalForecast} />

        {/* Chart + plants sidebar */}
        <div
          style={{
            display: "grid",
            gap: "0.875rem",
            gridTemplateColumns: "1fr",
            alignItems: "start",
          }}
          className="lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]"
        >
          <ForecastChart
            totalForecast={data.totalForecast}
            plantForecasts={data.forecast}
            plants={data.plants}
          />
          <PlantsList plants={data.plants} />
        </div>

        {/* Weather panel */}
        <WeatherPanel weather={data.weather} />
      </main>
    </div>
  );
}
