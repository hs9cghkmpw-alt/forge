import 'package:dio/dio.dart';

/// Backendの `POST /api/v1/ai/generate` ・ `POST /api/v1/ai/generate/confirm`
/// を叩くだけの薄い層。レスポンスの status 判定は repositories(data層) が行う
/// (このクラスはHTTPの詳細だけを知っていればよい)。
///
/// FORGE v0.2 P0.1対応: 以前は`{'text': text}`という、Backendの実際の
/// リクエスト契約(`backend/app/schemas/ai.py`の`GenerateRequest`、
/// `{version, input: {natural_language, generation_options}}`)と
/// 一致しないリクエストボディを送っていた。実際の契約に合わせて修正した。
class AiGenerationApi {
  final Dio _dio;
  const AiGenerationApi(this._dio);

  /// FORGE-AI-CONNECT-001対応(2026-08-10): `provider`を明示指定すると
  /// (例: `"gemini"`)、Backendの既定(`mock`)ではなく指定したProviderで
  /// 生成する(`backend/app/schemas/ai.py`の`GenerationOptionsDTO`)。
  /// `null`の場合(既定)は`generation_options`自体を送らず、Backend側の
  /// 既定動作(mock)に任せる。
  Future<Map<String, dynamic>> generate(String naturalLanguage, {String? provider}) async {
    final input = <String, dynamic>{'natural_language': naturalLanguage};
    if (provider != null) {
      input['generation_options'] = {'engine': 'forge_ai', 'provider': provider};
    }
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/ai/generate',
      data: {'version': '1.0', 'input': input},
    );
    return _requireBody(response);
  }

  /// FORGE v0.2 P0.2対応: `needs_confirmation`への回答を送信し、
  /// Backendが元の入力へ回答を付加した上で再実行した結果を受け取る
  /// (`backend/app/ai/runtime/confirmation_store.py`参照)。
  Future<Map<String, dynamic>> confirm({required String requestId, required String answer}) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/ai/generate/confirm',
      data: {'version': '1.0', 'request_id': requestId, 'answer': answer},
    );
    return _requireBody(response);
  }

  Map<String, dynamic> _requireBody(Response<Map<String, dynamic>> response) {
    final body = response.data;
    if (body == null) {
      throw DioException(
        requestOptions: response.requestOptions,
        message: 'empty response body',
      );
    }
    return body;
  }
}
