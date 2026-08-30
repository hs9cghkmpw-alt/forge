import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

void main() {
  test('ForgeDocument parses top-level GA-1 logic', () {
    final document = ForgeDocument.fromJson({
      'version': '1.15',
      'initial_screen_id': 's',
      'screens': [
        {
          'id': 's',
          'title': 'T',
          'state': <String, dynamic>{},
          'body': {'type': 'column', 'id': 'root', 'children': <dynamic>[]},
        },
      ],
      'logic': {
        'derived': {
          'balance': {'kind': 'literal', 'value': 10},
        },
        'visible_when': {
          'warning': {'kind': 'literal', 'value': false},
        },
      },
    });

    expect(document.logic.derived['balance']?['value'], 10);
    expect(document.logic.visibleWhen['warning']?['value'], isFalse);
  });

  test('legacy document receives empty logic', () {
    final document = ForgeDocument.fromJson({
      'version': '1.15',
      'initial_screen_id': 's',
      'screens': [
        {
          'id': 's',
          'title': 'T',
          'state': <String, dynamic>{},
          'body': {'type': 'column', 'id': 'root', 'children': <dynamic>[]},
        },
      ],
    });
    expect(document.logic.derived, isEmpty);
    expect(document.logic.visibleWhen, isEmpty);
  });
}
