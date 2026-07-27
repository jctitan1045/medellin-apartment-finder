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
  .spacer{flex:1}
  .link{background:none;border:none;color:var(--muted);text-decoration:underline;padding:7px 4px}
  .grid{max-width:1180px;margin:0 auto;padding:16px;display:grid;gap:14px;
        grid-template-columns:repeat(auto-fill,minmax(320px,1fr))}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;
        box-shadow:var(--shadow);display:flex;flex-direction:column;transition:opacity .15s}
  .card.saved{border-color:var(--yes);box-shadow:0 0 0 2px var(--yes) inset}
  .thumb{aspect-ratio:16/10;background:var(--chip) center/cover no-repeat;position:relative}
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
  footer{max-width:1180px;margin:0 auto;padding:8px 16px 40px;color:var(--muted);font-size:12px}
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <div class="sub"><span id="stat-count">__COUNT__ current matches</span> · <b>__NEW__ new today</b>
    · <span id="stat-saved">0 saved</span> · <span id="stat-hidden"></span>
    · updated __GENERATED__</div>
</header>
<div class="bar">
  <button id="savedBtn">★ Saved (<span id="savedN">0</span>)</button>
  <select id="area"><option value="">All areas</option></select>
  <select id="type"><option value="">All types</option></select>
  <select id="src"><option value="">All sources</option></select>
  <select id="sort">
    <option value="score">Sort: Best match</option>
    <option value="new">Sort: New first</option>
    <option value="price_asc">Sort: Price ↑</option>
    <option value="price_desc">Sort: Price ↓</option>
    <option value="area_desc">Sort: Size ↓</option>
  </select>
  <button id="newonly">Show new only</button>
  <span class="spacer"></span>
  <button class="link" id="exportSaved">⬇ Export saved</button>
  <button class="link" id="exportRej">⬇ Export hidden</button>
</div>
<div class="grid" id="grid"></div>
<div class="empty" id="empty" style="display:none"></div>
<footer>✓ saves to your list · ✕ hides a listing for good (recover with “reset” up top).
Decisions are stored in this browser. ⚠️ flags mean a spec (furnished / administración) couldn't be
auto-verified — check the listing. Prices are rent + administración in COP.</footer>
<script>
const DATA = __DATA__;
const grid=document.getElementById('grid'), empty=document.getElementById('empty');
const areaSel=document.getElementById('area'), typeSel=document.getElementById('type'),
      srcSel=document.getElementById('src'), sortSel=document.getElementById('sort');
const newBtn=document.getElementById('newonly'), savedBtn=document.getElementById('savedBtn');
let newOnly=false, savedView=false;

// ---- persistent triage state (survives the daily rebuild) ----
const LS_REJ='maf.rejected', LS_SAVE='maf.saved';
let rejected=new Set(JSON.parse(localStorage.getItem(LS_REJ)||'[]'));
let saved=JSON.parse(localStorage.getItem(LS_SAVE)||'{}');   // uid -> listing snapshot
const byUid={}; DATA.forEach(d=>byUid[d.uid]=d);
function persist(){localStorage.setItem(LS_REJ,JSON.stringify([...rejected]));
  localStorage.setItem(LS_SAVE,JSON.stringify(saved));}

const areaLabel=k=>(k||'').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
const TYPE_LABEL={apartamento:'Apartments',casa:'Houses',penthouse:'Penthouses'};
[...new Set(DATA.map(d=>d.area_key).filter(Boolean))].sort().forEach(a=>{
  const o=document.createElement('option');o.value=a;o.textContent=areaLabel(a);areaSel.appendChild(o);});
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

function render(){
  let rows = savedView ? Object.values(saved) : DATA.filter(d=>!rejected.has(d.uid));
  rows = rows.filter(d=>(!areaSel.value||d.area_key===areaSel.value)
    &&(!typeSel.value||d.property_type===typeSel.value)
    &&(!srcSel.value||d.source===srcSel.value)
    &&(savedView||!newOnly||d.is_new));
  const s=sortSel.value;
  rows.sort((a,b)=> s==='price_asc'?(a.price_total||9e9)-(b.price_total||9e9)
    : s==='price_desc'?(b.price_total||0)-(a.price_total||0)
    : s==='area_desc'?(b.area_m2||0)-(a.area_m2||0)
    : s==='new'?(b.is_new-a.is_new)||(b.score-a.score)
    : (b.score-a.score));
  grid.innerHTML='';
  empty.style.display=rows.length?'none':'block';
  empty.textContent = savedView ? 'No saved listings yet — tap ✓ Save on ones you like.'
                                : 'No listings match this view.';
  for(const d of rows){
    const el=document.createElement('div');el.className='card'+(saved[d.uid]?' saved':'');
    const img=d.image?`style="background-image:url('${d.image}')"`:'';
    const usd=d.price_usd?`<small>≈ $${d.price_usd}/mo</small>`:'';
    const m2=d.area_m2?`${Math.round(d.area_m2)}m²`:'';
    const chips=(d.score_flags||[]).slice(0,6).map(f=>`<span class="chip">${f}</span>`).join('');
    const notes=(d.notes||[]).map(n=>`<div class="note">⚠️ ${n}</div>`).join('');
    const isSaved=!!saved[d.uid];
    const ptb=d.property_type&&d.property_type!=='apartamento'
      ?`<span class="ptype ${d.property_type}">${d.property_type==='casa'?'HOUSE':'PENTHOUSE'}</span>`:'';
    el.innerHTML=`<div class="thumb" ${img}>
        <div class="badges"><span class="score">${d.score}</span>${d.is_new?'<span class="newb">NEW</span>':''}${ptb}</div>
        <span class="src">${d.source}</span></div>
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

grid.addEventListener('click',e=>{
  const b=e.target.closest('.act'); if(!b) return;
  const uid=b.dataset.uid;
  if(b.dataset.act==='reject'){ delete saved[uid]; rejected.add(uid); }
  else { if(saved[uid]) delete saved[uid];
         else { saved[uid]=byUid[uid]||saved[uid]; rejected.delete(uid); } }
  persist(); updateStats(); render();
});

function download(name,obj){
  const blob=new Blob([JSON.stringify(obj,null,2)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;a.click();
  URL.revokeObjectURL(a.href);
}
document.getElementById('exportSaved').onclick=()=>download('saved.json',Object.values(saved));
document.getElementById('exportRej').onclick=()=>download('rejected.json',[...rejected]);

[areaSel,typeSel,srcSel,sortSel].forEach(e=>e.addEventListener('change',render));
newBtn.addEventListener('click',()=>{newOnly=!newOnly;newBtn.classList.toggle('on',newOnly);render();});
savedBtn.addEventListener('click',()=>{savedView=!savedView;savedBtn.classList.toggle('on',savedView);
  newBtn.style.display=savedView?'none':'';render();});
updateStats(); render();
</script>
</body>
</html>"""
