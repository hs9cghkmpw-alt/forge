import 'package:flutter/material.dart';

import '../../../../core/theme/forge_theme.dart';

/// 「例を見る」をタップすると開くBottom Sheet。
///
/// CEO提示のUIモックアップ(2026-07-16)に基づく。既存の`_InspirationCard`
/// (ホーム画面へ常時表示されるチップ群)を置き換え、モーダルシートの中に
/// アイコン付きのカードとして表示する。タップした際の挙動(入力欄へ
/// 文章を入れるだけで、送信はしない)は変更していない
/// (`home_screen.dart`の`_onCardTap`と同じ方針)。
class ExampleItem {
  final IconData icon;
  final Color iconColor;
  final Color iconBackground;
  final String title;
  final String description;
  final String phrase;

  const ExampleItem({
    required this.icon,
    required this.iconColor,
    required this.iconBackground,
    required this.title,
    required this.description,
    required this.phrase,
  });
}

const List<ExampleItem> forgeExampleItems = [
  ExampleItem(
    icon: Icons.bar_chart_rounded,
    iconColor: Color(0xFF4C6FE0),
    iconBackground: Color(0xFFE7ECFC),
    title: '家計簿アプリを作りたい',
    description: '収入や支出を記録して、月ごとの収支をグラフで見たい',
    phrase: '家計簿アプリを作りたい',
  ),
  ExampleItem(
    icon: Icons.check_box_rounded,
    iconColor: Color(0xFF2FAE6B),
    iconBackground: Color(0xFFE1F5EA),
    title: 'ToDoリストを作りたい',
    description: 'やることを登録して、完了したらチェックしたい',
    phrase: 'ToDoリストを作りたい',
  ),
  ExampleItem(
    icon: Icons.menu_book_rounded,
    iconColor: Color(0xFF4C6FE0),
    iconBackground: Color(0xFFE7ECFC),
    title: '日記アプリを作りたい',
    description: '毎日の出来事や気持ちを記録して、振り返れるようにしたい',
    phrase: '日記アプリを作りたい',
  ),
  ExampleItem(
    icon: Icons.phishing_rounded,
    iconColor: Color(0xFF2AA7A0),
    iconBackground: Color(0xFFDFF3F1),
    title: '釣果記録アプリを作りたい',
    description: '釣った魚の記録を残して、場所やサイズを管理したい',
    phrase: '釣った魚の記録を残せて、場所やサイズも管理できるアプリを作りたい',
  ),
  ExampleItem(
    icon: Icons.favorite_rounded,
    iconColor: Color(0xFFE0679A),
    iconBackground: Color(0xFFFBE5EE),
    title: '子どもの成長記録を作りたい',
    description: '身長や体重、イベントなどを記録して、成長を可視化したい',
    phrase: '子どもの身長や体重、イベントを記録して成長を可視化できるアプリを作りたい',
  ),
];

/// [ExamplePickerSheet.show]でモーダル表示する。選ばれた例文
/// ([ExampleItem.phrase])を戻り値として返す(何も選ばずに閉じた場合はnull)。
class ExamplePickerSheet extends StatelessWidget {
  const ExamplePickerSheet({super.key});

  static Future<String?> show(BuildContext context) {
    return showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      backgroundColor: ForgeTheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      builder: (_) => const ExamplePickerSheet(),
    );
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      initialChildSize: 0.62,
      minChildSize: 0.4,
      maxChildSize: 0.9,
      expand: false,
      builder: (context, scrollController) {
        return Column(
          children: [
            const SizedBox(height: 10),
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: const Color(0xFFE2DFD8),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 18, 12, 4),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('例を見てみる', style: Theme.of(context).textTheme.bodyLarge?.copyWith(fontWeight: FontWeight.w600)),
                        const SizedBox(height: 2),
                        Text('気になる例をタップすると、入力欄に入ります', style: Theme.of(context).textTheme.bodyMedium),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close_rounded),
                    color: ForgeTheme.inkSoft,
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                ],
              ),
            ),
            Expanded(
              child: ListView.separated(
                controller: scrollController,
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                itemCount: forgeExampleItems.length,
                separatorBuilder: (_, __) => const SizedBox(height: 4),
                itemBuilder: (context, index) {
                  final item = forgeExampleItems[index];
                  return _ExampleTile(
                    item: item,
                    onTap: () => Navigator.of(context).pop(item.phrase),
                  );
                },
              ),
            ),
          ],
        );
      },
    );
  }
}

class _ExampleTile extends StatelessWidget {
  final ExampleItem item;
  final VoidCallback onTap;

  const _ExampleTile({required this.item, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(18),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: item.iconBackground,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(item.icon, color: item.iconColor, size: 22),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.title,
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: ForgeTheme.ink),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    item.description,
                    style: const TextStyle(fontSize: 13, color: ForgeTheme.inkSoft, height: 1.3),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 4),
            const Icon(Icons.chevron_right_rounded, color: ForgeTheme.inkSoft),
          ],
        ),
      ),
    );
  }
}
