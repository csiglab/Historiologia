#!/usr/bin/env python3
"""
Note link checker (Historiologia note module).

Scans the notes corpus and note viewers for internal references and
reports broken ones with a proposed fix. Read-only by default; pass
--apply to rewrite files for deterministic fixes only (unique remaps
and depth-rule prefix fixes in markdown; raw HTML attributes, ambiguous
cases and JS fetch() calls are always left for manual handling).

Link classes:
  - viewer links `note.html?n=<path>`:
      * the prefix must resolve to the viewer (/note/web/note.html):
        bare in *.md and web/*.html, `../`*(depth+1)+`web/` in live HTML;
      * the target path must exist under app/note/data/.
  - catalog links `index.html?...dir=<dir>`:
      * same prefix rule against /note/web/index.html;
      * the dir must exist under data/.
  - `data-navdir="<dir>"` attributes: dir must exist under data/.
  - relative filesystem links: resolved file must exist.
  - absolute served paths (/note/..., /shared/..., ...): must exist under app/.

Skips: URL fragments, mailto:, http(s)://, data:, and any URL carrying
a query string other than note.html?n= / index.html?...dir= (those are
runtime routes such as /epistemica/?node=, not files), plus /note/api/*.

Rename-aware proposals come from REMAP_EXACT / REMAP_PREFIX (verified
moves), falling back to a unique same-basename match in the corpus
(case-insensitive). Breaks are tagged `recent` when the target still
exists in git HEAD (i.e. removed by the pending restructure) and
`legacy` otherwise.

Usage:
  python3 bin/check_note_links.py [--apply]
Exit status: 0 when no broken links remain, 1 otherwise.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit, parse_qs

REPO = Path(__file__).resolve().parent.parent
APP = REPO / "app"
NOTEDATA = APP / "note" / "data"
NOTEWEB = APP / "note" / "web"

# Verified moves: old corpus path -> new corpus path (relative to data/).
REMAP_EXACT = {}

# Prefix moves, tried in order; candidate must exist to apply.
REMAP_PREFIX = []

MD_LINK_RE = re.compile(r"!?\[([^\]]*)\]\(([^)\s]+)\)")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
SCRIPT_RE = re.compile(r"<script\b.*?</script\s*>", re.DOTALL | re.IGNORECASE)
FETCH_RE = re.compile(r"""fetch\(\s*['"]([^'"]+)['"]""")
ATTR_RE = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""")
NAVDIR_RE = re.compile(r"""data-navdir\s*=\s*["']([^"']*)["']""")
VIEWER_PAGES = ("note.html", "index.html")


class Issue:
    def __init__(self, src, line, kind, target, proposal, note=""):
        self.src = src
        self.line = line
        self.kind = kind
        self.target = target
        self.proposal = proposal  # (action, detail)
        self.note = note


def in_head(rel):
    """True if repo-relative path exists in git HEAD."""
    try:
        r = subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{rel}"],
            cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return r.returncode == 0
    except (OSError, ValueError):
        return False


def expected_prefix(path):
    """Prefix that must precede note.html/index.html to reach the viewer.

    Markdown is rendered inside the viewer itself, and web/*.html live
    next to it, so bare links are correct there. Live HTML under data/
    is served at /note/data/<dir>/ and must climb to /note/web/.
    """
    if path.suffix == ".md":
        return ""
    try:
        rel = path.parent.relative_to(NOTEDATA)
    except ValueError:
        return ""
    depth = 0 if str(rel) == "." else len(rel.parts)
    return "../" * (depth + 1) + "web/"


class Checker:
    def __init__(self):
        self.issues = []
        self.by_basename = {}
        self.head_cache = {}
        for p in list(NOTEDATA.rglob("*.md")) + list(NOTEDATA.rglob("*.html")):
            self.by_basename.setdefault(p.name, []).append(p)
            self.by_basename.setdefault(p.name.lower(), []).append(p)
        try:
            subprocess.run(["git", "rev-parse", "--git-dir"], cwd=REPO,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=True)
            self.have_git = True
        except (OSError, subprocess.CalledProcessError):
            self.have_git = False

    # -- helpers ------------------------------------------------------
    def data_exists(self, rel):
        return (NOTEDATA / rel).exists()

    def age(self, rel):
        """recent if the missing target still exists in HEAD, else legacy."""
        if rel not in self.head_cache:
            self.head_cache[rel] = self.have_git and in_head(f"app/note/data/{rel}")
        return "recent" if self.head_cache[rel] else "legacy"

    def propose_remap(self, target, exclude=None):
        """Return new_target (str), candidate list, or None."""
        if target in REMAP_EXACT:
            cand = REMAP_EXACT[target]
            if self.data_exists(cand):
                return cand
        for old_pre, new_pre in REMAP_PREFIX:
            if target.startswith(old_pre):
                cand = new_pre + target[len(old_pre):]
                if self.data_exists(cand):
                    return cand
        seen = set()
        cands = []
        for key in (Path(target).name, Path(target).name.lower()):
            for p in self.by_basename.get(key, []):
                c = p.relative_to(NOTEDATA).as_posix()
                if c != target and c != exclude and c not in seen:
                    seen.add(c)
                    cands.append(c)
        if len(cands) == 1:
            return cands[0]
        if cands:
            return cands
        return None

    def add_viewer_issue(self, src, line, raw_link, target):
        if self.data_exists(target):
            return
        prop = self.propose_remap(target)
        age = self.age(target)
        if isinstance(prop, str):
            self.issues.append(Issue(src, line, "viewer", target,
                                    ("remap", prop), age))
        elif isinstance(prop, list):
            self.issues.append(Issue(src, line, "viewer", target,
                                    ("ambiguous", prop), age))
        else:
            self.issues.append(Issue(src, line, "viewer", target,
                                    ("unlink", None), age))

    def add_dir_issue(self, src, line, raw_link, target, attr=False):
        target = unquote(target)
        if not target:
            return
        if (NOTEDATA / target).is_dir():
            return
        prop = self.propose_remap(target)
        if isinstance(prop, str) and (NOTEDATA / prop).is_dir():
            self.issues.append(Issue(src, line, "navdir" if attr else "dir",
                                    target, ("remap-dir", prop),
                                    self.age(target)))
            return
        parts = target.split("/")
        for i in range(len(parts) - 1, 0, -1):
            if (NOTEDATA / "/".join(parts[:i])).is_dir():
                self.issues.append(Issue(src, line, "navdir" if attr else "dir",
                                        target,
                                        ("remap-dir", "/".join(parts[:i])),
                                        self.age(target) + " (ancestor fallback)"))
                return
        self.issues.append(Issue(src, line, "navdir" if attr else "dir",
                                target, ("unlink", None), self.age(target)))

    # -- link classification ------------------------------------------
    def check_url(self, src, line, raw_link, base_dir, manual=False):
        url = raw_link.strip()
        if not url or url.startswith("#") or url.startswith("mailto:"):
            return
        if url.startswith(("http://", "https://", "data:")):
            return
        bare = url.split("#")[0]
        if "note.html?" in bare:
            qs = parse_qs(urlsplit("x?" + bare.rpartition("note.html?")[2]).query)
            for n in qs.get("n", []):
                self.add_viewer_issue(src, line, raw_link, unquote(n))
            return
        if "index.html?" in bare or bare.startswith("?"):
            qs = parse_qs(urlsplit("x?" + bare.rpartition("?")[2]).query)
            for d in qs.get("dir", []):
                self.add_dir_issue(src, line, raw_link, d)
            return
        if "?" in bare:
            return  # runtime deep link (e.g. /epistemica/?node=), not a file
        if bare.startswith("/note/api/"):
            return  # server API, not a file
        if bare.startswith("/"):
            if not (APP / bare.lstrip("/")).exists():
                self.add_abs_issue(src, line, raw_link, bare, manual)
            return
        # relative filesystem reference
        p = (base_dir / bare).resolve()
        for base in (NOTEDATA, APP, REPO):
            try:
                rel = p.relative_to(base)
                break
            except ValueError:
                continue
        else:
            return  # outside the repo
        if not (base / rel).exists():
            self.add_rel_issue(src, line, raw_link, base, rel, manual)

    def add_rel_issue(self, src, line, raw_link, base, rel, manual):
        rel_s = rel.as_posix()
        if manual:
            self.issues.append(Issue(src, line, "relative", raw_link,
                                    ("manual", "JS fetch() context; verify by hand"),
                                    self.age(rel_s)))
            return
        try:
            exclude = src.relative_to(NOTEDATA).as_posix()
        except ValueError:
            exclude = None
        prop = self.propose_remap(rel_s, exclude) if base == NOTEDATA else None
        if isinstance(prop, str):
            self.issues.append(Issue(src, line, "relative", raw_link,
                                    ("remap-rel", prop), self.age(rel_s)))
        elif isinstance(prop, list):
            self.issues.append(Issue(src, line, "relative", raw_link,
                                    ("ambiguous", prop), self.age(rel_s)))
        elif Path(rel_s).name.lower() == "index.html":
            self.issues.append(Issue(src, line, "relative", raw_link,
                                    ("manual", "suggest /note/web/index.html (catalog home)"),
                                    self.age(rel_s)))
        else:
            self.issues.append(Issue(src, line, "relative", raw_link,
                                    ("unlink", None), self.age(rel_s)))

    def add_abs_issue(self, src, line, raw_link, url, manual):
        if manual:
            self.issues.append(Issue(src, line, "absolute", raw_link,
                                    ("manual", "JS fetch() context; verify by hand"),
                                    "legacy"))
            return
        rel = url.lstrip("/")
        prop = None
        if rel.startswith("note/data/"):
            prop = self.propose_remap(rel[len("note/data/"):])
        if isinstance(prop, str):
            self.issues.append(Issue(src, line, "absolute", raw_link,
                                    ("remap-abs", "note/data/" + prop),
                                    "recent"))
        elif isinstance(prop, list):
            self.issues.append(Issue(src, line, "absolute", raw_link,
                                    ("ambiguous", prop), "legacy"))
        else:
            self.issues.append(Issue(src, line, "absolute", raw_link,
                                    ("unlink", None), "legacy"))

    def check_prefix(self, src, line, raw_link, exp):
        """Viewer/catalog hrefs must resolve to /note/web/<page>."""
        url = raw_link.strip().split("#")[0]
        for page in VIEWER_PAGES:
            if page + "?" in url or url.endswith(page):
                pre = url[:url.index(page)]
                if pre != exp:
                    self.issues.append(Issue(
                        src, line, "prefix", raw_link,
                        ("remap-prefix", exp + page), "depth rule"))
                return

    # -- scanning ------------------------------------------------------
    def scan_md(self, path):
        try:
            txt = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return
        # blank fences but keep offsets/newlines so line numbers stay exact
        body = FENCE_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), txt)
        for m in MD_LINK_RE.finditer(body):
            line = txt.count("\n", 0, m.start()) + 1
            self.check_url(path, line, m.group(2), path.parent, False)

    def scan_html(self, path):
        try:
            txt = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return
        exp = expected_prefix(path)
        for m in ATTR_RE.finditer(txt):
            line = txt.count("\n", 0, m.start()) + 1
            self.check_url(path, line, m.group(1), path.parent, False)
            self.check_prefix(path, line, m.group(1), exp)
        for m in NAVDIR_RE.finditer(txt):
            line = txt.count("\n", 0, m.start()) + 1
            if m.group(1):
                self.add_dir_issue(path, line, m.group(1), m.group(1), attr=True)
        for m in FETCH_RE.finditer(txt):
            line = txt.count("\n", 0, m.start()) + 1
            self.check_url(path, line, m.group(1), path.parent, True)
            self.check_prefix(path, line, m.group(1), exp)

    def run(self):
        for p in sorted(NOTEDATA.rglob("*.md")):
            self.scan_md(p)
        for p in sorted(NOTEWEB.glob("*.html")):
            self.scan_html(p)
        for p in sorted(NOTEDATA.rglob("*.html")):
            self.scan_html(p)
        return self.issues


def describe(issue):
    action, detail = issue.proposal
    src = issue.src.relative_to(REPO) if issue.src.is_absolute() else issue.src
    shown = issue.target
    if issue.kind == "viewer":
        shown = f"note.html?n={issue.target}"
    elif issue.kind in ("dir", "navdir"):
        shown = f"dir={issue.target}"
    head = f"{src}:{issue.line} [{issue.kind}/{issue.note}] {shown}"
    if action == "remap":
        return head + f"\n    -> remap to note.html?n={detail}"
    if action == "remap-dir":
        return head + f"\n    -> remap dir to {detail}"
    if action == "remap-rel":
        return head + f"\n    -> remap to {detail} (relative to source dir)"
    if action == "remap-abs":
        return head + f"\n    -> remap to /{detail}"
    if action == "remap-prefix":
        return head + f"\n    -> fix link prefix to {detail}"
    if action == "ambiguous":
        cands = ", ".join(detail[:6]) + (" ..." if len(detail) > 6 else "")
        return head + f"\n    -> ambiguous candidates (manual): {cands}"
    if action == "manual":
        return head + f"\n    -> manual: {detail}"
    if issue.src.suffix == ".html":
        return head + "\n    -> manual review (HTML attribute)"
    return head + "\n    -> dead end: unlink, keep display text"


def _sub_once(txt, old, new, prefix):
    """Replace `prefix+old` only where not followed by path chars."""
    pat = re.compile(re.escape(prefix + old) + r"(?![A-Za-z0-9/_\-.%])")
    return pat.subn(prefix + new, txt)


def apply_fix(issue):
    """Apply a deterministic fix. Returns True if applied."""
    action, detail = issue.proposal
    if action in ("ambiguous", "manual"):
        return False
    if issue.src.suffix == ".html" and action in ("unlink", "remap-rel",
                                                  "remap-abs"):
        return False  # never rewrite raw HTML attributes automatically
    try:
        txt = issue.src.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    if action == "remap":
        new_txt, n = _sub_once(txt, issue.target, detail, "note.html?n=")
        if n == 0:
            from urllib.parse import quote
            new_txt, n = _sub_once(txt, quote(issue.target, safe=""),
                                   quote(detail, safe=""), "note.html?n=")
        if n == 0:
            return False
    elif action == "remap-dir":
        new_txt, n = _sub_once(txt, issue.target, detail, "dir=")
        if n == 0:
            from urllib.parse import quote
            new_txt, n = _sub_once(txt, quote(issue.target, safe=""),
                                   detail, "dir=")
        if n == 0:
            return False
    elif action == "remap-prefix":
        old_pre = issue.target[:issue.target.index(
            "note.html" if "note.html" in issue.target else "index.html")]
        pat = re.compile(r"""((?:href|src)\s*=\s*["']|fetch\(\s*['"])"""
                         + re.escape(old_pre))
        new_pre = detail[:detail.index(
            "note.html" if "note.html" in detail else "index.html")]
        new_txt, n = pat.subn(r"\1" + new_pre, txt)
        if n == 0:
            return False
    elif action in ("remap-rel", "remap-abs"):
        if action == "remap-rel":
            base = NOTEDATA if (NOTEDATA / detail).exists() else APP
            new_rel = os.path.relpath(base / detail, issue.src.parent)
            pat = re.compile(r"\]\(" + re.escape(issue.target) + r"\)")
            new_txt, n = pat.subn(f"]({new_rel})", txt)
        else:
            pat = re.compile(re.escape(issue.target) + r"(?![A-Za-z0-9/_\-.%])")
            new_txt, n = pat.subn("/" + detail, txt)
        if n == 0:
            return False
    elif action == "unlink":
        t = re.escape(issue.target)
        pats = [
            r"!?\[([^\]]*)\]\(" + t + r"\)",
            r"!?\[([^\]]*)\]\(note\.html\?n=" + t + r"\)",
            r"!?\[([^\]]*)\]\([^)]*dir=" + t + r"(?![A-Za-z0-9/_\-.%])[^)]*\)",
        ]
        for p in pats:
            new_txt, n = re.compile(p).subn(r"\1", txt)
            if n:
                break
        else:
            return False
    else:
        return False
    issue.src.write_text(new_txt, encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true",
                    help="rewrite files where exactly one fix exists")
    args = ap.parse_args()

    checker = Checker()
    issues = checker.run()
    if not issues:
        print("note-links: clean, no broken internal references")
        return 0

    order = {"recent": 0, "legacy": 1}
    issues.sort(key=lambda i: (order.get(i.note.split(" ")[0], 2),
                               i.kind, str(i.src), i.line))
    fixed, remaining = 0, 0
    # longest targets first so `dir=social` never corrupts `dir=social/x`
    appliable = sorted(
        (i for i in issues if i.proposal[0] not in ("ambiguous", "manual")),
        key=lambda i: -len(i.target))
    for issue in issues:
        print(describe(issue))
        if args.apply and issue in appliable and apply_fix(issue):
            print("    [applied]")
            fixed += 1
        else:
            remaining += 1
    by_kind = {}
    for issue in issues:
        by_kind[issue.kind] = by_kind.get(issue.kind, 0) + 1
    kinds = ", ".join(f"{k}:{v}" for k, v in sorted(by_kind.items()))
    print(f"note-links: {len(issues)} broken ({kinds}), "
          f"{fixed} fixed, {remaining} remaining")
    return 1 if remaining else 0


if __name__ == "__main__":
    raise SystemExit(main())
