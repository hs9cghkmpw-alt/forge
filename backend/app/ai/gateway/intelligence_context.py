"""Intelligence Context Resolver — **Provider選択の前に知識を決める**
(FORGE-017A §8・§15、2026-08-24)。

---

## AIRouterへ詰め込まない

017A §8の指示である。「parallel routerを作らない」は維持しつつ、
`AIRouter`へ Knowledge / Memory / Personal / App / Policy / Adapter /
Tool を**全部入れない**。

```
IntelligenceContextResolver     ← 何を知っているかを決める
        ↓ resolved context
AIRouter                        ← どのProviderへ投げるかを決める
        ↓
Provider
```

責務が分かれている理由は2つある。

1. **`AIRouter`が神クラスになる。** すでにRouting・Circuit Breaker・
   Quota・Latency予算・Experience記録・Local昇格を持っている。
   ここへ知識検索まで入れると、変更のたびに全部を読む必要が出る
   （Maintainability First）
2. **順番が逆になる。** 知識はProviderを選ぶ前に決まっていなければ
   ならない。Cloudへ行くかLocalへ行くかで渡す知識が変わると、
   「同じ問いに同じ知識で答えた」という比較ができなくなり、
   Benchmarkの前提が崩れる

## Resolverは順位を付けない

**Provider rankingをしない**（017A §8）。ここが答えるのは「この
Taskでは何を知っているべきか」だけである。どのProviderが良いかは
`AIRouter`と`LocalPromotionGate`の仕事で、こちらは知らない。
"""

from __future__ import annotations

from app.ai.gateway.knowledge import KnowledgeContext, KnowledgeStore, default_knowledge_store
from app.ai.gateway.learning_contract import IntelligenceScope
from app.ai.gateway.tasks import ForgeTask

__all__ = [
    "IntelligenceContextResolver",
    "default_intelligence_resolver",
]

#: Taskごとに、どの語彙が要るか。
#:
#: **全部渡さない。** 33件を毎回渡すと、AIは選択肢の多さで外すし
#: （014 §7でDESIGN_CHOICE_AXESを絞ったのと同じ理由）、Local Modelの
#: 文脈長を無駄に使う。
_TASK_PREFIXES: dict[ForgeTask, tuple[str, ...]] = {
    ForgeTask.ENTITY_SYNTHESIS: ("design_role.metric.", "design_role.text."),
    ForgeTask.FORGE_LANGUAGE_UPDATE: ("design_role.",),
    ForgeTask.COGNITIVE_STAGE: ("design_role.",),
    # 会話ステップはDesign Languageを必要としない——何を作るかを
    # 聞いている段階であって、どう見せるかはまだ決めていない。
    ForgeTask.CONVERSATION_STEP: (),
}


class IntelligenceContextResolver:
    """1回の推論のための知識を解決する。

    **Provider rankingはしない**（017A §8）。
    """

    _DEFAULT_LIMIT = 12

    def __init__(self, knowledge: KnowledgeStore | None = None) -> None:
        self._knowledge = knowledge or default_knowledge_store()

    def resolve(
        self,
        task: ForgeTask,
        *,
        scope: IntelligenceScope = IntelligenceScope.GLOBAL,
        app_id: str | None = None,
        limit: int | None = None,
    ) -> KnowledgeContext:
        """このTaskで使う知識。

        `scope`が`APP`なら、そのAppの知識とGlobalの知識が混ざる。
        **Personalは別のscopeの解決に現れない**（017 §17）。
        """
        prefixes = _TASK_PREFIXES.get(task, ("design_role.",))
        if not prefixes:
            return KnowledgeContext(scope=scope, app_id=app_id)

        available = self._knowledge.retrieve(scope=scope, app_id=app_id)
        matched = tuple(
            entry for entry in available
            if any(entry.entry_id.startswith(prefix) for prefix in prefixes)
        )
        capped = matched[: limit if limit is not None else self._DEFAULT_LIMIT]
        return KnowledgeContext(entries=capped, scope=scope, app_id=app_id)


_DEFAULT_RESOLVER: IntelligenceContextResolver | None = None


def default_intelligence_resolver() -> IntelligenceContextResolver:
    global _DEFAULT_RESOLVER  # noqa: PLW0603 — プロセス内Singleton
    if _DEFAULT_RESOLVER is None:
        _DEFAULT_RESOLVER = IntelligenceContextResolver()
    return _DEFAULT_RESOLVER
