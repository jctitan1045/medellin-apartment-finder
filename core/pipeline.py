"""Filter + score + detect logic. Portal-agnostic: operates on Listing objects."""
from __future__ import annotations

import re
from typing import Optional

from .models import Listing, strip_accents

# Furnished detectors. Order matters: negations checked first.
_UNFURNISHED_HINTS = ["sin amoblar", "no amoblado", "sin muebles", "desamoblado",
                      "unfurnished", "sin amoblamiento"]
_FURNISHED_HINTS = ["amoblado", "amueblado", "furnished", "con muebles",
                    "totalmente equipado", "full equipado"]
_PET_HINTS = ["mascota", "pet friendly", "pet-friendly", "se admiten mascotas",
              "admite mascotas", "acepta mascotas", "pet welcome"]
# Word-boundary match so standalone "PH"/"ático"/"cobertura"/"penthouse" count
# but substrings never create false positives. These portals rarely label
# penthouses, so this is deliberately precise rather than a top-floor guess.
_PENTHOUSE_RE = re.compile(r"\b(penthouse|pent[\s-]?house|ph|cobertura|atico)\b")


def classify_type(listing: Listing) -> str:
    """Resolve final property type. A penthouse is a top-floor apartment; detect it
    from the structured flag or an explicit label and upgrade the type."""
    ptype = listing.property_type or "apartamento"
    if ptype in ("apartamento", "penthouse"):
        if listing.is_penthouse or _PENTHOUSE_RE.search(listing.haystack()):
            return "penthouse"
    return ptype


def detect_furnished(listing: Listing) -> Optional[bool]:
    """Return True/False/None(unknown). If the scraper already set it, trust that."""
    if listing.furnished is not None:
        return listing.furnished
    hay = listing.haystack()
    if any(h in hay for h in _UNFURNISHED_HINTS):
        return False
    if any(h in hay for h in _FURNISHED_HINTS):
        return True
    return None


def detect_pets(listing: Listing) -> Optional[bool]:
    if listing.pets is not None:
        return listing.pets
    hay = listing.haystack()
    if any(h in hay for h in _PET_HINTS):
        return True
    return None


def match_area(neighborhood: str, city: str, areas_cfg: dict) -> Optional[str]:
    """Map a listing to a target-area key by neighborhood/city tokens.
    Returns the area key or None if it belongs to no target area."""
    hay = strip_accents(f"{neighborhood} {city}")
    for key, cfg in areas_cfg.items():
        for tok in cfg.get("tokens", []):
            if strip_accents(tok) in hay:
                return key
    return None


def apply_hard_filter(listing: Listing, hard: dict) -> list:
    """Return a list of deal-breaker reasons. Empty list == passes."""
    fails = []

    if listing.bedrooms is not None and listing.bedrooms < hard["min_bedrooms"]:
        fails.append(f"{listing.bedrooms} bedrooms (< {hard['min_bedrooms']})")
    if listing.bathrooms is not None and listing.bathrooms < hard["min_bathrooms"]:
        fails.append(f"{listing.bathrooms} bathrooms (< {hard['min_bathrooms']})")

    if listing.price_total and listing.price_total > hard["max_total_cop"]:
        fails.append(f"{listing.price_total:,} COP (> {hard['max_total_cop']:,})")

    if hard.get("require_unfurnished") and listing.furnished is True:
        fails.append("furnished")

    inc = hard.get("include_types")
    if inc and listing.property_type not in inc:
        fails.append(f"type '{listing.property_type}' excluded")

    if strip_accents(listing.city) and not any(
        c in strip_accents(listing.city) for c in hard["allowed_cities"]
    ):
        fails.append(f"city '{listing.city}' not in target")

    return fails


def score_listing(listing: Listing, scoring_cfg: dict) -> tuple[int, list]:
    """Compute 0–100 preference score and the list of matched flags."""
    hay = listing.haystack()
    total = 0
    flags = []

    for rule_name, rule in scoring_cfg.items():
        pts = rule.get("points", 0)
        flag = rule.get("flag", rule_name)
        matched = False

        # structural rules with no keyword list
        if rule_name == "three_plus_bedrooms":
            matched = (listing.bedrooms or 0) >= 3
        elif rule_name == "large_area":
            matched = (listing.area_m2 or 0) >= 120
        elif rule_name == "top_floor_penthouse":
            matched = listing.is_penthouse or any(a in hay for a in rule.get("any", []))
        elif rule_name == "office":
            matched = listing.has_office or any(a in hay for a in rule.get("any", []))
        elif rule_name == "pet_friendly":
            matched = listing.pets is True or any(a in hay for a in rule.get("any", []))
        else:
            matched = any(a in hay for a in rule.get("any", []))

        if matched:
            total += pts
            flags.append(flag)

    return min(total, 100), flags


def process(listing: Listing, cfg: dict) -> Listing:
    """Run detection, hard filter, and scoring; annotate the listing in place."""
    listing.furnished = detect_furnished(listing)
    listing.pets = detect_pets(listing)
    listing.property_type = classify_type(listing)

    if listing.furnished is None and cfg["hard"].get("require_unfurnished"):
        listing.notes.append("furnished status unknown — verify")

    if listing.price_admin == 0 and not listing.admin_known:
        listing.notes.append("administración unknown — total may be higher")

    listing.hard_fails = apply_hard_filter(listing, cfg["hard"])
    listing.score, listing.score_flags = score_listing(listing, cfg["scoring"])

    fx = cfg.get("fx_cop_per_usd", 4050)
    listing._usd = round(listing.price_total / fx) if listing.price_total else 0
    return listing
