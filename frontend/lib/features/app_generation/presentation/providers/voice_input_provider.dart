// 音声入力(FORGE-AI-CONNECT-001対応、2026-08-11)。
//
// **重要な限界(正直な申告)**: このファイルは、Claudeのサンドボックスに
// Flutter SDK・マイク・音声認識APIのいずれも無いため、**一度も実行・
// 検証できていない**。`speech_to_text`パッケージの実際のAPIシグネチャは
// 公式ドキュメントの記載に基づいて実装したが、実際のバージョン解決
// (`flutter pub get`)・Chromeでの動作は、CEO環境で初めて確認できる。
//
// **プラットフォームの制約**: このアプリは`android/`・`ios/`という
// ネイティブプロジェクトフォルダを一度も`flutter create`で生成して
// いない(`frontend/web/`のみ存在。`GETTING_STARTED.md`参照)。そのため、
// 現状の音声入力はWeb(Chrome等、ブラウザのWeb Speech APIを
// `speech_to_text`パッケージ経由で使う)でのみ動作する想定である。
// ネイティブ(Android/iOS)で使うには、別途
// `android/app/src/main/AndroidManifest.xml`への`RECORD_AUDIO`権限、
// `ios/Runner/Info.plist`への`NSMicrophoneUsageDescription`・
// `NSSpeechRecognitionUsageDescription`の追加が必要になるが、
// 該当フォルダ自体が存在しないため今回は対応していない。
//
// **検出のみで、常に安全側に倒す設計**: 音声認識が使えない環境
// (非対応ブラウザ、マイク権限拒否等)では、UI側(`home_screen.dart`)が
// `VoiceInputStatus.unavailable`を見て、マイクボタンを押しても
// 「動いたふりをしない」(エラーメッセージを表示し、テキスト入力への
// 切り替えを促す)。
//
// **設計判断**: Riverpod(このアプリの通常の状態管理)は使わず、素の
// `StatefulWidget`が直接所有するController(`home_screen.dart`の
// `_VoiceInputButton`参照)にした。理由: このアプリのどこにも
// `StateNotifier`/`StateNotifierProvider`パターンの実績が無く、
// Claude環境で一切検証できないこのコードに、検証済みの実績が無い
// 新しい状態管理パターンまで重ねるのはリスクが高いと判断した。
// `StatefulWidget`+`setState`は、このアプリの他の画面
// (`generation_flow_screen.dart`の`_GeneratingViewState`等)で
// 既に使われている、最も基本的で実績のあるFlutterパターン。

import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

enum VoiceInputStatus {
  /// 何もしていない(待機中)。
  idle,

  /// `SpeechToText.initialize()`を実行中。
  initializing,

  /// 実際に音声を聞き取っている最中。
  listening,

  /// この端末・ブラウザでは音声認識が使えない(非対応、権限拒否等)。
  unavailable,

  /// 認識中に何らかのエラーが発生した。
  error,
}

/// 音声認識状態の変化を呼び出し側(Widget)へ伝える。
typedef VoiceInputStatusListener = void Function(VoiceInputStatus status, String? errorMessage);

/// `speech_to_text`パッケージへの薄いラッパー。UIを一切持たない
/// (Widget側の責務との分離、`home_screen.dart`の`_VoiceInputButton`参照)。
class VoiceInputController {
  final stt.SpeechToText _speech = stt.SpeechToText();
  bool _initialized = false;
  bool _listening = false;

  bool get isListening => _listening;

  Future<bool> _ensureInitialized(VoiceInputStatusListener onStatusChange) async {
    if (_initialized) return true;
    onStatusChange(VoiceInputStatus.initializing, null);
    try {
      final available = await _speech.initialize(
        onError: (error) {
          _listening = false;
          onStatusChange(VoiceInputStatus.error, error.errorMsg);
        },
        onStatus: (status) {
          // `speech_to_text`パッケージが内部で使う文字列("notListening"・
          // "done"等)。認識が自然終了した場合、明示的に`stopListening()`を
          // 呼ばなくてもidleへ戻す。
          if ((status == 'notListening' || status == 'done') && _listening) {
            _listening = false;
            onStatusChange(VoiceInputStatus.idle, null);
          }
        },
      );
      _initialized = available;
      if (!available) {
        onStatusChange(VoiceInputStatus.unavailable, null);
      }
      return available;
    } catch (e) {
      _initialized = false;
      onStatusChange(VoiceInputStatus.unavailable, e.toString());
      return false;
    }
  }

  /// 音声入力を開始する。認識結果(途中経過含む)のたびに`onResult`が
  /// 呼ばれる(呼び出し側がテキスト欄へ反映する想定)。この関数自体は
  /// 入力欄を直接書き換えない。
  Future<void> startListening({
    required void Function(String text) onResult,
    required VoiceInputStatusListener onStatusChange,
  }) async {
    final available = await _ensureInitialized(onStatusChange);
    if (!available) return;

    _listening = true;
    onStatusChange(VoiceInputStatus.listening, null);
    await _speech.listen(
      localeId: 'ja_JP',
      onResult: (SpeechRecognitionResult result) {
        onResult(result.recognizedWords);
        if (result.finalResult) {
          _listening = false;
          onStatusChange(VoiceInputStatus.idle, null);
        }
      },
    );
  }

  Future<void> stopListening(VoiceInputStatusListener onStatusChange) async {
    if (!_initialized) return;
    await _speech.stop();
    if (_listening) {
      _listening = false;
      onStatusChange(VoiceInputStatus.idle, null);
    }
  }

  void dispose() {
    _speech.cancel();
  }
}
