"""Push delivery to WhatsApp (Twilio) + Telegram.

Reads credentials from env vars (same names Jordan's other projects use). If a
channel's creds are missing it's skipped silently, so local runs never fail.

Env:
  Twilio:   TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
            TWILIO_WHATSAPP_FROM (e.g. 'whatsapp:+14155238886'),
            WHATSAPP_TO         (e.g. 'whatsapp:+57...')
  Telegram: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request


def _post(url: str, data: dict, auth: tuple | None = None,
          headers: dict | None = None) -> bool:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers or {})
    if auth:
        import base64
        token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return 200 <= r.status < 300
    except Exception as e:
        print(f"    ! push error: {e}")
        return False


def send_whatsapp(text: str) -> bool:
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    tok = os.getenv("TWILIO_AUTH_TOKEN")
    frm = os.getenv("TWILIO_WHATSAPP_FROM")
    to = os.getenv("WHATSAPP_TO")
    if not all([sid, tok, frm, to]):
        print("    · WhatsApp: creds not set, skipping")
        return False
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    ok = _post(url, {"From": frm, "To": to, "Body": text}, auth=(sid, tok))
    print(f"    · WhatsApp: {'sent' if ok else 'failed'}")
    return ok


def send_telegram(text: str) -> bool:
    tok = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not all([tok, chat]):
        print("    · Telegram: creds not set, skipping")
        return False
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    ok = _post(url, {"chat_id": chat, "text": text,
                     "parse_mode": "Markdown",
                     "disable_web_page_preview": "false"})
    print(f"    · Telegram: {'sent' if ok else 'failed'}")
    return ok


def format_push(new_listings: list, dashboard_url: str, cfg: dict) -> str:
    """Compose the morning message from the new-listing dicts (already sorted)."""
    n = len(new_listings)
    if n == 0:
        return ("🏠 *Medellín Apartment Finder*\nNo new matches today. "
                f"Full board: {dashboard_url}")

    cap = cfg["output"].get("push_max_items", 15)
    lines = [f"🏠 *Medellín Apartment Finder* — {n} new match{'es' if n != 1 else ''} today\n"]
    for l in new_listings[:cap]:
        usd = f"~${l['price_usd']}" if l.get("price_usd") else ""
        area = l.get("area_key", "").replace("_", " ").title()
        beds = l.get("bedrooms") or "?"
        baths = l.get("bathrooms") or "?"
        m2 = f"{int(l['area_m2'])}m²" if l.get("area_m2") else ""
        price = f"{l['price_total']:,}".replace(",", ".") if l.get("price_total") else "?"
        flags = ", ".join(l.get("score_flags", [])[:4])
        note = " ⚠️" + "; ".join(l["notes"]) if l.get("notes") else ""
        lines.append(
            f"*[{l['score']}]* {area} · {beds}bd/{baths}ba {m2} · "
            f"${price} COP {usd}\n{flags}\n{l['url']}{note}\n")
    if n > cap:
        lines.append(f"…and {n - cap} more.")
    lines.append(f"\nFull ranked board → {dashboard_url}")
    return "\n".join(lines)


def push(new_listings: list, dashboard_url: str, cfg: dict) -> None:
    msg = format_push(new_listings, dashboard_url, cfg)
    send_whatsapp(msg)
    send_telegram(msg)
