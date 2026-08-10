"""Escalation Handler(FORGE-MILESTONE-007第一段階、M006 3.12節。
FORGE_v0.2_修正指示.md P0 3章で質問品質を改善。
FORGE_v0.2_最終調整 P2で revision_exhausted の質問品質を改善)。

Human Confirmation/Escalation(Terminal Outcome)の「受け皿」。
到達理由(reason)に応じた、ユーザー向けの確認メッセージを構築する。

**改善内容(正直な申告)**: 以前は`reason`ごとの固定テンプレート文言
(例:「もう少し詳しく教えてください」)しか返さず、`context.ambiguity_
report`(どのカテゴリが検出されたか)を一切利用していなかった。今回、
`ambiguity_report.issues`のカテゴリ(missing_goal/missing_domain/
missing_action/missing_data/multiple_possible_templates/
conflicting_requirements)を実際に見て、「何を答えればよいか」が
具体的に伝わる質問文・例を生成するようにした。

**最終調整での追加改善**: `revision_exhausted`(Design Criticの指摘が
解消せず、Cognitive Revisionの上限に達した場合)についても、以前は
「設計の見直しを繰り返しましたが、品質基準を満たせませんでした」という、
内部の処理過程(Revision・品質基準)をそのまま露出する文言だった。
`context.critic_report.issues`から、実際に何が不足しているか
(未割当の必須要件の具体的な説明文等)を抽出し、ユーザーに内部事情を
見せずに「何を答えればよいか」が伝わる質問へ改善した
(`_build_revision_exhausted_message()`参照)。

**既知の制限**: DomainRegistry自体はこのクラスへ注入されていない
(Blueprint設計上、`EscalationHandler()`はProviderのみを受け取る
`_default_cognitive_dependencies()`から引数無しで構築される)。
そのため、Domain例は実際のRegistryから動的に列挙するのではなく、
Forge標準ユースケース(指示書が明示する家計簿・買い物・予定・
子どもの成長等)を手動でキュレーションした固定リストを使う。将来的に
Registryを注入できるようにすれば、より正確な動的リストにできる
(既知の制限として記録)。
"""

from __future__ import annotations

from forge_ai.core.orchestration.cognitive_types import ConfirmationRequest

# 指示書P0 3章の例("家計・買い物・予定・子どもの成長")と、既存の
# 標準ユースケース(タスク管理・日記・在庫・アンケート)を合わせた、
# missing_domain時の例示リスト。
_DOMAIN_EXAMPLES: tuple[str, ...] = (
    "家計簿", "買い物リスト", "予定管理", "子どもの成長記録",
    "日記", "在庫管理", "タスク管理", "アンケート",
)

_PRIVACY_MESSAGE = (
    "記録する情報の内容によっては、プライバシーや安全に関わる可能性があります。"
    "記録する情報の範囲・共有範囲について教えてください。"
)

_REVISION_EXHAUSTED_FALLBACK_MESSAGE = (
    "いくつか確認させてください。作りたいアプリの目的・対象となる方・"
    "管理したい内容を、もう少し具体的に教えていただけますか。"
)

_TEMPLATE_MISMATCH_MESSAGE = (
    "画面構成の検討を繰り返しましたが、最適な形に収束しませんでした。"
    "作りたいアプリの主な操作を教えてください。"
)

_DEFAULT_MESSAGE = "確認が必要です。もう少し詳しく教えてください。"

# FORGE_v0.2_最終調整 P2対応:
# `CriticIssue.category`ごとの、ユーザー向けの「何が足りないか」表現。
# `design_critic.py`の内部語彙(category名・coverage_ratio等)を
# そのまま見せず、この対応表を介して自然な日本語へ変換する。
_CRITIC_CATEGORY_TOPICS: dict[str, str] = {
    "unassigned_mandatory_requirement": "次の点をどのように実現すればよいか",
    "intent_meaning_fidelity": "次のご要望をどのように実現すればよいか",
    "privacy": "記録する情報の範囲・共有範囲",
    "accessibility": "操作方法(キーボードのみでの操作等)についてのご要望",
    "navigation_coherence": "画面の移り変わり(どの操作でどの画面に進むか)",
    "completeness": "各画面でどのような項目を扱いたいか",
}

# この順に確認する(最も情報量が多い=具体的な要望内容から確認する)。
_CRITIC_CATEGORY_PRIORITY: tuple[str, ...] = (
    "unassigned_mandatory_requirement", "intent_meaning_fidelity", "privacy",
    "accessibility", "navigation_coherence", "completeness",
)

# Ambiguity Detectionの各カテゴリに対応する、具体的な質問文・例。
# `_build_ambiguity_driven_message()`が、実際に検出されたissueの
# カテゴリに応じてこの中から組み立てる。
_CATEGORY_QUESTIONS: dict[str, str] = {
    "missing_goal": "どのようなアプリを作りたいか、目的を教えてください。",
    "missing_domain": (
        "何を管理するアプリですか？\n例:\n"
        + "\n".join(f"・{example}" for example in _DOMAIN_EXAMPLES)
    ),
    "missing_action": "そのアプリで「追加する」「記録する」「管理する」のうち、主にどの操作をしたいですか？",
    "missing_data": "何のデータを扱いたいですか？(例: 品目、金額、日付、参加者など)",
    "multiple_possible_templates": "複数の分野に該当する可能性があります。最も近いものを教えてください。",
    "conflicting_requirements": "ご要望の中に、両立しにくい条件が含まれているようです。どちらを優先しますか？",
}

# 優先して1つだけ質問するための順序(複数該当時、最も基本的な情報が
# 欠けているものを優先する)。
_CATEGORY_PRIORITY: tuple[str, ...] = (
    "missing_goal", "missing_domain", "missing_action", "missing_data",
    "multiple_possible_templates", "conflicting_requirements",
)


def _build_ambiguity_driven_message(ambiguity_report) -> str | None:
    """`ambiguity_report.issues`から、最も優先度の高い(=情報として
    根本的な)カテゴリを1つ選び、そのカテゴリ向けの具体的な質問文を返す。
    該当カテゴリが無い場合は`None`(呼び出し側が既定文言を使う)。"""
    if ambiguity_report is None:
        return None
    present_categories = {issue.category for issue in ambiguity_report.issues}
    for category in _CATEGORY_PRIORITY:
        if category in present_categories:
            return _CATEGORY_QUESTIONS[category]
    return None


# FORGE v0.3 Task4対応: Domainが(ほぼ)確定していても、実際に生成する
# アプリの形を左右するsub-type(下位分類)がある場合、汎用的な
# 「どちらのDomainに近いか」という質問ではなく、そのDomain特有の
# 具体的な質問を優先する。
#
# **既知の制限**: `escalation_handler.py`冒頭のdocstring参照。
# DomainRegistry自体が注入されていないため、この対応表も手動
# キュレーションの固定リストである。
_DOMAIN_SUBTYPE_QUESTIONS: dict[str, str] = {
    "household_budget": "個人用の家計簿ですか？家族で共有する家計簿ですか？",
    "fishing_log": "海釣りですか？川や湖などの淡水釣りですか？",
    "habit_tracking": "健康・運動系の習慣ですか？勉強・仕事系の習慣ですか？",
    "study": "資格試験のための学習ですか？語学学習ですか？その他の学習ですか？",
    "travel": "国内旅行ですか？海外旅行ですか？",
}


def _build_domain_candidate_message(domain_classification) -> str | None:
    """`priority2_low_domain_confidence`用のメッセージを構築する。

    FORGE v0.3 Task4対応: まず、primary_domainがsub-type質問を持つ
    Domain(`_DOMAIN_SUBTYPE_QUESTIONS`)かどうかを確認する。該当する
    場合、Domain自体は(ほぼ)特定できているとみなし、「どのDomainか」
    ではなく「そのDomainのどのsub-typeか」を聞く、より具体的な質問へ
    切り替える。該当しない場合は、既存の「実際に僅差だった候補を列挙
    して聞く」動作(以前からの実装)にフォールバックする。
    """
    if domain_classification is None:
        return None

    primary_category = domain_classification.primary_domain.category.value
    subtype_question = _DOMAIN_SUBTYPE_QUESTIONS.get(primary_category)
    if subtype_question is not None:
        return subtype_question

    positive_candidates = [c for c in domain_classification.candidates if c.raw_score > 0]
    if len(positive_candidates) < 2:
        return None
    names = [c.domain.display_name for c in positive_candidates[:3]]
    return f"「{'」「'.join(names)}」のどちらに近いか、もう少し具体的に教えていただけますか。"


def _build_revision_exhausted_message(critic_report) -> str:
    """FORGE_v0.2_最終調整 P2対応: 「品質基準を満たせませんでした」という
    内部事情をそのまま見せず、`critic_report.issues`から実際に不足して
    いる情報(目的・対象・管理内容等)を具体的に質問する。

    `unassigned_mandatory_requirement`・`intent_meaning_fidelity`は
    `evidence`に実際の要件の説明文(日本語、例:「共有・複数利用者
    (家族)に対するアクセス権限を管理できること。」)を含むため、これを
    直接引用して質問へ含める(架空の質問を作らず、実際に検出された
    内容に基づく)。該当issueが無い場合は、指示書の例
    (目的・対象・管理内容)に沿った既定の質問文へフォールバックする。
    """
    if critic_report is None or not critic_report.issues:
        return _REVISION_EXHAUSTED_FALLBACK_MESSAGE

    issues_by_category: dict[str, list] = {}
    for issue in critic_report.issues:
        issues_by_category.setdefault(issue.category, []).append(issue)

    for category in _CRITIC_CATEGORY_PRIORITY:
        matched = issues_by_category.get(category)
        if not matched:
            continue
        topic = _CRITIC_CATEGORY_TOPICS[category]
        if category in ("unassigned_mandatory_requirement", "intent_meaning_fidelity"):
            # evidenceから実際の要件説明を抽出して質問へ含める
            # (例:「共有・複数利用者(家族)に対するアクセス権限を
            # 管理できること。」)。
            descriptions = _extract_requirement_descriptions(matched[0].evidence)
            if descriptions:
                bullet_list = "\n".join(f"・{d}" for d in descriptions)
                return f"{topic}、教えてください。\n{bullet_list}"
        return f"{topic}、もう少し具体的に教えてください。"

    return _REVISION_EXHAUSTED_FALLBACK_MESSAGE


def _extract_requirement_descriptions(evidence: str) -> tuple[str, ...]:
    """`CriticIssue.evidence`(例: "未割当の必須要件が1件残っています:
    ['共有・複数利用者(家族)に対するアクセス権限を管理できること']")から、
    実際の要件説明文だけを抜き出す。パターンに一致しない場合は空タプル
    (呼び出し側が安全にフォールバックできるようにする)。"""
    start = evidence.find("[")
    end = evidence.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return ()
    inner = evidence[start + 1 : end]
    # 各要素は`'...'`という形式(Pythonのlist-of-str repr)で並んでいる。
    parts = [p.strip().strip("'\"") for p in inner.split("', '")]
    cleaned = [p.replace("'", "").strip() for p in parts if p.strip()]
    return tuple(d for d in cleaned if d)


class EscalationHandler:
    """`EscalationHandlerProtocol`を満たす。"""

    def build_confirmation_request(self, context, reason: str) -> ConfirmationRequest:
        message = self._build_message(context, reason)
        open_questions: tuple[str, ...] = ()
        if context.intent is not None and context.intent.open_questions:
            open_questions = context.intent.open_questions
        return ConfirmationRequest(reason=reason, message=message, open_questions=open_questions)

    def _build_message(self, context, reason: str) -> str:
        if reason == "priority1_privacy_safety_permission":
            return _PRIVACY_MESSAGE
        if reason == "ambiguity_high_severity":
            # FORGE v0.2 P0 3章対応: ambiguity_reportの実際のカテゴリに
            # 基づいた、具体的な質問文を優先する。
            ambiguity_message = _build_ambiguity_driven_message(
                getattr(context, "ambiguity_report", None)
            )
            if ambiguity_message is not None:
                return ambiguity_message
            return "入力内容から目的を十分に読み取れませんでした。どのようなアプリを作りたいか、もう少し具体的に教えてください。"
        if reason == "priority2_low_domain_confidence":
            candidate_message = _build_domain_candidate_message(
                getattr(context, "domain_classification", None)
            )
            if candidate_message is not None:
                return candidate_message
            return _CATEGORY_QUESTIONS["missing_domain"]
        if reason == "preliminary_final_mismatch_exhausted":
            return _TEMPLATE_MISMATCH_MESSAGE
        if reason == "revision_exhausted":
            return _build_revision_exhausted_message(getattr(context, "critic_report", None))
        return _DEFAULT_MESSAGE
