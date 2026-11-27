"""Minimal HTML tree (stdlib only), shared by md_migrate.py and verify_roundtrip.py."""
import html
import re
from html.parser import HTMLParser

VOID = {"br", "img", "hr", "input", "meta", "link", "source", "circle", "path"}


class Node:
    def __init__(self, tag, attrs, parent=None):
        self.tag = tag
        self.attrs = list(attrs)          # keep source order
        self.parent = parent
        self.children = []

    @property
    def a(self):
        return dict(self.attrs)

    @property
    def cls(self):
        return self.a.get("class", "").split()

    def elems(self):
        return [c for c in self.children if isinstance(c, Node)]


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root", [])
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        self.cur.children.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def parse(src):
    t = Tree()
    t.feed(src)
    t.close()
    return t.root


def text(n):
    return n if isinstance(n, str) else "".join(text(c) for c in n.children)


def walk(n, pred):
    for c in n.children:
        if isinstance(c, Node):
            if pred(c):
                yield c
            yield from walk(c, pred)


def attr_str(n):
    out = []
    for k, v in n.attrs:
        out.append(k if v is None else f'{k}="{html.escape(v, quote=True)}"')
    return (" " + " ".join(out)) if out else ""


def serialize(n):
    """Re-serialize a node as HTML (text escaped, attributes kept in order)."""
    if isinstance(n, str):
        return html.escape(n, quote=False)
    if n.tag == "root":
        return "".join(serialize(c) for c in n.children)
    if n.tag in VOID:
        return f"<{n.tag}{attr_str(n)}>"
    return f"<{n.tag}{attr_str(n)}>" + "".join(serialize(c) for c in n.children) + f"</{n.tag}>"


def find_chapter_items(root):
    """Return {chapter_id: [acc-item nodes]} for the eight chapter pages."""
    out = {}
    for page in walk(root, lambda x: "page" in x.cls and x.a.get("id")):
        acc = next(walk(page, lambda x: "accordion" in x.cls), None)
        if acc is None:
            continue
        out[page.a["id"]] = acc
    return out


def acc_num(item):
    s = next(walk(item, lambda x: "acc-num" in x.cls), None)
    return text(s).strip() if s is not None else None


WS = re.compile(r"\s+")
