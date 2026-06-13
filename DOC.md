# WattsUp – Projektdokumentation

Echtzeit-Dashboard für die Wasserkraftprognose der Stadtwerke Jena.

---

## Inhaltsverzeichnis

1. [Überblick](#überblick)
2. [Tech-Stack](#tech-stack)
3. [Projektstruktur](#projektstruktur)
4. [Starten](#starten)
5. [Datenarchitektur](#datenarchitektur)
6. [Komponenten](#komponenten)
7. [Datenquelle wechseln](#datenquelle-wechseln)
8. [Anlagen hinzufügen / ändern](#anlagen-hinzufügen--ändern)

---

## Überblick

WattsUp zeigt die Erzeugungsprognose für die zwei Wasserkraftanlagen **KW Burgau** (320 kW) und **KW Rudolstadt** (200 kW) in einem interaktiven Dashboard:

- **−3 h Istwert** + **+24 h Prognose** in 15-Minuten-Auflösung
- Konfidenzband um die Prognose
- Visuelle Trennung von historischem Bereich und Vorhersage („Jetzt"-Linie)
- Kennzahlen-Cards: Ø Erzeugung, Peak, Low, 24 h-Energie
- Anlagen-Panel mit Auslastungsringen und Modell-Konfidenz
- Umweltfaktoren-Panel (Niederschlag, Temperatur, Pegelstand, Regenwahrsch.)
- Live-Uhr in der TopBar, Daten aktualisieren sich beim Seitenaufruf

---

## Tech-Stack

| Paket | Version | Zweck |
|---|---|---|
| React | 19 | UI-Framework |
| TypeScript | 6 | Typsicherheit |
| Vite | 8 | Build-Tool / Dev-Server |
| Tailwind CSS | v4 | Utility-CSS |
| Recharts | 3.8 | Diagramm-Bibliothek |
| lucide-react | 1.18 | Icons |

---

## Projektstruktur

```
wattsup3/
├── start.sh                        # Dev-Server starten
└── wattsup/
    └── src/
        ├── App.tsx                 # Root-Komponente, Layout
        ├── main.tsx                # React-Einstiegspunkt
        ├── index.css               # CSS-Variablen, Animationen
        ├── types/
        │   └── forecast.ts         # Alle TypeScript-Interfaces
        ├── lib/
        │   └── format.ts           # Formatierungsfunktionen (kW, MWh, …)
        ├── data/
        │   ├── dataAdapter.ts      # Datenquelle auswählen (mock / csv / api)
        │   └── mockForecast.ts     # Mock-Datengenerator
        └── components/
            ├── TopBar.tsx          # Header mit Live-Uhr
            ├── StatsBar.tsx        # Kennzahlen-Cards (Ø, Peak, Low, Energie)
            ├── ForecastChart.tsx   # Haupt-Prognose-Diagramm
            ├── PlantsList.tsx      # Anlagen-Panel mit Ring-Gauges
            └── WeatherPanel.tsx    # Umweltfaktoren
```

---

## Starten

```bash
./start.sh
```

Das Skript wechselt in `wattsup/`, installiert bei Bedarf `node_modules` und startet `vite dev`. Die App läuft dann auf [http://localhost:5173](http://localhost:5173).

Manuell:

```bash
cd wattsup
npm install
npm run dev
```

Produktions-Build:

```bash
cd wattsup
npm run build   # Output: wattsup/dist/
```

---

## Datenarchitektur

### Interfaces (`src/types/forecast.ts`)

```ts
ForecastPoint {
  timestamp: string        // ISO 8601
  predictedKw: number
  confidenceLower: number
  confidenceUpper: number
  actualKw?: number        // nur für vergangene Slots vorhanden
}

PlantForecast {
  plantId: string
  points: ForecastPoint[]  // 108 Punkte: 12 × Istwert + 96 × Prognose
}

Plant {
  id: string
  name: string
  installedKw: number
  currentKw: number
  modelConfidence: number  // 0–1
}

DashboardData {
  forecastDate: string
  metrics: DailyMetrics
  forecast: PlantForecast[]   // eine je Anlage
  totalForecast: ForecastPoint[]  // aggregiert über alle Anlagen
  plants: Plant[]
  weather: WeatherForecast
}
```

### Zeitfenster

| Bereich | Slots | Dauer |
|---|---|---|
| Istwert (Vergangenheit) | 12 | −3 h |
| Prognose (Zukunft) | 96 | +24 h |
| Gesamt | 108 | 27 h |

Alle Timestamps landen auf sauberen **:00 / :15 / :30 / :45**-Grenzen (`floorTo15Min`).

### Mock-Generator (`src/data/mockForecast.ts`)

Erzeugt realistische Tageskurven über ein sinusförmiges Tagesprofil (Peak ~12–14 Uhr) mit übergelagertem Rauschen. Der Seed basiert auf dem aktuellen Datum, sodass das Dashboard pro Tag konsistente Werte zeigt.

---

## Komponenten

### `TopBar`

Sticky Header. Zeigt Logo, Anwendungsname, Datum des Prognosetags und eine Live-Uhr (aktualisiert jede Sekunde per `setInterval`). „Live"-Badge mit animiertem Puls-Dot.

**Props:** `forecastDate: string`

---

### `StatsBar`

Vier Kennzahlen-Cards in einem responsiven Grid (`2 Spalten → 4 Spalten`).

| Card | Berechnung |
|---|---|
| Ø Erzeugung | Ø `predictedKw` über alle zukünftigen Slots |
| Peak | Max `predictedKw` über alle zukünftigen Slots |
| Low | Min `predictedKw` über alle zukünftigen Slots |
| 24 h-Energie | `metrics.forecastMwh` + Trend vs. Vortag |

**Props:** `metrics: DailyMetrics`, `totalForecast: ForecastPoint[]`

---

### `ForecastChart`

Das zentrale Diagramm. Wechselt per Tab zwischen **Gesamt**, **KW Burgau** und **KW Rudolstadt**.

**Aufbau:**
- `ComposedChart` (Recharts) mit `Area` + `Line`
- `ReferenceArea` färbt den historischen Bereich grau ein
- **„Jetzt"-Linie:** HTML-`div`, absolut über den Chart positioniert. Die x-Position wird per `onResize`-Callback von `ResponsiveContainer` berechnet:
  ```
  x = YAxisWidth + (nowIdx × PlotAreaWidth) / totalPoints
    = 52 + (12 × (chartWidth − 60)) / 108
  ```
- Konfidenzband: `upper`/`lower` sind für vergangene Slots `null`, damit das weiße Füll-Area die graue `ReferenceArea` nicht überdeckt
- X-Achse: `interval={0}` + `tickFormatter` zeigt nur `:00`-Labels, behält aber alle 108 Datenpunkte im kategorischen Scale

**Props:** `totalForecast`, `plantForecasts`, `plants`

---

### `PlantsList`

Zeigt jede Anlage als Card mit:
- **SVG Ring-Gauge** (Auslastung in %, Farbe je nach Auslastungsstufe)
- Aktueller Leistung und Nennleistung
- Fortschrittsbalken
- Konfidenz-Badge (Hoch / Mittel / Niedrig)
- Gesamt-Kapazitätszeile am Ende

**Auslastungsfarben:**

| Auslastung | Farbe |
|---|---|
| ≥ 75 % | Grün `#1D9E75` |
| ≥ 50 % | Hellgrün `#22C594` |
| ≥ 30 % | Gelb `#F59E0B` |
| < 30 % | Rot `#EF4444` |

**Props:** `plants: Plant[]`

---

### `WeatherPanel`

4 Umweltfaktoren in einem `2 × 2`-Grid (`lg: 4 Spalten`): Niederschlag, Temperatur, Pegelstand (m³/s), Regenwahrscheinlichkeit.

**Props:** `weather: WeatherForecast`

---

## Datenquelle wechseln

In `src/data/dataAdapter.ts` die Konstante `DATA_SOURCE` ändern:

```ts
const DATA_SOURCE: "mock" | "csv" | "api" = "mock";
```

| Wert | Verhalten |
|---|---|
| `"mock"` | Lokaler Generator, kein Backend nötig |
| `"csv"` | Liest `/public/data/forecast.csv` — Parser noch zu implementieren |
| `"api"` | Ruft `/api/forecast/latest` auf — Endpoint noch zu implementieren |

### Erwartetes CSV-Format

```
timestamp,plant_id,predicted_kw,conf_lower,conf_upper,actual_kw
2025-06-13T09:00:00Z,burgau,210.5,195.0,226.0,208.3
2025-06-13T09:00:00Z,rudolstadt,130.2,120.0,140.4,
```

---

## Anlagen hinzufügen / ändern

In `src/data/mockForecast.ts` das `PLANTS`-Array anpassen:

```ts
const PLANTS = [
  { id: "burgau",     name: "KW Burgau",     installedKw: 320, scale: 1.0,  confidence: 0.91 },
  { id: "rudolstadt", name: "KW Rudolstadt", installedKw: 200, scale: 0.62, confidence: 0.87 },
  // neue Anlage:
  { id: "saalfeld",  name: "KW Saalfeld",   installedKw: 150, scale: 0.47, confidence: 0.84 },
];
```

- `scale` skaliert das Tagesprofil relativ zur Maximalleistung (0–1)
- `confidence` ist der Modell-Konfidenzwert, der im `PlantsList`-Panel angezeigt wird
- `installedKw` ist die Nennleistung der Anlage

Beim Wechsel auf echte Daten (`csv` / `api`) entfällt das `PLANTS`-Array; die Anlagen-Metadaten sollten dann aus dem API-Response oder einer separaten Konfigurationsdatei kommen.
