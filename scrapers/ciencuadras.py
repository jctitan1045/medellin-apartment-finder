"""Ciencuadras scraper.

Ciencuadras is an Angular Universal app. Both the search page and the detail
page embed their server state in a single <script type="application/json"> block,
HTML-entity-encoded (&q; == "). We decode and parse that.

Strategy: the search list gives beds/baths/rent/area/neighborhood (enough to
area-match and pre-filter). We then fetch the detail page ONLY for listings that
pass the preliminary hard filter, to pull admin fee, description, amenities
(commonZonesProperty) and balcony/terrace/elevator/view signals.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from core.models import Listing, parse_int, parse_area, normalize_type
from .http import get, polite_sleep

BASE = "https://www.ciencuadras.com"
_JSON_RE = re.compile(
    r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', re.S)


def _decode_state(html: str) -> dict | None:
    m = _JSON_RE.search(html)
    if not m:
        return None
    dec = (m.group(1).replace("&q;", '"').replace("&a;", "&")
           .replace("&l;", "<").replace("&g;", ">")
           .replace("&s;", "'").replace("&b;", "\\"))
    try:
        return json.loads(dec)
    except json.JSONDecodeError:
        return None


def _num(v):
    n = parse_int(v)
    return n if n else 0


def _list_to_listing(raw: dict) -> Listing | None:
    sid = str(raw.get("code") or raw.get("id") or "")
    if not sid:
        return None
    url = raw.get("url") or ""
    if url and not url.startswith("http"):
        url = BASE + ("" if url.startswith("/") else "/") + url
    rent = _num(raw.get("rentPrice"))
    coord = raw.get("coordinates") or {}
    return Listing(
        source="ciencuadras",
        source_id=sid,
        url=url,
        title=f"{raw.get('realEstateType','Inmueble')} en {raw.get('neighborhood','')}, {raw.get('city','')}",
        property_type=normalize_type(raw.get("realEstateType")),
        neighborhood=raw.get("neighborhood", "") or "",
        city=raw.get("city", "") or "",
        price_rent=rent,
        price_total=rent,          # refined with admin at the detail step
        admin_known=False,
        bedrooms=parse_int(raw.get("rooms")),
        bathrooms=parse_int(raw.get("baths")),
        area_m2=parse_area(raw.get("area")),
        garages=parse_int(raw.get("garages")),
        lat=coord.get("latitude"),
        lng=coord.get("longitude"),
        image=raw.get("image", "") or "",
        images=[raw["image"]] if raw.get("image") else [],   # replaced by gallery on enrich
        created_at=str(raw.get("createdAt", "") or ""),
    )


def _enrich(listing: Listing) -> None:
    """Fetch the detail page and fill admin, description, amenities, signals."""
    html = get(listing.url)
    if not html:
        return
    state = _decode_state(html)
    if not state:
        return
    path = urlparse(listing.url).path
    detail = state.get(f"detail-property-{path}") or {}
    g = detail.get("generalData") or {}
    if not g:
        return

    rent = _num(g.get("leaseFee")) or _num(g.get("price")) or listing.price_rent
    admin = _num(g.get("adminValue"))
    listing.price_rent = rent
    listing.price_admin = admin
    listing.price_total = rent + admin
    listing.admin_known = admin > 0

    listing.description = g.get("description", "") or ""
    listing.neighborhood = g.get("neighborhoodName") or listing.neighborhood
    listing.city = g.get("cityName") or listing.city
    listing.bedrooms = parse_int(g.get("bedRoomNum")) or listing.bedrooms
    listing.bathrooms = parse_int(g.get("bathRoomNum")) or listing.bathrooms
    listing.area_m2 = parse_area(g.get("builtArea")) or listing.area_m2
    listing.stratum = parse_int(g.get("stratum")) or listing.stratum
    listing.floor = parse_int(g.get("floor")) or listing.floor

    amen = [z.get("label", "") for z in (detail.get("commonZonesProperty") or [])
            if z.get("label")]
    if parse_int(g.get("numBalconies")):
        amen.append("Balcón")
    if parse_int(g.get("numTerrace")):
        amen.append("Terraza")
    if parse_int(g.get("numElevators")):
        amen.append("Ascensor")
    if g.get("view"):
        amen.append("Vista")
    listing.amenities = amen

    gallery = [p.get("url") for p in ((detail.get("galleryData") or {}).get("flatPhotos") or [])
               if p.get("url")]
    if gallery:
        listing.images = gallery[:12]
        listing.image = listing.image or gallery[0]


def scrape(cfg: dict, hard: dict, areas_cfg: dict, match_area) -> list[Listing]:
    """match_area is injected to avoid a circular import with core.pipeline."""
    conf = cfg["sources"]["ciencuadras"]
    if not conf.get("enabled"):
        return []
    max_pages = conf.get("max_pages", 6)
    out: list[Listing] = []
    seen: set[str] = set()

    for path in conf["urls"]:
        for page in range(1, max_pages + 1):
            url = f"{BASE}/{path}" + (f"?page={page}" if page > 1 else "")
            html = get(url)
            if not html:
                break
            state = _decode_state(html)
            if not state:
                print(f"    ! ciencuadras: no state at {url}")
                break
            key = f"results-/{path}"
            block = (state.get(key) or {}).get("data") or {}
            rows = (block.get("results") or []) + (block.get("highlights") or [])
            if not rows:
                break

            page_keep = 0
            for raw in rows:
                lst = _list_to_listing(raw)
                if not lst or lst.uid in seen:
                    continue
                seen.add(lst.uid)
                # preliminary filter on cheap list fields before spending a detail fetch
                if lst.bedrooms is not None and lst.bedrooms < hard["min_bedrooms"]:
                    continue
                if lst.bathrooms is not None and lst.bathrooms < hard["min_bathrooms"]:
                    continue
                area = match_area(lst.neighborhood, lst.city, areas_cfg)
                if not area:
                    continue
                lst.area_key = area
                page_keep += 1
                out.append(lst)
            print(f"    ciencuadras/{path.split('/')[-1]} p{page}: "
                  f"kept {page_keep}/{len(rows)}")
            polite_sleep()

    # enrich survivors with detail-page data
    print(f"    ciencuadras: enriching {len(out)} survivors...")
    for lst in out:
        _enrich(lst)
        polite_sleep()
    return out
