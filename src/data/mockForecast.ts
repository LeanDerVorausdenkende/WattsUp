import type { DashboardData, ForecastPoint, PlantForecast } from "../types/forecast";

const PLANTS = [
  { id: "burgau",     name: "KW Burgau",     installedKw: 320, scale: 1.0,  confidence: 0.91 },
  { id: "rudolstadt", name: "KW Rudolstadt", installedKw: 200, scale: 0.62, confidence: 0.87 },
];

function floorTo15Min(d: Date): Date {
  const ms = 15 * 60 * 1000;
  return new Date(Math.floor(d.getTime() / ms) * ms);
}

const PAST_SLOTS   = 12;  // 3 h × 4 slots/h
const FUTURE_SLOTS = 96;  // 24 h × 4 slots/h
const TOTAL_SLOTS  = PAST_SLOTS + FUTURE_SLOTS;

function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    return (s >>> 0) / 0xffffffff;
  };
}

function makeDayProfile(
  scale: number,
  rng: () => number,
  startTime: Date,
  slots: number,
): number[] {
  return Array.from({ length: slots }, (_, i) => {
    const t = new Date(startTime.getTime() + i * 15 * 60 * 1000);
    const hour = t.getHours() + t.getMinutes() / 60;
    const base =
      scale *
      (40 +
        80 * Math.max(0, Math.sin(((hour - 5) * Math.PI) / 14)) +
        30 * Math.max(0, Math.sin(((hour - 10) * Math.PI) / 8)));
    const noise = (rng() - 0.5) * 12 * scale;
    return Math.max(5, base + noise);
  });
}

function makePlantForecast(
  plantId: string,
  scale: number,
  now: Date,
  rng: () => number,
): PlantForecast {
  const startTime = new Date(floorTo15Min(now).getTime() - PAST_SLOTS * 15 * 60 * 1000);
  const profile = makeDayProfile(scale, rng, startTime, TOTAL_SLOTS);

  const points: ForecastPoint[] = profile.map((predicted, i) => {
    const ts = new Date(startTime.getTime() + i * 15 * 60 * 1000);
    const band = 15 + rng() * 10;
    const point: ForecastPoint = {
      timestamp: ts.toISOString(),
      predictedKw: Math.round(predicted * 10) / 10,
      confidenceLower: Math.round((predicted - band) * 10) / 10,
      confidenceUpper: Math.round((predicted + band) * 10) / 10,
    };
    if (i < PAST_SLOTS) {
      const drift = (rng() - 0.5) * 0.18 * predicted;
      point.actualKw = Math.round((predicted + drift) * 10) / 10;
    }
    return point;
  });

  return { plantId, points };
}

export function generateMockDashboardData(): DashboardData {
  const now = new Date();
  const forecastDate = now.toISOString().slice(0, 10);
  const rng = seededRandom(parseInt(forecastDate.replace(/-/g, ""), 10));

  const forecast = PLANTS.map((p) => makePlantForecast(p.id, p.scale, now, rng));

  const totalForecast: ForecastPoint[] = forecast[0].points.map((_, i) => {
    const pts = forecast.map((pf) => pf.points[i]);
    const predicted = pts.reduce((s, p) => s + p.predictedKw, 0);
    const lower = pts.reduce((s, p) => s + p.confidenceLower, 0);
    const upper = pts.reduce((s, p) => s + p.confidenceUpper, 0);
    const actuals = pts.filter((p) => p.actualKw !== undefined);
    const result: ForecastPoint = {
      timestamp: pts[0].timestamp,
      predictedKw: Math.round(predicted * 10) / 10,
      confidenceLower: Math.round(lower * 10) / 10,
      confidenceUpper: Math.round(upper * 10) / 10,
    };
    if (actuals.length === pts.length) {
      result.actualKw = Math.round(
        actuals.reduce((s, p) => s + (p.actualKw ?? 0), 0) * 10,
      ) / 10;
    }
    return result;
  });

  const forecastMwh =
    Math.round(
      (totalForecast.slice(PAST_SLOTS).reduce((s, p) => s + p.predictedKw, 0) * 0.25) / 100,
    ) / 10;

  const plants = PLANTS.map((p) => {
    const pf = forecast.find((f) => f.plantId === p.id)!;
    const current = pf.points[PAST_SLOTS]?.predictedKw ?? pf.points[0].predictedKw;
    return {
      id: p.id,
      name: p.name,
      installedKw: p.installedKw,
      currentKw: Math.round(current),
      modelConfidence: p.confidence,
    };
  });

  return {
    forecastDate,
    metrics: {
      forecastMwh,
      avgFlowM3s: 28.4 + (rng() - 0.5) * 4,
      modelMaePercent: 3.8 + rng() * 2,
      plantsActive: 2,
      plantsTotal: 2,
      deltaVsYesterdayPct: (rng() - 0.45) * 18,
    },
    forecast,
    totalForecast,
    plants,
    weather: {
      date: forecastDate,
      precipitationMm: Math.round(rng() * 12 * 10) / 10,
      temperatureC: Math.round((14 + rng() * 8) * 10) / 10,
      riverFlowM3s: Math.round((26 + rng() * 8) * 10) / 10,
      precipProbability: Math.round(rng() * 100) / 100,
    },
  };
}
