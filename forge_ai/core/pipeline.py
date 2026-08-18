"""Cognitive Engine Pipeline(薄いオーケストレーション)。

自然言語 → World理解 → 意味理解 → 意図理解 → 設計 → Forge IR、という
一連の流れを1つの関数として提供する。ただしこのモジュール自体は
判断ロジックを一切持たない「呼び出し順序をまとめるだけ」の薄い層であり、
各段階の実装(core/*.py, repair/*.py, quality/*.py)へ処理を委譲する。

キックオフ指示書11章「巨大Manager」「God Class」を避けるため、
状態を保持するクラスではなく、単一の関数として実装した
(呼び出し側が各段階のコンポーネントを構築し、注入する)。
"""

from __future__ import annotations

from dataclasses import dataclass

from forge_ai.core.compiler import Compiler, ForgeIRDocument
from forge_ai.core.domain_model import Domain, DomainRegistry
from forge_ai.core.intent_model import Intent, IntentBuilder
from forge_ai.core.meaning_model import ExtractedMeaning, MeaningExtractor
from forge_ai.core.planner import ApplicationPlan, Planner
from forge_ai.core.world_model import World, WorldModelBuilder
from forge_ai.provider.provider_interface import AIProvider
from forge_ai.quality.quality_engine import QualityEngine, QualityScore


@dataclass(frozen=True)
class PipelineResult:
    """各段階の中間結果をすべて保持する(デバッグ・説明可能性のため)。
    「世界理解〜設計まで」(キックオフ指示書1章)の全段階を追跡できる。"""

    domain: Domain
    world: World
    meaning: ExtractedMeaning
    intent: Intent
    plan: ApplicationPlan
    ir: ForgeIRDocument
    quality: QualityScore


def run_pipeline(
    user_text: str,
    provider: AIProvider,
    *,
    domain_registry: DomainRegistry | None = None,
    world_builder: WorldModelBuilder | None = None,
) -> PipelineResult:
    """自然言語からForge IR + Quality Scoreまでを一気通貫で実行する。

    Repair EngineはここではChainしていない(Validator接続前の現段階では
    「何が問題か」を外部から与える必要があるため、パイプラインの外側で
    呼び出し側が明示的に行う設計とした。IMPLEMENTATION_REPORT.md参照)。
    """
    domain_registry = domain_registry or DomainRegistry()
    world_builder = world_builder or WorldModelBuilder()

    domain = domain_registry.resolve_from_keywords(user_text)
    world = world_builder.build(domain)

    meaning = MeaningExtractor(provider).extract(user_text, world)
    intent = IntentBuilder(provider).build(meaning, world)
    plan = Planner(provider).plan(intent)
    ir = Compiler(provider).compile(plan)
    quality = QualityEngine().evaluate(ir, plan)

    return PipelineResult(
        domain=domain, world=world, meaning=meaning, intent=intent, plan=plan, ir=ir, quality=quality,
    )


# ---------------------------------------------------------------------------
# run_cognitive_pipeline() — FORGE-MILESTONE-007第一段階、新規Facade
#
# 上記の run_pipeline()・PipelineResult は、このFacadeを追加するに
# あたって一切変更していない(シグネチャ・戻り値・内部動作とも無変更)。
# Legacy ProtocolとCognitive Protocolを混在させないため、実装は
# core/orchestration/ 配下の別モジュールへ完全に分離してある。
# ---------------------------------------------------------------------------

from forge_ai.core.confirmation.escalation_handler import EscalationHandler  # noqa: E402
from forge_ai.core.critic.design_critic import DesignCritic  # noqa: E402
from forge_ai.core.critic.revision_engine import RevisionEngine  # noqa: E402
from forge_ai.core.input_processing.ambiguity_detector import AmbiguityDetector  # noqa: E402
from forge_ai.core.input_processing.normalizer import InputNormalizer  # noqa: E402
from forge_ai.core.ir.entity_synthesizer import EntitySynthesizer  # noqa: E402
from forge_ai.core.orchestration.cognitive_dependencies import CognitiveDependencies  # noqa: E402
from forge_ai.core.orchestration.outcomes import CognitivePipelineOutcome  # noqa: E402
from forge_ai.core.orchestration.pipeline_orchestrator import CognitiveOrchestrator  # noqa: E402
from forge_ai.core.planning.application_planner import CognitiveApplicationPlanner  # noqa: E402
from forge_ai.core.planning.template_selector import TemplateSelector  # noqa: E402
from forge_ai.core.understanding.domain_classifier import CognitiveDomainClassifier  # noqa: E402
from forge_ai.core.understanding.intent_recognizer import CognitiveIntentRecognizer  # noqa: E402
from forge_ai.core.understanding.meaning_extractor import CognitiveMeaningExtractor  # noqa: E402
from forge_ai.core.understanding.requirement_extractor import RequirementExtractor  # noqa: E402
from forge_ai.core.understanding.world_builder import CognitiveWorldBuilder  # noqa: E402
from forge_ai.repair.repair_engine import RepairEngine  # noqa: E402,F401 (将来のRepair接続用、今回は未使用)


from forge_ai.contracts.design_language_contract import DesignLanguageGuidance  # noqa: E402
from forge_ai.core.ir.design_intent import DesignIntentSelector  # noqa: E402
from forge_ai.provider.mock_provider import MockProvider  # noqa: E402


def _default_cognitive_dependencies(
    provider: AIProvider, *, design_language: DesignLanguageGuidance | None = None
) -> CognitiveDependencies:
    """第一段階のルールベース実装一式を組み立てる。`compiler`のみ、
    実際に`provider.complete()`を呼び出す(`Compiler.compile()`は
    Provider依存のコンポーネントである。当初「Providerを呼ばない」と
    誤って想定していたが、実際に実行して確認し訂正した)。

    CEO実物監査(Phase 1.1)対応: `provider`を引数として受け取るように
    修正した(以前は関数内部で`MockProvider()`を固定生成しており、外部
    からのProvider差し替えができなかった)。
    """
    return CognitiveDependencies(
        normalizer=InputNormalizer(),
        ambiguity_detector=AmbiguityDetector(),
        intent_recognizer=CognitiveIntentRecognizer(),
        domain_classifier=CognitiveDomainClassifier(),
        world_builder=CognitiveWorldBuilder(),
        meaning_extractor=CognitiveMeaningExtractor(),
        requirement_extractor=RequirementExtractor(),
        template_selector=TemplateSelector(),
        planner=CognitiveApplicationPlanner(),
        design_critic=DesignCritic(),
        revision_engine=RevisionEngine(),
        escalation_handler=EscalationHandler(),
        compiler=Compiler(provider=provider),
        quality_engine=QualityEngine(),
        # FORGE-PRODUCT-VISION-002(2026-08-12): Curated Domain Libraryに
        # 無い依頼でも、型付きCRUDアプリを生成できるようにする
        # (`entity_synthesizer.py`参照)。`compiler`と同じく、実際に
        # `provider.complete()`を呼び出すコンポーネントである。
        entity_synthesizer=EntitySynthesizer(provider=provider),
        # FORGE-R1(2026-08-17): Design Languageの選択をAIへ委ねる。
        #
        # FORGE-R1-CLOSURE-015 §5で**遅延importをやめた**。以前はここで
        # `app.ai.runtime.design_language`をtry/exceptでimportしており、
        # 「forge_aiはbackendをimportしない」というコメントと実装が
        # 食い違っていた。しかもimport失敗を握り潰していたので、
        # Production（backendあり）とstandalone（backend無し）で
        # **同じコードが別の振る舞いをしていた**。
        #
        # いまは`DesignLanguageGuidance`という契約を外から受け取る。
        # 渡されなければAIへは聞かない——これは環境の違いではなく、
        # 明示的に「語彙を渡していない」という状態である。
        design_intent_selector=DesignIntentSelector(
            provider=provider, guidance=design_language,
        ),
    )


def run_cognitive_pipeline(
    raw_input: str,
    provider: AIProvider | None = None,
    *,
    clarification_answers: tuple[str, ...] = (),
    domain_registry: DomainRegistry | None = None,
    dependencies: CognitiveDependencies | None = None,
    design_language: "DesignLanguageGuidance | None" = None,
    title_seed: str | None = None,
) -> CognitivePipelineOutcome:
    """**M007 Phase 1 Minimal Cognitive Slice**のFacade。

    CEO実物監査(Phase 1.1)対応: 「Blueprint v1.3の実装」という表現は
    不正確だったため、`FORGE-MILESTONE-007-PHASE1-report.md`と合わせて
    この名称へ統一した。

    `run_pipeline()`(既存、上記)とは完全に分離された、別の関数・別の
    戻り値型である。

    CEO実物監査(Phase 1.1)対応: `provider`をBlueprint本来の契約どおり
    正式な引数として復元した。`dependencies`を明示的に渡した場合は
    `provider`より優先される(依存注入の一貫性のため)。`provider`を
    省略した場合、決定的な`MockProvider`を既定値として使う
    (第一段階の方針「Rule-Based中心、Mock Providerで決定的に動作する」
    を維持しつつ、外部から実Providerを注入できる形にした)。
    `CognitiveOrchestrator`自身はProviderを直接使わない(Legacy/
    Cognitive Protocol分離の原則、Compilerのみが利用する)。

    **`clarification_answers`(FORGE v0.2 Final Gate P0.1で新設、
    最終調整で単数→複数へ変更)**: Human Confirmation/Escalationへの
    回答を渡す、正式な別引数。**複数回の確認往復があった場合、全ての
    回答を順番通りタプルで渡すこと**(単数引数だった時代は、直近1件
    しか渡せず、1回目の回答が失われるバグがあった。最終調整で修正)。

    **修正した重大バグ(P0.1)**: 以前は呼び出し側(`confirmation_store.py`)
    が`f"{original}\\n(補足回答: {answer})"`という、Forge内部の管理用
    ラベル(「補足回答」)を自然言語へ直接埋め込んだ文字列を1本の
    `raw_input`として渡していた。この結果、「回答」という語が
    `lexicon.CONCEPT_KEYWORDS`のSurvey Domain概念("answer")と一致し、
    本来無関係なはずのSurvey Domainが競合候補として浮上する
    (実際に`"回答"`のみがマッチしてSurvey側のスコアが加算される)という
    実害を、このセッションで実際に再現・確認した。

    この関数は`raw_input`(元の入力)と`clarification_answers`(回答の
    タプル)を**常に別引数として受け取り**、内部でも管理用ラベルを
    一切使わずに結合する(下記`_combine_with_answers()`参照。ラベル
    無しの単純な連結のみを行う)。呼び出し側(`PromptPipeline`・
    `confirmation_store`)も、事前に結合済みの文字列を組み立てて
    渡すことを禁止し、常にこの関数へ2つの引数を個別に渡す設計へ
    統一した。

    **タイトルへのノイズ混入対策(最終調整P3)**: `raw_input`がノイズ的な
    短い入力("x"等)で`clarification_answers`が存在する場合、
    `title_seed`(回答部分のみを結合したテキスト)を計算し、
    `CognitiveOrchestrator.run()`へ渡す。これにより、Domain/Action等の
    判定には引き続き全文(ノイズ含む)を使いながら、生成されるアプリの
    タイトル(`Intent.goal`経由)には、意味の無い元入力が混ざらないように
    する(`_compute_title_seed()`参照)。

    **会話経由のタイトル(FORGE-HANDOFF-LOCAL-AI-UX-004、2026-08-13)**:
    `title_seed`を明示的に渡せるようにした。`/converse`が導入されて以降、
    `raw_input`はユーザーの一言ではなく**会話全体を要約した`build_brief`
    (数十〜百数十文字の説明文)**になった。`Intent.goal`はこの入力から
    導出されるため、生成されるアプリのタイトルが
    「買い物で何買うかを記録・管理するための道具」のような**説明文**に
    なっていた(実機で確認)。App Storeに並ぶアプリの名前は説明文では
    なく短い名詞句である。呼び出し側(`/converse`)が、ユーザー自身の
    短い言葉(`NeedModel.problem`)を`title_seed`として渡すことで、
    Domain判定には引き続き`build_brief`全体を使いながら、タイトルだけを
    ユーザーの言葉から導出する。Providerの種類に依存しない修正である
    (Mockでも実Geminiでも同じ問題が起きていた)。
    """
    if provider is None:
        provider = MockProvider()
    domain_registry = domain_registry or DomainRegistry()
    dependencies = dependencies or _default_cognitive_dependencies(
        provider, design_language=design_language
    )
    orchestrator = CognitiveOrchestrator(domain_registry, dependencies)
    effective_input = _combine_with_answers(raw_input, clarification_answers)
    # 呼び出し側が明示した`title_seed`を最優先する
    # (FORGE-HANDOFF-LOCAL-AI-UX-004対応、下記docstring「会話経由の
    # タイトル」参照)。指定が無い場合のみ、従来のノイズ入力対策
    # ヒューリスティック(`_compute_title_seed()`)へ委ねる。
    effective_title_seed = title_seed or _compute_title_seed(raw_input, clarification_answers)
    return orchestrator.run(effective_input, title_seed=effective_title_seed)


def _combine_with_answers(raw_input: str, clarification_answers: tuple[str, ...]) -> str:
    """`raw_input`と`clarification_answers`(**全件**)を、Forge内部の
    管理用ラベル(「補足回答」等)を一切混入させずに結合する
    (P0.1のバグ修正の核心、最終調整で全件累積対応)。単純な空白区切りの
    連結のみを行う(自然言語として、ユーザーが本当に複数文をまとめて
    書いたのと同じ形にする)。空文字列の回答は無視する。
    """
    pieces = [p for p in (raw_input, *clarification_answers) if p]
    return " ".join(pieces)


# FORGE_v0.2_最終修正指示(Final Gate) P3対応: `raw_input`がこの文字数
# 未満の場合、「ノイズ的な入力」とみなし、タイトル導出からは除外する
# 候補とする(`forge_ai/core/input_processing/ambiguity_detector.py`の
# `missing_goal`判定と同種の閾値だが、目的が異なる別々の定数として
# 独立させている: 片方はAmbiguity検出の閾値、片方はタイトル導出専用の
# ヒューリスティックであり、将来別々の調整が必要になりうるため)。
_NOISE_INPUT_MAX_LENGTH = 2


def _compute_title_seed(raw_input: str, clarification_answers: tuple[str, ...]) -> str | None:
    """`raw_input`がノイズ的で、かつ`clarification_answers`が存在する
    場合のみ、回答部分だけを結合した文字列を返す(タイトル導出専用)。
    それ以外(通常の入力、または回答が無い場合)は`None`を返し、
    `CognitiveIntentRecognizer`が通常通り`normalized_text`全体を使う
    (既存の挙動を維持、後方互換)。
    """
    if not clarification_answers:
        return None
    if len(raw_input.strip()) >= _NOISE_INPUT_MAX_LENGTH:
        # raw_input自体が既に意味のある長さを持つ場合、タイトルに
        # ノイズが混ざる心配は無いため、特別扱いしない。
        return None
    non_empty_answers = [a for a in clarification_answers if a]
    if not non_empty_answers:
        return None
    return " ".join(non_empty_answers)
