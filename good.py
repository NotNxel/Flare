import os, time, math, json, random, threading
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, request, jsonify, Response

FIRMS_KEY = os.environ.get("FIRMS_MAP_KEY", "")
AIRNOW_KEY = os.environ.get("AIRNOW_API_KEY", "")
DEMO = not FIRMS_KEY

FIRMS_SOURCES = ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"]
UA = {"User-Agent": "Flare-wildfire-context-app (educational project)"}

app = Flask(__name__)

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FLARE — wildfire context</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{
  --char:#0b0908;        /* charred ground */
  --smoke:#171310;
  --ash:#2a2320;
  --bone:#e8ded2;        /* text */
  --dim:#9a8c7c;
  --ember:#ff5a1f;       /* signature */
  --heat:#ffb02e;
  --blood:#e0301e;
  --safe:#7fb069;
  --mono:'JetBrains Mono',monospace;
}
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%}
body{background:var(--char);color:var(--bone);font-family:'Archivo',sans-serif;overflow:hidden}

/* ---------- layout ---------- */
#app{display:grid;grid-template-columns:380px 1fr;grid-template-rows:64px 1fr;height:100vh}
header{grid-column:1/3;display:flex;align-items:center;gap:16px;padding:0 22px;border-bottom:1px solid var(--ash);background:var(--smoke);z-index:500}
aside{border-right:1px solid var(--ash);background:var(--smoke);overflow-y:auto;padding:18px;display:flex;flex-direction:column;gap:18px}
#mapwrap{position:relative}
#map{height:100%;width:100%;background:#000}

/* ---------- header ---------- */
.logo{font-weight:900;font-stretch:120%;font-size:26px;letter-spacing:.06em;position:relative}
.logo b{color:var(--ember)}
.logo::after{content:"";position:absolute;left:0;bottom:-4px;width:100%;height:2px;
  background:linear-gradient(90deg,var(--ember),var(--heat),transparent);
  animation:burn 3s linear infinite;background-size:200% 100%}
@keyframes burn{to{background-position:-200% 0}}
.tag{font-family:var(--mono);font-size:11px;color:var(--dim)}
#demoBadge{margin-left:auto;font-family:var(--mono);font-size:11px;padding:4px 10px;border:1px solid var(--heat);color:var(--heat);border-radius:2px;display:none}

/* ---------- panel ---------- */
h2{font-size:11px;font-family:var(--mono);text-transform:uppercase;letter-spacing:.2em;color:var(--dim);margin-bottom:10px}
.card{background:var(--char);border:1px solid var(--ash);padding:14px;border-radius:3px}
input,button{font-family:inherit;font-size:14px}
input{width:100%;background:var(--smoke);border:1px solid var(--ash);color:var(--bone);padding:10px 12px;border-radius:2px;margin-bottom:8px;transition:border-color .2s}
input:focus{outline:none;border-color:var(--ember)}
.row{display:flex;gap:8px}
button{cursor:pointer;background:var(--ember);border:none;color:#140b06;font-weight:700;padding:10px 14px;border-radius:2px;transition:transform .12s,box-shadow .2s;width:100%}
button:hover{transform:translateY(-1px);box-shadow:0 0 22px rgba(255,90,31,.45)}
button:active{transform:translateY(0)}
button.ghost{background:transparent;border:1px solid var(--ash);color:var(--dim);width:auto}
button.ghost:hover{border-color:var(--ember);color:var(--ember);box-shadow:none}
button.ghost.on{border-color:var(--ember);color:var(--ember)}

/* location list */
.loc{display:flex;align-items:center;gap:12px;padding:11px 12px;border:1px solid var(--ash);border-radius:3px;margin-bottom:8px;cursor:pointer;transition:border-color .2s,background .2s;animation:rise .35s ease both}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.loc:hover,.loc.active{border-color:var(--ember);background:rgba(255,90,31,.05)}
.loc .nm{flex:1;font-weight:600;font-size:14px}
.loc .meta{font-family:var(--mono);font-size:10px;color:var(--dim)}
.loc .x{color:var(--dim);background:none;border:none;width:auto;padding:2px 6px;font-size:16px}
.loc .x:hover{color:var(--blood);box-shadow:none;transform:none}

/* score ring */
.ringwrap{display:flex;align-items:center;gap:16px}
.ring{position:relative;width:92px;height:92px;flex:none}
.ring svg{transform:rotate(-90deg)}
.ring circle{fill:none;stroke-width:7}
.ring .bg{stroke:var(--ash)}
.ring .fg{stroke:var(--ember);stroke-linecap:round;stroke-dasharray:264;stroke-dashoffset:264;transition:stroke-dashoffset 1.2s cubic-bezier(.2,.8,.2,1),stroke .5s}
.ring .val{position:absolute;inset:0;display:grid;place-items:center;font-family:var(--mono);font-weight:600;font-size:24px}
.ring .val small{font-size:9px;color:var(--dim);display:block;text-align:center}
.reasons{font-size:12.5px;line-height:1.55;color:var(--bone)}
.reasons li{margin-left:16px;margin-bottom:3px}
.limited{font-family:var(--mono);font-size:10px;color:var(--heat);margin-top:6px}

/* alerts */
.alert{border-left:3px solid var(--ember);background:rgba(255,90,31,.06);padding:10px 12px;margin-bottom:8px;border-radius:0 3px 3px 0;animation:flashin .5s ease both}
@keyframes flashin{0%{opacity:0;transform:translateX(-10px);background:rgba(255,90,31,.35)}100%{opacity:1;transform:none}}
.alert .t{font-weight:700;font-size:13px}
.alert .m{font-family:var(--mono);font-size:10.5px;color:var(--dim);margin-top:3px}

/* timeline */
#timeline{position:absolute;left:50%;transform:translateX(-50%);bottom:22px;width:min(680px,88%);background:rgba(11,9,8,.88);backdrop-filter:blur(8px);border:1px solid var(--ash);border-radius:4px;padding:12px 18px;z-index:600}
#timeline .lbl{display:flex;justify-content:space-between;font-family:var(--mono);font-size:10px;color:var(--dim);margin-bottom:6px}
#tslider{width:100%;accent-color:var(--ember)}
#tplay{width:auto;padding:4px 12px;font-size:12px;margin-top:6px}

/* map markers */
.det{border-radius:50%;background:radial-gradient(circle,var(--heat) 0%,var(--ember) 45%,transparent 70%);animation:pulse 1.8s ease-out infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(255,90,31,.7)}70%{box-shadow:0 0 0 14px rgba(255,90,31,0)}100%{box-shadow:0 0 0 0 rgba(255,90,31,0)}}
.home{width:14px;height:14px;background:var(--bone);border:3px solid var(--ember);border-radius:50%;box-shadow:0 0 16px rgba(255,90,31,.8)}
.leaflet-container{font-family:var(--mono)}
.leaflet-popup-content-wrapper{background:var(--smoke);color:var(--bone);border:1px solid var(--ash);border-radius:3px}
.leaflet-popup-tip{background:var(--smoke)}

/* embers canvas */
#embers{position:fixed;inset:0;pointer-events:none;z-index:2000}
.disclaimer{font-size:10.5px;font-family:var(--mono);color:var(--dim);line-height:1.5}
#fenceHint{position:absolute;top:14px;left:50%;transform:translateX(-50%);z-index:700;background:var(--ember);color:#140b06;font-weight:700;padding:8px 16px;border-radius:3px;display:none;animation:rise .3s ease}
@media (prefers-reduced-motion: reduce){*{animation:none!important;transition:none!important}}
@media (max-width:860px){#app{grid-template-columns:1fr;grid-template-rows:64px 45vh 1fr}aside{order:2;border-right:none;border-top:1px solid var(--ash)}}
</style>
</head>
<body>
<canvas id="embers"></canvas>
<div id="app">
  <header>
    <div class="logo">FLA<b>RE</b></div>
    <div class="tag">satellite fire detections · weather · air quality — informational only, not an emergency service</div>
    <div id="demoBadge">DEMO DATA</div>
  </header>

  <aside>
    <div>
      <h2>Save a location</h2>
      <div class="card">
        <input id="addr" placeholder="Address (e.g. 123 Main St, Sacramento CA)">
        <input id="lname" placeholder="Label (Home, Mom's house…)">
        <div class="row">
          <input id="radius" type="number" value="50" min="5" max="200" title="Alert radius km">
          <button id="addBtn">Track it</button>
        </div>
        <div class="disclaimer" style="margin-top:6px">radius in km · or click the map to drop a pin</div>
      </div>
    </div>

    <div>
      <h2>Locations</h2>
      <div id="locs"></div>
    </div>

    <div id="scoreBox" style="display:none">
      <h2>Context score</h2>
      <div class="card">
        <div class="ringwrap">
          <div class="ring">
            <svg width="92" height="92"><circle class="bg" cx="46" cy="46" r="42"/><circle class="fg" id="ringFg" cx="46" cy="46" r="42"/></svg>
            <div class="val"><div><span id="ringVal">0</span><small>/ 100</small></div></div>
          </div>
          <div>
            <div style="font-weight:700" id="scoreTitle">—</div>
            <div class="disclaimer">context score, not an official danger rating or fire-spread prediction</div>
            <button class="ghost" id="fenceBtn" style="margin-top:8px;font-size:12px">✏ draw custom geofence</button>
          </div>
        </div>
        <ul class="reasons" id="reasonList" style="margin-top:12px"></ul>
        <div class="limited" id="limitedNote"></div>
      </div>
    </div>

    <div>
      <h2>Alerts</h2>
      <div id="alertFeed"><div class="disclaimer">no alerts yet</div></div>
    </div>
  </aside>

  <div id="mapwrap">
    <div id="fenceHint">click to add points · double-click to close the fence</div>
    <div id="map"></div>
    <div id="timeline" style="display:none">
      <div class="lbl"><span>detected activity — last 30 h</span><span id="tlabel">now</span></div>
      <input id="tslider" type="range" min="0" max="30" step="0.5" value="30">
      <button id="tplay" class="ghost">▶ replay</button>
    </div>
  </div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
/* ---------------- ember particles ---------------- */
const cv=document.getElementById('embers'),cx=cv.getContext('2d');
let P=[];function rs(){cv.width=innerWidth;cv.height=innerHeight}rs();addEventListener('resize',rs);
function spawn(){if(P.length<40&&!matchMedia('(prefers-reduced-motion: reduce)').matches)
  P.push({x:Math.random()*cv.width,y:cv.height+8,r:Math.random()*2+.6,vy:-(Math.random()*.7+.25),vx:(Math.random()-.5)*.4,a:Math.random()*.55+.15,hue:Math.random()<.7?20:35});}
(function tick(){cx.clearRect(0,0,cv.width,cv.height);spawn();
  P=P.filter(p=>p.y>-10&&p.a>0);
  for(const p of P){p.x+=p.vx+Math.sin(p.y*.01)*.3;p.y+=p.vy;p.a-=.0012;
    cx.beginPath();cx.arc(p.x,p.y,p.r,0,7);cx.fillStyle=`hsla(${p.hue},100%,58%,${p.a})`;cx.fill();}
  requestAnimationFrame(tick)})();

/* ---------------- map ---------------- */
const map=L.map('map',{zoomControl:false}).setView([37.5,-119.5],6);
L.control.zoom({position:'bottomright'}).addTo(map);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
  {attribution:'&copy; OSM &copy; CARTO',maxZoom:19}).addTo(map);

let layers=L.layerGroup().addTo(map), fenceLayer=L.layerGroup().addTo(map);
let LOCS=[],CUR=null,CURDATA=null,drawing=false,fencePts=[],fencePreview=null;

const $=id=>document.getElementById(id);
const fmt=t=>new Date(t).toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});

fetch('/api/status').then(r=>r.json()).then(s=>{if(s.demo)$('demoBadge').style.display='block'});

/* ---------------- locations ---------------- */
async function loadLocs(){LOCS=await (await fetch('/api/locations')).json();renderLocs();}
function renderLocs(){
  $('locs').innerHTML=LOCS.length?'':'<div class="disclaimer">nothing tracked yet</div>';
  LOCS.forEach(l=>{
    const d=document.createElement('div');d.className='loc'+(CUR&&CUR.id===l.id?' active':'');
    d.innerHTML=`<div><div class="nm">${l.name}</div><div class="meta">${l.lat.toFixed(3)}, ${l.lon.toFixed(3)} · ${l.fence?'custom fence':l.radius_km+' km radius'}</div></div><button class="x">×</button>`;
    d.querySelector('.x').onclick=async e=>{e.stopPropagation();await fetch('/api/locations/'+l.id,{method:'DELETE'});if(CUR&&CUR.id===l.id){CUR=null;$('scoreBox').style.display='none';$('timeline').style.display='none';layers.clearLayers();fenceLayer.clearLayers();}loadLocs();};
    d.onclick=()=>select(l);
    $('locs').appendChild(d);
  });
}
$('addBtn').onclick=async()=>{
  const addr=$('addr').value.trim();if(!addr)return $('addr').focus();
  $('addBtn').textContent='…';
  const r=await fetch('/api/locations',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({address:addr,name:$('lname').value.trim(),radius_km:+$('radius').value||50})});
  $('addBtn').textContent='Track it';
  const j=await r.json();
  if(j.error)return alert(j.error);
  $('addr').value='';$('lname').value='';
  await loadLocs();select(j);
};
map.on('click',async e=>{
  if(drawing){fencePts.push([e.latlng.lat,e.latlng.lng]);drawFencePreview();return;}
  if(e.originalEvent.detail>1)return;
  const name=prompt('Label this pin (blank = skip):');if(name===null)return;
  const r=await fetch('/api/locations',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({lat:e.latlng.lat,lon:e.latlng.lng,name:name||'Pinned spot',radius_km:+$('radius').value||50})});
  const j=await r.json();await loadLocs();select(j);
});

/* ---------------- geofence drawing ---------------- */
$('fenceBtn').onclick=()=>{
  if(!CUR)return;
  drawing=!drawing;fencePts=[];
  $('fenceBtn').classList.toggle('on',drawing);
  $('fenceHint').style.display=drawing?'block':'none';
  if(!drawing&&fencePreview){map.removeLayer(fencePreview);fencePreview=null;}
};
function drawFencePreview(){
  if(fencePreview)map.removeLayer(fencePreview);
  fencePreview=L.polyline(fencePts,{color:'#ffb02e',dashArray:'6 6',weight:2}).addTo(map);
}
map.on('dblclick',async e=>{
  if(!drawing||fencePts.length<3)return;
  drawing=false;$('fenceHint').style.display='none';$('fenceBtn').classList.remove('on');
  if(fencePreview){map.removeLayer(fencePreview);fencePreview=null;}
  await fetch(`/api/locations/${CUR.id}/fence`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({fence:fencePts})});
  fencePts=[];await loadLocs();
  CUR=LOCS.find(l=>l.id===CUR.id);select(CUR);
});
map.doubleClickZoom.disable();

/* ---------------- assessment + render ---------------- */
async function select(l){
  CUR=l;renderLocs();
  map.flyTo([l.lat,l.lon],9,{duration:1.2});
  const j=await (await fetch(`/api/locations/${l.id}/assess`)).json();
  CURDATA=j;render(j);pollAlerts();
}
function render(j){
  layers.clearLayers();fenceLayer.clearLayers();
  const l=j.location;

  L.marker([l.lat,l.lon],{icon:L.divIcon({className:'',html:'<div class="home"></div>',iconSize:[14,14]})})
    .addTo(layers).bindPopup(`<b>${l.name}</b>`);
  if(l.fence)L.polygon(l.fence,{color:'#ff5a1f',weight:2,fillOpacity:.06}).addTo(fenceLayer);
  else L.circle([l.lat,l.lon],{radius:l.radius_km*1000,color:'#ff5a1f',weight:1.5,dashArray:'4 8',fillOpacity:.04}).addTo(fenceLayer);

  renderPoints(30); // full window
  $('timeline').style.display='block';
  $('tslider').value=30;$('tlabel').textContent='now';

  // score panel = top cluster
  $('scoreBox').style.display='block';
  const top=j.clusters[0];
  const s=top?top.assessment.score:0;
  $('ringVal').textContent=Math.round(s);
  const fg=$('ringFg');fg.style.strokeDashoffset=264-264*(s/100);
  fg.style.stroke=s>=60?'var(--blood)':s>=30?'var(--ember)':'var(--safe)';
  $('scoreTitle').textContent=top?`${l.name} — nearest activity ${top.assessment.distance_km} km`:`${l.name} — no detections in range`;
  $('reasonList').innerHTML=top?top.assessment.reasons.map(r=>`<li>${r}</li>`).join(''):'';
  $('limitedNote').textContent=top&&top.assessment.limited_data.length?`⚠ limited data: ${top.assessment.limited_data.join(', ')} unavailable`:'';
}
function renderPoints(hoursBack){
  layers.eachLayer(x=>{if(x._flarePt)layers.removeLayer(x)});
  if(!CURDATA)return;
  const cutoff=Date.now()-hoursBack*3600e3;
  CURDATA.clusters.forEach(c=>{
    c.points.forEach(p=>{
      if(new Date(p.time).getTime()<cutoff&&hoursBack<30)return;
      const age=(Date.now()-new Date(p.time).getTime())/3600e3;
      const sz=Math.max(10,Math.min(26,8+p.frp/6));
      const op=Math.max(.25,1-age/36);
      const m=L.marker([p.lat,p.lon],{icon:L.divIcon({className:'',
        html:`<div class="det" style="width:${sz}px;height:${sz}px;opacity:${op}"></div>`,iconSize:[sz,sz]})});
      m._flarePt=true;
      m.bindPopup(`<b>${p.sat}</b> · conf ${p.confidence}<br>FRP ${p.frp} MW<br>${fmt(p.time)}<br><i>satellite heat anomaly — not a confirmed wildfire</i>`);
      m.addTo(layers);
    });
  });
}

/* timeline replay */
$('tslider').oninput=e=>{
  const h=+e.target.value;
  $('tlabel').textContent=h>=30?'now':`-${(30-h).toFixed(1)} h`;
  renderPoints(h);
};
$('tplay').onclick=()=>{
  let h=0;$('tplay').textContent='…';
  const iv=setInterval(()=>{h+=.5;$('tslider').value=h;$('tslider').dispatchEvent(new Event('input'));
    if(h>=30){clearInterval(iv);$('tplay').textContent='▶ replay';}},120);
};

/* ---------------- alerts ---------------- */
async function pollAlerts(){
  const a=await (await fetch('/api/alerts')).json();
  $('alertFeed').innerHTML=a.length?'':'<div class="disclaimer">no alerts yet</div>';
  a.slice(0,12).forEach(x=>{
    const d=document.createElement('div');d.className='alert';
    d.innerHTML=`<div class="t">${x.trigger}</div>
      <div class="m">${x.location} · ${x.distance_km} km · ${x.sats.join('+')} · score ${x.score}<br>${fmt(x.time)}</div>`;
    $('alertFeed').appendChild(d);
  });
}
setInterval(()=>{if(CUR)pollAlerts()},30000);
loadLocs();
</script>
</body>
</html>
"""

# ------------------------------------------------------------------ state
LOCK = threading.Lock()
STATE = {
    "locations": {},   # id -> {id,name,lat,lon,radius_km, fence: [[lat,lon],...] or None}
    "alerts": [],      # newest first
    "seen_clusters": {},  # loc_id -> {cluster_key: {"sats": set-> list, "score": float}}
    "next_id": 1,
}

# ------------------------------------------------------------------ geo math
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

def bearing_deg(lat1, lon1, lat2, lon2):
    """Initial bearing from point 1 to point 2, degrees clockwise from north."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def angdiff(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)

def point_in_polygon(lat, lon, poly):
    """Ray casting. poly = [[lat,lon], ...]. Proper geofencing, as requested."""
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        yi, xi = poly[i]; yj, xj = poly[j]
        if ((xi > lon) != (xj > lon)) and (lat < (yj - yi) * (lon - xi) / ((xj - xi) or 1e-12) + yi):
            inside = not inside
        j = i
    return inside

def dist_to_polygon_km(lat, lon, poly):
    """0 if inside, else min distance to any vertex/edge midpoint (approx)."""
    if point_in_polygon(lat, lon, poly):
        return 0.0
    best = float("inf")
    for i in range(len(poly)):
        a = poly[i]; b = poly[(i + 1) % len(poly)]
        for t in (0, 0.25, 0.5, 0.75, 1):
            p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            best = min(best, haversine_km(lat, lon, p[0], p[1]))
    return best

# ------------------------------------------------------------------ geocoding
def geocode(addr):
    # US Census first
    try:
        r = requests.get(
            "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress",
            params={"address": addr, "benchmark": "Public_AR_Current", "format": "json"},
            timeout=8, headers=UA)
        m = r.json()["result"]["addressMatches"]
        if m:
            c = m[0]["coordinates"]
            return float(c["y"]), float(c["x"]), m[0]["matchedAddress"]
    except Exception:
        pass
    # Fallback: Nominatim (worldwide)
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search",
                         params={"q": addr, "format": "json", "limit": 1},
                         timeout=8, headers=UA)
        j = r.json()
        if j:
            return float(j[0]["lat"]), float(j[0]["lon"]), j[0]["display_name"]
    except Exception:
        pass
    return None

# ------------------------------------------------------------------ FIRMS
_firms_cache = {}  # bbox_key -> (ts, detections)

def fetch_firms(lat, lon, radius_km, days=2):
    """All VIIRS detections in a bbox around the point. Cached 10 min."""
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(0.2, math.cos(math.radians(lat))))
    bbox = (round(lon - dlon, 2), round(lat - dlat, 2), round(lon + dlon, 2), round(lat + dlat, 2))
    key = f"{bbox}-{days}"
    now = time.time()
    if key in _firms_cache and now - _firms_cache[key][0] < 600:
        return _firms_cache[key][1]

    dets = []
    if DEMO:
        dets = demo_detections(lat, lon, radius_km)
    else:
        area = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
        for src in FIRMS_SOURCES:
            try:
                url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_KEY}/{src}/{area}/{days}"
                r = requests.get(url, timeout=15, headers=UA)
                lines = r.text.strip().splitlines()
                if len(lines) < 2:
                    continue
                hdr = lines[0].split(",")
                idx = {h: i for i, h in enumerate(hdr)}
                for ln in lines[1:]:
                    c = ln.split(",")
                    try:
                        acq = datetime.strptime(
                            c[idx["acq_date"]] + c[idx["acq_time"]].zfill(4),
                            "%Y-%m-%d%H%M").replace(tzinfo=timezone.utc)
                        dets.append({
                            "lat": float(c[idx["latitude"]]),
                            "lon": float(c[idx["longitude"]]),
                            "time": acq.isoformat(),
                            "sat": src.replace("VIIRS_", "").replace("_NRT", ""),
                            "confidence": c[idx.get("confidence", 0)],
                            "frp": float(c[idx["frp"]]) if c[idx["frp"]] else 0.0,
                        })
                    except Exception:
                        continue
            except Exception:
                continue
    _firms_cache[key] = (now, dets)
    return dets

def demo_detections(lat, lon, radius_km):
    """Deterministic-ish synthetic fires so the demo feels alive."""
    rng = random.Random(int(lat * 100) ^ int(lon * 100))
    dets = []
    now = datetime.now(timezone.utc)
    for f in range(rng.randint(2, 4)):  # 2-4 fire complexes
        ang = rng.uniform(0, 360)
        dist = rng.uniform(radius_km * 0.15, radius_km * 0.9)
        fl = lat + (dist / 111) * math.cos(math.radians(ang))
        fo = lon + (dist / (111 * math.cos(math.radians(lat)))) * math.sin(math.radians(ang))
        n = rng.randint(3, 14)
        for i in range(n):
            dets.append({
                "lat": fl + rng.gauss(0, 0.012),
                "lon": fo + rng.gauss(0, 0.012),
                "time": (now - timedelta(hours=rng.uniform(0.3, 30))).isoformat(),
                "sat": rng.choice(["SNPP", "NOAA20", "NOAA21"]),
                "confidence": rng.choice(["n", "n", "h", "l"]),
                "frp": round(rng.uniform(1, 90), 1),
            })
    return dets

# ------------------------------------------------------------------ clustering
def cluster(dets, eps_km=3.0):
    """Greedy spatial clustering — one fire can produce many pixels."""
    clusters = []
    for d in sorted(dets, key=lambda x: x["time"]):
        placed = False
        for c in clusters:
            if haversine_km(d["lat"], d["lon"], c["lat"], c["lon"]) <= eps_km:
                k = len(c["points"])
                c["lat"] = (c["lat"] * k + d["lat"]) / (k + 1)
                c["lon"] = (c["lon"] * k + d["lon"]) / (k + 1)
                c["points"].append(d)
                placed = True
                break
        if not placed:
            clusters.append({"lat": d["lat"], "lon": d["lon"], "points": [d]})
    out = []
    conf_rank = {"l": 0, "low": 0, "n": 1, "nominal": 1, "h": 2, "high": 2}
    for c in clusters:
        pts = c["points"]
        sats = sorted({p["sat"] for p in pts})
        best_conf = max(pts, key=lambda p: conf_rank.get(str(p["confidence"]).lower(), 1))
        out.append({
            "lat": round(c["lat"], 4), "lon": round(c["lon"], 4),
            "first": min(p["time"] for p in pts),
            "latest": max(p["time"] for p in pts),
            "count": len(pts), "sats": sats,
            "confidence": best_conf["confidence"],
            "max_frp": max(p["frp"] for p in pts),
            "points": pts,
        })
    return out

# ------------------------------------------------------------------ weather / AQI
_wx_cache = {}
def fetch_weather(lat, lon):
    key = f"{round(lat,1)},{round(lon,1)}"
    if key in _wx_cache and time.time() - _wx_cache[key][0] < 1800:
        return _wx_cache[key][1]
    wx = None
    if DEMO:
        rng = random.Random(key)
        wx = {"wind_speed_kmh": round(rng.uniform(5, 45), 1),
              "wind_dir_from": rng.randrange(0, 360, 10),
              "humidity": rng.randint(12, 70),
              "updated": datetime.now(timezone.utc).isoformat(), "source": "demo"}
    else:
        try:
            p = requests.get(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}",
                             timeout=8, headers=UA).json()
            g = requests.get(p["properties"]["forecastGridData"], timeout=10, headers=UA).json()
            pr = g["properties"]
            def latest(prop, scale=1.0):
                vals = pr.get(prop, {}).get("values", [])
                return round(vals[0]["value"] * scale, 1) if vals and vals[0]["value"] is not None else None
            wx = {"wind_speed_kmh": latest("windSpeed"),
                  "wind_dir_from": latest("windDirection"),
                  "humidity": latest("relativeHumidity"),
                  "updated": pr.get("updateTime"), "source": "NWS"}
        except Exception:
            wx = None
    _wx_cache[key] = (time.time(), wx)
    return wx

def fetch_aqi(lat, lon):
    if DEMO or not AIRNOW_KEY:
        if DEMO:
            rng = random.Random(f"aqi{round(lat,1)}{round(lon,1)}")
            return {"aqi": rng.randint(20, 160), "pollutant": "PM2.5",
                    "updated": datetime.now(timezone.utc).isoformat(), "source": "demo"}
        return None
    try:
        r = requests.get("https://www.airnowapi.org/aq/observation/latLong/current/",
                         params={"format": "application/json", "latitude": lat,
                                 "longitude": lon, "distance": 60, "API_KEY": AIRNOW_KEY},
                         timeout=8, headers=UA).json()
        pm = [o for o in r if o.get("ParameterName") == "PM2.5"] or r
        if pm:
            o = pm[0]
            return {"aqi": o["AQI"], "pollutant": o["ParameterName"],
                    "updated": f'{o["DateObserved"]} {o["HourObserved"]}:00 UTC-ish',
                    "source": "AirNow"}
    except Exception:
        pass
    return None

# ------------------------------------------------------------------ scoring
def score_cluster(loc, c, wx, aqi):
    reasons, limited = [], []
    now = datetime.now(timezone.utc)

    if loc.get("fence"):
        d = dist_to_polygon_km(c["lat"], c["lon"], loc["fence"])
        in_fence = d == 0.0
    else:
        d = haversine_km(loc["lat"], loc["lon"], c["lat"], c["lon"])
        in_fence = d <= loc["radius_km"]

    age_h = max(0.1, (now - datetime.fromisoformat(c["latest"])).total_seconds() / 3600)

    s_dist = max(0, 40 * (1 - d / max(loc["radius_km"], 1)))          # 0-40
    s_age = max(0, 25 * (1 - age_h / 48))                             # 0-25
    conf = str(c["confidence"]).lower()
    s_conf = {"h": 10, "high": 10, "n": 6, "nominal": 6}.get(conf, 3) # ≤10
    s_frp = min(8, c["max_frp"] / 12)                                 # ≤8
    s_multi = min(7, (len(c["sats"]) - 1) * 3.5 + min(3, c["count"] / 5))  # ≤7

    s_wind = 0
    if wx and wx.get("wind_dir_from") is not None:
        toward = (wx["wind_dir_from"] + 180) % 360
        brg = bearing_deg(c["lat"], c["lon"], loc["lat"], loc["lon"])
        if angdiff(toward, brg) < 45:
            s_wind = 6 + min(4, (wx.get("wind_speed_kmh") or 0) / 12)
            reasons.append(f"location is downwind ({wx['wind_speed_kmh']} km/h wind)")
        if wx.get("humidity") is not None and wx["humidity"] < 25:
            s_wind += 2
            reasons.append(f"very dry air ({wx['humidity']}% RH)")
    else:
        limited.append("weather")

    s_aqi = 0
    if aqi and aqi.get("aqi") is not None:
        if aqi["aqi"] > 100:
            s_aqi = min(8, (aqi["aqi"] - 100) / 15)
            reasons.append(f"elevated PM2.5 (AQI {aqi['aqi']})")
    else:
        limited.append("air quality")

    if d < loc["radius_km"] * 0.35 or (loc.get("fence") and in_fence):
        reasons.insert(0, f"detection {d:.1f} km away — inside your zone" if in_fence
                       else f"detection only {d:.1f} km away")
    elif in_fence:
        reasons.insert(0, f"detection {d:.1f} km away, within alert radius")
    if age_h < 6:
        reasons.insert(1 if reasons else 0, f"detected {age_h:.1f} h ago (recent)")
    if len(c["sats"]) > 1:
        reasons.append(f"confirmed by {len(c['sats'])} satellites")

    total = round(min(100, s_dist + s_age + s_conf + s_frp + s_multi + s_wind + s_aqi), 1)
    return {"score": total, "distance_km": round(d, 2), "in_fence": in_fence,
            "age_hours": round(age_h, 1), "reasons": reasons, "limited_data": limited}

# ------------------------------------------------------------------ alerts
def check_alerts(loc, assessed):
    with LOCK:
        seen = STATE["seen_clusters"].setdefault(loc["id"], {})
        for a in assessed:
            if not a["assessment"]["in_fence"]:
                continue
            c = a["cluster"]
            key = f'{round(c["lat"],2)},{round(c["lon"],2)}'
            prev = seen.get(key)
            trig = None
            if prev is None:
                trig = "New detection group inside alert zone"
            elif set(c["sats"]) - set(prev["sats"]):
                trig = "Another satellite detected activity in the same area"
            elif a["assessment"]["score"] >= prev["score"] + 15:
                trig = "Context score increased significantly"
            if trig:
                STATE["alerts"].insert(0, {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "location": loc["name"], "loc_id": loc["id"],
                    "trigger": trig,
                    "distance_km": a["assessment"]["distance_km"],
                    "detected": c["latest"], "confidence": c["confidence"],
                    "sats": c["sats"], "score": a["assessment"]["score"],
                    "reasons": a["assessment"]["reasons"],
                })
                STATE["alerts"] = STATE["alerts"][:100]
            seen[key] = {"sats": list(c["sats"]), "score": a["assessment"]["score"]}

# ------------------------------------------------------------------ routes
@app.get("/")
def index():
    return Response(HTML, mimetype="text/html")

@app.get("/api/status")
def status():
    return jsonify({"demo": DEMO, "sources": FIRMS_SOURCES})

@app.post("/api/locations")
def add_location():
    b = request.json
    lat, lon, label = None, None, b.get("name", "")
    if b.get("lat") is not None:
        lat, lon = float(b["lat"]), float(b["lon"])
    else:
        g = geocode(b["address"])
        if not g:
            return jsonify({"error": "Could not geocode that address"}), 400
        lat, lon, label = g
    with LOCK:
        lid = STATE["next_id"]; STATE["next_id"] += 1
        loc = {"id": lid, "name": b.get("name") or label or f"Location {lid}",
               "lat": lat, "lon": lon,
               "radius_km": float(b.get("radius_km", 50)),
               "fence": b.get("fence")}
        STATE["locations"][lid] = loc
    return jsonify(loc)

@app.get("/api/locations")
def list_locations():
    return jsonify(list(STATE["locations"].values()))

@app.delete("/api/locations/<int:lid>")
def del_location(lid):
    with LOCK:
        STATE["locations"].pop(lid, None)
        STATE["seen_clusters"].pop(lid, None)
    return jsonify({"ok": True})

@app.put("/api/locations/<int:lid>/fence")
def set_fence(lid):
    with LOCK:
        loc = STATE["locations"].get(lid)
        if not loc:
            return jsonify({"error": "not found"}), 404
        loc["fence"] = request.json.get("fence")
    return jsonify(loc)

@app.get("/api/locations/<int:lid>/assess")
def assess(lid):
    loc = STATE["locations"].get(lid)
    if not loc:
        return jsonify({"error": "not found"}), 404
    search_km = max(loc["radius_km"] * 2, 120)
    dets = fetch_firms(loc["lat"], loc["lon"], search_km)
    clusters = cluster(dets)
    out = []
    for c in clusters:
        wx = fetch_weather(c["lat"], c["lon"])
        aqi = fetch_aqi(loc["lat"], loc["lon"])
        a = score_cluster(loc, c, wx, aqi)
        out.append({"cluster": {k: v for k, v in c.items() if k != "points"},
                    "points": c["points"], "weather": wx, "aqi": aqi, "assessment": a})
    out.sort(key=lambda x: -x["assessment"]["score"])
    check_alerts(loc, out)
    top = out[0]["assessment"]["score"] if out else 0
    return jsonify({"location": loc, "clusters": out,
                    "top_score": top, "demo": DEMO,
                    "fetched": datetime.now(timezone.utc).isoformat()})

@app.get("/api/alerts")
def alerts():
    return jsonify(STATE["alerts"])

if __name__ == "__main__":
    print(("🔥 FLARE — DEMO MODE (no FIRMS_MAP_KEY set; synthetic detections)"
           if DEMO else "🔥 FLARE — live FIRMS data"))
    app.run(debug=True, port=5000)
