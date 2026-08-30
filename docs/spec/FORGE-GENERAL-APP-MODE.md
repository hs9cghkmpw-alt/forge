# FORGE GENERAL APP MODE

Status: EXECUTION TARGET
Date: 2026-08-30

## Product target

Forge の次の正式ゴールは、単に Widget の種類を増やすことではない。

> **ユーザーが自然文で欲しいアプリを説明すると、Forge が要求を能力へ分解し、既存 Primitive で構成し、足りなければ不足を明示し、安全に能力を拡張し、生成・検証・修復まで行って動くアプリへ到達する。**

ユーザー体験としての到達点は「自然文を言えば何でもアプリになる」に近づける。ただし内部では「何でも」を無条件に成功扱いしない。実装不能・権限不足・危険な Effect は Capability Gap として正直に残し、作れたふりを禁止する。

本仕様は `FORGE-SELF-EXTENSION-ARCH-REVIEW-v2.md` の Product Goal / Semantic Capability と Runtime Primitive の分離 / A→B→C の Self-Extension 順序を実行計画へ落としたもの。

## Definition of Done

General App Mode は次の一連が自動で閉じる状態を PASS とする。

```text
natural language
  -> semantic/capability plan
  -> product spec
  -> runtime primitive plan
  -> Forge Document / generated workspace
  -> validator
  -> test
  -> build
  -> runtime probe
  -> visual/behavior evidence when applicable
  -> bounded repair
  -> final evidence
```

加えて、未実装能力を要求された場合は次を満たす。

```text
unsupported need
  -> exact missing capability
  -> safety/trust classification
  -> extension route (composition / declarative / build-time / service / privileged)
  -> no false success
```

## Capability expansion order

### GA-1 Logic Core

最優先。CRUD/画面配置から「アプリの振る舞い」へ広げる。

- condition / compare
- if / else
- derive / computed state
- filter
- sort
- aggregate
- arithmetic
- boolean composition
- event -> state transition
- reusable rule definitions

Acceptance examples:

- 「残高が0未満なら赤い警告を出す」
- 「未完了だけ表示する」
- 「カテゴリ別に支出を合計する」
- 「BMIを体重と身長から計算する」

### GA-2 Navigation + Persistent Data

- multi-screen navigation with parameters
- local persistent storage
- schema migration/versioning
- search/query
- relation/reference between records
- import/export of structured data

Acceptance examples:

- 顧客一覧 -> 顧客詳細 -> 編集
- アプリを閉じても記録が残る
- CSV/JSON の安全な入出力

### GA-3 External Service Effects

Effect は純粋な View/Transform と分離し、Policy Gate を必須にする。

- HTTP/API request
- authenticated service adapters
- file upload/download
- share
- notification
- email/webhook style outbound adapters

Requirements:

- outbound destination visible in evidence
- secret isolation
- timeout/retry boundary
- allowlist/policy
- irreversible operation confirmation where required

### GA-4 Device Capabilities

- camera
- microphone
- location
- file picker
- clipboard
- sensors where platform support exists

OS permission と Capability Safety を明示し、自動で権限を隠れて取得しない。

### GA-5 Rich Presentation

- image
- icon
- animation
- grid
- canvas/scene
- map
- richer charts
- responsive layouts
- theme/design composition

ここでも「Widgetを増やすだけ」に戻らず、Encoding Primitive（position/color/size/opacity 等）を優先する。

### GA-6 Media + Game Runtime

- user media import
- audio editing/composition/export
- image composition/export
- video/media timeline where justified
- input events
- collision/hit testing
- sprite/scene primitives
- deterministic game state
- save/load

既存 `simulate.loop` と `audio_mixer` を基礎に拡張する。

### GA-7 Safe Self-Extension

既存 Primitive だけで表現できる Capability は declarative definition として追加できるようにする。

新しい Runtime 実装が必要な場合は build-time extension とし、最低限:

1. generated change is isolated
2. validator/schema/parser/runtime/compiler binding exists
3. tests pass
4. build passes
5. runtime evidence passes
6. security/policy checks pass
7. only then capability status may become IMPLEMENTED

AI の自己申告だけで Capability を IMPLEMENTED に変更してはならない。

## Architecture rule

Capability と Widget を同一視しない。

```text
User Need
 -> Semantic Capability
 -> Runtime Primitive(s)
    DATA
    TRANSFORM
    VIEW
    ENCODING
    EFFECT
    SIMULATE
 -> Forge Language binding
 -> platform/runtime implementation
```

同じ Primitive を再利用して表現の族を増やす。例として aggregate を一度実装すれば、家計・体重・釣果・売上など複数ドメインで再利用する。

## Truthfulness rule

General App Mode の成功率を上げるために、Capability Gap を消すための嘘は禁止する。

- PARTIAL を IMPLEMENTED と呼ばない
- interactive audio mixing を media export と呼ばない
- browser/widget test を実端末/実ブラウザ evidence と混同しない
- visual unknown を PASS に書き換えない
- privileged effect を UI が存在するだけで実装済みにしない

## Execution strategy

一度に「全アプリ種類」を個別実装しない。汎用 Primitive を優先する。

優先度:

1. GA-1 Logic Core
2. GA-2 Persistent Data / Navigation
3. GA-3 External Service Effects
4. GA-5 Rich Presentation
5. GA-4 Device Capabilities
6. GA-6 Media/Game Runtime
7. GA-7 Build-Time Self-Extension

この順序は固定ではないが、個別 Widget を大量追加するより、条件・計算・派生状態・Effect Adapter のような横断 Primitive を優先する。

## First implementation slice

次の実装スライスは **GA-1 Logic Core**。

最初の縦切りは:

```text
condition expression
 -> conditional branch
 -> derived value
 -> UI visibility/value binding
 -> compiler generation
 -> backend validation
 -> Flutter runtime
 -> regression test
 -> generated-app evidence
```

Golden acceptance request:

> 「毎月の収入と支出を記録して、残高を自動計算し、残高がマイナスなら警告を表示する家計アプリを作って」

PASS 条件:

- income/expense records can be entered
- balance is derived, not hard-coded
- negative balance condition controls warning visibility
- generated document validates
- ordinary CI passes
- generated app builds and runs
- evidence confirms the condition changes behavior

## Relation to previous Golden game

Golden game closure is retained as evidence that Forge is already beyond static CRUD: deterministic simulation + interactive audio + real Chrome rendering passed. General App Mode starts from that proven baseline and expands breadth via reusable primitives rather than reopening the closed Golden game work.
