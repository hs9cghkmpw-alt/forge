import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/forge_theme.dart';
import '../../../../shared_widgets/generated_app_host_shell.dart';
import '../../../../shared_widgets/responsive_app_shell.dart';
import '../../domain/entities/generation_history_entry.dart';
import '../../domain/entities/saved_forge_app.dart';
import '../providers/app_library_provider.dart';

/// FORGE v0.2 P5対応(履歴)。
///
/// `onReusePrompt`はホーム画面から渡され、履歴のPromptをホームの入力欄へ
/// 反映して画面を閉じるためのコールバック(「HistoryからPrompt再利用して
/// ホームへ戻せる」の実装)。
class HistoryScreen extends ConsumerWidget {
  final void Function(String prompt)? onReusePrompt;

  const HistoryScreen({super.key, this.onReusePrompt});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final history = ref.watch(generationHistoryProvider);

    return ResponsiveAppShell(
      child: Scaffold(
        appBar: AppBar(title: const Text('履歴')),
        body: history.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => const Center(child: Text('読み込みに失敗しました。')),
          data: (entries) {
            if (entries.isEmpty) return const _EmptyHistory();
            return ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: entries.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (context, index) =>
                  _HistoryCard(entry: entries[index], onReusePrompt: onReusePrompt),
            );
          },
        ),
      ),
    );
  }
}

class _EmptyHistory extends StatelessWidget {
  const _EmptyHistory();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.history_rounded, size: 40, color: ForgeTheme.inkSoft),
            const SizedBox(height: 16),
            Text('まだ生成履歴がありません', style: Theme.of(context).textTheme.bodyLarge),
          ],
        ),
      ),
    );
  }
}

class _HistoryCard extends ConsumerWidget {
  final GenerationHistoryEntry entry;
  final void Function(String prompt)? onReusePrompt;

  const _HistoryCard({required this.entry, this.onReusePrompt});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Material(
      color: ForgeTheme.surface,
      borderRadius: BorderRadius.circular(20),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _StatusChip(status: entry.status),
                const Spacer(),
                Text(_formatDate(entry.createdAt), style: const TextStyle(fontSize: 11, color: ForgeTheme.inkSoft)),
              ],
            ),
            const SizedBox(height: 8),
            Text(entry.prompt, style: const TextStyle(fontSize: 14, color: ForgeTheme.ink)),
            if (entry.status == GenerationHistoryStatus.failure && entry.errorCategory != null) ...[
              const SizedBox(height: 4),
              Text('理由: ${entry.errorCategory}', style: const TextStyle(fontSize: 12, color: ForgeTheme.inkSoft)),
            ],
            const SizedBox(height: 12),
            Row(
              children: [
                if (entry.status == GenerationHistoryStatus.success && entry.appId != null)
                  TextButton(onPressed: () => _openApp(context, ref), child: const Text('開く')),
                if (onReusePrompt != null)
                  TextButton(
                    onPressed: () => onReusePrompt!(entry.prompt),
                    child: const Text('この内容でもう一度'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _openApp(BuildContext context, WidgetRef ref) async {
    final apps = await ref.read(savedAppsProvider.future);
    SavedForgeApp? app;
    for (final a in apps) {
      if (a.id == entry.appId) {
        app = a;
        break;
      }
    }
    if (app == null) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('このアプリは既に削除されています。')),
        );
      }
      return;
    }
    // FORGE v0.2 Flutter GO対応: `flutter analyze`が実際に検出したnull
    // safetyエラーの修正。上のnull checkだけでは、`app`が非finalの
    // ローカル変数のままクロージャ(下の`builder: (_) => ...`)へ
    // 捕捉されるため、Dartの型プロミオションがクロージャ境界を越えて
    // 効かない(`app`は再代入されうる変数として扱われ、クロージャ内では
    // 依然として`SavedForgeApp?`のまま扱われる)。null-checked済みの
    // 値を`final`のローカル変数へ入れ直すことで、以降は安全に
    // 非null型として扱えるようにする。
    final resolvedApp = app;
    if (!context.mounted) return;
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => Scaffold(
          body: SafeArea(
            child: GeneratedAppHostShell(
              forgeDocument: resolvedApp.forgeDocument,
              onBack: () => Navigator.of(context).pop(),
            ),
          ),
        ),
      ),
    );
  }

  String _formatDate(DateTime dt) {
    final local = dt.toLocal();
    return '${local.year}/${local.month.toString().padLeft(2, '0')}/${local.day.toString().padLeft(2, '0')} '
        '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
  }
}

class _StatusChip extends StatelessWidget {
  final GenerationHistoryStatus status;
  const _StatusChip({required this.status});

  @override
  Widget build(BuildContext context) {
    final (label, color) = switch (status) {
      GenerationHistoryStatus.success => ('成功', Colors.green),
      GenerationHistoryStatus.needsConfirmation => ('確認中断', Colors.orange),
      GenerationHistoryStatus.failure => ('失敗', Colors.redAccent),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(999)),
      child: Text(label, style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w600)),
    );
  }
}
