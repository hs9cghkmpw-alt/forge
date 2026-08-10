import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'core/config/app_config.dart';
import 'core/theme/forge_theme.dart';
import 'features/app_generation/presentation/screens/home_screen.dart';
import 'features/app_library/presentation/providers/app_library_provider.dart';

/// Forgeのエントリポイント。
/// FORGE-MERGE-001 縦の一本(Home→Confirm→Mock Generator→Validator→Renderer)により、
/// 起動確認用のプレースホルダー画面から HomeScreen へ差し替えた。
///
/// FORGE v0.2 P5対応: マイアプリ・履歴の永続化(`shared_preferences`)の
/// ため、`main()`を非同期化し、起動時に`SharedPreferences.getInstance()`
/// を1回だけ実行してProviderへ注入する。
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();
  runApp(
    ProviderScope(
      overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      child: const ForgeApp(),
    ),
  );
}

class ForgeApp extends StatelessWidget {
  const ForgeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Forge',
      debugShowCheckedModeBanner: false,
      theme: ForgeTheme.theme,
      home: const HomeScreen(),
      // FORGE v0.2 P5対応: 斜めのMOCK/LIVE Bannerはエンドユーザー体験を
      // 妨げるため、既定では非表示にした(以前はRUNTIME-001 Task 8で
      // 常時表示していた)。開発中だけ`--dart-define=FORGE_SHOW_DEV_BADGE=true`
      // を付けて起動すると、右上に小さな開発用Badgeが表示される。
      builder: (context, child) {
        if (!_showDevBadge) return child ?? const SizedBox.shrink();
        final mockMode = AppConfig.current.mockMode;
        return Banner(
          message: mockMode ? 'MOCK' : 'LIVE',
          location: BannerLocation.topEnd,
          color: mockMode ? Colors.deepOrange : Colors.green,
          child: child ?? const SizedBox.shrink(),
        );
      },
    );
  }
}

/// 既定は非表示(FORGE v0.2 P5対応)。開発時のみ
/// `flutter run -d chrome --dart-define=FORGE_SHOW_DEV_BADGE=true` で有効化する。
const bool _showDevBadge = bool.fromEnvironment('FORGE_SHOW_DEV_BADGE', defaultValue: false);
