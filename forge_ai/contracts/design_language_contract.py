"""Design Language Contract — forge_aiが**backendを知らずに**意味的役割を
扱うための境界(FORGE-R1-CLOSURE-015 §5、2026-08-17)。

---

## 何が問題だったか

`forge_ai/core/pipeline.py`が、Production時だけ遅延importで

    from app.ai.runtime.design_language import design_choice_guidance

を呼んでいた。コメントには「forge_aiはbackendをimportしない」と書いて
あったが、**実際にはしていた**。

しかもimportに失敗しても例外にせず、空の軸を返していた。結果:

```
Production          axesが解決できる → Design Intent 動く
forge_ai standalone ImportError     → Design Intent 動かない
```

同じコードが、動く環境と動かない環境で**別の振る舞いをする**。
forge_ai単体のテストが何件通っても、本番で語彙が渡っていることの
証拠にならない(だから§5のテストはbackend側に置いてある)。

## どう直したか

語彙の**形**をforge_ai側の契約として定義し、中身はbackendが注入する。

```
backend が持つもの : 実際の語彙（33 role、軸、検証関数）
forge_ai が持つもの: 「軸とは何か」という形だけ

    backend ──(注入)──> DesignLanguageGuidance ──> forge_ai pipeline
```

forge_aiは`app`というモジュール名を1文字も知らない。**知らないことが
テストで確認できる**(`test_dependency_boundary.py`)。

## 契約が無い場合

`DesignLanguageGuidance`が渡されなければ、Design Intentは動かず既定値
で成立する。これは「壊れている」ではなく「語彙を渡されていない」と
いう状態であり、**standaloneとProductionで挙動が違うのとは別**である
——渡せば同じように動く。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable

__all__ = ["DesignAxis", "DesignChoice", "DesignLanguageGuidance", "DesignChoiceValidator"]


@dataclass(frozen=True)
class DesignChoice:
    """1つの選択肢。**意味と、使う/避ける条件を必ず持つ。**

    IDだけを渡す案もあったが、それではAIは選べない——`density.compact`
    という文字列から「一覧向き」だと読み取れるのは、その語彙を既に
    知っている者だけである。将来Local AIへ渡すKnowledgeも同じ形で
    ある(§12)。
    """

    id: str
    meaning: str
    use_when: str = ""
    avoid_when: str = ""

    def to_prompt_dict(self) -> dict[str, str]:
        return {
            "id": self.id, "meaning": self.meaning,
            "use_when": self.use_when, "avoid_when": self.avoid_when,
        }


@dataclass(frozen=True)
class DesignAxis:
    """1つの問い(軸)と、その閉じた答えの集合。

    **自由記述にしない**のがこの型の要点である。選択肢が閉じている
    から、選ばれなかった候補が分かり、後から対比として学べる。
    """

    axis: str
    options: tuple[DesignChoice, ...]

    def to_prompt_dict(self) -> dict[str, object]:
        return {"axis": self.axis, "options": [o.to_prompt_dict() for o in self.options]}


@runtime_checkable
class DesignChoiceValidator(Protocol):
    """軸ごとに答えを検証する。**語彙全体に在るだけでは通さない。**

    `metric.primary`は正しいroleだが`screen_density`の答えとしては
    誤りである——この判定ができることが、この契約の存在理由である。
    """

    def __call__(self, axis: str, role: object) -> bool: ...


@dataclass(frozen=True)
class DesignLanguageGuidance:
    """AIへ提示する軸一式と、その答えの検証。

    **これがforge_aiとbackendの唯一の接点**である。forge_aiはこの型
    だけを知り、`app.ai.runtime.design_language`というモジュールの
    存在を知らない。
    """

    axes: tuple[DesignAxis, ...] = ()
    is_valid_choice: DesignChoiceValidator | Callable[[str, object], bool] | None = None

    @property
    def is_usable(self) -> bool:
        """AIへ聞いてよいか。

        **検証できない答えは採用しない**ので、検証関数が無ければ
        軸があっても聞かない。聞いて採用してしまうと、Runtimeが保証
        できない値が生成物へ入る。
        """
        return bool(self.axes) and self.is_valid_choice is not None

    def to_prompt_axes(self) -> tuple[dict[str, object], ...]:
        return tuple(a.to_prompt_dict() for a in self.axes)

    def validate(self, axis: str, role: object) -> bool:
        if self.is_valid_choice is None:
            return False
        return bool(self.is_valid_choice(axis, role))
