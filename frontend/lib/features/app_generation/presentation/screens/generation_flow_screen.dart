import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/forge_theme.dart';
import '../../../../json_ui/renderer/forge_renderer.dart';
import '../../../../json_ui/schema/forge_document.dart';
import '../../../../shared_widgets/forge_mark.dart';
import '../../../../shared_widgets/generated_app_host_shell.dart';
import '../../../../shared_widgets/responsive_app_shell.dart';
import '../../../app_library/domain/entities/generation_history_entry.dart';
import '../../../app_library/domain/entities/saved_forge_app.dart';
import '../../../app_library/presentation/providers/app_library_provider.dart';
import '../../domain/entities/generation_outcome.dart';
import '../../domain/repositories/app_generation_repository.dart';
import '../providers/app_generation_provider.dart';

/// `HomeScreen`から遷移する、生成フロー全体を1画面で表現するもの。
///
/// FORGE v0.2 P0・P5対応(まとめて記録):
/// * needs_confirmationを正式に扱う(確認質問→回答→再生成、指示書13章)。
/// * 「もう一度試す」が実際に再実行される(P5、`GenerationRequest`の
///   nonceを増やして新しいFutureProviderキーを作る)。
/// * 生成中の演出を3段階のメッセージ切り替えへ戻した(P5)。
/// * 「保存してあとで見る」が実際に`SharedPreferences`へ保存する(P5)。
/// * 「アプリを開く」も、開く前に保存する(あとから履歴・マイアプリに残る)。
/// * 完成画面の機能概要を、実際に生成されたDocumentから抽出する(P5)。
/// * `ResponsiveAppShell`でChrome中央最大幅に対応。
class GenerationFlowScreen extends ConsumerStatefulWidget {
  final String inputText;
  const GenerationFlowScreen({super.key, required this.inputText});

  @override
  ConsumerState<GenerationFlowScreen> createState() => _GenerationFlowScreenState();
}

class _GenerationFlowScreenState extends ConsumerState<GenerationFlowScreen> {
  int _generateNonce = 0;
  int _confirmNonce = 0;
  bool _appOpened = false;
  bool _savedForCurrentResult = false;

  // 確認フローに入ったら、以降はconfirmGenerationProviderを見る。
  ConfirmationAnswerRequest? _activeConfirmRequest;

  @override
  Widget build(BuildContext context) {
    final AsyncValue<GenerationOutcome> asyncOutcome;
    if (_activeConfirmRequest != null) {
      asyncOutcome = ref.watch(confirmGenerationProvider(_activeConfirmRequest!));
    } else {
      asyncOutcome = ref.watch(
        appGenerationProvider(GenerationRequest(text: widget.inputText, nonce: _generateNonce)),
      );
    }

    return ResponsiveAppShell(
      child: asyncOutcome.when(
        loading: () => const _GeneratingView(),
        error: (error, _) => _GenerationErrorView(error: error, onRetry: _retryFromScratch),
        data: (outcome) => switch (outcome) {
          GenerationSuccess() => _buildSuccess(outcome),
          GenerationNeedsConfirmation() => _ConfirmationView(
              outcome: outcome,
              onSubmit: (answer) => _submitConfirmation(outcome.requestId, answer),
            ),
          GenerationFailure() => _GenerationErrorView(
              error: outcome,
              onRetry: _retryFromScratch,
            ),
        },
      ),
    );
  }

  void _retryFromScratch() {
    setState(() {
      _activeConfirmRequest = null;
      _savedForCurrentResult = false;
      _appOpened = false;
      _generateNonce += 1;
    });
  }

  void _submitConfirmation(String requestId, String answer) {
    setState(() {
      _savedForCurrentResult = false;
      _confirmNonce += 1;
      _activeConfirmRequest = ConfirmationAnswerRequest(
        requestId: requestId,
        answer: answer,
        nonce: _confirmNonce,
      );
    });
  }

  Widget _buildSuccess(GenerationSuccess outcome) {
    if (_appOpened) {
      return Scaffold(
        body: SafeArea(
          child: GeneratedAppHostShell(
            forgeDocument: outcome.forgeDocument,
            onBack: () => Navigator.of(context).pop(),
          ),
        ),
      );
    }
    return _CompletionView(
      outcome: outcome,
      onOpen: () async {
        await _persistSuccess(outcome);
        if (mounted) setState(() => _appOpened = true);
      },
      onSaveForLater: () async {
        await _persistSuccess(outcome);
        if (mounted) Navigator.of(context).pop();
      },
    );
  }

  /// FORGE v0.2 P5対応: 「あとで見る」も「アプリを開く」も、実際に
  /// `SharedPreferences`へ保存する(以前は「あとで見る」を押しても
  /// 何も保存されなかった)。同じ結果に対して二重保存しないよう
  /// `_savedForCurrentResult`で1回に制限する。
  Future<void> _persistSuccess(GenerationSuccess outcome) async {
    if (_savedForCurrentResult) return;
    _savedForCurrentResult = true;

    final now = DateTime.now();
    final id = '${now.microsecondsSinceEpoch}';
    String title = 'あなたのアプリ';
    try {
      title = ForgeDocument.fromJson(outcome.forgeDocument).appTitle ?? title;
    } catch (_) {
      // タイトルが取れなくても保存自体は続ける。
    }

    final repository = ref.read(appLibraryRepositoryProvider);
    await repository.saveApp(SavedForgeApp(
      id: id,
      title: title,
      originalPrompt: widget.inputText,
      forgeDocument: outcome.forgeDocument,
      createdAt: now,
      updatedAt: now,
      providerUsed: outcome.diagnostics.providerUsed,
      qualityScore: outcome.quality?.score,
    ));
    await repository.addHistoryEntry(GenerationHistoryEntry(
      id: id,
      prompt: widget.inputText,
      status: GenerationHistoryStatus.success,
      createdAt: now,
      appId: id,
    ));
    ref.invalidate(savedAppsProvider);
    ref.invalidate(generationHistoryProvider);
  }
}

/// 生成中画面。FORGE v0.2 P5対応: 静止メッセージではなく、3段階の
/// メッセージ切り替えへ戻した。**Backendが進捗をStreamingで返さないため、
/// これらは「厳密なサーバー進捗」ではなく、待機体験のための演出**である
/// (指示書17章、既に無効化されているMotionは尊重する)。
class _GeneratingView extends StatefulWidget {
  const _GeneratingView();

  @override
  State<_GeneratingView> createState() => _GeneratingViewState();
}

class _GeneratingViewState extends State<_GeneratingView> with SingleTickerProviderStateMixin {
  static const _stages = [
    'アイデアを理解しています',
    '使いやすい構成を考えています',
    '画面と機能を組み立てています',
    '最終チェックをしています',
  ];

  AnimationController? _controller;
  Timer? _stageTimer;
  int _stageIndex = 0;

  @override
  void initState() {
    super.initState();
    final reduceMotion = WidgetsBinding.instance.platformDispatcher.accessibilityFeatures.disableAnimations;
    if (!reduceMotion) {
      _controller = AnimationController(vsync: this, duration: const Duration(seconds: 2))..repeat();
    }
    _stageTimer = Timer.periodic(const Duration(milliseconds: 1400), (_) {
      if (!mounted) return;
      setState(() => _stageIndex = (_stageIndex + 1) % _stages.length);
    });
  }

  @override
  void dispose() {
    _controller?.dispose();
    _stageTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  width: 160,
                  height: 160,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      if (controller != null)
                        RotationTransition(
                          turns: controller,
                          child: SizedBox(
                            width: 160,
                            height: 160,
                            child: CircularProgressIndicator(
                              strokeWidth: 3,
                              valueColor: const AlwaysStoppedAnimation(ForgeTheme.accent),
                              backgroundColor: ForgeTheme.accentSoft,
                              value: 0.72,
                            ),
                          ),
                        )
                      else
                        const SizedBox(
                          width: 160,
                          height: 160,
                          child: CircularProgressIndicator(
                            strokeWidth: 3,
                            valueColor: AlwaysStoppedAnimation(ForgeTheme.accent),
                            backgroundColor: ForgeTheme.accentSoft,
                          ),
                        ),
                      const ForgeMark(size: 84),
                    ],
                  ),
                ),
                const SizedBox(height: 32),
                Text('アプリを作成しています…', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontSize: 20)),
                const SizedBox(height: 12),
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 250),
                  child: Text(
                    _stages[_stageIndex],
                    key: ValueKey(_stageIndex),
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// FORGE v0.2 P0.2対応。needs_confirmation時の確認画面。
class _ConfirmationView extends StatefulWidget {
  final GenerationNeedsConfirmation outcome;
  final void Function(String answer) onSubmit;

  const _ConfirmationView({required this.outcome, required this.onSubmit});

  @override
  State<_ConfirmationView> createState() => _ConfirmationViewState();
}

class _ConfirmationViewState extends State<_ConfirmationView> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final canSubmit = _controller.text.trim().isNotEmpty;
    return Scaffold(
      appBar: AppBar(title: const Text('確認させてください')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.help_outline_rounded, size: 36, color: ForgeTheme.accent),
              const SizedBox(height: 16),
              Text(widget.outcome.question, style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontSize: 18)),
              if (widget.outcome.openQuestions.isNotEmpty) ...[
                const SizedBox(height: 12),
                for (final q in widget.outcome.openQuestions)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text('・$q', style: Theme.of(context).textTheme.bodyMedium),
                  ),
              ],
              const SizedBox(height: 20),
              TextField(
                controller: _controller,
                onChanged: (_) => setState(() {}),
                minLines: 2,
                maxLines: 4,
                decoration: const InputDecoration(hintText: '回答を入力してください'),
              ),
              const SizedBox(height: 8),
              Text(
                'あと${widget.outcome.roundsRemaining}回まで確認できます。',
                style: const TextStyle(fontSize: 12, color: ForgeTheme.inkSoft),
              ),
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: canSubmit ? () => widget.onSubmit(_controller.text.trim()) : null,
                  child: const Text('回答して続ける'),
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton(
                  onPressed: () => Navigator.of(context).pop(),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: ForgeTheme.ink,
                    side: const BorderSide(color: Color(0xFFE8E4DC)),
                    minimumSize: const Size(0, 56),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                  ),
                  child: const Text('キャンセルして入力に戻る'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 完成画面。
class _CompletionView extends StatelessWidget {
  final GenerationSuccess outcome;
  final VoidCallback onOpen;
  final VoidCallback onSaveForLater;

  const _CompletionView({required this.outcome, required this.onOpen, required this.onSaveForLater});

  String get _title {
    try {
      return ForgeDocument.fromJson(outcome.forgeDocument).appTitle ?? 'あなたのアプリ';
    } catch (_) {
      return 'あなたのアプリ';
    }
  }

  /// FORGE v0.2 P5対応: 固定文言ではなく、実際に生成されたDocumentから
  /// 機能概要を抽出する(指示書18章「固定の嘘の機能説明は禁止」)。
  List<String> get _featureSummary {
    final items = <String>[];
    final screens = (outcome.forgeDocument['screens'] as List?) ?? const [];
    items.add('${screens.length}画面');
    final docString = jsonEncode(outcome.forgeDocument);
    if (docString.contains('"validation"')) items.add('入力内容の検証');
    if (docString.contains('"empty_state')) items.add('空の状態の表示');
    if (screens.length > 1) items.add('画面間の移動');
    final domain = outcome.diagnostics.domainClassification?['display_name'] as String? ??
        outcome.diagnostics.domainClassification?['primary_domain'] as String?;
    if (domain != null) items.add('$domain向けの構成');
    return items;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 28),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const ForgeMark(size: 72),
                const SizedBox(height: 8),
                Text('✨ アプリが完成しました！', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontSize: 20)),
                const SizedBox(height: 6),
                Text('さっそく試してみましょう。', style: Theme.of(context).textTheme.bodyMedium),
                const SizedBox(height: 28),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: ForgeTheme.surface,
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(color: const Color(0xFFEFEBE3)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              _title,
                              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: ForgeTheme.ink),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Container(
                            width: 48,
                            height: 48,
                            decoration:
                                BoxDecoration(color: ForgeTheme.accentSoft, borderRadius: BorderRadius.circular(14)),
                            child: const Icon(Icons.auto_awesome_rounded, color: ForgeTheme.accent),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final feature in _featureSummary)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                              decoration: BoxDecoration(
                                color: ForgeTheme.background,
                                borderRadius: BorderRadius.circular(999),
                              ),
                              child: Text(feature, style: const TextStyle(fontSize: 12, color: ForgeTheme.ink)),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(onPressed: onOpen, child: const Text('アプリを開く')),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton(
                    onPressed: onSaveForLater,
                    style: OutlinedButton.styleFrom(
                      foregroundColor: ForgeTheme.ink,
                      side: const BorderSide(color: Color(0xFFE8E4DC)),
                      minimumSize: const Size(0, 56),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                    ),
                    // FORGE v0.2 P5対応: 「あとで見る」は実際にマイアプリへ
                    // 保存するようになった(以前は保存せず画面を戻すだけだった)。
                    child: const Text('保存してあとで見る'),
                  ),
                ),
                const SizedBox(height: 20),
                TextButton(
                  onPressed: () => Navigator.of(context).popUntil((route) => route.isFirst),
                  child: const Text('他のアプリを作る', style: TextStyle(color: ForgeTheme.inkSoft)),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// エラー画面。FORGE v0.2 P5対応: 「もう一度試す」が実際に再実行される
/// (以前は`Navigator.pop()`するだけだった)。
class _GenerationErrorView extends StatelessWidget {
  final Object error;
  final VoidCallback onRetry;
  const _GenerationErrorView({required this.error, required this.onRetry});

  String get _message {
    if (error is AppGenerationException) return (error as AppGenerationException).message;
    if (error is GenerationFailure) return (error as GenerationFailure).message;
    return '接続できませんでした。';
  }

  bool get _retryable {
    if (error is GenerationFailure) return (error as GenerationFailure).retryable;
    return true; // 通信自体の失敗(AppGenerationException)は再試行可能とする
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('作成できませんでした')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline_rounded, size: 40, color: Colors.redAccent),
              const SizedBox(height: 12),
              Text(_message, textAlign: TextAlign.center),
              const SizedBox(height: 20),
              if (_retryable)
                OutlinedButton(onPressed: onRetry, child: const Text('もう一度試す'))
              else
                OutlinedButton(onPressed: () => Navigator.of(context).pop(), child: const Text('入力に戻る')),
            ],
          ),
        ),
      ),
    );
  }
}
