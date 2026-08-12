import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/forge_theme.dart';
import '../../../../shared_widgets/generated_app_host_shell.dart';
import '../../../../shared_widgets/responsive_app_shell.dart';
import '../../domain/entities/saved_forge_app.dart';
import '../providers/app_library_provider.dart';

/// FORGE v0.2 P5対応(マイアプリ)。
class MyAppsScreen extends ConsumerWidget {
  const MyAppsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final savedApps = ref.watch(savedAppsProvider);

    return ResponsiveAppShell(
      child: Scaffold(
        appBar: AppBar(title: const Text('マイアプリ')),
        body: savedApps.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => const _LibraryErrorView(message: '読み込みに失敗しました。'),
          data: (apps) {
            if (apps.isEmpty) return const _EmptyMyApps();
            return ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: apps.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (context, index) => _SavedAppCard(app: apps[index]),
            );
          },
        ),
      ),
    );
  }
}

class _EmptyMyApps extends StatelessWidget {
  const _EmptyMyApps();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.grid_view_rounded, size: 40, color: ForgeTheme.inkSoft),
            const SizedBox(height: 16),
            Text('まだ保存されたアプリがありません', style: Theme.of(context).textTheme.bodyLarge),
            const SizedBox(height: 8),
            Text(
              'アプリを作って「保存してあとで見る」を選ぶと、ここに表示されます。',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }
}

class _LibraryErrorView extends StatelessWidget {
  final String message;
  const _LibraryErrorView({required this.message});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline_rounded, size: 32, color: Colors.redAccent),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}

class _SavedAppCard extends ConsumerWidget {
  final SavedForgeApp app;
  const _SavedAppCard({required this.app});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Material(
      color: ForgeTheme.surface,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: () => _openApp(context, ref),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      app.title,
                      style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: ForgeTheme.ink),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      app.originalPrompt,
                      style: const TextStyle(fontSize: 12, color: ForgeTheme.inkSoft),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 6),
                    Text(
                      _formatDate(app.updatedAt),
                      style: const TextStyle(fontSize: 11, color: ForgeTheme.inkSoft),
                    ),
                  ],
                ),
              ),
              IconButton(
                icon: const Icon(Icons.delete_outline_rounded, color: ForgeTheme.inkSoft),
                tooltip: '削除',
                onPressed: () => _confirmDelete(context, ref),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // FORGE-AI-QUALITY-001(2026-08-11)対応(ローカル永続化)。以前は
  // アプリを開くたびに文書の初期値(空のチェックリスト等)から始まり、
  // 前回追加したデータが常に消えていた。ここで保存済みの実行時State
  // を読み込んで渡し、State変化のたびに保存し直す。
  Future<void> _openApp(BuildContext context, WidgetRef ref) async {
    final repository = ref.read(appLibraryRepositoryProvider);
    final runtimeState = await repository.loadRuntimeState(app.id);
    if (!context.mounted) return;
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => Scaffold(
          body: SafeArea(
            child: GeneratedAppHostShell(
              forgeDocument: app.forgeDocument,
              onBack: () => Navigator.of(context).pop(),
              initialRuntimeState: runtimeState,
              // FORGE-PRODUCT-VISION-002(2026-08-11)対応: マイアプリから
              // 開いた場合も「ここを変える」で会話に戻れる(design doc C章)。
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

  Future<void> _confirmDelete(BuildContext context, WidgetRef ref) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('削除しますか？'),
        content: Text('「${app.title}」を削除します。この操作は元に戻せません。'),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('キャンセル')),
          TextButton(onPressed: () => Navigator.of(context).pop(true), child: const Text('削除')),
        ],
      ),
    );
    if (confirmed == true) {
      final repository = ref.read(appLibraryRepositoryProvider);
      await repository.deleteApp(app.id);
      // FORGE-AI-QUALITY-001(2026-08-11)対応: アプリ定義を消しても
      // ローカル保存された実行時Stateだけが残り続けることを防ぐ。
      await repository.deleteRuntimeState(app.id);
      ref.invalidate(savedAppsProvider);
    }
  }

  String _formatDate(DateTime dt) {
    final local = dt.toLocal();
    return '${local.year}/${local.month.toString().padLeft(2, '0')}/${local.day.toString().padLeft(2, '0')}';
  }
}
