"""Compare the chapter content of two index.html files section by section.

Canonical form per acc-item: tags, attributes (sorted), and text with whitespace
collapsed. Whitespace next to block-level tags is ignored. acc-item ids are ignored.

Usage: python -I tools/verify_roundtrip.py ORIGINAL.html BUILT.html [--show N]
Exit 0 when every section matches.
"""
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from htmltree import Node, parse, find_chapter_items, acc_num  # noqa: E402

BLOCK = {"div", "p", "ul", "ol", "li", "table", "thead", "tbody", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5",
         "section", "figure", "figcaption", "pre", "blockquote", "svg", "button", "label", "input", "circle", "img",
         "a_block"}


def canon(n, out):
    if isinstance(n, str):
        # Known fix: the original page has a mis-encoded chevron in 8.1 that the builder writes correctly.
        out.append(re.sub(r"\s+", " ", n.replace("â–¼", "▼")).replace("<", "&lt;"))
        return
    # Ignored on purpose: rel on links (the builder always adds rel="noopener noreferrer").
    attrs = sorted((k, v or "") for k, v in n.attrs if not (k == "rel" and n.tag == "a"))
    a = "".join(f' {k}="{v}"' for k, v in attrs)
    out.append(f"\n<{n.tag}{a}>")
    if "white-space:pre" in n.a.get("style", ""):
        # whitespace is visible here: compare text exactly (newlines made visible)
        out.append("".join(c if isinstance(c, str) else "<ELEM>" for c in n.children).replace("\n", "⏎").replace(" ", "·"))
        out.append(f"</{n.tag}>\n")
        return
    for c in n.children:
        canon(c, out)
    out.append(f"</{n.tag}>\n")


def norm(item):
    out = []
    canon(item, out)
    s = "".join(out)
    tags = "|".join(BLOCK)
    s = re.sub(rf"\s*(</?(?:{tags})\b[^>]*>)\s*", r"\n\1\n", s)
    s = re.sub(r" {2,}", " ", s)
    return [l for l in (x.strip() for x in s.split("\n")) if l]


def sections(path):
    root = parse(open(path, encoding="utf-8").read().replace("\r\n", "\n"))
    res = {}
    for cid, acc in find_chapter_items(root).items():
        if cid == "dashboard":
            continue
        for item in acc.elems():
            res[acc_num(item)] = norm(item)
    return res


PAGES = ["rutiner", "workflows", "edittips", "editassets", "grade", "ai", "prosjekter", "gear"]


def outside_accordions(src):
    """The page with every chapter accordion's inner HTML removed (must be byte-identical)."""
    for pid in PAGES:
        p = src.index(f'<div id="{pid}" class="page">')
        start = src.index('<div class="accordion">', p) + len('<div class="accordion">')
        depth = 1
        for m in re.compile(r"<div\b|</div>").finditer(src, start):
            depth += -1 if m.group() == "</div>" else 1
            if depth == 0:
                src = src[:start] + src[m.start():]
                break
    return src


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ra, rb = (open(p, encoding="utf-8").read() for p in sys.argv[1:3])
    if outside_accordions(ra).replace("\r\n", "\n").strip() != outside_accordions(rb).replace("\r\n", "\n").strip():
        print("Page outside the chapter accordions differs")
        sys.exit(1)
    a, b = sections(sys.argv[1]), sections(sys.argv[2])
    show = int(sys.argv[sys.argv.index("--show") + 1]) if "--show" in sys.argv else 3
    bad = 0
    for k in a:
        if k not in b:
            print(f"MISSING {k}")
            bad += 1
            continue
        if a[k] != b[k]:
            bad += 1
            if bad <= show:
                print(f"=== {k} differs")
                for l in list(difflib.unified_diff(a[k], b[k], lineterm="", n=1))[2:40]:
                    print(l[:220])
            else:
                print(f"=== {k} differs")
    extra = set(b) - set(a)
    for k in sorted(extra):
        print(f"EXTRA {k}")
    print(f"{len(a) - bad}/{len(a)} sections identical")
    sys.exit(1 if bad or extra else 0)


if __name__ == "__main__":
    main()
