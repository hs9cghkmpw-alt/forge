"""Domain Model。

対象となる問題領域(Domain)を定義する。DomainはUIを一切知らない
(Widget・画面・Actionという概念はここには一度も登場しない)。

Domainは「この問題領域には典型的にどんな概念(モノ)・行為があるか」という
語彙を持つ。これはWorld Modelが具体的なActor/Object/Relationship/Ruleを
組み立てる際の材料になる。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DomainCategory(str, Enum):
    """キックオフ指示書5章に列挙された例 + 汎用フォールバック。

    FORGE-MILESTONE-007第一段階で、CEO指定の6例(買い物・タスク管理・
    日記・アンケート・予定・在庫)のうち、既存に無かった3つ
    (TASK_MANAGEMENT・SURVEY・SCHEDULE)を追加した(既存5値+GENERICは
    無変更、後方互換)。

    FORGE_v0.2_修正指示.md P2 11章対応で、Forge標準ユースケースとして
    挙げられた「家計簿」「成長記録」に対応するHOUSEHOLD_BUDGET・
    CHILD_GROWTHを追加した(既存10値は無変更、後方互換な追加)。

    FORGE v0.3 Task1対応で、これまでLexicon不足によりDIARYへ吸収
    されていた4分野(釣果記録・習慣記録・学習記録・旅行記録)を、
    独立したDomainとして追加した(既存12値は無変更)。
    """

    SHOPPING = "shopping"
    HOSPITAL = "hospital"
    ATTENDANCE = "attendance"
    DIARY = "diary"
    INVENTORY = "inventory"
    TASK_MANAGEMENT = "task_management"
    SURVEY = "survey"
    SCHEDULE = "schedule"
    HOUSEHOLD_BUDGET = "household_budget"
    CHILD_GROWTH = "child_growth"
    FISHING_LOG = "fishing_log"
    HABIT_TRACKING = "habit_tracking"
    STUDY = "study"
    TRAVEL = "travel"
    GENERIC = "generic"  # どのカテゴリにも明確に一致しない場合の受け皿


@dataclass(frozen=True)
class DomainConcept:
    """ある問題領域に典型的な「モノ」を表す語彙。UI表現(Widget種別等)は含まない。"""

    name: str
    description: str


@dataclass(frozen=True)
class Domain:
    """1つの問題領域の定義。"""

    category: DomainCategory
    display_name: str
    typical_concepts: tuple[DomainConcept, ...]
    typical_actions: tuple[str, ...]


class DomainRegistry:
    """既知のDomain定義を保持し、カテゴリやキーワードから解決する。

    「新しいDomainを追加する」際にこのクラス自体を書き換える必要はあるが、
    他モジュール(World/Meaning/Intent等)を変更する必要はない、という
    責務分離を意図している。
    """

    def __init__(self) -> None:
        self._domains: dict[DomainCategory, Domain] = {d.category: d for d in _BUILTIN_DOMAINS}

    def get(self, category: DomainCategory) -> Domain:
        """指定カテゴリのDomainを返す。未登録の場合はGENERICへ安全にフォールバックする
        (存在しないDomainでクラッシュさせない)。"""
        return self._domains.get(category, self._domains[DomainCategory.GENERIC])

    def resolve_from_keywords(self, text: str) -> Domain:
        """テキスト中のキーワードから最も一致するDomainを推定する。
        一致が無ければGENERICを返す(必ず何らかのDomainが得られることを保証する)。
        """
        lowered = text.lower()
        for domain in self._domains.values():
            if domain.category == DomainCategory.GENERIC:
                continue
            for concept in domain.typical_concepts:
                if concept.name in lowered:
                    return domain
            for action in domain.typical_actions:
                if action in lowered:
                    return domain
        return self._domains[DomainCategory.GENERIC]

    def all_domains(self) -> tuple[Domain, ...]:
        """登録済みの全Domainを返す(GENERICを含む)。"""
        return tuple(self._domains.values())


_BUILTIN_DOMAINS: tuple[Domain, ...] = (
    Domain(
        category=DomainCategory.SHOPPING,
        display_name="Shopping",
        typical_concepts=(
            DomainConcept("item", "購入・記録の対象となる品目"),
            DomainConcept("price", "品目の価格"),
            DomainConcept("quantity", "品目の数量"),
            DomainConcept("store", "購入先"),
        ),
        typical_actions=("add_item", "remove_item", "mark_purchased", "set_budget"),
    ),
    Domain(
        category=DomainCategory.HOSPITAL,
        display_name="Hospital",
        typical_concepts=(
            DomainConcept("patient", "診療・記録の対象となる人物"),
            DomainConcept("appointment", "診察の予定"),
            DomainConcept("symptom", "症状の記録"),
            DomainConcept("medication", "処方・服薬記録"),
        ),
        typical_actions=("schedule_appointment", "record_symptom", "record_medication"),
    ),
    Domain(
        category=DomainCategory.ATTENDANCE,
        display_name="Attendance",
        typical_concepts=(
            DomainConcept("member", "出欠管理の対象となる人物"),
            DomainConcept("session", "出欠を記録する単位(授業・会議等)"),
            DomainConcept("status", "出席/欠席/遅刻等の状態"),
        ),
        typical_actions=("check_in", "check_out", "mark_absent"),
    ),
    Domain(
        category=DomainCategory.DIARY,
        display_name="Diary",
        typical_concepts=(
            DomainConcept("entry", "1回分の記録"),
            DomainConcept("date", "記録の日付"),
            DomainConcept("mood", "気分・状態の記録"),
        ),
        typical_actions=("add_entry", "edit_entry", "tag_entry"),
    ),
    Domain(
        category=DomainCategory.INVENTORY,
        display_name="Inventory",
        typical_concepts=(
            DomainConcept("stock", "在庫として管理される品目"),
            DomainConcept("location", "保管場所"),
            DomainConcept("threshold", "発注・警告の閾値"),
        ),
        typical_actions=("adjust_stock", "set_threshold", "record_shipment"),
    ),
    Domain(
        category=DomainCategory.TASK_MANAGEMENT,
        display_name="Task Management",
        typical_concepts=(
            DomainConcept("task", "管理・記録の対象となる作業項目"),
            DomainConcept("deadline", "作業の期限"),
            DomainConcept("priority", "作業の優先度"),
            DomainConcept("status", "未着手/進行中/完了等の状態"),
        ),
        typical_actions=("add_task", "complete_task", "delete_task", "set_priority"),
    ),
    Domain(
        category=DomainCategory.SURVEY,
        display_name="Survey",
        typical_concepts=(
            DomainConcept("question", "アンケートの設問"),
            DomainConcept("answer", "回答内容"),
            DomainConcept("respondent", "回答者"),
            DomainConcept("choice", "選択肢"),
        ),
        typical_actions=("add_question", "submit_response", "view_results"),
    ),
    Domain(
        category=DomainCategory.SCHEDULE,
        display_name="Schedule",
        typical_concepts=(
            DomainConcept("event", "管理対象となる予定"),
            DomainConcept("time", "予定の日時"),
            DomainConcept("reminder", "予定の通知"),
            DomainConcept("participant", "予定の参加者"),
        ),
        typical_actions=("add_event", "edit_event", "delete_event", "set_reminder"),
    ),
    Domain(
        category=DomainCategory.HOUSEHOLD_BUDGET,
        display_name="Household Budget",
        typical_concepts=(
            DomainConcept("transaction", "収入・支出の1件の記録"),
            DomainConcept("category", "費目(食費・光熱費等)"),
            DomainConcept("amount", "金額"),
            DomainConcept("budget_limit", "費目ごとの予算上限"),
        ),
        typical_actions=("add_transaction", "set_budget_limit", "view_summary"),
    ),
    Domain(
        category=DomainCategory.CHILD_GROWTH,
        display_name="Child Growth",
        typical_concepts=(
            DomainConcept("child", "記録対象となる子ども"),
            DomainConcept("measurement", "身長・体重等の測定値"),
            DomainConcept("milestone", "発達の節目(初めて歩いた等)"),
            DomainConcept("photo", "成長記録に添える写真"),
        ),
        typical_actions=("add_measurement", "add_milestone", "add_photo"),
    ),
    Domain(
        category=DomainCategory.FISHING_LOG,
        display_name="Fishing Log",
        typical_concepts=(
            DomainConcept("catch", "釣った魚1件の記録"),
            DomainConcept("species", "魚の種類"),
            DomainConcept("location", "釣った場所"),
            DomainConcept("size", "大きさ(体長)"),
            DomainConcept("weight", "重さ"),
        ),
        typical_actions=("add_catch", "record_location", "record_size"),
    ),
    Domain(
        category=DomainCategory.HABIT_TRACKING,
        display_name="Habit Tracking",
        typical_concepts=(
            DomainConcept("habit", "継続したい習慣"),
            DomainConcept("streak", "継続日数の記録"),
            DomainConcept("category", "習慣の分類(健康・運動等)"),
        ),
        typical_actions=("check_habit", "add_habit", "view_streak"),
    ),
    Domain(
        category=DomainCategory.STUDY,
        display_name="Study",
        typical_concepts=(
            DomainConcept("subject", "学習する科目・分野"),
            DomainConcept("material", "教材・参考書"),
            DomainConcept("progress", "学習の進捗"),
            DomainConcept("certification", "取得を目指す資格"),
        ),
        typical_actions=("add_study_log", "track_progress"),
    ),
    Domain(
        category=DomainCategory.TRAVEL,
        display_name="Travel",
        typical_concepts=(
            DomainConcept("destination", "旅行先"),
            DomainConcept("accommodation", "宿泊先"),
            DomainConcept("itinerary", "旅程"),
            DomainConcept("expense", "旅行にかかる費用"),
        ),
        typical_actions=("add_destination", "plan_itinerary"),
    ),
    Domain(
        category=DomainCategory.GENERIC,
        display_name="Generic",
        typical_concepts=(DomainConcept("item", "汎用的な記録対象"),),
        typical_actions=("add_item", "remove_item"),
    ),
)
