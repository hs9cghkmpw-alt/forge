"""Learning Contract — Growing AIが**共通で使う語彙**
(FORGE-017A §5・§6・§10、2026-08-24)。

---

## この module に実装は無い

ここにあるのは**語彙と境界**だけである。Learning Eventを実際に作って
送る経路は commit E で入る（017 §25「Interface / Event Contract /
Version / Privacy境界は先に定義する」）。

先に定義する理由は、**後から足せないものがあるから**である。
`intelligence_scope`や`app_id`は、Knowledge/Eventを1件でも作った後に
遡って付けようとすると全面書き換えになる。

---

## なぜEvent種類とTask種類をEvidence Storeの型に縛らないのか

017Aの指摘そのものである。commit BまでのLearning Event V1は

    event_type = generation | revision | ai_call | benchmark
    task_type  = ForgeTask（4値）

としていた。これは**いま実装がある型を並べただけ**で、Growing AIの
構想（build / compile / test / runtime / crash / tool result …）から
見ると勝手に縮小している。

実装が無いものを`⬜未実装`として持つのと、**構想から消す**のは違う。
前者は「まだ作っていない」だが、後者は「作らないことにした」である。

したがってここでは:

* **語彙は構想どおり広く持つ**（emitしないものは「未実装」でよい）
* ただし**自由文字列は禁止**（closed registry）——検証できない識別子が
  Cloudへ流れ込むと、Datasetが誰にも読めないラベルで汚れる
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.ai.gateway.tasks import ForgeTask

__all__ = [
    "ContributionTarget",
    "DataResidency",
    "IntelligenceScope",
    "LearningEventType",
    "LearningTaskId",
    "learning_task_for",
    "registered_task_ids",
]


class LearningEventType(str, Enum):
    """Learning Eventの種類（017A §5）。

    **Evidence Storeの型と1:1に固定しない。** `generation` /
    `revision` / `ai_call` / `benchmark` はいま実装がある4つだが、
    Growing AIの構想はそれより広い。

    実装が無いものに ⬜ を付けてある。**「未実装」であって
    「作らないことにした」ではない。**
    """

    # --- いま実装がある（Evidence Storeが対応する事実を持っている） ---
    GENERATION = "generation"
    """1つの生成物ができた。`GenerationRecord`。"""

    REVISION = "revision"
    """1回の変更が行われた。`RevisionRecord`。"""

    AI_CALL = "ai_call"
    """1回のAI呼び出し。`ExperienceRecord`。"""

    BENCHMARK = "benchmark"
    """1回の測定。`BenchmarkRun`。"""

    FEEDBACK = "feedback"
    """利用者が評価した。`ArtifactFeedbackEvent`（017A §2）。

    **`generation`の属性ではなく独立したEventである。** 時系列が
    それ自体Evidenceだから——「最初は良いと言ったが後から直した」は
    生成物の属性では表せない。"""

    # --- ⬜ まだemitしない（構想から消さない） ---
    REGENERATION = "regeneration"
    """⬜ 同じNeedに対して作り直した。"""

    BUILD = "build"
    """⬜ アプリのビルド（`flutter build`等）。"""

    COMPILE = "compile"
    """⬜ Forge Language → Runtime表現のコンパイル。"""

    TEST = "test"
    """⬜ テスト実行の結果。"""

    VALIDATION = "validation"
    """⬜ Validator単体の実行（生成と切り離して測る場合）。"""

    RUNTIME = "runtime"
    """⬜ 実行時の事実（描画できたか等）。"""

    CRASH = "crash"
    """⬜ 落ちた。**強い負例**になりうる。"""

    TOOL_RESULT = "tool_result"
    """⬜ Tool呼び出しの結果。"""

    @property
    def is_emitted_today(self) -> bool:
        """**現時点でForgeが実際に作れるか。**

        これを`True`と書いてよいのは、対応するEvidenceがProduction
        経路で残っている種類だけである。「型があるから作れる」と
        混同しない（Product Direction §7）。
        """
        return self in {
            LearningEventType.GENERATION,
            LearningEventType.REVISION,
            LearningEventType.AI_CALL,
            LearningEventType.BENCHMARK,
            LearningEventType.FEEDBACK,
        }


class IntelligenceScope(str, Enum):
    """**誰の知能を改善するEventか**（017A §10）。"""

    GLOBAL = "global"
    """Forge全体の知能。"""

    APP = "app"
    """特定のAppの知能。`app_id`が要る。"""

    PERSONAL = "personal"
    """その利用者だけの知能。"""


class DataResidency(str, Enum):
    """**外へ出してよいか**（017A §10）。

    `IntelligenceScope`と**分ける**のが要点である。混ぜると

        scope = personal

    が「個人の知能を改善する」なのか「外へ出してはいけない」なのかを
    1つの値が兼ねてしまい、片方の意図で書かれた値がもう片方の判断に
    使われる。

    例: Appの知能を改善するEventでも、内容によってはCloudへ出せない。
    2軸なら`(APP, LOCAL_ONLY)`と書ける。1軸だと表せない。
    """

    LOCAL_ONLY = "local_only"
    """**端末から出さない。既定値。**

    分からないものを楽観側（出してよい）へ倒さない（`CLAUDE.md` §3）。
    """

    CLOUD_ELIGIBLE = "cloud_eligible"
    """Consentとsanitizeを通っており、Cloudへ出してよい。"""


class ContributionTarget(str, Enum):
    """**どのDatasetへ寄与してよいか**（017A §10）。"""

    NONE = "none"
    """**既定値。** どのDatasetへも入れない。"""

    APP = "app"
    """そのAppのDatasetへのみ。"""

    GLOBAL = "global"
    """Global Datasetへ。**最も強い許可**であり、
    Genericに有用と判定されたものだけ（017 §18）。"""


@dataclass(frozen=True)
class LearningTaskId:
    """Learning SDK全体で使うTask識別子（017A §6）。

    ---

    ## なぜ`ForgeTask`をそのまま使わないのか

    `ForgeTask`は**AI Routing / Benchmarkの語彙**である。「どのProvider
    へ投げるか」「どの単位で品質を測るか」を決めるためのもので、現に
    4値しかない。

    Learning SDKが扱うのはそれより広い——`flutter.build`や
    `runtime.render`はAIを呼ばないので`ForgeTask`になりようがないが、
    Learning Eventとしては立派な事実である。

    `ForgeTask`へ無理に足すと、**AIを呼ばないTaskがRouting表に並ぶ**。
    Routingは「Providerを選ぶ」ことなので、Providerが要らないTaskが
    そこに居るのは嘘である。

    だから**分けて、対応付ける**。

    ## 自由文は禁止

    `namespace.name`という形に限る。外部Appが好きな文字列を送れると、
    Datasetが誰にも読めないラベルで汚れる。将来SDKを公開するときは、
    namespaceの登録も必要になる（017 §22）。
    """

    namespace: str
    """`forge` / `flutter` / `runtime` / `app.<登録名>` 等。"""

    name: str

    def __post_init__(self) -> None:
        for part, label in ((self.namespace, "namespace"), (self.name, "name")):
            if not part:
                msg = f"LearningTaskIdの{label}が空である"
                raise ValueError(msg)
            if not all(c.islower() or c.isdigit() or c in "._" for c in part):
                # 自由文・大文字・空白を弾く(006 §6 Semantic Identifier境界)。
                msg = f"LearningTaskIdの{label}が識別子の形をしていない: {part!r}"
                raise ValueError(msg)

    @property
    def value(self) -> str:
        return f"{self.namespace}.{self.name}"

    def __str__(self) -> str:
        return self.value


#: `ForgeTask` → `LearningTaskId` の対応（017A §6）。
#:
#: **全ての`ForgeTask`がここに在ることをテストが強制する。**
#: `ForgeTask`へ値を足した人がここを忘れると、そのTaskのEventだけ
#: 静かにLearning側から消える——「呼び出し側が忘れずに書く」設計に
#: しないための見張りである（`CLAUDE.md` §3）。
_FORGE_TASK_MAPPING: dict[ForgeTask, LearningTaskId] = {
    ForgeTask.CONVERSATION_STEP: LearningTaskId("forge", "conversation_step"),
    ForgeTask.ENTITY_SYNTHESIS: LearningTaskId("forge", "entity_synthesis"),
    ForgeTask.FORGE_LANGUAGE_UPDATE: LearningTaskId("forge", "forge_language_update"),
    ForgeTask.COGNITIVE_STAGE: LearningTaskId("forge", "cognitive_stage"),
}

#: まだ`ForgeTask`に対応が無いTask（017A §6の例）。
#:
#: **AIを呼ばないので`ForgeTask`にはならない。** それでもLearning
#: Eventとしては事実であり、構想から消さない。
_ADDITIONAL_TASK_IDS: tuple[LearningTaskId, ...] = (
    LearningTaskId("flutter", "build"),
    LearningTaskId("flutter", "test"),
    LearningTaskId("runtime", "render"),
    LearningTaskId("forge", "design_revision"),
)


def learning_task_for(task: ForgeTask) -> LearningTaskId:
    """`ForgeTask`に対応するLearning Task識別子。

    **対応が無ければ例外にする。** 既定値へ落とすと、対応を書き忘れた
    Taskが全部同じラベルに潰れて、後から見分けられなくなる。
    """
    mapped = _FORGE_TASK_MAPPING.get(task)
    if mapped is None:  # pragma: no cover — テストが存在を強制している
        msg = (
            f"ForgeTask.{task.name} に対応する LearningTaskId が無い。"
            "learning_contract._FORGE_TASK_MAPPING へ追加すること。"
        )
        raise KeyError(msg)
    return mapped


def registered_task_ids() -> tuple[LearningTaskId, ...]:
    """登録済みのTask識別子すべて。**自由文は含まれない。**"""
    return tuple(_FORGE_TASK_MAPPING.values()) + _ADDITIONAL_TASK_IDS
