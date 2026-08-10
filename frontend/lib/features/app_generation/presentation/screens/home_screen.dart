import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/forge_theme.dart';
import '../../../../shared_widgets/forge_mark.dart';
import '../../../../shared_widgets/generated_app_host_shell.dart';
import '../../../../shared_widgets/responsive_app_shell.dart';
import '../../../app_library/domain/entities/saved_forge_app.dart';
import '../../../app_library/presentation/providers/app_library_provider.dart';
import '../../../app_library/presentation/screens/history_screen.dart';
import '../../../app_library/presentation/screens/my_apps_screen.dart';
import '../widgets/example_picker_sheet.dart';
import 'generation_flow_screen.dart';

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

  Future<void> _onShowExamples() async {
    final phrase = await ExamplePickerSheet.show(context);
    if (phrase == null || !mounted) return;
    setState(() => _controller.text = phrase);
    _controller.selection = TextSelection.fromPosition(
      TextPosition(offset: _controller.text.length),
    );
    // Bottom Sheetは文章を入れるだけ。送信はしない(ユーザーが決める)。
  }

  void _onSubmit() {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => GenerationFlowScreen(inputText: text)),
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

  void _openSavedApp(SavedForgeApp app) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => Scaffold(
          body: SafeArea(
            child: GeneratedAppHostShell(
              forgeDocument: app.forgeDocument,
              onBack: () => Navigator.of(context).pop(),
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
        body: SafeArea(
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 8, 12, 0),
                child: Row(
                  children: [
                    const ForgeMark(size: 28),
                    const SizedBox(width: 8),
                    const Text(
                      'Forge',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: ForgeTheme.ink),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: Column(
                    children: [
                      const SizedBox(height: 24),
                      const ForgeMark(size: 120),
                      const SizedBox(height: 28),
                      // FORGE v0.2 P5対応: 音声入力を実装していないため、
                      // 「話すだけで」というコピーとマイクアイコンを削除し、
                      // 実態(テキスト入力)に一致させた。
                      Text(
                        'アイデアを入力するだけで、\nあなただけのアプリに。',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        '作りたいものを自由に入力してください。\nForgeが使えるアプリに仕上げます。',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.bodyMedium,
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
                              style: const TextStyle(fontSize: 16),
                              textInputAction: TextInputAction.done,
                              decoration: const InputDecoration(
                                hintText: 'どんなアプリを作りますか？',
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          _SendButton(enabled: canSubmit, onPressed: _onSubmit),
                        ],
                      ),
                      const SizedBox(height: 18),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.lock_outline_rounded, size: 14, color: ForgeTheme.inkSoft),
                          const SizedBox(width: 6),
                          Text('会話内容は安全に保護されます', style: Theme.of(context).textTheme.bodyMedium),
                        ],
                      ),
                      const SizedBox(height: 22),
                      Text('例を見てみたいときは', style: Theme.of(context).textTheme.bodyMedium),
                      const SizedBox(height: 10),
                      OutlinedButton.icon(
                        onPressed: _onShowExamples,
                        icon: const Icon(Icons.lightbulb_outline_rounded, size: 18, color: ForgeTheme.accent),
                        label: const Text('例を見る'),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: ForgeTheme.ink,
                          side: const BorderSide(color: Color(0xFFE8E4DC)),
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
                              Text('最近のアプリ', style: Theme.of(context).textTheme.bodyMedium),
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
          backgroundColor: ForgeTheme.surface,
          selectedItemColor: ForgeTheme.accent,
          unselectedItemColor: ForgeTheme.inkSoft,
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

class _RecentAppCard extends StatelessWidget {
  final SavedForgeApp app;
  final VoidCallback onTap;
  const _RecentAppCard({required this.app, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: ForgeTheme.surface,
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
                decoration: BoxDecoration(color: ForgeTheme.accentSoft, borderRadius: BorderRadius.circular(10)),
                child: const Icon(Icons.auto_awesome_rounded, color: ForgeTheme.accent, size: 18),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  app.title,
                  style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: ForgeTheme.ink),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const Icon(Icons.chevron_right_rounded, color: ForgeTheme.inkSoft, size: 20),
            ],
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
      child: Material(
        color: enabled ? ForgeTheme.accent : const Color(0xFFEDEAE3),
        shape: const CircleBorder(),
        child: InkWell(
          customBorder: const CircleBorder(),
          onTap: enabled ? onPressed : null,
          child: SizedBox(
            width: 52,
            height: 52,
            child: Icon(
              Icons.arrow_upward_rounded,
              color: enabled ? ForgeTheme.ink : ForgeTheme.inkSoft,
            ),
          ),
        ),
      ),
    );
  }
}
