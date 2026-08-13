const byId = (id) => document.getElementById(id);

const map = L.map('map').setView([34.05, -118.24], 7);

L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  attribution: 'OSM/CARTO'
}).addTo(map);

let resultsLayer = L.layerGroup().addTo(map);

async function scanForFires() {
  const lat = +byId('lat-input').value;
  const lon = +byId('lon-input').value;
  const radiusKm = +byId('radius-input').value;

  resultsLayer.clearLayers();
  map.flyTo([lat, lon], 8);

  L.circle([lat, lon], {
    radius: radiusKm * 1000,
    color: '#ff5a1f',
    weight: 1.5,
    dashArray: '4 8',
    fillOpacity: .04
  }).addTo(resultsLayer);

  L.circleMarker([lat, lon], {
    radius: 6,
    color: '#e8ded2',
    fillColor: '#ff5a1f',
    fillOpacity: 1
  }).addTo(resultsLayer);

  const response = await fetch(`/api/fires?lat=${lat}&lon=${lon}&rad=${radiusKm}`);
  const detections = await response.json();

  detections.forEach((point) => {
    const dotSize = Math.max(10, Math.min(26, 8 + point.frp / 6));

    const opacity = Math.max(0.3, 1 - point.age / 36);

    const icon = L.divIcon({
      className: '',
      html: `<div class="detection-dot" style="width:${dotSize}px;height:${dotSize}px;opacity:${opacity}"></div>`,
      iconSize: [dotSize, dotSize]
    });

    L.marker([point.lat, point.lon], { icon })
      .bindPopup(`
        <b>${point.sat}</b> · FRP ${point.frp} MW<br>
        ${point.d} km away · ${point.age} h ago<br>
        score ${point.score}<br>
      `)
      .addTo(resultsLayer);
  });
}

scanForFires();