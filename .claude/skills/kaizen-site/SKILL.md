---
name: kaizen-site
description: 稼ぎのトリセツの「改善の1周」で、このサイトだけに当てはまる部分(読者像、判断の観点、確かめ方)。共通の手順は TakahiroUkai/site-ops の kaizen-loop スキルにある。
---

# 改善の1周(稼ぎのトリセツだけの部分)

共通の手順(`TakahiroUkai/site-ops` の `.claude/skills/kaizen-loop/SKILL.md`)と一緒に使う。

## 基本

- 項目の接頭辞: `KT`(司令塔の `site` は `kasegi`)
- 既定ブランチ: `main`。公開URL: https://takahiroukai.github.io/kasegi-torisetsu/
- 改善の順番: 1番目(稼ぎのトリセツ → あんなことこんなことClaude → 机タイム素材集 → 注目銘柄メモの順に、実行のたびに次へ進む)

## ユーザー役の読者像

`style.md` の「想定読者」になりきる。スマホ幅で、トップページ → 手法ページ → 注意喚起(caution)のページ → クイズ、の順に読んで、「どれから始めればよいか分かるか」「怪しい話を見分けられるか」「出典をたどれるか」を確かめる。

## 事業推進役の観点(共通の観点に加えて)

- 自分に合う手法を見つけやすいか(カテゴリ、比較、向く人/向かない人)。
- 注意喚起のページが、読者を守る役に立っているか。
- ほかのサイト(特に注目銘柄メモ、あんなことこんなことClaude)への自然な導線になるか。

## 直してよい範囲

- `build.py` のページの組み立て、CSS、トップページの並び、既存の手法ページの分かりにくい文や図解。
- 直さない: `config/site.json` の affiliate・ads、`data/queue.json` の順番(毎日の追加タスクが使う)、`RULES.md` と `style.md`(変えたほうがよいときは「要確認」の項目にする)。

## 確かめ方

1. `python3 build.py`
2. `python3 check.py --visual` で ERROR が 0 件(WARN も読む)。
3. 変えたページを、スマホ幅(iPhone 13 相当)のスクリーンショットで見て、崩れがないこと。
