import 'package:dio/dio.dart';

import '../config/app_config.dart';

/// FORGE-RUNTIME-001 Task 1でBase URLを`AppConfig`へ統合した
/// (`core/config`ができるまでの暫定値、という位置づけ自体はAppConfig側の
/// コメントに引き継いでいる。ここに重複して定数を持たない)。
Dio createForgeDioClient() {
  return Dio(
    BaseOptions(
      baseUrl: AppConfig.current.apiBaseUrl,
      // 到達できるかどうかは 10 秒で分かる。ここは変えない。
      connectTimeout: const Duration(seconds: 10),
      // **応答を待つ時間は、生成の実時間に合わせる。**
      //
      // 実機（2026-08-31、Ollama + qwen2.5:1.5b-instruct）で
      // `/converse` が 73.54 秒かかり、ここで先に切れて画面には
      // 「サーバーに接続できませんでした」しか出なかった。
      //
      // **主たる直しは待ち時間を伸ばすことではない。** 会話の判定を
      // 決定的な速い道へ逃がして、簡単な要求では LLM を呼ばないように
      // した（`conversation_fast_path.py`。実測 73.54 秒 → 0.09 ミリ秒）。
      //
      // それでも BUILD 段では小型ローカルモデルが実際に生成するため、
      // 10 秒は生成の実時間より短い。ここはその一段だけを見込んだ値で
      // あって、遅さを許す値ではない。生成が遅いこと自体は別に測る。
      receiveTimeout: const Duration(seconds: 60),
      contentType: 'application/json',
    ),
  );
}
