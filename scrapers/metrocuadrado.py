"""Metrocuadrado scraper.

Metrocuadrado is a Next.js App-Router site: no __NEXT_DATA__, instead it streams
its data as RSC "flight" chunks via self.__next_f.push([1,"...json..."]). The
search results array is embedded there. We fetch the per-neighborhood page with a
plain request, reassemble the flight chunks, and pull the "results" array — 54
listings/page, every field we need at top level, description in `comment`, so no
detail-page fetch is required.
"""
from __future__ import annotations

import json
import re

from core.models import Listing, parse_int, parse_area, normalize_type, wa_number, clean_phone
from .http import get, polite_sleep

BASE = "https://www.metrocuadrado.com"
_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[\d+,\s*"((?:[^"\\]|\\.)*)"\]\)')


def _flight_blob(html: str) -> str:
    """Reassemble the RSC flight payload into one string, UTF-8 clean."""
    out = []
    for chunk in _PUSH_RE.findall(html):
        try:                      # decode JS/JSON string escapes without mojibake
            out.append(json.loads('"' + chunk + '"'))
        except json.JSONDecodeError:
            out.append(chunk)
    return "".join(out)


def _extract_results(blob: str) -> list:
    """Find "results":[ ... ] and brace-match the array out of the blob."""
    i = blob.find('"results":[')
    if i < 0:
        return []
    start = blob.find("[", i + len('"results":') - 1)
    depth = 0
    for k in range(start, len(blob)):
        c = blob[k]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(blob[start:k + 1])
                except json.JSONDecodeError:
                    return []
    return []


def _name(v):
    """Some fields are {'id':..,'nombre':..}; return the nombre or the raw value."""
    if isinstance(v, dict):
        return v.get("nombre", "") or ""
    return v or ""


def _to_listing(raw: dict, area_hint: str) -> Listing | None:
    sid = str(raw.get("midinmueble") or "")
    if not sid:
        return None
    if raw.get("mtiponegocio") and "arriendo" not in str(raw["mtiponegocio"]).lower():
        return None

    link = raw.get("link") or ""
    url = link if link.startswith("http") else BASE + link

    rent = parse_int(raw.get("mvalorarriendo")) or 0
    neigh = _name(raw.get("mnombrecomunbarrio")) or _name(raw.get("mbarrio"))
    desc = raw.get("comment", "") or ""

    # gallery: mgaleriainmueble is a list of photo ids -> CDN url pattern
    photo_ids = raw.get("mgaleriainmueble") or []
    gallery = [f"https://multimedia.metrocuadrado.com/{sid}/{pid}_p.jpg"
               for pid in photo_ids if pid][:12]
    primary = raw.get("imageLink", "") or (gallery[0] if gallery else "")
    if primary and primary not in gallery:
        gallery = [primary] + gallery

    lat = lng = None                       # geopoints[0] = building-level location
    gp = raw.get("geopoints") or []
    if gp:
        try:
            lat = float(gp[0].get("latitude"))
            lng = float(gp[0].get("longitude"))
        except (TypeError, ValueError):
            lat = lng = None

    return Listing(
        source="metrocuadrado",
        source_id=sid,
        url=url,
        title=raw.get("title", "") or "",
        area_key=area_hint,
        property_type=normalize_type(_name(raw.get("mtipoinmueble"))),
        neighborhood=neigh,
        city=_name(raw.get("mciudad")),
        price_rent=rent,
        price_total=rent,             # admin not in list payload -> flagged unknown
        admin_known=False,
        bedrooms=parse_int(raw.get("mnrocuartos")),
        bathrooms=parse_int(raw.get("mnrobanos")),
        area_m2=parse_area(raw.get("mareac") or raw.get("marea")),
        stratum=parse_int(raw.get("estrato")),
        garages=parse_int(raw.get("mnrogarajes")),
        description=desc,
        lat=lat,
        lng=lng,
        image=primary,
        images=gallery[:12],
        contact_name=_name(raw.get("moferente")) if raw.get("moferente") not in ("RealEstate", None) else "",
        contact_phone=clean_phone(raw.get("contactPhone") or raw.get("mcontactoinmobiliaria_fijo1")),
        contact_whatsapp=wa_number(raw.get("whatsapp")),
    )


def scrape(cfg: dict, hard: dict, areas_cfg: dict, match_area) -> list[Listing]:
    conf = cfg["sources"]["metrocuadrado"]
    if not conf.get("enabled"):
        return []
    max_pages = conf.get("max_pages", 2)
    out: list[Listing] = []
    seen: set[str] = set()

    for area_key, path in conf["areas"].items():
        for page in range(1, max_pages + 1):
            url = f"{BASE}/{path}" + (f"{page}/" if page > 1 else "")
            html = get(url)
            if not html:
                break
            rows = _extract_results(_flight_blob(html))
            if not rows:
                if page == 1:
                    print(f"    ! metrocuadrado: no results at {url}")
                break

            kept = 0
            for raw in rows:
                lst = _to_listing(raw, area_key)
                if not lst or lst.uid in seen:
                    continue
                seen.add(lst.uid)
                # confirm the barrio really is in a target area (drops padding)
                area = match_area(lst.neighborhood, lst.city, areas_cfg)
                if not area:
                    continue
                lst.area_key = area
                out.append(lst)
                kept += 1
            print(f"    metrocuadrado/{area_key} p{page}: kept {kept}/{len(rows)}")
            if kept == 0 and page > 1:
                break
            polite_sleep()

    return out
