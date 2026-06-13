export function fmtKw(kw: number, decimals = 0): string {
  return kw.toLocaleString("de-DE", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function fmtMwh(mwh: number): string {
  return mwh.toLocaleString("de-DE", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

export function fmtFlow(m3s: number): string {
  return m3s.toLocaleString("de-DE", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

export function fmtPercent(pct: number, decimals = 1): string {
  return pct.toLocaleString("de-DE", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function fmtTime(isoString: string): string {
  const d = new Date(isoString);
  return d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}

export function fmtDate(isoDate: string): string {
  const d = new Date(isoDate + "T12:00:00");
  return d.toLocaleDateString("de-DE", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function fmtDelta(pct: number): string {
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${fmtPercent(pct)} %`;
}
