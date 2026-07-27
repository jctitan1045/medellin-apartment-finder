"""Common listing schema shared across all portal scrapers.

Every scraper normalizes its portal-specific data into a Listing so the
filter / score / dedup / dashboard layers never see portal quirks.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Optional


def strip_accents(text: str) -> str:
    """Lowercase + remove accents so 'Balcón' matches token 'balcon'."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


@dataclass
class Listing:
    source: str                       # "fincaraiz" | "ciencuadras"
    source_id: str                    # portal's own id
    url: str
    title: str = ""
    area_key: str = ""                # our target-area key (poblado, laureles, ...)
    neighborhood: str = ""
    city: str = ""

    price_rent: int = 0               # COP, rent only
    price_admin: int = 0              # COP, administración (HOA), 0 if unknown/included
    price_total: int = 0              # COP, rent + admin (the enforced number)
    admin_known: bool = True          # False when we couldn't determine admin

    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    area_m2: Optional[float] = None
    stratum: Optional[int] = None
    floor: Optional[int] = None
    garages: Optional[int] = None

    property_type: str = "apartamento"   # apartamento | casa | penthouse (derived)
    is_penthouse: bool = False
    has_office: bool = False
    furnished: Optional[bool] = None  # True/False/None(unknown)
    pets: Optional[bool] = None

    amenities: list = field(default_factory=list)
    description: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    image: str = ""                   # primary photo (kept for back-compat)
    images: list = field(default_factory=list)   # full gallery, first = primary
    created_at: str = ""
    updated_at: str = ""

    # populated downstream
    score: int = 0
    score_flags: list = field(default_factory=list)
    hard_fails: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    is_new: bool = False

    @property
    def uid(self) -> str:
        return f"{self.source}:{self.source_id}"

    @property
    def price_usd(self) -> int:
        # display only; set by pipeline via fx rate
        return self._usd if hasattr(self, "_usd") else 0

    def haystack(self) -> str:
        """All free text a scorer/detector should scan, accent-stripped."""
        parts = [self.title, self.description, self.neighborhood,
                 " ".join(self.amenities)]
        return strip_accents(" ".join(p for p in parts if p))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["uid"] = self.uid
        d["price_usd"] = self.price_usd
        return d


def normalize_type(name: str) -> str:
    """Map a portal's property-type label to our canonical set.
    Studios/offices/locales come back as-is so the type filter can drop them."""
    n = strip_accents(name or "")
    if "penthouse" in n or "pent house" in n or "pent-house" in n:
        return "penthouse"
    if "apartaestudio" in n or "aparta estudio" in n or "aparta-estudio" in n:
        return "apartaestudio"
    if "casa" in n or "cabana" in n or "chalet" in n or "casa campestre" in n:
        return "casa"
    if "apartamento" in n or "apto" in n or n == "":
        return "apartamento"
    return n


def parse_int(value) -> Optional[int]:
    """Integer from money/count strings where '.' is a thousands separator.
    '5.300.000' -> 5300000, '104 m2' -> 104, '2' -> 2.
    NOTE: wrong for decimals like '122.0' — use parse_area for areas."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    m = re.search(r"\d[\d.\s]*", str(value))
    if not m:
        return None
    digits = re.sub(r"[.\s]", "", m.group())
    return int(digits) if digits else None


def parse_area(value) -> Optional[float]:
    """Square-metre value where '.' is a DECIMAL point: '122.0'->122, '104 m2'->104.
    Handles Colombian ',' decimals too ('122,5'->122.5) and thousands-dot areas
    ('1.200'->1200 only when clearly an integer thousands group)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value)
    m = re.search(r"\d[\d.,]*", s)
    if not m:
        return None
    tok = m.group()
    if "," in tok:                      # comma is the decimal sep -> drop dot thousands
        tok = tok.replace(".", "").replace(",", ".")
    elif tok.count(".") > 1:            # e.g. 1.234.5 -> treat leading dots as thousands
        head, _, tail = tok.rpartition(".")
        tok = head.replace(".", "") + "." + tail
    try:
        return float(tok)
    except ValueError:
        return None
