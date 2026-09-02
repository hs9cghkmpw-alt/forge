// 利用者から見える「AI」の見せ方を、**1箇所に閉じる**。
//
// ---
//
// ## なぜ要るのか
//
// Forge は OpenAI でも Claude でも Gemini でも Ollama でもない
// （Constitution §9）。Provider と base model は差し替え可能な実装手段で
// あって、製品の正体ではない。
//
// それまでホーム画面には **Provider を利用者が切り替えるトグル**があった。
// これは2つの意味で方針違反である。
//
// 1. 内部事情（Provider 名）を通常利用者へ見せている（§4・§9）
// 2. **どの AI 経路を使うかを利用者に決めさせている。**
//    Forge が内部で選ぶべきものである
//
// さらに悪いことに、片方の選択肢は疑似データ（Test Double）だった。
// 利用者が「AI を使う」つもりで選べない状態を、選択肢として並べていた。
//
// ## 通常利用者が認識してよいのは「AIモード」だけ
//
// Local / Cloud / Reuse / Tool / Fallback のどれを使ったかは Forge の内部
// 事情である。Evidence と開発者診断では実 Provider 名と Model 名を
// **正確に**残し続ける——ここで消すのは**通常画面の表示だけ**である。
//
// ## ただし、嘘はつかない
//
// AI に接続していないのに「AIモード」と表示してはならない。
// `AiModeState` は**実状態**を表し、疑似データのときは疑似データだと言う。

import 'package:flutter/material.dart';

import '../core/config/app_config.dart';
import '../core/theme/forge_theme.dart';

/// 利用者へ見せる、AI の**実状態**。
///
/// **表示と実状態を一致させるための型である。** 「AIモード」と出してよい
/// のは `ready` / `working` のときだけで、疑似データや未接続を混ぜない。
enum AiModeState {
  /// AI を使う経路で動く。**ここが通常の「AIモード」である。**
  ready,

  /// いま AI が考えている（要求を送信して応答を待っている）。
  working,

  /// 準備中（接続確認中で、まだ実状態が確定していない）。
  preparing,

  /// 疑似データ（Test Double）。**AI には接続していない。**
  simulated,

  /// AI に接続できない。
  unavailable,
}

/// 通常利用者へ見せる正式名称。**Provider 名を出さない。**
const String kAiModeName = 'AIモード';

extension AiModeStateDisplay on AiModeState {
  /// 画面に出す短い名前。
  String get label => switch (this) {
        AiModeState.ready => kAiModeName,
        AiModeState.working => 'AIが考えています…',
        AiModeState.preparing => '$kAiModeNameを準備しています…',
        // **「AIモード」と呼ばない。** 接続していないのだから。
        AiModeState.simulated => 'お試しモード',
        AiModeState.unavailable => 'AIに接続できません',
      };

  /// 補足の一文（Tooltip / Semantics）。
  String get description => switch (this) {
        AiModeState.ready =>
          'AIを使って、あなたに合った道具を考えます。使うAIはForgeが選びます。',
        AiModeState.working => 'AIがあなたの話から、必要な道具を考えています。',
        AiModeState.preparing => 'AIを使う準備をしています。',
        AiModeState.simulated =>
          'これはお試し用の疑似データです。AIには接続していません。',
        AiModeState.unavailable =>
          'いまAIに接続できません。しばらくしてからもう一度お試しください。',
      };

  /// 「AI が動いている」と言ってよい状態かどうか。
  ///
  /// 表示側はこれを見て「AIモード」と名乗ってよいかを決める。
  /// `simulated` を `true` にしてはならない（Mock を実 AI として見せない）。
  bool get isRealAi => this == AiModeState.ready || this == AiModeState.working;

  IconData get icon => switch (this) {
        AiModeState.ready => Icons.auto_awesome_rounded,
        AiModeState.working => Icons.auto_awesome_rounded,
        AiModeState.preparing => Icons.hourglass_top_rounded,
        AiModeState.simulated => Icons.science_outlined,
        AiModeState.unavailable => Icons.cloud_off_rounded,
      };
}

/// いまの実状態を決める。
///
/// **推測で楽観側へ倒さない**（CLAUDE.md「分からないものを楽観側へ
/// 倒さない」）。順序に意味がある。
///
/// * `unreachable` — 接続できなかったという**観測事実**。最優先。
/// * `AppConfig.current.mockMode` — このビルド自体が疑似データ専用。
///   Backend が何を返そうと実 AI ではない。
/// * `simulatedFromBackend == true` — Backend が「これは模擬出力だ」と
///   言った事実（`simulated` フィールド）。
/// * `busy` — 応答待ち。
///
/// `mockBuild` は**テストのための注入口**である。`AppConfig.current`は
/// compile time 定数なので、テストから疑似ビルドを再現する手段がこれしか
/// 無い。本番の呼び出し側は渡さず、既定の `AppConfig.current.mockMode`
/// がそのまま使われる（渡し忘れても本番の意味が変わらない形にしてある）。
AiModeState resolveAiModeState({
  bool? simulatedFromBackend,
  bool unreachable = false,
  bool busy = false,
  bool? mockBuild,
}) {
  if (unreachable) return AiModeState.unavailable;
  if (mockBuild ?? AppConfig.current.mockMode) return AiModeState.simulated;
  if (simulatedFromBackend == true) return AiModeState.simulated;
  if (busy) return AiModeState.working;
  return AiModeState.ready;
}

/// この結果を「疑似出力」として扱うべきか。
///
/// ---
///
/// ## なぜ Backend の返事だけを見ないのか
///
/// 実機描画（2026-09-02）で見つけた実バグ。`USE_MOCK_GENERATION=true` で
/// ビルドすると `MockConversationRepository` が応答を組み立てるが、その
/// Repository は `simulated: true` を**付け忘れていた**。結果、疑似データ
/// で作られた道具が、実 AI の生成物と見分けの付かない形で表示されていた
/// （Universal Quality §3「未対応Capabilityを黙って削り、生成成功として
/// 表示する」と同じ種類の不正直さ）。
///
/// 「Repository が忘れずに付ける」設計は忘れられる（CLAUDE.md §3）。
/// **ビルド自体が疑似モードなら、誰が何を返そうと疑似である。**
/// その事実をここで足す。
bool isSimulatedOutput({
  required bool backendSaidSimulated,
  bool? mockBuild,
}) =>
    (mockBuild ?? AppConfig.current.mockMode) || backendSaidSimulated;

/// 画面の隅に置く、**押せない**状態表示。
///
/// 以前ここにあったのは Provider 切り替えトグルだった。
/// **利用者に AI 経路を選ばせない**ので、これは表示専用である
/// （押せるのに何も起きない飾りも作らない——Universal Quality §9）。
class AiModeIndicator extends StatelessWidget {
  final AiModeState state;

  const AiModeIndicator({super.key, required this.state});

  @override
  Widget build(BuildContext context) {
    final accent = switch (state) {
      AiModeState.ready || AiModeState.working => ForgeTheme.gradientEnd,
      AiModeState.preparing ||
      AiModeState.simulated ||
      AiModeState.unavailable =>
        ForgeTheme.consoleInkSoft,
    };
    final ink = state.isRealAi ? ForgeTheme.consoleInk : ForgeTheme.consoleInkSoft;

    return Tooltip(
      message: state.description,
      child: Semantics(
        label: state.label,
        hint: state.description,
        readOnly: true,
        container: true,
        // 子の `Text` も同じ文字を読み上げるため、除外しないと
        // 「AIモード AIモード」と二重に読まれる（実際に起きていた）。
        excludeSemantics: true,
        child: Container(
          constraints: const BoxConstraints(maxWidth: 220),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(999),
            border: Border.all(color: accent),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(state.icon, size: 14, color: accent),
              const SizedBox(width: 5),
              // 幅が狭い端末でも文字が切れないようにする
              // （Universal Quality: 端末差を品質差にしない）。
              Flexible(
                child: Text(
                  state.label,
                  overflow: TextOverflow.ellipsis,
                  softWrap: false,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: ink,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
