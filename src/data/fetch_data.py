"""
Minimal downloader for Pegel observations from the Thuringia FROST-Server
(OGC SensorThings API v1.1).

Accepts four inputs via a .env file and writes a two-column CSV.

.env variables
--------------
STATION_NAME : str  (required)
    Exact or partial station name, case-insensitive.
    E.g. ``"Rothenstein"`` or ``"eisenach"``.
PARAMETER : str  (optional, default "W")
    ``"W"`` — Wasserstand (water level, cm)
    ``"Q"`` — Abfluss (discharge, m³/s)
DATA_FREQ : str  (optional, default "1D")
    ``"1D"``    — daily observations  (long history available)
    ``"15min"`` — 15-minute observations (available from ~2025-05-17)
START_DATE : str  (required)
    Start of the time window, e.g. ``"2020-01-01"``.
END_DATE : str  (required)
    End of the time window,   e.g. ``"2026-01-01"``.

Output
------
A CSV file named ``<PARAMETER>_<station>_<FREQ>.csv`` with columns:
    phenomenonTime, <PARAMETER>_<unit>

Usage::

    python download_pegel_data_minimal.py

API base: https://kshww2.thueringen.de/FROST-Server/v1.1
API documentation: https://developers.sensorup.com/docs/#introduction 
"""

import csv
import os
import sys

import requests
from dotenv import load_dotenv


class FetchingError(Exception):
    pass

BASE_URL = "https://kshww2.thueringen.de/FROST-Server/v1.1"

FREQ_TO_TYPE = {
    "1D":    "TH_PEGELDATEN_1D",
    "15min": "TH_PEGELDATEN_15MIN",
}


def get(path: str, params: dict | None = None) -> dict:
    """GET ``BASE_URL/<path>`` and return the parsed JSON body."""
    resp = requests.get(f"{BASE_URL}/{path.lstrip('/')}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def find_thing(station_name: str) -> dict:
    """
    Return the first Thing whose name contains ``station_name`` (case-insensitive).

    Raises ``SystemExit`` if no match is found.
    """
    data = get("Things", {
        "$filter": f"substringof('{station_name.lower()}',tolower(name))",
        "$select": "name,description,@iot.id",
        "$top": 1,
    })
    things = data.get("value", [])
    if not things:
        sys.exit(f"No station found matching '{station_name}'.")
    return things[0]


def find_datastream(thing_id: int, parameter: str, freq: str) -> dict:
    """
    Return the Datastream matching ``<parameter>@`` prefix and ``freq`` type.

    Raises ``SystemExit`` if the combination does not exist for the station.
    """
    data = get(
        f"Things({thing_id})/Datastreams",
        {"$select": "name,@iot.id,unitOfMeasurement,properties,phenomenonTime",}
    )
    target_type = FREQ_TO_TYPE[freq]
    for s in data.get("value", []):
        if (s["name"].startswith(f"{parameter}@")
                and s.get("properties", {}).get("type") == target_type):
            return s
    
    raise FetchingError(f"No datastream for parameter='{parameter}', freq='{freq}' on Thing {thing_id}. Run explore_api.py → list_datastreams({thing_id}) to see what is available.")
    

def fetch_observations(datastream_id: int, start_iso: str, end_iso: str) -> list[dict]:
    """
    Return all observations in the time window, following pagination.

    Parameters
    ----------
    datastream_id : int
        ``@iot.id`` of the target Datastream.
    start_iso : str
        Window start as UTC ISO-8601, e.g. ``"2020-01-01T00:00:00Z"``.
    end_iso : str
        Window end   as UTC ISO-8601, e.g. ``"2026-01-01T00:00:00Z"``.

    Returns
    -------
    list[dict]
        Each entry has keys ``phenomenonTime`` (str) and ``result`` (float).
    """
    url = f"{BASE_URL}/Datastreams({datastream_id})/Observations"
    params = {
        "$select": "phenomenonTime,result",
        "$filter": f"phenomenonTime ge {start_iso} and phenomenonTime le {end_iso}",
        "$orderby": "phenomenonTime asc",
        "$top": 1000,
        "$count": "true",
    }
    rows, next_url = [], None
    while True:
        data = requests.get(
            next_url or url,
            params=None if next_url else params,
            timeout=30
        ).json()
        rows.extend(data.get("value", []))
        print(f"  fetched {len(rows)} / {data.get('@iot.count', '?')}")
        next_url = data.get("@iot.nextLink")
        if not next_url:
            break
    return rows


def fetch_data(station, param, freq, start_date, end_date, output_dir):
    if not station or not start_date or not end_date:
        sys.exit("Set STATION_NAME, START_DATE and END_DATE in your .env file.")
    if freq not in FREQ_TO_TYPE:
        sys.exit(f"DATA_FREQ must be one of: {', '.join(FREQ_TO_TYPE)}")

    
    start_iso = start_date if "T" in start_date else f"{start_date}T00:00:00Z"
    end_iso   = end_date   if "T" in end_date   else f"{end_date}T00:00:00Z"
    print(f"Station={station}  Parameter={param}  Freq={freq}  {start_iso} → {end_iso}\n")


    thing  = find_thing(station)
    try: 
        stream = find_datastream(thing["@iot.id"], param, freq)
    except Exception as e:
        print(f"Error fetching {e}")
        return; # return becuase there was an error fetching the data

    unit   = stream["unitOfMeasurement"]["symbol"]
    avail  = stream.get("phenomenonTime", "unknown")
    print(f"Datastream: [{stream['@iot.id']}] {stream['name']} ({unit})  available: {avail}\n")

    observations = fetch_observations(stream["@iot.id"], start_iso, end_iso)
    if not observations:
        sys.exit(f"No data found. Datastream available range: {avail}")

    safe_name   = thing["name"].replace("/", "-").replace(" ", "_")
    output_path = f"{output_dir}/{param}_{safe_name}_{freq}.csv"
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["phenomenonTime", f"{param}_{unit}"])
        for obs in observations:
            writer.writerow([obs["phenomenonTime"], obs["result"]])
    print(f"\nSaved {len(observations)} rows to '{output_path}'")



class NoDataException(Exception):
    pass

def fetch_data_good(station, param, freq, start_date, end_date, output_dir):
    if not station or not start_date or not end_date:
        sys.exit("Set STATION_NAME, START_DATE and END_DATE in your .env file.")
    if freq not in FREQ_TO_TYPE:
        sys.exit(f"DATA_FREQ must be one of: {', '.join(FREQ_TO_TYPE)}")

    
    start_iso = start_date if "T" in start_date else f"{start_date}T00:00:00Z"
    end_iso   = end_date   if "T" in end_date   else f"{end_date}T00:00:00Z"
    print(f"Station={station}  Parameter={param}  Freq={freq}  {start_iso} → {end_iso}\n")


    thing  = find_thing(station)
    try: 
        stream = find_datastream(thing["@iot.id"], param, freq)
    except Exception as e:
        print(f"Error fetching {e}")
        raise e; # return becuase there was an error fetching the data

    unit   = stream["unitOfMeasurement"]["symbol"]
    avail  = stream.get("phenomenonTime", "unknown")
    print(f"Datastream: [{stream['@iot.id']}] {stream['name']} ({unit})  available: {avail}\n")

    observations = fetch_observations(stream["@iot.id"], start_iso, end_iso)
    
    if not observations:
        raise NoDataException(f"No data found. Datastream available range: {avail}")
        #sys.exit(f"No data found. Datastream available range: {avail}") why would you do this

    safe_name   = thing["name"].replace("/", "-").replace(" ", "_")
    output_path = f"{output_dir}/{param}_{safe_name}_{freq}.csv"
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["phenomenonTime", f"{param}_{unit}"])
        for obs in observations:
            writer.writerow([obs["phenomenonTime"], obs["result"]])
    print(f"\nSaved {len(observations)} rows to '{output_path}'")

