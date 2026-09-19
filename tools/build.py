#!/usr/bin/env python3
"""Render sites/<slug>.json -> <slug>/index.html.

    python3 tools/build.py                 # build every sites/*.json
    python3 tools/build.py lucky-jean-seafood chez-pierre-bakery-lakeview

The output is byte-identical to the hand-built v3 pages for the seven
original sites (see tools/test_roundtrip.py), so a new site only needs a
data file. Theme tokens live under "theme" in the JSON; everything else is
content. Photos are referenced relative to the site folder (img/NN.jpg).
"""
import html, json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE_STYLE = (ROOT / "tools" / "base_style.css").read_text()
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def e(x): return html.escape(str(x), quote=True)

def render_style(t):
    s = BASE_STYLE
    root = ";".join(f"{k}:{v}" for k, v in t["colors"].items())
    s = re.sub(r":root\{.*?\}", lambda m: ":root{" + root + "}", s, count=1)
    font = t["font_stack"]
    s = s.replace("'Libre Caslon Text', Georgia, serif", font)
    if t["dark"]:
        s = s.replace("opacity:.05;background-image", "opacity:.07;background-image")
    s = re.sub(r"\nh1\{.*?\}", lambda m: "\nh1{" + t["h1"] + "}", s, count=1)
    s = s.replace("h2{font-size:clamp(1.9rem,3.6vw,2.9rem);font-weight:700", f"h2{{font-size:clamp(1.9rem,3.6vw,2.9rem);font-weight:{t['h2_weight']}")
    s = s.replace("h3{font-size:1.25rem;font-weight:700}", f"h3{{font-size:1.25rem;font-weight:{t['h3_weight']}}}")
    s = re.sub(r"(\.brand\{font-family:.*?;font-size:1\.35rem;font-weight:)\d+", lambda m: m.group(1) + t["brand_weight"], s, count=1)
    if t["alt_dark"]:
        s = s.replace("section.alt .kicker{color:var(--acc2)}", "section.alt .kicker{color:rgba(255,255,255,.75)}")
    s = re.sub(r"(\.stat b\{.*?font-weight:)\d+\}", lambda m: m.group(1) + t["stat_weight"] + "}", s, count=1)
    s = re.sub(r"(\.num\{.*?font-weight:)\d+\}", lambda m: m.group(1) + t["num_weight"] + "}", s, count=1)
    s = re.sub(r"(\.quoteband blockquote\{.*?font-weight:)\d+\}", lambda m: m.group(1) + t["quote_weight"] + "}", s, count=1)
    s = re.sub(r"(\.big b\{.*?font-weight:)\d+\}", lambda m: m.group(1) + t["big_weight"] + "}", s, count=1)
    s = re.sub(r"(\.cloud span\{.*?;font-weight:)\d+(;cursor)", lambda m: m.group(1) + t["cloud_weight"] + m.group(2), s, count=1)
    if t["dark"]:
        s = s.replace("box-shadow:0 10px 40px rgba(0,0,0,.07)", "box-shadow:0 10px 40px rgba(0,0,0,.35)")
        s = s.replace("box-shadow:0 8px 30px rgba(0,0,0,.08);display:flex", "box-shadow:0 8px 30px rgba(0,0,0,.35);display:flex")
        s = s.replace("box-shadow:0 18px 50px rgba(0,0,0,.14)", "box-shadow:0 18px 50px rgba(0,0,0,.5)")
        s = s.replace("padding:28px;box-shadow:0 8px 30px rgba(0,0,0,.06)", "padding:28px;box-shadow:0 8px 30px rgba(0,0,0,.35)")
        s = s.replace("filter:grayscale(.2) contrast(1.05)", "filter:invert(.9) hue-rotate(180deg)")
    return s

def render(d):
    t = d["theme"]; name = d["name"]; N = e(name)
    tel = d["phone_e164"]; ph = e(d["phone_display"])
    lat, lng = d["geo"]["lat"], d["geo"]["lng"]
    dir_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}&destination_place_id={d['place_id']}"
    maps_url = f"https://www.google.com/maps?cid={d['cid']}"
    addr = e(d["address_display"])
    ld = {"@context": "https://schema.org", "@type": d["schema_type"], "name": name, "telephone": d["phone_schema"],
          "address": {"@type": "PostalAddress", **d["address"]},
          "geo": {"@type": "GeoCoordinates", "latitude": lat, "longitude": lng},
          "image": d["hero_img"], "servesCuisine": d["category"],
          "aggregateRating": {"@type": "AggregateRating", "ratingValue": d["rating"], "reviewCount": d["review_count"]},
          "hasMap": maps_url}
    if d.get("founding"): ld["foundingDate"] = d["founding"]
    ic = d["icon"]
    icon = ("data:image/svg+xml,&lt;svg xmlns=&quot;http://www.w3.org/2000/svg&quot; viewBox=&quot;0 0 64 64&quot;&gt;&lt;rect width=&quot;64&quot; height=&quot;64&quot; rx=&quot;14&quot; "
            f"fill=&quot;{ic['bg']}&quot;/&gt;&lt;text x=&quot;32&quot; y=&quot;41&quot; font-family=&quot;Georgia,serif&quot; font-weight=&quot;700&quot; font-size=&quot;28&quot; text-anchor=&quot;middle&quot; fill=&quot;{ic['fg']}&quot;&gt;{e(ic['initials'])}&lt;/text&gt;&lt;/svg&gt;")
    ring = e(f"{name} · {d['seal']['tag']} · " * 2)
    h1 = " ".join(f"<span style='--i:{i}'>{e(w)}</span>" for i, w in enumerate(d["hero"]["headline"].split(" ")))
    stats = "".join(f"<div class='stat rv'><b data-count='{e(s['count'])}'>{e(s['count'])}</b><span>{e(s['label'])}</span></div>" for s in d["stats"])
    story_ps = "".join(f"<p>{e(p)}</p>" for p in d["story"]["paragraphs"])
    facts = "".join(f"<li>{e(f)}</li>" for f in d["facts"])
    ig = f"<a href='{d['instagram']}' target='_blank' rel='noopener'>Instagram</a> · " if d.get("instagram") else ""
    ig_footer = f"<a href='{d['instagram']}' target='_blank' rel='noopener'>Instagram</a>" if d.get("instagram") else ""
    vcard = (f"data:text/vcard;charset=utf-8,BEGIN:VCARD%0AVERSION:3.0%0AFN:{N}%0AORG:{N}%0ATEL;TYPE=WORK:{tel}%0AADR;TYPE=WORK:;;{addr}%0AURL:{maps_url}%0AEND:VCARD")
    order = "".join(f"<article class='rv'><img src='{o['img']}' alt='{e(o['name'])}'><div class='b'><span class='num'>No. {i:02d}</span><h3>{e(o['name'])}</h3><p>{e(o['blurb'])}</p></div></article>" for i, o in enumerate(d["order"], 1))
    menu = "".join("<div class='mcol rv'><h3>" + e(c["h3"]) + "</h3><ul>" + "".join(f"<li><span>{e(it['name'])}</span><i></i><b>{e(it['price'])}</b></li>" for it in c["items"]) + "</ul></div>" for c in d["menu"]["cols"])
    total = sum(d["breakdown"]) or 1
    bars = "" if not d["breakdown"] else "".join(f"<div class='bar'><span>{5-i}</span><i><b style='--w:{c/total*100:.1f}%'></b></i><em>{c:,}</em></div>" for i, c in enumerate(d["breakdown"]))
    cloud = "".join(f"<span style='--s:{c['s']}' title='{c['mentions']} mentions'>{e(c['term'])}</span>" for c in d["cloud"])
    reviews = "".join(f"<div class='rev rv'><div class='stars'>{r['stars']}</div><p>{e(r['text'])}</p><small>{e(r['who'])}</small></div>" for r in d["reviews"])
    gallery = "".join(f"<a href='{g}' class='lb'><img src='{g}' alt='{N}'></a>" for g in d["gallery"])
    hours_rows = "\n".join(f"<tr data-day='{i}'><td>{DAYS[i]}</td><td>{e(h)}</td></tr>" for i, h in enumerate(d["hours_display"]))
    gh = "".join(f"<li>{e(x)}</li>" for x in d["getting_here"])
    seal = d["seal"]
    q = d.get("quote") or {}
    quoteband = (f"<div class='quoteband'><div class='im'><img src='{q['img']}' alt=''></div><div class='q'><blockquote class='rv'>{e(q['text'])}</blockquote><cite class='rv'>{e(q['cite'])}</cite></div></div>\n") if q.get("text") else ""
    footer = d.get("footer_note") or f"© 2026 {N}. Photos, reviews, hours and popular times from the business's public Google profile."
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>
<meta name='robots' content='noindex,nofollow'><title>{e(d['title'])}</title>
<meta name='description' content='{e(d['description'])}'><meta name='theme-color' content='{t['colors']['--bg']}'>
<meta property='og:title' content='{N}'><meta property='og:description' content='{e(d['description'])}'><meta property='og:type' content='business.business'><meta property='og:image' content='{d['hero_img']}'>
<link rel='icon' href='{icon}'>
<link rel='preconnect' href='https://fonts.googleapis.com'><link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>
<link href='https://fonts.googleapis.com/css2?family={t['font_link']}&family=Inter:wght@400;500;600&display=swap' rel='stylesheet'>
<script type='application/ld+json'>{json.dumps(ld)}</script>
<style>{render_style(t)}</style></head><body>
<div class='top'><div class='wrap'><a class='brand' href='#'><i>{e(ic['initials'])}</i>{N}</a><nav class='nav'><a href='#story'>Story</a><a href='#menu'>Menu</a><a href='#photos'>Photos</a><a href='#visit'>Hours & map</a><a href='tel:{tel}' style='opacity:1;color:var(--acc);font-weight:600'>{ph}</a></nav><span class='status'>Checking hours…</span></div></div>
<header class='hero'><img src='{d['hero_img']}' alt='{N}' fetchpriority='high'>
<svg class='seal' viewBox='0 0 150 150' aria-hidden='true'><defs><path id='c' d='M75,75 m-58,0 a58,58 0 1,1 116,0 a58,58 0 1,1 -116,0'/></defs><circle cx='75' cy='75' r='72'/><circle class='mid' cx='75' cy='75' r='44'/><text><textPath href='#c'>{ring}</textPath></text><text x='75' y='82' text-anchor='middle' style='{seal['center_style']}'>{e(seal['center'])}</text></svg>
<div class='wrap'>
<div class='rating'><span class='stars'>{d['stars']}</span><b>{d['rating']}</b><span>{e(d['review_count_display'])} Google reviews</span></div>
<div class='kicker'>{e(d['hero']['kicker'])}</div>
<h1>{h1}</h1>
<p class='sub'>{e(d['hero']['sub'])}</p>
<div class='actions'><a class='btn p' href='tel:{tel}'>Call {ph}</a><a class='btn {d['hero']['dir_btn']}' href='{dir_url}' target='_blank' rel='noopener'>Get directions</a><a class='btn g' style='color:#fff;border-color:rgba(255,255,255,.5)' href='#menu'>See the menu</a></div></div>
<div class='scrollhint'>Scroll</div></header>
<main>
<div class='statsbar'><div class='wrap stats'>{stats}</div></div>
<section id='story'><div class='wrap intro'><div class='story rv'><div class='kicker'>{e(d['story']['kicker'])}</div><h2>{e(d['story']['h2'])}</h2>{story_ps}</div>
<aside class='facts rv'><h3>Good to know</h3><ul>{facts}</ul><p class='addr'>{addr}</p><p class='today'><span class='status'>Checking hours…</span></p><p><a class='btn p' href='tel:{tel}'>Call {ph}</a></p><p style='margin:0'><a href='{maps_url}' target='_blank' rel='noopener'>Open in Google Maps</a> · {ig}<a href='{vcard}' download='{N}.vcf'>Save contact</a></p></aside></div></section>
<section id='order' class='alt'><div class='wrap'><div class='kicker rv'>What to order</div><h2 class='rv'>The regulars' list</h2><div class='sig'>{order}</div></div></section>
<section id='menu'><div class='wrap'><div class='kicker rv'>Menu</div><h2 class='rv'>Highlights & prices</h2><div class='menu'>{menu}</div><p class='menunote rv'>{e(d['menu']['note'])}</p></div></section>
{quoteband}<section id='reviews'><div class='wrap'><div class='ratingblock'><div><div class='kicker'>Reviews</div><div class='big'><b>{d['rating']}</b><div><div class='stars' style='font-size:1.3rem'>{d['stars']}</div><div style='color:var(--muted)'>{e(d['review_count_display'])} public Google reviews</div></div></div>{"<div style='margin-top:22px'>"+bars+"</div>" if bars else ""}<p style='margin-top:22px'><a class='btn g' href='https://search.google.com/local/writereview?placeid={d['place_id']}' target='_blank' rel='noopener'>Leave a Google review</a></p></div>
{"<div class='rv'><h3>"+e(d['cloud_h3'])+"</h3><div class='cloud'>"+cloud+"</div></div>" if cloud else ""}</div><div class='reviews'>{reviews}</div></div></section>
<section id='photos' class='alt'><div class='wrap'><div class='kicker rv'>Photos</div><h2 class='rv'>Around the place</h2><div class='mosaic'>{gallery}</div></div></section>
<section id='visit'><div class='wrap visit'><div class='rv'><div class='kicker'>Visit</div><h2>Hours & location</h2><table>{hours_rows}</table>
<div class='busy'><h3>Best time to come <span id='busytxt'></span></h3><div class='chart' id='chart'></div><div class='chartx' id='chartx'></div></div>
<div class='tip'><b>{e(d['tip']['b'])}</b>{e(d['tip']['text'])}</div></div>
<div class='rv'><iframe loading='lazy' src='https://maps.google.com/maps?q={lat},{lng}&z=16&output=embed' title='Map to {N}'></iframe><div class='dirs'><a class='btn g' href='{dir_url}' target='_blank' rel='noopener'>Google Maps</a><a class='btn g' href='https://maps.apple.com/?daddr={lat},{lng}&q={N}' target='_blank' rel='noopener'>Apple Maps</a><a class='btn g' href='https://m.uber.com/ul/?action=setPickup&pickup=my_location&dropoff[latitude]={lat}&dropoff[longitude]={lng}&dropoff[nickname]={N}' target='_blank' rel='noopener'>Ride there</a><button class='btn g' id='share'>Share</button></div><ul class='gh' style='margin-top:20px'>{gh}</ul><p class='addr' style='margin-top:14px;font-weight:500'>{addr}<br><a href='tel:{tel}'>{ph}</a></p></div></div></section>
<div class='cta'><div class='wrap'><h2 class='rv'>{e(d['cta_h2'])}</h2><div class='actions rv'><a class='btn p' href='tel:{tel}'>Call {ph}</a><a class='btn {d['cta_dir_btn']}' href='{dir_url}' target='_blank' rel='noopener'>Get directions</a></div></div></div>
</main>
<footer><div class='wrap row'><div><strong style='color:var(--ink)'>{N}</strong><br>{addr}<br><a href='tel:{tel}'>{ph}</a></div><div style='text-align:right'>{ig_footer}<br><small>{footer}</small></div></div></footer>
<div class='mobilebar'><a class='btn p' href='tel:{tel}'>Call</a><a class='btn g' href='{dir_url}' target='_blank' rel='noopener'>Directions</a><a class='btn g' href='#menu'>Menu</a></div>
<div class='lbx' id='lbx'><button class='x'>✕</button><button class='prev'>‹</button><img alt=''><button class='next'>›</button></div>
<div class='preview'>PREVIEW · NOT LIVE</div>
<script>
const HOURS={json.dumps(d['hours'])}, PT={json.dumps(d['popular_times'])};
""" + JS_TAIL

JS_TAIL = (ROOT / "tools" / "page.js").read_text() if (ROOT / "tools" / "page.js").exists() else ""

def build(slug):
    d = json.loads((ROOT / "sites" / f"{slug}.json").read_text())
    out = ROOT / slug / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(render(d))
    return out

if __name__ == "__main__":
    slugs = sys.argv[1:] or sorted(p.stem for p in (ROOT / "sites").glob("*.json"))
    for s in slugs:
        print("built", build(s))
