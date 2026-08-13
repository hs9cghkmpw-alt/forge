import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/config/app_config.dart';
import '../../../../core/theme/forge_theme.dart';
import '../../../../shared_widgets/forge_sparkle_mark.dart';
import '../../../../shared_widgets/generated_app_host_shell.dart';
import '../../../../shared_widgets/responsive_app_shell.dart';
import '../../../app_library/domain/entities/saved_forge_app.dart';
import '../../../app_library/presentation/providers/app_library_provider.dart';
import '../../../app_library/presentation/screens/history_screen.dart';
import '../../../app_library/presentation/screens/my_apps_screen.dart';
import '../providers/app_generation_provider.dart';
import '../providers/voice_input_provider.dart';
import '../widgets/example_picker_sheet.dart';
import 'conversation_flow_screen.dart';

/// ホーム画面。
///
/// FORGE v0.2 P5対応(過去のレビュー・修正指示への対応、まとめて記録):
/// * マイク機能が無いのに「話すだけで」「マイクアイコン」を出していた
///   矛盾を解消(コピーを実態に合わせ、マイクアイコンを削除)。
/// * アカウント機能が無いプロフィールボタンを削除。
/// * 「マイアプリ」「履歴」タブは、今回実装した実画面へ実際に遷移する
///   (以前は「準備中」というSnackBarを出すだけだった)。
/// * ホーム下部へ「最近のアプリ」(最大3件)を追加。
/// * `ResponsiveAppShell`でChrome中央最大幅に対応。
///
/// FORGE-UI-REFRESH(2026-08-10、CEO提示のUIモックアップに基づく):
/// * ロゴを`ForgeMark`(PNG、ネイビーF)から`ForgeSparkleMark`
///   (ベクター、紫→青グラデーション)へ変更。
/// * 画面全体を`ForgeTheme.consoleBackground`ベースのダーク配色にした
///   (「AIが考えている最中」の演出。完成画面・生成後アプリは既存の
///   lightな配色のまま据え置き、画面単位で意図的に切り替える設計)。
/// * 送信ボタンをグラデーション化。
/// * モックアップにある「クイック候補チップ」を追加(既存の`forgeExampleItems`
///   を流用。タップすると入力欄に入るだけで送信はしない、既存の
///   「例を見る」Bottom Sheetと同じ挙動を`_setPromptText()`で共通化)。
///   このUI刷新の時点では音声入力が未実装だったため、モックアップの
///   マイクアイコンは採用していなかった(実装していない機能をあるように
///   見せない、という既存方針をそのまま踏襲していた)。
///
/// FORGE-AI-CONNECT-001(2026-08-11): 実際に`speech_to_text`パッケージへ
/// 接続した音声入力を実装したため、上記の判断を更新し、マイクボタンを
/// 追加した(`_VoiceInputButton`)。`voice_input_provider.dart`冒頭の
/// docstring参照: Claude環境では未検証。
class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  final TextEditingController _controller = TextEditingController();
  final FocusNode _focusNode = FocusNode();
  int _selectedTabIndex = 0;

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _setPromptText(String phrase) {
    setState(() => _controller.text = phrase);
    _controller.selection = TextSelection.fromPosition(
      TextPosition(offset: _controller.text.length),
    );
  }

  Future<void> _onShowExamples() async {
    final phrase = await ExamplePickerSheet.show(context);
    if (phrase == null || !mounted) return;
    // Bottom Sheetは文章を入れるだけ。送信はしない(ユーザーが決める)。
    _setPromptText(phrase);
  }

  void _onSubmit() {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    final provider = ref.read(selectedAiProviderProvider);
    // FORGE-PRODUCT-VISION-002(2026-08-11)対応: 単発の生成
    // (`GenerationFlowScreen`、無変更のまま残す)ではなく、複数ターンの
    // 会話(`ConversationFlowScreen`、design doc C章)へ遷移する。
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => ConversationFlowScreen(initialMessage: text, provider: provider)),
    );
  }

  void _setPromptAndReturnHome(String prompt) {
    Navigator.of(context).popUntil((route) => route.isFirst);
    setState(() {
      _selectedTabIndex = 0;
      _controller.text = prompt;
    });
  }

  void _onTabTapped(int index) {
    if (index == _selectedTabIndex) return;
    if (index == 0) {
      setState(() => _selectedTabIndex = 0);
      return;
    }
    if (index == 1) {
      Navigator.of(context)
          .push(MaterialPageRoute<void>(builder: (_) => const MyAppsScreen()))
          .then((_) => setState(() => _selectedTabIndex = 0));
      return;
    }
    Navigator.of(context)
        .push(MaterialPageRoute<void>(
          builder: (_) => HistoryScreen(onReusePrompt: _setPromptAndReturnHome),
        ))
        .then((_) => setState(() => _selectedTabIndex = 0));
  }

  // FORGE-AI-QUALITY-001(2026-08-11)対応(ローカル永続化)。
  // `my_apps_screen.dart`の`_openApp`と同じ理由・同じ方式。
  Future<void> _openSavedApp(SavedForgeApp app) async {
    final repository = ref.read(appLibraryRepositoryProvider);
    final runtimeState = await repository.loadRuntimeState(app.id);
    if (!mounted) return;
    final provider = ref.read(selectedAiProviderProvider);
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => Scaffold(
          body: SafeArea(
            child: GeneratedAppHostShell(
              forgeDocument: app.forgeDocument,
              onBack: () => Navigator.of(context).pop(),
              initialRuntimeState: runtimeState,
              provider: provider,
              // FORGE-PRODUCT-VISION-002(2026-08-11)対応: 保存済みアプリを
              // 開いた画面(Held)からも「ここを変える」で会話に戻れる
              // (design doc C章)。
              onDocumentUpdated: (updated) => repository.saveApp(SavedForgeApp(
                id: app.id, title: app.title, originalPrompt: app.originalPrompt, forgeDocument: updated,
                createdAt: app.createdAt, updatedAt: DateTime.now(), providerUsed: app.providerUsed,
                qualityScore: app.qualityScore,
              )),
              onScreenStateChanged: (screenId, stateJson) =>
                  repository.saveRuntimeStateForScreen(app.id, screenId, stateJson),
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final canSubmit = _controller.text.trim().isNotEmpty;
    final recentApps = ref.watch(savedAppsProvider);

    return ResponsiveAppShell(
      child: Scaffold(
        backgroundColor: ForgeTheme.consoleBackground,
        body: SafeArea(
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 8, 12, 0),
                child: Row(
                  children: [
                    const ForgeSparkleMark(size: 26),
                    const SizedBox(width: 8),
                    const Text(
                      'Forge',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: ForgeTheme.consoleInk),
                    ),
                    const Spacer(),
                    // FORGE-AI-CONNECT-001対応(2026-08-10): Mock Modeで
                    // ビルドされている場合(`USE_MOCK_GENERATION=true`)は
                    // Backendへ接続しないため、Provider切り替え自体が
                    // 意味を持たない。Live Mode(既定)のときだけ表示する。
                    if (!AppConfig.current.mockMode) const _ProviderToggle(),
                  ],
                ),
              ),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: Column(
                    children: [
                      const SizedBox(height: 20),
                      const ForgeSparkleMark(size: 72),
                      const SizedBox(height: 24),
                      // FORGE-PRODUCT-VISION-002(2026-08-11)対応:
                      // 「アプリを作るAI」ではなく「困りごとを話すと道具が
                      // 生まれるAI」という製品思想更新(design doc C.1、
                      // Space)に合わせ、「何のアプリを作りますか」的な
                      // 導入文言から「困りごとを話せる場所」的な文言へ
                      // 変更した。入力欄への遷移先自体は
                      // `ConversationFlowScreen`(複数ターンの会話)へ
                      // 既に切り替え済み(`_onSubmit()`参照)。
                      const Text(
                        '最近、ちょっと\n困ってることある？',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.w600,
                          color: ForgeTheme.consoleInk,
                          letterSpacing: -0.5,
                          height: 1.3,
                        ),
                      ),
                      const SizedBox(height: 12),
                      const Text(
                        '面倒だな、忘れちゃう、毎回同じことしてる——\nそんな一言をそのまま話してください。',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 14, color: ForgeTheme.consoleInkSoft, height: 1.4),
                      ),
                      const SizedBox(height: 28),
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Expanded(
                            child: TextField(
                              controller: _controller,
                              focusNode: _focusNode,
                              onChanged: (_) => setState(() {}),
                              minLines: 1,
                              maxLines: 4,
                              style: const TextStyle(fontSize: 16, color: ForgeTheme.consoleInk),
                              cursorColor: ForgeTheme.consoleInk,
                              textInputAction: TextInputAction.done,
                              decoration: InputDecoration(
                                hintText: '困っていることを話してみてください',
                                hintStyle: const TextStyle(color: ForgeTheme.consoleInkSoft),
                                filled: true,
                                fillColor: ForgeTheme.consoleSurface,
                                contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(20),
                                  borderSide: const BorderSide(color: ForgeTheme.consoleBorder),
                                ),
                                enabledBorder: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(20),
                                  borderSide: const BorderSide(color: ForgeTheme.consoleBorder),
                                ),
                                focusedBorder: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(20),
                                  borderSide: const BorderSide(color: ForgeTheme.gradientEnd, width: 1.5),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          _VoiceInputButton(onResult: _setPromptText),
                          const SizedBox(width: 10),
                          _SendButton(enabled: canSubmit, onPressed: _onSubmit),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Wrap(
                        alignment: WrapAlignment.center,
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final item in forgeExampleItems.take(4))
                            _QuickPickChip(label: item.title, onTap: () => _setPromptText(item.phrase)),
                        ],
                      ),
                      const SizedBox(height: 18),
                      const Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.lock_outline_rounded, size: 14, color: ForgeTheme.consoleInkSoft),
                          SizedBox(width: 6),
                          Text(
                            '会話内容は安全に保護されます',
                            style: TextStyle(fontSize: 13, color: ForgeTheme.consoleInkSoft),
                          ),
                        ],
                      ),
                      const SizedBox(height: 14),
                      OutlinedButton.icon(
                        onPressed: _onShowExamples,
                        icon: const Icon(Icons.lightbulb_outline_rounded, size: 18, color: ForgeTheme.gradientEnd),
                        label: const Text('もっと例を見る'),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: ForgeTheme.consoleInk,
                          side: const BorderSide(color: ForgeTheme.consoleBorder),
                          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
                        ),
                      ),
                      const SizedBox(height: 32),
                      recentApps.when(
                        loading: () => const SizedBox.shrink(),
                        error: (_, __) => const SizedBox.shrink(),
                        data: (apps) {
                          if (apps.isEmpty) return const SizedBox.shrink();
                          final recent = apps.take(3).toList();
                          return Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                '最近のアプリ',
                                style: TextStyle(fontSize: 13, color: ForgeTheme.consoleInkSoft),
                              ),
                              const SizedBox(height: 10),
                              for (final app in recent) ...[
                                _RecentAppCard(app: app, onTap: () => _openSavedApp(app)),
                                const SizedBox(height: 8),
                              ],
                            ],
                          );
                        },
                      ),
                      const SizedBox(height: 24),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
        bottomNavigationBar: BottomNavigationBar(
          currentIndex: _selectedTabIndex,
          onTap: _onTabTapped,
          type: BottomNavigationBarType.fixed,
          backgroundColor: ForgeTheme.consoleSurface,
          selectedItemColor: const Color(0xFFB9AFFA),
          unselectedItemColor: ForgeTheme.consoleInkSoft,
          items: const [
            BottomNavigationBarItem(icon: Icon(Icons.home_rounded), label: 'ホーム'),
            BottomNavigationBarItem(icon: Icon(Icons.grid_view_rounded), label: 'マイアプリ'),
            BottomNavigationBarItem(icon: Icon(Icons.history_rounded), label: '履歴'),
          ],
        ),
      ),
    );
  }
}

class _QuickPickChip extends StatelessWidget {
  final String label;
  final VoidCallback onTap;

  const _QuickPickChip({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: ForgeTheme.consoleSurface,
      borderRadius: BorderRadius.circular(999),
      child: InkWell(
        borderRadius: BorderRadius.circular(999),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(999),
            border: Border.all(color: ForgeTheme.consoleBorder),
          ),
          child: Text(
            label,
            style: const TextStyle(fontSize: 13, color: ForgeTheme.consoleInk, fontWeight: FontWeight.w500),
          ),
        ),
      ),
    );
  }
}

class _RecentAppCard extends StatelessWidget {
  final SavedForgeApp app;
  final VoidCallback onTap;
  const _RecentAppCard({required this.app, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: ForgeTheme.consoleSurface,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(gradient: ForgeTheme.brandGradient, borderRadius: BorderRadius.circular(10)),
                child: const Icon(Icons.auto_awesome_rounded, color: Colors.white, size: 18),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  app.title,
                  style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: ForgeTheme.consoleInk),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const Icon(Icons.chevron_right_rounded, color: ForgeTheme.consoleInkSoft, size: 20),
            ],
          ),
        ),
      ),
    );
  }
}

/// FORGE-AI-CONNECT-001対応(2026-08-11)。マイクボタン。タップで
/// `VoiceInputController`経由の音声認識を開始/停止する。
///
/// **未検証(重要)**: `voice_input_provider.dart`冒頭のdocstring参照。
/// Claude環境では一度も実行できていない。
///
/// 「動いたふりをしない」という既存方針(このファイル冒頭のコメント
/// 参照)を守るため、`VoiceInputStatus.unavailable`の場合はタップしても
/// 再試行せず、その旨を1回だけSnackBarで伝える(無言で何も起きない
/// ボタンにしない)。
class _VoiceInputButton extends StatefulWidget {
  final void Function(String text) onResult;

  const _VoiceInputButton({required this.onResult});

  @override
  State<_VoiceInputButton> createState() => _VoiceInputButtonState();
}

class _VoiceInputButtonState extends State<_VoiceInputButton> {
  final VoiceInputController _controller = VoiceInputController();
  VoiceInputStatus _status = VoiceInputStatus.idle;

  void _handleStatusChange(VoiceInputStatus status, String? errorMessage) {
    if (!mounted) return;
    setState(() => _status = status);
  }

  Future<void> _onTap() async {
    if (_status == VoiceInputStatus.listening) {
      await _controller.stopListening(_handleStatusChange);
      return;
    }

    if (_status == VoiceInputStatus.unavailable) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('この端末・ブラウザでは音声入力を利用できません。テキストで入力してください。')),
      );
      return;
    }

    await _controller.startListening(onResult: widget.onResult, onStatusChange: _handleStatusChange);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isListening = _status == VoiceInputStatus.listening;
    final isUnavailable = _status == VoiceInputStatus.unavailable;

    return Tooltip(
      message: isListening ? '音声入力を停止' : '音声入力',
      child: Container(
        width: 52,
        height: 52,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: isListening ? const Color(0xFF3D1620) : ForgeTheme.consoleSurface,
          border: Border.all(
            color: isListening ? const Color(0xFFE05A6E) : ForgeTheme.consoleBorder,
          ),
        ),
        child: Material(
          color: Colors.transparent,
          shape: const CircleBorder(),
          child: InkWell(
            customBorder: const CircleBorder(),
            onTap: _onTap,
            child: Icon(
              isListening
                  ? Icons.mic_rounded
                  : (isUnavailable ? Icons.mic_off_rounded : Icons.mic_none_rounded),
              color: isListening ? const Color(0xFFE05A6E) : ForgeTheme.consoleInkSoft,
            ),
          ),
        ),
      ),
    );
  }
}

class _SendButton extends StatelessWidget {
  final bool enabled;
  final VoidCallback onPressed;

  const _SendButton({required this.enabled, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: '送信',
      child: Container(
        width: 52,
        height: 52,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: enabled ? ForgeTheme.brandGradient : null,
          color: enabled ? null : ForgeTheme.consoleSurface,
          border: enabled ? null : Border.all(color: ForgeTheme.consoleBorder),
        ),
        child: Material(
          color: Colors.transparent,
          shape: const CircleBorder(),
          child: InkWell(
            customBorder: const CircleBorder(),
            onTap: enabled ? onPressed : null,
            child: Icon(
              Icons.arrow_upward_rounded,
              color: enabled ? Colors.white : ForgeTheme.consoleInkSoft,
            ),
          ),
        ),
      ),
    );
  }
}

/// FORGE-AI-CONNECT-001対応(2026-08-10)。Backendの生成Providerを
/// `mock`⇔`gemini`でタップ切り替えする、小さなピル型トグル。
///
/// 「設定より会話」(Forge Constitution第三原則)を踏まえ、専用の設定画面は
/// 作らず、ホーム画面のヘッダーに収まる最小限のUIにした。永続化もしない
/// (`selectedAiProviderProvider`参照)。
class _ProviderToggle extends ConsumerWidget {
  const _ProviderToggle();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final provider = ref.watch(selectedAiProviderProvider);
    final isGemini = provider == 'gemini';

    return Tooltip(
      message: isGemini ? 'Gemini APIを使用中(タップでMockへ切り替え)' : 'Mockを使用中(タップでGeminiへ切り替え)',
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(999),
        child: InkWell(
          borderRadius: BorderRadius.circular(999),
          onTap: () => ref.read(selectedAiProviderProvider.notifier).state = isGemini ? null : 'gemini',
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: isGemini ? ForgeTheme.gradientEnd : ForgeTheme.consoleBorder),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  isGemini ? Icons.auto_awesome_rounded : Icons.smart_toy_outlined,
                  size: 14,
                  color: isGemini ? ForgeTheme.gradientEnd : ForgeTheme.consoleInkSoft,
                ),
                const SizedBox(width: 5),
                Text(
                  isGemini ? 'Gemini' : 'Mock',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: isGemini ? ForgeTheme.consoleInk : ForgeTheme.consoleInkSoft,
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
