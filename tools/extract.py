#!/usr/bin/env python3
"""Extract a v3 hand-built site (index.html) back into sites/<slug>.json.

Used once to bootstrap the data files for the seven original sites, and by
tools/test_roundtrip.py to prove build.py reproduces them byte for byte.
"""
import html, json, re, sys, pathlib

def unesc(s): return html.unescape(s)

def grab(pat, s, flags=re.S, group=1, default=None):
    m = re.search(pat, s, flags)
    if not m:
        if default is not None: return default
        raise SystemExit(f"pattern not found: {pat[:60]}")
    return m.group(group)

def extract(path):
    s = pathlib.Path(path).read_text()
    slug = pathlib.Path(path).parent.name
    d = {"slug": slug}
    style = grab(r"<style>(.*?)</style>", s)

    # ---- theme -------------------------------------------------------
    root = grab(r":root\{(.*?)\}", style)
    colors = dict(kv.split(":", 1) for kv in root.split(";") if kv)
    d["theme"] = {
        "colors": colors,
        "font_link": grab(r"css2\?family=(.*?)&family=Inter", s),
        "font_stack": grab(r"h1,h2,h3,\.disp\{font-family:(.*?);margin", style),
        "h1": grab(r"\nh1\{(.*?)\}", style),
        "h2_weight": grab(r"\nh2\{font-size:clamp\(1\.9rem,3\.6vw,2\.9rem\);font-weight:(\d+)", style),
        "h3_weight": grab(r"\nh3\{font-size:1\.25rem;font-weight:(\d+)\}", style),
        "brand_weight": grab(r"\.brand\{font-family:.*?;font-size:1\.35rem;font-weight:(\d+)", style),
        "stat_weight": grab(r"\.stat b\{.*?font-weight:(\d+)\}", style),
        "num_weight": grab(r"\.num\{.*?font-weight:(\d+)\}", style),
        "quote_weight": grab(r"\.quoteband blockquote\{.*?font-weight:(\d+)\}", style),
        "big_weight": grab(r"\.big b\{.*?font-weight:(\d+)\}", style),
        "cloud_weight": grab(r"\.cloud span\{.*?;font-weight:(\d+);cursor", style),
        "dark": "opacity:.07;background-image" in style,
        "alt_dark": "section.alt .kicker{color:rgba(255,255,255,.75)}" in style,
    }

    # ---- head --------------------------------------------------------
    d["title"] = unesc(grab(r"<title>(.*?)</title>", s))
    d["description"] = unesc(grab(r"<meta name='description' content='(.*?)'>", s))
    m = re.search(r"rx=&quot;14&quot; fill=&quot;(.*?)&quot;/&gt;.*?text-anchor=&quot;middle&quot; fill=&quot;(.*?)&quot;&gt;(.*?)&lt;/text", s, re.S)
    d["icon"] = {"bg": m.group(1), "fg": m.group(2), "initials": unesc(m.group(3))}
    ld = json.loads(grab(r"<script type='application/ld\+json'>(.*?)</script>", s))
    d["schema_type"] = ld["@type"]
    d["name"] = ld["name"]
    d["phone_e164"] = ld["telephone"].replace("-", "")
    d["phone_schema"] = ld["telephone"]
    d["address"] = {k: ld["address"][k] for k in ("streetAddress", "addressLocality", "addressRegion", "postalCode")}
    d["geo"] = {"lat": ld["geo"]["latitude"], "lng": ld["geo"]["longitude"]}
    d["hero_img"] = ld["image"]
    d["category"] = ld["servesCuisine"]
    d["rating"] = ld["aggregateRating"]["ratingValue"]
    d["review_count"] = ld["aggregateRating"]["reviewCount"]
    d["cid"] = ld["hasMap"].split("cid=")[1]
    if "foundingDate" in ld: d["founding"] = ld["foundingDate"]
    d["place_id"] = grab(r"destination_place_id=([A-Za-z0-9_-]+)", s)

    # ---- top bar / hero ----------------------------------------------
    d["phone_display"] = unesc(grab(r"<a href='tel:\+\d+' style='opacity:1;color:var\(--acc\);font-weight:600'>(.*?)</a>", s))
    seal = grab(r"<textPath href='#c'>(.*?)</textPath></text><text x='75' y='82' text-anchor='middle' style='([^']*)'>(.*?)</text>", s, group=0)
    m = re.search(r"<textPath href='#c'>(.*?)</textPath></text><text x='75' y='82' text-anchor='middle' style='([^']*)'>(.*?)</text>", s, re.S)
    ring = unesc(m.group(1))
    unit = ring[: len(ring)//2]  # "Name · X · " repeated twice
    d["seal"] = {"tag": unit.split(" · ")[1], "center": unesc(m.group(3)), "center_style": m.group(2)}
    d["stars"] = grab(r"<div class='rating'><span class='stars'>(.*?)</span>", s)
    d["hero"] = {
        "kicker": unesc(grab(r"<div class='kicker'>(.*?)</div>\n<h1>", s)),
        "headline": unesc(re.sub(r"<span style='--i:\d+'>|</span>", "", grab(r"<h1>(.*?)</h1>", s))),
        "sub": unesc(grab(r"<p class='sub'>(.*?)</p>", s)),
        "dir_btn": grab(r"<a class='btn (\w)' href='https://www.google.com/maps/dir/[^']*' target='_blank' rel='noopener'>Get directions</a><a class='btn g' style", s),
    }
    # ---- stats ---------------------------------------------------------
    d["stats"] = [{"count": unesc(c), "label": unesc(l)} for c, l in re.findall(r"<div class='stat rv'><b data-count='[^']*'>(.*?)</b><span>(.*?)</span></div>", s, re.S)]
    # ---- story -----------------------------------------------------------
    story = grab(r"<div class='story rv'><div class='kicker'>(.*?)</div><h2>(.*?)</h2>(.*?)</div>\n<aside", s, group=0)
    m = re.search(r"<div class='story rv'><div class='kicker'>(.*?)</div><h2>(.*?)</h2>(.*?)</div>\n<aside", s, re.S)
    d["story"] = {"kicker": unesc(m.group(1)), "h2": unesc(m.group(2)),
                  "paragraphs": [unesc(p) for p in re.findall(r"<p>(.*?)</p>", m.group(3), re.S)]}
    facts = grab(r"<aside class='facts rv'><h3>Good to know</h3><ul>(.*?)</ul>", s)
    d["facts"] = [unesc(x) for x in re.findall(r"<li>(.*?)</li>", facts, re.S)]
    d["address_display"] = unesc(grab(r"<p class='addr'>(.*?)</p>", s))
    d["instagram"] = grab(r"<a href='(https://www.instagram.com/[^']*)' target='_blank' rel='noopener'>Instagram</a>", s, default="") or None
    # ---- order ---------------------------------------------------------
    d["order"] = [{"img": i, "name": unesc(n), "blurb": unesc(b)} for i, n, b in
                  re.findall(r"<article class='rv'><img src='(.*?)' alt='.*?'><div class='b'><span class='num'>No\. \d+</span><h3>(.*?)</h3><p>(.*?)</p></div></article>", s, re.S)]
    # ---- menu ------------------------------------------------------------
    menu = grab(r"<div class='menu'>(.*?)</div><p class='menunote rv'>(.*?)</p>", s, group=0)
    m = re.search(r"<div class='menu'>(.*?)</div><p class='menunote rv'>(.*?)</p>", s, re.S)
    cols = []
    for h, items in re.findall(r"<div class='mcol rv'><h3>(.*?)</h3><ul>(.*?)</ul></div>", m.group(1), re.S):
        cols.append({"h3": unesc(h), "items": [{"name": unesc(n), "price": unesc(p)} for n, p in re.findall(r"<li><span>(.*?)</span><i></i><b>(.*?)</b></li>", items, re.S)]})
    d["menu"] = {"cols": cols, "note": unesc(m.group(2))}
    # ---- quote -------------------------------------------------------------
    m = re.search(r"<div class='quoteband'><div class='im'><img src='(.*?)' alt=''></div><div class='q'><blockquote class='rv'>(.*?)</blockquote><cite class='rv'>(.*?)</cite>", s, re.S)
    d["quote"] = {"img": m.group(1), "text": unesc(m.group(2)), "cite": unesc(m.group(3))}
    # ---- reviews -------------------------------------------------------------
    d["review_count_display"] = unesc(grab(r"<div style='color:var\(--muted\)'>(.*?) public Google reviews</div>", s))
    d["breakdown"] = [int(c.replace(",", "")) for c in re.findall(r"<div class='bar'><span>\d</span><i><b style='--w:[\d.]+%'></b></i><em>(.*?)</em></div>", s, re.S)]
    d["cloud"] = [{"s": sc, "mentions": int(mn), "term": unesc(t)} for sc, mn, t in
                  re.findall(r"<span style='--s:([\d.]+)' title='(\d+) mentions'>(.*?)</span>", s, re.S)]
    d["cloud_h3"] = unesc(grab(r"<div class='rv'><h3>(.*?)</h3><div class='cloud'>", s))
    d["reviews"] = [{"stars": st, "text": unesc(t), "who": unesc(w)} for st, t, w in
                    re.findall(r"<div class='rev rv'><div class='stars'>(.*?)</div><p>(.*?)</p><small>(.*?)</small></div>", s, re.S)]
    # ---- gallery -----------------------------------------------------------------
    d["gallery"] = re.findall(r"<a href='([^']*)' class='lb'>", s)
    # ---- visit -------------------------------------------------------------------
    d["hours_display"] = [unesc(h) for h in re.findall(r"<tr data-day='\d'><td>\w+</td><td>(.*?)</td></tr>", s, re.S)]
    m = re.search(r"<div class='tip'><b>(.*?)</b>(.*?)</div>", s, re.S)
    d["tip"] = {"b": unesc(m.group(1)), "text": unesc(m.group(2))}
    gh = grab(r"<ul class='gh' style='margin-top:20px'>(.*?)</ul>", s)
    d["getting_here"] = [unesc(x) for x in re.findall(r"<li>(.*?)</li>", gh, re.S)]
    d["cta_h2"] = unesc(grab(r"<div class='cta'><div class='wrap'><h2 class='rv'>(.*?)</h2>", s))
    d["cta_dir_btn"] = grab(r"<div class='cta'>.*?<a class='btn (\w)' href='https://www.google.com/maps/dir", s)
    # ---- js data --------------------------------------------------------------------
    d["hours"] = json.loads(grab(r"const HOURS=(\[.*?\]), PT=", s))
    d["popular_times"] = json.loads(grab(r", PT=(\{.*?\});\n", s))
    return d

if __name__ == "__main__":
    for p in sys.argv[1:]:
        data = extract(p)
        out = pathlib.Path("sites") / f"{data['slug']}.json"
        out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
        print("wrote", out)
