# Notes corpus — authoring rules

> Corpus `readme.md` files are ordinary served notes: indexed, browsable, and
> searchable like any other note. The corpus lives at `app/note/data/`.

Long-form notes for Historiologia (`/note/web/` catalog, `/note/web/note.html?n=<path>`
reader). This directory is the **source of truth** — hand-edited markdown,
never machine-edited. After any change, rebuild the indexes and commit them:

```sh
make index
```

## Format

- A **note** is a markdown file (`*.md`), rendered on the fly by the viewer.
  No metadata required: the title comes from the first `# ` heading (else
  the filename); the top-level directory is the section. Optional tags go
  in `---` front matter (only `tags: [...]` is read, everything else ignored):
  ```md
  ---
  tags: [economia, fiscalidad]
  ---
  ```
- The tag **`unfinished`** is reserved: it marks a note that is not yet
  finished (stub, placeholder, or work in progress). Add it when the note
  is not done, remove it when it is. The catalog has a dedicated
  `unfinished` filter for this tag, and typing `unfinished`
  in the search box matches it like any other tag.
- A **live note** is a self-contained, hand-authored HTML page (`*.html`)
  with bespoke interactivity and its own scripts. Served as-is, never
  rendered through the viewer; the catalog still indexes it (title,
  headings, text) and links straight to the page with a `live` chip.
  No CDN libraries allowed in live notes.

## Naming convention

Note paths (directories and `.md`/`.html` filenames) must be:

- **ASCII** only — `a-z`, `0-9`, `-` (no accents, spaces, underscores, dots
  beyond the `.md`/`.html` extension)
- **lowercase** — never capitals
- **kebab-case** — words separated by `-`

Examples: `castilla/reformas-borbonicas.md`, `soviet-union/gulag.md`.

Canonical slug: NFKD-normalize to ASCII, lowercase, every run of
non-alphanumeric characters becomes a single `-`, trim leading/trailing `-`;
collisions get a `-2`, `-3`, … suffix.

`bin/build_note_index.py` validates every note path and tag, prints
warnings with the suggested normalized form for violations, and never
fails the build. Keep the output warning-free.

## Changelog

Per-file edit history for markdown notes lives in `changelog.json`
(beside the corpus, with `changelog.schema.json`): an array of
`{file_path, logs[]}` objects, `file_path` a corpus-relative `.md` path
(live HTML and other assets are out of scope). Each log is
`{date: YYYY-MM-DD, summary; optional kind}` (commit-type words like
`feat`/`fix`/`docs` suggested). Object key order follows the schema's
`properties` order.

Every change set touching `data/**/*.md` appends one log per touched
note, in the same commit. Validate with `python -m json.tool
app/note/data/changelog.json`. The changelog is a per-file narrative for
agents and readers; git log remains the source of truth.
