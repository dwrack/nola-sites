#!/bin/bash
# Second pass: any raw scrape missing reviews or photos gets re-scraped and merged.
cd "$(dirname "$0")/.." || exit 1
while IFS=$'\t' read -r pid slug name; do
  [ -z "$pid" ] && continue
  case "$pid" in \#*) continue;; esac
  [ -s "raw/$slug.json" ] || continue
  thin=$(python3 -c "
import json;d=json.load(open('raw/$slug.json'))
print(1 if (len(d.get('reviews') or [])==0 or len(d.get('photos') or [])<14 or not d.get('userRatingCount')) else 0)")
  [ "$thin" = "1" ] || { echo "ok    $name"; continue; }
  echo "=== re-scrape $name"
  node tools/scrape_maps.js --place-id "$pid" --out "raw/$slug.b.json" 2>&1 | tail -1
  [ -s "raw/$slug.b.json" ] && python3 tools/merge_scrape.py "raw/$slug.json" "raw/$slug.b.json" && rm -f "raw/$slug.b.json"
  sleep 20
done < "${1:-prospects.tsv}"
echo "RESCRAPE DONE"
