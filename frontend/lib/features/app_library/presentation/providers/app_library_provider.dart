import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../data/repositories/shared_preferences_app_library_repository.dart';
import '../../domain/entities/generation_history_entry.dart';
import '../../domain/entities/saved_forge_app.dart';
import '../../domain/repositories/app_library_repository.dart';

/// `main()`で`SharedPreferences.getInstance()`の結果を`overrideWithValue`
/// することを前提にした Provider。既定値(オーバーライドされない場合)は
/// 例外を投げる(「初期化を忘れた」ことに気づけるようにするため、
/// 静かにNullを返す等のごまかしはしない)。
final sharedPreferencesProvider = Provider<SharedPreferences>((ref) {
  throw UnimplementedError(
    'sharedPreferencesProvider is not overridden. '
    'main()で SharedPreferences.getInstance() の結果を overrideWithValue してください。',
  );
});

final appLibraryRepositoryProvider = Provider<AppLibraryRepository>((ref) {
  return SharedPreferencesAppLibraryRepository(ref.watch(sharedPreferencesProvider));
});

/// マイアプリ一覧。保存・削除の後は`ref.invalidate(savedAppsProvider)`で
/// 再読み込みする(単純なFutureProviderのため、明示的な再読み込みが必要)。
final savedAppsProvider = FutureProvider<List<SavedForgeApp>>((ref) {
  return ref.watch(appLibraryRepositoryProvider).listSavedApps();
});

final generationHistoryProvider = FutureProvider<List<GenerationHistoryEntry>>((ref) {
  return ref.watch(appLibraryRepositoryProvider).listHistory();
});
