import type { Plant } from "../types/forecast";
import { fmtKw, fmtPercent } from "../lib/format";

interface Props {
  plants: Plant[];
}

function utilizationColor(ratio: number): string {
  if (ratio >= 0.75) return "#1D9E75";
  if (ratio >= 0.5) return "#22C594";
  if (ratio >= 0.3) return "#F59E0B";
  return "#EF4444";
}

function confidenceStyle(conf: number): { text: string; bg: string; label: string } {
  if (conf >= 0.85) return { text: "#1D9E75", bg: "#ECFDF5", label: "Hoch" };
  if (conf >= 0.7) return { text: "#B45309", bg: "#FFFBEB", label: "Mittel" };
  return { text: "#DC2626", bg: "#FEF2F2", label: "Niedrig" };
}

function Ring({
  value,
  max,
  size = 76,
  strokeWidth = 7,
  color,
}: {
  value: number;
  max: number;
  size?: number;
  strokeWidth?: number;
  color: string;
}) {
  const r = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * r;
  const pct = Math.min(1, Math.max(0, value / max));
  const offset = circumference * (1 - pct);
  const cx = size / 2;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      style={{ flexShrink: 0 }}
      aria-hidden="true"
    >
      {/* Track */}
      <circle
        cx={cx}
        cy={cx}
        r={r}
        fill="none"
        stroke="#E2E8F0"
        strokeWidth={strokeWidth}
      />
      {/* Progress */}
      <circle
        cx={cx}
        cy={cx}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${cx} ${cx})`}
        style={{ transition: "stroke-dashoffset 0.8s cubic-bezier(0.22,1,0.36,1)" }}
      />
      {/* Label */}
      <text
        x={cx}
        y={cx}
        textAnchor="middle"
        dominantBaseline="central"
        style={{
          fontSize: 14,
          fontWeight: 700,
          fill: color,
          fontVariantNumeric: "tabular-nums",
          fontFamily: "ui-monospace, monospace",
        }}
      >
        {Math.round(pct * 100)}%
      </text>
    </svg>
  );
}

export default function PlantsList({ plants }: Props) {
  const totalInstalled = plants.reduce((s, p) => s + p.installedKw, 0);
  const totalCurrent = plants.reduce((s, p) => s + p.currentKw, 0);

  return (
    <div
      className="rounded-2xl flex flex-col"
      style={{
        backgroundColor: "#FFFFFF",
        border: "1px solid #E2E8F0",
        padding: "1rem 1.25rem",
        height: "100%",
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      <h2 style={{ margin: "0 0 4px", fontSize: 14, fontWeight: 600, color: "#0F172A" }}>
        Anlagen
      </h2>
      <p style={{ margin: "0 0 14px", fontSize: 12, color: "#64748B" }}>
        Leistung · Auslastung · Konfidenz
      </p>

      <div className="flex flex-col gap-3 flex-1">
        {plants.map((plant) => {
          const ratio = plant.currentKw / plant.installedKw;
          const ringColor = utilizationColor(ratio);
          const conf = confidenceStyle(plant.modelConfidence);

          return (
            <div
              key={plant.id}
              className="rounded-xl p-3"
              style={{ backgroundColor: "#F8FAFC", border: "1px solid #E2E8F0" }}
            >
              {/* Name + status + confidence badge */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius: "50%",
                      backgroundColor: "#1D9E75",
                      boxShadow: "0 0 5px rgba(29, 158, 117, 0.5)",
                      flexShrink: 0,
                    }}
                  />
                  <span style={{ fontSize: 13, fontWeight: 600, color: "#0F172A" }}>
                    {plant.name}
                  </span>
                </div>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    color: conf.text,
                    backgroundColor: conf.bg,
                    borderRadius: 20,
                    padding: "2px 8px",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    whiteSpace: "nowrap",
                  }}
                >
                  {fmtPercent(plant.modelConfidence * 100, 0)} % · {conf.label}
                </span>
              </div>

              {/* Ring + values */}
              <div className="flex items-center gap-4">
                <Ring value={plant.currentKw} max={plant.installedKw} color={ringColor} />
                <div className="flex flex-col gap-1 flex-1 min-w-0">
                  <div className="flex items-baseline gap-1">
                    <span
                      className="mono"
                      style={{ fontSize: 26, fontWeight: 700, color: ringColor, lineHeight: 1.0 }}
                    >
                      {fmtKw(plant.currentKw)}
                    </span>
                    <span style={{ fontSize: 12, color: "#64748B" }}>kW</span>
                  </div>
                  <span style={{ fontSize: 11, color: "#64748B" }}>
                    Nennleistung: {fmtKw(plant.installedKw)} kW
                  </span>
                  {/* Progress bar */}
                  <div
                    className="rounded-full overflow-hidden mt-1.5"
                    style={{ height: 4, backgroundColor: "#E2E8F0" }}
                  >
                    <div
                      className="rounded-full"
                      style={{
                        width: `${Math.min(100, ratio * 100)}%`,
                        height: "100%",
                        backgroundColor: ringColor,
                        transition: "width 0.8s cubic-bezier(0.22,1,0.36,1)",
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Total row */}
      <div
        className="flex justify-between items-center mt-4 pt-3"
        style={{ borderTop: "1px solid #E2E8F0" }}
      >
        <span style={{ fontSize: 12, color: "#64748B", fontWeight: 500 }}>
          Gesamt-Kapazität
        </span>
        <div className="flex items-baseline gap-1">
          <span
            className="mono"
            style={{ fontSize: 14, fontWeight: 700, color: "#0F172A" }}
          >
            {fmtKw(totalCurrent)}
          </span>
          <span style={{ fontSize: 12, color: "#64748B" }}>
            / {fmtKw(totalInstalled)} kW
          </span>
        </div>
      </div>
    </div>
  );
}
