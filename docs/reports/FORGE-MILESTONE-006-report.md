# FORGE-MILESTONE-006 実施レポート — Cognitive Architecture v2.0

**Ref:** FORGE-MILESTONE-006(Architecture Design Only)
**担当:** Principal Engineer / Architect（Claude）　**日付:** 2026-07-15

**新規コードは0行。** Python/Dart/Flutter/Backend/Nativeディレクトリの
いずれも変更していない(実行して確認済み、後述)。

---

## 1. 成果物

| ファイル | 内容 |
|---|---|
| `docs/spec/FORGE_COGNITIVE_ARCHITECTURE_V2.md` | 本体(約960行) |
| `docs/adr/ADR-001`〜`007` | 7件のADR |
| `docs/diagrams/01`〜`09` | Mermaid図9件 |
| `docs/examples/01`〜`06` | 完全トレース例6件 |
| `docs/tasks/task030.md` | 本Task記録 |
| `CHANGELOG.md` Task030 | 更新済み |

---

## 2. 設計の要点

### 2.1 既存実装との関係
本設計はforge_ai/(M004)をゼロから作り直すものではなく、既存の
`Domain → World → Meaning → Intent → Planner → Compiler`という順序・
既存の80テストを前提に、認知能力(Ambiguity Detection・Design Critic・
Self-Revision Loop等)を**追加・強化**する形を取った。既存`World`型
(Actor/WorldObject/Relationship/Rule)へEvents/States/Permissionsを
追加する等、後方互換な拡張(既存の`IntentIR`/`PlanIR`拡張と同じ手法)を
前提としている。

### 2.2 Hybrid方式の採用
Rule-Based中心(Option A)・LLM中心(Option B)・Hybrid(Option C)を
10軸で比較し、Hybridを採用した(20章、ADR-001)。「結論ありきにしない」
という指示に従い、A・Bそれぞれが優位な観点も明記した。

### 2.3 最も重要な設計判断: Cognitive RevisionとSchema Repairの分離
既存M005で実際に発生した「Repair二重ループ問題」
(`docs/DECISIONS.md` D59)と同じ轍を、新設するSelf-Revision Loopで
踏まないよう、対象(Plan vs IR)・基準(設計品質 vs 仕様適合性)・
カウンタを明確に分離した(12章、ADR-004)。

### 2.4 Human Overrideが実際にパイプラインへ影響する設計
`docs/examples/05_welfare_support_record.md`で、Privacy起因のHIGH
Ambiguityが検出された場合、Application Plan生成前にパイプラインが
停止し確認要求するケースを具体的にトレースした。これはConfidence
Model(14章)の機械的な閾値処理よりもPrivacy起因のHIGH判定を優先する、
という優先順位の明示でもある(ADR-007)。

---

## 3. 既存コードの問題点・不足点(指示書30章「明示すること」への対応)

- forge_ai/既存の`World`型は`Events`/`States`/`Permissions`を持たず、
  病院予約のような「予約ステータスの遷移」「権限差」を表現しにくい
  (6章で拡張案を明記)。
- forge_ai/既存の`QualityScore`(6軸、IR生成後)と、本設計のDesign
  Critic(14軸、IR生成前)は評価対象・タイミングが異なり、そのまま
  流用できない(11.1節で明記、統合しない判断とした)。
- `backend/app/ai/native/`に類似実装(ルールベースIntent認識等)が
  既に存在する可能性があるが、今回は精査していない(19章で明記。
  精査自体が実装寄りの作業であり、今回のスコープ外とした)。

---

## 4. 事実・推測・提案の分離

- **事実**: 既存forge_ai/の型・テスト件数・既存M005の「Repair二重
  ループ問題」の実例は、いずれも過去に実際に確認済みの事実。
- **推測**: Confidence閾値(0.8/0.5/0.3)、Revision改善閾値(0.05)、
  Domain分類confidence閾値(0.5)は、実運用データが無い現時点での
  **提案**であり、確定した仕様ではない(本文中に明記済み)。
- **提案**: Domain Knowledge保存方式(Python定義を採用)・World Model
  拡張フィールド・Template評価基準の重み付けは、いずれも設計上の
  提案であり、実装フェーズでCEO承認・詳細検討を経ることを前提とする。

---

## 5. 検証(実行結果、事実)

```
$ python -m unittest discover -s backend/tests -p "test_*.py"
Ran 265 tests in 0.029s
OK (skipped=17)

$ python -m unittest discover -s forge_ai/tests -p "test_*.py"
Ran 80 tests in 0.016s
OK
```

新規に作成したファイル23件は全てMarkdown(`docs/spec/`・`docs/adr/`・
`docs/diagrams/`・`docs/examples/`)であり、Python/Dartコードは一切
含まれない(確認済み)。Flutterのbrace整合性も再確認し、無変更である
ことを確認した。

---

## 6. 完了条件

`docs/spec/FORGE_COGNITIVE_ARCHITECTURE_V2.md` 22章の完了条件
チェックリスト(18項目)を参照。全項目を満たしている。

---

## 7. CEOへの確認事項(次フェーズへの申し送り)

1. Hybrid方式(Option C)の採用、および20章の比較表の妥当性。
2. 6.1節のWorld Model拡張(Events/States/Permissions追加)を、
   forge_ai/へ実際に反映してよいか(後方互換な追加として設計済み)。
3. Confidence閾値・Revision改善閾値等の暫定数値について、実装着手前に
   さらに議論が必要か、実装後の運用データ待ちでよいか。
4. `backend/app/ai/native/`の精査(19章で明記した通り、今回は
   実施していない)を、M007着手前に別Taskとして行うべきか。
5. 実装(M007以降)の優先順位: Cognitive Pipeline全16段階を一度に
   実装するか、Ambiguity Detection・Design Critic等、価値の高い
   段階から段階的に実装するか。

## 9. 実物監査(2回目)による4点修正（2026-07-15追記）

CEOがmain spec 954行・ADR7件・図9件・例6件を実物監査し、Hybrid方式・
Decision Trace・Cognitive Revision/Schema Repair分離・M004/M005責務
境界は承認された上で、正式確定前に以下4点の文書修正を求められた。
**新規コードは追加していない。**

### 修正1: Cognitive Pipelineの段階数不一致(14→16)を解消
「全16段階」と記載しながら個別定義が14段階だった不一致を解消した。
Design Criticの後に「Cognitive Revision」「Human Confirmation /
Escalation」を独立段階として追加し(3.11節・3.12節)、真に16段階へ
統一した。3章・13章・図1・完了条件・自己レビューの記載を全て統一した。

### 修正2: Confidence/Ambiguityの優先順位統一
「Domain confidence<0.5→HIGH確認」(4.3節)と「confidence 0.3〜0.5未満
→Genericへフォールバック」(14.2節)が0.3〜0.5の範囲で矛盾していた。
以下の3段階優先順位へ統一した(4.3節)。

1. Privacy/Safety/Permission関連のHIGH ambiguity → confidenceに
   関わらず必ず確認。
2. Domain confidence<0.5 → 原則確認。
3. 低リスクかつ後から安全に変更可能な用途のみ → Genericで仮設計可。

副産物として、以前の「0.3」という追加閾値も廃止し、0.5・0.8の2閾値へ
整理した(14.2節)。図1・ADR-007・`docs/examples/05_welfare_support_
record.md`(この優先順位が実際に効くケース)へ反映した。

### 修正3: Ambiguity Detection失敗時の楽観的継続を廃止
「検出失敗→ambiguities=()→曖昧さ無しとして継続」という、Human
Override原則に反する挙動を廃止した。`detection_status="failed"`・
`overall_severity="unknown"`という明示的な状態を新設し(4.4節)、
Privacy/Health/Welfare/Reservation/Permission関連の可能性がある場合は
確認・安全停止、それ以外の低リスクな場合のみwarning付きで限定継続する
よう分岐を明文化した。

### 修正4: Application Planning/Template Selectionの二段階化
Application PlanningがDomain Registryの`recommended_patterns`を参照
しながらTemplate Selectionが独立した後続段階であるという、隠れた循環
依存を解消した。Application Planningの内部フェーズとして
「Preliminary Pattern Candidates」(Domain/Intent/Requirementsのみで
大まかに絞り込む)を新設し、Template Selectionは「Final Template
Selection」(確定したApplicationPlanの画面数等を使って最終決定)として
明確化した(3.8節・3.9節、ADR-008新設)。Preliminary/Final不一致時の
再計画は、Cognitive Revisionと**同じカウンタ・上限を共有**させ、新たな
独立ループを作らないことを明記した(12.4節・ADR-008、既存M005の
「Repair二重ループ問題」と同じ轍を踏まないため)。

### 監査で追加確認した軽微な不整合
本セッションでの独立監査により、ADR新設(7→8件)に伴う表記漏れを
2箇所(0章・21章)発見し修正した(完了条件チェックリストは既に8件と
正しく記載されていた)。

### 検証
```
$ python -m unittest discover -s backend/tests -p "test_*.py"
Ran 265 tests in 0.026s
OK (skipped=17)

$ python -m unittest discover -s forge_ai/tests -p "test_*.py"
Ran 80 tests in 0.013s
OK
```
無影響を再確認した。`backend/app/ai/native/`・Flutter・M005も無変更。

