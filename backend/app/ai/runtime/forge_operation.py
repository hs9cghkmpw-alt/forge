"""Forming Operation(UPDATE) — 既存Forge Documentを会話で育てる
(FORGE-PRODUCT-VISION-002 TD40対応、2026-08-11)。

design doc(`docs/spec/FORGE_PRODUCT_VISION_002_CONVERSATIONAL_
ARCHITECTURE.md` B.4)が挙げた2案のうち、実機検証(TECH_DEBT.md TD40
追記)で確認した「案2」(`responseSchema`を使わず、フリーフォームJSON+
`validate_forge_document()`で事後検証)を実装する。

**技術検証で確認した事実(重要)**: Forge DocumentのWidget木は再帰的な
構造であり、Gemini `responseSchema`(`$ref`未対応)へ「type: object」
とだけ渡して`properties`を書かない形にすると、その部分は**空
オブジェクトで返ってくる**(既存の構造化データを丸ごと失う)。
`responseSchema`を送らずフリーフォームJSONとして生成させると、既存の
構造を維持しながら新しい要素を追加できることを実機で確認した
(`GeminiProvider.complete_structured()`のdocstring、`response_schema={}`
で送信を省略する分岐を参照)。

ForgeAIPipelineErrorのcategoryを持たない、独立した薄いモジュール
(ADR-014と同じ思想: Cognitive Pipelineにもforge_ai/にも依存しない)。
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.ai.gateway.ai_router import NoProviderAvailableError
from app.ai.runtime.provider_router import AIProvider
from app.ai.validators.schema_validator import ValidationResult, validate_forge_document

# `prompt_pipeline.py`のMAX_REPAIR_ATTEMPTSと同じ思想(無限リトライ禁止、
# 共通指示書6.5節)。UPDATEは「生成し直す」1往復+「Validatorのエラーを
# 見せて直させる」1往復の、計2回までとする。
MAX_UPDATE_ATTEMPTS = 2


@dataclass(frozen=True)
class UpdateResult:
    success: bool
    forge_document: dict | None
    validation: ValidationResult | None
    attempts: int
    error_message: str | None = None


_UPDATE_PROMPT_TEMPLATE = """あなたはForgeという製品のバックエンドです。
既に生成済みのアプリ(Forge Language JSON)を、ユーザーの変更要求に
従って更新します。

厳守事項:
1. 既存のWidget構成(column/row/checklist/text_field/button/
   choice_field/date_field/slider等)・state型(string/number/boolean/
   checklist/record_list等)・Action構成(add_item/add_record等)の形式を
   そのまま踏襲すること。知らない新しいtype名を発明しないこと。
2. 変更要求に関係が無い既存の部分(既存のWidget・stateの値等)は、
   そのまま維持すること。
3. 説明文やMarkdownのコードブロック記法(```等)は一切含めず、更新後の
   完全なJSON文書だけを返すこと。

[既存のForge Document]
{current_document}

[ユーザーの変更要求]
{change_request}
{repair_context}"""

_REPAIR_CONTEXT_TEMPLATE = """

[直前の出力の問題点(修正すること)]
{issues}"""


class ForgeOperationEngine:
    """`apply_update()`が唯一の公開API。"""

    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    def apply_update(self, current_document: dict, change_request: str) -> UpdateResult:
        repair_context = ""
        candidate: dict | None = None
        validation: ValidationResult | None = None

        for attempt in range(1, MAX_UPDATE_ATTEMPTS + 1):
            prompt = _UPDATE_PROMPT_TEMPLATE.format(
                current_document=json.dumps(current_document, ensure_ascii=False),
                change_request=change_request,
                repair_context=repair_context,
            )
            try:
                candidate = self._provider.complete_structured(prompt, {})
            except NoProviderAvailableError:
                # FORGE-AI-FOUNDATION-010 Phase B: **「AIが無い」と
                # 「AIの出力が悪い」を混ぜない**。
                #
                # `UpdateResult(success=False)`は「AIには聞けたが、
                # 使える更新結果を得られなかった」という意味であり、
                # HTTP層はこれを`UpdateOperationError`(利用者の要求の
                # 問題でありうる)へ変換する。枠切れ・Circuit Breakerで
                # **1つも呼べなかった**場合は種類が違う失敗であり、
                # 利用者へ伝えるべき言葉も対処も違う。そのまま通して、
                # HTTP層でProviderErrorとして扱わせる。
                raise
            except Exception as exc:  # noqa: BLE001 — Provider呼び出し失敗を、成功/失敗が明確なUpdateResultへ変換する
                return UpdateResult(
                    success=False, forge_document=None, validation=None, attempts=attempt,
                    error_message=f"Provider呼び出しに失敗しました: {exc}",
                )

            if not isinstance(candidate, dict):
                repair_context = _REPAIR_CONTEXT_TEMPLATE.format(
                    issues="直前の出力はJSONオブジェクトではありませんでした。"
                )
                continue

            validation = validate_forge_document(candidate)
            if validation.valid:
                return UpdateResult(
                    success=True, forge_document=candidate, validation=validation, attempts=attempt,
                )
            repair_context = _REPAIR_CONTEXT_TEMPLATE.format(
                issues="\n".join(f"- {e.path}: {e.message}" for e in validation.errors)
            )

        return UpdateResult(
            success=False, forge_document=candidate, validation=validation, attempts=MAX_UPDATE_ATTEMPTS,
            error_message=f"Validatorに合格しないまま、上限({MAX_UPDATE_ATTEMPTS}回)に達しました。",
        )
