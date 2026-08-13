# Forge 詳細ロードマップ

CEO提示(2026-08-13)。**作業を始める前に必ずこれを見ること。**

会話から道具を作るForgeを、自由度・安全性・賢さを両立しながら
進化させるための計画。図版が原典であり、この文書はセッションを
またいでも参照できるようにするための転記である。

---

## 1. 全体方針(4原則)

| # | 原則 | 意味 |
|---|---|---|
| 1 | **Conversation is the product** | すべての体験は会話から始まり、会話の連続性と自然さを最優先する |
| 2 | **Capability ≠ Widget** | 能力を再利用可能な部品として設計し、組み合わせで価値を生む |
| 3 | **精度のために自由度を捨てない** | 型にはめず、多様な解法と表現を許容する |
| 4 | **自由度のために安全を捨てない** | Self-Extensionも安全境界・検証・ロールバックを前提に行う |

---

## 2. フェーズ別ロードマップ

### Phase 1 — 現在地の安定化 ✅ 完了(2026-08-13)

- [x] 戻るボタン修正(TD53)
- [x] Mock UX整理(TD54)
- [x] verify / Python環境改善
- [x] analyze差分確認(77件 → 0件)

### Phase 2 — Stateful User Correction ✅ 完了(2026-08-13)

- [x] `current_hypothesis` 保持
- [x] `correction_history` 保持
- [x] 承認 / 訂正 / 問題修正の判定
- [x] ACCEPT → BUILD 接続

### Phase 3 — Capabilityモデル化 ✅ ほぼ完了(2026-08-13)

- [x] Data / Transform / View / Encoding / Effect
- [x] Semantic Capability設計
- [x] Missing Primitive検出
- [~] Capability依存関係の整理 — 分解表(`_DECOMPOSITION`)まで。
      本格的なDependency Graphは未着手

### Phase 3.5 — Conversation Foundation 是正 ✅ 完了(2026-08-13、指示書007)

- [x] Problem → Need → Solution の順序(`ConversationPhase`)
- [x] Pending Hypothesisへの返答を優先
- [x] Missingを層から導出(単一の真実)
- [x] Acceptance判定(態度 → 対比 → 追加 → 対象)
- [x] Trust と Execution Readiness の軸分離
- [x] EXACT / FALLBACK / BLOCKED の3分類
- [x] Golden Flow(3ターン)のE2E固定

### Phase 4 — Vertical Slice検証 ← **現在ここ**

- [x] `transform.aggregate` の実装 — **Runtime描画まで到達**(2026-08-13)
      - Forge Language v1.9(`bar_chart.group_by` / `aggregate`)
      - Validator(v1.9、参照整合性・enum・条件付き必須)
      - Runtime(`forge_aggregate.dart`の純粋関数 + `bar_chart`が利用)
      - **未達**: Compiler接続(Plannerがこの形を選ぶ経路が無い)
- [ ] Smallest Useful Tool 代替 — `CapabilityAvailability.FALLBACK`まで。会話への接続は未
- [ ] 回帰テスト追加 — 集計分は完了(単体14 + Widget 7 + Validator 12)
- [ ] Conversation E2E検証(Compiler接続後)

**なぜここが次なのか**: `transform.aggregate` は、§56の「能力を足した」
基準(表現 → 検証 → コンパイル → 描画 → 使用)を**初めて満たせる**地点で
ある。現状は「表現 → 検証」で止まっている。

### Phase 5 — Local AI強化

- [ ] Need抽出 / Correction分類 / Capability推論 を Local AI へ
- [ ] Semantic RAG
- [ ] Geminiなしでも検証可能

### Phase 6 — Safe Self-Extension設計

- [ ] Composition Extension
- [ ] Declarative Extension PoC(**一部着手済み**: `capability_definition.py`)
- [ ] Trust / Versioning / Rollback
- [ ] Sandbox / Security Gate

### Phase 7 — 将来拡張

- [ ] Build-Time Extension
- [ ] Controlled Promotion
- [ ] Capability再利用分析
- [ ] User Feedback を進化へ反映

**期間感**: 短期(〜3ヶ月)/ 中期(3〜9ヶ月)/ 長期(9ヶ月〜)。

---

## 3. 会話から道具になる流れ

```
ユーザーの困りごと
  → Problem Discovery      会話から問題を見つけ出す
  → Need Model             必要な機能と価値を構造化
  → Solution Hypothesis    解決の仮説(複数案可)
  → User Correction        修正・追加・削除のフィードバック  ←「違う」は重要な信号
  → Accepted Product Spec  ユーザー承認済みの仕様
  → Capability Resolver    必要な能力を特定し既存と照合
  → 既存能力で作れる？
       ├ Yes → Product Planner → Compiler → Validator/Repair → Runtime → Usable Tool
       └ No  → Missing Primitive → Userと仕様確認 → Safe Extension Strategy
                → Candidate Capability → Validation/Test/Security Gate
                → 後続フェーズでForgeへ追加
```

---

## 4. 重要な論点と次の焦点

### A. 今すぐ直すべきポイント ✅ 全件対応済み(2026-08-13)

- [x] Problem理解より先にCapability提案しない → `ConversationPhase`
- [x] Correctionで他LayerのMissingを消さない → `missing`をプロパティ化
- [x] 「うん、地図でいい」を承認として扱う → stance判定
- [x] Documentation drift を減らす → STATUS / TD55 訂正

### B. Self-Extensionで守ること

- Product Spec と Platform Capability を分離
- User Feedback と Security Approval を分離
- Global Capability と Tool固有仕様を分離
- **任意コード実行を許さない**

### C. 最終ゴール

> 会話で仕様を育てる / 足りない能力を見つける / 安全に能力を増やす
> → **以前は作れなかったToolを作れるようにする**

---

## 横断原則

会話中心 / 安全第一 / 部品化・再利用 / 検証・観測 / 段階的拡張。

**すべての拡張は、安全境界・検証・ロールバックを前提に進める。**

---

## 関連文書

- `docs/spec/FORGE-SELF-EXTENSION-ARCH-REVIEW-v2.md` — Self-Extensionの定義と成立条件
- `STATUS.md` — 今どこまで動くか
- `TECH_DEBT.md` — TD56(Correction状態)/ TD57(派生状態の不在)/ TD58(Compiler未接続)
