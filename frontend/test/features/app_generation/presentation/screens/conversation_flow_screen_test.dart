// ConversationFlowScreen Widget Test(FORGE-PRODUCT-VISION-002、2026-08-11)。
//
// `MockConversationRepository`(常に即座にBUILD)ではASK/UPDATE分岐を
// 検証できないため、ここでは呼び出しごとに指定した結果を返す
// FakeConversationRepositoryを使う。

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/core/theme/forge_theme.dart';
import 'package:forge_app/features/app_generation/domain/entities/conversation_outcome.dart';
import 'package:forge_app/features/app_generation/domain/entities/generation_outcome.dart';
import 'package:forge_app/features/app_generation/domain/repositories/conversation_repository.dart';
import 'package:forge_app/features/app_generation/presentation/providers/conversation_provider.dart';
import 'package:forge_app/features/app_generation/presentation/screens/conversation_flow_screen.dart';
import 'package:forge_app/features/app_library/presentation/providers/app_library_provider.dart';
import 'package:forge_app/shared_widgets/generated_app_host_shell.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _FakeConversationRepository implements ConversationRepository {
  final List<ConversationOutcome> _script;
  int _index = 0;
  final List<String> capturedMessages = [];

  _FakeConversationRepository(this._script);

  @override
  Future<ConversationOutcome> converse({
    String? sessionId,
    required String message,
    String? provider,
    Map<String, dynamic>? currentDocument,
  }) async {
    capturedMessages.add(message);
    final outcome = _script[_index];
    _index += 1;
    return outcome;
  }
}

GenerationSuccess _buildResult(String title) => GenerationSuccess(
      forgeDocument: {
        'version': '1.0',
        'app': {'title': title},
        'initial_screen_id': 's1',
        'screens': [
          {
            'id': 's1', 'title': title, 'state': {},
            'body': {'type': 'column', 'id': 'root', 'children': []},
          },
        ],
      },
      diagnostics: const GenerationDiagnostics(engineUsed: 'forge_ai', providerUsed: 'mock', repairAttempts: 0),
    );

Future<Widget> _wrap(Widget child, ConversationRepository repository) async {
  SharedPreferences.setMockInitialValues({});
  final prefs = await SharedPreferences.getInstance();
  return ProviderScope(
    overrides: [
      sharedPreferencesProvider.overrideWithValue(prefs),
      conversationRepositoryProvider.overrideWithValue(repository),
    ],
    child: MaterialApp(theme: ForgeTheme.theme, home: child),
  );
}

void main() {
  testWidgets('ASK then BUILD: 質問が表示され、返信すると生成されたアプリが開く', (tester) async {
    final repository = _FakeConversationRepository([
      const ConversationAsk(
        sessionId: 'sess-1', question: '家族も追加できた方がいい?',
        needModel: NeedModelSummary(problem: '買い物で忘れる'),
      ),
      ConversationBuilt(buildBrief: '買い物リストを作る', result: _buildResult('買い物リスト')),
    ]);

    await tester.pumpWidget(await _wrap(
      const ConversationFlowScreen(initialMessage: '買い物行くと、いつも何買うか忘れるんだよね'), repository,
    ));
    await tester.pump(); // 初回のconverse()呼び出し

    expect(find.text('買い物行くと、いつも何買うか忘れるんだよね'), findsOneWidget);
    expect(find.text('家族も追加できた方がいい?'), findsOneWidget);
    expect(find.byType(TextField), findsOneWidget);

    // `enterText()`直後にタップすると、テキストの変更が`_ReplyBar`の
    // 送信ボタン(`canSend`)へ反映されるフレームが挟まらず、タップが
    // 空振りすることがある(実際にWidget Testで発見した挙動)ため、
    // 間に1フレーム`pump()`を挟む。
    await tester.enterText(find.byType(TextField), 'いや、自分だけでいいかな');
    await tester.pump();
    await tester.tap(find.byIcon(Icons.arrow_upward_rounded));
    // BUILD結果を反映する非同期処理(_finishBuild()のsaveApp()等)が
    // 完了し、Navigator.pushReplacement()が反映されるまで数フレーム
    // 掛かるため、複数回pumpする。
    for (var i = 0; i < 4; i++) {
      await tester.pump();
    }

    expect(find.byType(GeneratedAppHostShell), findsOneWidget);
    expect(repository.capturedMessages, [
      '買い物行くと、いつも何買うか忘れるんだよね',
      'いや、自分だけでいいかな',
    ]);
    expect(tester.takeException(), isNull);
  });

  testWidgets('UPDATE mode: initialMessageがnullだとForgeから先に聞き、送信するとpopで新しいDocumentを返す', (tester) async {
    final repository = _FakeConversationRepository([
      const ConversationUpdated(
        changeRequest: 'よく買うものを上に置きたい',
        forgeDocument: {'version': '1.0', 'app': {'title': '更新済み'}},
        valid: true, attempts: 1,
      ),
    ]);

    Map<String, dynamic>? poppedResult;

    await tester.pumpWidget(await _wrap(
      Builder(
        builder: (context) => Scaffold(
          body: Center(
            child: ElevatedButton(
              onPressed: () async {
                poppedResult = await Navigator.of(context).push<Map<String, dynamic>>(
                  MaterialPageRoute<Map<String, dynamic>>(
                    builder: (_) => ConversationFlowScreen(currentDocument: const {'version': '1.0'}),
                  ),
                );
              },
              child: const Text('open'),
            ),
          ),
        ),
      ),
      repository,
    ));

    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();

    // initialMessageが無いため、まだconverse()は呼ばれておらず、
    // Forgeからの一言(静的な挨拶)と返信欄が出ているはず。
    expect(find.text('どこを変えましょうか？'), findsOneWidget);
    expect(repository.capturedMessages, isEmpty);

    await tester.enterText(find.byType(TextField), 'よく買うものを上に置きたい');
    await tester.pump();
    await tester.tap(find.byIcon(Icons.arrow_upward_rounded));
    await tester.pump(); // converse()呼び出し(UPDATE)
    await tester.pumpAndSettle();

    expect(repository.capturedMessages, ['よく買うものを上に置きたい']);
    expect(poppedResult, {'version': '1.0', 'app': {'title': '更新済み'}});
    expect(tester.takeException(), isNull);
  });
}
