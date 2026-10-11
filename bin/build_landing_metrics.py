"""Build landing-page metrics for the Historiologia hub.

Reads the notes index, writes committed app/data/landing-metrics.json
(fetched by app/index.html; renders em-dash when absent).
Stdlib only. Never fails the build: missing inputs degrade to nulls.
"""
import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "app", "data", "landing-metrics.json")


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def main():
    notes = load_json(os.path.join(ROOT, "app", "note", "data", "index.json"))
    count = None
    words = None
    sections = {}
    tags = 0
    unfinished = 0
    if isinstance(notes, dict):
        notes_list = notes.get("notes", [])
        count = notes.get("count", len(notes_list))
        words = sum(n.get("words", 0) for n in notes_list if isinstance(n, dict))
        all_tags = set()
        for n in notes_list:
            if not isinstance(n, dict):
                continue
            s = n.get("section", "root")
            sections[s] = sections.get(s, 0) + 1
            for t in n.get("tags", []) or []:
                all_tags.add(t)
            if "unfinished" in (n.get("tags", []) or []):
                unfinished += 1
        tags = len(all_tags)
    payload = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": count,
        "words": words,
        "sections": sections,
        "tags": tags,
        "unfinished": unfinished,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    print(f"landing-metrics: notes={count} words={words} tags={tags} unfinished={unfinished} -> app/data/landing-metrics.json")


if __name__ == "__main__":
    main()
