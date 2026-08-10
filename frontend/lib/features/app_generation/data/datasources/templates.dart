/// Forge Template System(Dart版、FORGE-MILESTONE-002 PHASE4)。
///
/// Python版(backend/app/ai/generators/templates/)と同じ3つの構造Template
/// (Checklist/Memo/Form)を提供する。出力するJSON構造はPython版と完全に
/// 一致させている(docs/spec/MOCK_GENERATOR_CONTRACT.md参照)。
library;

class ChecklistTemplateParams {
  final String title;
  final List<String> items;
  const ChecklistTemplateParams({required this.title, required this.items});
}

Map<String, dynamic> buildChecklistTemplate(ChecklistTemplateParams params) {
  final checklistItems = [
    for (var i = 0; i < params.items.length; i++)
      {'id': 'item_${i + 1}', 'text': params.items[i], 'done': false},
  ];
  return {
    'version': '1.0',
    'app': {'title': params.title},
    'initial_screen_id': 'generated_screen',
    'screens': [
      {
        'id': 'generated_screen',
        'title': params.title,
        'state': {
          'new_item_text': {'type': 'string', 'value': ''},
          'items': {'type': 'checklist', 'value': checklistItems},
        },
        'body': {
          'type': 'column',
          'id': 'root_column',
          'children': [
            {
              'type': 'checklist',
              'id': 'list_view',
              'state_ref': 'items',
              'empty_state_text': 'アイテムはまだないよ',
            },
            {
              'type': 'row',
              'id': 'add_row',
              'children': [
                {
                  'type': 'text_field',
                  'id': 'add_field',
                  'state_ref': 'new_item_text',
                  'placeholder': 'アイテムを追加',
                },
                {
                  'type': 'button',
                  'id': 'add_button',
                  'label': '追加',
                  'action': {
                    'type': 'add_item',
                    'target_state_ref': 'items',
                    'source_state_ref': 'new_item_text',
                  },
                },
              ],
            },
          ],
        },
      },
    ],
  };
}

class MemoTemplateParams {
  final String title;
  final String placeholder;
  const MemoTemplateParams({required this.title, this.placeholder = 'ここに書く'});
}

Map<String, dynamic> buildMemoTemplate(MemoTemplateParams params) {
  return {
    'version': '1.1',
    'app': {'title': params.title},
    'initial_screen_id': 'generated_screen',
    'screens': [
      {
        'id': 'generated_screen',
        'title': params.title,
        'state': {
          'note': {'type': 'string', 'value': ''},
        },
        'body': {
          'type': 'column',
          'id': 'root_column',
          'children': [
            {'type': 'heading', 'id': 'heading1', 'value': params.title, 'level': 1},
            {
              'type': 'text_field',
              'id': 'note_field',
              'state_ref': 'note',
              'placeholder': params.placeholder,
            },
          ],
        },
      },
    ],
  };
}

enum FormQuestionKind { text, checkbox }

class FormQuestion {
  final String key;
  final String label;
  final FormQuestionKind kind;
  const FormQuestion({required this.key, required this.label, required this.kind});
}

class FormTemplateParams {
  final String title;
  final List<FormQuestion> questions;
  final String thanksMessage;
  const FormTemplateParams({
    required this.title,
    required this.questions,
    this.thanksMessage = 'ご協力ありがとうございました。',
  });
}

Map<String, dynamic> buildFormTemplate(FormTemplateParams params) {
  final state = <String, dynamic>{};
  final questionWidgets = <Map<String, dynamic>>[];

  for (final q in params.questions) {
    if (q.kind == FormQuestionKind.checkbox) {
      state[q.key] = {'type': 'boolean', 'value': false};
      questionWidgets.add({'type': 'checkbox', 'id': '${q.key}_input', 'label': q.label, 'state_ref': q.key});
    } else {
      state[q.key] = {'type': 'string', 'value': ''};
      questionWidgets.add({
        'type': 'text_field', 'id': '${q.key}_input', 'state_ref': q.key, 'placeholder': q.label,
        // FORGE-MILESTONE-003: Python版(form_template.py)と揃えたvalidation。
        'validation': {
          'rules': [
            {'type': 'max_length', 'value': 200, 'message': '200文字以内でお願いします'},
          ],
        },
      });
    }
  }

  final mainScreen = {
    'id': 'generated_screen',
    'title': params.title,
    'state': state,
    'body': {
      'type': 'column',
      'id': 'root_column',
      'children': [
        {'type': 'heading', 'id': 'heading1', 'value': params.title, 'level': 1},
        {
          'type': 'card',
          'id': 'form_card',
          'children': [
            {
              'type': 'form',
              'id': 'main_form',
              'children': questionWidgets,
              'submit_label': '送信する',
              'submit_action': {'type': 'navigate', 'target_screen_id': 'thanks_screen'},
            },
          ],
        },
      ],
    },
  };

  final thanksScreen = {
    'id': 'thanks_screen',
    'title': '送信完了',
    'state': <String, dynamic>{},
    'body': {
      'type': 'column',
      'id': 'thanks_root',
      'children': [
        {'type': 'heading', 'id': 'thanks_heading', 'value': '送信完了', 'level': 1},
        {'type': 'text', 'id': 'thanks_text', 'value': params.thanksMessage},
        {
          'type': 'button', 'id': 'back_button', 'label': '戻る',
          'action': {'type': 'go_back'},
        },
      ],
    },
  };

  return {
    // FORGE-MILESTONE-003: コメント欄にvalidationを追加したため1.1→1.2。
    'version': '1.2',
    'app': {'title': params.title},
    'initial_screen_id': 'generated_screen',
    'screens': [mainScreen, thanksScreen],
  };
}
