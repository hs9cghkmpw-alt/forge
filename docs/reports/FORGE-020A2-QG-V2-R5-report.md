# FORGE-020A2 / GENERATED-UI-QG-V2-R5 Report

- Branch: `claude/forge-master-handoff-k46jns`
- Start HEAD: `29d7c0aa3bff2231bed9e67496f8c9331a40a766`
- Final HEAD: commit/push後にGitHubで確認
- Date: 2026-08-27
- Real Local Model runs: **0**
- Overall: **INCOMPLETE — Level 0は未PASS**

## Implementation / production wiring

`GenerationRecord.structure_provenance`を追加し、リクエスト中にLocal Providerが
応答した事実と、Software structureを実際に決めた主体を分離した。

```
pipeline entity_source
  → prompt_pipeline._structure_provenance
  → durable GenerationRecord
  → verify_local_model_level0.py
  → RealLocalModelRun.counts_as_real_local
```

Level 0はproduction `/generate`、AIRouter task観測、Validator、Evidence uid、
`generation_source=local_ai`に加え、`structure_provenance=local_ai`を必須とする。
deterministic Capability Plan / Curated fallbackが構造を作った場合はHTTP 200でも
`INVALID_PROBE`であり、runへ加算しない。

Level 0既定モデルは`qwen2.5:7b-instruct`。`bge-m3`はembedding専用で生成未使用。
モデルdownloadは行っていない。Windows UTF-8表示とscript/provider timeoutの
不一致も修正した。

## Tests / mutation

- focused: **105 passed**
- backend full: **1779 passed, 17 skipped**
- forge_ai full: **567 passed**
- ruff changed Python: PASS
- `git diff --check`: PASS
- mutation: deterministic Capability PlanをLOCAL_AIと同様に許可すると、専用
  偽PASS防止テストが`counts_as_real_local=True`となりFAIL。復元後green。

## Real machine Level 0

Ollama API/model availabilityを各公式実測前に確認した。Runtime 0.32.15、
model `qwen2.5:7b-instruct`、digest
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`。

- `level0-20260827-103251.json`: FAILED（Provider 120秒timeout、修正済み）
- `level0-20260827-103709.json`: INVALID_PROBE
- `level0-20260827-104126.json`: INVALID_PROBE
- `level0-20260827-104538.json`: INVALID_PROBE

後3件はproduction HTTP 200、Validator PASS、Evidence uid、
`generation_source=local_ai`まで通ったが、structureは決定的fallback由来だった。
したがって真のPASSではなく、**Real Local Model runs = 0**。

単独entity synthesisおよび一時的production診断では有効構造と
`entity_source=synthesized(generic)`を観測したが、公式Evidenceではないため
runへ加算していない。

## QG-V2-R5 visual status

この変更はEvidence/Level 0判定とCLIのみで、UI・renderer・Design Language・
generated-app appearanceを変更していない。新規visual captureは**対象外**。
既存Golden GateのFAIL状態は変更しておらず、R5 visual quality改善は
**INCOMPLETE**である。

## UNVERIFIED / Technical Debt / next task

- この文書作成時点ではcommit/push/CIはUNVERIFIED。handoff完了時にGitHubで確認。
- TD91: Entity synthesis不採用理由をraw応答なしの閉じたreason codeでdurable化。
- Level 0 Integrity条件を緩めず、公式Evidenceでstructure generationがLocal AI
  由来になった場合だけrunsを1へ更新する。
