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
