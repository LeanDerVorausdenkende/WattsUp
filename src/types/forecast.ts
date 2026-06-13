export interface ForecastPoint {
  timestamp: string;
  predictedKw: number;
  confidenceLower: number;
  confidenceUpper: number;
  actualKw?: number;
}

export interface PlantForecast {
  plantId: string;
  points: ForecastPoint[];
}

export interface Plant {
  id: string;
  name: string;
  installedKw: number;
  currentKw: number;
  modelConfidence: number;
}

export interface WeatherForecast {
  date: string;
  precipitationMm: number;
  temperatureC: number;
  riverFlowM3s: number;
  precipProbability: number;
}

export interface DailyMetrics {
  forecastMwh: number;
  avgFlowM3s: number;
  modelMaePercent: number;
  plantsActive: number;
  plantsTotal: number;
  deltaVsYesterdayPct: number;
}

export interface DashboardData {
  forecastDate: string;
  metrics: DailyMetrics;
  forecast: PlantForecast[];
  totalForecast: ForecastPoint[];
  plants: Plant[];
  weather: WeatherForecast;
}
