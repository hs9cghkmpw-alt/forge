// ForgeFieldValueParser Unit Test(FORGE v1.0 Workstream E/B)。
//
// 指示書「Value Parser」節の全項目をカバーする。実行未検証
// (Claudeのサンドボックスに Dart SDK が無い)。

import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';
import 'package:forge_app/json_ui/validation/forge_field_value_parser.dart';

ForgeRecordSchemaField _field({
  required ForgeRecordFieldType type,
  bool required = true,
  List<String>? options,
  String name = 'f',
  String label = 'F',
}) {
  return ForgeRecordSchemaField(name: name, type: type, label: label, required: required, options: options);
}

void main() {
  const parser = ForgeFieldValueParser();

  group('valid number', () {
    test('整数はintとして保持される', () {
      final result = parser.parse('30', _field(type: ForgeRecordFieldType.number, required: false));
      expect(result, isA<FieldParseSuccess>());
      expect((result as FieldParseSuccess).value, isA<int>());
      expect(result.value, 30);
    });

    test('負の整数を受け入れる', () {
      final result = parser.parse('-2', _field(type: ForgeRecordFieldType.number, required: false));
      expect(result, isA<FieldParseSuccess>());
      expect((result as FieldParseSuccess).value, -2);
      expect(result.value, isA<int>());
    });

    test('小数はdoubleとして保持される', () {
      final result = parser.parse('1.5', _field(type: ForgeRecordFieldType.number, required: false));
      expect(result, isA<FieldParseSuccess>());
      expect((result as FieldParseSuccess).value, 1.5);
      expect(result.value, isA<double>());
    });
  });

  group('invalid number', () {
    test('数字でない文字列はinvalidNumberで失敗する', () {
      final result = parser.parse('abc', _field(type: ForgeRecordFieldType.number, required: false));
      expect(result, isA<FieldParseFailure>());
      expect((result as FieldParseFailure).reason, FieldParseFailureReason.invalidNumber);
    });
  });

  group('negative number', () {
    test('-2.5のような負の小数も受け入れる', () {
      final result = parser.parse('-2.5', _field(type: ForgeRecordFieldType.number, required: false));
      expect(result, isA<FieldParseSuccess>());
      expect((result as FieldParseSuccess).value, -2.5);
    });
  });

  group('decimal', () {
    test('小数点付きの整数値相当(30.0)はdoubleとして保持される', () {
      final result = parser.parse('30.0', _field(type: ForgeRecordFieldType.number, required: false));
      expect(result, isA<FieldParseSuccess>());
      expect((result as FieldParseSuccess).value, isA<double>());
    });
  });

  group('valid date', () {
    test('2026-07-19は有効', () {
      final result = parser.parse('2026-07-19', _field(type: ForgeRecordFieldType.date, required: false));
      expect(result, isA<FieldParseSuccess>());
      expect((result as FieldParseSuccess).value, '2026-07-19');
    });
  });

  group('invalid date', () {
    test('19/07/2026(スラッシュ区切り)は無効', () {
      final result = parser.parse('19/07/2026', _field(type: ForgeRecordFieldType.date, required: false));
      expect(result, isA<FieldParseFailure>());
      expect((result as FieldParseFailure).reason, FieldParseFailureReason.invalidDate);
    });

    test('桁数が違う日付は無効', () {
      final result = parser.parse('26-7-19', _field(type: ForgeRecordFieldType.date, required: false));
      expect(result, isA<FieldParseFailure>());
    });
  });

  group('nonexistent date', () {
    test('2026-02-30(実在しない日付)は無効', () {
      final result = parser.parse('2026-02-30', _field(type: ForgeRecordFieldType.date, required: false));
      expect(result, isA<FieldParseFailure>());
      expect((result as FieldParseFailure).reason, FieldParseFailureReason.nonexistentDate);
    });

    test('2026-13-01(存在しない月)は無効', () {
      final result = parser.parse('2026-13-01', _field(type: ForgeRecordFieldType.date, required: false));
      expect(result, isA<FieldParseFailure>());
    });

    test('うるう年の2024-02-29は有効', () {
      final result = parser.parse('2024-02-29', _field(type: ForgeRecordFieldType.date, required: false));
      expect(result, isA<FieldParseSuccess>());
    });

    test('うるう年でない2026-02-29は無効', () {
      final result = parser.parse('2026-02-29', _field(type: ForgeRecordFieldType.date, required: false));
      expect(result, isA<FieldParseFailure>());
      expect((result as FieldParseFailure).reason, FieldParseFailureReason.nonexistentDate);
    });
  });

  group('valid boolean', () {
    test('parseBoolean(true)は成功する', () {
      final result = parser.parseBoolean(true);
      expect(result, isA<FieldParseSuccess>());
      expect((result as FieldParseSuccess).value, true);
    });

    test('parseBoolean(false)も成功する(false自体は失敗ではない)', () {
      final result = parser.parseBoolean(false);
      expect(result, isA<FieldParseSuccess>());
      expect((result as FieldParseSuccess).value, false);
    });
  });

  group('valid choice', () {
    test('optionsに含まれる値は成功する', () {
      final field = _field(type: ForgeRecordFieldType.choice, required: false, options: ['食費', '交通費', '娯楽']);
      final result = parser.parse('交通費', field);
      expect(result, isA<FieldParseSuccess>());
      expect((result as FieldParseSuccess).value, '交通費');
    });
  });

  group('invalid choice', () {
    test('optionsに含まれない値はinvalidChoiceで失敗する', () {
      final field = _field(type: ForgeRecordFieldType.choice, required: false, options: ['食費', '交通費', '娯楽']);
      final result = parser.parse('サブスク', field);
      expect(result, isA<FieldParseFailure>());
      expect((result as FieldParseFailure).reason, FieldParseFailureReason.invalidChoice);
    });

    test('optionsが空の場合、どんな値もinvalidChoiceになる', () {
      final field = _field(type: ForgeRecordFieldType.choice, required: false, options: []);
      final result = parser.parse('何か', field);
      expect(result, isA<FieldParseFailure>());
    });
  });

  group('required empty', () {
    test('required=trueで空文字はrequiredEmptyで失敗する', () {
      final field = _field(type: ForgeRecordFieldType.string, required: true);
      final result = parser.parse('', field);
      expect(result, isA<FieldParseFailure>());
      expect((result as FieldParseFailure).reason, FieldParseFailureReason.requiredEmpty);
    });

    test('required=falseで空文字はFieldParseEmptyになる(失敗ではない)', () {
      final field = _field(type: ForgeRecordFieldType.string, required: false);
      final result = parser.parse('', field);
      expect(result, isA<FieldParseEmpty>());
    });

    test('数値型でも、required=falseなら空文字は失敗ではない', () {
      final field = _field(type: ForgeRecordFieldType.number, required: false);
      final result = parser.parse('', field);
      expect(result, isA<FieldParseEmpty>());
    });
  });

  group('string type', () {
    test('string型は常にそのまま受け入れる', () {
      final result = parser.parse('アジ', _field(type: ForgeRecordFieldType.string, required: false));
      expect(result, isA<FieldParseSuccess>());
      expect((result as FieldParseSuccess).value, 'アジ');
    });
  });

  group('unknown type fallback', () {
    test('未知の型は文字列としてそのまま受け入れる(安全側のフォールバック)', () {
      const field = ForgeRecordSchemaField(
        name: 'f', type: ForgeRecordFieldType.unknown, label: 'F', required: false,
      );
      final result = parser.parse('何かの値', field);
      expect(result, isA<FieldParseSuccess>());
      expect((result as FieldParseSuccess).value, '何かの値');
    });
  });
}
