#!/usr/bin/env python3
"""Turn a tools/scrape_maps.js dump into sites/<slug>.json + <slug>/img/.

The Places API (New) is not enabled on this Google account, so fetch.py cannot
run. This is the same pipeline with the Maps page as the source: it builds the
Places-API-shaped dict fetch.py's skeleton() expects, hands it straight to
skeleton()/contact_sheet(), and additionally fills the three blocks the API
never had — the 5..1 star breakdown, popular times, and profile attributes.

    node tools/scrape_maps.js --place-id ChIJ... --out raw/markeys-bar.json
    python3 tools/from_scrape.py raw/markeys-bar.json [--csv-row "Markey's Bar"]

Numbers the sweep already verified (rating, review count, cid, neighborhood)
are taken from candidates.csv when --csv is given, since the Maps page drops
them under rate limiting.
"""
import argparse, csv, json, pathlib, re, sys, time
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import fetch as F  # slugify, initials, hours_from, pick_theme, skeleton, contact_sheet

DAY_IDX = {"Monday":0,"Tuesday":1,"Wednesday":2,"Thursday":3,"Friday":4,"Saturday":5,"Sunday":6}
API_DAY = {"Sunday":0,"Monday":1,"Tuesday":2,"Wednesday":3,"Thursday":4,"Friday":5,"Saturday":6}

def parse_clock(s):
    """'3 PM' / '11:30 AM' / 'Midnight' / 'Noon' -> minutes past midnight."""
    s = s.strip().lower().replace(' ', ' ')
    if s in ("midnight",): return 0
    if s in ("noon",): return 720
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", s)
    if not m: return None
    h = int(m.group(1)) % 12
    mm = int(m.group(2) or 0)
    if m.group(3) == "pm": h += 12
    return h * 60 + mm

def hours_to_periods(hours_raw):
    """{'Monday': '3 PM–3 AM'} -> Places API regularOpeningHours.periods"""
    periods = []
    for day, txt in (hours_raw or {}).items():
        if day not in API_DAY: continue
        t = (txt or "").strip()
        if not t or re.search(r"closed", t, re.I): continue
        if re.search(r"open 24 hours|24 hours", t, re.I):
            periods.append({"open": {"day": API_DAY[day], "hour": 0, "minute": 0}}); continue
        for chunk in re.split(r",\s*", t):
            m = re.match(r"(.+?)\s*[–—-]\s*(.+)", chunk)
            if not m: continue
            a, b = parse_clock(m.group(1)), parse_clock(m.group(2))
            if a is None or b is None: continue
            cd = API_DAY[day] if b > a else (API_DAY[day] + 1) % 7
            periods.append({"open": {"day": API_DAY[day], "hour": a // 60, "minute": a % 60},
                            "close": {"day": cd, "hour": (b // 60) % 24, "minute": b % 60}})
    return periods

def addr_components(formatted):
    """'949 N Rendon, New Orleans, LA 70119' -> addressComponents-ish"""
    out = []
    parts = [x.strip() for x in (formatted or "").split(",")]
    if parts:
        m = re.match(r"(\d+[A-Za-z]?)\s+(.*)", parts[0])
        if m:
            out.append({"types": ["street_number"], "longText": m.group(1)})
            out.append({"types": ["route"], "longText": m.group(2)})
        else:
            out.append({"types": ["route"], "longText": parts[0]})
    if len(parts) > 1: out.append({"types": ["locality"], "longText": parts[1]})
    if len(parts) > 2:
        m = re.match(r"([A-Z]{2})\s*(\d{5})?", parts[2])
        if m:
            out.append({"types": ["administrative_area_level_1"], "shortText": m.group(1), "longText": m.group(1)})
            if m.group(2): out.append({"types": ["postal_code"], "longText": m.group(2)})
    return out

def download(urls, folder, limit):
    """Save up to `limit` photos as NN.jpg; return fetch.py-style photo records."""
    folder.mkdir(parents=True, exist_ok=True)
    recs, n = [], 0
    for u in urls:
        if n >= limit: break
        n += 1
        dest = folder / f"{n:02d}.jpg"
        try:
            r = requests.get(u, timeout=45, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            if len(r.content) < 9000:   # placeholder / 1px
                n -= 1; continue
            dest.write_bytes(r.content)
            recs.append({"file": f"img/{n:02d}.jpg", "source": "google", "url": u.split("=")[0], "by": ""})
        except Exception as e:
            print(f"    photo {n} failed: {e}"); n -= 1
    return recs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("--csv", default=str(pathlib.Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/TheBrain/03 Projects/NOLA Web Studio/candidates.csv"))
    ap.add_argument("--photos", type=int, default=14)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    d = json.loads(pathlib.Path(a.raw).read_text())
    name = d.get("name") or ""
    if not name: sys.exit("scrape has no name")

    row = {}
    try:
        for r in csv.DictReader(open(a.csv)):
            if r["title"].strip().lower() == name.strip().lower(): row = r; break
    except Exception: pass
    # fall back to the file stem matching a csv title
    if not row:
        stem = pathlib.Path(a.raw).stem
        for r in csv.DictReader(open(a.csv)):
            if F.slugify(r["title"]) == stem: row = r; break

    site = (d.get("websiteUri") or "").strip()
    if site and "instagram.com" not in site and "facebook.com" not in site and not a.force:
        print(f"  HAS A WEBSITE already: {site}  (skip; --force to override)"); return

    rating = d.get("rating") or float(row.get("rating") or 0)
    count = d.get("userRatingCount") or int(float(row.get("votes") or 0))
    cat = d.get("category") or row.get("category") or "Restaurant"
    lat = d.get("lat") or float(row.get("lat") or 0)
    lng = d.get("lng") or float(row.get("lng") or 0)
    phone = d.get("nationalPhoneNumber") or ""
    intl = row.get("phone") or ""
    if phone and not intl:
        digits = re.sub(r"\D", "", phone)
        intl = "+1" + digits if len(digits) == 10 else ""
    addr = d.get("formattedAddress") or row.get("address") or ""

    p = {
        "displayName": {"text": name},
        "formattedAddress": addr,
        "addressComponents": addr_components(addr),
        "nationalPhoneNumber": phone,
        "internationalPhoneNumber": re.sub(r"[^\d+]", "", intl),
        "location": {"latitude": lat, "longitude": lng},
        "rating": rating, "userRatingCount": count,
        "regularOpeningHours": {"periods": hours_to_periods(d.get("hoursRaw"))},
        "reviews": [{"text": {"text": r["text"]}, "rating": r.get("rating", 5),
                     "authorAttribution": {"displayName": r.get("author", "")}} for r in d.get("reviews", [])],
        "websiteUri": site or None,
        "googleMapsUri": f"https://maps.google.com/?cid={d.get('cid_dec') or row.get('cid','')}",
        "primaryTypeDisplayName": {"text": cat},
        "primaryType": re.sub(r"[^a-z]+", "_", cat.lower()),
        "types": [re.sub(r"[^a-z]+", "_", cat.lower())],
        "businessStatus": "OPERATIONAL",
    }

    slug = F.slugify(name)
    folder = ROOT / slug / "img"
    out = ROOT / "sites" / f"{slug}.json"
    if out.exists() and not a.force:
        print(f"  {out} exists; --force to overwrite"); return

    photos = download(d.get("photos", []), folder, a.photos)
    spans, disp = F.hours_from(p)
    theme_slug, theme = F.pick_theme(p)
    site_json = F.skeleton(p, row.get("place_id") or d.get("place_id") or "", theme_slug, theme, photos, spans, disp)

    # neighbourhood + cid the sweep already resolved
    if row.get("borough"):
        site_json["seal"]["tag"] = row["borough"]
        site_json["story"]["kicker"] = row["borough"]
        street = site_json["address"]["streetAddress"]
        site_json["hero"]["kicker"] = f"{cat} · {street}, {row['borough']}"
    if row.get("cid"): site_json["cid"] = row["cid"]

    # the three blocks the Places API never had
    bd = {s: c for s, c in d.get("breakdown", [])}
    if bd:
        total = sum(bd.values()) or 1
        site_json["breakdown"] = [{"stars": s, "count": bd.get(s, 0),
                                   "pct": round(100 * bd.get(s, 0) / total)} for s in (5, 4, 3, 2, 1)]
    pop = d.get("popular") or []
    if pop:
        site_json["_scraped_popular"] = pop
    if d.get("attributes"):
        site_json["_source"]["attributes"] = d["attributes"]
    site_json["_source"]["scraped_from"] = d.get("url")
    site_json["_source"]["method"] = "maps page scrape (Places API New not enabled)"

    ig = (row.get("social") or "")
    if "instagram.com/" in ig and "/p/" not in ig and "/explore/" not in ig:
        h = ig.split("instagram.com/")[1].split("/")[0].split("?")[0]
        if h: site_json["instagram"] = f"https://www.instagram.com/{h}/"

    out.write_text(json.dumps(site_json, indent=1, ensure_ascii=False) + "\n")
    F.contact_sheet(folder, photos, name)
    print(f"  wrote {out} · {len(photos)} photos · theme {theme_slug} · sheet {folder/'_sheet.html'}")

if __name__ == "__main__":
    main()
