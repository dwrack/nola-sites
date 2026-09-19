#!/bin/bash
# Scrape every Round 2 prospect's Maps page, paced so Google does not
# drop us into the signed-out "limited view" that hides review counts.
#   bash tools/scrape_round2.sh [prospects.tsv]
cd "$(dirname "$0")/.." || exit 1
LIST="${1:-prospects.tsv}"
mkdir -p raw
while IFS=$'\t' read -r pid slug name; do
  [ -z "$pid" ] && continue
  case "$pid" in \#*) continue;; esac
  if [ -s "raw/$slug.json" ]; then echo "skip  $name (have raw/$slug.json)"; continue; fi
  echo "=== $name"
  node tools/scrape_maps.js --place-id "$pid" --out "raw/$slug.json" 2>&1 | tail -2
  sleep 25
done < "$LIST"
echo "ALL DONE"
