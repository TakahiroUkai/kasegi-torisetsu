#!/usr/bin/env python3
"""稼ぎのトリセツ 静的サイト生成(標準ライブラリのみ)。

使い方:
  python3 build.py          content/methods/*.md から docs/ を再生成する
  python3 build.py --next   次に追加する手法(data/queue.json の先頭の未掲載)を表示する
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content" / "methods"
DOCS = ROOT / "docs"
CONFIG = json.loads((ROOT / "config" / "site.json").read_text(encoding="utf-8"))
QUEUE = json.loads((ROOT / "data" / "queue.json").read_text(encoding="utf-8"))

REQUIRED = ["title", "category", "summary", "cost", "time_to_income", "skill", "face", "risk", "risk_label", "updated"]
LIST_KEYS = ("books", "sources")


def esc(s):
    return html.escape(str(s), quote=True)


# ---------- 読み込み ----------

def parse_front(text, name):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise SystemExit(f"{name}: 先頭の --- で囲んだメタ情報がありません")
    meta, key = {}, None
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        if line.startswith("- ") and key in LIST_KEYS:
            meta[key].append([p.strip() for p in line[2:].split("|")])
        else:
            k, _, v = line.partition(":")
            key, v = k.strip(), v.strip()
            meta[key] = [] if (key in LIST_KEYS and not v) else v
    for k in REQUIRED:
        if not meta.get(k):
            raise SystemExit(f"{name}: メタ情報 {k} がありません")
    if not meta.get("sources"):
        raise SystemExit(f"{name}: sources(出典)が1件もありません。調べた情報源を載せてください")
    try:
        meta["risk"] = int(meta["risk"])
    except ValueError:
        raise SystemExit(f"{name}: risk は1〜5の整数にしてください")
    if not 1 <= meta["risk"] <= 5:
        raise SystemExit(f"{name}: risk は1〜5の整数にしてください")
    return meta, m.group(2)


def load_methods():
    methods = {}
    for p in sorted(CONTENT.glob("*.md")):
        meta, body = parse_front(p.read_text(encoding="utf-8"), p.name)
        meta["slug"] = p.stem
        meta["body"] = body
        methods[p.stem] = meta
    return methods


# ---------- 簡易Markdown ----------

def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)

    def link(m):
        url = m.group(2).replace('"', "%22")
        if not re.match(r"^(https?://|\.{0,2}/|#)", url):
            return m.group(0)
        ext = ' rel="noopener" target="_blank"' if url.startswith("http") else ""
        return f'<a href="{url}"{ext}>{m.group(1)}</a>'

    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, s)


def to_blocks(md):
    blocks, para, items, kind = [], [], [], None

    def flush():
        nonlocal para, items, kind
        if para:
            blocks.append(("p", " ".join(para)))
        if items:
            blocks.append((kind, items))
        para, items, kind = [], [], None

    for line in md.strip("\n").splitlines():
        s = line.strip()
        if not s:
            flush()
        elif s.startswith("## "):
            flush(); blocks.append(("h2", s[3:]))
        elif s.startswith("### "):
            flush(); blocks.append(("h3", s[4:]))
        elif re.match(r"^[-*] ", s):
            if kind != "ul":
                flush()
            kind = "ul"; items.append(s[2:])
        elif re.match(r"^\d+\. ", s):
            if kind != "ol":
                flush()
            kind = "ol"; items.append(re.sub(r"^\d+\. ", "", s))
        else:
            if items:
                flush()
            para.append(s)
    flush()
    return blocks


def block_html(b):
    t, c = b
    if t == "h3":
        return f"<h3>{inline(c)}</h3>"
    if t == "p":
        return f"<p>{inline(c)}</p>"
    tag = "ul" if t == "ul" else "ol"
    return f"<{tag}>" + "".join(f"<li>{inline(i)}</li>" for i in c) + f"</{tag}>"


def section_class(title):
    if title.startswith(("注意", "警告")):
        return "warn"
    if "始め方" in title or "手順" in title:
        return "steps"
    if title.startswith("こんなとき") or "つまずき" in title:
        return "trouble"
    return ""


def render_body(md):
    """h2 ごとに <section> に分け、(本文HTML, ページ内目次) を返す。"""
    sections, cur = [], {"title": None, "blocks": []}
    for b in to_blocks(md):
        if b[0] == "h2":
            sections.append(cur)
            cur = {"title": b[1], "blocks": []}
        else:
            cur["blocks"].append(b)
    sections.append(cur)

    out, nav, n = [], [], 0
    for sec in sections:
        inner = "".join(block_html(b) for b in sec["blocks"])
        if sec["title"] is None:
            out.append(inner)
            continue
        n += 1
        sid = f"s{n}"
        nav.append((sid, sec["title"]))
        cls = section_class(sec["title"])
        out.append(f'<section id="{sid}"{f" class=\"{cls}\"" if cls else ""}><h2>{inline(sec["title"])}</h2>{inner}</section>')
    return "".join(out), nav


# ---------- 部品 ----------

def risk_dots(n):
    cells = "".join(
        f'<i class="on{" hot" if n >= 4 else ""}"></i>' if i < n else "<i></i>" for i in range(5)
    )
    return f'<span class="risk" role="img" aria-label="リスク度 {n}/5">{cells}</span>'


def ad_slot():
    ads = CONFIG.get("ads", {})
    if not ads.get("enabled"):
        return ""
    snippet = ""
    f = ROOT / ads.get("snippet_file", "")
    if f.is_file():
        snippet = f.read_text(encoding="utf-8")
    return f'<aside class="ad-slot" aria-label="広告">{snippet}</aside>'


def affiliate_on():
    return bool(CONFIG.get("affiliate", {}).get("amazon_tag"))


def book_item(b):
    title = b[0]
    author = b[1] if len(b) > 1 else ""
    isbn = re.sub(r"[^0-9Xx]", "", b[2]) if len(b) > 2 else ""
    tag = CONFIG.get("affiliate", {}).get("amazon_tag", "")
    name = esc(title)
    if tag and isbn:
        url = f"https://www.amazon.co.jp/s?k={esc(isbn)}&amp;tag={esc(tag)}"
        name = f'<a href="{url}" rel="sponsored noopener" target="_blank">{name}</a>'
    by = f'<div class="by">{esc(author)}</div>' if author else ""
    return f"<li>{name}{by}</li>"


def layout(title, desc, body, root, show_disclosure):
    name = CONFIG["name"]
    full = name if title == name else f"{title} | {name}"
    disclosure = ""
    if show_disclosure or affiliate_on() or CONFIG.get("ads", {}).get("enabled"):
        parts = []
        if affiliate_on():
            parts.append("このサイトには、書籍紹介のアフィリエイトリンク(広告)が含まれます。リンク先で購入されると、運営者に報酬が入ることがあります。")
        if CONFIG.get("ads", {}).get("enabled"):
            parts.append("広告枠を設けています。")
        if parts:
            disclosure = f'<p><strong>広告について</strong> {"".join(parts)}</p>'
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full)}</title>
<meta name="description" content="{esc(desc)}">
<meta property="og:title" content="{esc(full)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=BIZ+UDPGothic:wght@400;700&amp;display=swap">
<link rel="stylesheet" href="{root}assets/style.css">
</head>
<body>
<header class="site-head">
  <div class="wrap">
    <a class="site-name" href="{root or './'}">{esc(name)}</a>
    <p class="site-tag">{esc(CONFIG["subtitle"])}</p>
  </div>
</header>
<main>
{body}
</main>
<footer class="site-foot">
  <div class="wrap">
    <p><strong>ご利用にあたって</strong> このサイトは一般的な情報の整理であり、収益を保証するものでも、投資の助言や勧誘でもありません。金額・手数料・規約は変わることがあるため、始める前に必ず公式の情報を確認してください。最終的な判断はご自身の責任でお願いします。</p>
    {disclosure}
    <p>{esc(name)} は1日1手法ずつ、ページを追加しています。</p>
  </div>
</footer>
</body>
</html>
"""


# ---------- ページ生成 ----------

def render_method(m):
    body_html, nav = render_body(m["body"])
    spec_rows = [
        ("初期費用", esc(m["cost"])),
        ("収益化まで", esc(m["time_to_income"])),
        ("必要なスキル", esc(m["skill"])),
        ("顔出し", esc(m["face"])),
        ("リスク度", f'{risk_dots(m["risk"])} {esc(m["risk_label"])}'),
    ]
    spec = "".join(f"<tr><th scope=\"row\">{k}</th><td>{v}</td></tr>" for k, v in spec_rows)
    inpage = "".join(f'<li><a href="#{sid}">{esc(t)}</a></li>' for sid, t in nav)
    books = ""
    if m.get("books"):
        books = (
            '<section class="books"><h2>この手法を紹介している本</h2><ul class="book-list">'
            + "".join(book_item(b) for b in m["books"])
            + "</ul></section>"
        )
    sources = (
        '<section class="sources"><h2>調べた情報源</h2><ul class="source-list">'
        + "".join(
            f'<li><a href="{esc(s[1])}" rel="noopener" target="_blank">{esc(s[0])}</a></li>' if len(s) > 1 else f"<li>{esc(s[0])}</li>"
            for s in m["sources"]
        )
        + "</ul></section>"
    )
    page = f"""<div class="wrap doc">
  <div class="doc-head">
    <p class="crumb"><a href="../">もくじ</a></p>
    <h1>{esc(m["title"])}</h1>
    <p class="summary">{esc(m["summary"])}</p>
    <p class="stamp">{esc(m["updated"])} 時点の情報</p>
    <table class="spec"><caption>仕様</caption><tbody>{spec}</tbody></table>
    <ul class="inpage" aria-label="このページの内容">{inpage}</ul>
  </div>
  {body_html}
  {ad_slot()}
  {books}
  {sources}
  <p style="margin-top:2.5rem"><a href="../">もくじにもどる</a></p>
</div>"""
    return layout(m["title"], m["summary"], page, "../", False)


def render_index(methods):
    cats = CONFIG["categories"]
    order = {q["slug"]: i for i, q in enumerate(QUEUE)}
    groups = []
    for c in cats:
        items = sorted((m for m in methods.values() if m["category"] == c["id"]), key=lambda m: order.get(m["slug"], 999))
        groups.append((c, items))
    total = len(QUEUE)
    done = len(methods)

    toc = []
    for c, items in groups:
        if items:
            rows = "".join(
                f'<li><div class="toc-row"><a href="methods/{esc(m["slug"])}.html">{esc(m["title"])}</a>'
                f'<span class="leader" aria-hidden="true"></span>{risk_dots(m["risk"])}</div>'
                f'<p class="toc-sum">{esc(m["summary"])}</p></li>'
                for m in items
            )
            lst = f'<ul class="toc-list">{rows}</ul>'
        else:
            lst = '<p class="toc-empty">これから追加します。</p>'
        toc.append(
            f'<div class="toc-group"><h3>{esc(c["name"])}</h3><p class="desc">{esc(c["desc"])}</p>{lst}</div>'
        )

    body = f"""<div class="wrap">
  <div class="cover">
    <h1>{esc(CONFIG["name"])}</h1>
    <p class="sub">{esc(CONFIG["subtitle"])}</p>
    <p class="lead">副業や個人事業で稼ぐ方法は、数が多く、怪しい話も混ざっています。ここでは1日1つずつ、手法を取扱説明書の形で整理します。どの手法も同じ順番(しくみ、向き不向き、リスク、始め方)で書くので、見比べて選べます。</p>
    <div class="howto">
      <h2>この説明書の読み方</h2>
      <dl>
        <dt>仕様</dt><dd>各ページの最初の表です。初期費用、収益化までの目安、必要なスキル、顔出しの要否、リスク度をまとめています。</dd>
        <dt>リスク度 {risk_dots(1)} から {risk_dots(5)}</dt><dd>点が多いほど、お金や時間を失いやすい手法です。4以上は黄色で示します。</dd>
        <dt>黄色と黒の枠</dt><dd>損をしやすいポイントです。始める前に必ず読んでください。</dd>
      </dl>
    </div>
  </div>
  <section class="toc">
    <h2>もくじ</h2>
    <p class="toc-count">掲載中 {done}件 / 追加予定を含め {total}件。毎日1件ずつ増えます。</p>
    {"".join(toc)}
  </section>
  {ad_slot()}
</div>"""
    return layout(CONFIG["name"], CONFIG["description"], body, "", False)


def build():
    methods = load_methods()
    known = {q["slug"] for q in QUEUE}
    for slug in methods:
        if slug not in known:
            print(f"注意: {slug} は data/queue.json にありません(もくじには出ますが、順序は最後になります)")
    (DOCS / "methods").mkdir(parents=True, exist_ok=True)
    for old in (DOCS / "methods").glob("*.html"):
        if old.stem not in methods:
            old.unlink()
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    (DOCS / "index.html").write_text(render_index(methods), encoding="utf-8")
    for slug, m in methods.items():
        (DOCS / "methods" / f"{slug}.html").write_text(render_method(m), encoding="utf-8")
    print(f"生成しました: もくじ + 手法ページ {len(methods)}件")


def show_next():
    done = {p.stem for p in CONTENT.glob("*.md")}
    for q in QUEUE:
        if q["slug"] not in done:
            print(f'{q["slug"]}\t{q["title"]}\t{q["category"]}')
            return
    print("追加予定の手法はすべて掲載済みです。data/queue.json に候補を足してください。")


if __name__ == "__main__":
    show_next() if "--next" in sys.argv else build()
