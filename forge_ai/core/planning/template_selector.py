"""Template Selector(FORGE-MILESTONE-007 Phase 1 Minimal Cognitive Slice、M006 13章)。

Preliminary(Domain/Intent/Requirementsのみで大まかに絞り込む)と
Final(確定したApplicationPlanの構造で最終決定する)の2メソッドを持つ。

**第一段階の簡略化**: M006 13章が求める9項目の評価基準のうち、今回は
「Dominant user action」「Data lifecycle(のキーワード近似)」
「Number of entities」「Need for validation」に基づく簡易スコアリング
のみを実装する(既知の制限)。

**CEO実物監査(Phase 1.1)対応**: 同点時に`sorted()`の辞書挿入順へ
暗黙に依存していた問題を解消した。`select_final()`は
`preliminary_candidates`を新たな引数として受け取り、以下の順序で
決定的にtie-breakする。

1. Preliminary候補に含まれるTemplateを優先
2. Dominant action(主要操作)との一致数
3. Data lifecycle(データの性質を示すキーワード)との一致数
4. それでも決まらない場合はgeneric
"""

from __future__ import annotations

from forge_ai.core.domain_model import Domain, DomainCategory
from forge_ai.core.intent_model import Intent
from forge_ai.core.orchestration.cognitive_types import RequirementSet, TemplateSelection
from forge_ai.core.planner import ApplicationPlan

# Domain category(文字列) -> Preliminary候補(スコア降順)。
#
# **FORGE v0.3で発見・修正した重大な欠落**: `household_budget`・
# `child_growth`(FORGE_v0.2_修正指示.md P2 11章で追加)は、Domain
# Registryへ登録されただけで、この辞書には一度も追加されていなかった。
# 実際に「家計簿をつけたい」を実行して検証した結果、`.get(domain.
# category.value, ("generic",))`のフォールバックにより常に
# `("generic",)`しかPreliminary候補にならず、`select_final()`が
# 別のTemplateを選ぶたびに`differs_from_preliminary=True`が繰り返され、
# 最終的に`preliminary_final_mismatch_exhausted`で確認要求に落ちる
# (=Success状態に一度も到達できない)という不具合を発見した。今回、
# 既存2Domain分の欠落を修正し、新設4Domain(fishing_log/habit_tracking/
# study/travel)分もあわせて追加した。
_DOMAIN_TO_PRELIMINARY: dict[str, tuple[str, ...]] = {
    "shopping": ("checklist", "form"),
    "task_management": ("checklist", "crud"),
    "diary": ("memo", "crud"),
    "survey": ("form", "wizard"),
    "schedule": ("calendar", "tracker"),
    "inventory": ("tracker", "crud"),
    "hospital": ("form", "crud"),
    "attendance": ("checklist", "tracker"),
    "household_budget": ("tracker", "form"),
    "child_growth": ("tracker", "memo"),
    "fishing_log": ("tracker", "memo"),
    "habit_tracking": ("checklist", "tracker"),
    "study": ("tracker", "memo"),
    "travel": ("checklist", "form"),
    "generic": ("checklist", "generic"),
}


def _missing_domain_preliminary_entries() -> frozenset[str]:
    """`DomainCategory`の全`.value`のうち、`_DOMAIN_TO_PRELIMINARY`に
    登録されていないものを返す(空なら欠落なし)。テスト
    (`test_planning_and_critic.py`の
    `test_all_domain_category_values_are_registered_in_preliminary_
    table`)とモジュール読み込み時の自己検証(下記)の両方から呼ばれる、
    単一の判定ロジック(重複させない)。"""
    return frozenset({c.value for c in DomainCategory}) - frozenset(_DOMAIN_TO_PRELIMINARY.keys())


def _extra_domain_preliminary_entries() -> frozenset[str]:
    """`_DOMAIN_TO_PRELIMINARY`に登録されているが、`DomainCategory`の
    どの`.value`にも一致しないキーを返す(逆方向、CEO指摘「余分な
    未知キーも検出するか」への回答)。

    **設計判断: 余分なキーはimport時にエラーにしない(明文化)**。
    欠落(`_missing_domain_preliminary_entries()`)と異なり、余分な
    キーは`.get(domain.category.value, ("generic",))`から一度も
    参照されないだけであり、`preliminary_final_mismatch_exhausted`
    という実害には繋がらない(Domainが将来的にrenameまたは削除
    された際の、一時的な取り残しに過ぎない可能性が高い)。このため、
    import時のfail-fastの対象には**含めない**(欠落ほど危険では
    ないものを同じ強さで扱うと、正当な移行期間中の一時的な状態でも
    パイプライン全体を止めてしまいかねないため)。

    ただし、これは「タイポで作った誤ったキー」を発見する手がかりにも
    なりうる(例: `"houshold_budget"`という誤字は、`missing`側で
    `"household_budget"`の欠落として検出されると同時に、この
    `extra`側にも現れる)。そのため、**テスト側(`test_planning_and_
    critic.py`)で明示的に検査対象とする**(hygiene目的、必須の
    fail-fastとしては扱わない)。
    """
    return frozenset(_DOMAIN_TO_PRELIMINARY.keys()) - frozenset(c.value for c in DomainCategory)


def _raise_if_domain_preliminary_incomplete(missing: frozenset[str]) -> None:
    """`missing`が空でなければ、`RuntimeError`を送出する。

    **2026-07-21修正(CEO指摘)**: 以前は`raise AssertionError(...)`を
    使っていた。これは`assert`文そのものではなく、明示的な`raise`文
    だったため、実際には`python -O`実行時に除去される対象では
    **無かった**(`python -O`が除去するのは`assert`文・`if __debug__:`
    ブロックのみであり、`raise AssertionError(...)`という通常の
    例外送出はその対象外——実際に`python -O`で再現し、除去されない
    ことを確認済み)。

    とはいえ、`AssertionError`という例外型自体が「デバッグ時のみの
    検査」という印象を与え、将来誰かがこれを本当の`assert`文へ
    書き換えてしまうリスクがある。CEOの指摘通り、意図をより明確に
    示すため`RuntimeError`へ変更した(Runtimeの不変条件違反を表す、
    最適化フラグの影響を受けないことが型名からも明らかな例外)。
    """
    if missing:
        raise RuntimeError(
            "Missing preliminary template mappings for DomainCategory: "
            + ", ".join(sorted(missing))
            + ". Every DomainCategory must have an explicit entry in "
            "_DOMAIN_TO_PRELIMINARY (forge_ai/core/planning/"
            "template_selector.py) — falling back to the ('generic',) "
            "default causes a preliminary_final_mismatch_exhausted "
            "regression (this exact class of bug previously affected "
            "'household_budget', see FORGE v0.3 and the 2026-07-21 audit). "
            "Add an entry for the missing domain(s) above before using "
            "this module."
        )


# **CI/開発者向けの自己検証(2026-07-21、CEO指示「辞書の手動管理に
# 依存しない検出の仕組み」対応。同日、CEO指摘によりAssertionError→
# RuntimeErrorへ修正)**: `DomainCategory`へ新しいDomainを追加したのに
# `_DOMAIN_TO_PRELIMINARY`への追記を忘れる、という クラスの不具合
# (household_budget欠落事案)を、テストの実行有無に関わらず構造的に
# 防ぐ。このモジュールが**import された瞬間**に検証し、欠落があれば
# `RuntimeError`で即座に失敗させる。
#
# **import-time fail-fastを採用する設計理由と影響(CEO指摘5.への回答、
# `docs/adr/ADR-013-template-selection-mismatch-severity.md`にも
# 転記済み)**:
# - 理由: この`import`は、`forge_ai`パイプラインが実際に動作する経路
#   (`pipeline_orchestrator.py`が`TemplateSelector`を使う)・テスト
#   実行経路のいずれでも必ず通るため、「テストを書いたのに実行し
#   忘れる」「テストファイル自体が存在するのを忘れる」という失敗
#   モードを、「モジュールを読み込んだ瞬間に落ちる」という、より
#   強い保証で置き換えられる(Pythonには真の意味でのコンパイル時型
#   検査は無いため、現実的に到達可能な最も近い等価物として採用)。
# - 影響: 欠落が生じた場合、`preliminary_final_mismatch_exhausted`
#   という(会話は継続できる)確認要求ではなく、**forge_aiパイプライン
#   全体がimportの時点で起動不能になる**、より厳しい失敗モードに
#   なる。これは意図した設計判断である(「実行時に静かに劣化する
#   より、明確に検出できる形で早期に失敗する方が良い」)が、本番
#   環境でこの失敗が起きた場合の影響範囲(forge_aiに依存する
#   backend全体が起動できなくなる)を認識した上で採用している。
_raise_if_domain_preliminary_incomplete(_missing_domain_preliminary_entries())

# Template Family毎の「Dominant action」典型操作(tie-break 2で使う)。
_TEMPLATE_ACTIONS: dict[str, tuple[str, ...]] = {
    "checklist": ("add_item", "remove_item", "mark_purchased", "add_task",
                  "complete_task", "delete_task", "check_in", "check_out", "mark_absent",
                  "check_habit", "add_habit", "view_streak", "add_destination", "plan_itinerary"),
    "form": ("add_question", "submit_response", "schedule_appointment",
             "record_symptom", "record_medication"),
    "tracker": ("adjust_stock", "set_threshold", "record_shipment", "set_budget",
                "add_transaction", "set_budget_limit", "view_summary",
                "add_measurement", "add_milestone", "add_photo",
                "add_catch", "record_location", "record_size",
                "add_study_log", "track_progress"),
    "calendar": ("add_event", "edit_event", "delete_event", "set_reminder"),
    "memo": ("add_entry", "edit_entry", "tag_entry"),
}

# Template Family毎の「Data lifecycle」近似キーワード(tie-break 3で使う)。
_TEMPLATE_ENTITY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "tracker": ("stock", "threshold", "quantity",
                "transaction", "amount", "budget_limit",
                "measurement", "milestone",
                "catch", "species", "size", "weight",
                "progress", "material"),
    "calendar": ("event", "time", "reminder", "participant"),
    "memo": ("entry", "mood"),
    "form": ("question", "answer", "respondent", "choice"),
    "checklist": ("item", "task", "status", "habit", "streak", "destination", "itinerary"),
}

_ALL_TEMPLATES = (
    "checklist", "form", "memo", "crud", "dashboard", "calendar",
    "tracker", "catalog", "detail_list", "wizard", "generic",
)


def _count_matches(candidate_values: tuple[str, ...], keyword_pool: tuple[str, ...]) -> int:
    """candidate_valuesのうち、keyword_poolに含まれる要素の個数を返す
    (部分一致ではなく完全一致。tie-break専用の単純なカウント)。"""
    return sum(1 for v in candidate_values if v in keyword_pool)


class TemplateSelector:
    """`TemplateSelectorProtocol`を満たす。"""

    def select_preliminary(
        self, domain: Domain, intent: Intent, requirements: RequirementSet
    ) -> tuple[str, ...]:
        return _DOMAIN_TO_PRELIMINARY.get(domain.category.value, ("generic",))

    def select_final(
        self, plan: ApplicationPlan, preliminary_candidates: tuple[str, ...] = ()
    ) -> TemplateSelection:
        entity_count = len(plan.data_entities)
        validation_count = sum(len(s.validation_rules) for s in plan.screens)
        entities_lower = tuple(e.lower() for e in plan.data_entities)
        actions_lower = tuple(a.lower() for a in plan.primary_flow)

        scores: dict[str, float] = {t: 0.0 for t in _ALL_TEMPLATES}

        # 主な操作(action verb)は、単純なentity数より強い手がかりになる
        # (実際にテストして、entity数だけの判定だと'form'に偏りすぎることを発見し、修正した)。
        for template, typical_actions in _TEMPLATE_ACTIONS.items():
            if any(a in typical_actions for a in actions_lower):
                scores[template] += 3.0

        # entity/keywordベースの補助シグナル(action verbだけで決まらない場合の補強)。
        for template, keywords in _TEMPLATE_ENTITY_KEYWORDS.items():
            if any(k in e for e in entities_lower for k in keywords):
                scores[template] += 1.0

        # entity数・validation数は、action verbで決着しなかった場合のみの弱い補強とする。
        if entity_count >= 3 and validation_count > 0 and max(scores.values()) < 1.0:
            scores["form"] += 1.0
        if entity_count <= 2 and max(scores.values()) < 1.0:
            scores["checklist"] += 1.0

        scores["generic"] += 0.1  # 何もヒットしない場合の最終防波堤(必ず何か選ばれる)

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        max_score = ranked[0][1]
        tied = tuple(name for name, score in ranked if score == max_score)

        tie_break_notes: list[str] = []
        if len(tied) == 1:
            best_template = tied[0]
        else:
            tie_break_notes.append(f"同点(score={max_score:.2f}): {tied}")

            # Tie-break 1: Preliminary候補に含まれるTemplateを優先。
            within_preliminary = tuple(t for t in tied if t in preliminary_candidates)
            candidates = within_preliminary if len(within_preliminary) == 1 else (within_preliminary or tied)
            if len(within_preliminary) == 1:
                best_template = within_preliminary[0]
                tie_break_notes.append(f"Preliminary候補{preliminary_candidates}内で絞り込み -> {best_template}")
            else:
                if within_preliminary:
                    tie_break_notes.append(f"Preliminary候補内でも複数該当のため継続: {within_preliminary}")
                else:
                    tie_break_notes.append("Preliminary候補内に該当なし、全同点候補で継続")

                # Tie-break 2: Dominant action(主要操作)との一致数。
                action_counts = {t: _count_matches(actions_lower, _TEMPLATE_ACTIONS.get(t, ())) for t in candidates}
                max_action_count = max(action_counts.values(), default=0)
                by_action = tuple(t for t in candidates if action_counts[t] == max_action_count)
                if len(by_action) == 1 and max_action_count > 0:
                    best_template = by_action[0]
                    tie_break_notes.append(f"Dominant action一致数({max_action_count})で絞り込み -> {best_template}")
                else:
                    tie_break_notes.append(f"Dominant actionでも同点: {by_action}")

                    # Tie-break 3: Data lifecycle(entityキーワード)との一致数。
                    lifecycle_counts = {
                        t: _count_matches(entities_lower, _TEMPLATE_ENTITY_KEYWORDS.get(t, ())) for t in by_action
                    }
                    max_lifecycle_count = max(lifecycle_counts.values(), default=0)
                    by_lifecycle = tuple(t for t in by_action if lifecycle_counts[t] == max_lifecycle_count)
                    if len(by_lifecycle) == 1 and max_lifecycle_count > 0:
                        best_template = by_lifecycle[0]
                        tie_break_notes.append(f"Data lifecycle一致数({max_lifecycle_count})で絞り込み -> {best_template}")
                    else:
                        # Tie-break 4: それでも決まらない場合はgeneric。
                        best_template = "generic"
                        tie_break_notes.append(f"Data lifecycleでも同点({by_lifecycle})のためgenericへ既定")

        rationale = (
            f"actions={list(plan.primary_flow)}, data_entities={list(plan.data_entities)}, "
            f"validation_count={validation_count}, scores上位={ranked[:3]}"
        )
        if tie_break_notes:
            rationale += " | tie-break: " + " / ".join(tie_break_notes)

        return TemplateSelection(
            template=best_template,
            score_by_template=tuple(ranked),
            differs_from_preliminary=best_template not in preliminary_candidates,
            rationale=rationale,
        )

