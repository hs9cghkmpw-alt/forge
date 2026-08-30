# Prompt Template: generate_ui_schema (v1)

> **Legacy / narrow runtime prompt surface.** このテンプレートは Forge の製品境界を定義しない。
> 上位方針は `docs/FORGE-CORE-CONSTITUTION.md` → `docs/PRODUCT-DIRECTION.md` →
> `docs/GENERATIVE-SOFTWARE-DIRECTION.md`。

この経路の責務は、**すでに現行 Forge Language で表現可能だと確認された要求**を、
versioned JSON UI Schemaへ落とすことだけである。要求をSchemaに合わせて意味変更してはならない。

入力:
- ユーザーの会話履歴
- Capability Plan / semantic requirements
- 直近の `app_versions`（存在する場合）

出力:
- 表現可能な場合: `shared/schemas/ui_schema.v1.json` に準拠したJSON UI Schema 1件
- 表現不能な場合: 近いWidget/Templateへの代用をせず、上位plannerへ exact Capability Gap を返す

不変条件:
- 未定義 `type` を捏造してValidatorを迂回しない。
- Checklist/Form/CRUD等、現在作れる形へ要求を縮小して成功扱いしない。
- `PARTIAL` / `MISSING` / `UNVERIFIED` を `IMPLEMENTED` / `PASS` に昇格させない。
- 不足Capabilityはself-extension / build-time extension等の管理された生成経路へ渡す。
