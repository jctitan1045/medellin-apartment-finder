"""Fincaraíz scraper.

Fincaraíz is a Next.js app that server-renders the full search result set into
a __NEXT_DATA__ JSON blob (props.pageProps.fetchResult.searchFast.data). We fetch
the per-neighborhood page HTML with a plain request and parse that JSON — no
headless browser, and every field we need (rent, admin, beds, baths, m², floor,
penthouse/office booleans, facilities, description, geo) is present.
"""
from __future__ import annotations

import json
import re

from core.models import Listing, parse_int, parse_area, normalize_type
from .http import get, polite_sleep

BASE = "https://www.fincaraiz.com.co"
_NEXT_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', re.S)


def _extract_next_data(html: str) -> dict | None:
    m = _NEXT_RE.search(html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _tech(sheet: list, field: str):
    for row in sheet or []:
        if row.get("field") == field:
            return row.get("value")
    return None


def _to_listing(raw: dict, area_key: str) -> Listing | None:
    try:
        sid = str(raw.get("id"))
        if not sid or sid == "None":
            return None

        price = raw.get("price") or {}
        rent = parse_int(price.get("amount")) or 0
        common = raw.get("commonExpenses") or {}
        admin = parse_int(common.get("amount")) or 0
        include_admin = bool(raw.get("include_administration"))
        total = rent if include_admin else rent + admin
        admin_known = include_admin or admin > 0

        loc = raw.get("locations") or {}
        main = (loc.get("location_main") or {})
        neigh = main.get("name") or ""
        city_list = loc.get("city") or []
        city = city_list[0]["name"] if city_list else ""

        sheet = raw.get("technicalSheet") or []
        facilities = [f.get("name", "") for f in (raw.get("facilities") or [])]

        allow_pets = _tech(sheet, "allowPets")
        pets = True if (allow_pets and str(allow_pets).strip()) else None

        link = raw.get("link") or ""
        url = link if link.startswith("http") else BASE + link

        return Listing(
            source="fincaraiz",
            source_id=sid,
            url=url,
            title=raw.get("title", "") or "",
            area_key=area_key,
            neighborhood=neigh,
            city=city,
            price_rent=rent,
            price_admin=admin,
            price_total=total,
            admin_known=admin_known,
            bedrooms=raw.get("bedrooms") if raw.get("bedrooms") is not None
                     else parse_int(_tech(sheet, "bedrooms")),
            bathrooms=raw.get("bathrooms") if raw.get("bathrooms") is not None
                      else parse_int(_tech(sheet, "bathrooms")),
            area_m2=parse_area(raw.get("m2")) or parse_area(_tech(sheet, "m2Built")),
            stratum=raw.get("stratum") or parse_int(_tech(sheet, "stratum")),
            floor=raw.get("floor") or parse_int(_tech(sheet, "floor")),
            garages=raw.get("garage"),
            property_type=normalize_type((raw.get("property_type") or {}).get("name")),
            is_penthouse=bool(raw.get("penthouse")),
            has_office=bool(raw.get("office")),
            pets=pets,
            amenities=facilities,
            description=raw.get("description", "") or "",
            lat=raw.get("latitude"),
            lng=raw.get("longitude"),
            image=raw.get("img", "") or "",
            created_at=raw.get("created_at", "") or "",
            updated_at=raw.get("updated_at", "") or "",
        )
    except (KeyError, TypeError, ValueError) as e:
        print(f"    ! fincaraiz parse skip: {e}")
        return None


def scrape(cfg: dict) -> list[Listing]:
    conf = cfg["sources"]["fincaraiz"]
    if not conf.get("enabled"):
        return []
    max_pages = conf.get("max_pages_per_area", 4)
    out: list[Listing] = []

    for area_key, path in conf["areas"].items():
        seen_ids: set[str] = set()
        for page in range(1, max_pages + 1):
            url = f"{BASE}/{path}" + (f"/pagina{page}" if page > 1 else "")
            html = get(url)
            if not html:
                break
            data = _extract_next_data(html)
            if not data:
                print(f"    ! fincaraiz: no __NEXT_DATA__ at {url}")
                break
            try:
                rows = data["props"]["pageProps"]["fetchResult"]["searchFast"]["data"]
            except (KeyError, TypeError):
                break
            if not rows:
                break

            page_new = 0
            for raw in rows:
                lst = _to_listing(raw, area_key)
                if lst and lst.source_id not in seen_ids:
                    seen_ids.add(lst.source_id)
                    out.append(lst)
                    page_new += 1
            print(f"    fincaraiz/{area_key} p{page}: +{page_new} "
                  f"({len(rows)} raw)")
            if page_new == 0:
                break
            polite_sleep()

    return out
