# Site pipeline

Every site under this repo is rendered from `sites/<slug>.json` by `tools/build.py`.
The seven original hand-built pages round-trip byte for byte (`tools/test_roundtrip.py`),
so the generator is the source of truth from here on.

## New site, start to finish

```bash
export GOOGLE_MAPS_API_KEY=...        # Places API (New) enabled
python3 tools/fetch.py "Name of Place, New Orleans" --instagram theirhandle
#   -> sites/<slug>.json (data filled, copy marked TODO)
#   -> <slug>/img/01..12.jpg (Google) and ig01..08.jpg (Instagram top posts by likes)
#   -> <slug>/img/_sheet.html contact sheet
open <slug>/img/_sheet.html            # pick hero, 4 order photos, quote photo, 6-8 gallery
$EDITOR sites/<slug>.json              # replace every TODO, set photo picks, trim menu
python3 tools/build.py <slug>
python3 tools/test_roundtrip.py        # originals still exact
git add -A && git commit
```

Batch: put one query or place id per line in a file and run `tools/fetch.py --list file`.
Places that already have a website are skipped (that is the whole point); `--force` overrides.

## What the API does not give you

Popular times, the 5..1 star breakdown, and the review topic cloud are not in the
Places API. The page hides those blocks when the fields are empty. If you scrape them
from the Maps page (as the original seven were), paste them in and they render.

## Files

- `tools/build.py` renders JSON to HTML. `tools/base_style.css` and `tools/page.js` are shared verbatim.
- `tools/extract.py` is the inverse, used to bootstrap the seven originals.
- `tools/themes.json` holds each original's theme block and a keyword map from Google place type to theme.
- `tools/fetch.py` pulls data and photos.

## Photo rights

Google profile photos include customer uploads and Instagram posts belong to the business.
Fine for a noindex preview. Before a site goes live under the owner's domain, get their
own photos or an okay on the ones used; `_source.photos` in the JSON records who took each one.
