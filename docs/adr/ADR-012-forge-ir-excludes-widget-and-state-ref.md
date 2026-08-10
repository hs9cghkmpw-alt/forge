# ADR-012: Why FORGE IR Does Not Include Widget Types or state_ref

**Status:** Accepted
**Ref:** FORGE v0.5「FORGE IR v1 Architecture Proposal」0章・2章・3章

## Context

FORGE IRを設計するにあたり、「View」という要素が、実際にどこまで
具体的な情報を持つべきかが論点になった。Widget種別(`text_field`・
`checklist`・`card`等)やstate_ref(Forge Runtimeの状態管理における
識別子)を含めれば、IRからForge Language JSONへの変換ロジック
(`ForgeLanguageCompiler`)を単純化できる。一方、これらはいずれも
「Flutter Runtimeがどう状態を保持し、どう描画するか」という、
Flutter固有の実装詳細である。

## Decision

**FORGE IRには、Widget種別・state_ref・Forge Language固有のAction
JSON形式(`composite`/`add_item`/`reset_state`等)を一切含めない。**

IRの`View`は`kind`(list/form/detail)という**意図**のみを持ち、
どのWidgetで表現するか、どうレイアウトするかは`ForgeLanguageCompiler`
(またはFlutter以外のターゲットでは、それぞれのCompiler Backend)の
判断に委ねる。IRの`Action`は`kind`(create_entity/update_entity/
delete_entity/navigate)という**抽象的な操作**のみを持ち、その操作を
Forge Runtime上でどう実現するか(`add_item`+`reset_state`の
`composite`にする、等)は`ForgeLanguageCompiler`が決める。

判断基準として、「この要素はFlutter以外のUIフレームワーク(React/
SwiftUI/Jetpack Compose)でも同じ意味を持つか?」を、IRへ新しい要素を
追加する際に必ず自問する、というガバナンス方針を明文化する
(`FORGE-IR-V1-PROPOSAL.md` 0章4項)。

## Alternatives

- **IRのViewに、Widget種別のヒント(例: `preferred_widget: "checklist"`)
  を持たせる**: 却下。「ヒント」という位置づけであっても、実際には
  ほぼ確実にFlutter Runtimeの語彙がIRへ漏れ出す(最初は「ヒント」でも、
  次第に`ForgeLanguageCompiler`がそのヒントへ依存するようになり、
  実質的にWidget選択がIR側で決まってしまう)。
- **IRのActionに、`composite`のような複合Action構造を持たせる**:
  却下。`composite`はForge Language v1.2で新設した、Flutter Runtime
  の状態管理モデル(state_refベースのフラットなストア)に依存した
  実現方法である。IRの`Action`は「Entityを作成する」という抽象操作
  のみを表現し、それを1つのAction呼び出しで実現するか複数のAction
  合成で実現するかは、`ForgeLanguageCompiler`側の実装詳細とする。

## Consequences

- `ForgeLanguageCompiler`は、IRの抽象的な`View`/`Action`から、
  具体的なWidget/Action JSON構造を**自分で決定する**責務を持つ
  (Template-aware Compiler Stage1の`_compile_record_template()`と
  ほぼ同じロジックを、入力元だけIRへ変えて実装した)。
- 「List ViewとForm Viewを、Forge Language側の制約(stateは画面ごとに
  スコープされる)により単一画面へ畳み込む」という判断は、IR層には
  一切現れず、`ForgeLanguageCompiler`(および付随する`NavigationGraph.
  edges`が空になるという結果)にのみ現れる。IR自体は、List ViewとForm
  Viewを独立した2つのViewとして表現し続ける(`FORGE-IR-V1-PROPOSAL.md`
  3.3節、Stage1で発見した制約をIRの表現力の制限理由にしない、という
  方針の具体的な帰結)。
- 将来Flutter以外のCompiler Backendを追加する際、そのBackendは
  IRから「Flutter向けの決定」を一切引き継がず、ゼロから自分自身の
  Widget選択・状態管理方式を決定できる。

## Revisit Conditions

- Flutter以外の2つ目のCompiler Backendを実際に実装する段階になって、
  IRの抽象化(Widget/state_refを含めないという判断)が本当に十分
  だったか(逆に情報が不足していて、2つ目のBackendが実装しづらいIR
  になっていないか)を実地で検証する。この検証は、1つのターゲットの
  経験だけからは行えない(`FORGE-IR-V1-PROPOSAL.md`9章「デメリット」
  2項)。
