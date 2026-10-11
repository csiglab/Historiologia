# Guideline

Repository conventions for Historiologia. Binding for all contributors and agents.

## File Naming

> Semantic name, semantic path, semantic URL. Lowercase, ASCII.

Rules for files and directories we author:

- **Lowercase ASCII only** — no uppercase, spaces, parentheses, or diacritics.
- **Extensions lowercase** — `.md`, `.py`, `.html`, `.json`, `.png`.
- **Python/scripts** — `_` separates words (`build_note_index.py`, `check_note_links.py`, `app.py` is the server entry point).
- **Content slugs** — notes (`app/note/data/`) are named after their content,
  slugified by `bin/build_note_index.py:slugify_segment()` (NFKD to ASCII,
  lowercase, runs of non-alphanumerics to `-`; `æ→ae`, `ø→o`, `œ→oe`, `ß→ss`).
  The canonical human term lives inside the file (H1), never in the file name.
  Collisions get a `-2`, `-3`, … suffix.

### Exemptions

- **Canonical names** — `Makefile`, `README.md`, `AGENTS.md`, `LICENSE`, `.gitignore`.
- **This directory** — `guideline/README.md` (directory-entry convention shared
  with `spec/` readmes).
- **`app/note/web/vendor/`, `app/shared/vendor/`** — third-party code keeps its
  upstream name (`marked.min.js`, `katex/`).
- **`app/note/data/`** — corpus paths follow the kebab rule above (not `_`):
  `<section>/<kebab-case>.md`, top-level directory is the section. Generated
  `index.json` beside it is never hand-edited (rebuild with `make notes-index`).
  Live notes (`*.html`) follow the same path rule. Non-markdown assets beside
  notes are exempt from the filename rule, but directories always follow it.

## Paths & URLs

- Served root is `app/`. URLs mirror paths: `/` (hub), `/about.html`,
  `/note/web/` (catalog), `/note/web/note.html?n=<path>` (reader),
  `/note/data/<path>` (raw note / live page), `/shared/*` (theme, vendor, img).
- Read-only API: `/api/health`, `/api/search?q=`, `/api/index`.
- The viewer resolves `note.html?n=<path>` against `app/note/data/`.

## Commits & branches

```text
<type>(<optional scope>): <description>
```

Allowed `<type>`: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.
Scope, when used, is the concern: `feat(catalog): …`, `fix(links): …`,
`docs(about): …`.

- `main` is the default branch.
- Working branches: `<type>/<slug>` — lowercase ASCII with `-` word separation
  (e.g. `feat/note-atlas`, `fix/kebab-links`).
