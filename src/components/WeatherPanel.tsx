import { Droplets, Thermometer, Waves, CloudRain } from "lucide-react";
import type { WeatherForecast } from "../types/forecast";
import { fmtFlow, fmtPercent } from "../lib/format";

interface Props {
  weather: WeatherForecast;
}

interface ItemProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  unit: string;
  accentColor?: string;
}

function WeatherItem({ icon, label, value, unit, accentColor = "#3B82F6" }: ItemProps) {
  return (
    <div
      className="flex items-center gap-3 rounded-xl p-3 cursor-default"
      style={{ backgroundColor: "#F8FAFC", border: "1px solid #E2E8F0" }}
    >
      <div
        className="flex items-center justify-center rounded-lg"
        style={{
          width: 36,
          height: 36,
          backgroundColor: `${accentColor}18`,
          color: accentColor,
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
      <div className="flex flex-col gap-0.5 min-w-0">
        <span
          style={{
            fontSize: 11,
            color: "#64748B",
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          {label}
        </span>
        <div className="flex items-baseline gap-1">
          <span
            className="mono"
            style={{ fontSize: 20, fontWeight: 700, color: "#0F172A", lineHeight: 1.1 }}
          >
            {value}
          </span>
          <span style={{ fontSize: 12, color: "#64748B" }}>{unit}</span>
        </div>
      </div>
    </div>
  );
}

export default function WeatherPanel({ weather }: Props) {
  return (
    <div
      className="rounded-2xl"
      style={{
        backgroundColor: "#FFFFFF",
        border: "1px solid #E2E8F0",
        padding: "1rem 1.25rem",
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      <h2 style={{ margin: "0 0 4px", fontSize: 14, fontWeight: 600, color: "#0F172A" }}>
        Umweltfaktoren
      </h2>
      <p style={{ margin: "0 0 14px", fontSize: 12, color: "#64748B" }}>
        Prognose Folgetag
      </p>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        <WeatherItem
          icon={<Droplets size={17} strokeWidth={2} />}
          label="Niederschlag"
          value={weather.precipitationMm.toLocaleString("de-DE", { maximumFractionDigits: 1 })}
          unit="mm"
          accentColor="#3B82F6"
        />
        <WeatherItem
          icon={<Thermometer size={17} strokeWidth={2} />}
          label="Temperatur"
          value={weather.temperatureC.toLocaleString("de-DE", { maximumFractionDigits: 1 })}
          unit="°C"
          accentColor="#F59E0B"
        />
        <WeatherItem
          icon={<Waves size={17} strokeWidth={2} />}
          label="Pegelstand"
          value={fmtFlow(weather.riverFlowM3s)}
          unit="m³/s"
          accentColor="#1D9E75"
        />
        <WeatherItem
          icon={<CloudRain size={17} strokeWidth={2} />}
          label="Regenwahrsch."
          value={fmtPercent(weather.precipProbability * 100, 0)}
          unit="%"
          accentColor="#8B5CF6"
        />
      </div>
    </div>
  );
}
