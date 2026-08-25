# Forge Agent Protocol

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

## Independent Review

ChatGPT ReviewerはImplementation Agentの報告をそのまま承認せず、GitHub上の
HEAD、diff、実コード、tests、CIを独立確認する。GitHubへpushされていない
Markdownは共有記憶として扱わない。
