"""Forge Template System — 基底定義。

FORGE-MILESTONE-002 PHASE4。「Template」とは、画面の構造(Widget構成・
State構成)を決める再利用可能な生成関数である。「Category」(買い物・旅行等)は
Templateとは別の概念で、「どのTemplateを、どんなパラメータで呼び出すか」を
決める判定ロジック(mock_generator.py側)に属する。

例:
  - 「買い物メモを作って」というCategory判定 → ChecklistTemplateを、
    title="買い物メモ", items=[...] というパラメータで呼び出す。
  - 「満足度アンケートを作って」というCategory判定 → FormTemplateを、
    質問リストというパラメータで呼び出す。

この分離により、新しいCategory(例:「引っ越しリスト」)を追加する際、
既存Templateのどれかにパラメータを与えるだけで済み、Template自体の
実装を毎回増やす必要が無くなる(PHASE5「カテゴリ追加しやすい構造」)。
"""

from __future__ import annotations

from typing import Any


def build_screen_shell(
    screen_id: str,
    title: str,
    state: dict[str, Any],
    body: dict[str, Any],
) -> dict[str, Any]:
    """全Templateが共有する、1画面分のJSON骨格を組み立てる共通ヘルパー。"""
    return {
        "id": screen_id,
        "title": title,
        "state": state,
        "body": body,
    }


def build_document(
    app_title: str,
    initial_screen_id: str,
    screens: list[dict[str, Any]],
    version: str = "1.0",
) -> dict[str, Any]:
    """全Templateが共有する、文書全体(version/app/screens)を組み立てる共通ヘルパー。

    version は既定で"1.0"(v1.0時代のWidgetしか使わないTemplateは、
    実際にv1.0のRuntimeでも解釈できるため、正直に"1.0"と申告する。
    docs/spec/LANGUAGE_FREEZE.md の「versionは実際に必要な最小バージョンを
    表す」という原則に従う)。v1.1専用Widget(heading/checkbox/card/list/
    divider/form)を1つでも使うTemplateは、呼び出し側で明示的に
    `version="1.1"`を渡すこと。
    """
    return {
        "version": version,
        "app": {"title": app_title},
        "initial_screen_id": initial_screen_id,
        "screens": screens,
    }
