"""One-time migration: index.html -> rich markdown (bibelen/*.md format).

Known page components become readable markdown; anything else is kept as raw
HTML inside the markdown so build_from_md.js can reproduce it exactly.
Interactive widgets (svg, inputs, buttons, scripts) go to partials/<name>.html.

Usage: python -I tools/md_migrate.py index.html OUT_DIR
Writes OUT_DIR/<chapter>.body.md per chapter and OUT_DIR/partials/*.html,
plus a report of raw-HTML usage on stderr.
"""
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from htmltree import Node, parse, text, walk, serialize, attr_str, find_chapter_items, acc_num  # noqa: E402

BASE = "https://regularivar.github.io/NesheiMedia-guide/"
CHAPTERS = [("rutiner", "01"), ("workflows", "02"), ("edittips", "03"), ("editassets", "04"),
            ("grade", "05"), ("ai", "06"), ("prosjekter", "07"), ("gear", "08")]
CALLOUT = {"blue": "info", "orange": "warning", "green": "tip", "red": "danger"}
PALETTE = ["#4f8ef7", "#34d399", "#fb923c", "#c084fc", "#22d3ee", "#f472b6", "#fbbf24", "#a3e635"]
FIG_STYLE = "margin:0;background:rgba(255,255,255,0.03);border:1px solid var(--border);border-radius:12px;overflow:hidden"
FIG_IMG = [("loading", "lazy"), ("style", "width:100%;display:block")]
CAP_STYLE = "padding:10px 12px;color:var(--text2);font-family:var(--mono);font-size:11px"
BLOCK = {"div", "p", "ul", "ol", "li", "table", "thead", "tbody", "tr", "td", "th", "h1", "h2", "h3", "h4",
         "h5", "section", "figure", "figcaption", "pre", "blockquote", "svg", "label", "button"}
WIDGET = {"svg", "input", "button", "script", "label", "select", "textarea"}

report = Counter()
partials = {}


# ---------- helpers ----------

def is_symbol_token(s):
    return bool(s) and not re.search(r"[A-Za-z0-9ÆØÅæøå\s]", s)


def rule_class(icon):
    if icon == "✓":
        return "ok"
    if icon in ("⚠", "⚠️", "!", "✕"):
        return "warn"
    return "info"


def has_block(n):
    return any(isinstance(c, Node) and (c.tag in BLOCK or has_block(c)) for c in n.children)


def has_widget(n):
    return any(True for _ in walk(n, lambda x: x.tag in WIDGET)) or n.tag in WIDGET


def esc_text(s, line_start=False):
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\\(?=[!-/:-@\[-`{-~]|$)", r"\\\\", s)      # backslash before punctuation or a following tag
    s = s.replace("*", r"\*").replace("`", r"\`").replace("[", r"\[").replace("]", r"\]")
    s = re.sub(r"<(?=[A-Za-z/!])", r"\\<", s)
    s = s.replace("&", "&amp;") if re.search(r"&[A-Za-z#]", s) else s
    return s


def guard_line_start(s):
    # Keep a paragraph from being parsed as another block type.
    s = s.replace(" :: ", " \\:: ")              # not a param row
    if s.startswith("▶ ["):
        raise SystemExit("Paragraph looks like a YouTube card: " + s[:80])
    if re.match(r"(#|>|- |\* |\+ |\d+\. |\||<!--|---|```)", s):
        return "\\" + s if not s.startswith("<") else s
    return s


def img_src(src):
    return src if src.startswith(("http:", "https:", "data:")) else BASE + src.lstrip("./")


# ---------- inline ----------

def inline(n):
    if isinstance(n, str):
        return esc_text(n)
    t, a = n.tag, n.a
    kids = "".join(inline(c) for c in n.children)
    if t == "strong" and not n.attrs and kids.strip() and kids == kids.strip():
        return f"**{kids}**"
    if t == "em" and not n.attrs and kids.strip() and kids == kids.strip():
        return f"*{kids}*"
    if t == "code" and not n.attrs and not n.elems():
        s = text(n)
        if s and "`" not in s and s == s.strip():
            # ``x`` = plain <code> even when x looks like a drive letter or UNC path
            return f"``{s}``" if is_drive(s) or is_unc(s) else f"`{s}`"
    if t == "span" and n.attrs == [("class", "drive-badge")] and not n.elems() and is_drive(text(n)):
        return f"`{text(n)}`"
    if t == "span" and n.attrs == [("class", "path")] and not n.elems() and is_unc(text(n)) and "`" not in text(n):
        return f"`{text(n)}`"
    if t == "a" and [k for k, _ in n.attrs if k != "rel"] == ["href", "target"] and a["target"] == "_blank" \
            and a.get("rel", "noopener noreferrer") == "noopener noreferrer" \
            and not n.elems() and text(n).strip() and ")" not in a["href"] and " " not in a["href"]:
        return f"[{kids}]({a['href']})"
    if t == "img" and [k for k, _ in n.attrs] == ["src", "alt"] and " " not in a["src"] and ")" not in a["src"]:
        return f"![{esc_text(a['alt'])}]({img_src(a['src'])})"
    if t == "br" and not n.attrs:
        return "<br>"
    # raw inline
    report["inline:" + t + ("." + ".".join(n.cls) if n.cls else "")] += 1
    if t in ("img", "br", "input"):
        return f"<{t}{attr_str(n)}>"
    return f"<{t}{attr_str(n)}>{kids}</{t}>"


def is_drive(s):
    return bool(re.fullmatch(r"[A-Z]:\\", s))


def is_unc(s):
    return s.startswith("\\\\")


def inline_run(nodes):
    s = "".join(inline(c) for c in nodes)
    s = re.sub(r"[ \t]+", " ", s).strip()
    return guard_line_start(s)


# ---------- blocks ----------

def quote(md):
    return "\n".join(("> " + l) if l else ">" for l in md.split("\n"))


def blocks(children, ctx=""):
    """Convert a list of sibling nodes to a list of markdown blocks."""
    out, run = [], []

    def flush():
        if run:
            s = inline_run(run)
            if s:
                out.append(s)
            run.clear()

    for c in children:
        if isinstance(c, str) or (c.tag not in BLOCK and not has_block(c)):
            run.append(c)
            continue
        flush()
        out.extend(block(c, ctx))
    flush()
    return out


def partial(n, ctx):
    k = 1
    while f"{ctx}-{k}" in partials:
        k += 1
    name = f"{ctx}-{k}"
    partials[name] = serialize(n)
    report["partial"] += 1
    return [f"<!-- html:{name} -->"]


def raw_block(n, ctx):
    if has_widget(n):
        return partial(n, ctx)
    report["block:" + n.tag + ("." + ".".join(n.cls) if n.cls else "")] += 1
    if not has_block(n):
        return [f"<{n.tag}{attr_str(n)}>{inline_run(n.children)}</{n.tag}>"]
    inner = blocks(n.children, ctx)
    return [f"<{n.tag}{attr_str(n)}>"] + inner + [f"</{n.tag}>"]


def sub_items(acc, ctx, mark):
    """sub-accordion -> [mark + title, blocks...] per item."""
    out = []
    for sub in acc.elems():
        btn, sc = sub.elems()
        if sub.attrs != [("class", "sub-acc-item")] or btn.attrs != [("class", "sub-acc-trigger"), ("onclick", "toggleSubAcc(this)")] \
                or sc.attrs != [("class", "sub-acc-content")]:
            raise SystemExit(f"Unexpected sub-accordion markup in {ctx}")
        st = [s for s in btn.elems() if not s.attrs][0]
        out.append(mark + inline_run(st.children))
        out.extend(blocks(sc.children, ctx))
    return out


def block(n, ctx):
    t, cls, a = n.tag, n.cls, n.a
    if n.attrs == [("class", "sub-accordion")]:
        # nested tabs inside a ### tab
        inner = sub_items(n, ctx, "##### ")
        if sum(x.startswith("##### ") for x in inner) != len(n.elems()):   # a third level would add more
            raise SystemExit(f"Tabs nested more than two levels in {ctx}")
        return inner + ["<!-- /undertabs -->"]
    if has_widget(n) and not ("callout" in cls or "cards" in cls):
        # callouts/cards may hold an inline button; everything else with widgets is a partial
        if n.tag in WIDGET or any(True for _ in walk(n, lambda x: x.tag in ("svg", "input", "script"))):
            return partial(n, ctx)

    if t == "div" and "white-space:pre" in a.get("style", ""):
        r = pre_block(n)
        if r is not None:
            return [r]
        return partial(n, ctx)

    if n.attrs == [("class", "section-sub-header")] and not has_block(n):
        return ["#### " + inline_run(n.children)]

    if len(cls) == 2 and cls[0] == "callout" and cls[1] in CALLOUT and len(n.attrs) == 1:
        el = n.elems()
        if len(el) == 2 and el[0].attrs == [("class", "callout-icon")] and el[1].attrs == [("class", "callout-text")] \
                and not [c for c in n.children if isinstance(c, str) and c.strip()]:
            icon = text(el[0]).strip()
            body = callout_body(el[1], ctx)
            if body is not None and " " not in icon:
                return [f"> [!{CALLOUT[cls[1]]}] {icon}".rstrip() + ("\n" + quote(body) if body else "")]

    if n.attrs == [("class", "rules")]:
        r = rules(n)
        if r is not None:
            return [r]

    if n.attrs == [("class", "steps")]:
        r = steps(n)
        if r is not None:
            return [r]

    if n.attrs == [("class", "cards")]:
        r = cards(n, ctx)
        if r is not None:
            return [r]

    if n.attrs == [("class", "nb-card")]:
        el = n.elems()
        if len(el) == 2 and el[0].attrs == [("class", "nb-header")] and el[1].attrs == [("class", "nb-body")] \
                and not has_block(el[0]):
            body = "\n\n".join(blocks(el[1].children, ctx))
            return ["> [!note] " + inline_run(el[0].children) + ("\n" + quote(body) if body else "")]

    if n.attrs == [("class", "table-wrap")]:
        r = table(n)
        if r is not None:
            return [r]

    if t == "figure":
        r = figure(n)
        if r is not None:
            return [r]

    if t == "div" and n.attrs and n.attrs[0][0] == "style" and len(n.attrs) == 1 \
            and n.elems() and all(e.tag == "figure" and figure(e) for e in n.elems()) \
            and not [c for c in n.children if isinstance(c, str) and c.strip()]:
        m = re.fullmatch(r"display:grid;grid-template-columns:repeat\(auto-(fit|fill),minmax\((\d+)px,1fr\)\);gap:(\d+)px;margin-bottom:(\d+)px", a["style"])
        figs = "\n".join(figure(e) for e in n.elems())
        if m:
            head = f"> [!gallery] {m.group(1)} {m.group(2)} {m.group(3)} {m.group(4)}"
        else:
            head = f'> [!gallery] <!-- style="{a["style"]}" -->'
        return [head + "\n" + quote(figs)]

    if t == "img" and not n.elems():
        return [inline(n)]

    if t == "ul":
        r = plain_list(n)
        if r is not None:
            return [r]

    if t == "a" and "yt-card" in cls:
        r = yt_card(n)
        if r is not None:
            return [r]

    if n.attrs == [("class", "param-row")]:
        el = n.elems()
        if len(el) == 2 and el[0].attrs == [("class", "param-name")] and el[1].attrs == [("class", "param-val")] \
                and not [c for c in n.children if isinstance(c, str) and c.strip()]:
            k, v = inline_run(el[0].children), inline_run(el[1].children)
            if k and v and " :: " not in k + v and not k.startswith(("▶", "<", "\\")):
                return [f"{k} :: {v}"]

    return raw_block(n, ctx)


PRE_KODE = ("background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:16px 20px;margin-bottom:20px;"
            "font-family:var(--mono);font-size:12px;color:var(--text2);line-height:1.8;white-space:pre")
PRE_PROMPT = ("background:rgba(0,0,0,0.3);border:1px solid var(--border);border-radius:8px;padding:16px;font-family:var(--mono);"
              "font-size:11px;color:var(--text2);white-space:pre-wrap;line-height:1.7;{}margin-bottom:8px")


def pre_block(n):
    """Whitespace-preserving div -> fenced block: ```kode or ```prompt [max-height px]."""
    if len(n.attrs) != 1 or n.elems():
        return None
    st, body = n.a["style"], text(n)
    if st == PRE_KODE:
        info = "kode"
    elif st == PRE_PROMPT.format(""):
        info = "prompt"
    else:
        m = re.fullmatch(re.escape(PRE_PROMPT).replace(r"\{\}", r"max\-height:(\d+)px;overflow\-y:auto;"), st)
        if not m:
            return None
        info = f"prompt {m.group(1)}"
    # Lines starting with '#' would be read as section/sub-tab headings by the builder.
    if "```" in body or body != body.strip("\n") or not body or re.search(r"^(#|<!--)", body, re.M):
        return None
    return f"```{info}\n{body}\n```"


YT_RE = re.compile(r"https://www\.youtube\.com/watch\?v=([\w-]+)(?:&[^\s()]*)?")


def yt_card(n):
    """<a class="yt-card"> with thumb, badge, title and meta -> '▶ [title](url) – meta'."""
    if n.attrs != [("href", n.a["href"]), ("target", "_blank"), ("rel", "noopener noreferrer"), ("class", "yt-card")]:
        return None
    m = YT_RE.fullmatch(n.a["href"])
    el = n.elems()
    if not m or len(el) != 2 or el[0].attrs != [("class", "yt-thumb")] or el[1].attrs != [("class", "yt-info")]:
        return None
    th = el[0].elems()
    if len(th) != 3 or th[0].attrs != [("src", f"https://img.youtube.com/vi/{m.group(1)}/mqdefault.jpg")] \
            or th[1].attrs != [("class", "yt-badge")] or text(th[1]) != "▶ VIDEO" \
            or th[2].attrs != [("class", "yt-ext")] or text(th[2]) != "↗ YouTube":
        return None
    info = el[1].elems()
    if [e.attrs for e in info] != [[("class", "yt-title")], [("class", "yt-meta")]] or any(has_block(e) for e in info):
        return None
    title, meta = inline_run(info[0].children), inline_run(info[1].children)
    if not title or "](" in title:
        return None
    return f"▶ [{title}]({n.a['href']})" + (f" – {meta}" if meta else "")


def callout_body(ct, ctx):
    """callout-text content: inline paragraphs separated by <br><br>, or blocks."""
    if has_block(ct):
        return "\n\n".join(blocks(ct.children, ctx))
    s = inline_run(ct.children)
    s = re.sub(r"\s*<br><br>\s*", "\n\n", s)
    s = re.sub(r"\s*<br>\s*", "<br>", s)
    return "\n".join(guard_line_start(x) if x else x for x in s.split("\n"))


def rules(n):
    items = []
    for r in n.elems():
        if len(r.cls) != 2 or r.cls[0] != "rule" or len(r.attrs) != 1:
            return None
        el = r.elems()
        if len(el) != 2 or el[0].attrs != [("class", "icon")] or el[1].attrs:
            return None
        icon = text(el[0]).strip()
        if not is_symbol_token(icon) or rule_class(icon) != r.cls[1]:
            return None
        body = inline_run(el[1].children)
        items.append(f"- {icon} {body}")
    if [c for c in n.children if isinstance(c, str) and c.strip()] or not items:
        return None
    return "\n".join(items)


def steps(n):
    items = []
    for st in n.elems():
        el = st.elems()
        if st.attrs != [("class", "step")] or len(el) != 2 or el[0].attrs != [("class", "step-num")] \
                or el[1].attrs != [("class", "step-content")]:
            return None
        num = text(el[0]).strip()
        if not num.isdigit():
            return None
        items.append(f"{num}. {inline_run(el[1].children)}")
    return "\n".join(items) if items else None


def plain_list(ul):
    if ul.tag != "ul" or ul.attrs:
        return None
    items = []
    for li in ul.elems():
        if li.tag != "li" or li.attrs:
            return None
        items.append(inline_run(li.children))
    if not items or all(is_symbol_token(i.split(" ", 1)[0]) for i in items):
        return None  # would be read back as rules
    if any(re.match(r"\d+\. ", i) for i in items):
        return None
    return "\n".join("- " + i for i in items)


def cards(n, ctx):
    out = []
    for k, card in enumerate(n.elems()):
        if card.attrs != [("class", "card")]:
            return None
        el = card.elems()
        if not el or el[0].attrs != [("class", "card-title-inner")]:
            return None
        title = el[0]
        dot = title.elems()[0] if title.elems() else None
        if dot is None or dot.attrs[:1] != [("class", "dot")] or len(dot.attrs) != 2 or title.children[0] is not dot:
            return None
        color = re.fullmatch(r"background:(#[0-9a-fA-F]{3,6})", dot.a.get("style", ""))
        if not color:
            return None
        ttl = inline_run(title.children[1:])
        mark = "" if k < len(PALETTE) and color.group(1).lower() == PALETTE[k] else f" <!-- {color.group(1)} -->"
        body = []
        for c in card.children[card.children.index(title) + 1:]:
            if isinstance(c, str):
                if c.strip():
                    return None
                continue
            pl = plain_list(c)
            if pl is None:
                return None
            body.append(pl)
        out.append(f"**{ttl}**{mark}" + ("\n" + "\n\n".join(body) if body else ""))
        if not ttl.strip() or "\n" in ttl:
            return None
    if [c for c in n.children if isinstance(c, str) and c.strip()] or not out:
        return None
    return "> [!cards]\n" + quote("\n\n".join(out))


def table(wrap):
    el = wrap.elems()
    if len(el) != 1 or el[0].tag != "table" or el[0].attrs:
        return None
    tb = el[0]
    parts = tb.elems()
    if [p.tag for p in parts] != ["thead", "tbody"] or any(p.attrs for p in parts):
        return None
    rows = []
    for p in parts:
        for tr in p.elems():
            if tr.tag != "tr" or tr.attrs:
                return None
            cells = []
            want = "th" if p.tag == "thead" else "td"
            for c in tr.elems():
                if c.tag != want or c.attrs:
                    return None
                cells.append(inline_run(c.children).replace("|", "\\|") or " ")
            rows.append(cells)
    if len(parts[0].elems()) != 1 or not rows:
        return None
    w = len(rows[0])
    if any(len(r) != w for r in rows):
        return None
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * w]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def figure(f):
    if f.tag != "figure" or f.attrs != [("style", FIG_STYLE)]:
        return None
    el = f.elems()
    if len(el) != 2 or el[0].tag != "img" or el[1].tag != "figcaption":
        return None
    img, cap = el
    ia = img.attrs
    if [k for k, _ in ia[:2]] != ["src", "alt"] or ia[2:] != FIG_IMG:
        return None
    cs = cap.a.get("style", "")
    if cap.attrs != [("style", CAP_STYLE)] or has_block(cap):
        return None
    src = img.a["src"]
    if ")" in src or '"' in cap_text(cap):
        return None
    alt = esc_text(img.a["alt"])
    return f'![{alt}]({img_src(src).replace(" ", "%20")} "{cap_text(cap)}")'


def cap_text(cap):
    return inline_run(cap.children)


# ---------- sections ----------

def section(item, ctx):
    num = acc_num(item)
    trig = item.elems()[0]
    content = item.elems()[1] if len(item.elems()) > 1 else None
    left = trig.elems()[0]
    after_num = left.children[left.children.index(left.elems()[0]) + 1:]
    after_num = [c for c in after_num if not (isinstance(c, str) and not c.strip())]
    if len(after_num) == 1 and isinstance(after_num[0], Node) and after_num[0].tag == "span" and not after_num[0].attrs:
        title = inline_run(after_num[0].children)
    else:
        raise SystemExit(f"Unexpected title markup in {num}")
    extra = [(k, v) for k, v in item.attrs if k != "class"]
    if item.cls != ["acc-item"] or trig.attrs != [("class", "acc-trigger"), ("onclick", "toggleAcc(this)")]:
        raise SystemExit(f"Unexpected acc-item markup in {num}")
    tmp = Node("x", extra)
    lines = [f"## {num} {title}" + (f" <!-- attrs:{attr_str(tmp)} -->" if extra else "")]
    body = []
    kids = content.children if content is not None else []
    i = 0
    while i < len(kids):
        c = kids[i]
        if isinstance(c, Node) and c.attrs == [("class", "sub-accordion")]:
            body.extend(sub_items(c, ctx, "### "))
            rest = [x for x in kids[i + 1:] if not (isinstance(x, str) and not x.strip())]
            if rest:
                body.append("<!-- /sub -->")
            i += 1
            continue
        j = i
        while j < len(kids) and not (isinstance(kids[j], Node) and kids[j].attrs == [("class", "sub-accordion")]):
            j += 1
        body.extend(blocks(kids[i:j], ctx))
        i = j
    return "\n\n".join(lines + body)


def main():
    src, outdir = sys.argv[1], sys.argv[2]
    root = parse(open(src, encoding="utf-8").read())
    chapters = find_chapter_items(root)
    os.makedirs(os.path.join(outdir, "partials"), exist_ok=True)
    for cid, num in CHAPTERS:
        acc = chapters[cid]
        secs = []
        for item in acc.elems():
            if "acc-item" not in item.cls:
                raise SystemExit(f"Unexpected element in accordion of {cid}: {item.tag} {item.attrs}")
            n = acc_num(item)
            secs.append(section(item, n))
        with open(os.path.join(outdir, f"{num}.body.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n\n---\n\n".join(secs) + "\n")
    for name, h in partials.items():
        with open(os.path.join(outdir, "partials", name + ".html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(h + "\n")
    for k, v in report.most_common():
        print(f"{v:4} {k}", file=sys.stderr)


if __name__ == "__main__":
    main()
