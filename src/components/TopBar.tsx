import { useState, useEffect } from "react";
import { Zap } from "lucide-react";
import { fmtDate } from "../lib/format";

interface Props {
  forecastDate: string;
}

export default function TopBar({ forecastDate }: Props) {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const clock = now.toLocaleTimeString("de-DE", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  return (
    <header
      style={{
        backgroundColor: "#FFFFFF",
        borderBottom: "1px solid #E2E8F0",
        boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
      }}
      className="sticky top-0 z-50"
    >
      <div
        className="flex items-center justify-between px-5 py-3"
        style={{ maxWidth: "1600px", margin: "0 auto" }}
      >
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div
            className="flex items-center justify-center"
            style={{
              width: 38,
              height: 38,
              background: "linear-gradient(140deg, #1D9E75 0%, #0D6B4E 100%)",
              borderRadius: 10,
              boxShadow: "0 2px 10px rgba(29, 158, 117, 0.25), inset 0 1px 0 rgba(255,255,255,0.15)",
              flexShrink: 0,
            }}
          >
            <Zap size={19} color="#fff" strokeWidth={2.5} />
          </div>
          <div>
            <span
              style={{ fontSize: 17, fontWeight: 700, color: "#0F172A", letterSpacing: "-0.02em" }}
            >
              WattsUp
            </span>
            <span
              className="hidden sm:inline"
              style={{ marginLeft: 8, fontSize: 12, color: "#64748B", fontWeight: 400 }}
            >
              Stadtwerke Jena · Wasserkraftprognose
            </span>
          </div>
        </div>

        {/* Right: clock + date + live badge */}
        <div className="flex items-center gap-5">
          <div className="hidden md:flex flex-col items-end gap-0.5">
            <span
              className="mono"
              style={{ fontSize: 15, fontWeight: 600, color: "#0F172A", letterSpacing: "0.04em" }}
            >
              {clock}
            </span>
            <span style={{ fontSize: 11, color: "#64748B" }}>
              {fmtDate(forecastDate)}
            </span>
          </div>

          <div
            className="flex items-center gap-1.5 rounded-full px-3 py-1.5"
            style={{
              backgroundColor: "#ECFDF5",
              border: "1px solid #6EE7B7",
            }}
          >
            <span
              className="live-dot"
              style={{
                width: 7,
                height: 7,
                backgroundColor: "#1D9E75",
                display: "inline-block",
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: "#1D9E75",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              Live
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
