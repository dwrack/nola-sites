#!/usr/bin/env python3
"""Prove build.py reproduces every existing site byte for byte from its JSON."""
import pathlib, sys, difflib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build, json
ROOT = build.ROOT
ok = True
pending = []
for p in sorted((ROOT / "sites").glob("*.json")):
    built = ROOT / p.stem / "index.html"
    if not built.exists():
        # a site whose JSON exists but has not been built yet is not a failure,
        # it is work in progress. Hard-reading it made this test blow up whenever
        # two people were adding sites at once.
        pending.append(p.stem)
        continue
    orig = built.read_text()
    new = build.render(json.loads(p.read_text()))
    if orig == new:
        print("OK  ", p.stem)
    else:
        ok = False
        i = next(k for k in range(min(len(orig), len(new))) if orig[k] != new[k]) if orig[:min(len(orig),len(new))] != new[:min(len(orig),len(new))] else min(len(orig),len(new))
        print("DIFF", p.stem, "at", i, "\n  orig:", repr(orig[max(0,i-80):i+120]), "\n  new: ", repr(new[max(0,i-80):i+120]))
for stem in pending:
    print("SKIP", stem, "(no index.html yet, run tools/build.py)")
sys.exit(0 if ok else 1)
