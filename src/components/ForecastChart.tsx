import { useState } from "react";
import {
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ComposedChart,
  ReferenceArea,
} from "recharts";
import type { ForecastPoint, PlantForecast, Plant } from "../types/forecast";
import { fmtTime, fmtKw } from "../lib/format";

interface Props {
  totalForecast: ForecastPoint[];
  plantForecasts: PlantForecast[];
  plants: Plant[];
}

type TabId = "total" | string;

interface TooltipPayload {
  name: string;
  value: number;
  color: string;
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayload[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const visible = payload.filter(
    (p) => p.value !== undefined && p.value !== null && p.name !== "__upper" && p.name !== "__lower",
  );
  return (
    <div
      style={{
        backgroundColor: "#FFFFFF",
        border: "1px solid #E2E8F0",
        borderRadius: 10,
        padding: "10px 14px",
        fontSize: 12,
        boxShadow: "0 8px 24px rgba(0,0,0,0.1)",
        minWidth: 160,
      }}
    >
      <div style={{ fontWeight: 700, color: "#0F172A", marginBottom: 8 }}>{label}</div>
      {visible.map((p) => (
        <div
          key={p.name}
          className="tabular"
          style={{ display: "flex", justifyContent: "space-between", gap: 16, marginBottom: 3 }}
        >
          <span style={{ color: "#64748B" }}>{p.name}</span>
          <span style={{ fontWeight: 700, color: p.color }}>{fmtKw(p.value, 1)} kW</span>
        </div>
      ))}
    </div>
  );
}

const YAXIS_W = 52;
const MARGIN_RIGHT = 8;
const XAXIS_H = 30; // approx recharts XAxis height
const MARGIN_TOP = 4;

export default function ForecastChart({ totalForecast, plantForecasts, plants }: Props) {
  const [tab, setTab] = useState<TabId>("total");
  const [chartWidth, setChartWidth] = useState(0);

  const activePoints =
    tab === "total"
      ? totalForecast
      : (plantForecasts.find((pf) => pf.plantId === tab)?.points ?? totalForecast);

  const activeLabel =
    tab === "total" ? "Alle Anlagen" : (plants.find((p) => p.id === tab)?.name ?? "");

  const data = activePoints.map((p) => {
    const isPast = p.actualKw !== undefined;
    return {
      time: fmtTime(p.timestamp),
      prognose: p.predictedKw,
      upper: isPast ? null : p.confidenceUpper,
      lower: isPast ? null : p.confidenceLower,
      istwert: p.actualKw ?? null,
    };
  });

  const nowIdx = data.findIndex((d) => d.istwert === null);
  const lastHistoryTime = nowIdx > 0 ? data[nowIdx - 1]?.time : undefined;


  // Pixel x for the boundary: left edge of band at nowIdx
  const nowX =
    chartWidth > 0 && nowIdx >= 0
      ? YAXIS_W + (nowIdx * (chartWidth - YAXIS_W - MARGIN_RIGHT)) / data.length
      : null;

  const tabs: Array<{ id: TabId; label: string }> = [
    { id: "total", label: "Gesamt" },
    ...plants.map((p) => ({ id: p.id, label: p.name })),
  ];

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
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h2 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: "#0F172A" }}>
            Erzeugungsprognose
          </h2>
          <p style={{ margin: 0, fontSize: 12, color: "#64748B" }}>
            {activeLabel} · −3 h Istwert + 24 h Prognose · 15-Min-Auflösung
          </p>
        </div>

        {/* Tab selector */}
        <div
          className="flex items-center gap-1 rounded-xl p-1"
          style={{ backgroundColor: "#F1F5F9", border: "1px solid #E2E8F0" }}
        >
          {tabs.map(({ id, label }) => {
            const active = tab === id;
            return (
              <button
                key={id}
                onClick={() => setTab(id)}
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: active ? "#0F172A" : "#64748B",
                  backgroundColor: active ? "#FFFFFF" : "transparent",
                  border: active ? "1px solid #E2E8F0" : "1px solid transparent",
                  borderRadius: 8,
                  padding: "4px 12px",
                  cursor: "pointer",
                  transition: "all 0.18s",
                  boxShadow: active ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
                  whiteSpace: "nowrap",
                }}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Legend chips */}
      <div className="flex items-center gap-4 mb-3" style={{ fontSize: 12 }}>
        <span className="flex items-center gap-1.5">
          <span style={{ display: "inline-block", width: 20, height: 2, backgroundColor: "#475569", verticalAlign: "middle" }} />
          <span style={{ color: "#64748B" }}>Istwert</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span style={{ display: "inline-block", width: 20, height: 2, backgroundColor: "#1D9E75", verticalAlign: "middle" }} />
          <span style={{ color: "#64748B" }}>Prognose</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span style={{ display: "inline-block", width: 14, height: 8, backgroundColor: "rgba(29,158,117,0.12)", border: "1px solid rgba(29,158,117,0.25)", borderRadius: 2, verticalAlign: "middle" }} />
          <span style={{ color: "#64748B" }}>Konfidenzband</span>
        </span>
      </div>

      {/* Chart + Jetzt overlay */}
      <div style={{ position: "relative" }}>
        <ResponsiveContainer
          width="100%"
          height={300}
          onResize={(w) => setChartWidth(w)}
        >
          <ComposedChart data={data} margin={{ top: MARGIN_TOP, right: MARGIN_RIGHT, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="confGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#1D9E75" stopOpacity={0.18} />
                <stop offset="100%" stopColor="#1D9E75" stopOpacity={0.0} />
              </linearGradient>
            </defs>

            {/* Historical region shading */}
            {lastHistoryTime && (
              <ReferenceArea
                x1={data[0]?.time}
                x2={lastHistoryTime}
                fill="rgba(100, 116, 139, 0.09)"
                strokeOpacity={0}
              />
            )}

            <CartesianGrid strokeDasharray="2 4" stroke="#F0F4F8" vertical={false} />

            <XAxis
              dataKey="time"
              interval={0}
              tickFormatter={(v: string) => v.endsWith(":00") ? v : ""}
              tick={{ fontSize: 11, fill: "#94A3B8" }}
              tickLine={false}
              axisLine={{ stroke: "#E2E8F0" }}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "#94A3B8" }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${fmtKw(v)}`}
              width={YAXIS_W}
            />

            <Tooltip content={<CustomTooltip />} />

            <Area
              type="monotone"
              dataKey="upper"
              stroke="none"
              fill="url(#confGrad)"
              legendType="none"
              name="__upper"
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="lower"
              stroke="none"
              fill="#FFFFFF"
              legendType="none"
              name="__lower"
              isAnimationActive={false}
            />

            <Line
              type="monotone"
              dataKey="prognose"
              name="Prognose"
              stroke="#1D9E75"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: "#1D9E75", strokeWidth: 0 }}
              isAnimationActive={false}
              legendType="none"
            />

            <Line
              type="monotone"
              dataKey="istwert"
              name="Istwert"
              stroke="#475569"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 3, fill: "#475569", strokeWidth: 0 }}
              connectNulls={false}
              isAnimationActive={false}
              legendType="none"
            />
          </ComposedChart>
        </ResponsiveContainer>

        {/* Jetzt divider — absolutely positioned HTML overlay */}
        {nowX !== null && (
          <div
            style={{
              position: "absolute",
              left: nowX,
              top: MARGIN_TOP,
              bottom: XAXIS_H,
              width: 2,
              backgroundColor: "#1D9E75",
              pointerEvents: "none",
              zIndex: 10,
            }}
          >
            <div
              style={{
                position: "absolute",
                top: 6,
                left: 5,
                backgroundColor: "#1D9E75",
                color: "#FFFFFF",
                fontSize: 10,
                fontWeight: 700,
                padding: "2px 7px",
                borderRadius: 4,
                whiteSpace: "nowrap",
                lineHeight: "16px",
                letterSpacing: "0.03em",
              }}
            >
              Jetzt
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
