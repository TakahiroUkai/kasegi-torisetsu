# 稼ぎのトリセツ ― 1人でお金を稼ぐ道

副業・個人事業で稼ぐ方法を、しくみ・手数料・リスク・始め方まで同じ順番で整理する静的サイトです。1日1つずつ、手法のページを追加しています。

収益を保証するものではなく、投資の助言や勧誘でもありません。金額・手数料・規約は変わることがあるため、各ページの出典(公式情報)を確認してください。

## 構成

| パス | 内容 |
|---|---|
| `content/methods/` | 手法ページの原稿(Markdown) |
| `data/queue.json` | 掲載する手法の一覧と順序 |
| `config/site.json` | サイト名、カテゴリなどの設定 |
| `build.py` | 原稿から `docs/` を生成するスクリプト(Python 3、標準ライブラリのみ) |
| `docs/` | 生成されたサイト |

## ビルド

```
python3 build.py
```

## 原稿の書式

`content/methods/<slug>.md` の先頭に、次のメタ情報を書きます。本文は `##` の見出しごとに区切ります。

```
---
title: 手法の名前
category: content
summary: 一文の説明
cost: 初期費用
time_to_income: 収益化までの目安
skill: 必要なスキル
face: 顔出しの要否
risk: 2
risk_label: リスクの中身
updated: 2026-10-28
books:
- 書名 | 著者(出版社) | ISBN
sources:
- 情報源のタイトル | URL
---
```

`category` は `config/site.json` のカテゴリID、`risk` は1〜5の整数です。`sources` が空だとビルドは止まります。
