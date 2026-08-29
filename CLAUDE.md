# Forge — 作業ルール

> **全Agent共通Protocolはroot `AGENTS.md`を正とする。Claude Codeも
> 作業開始時に最初に読むこと。** この文書はClaude/Repository固有の補足で
> あり、共通Protocolを置き換えない。

このファイルは、このリポジトリで作業するAIエージェント（Claude Code等）
への恒久的な指示である。**セッションを跨いで有効。**

---

## 0. 作業開始時に必ず読むもの

Claude Codeは毎回、実装前に最低限この順で読む。

1. `docs/FORGE-CORE-CONSTITUTION.md`
2. `docs/PRODUCT-DIRECTION.md`
3. `docs/GENERATIVE-SOFTWARE-DIRECTION.md`
4. `docs/LEARNABLE-LOCAL-AI-VISION.md`
5. `docs/FORGE-CURRENT-STATE.md`
6. `docs/HANDOFF.md`
7. root `AGENTS.md`
8. `docs/ROADMAP-TO-TARGET.md`
9. `TECH_DEBT.md`
10. relevant Architecture / Spec / latest Report / Evidence / current HEAD / diff / CI

`FORGE-CORE-CONSTITUTION.md`の意味変更が必要に見える場合は、勝手に更新せず
`FORGE CONSTITUTION CHANGE PROPOSAL`としてCEOへ提案する。CEO承認前は現行版を
正典とする。

`FORGE-CURRENT-STATE.md`は不動文書ではなく、実装・Evidence・Current Taskの
変化に合わせて更新するmutable snapshotである。GitHubの新しいEvidenceと
矛盾した場合は新しいEvidenceを正として、同Task内でCurrent Stateを更新する。

---

## 1. 報告は必ずmdファイルにして、同じpushに含める（2026-08-17、CEO指示）

**チャットの中だけで報告してはならない。**

理由: このリポジトリは**複数のAI（Claude / ChatGPT）が同じGitHubを見て
作業する**。チャットの内容は他方から見えないので、チャットにしか無い
情報は**存在しないのと同じ**である。

### 守ること

作業を終えてpushするとき、**同じcommitに**次を含める。

1. **`docs/HANDOFF.md` を上書き更新する**（パス固定・毎回）
   * CEOへの依頼（APIキーが要る等）を**一番上**に書く
   * やったこと / 今の状態 / 次にやること / 未解決
   * **チャットで報告する内容と同じものを書く。** チャットを読んで
     いない人が読んでも分かるように、自己完結させる
2. **まとまった作業は `docs/reports/<TASK名>-report.md` にも残す**
   （詳細・根拠・実測値。HANDOFFは要約、reportsは全文）
3. **`CHANGELOG.md`** にTaskとして追記
4. 状態が変わったら **`docs/FORGE-CURRENT-STATE.md`** と **`STATUS.md`**、
   負債が増減したら **`TECH_DEBT.md`**

### やりがちな失敗（実際にやった）

* 実機で見つけた発見をチャットで報告して、mdに書かなかった
  → 次のセッションで消える。**発見はその場でmdに落とす**
* レポートをリポジトリ直下に置いた → 正しい場所は `docs/reports/`
* 「動いた」で満足して報告文書を書かずに終えた

---

## 2. 上位文書

矛盾したら**上のものが勝つ**。ただしConstitutionの変更が必要になる矛盾は
黙って解釈せずCEOへ提案する。

| 順位 | 文書 | 内容 |
|---|---|---|
| 0 | `docs/FORGE-CORE-CONSTITUTION.md` | **不動原則。** Forgeの存在目的・核心UX・Evidence原則 |
| 1 | `docs/PRODUCT-DIRECTION.md` | **変更不可。** 実装都合で縮小・先送りしない |
| 2 | `docs/GENERATIVE-SOFTWARE-DIRECTION.md` | **何を作る機械なのか。** 有限Widget Builderにしない |
| 2 | `docs/LEARNABLE-LOCAL-AI-VISION.md` | **作る側のAIが何になるべきか。** Local Model接続で終わらせない |
| 3 | `docs/architecture/FORGE-GROWING-AI-ARCHITECTURE.md` | AI/Learning領域のArchitecture |
| 4 | `docs/ROADMAP-TO-TARGET.md` | 完成図までの段取り（閉ループ版） |
| 5 | `docs/ROADMAP.md` | 全体方針 |

`docs/FORGE-CURRENT-STATE.md`はこの順位表の「方針」文書ではなく、現在地を
示すmutable snapshot。方針より上書きしないが、古いチャットや古いhandoffより
新しい実Repository/Evidenceを反映する。

順位2の2つは並列である（片方は成果物、片方はそれを作るAI）。
どちらも**実装の都合で目標を縮小しないための下限**であり、
「Local Modelを接続した」「Widget/Templateを増やした」を達成と数えない。

`PRODUCT-DIRECTION.md` §8 の**7問の自己監査**に、最終報告の前に必ず
答えること。問題があれば黙って目標を変えず、問題・代替案・Trade-offを
報告する。

---

## 3. 実装のルール（過去に踏んだ失敗から）

### 直す前に再現する

推測で直さない。**再現できていないものは直したと言わない。**

### 「作ったが本番から呼ばれない」を作らない

これは**4回以上繰り返している**失敗である（TD59 / 007 §10 / 010 Phase B /
TD64等）。共通するのは「呼び出し側が忘れずに呼ぶ」設計だったこと。
**忘れずに呼ばれる保証が無いものは忘れられる。**

新しい仕組みは、本番が必ず通る場所へ置くか、**通らなければテストが
落ちる**形にする。

### ガードが実際に効くことを確かめる

テストを書いたら、**直した配線を1つずつ外して、対応するテストが落ちる
ことを確認する**。落ちなければそのテストは置物である。

### 分からないものを楽観側へ倒さない

`UNKNOWN` を既定値にする。「記録し忘れ」が「安全」「承認済み」「PASS」へ
化けない向きに倒す。

### 実測と公称を分ける

Provider公称値をコードへ固定しない。書いてよいのは**実際に呼んで
確認したものだけ**。検証区分（実測 / Test Double / 未検証）を報告に
明記する。

### Template / Widget数を生成力KPIにしない

有限部品を増やして「作れるジャンルが増えた」と言わない。
NeedをCapabilityへ分解し、既存Capability再利用・missing/unsupportedを
正直に扱い、必要ならGate付きSelf-Extensionへ進む。

---

## 4. Secret

* Git追跡対象に持ってよいのは**環境変数の名前だけ**。値は持たない
* Source / Test Fixture / Documentation / Report へ実値を書かない
* ログにも出さない。長さや先頭数文字も出さない
* CIにAPIキーを置かない（Live Testは既定SKIP）

---

## 5. API無料枠

Gemini等の無料枠・Provider制限は変動し得る。Repositoryに実測値を残す場合は
実測日時・Provider・Model・検証条件を明示し、古い実測を永久仕様として
扱わない。429を作るためだけにquotaを浪費しない。

---

## 6. テスト・CI

```text
cd backend  && python -m pytest tests -q
cd forge_ai && python -m pytest tests -q
```

Flutter/UI変更はroot `AGENTS.md`のVisual Evidenceルールに従う。
CIの実際のjob構成は `.github/workflows/` と最新runを確認し、古い文書上の
job数を固定仕様として扱わない。

## 7. ブランチ

作業ブランチは指示されたものを使う。**指示なく別ブランチへpushしない。**
