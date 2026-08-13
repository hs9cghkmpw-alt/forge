// ApiConversationRepository Unit Test(FORGE-PRODUCT-VISION-002、2026-08-11)。
//
// `api_app_generation_repository_test.dart`と同じ手法
// (Dio Interceptorで応答を差し替え、実ネットワークには依存しない)。

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/features/app_generation/data/datasources/ai_conversation_api.dart';
import 'package:forge_app/features/app_generation/data/repositories/api_conversation_repository.dart';
import 'package:forge_app/features/app_generation/domain/entities/conversation_outcome.dart';

class _ScriptedInterceptor extends Interceptor {
  final List<Future<void> Function(RequestOptions options, RequestInterceptorHandler handler)> _script;
  int _index = 0;
  _ScriptedInterceptor(this._script);

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final step = _script[_index];
    _index++;
    step(options, handler);
  }
}

Dio _buildDio(
  List<Future<void> Function(RequestOptions options, RequestInterceptorHandler handler)> script,
) {
  final dio = Dio(BaseOptions(baseUrl: 'http://127.0.0.1:8000'));
  dio.interceptors.add(_ScriptedInterceptor(script));
  return dio;
}

Future<void> _resolveJson(
  RequestOptions options, RequestInterceptorHandler handler, int statusCode, Map<String, dynamic> body,
) async {
  handler.resolve(Response<Map<String, dynamic>>(requestOptions: options, statusCode: statusCode, data: body));
}

void main() {
  group('ApiConversationRepository.converse() — ask/build/update', () {
    test('askレスポンスをConversationAskへ変換する', () async {
      final dio = _buildDio([
        (options, handler) => _resolveJson(options, handler, 200, {
              'version': '1.0',
              'status': 'ask',
              'session_id': 'sess-1',
              'question': '家族も追加できた方がいい?',
              'need_model': {
                'problem': '買い物で忘れる',
                'known': ['店で消す'],
                'unknown_important': ['家族も使うか'],
                'safe_assumptions': <dynamic>[],
                'confidence': 0.5,
              },
            }),
      ]);
      final repository = ApiConversationRepository(AiConversationApi(dio));

      final outcome = await repository.converse(message: '買い物で忘れる');

      expect(outcome, isA<ConversationAsk>());
      final ask = outcome as ConversationAsk;
      expect(ask.sessionId, 'sess-1');
      expect(ask.question, '家族も追加できた方がいい?');
      expect(ask.needModel.problem, '買い物で忘れる');
      expect(ask.needModel.knownFacts, ['店で消す']);
    });

    test('confirmレスポンスをConversationConfirmへ変換する', () async {
      // FORGE-CONVERSATION-READY-001(2026-08-12、指示書4章)。
      final dio = _buildDio([
        (options, handler) => _resolveJson(options, handler, 200, {
              'version': '1.0',
              'status': 'confirm',
              'session_id': 'sess-9',
              'question': 'ご家族へ送ってよいですか？',
              'reason': 'Forgeの外(他の人・外部サービス)へ影響が及ぶため',
              'readiness': 'needs_confirmation',
              'need_model': {
                'problem': '家族へ共有したい',
                'known': <dynamic>[],
                'unknown_important': <dynamic>[],
                'safe_assumptions': <dynamic>[],
                'confidence': 0.8,
                'unknowns': <dynamic>[],
                'assumptions': <dynamic>[],
              },
            }),
      ]);
      final repository = ApiConversationRepository(AiConversationApi(dio));

      final outcome = await repository.converse(message: 'これを家族にも送って');

      expect(outcome, isA<ConversationConfirm>());
      final confirm = outcome as ConversationConfirm;
      expect(confirm.sessionId, 'sess-9');
      expect(confirm.question, 'ご家族へ送ってよいですか？');
      expect(confirm.reason, contains('外'));
    });

    test('need_modelの新しいunknowns/assumptionsがあっても既存パースを壊さない', () async {
      // 後方互換の確認: `unknown_important`/`safe_assumptions`(文字列
      // リスト)は従来どおり読めること。
      final dio = _buildDio([
        (options, handler) => _resolveJson(options, handler, 200, {
              'version': '1.0',
              'status': 'ask',
              'session_id': 'sess-1',
              'question': '家族も使いますか?',
              'readiness': 'needs_question',
              'need_model': {
                'problem': '買い物で忘れる',
                'known': ['店で消す'],
                'unknown_important': ['shared_usage'],
                'safe_assumptions': ['allow_delete=true'],
                'confidence': 0.5,
                'unknowns': [
                  {'key': 'shared_usage', 'impact': 'high', 'reason': '権限が変わる', 'status': 'unknown'},
                ],
                'assumptions': [
                  {'key': 'allow_delete', 'value': 'true', 'reason': '元に戻せる操作のため'},
                ],
              },
            }),
      ]);
      final repository = ApiConversationRepository(AiConversationApi(dio));

      final outcome = await repository.converse(message: '買い物で忘れる');

      final ask = outcome as ConversationAsk;
      expect(ask.needModel.knownFacts, ['店で消す']);
      expect(ask.needModel.safeAssumptions, ['allow_delete=true']);
    });

    test('buildレスポンスをConversationBuiltへ変換する', () async {
      final dio = _buildDio([
        (options, handler) => _resolveJson(options, handler, 200, {
              'version': '1.0',
              'status': 'build',
              'session_id': 'sess-2',
              'build_brief': '買い物リストを作る',
              'need_model': {
                'problem': 'p', 'known': <dynamic>[], 'unknown_important': <dynamic>[], 'safe_assumptions': <dynamic>[], 'confidence': 0.9,
              },
              'result': {
                'forge_document': {'version': '1.0', 'app': {'title': '買い物リスト'}, 'screens': <dynamic>[]},
                'validation': {'valid': true, 'errors': <dynamic>[], 'warnings': <dynamic>[]},
                'diagnostics': {'engine_used': 'forge_ai', 'provider_used': 'mock', 'repair_attempts': 0},
              },
            }),
      ]);
      final repository = ApiConversationRepository(AiConversationApi(dio));

      final outcome = await repository.converse(message: '買い物で忘れる');

      expect(outcome, isA<ConversationBuilt>());
      final built = outcome as ConversationBuilt;
      expect(built.buildBrief, '買い物リストを作る');
      expect(built.result.forgeDocument['app'], {'title': '買い物リスト'});
    });

    test('updateレスポンスをConversationUpdatedへ変換する', () async {
      final dio = _buildDio([
        (options, handler) => _resolveJson(options, handler, 200, {
              'version': '1.0',
              'status': 'update',
              'session_id': 'sess-3',
              'change_request': 'カテゴリ分けしたい',
              'need_model': {
                'problem': 'p', 'known': <dynamic>[], 'unknown_important': <dynamic>[], 'safe_assumptions': <dynamic>[], 'confidence': 0.9,
              },
              'result': {
                'forge_document': {'version': '1.0', 'app': {'title': '更新済み'}, 'screens': <dynamic>[]},
                'validation': {'valid': true, 'errors': <dynamic>[], 'warnings': <dynamic>[]},
                'attempts': 2,
              },
            }),
      ]);
      final repository = ApiConversationRepository(AiConversationApi(dio));

      final outcome = await repository.converse(
        message: 'カテゴリ分けしたい', currentDocument: {'version': '1.0'},
      );

      expect(outcome, isA<ConversationUpdated>());
      final updated = outcome as ConversationUpdated;
      expect(updated.changeRequest, 'カテゴリ分けしたい');
      expect(updated.valid, isTrue);
      expect(updated.attempts, 2);
      expect(updated.forgeDocument['app'], {'title': '更新済み'});
    });

    test('needs_confirmationレスポンスをConversationFallbackConfirmationへ変換する', () async {
      final dio = _buildDio([
        (options, handler) => _resolveJson(options, handler, 200, {
              'version': '1.0',
              'status': 'needs_confirmation',
              'confirmation': {
                'request_id': 'req-9',
                'question': '記録する情報の範囲を教えてください。',
                'reason': 'priority1_privacy_safety_permission',
                'reached_stage': 'ambiguity_detection',
                'open_questions': <dynamic>[],
                'rounds_remaining': 2,
              },
            }),
      ]);
      final repository = ApiConversationRepository(AiConversationApi(dio));

      final outcome = await repository.converse(message: '薬を飲むのを忘れる');

      expect(outcome, isA<ConversationFallbackConfirmation>());
      final fallback = outcome as ConversationFallbackConfirmation;
      expect(fallback.confirmation.requestId, 'req-9');
    });

    test('errorレスポンスをConversationFailureへ変換する', () async {
      final dio = _buildDio([
        (options, handler) => _resolveJson(options, handler, 503, {
              'version': '1.0',
              'status': 'error',
              'error': {
                'category': 'provider_error',
                'sub_reason': 'rate_limited',
                'message': '利用上限に達しました。',
                'retryable': true,
              },
            }),
      ]);
      final repository = ApiConversationRepository(AiConversationApi(dio));

      final outcome = await repository.converse(message: 'x');

      expect(outcome, isA<ConversationFailure>());
      final failure = (outcome as ConversationFailure).failure;
      expect(failure.category, 'provider_error');
      expect(failure.retryable, isTrue);
    });

    test('session_idとcurrent_documentが送信ボディへ含まれる', () async {
      Map<String, dynamic>? capturedBody;
      final dio = _buildDio([
        (options, handler) async {
          capturedBody = options.data as Map<String, dynamic>;
          await _resolveJson(options, handler, 200, {
            'version': '1.0', 'status': 'ask', 'session_id': 's', 'question': 'q?',
            'need_model': {
              'problem': 'p', 'known': <dynamic>[], 'unknown_important': ['x'], 'safe_assumptions': <dynamic>[], 'confidence': 0.1,
            },
          });
        },
      ]);
      final repository = ApiConversationRepository(AiConversationApi(dio));

      await repository.converse(
        sessionId: 'sess-abc', message: 'そうそう', provider: 'gemini', currentDocument: {'version': '1.0'},
      );

      expect(capturedBody?['session_id'], 'sess-abc');
      expect(capturedBody?['message'], 'そうそう');
      expect(capturedBody?['provider'], 'gemini');
      expect(capturedBody?['current_document'], {'version': '1.0'});
    });
  });
}
