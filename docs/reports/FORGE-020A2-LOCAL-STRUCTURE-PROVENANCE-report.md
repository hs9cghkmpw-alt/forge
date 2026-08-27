# FORGE-020A2 Local Structure Provenance Report

- Branch: `claude/forge-master-handoff-k46jns`
- Start HEAD: `29d7c0aa3bff2231bed9e67496f8c9331a40a766`
- Final HEAD: **UNCOMMITTED**
- Date: 2026-08-27
- Real Local Model runs: **0**

## Outcome

`GenerationSource.LOCAL_AI`だけではLevel 0の証拠にならないことを修正した。
後段のDesign IntentでLocal Modelが応答しても、Software structureを
deterministic Capability PlanまたはCurated fallbackが作ったなら数えない。
`GenerationRecord.structure_provenance`をproduction pathへ配線し、
`RealLocalModelRun`は`LOCAL_AI`を必須とする。決定的構造は`INVALID_PROBE`。

## Production wiring

`pipeline_orchestrator`の`entity_source` → `prompt_pipeline`の閉じた分類 →
durable `GenerationRecord.structure_provenance` → Level 0 script →
`RealLocalModelRun.counts_as_real_local`。ValidatorとEvidence uidも従来どおり必須。

## Tests and mutation

- 関連: 70 passed。その後の追加修正: 46 passed。
- backend全体: 1778 passed, 17 skipped。
- ruff: changed Python files clean。
- mutation: deterministic Capability PlanをLOCAL_AI同様に許可するようguardを
  意図的に変更すると、専用テストが`counts_as_real_local=True`でFAIL。復元後green。
- UI変更なし。visual evidenceは対象外。

## Real machine evidence

Ollama APIで0.32.15、`qwen2.5:7b-instruct`、digest
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`を確認。
`bge-m3:latest`はavailabilityだけ確認し、生成には使用していない。downloadなし。

1. `103251`: FAILED。script 180秒よりproduction Provider 120秒が先にtimeout。
2. `103709`, `104126`, `104538`: HTTP 200、Validator PASS、Evidence uid、
   `generation_source=local_ai`まで到達したが`structure_provenance=curated`。
   公式判定はINVALID_PROBE、runs 0。

単独entity synthesisと一時的production診断では有効構造の採用および
`entity_source=synthesized(generic)`を確認したが、公式Level 0 Evidenceでは
ないためrunに加算していない。

## Unverified / debt / next task

commit、push、CIは未実施。TD91として、raw応答を保存せずEntity synthesisの
不採用reason codeをdurableに残す。判定条件を緩めず公式PASSを再測定する。
