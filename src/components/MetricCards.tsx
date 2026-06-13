import { Droplets, Activity, TrendingUp, TrendingDown, Zap, Gauge } from "lucide-react";
import type { DailyMetrics } from "../types/forecast";
import { fmtMwh, fmtFlow, fmtPercent, fmtDelta } from "../lib/format";

interface Props {
  metrics: DailyMetrics;
}

interface CardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  unit: string;
  sub?: React.ReactNode;
  accentColor?: string;
  delay?: number;
}

function Card({ icon, label, value, unit, sub, accentColor = "#1D9E75", delay = 0 }: CardProps) {
  return (
    <div
      className="count-up rounded-2xl flex flex-col gap-3 cursor-default"
      style={{
        backgroundColor: "#FFFFFF",
        border: "1px solid #E2E8F0",
        padding: "1.125rem 1.25rem",
        animationDelay: `${delay}ms`,
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

      {sub && (
        <div style={{ fontSize: 12, color: "#64748B" }}>{sub}</div>
      )}
    </div>
  );
}

export default function MetricCards({ metrics }: Props) {
  const isPositive = metrics.deltaVsYesterdayPct >= 0;
  const deltaColor = isPositive ? "#1D9E75" : "#EF4444";

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <Card
        icon={<Zap size={15} strokeWidth={2.5} />}
        label="Tagesprognose"
        value={fmtMwh(metrics.forecastMwh)}
        unit="MWh"
        accentColor="#1D9E75"
        sub={
          <span
            className="flex items-center gap-1"
            style={{ color: deltaColor, fontWeight: 600 }}
          >
            {isPositive
              ? <TrendingUp size={12} strokeWidth={2.5} />
              : <TrendingDown size={12} strokeWidth={2.5} />}
            {fmtDelta(metrics.deltaVsYesterdayPct)} gg. gestern
          </span>
        }
        delay={0}
      />
      <Card
        icon={<Droplets size={15} strokeWidth={2.5} />}
        label="Ø Durchfluss"
        value={fmtFlow(metrics.avgFlowM3s)}
        unit="m³/s"
        accentColor="#3B82F6"
        sub={<span>Saale-Pegel heute</span>}
        delay={60}
      />
      <Card
        icon={<Gauge size={15} strokeWidth={2.5} />}
        label="Modell-MAE"
        value={fmtPercent(metrics.modelMaePercent)}
        unit="%"
        accentColor="#F59E0B"
        sub={<span>Mean Absolute Error</span>}
        delay={120}
      />
      <Card
        icon={<Activity size={15} strokeWidth={2.5} />}
        label="Anlagen aktiv"
        value={`${metrics.plantsActive}`}
        unit={`/ ${metrics.plantsTotal}`}
        accentColor="#1D9E75"
        sub={<span>alle Anlagen im Normalbetrieb</span>}
        delay={180}
      />
    </div>
  );
}
