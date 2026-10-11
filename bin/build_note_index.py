#!/usr/bin/env python3
"""
Notes index builder (Naturgnosis note module).

Scans app/note/data/** for notes — markdown (*.md, kind "note") and
self-contained HTML live notes (*.html, kind "live") — and emits
app/note/data/index.json, the search corpus for the notes catalog
(/note/). The generated index.json sits beside the corpus and is skipped
by the scan (only *.md/*.html match). Stdlib only. Ported from
Epistecnica's src/note/bin/index.py; machinery only, no content carried over.

For each note it extracts: path (relative to data/), title (markdown:
first "# " heading; html: <title>, else first <h1>; fallback: the
filename), top-level section (first path component), h2/h3 headings,
tags (optional `tags: [...]` front matter, same `---` style as
Epistecnica's note system), lowercased plain text, and word count.
Paths and tags are validated against the naming convention (see
spec/note/authoring.md); violations print as warnings and never fail
the build. The canonical slug form is `slugify_segment()` (Epistecnica
parity: NFKD to ASCII, lowercase, runs of non-alphanumerics to `-`).

Usage: python3 bin/build_note_index.py
"""

import json
import re
import sys
import unicodedata
from datetime import date
from html import unescape
from pathlib import Path

NOTE = Path(__file__).resolve().parent.parent
APP = NOTE / "app" / "note"
NOTES = APP / "data"
OUT = APP / "data" / "index.json"

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
TAGS_RE = re.compile(r"^tags:\s*\[(.*)\]\s*$")
LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
FENCE_RE = re.compile(r"```[^\n]*\n|```")
HTML_BLOCK_RE = re.compile(r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
HTML_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
HTML_H_RE = re.compile(r"<h([1-6])[^>]*>(.*?)</h\1>", re.IGNORECASE | re.DOTALL)
HTML_TAG_RE = re.compile(r"<[^>]+>")


# æ/ø/œ/ß have no NFKD decomposition (they would vanish); transliterate first.
TRANSLITERATE = {
    "æ": "ae", "ø": "o", "œ": "oe", "ß": "ss", "đ": "d",
    "ł": "l", "þ": "th", "ð": "d", "ı": "i", "ŋ": "n",
}


def slugify_segment(raw: str) -> str:
    """Canonical note slug for one path segment (Epistecnica parity).

    Lowercase, fixed transliterations (æ/ø/œ/ß…), NFKD-normalize to
    ASCII, every run of non-alphanumeric characters becomes a single
    `-`, trim leading/trailing `-`. Mirrors the viewer/validator rule
    (NAME_RE); `bin/slugify_files.py` must not be used on notes (it
    emits `_`).
    """
    text = raw.lower()
    for src, dst in TRANSLITERATE.items():
        text = text.replace(src, dst)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def normalize_rel(rel: Path) -> str:
    """Suggested canonical path for a note (kebab segments, lower suffix)."""
    *dirs, filename = rel.parts
    stem, dot, ext = filename.rpartition(".")
    if not dot:  # no extension (e.g. a directory preview) — slugify whole
        return "/".join([slugify_segment(d) for d in rel.parts])
    segs = [slugify_segment(d) for d in dirs] + [slugify_segment(stem)]
    return "/".join(segs) + dot + ext.lower()


def check_name(rel: Path, warnings: list):
    for part in rel.parts[:-1]:
        if not NAME_RE.match(part):
            warnings.append(f"{rel.as_posix()} (directory '{part}' -> '{slugify_segment(part)}')")
            return
    filename = rel.parts[-1]
    stem, dot, ext = filename.rpartition(".")
    if not NAME_RE.match(stem):
        warnings.append(f"{rel.as_posix()} (filename -> '{normalize_rel(rel)}')")


def plain_text(md: str) -> str:
    md = FENCE_RE.sub("\n", md)
    md = LINK_RE.sub(r"\1", md)
    lines = []
    for line in md.splitlines():
        line = HEADING_RE.sub(r"\2", line)
        line = re.sub(r"[*_>`|]", " ", line)
        lines.append(line)
    return re.sub(r"\s+", " ", "\n".join(lines)).strip().lower()


def parse_tags(md: str, rel: Path, warnings: list) -> tuple:
    """Split optional `---` front matter off; return (body, tags).

    Only the `tags: [...]` line is read; anything else in the fence is
    ignored. Invalid tags warn and are dropped. (Epistecnica parity.)
    """
    tags = []
    fm = FRONT_MATTER_RE.match(md)
    if fm:
        for line in fm.group(1).splitlines():
            m = TAGS_RE.match(line.strip())
            if m:
                for raw in m.group(1).split(","):
                    tag = raw.strip().strip("'\"").lower()
                    if not tag:
                        continue
                    if NAME_RE.match(tag):
                        if tag not in tags:
                            tags.append(tag)
                    else:
                        warnings.append(f"{rel.as_posix()} (tag '{tag}')")
        md = md[fm.end():]
    return md, tags


def parse(path: Path, rel: Path, warnings: list) -> dict:
    md = path.read_text(encoding="utf-8", errors="replace")
    md, tags = parse_tags(md, rel, warnings)
    title = None
    headings = []
    for line in md.splitlines():
        m = HEADING_RE.match(line)
        if not m:
            continue
        level, text = len(m.group(1)), m.group(2).strip()
        if level == 1 and title is None:
            title = text
        elif level >= 2:
            headings.append({"level": level, "text": text})
    if title is None:
        title = rel.stem.replace("-", " ")
    text = plain_text(md)
    return entry(rel, title, headings, text, tags, kind="note")


def parse_html(path: Path, rel: Path, warnings: list) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    body = HTML_BLOCK_RE.sub(" ", raw)

    title = None
    m = HTML_TITLE_RE.search(body)
    if m:
        title = HTML_TAG_RE.sub(" ", m.group(1)).strip()
    headings = []
    for hm in HTML_H_RE.finditer(body):
        level = int(hm.group(1))
        text = unescape(HTML_TAG_RE.sub(" ", hm.group(2))).strip()
        text = re.sub(r"\s+", " ", text)
        if not text:
            continue
        if level == 1 and title is None:
            title = text
        elif level >= 2:
            headings.append({"level": level, "text": text})
    if title is None:
        title = rel.stem.replace("-", " ")

    text = unescape(HTML_TAG_RE.sub(" ", body))
    text = re.sub(r"\s+", " ", text).strip().lower()
    return entry(rel, title, headings, text, [], kind="live")


def entry(rel: Path, title: str, headings: list, text: str, tags: list, kind: str) -> dict:
    parts = rel.parts
    section = parts[0] if len(parts) > 1 else "root"
    return {
        "path": rel.as_posix(),
        "title": title,
        "section": section,
        "kind": kind,
        "tags": tags,
        "headings": headings,
        "text": text,
        "words": len(text.split()),
    }


def main() -> int:
    if not NOTES.is_dir():
        print(f"ERROR: notes directory not found: {NOTES}", file=sys.stderr)
        return 1

    warnings: list = []
    notes: list = []
    for pattern, parser in (("*.md", parse), ("*.html", parse_html)):
        for path in sorted(NOTES.rglob(pattern)):
            rel = path.relative_to(NOTES)
            if rel.parts[:2] == ("meta", "graph"):  # relocated app viewer, not notes
                continue
            check_name(rel, warnings)
            notes.append(parser(path, rel, warnings))

    sections: dict = {}
    for n in notes:
        sections[n["section"]] = sections.get(n["section"], 0) + 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated": date.today().isoformat(),
        "count": len(notes),
        "sections": sections,
        "notes": notes,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    kb = OUT.stat().st_size / 1024
    tagged = sum(1 for n in notes if n["tags"])
    print(f"notes-index: {len(notes)} notes ({tagged} tagged), {sum(n['words'] for n in notes)} words -> {OUT.relative_to(NOTE)} ({kb:.0f} KB)")
    for section, count in sorted(sections.items()):
        print(f"  {section}: {count}")
    if warnings:
        print(f"naming warnings: {len(warnings)} (see spec/note/authoring.md)")
        for w in warnings:
            print(f"  ! {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
