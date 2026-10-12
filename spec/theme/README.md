# Theme — Oxford Common Room (Historiologia)

Source of truth: `app/shared/theme.css` — update both together. Viewer pages
(`app/index.html`, `app/about.html`, `app/note/web/*.html`, live notes) carry
inline `:root` blocks that must stay identical to the shared tokens below.

- Fonts: `Cormorant Garamond` (display italic) + `Inter` (body, light 300) +
  `JetBrains Mono` (labels), via Google Fonts.
- Dark default (`--bg-void #0b0e14`, copper `#c9956c`, cyan `#4dd4c4`);
  `html[data-theme="light"]` parchment override (`--bg-void #f5f2ea`,
  copper `#9a7b3f`, cyan `#0e7c72`).
- Helpers: display italic headings, mono eyebrow/caption labels, card/panel
  surfaces, thin borders, copper focus. Ambient constellation canvas
  (copper/cyan, `prefers-reduced-motion` off), blurred sticky nav.
- Every page shares the same nav shell (`brand-lockup`: italic
  `Historiologia.` + `Laboratorium Maius Studiorum Historiologiae` sub-line,
  Corpus / Atlas / Chronology / Sources / About links, sun/moon icon toggle,
  `localStorage:historiologia-theme`) and footer
  (`Historiologia · HISTORIA · MEMORIA · UNUS INDEX` + the same links).
  (Live note `atlas.html` keeps its breadcrumb nav.)
