"""
Exploration script for the Thuringia FROST-Server (OGC SensorThings API v1.1).

Run individual sections by uncommenting the function calls at the bottom.
Each function prints results to stdout in a readable format.

API base: https://kshww2.thueringen.de/FROST-Server/v1.1
API documentation: https://developers.sensorup.com/docs/#introduction 
"""

import requests

BASE_URL = "https://kshww2.thueringen.de/FROST-Server/v1.1"


def _get(path: str, params: dict | None = None) -> dict:
    url = f"{BASE_URL}/{path.lstrip('/')}"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ─────────────────────────────────────────────────────────────────────────────
# 1. List all stations (Things)
# ─────────────────────────────────────────────────────────────────────────────

def list_all_stations() -> list:
    """Print every station with its id, name, description, and station_id."""
    print("=== ALL STATIONS ===")
    params = {
        "$select": "name,description,@iot.id,properties",
        "$top": 500,
        "$orderby": "name asc",
    }
    data = _get("Things", params)
    things = data.get("value", [])
    print(f"Total stations: {data.get('@iot.count', len(things))}\n")
    print(f"{'ID':>6}  {'station_id':>12}  {'name':<45}  description")
    print("-" * 100)
    for t in things:
        props = t.get("properties") or {}
        sid = props.get("station_id", "")
        print(f"{t['@iot.id']:>6}  {str(sid):>12}  {t['name']:<45}  {t.get('description','')}")


def get_all_station_names() -> list:
    """Return every station with its name."""
    print("=== ALL STATIONS ===")
    params = {
        "$select": "name,description,@iot.id,properties",
        "$top": 500,
        "$orderby": "name asc",
    }
    data = _get("Things", params)
    things = data.get("value", [])
    return things


def search_stations(keyword: str) -> None:
    """Print stations whose name contains keyword."""
    print(f"=== STATIONS MATCHING '{keyword}' ===")
    params = {
        "$filter": f"substringof('{keyword}',name)",
        "$select": "name,description,@iot.id,properties",
        "$top": 50,
    }
    data = _get("Things", params)
    things = data.get("value", [])
    print(f"Found {len(things)} match(es)\n")
    for t in things:
        props = t.get("properties") or {}
        print(f"  [{t['@iot.id']}]  {t['name']}  –  {t.get('description','')}  (station_id: {props.get('station_id','')})")


# ─────────────────────────────────────────────────────────────────────────────
# 2. List datastreams for a station
# ─────────────────────────────────────────────────────────────────────────────

def list_datastreams(thing_id: int) -> None:
    """Print all datastreams for a given Thing (station) id."""
    print(f"=== DATASTREAMS FOR THING {thing_id} ===")
    params = {"$select": "name,@iot.id,unitOfMeasurement,properties,phenomenonTime"}
    data = _get(f"Things({thing_id})/Datastreams", params)
    streams = data.get("value", [])
    print(f"Found {len(streams)} datastream(s)\n")
    print(f"  {'DS-ID':>6}  {'type':<25}  {'unit':>6}  {'phenomenonTime'}")
    print("  " + "-" * 90)
    for s in streams:
        props = s.get("properties") or {}
        unit = s.get("unitOfMeasurement", {}).get("symbol", "")
        ptime = s.get("phenomenonTime", "no data")
        dtype = props.get("type", "")
        print(f"  {s['@iot.id']:>6}  {s['name']:<25}  {unit:>6}  {ptime}  [{dtype}]")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Summarise all datastream types and frequencies across the entire server
# ─────────────────────────────────────────────────────────────────────────────

def list_datastream_types() -> None:
    """Count and list all distinct datastream types (frequencies) on the server."""
    print("=== ALL DATASTREAM TYPES (server-wide) ===")
    params = {
        "$select": "name,properties",
        "$top": 1000,
    }
    data = _get("Datastreams", params)
    streams = data.get("value", [])

    from collections import Counter
    type_counts: Counter = Counter()
    param_counts: Counter = Counter()

    for s in streams:
        props = s.get("properties") or {}
        type_counts[props.get("type", "unknown")] += 1
        param_counts[props.get("parameter", "unknown")] += 1

    print("\nBy type (data frequency):")
    for t, n in type_counts.most_common():
        print(f"  {n:>4}x  {t}")

    print("\nBy parameter (variable):")
    for p, n in param_counts.most_common():
        print(f"  {n:>4}x  {p}")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Inspect a specific datastream: time range, observation count, sample rows
# ─────────────────────────────────────────────────────────────────────────────

def inspect_datastream(datastream_id: int, n_samples: int = 5) -> None:
    """Print metadata and sample observations for a datastream."""
    print(f"=== DATASTREAM {datastream_id} ===")

    # Metadata
    ds = _get(
        f"Datastreams({datastream_id})",
        {"$select": "name,unitOfMeasurement,properties,phenomenonTime"}
    )
    props = ds.get("properties") or {}
    unit = ds.get("unitOfMeasurement", {}).get("symbol", "")
    print(f"  Name           : {ds['name']}")
    print(f"  Unit           : {unit}")
    print(f"  Type           : {props.get('type', '')}")
    print(f"  Parameter      : {props.get('parameter', '')}")
    print(f"  station_id     : {props.get('station_id', '')}")
    print(f"  measurement_start (meta): {props.get('measurement_start', '')}")
    print(f"  phenomenonTime (actual) : {ds.get('phenomenonTime', 'unknown')}")

    # Total observation count
    count_data = _get(
        f"Datastreams({datastream_id})/Observations",
        {"$count": "true", "$top": 0}
    )
    print(f"  Total observations      : {count_data.get('@iot.count', '?')}")

    # Earliest observations
    print(f"\n  First {n_samples} observations:")
    first = _get(
        f"Datastreams({datastream_id})/Observations",
        {"$select": "phenomenonTime,result", "$top": n_samples, "$orderby": "phenomenonTime asc"}
    )
    for o in first.get("value", []):
        print(f"    {o['phenomenonTime']}  →  {o['result']} {unit}")

    # Latest observations
    print(f"\n  Last {n_samples} observations:")
    last = _get(
        f"Datastreams({datastream_id})/Observations",
        {"$select": "phenomenonTime,result", "$top": n_samples, "$orderby": "phenomenonTime desc"}
    )
    for o in last.get("value", []):
        print(f"    {o['phenomenonTime']}  →  {o['result']} {unit}")


# ─────────────────────────────────────────────────────────────────────────────
# 5. List all datastreams for a station grouped by frequency
# ─────────────────────────────────────────────────────────────────────────────

def list_station_frequencies(thing_id: int) -> None:
    """Show available data frequencies and their actual time ranges for a station."""
    print(f"=== AVAILABLE FREQUENCIES FOR THING {thing_id} ===")
    params = {"$select": "name,@iot.id,unitOfMeasurement,properties,phenomenonTime"}
    data = _get(f"Things({thing_id})/Datastreams", params)
    streams = data.get("value", [])

    from collections import defaultdict
    by_freq: dict = defaultdict(list)
    for s in streams:
        dtype = (s.get("properties") or {}).get("type", "unknown")
        by_freq[dtype].append(s)

    for freq, ss in sorted(by_freq.items()):
        print(f"\n  [{freq}]")
        for s in ss:
            unit = s.get("unitOfMeasurement", {}).get("symbol", "")
            ptime = s.get("phenomenonTime", "no data")
            print(f"    DS {s['@iot.id']:>5}  {s['name']:<30}  ({unit})  {ptime}")


# ─────────────────────────────────────────────────────────────────────────────
# 6. Station location (GPS coordinates)
# ─────────────────────────────────────────────────────────────────────────────

def get_station_location(thing_id: int) -> None:
    """
    Print the GPS coordinates of a station.

    Parameters
    ----------
    thing_id:
        Numeric ``@iot.id`` of the Thing, e.g. ``190``.
    """
    print(f"=== LOCATION OF THING {thing_id} ===")
    data = _get(f"Things({thing_id})/Locations", {"$select": "name,location"})
    for loc in data.get("value", []):
        coords = loc.get("location", {}).get("coordinates", [])
        if coords:
            print(f"  Longitude : {coords[0]}")
            print(f"  Latitude  : {coords[1]}")
        print(f"  GeoJSON   : {loc['location']}")


# ─────────────────────────────────────────────────────────────────────────────
# 7. Latest observation for a datastream
# ─────────────────────────────────────────────────────────────────────────────

def get_latest_observation(datastream_id: int) -> None:
    """
    Print the most recent observation for a datastream.

    Useful for checking current water levels.

    Parameters
    ----------
    datastream_id:
        Numeric ``@iot.id`` of the Datastream, e.g. ``7301``.
    """
    print(f"=== LATEST OBSERVATION FOR DATASTREAM {datastream_id} ===")
    ds = _get(f"Datastreams({datastream_id})", {"$select": "name,unitOfMeasurement"})
    unit = ds.get("unitOfMeasurement", {}).get("symbol", "")

    data = _get(
        f"Datastreams({datastream_id})/Observations",
        {"$top": 1, "$orderby": "phenomenonTime desc", "$select": "phenomenonTime,result"},
    )
    obs = data.get("value", [])
    if obs:
        print(f"  {ds['name']}: {obs[0]['result']} {unit}  at  {obs[0]['phenomenonTime']}")
    else:
        print("  No observations found.")


# ─────────────────────────────────────────────────────────────────────────────
# 8. Filter observations by threshold (flood / drought detection)
# ─────────────────────────────────────────────────────────────────────────────

def get_threshold_exceedances(datastream_id: int, threshold: float, above: bool = True) -> None:
    """
    Print observations where the water level exceeds (or falls below) a threshold.

    Parameters
    ----------
    datastream_id:
        Numeric ``@iot.id`` of the Datastream, e.g. ``7301``.
    threshold:
        Water level value in the datastream's unit (e.g. cm).
    above:
        If ``True`` (default), find values above threshold (flood).
        If ``False``, find values below threshold (drought / low water).
    """
    op = "gt" if above else "lt"
    label = f"above {threshold}" if above else f"below {threshold}"
    print(f"=== OBSERVATIONS {label.upper()} FOR DATASTREAM {datastream_id} ===")

    ds = _get(f"Datastreams({datastream_id})", {"$select": "name,unitOfMeasurement"})
    unit = ds.get("unitOfMeasurement", {}).get("symbol", "")

    data = _get(
        f"Datastreams({datastream_id})/Observations",
        {
            "$filter": f"result {op} {threshold}",
            "$select": "phenomenonTime,result",
            "$orderby": "phenomenonTime asc",
            "$top": 20,
            "$count": "true",
        },
    )
    total = data.get("@iot.count", "?")
    print(f"  Total exceedances: {total}  (showing first 20)\n")
    for o in data.get("value", []):
        print(f"  {o['phenomenonTime']}  →  {o['result']} {unit}")


# ─────────────────────────────────────────────────────────────────────────────
# 9. Find all Abflusspegel stations within a bounding box
# ─────────────────────────────────────────────────────────────────────────────

def find_stations_in_bbox(lon_min: float, lat_min: float, lon_max: float, lat_max: float) -> None:
    """
    Print all stations (Things) whose location falls within a bounding box.

    Parameters
    ----------
    lon_min, lat_min, lon_max, lat_max:
        Bounding box in WGS84 decimal degrees.

    Example
    -------
    # Roughly all of Thuringia:
    find_stations_in_bbox(9.8, 50.2, 12.7, 51.7)
    """
    print(f"=== STATIONS IN BBOX [{lon_min},{lat_min} → {lon_max},{lat_max}] ===")
    polygon = (
        f"POLYGON(({lon_min} {lat_min}, {lon_max} {lat_min}, "
        f"{lon_max} {lat_max}, {lon_min} {lat_max}, {lon_min} {lat_min}))"
    )
    data = _get(
        "Things",
        {
            "$filter": f"st_within(Locations/location,geography'{polygon}')",
            "$select": "name,description,@iot.id,properties",
            "$top": 200,
            "$orderby": "name asc",
        },
    )
    things = data.get("value", [])
    print(f"Found {data.get('@iot.count', len(things))} station(s)\n")
    print(f"  {'ID':>6}  {'name':<40}  description")
    print("  " + "-" * 75)
    for t in things:
        print(f"  {t['@iot.id']:>6}  {t['name']:<40}  {t.get('description','')}")


# ─────────────────────────────────────────────────────────────────────────────
# 10. Download observations directly as CSV (no pagination needed for small windows)
# ─────────────────────────────────────────────────────────────────────────────

def download_csv(datastream_id: int, start_iso: str, end_iso: str, output_path: str) -> None:
    """
    Download observations as CSV directly via the server's CSV result format.

    The server formats the response as CSV when ``$resultFormat=CSV`` is set,
    avoiding the need for manual JSON parsing.  Note: for large time windows
    the server may still paginate — in that case use ``fetch_observations`` in
    ``download_pegel_data.py`` instead.

    Parameters
    ----------
    datastream_id:
        Numeric ``@iot.id`` of the Datastream, e.g. ``7301``.
    start_iso:
        Start of time window, ISO-8601, e.g. ``"2020-01-01T00:00:00Z"``.
    end_iso:
        End of time window, ISO-8601, e.g. ``"2020-12-31T00:00:00Z"``.
    output_path:
        File path to write the CSV, e.g. ``"output.csv"``.
    """
    import requests

    print(f"=== DOWNLOADING CSV FOR DATASTREAM {datastream_id} ===")
    url = f"{BASE_URL}/Datastreams({datastream_id})/Observations"
    params = {
        "$filter": f"phenomenonTime ge {start_iso} and phenomenonTime le {end_iso}",
        "$orderby": "phenomenonTime asc",
        "$select": "phenomenonTime,result",
        "$resultFormat": "CSV",
        "$top": 10000,
    }
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(resp.text)

    lines = resp.text.strip().splitlines()
    print(f"  Saved {max(0, len(lines) - 1)} rows to '{output_path}'")
    if lines:
        print(f"  Header : {lines[0]}")
    if len(lines) > 1:
        print(f"  First  : {lines[1]}")
    if len(lines) > 2:
        print(f"  Last   : {lines[-1]}")


# ─────────────────────────────────────────────────────────────────────────────
# Run — uncomment the calls you want
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # 1. List every station on the server
    # list_all_stations()

    # 2. Search stations by partial name
    # search_stations("Eisenach")

    # 3. All distinct types/frequencies across the whole server
    # list_datastream_types()

    # 4. All datastreams for a specific station (use @iot.id from list_all_stations)
    # list_datastreams(190)

    # 5. Available frequencies + actual data ranges for a station
    # list_station_frequencies(190)

    # 6. Deep-inspect a single datastream (use @iot.id from list_datastreams)
    # inspect_datastream(7301)

    # 7. GPS coordinates of a station
    # get_station_location(190)

    # 8. Current / most recent water level
    # get_latest_observation(7301)

    # 9. All observations where water level exceeded a threshold (e.g. 150 cm = flood)
    # get_threshold_exceedances(7301, threshold=150, above=True)

    # 10. Find all stations inside a bounding box (WGS84 decimal degrees)
    # find_stations_in_bbox(lon_min=9.8, lat_min=50.2, lon_max=12.7, lat_max=51.7)

    # 11. Download a time window directly as CSV (no JSON parsing)
    # download_csv(7301, "2020-01-01T00:00:00Z", "2020-12-31T00:00:00Z", "output.csv")

    pass
