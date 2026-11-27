#!/usr/bin/env node
// Build the chapter content of index.html from the Bible markdown (bibelen/*.md).
// Only the inside of each chapter's <div class="accordion"> is replaced; the shell,
// CSS, JS, front page and dashboard stay untouched.
//
// Usage: node tools/build-from-md.js [--md DIR] [--html FILE] [--out FILE] [--check]
//   --md    markdown folder (default: ../OBSIDIAN_VAULT/wiki/workflow/NesheiMedia-guide/bibelen)
//   --html  page to update (default: index.html in the repo)
//   --out   where to write (default: same as --html)
//   --partials folder with HTML partials (default: partials/ in the repo)
//   --check exit 1 if the output would differ from --html (writes nothing)

'use strict';
const fs = require('fs');
const path = require('path');

const REPO = path.resolve(__dirname, '..');
const BASE = 'https://regularivar.github.io/NesheiMedia-guide/';
const CHAPTERS = [['rutiner', '01'], ['workflows', '02'], ['edittips', '03'], ['editassets', '04'],
  ['grade', '05'], ['ai', '06'], ['prosjekter', '07'], ['gear', '08']];
const CALLOUT = { info: 'blue', warning: 'orange', tip: 'green', danger: 'red' };
const PALETTE = ['#4f8ef7', '#34d399', '#fb923c', '#c084fc', '#22d3ee', '#f472b6', '#fbbf24', '#a3e635'];
const FIG_STYLE = 'margin:0;background:rgba(255,255,255,0.03);border:1px solid var(--border);border-radius:12px;overflow:hidden';
const CAP_STYLE = 'padding:10px 12px;color:var(--text2);font-family:var(--mono);font-size:11px';
const VOID = new Set(['br', 'img', 'hr', 'input', 'meta', 'link', 'source', 'circle', 'path']);
const BLOCK_TAGS = new Set(['div', 'p', 'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'td', 'th', 'h1', 'h2',
  'h3', 'h4', 'h5', 'section', 'figure', 'figcaption', 'pre', 'blockquote', 'svg', 'label', 'button']);

function arg(name, def) {
  const i = process.argv.indexOf(name);
  return i > 0 ? process.argv[i + 1] : def;
}

// ---------- inline ----------

const PUNCT = /[!-\/:-@\[-`{-~]/;

function escHtml(s) {
  return s.replace(/&(?![A-Za-z][A-Za-z0-9]*;|#\d+;|#x[0-9a-fA-F]+;)/g, '&amp;').replace(/</g, '&lt;');
}

function escAttr(s) {
  return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function imgSrc(src) {
  return src.startsWith(BASE) ? decodeURI(src.slice(BASE.length)) : src;
}

// Find the end of a delimiter run starting at i, skipping code spans, tags and escapes.
function findClose(s, i, delim) {
  while (i < s.length) {
    const c = s[i];
    if (c === '\\' && i + 1 < s.length && PUNCT.test(s[i + 1])) { i += 2; continue; }
    if (c === '`') { const j = s.indexOf('`', i + 1); if (j < 0) return -1; i = j + 1; continue; }
    if (c === '<') { const m = /^<\/?[A-Za-z][^>]*>/.exec(s.slice(i)); if (m) { i += m[0].length; continue; } }
    if (s.startsWith(delim, i)) {
      if (delim === '*' && s[i + 1] === '*') { const j = findClose(s, i + 2, '**'); if (j < 0) return -1; i = j + 2; continue; }
      return i;
    }
    i++;
  }
  return -1;
}

function codeSpan(t) {
  if (/^[A-Z]:\\$/.test(t)) return `<span class="drive-badge">${escHtml(t)}</span>`;
  if (t.startsWith('\\\\')) return `<span class="path">${escHtml(t)}</span>`;
  return `<code>${escHtml(t)}</code>`;
}

function inline(s) {
  let out = '';
  let i = 0;
  while (i < s.length) {
    const c = s[i];
    const rest = s.slice(i);
    if (c === '\\' && i + 1 < s.length && PUNCT.test(s[i + 1])) { out += escHtml(s[i + 1]); i += 2; continue; }
    if (c === '<') {
      const m = /^<!--[\s\S]*?-->|^<\/?[A-Za-z][^>]*>/.exec(rest);
      if (m) { out += m[0]; i += m[0].length; continue; }
    }
    if (rest.startsWith('``')) {
      const j = s.indexOf('``', i + 2);
      if (j > i + 1) { out += `<code>${escHtml(s.slice(i + 2, j))}</code>`; i = j + 2; continue; }
    }
    if (c === '`') {
      const j = s.indexOf('`', i + 1);
      if (j > i) { out += codeSpan(s.slice(i + 1, j)); i = j + 1; continue; }
    }
    if (rest.startsWith('**')) {
      const j = findClose(s, i + 2, '**');
      if (j > i + 2) { out += `<strong>${inline(s.slice(i + 2, j))}</strong>`; i = j + 2; continue; }
    }
    if (c === '*') {
      const j = findClose(s, i + 1, '*');
      if (j > i + 1) { out += `<em>${inline(s.slice(i + 1, j))}</em>`; i = j + 1; continue; }
    }
    if (rest.startsWith('![')) {
      const m = /^!\[((?:\\.|[^\]\\])*)\]\(([^)\s]+)\)/.exec(rest);
      if (m) { out += `<img src="${escAttr(imgSrc(m[2]))}" alt="${escAttr(unesc(m[1]))}">`; i += m[0].length; continue; }
    }
    if (c === '[') {
      const j = findClose(s, i + 1, ']');
      if (j > i && s[j + 1] === '(') {
        const k = s.indexOf(')', j + 2);
        if (k > j) {
          out += `<a href="${escAttr(s.slice(j + 2, k))}" target="_blank" rel="noopener noreferrer">${inline(s.slice(i + 1, j))}</a>`;
          i = k + 1; continue;
        }
      }
    }
    out += c === '<' ? '&lt;' : c;
    i++;
  }
  return out;
}

function unesc(s) {
  return s.replace(/\\([!-\/:-@\[-`{-~])/g, '$1');
}

// ---------- blocks ----------

const isSymbolToken = (t) => !!t && !/[A-Za-z0-9ÆØÅæøå\s]/.test(t);

function ruleClass(icon) {
  if (icon === '✓') return 'ok';
  if (['⚠', '⚠️', '!', '✕'].includes(icon)) return 'warn';
  return 'info';
}

function list(items) {
  const toks = items.map((it) => it.split(' ')[0]);
  if (toks.every(isSymbolToken)) {
    return '<div class="rules">\n' + items.map((it) => {
      const icon = it.split(' ')[0];
      const body = it.slice(icon.length + 1);
      return `  <div class="rule ${ruleClass(icon)}"><div class="icon">${escHtml(icon)}</div><div>${inline(body)}</div></div>`;
    }).join('\n') + '\n</div>';
  }
  return '<ul>' + items.map((it) => `<li>${inline(it)}</li>`).join('') + '</ul>';
}

function table(lines) {
  const row = (l) => {
    const cells = [];
    let cur = '';
    const s = l.trim().replace(/^\|/, '').replace(/\|$/, '');
    for (let i = 0; i < s.length; i++) {
      if (s[i] === '\\' && s[i + 1] === '|') { cur += '|'; i++; continue; }
      if (s[i] === '|') { cells.push(cur.trim()); cur = ''; continue; }
      cur += s[i];
    }
    cells.push(cur.trim());
    return cells;
  };
  const head = row(lines[0]);
  const body = lines.slice(2).map(row);
  return '<div class="table-wrap"><table>\n<thead><tr>' + head.map((c) => `<th>${inline(c)}</th>`).join('') +
    '</tr></thead>\n<tbody>\n' + body.map((r) => '<tr>' + r.map((c) => `<td>${inline(c)}</td>`).join('') + '</tr>').join('\n') +
    '\n</tbody>\n</table></div>';
}

function figure(line) {
  const m = /^!\[((?:\\.|[^\]\\])*)\]\((\S+) "(.*)"\)$/.exec(line);
  if (!m) throw new Error('Bad gallery image: ' + line);
  return `<figure style="${FIG_STYLE}"><img src="${escAttr(imgSrc(m[2]))}" alt="${escAttr(unesc(m[1]))}" loading="lazy" style="width:100%;display:block"><figcaption style="${CAP_STYLE}">${inline(m[3])}</figcaption></figure>`;
}

function cards(lines, ctx, md) {
  const groups = [];
  for (const l of lines) {
    const m = /^\*\*(.+)\*\*(?: <!-- (#[0-9a-fA-F]{3,6}) -->)?$/.exec(l);
    if (m) {
      groups.push({ title: m[1], color: m[2], body: [] });
    } else if (groups.length) {
      groups[groups.length - 1].body.push(l);
    } else if (l.trim()) {
      throw new Error(`${ctx}: text before first card: ${l}`);
    }
  }
  return '<div class="cards">\n' + groups.map((g, k) => {
    const color = g.color || PALETTE[k];
    return `  <div class="card"><div class="card-title-inner"><span class="dot" style="background:${color}"></span>${inline(g.title)}</div>${blocks(g.body, ctx, md)}</div>`;
  }).join('\n') + '\n</div>';
}

function callout(lines, ctx, md) {
  const head = /^\[!(\w+)\]\s*(.*)$/.exec(lines[0]);
  if (!head) throw new Error(`${ctx}: bad callout ${lines[0]}`);
  const [, kind, rest] = head;
  const body = lines.slice(1);
  if (kind === 'vault') return '';   // vault-only notes and [[links]]: shown in Obsidian, not on the page
  if (kind === 'cards') return cards(body, ctx, md);
  if (kind === 'note') {
    return `<div class="nb-card">\n  <div class="nb-header">${inline(rest)}</div>\n  <div class="nb-body">\n${blocks(body, ctx, md)}\n  </div>\n</div>`;
  }
  if (kind === 'gallery') {
    const custom = /^<!-- style="([^"]*)" -->$/.exec(rest);
    const [fit, min, gap, mb] = rest.split(' ');
    const style = custom ? custom[1]
      : `display:grid;grid-template-columns:repeat(auto-${fit},minmax(${min}px,1fr));gap:${gap}px;margin-bottom:${mb}px`;
    return `<div style="${style}">\n` +
      body.filter((l) => l.trim()).map((l) => '  ' + figure(l)).join('\n') + '\n</div>';
  }
  if (!CALLOUT[kind]) throw new Error(`${ctx}: unknown callout type ${kind}`);
  const parsed = parseBlocks(body, ctx, md);
  let text;
  if (parsed.every((b) => b.type === 'p')) {
    text = parsed.map((b) => inline(b.text)).join('<br><br>');
  } else {
    text = parsed.map((b) => b.html).join('\n');
  }
  return `<div class="callout ${CALLOUT[kind]}"><span class="callout-icon">${escHtml(rest)}</span><div class="callout-text">${text}</div></div>`;
}

// ```kode = shell/batch script box, ```prompt [max-height] = AI prompt box (whitespace kept)
function preStyle([kind, h], ctx) {
  if (kind === 'kode') {
    return 'background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:16px 20px;margin-bottom:20px;' +
      'font-family:var(--mono);font-size:12px;color:var(--text2);line-height:1.8;white-space:pre';
  }
  if (kind === 'prompt') {
    return 'background:rgba(0,0,0,0.3);border:1px solid var(--border);border-radius:8px;padding:16px;font-family:var(--mono);' +
      'font-size:11px;color:var(--text2);white-space:pre-wrap;line-height:1.7;' +
      (h ? `max-height:${h}px;overflow-y:auto;` : '') + 'margin-bottom:8px';
  }
  throw new Error(`${ctx}: unknown code block type "${kind}" (use kode or prompt)`);
}

const OPEN_TAG =/^<([A-Za-z][A-Za-z0-9]*)(\s[^>]*)?>$/;

function isParaStart(l) {
  return !(l.trim() === '' || l === '---' || l.startsWith('```') ||l.startsWith('#') || l.startsWith('>') || /^- /.test(l) ||
    /^\d+\. /.test(l) || l.startsWith('|') || l.startsWith('<!--') || OPEN_TAG.test(l) || /^<\/\w+>$/.test(l));
}

// Parse markdown lines into [{type, html, text}] blocks.
function parseBlocks(lines, ctx, md) {
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (l.trim() === '' || l === '---') { i++; continue; }
    if (l.startsWith('```')) {
      const info = l.slice(3).trim().split(' ');
      const j = lines.indexOf('```', i + 1);
      if (j < 0) throw new Error(`${ctx}: unclosed code block`);
      out.push({ type: 'pre', html: `<div style="${preStyle(info, ctx)}">${lines.slice(i + 1, j).join('\n').replace(/&/g, '&amp;').replace(/</g, '&lt;')}</div>` });
      i = j + 1; continue;
    }
    if (l.startsWith('##### ')) {
      // nested tabs inside a ### tab, closed by <!-- /undertabs -->
      const j = lines.indexOf('<!-- /undertabs -->', i);
      if (j < 0) throw new Error(`${ctx}: ##### tabs without <!-- /undertabs -->`);
      const items = [];
      for (const x of lines.slice(i, j)) {
        if (x.startsWith('##### ')) items.push({ title: x.slice(6), lines: [] });
        else items[items.length - 1].lines.push(x);
      }
      out.push({ type: 'tabs', html: subAccordion(items, ctx, md) });
      i = j + 1; continue;
    }
    if (l.startsWith('#### ')) { out.push({ type: 'h', html: `<div class="section-sub-header">${inline(l.slice(5))}</div>` }); i++; continue; }
    if (l.startsWith('#')) throw new Error(`${ctx}: heading not allowed here: ${l}`);
    let m = /^<!-- html:([\w.-]+) -->$/.exec(l);
    if (m) {
      const f = path.join(md.partials, m[1] + '.html');
      out.push({ type: 'partial', html: fs.readFileSync(f, 'utf8').replace(/\n$/, '') });
      i++; continue;
    }
    if (l.startsWith('>')) {
      const q = [];
      while (i < lines.length && lines[i].startsWith('>')) { q.push(lines[i].replace(/^> ?/, '')); i++; }
      out.push({ type: 'callout', html: callout(q, ctx, md) });
      continue;
    }
    if (/^- /.test(l)) {
      const items = [];
      while (i < lines.length && /^- /.test(lines[i])) { items.push(lines[i].slice(2)); i++; }
      out.push({ type: 'list', html: list(items) });
      continue;
    }
    if (/^\d+\. /.test(l)) {
      const items = [];
      while (i < lines.length && /^\d+\. /.test(lines[i])) { items.push(/^(\d+)\. (.*)$/.exec(lines[i]).slice(1)); i++; }
      out.push({ type: 'steps', html: '<div class="steps">\n' + items.map(([n, t]) =>
        `  <div class="step"><div class="step-num">${n}</div><div class="step-content">${inline(t)}</div></div>`).join('\n') + '\n</div>' });
      continue;
    }
    if (l.startsWith('|')) {
      const t = [];
      while (i < lines.length && lines[i].startsWith('|')) { t.push(lines[i]); i++; }
      out.push({ type: 'table', html: table(t) });
      continue;
    }
    m = OPEN_TAG.exec(l);
    if (m && !VOID.has(m[1].toLowerCase())) {
      const tag = m[1];
      let depth = 1;
      let j = i + 1;
      for (; j < lines.length; j++) {
        if (new RegExp(`^<${tag}(\\s[^>]*)?>$`).test(lines[j])) depth++;
        else if (lines[j] === `</${tag}>` && --depth === 0) break;
      }
      if (j >= lines.length) throw new Error(`${ctx}: unclosed <${tag}>`);
      out.push({ type: 'raw', html: l + '\n' + blocks(lines.slice(i + 1, j), ctx, md) + '\n' + lines[j] });
      i = j + 1;
      continue;
    }
    if (l.startsWith('<!--')) { i++; continue; }  // other comments are notes, not output
    m = /^▶ \[(.+)\]\((https:\/\/www\.youtube\.com\/watch\?v=([\w-]+)[^\s()]*)\)(?: – (.*))?$/.exec(l);
    if (m) {
      const [, title, url, id, meta] = m;
      out.push({ type: 'yt', html: `<a href="${escAttr(url)}" target="_blank" rel="noopener noreferrer" class="yt-card">` +
        `<div class="yt-thumb"><img src="https://img.youtube.com/vi/${id}/mqdefault.jpg"><span class="yt-badge">▶ VIDEO</span><span class="yt-ext">↗ YouTube</span></div>` +
        `<div class="yt-info"><div class="yt-title">${inline(title)}</div><div class="yt-meta">${inline(meta || '')}</div></div></a>` });
      i++; continue;
    }
    m = /^(.+?) :: (.+)$/.exec(l);
    if (m && !l.startsWith('<')) {
      out.push({ type: 'param', html: `<div class="param-row"><span class="param-name">${inline(m[1])}</span><span class="param-val">${inline(m[2])}</span></div>` });
      i++; continue;
    }
    const para = [];
    while (i < lines.length && (para.length === 0 || isParaStart(lines[i]))) { para.push(lines[i]); i++; }
    const text = para.join(' ');
    const bm = /^<([A-Za-z][A-Za-z0-9]*)[\s>]/.exec(text);
    if (bm && BLOCK_TAGS.has(bm[1].toLowerCase())) out.push({ type: 'raw', html: inline(text) });
    else out.push({ type: 'p', text, html: inline(text) });
  }
  return out;
}

function blocks(lines, ctx, md) {
  return parseBlocks(lines, ctx, md).map((b) => b.html).join('\n');
}

function subAccordion(items, ctx, md) {
  return '<div class="sub-accordion">\n' + items.map((s) =>
    `<div class="sub-acc-item"><button class="sub-acc-trigger" onclick="toggleSubAcc(this)"><span>${inline(s.title)}</span><span class="acc-chevron">▼</span></button><div class="sub-acc-content">\n${blocks(s.lines, ctx + ' / ' + s.title, md)}\n</div></div>`
  ).join('\n') + '\n</div>';
}

// ---------- sections ----------

function section(lines, md) {
  const m = /^## (\S+) (.*?)(?: <!-- attrs: (.*) -->)?$/.exec(lines[0]);
  const [, num, title, attrs] = m;
  const ctx = num;
  const parts = [];
  let cur = [];
  let sub = null;           // list of {title, lines}
  const flush = () => { if (cur.length) parts.push(blocks(cur, ctx, md)); cur = []; };
  const closeSub = () => {
    if (!sub) return;
    parts.push(subAccordion(sub, ctx, md));
    sub = null;
  };
  for (const l of lines.slice(1)) {
    if (l.startsWith('### ')) {
      flush();
      if (!sub) sub = [];
      sub.push({ title: l.slice(4), lines: [] });
    } else if (l === '<!-- /sub -->') {
      closeSub();
    } else if (sub) {
      sub[sub.length - 1].lines.push(l);
    } else {
      cur.push(l);
    }
  }
  flush();
  closeSub();
  const extra = attrs ? ' ' + attrs : '';
  return `      <div class="acc-item"${extra}><button class="acc-trigger" onclick="toggleAcc(this)"><div class="acc-left"><span class="acc-num">${escHtml(num)}</span><span>${inline(title)}</span></div><span class="acc-chevron">▼</span></button><div class="acc-content">\n` +
    parts.join('\n') + '\n</div></div>';
}

function chapterHtml(src, md) {
  const lines = src.replace(/\r\n/g, '\n').split('\n');
  let i = lines.findIndex((l) => l.startsWith('## '));
  if (i < 0) throw new Error('No sections found');
  const secs = [];
  let cur = null;
  for (; i < lines.length; i++) {
    const l = lines[i];
    if (l.startsWith('## ')) { if (cur) secs.push(cur); cur = [l]; } else cur.push(l);
  }
  if (cur) secs.push(cur);
  // Drop trailing section separators.
  return secs.map((s) => section(s, md)).join('\n');
}

// Locate the accordion inside a chapter page and return [start, end] of its inner HTML.
function accordionRange(html, pageId) {
  const p = html.indexOf(`<div id="${pageId}" class="page">`);
  if (p < 0) throw new Error('Page not found: ' + pageId);
  const open = '<div class="accordion">';
  const a = html.indexOf(open, p);
  const start = a + open.length;
  const re = /<div\b|<\/div>/g;
  re.lastIndex = start;
  let depth = 1;
  let m;
  while ((m = re.exec(html))) {
    depth += m[0] === '</div>' ? -1 : 1;
    if (depth === 0) return [start, m.index];
  }
  throw new Error('Unbalanced accordion in ' + pageId);
}

function build(htmlSrc, mdDir, partialsDir) {
  const md = { partials: partialsDir || path.join(REPO, 'partials') };
  const files = fs.readdirSync(mdDir);
  let html = htmlSrc;
  for (const [id, num] of CHAPTERS) {
    const f = files.find((x) => x.startsWith(num + '-') && x.endsWith('.md')) || files.find((x) => x === num + '.body.md');
    if (!f) throw new Error(`No markdown for chapter ${num} in ${mdDir}`);
    const body = chapterHtml(fs.readFileSync(path.join(mdDir, f), 'utf8'), md);
    const [s, e] = accordionRange(html, id);
    const nl = htmlSrc.includes('\r\n') ? '\r\n' : '\n';   // keep the file's line endings
    html = html.slice(0, s) + ('\n' + body + '\n    ').replace(/\r?\n/g, nl) + html.slice(e);
  }
  return html;
}

if (require.main === module) {
  const mdDir = path.resolve(arg('--md', path.join(REPO, '../OBSIDIAN_VAULT/wiki/workflow/NesheiMedia-guide/bibelen')));
  const htmlFile = path.resolve(arg('--html', path.join(REPO, 'index.html')));
  const outFile = path.resolve(arg('--out', htmlFile));
  const src = fs.readFileSync(htmlFile, 'utf8');
  const out = build(src, mdDir, arg('--partials') && path.resolve(arg('--partials')));
  if (process.argv.includes('--check')) {
    if (out !== src) { console.error('index.html is not up to date with the markdown'); process.exit(1); }
    console.log('index.html is up to date');
  } else {
    fs.writeFileSync(outFile, out);
    console.log(`Built ${path.relative(process.cwd(), outFile)} from ${mdDir}`);
  }
}

module.exports = { build, inline };
