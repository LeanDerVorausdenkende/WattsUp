import type { Plant } from "../types/forecast";
import { fmtPercent } from "../lib/format";

interface Props {
  plants: Plant[];
}

function confidenceColor(conf: number): { bar: string; bg: string; text: string } {
  if (conf >= 0.85)
    return { bar: "#1D9E75", bg: "#EAF3DE", text: "#1D9E75" };
  if (conf >= 0.7)
    return { bar: "#EF9F27", bg: "#FEF3E2", text: "#C47D0A" };
  return { bar: "#E24B4A", bg: "#FDEEED", text: "#C02020" };
}

function confidenceLabel(conf: number): string {
  if (conf >= 0.85) return "Hoch";
  if (conf >= 0.7) return "Mittel";
  return "Niedrig";
}

export default function ConfidencePanel({ plants }: Props) {
  return (
    <div
      className="rounded-xl"
      style={{
        backgroundColor: "#ffffff",
        border: "1px solid #E5E5E0",
        padding: "1rem 1.25rem",
      }}
    >
      <h2
        style={{
          margin: "0 0 4px",
          fontSize: 14,
          fontWeight: 600,
          color: "#1A1A1A",
        }}
      >
        Modell-Konfidenz
      </h2>
      <p style={{ margin: "0 0 16px", fontSize: 12, color: "#6B6B66" }}>
        Je Anlage · Grün ≥ 85 % · Gelb ≥ 70 % · Rot &lt; 70 %
      </p>

      <div className="flex flex-col gap-4">
        {plants.map((plant) => {
          const colors = confidenceColor(plant.modelConfidence);
          const pct = plant.modelConfidence * 100;
          return (
            <div key={plant.id}>
              <div className="flex justify-between items-center mb-1.5">
                <span
                  style={{ fontSize: 13, fontWeight: 500, color: "#1A1A1A" }}
                >
                  {plant.name}
                </span>
                <div className="flex items-center gap-2">
                  <span
                    className="tabular"
                    style={{ fontSize: 13, fontWeight: 700, color: colors.text }}
                  >
                    {fmtPercent(pct, 0)} %
                  </span>
                  <span
                    className="rounded-full px-2 py-0.5"
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      backgroundColor: colors.bg,
                      color: colors.text,
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                    }}
                  >
                    {confidenceLabel(plant.modelConfidence)}
                  </span>
                </div>
              </div>
              <div
                className="rounded-full overflow-hidden"
                style={{ height: 6, backgroundColor: "#F0F0EC" }}
              >
                <div
                  className="rounded-full"
                  style={{
                    width: `${pct}%`,
                    height: "100%",
                    backgroundColor: colors.bar,
                    transition: "width 0.6s ease",
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
