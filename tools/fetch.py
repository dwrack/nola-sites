#!/usr/bin/env python3
"""Pull a business's public data into sites/<slug>.json and <slug>/img/.

    export GOOGLE_MAPS_API_KEY=...            # Places API (New) enabled on the key
    python3 tools/fetch.py "Lucky Jean Seafood, New Orleans"
    python3 tools/fetch.py ChIJ_VlHMjCoIIYRqvBMZjIrECQ --instagram luckyjeanseafood
    python3 tools/fetch.py --list prospects.txt   # one query or place_id per line, '#' comments

What it does
  1. Resolves the query to a place (Text Search), or uses the place_id directly.
  2. Pulls name, address, phone, geo, rating, review count, hours, reviews,
     website (to confirm there is none), Google Maps CID, and up to --photos
     Google photos at 1600px into <slug>/img/NN.jpg.
  3. If --instagram HANDLE is given (or the profile's website is an Instagram
     link), pulls the top --ig-posts posts by likes via instaloader into
     <slug>/img/igNN.jpg. Instaloader may need a login for some profiles;
     pass --ig-login USER once and it will cache the session.
  4. Writes sites/<slug>.json with every data field filled and every copy
     field (headline, story, "what to order", menu, tip) set to a TODO string,
     then writes <slug>/img/_sheet.html, a contact sheet for picking the hero,
     order, quote, and gallery photos.
  5. Picks a theme from tools/themes.json by the place's primary type.

Then: write the copy in the JSON, choose photos, and run tools/build.py.

Not available from the official API and left empty on purpose: popular
times (the page hides the chart when empty), the 5..1 star breakdown (bars
are hidden when empty), and the topic cloud (hidden when empty). The seven
original sites got those from the Google Maps page itself; if you have that
scrape, paste it into the JSON and the page will show it.
"""
import argparse, json, os, pathlib, re, sys, time
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://places.googleapis.com/v1"
FIELDS = ",".join([
    "id", "displayName", "formattedAddress", "addressComponents", "nationalPhoneNumber",
    "internationalPhoneNumber", "location", "rating", "userRatingCount", "regularOpeningHours",
    "reviews", "photos", "websiteUri", "googleMapsUri", "primaryTypeDisplayName", "primaryType",
    "editorialSummary", "priceLevel", "businessStatus", "types"])
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def key():
    k = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not k:
        sys.exit("Set GOOGLE_MAPS_API_KEY (a key with Places API (New) enabled).")
    return k

def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s

def initials(name):
    words = [w for w in re.findall(r"[A-Za-z]+", name) if w.lower() not in ("the", "and", "of", "inc", "llc")]
    return "".join(w[0] for w in words[:2]).upper() or name[:2].upper()

def fmt(m):
    m %= 1440; h, mm = divmod(m, 60); ap = "am" if h < 12 else "pm"; h = h % 12 or 12
    return f"{h}:{mm:02d}{ap}" if mm else f"{h}{ap}"

def resolve(query, k):
    if re.fullmatch(r"ChIJ[A-Za-z0-9_-]+", query):
        return query
    r = requests.post(f"{API}/places:searchText", json={"textQuery": query, "maxResultCount": 1},
                      headers={"X-Goog-Api-Key": k, "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress"}, timeout=30)
    r.raise_for_status()
    places = r.json().get("places", [])
    if not places:
        sys.exit(f"No place found for: {query}")
    p = places[0]
    print(f"  -> {p['displayName']['text']} · {p.get('formattedAddress','')}")
    return p["id"]

def details(pid, k):
    r = requests.get(f"{API}/places/{pid}", headers={"X-Goog-Api-Key": k, "X-Goog-FieldMask": FIELDS}, timeout=30)
    r.raise_for_status()
    return r.json()

def hours_from(p):
    """-> (HOURS spans Mon-first in minutes, display strings). Closed day = []."""
    spans = [[] for _ in range(7)]
    periods = (p.get("regularOpeningHours") or {}).get("periods") or []
    for per in periods:
        o = per.get("open", {}); c = per.get("close")
        d = (o.get("day", 0) + 6) % 7
        start = o.get("hour", 0) * 60 + o.get("minute", 0)
        if not c:  # open 24 hours
            spans[d].append([0, 1440]); continue
        end = c.get("hour", 0) * 60 + c.get("minute", 0)
        if (c.get("day", 0) + 6) % 7 != d or end <= start:
            end += 1440
        spans[d].append([start, end])
    disp = []
    for s in spans:
        if not s: disp.append("Closed")
        elif s == [[0, 1440]]: disp.append("Open 24 hours")
        else: disp.append(", ".join(f"{fmt(a)} – {fmt(b)}" for a, b in sorted(s)))
    return spans, disp

def download(url, dest, k=None):
    r = requests.get(url, headers={"X-Goog-Api-Key": k} if k else {}, timeout=60, allow_redirects=True)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return len(r.content)

def google_photos(p, folder, n, k):
    out = []
    for i, ph in enumerate((p.get("photos") or [])[:n], 1):
        dest = folder / f"{i:02d}.jpg"
        try:
            size = download(f"{API}/{ph['name']}/media?maxWidthPx=1600&maxHeightPx=1600", dest, k)
            attrib = ", ".join(a.get("displayName", "") for a in ph.get("authorAttributions", []))
            out.append({"file": f"img/{dest.name}", "source": "google", "by": attrib, "w": ph.get("widthPx"), "h": ph.get("heightPx")})
            print(f"  photo {dest.name} {size//1024}KB {attrib}")
        except Exception as ex:
            print(f"  photo {i} failed: {ex}")
        time.sleep(0.2)
    return out

def instagram_photos(handle, folder, n, login=None):
    try:
        import instaloader
    except ImportError:
        print("  instaloader not installed (pip install instaloader); skipping Instagram"); return []
    L = instaloader.Instaloader(download_pictures=False, download_videos=False, download_video_thumbnails=False,
                                download_comments=False, save_metadata=False, quiet=True)
    if login:
        try: L.load_session_from_file(login)
        except FileNotFoundError:
            L.interactive_login(login); L.save_session_to_file()
    try:
        prof = instaloader.Profile.from_username(L.context, handle)
    except Exception as ex:
        print(f"  instagram {handle}: {ex}"); return []
    posts = []
    for i, post in enumerate(prof.get_posts()):
        if i >= 120: break
        if post.is_video: continue
        posts.append(post)
    posts.sort(key=lambda p: p.likes, reverse=True)
    out = []
    for i, post in enumerate(posts[:n], 1):
        dest = folder / f"ig{i:02d}.jpg"
        try:
            download(post.url, dest)
            out.append({"file": f"img/{dest.name}", "source": "instagram", "likes": post.likes, "caption": (post.caption or "")[:140], "url": f"https://www.instagram.com/p/{post.shortcode}/"})
            print(f"  ig {dest.name} {post.likes} likes")
        except Exception as ex:
            print(f"  ig post {post.shortcode} failed: {ex}")
    return out

def pick_theme(p):
    lib = json.loads((ROOT / "tools" / "themes.json").read_text())
    hay = " ".join([p.get("primaryType", ""), (p.get("primaryTypeDisplayName") or {}).get("text", ""), " ".join(p.get("types", []))]).lower()
    for word, slug in lib["_verticals"].items():
        if word != "default" and word in hay:
            return slug, lib["themes"][slug]
    return "mother-s-restaurant", lib["themes"]["mother-s-restaurant"]

def contact_sheet(folder, photos, name):
    cells = "".join(f"<figure><img src='{ph['file'].split('/')[-1]}' loading='lazy'><figcaption>{ph['file']}<br><small>{ph.get('by') or ph.get('caption','')}{' · '+str(ph['likes'])+' likes' if 'likes' in ph else ''}</small></figcaption></figure>" for ph in photos)
    (folder / "_sheet.html").write_text(f"<!doctype html><meta charset=utf-8><title>{name} photos</title><style>body{{font:14px system-ui;margin:20px}}div{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}}img{{width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:6px}}figure{{margin:0}}</style><h1>{name}</h1><p>Pick hero (1), what-to-order (3–4), quote band (1), gallery (6–8). Not for the site: blurry, dark, screenshots, menus as photos, other people's faces up close.</p><div>{cells}</div>")

def skeleton(p, pid, theme_slug, theme, photos, spans, disp):
    name = p["displayName"]["text"]
    comp = {c["types"][0]: c for c in p.get("addressComponents", []) if c.get("types")}
    street = " ".join(x for x in [comp.get("street_number", {}).get("longText"), comp.get("route", {}).get("longText")] if x) or p.get("formattedAddress", "").split(",")[0]
    city = comp.get("locality", {}).get("longText", "New Orleans"); region = comp.get("administrative_area_level_1", {}).get("shortText", "LA"); zipc = comp.get("postal_code", {}).get("longText", "")
    hood = comp.get("neighborhood", {}).get("longText") or comp.get("sublocality", {}).get("longText") or city
    nat = p.get("nationalPhoneNumber", ""); intl = re.sub(r"[^\d+]", "", p.get("internationalPhoneNumber", "") or "")
    cid = re.search(r"cid=(\d+)", p.get("googleMapsUri", "") or "")
    rating = p.get("rating", 0); count = p.get("userRatingCount", 0)
    cat = (p.get("primaryTypeDisplayName") or {}).get("text", "Restaurant")
    stars = "★" * int(rating) + "☆" * (5 - int(rating))
    reviews = []
    for r in (p.get("reviews") or []):
        t = (r.get("text") or {}).get("text", "").strip()
        if not t: continue
        if len(t) > 300: t = t[:300].rstrip() + "…"
        reviews.append({"stars": "★" * int(r.get("rating", 5)) + "☆" * (5 - int(r.get("rating", 5))), "text": f"“{t}”", "who": f"{(r.get('authorAttribution') or {}).get('displayName','')} · Google"})
    reviews.sort(key=lambda r: -r["stars"].count("★"))
    g = [ph["file"] for ph in photos if ph["source"] == "google"]
    ig = [ph["file"] for ph in photos if ph["source"] == "instagram"]
    allp = ig[:1] + g if ig else g
    hero = allp[0] if allp else "img/01.jpg"
    TODO = "TODO"
    return {
        "slug": slugify(name), "theme": theme, "theme_from": theme_slug,
        "title": f"{name} · {cat} · {city}", "description": f"{TODO}: one sentence, ~120 chars, the thing locals say about this place.",
        "icon": {"bg": theme["colors"]["--acc"], "fg": theme["colors"]["--accink"], "initials": initials(name)},
        "schema_type": "Restaurant" if "restaurant" in cat.lower() or "food" in " ".join(p.get("types", [])) else "LocalBusiness",
        "name": name, "phone_e164": intl, "phone_schema": (intl[:2] + intl[2:5] + "-" + intl[5:8] + "-" + intl[8:]) if len(intl) == 12 else intl,
        "address": {"streetAddress": street, "addressLocality": city, "addressRegion": region, "postalCode": zipc},
        "geo": {"lat": p["location"]["latitude"], "lng": p["location"]["longitude"]},
        "hero_img": hero, "category": cat, "rating": rating, "review_count": count, "cid": cid.group(1) if cid else "",
        "place_id": pid, "phone_display": nat,
        "seal": {"tag": hood, "center": initials(name), "center_style": "font-size:20px;letter-spacing:0;font-family:Georgia,serif;font-weight:700"},
        "stars": stars,
        "hero": {"kicker": f"{cat} · {street}, {hood}", "headline": f"{TODO} headline, one sentence, twelve to twenty words, the reason people come.",
                 "sub": f"{TODO}: two sentences. What it is, who it is for, the one detail that proves you have been there.", "dir_btn": "w"},
        "stats": [{"count": f"{count:,}", "label": "Google reviews"}, {"count": str(rating), "label": "stars on Google"}, {"count": TODO, "label": TODO}, {"count": TODO, "label": TODO}],
        "story": {"kicker": hood, "h2": name, "paragraphs": [f"{TODO}: paragraph one, the history and the room.", f"{TODO}: paragraph two, the food and who orders it."]},
        "facts": [f"{TODO} fact from the Google profile (service options, payments, parking, accessibility)"] * 5,
        "address_display": f"{street}, {city}, {region} {zipc}",
        "instagram": None,
        "order": [{"img": (allp[i + 1] if len(allp) > i + 1 else hero), "name": f"{TODO} dish {i+1}", "blurb": f"{TODO} one line, what it is and why."} for i in range(4)],
        "menu": {"cols": [{"h3": f"{TODO} section", "items": [{"name": f"{TODO} item", "price": "0.00"}] * 4} for _ in range(3)], "note": "From the current menu. Prices as posted and subject to change."},
        "quote": {"img": allp[1] if len(allp) > 1 else hero, "text": reviews[0]["text"] if reviews else f"“{TODO}”", "cite": f"Google review · {rating} stars from {count:,} reviews"},
        "review_count_display": f"{count:,}", "breakdown": [], "cloud": [], "cloud_h3": f"What {count:,} people keep mentioning",
        "reviews": reviews[:3],
        "gallery": allp[2:9] if len(allp) > 2 else allp,
        "hours_display": disp, "hours": spans, "popular_times": {},
        "tip": {"b": "Local tip", "text": f"{TODO}: when to come and what to do when you get there."},
        "getting_here": [f"{TODO}: nearest landmark or cross street", f"{TODO}: parking or transit"],
        "cta_h2": f"Come hungry. {name} is waiting.", "cta_dir_btn": "g",
        "_source": {"website": p.get("websiteUri"), "maps": p.get("googleMapsUri"), "status": p.get("businessStatus"), "price": p.get("priceLevel"),
                     "summary": (p.get("editorialSummary") or {}).get("text"), "photos": photos, "fetched": time.strftime("%Y-%m-%d")},
    }

def run(query, args, k):
    print(query)
    pid = resolve(query, k)
    p = details(pid, k)
    name = p["displayName"]["text"]; slug = slugify(name)
    if p.get("websiteUri") and "instagram.com" not in p["websiteUri"] and "facebook.com" not in p["websiteUri"] and not args.force:
        print(f"  HAS A WEBSITE already: {p['websiteUri']}  (skip; pass --force to build anyway)"); return
    folder = ROOT / slug / "img"; folder.mkdir(parents=True, exist_ok=True)
    photos = google_photos(p, folder, args.photos, k)
    ig = args.instagram
    if not ig and p.get("websiteUri") and "instagram.com" in p["websiteUri"]:
        ig = p["websiteUri"].rstrip("/").split("/")[-1]
    if ig:
        photos += instagram_photos(ig, folder, args.ig_posts, args.ig_login)
    spans, disp = hours_from(p)
    theme_slug, theme = pick_theme(p)
    d = skeleton(p, pid, theme_slug, theme, photos, spans, disp)
    if ig: d["instagram"] = f"https://www.instagram.com/{ig}/"
    out = ROOT / "sites" / f"{slug}.json"
    if out.exists() and not args.force:
        print(f"  {out} exists; pass --force to overwrite"); return
    out.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")
    contact_sheet(folder, photos, name)
    print(f"  wrote {out} · {len(photos)} photos · theme {theme_slug} · open {folder/'_sheet.html'} to pick photos")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("queries", nargs="*", help="'Name, City' text queries or ChIJ place ids")
    ap.add_argument("--list", help="file with one query per line")
    ap.add_argument("--instagram", help="handle, for a single query")
    ap.add_argument("--photos", type=int, default=12)
    ap.add_argument("--ig-posts", type=int, default=8)
    ap.add_argument("--ig-login", help="your Instagram username; session is cached after the first login")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    qs = list(a.queries)
    if a.list:
        qs += [l.strip() for l in open(a.list) if l.strip() and not l.startswith("#")]
    if not qs: ap.error("give a query, a place id, or --list")
    k = key()
    for q in qs:
        try: run(q, a, k)
        except requests.HTTPError as ex:
            print(f"  API error: {ex} {ex.response.text[:300]}")
