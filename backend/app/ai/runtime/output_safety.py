"""Output Safety Checker(FORGE-AI-CONNECT-001 TD20対応、2026-08-11)。

生成された最終Forge Document(JSON)を検査し、過剰な個人情報収集等の
安全性上の懸念を検出する。**検出のみを行い、生成そのものはブロック
しない**(TD21のInjection Guardと同じ設計方針。誤検知によってForge体験
「話しかけたらすぐアプリができる」を壊すリスクを、無条件ブロックより
優先して避ける。`TECH_DEBT.md` TD20・TD21参照)。

既存のValidator(`app/ai/validators/schema_validator.py`)は構造的整合性
(型・参照・再帰深度等)のみを検査し、文書の「意味」は見ない。この
チェッカーは、文書中の**全ての文字列値**(Widgetのlabel/placeholder/
hint_text/title等、キー名を限定せず網羅的に走査する)を対象に、個人情報
収集を示唆するキーワードパターンとの一致を判定する。forge_ai/の
lexicon.pyと同じ「決定的・キーワードベースの一致判定」という設計思想を
踏襲しており、AIによる意味理解や機械学習的な検出ではない(過剰な
主張をしないため、モジュール名・docstringともに「Checker」
「パターン一致」と明記する)。

**既知の限界**: キーワード一致に基づく検出であり、婉曲表現・別言語・
表記ゆれには対応しない(例: 「暗証番号」は検出するが、それを意図的に
言い換えた表現までは検出できない)。「誤解を招く選択肢を持つUI」等、
TD20が言及するもう一方の懸念(構造上は正しいが意味的に不誠実なUI)は、
汎用的な検出方法が確立できておらず、今回のスコープに含めていない。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

# 高リスク: 単体で収集要求されているだけでも問題になりうるPII。
_HIGH_RISK_PII_PATTERNS: tuple[str, ...] = (
    "マイナンバー",
    "クレジットカード番号",
    "カード番号",
    "セキュリティコード",
    "cvv",
    "cvc",
    "暗証番号",
    "銀行口座番号",
    "口座番号",
    "パスワード",
    "ソーシャルセキュリティ番号",
    "運転免許証番号",
    "パスポート番号",
    "マイナンバーカード",
)

# 中リスク: 文脈次第では正当な用途もあるが、注意が必要なPII。
_MEDIUM_RISK_PII_PATTERNS: tuple[str, ...] = (
    "生年月日",
    "自宅住所",
    "電話番号",
    "本名",
    "身分証",
)


@dataclass(frozen=True)
class SafetyIssue:
    """検出された1件の安全性上の懸念。"""

    path: str
    category: str  # 現状は"excessive_pii_collection"のみ
    severity: str  # "high" | "medium"
    matched_phrase: str
    message: str


@dataclass(frozen=True)
class SafetyCheckResult:
    """`OutputSafetyChecker.check()`の戻り値。

    `safe`は`severity="high"`の`issue`が1件も無い場合に`True`になる
    (`medium`は記録するが`safe`の判定には使わない。誤検知で`safe=False`
    になりすぎないようにするための、意図的な閾値設計)。
    """

    safe: bool
    issues: tuple[SafetyIssue, ...] = ()


def _iter_string_leaves(node: Any, path: str) -> Iterator[tuple[str, str]]:
    """`node`(Forge Documentのdict、または途中のdict/list/プリミティブ)を
    再帰的に走査し、文字列の葉ノードを`(path, text)`として列挙する。
    キー名を限定しない(特定のWidget種別・フィールド名に依存しないため、
    将来Widgetが増えても追従できる)。"""
    if isinstance(node, str):
        if node:
            yield path, node
        return
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _iter_string_leaves(value, f"{path}.{key}" if path else str(key))
        return
    if isinstance(node, list):
        for index, value in enumerate(node):
            yield from _iter_string_leaves(value, f"{path}[{index}]")
        return
    # int/float/bool/None等はテキストとして扱わない。


class OutputSafetyChecker:
    """生成されたForge Document(dict)を検査する。"""

    def check(self, document: dict[str, Any]) -> SafetyCheckResult:
        issues: list[SafetyIssue] = []
        for path, text in _iter_string_leaves(document, ""):
            issues.extend(self._check_text(path, text))
        safe = not any(issue.severity == "high" for issue in issues)
        return SafetyCheckResult(safe=safe, issues=tuple(issues))

    def _check_text(self, path: str, text: str) -> list[SafetyIssue]:
        found: list[SafetyIssue] = []
        lowered = text.lower()
        for phrase in _HIGH_RISK_PII_PATTERNS:
            if phrase in text or phrase in lowered:
                found.append(
                    SafetyIssue(
                        path=path,
                        category="excessive_pii_collection",
                        severity="high",
                        matched_phrase=phrase,
                        message=f"'{phrase}' の収集を示唆するテキストが見つかりました({path})。",
                    )
                )
        for phrase in _MEDIUM_RISK_PII_PATTERNS:
            if phrase in text:
                found.append(
                    SafetyIssue(
                        path=path,
                        category="excessive_pii_collection",
                        severity="medium",
                        matched_phrase=phrase,
                        message=f"'{phrase}' の収集を示唆するテキストが見つかりました({path})。",
                    )
                )
        return found
