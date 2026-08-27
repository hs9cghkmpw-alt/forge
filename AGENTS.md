# Forge Agent Protocol

## Visual evidence for UI work

Any task that changes UI, renderer behavior, Design Language, or generated-app appearance is incomplete without a real render and visual evidence. The implementation agent must start the relevant preview, render at the relevant viewport, capture representative before/after screenshots, open and inspect the images, fix observed defects, and record findings in the task report and visual manifest. Unit tests alone never justify “looks correct.” If the agent did not inspect a real render, the result is `UNVERIFIED`.

GitHub上のこのRepositoryと、commit/pushされたMarkdownを全Agent間の
Source of Truthとする。Codex/Claude固有のローカルhandoffは補助情報であり、
この文書を置き換えない。

## 作業開始

実装前に、root `AGENTS.md`、`CLAUDE.md`、`docs/PRODUCT-DIRECTION.md`、
`docs/HANDOFF.md`、`docs/ROADMAP-TO-TARGET.md`、`TECH_DEBT.md`、関連する
Architecture/Spec、最新の関連Reportを読む。併せて`git status`、現在branch、
HEAD/log、unstaged/staged diff、remoteとの同期を確認する。

未commit差分は別Agentまたは利用者の作業かもしれない。監査せずに
reset、delete、overwriteしてはならない。

## 実装と交代

- 同じworking treeで動くImplementation Agentは一度に1つとする。
- Agent交代は、自己完結した実装・検証・文書をcommitして指定branchへpush
  することでバトンを渡す。
- 「コードがある」だけを完了にしない。Production wiring、回帰test、
  配線を意図的に壊したmutation確認、Markdown更新、push、CI確認までを
  完了条件とする。
- 実行していない確認は`UNVERIFIED`、存在しないProduction経路は
  `未実装`と明記する。

## 作業終了

最低限`docs/HANDOFF.md`、Task固有の`docs/reports/<TASK>-report.md`、
`CHANGELOG.md`を更新する。状態・設計・負債が変わった場合は`STATUS.md`、
`TECH_DEBT.md`、関連Architecture/Spec/ROADMAPも更新する。コードだけ、
または古いHANDOFFのままpushしたTaskは未完了とする。

HANDOFFとReportにはbranch、start/final HEAD、実装内容、Production wiring、
tests、mutation、CI、未検証、Technical Debt、次Taskを残す。秘密値やraw
利用者データは文書・fixture・logへ残さない。

## Context / Token Safety — mandatory

全Agentは作業中、残りcontext/token余力と残作業量を継続的に確認または保守的に推定する。正確な残量を取得できない場合でも、この規則は免除されない。

context切れ・出力打切り・作業途中の情報喪失が起きそうな状態まで作業を続けることは禁止する。危険域に入る前に安全なcheckpointを作り、現在の変更を可能な範囲で保存し、`docs/HANDOFF.md`、Task report、Issue/PRなどSource of Truthへ `AI-HANDOFF` を残して作業を止める。

`AI-HANDOFF` には最低限、(1)目的、(2)完了済み、(3)未完了、(4)branch/commit/PR/Issue、(5)変更ファイル、(6)実行済みtests/CI/visual結果、(7)blocker、(8)次の具体的1〜3手、(9)触ってはいけない安全境界、(10)推測・未検証事項を含める。

申し送り後に新しい大規模変更を開始してはならない。次Agentは最初に最新HANDOFFを読み、重複作業をせず続きから再開する。トークンを使い切ることより、早めで完全な申し送りを優先する。

## Agent Execution Policy

Implementation Agent が、いちいち確認を取らずに実行してよいことと、
必ず確認を取ることと、やってはいけないことを分ける。

**確認の回数を減らすためのルールではない。** 取り返しがつくかどうかで
分けている——戻せる操作で人を待たせず、戻せない操作を勝手にやらない。

### 自動実行してよい

- read / edit / file create
- `git status` / `git log` / `git diff` / `git fetch`
- tests
- lint / analyze
- build
- localhost preview
- visual capture

### 確認が必須

- commit
- push
- package / SDK / system install
- OS設定の変更
- credential / auth の変更
- 大量の削除・移動
- 外部へのデータ送信
- 既存作業へ影響する branch 操作

### 禁止

- `git reset --hard`
- `git clean -fd` / `-fdx`
- 出所の分からない未commit作業の削除
- secrets の commit
- 許可の無い破壊的操作

未commit差分は別Agentまたは利用者の作業かもしれない。**監査せずに
消さない**（「作業開始」節と同じ）。

---

## GitHub Handoff / No Manual Copy-Paste

**Implementation Agent の長文結果を、利用者が Reviewer へ手で転送する
運用を禁止する。**

人が中継すると、転送漏れ・古い版の貼り付け・要約による欠落が起きる。
そして**GitHubに無いものは、Reviewer から見て存在しない**（この文書の
冒頭のとおり）。

Task 終了時、次までが Agent の仕事である。

```
docs/HANDOFF.md
→ docs/reports/<TASK>-report.md
→ CHANGELOG.md
→ 必要な Spec / TECH_DEBT / Architecture
→ tests / mutation / visual / CI の evidence
→ commit
→ push
→ local と remote の HEAD 一致を確認
```

**Reviewer は GitHub を直接読む。**

利用者が言うことは、原則として

> 「終わった、レビューして」

だけでよい。それ以上を人に運ばせているなら、Agent の仕事が終わって
いない。

---

## Independent Review

ChatGPT ReviewerはImplementation Agentの報告をそのまま承認せず、GitHub上の
HEAD、diff、実コード、tests、CIを独立確認する。GitHubへpushされていない
Markdownは共有記憶として扱わない。
