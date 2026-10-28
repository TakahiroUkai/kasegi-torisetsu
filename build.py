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
    if meta.get("category") != "caution":
        for k in ("ai_auto", "ai_auto_label"):
            if not meta.get(k):
                raise SystemExit(f"{name}: メタ情報 {k}(AIでの自動化しやすさ)がありません")
    if meta.get("ai_auto"):
        try:
            meta["ai_auto"] = int(meta["ai_auto"])
        except ValueError:
            raise SystemExit(f"{name}: ai_auto は1〜5の整数にしてください")
        if not 1 <= meta["ai_auto"] <= 5:
            raise SystemExit(f"{name}: ai_auto は1〜5の整数にしてください")
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

    fence = None
    for line in md.strip("\n").splitlines():
        s = line.strip()
        if fence is not None:
            if s == ":::":
                blocks.append(("fig", (fence[0], fence[1])))
                fence = None
            elif s:
                fence[1].append(s)
            continue
        if s.startswith(":::"):
            flush()
            fence = (s[3:].strip(), [])
        elif not s:
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


def num(v):
    return float(re.sub(r"[^0-9.]", "", v) or 0)


def render_fig(head, lines):
    """図解ブロック。書式は README ではなく運営メモ(Artifact)に記載。
    :::flow 見出し       行: 見出し | 補足          (手順・しくみの流れ)
    :::yen 見出し         行: ラベル | 名前:金額 | 名前:金額 ...  (金額の内訳の帯グラフ)
    :::calc 見出し        行: [×=−+] ラベル | 値      (掛け算・引き算の計算の流れ)
    """
    kind, _, title = head.partition(" ")
    cap = f"<figcaption>{inline(title)}</figcaption>" if title else ""
    rows = [[c.strip() for c in l.split("|")] for l in lines]
    if kind == "flow":
        li = "".join(
            f"<li><strong>{inline(r[0])}</strong>" + (f"<span>{inline(r[1])}</span>" if len(r) > 1 and r[1] else "") + "</li>"
            for r in rows
        )
        return f'<figure class="fig fig-flow">{cap}<ol class="flow">{li}</ol></figure>'
    if kind == "yen":
        parsed = []
        for r in rows:
            segs = []
            for c in r[1:]:
                n, _, v = c.partition(":")
                segs.append((n.strip(), num(v)))
            parsed.append((r[0], segs))
        top = max((sum(v for _, v in s) for _, s in parsed), default=1) or 1
        out = []
        for label, segs in parsed:
            total = sum(v for _, v in segs)
            cells = "".join(
                f'<i class="seg{i}" style="width:{v / top * 100:.1f}%"></i>' for i, (_, v) in enumerate(segs)
            )
            legend = "".join(
                f'<li><i class="sw seg{i}"></i>{esc(n)} {v:,.0f}円</li>' for i, (n, v) in enumerate(segs)
            )
            out.append(
                f'<div class="bar-row"><p class="bar-label">{inline(label)}<span>合計 {total:,.0f}円</span></p>'
                f'<div class="bar" aria-hidden="true">{cells}</div><ul class="legend">{legend}</ul></div>'
            )
        return f'<figure class="fig fig-yen">{cap}{"".join(out)}</figure>'
    if kind == "calc":
        li = []
        for r in rows:
            label = r[0]
            op = ""
            if label and label[0] in "×=−+":
                op, label = label[0], label[1:].strip()
            val = r[1] if len(r) > 1 else ""
            cls = ' class="res"' if op == "=" else ""
            li.append(f'<li{cls}><b class="op" aria-hidden="true">{op}</b><span class="lb">{inline(label)}</span><span class="vl">{inline(val)}</span></li>')
        return f'<figure class="fig fig-calc">{cap}<ul class="calc">{"".join(li)}</ul></figure>'
    if kind == "mock":
        cls = {"title": "m-title", "text": "m-text", "paywall": "m-paywall", "price": "m-price",
               "button": "m-button", "field": "m-field", "image": "m-image"}
        rows_html, notes, n = [], [], 0
        for r in rows:
            k = r[0] if r[0] in cls else "text"
            label = r[1] if len(r) > 1 else ""
            note = r[2] if len(r) > 2 else ""
            badge = ""
            if note:
                n += 1
                badge = f'<b class="badge" aria-hidden="true">{n}</b>'
                notes.append(f"<li>{inline(note)}</li>")
            rows_html.append(f'<div class="{cls[k]}">{inline(label)}{badge}</div>')
        return (f'<figure class="fig fig-mock">{cap}<div class="mock"><div class="mock-bar" aria-hidden="true"><i></i><i></i><i></i></div>'
                f'<div class="mock-body">{"".join(rows_html)}</div></div>'
                f'<ol class="mock-notes">{"".join(notes)}</ol>'
                f'<p class="fig-caption-note">画面のイメージ図です。実際の画面とは異なります。</p></figure>')
    if kind == "auto":
        who = {"AI": ("ai", "AI"), "自動": ("tool", "自動"), "人": ("human", "人")}
        li = []
        for r in rows:
            c, lab = who.get(r[0], ("human", r[0]))
            title_ = r[1] if len(r) > 1 else ""
            note = r[2] if len(r) > 2 else ""
            li.append(
                f'<li class="is-{c}"><strong><span class="who who-{c}">{esc(lab)}</span>{inline(title_)}</strong>'
                + (f"<span>{inline(note)}</span>" if note else "") + "</li>"
            )
        legend = '<p class="auto-legend"><span>AI: 文章や判断をAIに任せる工程</span><span>自動: 決まった手順をツールが動かす工程</span><span>人: 人が確認・決定する工程</span></p>'
        return f'<figure class="fig fig-flow fig-auto">{cap}{legend}<ol class="flow">{"".join(li)}</ol></figure>'
    raise SystemExit(f"不明な図の種類: {kind}")


def block_html(b):
    t, c = b
    if t == "fig":
        return render_fig(*c)
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
    if "AI" in title:
        return "auto"
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
        if n == 4 and len(sections) >= 7:
            out.append(ad_slot())
    return "".join(out), nav


# ---------- 部品 ----------

def risk_dots(n):
    cells = "".join(
        f'<i class="on{" hot" if n >= 4 else ""}"></i>' if i < n else "<i></i>" for i in range(5)
    )
    return f'<span class="risk" role="img" aria-label="リスク度 {n}/5">{cells}</span>'


def ai_dots(n):
    cells = "".join('<i class="on"></i>' if i < n else "<i></i>" for i in range(5))
    return f'<span class="auto-gauge" role="img" aria-label="AIでの自動化しやすさ {n}/5">{cells}</span>'


def ad_slot():
    ads = CONFIG.get("ads", {})
    if not ads.get("enabled"):
        if ads.get("placeholder"):
            return '<aside class="ad-slot is-empty" aria-label="広告"><span>広告スペース(準備中)</span></aside>'
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
<meta name="color-scheme" content="light">
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
    if m.get("ai_auto"):
        spec_rows.append(("AI自動化しやすさ", f'{ai_dots(m["ai_auto"])} {esc(m["ai_auto_label"])}'))
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
    is_caution = m["category"] == "caution"
    banner = '<p class="caution-banner">稼ぎ方ではなく、手を出してはいけない話(怪しい話・違法な話)の解説です</p>' if is_caution else ""
    page = f"""<div class="wrap doc{" cat-caution" if is_caution else ""}">
  <div class="doc-head">
    {banner}
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
                f'<span class="leader" aria-hidden="true"></span><span class="toc-meta"><span><small>リスク</small>{risk_dots(m["risk"])}</span>'
                + (f'<span><small>自動化</small>{ai_dots(m["ai_auto"])}</span>' if m.get("ai_auto") else "")
                + '</span></div>'
                f'<p class="toc-sum">{esc(m["summary"])}</p></li>'
                for m in items
            )
            lst = f'<ul class="toc-list">{rows}</ul>'
        else:
            lst = '<p class="toc-empty">これから追加します。</p>'
        note = ""
        if c["id"] == "caution":
            note = '<p class="caution-note">ここから先は、稼ぎ方ではありません。詐欺・違法行為・それに近い話を、見分けて避けるための解説です。</p>'
        toc.append(
            f'<div class="toc-group{" cat-caution" if c["id"] == "caution" else ""}"><h3>{esc(c["name"])}</h3>{note}<p class="desc">{esc(c["desc"])}</p>{lst}</div>'
        )

    body = f"""<div class="wrap">
  <div class="cover">
    <h1>{esc(CONFIG["name"])}</h1>
    <p class="sub">{esc(CONFIG["subtitle"])}</p>
    <p class="lead">副業や個人事業で稼ぐ方法は、数が多く、怪しい話も混ざっています。ここでは手法を、取扱説明書の形で整理します。どの手法も同じ順番(しくみ、向き不向き、リスク、始め方)で書くので、見比べて選べます。</p>
    <div class="howto">
      <h2>この説明書の読み方</h2>
      <dl>
        <dt>仕様</dt><dd>各ページの最初の表です。初期費用、収益化までの目安、必要なスキル、顔出しの要否、リスク度をまとめています。</dd>
        <dt>リスク度 {risk_dots(1)} から {risk_dots(5)}</dt><dd>点が多いほど、お金や時間を失いやすい手法です。4以上は黄色で示します。</dd>
        <dt>自動化しやすさ {ai_dots(1)} から {ai_dots(5)}</dt><dd>AIとツールに任せられる作業が多いほど、点が多くなります。最後の確認と判断は、どの手法でも人が行います。</dd>
        <dt>黄色と黒の枠</dt><dd>損をしやすいポイントです。始める前に必ず読んでください。</dd>
      </dl>
    </div>
  </div>
  <section class="toc">
    <h2>もくじ</h2>
    <p class="toc-count">掲載中 {done}件 / 追加予定を含め {total}件。</p>
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
