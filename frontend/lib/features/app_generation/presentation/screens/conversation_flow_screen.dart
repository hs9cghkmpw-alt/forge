import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/forge_theme.dart';
import '../../../../json_ui/schema/forge_document.dart';
import '../../../../shared_widgets/forge_sparkle_mark.dart';
import '../../../../shared_widgets/generated_app_host_shell.dart';
import '../../../../shared_widgets/responsive_app_shell.dart';
import '../../../../shared_widgets/simulated_output_banner.dart';
import '../../../app_library/domain/entities/generation_history_entry.dart';
import '../../../app_library/domain/entities/saved_forge_app.dart';
import '../../../app_library/presentation/providers/app_library_provider.dart';
import '../../domain/entities/conversation_outcome.dart';
import '../../domain/entities/generation_outcome.dart';
import '../../domain/repositories/app_generation_repository.dart';
import '../providers/app_generation_provider.dart';
import '../providers/conversation_provider.dart';

/// FORGE-PRODUCT-VISION-002(2026-08-11)対応。`HomeScreen`(Space)から
/// 遷移する、複数ターンの会話でツールを組み立てる画面(Forming)。
///
/// 「話せば、形になる」体験の中心。`generation_flow_screen.dart`
/// (`/generate`・`/generate/confirm`、単発入力→最大3往復の確認)は
/// 無変更のまま残し、この画面は新設の`/converse`(design doc B章、
/// ADR-014)を使う。既存のCognitive Pipeline側がさらに`needs_
/// confirmation`を返した場合(実機確認済み)は、既存の`/generate/
/// confirm`フローへそのまま委譲する。
///
/// `currentDocument`が渡された場合(`GeneratedAppHostShell`の「ここを
/// 変える」から遷移、Held→Forming)、Backend側がUPDATE(TD40)を選び
/// うる。`ConversationUpdated`を受け取ったら、新しいDocumentを持って
/// `Navigator.pop()`し、呼び出し元(Held画面)が表示を差し替える。
class ConversationFlowScreen extends ConsumerStatefulWidget {
  /// `null`の場合、まだ何も送信せずに待機した状態で開く(`Generated
  /// AppHostShell`の「ここを変える」から遷移した場合——ユーザーは
  /// まだ何と言うか決めていない、Homeとは違う起点)。非nullの場合
  /// (Home画面から遷移)、この画面が開いた瞬間に1ターン目として送信する。
  final String? initialMessage;
  final String? provider;
  final Map<String, dynamic>? currentDocument;

  const ConversationFlowScreen({super.key, this.initialMessage, this.provider, this.currentDocument});

  bool get isUpdateMode => currentDocument != null;

  /// 「はい、どうぞ」Moment(指示書7章)の合計所要時間。
  ///
  /// 公開しているのはテストのためである——Widget Testがこの演出を
  /// 待つ際、マジックナンバー(「1500ms待つ」)を各テストへ散らすと、
  /// 演出の長さを変えた瞬間に複数のテストが理由不明で落ちる。
  static const handoffMomentDuration = Duration(milliseconds: 1500);

  @override
  ConsumerState<ConversationFlowScreen> createState() => _ConversationFlowScreenState();
}

class _ChatEntry {
  final bool isUser;
  final String text;
  const _ChatEntry({required this.isUser, required this.text});
}

class _ConversationFlowScreenState extends ConsumerState<ConversationFlowScreen> {
  final List<_ChatEntry> _transcript = [];
  final TextEditingController _replyController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  /// 直近に受け取ったASKレスポンスのsession_id。次の`_sendReply()`が
  /// 送るリクエストの構築にのみ使う(下記`_currentRequest`のコメント参照)。
  String? _sessionId;

  /// 現在監視中(または直近に送信済み)のリクエスト。**`build()`内で
  /// `_sessionId`等から毎回組み立て直さない**——ASKレスポンス処理で
  /// `_sessionId`をsetStateすると、その値を使って`build()`内で
  /// `ConversationTurnRequest`を再構築した場合、`nonce`はそのままでも
  /// `sessionId`が変わるため`==`が不一致になり、Riverpodが
  /// **同じユーザー発話で余分な`/converse`往復を発生させてしまう**
  /// (Widget Test実行で発見した実バグ、2026-08-11)。新しいリクエストは
  /// 必ず`_sendReply()`(ユーザーが実際に何かを送信した瞬間)でのみ
  /// 組み立てて`_currentRequest`へ確定させ、`build()`はそれを
  /// そのまま使う(スナップショット方式)。
  ConversationTurnRequest? _currentRequest;
  int _nonce = 0;
  bool _handledCurrentTurn = false;
  bool _awaitingReply = false;

  /// 保存(`SavedForgeApp.originalPrompt`等)用に、会話で最初にユーザーが
  /// 送った文を保持する。`widget.initialMessage`が`null`(「ここを変える」
  /// から空で始まった場合)は、`_sendReply()`で最初の送信時に確定する。
  String _originalPrompt = '';

  String? _pendingConfirmationRequestId;
  ConfirmationAnswerRequest? _activeConfirmRequest;
  int _confirmNonce = 0;

  String? _errorMessage;
  bool _retryable = true;

  bool _savedForCurrentResult = false;

  /// FORGE-HANDOFF-LOCAL-AI-UX-004 §9(2026-08-13)。直近の応答が
  /// Mockの模擬出力だったかどうか。`true`の間、画面上部に
  /// `SimulatedOutputBanner`を出す——「Silent Mock fallbackは禁止」。
  bool _simulated = false;

  @override
  void initState() {
    super.initState();
    final initial = widget.initialMessage;
    if (initial != null && initial.trim().isNotEmpty) {
      _originalPrompt = initial;
      _currentRequest = ConversationTurnRequest(
        message: initial, provider: widget.provider, currentDocument: widget.currentDocument, nonce: _nonce,
      );
      _transcript.add(_ChatEntry(isUser: true, text: initial));
    } else {
      // 「ここを変える」から遷移した場合: まだ何も送信しない。
      // Forgeから先に一言かけ、返信欄をすぐ出す(design doc 2章の
      // 「Forgeが先に聞く」という会話開始の形を、UPDATE再開時にも
      // 踏襲する)。
      _transcript.add(const _ChatEntry(isUser: false, text: 'どこを変えましょうか？'));
      _awaitingReply = true;
    }
  }

  @override
  void dispose() {
    _replyController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottomSoon() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    });
  }

  void _sendReply() {
    final text = _replyController.text.trim();
    if (text.isEmpty) return;
    final requestId = _pendingConfirmationRequestId;
    setState(() {
      _transcript.add(_ChatEntry(isUser: true, text: text));
      _awaitingReply = false;
      _errorMessage = null;
      _replyController.clear();
      if (requestId != null) {
        _pendingConfirmationRequestId = null;
        _confirmNonce += 1;
        _activeConfirmRequest = ConfirmationAnswerRequest(requestId: requestId, answer: text, nonce: _confirmNonce);
      } else {
        if (_originalPrompt.isEmpty) _originalPrompt = text;
        _nonce += 1;
        _handledCurrentTurn = false;
        _currentRequest = ConversationTurnRequest(
          sessionId: _sessionId, message: text, provider: widget.provider,
          currentDocument: widget.currentDocument, nonce: _nonce,
        );
      }
    });
    _scrollToBottomSoon();
  }

  void _retry() {
    setState(() {
      _errorMessage = null;
      _handledCurrentTurn = false;
      if (_activeConfirmRequest != null) {
        _confirmNonce += 1;
        _activeConfirmRequest = ConfirmationAnswerRequest(
          requestId: _activeConfirmRequest!.requestId, answer: _activeConfirmRequest!.answer, nonce: _confirmNonce,
        );
      } else if (_currentRequest != null) {
        _nonce += 1;
        _currentRequest = ConversationTurnRequest(
          sessionId: _currentRequest!.sessionId, message: _currentRequest!.message, provider: widget.provider,
          currentDocument: widget.currentDocument, nonce: _nonce,
        );
      }
    });
  }

  void _handleConversationOutcome(ConversationOutcome outcome) {
    // 模擬出力かどうかは、どの結果種別でも同じように記録する
    // (§9: Mockであることを黙って隠さない)。
    //
    // **一度trueになったらfalseへ戻さない**。模擬かどうかは会話の
    // 1ターンの性質ではなく、そのセッションが使っているProviderの
    // 性質だからである。実際、Cognitive Pipeline側が確認を求めた場合の
    // `ConversationFallbackConfirmation`はこのフィールドを持たない
    // (`/generate`と共有のレスポンス型)ため、素直に代入すると会話の
    // 途中でバナーが消える——実際にHTTPで流して確認した。
    if (outcome.simulated && !_simulated) {
      setState(() => _simulated = true);
    }
    switch (outcome) {
      case ConversationAsk(:final sessionId, :final question):
        setState(() {
          _sessionId = sessionId;
          _transcript.add(_ChatEntry(isUser: false, text: question));
          _awaitingReply = true;
        });
        _scrollToBottomSoon();
      case ConversationConfirm(:final sessionId, :final question):
        // 指示書4章: 確認は専用画面ではなく、会話の1ターンとして出す。
        // ユーザーの返事は通常どおり`/converse`へ戻る。
        setState(() {
          _sessionId = sessionId;
          _transcript.add(_ChatEntry(isUser: false, text: question));
          _awaitingReply = true;
        });
        _scrollToBottomSoon();
      case ConversationBuilt(:final result):
        _finishBuild(result);
      case ConversationUpdated(:final forgeDocument):
        Navigator.of(context).pop(forgeDocument);
      case ConversationFallbackConfirmation(:final confirmation):
        setState(() {
          _transcript.add(_ChatEntry(isUser: false, text: confirmation.question));
          _pendingConfirmationRequestId = confirmation.requestId;
          _awaitingReply = true;
        });
        _scrollToBottomSoon();
      case ConversationFailure(:final failure):
        setState(() {
          _errorMessage = failure.message;
          _retryable = failure.retryable;
        });
    }
  }

  void _handleGenerationOutcome(GenerationOutcome outcome) {
    switch (outcome) {
      case GenerationSuccess():
        _finishBuild(outcome);
      case GenerationNeedsConfirmation(:final requestId, :final question):
        setState(() {
          _activeConfirmRequest = null;
          _transcript.add(_ChatEntry(isUser: false, text: question));
          _pendingConfirmationRequestId = requestId;
          _awaitingReply = true;
        });
        _scrollToBottomSoon();
      case GenerationFailure(:final message, :final retryable):
        setState(() {
          _errorMessage = message;
          _retryable = retryable;
        });
    }
  }

  /// 「はい、どうぞ」Moment(FORGE-CONVERSATION-READY-001、2026-08-12、
  /// 指示書7章)。
  ///
  /// チャットから使えるものへ、意味的につながったまま切り替わる体験を
  /// つくる。単なる画面遷移にしないが、**アニメーション過多にもしない**
  /// ——足すのは3つの短い発話だけで、合計1.5秒に収める(指示書7章
  /// 「長い待機画面も避ける」)。生成そのものの待ち時間は、既存の
  /// `_ThinkingBubble`が担っている。
  ///
  /// 「こんなのがあると楽そう。」に**実際に作られた道具の名前**を
  /// 差し込むのが要点である(指示書7章「会話からToolへ意味的に
  /// つながる文言」)——ここが汎用文言だと、ただの装飾になる。
  static const _handoffBeat = Duration(milliseconds: 550);
  static const _handoffFinalBeat = Duration(milliseconds: 400);

  Future<void> _playHandoffMoment(String title) async {
    void say(String text) {
      if (!mounted) return;
      setState(() => _transcript.add(_ChatEntry(isUser: false, text: text)));
      _scrollToBottomSoon();
    }

    say('うん、だいたい分かった。');
    await Future<void>.delayed(_handoffBeat);
    if (!mounted) return;
    say('「$title」があると楽そう。');
    await Future<void>.delayed(_handoffBeat);
    if (!mounted) return;
    say('はい、どうぞ。');
    await Future<void>.delayed(_handoffFinalBeat);
  }

  Future<void> _finishBuild(GenerationSuccess result) async {
    if (_savedForCurrentResult) return;
    _savedForCurrentResult = true;

    final now = DateTime.now();
    final id = '${now.microsecondsSinceEpoch}';
    String title = 'あなたのアプリ';
    try {
      title = ForgeDocument.fromJson(result.forgeDocument).appTitle ?? title;
    } catch (_) {
      // タイトルが取れなくても保存自体は続ける。
    }

    final repository = ref.read(appLibraryRepositoryProvider);
    await repository.saveApp(SavedForgeApp(
      id: id,
      title: title,
      originalPrompt: _originalPrompt,
      forgeDocument: result.forgeDocument,
      createdAt: now,
      updatedAt: now,
      providerUsed: result.diagnostics.providerUsed,
      qualityScore: result.quality?.score,
    ));
    await repository.addHistoryEntry(GenerationHistoryEntry(
      id: id, prompt: _originalPrompt, status: GenerationHistoryStatus.success, createdAt: now, appId: id,
    ));
    ref.invalidate(savedAppsProvider);
    ref.invalidate(generationHistoryProvider);

    if (!mounted) return;
    // 指示書7章「はい、どうぞ」Moment。保存はここまでで完了しており、
    // ここから先は演出だけなので、途中で失敗しても道具は失われない。
    await _playHandoffMoment(title);
    if (!mounted) return;
    // **FORGE-HANDOFF-LOCAL-AI-UX-004 §31 / -005 §25 で報告された実機バグの修正**。
    //
    // 症状: 生成されたToolの左上「戻る」を押しても何も起きない。
    //
    // 原因は2つ重なっていた。
    //
    // 1. `pushReplacement`でConversationFlowScreenを**破棄**していた。
    //    §32の期待仕様「Tool → 戻る → Conversation」は、Conversationが
    //    スタックから消えている以上、原理的に成立しない。
    // 2. `onBack`が`Navigator.of(context)`の`context`として、
    //    **この画面(ConversationFlowScreen)自身のcontext**を捕捉して
    //    いた。`pushReplacement`直後にこのElementはunmountされるため、
    //    押しても解決先のNavigatorが得られず、実機では「無反応」に
    //    見えていた。
    //
    // したがって`push`へ変え、`onBack`は**新しいRouteのcontext**
    // (`routeContext`)から解決する。これで戻り先はConversationになり、
    // 会話の続き(さらに戻ればHome)も維持される。
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (routeContext) => Scaffold(
        body: SafeArea(
          child: GeneratedAppHostShell(
            forgeDocument: result.forgeDocument,
            onBack: () => Navigator.of(routeContext).pop(),
            // §9: 生成されたTool側でも、模擬データであることを隠さない。
            simulated: _simulated,
            provider: widget.provider,
            onDocumentUpdated: (updated) => repository.saveApp(SavedForgeApp(
              id: id, title: title, originalPrompt: _originalPrompt, forgeDocument: updated,
              createdAt: now, updatedAt: DateTime.now(), providerUsed: result.diagnostics.providerUsed,
              qualityScore: result.quality?.score,
            )),
            onScreenStateChanged: (screenId, stateJson) =>
                repository.saveRuntimeStateForScreen(id, screenId, stateJson),
          ),
        ),
      ),
    ));
  }

  @override
  Widget build(BuildContext context) {
    AsyncValue<Object?> asyncOutcome = const AsyncData(null);
    final activeConfirm = _activeConfirmRequest;
    final request = _currentRequest;
    if (activeConfirm != null) {
      asyncOutcome = ref.watch(confirmGenerationProvider(activeConfirm));
      ref.listen(confirmGenerationProvider(activeConfirm), (previous, next) {
        next.whenData((outcome) {
          if (_handledCurrentTurn) return;
          _handledCurrentTurn = true;
          _handleGenerationOutcome(outcome);
        });
      });
    } else if (request != null) {
      // `request`は`_sendReply()`/`initState()`で確定したスナップショット
      // であり、ここで`_sessionId`等から毎回組み立て直さない
      // (`_currentRequest`のコメント参照——組み立て直すと、ASK処理の
      // 副作用で余分な`/converse`呼び出しが発生する実バグになる)。
      asyncOutcome = ref.watch(conversationTurnProvider(request));
      ref.listen(conversationTurnProvider(request), (previous, next) {
        next.whenData((outcome) {
          if (_handledCurrentTurn) return;
          _handledCurrentTurn = true;
          _handleConversationOutcome(outcome);
        });
      });
    }
    // `request == null && activeConfirm == null`: まだ何も送信していない
    // 待機状態(「ここを変える」直後)。既定の`AsyncData(null)`
    // (isLoading=false・hasError=false)のまま、返信欄だけを表示する。

    final isThinking = asyncOutcome.isLoading;
    final streamError = asyncOutcome.hasError ? asyncOutcome.error : null;

    return ResponsiveAppShell(
      child: Scaffold(
        backgroundColor: ForgeTheme.consoleBackground,
        appBar: AppBar(
          backgroundColor: ForgeTheme.consoleBackground,
          elevation: 0,
          foregroundColor: ForgeTheme.consoleInk,
          title: Text(widget.isUpdateMode ? 'ここを変える' : 'Forgeと話す'),
        ),
        body: SafeArea(
          child: Column(
            children: [
              SimulatedOutputBanner(simulated: _simulated),
              Expanded(
                child: _errorMessage != null || streamError != null
                    ? _ConversationErrorView(
                        message: _errorMessage ?? _streamErrorMessage(streamError),
                        retryable: _errorMessage == null || _retryable,
                        onRetry: _retry,
                      )
                    : _TranscriptView(
                        controller: _scrollController, entries: _transcript, thinking: isThinking,
                      ),
              ),
              if (_awaitingReply && _errorMessage == null && streamError == null)
                _ReplyBar(controller: _replyController, onSend: _sendReply),
            ],
          ),
        ),
      ),
    );
  }

  String _streamErrorMessage(Object? error) {
    if (error is AppGenerationException) return error.message;
    return '接続できませんでした。';
  }
}

class _TranscriptView extends StatelessWidget {
  final ScrollController controller;
  final List<_ChatEntry> entries;
  final bool thinking;

  const _TranscriptView({required this.controller, required this.entries, required this.thinking});

  @override
  Widget build(BuildContext context) {
    return ListView(
      controller: controller,
      padding: const EdgeInsets.all(20),
      children: [
        for (final entry in entries) _ChatBubble(entry: entry),
        if (thinking) const _ThinkingBubble(),
      ],
    );
  }
}

class _ChatBubble extends StatelessWidget {
  final _ChatEntry entry;
  const _ChatBubble({required this.entry});

  @override
  Widget build(BuildContext context) {
    final isUser = entry.isUser;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          if (!isUser) ...[const ForgeSparkleMark(size: 20), const SizedBox(width: 8)],
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                gradient: isUser ? ForgeTheme.brandGradient : null,
                color: isUser ? null : ForgeTheme.consoleSurface,
                borderRadius: BorderRadius.circular(18),
              ),
              child: Text(
                entry.text,
                style: TextStyle(
                  fontSize: 15, height: 1.4,
                  color: isUser ? Colors.white : ForgeTheme.consoleInk,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ThinkingBubble extends StatelessWidget {
  const _ThinkingBubble();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          const ForgeSparkleMark(size: 20),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: BoxDecoration(color: ForgeTheme.consoleSurface, borderRadius: BorderRadius.circular(18)),
            child: const SizedBox(
              width: 18, height: 18,
              child: CircularProgressIndicator(strokeWidth: 2, valueColor: AlwaysStoppedAnimation(ForgeTheme.gradientEnd)),
            ),
          ),
        ],
      ),
    );
  }
}

class _ReplyBar extends StatefulWidget {
  final TextEditingController controller;
  final VoidCallback onSend;
  const _ReplyBar({required this.controller, required this.onSend});

  @override
  State<_ReplyBar> createState() => _ReplyBarState();
}

class _ReplyBarState extends State<_ReplyBar> {
  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onChanged);
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onChanged);
    super.dispose();
  }

  void _onChanged() => setState(() {});

  @override
  Widget build(BuildContext context) {
    final canSend = widget.controller.text.trim().isNotEmpty;
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: ForgeTheme.consoleBorder)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: TextField(
              controller: widget.controller,
              minLines: 1,
              maxLines: 4,
              style: const TextStyle(fontSize: 15, color: ForgeTheme.consoleInk),
              cursorColor: ForgeTheme.consoleInk,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => widget.onSend(),
              decoration: InputDecoration(
                hintText: '返信を入力',
                hintStyle: const TextStyle(color: ForgeTheme.consoleInkSoft),
                filled: true,
                fillColor: ForgeTheme.consoleSurface,
                contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(18),
                  borderSide: const BorderSide(color: ForgeTheme.consoleBorder),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(18),
                  borderSide: const BorderSide(color: ForgeTheme.consoleBorder),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(18),
                  borderSide: const BorderSide(color: ForgeTheme.gradientEnd, width: 1.5),
                ),
              ),
            ),
          ),
          const SizedBox(width: 10),
          Container(
            width: 48, height: 48,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: canSend ? ForgeTheme.brandGradient : null,
              color: canSend ? null : ForgeTheme.consoleSurface,
              border: canSend ? null : Border.all(color: ForgeTheme.consoleBorder),
            ),
            child: Material(
              color: Colors.transparent,
              shape: const CircleBorder(),
              child: InkWell(
                customBorder: const CircleBorder(),
                onTap: canSend ? widget.onSend : null,
                child: Icon(Icons.arrow_upward_rounded, color: canSend ? Colors.white : ForgeTheme.consoleInkSoft),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ConversationErrorView extends StatelessWidget {
  final String message;
  final bool retryable;
  final VoidCallback onRetry;
  const _ConversationErrorView({required this.message, required this.retryable, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline_rounded, size: 40, color: Colors.redAccent),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center, style: const TextStyle(color: ForgeTheme.consoleInk)),
            const SizedBox(height: 20),
            if (retryable)
              OutlinedButton(onPressed: onRetry, child: const Text('もう一度試す'))
            else
              OutlinedButton(onPressed: () => Navigator.of(context).pop(), child: const Text('戻る')),
          ],
        ),
      ),
    );
  }
}
