# Historiologia

> *Laboratorium Maius Studiorum Historiologiae*: a collaborative research hub dedicated to the advanced study, preservation, and dissemination of Hispanic cultural, historical, and literary heritage.

Static-first notes hub. Hand-edited markdown in `app/note/data/` (sections:
`breviarium`, `castilla`, `portugal`, `russian-empire`, `soviet-union`, `meta`),
prebuilt JSON indexes, vanilla HTML/CSS/JS viewer with a shared nav/footer and
Oxford Common Room theme. No database, no build step, no npm. Thin stdlib-only
server `app.py` for local serving plus a read-only API; any static host serves
`app/` directly.

## Layout

- `app/index.html` — entry: hero, statistics, method, selected works, links to catalog/atlas/about
- `app/about.html` — mission, scope, method, contribution
- `app/note/web/` — catalog navigator (`index.html`) + reader (`note.html`)
- `app/note/data/` — corpus (`<section>/<kebab>.md`, live `*.html`, `index.json`, `changelog.json`)
- `app/note/data/meta/atlas.html` — live treemap atlas
- `bin/` — `build_note_index.py`, `build_search_index.py`,
  `build_landing_metrics.py`, `check_note_links.py` (stdlib only)
- `app.py` — thin server (static + read-only `/api/health|search|index`)

## Commands

```sh
make index          # rebuild all indexes (commit the result)
make check-links    # report broken internal links
make serve          # python app.py → http://127.0.0.1:8000/
```

Read `AGENTS.md` and `spec/note/authoring.md` before contributing notes.

## Todo 

- [ ]  [Ilustración Hispanoamericana](https://es.wikipedia.org/wiki/Ilustraci%C3%B3n_hispanoamericana)
- [ ]  Consevacion de Monarquias y Discursos Políticos - Sobre la Gran Consulta que el Consejo Hizo al Señor Rey Don Felipe Tercero. - https://play.google.com/books/reader?id=Isb9IYPMAykC&pg=GBS.PP8&hl=en
- [ ]  China
- [ ]  India

