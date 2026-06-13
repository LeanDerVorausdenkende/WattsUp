"""
Downloader for Pegel (gauge) observations from the Thuringia FROST-Server
(OGC SensorThings API v1.1).

Fetches water-level (W) or discharge (Q) time series for a named station and
writes a two-column CSV.  Supports daily (``1D``) and 15-minute (``15min``)
resolutions.

Notes
-----
15-minute data is only available from approximately 2025-05-17 onwards.
All timestamps returned by the API are in UTC (ISO-8601 with trailing ``Z``).

API base : https://kshww2.thueringen.de/FROST-Server/v1.1
API docs  : https://developers.sensorup.com/docs/#introduction
"""

import csv
import sys

import requests


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://kshww2.thueringen.de/FROST-Server/v1.1"

FREQ_TO_TYPE: dict[str, str] = {
    "1D":    "TH_PEGELDATEN_1D",
    "15min": "TH_PEGELDATEN_15MIN",
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class FetchingError(Exception):
    """Raised when a requested datastream cannot be found on the server."""


class NoDataException(Exception):
    """Raised when a datastream exists but contains no observations in the
    requested time window."""


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _get(path: str, params: dict | None = None) -> dict:
    """Send a GET request to the FROST-Server and return the parsed JSON body.

    Parameters
    ----------
    path : str
        API path relative to ``BASE_URL``, e.g. ``"Things"`` or
        ``"Datastreams(7301)/Observations"``.
    params : dict, optional
        Query-string parameters forwarded to ``requests.get``.

    Returns
    -------
    dict
        Parsed JSON response body.

    Raises
    ------
    requests.HTTPError
        If the server returns a non-2xx status code.
    """
    resp = requests.get(
        f"{BASE_URL}/{path.lstrip('/')}",
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Domain helpers
# ---------------------------------------------------------------------------

def find_thing(station_name: str) -> dict:
    """Find the first API *Thing* whose name contains ``station_name``.

    The match is case-insensitive and uses a substring search.

    Parameters
    ----------
    station_name : str
        Full or partial station name, e.g. ``"Rothenstein"`` or
        ``"eisenach"``.

    Returns
    -------
    dict
        The matching Thing object with keys ``name``, ``description``, and
        ``@iot.id``.

    Raises
    ------
    SystemExit
        If no station matching ``station_name`` is found.
    """
    data = _get("Things", {
        "$filter": f"substringof('{station_name.lower()}',tolower(name))",
        "$select": "name,description,@iot.id",
        "$top": 1,
    })
    things = data.get("value", [])
    if not things:
        sys.exit(f"No station found matching '{station_name}'.")
    return things[0]


def find_datastream(thing_id: int, parameter: str, freq: str) -> dict:
    """Find the datastream for a given station, parameter, and frequency.

    Parameters
    ----------
    thing_id : int
        ``@iot.id`` of the parent Thing (station).
    parameter : str
        ``"W"`` for water level (cm) or ``"Q"`` for discharge (m³/s).
    freq : str
        ``"1D"`` for daily or ``"15min"`` for 15-minute observations.

    Returns
    -------
    dict
        Matching Datastream object.

    Raises
    ------
    FetchingError
        If no datastream matches the requested ``parameter`` / ``freq``
        combination for this station.  The error message includes a hint to
        run ``explore_api.list_datastreams`` for a full listing.
    """
    data = _get(
        f"Things({thing_id})/Datastreams",
        {"$select": "name,@iot.id,unitOfMeasurement,properties,phenomenonTime"},
    )
    target_type = FREQ_TO_TYPE[freq]
    for s in data.get("value", []):
        if (
            s["name"].startswith(f"{parameter}@")
            and s.get("properties", {}).get("type") == target_type
        ):
            return s

    raise FetchingError(
        f"No datastream for parameter='{parameter}', freq='{freq}' on Thing "
        f"{thing_id}.  Run explore_api.list_datastreams({thing_id}) to see "
        f"what is available."
    )


def fetch_observations(
    datastream_id: int,
    start_iso: str,
    end_iso: str,
) -> list[dict]:
    """Download all observations in a time window, following pagination.

    Parameters
    ----------
    datastream_id : int
        ``@iot.id`` of the target Datastream.
    start_iso : str
        Window start as UTC ISO-8601, e.g. ``"2020-01-01T00:00:00Z"``.
    end_iso : str
        Window end as UTC ISO-8601, e.g. ``"2026-01-01T00:00:00Z"``.

    Returns
    -------
    list of dict
        Each entry has keys ``phenomenonTime`` (str, UTC ISO-8601) and
        ``result`` (float).

    Notes
    -----
    The server paginates at 1 000 rows per page.  This function follows
    ``@iot.nextLink`` automatically until all pages are consumed.
    """
    url = f"{BASE_URL}/Datastreams({datastream_id})/Observations"
    params = {
        "$select":  "phenomenonTime,result",
        "$filter":  f"phenomenonTime ge {start_iso} and phenomenonTime le {end_iso}",
        "$orderby": "phenomenonTime asc",
        "$top":     1000,
        "$count":   "true",
    }
    rows: list[dict] = []
    next_url: str | None = None

    while True:
        data = requests.get(
            next_url or url,
            params=None if next_url else params,
            timeout=30,
        ).json()
        rows.extend(data.get("value", []))
        print(f"  fetched {len(rows)} / {data.get('@iot.count', '?')}")
        next_url = data.get("@iot.nextLink")
        if not next_url:
            break

    return rows


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def fetch_data(
    station: str,
    param: str,
    freq: str,
    start_date: str,
    end_date: str,
    output_dir: str,
) -> None:
    """Download gauge observations and write them to a CSV file.

    Parameters
    ----------
    station : str
        Full or partial station name (case-insensitive substring match).
    param : str
        ``"W"`` for water level (cm) or ``"Q"`` for discharge (m³/s).
    freq : str
        ``"1D"`` for daily or ``"15min"`` for 15-minute resolution.
        15-minute data is only available from ~2025-05-17.
    start_date : str
        Start of the desired time window.  Either ``"YYYY-MM-DD"`` or full
        UTC ISO-8601 (``"YYYY-MM-DDTHH:MM:SSZ"``).
    end_date : str
        End of the desired time window (same formats as ``start_date``).
    output_dir : str
        Directory in which the output CSV will be created.  Must already
        exist.

    Raises
    ------
    FetchingError
        If the requested parameter / frequency combination does not exist for
        the station.
    NoDataException
        If the datastream exists but contains no observations in the
        requested window.

    Notes
    -----
    Output filename pattern: ``<param>_<station_name>_<freq>.csv``.
    The CSV has two columns: ``phenomenonTime`` (UTC ISO-8601) and
    ``<param>_<unit>`` (numeric).
    """
    if not station or not start_date or not end_date:
        sys.exit("station, start_date, and end_date must all be non-empty.")
    if freq not in FREQ_TO_TYPE:
        sys.exit(f"freq must be one of: {', '.join(FREQ_TO_TYPE)}")

    start_iso = start_date if "T" in start_date else f"{start_date}T00:00:00Z"
    end_iso   = end_date   if "T" in end_date   else f"{end_date}T00:00:00Z"
    print(f"Station={station}  Parameter={param}  Freq={freq}  "
          f"{start_iso} → {end_iso}\n")

    thing  = find_thing(station)
    stream = find_datastream(thing["@iot.id"], param, freq)

    unit  = stream["unitOfMeasurement"]["symbol"]
    avail = stream.get("phenomenonTime", "unknown")
    print(f"Datastream: [{stream['@iot.id']}] {stream['name']} "
          f"({unit})  available: {avail}\n")

    observations = fetch_observations(stream["@iot.id"], start_iso, end_iso)
    if not observations:
        raise NoDataException(
            f"No data found in window {start_iso}–{end_iso}.  "
            f"Datastream available range: {avail}"
        )

    safe_name   = thing["name"].replace("/", "-").replace(" ", "_")
    output_path = f"{output_dir}/{param}_{safe_name}_{freq}.csv"
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["phenomenonTime", f"{param}_{unit}"])
        for obs in observations:
            writer.writerow([obs["phenomenonTime"], obs["result"]])

    print(f"\nSaved {len(observations)} rows → '{output_path}'")
