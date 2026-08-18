"""Design Intent — **AIに意味的役割を選ばせる**段
(FORGE-R1-ENTRY-AND-DESIGN-LANGUAGE-014、2026-08-17)。

---

## なぜこの段が要るのか

014 の最初の版では、`style_role` を出しているのが **Compiler だけ**
だった。つまり「AIは意味を決める。Forgeは品質を保証する」の
**AI側が動いていなかった**（TD69）。

Compiler が出せるのは「これはセクション見出しである」「これは繰り返し
項目の一覧である」という**構造上の事実**から決まる role に限られる。
「この画面はゆったり見せるべきか、詰めて見せるべきか」は構造からは
決まらない——利用者のNeedから来る意味であり、**AIが決めるもの**である。

## 設計

### 値を聞かない

`font_size` も色コードも聞かない。聞くのは軸ごとの**択一**だけ。

```
screen_density  → density.compact | density.normal | density.relaxed
list_surface    → surface.card    | surface.elevated
```

### 自由記述にしない

閉じた選択肢から選ばせる。理由は2つある。

1. Runtimeが保証できない値が入らない
2. **選ばれなかった候補が分かる** — 後から「このNeedでは relaxed では
   なく compact が受け入れられた」という対比が学習素材になる。
   自由記述だと「他に何がありえたか」が残らない

Local AIにとっても、生成より選択の方がはるかに易しい（Product
Direction §3「Local AIを小さく・安く・高品質に」）。

### AIの答えを信用しない

`is_valid_choice()` で軸ごとに検証する。**語彙全体に含まれるだけでは
通さない** — `metric.primary` は正しい role だが `screen_density` の
答えとしては誤りである。

外れた場合・AIを呼べなかった場合は**決定的な既定値へ落ちる**。
落ちたこと自体を `fallback_axes` に残すので、「AIが選んだ」と
「Forgeが既定で埋めた」が Evidence 上で混ざらない
（`CLAUDE.md` §3「分からないものを楽観側へ倒さない」）。

## AIを呼べない場合も壊さない

Provider が無い・失敗した・応答が壊れている——どの場合でも既定値で
成立する。Design Language が入ったことで**生成そのものが不安定になる
のは本末転倒**である。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from forge_ai.contracts.design_language_contract import DesignLanguageGuidance
from forge_ai.prompt.prompt_builder import PromptBuilder
from forge_ai.provider.provider_interface import AIProvider

__all__ = ["DesignIntent", "DesignIntentSelector"]

# 決定的な既定値。**AIが選ばなかったときの答え**であり、
# 「一番無難なもの」を選んである。
_DEFAULTS: dict[str, str] = {
    "screen_density": "density.normal",
    "list_surface": "surface.card",
}


@dataclass(frozen=True)
class DesignIntent:
    """1つの生成物についての、意味的役割の選択。

    **どの軸をAIが選び、どの軸が既定へ落ちたか**を持つ。
    混ぜると「AIの選択が受け入れられた」と「既定が受け入れられた」が
    区別できなくなり、Local AIの学習で嘘になる。
    """

    choices: dict[str, str] = field(default_factory=lambda: dict(_DEFAULTS))
    fallback_axes: tuple[str, ...] = ()
    """AIの答えを採用**しなかった**軸。全軸ここに入る＝AIは一度も
    選べていない。"""

    @property
    def ai_selected(self) -> bool:
        """AIが1つでも選べたか。"""
        return bool(self.choices) and len(self.fallback_axes) < len(self.choices)

    def role_for(self, axis: str) -> str:
        return self.choices.get(axis, _DEFAULTS.get(axis, ""))

    @classmethod
    def default(cls) -> "DesignIntent":
        """AIを呼ばなかった場合。**全軸がfallback**である。"""
        return cls(choices=dict(_DEFAULTS), fallback_axes=tuple(_DEFAULTS))


class DesignIntentSelector:
    """AIへ軸を提示し、答えを検証して`DesignIntent`にする。

    `EntitySynthesizer`と同じ形にしてある——AIに決めさせ、**Forge側で
    決定的に検証する**（AIの出力をそのまま信用しない）。
    """

    def __init__(
        self,
        provider: AIProvider,
        prompt_builder: PromptBuilder | None = None,
        *,
        guidance: DesignLanguageGuidance | None = None,
    ) -> None:
        self._provider = provider
        self._prompt_builder = prompt_builder or PromptBuilder()
        # 語彙の**中身**はforge_aiの外にある。ここが知っているのは
        # `DesignLanguageGuidance`という形だけで、`app.*`というモジュール
        # 名は1文字も現れない（§5、`design_language_contract.py`参照）。
        #
        # 渡されなければ何も選ばせない（既定値のまま）。これは「壊れて
        # いる」ではなく「語彙を渡されていない」という状態である。
        self._guidance = guidance or DesignLanguageGuidance()

    def select(
        self, *, need_summary: str, entity_label: str, field_labels: tuple[str, ...]
    ) -> DesignIntent:
        if not self._guidance.is_usable:
            return DesignIntent.default()

        try:
            response = self._provider.complete(
                self._prompt_builder.build_design_intent_prompt(
                    need_summary=need_summary,
                    entity_label=entity_label,
                    field_labels=field_labels,
                    axes=self._guidance.to_prompt_axes(),
                )
            )
            raw = response.structured if isinstance(response.structured, dict) else {}
        except Exception:  # noqa: BLE001 — AIが呼べなくても生成は続ける
            # **Design Languageが入ったせいで生成が落ちる**のは本末転倒。
            # 既定値で成立させ、fallbackとして記録する。
            return DesignIntent.default()

        choices: dict[str, str] = {}
        fallbacks: list[str] = []
        for entry in self._guidance.axes:
            axis = entry.axis
            if not axis:
                continue
            answer = raw.get(axis)
            if self._guidance.validate(axis, answer):
                choices[axis] = str(answer)
            else:
                # 語彙全体に含まれていても、**その軸の答えでなければ通さない**。
                choices[axis] = _DEFAULTS.get(axis, "")
                fallbacks.append(axis)
        return DesignIntent(choices=choices, fallback_axes=tuple(fallbacks))
