#!/usr/bin/env python3
"""Medellín Apartment Finder — daily orchestrator.

  scrape  ->  area-match + hard-filter + score  ->  dedup  ->  dashboard + push

Usage:
  python run.py                 full run (scrape, build dashboard, push new)
  python run.py --no-notify     everything except the WhatsApp/Telegram push
  python run.py --dry           quick run: fewer pages, no push (local testing)
"""
from __future__ import annotations

import argparse
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import pipeline, store
from core.models import Listing
from scrapers import fincaraiz, ciencuadras, metrocuadrado
from dashboard import build as dashboard
import notify

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
DASHBOARD_URL = os.getenv(
    "DASHBOARD_URL", "https://jctitan1045.github.io/medellin-apartment-finder/")


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect(cfg: dict) -> list[Listing]:
    all_listings: list[Listing] = []

    if cfg["sources"]["fincaraiz"].get("enabled"):
        print("→ Fincaraíz")
        fr = fincaraiz.scrape(cfg)
        # Fincaraíz pads results with nearby barrios; re-derive the area from the
        # listing's own neighborhood and drop anything outside our target set.
        kept = 0
        for l in fr:
            area = pipeline.match_area(l.neighborhood, l.city, cfg["areas"])
            if area:
                l.area_key = area
                all_listings.append(l)
                kept += 1
        print(f"  fincaraiz: {kept}/{len(fr)} in-target after area match")

    if cfg["sources"]["ciencuadras"].get("enabled"):
        print("→ Ciencuadras")
        cc = ciencuadras.scrape(cfg, cfg["hard"], cfg["areas"], pipeline.match_area)
        all_listings.extend(cc)

    if cfg["sources"].get("metrocuadrado", {}).get("enabled"):
        print("→ Metrocuadrado")
        mc = metrocuadrado.scrape(cfg, cfg["hard"], cfg["areas"], pipeline.match_area)
        all_listings.extend(mc)

    # de-duplicate by uid (same listing can appear on overlapping area/zone pages)
    unique: dict[str, Listing] = {}
    for l in all_listings:
        unique.setdefault(l.uid, l)
    dropped = len(all_listings) - len(unique)
    if dropped:
        print(f"  de-duped {dropped} cross-page duplicate(s)")
    return list(unique.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-notify", action="store_true", help="skip the push")
    ap.add_argument("--dry", action="store_true", help="fast local run, no push")
    args = ap.parse_args()

    cfg = load_config()
    if args.dry:
        cfg["sources"]["fincaraiz"]["max_pages_per_area"] = 1
        cfg["sources"]["ciencuadras"]["max_pages"] = 1

    listings = collect(cfg)
    print(f"\nCollected {len(listings)} in-target listings. Processing...")

    for l in listings:
        pipeline.process(l, cfg)

    matches = [l for l in listings if not l.hard_fails]

    # drop anything the user rejected on the dashboard (exported to rejected.json)
    rejected = store.load_rejected()
    if rejected:
        before = len(matches)
        matches = [l for l in matches if l.uid not in rejected]
        print(f"excluded {before - len(matches)} rejected listing(s).")

    matches.sort(key=lambda x: -x.score)
    print(f"{len(matches)} pass all hard filters.")

    # dedup / new-detection
    seen = store.load_seen()
    new_uids = set(store.mark_seen(seen, [l.uid for l in matches]))
    for l in matches:
        l.is_new = l.uid in new_uids
    store.save_seen(seen)
    print(f"{len(new_uids)} are new since last run.")

    dicts = [l.to_dict() for l in matches]
    store.save_listings(dicts)
    out = dashboard.build(dicts, cfg)
    print(f"Dashboard written: {out}")

    if args.dry or args.no_notify:
        print("Push skipped.")
        return

    new_sorted = [d for d in dicts if d["is_new"]
                  and d["score"] >= cfg["output"].get("push_min_score", 0)]
    notify.push(new_sorted, DASHBOARD_URL, cfg)
    print("Done.")


if __name__ == "__main__":
    main()
