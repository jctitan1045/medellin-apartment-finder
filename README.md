# Medellín Apartment Finder

A daily agent that scrapes Colombian real-estate portals for **unfurnished**
rental apartments in **El Poblado, Laureles, Envigado, and Ciudad del Río** that
fit a fixed spec, ranks them by a preference score, and delivers a ranked
shortlist to a dashboard + a morning WhatsApp/Telegram push.

## What it does each morning

1. **Scrape** Fincaraíz + Ciencuadras (per-neighborhood).
2. **Area-match** every listing by its own neighborhood/city (so a portal's
   fuzzy "nearby" padding can't leak the wrong barrio in).
3. **Hard-filter** (deal-breakers): rent+administración ≤ 4.5 M COP,
   ≥ 2 bed, ≥ 2 bath, not furnished.
4. **Score** survivors 0–100 on strong preferences (penthouse/top floor,
   balcony/terrace, view, pool, turco/sauna, office, 24h security, elevator,
   near park, natural light, 3+ beds, spaciousness, pet-friendly…).
5. **Dedup** against `data/seen.json` so the push only shows what's new.
6. **Publish** `docs/index.html` (GitHub Pages) and **push** new matches.

Anything that can't be auto-verified (furnished status, administración fee) is
**kept and flagged ⚠️**, never silently dropped.

## Configuration

Everything tunable lives in [`config.yaml`](config.yaml) — price cap, min
beds/baths, target-area neighborhood tokens, and every scoring weight. No code
changes needed to adjust the spec.

## Run locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python run.py --dry        # fast: 1 page/source, no push
python run.py --no-notify  # full scrape + dashboard, no push
python run.py              # full run + WhatsApp/Telegram push
```

Open `docs/index.html` in a browser to view the board.

## Deploy (GitHub Actions + Pages)

1. Push this repo to GitHub.
2. **Settings → Pages** → deploy from branch `main`, folder `/docs`.
3. **Settings → Secrets and variables → Actions** → add:
   `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`,
   `WHATSAPP_TO`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and optionally
   `DASHBOARD_URL`.
4. The workflow (`.github/workflows/daily.yml`) runs 07:30 America/Bogotá daily
   and can be triggered manually from the Actions tab. It commits the updated
   dashboard + dedup ledger back to the repo.

## Sources & status

| Portal | Status | Method |
|---|---|---|
| Fincaraíz   | ✅ live | `__NEXT_DATA__` JSON, plain HTTP |
| Ciencuadras | ✅ live | Angular state JSON, list + detail enrich |
| Metrocuadrado | ✅ live | Next.js RSC flight payload (`__next_f`), plain HTTP, 54/page |
| Properati   | ⏳ Phase 2 | 403s bots; needs headless fallback |

If a source is down, the run degrades gracefully and continues with the others.

## Layout

```
config.yaml            # all filters, areas, scoring weights
run.py                 # orchestrator (scrape → filter → score → dedup → publish)
core/     models, pipeline (filter/score/detect), store (dedup)
scrapers/ http, fincaraiz, ciencuadras
dashboard/ build.py    # renders docs/index.html
notify.py              # WhatsApp + Telegram push
data/     seen.json, listings.json   (committed for cross-run dedup)
docs/     index.html                 (GitHub Pages)
```
