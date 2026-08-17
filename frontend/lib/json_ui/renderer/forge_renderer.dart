import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter/material.dart';

import '../../core/utils/forge_logger.dart';
import '../schema/forge_document.dart';
import '../widget_registry/widget_registry.dart';
import 'forge_runtime_state.dart';
import 'design_language.dart';

/// Rendererの入口。Backendから受け取った生JSON(`Map<String, dynamic>`)を渡すと、
/// パース→初期画面の描画までを行う。パースに失敗しても画面全体をクラッシュさせず、
/// 安全なエラー画面へ倒す(development: 理由を表示 / production: 静かな表示。方針12章)。
class ForgeDocumentView extends StatelessWidget {
  final Map<String, dynamic> rawJson;

  /// FORGE-AI-QUALITY-001(2026-08-11)新設(ローカル永続化対応)。
  /// 画面ID→前回保存された実行時State(JSON形式)。呼び出し元
  /// (`GeneratedAppHostShell`)がローカルストレージから読み込んで渡す。
  /// このView自体はストレージの存在を一切知らない(Runtime非依存の
  /// 既存方針を保つ、`forge_runtime_state.dart`冒頭のコメント参照)。
  final Map<String, Map<String, dynamic>>? initialRuntimeState;

  /// FORGE-AI-QUALITY-001(2026-08-11)新設。いずれかの画面のStateが
  /// 変化するたびに呼ばれる(画面ID, 変化後のState全体のJSON)。
  /// 呼び出し元がこれを実際に保存するかどうかを決める。
  final void Function(String screenId, Map<String, dynamic> stateJson)? onScreenStateChanged;

  const ForgeDocumentView({
    super.key,
    required this.rawJson,
    this.initialRuntimeState,
    this.onScreenStateChanged,
  });

  @override
  Widget build(BuildContext context) {
    final ForgeDocument document;
    try {
      document = ForgeDocument.fromJson(rawJson);
    } catch (e) {
      return _ForgeRenderErrorScreen(reason: 'ドキュメントを解釈できませんでした: $e');
    }

    final initial = document.screenById(document.initialScreenId);
    if (initial == null) {
      return const _ForgeRenderErrorScreen(reason: 'initial_screen_id に一致する画面がありません。');
    }

    final screenView = ForgeScreenView(
      document: document,
      screen: initial,
      initialRuntimeState: initialRuntimeState,
      onScreenStateChanged: onScreenStateChanged,
    );

    // FORGE v1.0新規(Product Quality Sprint1)。design_tokensが
    // 存在する場合のみ、ローカルな`Theme`で上書きする。ネイティブの
    // `ForgeTheme`(ホーム画面・生成フロー等)は一切変更しない
    // (`ForgeTheme`はアプリ全体で共有されているため、ここで
    // `ThemeData`を直接書き換えるのではなく、`Theme`Widgetで
    // このサブツリーだけに局所的に適用する、という設計)。
    final tokens = document.designTokens;
    if (tokens == null) {
      return screenView;
    }
    final baseTheme = Theme.of(context);
    return Theme(
      data: _applyDesignTokens(baseTheme, tokens),
      child: screenView,
    );
  }

  /// `tokens`から、既存の`baseTheme`(通常はネイティブの`ForgeTheme.
  /// theme`)を上書きした`ThemeData`を組み立てる。**未指定の色・
  /// 角丸は`baseTheme`の値をそのまま使う**(全て置き換えるのではなく、
  /// 部分的な上書き、Legacy文書に近い体験を保つための安全策)。
  ///
  /// **Sprint1 Patch2で修正した実バグ**: 以前は`baseTheme.colorScheme.
  /// copyWith(primary: primary, ...)`のように、`primary`等の個別
  /// フィールドだけを上書きしていた。Material3の`ColorScheme`は、
  /// `primaryContainer`・`onPrimary`・`surfaceTint`等、`primary`から
  /// 派生する多数のロールを持つが、`copyWith`は指定したフィールド
  /// **以外**を一切再計算しない。このため、`primary`は新しい色に
  /// 変わるのに、`primaryContainer`(例: 選択中Cardの背景色に使用、
  /// `widget_registry_v1_3.dart`参照)は元の(design_tokens導入前の)
  /// 色のままになる、という不整合があった。今回、design_tokensの
  /// primaryを`seedColor`として`ColorScheme.fromSeed()`で
  /// ColorScheme全体を再構築するよう修正し、派生ロールも含めて一貫して
  /// design_tokensの色調へ揃うようにした。
  static ThemeData _applyDesignTokens(ThemeData baseTheme, ForgeDesignTokens tokens) {
    final primary = tokens.colorOr('primary', baseTheme.colorScheme.primary);
    final mediumRadius = tokens.radiusOr('medium', 20);

    // `ColorScheme.fromSeed()`は、`primaryContainer`等の派生ロールを
    // 得るために使うが、**`.primary`自体はdesign_tokensで指定された
    // 値そのものに固定する**(Material3のトーン計算により、seedColor
    // と`colorScheme.primary`が厳密には一致しない場合があるため。
    // 「design_tokensで指定した色がそのままprimaryとして使われる」
    // という利用者から見た直感的な期待を優先し、`primaryContainer`
    // 等の"あくまで調和させるための派生色"とは区別する)。
    var colorScheme = ColorScheme.fromSeed(seedColor: primary, brightness: baseTheme.brightness)
        .copyWith(primary: primary);
    if (tokens.colorScheme.containsKey('secondary')) {
      colorScheme = colorScheme.copyWith(secondary: tokens.colorScheme['secondary']);
    }
    if (tokens.colorScheme.containsKey('error')) {
      colorScheme = colorScheme.copyWith(error: tokens.colorScheme['error']);
    }

    return baseTheme.copyWith(
      colorScheme: colorScheme,
      elevatedButtonTheme: ElevatedButtonThemeData(
        // 既存`ForgeTheme.theme`と同じ`ElevatedButton.styleFrom()`パターンを
        // 踏襲する(このプロジェクトで実績のある書き方を優先し、未使用の
        // Flutter APIを新たに持ち込むリスクを避けるため)。
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: colorScheme.onPrimary,
          minimumSize: const Size(0, 56),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(mediumRadius)),
          elevation: 0,
        ),
      ),
      inputDecorationTheme: baseTheme.inputDecorationTheme.copyWith(
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(mediumRadius)),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(mediumRadius)),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(mediumRadius),
          borderSide: BorderSide(color: primary, width: 1.5),
        ),
      ),
      cardTheme: baseTheme.cardTheme.copyWith(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(tokens.radiusOr('large', 16))),
      ),
    );
  }
}

/// 1画面分の描画。Widgetツリーの再帰構築・Action処理・画面遷移をここで担う。
class ForgeScreenView extends StatefulWidget {
  final ForgeDocument document;
  final ForgeScreen screen;

  /// FORGE-MILESTONE-003 Task 6: 現在何画面目かを表す(rootは0)。
  /// 同一画面への無限遷移(または実質的に無限に等しい深いネスト)を防ぐために使う。
  final int navigationDepth;

  /// FORGE-AI-QUALITY-001(2026-08-11)新設(ローカル永続化対応)。
  /// `ForgeDocumentView`のdocstring参照。画面遷移(`Navigator.push`)を
  /// またいでも同じMapをそのまま引き継ぐ(多画面の各Screenがそれぞれ
  /// 自分のIDで参照する)。
  final Map<String, Map<String, dynamic>>? initialRuntimeState;
  final void Function(String screenId, Map<String, dynamic> stateJson)? onScreenStateChanged;

  const ForgeScreenView({
    super.key,
    required this.document,
    required this.screen,
    this.navigationDepth = 0,
    this.initialRuntimeState,
    this.onScreenStateChanged,
  });

  @override
  State<ForgeScreenView> createState() => _ForgeScreenViewState();
}

class _ForgeScreenViewState extends State<ForgeScreenView> {
  // Validatorはサーバー側で既に再帰深度をチェック済みだが(shared/schemas/ui_schema.v1.json
  // 準拠, MAX_NESTING_DEPTH=12)、Runtime側でも独立して同じ上限を多重防御として持つ。
  static const int _maxClientSideDepth = 12;

  // FORGE-MILESTONE-003 Task 6: 文書内のscreen数の上限(MAX_SCREENS、
  // shared/schemas/ui_schema.v1.2.json準拠)と同じ値を、ナビゲーション段数の
  // 上限としても使う。これより深く画面遷移が続く場合、ループが疑われる。
  static const int _maxNavigationDepth = 20;

  late final ForgeRuntimeState _state;
  final ForgeWidgetRegistry _registry = buildDefaultForgeRegistry();

  @override
  void initState() {
    super.initState();
    // FORGE-AI-QUALITY-001(2026-08-11)新設(ローカル永続化対応): 文書が
    // 宣言する初期Stateへ、前回保存された実行時Stateを上書きマージする。
    // 保存が無い(初回起動・保存に対応していない呼び出し元)場合は
    // `mergePersistedState`が`widget.screen.state`をそのまま返すため、
    // 既存の挙動を一切変えない。
    final initialState = mergePersistedState(
      widget.screen.state,
      widget.initialRuntimeState?[widget.screen.id],
    );
    _state = ForgeRuntimeState(
      initialState,
      onNavigationAction: _handleNavigationAction,
      screenRoot: widget.screen.body,
      onDiagnostic: (category, message) => ForgeLogger.error('ForgeRuntimeState', '[$category] $message'),
      // FORGE v0.9新規(Typed Record Runtime Phase1)。文書トップレベルの
      // record_schemasを、この画面のRuntimeへそのまま引き継ぐ(型情報を
      // 保持するだけであり、Widget構築・Action実行には一切影響しない)。
      recordSchemas: widget.document.recordSchemas,
      // FORGE v1.0新規(Product Quality Sprint1)。文書トップレベルの
      // design_tokensを、この画面のRuntimeへそのまま引き継ぐ(Widget
      // 側が色・角丸を参照するために使う。CRUD挙動には一切影響しない)。
      designTokens: widget.document.designTokens,
    );
    if (widget.onScreenStateChanged != null) {
      _state.addListener(_persistState);
    }
  }

  /// FORGE-AI-QUALITY-001(2026-08-11)新設。`_state`が変化するたび
  /// (チェックリストの追加・チェック、Recordの追加・更新・削除、
  /// フォーム送信等)呼ばれる。text_fieldの1文字ごとの入力は
  /// `notify: false`で書き込まれるため対象外(`widget_registry.dart`
  /// の`_BoundTextField.onChanged`参照)——未確定の下書き入力まで
  /// 毎回保存されることを避ける、既存の設計をそのまま活かしている。
  void _persistState() {
    widget.onScreenStateChanged?.call(widget.screen.id, _state.exportStateJson());
  }

  @override
  void dispose() {
    if (widget.onScreenStateChanged != null) {
      _state.removeListener(_persistState);
    }
    _state.dispose();
    super.dispose();
  }

  void _handleNavigationAction(ForgeAction action) {
    if (action is NavigateAction) {
      final target = widget.document.screenById(action.targetScreenId);
      if (target == null) {
        // Validatorが本来防ぐはずのケース。多重防御としてクラッシュせずSnackBarで知らせる。
        ForgeLogger.error('Navigation', '遷移先の画面が見つかりません: ${action.targetScreenId}');
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('遷移先の画面が見つかりません: ${action.targetScreenId}')),
        );
        return;
      }
      if (widget.navigationDepth >= _maxNavigationDepth) {
        // 無限遷移(または実質的にそれに近い、異常に深いネスト)防止。
        ForgeLogger.error('Navigation',
            '画面遷移の段数が上限($_maxNavigationDepth)を超えたため、これ以上遷移しません。'
            '循環的なnavigateが無いか、生成されたJSONを確認してください。');
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('これ以上進めません(画面遷移が深くなりすぎました)。')),
        );
        return;
      }
      // FORGE-MERGE-005 Task 1: 戻り値は使用していないため <void> を明示する
      // (Task 2で確認済み: push()の結果はawait/代入されていない)。
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => ForgeScreenView(
            document: widget.document,
            screen: target,
            navigationDepth: widget.navigationDepth + 1,
            initialRuntimeState: widget.initialRuntimeState,
            onScreenStateChanged: widget.onScreenStateChanged,
          ),
        ),
      );
      return;
    }
    if (action is GoBackAction) {
      Navigator.of(context).maybePop();
      return;
    }
    // ForgeRuntimeState.dispatch() は navigate/go_back の時だけこのコールバックを呼ぶため、
    // ここに他のActionが来ることは無い想定だが、念のため何もせず抜ける(多重防御)。
  }

  Widget _build(ForgeWidgetNode node, int depth) {
    if (depth > _maxClientSideDepth) {
      return const ForgeFallbackWidget(reason: '再帰深度の上限を超えました(クライアント側ガード)');
    }
    final built =
        buildForgeWidget(context, node, _state, _registry, (child) => _build(child, depth + 1));
    // Design Language（v1.10）。**ここ1箇所だけ**で role を被せる。
    // 19種の builder それぞれへ配ると、Widget を1つ足すたびに
    // 付け忘れる（`CLAUDE.md` §3「忘れずに呼ばれる保証が無いものは
    // 忘れられる」）。
    return applyForgeRole(context, widget.screen.styleRoles[node.id], built);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.screen.title)),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: _build(widget.screen.body, 0),
        ),
      ),
    );
  }
}

class _ForgeRenderErrorScreen extends StatelessWidget {
  final String reason;
  const _ForgeRenderErrorScreen({required this.reason});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('表示できませんでした')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline_rounded, size: 40, color: Colors.redAccent),
              const SizedBox(height: 12),
              const Text('うまく作れませんでした。もう一度試してください。', textAlign: TextAlign.center),
              if (kDebugMode) ...[
                const SizedBox(height: 12),
                Text(reason, style: const TextStyle(fontSize: 11, color: Colors.grey), textAlign: TextAlign.center),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
