"""FLARE lite — live wildfire map. pip install flask requests; python flare_lite.py; open localhost:5000"""
import math, requests
from datetime import datetime, timezone
from flask import Flask, request, jsonify, Response

KEY = "944becee14a34c013744053eb553e36b"  # regenerate this before sharing the file anywhere!
app = Flask(__name__)
km = lambda a,b,c,d: 12742*math.asin(math.sqrt(math.sin(math.radians(c-a)/2)**2+math.cos(math.radians(a))*math.cos(math.radians(c))*math.sin(math.radians(d-b)/2)**2))

@app.get("/api/fires")
def fires():
    lat, lon, rad = float(request.args["lat"]), float(request.args["lon"]), float(request.args.get("rad", 100))
    dl, dn = rad/111, rad/(111*math.cos(math.radians(lat)))
    area, out, now = f"{lon-dn:.2f},{lat-dl:.2f},{lon+dn:.2f},{lat+dl:.2f}", [], datetime.now(timezone.utc)
    for src in ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"]:
        try: rows = requests.get(f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{KEY}/{src}/{area}/2", timeout=15).text.strip().splitlines()
        except Exception: continue
        if len(rows) < 2: continue
        h = {n:i for i,n in enumerate(rows[0].split(","))}
        for r in rows[1:]:
            c = r.split(",")
            try:
                t = datetime.strptime(c[h["acq_date"]]+c[h["acq_time"]].zfill(4), "%Y-%m-%d%H%M").replace(tzinfo=timezone.utc)
                fla, flo, frp = float(c[h["latitude"]]), float(c[h["longitude"]]), float(c[h["frp"]] or 0)
                d, age = km(lat,lon,fla,flo), (now-t).total_seconds()/3600
                out.append({"lat":fla,"lon":flo,"sat":src[6:-4],"frp":frp,"t":t.isoformat(),"d":round(d,1),"age":round(age,1),
                            "score":round(min(100,max(0,45*(1-d/rad))+max(0,35*(1-age/48))+min(10,frp/10)+10*(d<=rad)),1)})
            except Exception: continue
    return jsonify(sorted(out, key=lambda x:-x["score"])[:400])


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

    <small>satellite heat anomalies — not confirmed fires · informational only</small>
  </header>

  <div id="map"></div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    // Small helper so we don't have to write document.getElementById everywhere
    const byId = (id) => document.getElementById(id);

    // --- Set up the base map, centered on the default coordinates ---
    const map = L.map('map').setView([34.05, -118.24], 7);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: 'OSM/CARTO'
    }).addTo(map);

    // All markers/circles for the current scan live in this layer group,
    // so we can clear them out cleanly before drawing the next scan.
    let resultsLayer = L.layerGroup().addTo(map);

    async function scanForFires() {
      const lat = +byId('lat-input').value;
      const lon = +byId('lon-input').value;
      const radiusKm = +byId('radius-input').value;

      // Remove markers from the previous scan and fly the map to the new center
      resultsLayer.clearLayers();
      map.flyTo([lat, lon], 8);

      // Dashed circle showing the search radius around the target point
      L.circle([lat, lon], {
        radius: radiusKm * 1000, // Leaflet circles use meters
        color: '#ff5a1f',
        weight: 1.5,
        dashArray: '4 8',
        fillOpacity: .04
      }).addTo(resultsLayer);

      // Solid marker for the target point itself
      L.circleMarker([lat, lon], {
        radius: 6,
        color: '#e8ded2',
        fillColor: '#ff5a1f',
        fillOpacity: 1
      }).addTo(resultsLayer);

      // Ask the backend for fire detections near this point.
      // Expected response: array of { lat, lon, sat, frp, d, age, score }
      //   frp   = fire radiative power (MW)
      //   d     = distance from the target point (km)
      //   age   = hours since the detection was recorded
      //   score = this app's computed relevance score
      const response = await fetch(`/api/fires?lat=${lat}&lon=${lon}&rad=${radiusKm}`);
      const detections = await response.json();

      detections.forEach((point) => {
        // Bigger dot for a stronger heat signal, clamped to a sane pixel range
        const dotSize = Math.max(10, Math.min(26, 8 + point.frp / 6));

        // Fade older detections out — full opacity when brand new,
        // fading toward 0.3 opacity by 36 hours old
        const opacity = Math.max(0.3, 1 - point.age / 36);

        const icon = L.divIcon({
          className: '', // avoid Leaflet's default marker styling
          html: `<div class="detection-dot" style="width:${dotSize}px;height:${dotSize}px;opacity:${opacity}"></div>`,
          iconSize: [dotSize, dotSize]
        });

        L.marker([point.lat, point.lon], { icon })
          .bindPopup(`
            <b>${point.sat}</b> · FRP ${point.frp} MW<br>
            ${point.d} km away · ${point.age} h ago<br>
            score ${point.score}<br>
            <i>heat anomaly, not confirmed fire</i>
          `)
          .addTo(resultsLayer);
      });
    }

    // Run an initial scan with the default coordinates on page load
    scanForFires();
  </script>

</body>
</html>"""

@app.get("/")
def home(): return Response(HTML, mimetype="text/html")
app.run(port=2704)
