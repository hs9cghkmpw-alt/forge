import 'package:dio/dio.dart';

/// Backendの `POST /api/v1/ai/converse` を叩くだけの薄い層
/// (`ai_generation_api.dart`と同じ設計方針)。
class AiConversationApi {
  final Dio _dio;
  const AiConversationApi(this._dio);

  Future<Map<String, dynamic>> converse({
    String? sessionId,
    required String message,
    String? provider,
    Map<String, dynamic>? currentDocument,
  }) async {
    final data = <String, dynamic>{'version': '1.0', 'message': message};
    if (sessionId != null) data['session_id'] = sessionId;
    if (provider != null) data['provider'] = provider;
    if (currentDocument != null) data['current_document'] = currentDocument;

    final response = await _dio.post<Map<String, dynamic>>('/api/v1/ai/converse', data: data);
    return _requireBody(response);
  }

  Map<String, dynamic> _requireBody(Response<Map<String, dynamic>> response) {
    final body = response.data;
    if (body == null) {
      throw DioException(requestOptions: response.requestOptions, message: 'empty response body');
    }
    return body;
  }
}
