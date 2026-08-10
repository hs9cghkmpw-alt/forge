// ApiAppGenerationRepository Unit Test(FORGE v0.2 Backend接続対応)。
//
// 実ネットワークには一切依存しない。DioのInterceptorで`onRequest`を
// 横取りし、`handler.resolve(...)`(成功/構造化エラー応答)または
// `handler.reject(...)`(接続エラー)を直接呼ぶことで、実際のHTTP通信を
// 起こさずにdioの応答/例外経路を再現する(dioの公式に文書化された
// テスト手法。`http_mock_adapter`等の追加パッケージは導入していない)。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/features/app_generation/data/datasources/ai_generation_api.dart';
import 'package:forge_app/features/app_generation/data/repositories/api_app_generation_repository.dart';
import 'package:forge_app/features/app_generation/domain/entities/generation_outcome.dart';
import 'package:forge_app/features/app_generation/domain/repositories/app_generation_repository.dart';

/// テスト専用のInterceptor。`onRequest`をあらかじめ登録した応答へ
/// 差し替える。1回呼ばれるごとに`_script`を1件消費する(呼び出し順が
/// 決まっているテストのみを想定した、単純なFIFOスクリプト)。
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
  RequestOptions options,
  RequestInterceptorHandler handler,
  int statusCode,
  Map<String, dynamic> body,
) async {
  handler.resolve(
    Response<Map<String, dynamic>>(requestOptions: options, statusCode: statusCode, data: body),
  );
}

Future<void> _rejectWithType(
  RequestOptions options,
  RequestInterceptorHandler handler,
  DioExceptionType type, {
  Response<dynamic>? response,
}) async {
  handler.reject(DioException(requestOptions: options, type: type, response: response));
}

void main() {
  group('ApiAppGenerationRepository.generate() — 正常系', () {
    test('successレスポンスをGenerationSuccessへ変換する', () async {
      final dio = _buildDio([
        (options, handler) => _resolveJson(options, handler, 200, {
              'version': '1.0',
              'status': 'success',
              'result': {
                'forge_document': {
                  'version': '1.0',
                  'app': {'title': '買い物リスト'},
                  'screens': [],
                },
                'validation': {'valid': true, 'errors': [], 'warnings': []},
                'quality': {'score': 80, 'release_ready': true, 'issues': [], 'required_fixes': []},
                'diagnostics': {
                  'engine_used': 'forge_ai',
                  'provider_used': 'mock',
                  'repair_attempts': 0,
                },
              },
            }),
      ]);
      final repository = ApiAppGenerationRepository(AiGenerationApi(dio));

      final outcome = await repository.generate('買い物リストを作りたい');

      expect(outcome, isA<GenerationSuccess>());
      final success = outcome as GenerationSuccess;
      expect(success.forgeDocument['app'], {'title': '買い物リスト'});
      expect(success.quality?.score, 80);
      expect(success.diagnostics.providerUsed, 'mock');
    });

    test('needs_confirmationレスポンスをGenerationNeedsConfirmationへ変換する', () async {
      final dio = _buildDio([
        (options, handler) => _resolveJson(options, handler, 200, {
              'version': '1.0',
              'status': 'needs_confirmation',
              'confirmation': {
                'request_id': 'req-123',
                'question': '何を管理するアプリですか？',
                'reason': 'priority2_low_domain_confidence',
                'reached_stage': 'domain_classification',
                'open_questions': ['例: 買い物'],
                'rounds_remaining': 2,
              },
            }),
      ]);
      final repository = ApiAppGenerationRepository(AiGenerationApi(dio));

      final outcome = await repository.generate('x');

      expect(outcome, isA<GenerationNeedsConfirmation>());
      final confirmation = outcome as GenerationNeedsConfirmation;
      expect(confirmation.requestId, 'req-123');
      expect(confirmation.roundsRemaining, 2);
    });
  });

  group('ApiAppGenerationRepository.generate() — HTTPエラー(BACKEND、構造化)', () {
    test('HTTP 422のError Envelopeを例外にせずGenerationFailureとして返す', () async {
      final dio = _buildDio([
        (options, handler) => _rejectWithType(
              options,
              handler,
              DioExceptionType.badResponse,
              response: Response<Map<String, dynamic>>(
                requestOptions: options,
                statusCode: 422,
                data: {
                  'version': '1.0',
                  'status': 'error',
                  'error': {
                    'category': 'request_error',
                    'sub_reason': 'schema_invalid',
                    'message': 'natural_languageが空です。',
                    'retryable': false,
                  },
                },
              ),
            ),
      ]);
      final repository = ApiAppGenerationRepository(AiGenerationApi(dio));

      final outcome = await repository.generate('');

      expect(outcome, isA<GenerationFailure>());
      final failure = outcome as GenerationFailure;
      expect(failure.category, 'request_error');
      expect(failure.subReason, 'schema_invalid');
      expect(failure.retryable, isFalse);
    });

    test('HTTP 500のError Envelopeをretryable=falseのGenerationFailureとして返す', () async {
      final dio = _buildDio([
        (options, handler) => _rejectWithType(
              options,
              handler,
              DioExceptionType.badResponse,
              response: Response<Map<String, dynamic>>(
                requestOptions: options,
                statusCode: 500,
                data: {
                  'version': '1.0',
                  'status': 'error',
                  'error': {
                    'category': 'runtime_error',
                    'sub_reason': null,
                    'message': '予期しないエラーが発生しました。',
                    'retryable': false,
                  },
                },
              ),
            ),
      ]);
      final repository = ApiAppGenerationRepository(AiGenerationApi(dio));

      final outcome = await repository.generate('test');

      expect(outcome, isA<GenerationFailure>());
      expect((outcome as GenerationFailure).category, 'runtime_error');
    });

    test('Providerタイムアウト等のretryable=trueなエラーはretryable=trueのまま伝わる', () async {
      final dio = _buildDio([
        (options, handler) => _rejectWithType(
              options,
              handler,
              DioExceptionType.badResponse,
              response: Response<Map<String, dynamic>>(
                requestOptions: options,
                statusCode: 504,
                data: {
                  'version': '1.0',
                  'status': 'error',
                  'error': {
                    'category': 'provider_error',
                    'sub_reason': 'timeout',
                    'message': 'Provider応答がタイムアウトしました。',
                    'retryable': true,
                  },
                },
              ),
            ),
      ]);
      final repository = ApiAppGenerationRepository(AiGenerationApi(dio));

      final outcome = await repository.generate('test');

      expect((outcome as GenerationFailure).retryable, isTrue);
    });
  });

  group('ApiAppGenerationRepository.generate() — 通信エラー(NETWORK)', () {
    test('接続タイムアウトはAppGenerationExceptionをthrowする(GenerationFailureにはしない)', () async {
      final dio = _buildDio([
        (options, handler) => _rejectWithType(options, handler, DioExceptionType.connectionTimeout),
      ]);
      final repository = ApiAppGenerationRepository(AiGenerationApi(dio));

      await expectLater(
        () => repository.generate('test'),
        throwsA(isA<AppGenerationException>().having((e) => e.code, 'code', 'NETWORK_ERROR')),
      );
    });

    test('FastAPI未起動相当(connectionError)もNETWORK_ERRORとしてthrowする', () async {
      final dio = _buildDio([
        (options, handler) => _rejectWithType(options, handler, DioExceptionType.connectionError),
      ]);
      final repository = ApiAppGenerationRepository(AiGenerationApi(dio));

      await expectLater(
        () => repository.generate('test'),
        throwsA(isA<AppGenerationException>().having((e) => e.code, 'code', 'NETWORK_ERROR')),
      );
    });
  });

  group('ApiAppGenerationRepository.generate() — 不正な応答(INVALID_RESPONSE)', () {
    test('forge_documentが欠落したsuccess応答はINVALID_RESPONSEとしてthrowする', () async {
      final dio = _buildDio([
        (options, handler) => _resolveJson(options, handler, 200, {
              'version': '1.0',
              'status': 'success',
              'result': {
                // forge_document欠落
                'validation': {'valid': true, 'errors': [], 'warnings': []},
              },
            }),
      ]);
      final repository = ApiAppGenerationRepository(AiGenerationApi(dio));

      await expectLater(
        () => repository.generate('test'),
        throwsA(isA<AppGenerationException>().having((e) => e.code, 'code', 'INVALID_RESPONSE')),
      );
    });

    test('未知のstatus値はINVALID_RESPONSEとしてthrowする', () async {
      final dio = _buildDio([
        (options, handler) => _resolveJson(options, handler, 200, {
              'version': '1.0',
              'status': 'something_unexpected',
            }),
      ]);
      final repository = ApiAppGenerationRepository(AiGenerationApi(dio));

      await expectLater(
        () => repository.generate('test'),
        throwsA(isA<AppGenerationException>().having((e) => e.code, 'code', 'INVALID_RESPONSE')),
      );
    });

    test('needs_confirmationなのにconfirmationフィールドが無い場合もINVALID_RESPONSE', () async {
      final dio = _buildDio([
        (options, handler) => _resolveJson(options, handler, 200, {
              'version': '1.0',
              'status': 'needs_confirmation',
              // confirmation欠落
            }),
      ]);
      final repository = ApiAppGenerationRepository(AiGenerationApi(dio));

      await expectLater(
        () => repository.generate('test'),
        throwsA(isA<AppGenerationException>().having((e) => e.code, 'code', 'INVALID_RESPONSE')),
      );
    });
  });

  group('ApiAppGenerationRepository.confirm()', () {
    test('確認回答APIも同じ契約でパースする', () async {
      final dio = _buildDio([
        (options, handler) => _resolveJson(options, handler, 200, {
              'version': '1.0',
              'status': 'success',
              'result': {
                'forge_document': {'version': '1.0', 'app': {'title': 'T'}, 'screens': []},
                'validation': {'valid': true, 'errors': [], 'warnings': []},
                'quality': null,
                'diagnostics': {'engine_used': 'forge_ai', 'provider_used': 'mock', 'repair_attempts': 0},
              },
            }),
      ]);
      final repository = ApiAppGenerationRepository(AiGenerationApi(dio));

      final outcome = await repository.confirm(requestId: 'req-1', answer: '買い物リストです');

      expect(outcome, isA<GenerationSuccess>());
    });
  });
}
