"""生成物についてのEvidence
(FORGE-PRE-R1-INTEGRITY-GATE-013 §4、2026-08-17)。

---

## なぜ`ExperienceRecord`では足りないのか

R0で入れた`ExperienceRecord`は **「1回のAI呼び出しについての事実」**
である。Provider・model・latency・構造化出力の妥当性・Validatorの合否・
利用者の承認/訂正を持つ。

これで測れないものが1つある。

    AIを1回も呼ばずに作られた、良い生成物

実測(2026-08-17、TD65):

| 経路 | 生成stageのAI呼び出し | 残る記録 |
|---|---|---|
| Curated Domain | **0回** | 生成物についての記録は**無い** |
| Generated Domain | 数回 | AI呼び出しの記録に付随して残る |

Curated経路は、**0.01秒・Quota消費0・Validator合格**でアプリを作る。
これは弱点ではなく長所である。しかしForgeは、その成功を
**学習素材として残す場所を持っていなかった**。

### やってはいけない解き方

学習データを作るためだけに、Curatedにも無理やりAIを通す。

これは本末転倒である。速くて安定していて無料な経路を、記録の都合で
遅く・不安定に・有料にすることになる。**記録の形が実行の形を歪めて
いる**という、設計として逆立ちした状態になる。

## 採る形

**AI呼び出しの記録**と、**生成物の記録**を分ける。

    ExperienceRecord   1回のAI呼び出しについての事実（R0、既存）
    GenerationRecord   1つの生成物についての事実（ここ、新規）

`GenerationRecord.source`が由来を持つので、
「Curatedで作った成功例」も「Cloud AIで作った成功例」も、
**同じ形のEvidence**として並ぶ。Local AIの学習では、

    このNeed（の構造的特徴）に対して
    この Capability / Design Language / Forge Language 構造は
    Validatorを通り、Runtimeで動き、利用者に受け入れられた

という単位で使う。これはAIを呼んだかどうかと**独立**である。

## Privacy境界は`ExperienceRecord`と同じ（006 §22）

**利用者の発話も生成物本文も持てない型にしてある。** 持つのは

* 何の種類の問題だったか（domain識別子）
* どんな構造だったか（capability / design roleの**識別子の集合**）
* 検証がどうだったか（Validator / Runtime / 利用者の反応）

であり、`str`の自由入力欄は`source`・`domain`・`forge_language_version`
（いずれも識別子）に限る。テストが型で固定している。

## Curatedの出力をTruthとして固定しない

Product Direction §5 は「Cloud出力はTeacher Candidateであって
Truthではない」と決めている。**Curatedも同じ扱いにする。**

`GenerationRecord`は「Curatedがこう作った」という事実を持つだけで、
「それが正解である」とは言わない。正解の根拠は`validator_passed` /
`runtime_success` / `user_acceptance` の側にある。

家計簿Templateを教師のTruthとして焼き込むと、Product Direction §4が
禁じた「有限Template選択システムへの退化」を、**学習側から**招く。

## 現時点の実装範囲（正直な申告）

**Production配線済み。** `PromptPipeline`が生成を終える地点
（`/generate`・`/converse` BUILDの両方が必ず通る唯一の場所）で1件残す。
Validator不合格でも残す。実測で確認済み:

```
{"source":"curated",  "domain":"household_budget", "ai_calls":0, "validator_passed":true}
{"source":"cloud_ai", "domain":"diary",            "ai_calls":1, "validator_passed":true}
```

**当初はR1へ先送りするつもりだった**——`design_language_roles`が
実在しないので粒度が足りない、という理由である。しかしそれは
「作ったが本番から呼ばれない」を5回目にする判断だったので、
やめて今つないだ。粒度が足りないなら**足りないまま残す**方がよい。

埋まっていないもの（**空であることが事実であり、欠損ではない**）:

* `capabilities` / `design_language_roles` — R1でDesign Languageが
  実在するようになったら埋まる
* `runtime_outcome` — Flutter側から結果が戻る経路がまだ無い
* `user_acceptance` — 生成物に対する明示的な承認を、UIがまだ聞かない

配線しない経路（意図的）:

* `/update` — 既存文書の**変更**であって生成ではない。同じ表へ混ぜると
  「生成の成功率」が変更の成功率で薄まる
"""

from __future__ import annotations

from app.ai.gateway.capability_evidence import (
    CapabilityUsage,
    CapabilityUsageSource,
    CapabilityUsageStatus,
    GenerationStructureSource,
    StructureProvider,
)

import time
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from uuid import uuid4

from app.ai.gateway.learning_foundation import AcceptanceSignal

__all__ = [
    "DesignDecisionSource",
    "DesignRoleDecision",
    "GenerationEvidenceStore",
    "GenerationRecord",
    "GenerationSource",
    "StructureProvenance",
    "StructureProvider",
    "CapabilityUsageEvidence",
    "CapabilityUsageStatus",
    "CapabilityUsageSource",
    "source_for_generated",
    "RuntimeOutcome",
    "default_generation_store",
]


class GenerationSource(str, Enum):
    """その生成物を**誰が作ったか**。

    Local AIの学習では、これで層別する必要がある。Curatedの成功を
    「AIが上手くやった」と数えると、AIの実力を過大評価する。
    """

    CURATED = "curated"
    """Curated Domain Libraryのルールベース生成。AI呼び出し0回。"""

    CLOUD_AI = "cloud_ai"
    """Cloud Providerが構造を決めた。**Teacher Candidateであって
    Truthではない**(Product Direction §5)。"""

    LOCAL_AI = "local_ai"
    """Forge自身のLocal Modelが構造を決めた。まだ発生しない。"""

    COMPOSITION = "composition"
    """Curatedを土台にAIが調整した等の複合。TD65の解決案1がこれ。"""

    TEST_DOUBLE = "test_double"
    """Mock等のテスト専用Providerが作った(014 §2で追加)。

    **`CLOUD_AI`にも`LOCAL_AI`にも入れてはならない。** `mock`は
    Registry上`deployment=local`だが、これを`LOCAL_AI`として数えると
    「Local AIはもう十分な実績がある」という嘘の統計ができあがり、
    Local Routingへの昇格判断が壊れる。Cloudへ入れれば同じことが
    Cloud側で起きる。

    **どちらでもない**ので、専用の値を持つ。"""

    UNKNOWN = "unknown"
    """**既定値。** 由来が記録されていない。

    学習に使ってよいかを判断する経路では通さない
    (`TrainingProvenance.UNKNOWN`と同じ姿勢)。"""

    @property
    def is_usable_for_training(self) -> bool:
        """由来が分かっていて、かつ**本物**か。

        `TEST_DOUBLE`は由来が分かっているが、学習には使えない
        ——Mockの出力を教師にすると、Mockの癖を学ぶことになる。
        """
        return self not in {GenerationSource.UNKNOWN, GenerationSource.TEST_DOUBLE}

    @property
    def is_ai_generated(self) -> bool:
        """AIが構造を決めたか。Curated/Test Doubleは`False`。"""
        return self in {
            GenerationSource.CLOUD_AI,
            GenerationSource.LOCAL_AI,
            GenerationSource.COMPOSITION,
        }


#: **構造を誰が作ったか** の型は1箇所にしか置かない
#: （020A2 と 020A3 の merge、2026-08-27）。
#:
#: 両者が別々に同じ enum を書いていた。同じ値の enum が2つあると
#: `is` 比較が常に False になる——TD85 で実際に踏んだ形である。
#: ここは**別名**であって、写しではない。
StructureProvenance = GenerationStructureSource
CapabilityUsageEvidence = CapabilityUsage


def source_for_generated(provider_used: str | None) -> GenerationSource:
    """**実際に構造生成へ成功したProviderの事実**から由来を決める
    (014 §2)。

    ---

    ## 直した問題

    013では`domain_resolution == "generated"`を無条件に`CLOUD_AI`へ
    写していた。しかし`generated`が表しているのは

        「決定的なCurated生成ではなかった」

    ということだけである。**誰が作ったかは言っていない。** この対応の
    ままLocal AIが構造を作るようになると、その実績が丸ごとCloud AIの
    成績として記録される——Local Routingへの昇格判断の根拠が、
    最初から汚染される。

    ## 判定の順序（順序に意味がある）

    1. **`test_only`** — Mockは`deployment=local`だが、`LOCAL_AI`に
       するとLocal AIの実績を水増しする。**先に弾く**
    2. **`deployment`** — Registryが持つ事実。LOCAL / CLOUD
    3. それ以外（未登録・Provider不明） — `UNKNOWN`

    ## やらないこと

    * `ai_calls > 0`だからCloud、という推測
    * Model名の文字列からlocal/cloudを判定（`llama`が入っていれば
      Local、のような判定はProviderをまたぐと必ず外れる）
    * 分からないものを楽観側へ倒す
    """
    from app.ai.gateway.provider_registry import (  # noqa: PLC0415 — 循環import回避
        Deployment,
        definition_for,
    )

    if not provider_used:
        return GenerationSource.UNKNOWN
    definition = definition_for(provider_used)
    if definition is None:
        # Registryに宣言が無い名前。テストのFake等。**推測しない。**
        return GenerationSource.UNKNOWN
    if definition.test_only:
        return GenerationSource.TEST_DOUBLE
    if definition.deployment is Deployment.LOCAL:
        return GenerationSource.LOCAL_AI
    if definition.deployment is Deployment.CLOUD:
        return GenerationSource.CLOUD_AI
    return GenerationSource.UNKNOWN


class RuntimeOutcome(str, Enum):
    """Runtimeで実際にどうなったか。

    `UNKNOWN`が既定である——**「落ちなかった」と「確かめていない」を
    混同しない**。Runtime Evidenceは、現時点ではFlutter側から戻って
    こないので、当面ほとんどが`UNKNOWN`になる。それが事実である。
    """

    RENDERED = "rendered"
    """描画まで到達した。"""

    FAILED = "failed"
    """Runtimeで落ちた。**強い負例**である。"""

    UNKNOWN = "unknown"
    """**既定値。** 確かめていない。"""

    @property
    def is_usable_as_supervision(self) -> bool:
        return self is not RuntimeOutcome.UNKNOWN


class DesignDecisionSource(str, Enum):
    """その意味的役割を**誰が決めたか**(FORGE-R1-CLOSURE-015 §4、2026-08-17)。

    ---

    ## なぜ分けるのか

    `design_language_roles`は最終的に使われたrole一覧しか持たない。
    だから記録を後から見ても

        screen_density = density.compact

    が**AIが選んだ結果**なのか、**AIが答えられずForgeが既定で埋めた
    結果**なのかが分からない。

    そのままLocal AIの教師データにすると、**Forgeの既定値をAIの成功例
    として学習する**ことになる。「このNeedではcompactが良い」とAIが
    判断した事実は1つも無いのに、そう記録されてしまう。

    `DesignIntent`の内部には`fallback_axes`として区別が存在していた。
    **Evidenceへ渡すところで消えていた**ので、そこを繋ぐ。
    """

    AI = "ai"
    """AIが選び、Forgeの検証を通った。**唯一「AIの成功例」と呼べるもの。**"""

    DETERMINISTIC = "deterministic"
    """Compilerが構造から決めた(見出し・一覧・ボタン)。
    AIの手柄ではないが、間違いでもない——構造から一意に決まる。"""

    FALLBACK = "fallback"
    """AIへ聞いたが採れなかったので既定値で埋めた。
    **AIの選択が受け入れられた証拠にはならない。**"""

    CURATED = "curated"
    """人手で書いたCurated定義に由来する。"""

    USER_CORRECTION = "user_correction"
    """**利用者が「違う」と言って直させた。**（FORGE-016A §4、2026-08-24）

    AIの選択でもForgeの既定でもなく、**利用者の意思**である。

    これを`AI`と混ぜてはならない——「AIがelevatedを選んで受け入れられた」
    と「AIはcardを選んだが利用者がelevatedへ直させた」は、Local AIに
    とって正反対の教師信号である。前者はAIの成功例だが、後者はAIの
    **失敗例**であり、同時に「利用者が何を望むか」の正例である。"""

    UNKNOWN = "unknown"
    """由来を記録し損ねた。**既定値。** 楽観側(AI)へ倒さない。"""

    @property
    def is_ai_evidence(self) -> bool:
        """AIの選択の成否を語ってよいか。

        **`USER_CORRECTION`は含まない。** 利用者が直したものは、AIが
        選んで受け入れられた証拠ではない（むしろAIが外した証拠である）。
        """
        return self is DesignDecisionSource.AI


@dataclass(frozen=True)
class DesignRoleDecision:
    """1つの軸について「どのroleが、誰の判断で選ばれたか」。

    **識別子しか持たない。** Promptも、Providerの生出力も、利用者の
    発話も入らない(`ExperienceRecord`と同じPrivacy境界、006 §22)。
    """

    axis: str
    """`screen_density`等。何についての判断か。"""

    role: str
    """`density.compact`等。選ばれた意味。"""

    source: DesignDecisionSource = DesignDecisionSource.UNKNOWN

    def to_dict(self) -> dict[str, str]:
        return {"axis": self.axis, "role": self.role, "source": self.source.value}


@dataclass(frozen=True)
class GenerationRecord:
    """1つの生成物についての**Forgeの振る舞いの事実**。

    **`ExperienceRecord`と同じPrivacy境界を持つ**(006 §22)。
    利用者の発話も、生成されたForge Documentの本文も、この型では
    表現できない。持つのは識別子と検証結果だけである。
    """

    source: GenerationSource
    domain: str
    """どの種類の問題だったか。**利用者の言葉ではなく**、Forgeが
    分類した識別子(`household_budget`等)。"""

    validator_passed: bool
    """Forge Language Validatorを通ったか。"""

    capabilities: tuple[str, ...] = ()
    """使われたCapabilityの識別子。**値ではなく名前**。

    **これは古い契約である。Source of Truth は `capability_usage` の方**
    （020A3B §5、2026-08-27）。新しく読む側は typed の方を読むこと。

    ---

    ## 接頭辞の意味（読む側が必ず守ること）

    | 形 | 意味 |
    |---|---|
    | `view.list` | **全部出来て、実際に使った** |
    | `partial:data.photo` | 出来たが本来の形ではない |
    | `unsupported:simulate.loop` | 求められたが**持っていない** |

    **素の ID と `partial:` が同じ ID について両方入ることはない。**
    以前は両方入っており、素の並びだけを読む利用者が
    「写真を扱えた」を成功例として学習しうる状態だった
    （`test_forge_020a3b_partial_is_not_success.py` が固定する）。

    ## なぜ残してあるか

    「持っていなかった」という事実も学習の材料だからである。
    ただし接頭辞を parse させる設計は脆い——だから
    `capability_usage` が `status` を**欄で**言う。

    Dataset Builder / Local AI の学習は `capability_usage` を読むこと。
    """

    entity_synthesis_attempted: bool = False
    """AI の Entity 合成を**試したか**（020A3）。"""

    entity_synthesis_accepted: bool = False
    """試した結果を**受け取ったか**。試していないときも False なので、
    `entity_synthesis_attempted` と併せて読む。"""

    entity_synthesis_rejection_reason: str | None = None
    """落とした理由。`EntitySynthesisRejectionReason` の値。

    「試したが落とした」と「そもそも試していない」を区別できないと、
    Local Model が伸びているのかどうかが分からない。"""

    entity_synthesis_raw_schema_valid: bool = False
    entity_synthesis_repairs: tuple[str, ...] = ()
    entity_synthesis_fields_received: int = 0
    entity_synthesis_fields_accepted: int = 0
    entity_synthesis_strict_contract_passed: bool = False
    entity_synthesis_structured_output_mode: str = ""
    """020A4C: Model 自身の契約能力と Forge repair を分離した構造 Evidence。

    生 Prompt / 生 Model 出力 / 利用者本文は持たない。未知は fail-closed。
    """

    design_language_roles: tuple[str, ...] = ()
    """選ばれたDesign Languageの役割(`metric.primary`等)。

    R1で実在するようになる。それまでは空——**空であることが
    「まだ語彙が無い」という事実**であり、埋めるべき欠損ではない。"""

    visual_structure: dict[str, object] = field(default_factory=dict)
    """生成物の**構造についての決定的な事実**(§10)。

    主KPIが何個あるか、意味が付いている割合、階層の深さ——「美しい」を
    測ったものではない。名前を`visual_quality`にしなかったのはそのため
    である(測れていないものを測ったことにしない)。

    それでも`UNKNOWN`のまま置くよりはよい。**後から「どういう構造の
    生成物が受け入れられたか」を突き合わせられる**、機械的に再現できる
    事実である。"""

    design_decisions: tuple[DesignRoleDecision, ...] = ()
    """軸ごとの「誰が決めたか」(FORGE-R1-CLOSURE-015 §4)。

    `design_language_roles`が**結果**の一覧であるのに対し、こちらは
    **由来**を持つ。片方だけでは、Forgeの既定値をAIの成功例として
    学習してしまう。"""

    forge_language_version: str = ""
    """生成時のForge Languageのバージョン。仕様が動くので、
    どの仕様下で成立した構造なのかが分からないと後から使えない。"""

    runtime_outcome: RuntimeOutcome = RuntimeOutcome.UNKNOWN
    user_acceptance: AcceptanceSignal = AcceptanceSignal.UNKNOWN
    """`ExperienceRecord`と**同じEnumを使う**。会話側の判定を1つの
    語彙で扱うためであり、ここだけ別の名前にすると突き合わせられない。"""

    repair_attempts: int = 0
    ai_calls: int = 0
    """この生成物のために呼んだAIの回数。**Curatedなら0**。
    0が異常値ではないことが、この型を作った理由である。"""

    structure_source: GenerationStructureSource = GenerationStructureSource.UNKNOWN
    """**その文書の構造を誰が作ったか**（FORGE-020A2 §3、2026-08-26）。

    `source`（誰が生成したか＝Provider の話）とは**別の軸**である。

    R4 以降、`Capability Plan → 決定的な EntitySpec → IR` で構造が
    決まったあと、**Design Intent だけ AI を呼ぶ**ことがある。その状態で
    `last_provider_used == "local"` を見て `LOCAL_AI` にすると、
    「Local Model が構造を決めた」という**嘘の Evidence**になる。

    Level 0 はこちらを見る。`DETERMINISTIC_CAPABILITY_PLAN` は
    「Local Model が構造生成を担当した」ではない。
    """

    structure_provider: StructureProvider = StructureProvider.NONE
    """構造を作った段が**実際に**使った Provider の種類。

    決定的に組んだときは `NONE` である——**空文字にしない**（020A3）。
    「記録し忘れ」と「AI を呼んでいない」が同じ値になると区別できない。
    """

    structure_task: str = ""
    """構造を作った段の `ForgeTask`。**手で書かない**——観測した値を入れる。"""

    capability_usage: tuple[CapabilityUsage, ...] = ()
    """Capability ごとの事実（FORGE-020A2 §4）。

    `capabilities`（ID の並び）では、**求められた / 実際に使われた /
    一部だけ / 無かった**の4つが区別できない。将来 JSONL Dataset へ
    落とすときに必要になるので、型で持つ。**値は入らない。**
    """

    knowledge_references: tuple[str, ...] = ()
    """この生成に渡した知識の**識別子と版**(FORGE-016A commit D)。

    `design_role.metric.primary@v1`のような形。**本文は入らない**
    (016 §12.1「raw retrieved textではなくIdentifierだけ」)。

    残す理由は、知識を直したあとで「どの版の知識で作られたものか」を
    辿れるようにするためである。辿れないと、生成物の品質が上がった/
    下がったときに、知識の変更が効いたのかAIが変わったのかを分けられ
    ない。

    空は「知識を渡していない」——会話ステップのようにDesign Language
    を必要としないTaskでは、それが正しい状態である。
    """

    recorded_at: float = 0.0
    ref: int = 0

    uid: str = ""
    """**Dataset Lineage用の永続ID**(FORGE-017A §3、2026-08-24)。

    `ref`との違いが要点である。

    * `ref` … `GenerationEvidenceStore`**内の位置**。プロセスを跨いで
      意味を持たない。プロセス内でこの記録を引くためのもの
    * `uid` … この**記録そのもの**の身元。記録に貼り付いて動くので、
      書き出しても・別のStoreへ移しても同じものを指す

    Learning Event / Dataset の系譜（どのEventからどのDatasetを作ったか）
    は`uid`で辿る。`ref`で辿ると、プロセスが再起動した瞬間に
    **別の生成物を指すID**になる（1番は次のプロセスでも1番だが、
    中身は別物である）。

    Clientへ渡すハンドル(`ArtifactHandle`)とも別物である
    ——あちらは失効する capability であり、系譜のIDではない。
    """

    @property
    def is_positive_example(self) -> bool:
        """教師データの候補になるか。

        **Validator合格だけでは足りない。** 利用者が明示的に受け入れた
        ものだけを正例とする(Product Direction §5、011 §5と同じ基準)。
        由来不明のものも除く。
        """
        return (
            self.validator_passed
            and self.user_acceptance.is_positive
            and self.source.is_usable_for_training
            and self.runtime_outcome is not RuntimeOutcome.FAILED
        )

    @property
    def ai_selected_roles(self) -> tuple[DesignRoleDecision, ...]:
        """**AIが選んだものだけ。** Local AIの教師データはここから採る。

        `design_language_roles`をそのまま使うと、Forgeが既定で埋めた
        roleまで「AIの成功例」に混ざる(§4.3)。
        """
        return tuple(d for d in self.design_decisions if d.source.is_ai_evidence)

    @property
    def fallback_roles(self) -> tuple[DesignRoleDecision, ...]:
        """AIが答えられなかった軸。**どこが弱いか**が分かる。"""
        return tuple(
            d for d in self.design_decisions
            if d.source is DesignDecisionSource.FALLBACK
        )

    def to_dict(self) -> dict[str, object]:
        """診断・集計用。**本文が現れないことが不変条件である。**"""
        return {
            "ref": self.ref,
            "uid": self.uid,
            "source": self.source.value,
            "domain": self.domain,
            "validator_passed": self.validator_passed,
            "capabilities": list(self.capabilities),
            "entity_synthesis_attempted": self.entity_synthesis_attempted,
            "entity_synthesis_accepted": self.entity_synthesis_accepted,
            "entity_synthesis_rejection_reason": self.entity_synthesis_rejection_reason,
            "entity_synthesis_raw_schema_valid": self.entity_synthesis_raw_schema_valid,
            "entity_synthesis_repairs": list(self.entity_synthesis_repairs),
            "entity_synthesis_fields_received": self.entity_synthesis_fields_received,
            "entity_synthesis_fields_accepted": self.entity_synthesis_fields_accepted,
            "entity_synthesis_strict_contract_passed": self.entity_synthesis_strict_contract_passed,
            "entity_synthesis_structured_output_mode": self.entity_synthesis_structured_output_mode,
            "design_language_roles": list(self.design_language_roles),
            "design_decisions": [d.to_dict() for d in self.design_decisions],
            "structure_source": self.structure_source.value,
            "structure_provider": self.structure_provider.value,
            "structure_task": self.structure_task,
            "capability_usage": [u.to_dict() for u in self.capability_usage],
            "knowledge_references": list(self.knowledge_references),
            "visual_structure": dict(self.visual_structure),
            "forge_language_version": self.forge_language_version,
            "runtime_outcome": self.runtime_outcome.value,
            "user_acceptance": self.user_acceptance.value,
            "repair_attempts": self.repair_attempts,
            "ai_calls": self.ai_calls,
            "recorded_at": self.recorded_at,
        }


class GenerationEvidenceStore:
    """`GenerationRecord`の保持。

    `ExperienceStore`と同じ形にしてある——後から書き足せること、
    プロセス内メモリのみ(TD41)、上限を超えたら古い順に捨てること。
    """

    _MAX_RECORDS = 1000

    def __init__(self, *, now: object = time.time) -> None:
        self._records: dict[int, GenerationRecord] = {}
        self._next_ref = 1
        self._now = now

    def record(self, entry: GenerationRecord) -> GenerationRecord:
        if entry.recorded_at <= 0:
            entry = replace(entry, recorded_at=self._now())
        # **uidはStoreが付ける。** 呼び出し側に任せると、付け忘れた記録が
        # 系譜から静かに落ちる(「呼び出し側が忘れずに呼ぶ」設計にしない)。
        entry = replace(entry, ref=self._next_ref, uid=entry.uid or uuid4().hex)
        self._next_ref += 1
        self._records[entry.ref] = entry
        while len(self._records) > self._MAX_RECORDS:
            del self._records[next(iter(self._records))]
        from app.ai.gateway.learning_events import observe_evidence  # noqa: PLC0415
        observe_evidence(entry)
        return entry

    def note_user_acceptance(self, refs: Sequence[int], signal: AcceptanceSignal) -> int:
        """利用者がその生成物をどう扱ったか。

        `ExperienceStore.note_acceptance()`と同じ規則——**先に書かれた
        信号が勝つ**、`UNKNOWN`は上書きの理由にならない。
        """
        if signal is AcceptanceSignal.UNKNOWN:
            return 0
        written = 0
        for ref in refs:
            existing = self._records.get(ref)
            if existing is None or existing.user_acceptance is not AcceptanceSignal.UNKNOWN:
                continue
            self._records[ref] = replace(existing, user_acceptance=signal)
            written += 1
        return written

    def note_runtime_outcome(self, refs: Sequence[int], outcome: RuntimeOutcome) -> int:
        if outcome is RuntimeOutcome.UNKNOWN:
            return 0
        written = 0
        for ref in refs:
            existing = self._records.get(ref)
            if existing is None or existing.runtime_outcome is not RuntimeOutcome.UNKNOWN:
                continue
            self._records[ref] = replace(existing, runtime_outcome=outcome)
            written += 1
        return written

    def get(self, ref: int) -> GenerationRecord | None:
        """1件を引く(FORGE-016A §3)。

        `ArtifactFeedbackService`が「もう評価が付いているか」をここで
        確かめる。Service側に写しを持つと、Storeだけをresetしたときに
        食い違う——**Storeを唯一の真実にする**ために必要な口である。
        """
        return self._records.get(ref)

    def all_records(self) -> tuple[GenerationRecord, ...]:
        return tuple(self._records.values())

    def training_candidates(self) -> tuple[GenerationRecord, ...]:
        """教師データの候補。**判断はここでしない**——条件は
        `GenerationRecord.is_positive_example`が持つ。"""
        return tuple(r for r in self._records.values() if r.is_positive_example)

    def summary_by_source(self) -> dict[str, dict[str, object]]:
        """由来別の集計。

        **Curatedの成功をAIの成功として数えない**ために、必ず
        `source`で割る。混ぜると、Local AIを昇格させてよいかの判断が
        Curatedの成績で押し上げられる。
        """
        summary: dict[str, dict[str, object]] = {}
        for source in GenerationSource:
            entries = [r for r in self._records.values() if r.source is source]
            if not entries:
                continue
            total = len(entries)
            summary[source.value] = {
                "samples": total,
                "validator_pass_rate": round(
                    sum(1 for r in entries if r.validator_passed) / total, 3
                ),
                "explicit_acceptance_rate": round(
                    sum(1 for r in entries if r.user_acceptance.is_positive) / total, 3
                ),
                "training_candidates": sum(1 for r in entries if r.is_positive_example),
                "mean_ai_calls": round(sum(r.ai_calls for r in entries) / total, 2),
            }
        return summary

    def reset(self) -> None:
        self._records.clear()


_default_store: GenerationEvidenceStore | None = None


def default_generation_store() -> GenerationEvidenceStore:
    global _default_store  # noqa: PLW0603 — プロセス内Singleton(既存のStoreと同じ方針)
    if _default_store is None:
        _default_store = GenerationEvidenceStore()
    return _default_store
