import type { DashboardData } from "../types/forecast";
import { generateMockDashboardData } from "./mockForecast";

const DATA_SOURCE: "mock" | "csv" | "api" = "mock";

export async function loadDashboardData(): Promise<DashboardData> {
  switch (DATA_SOURCE) {
    case "mock":
      return generateMockDashboardData();

    case "csv":
      // TODO ML-Team: CSV aus /public/data/forecast.csv parsen
      // return await loadFromCsv("/data/forecast.csv");
      throw new Error("CSV loader not implemented yet");

    case "api":
      // TODO ML-Team: Echten Endpoint aufrufen
      // const res = await fetch("/api/forecast/latest");
      // return await res.json();
      throw new Error("API loader not implemented yet");
  }
}

// Erwartetes CSV-Format:
// timestamp,plant_id,predicted_kw,conf_lower,conf_upper,actual_kw
export async function loadFromCsv(_path: string): Promise<DashboardData> {
  // TODO: Papa Parse o.ä. nutzen, dann nach plant_id gruppieren
  throw new Error("Implement CSV parsing here");
}
