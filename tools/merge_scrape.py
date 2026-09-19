#!/usr/bin/env python3
"""Merge a second scrape of the same place into the first.

The Maps place page serves two different layouts. One gives the rating, the
review count, the 5..1 breakdown and three review bodies but only a handful of
photos and a single attribute group. The other gives the full photo grid and
every attribute group but no review data at all. Which one you get is not
something the scraper controls, so places often need two passes.

    python3 tools/merge_scrape.py raw/two-sisters.json raw/two-sisters.b.json

Non-empty values in either file win; the richer of the two is kept per field.
"""
import json, pathlib, sys

RICHER_WINS = ["photos", "reviews", "attributes", "breakdown", "popular"]
FILL_IF_EMPTY = ["name", "rating", "userRatingCount", "category", "formattedAddress",
                 "nationalPhoneNumber", "websiteUri", "plusCode", "hoursRaw", "lat", "lng",
                 "cidHex", "ftid", "url", "place_id", "cid_dec"]

def main():
    if len(sys.argv) < 3:
        sys.exit("usage: merge_scrape.py base.json extra.json [more.json ...]")
    base_p = pathlib.Path(sys.argv[1])
    out = json.loads(base_p.read_text())
    for extra_p in sys.argv[2:]:
        ex = json.loads(pathlib.Path(extra_p).read_text())
        for k in RICHER_WINS:
            if len(ex.get(k) or []) > len(out.get(k) or []):
                out[k] = ex[k]
        for k in FILL_IF_EMPTY:
            if not out.get(k) and ex.get(k):
                out[k] = ex[k]
        # hours: whichever lists more days
        if len(ex.get("hoursRaw") or {}) > len(out.get("hoursRaw") or {}):
            out["hoursRaw"] = ex["hoursRaw"]
    base_p.write_text(json.dumps(out, indent=1))
    print(f"  {out.get('name')} -> rc={out.get('userRatingCount')} rev={len(out.get('reviews') or [])} "
          f"bd={len(out.get('breakdown') or [])} ph={len(out.get('photos') or [])} attrs={len(out.get('attributes') or [])}")

if __name__ == "__main__":
    main()
