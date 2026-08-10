"""Input Normalizer(FORGE-MILESTONE-007第一段階、M006 5章)。

前後空白除去・表記揺れの一部(全角記号→半角相当)を扱う。決定的・
ルールベースであり、LLM Providerを必要としない。

第一段階では、以下は扱わない(既知の制限、正直な申告):
* 口語・誤字・省略の訂正(NLPライブラリが必要になるため、新規依存
  禁止の制約から今回は対象外)
* 複数要求の分割
* 日本語と英語の混在の正規化
Normalizationはユーザーの意味を勝手に変更してはならない、という
M006の原則を守るため、これらの「訂正」を伴う処理は、確信が持てない
限り行わない設計にしている。
"""

from __future__ import annotations

from forge_ai.core.orchestration.cognitive_types import NormalizedInput

# 全角記号 -> 半角/標準的な表記への対応表(意味を変えない、表記揺れのみ)
_FULLWIDTH_TO_HALFWIDTH = {
    "？": "?",
    "！": "!",
    "　": " ",  # 全角スペース
}


class InputNormalizer:
    """`InputNormalizerProtocol`を満たす。"""

    def normalize(self, raw_input: str) -> NormalizedInput:
        """前後空白除去・内部の連続空白の圧縮・一部の全角記号正規化を行う。
        元の入力(`original_text`)は変更せずそのまま保持する。
        """
        text = raw_input
        for full, half in _FULLWIDTH_TO_HALFWIDTH.items():
            text = text.replace(full, half)
        # 内部の連続空白を1つへ圧縮する(前後の空白は別途strip)。
        text = " ".join(text.split())
        return NormalizedInput(original_text=raw_input, normalized_text=text)
