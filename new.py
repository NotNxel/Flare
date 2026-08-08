import csv
import io
import math
import requests
from datetime import datetime, timezone
from flask import Flask, request, jsonify, Response

KEY = "944becee14a34c013744053eb553e36b"
app = Flask(__name__)
SATELLITES = ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"]


def distance_km(lat1, lon1, lat2, lon2):
    """Straight-line distance between two lat/lon points, in km."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


def score(dist_km, age_hours, frp, radius_km):
    """0-100 relevance score: closer + newer + hotter = higher score."""
    closeness = max(0, 45 * (1 - dist_km / radius_km))
    recency = max(0, 35 * (1 - age_hours / 48))
    intensity = min(10, frp / 10)
    return round(min(100, closeness + recency + intensity), 1)


def get_detections(satellite, area):
    """Download and parse one satellite's CSV feed. Returns a list of dict rows."""
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{KEY}/{satellite}/{area}/2"
    try:
        response = requests.get(url, timeout=15)
        return list(csv.DictReader(io.StringIO(response.text)))
    except Exception:
        return []


@app.get("/api/fires")
def fires():
    lat = float(request.args["lat"])
    lon = float(request.args["lon"])
    radius_km = float(request.args.get("rad", 100))

    # Build a lat/lon box around the search point to query FIRMS with
    lat_pad = radius_km / 111
    lon_pad = radius_km / (111 * math.cos(math.radians(lat)))
    area = f"{lon - lon_pad:.2f},{lat - lat_pad:.2f},{lon + lon_pad:.2f},{lat + lat_pad:.2f}"

    now = datetime.now(timezone.utc)
    results = []

    for satellite in SATELLITES:
        for row in get_detections(satellite, area):
            try:
                fire_lat = float(row["latitude"])
                fire_lon = float(row["longitude"])
                frp = float(row["frp"] or 0)
                detected_at = datetime.strptime(row["acq_date"] + row["acq_time"], "%Y-%m-%d%H%M").replace(tzinfo=timezone.utc)

                dist = distance_km(lat, lon, fire_lat, fire_lon)
                age_hours = (now - detected_at).total_seconds() / 3600

                results.append({
                    "lat": fire_lat,
                    "lon": fire_lon,
                    "sat": satellite.split("_")[1],
                    "frp": frp,
                    "t": detected_at.isoformat(),
                    "d": round(dist, 1),
                    "age": round(age_hours, 1),
                    "score": score(dist, age_hours, frp, radius_km),
                })
            except Exception:
                continue  # skip bad rows

    results.sort(key=lambda r: -r["score"])
    return jsonify(results[:400])


#Rithin


HTML = r"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FLARE</title>

  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">

  <style>
    :root {
      --ember: #ff5a1f;
    }

    * {
      margin: 0;
      box-sizing: border-box;
    }

    body {
      background: #0b0908;
      color: #e8ded2;
      font: 14px/1.4 system-ui;
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    /* --- Header bar with title + controls --- */

    header {
      padding: 12px 20px;
      display: flex;
      gap: 14px;
      align-items: center;
      border-bottom: 1px solid #2a2320;
      background: #171310;
    }

    h1 {
      font-size: 22px;
      letter-spacing: .08em;
    }

    h1 b {
      color: var(--ember);
    }

    /* Animated gradient underline beneath the title */
    h1::after {
      content: "";
      display: block;
      height: 2px;
      background: linear-gradient(90deg, var(--ember), #ffb02e, transparent);
      background-size: 200% 100%;
      animation: slide-underline 3s linear infinite;
    }

    @keyframes slide-underline {
      to { background-position: -200% 0; }
    }

    input, button {
      background: #0b0908;
      border: 1px solid #2a2320;
      color: #e8ded2;
      padding: 8px 12px;
      border-radius: 3px;
    }

    button {
      background: var(--ember);
      color: #140b06;
      font-weight: 700;
      cursor: pointer;
      border: 0;
      transition: .15s;
    }

    button:hover {
      box-shadow: 0 0 18px rgba(255, 90, 31, .5);
    }

    #map {
      flex: 1;
    }

    /* --- Pulsing dot used for each fire detection marker --- */

    .detection-dot {
      border-radius: 50%;
      background: radial-gradient(circle, #ffb02e, var(--ember) 50%, transparent 72%);
      animation: pulse 1.8s infinite;
    }

    @keyframes pulse {
      0%   { box-shadow: 0 0 0 0 rgba(255, 90, 31, .7); }
      70%  { box-shadow: 0 0 0 14px rgba(255, 90, 31, 0); }
      100% { box-shadow: 0 0 0 0 rgba(255, 90, 31, 0); }
    }

    /* Dark-themed Leaflet popups to match the rest of the UI */
    .leaflet-popup-content-wrapper,
    .leaflet-popup-tip {
      background: #171310;
      color: #e8ded2;
    }

    small {
      color: #9a8c7c;
    }
  </style>
</head>

<body>

  <header>
    <h1>FLA<b>RE</b></h1>

    <input id="lat-input" placeholder="lat" value="34.05" size="7">
    <input id="lon-input" placeholder="lon" value="-118.24" size="8">
    <input id="radius-input" type="number" value="150" size="5" title="radius km">

    <button onclick="scanForFires()">scan 🔥</button>

  </header>

  <div id="map"></div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://cdn.jsdelivr.net/gh/NotNxel/Flare@main/script.js"></script>

</body>
</html>"""

@app.get("/")
def home(): return Response(HTML, mimetype="text/html")

if __name__ == "__main__":
    app.run(port=2704)
