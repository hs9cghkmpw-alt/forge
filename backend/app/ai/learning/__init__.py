"""Forge の**長期資産**（FORGE-020、2026-08-25）。

Base Model は交換可能である。交換しても残るものをここへ置く。

```
GenerationEpisode   一仕事の軌跡（何を調べ、何を作り、どう直したか）
TeacherComparison   Teacher と Local を**同じ物差し**で測った結果
TrainingGym         本番データだけで育てないための課題集
NovelBenchmark      training に入れていない未知課題での生成力
DatasetBuilder      Episode → 学習候補（品質Gateを通ったものだけ）
AdapterPromotion    Dataset → LoRA/Adapter → Benchmark → 昇格 / 巻き戻し
SelfExtension       足りない能力を、sandbox で作って昇格させる道
```
"""
