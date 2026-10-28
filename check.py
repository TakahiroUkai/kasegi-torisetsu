#!/usr/bin/env python3
"""公開前チェック。python3 check.py [--visual]
エラー(ERROR)が1つでもあれば終了コード1。警告(WARN)は目視で確認する。"""
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parent
errors, warns = [], []
def err(m): errors.append(m)
def warn(m): warns.append(m)

subprocess.run([sys.executable, "build.py"], cwd=ROOT, capture_output=True)
site = json.loads((ROOT / "config/site.json").read_text(encoding="utf-8"))
docs = sorted((ROOT / "docs").rglob("*.html"))
contents = sorted((ROOT / "content/methods").glob("*.md"))

def text_of(p): return p.read_text(encoding="utf-8")

# 1. 個人情報・非公開情報(docs, content, data, config, README)
targets = docs + contents + [ROOT / "README.md", ROOT / "config/site.json",
                             ROOT / "data/queue.json", ROOT / "data/quiz.json"]
personal = [r"ut\.0608", r"@gmail\.com", r"[\w.+-]+@[\w-]+\.[\w.]+(?<!noreply\.github\.com)"]
for p in targets:
    t = text_of(p)
    for pat in personal:
        for m in re.finditer(pat, t):
            if "users.noreply.github.com" in m.group(0):
                continue
            err(f"個人情報らしき文字列 {m.group(0)!r}: {p.relative_to(ROOT)}")
fit_words = ["向き度", "自分への注意度", "ひらがな学習アプリ", "日本株の調査", "勤務先の副業", "fit:", "運営メモ"]
for p in docs + contents:
    t = text_of(p)
    for w in fit_words:
        if w in t:
            err(f"非公開の評価に関わる語 {w!r}: {p.relative_to(ROOT)}")

# 2. 禁止・要注意表現
hard_ban = [r"1日1[つ手]", r"毎日更新", r"毎日1[つ手]", r"1日1手法"]
soft_ban = [r"簡単に稼", r"誰でも稼", r"確実に稼", r"必ず稼", r"絶対に?稼", r"絶対儲", r"楽して", r"ノーリスク"]
for p in docs:
    t = re.sub(r"<[^>]+>", "", text_of(p))
    for pat in hard_ban:
        if re.search(pat, t):
            err(f"更新頻度の説明 {pat}: {p.relative_to(ROOT)}")
    for pat in soft_ban:
        for m in re.finditer(pat, t):
            s = t[max(0, m.start() - 25): m.end() + 25].replace("\n", " ")
            warn(f"要注意表現(注意喚起の文脈か確認) {pat}: {p.relative_to(ROOT)} …{s}…")

# 3. 広告・アフィリエイト設定
ads = site.get("ads", {})
if not ads.get("enabled") and not ads.get("placeholder"):
    for p in docs:
        if "ad-slot" in text_of(p) or "広告スペース" in text_of(p):
            err(f"広告枠の表示が残っている: {p.relative_to(ROOT)}")
if ads.get("enabled") or site.get("affiliate", {}).get("amazon_tag"):
    if not any("広告について" in text_of(p) for p in docs):
        err("広告/アフィリエイトが有効なのに「広告について」の表記がない")

# 4. 各ページの必須項目とcautionルール
for p in contents:
    t = text_of(p)
    m = re.match(r"---\n(.*?)\n---\n(.*)", t, re.S)
    if not m:
        err(f"フロントマターなし: {p.name}"); continue
    fm, body = m.group(1), m.group(2)
    cat = re.search(r"^category:\s*(\S+)", fm, re.M)
    cat = cat.group(1) if cat else ""
    if not re.search(r"^sources:", fm, re.M):
        err(f"sources なし: {p.name}")
    urls = re.findall(r"https?://[^\s|]+", fm)
    if len(urls) < 2:
        warn(f"出典URLが少ない({len(urls)}件): {p.name}")
    for fig in ("flow", "yen", "calc"):
        if f":::{fig}" not in body:
            warn(f"図解 {fig} なし: {p.name}")
    if cat == "caution":
        for w in ["向いている", "向いていない", "おすすめ"]:
            if w in body:
                err(f"cautionページに {w!r}: {p.name}")
        if "見分けやすい人・気をつけたい人" not in body:
            err(f"caution見出しなし: {p.name}")
        if ":::auto" in body or "ai_auto" in fm:
            err(f"cautionページに AI自動化の記述: {p.name}")
        for m2 in re.finditer(r"(株式会社|有限会社|合同会社)[^\s、。]{1,12}", body):
            warn(f"法人名らしき記述(特定企業の断定になっていないか確認): {p.name} {m2.group(0)}")
        for pat in [r"の手口を再現", r"台本", r"以下のように(声をかけ|話し)"]:
            if re.search(pat, body):
                warn(f"勧誘の台本・再現手順になっていないか確認 {pat}: {p.name}")
    else:
        if ":::auto" not in body:
            warn(f"AI自動化の図(:::auto)なし: {p.name}")
        if ":::mock" not in body:
            warn(f"画面イメージ(:::mock)なし: {p.name}")
        if re.search(r"(必ず|確実に|絶対に?)(稼|儲|収益)", body):
            err(f"収益の断定表現: {p.name}")

# 5. クイズ
q = json.loads((ROOT / "data/quiz.json").read_text(encoding="utf-8"))
ids = set()
answers = []
for it in q:
    if it["id"] in ids: err(f"クイズid重複: {it['id']}")
    ids.add(it["id"])
    if len(it["options"]) != 3 or not (0 <= it["answer"] < 3): err(f"クイズ形式: {it['id']}")
    if not it.get("explain") or not it.get("source") or not str(it["source"][1]).startswith("http"):
        err(f"クイズの解説/出典なし: {it['id']}")
    answers.append(it["answer"])

# 6. docs が最新のビルド結果か
b = subprocess.run([sys.executable, "build.py"], cwd=ROOT, capture_output=True, text=True)
if b.returncode != 0:
    err("build.py 失敗: " + b.stderr[-300:])
else:
    d = subprocess.run(["git", "status", "--porcelain", "docs"], cwd=ROOT, capture_output=True, text=True).stdout
    # 未コミットの差分は許容(これからコミットする)。ここでは build が通ることだけを確認
# 7. 内部リンク切れ
for p in docs:
    for href in re.findall(r'href="([^"#:]+?)"', text_of(p)):
        if href.startswith(("http", "mailto")) or re.search(r"[\'\"+ ]", href): continue
        tgt = (p.parent / href).resolve()
        if tgt.is_dir(): tgt = tgt / "index.html"
        if not tgt.exists():
            err(f"リンク切れ {href}: {p.relative_to(ROOT)}")

# 8. 見た目(任意): スマホ幅で横スクロールが出ないか
if "--visual" in sys.argv:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_page(viewport={"width": 390, "height": 800})
        for p in docs:
            pg.goto(p.resolve().as_uri())
            w = pg.evaluate("document.documentElement.scrollWidth")
            if w > 392: err(f"横スクロール発生({w}px): {p.relative_to(ROOT)}")
        br.close()

for w in warns: print("WARN ", w)
for e in errors: print("ERROR", e)
print(f"\n{len(errors)} errors, {len(warns)} warnings, {len(docs)} html pages")
sys.exit(1 if errors else 0)
