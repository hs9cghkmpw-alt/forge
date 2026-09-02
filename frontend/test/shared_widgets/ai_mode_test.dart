// 通常画面に **Provider の身元を出さない**（Constitution §4・§9）。
//
// ---
//
// ## この試験が守っているもの
//
// 以前ホーム画面には `Gemini` ⇔ `Mock` のタップ切り替えトグルがあった。
// 表示文字だけでなく、**利用者に AI 経路を選ばせる構造**そのものが
// 方針違反だった。ここでは3つを別々に検査する。
//
// 1. 表示名が Provider 非依存であること（`AIモード`）
// 2. **疑似データを「AIモード」と呼ばないこと**（表示＝実状態）
// 3. Semantics / Tooltip にも身元が出ないこと（読み上げも UI である）

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/shared_widgets/ai_mode.dart';

/// 通常画面へ出てはいけない語。小文字で比較する。
///
/// Backend 側の `PROVIDER_IDENTITY_TOKENS` と同じ考え方であり、
/// **片方だけ守っても意味が無い**ので両方に置く。
const List<String> providerIdentityTokens = <String>[
  'gemini',
  'openai',
  'chatgpt',
  'gpt-',
  'anthropic',
  'claude',
  'ollama',
  'llama',
  'qwen',
  'mistral',
  'gemma',
  'mock',
  'forge_ai',
  'provider',
  'プロバイダ',
  'モック',
];

bool mentionsProviderIdentity(String text) {
  final lowered = text.toLowerCase();
  return providerIdentityTokens.any(lowered.contains);
}

void main() {
  _simulatedOutputTests();
  group('表示名は Provider 非依存である', () {
    test('通常状態の正式名称は「AIモード」', () {
      expect(AiModeState.ready.label, 'AIモード');
      expect(kAiModeName, 'AIモード');
    });

    test('どの状態の label / description にも Provider の身元が出ない', () {
      for (final state in AiModeState.values) {
        expect(
          mentionsProviderIdentity(state.label),
          isFalse,
          reason: '${state.name} の label に Provider の身元が出ている: ${state.label}',
        );
        expect(
          mentionsProviderIdentity(state.description),
          isFalse,
          reason: '${state.name} の description に身元が出ている: ${state.description}',
        );
      }
    });
  });

  group('表示は実状態と一致する', () {
    test('疑似データのビルドを「AIモード」と呼ばない', () {
      final state = resolveAiModeState(mockBuild: true);
      expect(state, AiModeState.simulated);
      expect(state.isRealAi, isFalse);
      expect(state.label, isNot('AIモード'));
      // **「これは疑似だ」と言っていること。** 黙って隠さない。
      expect(state.description, contains('AIには接続していません'));
    });

    test('Backend が simulated=true と言ったら「AIモード」と呼ばない', () {
      final state = resolveAiModeState(mockBuild: false, simulatedFromBackend: true);
      expect(state, AiModeState.simulated);
      expect(state.isRealAi, isFalse);
    });

    test('疑似ビルドは、Backend が simulated=false と言っても疑似のままである', () {
      // ビルド自体が Backend へ繋がないのだから、Backend の返事より
      // ビルドの事実が優先する。**楽観側へ倒さない。**
      final state = resolveAiModeState(mockBuild: true, simulatedFromBackend: false);
      expect(state, AiModeState.simulated);
    });

    test('接続できないときは「AIモード」と表示しない', () {
      final state = resolveAiModeState(mockBuild: false, unreachable: true);
      expect(state, AiModeState.unavailable);
      expect(state.isRealAi, isFalse);
    });

    test('接続できないことは、疑似ビルドかどうかより優先する', () {
      expect(
        resolveAiModeState(mockBuild: true, unreachable: true),
        AiModeState.unavailable,
      );
    });

    test('応答待ちは「AIが考えています…」', () {
      final state = resolveAiModeState(mockBuild: false, busy: true);
      expect(state, AiModeState.working);
      expect(state.label, 'AIが考えています…');
      expect(state.isRealAi, isTrue);
    });

    test('通常は「AIモード」', () {
      expect(resolveAiModeState(mockBuild: false), AiModeState.ready);
    });
  });

  group('AiModeIndicator', () {
    Widget wrap(AiModeState state) => MaterialApp(
          home: Scaffold(body: Center(child: AiModeIndicator(state: state))),
        );

    testWidgets('「AIモード」を表示し、Tooltip と Semantics を持つ', (tester) async {
      final handle = tester.ensureSemantics();
      await tester.pumpWidget(wrap(AiModeState.ready));
      await tester.pump();

      expect(find.text('AIモード'), findsOneWidget);

      final tooltip = tester.widget<Tooltip>(find.byType(Tooltip));
      expect(tooltip.message, AiModeState.ready.description);

      // 読み上げでも同じことを言う（Accessibility も同一品質である）。
      expect(find.bySemanticsLabel('AIモード'), findsWidgets);
      final semantics = tester.getSemantics(find.text('AIモード'));
      expect(semantics.label, 'AIモード');
      expect(semantics.hint, AiModeState.ready.description);
      expect(
        mentionsProviderIdentity('${semantics.label} ${semantics.hint}'),
        isFalse,
        reason: '読み上げ側に Provider の身元が出ている',
      );
      handle.dispose();
    });

    testWidgets('押せる部品ではない（押せるのに何も起きない飾りを作らない）', (tester) async {
      await tester.pumpWidget(wrap(AiModeState.ready));
      await tester.pump();
      expect(find.byType(InkWell), findsNothing);
      expect(find.byType(GestureDetector), findsNothing);
    });

    testWidgets('疑似データのときは「AIモード」と書かない', (tester) async {
      await tester.pumpWidget(wrap(AiModeState.simulated));
      await tester.pump();
      expect(find.text('AIモード'), findsNothing);
      expect(find.text('お試しモード'), findsOneWidget);
    });

    testWidgets('狭い画面でも文字が溢れない（端末差を品質差にしない）', (tester) async {
      tester.view.physicalSize = const Size(360, 640);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      for (final state in AiModeState.values) {
        await tester.pumpWidget(wrap(state));
        await tester.pump();
        expect(
          tester.takeException(),
          isNull,
          reason: '${state.name} の表示で Overflow が起きている',
        );
      }
    });
  });
}

/// 疑似ビルドで、疑似データが「本物」に見えないこと。
///
/// ---
///
/// 2026-09-02 の実機描画（Chromium、`USE_MOCK_GENERATION=true` ビルド）で
/// 見つけた実バグ。`MockConversationRepository` が `simulated: true` を
/// 付け忘れていたため、`SimulatedOutputBanner` も
/// `GeneratedAppHostShell` の「お試し用の疑似データ」表記も出ず、
/// **疑似データが実 AI の生成物と同じ見た目で表示されていた**。
///
/// 直し方を「Repository が忘れずに付ける」にしなかったのは、
/// 忘れずに呼ばれる保証が無いものは忘れられるからである（CLAUDE.md §3）。
/// ビルド自体が疑似モードなら、誰が何を返そうと疑似である。
void _simulatedOutputTests() {
  group('isSimulatedOutput', () {
    test('Backend が黙っていても、疑似ビルドなら疑似である', () {
      expect(
        isSimulatedOutput(backendSaidSimulated: false, mockBuild: true),
        isTrue,
        reason: 'Repository の付け忘れで、疑似データが本物として表示される',
      );
    });

    test('通常ビルドでは Backend の返事に従う', () {
      expect(isSimulatedOutput(backendSaidSimulated: false, mockBuild: false), isFalse);
      expect(isSimulatedOutput(backendSaidSimulated: true, mockBuild: false), isTrue);
    });
  });
}
