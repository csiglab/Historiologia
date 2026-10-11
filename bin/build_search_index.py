#!/usr/bin/env python3
"""Universal search index builder (Historiologia hub).

Reads app/note/data/index.json and emits a trimmed
app/data/search-index.json consumed by the hub search box (/).
Stdlib only. Notes-only: no graph/QA/glossarium inputs.

Usage: python3 bin/build_search_index.py
"""

import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "app" / "data" / "search-index.json"

EXCERPT_LEN = 500


def excerpt(text: str) -> str:
    text = " ".join((text or "").split())
    if len(text) <= EXCERPT_LEN:
        return text
    cut = text[:EXCERPT_LEN]
    space = cut.rfind(" ")
    return (cut[:space] if space > 40 else cut).rstrip() + " …"


def main() -> int:
    src = REPO / "app" / "note" / "data" / "index.json"
    if not src.is_file():
        print(f"ERROR: missing notes index {src} — run: make notes-index", file=sys.stderr)
        return 1
    idx = json.loads(src.read_text(encoding="utf-8"))
    entries = []
    for n in idx.get("notes", []):
        entries.append(
            {
                "surface": "note",
                "kind": n.get("kind", "note"),
                "type": n.get("section", ""),
                "title": n.get("title", ""),
                "path": n.get("path", ""),
                "tags": n.get("tags", []),
                "excerpt": excerpt(n.get("text", "")),
            }
        )
    counts = {"note": len(entries)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {"generated": date.today().isoformat(), "counts": counts, "entries": entries},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    kb = OUT.stat().st_size / 1024
    print(f"search-index: {len(entries)} entries -> app/data/search-index.json ({kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
