# AGENTS.md

## Purpose

Instructions for AI agents working in this repository. Follow the conventions below.
`guideline/` (file naming, paths/URLs, commits) is binding. Authoring rules for
notes live in `spec/note/authoring.md`.

## Project Context

Historiologia (*Laboratorium Maius Studiorum Historiologiae*) is a collaborative
research hub for Hispanic cultural, historical, and literary heritage, with
comparative world-history notes. Static-first: hand-edited markdown notes,
prebuilt JSON indexes, vanilla HTML/CSS/JS viewer. **No database, no build step,
no npm.** One thin server (`app.py`, stdlib only) for local serving plus a
read-only API; any static host serves `app/` directly.

### Objectives

- Keep every note reachable: catalog (navigator), atlas, hub search, reader.
- Keep every page sharing the same nav bar, footer, theme and typography
  (Oxford Common Room tokens in `app/shared/theme.css`).
- Two note kinds only: `.md` notes (rendered on the fly) and live `.html`
  notes (bespoke interactivity, served as-is).

### Scope

- In: `app/` (hub, about, note viewer, corpus), `bin/` (index builders,
  link checker), `app.py`, `guideline/`, `spec/`.
- Out: databases, backends, npm/vite toolchains, CDN libraries in live notes.

## Repository Structure

| Path | Role |
|------|------|
| `app/index.html` | Entry/registry: hero, statistics, method, selected works, links to catalog/atlas/about |
| `app/about.html` | About page: mission, scope, method, contribution |
| `app/note/web/` | Viewer: `index.html` (catalog/navigator), `note.html` (reader), `notes.css`, `vendor/marked.min.js` |
| `app/note/data/` | Corpus: hand-edited `<section>/<kebab>.md` + live `*.html`, generated `index.json`, hand-edited `changelog.json` |
| `app/note/data/meta/atlas.html` | Live note atlas (treemap by count/words) |
| `app/shared/` | `theme.css` (Oxford Common Room tokens), `vendor/katex/`, `img/` |
| `app/data/` | Generated `search-index.json`, `landing-metrics.json` (hub search + metrics) |
| `bin/` | `build_note_index.py`, `build_search_index.py`, `build_landing_metrics.py`, `check_note_links.py` (stdlib only) |
| `app.py` | Thin server: static `app/` + read-only `/api/health|search|index`; `503` on `/note/api/pins` (catalog hides pin UI) |
| `Dockerfile`, `docker-compose.yml` | Container: `python:3.12-slim` + `app.py` + `app/`; port from `.env` (`PORT=8022`) |
| `.env` (git-ignored, see `.env.example`) | Runtime env: `PORT`, `HOST` |
| `spec/note/authoring.md` | Canonical note-authoring rules |
| `guideline/README.md` | Naming, paths/URLs, commits, branches |

Sections (keep as-is): `breviarium/`, `castilla/`, `portugal/`,
`russian-empire/`, `soviet-union/`, plus `meta/` (atlas, inbox).

## Agent Operating Principles

### Understand Before Changing

Read `spec/note/authoring.md` and the relevant page before editing. The viewer
pages are large single-file apps with no build step — make surgical edits and
keep the inline `:root` tokens identical to `app/shared/theme.css`.

### Prefer Existing Solutions

- Reuse the tokens in `app/shared/theme.css`; never hardcode colors.
- Reuse the builder slug rule (`bin/build_note_index.py:slugify_segment()`);
  never run an underscore slugifier on the corpus.
- Copy the nav/footer/ambient-canvas/theme-toggle snippet when adding a page.

### Preserve Invariants

- `app/note/data/` holds the hand-edited corpus; `app/note/data/index.json`,
  `app/data/search-index.json`, `app/data/landing-metrics.json` are generated —
  never hand-edit them (run `make index` and commit the result).
- Note paths are kebab-case ASCII (`spec/note/authoring.md`); the builder warns
  on violations — keep the output warning-free.
- Per-file edit history lives in `app/note/data/changelog.json` (array of
  `{file_path, logs[]}`, key order follows `changelog.schema.json`). Every
  change set touching `app/note/data/**/*.md` appends one log per file
  (`{date: YYYY-MM-DD, summary; optional kind}`) in the same commit.
- Tags are optional `--- tags: [...]` front matter; `unfinished` is reserved
  for stubs and feeds the catalog filter.
- Reference links are bare `[Name](target)`; prose glosses go around the link,
  never trailing parentheticals after it (new links; legacy left as-is).
- Live notes (`*.html`) are self-contained, no CDN libraries; the catalog
  indexes them (title/headings/text) and links straight to the page with a
  `live` chip.
- Viewer + catalog must stay free of cross-repo residue (no foreign brands).
- Static-only: no database writes, no server-side state. `.env` holds only
  runtime `PORT`/`HOST` (git-ignored, see `.env.example`).

### Keep Work Scoped

One concern per change set; commit style
`feat|fix|docs|style|refactor|test|chore(scope): summary`, branches
`<type>/<slug>` (see `guideline/README.md`).

## Development Environment

Requirements: Python 3.12+ (stdlib only). Docker optional (container).

```sh
make index          # rebuild all indexes (commit the result)
make check-links    # report broken internal links
make serve          # python app.py → http://127.0.0.1:8000/ (PORT/HOST env override)
make docker-up      # container on http://127.0.0.1:8022/ (PORT from .env)
make update         # rebuild indexes + cp notes/indexes into the running container (no rebuild)
```

## Verification

Before declaring done: `make index` (warning-free), `make check-links` (clean),
`python app.py` and check every touched route returns 200
(`/`, `/about.html`, `/note/web/`, `/note/web/note.html?n=<path>`,
`/note/data/meta/atlas.html`); `curl /api/health` returns JSON. There is no
test suite; the index build + link check + route smoke test are the gate.
