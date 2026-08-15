"""Render data/listings.json into docs/index.html (GitHub Pages).

Self-contained: listing data is embedded as JSON and filtered/sorted client-side.
Theme-aware (light/dark), responsive, no external requests.

Triage: each card has ✓ (save) and ✕ (reject). Decisions persist in the browser's
localStorage keyed by listing uid, so they survive the daily rebuild:
  · ✕ hides the listing permanently (even when tomorrow's run re-includes it)
  · ✓ snapshots it into a Saved view that survives even if it later delists
Export buttons let you push those decisions back to the repo (data/rejected.json)
for server-side exclusion / cross-device use.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(__file__))
DOCS = os.path.join(ROOT, "docs")


def build(listings: list, cfg: dict) -> str:
    os.makedirs(DOCS, exist_ok=True)
    title = cfg["output"].get("dashboard_title", "Apartment Finder")
    generated = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    payload = json.dumps(listings, ensure_ascii=False)
    new_count = sum(1 for l in listings if l.get("is_new"))

    html = _TEMPLATE.replace("__TITLE__", title) \
                    .replace("__GENERATED__", generated) \
                    .replace("__COUNT__", str(len(listings))) \
                    .replace("__NEW__", str(new_count)) \
                    .replace("__DATA__", payload)
    out = os.path.join(DOCS, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    return out


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script defer src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  :root{
    --bg:#f6f7f9; --card:#fff; --ink:#12161c; --muted:#5b6673; --line:#e5e8ec;
    --accent:#1f7a5a; --accent-ink:#fff; --new:#c2410c; --chip:#eef1f4;
    --yes:#1f7a5a; --no:#b91c1c; --shadow:0 1px 3px rgba(0,0,0,.08);
  }
  @media (prefers-color-scheme:dark){
    :root{--bg:#0e1116;--card:#171b22;--ink:#e6e9ee;--muted:#9aa4b2;--line:#252b34;
          --accent:#38b489;--accent-ink:#08130e;--new:#fb923c;--chip:#222833;
          --yes:#38b489;--no:#f87171;--shadow:0 1px 3px rgba(0,0,0,.4);}
  }
  *{box-sizing:border-box}
  body{margin:0;font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
       background:var(--bg);color:var(--ink)}
  header{padding:20px 16px 8px;max-width:1180px;margin:0 auto}
  h1{margin:0 0 2px;font-size:20px;letter-spacing:-.01em}
  .sub{color:var(--muted);font-size:13px}
  .sub a{color:var(--muted);text-decoration:underline;cursor:pointer}
  .bar{position:sticky;top:0;z-index:5;background:var(--bg);
       max-width:1180px;margin:0 auto;padding:10px 16px;display:flex;gap:8px;flex-wrap:wrap;
       align-items:center;border-bottom:1px solid var(--line)}
  select,button{font:inherit;color:var(--ink);background:var(--card);border:1px solid var(--line);
       border-radius:8px;padding:7px 10px;cursor:pointer}
  button.on{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
  .dd{position:relative}
  .dd>summary{list-style:none;cursor:pointer;background:var(--card);border:1px solid var(--line);
       border-radius:8px;padding:7px 10px;user-select:none;white-space:nowrap}
  .dd>summary::-webkit-details-marker{display:none}
  .dd[open]>summary{border-color:var(--accent)}
  .ddbody{position:absolute;top:calc(100% + 4px);left:0;z-index:20;background:var(--card);
       border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow);padding:8px;min-width:180px}
  .ddbody label{display:flex;align-items:center;gap:8px;padding:5px 6px;border-radius:6px;cursor:pointer;font-size:14px}
  .ddbody label:hover{background:var(--chip)}
  .ddall{border-bottom:1px solid var(--line);margin-bottom:4px;padding-bottom:6px!important;font-weight:600}
  .ddbody input[type=checkbox]{width:16px;height:16px;accent-color:var(--accent)}
  .spacer{flex:1}
  .link{background:none;border:none;color:var(--muted);text-decoration:underline;padding:7px 4px}
  .grid{max-width:1180px;margin:0 auto;padding:16px;display:grid;gap:14px;
        grid-template-columns:repeat(auto-fill,minmax(320px,1fr))}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;
        box-shadow:var(--shadow);display:flex;flex-direction:column;transition:opacity .15s}
  .card.saved{border-color:var(--yes);box-shadow:0 0 0 2px var(--yes) inset}
  .thumb{aspect-ratio:16/10;background:var(--chip) center/cover no-repeat;position:relative;
         touch-action:pan-y}
  .nav{position:absolute;top:50%;transform:translateY(-50%);width:32px;height:32px;padding:0;
       border:none;border-radius:50%;background:rgba(0,0,0,.45);color:#fff;font-size:18px;line-height:1;
       display:flex;align-items:center;justify-content:center;cursor:pointer;opacity:.55;transition:opacity .15s}
  .nav:hover{opacity:1;background:rgba(0,0,0,.7)}
  .nav.prev{left:8px} .nav.next{right:8px}
  .counter{position:absolute;bottom:8px;right:8px;background:rgba(0,0,0,.6);color:#fff;
           font-size:11px;padding:2px 8px;border-radius:10px;pointer-events:none}
  .badges{position:absolute;top:8px;left:8px;display:flex;gap:6px}
  .score{background:var(--accent);color:var(--accent-ink);font-weight:700;border-radius:20px;
         padding:3px 9px;font-size:13px}
  .newb{background:var(--new);color:#fff;border-radius:20px;padding:3px 9px;font-size:11px;
        font-weight:700;letter-spacing:.03em}
  .ptype{border-radius:20px;padding:3px 9px;font-size:11px;font-weight:700;letter-spacing:.03em}
  .ptype.casa{background:#b45309;color:#fff}
  .ptype.penthouse{background:#6d28d9;color:#fff}
  .src{position:absolute;top:8px;right:8px;background:rgba(0,0,0,.55);color:#fff;border-radius:6px;
       padding:2px 7px;font-size:11px}
  .body{padding:12px 13px 13px;display:flex;flex-direction:column;gap:8px;flex:1}
  .price{font-size:18px;font-weight:700}
  .price small{font-weight:500;color:var(--muted);font-size:12px}
  .meta{color:var(--muted);font-size:13px}
  .where{font-weight:600}
  .chips{display:flex;flex-wrap:wrap;gap:5px}
  .chip{background:var(--chip);border-radius:20px;padding:3px 8px;font-size:11.5px}
  .note{color:var(--new);font-size:12px}
  .foot{margin-top:auto;display:flex;justify-content:space-between;align-items:center;gap:8px}
  .acts{display:flex;gap:6px}
  .act{width:34px;height:34px;padding:0;border-radius:9px;font-size:16px;line-height:1;
       display:flex;align-items:center;justify-content:center}
  .act.save{width:auto;padding:0 11px;font-size:13px;font-weight:600;gap:5px}
  .act.no:hover{background:var(--no);color:#fff;border-color:var(--no)}
  .act.save:hover{border-color:var(--yes)}
  .act.save.on{background:var(--yes);color:#fff;border-color:var(--yes)}
  a.view{background:var(--accent);color:var(--accent-ink);text-decoration:none;font-weight:600;
         border-radius:8px;padding:7px 12px;font-size:13px}
  .empty{max-width:1180px;margin:40px auto;text-align:center;color:var(--muted)}
  #mapwrap{max-width:1180px;margin:0 auto;padding:16px;display:none}
  #map{height:70vh;min-height:420px;border-radius:12px;border:1px solid var(--line);z-index:1}
  .maphint{color:var(--muted);font-size:12px;margin:8px 2px 0;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
  .lg{display:inline-flex;align-items:center;gap:5px}
  .dot{width:11px;height:11px;border-radius:50%;display:inline-block}
  .pop{width:180px;font:13px/1.4 -apple-system,sans-serif}
  .pop img{width:100%;height:104px;object-fit:cover;border-radius:6px;display:block;margin-bottom:6px}
  .pop .pp{font-weight:700;font-size:14px}
  .pop .pm{color:#5b6673;font-size:12px;margin:2px 0 6px}
  .pop a{color:#1f7a5a;font-weight:600;text-decoration:none}
  footer{max-width:1180px;margin:0 auto;padding:8px 16px 40px;color:var(--muted);font-size:12px}
</style>
</head>
<body>
<header>
  <a href="visits.html" style="color:var(--accent);text-decoration:none;font-weight:600;font-size:13px">📋 Visit scorecard →</a>
  <a href="tryout.html" style="color:var(--muted);text-decoration:none;font-size:13px;margin-left:12px">🧭 Neighborhood tryout planner</a>
  <h1>__TITLE__</h1>
  <div class="sub"><span id="stat-count">__COUNT__ current matches</span> · <b>__NEW__ new today</b>
    · <span id="stat-saved">0 saved</span> · <span id="stat-hidden"></span>
    · updated __GENERATED__</div>
</header>
<div class="bar">
  <button id="savedBtn">★ Saved (<span id="savedN">0</span>)</button>
  <details class="dd" id="areaDD">
    <summary id="areaSum">All areas</summary>
    <div class="ddbody">
      <label class="ddall"><input type="checkbox" id="areaAll" checked> All areas</label>
      <div id="areaBoxes"></div>
    </div>
  </details>
  <select id="type"><option value="">All types</option></select>
  <select id="beds">
    <option value="">Any beds</option>
    <option value="1">1 bed</option>
    <option value="2">2 bed</option>
    <option value="3">3 bed</option>
    <option value="4">4+ bed</option>
  </select>
  <select id="src"><option value="">All sources</option></select>
  <select id="minscore">
    <option value="0">Any score</option>
    <option value="50">Score 50+</option>
    <option value="60">Score 60+</option>
    <option value="70">Score 70+</option>
    <option value="80">Score 80+</option>
  </select>
  <select id="sort">
    <option value="score">Sort: Best match</option>
    <option value="new">Sort: New first</option>
    <option value="price_asc">Sort: Price ↑</option>
    <option value="price_desc">Sort: Price ↓</option>
    <option value="area_desc">Sort: Size ↓</option>
    <option value="beds_desc">Sort: Bedrooms ↓</option>
    <option value="beds_asc">Sort: Bedrooms ↑</option>
  </select>
  <button id="newonly">Show new only</button>
  <button id="mapBtn">🗺 Map</button>
  <span class="spacer"></span>
  <button class="link" id="shareBroker">📤 Send to broker</button>
  <button class="link" id="exportViewX">⬇ View (Excel)</button>
  <button class="link" id="exportView">View (CSV)</button>
  <button class="link" id="exportSavedX">⬇ Saved (Excel)</button>
  <button class="link" id="exportSaved">Saved (CSV)</button>
  <button class="link" id="exportRej">Hidden</button>
</div>
<div class="grid" id="grid"></div>
<div id="mapwrap">
  <div id="map"></div>
  <div class="maphint">
    <span id="mapcount"></span>
    <span class="lg"><span class="dot" style="background:#1f7a5a"></span>Poblado</span>
    <span class="lg"><span class="dot" style="background:#6d28d9"></span>Laureles</span>
    <span class="lg"><span class="dot" style="background:#b45309"></span>Envigado</span>
    <span class="lg"><span class="dot" style="background:#0369a1"></span>Ciudad del Río</span>
    <span class="lg"><span class="dot" style="background:#db2777"></span>Las Palmas</span>
    <span class="lg"><span class="dot" style="background:#dc2626"></span>La Frontera</span>
  </div>
</div>
<div class="empty" id="empty" style="display:none"></div>
<footer>✓ saves to your list · ✕ hides a listing for good (recover with “reset” up top).
Decisions are stored in this browser. ⚠️ flags mean a spec (furnished / administración) couldn't be
auto-verified — check the listing. Prices are rent + administración in COP.</footer>
<script>
const DATA = __DATA__;
const grid=document.getElementById('grid'), empty=document.getElementById('empty');
const typeSel=document.getElementById('type'),
      srcSel=document.getElementById('src'), sortSel=document.getElementById('sort');
const areaSum=document.getElementById('areaSum'), areaBoxes=document.getElementById('areaBoxes'),
      areaAll=document.getElementById('areaAll');
const newBtn=document.getElementById('newonly'), savedBtn=document.getElementById('savedBtn');
const minScoreSel=document.getElementById('minscore'), bedsSel=document.getElementById('beds');
let newOnly=false, savedView=false, mapView=false;

// ---- persistent triage state (survives the daily rebuild) ----
const LS_REJ='maf.rejected', LS_SAVE='maf.saved';
let rejected=new Set(JSON.parse(localStorage.getItem(LS_REJ)||'[]'));
let saved=JSON.parse(localStorage.getItem(LS_SAVE)||'{}');   // uid -> listing snapshot
const byUid={}; DATA.forEach(d=>byUid[d.uid]=d);
function persist(){localStorage.setItem(LS_REJ,JSON.stringify([...rejected]));
  localStorage.setItem(LS_SAVE,JSON.stringify(saved));}

const areaLabel=k=>(k||'').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
const TYPE_LABEL={apartamento:'Apartments',casa:'Houses',penthouse:'Penthouses'};
const ALL_AREAS=[...new Set(DATA.map(d=>d.area_key).filter(Boolean))].sort();
ALL_AREAS.forEach(a=>{
  const lb=document.createElement('label');
  lb.innerHTML=`<input type="checkbox" class="areaChk" value="${a}" checked> ${areaLabel(a)}`;
  areaBoxes.appendChild(lb);
});
function checkedAreas(){ return new Set([...areaBoxes.querySelectorAll('.areaChk:checked')].map(c=>c.value)); }
function updateAreaSummary(){
  const chosen=checkedAreas(), n=chosen.size;
  areaAll.checked = n===ALL_AREAS.length;
  areaAll.indeterminate = n>0 && n<ALL_AREAS.length;
  areaSum.textContent = n===ALL_AREAS.length ? 'All areas'
    : n===0 ? 'No areas' : n===1 ? areaLabel([...chosen][0]) : n+' areas';
}
[...new Set(DATA.map(d=>d.property_type).filter(Boolean))].sort().forEach(t=>{
  const o=document.createElement('option');o.value=t;o.textContent=TYPE_LABEL[t]||areaLabel(t);typeSel.appendChild(o);});
[...new Set(DATA.map(d=>d.source))].sort().forEach(s=>{
  const o=document.createElement('option');o.value=s;o.textContent=s;srcSel.appendChild(o);});
const money=n=>n?('$'+n.toLocaleString('es-CO')+' COP'):'Precio n/d';

function updateStats(){
  const nSaved=Object.keys(saved).length, nHid=rejected.size;
  document.getElementById('savedN').textContent=nSaved;
  document.getElementById('stat-saved').textContent=nSaved+' saved';
  document.getElementById('stat-hidden').innerHTML = nHid
    ? nHid+' hidden (<a id="resetHid">reset</a>)' : '0 hidden';
  const r=document.getElementById('resetHid');
  if(r) r.onclick=()=>{ if(confirm('Un-hide all '+nHid+' rejected listings?')){
    rejected=new Set(); persist(); updateStats(); render(); } };
}

function currentRows(){
  let rows = savedView ? Object.values(saved) : DATA.filter(d=>!rejected.has(d.uid));
  const minScore=+minScoreSel.value||0, beds=bedsSel.value, areas=checkedAreas();
  rows = rows.filter(d=>(areas.has(d.area_key))
    &&(!typeSel.value||d.property_type===typeSel.value)
    &&(!srcSel.value||d.source===srcSel.value)
    &&(d.score>=minScore)
    &&(!beds || (beds==='4' ? (d.bedrooms||0)>=4 : d.bedrooms===+beds))
    &&(savedView||!newOnly||d.is_new));
  const s=sortSel.value;
  rows.sort((a,b)=> s==='price_asc'?(a.price_total||9e9)-(b.price_total||9e9)
    : s==='price_desc'?(b.price_total||0)-(a.price_total||0)
    : s==='area_desc'?(b.area_m2||0)-(a.area_m2||0)
    : s==='beds_desc'?((b.bedrooms||0)-(a.bedrooms||0))||(b.score-a.score)
    : s==='beds_asc'?((a.bedrooms||99)-(b.bedrooms||99))||(b.score-a.score)
    : s==='new'?(b.is_new-a.is_new)||(b.score-a.score)
    : (b.score-a.score));
  return rows;
}
function render(){
  const rows=currentRows();
  grid.innerHTML='';
  empty.style.display=(!mapView&&!rows.length)?'block':'none';
  empty.textContent = savedView ? 'No saved listings yet — tap ✓ Save on ones you like.'
                                : 'No listings match this view.';
  for(const d of rows){
    const el=document.createElement('div');el.className='card'+(saved[d.uid]?' saved':'');
    const gal=(d.images&&d.images.length)?d.images:(d.image?[d.image]:[]);
    const img=gal.length?`style="background-image:url('${gal[0]}')"`:'';
    const carousel = gal.length>1
      ? `<button class="nav prev" data-nav="prev" aria-label="Previous photo">‹</button>
         <button class="nav next" data-nav="next" aria-label="Next photo">›</button>
         <span class="counter">1/${gal.length}</span>` : '';
    const usd=d.price_usd?`<small>≈ $${d.price_usd}/mo</small>`:'';
    const m2=d.area_m2?`${Math.round(d.area_m2)}m²`:'';
    const chips=(d.score_flags||[]).slice(0,6).map(f=>`<span class="chip">${f}</span>`).join('');
    const notes=(d.notes||[]).map(n=>`<div class="note">⚠️ ${n}</div>`).join('');
    const isSaved=!!saved[d.uid];
    const ptb=d.property_type&&d.property_type!=='apartamento'
      ?`<span class="ptype ${d.property_type}">${d.property_type==='casa'?'HOUSE':'PENTHOUSE'}</span>`:'';
    el.innerHTML=`<div class="thumb" data-uid="${d.uid}" data-idx="0" ${img}>
        <div class="badges"><span class="score">${d.score}</span>${d.is_new?'<span class="newb">NEW</span>':''}${ptb}</div>
        <span class="src">${d.source}</span>${carousel}</div>
      <div class="body">
        <div class="price">${money(d.price_total)} ${usd}</div>
        <div class="meta"><span class="where">${areaLabel(d.area_key)}</span>${d.neighborhood?' · '+d.neighborhood:''}</div>
        <div class="meta">${d.bedrooms??'?'} bd · ${d.bathrooms??'?'} ba · ${m2} ${d.stratum?'· estrato '+d.stratum:''}</div>
        <div class="chips">${chips}</div>${notes}
        <div class="foot">
          <div class="acts">
            <button class="act no" data-act="reject" data-uid="${d.uid}" title="Not interested — hide for good">✕</button>
            <button class="act save ${isSaved?'on':''}" data-act="save" data-uid="${d.uid}" title="Save to your list">${isSaved?'✓ Saved':'♡ Save'}</button>
          </div>
          <a class="view" href="${d.url}" target="_blank" rel="noopener">View →</a>
        </div>
      </div>`;
    grid.appendChild(el);
  }
}

function galleryOf(uid){ return (byUid[uid]||saved[uid]||{}).images || []; }
function flip(thumb,dir){
  const imgs=galleryOf(thumb.dataset.uid); if(imgs.length<2) return;
  let i=(+thumb.dataset.idx||0);
  i = dir>0 ? (i+1)%imgs.length : (i-1+imgs.length)%imgs.length;
  thumb.dataset.idx=i;
  thumb.style.backgroundImage=`url('${imgs[i]}')`;
  const c=thumb.querySelector('.counter'); if(c) c.textContent=(i+1)+'/'+imgs.length;
}

grid.addEventListener('click',e=>{
  const nav=e.target.closest('.nav');
  if(nav){ e.preventDefault(); flip(nav.closest('.thumb'), nav.dataset.nav==='next'?1:-1); return; }
  const b=e.target.closest('.act'); if(!b) return;
  const uid=b.dataset.uid;
  if(b.dataset.act==='reject'){ delete saved[uid]; rejected.add(uid); }
  else { if(saved[uid]) delete saved[uid];
         else { saved[uid]=byUid[uid]||saved[uid]; rejected.delete(uid); } }
  persist(); updateStats(); render();
});

// swipe to flip photos on touch devices
grid.addEventListener('touchstart',e=>{const t=e.target.closest('.thumb');if(t)t._sx=e.touches[0].clientX;},{passive:true});
grid.addEventListener('touchend',e=>{const t=e.target.closest('.thumb');
  if(t&&t._sx!=null){const dx=e.changedTouches[0].clientX-t._sx;
    if(Math.abs(dx)>30) flip(t, dx<0?1:-1); t._sx=null;}},{passive:true});

function downloadBlob(name,text,mime){
  const blob=new Blob([text],{type:mime});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;a.click();
  URL.revokeObjectURL(a.href);
}
// CSV with every field, RFC-4180 quoting, UTF-8 BOM so accents open right in Excel
function waLink(d){
  if(!d.contact_whatsapp) return '';
  const msg=`Hola, vi este inmueble en ${d.neighborhood||'Medellín'} (${d.bedrooms||'?'} hab, `
    +`${d.bathrooms||'?'} baños) publicado en ${d.source} y me interesa. ¿Sigue disponible? `
    +`Me gustaría agendar una visita. ${d.url}`;
  return `https://wa.me/${d.contact_whatsapp}?text=${encodeURIComponent(msg)}`;
}
// Ordered as a contact/call sheet for the assistant: what it is, then how to reach them.
const CSV_COLS=[
  ['score','score'],['area',d=>areaLabel(d.area_key)],['neighborhood','neighborhood'],
  ['type','property_type'],['bedrooms','bedrooms'],['bathrooms','bathrooms'],
  ['area_m2',d=>d.area_m2?Math.round(d.area_m2):''],
  ['total_cop','price_total'],['approx_usd','price_usd'],
  ['contact_name','contact_name'],['phone','contact_phone'],
  ['whatsapp_link',waLink],['email','contact_email'],['listing_url','url'],
  ['status',''],['notes_for_visit',''],   // blank columns for the assistant to fill in
  ['source','source'],['stratum','stratum'],['floor','floor'],['garages','garages'],
  ['furnished',d=>d.furnished===true?'furnished':d.furnished===false?'unfurnished':'unknown'],
  ['pet_friendly',d=>d.pets===true?'yes':''],
  ['match_flags',d=>(d.score_flags||[]).join('; ')],
  ['warnings',d=>(d.notes||[]).join('; ')],
  ['is_new',d=>d.is_new?'new':''],
  ['photo',d=>(d.images&&d.images[0])||d.image||''],
  ['rent_cop','price_rent'],['admin_cop','price_admin'],
  ['latitude','lat'],['longitude','lng'],['id','uid'],
];
function csvCell(v){ if(v==null) return ''; const s=String(v).replace(/"/g,'""');
  return /[",\n\r]/.test(s)?`"${s}"`:s; }
function rowsToCSV(rows){
  const head=CSV_COLS.map(c=>c[0]).join(',');
  const body=rows.map(d=>CSV_COLS.map(c=>csvCell(typeof c[1]==='function'?c[1](d):d[c[1]])).join(','));
  return '﻿'+[head,...body].join('\r\n');
}
document.getElementById('exportSaved').onclick=()=>{
  const rows=Object.values(saved).sort((a,b)=>b.score-a.score);
  if(!rows.length){ alert('No saved listings yet — tap ✓ Save on ones you like first.'); return; }
  downloadBlob('saved-listings.csv', rowsToCSV(rows), 'text/csv;charset=utf-8');
};
document.getElementById('exportView').onclick=()=>{
  const rows=currentRows();
  if(!rows.length){ alert('Nothing in the current view to export.'); return; }
  downloadBlob('listings-view.csv', rowsToCSV(rows), 'text/csv;charset=utf-8');
};
document.getElementById('exportRej').onclick=()=>downloadBlob('rejected.json',JSON.stringify([...rejected],null,2),'application/json');

// ---- native Excel (.xlsx) via SheetJS, lazy-loaded on first use ----
let xlsxLoading=null;
function ensureXLSX(){
  if(window.XLSX) return Promise.resolve();
  if(xlsxLoading) return xlsxLoading;
  xlsxLoading=new Promise((res,rej)=>{
    const s=document.createElement('script');
    s.src='https://unpkg.com/xlsx@0.18.5/dist/xlsx.full.min.js';
    s.onload=res; s.onerror=()=>rej(new Error('could not load the Excel library'));
    document.head.appendChild(s);
  });
  return xlsxLoading;
}
const LINK_CELLS={whatsapp_link:'WhatsApp', listing_url:'Ver anuncio', photo:'Foto'};
function rowsToXLSX(rows,filename){
  ensureXLSX().then(()=>{
    const header=CSV_COLS.map(c=>c[0]);
    const aoa=[header, ...rows.map(d=>CSV_COLS.map(c=>{
      const v=typeof c[1]==='function'?c[1](d):d[c[1]]; return v==null?'':v; }))];
    const ws=XLSX.utils.aoa_to_sheet(aoa);
    rows.forEach((d,ri)=>Object.entries(LINK_CELLS).forEach(([col,label])=>{
      const ci=header.indexOf(col); if(ci<0) return;
      const addr=XLSX.utils.encode_cell({r:ri+1,c:ci}); const cell=ws[addr];
      if(cell&&cell.v){ cell.l={Target:String(cell.v)}; cell.v=label; }
    }));
    ws['!cols']=header.map(h=>({wch:Math.min(Math.max(h.length+2,10),42)}));
    const wb=XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb,ws,'Apartamentos');
    XLSX.writeFile(wb,filename);
  }).catch(e=>alert('Excel export failed ('+e.message+'). The CSV export always works as a fallback.'));
}
document.getElementById('exportViewX').onclick=()=>{
  const rows=currentRows();
  if(!rows.length){ alert('Nothing in the current view to export.'); return; }
  rowsToXLSX(rows,'listings-view.xlsx');
};
document.getElementById('exportSavedX').onclick=()=>{
  const rows=Object.values(saved).sort((a,b)=>b.score-a.score);
  if(!rows.length){ alert('No saved listings yet — tap ✓ Save on ones you like first.'); return; }
  rowsToXLSX(rows,'saved-listings.xlsx');
};
// Build a shareable, forward-facing broker page (data rides in the URL; no backend)
document.getElementById('shareBroker').onclick=()=>{
  const rows=Object.values(saved).sort((a,b)=>b.score-a.score);
  if(!rows.length){ alert('Save some listings first (tap ✓ Save), then send them to your broker.'); return; }
  const payload=rows.map(d=>({
    a:areaLabel(d.area_key), n:d.neighborhood, b:d.bedrooms, ba:d.bathrooms,
    m:d.area_m2?Math.round(d.area_m2):'', p:d.price_total, pu:d.price_usd,
    cn:d.contact_name, ph:d.contact_phone, wa:d.contact_whatsapp,
    u:d.url, img:(d.images&&d.images[0])||d.image||''
  }));
  const b64=btoa(unescape(encodeURIComponent(JSON.stringify(payload))));
  const base=(location.origin+location.pathname).replace(/[^/]*$/,'');
  const link=base+'broker.html#'+b64;
  const long = link.length>7000 ? '\n\n(Long list — if the link breaks when sending, share fewer at a time or use Export view CSV.)' : '';
  const done=()=>alert('Broker link copied ✓  ('+rows.length+' saved listings)\n\nPaste it to your broker via WhatsApp or email. She opens it and can WhatsApp / call each place — no login needed.'+long);
  if(navigator.clipboard&&navigator.clipboard.writeText){ navigator.clipboard.writeText(link).then(done,()=>prompt('Copy this link for your broker:',link)); }
  else prompt('Copy this link for your broker:',link);
};

// ---- map view (Leaflet + OpenStreetMap, lazy-initialised on first open) ----
const AREA_COLOR={poblado:'#1f7a5a',laureles:'#6d28d9',envigado:'#b45309',ciudad_del_rio:'#0369a1',las_palmas:'#db2777',frontera:'#dc2626'};
let map=null, markerLayer=null;
const mapBtn=document.getElementById('mapBtn'), mapwrap=document.getElementById('mapwrap');
function initMap(){
  if(map||typeof L==='undefined') return;
  map=L.map('map',{scrollWheelZoom:true}).setView([6.230,-75.575],12);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    {maxZoom:19,attribution:'© OpenStreetMap'}).addTo(map);
  markerLayer=L.layerGroup().addTo(map);
}
window.mafSave=function(uid){
  if(saved[uid]) delete saved[uid];
  else { saved[uid]=byUid[uid]||saved[uid]; rejected.delete(uid); }
  persist(); updateStats(); render(); renderMap();
};
function popupHTML(d){
  const gal=(d.images&&d.images.length)?d.images:(d.image?[d.image]:[]);
  const m2=d.area_m2?Math.round(d.area_m2)+'m²':'';
  return `<div class="pop">${gal.length?`<img src="${gal[0]}" alt="">`:''}
    <div class="pp">${money(d.price_total)}</div>
    <div class="pm">${areaLabel(d.area_key)}${d.neighborhood?' · '+d.neighborhood:''}<br>
      ${d.bedrooms??'?'} bd · ${d.bathrooms??'?'} ba · ${m2} · score ${d.score}</div>
    <a href="${d.url}" target="_blank" rel="noopener">View →</a> &nbsp;·&nbsp;
    <a href="javascript:void(0)" onclick="mafSave('${d.uid}')">${saved[d.uid]?'✓ Saved':'♡ Save'}</a></div>`;
}
function renderMap(){
  if(!map) return;
  markerLayer.clearLayers();
  const shown=currentRows();
  const rows=shown.filter(d=>typeof d.lat==='number'&&typeof d.lng==='number');
  const pts=[];
  for(const d of rows){
    L.circleMarker([d.lat,d.lng],{radius:7,weight:1.5,color:'#fff',
      fillColor:AREA_COLOR[d.area_key]||'#555',fillOpacity:saved[d.uid]?1:.85})
      .bindPopup(popupHTML(d),{minWidth:180}).addTo(markerLayer);
    pts.push([d.lat,d.lng]);
  }
  document.getElementById('mapcount').textContent=`${pts.length} of ${shown.length} shown listings mapped`;
  if(pts.length) map.fitBounds(pts,{padding:[30,30],maxZoom:15});
  setTimeout(()=>map.invalidateSize(),0);
}
function setMapView(on){
  mapView=on; mapBtn.classList.toggle('on',on);
  mapwrap.style.display=on?'block':'none'; grid.style.display=on?'none':'';
  render(); if(on){ initMap(); renderMap(); }
}
mapBtn.addEventListener('click',()=>setMapView(!mapView));

function refresh(){ render(); if(mapView) renderMap(); }
[typeSel,bedsSel,srcSel,minScoreSel,sortSel].forEach(e=>e.addEventListener('change',refresh));
areaBoxes.addEventListener('change',()=>{ updateAreaSummary(); refresh(); });
areaAll.addEventListener('change',()=>{
  areaBoxes.querySelectorAll('.areaChk').forEach(c=>c.checked=areaAll.checked);
  updateAreaSummary(); refresh(); });
newBtn.addEventListener('click',()=>{newOnly=!newOnly;newBtn.classList.toggle('on',newOnly);refresh();});
savedBtn.addEventListener('click',()=>{savedView=!savedView;savedBtn.classList.toggle('on',savedView);
  newBtn.style.display=savedView?'none':'';refresh();});
updateAreaSummary(); updateStats(); render();
</script>
</body>
</html>"""
