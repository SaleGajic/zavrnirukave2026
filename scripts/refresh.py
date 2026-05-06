#!/usr/bin/env python3
"""Fetch zavrnirukave.rs locations page via WP REST and emit locations.json.

Exits 0 on success (whether or not file changed). Exits non-zero on fetch/parse error.
The workflow checks `git status` to decide whether to commit.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

SOURCE = "https://zavrnirukave.rs/wp-json/wp/v2/pages?slug=prijavljene-lokacije"
OUT = Path(__file__).resolve().parent.parent / "locations.json"

REGIONS = {
    "Beograd",
    "Vojvodina",
    "Centralna Srbija",
    "Zapadna Srbija",
    "Istočna Srbija",
    "Južna Srbija",
}


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "zavrnirukave2026-refresh/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def parse(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []
    region: str | None = None
    coord_re = re.compile(r"query=([-\d.]+),([-\d.]+)")
    for el in soup.find_all(["h1", "h2", "h3", "h4", "table"]):
        if el.name != "table":
            t = el.get_text(strip=True)
            if t in REGIONS:
                region = t
            continue
        if region is None:
            continue
        rows = el.find_all("tr")
        if not rows:
            continue
        headers = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
        for tr in rows[1:]:
            link = tr.find("a", href=coord_re)
            if not link:
                continue
            m = coord_re.search(link["href"])
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            row = dict(zip(headers, cells))
            out.append(
                {
                    "r": region,
                    "lat": float(m.group(1)),
                    "lon": float(m.group(2)),
                    "name": row.get("Ime lokacije", ""),
                    "city": row.get("Grad / mesto", ""),
                    "leader": row.get("Ime lidera lokacije", ""),
                    "team": row.get("Tim", ""),
                }
            )
    return out


def main() -> int:
    payload = fetch(SOURCE)
    if not isinstance(payload, list) or not payload:
        print("unexpected response shape", file=sys.stderr)
        return 2
    page = payload[0]
    html = page["content"]["rendered"]
    locations = parse(html)
    if not locations:
        print("no locations parsed - aborting to avoid wiping data", file=sys.stderr)
        return 3
    doc = {
        "modified_gmt": page.get("modified_gmt"),
        "source": SOURCE,
        "count": len(locations),
        "locations": locations,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.name}: {len(locations)} locations · modified_gmt={doc['modified_gmt']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
