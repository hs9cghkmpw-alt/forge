/// Deterministic Mock Generator v2(Dart版、FORGE-MILESTONE-002 PHASE5)。
///
/// Python版(backend/app/ai/generators/mock_generator.py)と同じく、
/// 「Category判定」と「Template実行」を分離した。カテゴリ・キーワード・
/// 判定順序をPython版と完全に一致させている
/// (docs/spec/MOCK_GENERATOR_CONTRACT.md 参照)。
library;

import 'templates.dart';

typedef _Builder = Map<String, dynamic> Function();

class _Category {
  final List<String> keywords;
  final _Builder build;
  const _Category(this.keywords, this.build);
}

_Builder _checklist(String title, List<String> items) {
  return () => buildChecklistTemplate(ChecklistTemplateParams(title: title, items: items));
}

// 判定順が重要。Python版と完全に同じ順序を維持すること
// (docs/spec/MOCK_GENERATOR_CONTRACT.md)。
final List<_Category> _kCategories = [
  _Category(['買い物', 'スーパー', '食材', 'shopping'],
      _checklist('買い物メモ', ['卵', '牛乳', '食パン', '野菜', '洗剤'])),
  _Category(['todo', 'タスク', 'やること', '仕事'],
      _checklist('Todo', ['メールを返す', '資料を準備する', '打ち合わせに出る'])),
  _Category(['ご飯', '晩ご飯', '夕食', '献立'],
      _checklist('今日のご飯メモ', ['主菜を決める', '副菜を決める', '足りない食材を確認する', '買い出しに行く'])),
  _Category(['家計簿', '家計', '貯金', '支出'],
      _checklist('家計簿', ['今月の収入を記録する', '固定費を確認する', '今日の支出を記録する', '来月の予算を立てる'])),
  _Category(['予定', 'スケジュール', 'schedule'],
      _checklist('今日の予定', ['午前のタスクを確認する', '午後のタスクを確認する', '夜までにやることを確認する'])),
  _Category(['子ども', 'こども', '子供'],
      _checklist('子どもの持ち物チェック', ['着替え', 'オムツ', '水筒', 'タオル', 'お気に入りのおもちゃ'])),
  _Category(['ペット', 'pet'],
      _checklist('ペットのお世話チェック', ['ごはん', 'お水の交換', '散歩', 'トイレ掃除'])),
  _Category(['プレゼント', 'ギフト', 'gift'],
      _checklist('プレゼントのアイデア', ['予算を決める', '候補を3つ挙げる', '相手の好みを思い出す'])),
  _Category(['家事', '片付け', 'そうじ', '掃除'],
      _checklist('今日の家事', ['掃除機をかける', '洗濯をする', '食器を洗う', 'ゴミ出しをする'])),
  _Category(['旅行', '持ち物', 'パッキング', '出張'],
      _checklist('旅行の持ち物チェック', ['パスポート', '充電器', '着替え', '歯ブラシ', '常備薬'])),
  _Category(['アンケート', 'survey', '満足度'], () {
    // FORGE-MILESTONE-002.1 Task 1: title/questionsとも実行時に変わらない
    // compile-time constantのため、const化してprefer_const_constructorsに対応した
    // (呼び出しのたびに新規インスタンスを作らずに済む、実際の性能改善でもある)。
    return buildFormTemplate(const FormTemplateParams(
      title: '満足度アンケート',
      questions: <FormQuestion>[
        FormQuestion(key: 'q_satisfied', label: '今回のサービスに満足しましたか', kind: FormQuestionKind.checkbox),
        FormQuestion(key: 'q_recommend', label: '友人に勧めたいと思いますか', kind: FormQuestionKind.checkbox),
        FormQuestion(key: 'q_comment', label: 'ご意見・ご感想（任意）', kind: FormQuestionKind.text),
      ],
    ));
  }),
  _Category(['メモ', 'memo', 'ノート'], () => buildMemoTemplate(const MemoTemplateParams(title: 'メモ'))),
];

class MockGenerationDataSource {
  const MockGenerationDataSource();

  Map<String, dynamic> generate(String rawInput) {
    final text = rawInput.trim();
    final lower = text.toLowerCase();

    final builder = _matchCategory(lower);
    if (builder != null) {
      return builder();
    }

    final title = text.isNotEmpty ? text : '新しいリスト';
    return buildChecklistTemplate(ChecklistTemplateParams(title: title, items: const ['最初のアイテム']));
  }

  _Builder? _matchCategory(String lowerText) {
    for (final category in _kCategories) {
      if (category.keywords.any((keyword) => lowerText.contains(keyword))) {
        return category.build;
      }
    }
    return null;
  }
}
