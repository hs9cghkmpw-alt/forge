/// Forge Language v1 の Dart モデル。
///
/// `shared/schemas/ui_schema.v1.json` と対応する(手動同期。理由はDECISIONS.md参照)。
/// pubspec.yaml には freezed / json_serializable が入っているが、本ファイルは
/// あえてそれらを使わず手書きにしている。理由:
///   - build_runner のコード生成ステップ無しで、このまま `flutter run` できる
///     ようにするため(縦の一本を最短距離で通す、FORGE-MERGE-001 8章の狙いに合わせた)。
///   - Claudeのサンドボックスに Dart SDK/build_runner が無く、生成コードの
///     動作確認ができないため、生成に依存しない形の方が誠実である。
/// 将来、Widget種別が増えて手書きの負担が増えたら freezed へ移行することを
/// DECISIONS.md に「保留」として明記している。
library;

// FORGE v1.0新規(Product Quality Sprint1)。`ForgeDesignTokens`が
// `Color`(色)を保持するために必要。他の型(`ForgeRecordSchema`等)は
// 引き続きFlutter/dart:ui非依存の純粋なDartデータ構造のままである
// (design_tokens自体がFlutter Runtime固有の描画情報であるため、この
// 1クラスに限りdart:uiへの依存を許容する、という意図的な判断)。
import 'dart:ui' show Color;

/// 未知の構造・型不一致など、サーバー側Validatorを通過したはずのJSONが
/// クライアント側で解釈できなかった場合に投げる。Renderer側でこれを捕まえ、
/// 安全なFallback表示に倒す(素通しでクラッシュさせない)。
class ForgeParseException implements Exception {
  final String path;
  final String message;
  ForgeParseException(this.path, this.message);

  @override
  String toString() => 'ForgeParseException at $path: $message';
}

/// v1.2新規(FORGE-MILESTONE-003)。text_field/checkboxへ付与できる検証ルール1件。
class ForgeValidationRule {
  final String type; // required | min_length | max_length | min | max | pattern
  final dynamic value;
  final String message;
  const ForgeValidationRule({required this.type, required this.value, required this.message});

  factory ForgeValidationRule.fromJson(Map<String, dynamic> json, String path) {
    final type = json['type'];
    if (type is! String) {
      throw ForgeParseException('$path/type', 'validation rule type is required');
    }
    final message = json['message'];
    if (message is! String || message.isEmpty) {
      throw ForgeParseException('$path/message', 'validation rule message is required');
    }
    return ForgeValidationRule(type: type, value: json['value'], message: message);
  }
}

List<ForgeValidationRule>? _parseValidation(dynamic validationJson, String path) {
  if (validationJson == null) return null;
  if (validationJson is! Map<String, dynamic>) {
    throw ForgeParseException(path, 'validation must be an object');
  }
  final rulesJson = validationJson['rules'];
  if (rulesJson is! List) {
    throw ForgeParseException('$path/rules', 'validation.rules must be an array');
  }
  final rules = <ForgeValidationRule>[];
  for (var i = 0; i < rulesJson.length; i++) {
    final r = rulesJson[i];
    if (r is! Map<String, dynamic>) {
      throw ForgeParseException('$path/rules/$i', 'validation rule must be an object');
    }
    rules.add(ForgeValidationRule.fromJson(r, '$path/rules/$i'));
  }
  return rules;
}

class ForgeDocument {
  final String version;
  final String? appTitle;
  final String initialScreenId;
  final List<ForgeScreen> screens;

  /// FORGE v0.9新規(Typed Record Runtime Phase1)。Schema名 →
  /// [ForgeRecordSchema]。`record_list`型のStateとは独立した、
  /// 文書トップレベルの型定義(`schema_ref`で結び付けられる)。
  /// v1.4未満の文書、または`record_schemas`を持たない文書では空。
  final Map<String, ForgeRecordSchema> recordSchemas;

  /// FORGE v1.0新規(Product Quality Sprint1)。色・角丸・余白の
  /// トークン。v1.5未満の文書、または`design_tokens`を持たない文書
  /// では`null`(ネイティブの`ForgeTheme`をそのまま使う、Legacy
  /// fallback)。

  final ForgeDesignTokens? designTokens;

  ForgeDocument({
    required this.version,
    required this.appTitle,
    required this.initialScreenId,
    required this.screens,
    this.recordSchemas = const {},
    this.designTokens,
  });

  factory ForgeDocument.fromJson(Map<String, dynamic> json) {
    final screensJson = json['screens'];
    if (screensJson is! List || screensJson.isEmpty) {
      throw ForgeParseException('/screens', 'screens must be a non-empty array');
    }
    final screens = <ForgeScreen>[];
    for (var i = 0; i < screensJson.length; i++) {
      final s = screensJson[i];
      if (s is! Map<String, dynamic>) {
        throw ForgeParseException('/screens/$i', 'screen must be an object');
      }
      screens.add(ForgeScreen.fromJson(s, '/screens/$i'));
    }

    final initialScreenId = json['initial_screen_id'];
    if (initialScreenId is! String || initialScreenId.isEmpty) {
      throw ForgeParseException('/initial_screen_id', 'must be a non-empty string');
    }

    final app = json['app'];
    final appTitle = (app is Map<String, dynamic>) ? app['title'] as String? : null;

    final rawRecordSchemas = json['record_schemas'];
    final recordSchemas = <String, ForgeRecordSchema>{};
    if (rawRecordSchemas is Map<String, dynamic>) {
      for (final entry in rawRecordSchemas.entries) {
        final schemaJson = entry.value;
        if (schemaJson is! Map<String, dynamic>) {
          throw ForgeParseException('/record_schemas/${entry.key}', 'record_schema must be an object');
        }
        recordSchemas[entry.key] = ForgeRecordSchema.fromJson(schemaJson, '/record_schemas/${entry.key}');
      }
    }

    final rawDesignTokens = json['design_tokens'];
    final designTokens = (rawDesignTokens is Map<String, dynamic>)
        ? ForgeDesignTokens.fromJson(rawDesignTokens, '/design_tokens')
        : null;

    return ForgeDocument(
      version: json['version'] as String? ?? '',
      appTitle: appTitle,
      initialScreenId: initialScreenId,
      screens: screens,
      recordSchemas: recordSchemas,
      designTokens: designTokens,
    );
  }

  ForgeScreen? screenById(String id) {
    for (final s in screens) {
      if (s.id == id) return s;
    }
    return null;
  }

  /// 型取得(FORGE v0.9新規)。`schemaRef`に対応する[ForgeRecordSchema]を
  /// 返す。存在しない場合は`null`。
  ForgeRecordSchema? recordSchemaByRef(String schemaRef) => recordSchemas[schemaRef];
}

/// FORGE v1.0新規(Product Quality Sprint1)。文書トップレベルの
/// `design_tokens`(色・角丸・余白)。**このクラスが持つ情報は全て
/// Flutter Runtime固有の描画情報である**(IRには一切含まれない、
/// `forge_language_compiler.py`のモジュールdocstring・ADR-012参照)。
/// ネイティブの`ForgeTheme`とは完全に独立しており、`design_tokens`が
/// 無い文書ではこのクラス自体が生成されない(Legacy fallback、
/// `ForgeDocument.designTokens`が`null`のままネイティブテーマを使う)。
class ForgeDesignTokens {
  final Map<String, Color> colorScheme;
  final Map<String, double> cornerRadius;
  final Map<String, double> spacingScale;

  const ForgeDesignTokens({
    required this.colorScheme,
    required this.cornerRadius,
    required this.spacingScale,
  });

  factory ForgeDesignTokens.fromJson(Map<String, dynamic> json, String path) {
    final colorScheme = <String, Color>{};
    final rawColorScheme = json['color_scheme'];
    if (rawColorScheme is Map<String, dynamic>) {
      for (final entry in rawColorScheme.entries) {
        final hex = entry.value;
        if (hex is String) {
          final parsed = _parseHexColor(hex);
          if (parsed != null) colorScheme[entry.key] = parsed;
        }
      }
    }

    final cornerRadius = <String, double>{};
    final rawCornerRadius = json['corner_radius'];
    if (rawCornerRadius is Map<String, dynamic>) {
      for (final entry in rawCornerRadius.entries) {
        final value = entry.value;
        if (value is num) cornerRadius[entry.key] = value.toDouble();
      }
    }

    final spacingScale = <String, double>{};
    final rawSpacingScale = json['spacing_scale'];
    if (rawSpacingScale is Map<String, dynamic>) {
      for (final entry in rawSpacingScale.entries) {
        final value = entry.value;
        if (value is num) spacingScale[entry.key] = value.toDouble();
      }
    }

    return ForgeDesignTokens(colorScheme: colorScheme, cornerRadius: cornerRadius, spacingScale: spacingScale);
  }

  /// `#RRGGBB`形式の文字列をDartの[Color]へ変換する。不正な形式の場合は
  /// `null`(呼び出し側は当該色を無視し、既定のテーマ色を使う——安全側の
  /// フォールバック、Backend Validatorが既に書式を検査済みだが、
  /// Runtime側でも二重に安全策を取る)。
  static Color? _parseHexColor(String hex) {
    final match = RegExp(r'^#([0-9A-Fa-f]{6})$').firstMatch(hex);
    if (match == null) return null;
    return Color(int.parse('FF${match.group(1)}', radix: 16));
  }

  /// 指定した`role`の色を返す。無ければ`fallback`を返す。
  Color colorOr(String role, Color fallback) => colorScheme[role] ?? fallback;

  /// 指定した`size`のCorner Radiusを返す。無ければ`fallback`を返す。
  double radiusOr(String size, double fallback) => cornerRadius[size] ?? fallback;
}

/// FORGE v0.9新規(Typed Record Runtime Phase1)。`record_schema`1件
/// (`record_list`とは独立した、Recordの型定義)。
///
/// **設計上の注記(ADR-012と同じ思想)**: このクラスはFieldの型情報
/// (`name`/`type`/`label`/`required`/`options`)だけを保持する。
/// Widget種別・入力方式(text_field等)は一切含まない。「型システムを
/// 導入すること」が目的であり、UIをどう構築するかはこのクラスの
/// 責務ではない(指示書「特定Runtimeに依存する情報は含めない」)。
class ForgeRecordSchema {
  final List<ForgeRecordSchemaField> fields;
  const ForgeRecordSchema({required this.fields});

  factory ForgeRecordSchema.fromJson(Map<String, dynamic> json, String path) {
    final rawFields = json['fields'];
    if (rawFields is! List || rawFields.isEmpty) {
      throw ForgeParseException('$path/fields', 'record_schema.fields must be a non-empty array');
    }
    final fields = rawFields.asMap().entries.map((entry) {
      final f = entry.value;
      if (f is! Map<String, dynamic>) {
        throw ForgeParseException('$path/fields/${entry.key}', 'record_schema field must be an object');
      }
      return ForgeRecordSchemaField.fromJson(f, '$path/fields/${entry.key}');
    }).toList();
    return ForgeRecordSchema(fields: fields);
  }

  /// 型取得(FORGE v0.9新規)。Field名から[ForgeRecordSchemaField]を
  /// 引く。見つからない場合は`null`。
  ForgeRecordSchemaField? fieldByName(String name) {
    for (final f in fields) {
      if (f.name == name) return f;
    }
    return null;
  }
}

/// FORGE v0.9新規(Typed Record Runtime Phase1)。`record_schema`が持つ
/// Field 1つの型情報。
class ForgeRecordSchemaField {
  final String name;
  final ForgeRecordFieldType type;
  final String label;
  final bool required;

  /// `type == ForgeRecordFieldType.choice`の場合のみ意味を持つ。
  final List<String>? options;

  const ForgeRecordSchemaField({
    required this.name,
    required this.type,
    required this.label,
    required this.required,
    this.options,
  });

  factory ForgeRecordSchemaField.fromJson(Map<String, dynamic> json, String path) {
    final name = json['name'];
    if (name is! String || name.isEmpty) {
      throw ForgeParseException('$path/name', 'record_schema field name is required');
    }
    final typeRaw = json['type'];
    if (typeRaw is! String) {
      throw ForgeParseException('$path/type', 'record_schema field type is required');
    }
    final label = json['label'] as String?;
    if (label == null || label.isEmpty) {
      throw ForgeParseException('$path/label', 'record_schema field label is required');
    }
    final rawOptions = json['options'];
    return ForgeRecordSchemaField(
      name: name,
      type: ForgeRecordFieldType.fromJson(typeRaw),
      label: label,
      required: json['required'] as bool? ?? true,
      options: (rawOptions is List) ? rawOptions.cast<String>() : null,
    );
  }
}

/// FORGE v0.9新規(Typed Record Runtime Phase1)。record_schemaの
/// Fieldが取りうる型(指示書「Supported Types」)。
///
/// `unknown`は、将来Backend側がこのRuntimeより先に新しい型を追加した
/// 場合の後方互換用フォールバック(既存の「未知Widgetは安全にFallback」
/// という設計原則と同じ考え方を、型情報にも適用したもの)。
enum ForgeRecordFieldType {
  string,
  number,
  boolean,
  date,
  choice,
  unknown;

  static ForgeRecordFieldType fromJson(String raw) => switch (raw) {
        'string' => ForgeRecordFieldType.string,
        'number' => ForgeRecordFieldType.number,
        'boolean' => ForgeRecordFieldType.boolean,
        'date' => ForgeRecordFieldType.date,
        'choice' => ForgeRecordFieldType.choice,
        _ => ForgeRecordFieldType.unknown,
      };
}

class ForgeScreen {
  final String id;
  final String title;
  final Map<String, ForgeStateValue> state;
  final ForgeWidgetNode body;

  ForgeScreen({required this.id, required this.title, required this.state, required this.body});

  factory ForgeScreen.fromJson(Map<String, dynamic> json, String path) {
    final id = json['id'];
    if (id is! String || id.isEmpty) {
      throw ForgeParseException('$path/id', 'screen.id must be a non-empty string');
    }
    final stateJson = json['state'];
    final state = <String, ForgeStateValue>{};
    if (stateJson is Map<String, dynamic>) {
      stateJson.forEach((key, value) {
        if (value is Map<String, dynamic>) {
          state[key] = ForgeStateValue.fromJson(value, '$path/state/$key');
        }
      });
    }
    final bodyJson = json['body'];
    if (bodyJson is! Map<String, dynamic>) {
      throw ForgeParseException('$path/body', 'screen.body is required');
    }
    return ForgeScreen(
      id: id,
      title: json['title'] as String? ?? '',
      state: state,
      body: ForgeWidgetNode.fromJson(bodyJson, '$path/body'),
    );
  }
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

/// FORGE-AI-QUALITY-001(2026-08-11)新設(ローカル永続化対応)。
///
/// 文書が宣言する初期State(`declared`、通常は`ForgeScreen.state`)へ、
/// ローカル保存されていた実行時State(`persisted`。ユーザーが以前
/// 追加・変更したチェックリスト項目やRecord等)を上書きマージした、
/// 新しいMapを返す。
///
/// **設計方針(安全側に倒す)**: `persisted`にキーが存在しても、以下の
/// いずれかに該当する場合は、そのキーだけ`declared`側の値(=AIが宣言した
/// 初期値)をそのまま使う(黙って無視する。個別の復元失敗で画面全体が
/// クラッシュ・変な状態になることを防ぐ、多重防御)。
///
/// * `declared`側にそのキーが無い(AIが再生成してScreen構造が変わった、
///   等)。
/// * 保存されていた値のJSON形式が壊れている(`ForgeStateValue.fromJson`が
///   例外を投げる)。
/// * 型が一致しない(例: 以前は`checklist`だったキーが、再生成後は
///   `record_list`になっていた)。
Map<String, ForgeStateValue> mergePersistedState(
  Map<String, ForgeStateValue> declared,
  Map<String, dynamic>? persisted,
) {
  if (persisted == null || persisted.isEmpty) return declared;
  final merged = Map<String, ForgeStateValue>.of(declared);
  for (final key in declared.keys) {
    final rawValue = persisted[key];
    if (rawValue is! Map<String, dynamic>) continue;
    try {
      final restored = ForgeStateValue.fromJson(rawValue, '/persisted_state/$key');
      if (restored.runtimeType == declared[key].runtimeType) {
        merged[key] = restored;
      }
    } catch (_) {
      // 復元失敗時は宣言された初期値のまま(既にmergedへ入っている)。
    }
  }
  return merged;
}

sealed class ForgeStateValue {
  const ForgeStateValue();

  /// FORGE-AI-QUALITY-001(2026-08-11)新設(ローカル永続化対応)。
  /// [fromJson]の逆変換。`{"type": ..., "value": ...}`という、[fromJson]が
  /// 読める形と厳密に対称な形を返す(round-trip: `fromJson(toJson(x), _) == x`
  /// 相当)。AI生成アプリの実行時State(Runtime起動中にユーザーが追加・
  /// 変更したデータ)をローカル保存する際に使う
  /// (`app_library/data/repositories/`参照)。
  Map<String, dynamic> toJson();

  factory ForgeStateValue.fromJson(Map<String, dynamic> json, String path) {
    final type = json['type'];
    switch (type) {
      case 'string':
        return ForgeStringState(json['value'] as String? ?? '');
      case 'boolean':
        return ForgeBooleanState(json['value'] as bool? ?? false);
      case 'number':
        // FORGE-MILESTONE-003 Task 4: JSONのnumberはDartではintまたはdoubleに
        // なりうるため、num型で受けてdoubleへ正規化する(1と1.0を同じ扱いにする)。
        final raw = json['value'];
        if (raw is! num) {
          throw ForgeParseException('$path/value', 'number value must be numeric');
        }
        return ForgeNumberState(raw.toDouble());
      case 'string_list':
        // FORGE-MILESTONE-002.1 Task 4監査: 左辺(List<String>?)からの推論に
        // 頼らず、右辺にも明示的な型引数を付けて inference_failure を確実に避ける。
        final list = (json['value'] as List?)?.cast<String>() ?? const <String>[];
        return ForgeStringListState(list);
      case 'checklist':
        final rawItems = json['value'];
        if (rawItems is! List) {
          throw ForgeParseException('$path/value', 'checklist value must be an array');
        }
        final items = rawItems.asMap().entries.map((entry) {
          final item = entry.value;
          if (item is! Map<String, dynamic>) {
            throw ForgeParseException('$path/value/${entry.key}', 'checklist item must be an object');
          }
          return ForgeChecklistItem(
            id: item['id'] as String? ?? '',
            text: item['text'] as String? ?? '',
            done: item['done'] as bool? ?? false,
          );
        }).toList();
        return ForgeChecklistState(items);
      case 'record_list':
        // FORGE v0.7新規(Record Runtime Phase1)。record_schemas(Field型の
        // 宣言)を伴わない場合、fieldsの各値はdynamicのまま保持する
        // (Backend Validatorが文字列/数値/真偽値に制限済み、
        // クライアント側は素直にそれを信頼する)。
        // FORGE v0.9新規(Typed Record Runtime Phase1)。任意の
        // schema_refを保持する(`ForgeDocument.recordSchemas`を
        // 引くために使う。この時点では検証・利用はしない)。
        final rawRecords = json['value'];
        if (rawRecords is! List) {
          throw ForgeParseException('$path/value', 'record_list value must be an array');
        }
        final records = rawRecords.asMap().entries.map((entry) {
          final record = entry.value;
          if (record is! Map<String, dynamic>) {
            throw ForgeParseException('$path/value/${entry.key}', 'record_list item must be an object');
          }
          return _parseRecordItem(record, '$path/value/${entry.key}');
        }).toList();
        return ForgeRecordListState(records, schemaRef: json['schema_ref'] as String?);
      case 'selected_record':
        // FORGE v0.8新規(Record Runtime Phase2)。無選択時はvalue: null。
        final rawSelected = json['value'];
        if (rawSelected == null) {
          return const ForgeSelectedRecordState(null);
        }
        if (rawSelected is! Map<String, dynamic>) {
          throw ForgeParseException('$path/value', 'selected_record value must be an object or null');
        }
        return ForgeSelectedRecordState(_parseRecordItem(rawSelected, '$path/value'));
      default:
        throw ForgeParseException(path, 'unknown state type: $type');
    }
  }
}

/// `record_list`/`selected_record`が共有する、1件のRecordのパース処理
/// (FORGE v0.8対応で共通化した)。
ForgeRecordItem _parseRecordItem(Map<String, dynamic> json, String path) {
  final rawFields = json['fields'];
  if (rawFields is! Map<String, dynamic>) {
    throw ForgeParseException('$path/fields', 'record item fields must be an object');
  }
  return ForgeRecordItem(id: json['id'] as String? ?? '', fields: Map<String, dynamic>.from(rawFields));
}

class ForgeStringState extends ForgeStateValue {
  final String value;
  const ForgeStringState(this.value);

  @override
  Map<String, dynamic> toJson() => {'type': 'string', 'value': value};
}

class ForgeBooleanState extends ForgeStateValue {
  final bool value;
  const ForgeBooleanState(this.value);

  @override
  Map<String, dynamic> toJson() => {'type': 'boolean', 'value': value};
}

/// v1.2新規(FORGE-MILESTONE-003)。
class ForgeNumberState extends ForgeStateValue {
  final double value;
  const ForgeNumberState(this.value);

  @override
  Map<String, dynamic> toJson() => {'type': 'number', 'value': value};
}

class ForgeStringListState extends ForgeStateValue {
  final List<String> value;
  const ForgeStringListState(this.value);

  @override
  Map<String, dynamic> toJson() => {'type': 'string_list', 'value': value};
}

class ForgeChecklistState extends ForgeStateValue {
  final List<ForgeChecklistItem> value;
  const ForgeChecklistState(this.value);

  @override
  Map<String, dynamic> toJson() => {
        'type': 'checklist',
        'value': value.map((i) => i.toJson()).toList(),
      };
}

class ForgeChecklistItem {
  final String id;
  final String text;
  final bool done;
  const ForgeChecklistItem({required this.id, required this.text, required this.done});

  ForgeChecklistItem copyWith({String? text, bool? done}) =>
      ForgeChecklistItem(id: id, text: text ?? this.text, done: done ?? this.done);

  Map<String, dynamic> toJson() => {'id': id, 'text': text, 'done': done};
}

/// v1.3新規(FORGE v0.7 Record Runtime Phase1)。複数のFieldを持つRecordの
/// 配列。`record_schemas`(Field型の宣言)・単体の`record`型はまだ無い
/// (指示書の制約、Phase1はrecord_listのみ)。
class ForgeRecordListState extends ForgeStateValue {
  final List<ForgeRecordItem> value;

  /// FORGE v0.9新規(Typed Record Runtime Phase1)。`record_schemas`
  /// (`ForgeDocument.recordSchemas`)のいずれかのSchema名を指す
  /// (任意、v1.4未満の文書やschema_ref無しの文書では`null`)。
  final String? schemaRef;

  const ForgeRecordListState(this.value, {this.schemaRef});

  @override
  Map<String, dynamic> toJson() => {
        'type': 'record_list',
        'value': value.map((r) => r.toJson()).toList(),
        if (schemaRef != null) 'schema_ref': schemaRef,
      };
}

class ForgeRecordItem {
  final String id;
  final Map<String, dynamic> fields;
  const ForgeRecordItem({required this.id, required this.fields});

  ForgeRecordItem copyWith({Map<String, dynamic>? fields}) =>
      ForgeRecordItem(id: id, fields: fields ?? this.fields);

  Map<String, dynamic> toJson() => {'id': id, 'fields': fields};
}

/// v1.3新規(FORGE v0.8 Record Runtime Phase2)。選択中の1件
/// (無選択時は`value`が`null`)。単体の`record`型そのもの(v1.3提案時の
/// より汎用的な構想)ではなく、「選択」というPhase2固有のユースケースに
/// 限定した型にしている(`ir_generator.py`のモジュールdocstring・
/// ADR-012と同じ設計思想: 選択状態の持ち方はForge Language固有の
/// 実装詳細)。
class ForgeSelectedRecordState extends ForgeStateValue {
  final ForgeRecordItem? value;
  const ForgeSelectedRecordState(this.value);

  @override
  Map<String, dynamic> toJson() => {'type': 'selected_record', 'value': value?.toJson()};
}

// ---------------------------------------------------------------------------
// Widget
// ---------------------------------------------------------------------------

sealed class ForgeWidgetNode {
  final String id;
  const ForgeWidgetNode(this.id);

  factory ForgeWidgetNode.fromJson(Map<String, dynamic> json, String path) {
    final type = json['type'];
    final id = json['id'] as String? ?? '';
    switch (type) {
      case 'text':
        return ForgeTextWidgetNode(
          id, value: json['value'] as String? ?? '', stateRef: json['state_ref'] as String?,
        );
      case 'text_field':
        final stateRef = json['state_ref'];
        if (stateRef is! String || stateRef.isEmpty) {
          throw ForgeParseException('$path/state_ref', 'text_field.state_ref is required');
        }
        return ForgeTextFieldWidgetNode(
          id, stateRef: stateRef, placeholder: json['placeholder'] as String?,
          validationRules: _parseValidation(json['validation'], '$path/validation'),
        );
      case 'button':
        final actionJson = json['action'];
        if (actionJson is! Map<String, dynamic>) {
          throw ForgeParseException('$path/action', 'button.action is required');
        }
        return ForgeButtonWidgetNode(
          id, label: json['label'] as String? ?? '', action: ForgeAction.fromJson(actionJson, '$path/action'),
        );
      case 'column':
      case 'row':
        final childrenJson = json['children'];
        if (childrenJson is! List) {
          throw ForgeParseException('$path/children', '$type.children must be an array');
        }
        final children = <ForgeWidgetNode>[];
        for (var i = 0; i < childrenJson.length; i++) {
          final c = childrenJson[i];
          if (c is! Map<String, dynamic>) {
            throw ForgeParseException('$path/children/$i', 'child must be an object');
          }
          children.add(ForgeWidgetNode.fromJson(c, '$path/children/$i'));
        }
        return type == 'column'
            ? ForgeColumnWidgetNode(id, children: children)
            : ForgeRowWidgetNode(id, children: children);
      case 'checklist':
        final stateRef = json['state_ref'];
        if (stateRef is! String || stateRef.isEmpty) {
          throw ForgeParseException('$path/state_ref', 'checklist.state_ref is required');
        }
        return ForgeChecklistWidgetNode(
          id, stateRef: stateRef, emptyStateText: json['empty_state_text'] as String? ?? 'アイテムはまだないよ',
        );
      case 'heading':
        return ForgeHeadingWidgetNode(
          id, value: json['value'] as String? ?? '', level: (json['level'] as num?)?.toInt() ?? 1,
        );
      case 'checkbox':
        final stateRef = json['state_ref'];
        if (stateRef is! String || stateRef.isEmpty) {
          throw ForgeParseException('$path/state_ref', 'checkbox.state_ref is required');
        }
        return ForgeCheckboxWidgetNode(
          id, label: json['label'] as String? ?? '', stateRef: stateRef,
          validationRules: _parseValidation(json['validation'], '$path/validation'),
        );
      case 'card':
        return ForgeCardWidgetNode(id, children: _parseChildren(json['children'], path, 'card'));
      case 'list':
        final stateRef = json['state_ref'];
        if (stateRef is! String || stateRef.isEmpty) {
          throw ForgeParseException('$path/state_ref', 'list.state_ref is required');
        }
        return ForgeListWidgetNode(
          id, stateRef: stateRef, emptyStateText: json['empty_state_text'] as String? ?? 'まだ何もないよ',
        );
      case 'record_list_view':
        // FORGE v0.7新規(Record Runtime Phase1)。Phase1では
        // layout="card"のみをBackend Validatorが許可しているが、
        // 未指定時のRuntime側の既定値としても"card"を使う(Schema側の
        // 既定値と揃える)。
        final recordStateRef = json['state_ref'];
        if (recordStateRef is! String || recordStateRef.isEmpty) {
          throw ForgeParseException('$path/state_ref', 'record_list_view.state_ref is required');
        }
        final rawDisplayFields = json['display_fields'];
        // FORGE v0.8新規(Record Runtime Phase2)。
        final rawSelectFieldBindings = json['select_field_bindings'];
        return ForgeRecordListViewWidgetNode(
          id,
          stateRef: recordStateRef,
          emptyStateText: json['empty_state_text'] as String? ?? 'まだ記録がないよ',
          layout: json['layout'] as String? ?? 'card',
          displayFields: (rawDisplayFields is List) ? rawDisplayFields.cast<String>() : null,
          selectable: json['selectable'] as bool? ?? false,
          selectedStateRef: json['selected_state_ref'] as String?,
          selectFieldBindings: (rawSelectFieldBindings is Map<String, dynamic>)
              ? Map<String, String>.from(rawSelectFieldBindings)
              : null,
        );
      case 'divider':
        return ForgeDividerWidgetNode(id);
      case 'section_header':
        // FORGE v1.0新規(Product Quality Sprint1)。
        final title = json['title'];
        if (title is! String || title.isEmpty) {
          throw ForgeParseException('$path/title', 'section_header.title is required');
        }
        return ForgeSectionHeaderWidgetNode(id, title: title, subtitle: json['subtitle'] as String?);
      case 'form':
        final submitActionJson = json['submit_action'];
        if (submitActionJson is! Map<String, dynamic>) {
          throw ForgeParseException('$path/submit_action', 'form.submit_action is required');
        }
        return ForgeFormWidgetNode(
          id,
          children: _parseChildren(json['children'], path, 'form'),
          submitLabel: json['submit_label'] as String? ?? '',
          submitAction: ForgeAction.fromJson(submitActionJson, '$path/submit_action'),
        );
      case 'choice_field':
        // v1.6新規(Widget Vocabulary Expansion、2026-08-11、CEO承認により
        // Forge Language Freeze運用を解除)。TD33の応急処置
        // (text_fieldのplaceholderへ選択肢を埋め込む)を置き換える、
        // 専用のドロップダウンWidget。
        final choiceStateRef = json['state_ref'];
        if (choiceStateRef is! String || choiceStateRef.isEmpty) {
          throw ForgeParseException('$path/state_ref', 'choice_field.state_ref is required');
        }
        final rawOptions = json['options'];
        if (rawOptions is! List || rawOptions.isEmpty) {
          throw ForgeParseException('$path/options', 'choice_field.options must be a non-empty array');
        }
        return ForgeChoiceFieldWidgetNode(
          id,
          stateRef: choiceStateRef,
          label: json['label'] as String? ?? '',
          options: rawOptions.cast<String>(),
          placeholder: json['placeholder'] as String?,
        );
      case 'bar_chart':
        // v1.6新規。record_listの数値Fieldを棒グラフで可視化する
        // (1 Record = 1本の棒、集計は行わないPhase1最小実装)。
        final chartStateRef = json['state_ref'];
        if (chartStateRef is! String || chartStateRef.isEmpty) {
          throw ForgeParseException('$path/state_ref', 'bar_chart.state_ref is required');
        }
        final valueField = json['value_field'];
        if (valueField is! String || valueField.isEmpty) {
          throw ForgeParseException('$path/value_field', 'bar_chart.value_field is required');
        }
        final labelField = json['label_field'];
        if (labelField is! String || labelField.isEmpty) {
          throw ForgeParseException('$path/label_field', 'bar_chart.label_field is required');
        }
        return ForgeBarChartWidgetNode(
          id,
          stateRef: chartStateRef,
          valueField: valueField,
          labelField: labelField,
          title: json['title'] as String?,
        );
      case 'date_field':
        // v1.7新規(Widget Vocabulary Expansion第2弾、2026-08-11)。
        // TD33の「text_fieldのplaceholderへYYYY-MM-DD形式のヒントを
        // 埋め込む」応急処置を、choice_field(TD34)と同じ理由で専用の
        // カレンダー選択Widgetへ置き換える。
        final dateStateRef = json['state_ref'];
        if (dateStateRef is! String || dateStateRef.isEmpty) {
          throw ForgeParseException('$path/state_ref', 'date_field.state_ref is required');
        }
        return ForgeDateFieldWidgetNode(
          id,
          stateRef: dateStateRef,
          label: json['label'] as String? ?? '',
          placeholder: json['placeholder'] as String?,
        );
      case 'tab_view':
        // v1.7新規。column/row/card/formと同じ「フラットなchildren配列を
        // 持つコンテナ」として設計している(`schema_validator.py`の
        // `CONTAINER_WIDGET_TYPES`コメント参照)。`children[i]`が
        // `tab_titles[i]`というタブの中身に対応する。
        final rawTabTitles = json['tab_titles'];
        if (rawTabTitles is! List || rawTabTitles.isEmpty) {
          throw ForgeParseException('$path/tab_titles', 'tab_view.tab_titles must be a non-empty array');
        }
        final tabChildren = _parseChildren(json['children'], path, 'tab_view');
        if (tabChildren.length != rawTabTitles.length) {
          throw ForgeParseException(
            '$path/children', 'tab_view.tab_titles and children must have the same length',
          );
        }
        return ForgeTabViewWidgetNode(id, tabTitles: rawTabTitles.cast<String>(), children: tabChildren);
      default:
        // 未知Widget: 例外を投げず、専用のFallbackノードとして扱う。
        // (Validatorが既に弾いているはずだが、クライアント側も多重防御する)
        return ForgeUnknownWidgetNode(id, rawType: '$type');
    }
  }
}

/// column/row/card/form が共有する「childrenをパースする」処理の共通化。
List<ForgeWidgetNode> _parseChildren(dynamic childrenJson, String path, String widgetType) {
  if (childrenJson is! List) {
    throw ForgeParseException('$path/children', '$widgetType.children must be an array');
  }
  final children = <ForgeWidgetNode>[];
  for (var i = 0; i < childrenJson.length; i++) {
    final c = childrenJson[i];
    if (c is! Map<String, dynamic>) {
      throw ForgeParseException('$path/children/$i', 'child must be an object');
    }
    children.add(ForgeWidgetNode.fromJson(c, '$path/children/$i'));
  }
  return children;
}

class ForgeTextWidgetNode extends ForgeWidgetNode {
  final String value;
  final String? stateRef;
  const ForgeTextWidgetNode(super.id, {required this.value, this.stateRef});
}

class ForgeTextFieldWidgetNode extends ForgeWidgetNode {
  final String stateRef;
  final String? placeholder;
  final List<ForgeValidationRule>? validationRules; // v1.2新規(FORGE-MILESTONE-003)
  const ForgeTextFieldWidgetNode(super.id, {required this.stateRef, this.placeholder, this.validationRules});
}

class ForgeButtonWidgetNode extends ForgeWidgetNode {
  final String label;
  final ForgeAction action;
  const ForgeButtonWidgetNode(super.id, {required this.label, required this.action});
}

class ForgeColumnWidgetNode extends ForgeWidgetNode {
  final List<ForgeWidgetNode> children;
  const ForgeColumnWidgetNode(super.id, {required this.children});
}

class ForgeRowWidgetNode extends ForgeWidgetNode {
  final List<ForgeWidgetNode> children;
  const ForgeRowWidgetNode(super.id, {required this.children});
}

class ForgeChecklistWidgetNode extends ForgeWidgetNode {
  final String stateRef;
  final String emptyStateText;
  const ForgeChecklistWidgetNode(super.id, {required this.stateRef, required this.emptyStateText});
}

/// v1.1新規(FORGE-MILESTONE-002 PHASE1)。
class ForgeHeadingWidgetNode extends ForgeWidgetNode {
  final String value;
  final int level; // 1 or 2
  const ForgeHeadingWidgetNode(super.id, {required this.value, required this.level});
}

/// v1.1新規。checklistとは異なり単一のboolean stateに対する1個のON/OFF。
class ForgeCheckboxWidgetNode extends ForgeWidgetNode {
  final String label;
  final String stateRef;
  final List<ForgeValidationRule>? validationRules; // v1.2新規(FORGE-MILESTONE-003)
  const ForgeCheckboxWidgetNode(super.id, {required this.label, required this.stateRef, this.validationRules});
}

/// v1.1新規。columnと構造は同じだが、視覚的に区切られた塊であることを示す。
class ForgeCardWidgetNode extends ForgeWidgetNode {
  final List<ForgeWidgetNode> children;
  const ForgeCardWidgetNode(super.id, {required this.children});
}

/// v1.1新規。string_list型のstateを表示する読み取り専用の単純な箇条書き。
/// TECH_DEBT.md TD7(string_list型を消費するWidgetが無い)を解消する。
class ForgeListWidgetNode extends ForgeWidgetNode {
  final String stateRef;
  final String emptyStateText;
  const ForgeListWidgetNode(super.id, {required this.stateRef, required this.emptyStateText});
}

/// v1.3新規(FORGE v0.7 Record Runtime Phase1)。record_list型のstateを
/// 表示する。Phase1では`layout`は"card"のみが有効(Backend Validatorが
/// 強制する)。`displayFields`が`null`の場合、各Recordの`fields`に実際に
/// 含まれる全キーを表示する(Compilerは通常明示的に渡すが、直接組み立てた
/// テスト用の文書等でdisplay_fieldsを省略した場合の安全なフォールバック)。
///
/// FORGE v0.8(Record Runtime Phase2)対応: `selectable`が`true`の場合、
/// 各Cardをタップすると選択できる。選択されると`selectedStateRef`
/// (必須)へそのRecordが設定され、`selectFieldBindings`(任意)に
/// 従って編集用フォームのフィールドへ値が反映される。「更新」
/// (`UpdateRecordAction`)「削除」(`DeleteRecordAction`)は、いずれも
/// この「選択中の1件」に対する操作として、record_list_view自体では
/// なく別のForm/Buttonから静的なJSONとして発行される
/// (`forge_ai/core/ir/forge_language_compiler.py`と対称的な設計、
/// 選択・更新・削除の起点をrecord_list_view単体に集約しすぎない
/// ための責務分離)。
class ForgeRecordListViewWidgetNode extends ForgeWidgetNode {
  final String stateRef;
  final String emptyStateText;
  final String layout; // "card" | "grid"(FORGE v1.0で"grid"を追加、"table"は未実装)
  final List<String>? displayFields;
  final bool selectable;
  final String? selectedStateRef;
  final Map<String, String>? selectFieldBindings;
  const ForgeRecordListViewWidgetNode(
    super.id, {
    required this.stateRef,
    required this.emptyStateText,
    required this.layout,
    this.displayFields,
    this.selectable = false,
    this.selectedStateRef,
    this.selectFieldBindings,
  });
}

/// v1.1新規。区切り線。状態・アクションを持たない最も単純なWidget。
class ForgeDividerWidgetNode extends ForgeWidgetNode {
  const ForgeDividerWidgetNode(super.id);
}

/// v1.5新規(FORGE v1.0 Product Quality Sprint1)。単一画面内の
/// 視覚的階層(セクション区切り)を表す、状態・アクションを持たない
/// 表示専用Widget(`ForgeDividerWidgetNode`と同じ、最も単純な部類の
/// Widget)。
class ForgeSectionHeaderWidgetNode extends ForgeWidgetNode {
  final String title;
  final String? subtitle;
  const ForgeSectionHeaderWidgetNode(super.id, {required this.title, this.subtitle});
}

/// v1.1新規。入力系Widgetをまとめ、1つの送信操作に束ねるコンテナ。
class ForgeFormWidgetNode extends ForgeWidgetNode {
  final List<ForgeWidgetNode> children;
  final String submitLabel;
  final ForgeAction submitAction;
  const ForgeFormWidgetNode(
    super.id, {
    required this.children,
    required this.submitLabel,
    required this.submitAction,
  });
}

/// v1.6新規(Widget Vocabulary Expansion、2026-08-11)。決まった選択肢
/// から1つを選ばせる入力(Flutterの`DropdownButtonFormField`で実装、
/// `widget_registry_v1_6.dart`参照)。`options`と一致しない値を
/// 構造的に入力できないため、`ForgeFieldValueParser._parseChoice()`が
/// 要求する完全一致を、UIの構造そのもので保証する(TD33の
/// placeholder応急処置より根本的)。
class ForgeChoiceFieldWidgetNode extends ForgeWidgetNode {
  final String stateRef;
  final String label;
  final List<String> options;
  final String? placeholder;
  const ForgeChoiceFieldWidgetNode(
    super.id, {
    required this.stateRef,
    required this.label,
    required this.options,
    this.placeholder,
  });
}

/// v1.6新規。`record_list`型stateの数値Field(`valueField`)を、
/// `labelField`ごとの棒として可視化する(1 Record = 1本の棒、集計は
/// 行わないPhase1最小実装)。
class ForgeBarChartWidgetNode extends ForgeWidgetNode {
  final String stateRef;
  final String valueField;
  final String labelField;
  final String? title;
  const ForgeBarChartWidgetNode(
    super.id, {
    required this.stateRef,
    required this.valueField,
    required this.labelField,
    this.title,
  });
}

/// v1.7新規(Widget Vocabulary Expansion第2弾、2026-08-11)。カレンダー
/// UI(`showDatePicker()`、`widget_registry_v1_7.dart`参照)で日付を
/// 選ばせる入力。`options`と一致しない値を入力できないchoice_fieldと
/// 同じ理由で、`ForgeFieldValueParser._parseDate()`が要求するISO 8601
/// 完全一致を、UIの構造そのもので保証する。
class ForgeDateFieldWidgetNode extends ForgeWidgetNode {
  final String stateRef;
  final String label;
  final String? placeholder;
  const ForgeDateFieldWidgetNode(super.id, {required this.stateRef, required this.label, this.placeholder});
}

/// v1.7新規。複数の子Widget群(`children[i]`)を、`tabTitles[i]`という
/// タイトルのタブとして切り替え表示する(Flutterの
/// `DefaultTabController`/`TabBar`/`TabBarView`で実装、新規パッケージ
/// 依存なし)。**画面遷移(Navigator.push)ではなくタブを選んだ理由**:
/// `forge_renderer.dart`の`_ForgeScreenViewState.initState()`は、画面
/// 遷移のたびに独立した新しい`ForgeRuntimeState`を生成する設計であり、
/// 複数`screens`によるCRUD分割は「一覧画面」と「追加画面」で`records`
/// Stateが同期しない、壊れたアプリを生成してしまう。`tab_view`は
/// 同一画面・同一Stateのまま表示だけを切り替えるため、この制約を
/// 安全に回避できる(`forge_language_compiler.py`のv1.7節、
/// `TECH_DEBT.md`参照)。
class ForgeTabViewWidgetNode extends ForgeWidgetNode {
  final List<String> tabTitles;
  final List<ForgeWidgetNode> children;
  const ForgeTabViewWidgetNode(super.id, {required this.tabTitles, required this.children});
}

/// Validatorをすり抜けた未知typeに対する、クライアント側の最終防衛線。
class ForgeUnknownWidgetNode extends ForgeWidgetNode {
  final String rawType;
  const ForgeUnknownWidgetNode(super.id, {required this.rawType});
}

// ---------------------------------------------------------------------------
// Action
// ---------------------------------------------------------------------------

sealed class ForgeAction {
  const ForgeAction();

  factory ForgeAction.fromJson(Map<String, dynamic> json, String path) {
    switch (json['type']) {
      case 'navigate':
        final target = json['target_screen_id'];
        if (target is! String || target.isEmpty) {
          throw ForgeParseException('$path/target_screen_id', 'navigate.target_screen_id is required');
        }
        return NavigateAction(target);
      case 'go_back':
        return const GoBackAction();
      case 'set_value':
      case 'set_state':
        // set_state は v1.2の正式名称、set_value は v1.0/v1.1互換のため維持。
        // 意味論が完全に同じなので同じDartクラスへ写像する(DECISIONS.md参照)。
        final stateRef = json['state_ref'];
        if (stateRef is! String || stateRef.isEmpty) {
          throw ForgeParseException('$path/state_ref', '${json['type']}.state_ref is required');
        }
        return SetValueAction(stateRef, json['value']);
      case 'add_item':
        final target = json['target_state_ref'];
        final source = json['source_state_ref'];
        if (target is! String || target.isEmpty || source is! String || source.isEmpty) {
          throw ForgeParseException(path, 'add_item requires target_state_ref and source_state_ref');
        }
        return AddItemAction(targetStateRef: target, sourceStateRef: source);
      case 'add_record':
        // FORGE v0.7新規(Record Runtime Phase1)。
        final target = json['target_state_ref'];
        if (target is! String || target.isEmpty) {
          throw ForgeParseException('$path/target_state_ref', 'add_record.target_state_ref is required');
        }
        final bindings = _parseFieldBindings(json['field_bindings'], '$path/field_bindings');
        return AddRecordAction(targetStateRef: target, fieldBindings: bindings);
      case 'select_record':
        // FORGE v0.8新規(Record Runtime Phase2)。**通常、この'select_record'
        // ケースが実際に呼ばれることは無い**(`record_id`は特定の1件を
        // 指す値であり、静的なJSONへCompilerが埋め込める情報ではない
        // ため。`record_list_view`のCard選択は、Runtimeが
        // `SelectRecordAction`を直接組み立てて発行する、
        // `widget_registry_v1_3.dart`参照)。将来の直接記述・テスト用に
        // パース自体は用意しておく(`recordId`は空文字列になる。実際の
        // 選択操作でこの空のrecordIdが使われることは無い)。
        final sourceRef = json['source_state_ref'];
        final targetRef = json['target_state_ref'];
        if (sourceRef is! String || sourceRef.isEmpty) {
          throw ForgeParseException('$path/source_state_ref', 'select_record.source_state_ref is required');
        }
        if (targetRef is! String || targetRef.isEmpty) {
          throw ForgeParseException('$path/target_state_ref', 'select_record.target_state_ref is required');
        }
        final selectBindings = json.containsKey('field_bindings')
            ? _parseFieldBindings(json['field_bindings'], '$path/field_bindings')
            : const <String, String>{};
        return SelectRecordAction(
          sourceStateRef: sourceRef, targetStateRef: targetRef, recordId: '', fieldBindings: selectBindings,
        );
      case 'update_record':
        // FORGE v0.8新規(Record Runtime Phase2)。
        final updateTarget = json['target_state_ref'];
        final recordIdRef = json['record_id_ref'];
        if (updateTarget is! String || updateTarget.isEmpty) {
          throw ForgeParseException('$path/target_state_ref', 'update_record.target_state_ref is required');
        }
        if (recordIdRef is! String || recordIdRef.isEmpty) {
          throw ForgeParseException('$path/record_id_ref', 'update_record.record_id_ref is required');
        }
        final updateBindings = _parseFieldBindings(json['field_bindings'], '$path/field_bindings');
        return UpdateRecordAction(targetStateRef: updateTarget, recordIdRef: recordIdRef, fieldBindings: updateBindings);
      case 'delete_record':
        // FORGE v0.8新規(Record Runtime Phase2)。
        final deleteTarget = json['target_state_ref'];
        final deleteRecordIdRef = json['record_id_ref'];
        if (deleteTarget is! String || deleteTarget.isEmpty) {
          throw ForgeParseException('$path/target_state_ref', 'delete_record.target_state_ref is required');
        }
        if (deleteRecordIdRef is! String || deleteRecordIdRef.isEmpty) {
          throw ForgeParseException('$path/record_id_ref', 'delete_record.record_id_ref is required');
        }
        return DeleteRecordAction(targetStateRef: deleteTarget, recordIdRef: deleteRecordIdRef);
      case 'toggle_state':
        final stateRef = json['state_ref'];
        if (stateRef is! String || stateRef.isEmpty) {
          throw ForgeParseException('$path/state_ref', 'toggle_state.state_ref is required');
        }
        return ToggleStateAction(stateRef);
      case 'reset_state':
        final stateRef = json['state_ref'];
        if (stateRef is! String || stateRef.isEmpty) {
          throw ForgeParseException('$path/state_ref', 'reset_state.state_ref is required');
        }
        return ResetStateAction(stateRef);
      case 'submit_form':
        final formRef = json['form_ref'];
        if (formRef is! String || formRef.isEmpty) {
          throw ForgeParseException('$path/form_ref', 'submit_form.form_ref is required');
        }
        final successActionJson = json['success_action'];
        if (successActionJson is! Map<String, dynamic>) {
          throw ForgeParseException('$path/success_action', 'submit_form.success_action is required');
        }
        return SubmitFormAction(
          formRef: formRef,
          successAction: ForgeAction.fromJson(successActionJson, '$path/success_action'),
        );
      case 'composite':
        final actionsJson = json['actions'];
        if (actionsJson is! List || actionsJson.isEmpty) {
          throw ForgeParseException('$path/actions', 'composite.actions must be a non-empty array');
        }
        final actions = <ForgeAction>[];
        for (var i = 0; i < actionsJson.length; i++) {
          final a = actionsJson[i];
          if (a is! Map<String, dynamic>) {
            throw ForgeParseException('$path/actions/$i', 'action must be an object');
          }
          actions.add(ForgeAction.fromJson(a, '$path/actions/$i'));
        }
        return CompositeAction(actions);
      default:
        throw ForgeParseException(path, 'unknown action type: ${json['type']}');
    }
  }
}

/// `add_record`/`select_record`/`update_record`が共有する、
/// `field_bindings`(Record Field名 → source state key)のパース処理
/// (FORGE v0.8対応で共通化した)。
Map<String, String> _parseFieldBindings(dynamic rawBindings, String path) {
  if (rawBindings is! Map<String, dynamic> || rawBindings.isEmpty) {
    throw ForgeParseException(path, 'field_bindings must be a non-empty object');
  }
  final bindings = <String, String>{};
  for (final entry in rawBindings.entries) {
    final sourceRef = entry.value;
    if (sourceRef is! String || sourceRef.isEmpty) {
      throw ForgeParseException('$path/${entry.key}', 'field_bindings value must be a non-empty string');
    }
    bindings[entry.key] = sourceRef;
  }
  return bindings;
}

class NavigateAction extends ForgeAction {
  final String targetScreenId;
  const NavigateAction(this.targetScreenId);
}

class GoBackAction extends ForgeAction {
  const GoBackAction();
}

class SetValueAction extends ForgeAction {
  final String stateRef;
  final dynamic value;
  const SetValueAction(this.stateRef, this.value);
}

class AddItemAction extends ForgeAction {
  final String targetStateRef;
  final String sourceStateRef;
  const AddItemAction({required this.targetStateRef, required this.sourceStateRef});
}

/// v1.3新規(FORGE v0.7 Record Runtime Phase1)。`fieldBindings`(Record
/// field名 → source state key)の各エントリの現在値を1つのRecordへ束ねて
/// `targetStateRef`(record_list型)へ追加する。
class AddRecordAction extends ForgeAction {
  final String targetStateRef;
  final Map<String, String> fieldBindings;
  const AddRecordAction({required this.targetStateRef, required this.fieldBindings});
}

/// v1.3新規(FORGE v0.8 Record Runtime Phase2)。`sourceStateRef`
/// (record_list型)から`recordId`が一致するRecordを取り出し、
/// `targetStateRef`(selected_record型)へ設定する。`fieldBindings`が
/// 指定されている場合、そのRecordの各Field値を、対応するstateへ
/// 反映する(編集用フォームの事前入力)。
///
/// **`recordId`は通常、Dartコード側(`widget_registry_v1_3.dart`)が
/// タップされたRecordの実際のidを渡して構築する**。JSONから`fromJson`
/// でパースされたインスタンスの`recordId`は常に空文字列になる
/// (`forge_document.dart`の`fromJson`実装参照)。
class SelectRecordAction extends ForgeAction {
  final String sourceStateRef;
  final String targetStateRef;
  final String recordId;
  final Map<String, String> fieldBindings;
  const SelectRecordAction({
    required this.sourceStateRef,
    required this.targetStateRef,
    required this.recordId,
    this.fieldBindings = const {},
  });

  /// タップされたRecordの実際のidを渡した、新しいインスタンスを作る
  /// (`fromJson`で`recordId: ''`のまま構築されたインスタンスから、
  /// Widgetが実際に使う値へ差し替えるためのヘルパー)。
  SelectRecordAction withRecordId(String actualRecordId) => SelectRecordAction(
        sourceStateRef: sourceStateRef,
        targetStateRef: targetStateRef,
        recordId: actualRecordId,
        fieldBindings: fieldBindings,
      );
}

/// v1.3新規(FORGE v0.8 Record Runtime Phase2)。`recordIdRef`が指す
/// state(通常`selected_record`型)のidを持つRecordを、`targetStateRef`
/// (record_list型)の中から見つけて、`fieldBindings`の現在値で
/// フィールドを置き換える。`update_record`は`select_record`と異なり、
/// 常に静的なJSON(button/form.submit_action)として文書内に現れる
/// (`record_id_ref`という「stateを指す」形で対象を特定できるため)。
class UpdateRecordAction extends ForgeAction {
  final String targetStateRef;
  final String recordIdRef;
  final Map<String, String> fieldBindings;
  const UpdateRecordAction({required this.targetStateRef, required this.recordIdRef, required this.fieldBindings});
}

/// v1.3新規(FORGE v0.8 Record Runtime Phase2)。`recordIdRef`が指す
/// stateのidを持つRecordを、`targetStateRef`から削除する。
class DeleteRecordAction extends ForgeAction {
  final String targetStateRef;
  final String recordIdRef;
  const DeleteRecordAction({required this.targetStateRef, required this.recordIdRef});
}

/// v1.2新規(FORGE-MILESTONE-003)。boolean stateを反転する。
class ToggleStateAction extends ForgeAction {
  final String stateRef;
  const ToggleStateAction(this.stateRef);
}

/// v1.2新規。指定したstateを画面初期化時点の値へ戻す。
class ResetStateAction extends ForgeAction {
  final String stateRef;
  const ResetStateAction(this.stateRef);
}

/// v1.2新規。form_refが指すformを検証し、合格した場合のみsuccessActionを実行する。
class SubmitFormAction extends ForgeAction {
  final String formRef;
  final ForgeAction successAction;
  const SubmitFormAction({required this.formRef, required this.successAction});
}

/// v1.2新規。複数Actionを順番に実行する。
class CompositeAction extends ForgeAction {
  final List<ForgeAction> actions;
  const CompositeAction(this.actions);
}
