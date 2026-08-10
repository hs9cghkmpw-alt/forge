// ForgeFormValidator Unit Test(FORGE-MILESTONE-003)。
//
// 指示書5章「Validation」の項目を網羅する: required・min_length・max_length・
// min・max・pattern・エラーメッセージ表示・検証成功時のみAction実行
// (Action実行そのものはforge_action_dispatcher_test.dartのsubmit_form系で検証済み。
// ここではForgeFormValidator単体のルール判定ロジックを検証する)。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/runtime/forge_form_validator.dart';
import 'package:forge_app/json_ui/runtime/forge_state_store.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

void main() {
  const validator = ForgeFormValidator();

  test('required: 空文字は失敗、非空は成功', () {
    final store = ForgeStateStore({'name': const ForgeStringState('')});
    final fields = [
      const ForgeValidatableField(stateRef: 'name', rules: [
        ForgeValidationRule(type: 'required', value: null, message: '必須です'),
      ]),
    ];
    var errors = validator.validate(fields, store);
    expect(errors, {'name': '必須です'});

    store.write('name', '太郎');
    errors = validator.validate(fields, store);
    expect(errors, isEmpty);
  });

  test('required: boolean(checkbox)ではfalseが失敗、trueが成功', () {
    final store = ForgeStateStore({'agreed': const ForgeBooleanState(false)});
    final fields = [
      const ForgeValidatableField(stateRef: 'agreed', rules: [
        ForgeValidationRule(type: 'required', value: null, message: '同意が必要です'),
      ]),
    ];
    var errors = validator.validate(fields, store);
    expect(errors, {'agreed': '同意が必要です'});

    store.write('agreed', true);
    errors = validator.validate(fields, store);
    expect(errors, isEmpty);
  });

  test('min_length: 文字数が足りない場合は失敗', () {
    final store = ForgeStateStore({'pw': const ForgeStringState('ab')});
    final fields = [
      const ForgeValidatableField(stateRef: 'pw', rules: [
        ForgeValidationRule(type: 'min_length', value: 8, message: '8文字以上にしてください'),
      ]),
    ];
    expect(validator.validate(fields, store), {'pw': '8文字以上にしてください'});
  });

  test('max_length: 文字数超過は失敗', () {
    final store = ForgeStateStore({'bio': ForgeStringState('あ' * 100)});
    final fields = [
      const ForgeValidatableField(stateRef: 'bio', rules: [
        ForgeValidationRule(type: 'max_length', value: 50, message: '50文字以内にしてください'),
      ]),
    ];
    expect(validator.validate(fields, store), {'bio': '50文字以内にしてください'});
  });

  test('min: 数値が下限未満は失敗', () {
    final store = ForgeStateStore({'age': const ForgeNumberState(15)});
    final fields = [
      const ForgeValidatableField(stateRef: 'age', rules: [
        ForgeValidationRule(type: 'min', value: 18, message: '18歳以上にしてください'),
      ]),
    ];
    expect(validator.validate(fields, store), {'age': '18歳以上にしてください'});
  });

  test('max: 数値が上限超過は失敗', () {
    final store = ForgeStateStore({'count': const ForgeNumberState(1000)});
    final fields = [
      const ForgeValidatableField(stateRef: 'count', rules: [
        ForgeValidationRule(type: 'max', value: 100, message: '100以下にしてください'),
      ]),
    ];
    expect(validator.validate(fields, store), {'count': '100以下にしてください'});
  });

  test('pattern: 正規表現に一致しない場合は失敗', () {
    final store = ForgeStateStore({'email': const ForgeStringState('not-an-email')});
    final fields = [
      const ForgeValidatableField(stateRef: 'email', rules: [
        ForgeValidationRule(type: 'pattern', value: r'^[^@]+@[^@]+\.[^@]+$', message: 'メール形式が不正です'),
      ]),
    ];
    expect(validator.validate(fields, store), {'email': 'メール形式が不正です'});
  });

  test('pattern: 正規表現に一致する場合は成功', () {
    final store = ForgeStateStore({'email': const ForgeStringState('a@example.com')});
    final fields = [
      const ForgeValidatableField(stateRef: 'email', rules: [
        ForgeValidationRule(type: 'pattern', value: r'^[^@]+@[^@]+\.[^@]+$', message: 'メール形式が不正です'),
      ]),
    ];
    expect(validator.validate(fields, store), isEmpty);
  });

  test('複数フィールド: 合格したフィールドはエラーマップに含まれない', () {
    final store = ForgeStateStore({
      'name': const ForgeStringState('太郎'), // OK
      'email': const ForgeStringState(''), // NG
    });
    final fields = [
      const ForgeValidatableField(stateRef: 'name', rules: [
        ForgeValidationRule(type: 'required', value: null, message: '名前必須'),
      ]),
      const ForgeValidatableField(stateRef: 'email', rules: [
        ForgeValidationRule(type: 'required', value: null, message: 'メール必須'),
      ]),
    ];
    final errors = validator.validate(fields, store);
    expect(errors.containsKey('name'), isFalse);
    expect(errors['email'], 'メール必須');
  });

  test('不正な正規表現でもクラッシュせず、そのルールを無視する', () {
    final store = ForgeStateStore({'x': const ForgeStringState('anything')});
    final fields = [
      const ForgeValidatableField(stateRef: 'x', rules: [
        ForgeValidationRule(type: 'pattern', value: '(unclosed', message: '不正な形式'),
      ]),
    ];
    expect(() => validator.validate(fields, store), returnsNormally);
    expect(validator.validate(fields, store), isEmpty, reason: '不正な正規表現はクラッシュせず無視される');
  });

  test('State型に適用できないルール(stringにmin/max等)は安全に無視される', () {
    final store = ForgeStateStore({'agreed': const ForgeBooleanState(true)});
    final fields = [
      const ForgeValidatableField(stateRef: 'agreed', rules: [
        ForgeValidationRule(type: 'min_length', value: 5, message: '無関係なルール'),
      ]),
    ];
    expect(() => validator.validate(fields, store), returnsNormally);
    expect(validator.validate(fields, store), isEmpty);
  });

  test('1フィールドに複数ルール: 最初に失敗したルールのメッセージが返る', () {
    final store = ForgeStateStore({'name': const ForgeStringState('')});
    final fields = [
      const ForgeValidatableField(stateRef: 'name', rules: [
        ForgeValidationRule(type: 'required', value: null, message: '必須です'),
        ForgeValidationRule(type: 'max_length', value: 10, message: '長すぎます'),
      ]),
    ];
    expect(validator.validate(fields, store), {'name': '必須です'});
  });
}
