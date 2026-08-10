// ForgeDesignTokens parsing test(FORGE v1.0 Product Quality Sprint1)。
//
// design_tokensのparse・保持・型取得をカバーする。実行未検証
// (Claudeのサンドボックスに Dart SDK が無い)。

import 'package:flutter/material.dart' show Color;
import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

void main() {
  group('design_tokens parse', () {
    test('color_scheme/corner_radius/spacing_scaleが正しく解析される', () {
      final tokens = ForgeDesignTokens.fromJson({
        'color_scheme': {'primary': '#6366F1', 'secondary': '#8B5CF6'},
        'corner_radius': {'small': 8, 'medium': 12, 'large': 20},
        'spacing_scale': {'xs': 4, 'md': 16},
      }, '/design_tokens');

      expect(tokens.colorScheme['primary'], const Color(0xFF6366F1));
      expect(tokens.colorScheme['secondary'], const Color(0xFF8B5CF6));
      expect(tokens.cornerRadius['medium'], 12.0);
      expect(tokens.spacingScale['xs'], 4.0);
    });

    test('不正な16進数の色は無視され、他の色はそのまま解析される', () {
      final tokens = ForgeDesignTokens.fromJson({
        'color_scheme': {'primary': '#6366F1', 'secondary': 'not-a-color'},
      }, '/design_tokens');
      expect(tokens.colorScheme.containsKey('primary'), isTrue);
      expect(tokens.colorScheme.containsKey('secondary'), isFalse);
    });

    test('空のdesign_tokensも安全に解析できる(全キー省略)', () {
      final tokens = ForgeDesignTokens.fromJson({}, '/design_tokens');
      expect(tokens.colorScheme, isEmpty);
      expect(tokens.cornerRadius, isEmpty);
      expect(tokens.spacingScale, isEmpty);
    });
  });

  group('colorOr/radiusOr', () {
    test('存在するroleはその値を返す', () {
      final tokens = ForgeDesignTokens.fromJson({
        'color_scheme': {'primary': '#000000'},
      }, '/design_tokens');
      expect(tokens.colorOr('primary', const Color(0xFFFFFFFF)), const Color(0xFF000000));
    });

    test('存在しないroleはfallbackを返す', () {
      final tokens = ForgeDesignTokens.fromJson({}, '/design_tokens');
      expect(tokens.colorOr('primary', const Color(0xFFFFFFFF)), const Color(0xFFFFFFFF));
      expect(tokens.radiusOr('medium', 20), 20.0);
    });
  });

  group('ForgeDocument経由でのdesign_tokens parse', () {
    test('design_tokensを含む文書は、ForgeDocument.designTokensへ格納される', () {
      final doc = ForgeDocument.fromJson({
        'version': '1.5',
        'initial_screen_id': 's1',
        'design_tokens': {
          'color_scheme': {'primary': '#5B7C99'},
        },
        'screens': [
          {'id': 's1', 'title': 'S1', 'state': {}, 'body': {'type': 'text', 'id': 't1', 'value': 'x'}},
        ],
      });
      expect(doc.designTokens, isNotNull);
      expect(doc.designTokens!.colorScheme['primary'], const Color(0xFF5B7C99));
    });

    test('design_tokensが無い文書ではdesignTokensがnullになる(Legacy fallback)', () {
      final doc = ForgeDocument.fromJson({
        'version': '1.4',
        'initial_screen_id': 's1',
        'screens': [
          {'id': 's1', 'title': 'S1', 'state': {}, 'body': {'type': 'text', 'id': 't1', 'value': 'x'}},
        ],
      });
      expect(doc.designTokens, isNull);
    });
  });

  group('section_header parse', () {
    test('titleのみのsection_headerを解析できる', () {
      final doc = ForgeDocument.fromJson({
        'version': '1.5', 'initial_screen_id': 's1',
        'screens': [
          {'id': 's1', 'title': 'S1', 'state': {},
           'body': {'type': 'section_header', 'id': 'sec1', 'title': '記録の追加'}},
        ],
      });
      final node = doc.screens.first.body as ForgeSectionHeaderWidgetNode;
      expect(node.title, '記録の追加');
      expect(node.subtitle, isNull);
    });

    test('title欠落はForgeParseExceptionを送出する', () {
      expect(
        () => ForgeDocument.fromJson({
          'version': '1.5', 'initial_screen_id': 's1',
          'screens': [
            {'id': 's1', 'title': 'S1', 'state': {}, 'body': {'type': 'section_header', 'id': 'sec1'}},
          ],
        }),
        throwsA(isA<ForgeParseException>()),
      );
    });
  });

  group('record_list_view grid layout parse', () {
    test('layout: "grid"を正しく解析する', () {
      final doc = ForgeDocument.fromJson({
        'version': '1.5', 'initial_screen_id': 's1',
        'screens': [
          {
            'id': 's1', 'title': 'S1',
            'state': {'records': {'type': 'record_list', 'value': []}},
            'body': {'type': 'record_list_view', 'id': 'rlv1', 'state_ref': 'records', 'layout': 'grid'},
          },
        ],
      });
      final node = doc.screens.first.body as ForgeRecordListViewWidgetNode;
      expect(node.layout, 'grid');
    });

    test('layout省略時は既定で"card"になる(後方互換)', () {
      final doc = ForgeDocument.fromJson({
        'version': '1.4', 'initial_screen_id': 's1',
        'screens': [
          {
            'id': 's1', 'title': 'S1',
            'state': {'records': {'type': 'record_list', 'value': []}},
            'body': {'type': 'record_list_view', 'id': 'rlv1', 'state_ref': 'records'},
          },
        ],
      });
      final node = doc.screens.first.body as ForgeRecordListViewWidgetNode;
      expect(node.layout, 'card');
    });
  });
}
