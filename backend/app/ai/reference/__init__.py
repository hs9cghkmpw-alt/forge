"""開発用 Reference Provider 群。Product Runtime の自動 Routing とは分離する。"""

from .openai_reference import (
    DEFAULT_OPENAI_REFERENCE_MODEL,
    OPENAI_REFERENCE_API_BASE,
    OPENAI_REFERENCE_PROVIDER_ID,
    OpenAIReferenceProvider,
    build_reference_judge_prompt,
    judge_candidate,
)

__all__ = [
    "DEFAULT_OPENAI_REFERENCE_MODEL",
    "OPENAI_REFERENCE_API_BASE",
    "OPENAI_REFERENCE_PROVIDER_ID",
    "OpenAIReferenceProvider",
    "build_reference_judge_prompt",
    "judge_candidate",
]
