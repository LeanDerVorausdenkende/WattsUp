import { TrendingUp, TrendingDown, Zap, ArrowUp, ArrowDown } from "lucide-react";
import type { DailyMetrics, ForecastPoint } from "../types/forecast";
import { fmtMwh, fmtDelta, fmtKw } from "../lib/format";

interface Props {
  metrics: DailyMetrics;
  totalForecast: ForecastPoint[];
}

interface CardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  unit: string;
  sub?: React.ReactNode;
  accentColor?: string;
}

function Card({ icon, label, value, unit, sub, accentColor = "#1D9E75" }: CardProps) {
  return (
    <div
      className="rounded-2xl flex flex-col gap-3 cursor-default"
      style={{
        backgroundColor: "#FFFFFF",
        border: "1px solid #E2E8F0",
        padding: "1.125rem 1.25rem",
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      <div className="flex items-center justify-between">
        <span
          style={{
            fontSize: 11,
            color: "#64748B",
            fontWeight: 600,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
          }}
        >
          {label}
        </span>
        <div
          className="flex items-center justify-center rounded-lg"
          style={{
            width: 30,
            height: 30,
            backgroundColor: `${accentColor}18`,
            color: accentColor,
            flexShrink: 0,
          }}
        >
          {icon}
        </div>
      </div>

      <div className="flex items-baseline gap-1.5">
        <span
          className="mono"
          style={{ fontSize: 30, fontWeight: 700, color: "#0F172A", lineHeight: 1.0 }}
        >
          {value}
        </span>
        <span style={{ fontSize: 13, color: "#64748B", fontWeight: 400 }}>{unit}</span>
      </div>

      {sub && <div style={{ fontSize: 12, color: "#64748B" }}>{sub}</div>}
    </div>
  );
}

export default function StatsBar({ metrics, totalForecast }: Props) {
  const future = totalForecast.filter((p) => p.actualKw === undefined);
  const vals = future.map((p) => p.predictedKw);

  const avg = vals.length ? Math.round(vals.reduce((s, v) => s + v, 0) / vals.length) : 0;
  const peak = vals.length ? Math.round(Math.max(...vals)) : 0;
  const low = vals.length ? Math.round(Math.min(...vals)) : 0;

  const isPositive = metrics.deltaVsYesterdayPct >= 0;
  const deltaColor = isPositive ? "#1D9E75" : "#EF4444";

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <Card
        icon={<Zap size={15} strokeWidth={2.5} />}
        label="Ø Erzeugung"
        value={fmtKw(avg, 0)}
        unit="kW"
        accentColor="#1D9E75"
        sub="Ø nächste 24 h"
      />
      <Card
        icon={<ArrowUp size={15} strokeWidth={2.5} />}
        label="Peak"
        value={fmtKw(peak, 0)}
        unit="kW"
        accentColor="#F59E0B"
        sub="Tagesmaximum"
      />
      <Card
        icon={<ArrowDown size={15} strokeWidth={2.5} />}
        label="Low"
        value={fmtKw(low, 0)}
        unit="kW"
        accentColor="#64748B"
        sub="Tagesminimum"
      />
      <Card
        icon={<Zap size={15} strokeWidth={2.5} />}
        label="24 h-Energie"
        value={fmtMwh(metrics.forecastMwh)}
        unit="MWh"
        accentColor="#1D9E75"
        sub={
          <span className="flex items-center gap-1" style={{ color: deltaColor, fontWeight: 600 }}>
            {isPositive
              ? <TrendingUp size={12} strokeWidth={2.5} />
              : <TrendingDown size={12} strokeWidth={2.5} />}
            {fmtDelta(metrics.deltaVsYesterdayPct)} gg. gestern
          </span>
        }
      />
    </div>
  );
}
