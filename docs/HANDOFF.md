# Forge 申し送り（最新）

**最終更新: 2026-08-25**

**branch:** `claude/forge-master-handoff-k46jns`

**start HEAD:** `7f31aa46785d6db7fbcc4bbf7097b9bd889c927e`

**final HEAD:** この文書を含むFORGE-018 commit（Git logの先頭を正とする）

**current phase:** Growing AI / Learning Event Foundation

**current task:** FORGE-018 commit E — 実装・ローカル検証完了、push/CI確認中

**next task:** FORGE-019 Semantic Design Revision

## 継続中のCEO依頼

- 過去にチャットへ貼られたOpenAI API keyは使用・保存していないが、失効と
  再発行が必要。新keyはチャットでなく`backend/.env`へ直接設定する
- CEO環境でCORS障害が続く場合はブラウザconsoleの実エラーが必要

## 現在地

既存の`ExperienceRecord` / `GenerationRecord` / `RevisionRecord` /
`ArtifactFeedbackEvent`をSource of Truthのまま維持し、全Storeの記録直後が
単一の`LearningEventProjector`を必ず通るProduction Pathを実装した。

```
AI call / generation / POST /feedback
  → existing append-only evidence
  → LearningEventProjector（入口1つ）
  → Local LearningEvent（raw本文なし）
  → Consent + Sanitizer + TrainingEligibilityPolicy
  → ExportDecision + DatasetCandidate lineage
  → CloudLearningEnvelope outbox（全条件成立時のみ）
```

Production既定は`PERSONAL / LOCAL_ONLY / contribution NONE /
training_use UNKNOWN`、Consentは6カテゴリすべてOFF。通常のHTTP実行でLocal
Eventと拒否理由付きDataset Candidateは残るが、Cloud Outboxは0件である。

## 実装内容 / Production wiring

- `LearningEvent` Production型、単一Projector、Local Event Store
- AI_CALL / GENERATION / FEEDBACKのProduction emit
- Revision projector（Store入力対応のみ。`/update`配線はFORGE-019）
- 6カテゴリ`ConsentSnapshot`（既定ALL OFF）
- Local Eventと`CloudLearningEnvelope`を別型に分離
- `ContributorIdentityProvider`境界（Production実装なし、fail closed）
- `AppIdentity` / `AppTrustTier`の最小trust boundary
- Learning Sanitizer、Retention、Learning Artifact契約、Dataset lineage
- 中央`TrainingEligibilityPolicy`
- `knowledge_references`を本文なしでEventへ継承

FastAPI `TestClient`で`POST /generate`からAI_CALLとGENERATIONを確認。同じ
artifactへ`POST /feedback`でACCEPTED→CORRECTEDを送り、FEEDBACK 2件が順番を
保って残ることを確認した。実測はAI_CALL 1 / GENERATION 1 / FEEDBACK 2 /
Dataset Candidate 4 / Cloud Outbox 0。Client handle/version tokenはCloud型に
存在しない。

FlutterはBackendのartifact handle/version tokenを`GenerationSuccess`へ保持
していない。ボタンだけ足すと対象世代を安全に指せないため今回は追加せず、
Backend API contractを固定した。FORGE-019でDomain層とhost previewを接続する。

## Consent / Privacy / Cloud

- 同意なしでもLocal Evidence / Local Event / Forge基本機能は動く
- withdrawal後は未送信Outboxを消し、将来exportを止める
- 既学習weightのunlearningは未実装
- LearningEventにraw発話/会話/response/Document/secret/handle/tokenは無い
- Sanitizerは明白なsecret/PIIを拒否するが100%除去とは主張しない
- Supabase送信、migration、RLS、Auth、Object Storage送信は未実装
- Production Cloud exportはserver-issued identity不在のためblocked
- Test DoubleでのみEnvelope生成を実証

## Tests

- FORGE-018 focused: **18 passed**
- backend full: **1424 passed, 17 skipped**
- forge_ai full: **521 passed**
- ruff（変更Python）: **All checks passed**
- Flutter test: **508 passed**
- flutter analyze: **No issues found**
- flutter build web: **成功**（font warningあり、既知の非致命warning）
- CI: push前、未実行

## Intentional break / mutation

13 roundすべてでFAILを確認し、復元後focused 18件PASS:

1. Experience→Projector配線を外す
2. Consent既定をON
3. UNKNOWN/FORBIDDEN training_useを許可
4. TEST_DOUBLEを許可
5. Feedback 2件目を捨てる
6. `raw_output` fieldを追加
7. LOCAL_ONLYをCloudへ通す
8. sanitizer失敗を無視
9. `knowledge_references`を落とす
10. `artifact_handle` fieldを追加
11. fake client contributor IDを許可
12. untrusted appのGlobal寄与を許可
13. expired Eventを許可

## 未検証 / Technical Debt

- Outboxはin-memoryでdurableではない
- Supabase learning tables / RLS / Auth / server identity未実装
- 実Cloud送信0件。実Local Model生成0回
- Flutter feedback UI未実装（artifact identityがDomain層で失われる）
- Learning Artifactは契約のみ。Dataset CandidateはTraining Datasetではない
- token usage等、既存Evidenceが持たない値はNone

## 次のTask / 次の3手

次はFORGE-019 Semantic Design Revision。「残高をもっと目立たせて」等を
Target resolution → typed operation → local patch → Validator/Critic → Revision
Evidence → Feedback → Learning EventまでProductionで閉じる。

1. Flutter Domain層へartifact handle/version tokenを通し、「これでOK」/
   「直したい」を`POST /feedback`へ接続
2. `/update`を`RevisionRecord`へ接続し、局所Semantic Patchを実装
3. Auth/RLS/server identity実測後、durable Supabase Outboxを実装
