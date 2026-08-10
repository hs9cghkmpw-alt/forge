// ForgeStateStore Unit Test(FORGE-MILESTONE-003)。
//
// 指示書5章「State Store」の8項目を網羅する:
// 初期値取得・string更新・booleanのtoggle・string_list更新・checklist更新・
// 存在しないStateでもクラッシュしない・型不一致を安全に処理する・resetで初期値へ戻る。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/runtime/forge_state_store.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

void main() {
  group('初期値', () {
    test('コンストラクタに渡した初期値をreadで取得できる', () {
      final store = ForgeStateStore({
        'name': const ForgeStringState('太郎'),
        'agreed': const ForgeBooleanState(true),
      });
      expect(store.read('name'), '太郎');
      expect(store.read('agreed'), true);
    });

    test('contains: 存在するキーはtrue、存在しないキーはfalse', () {
      final store = ForgeStateStore({'x': const ForgeStringState('')});
      expect(store.contains('x'), isTrue);
      expect(store.contains('y'), isFalse);
    });
  });

  group('string更新', () {
    test('write()でstring値を更新できる', () {
      final store = ForgeStateStore({'note': const ForgeStringState('')});
      final ok = store.write('note', '新しいメモ');
      expect(ok, isTrue);
      expect(store.read('note'), '新しいメモ');
    });
  });

  group('booleanのtoggle', () {
    test('toggleBoolean()で反転する', () {
      final store = ForgeStateStore({'flag': const ForgeBooleanState(false)});
      expect(store.toggleBoolean('flag'), isTrue);
      expect(store.read('flag'), true);
      expect(store.toggleBoolean('flag'), isTrue);
      expect(store.read('flag'), false);
    });

    test('boolean以外へのtoggleBoolean()は失敗しfalseを返す', () {
      final store = ForgeStateStore({'note': const ForgeStringState('x')});
      expect(store.toggleBoolean('note'), isFalse);
      expect(store.read('note'), 'x', reason: '失敗時は値を変更しない');
    });
  });

  group('string_list更新', () {
    test('write()でstring_listを更新できる', () {
      final store = ForgeStateStore({'tags': const ForgeStringListState(['a'])});
      final ok = store.write('tags', ['a', 'b', 'c']);
      expect(ok, isTrue);
      expect(store.read('tags'), ['a', 'b', 'c']);
    });

    test('string以外を含むlistへのwriteは失敗する', () {
      final store = ForgeStateStore({'tags': const ForgeStringListState(['a'])});
      final ok = store.write('tags', ['a', 123, 'c']);
      expect(ok, isFalse);
      expect(store.read('tags'), ['a'], reason: '失敗時は元の値を保持する');
    });
  });

  group('checklist更新', () {
    test('addChecklistItem/toggleChecklistItem/deleteChecklistItemが動作する', () {
      final store = ForgeStateStore({
        'items': const ForgeChecklistState([]),
        'new_item_text': const ForgeStringState('牛乳'),
      });

      expect(store.addChecklistItem('items', 'new_item_text'), AddChecklistItemOutcome.added);
      var items = store.readChecklist('items');
      expect(items, hasLength(1));
      expect(items.first.text, '牛乳');
      expect(items.first.done, isFalse);
      expect(store.read('new_item_text'), '', reason: 'add後はsourceが空に戻る');

      final itemId = items.first.id;
      expect(store.toggleChecklistItem('items', itemId), isTrue);
      items = store.readChecklist('items');
      expect(items.first.done, isTrue);

      expect(store.deleteChecklistItem('items', itemId), isTrue);
      expect(store.readChecklist('items'), isEmpty);
    });

    // FORGE-MILESTONE-003.1 PHASE1/2: CEO実機で発見された add_item_failed の
    // 回帰テスト。「何も入力せず追加を押した」は正常操作であり、
    // targetMissing/sourceMissing(契約違反)とは明確に区別されるべき。
    test('sourceが空文字の場合はemptySourceを返す(契約違反ではない、正常操作)', () {
      final store = ForgeStateStore({
        'items': const ForgeChecklistState([]),
        'new_item_text': const ForgeStringState(''),
      });
      expect(store.addChecklistItem('items', 'new_item_text'), AddChecklistItemOutcome.emptySource);
      expect(store.readChecklist('items'), isEmpty, reason: '空文字では何も追加されない');
    });

    test('sourceが空白のみの場合もemptySourceを返す(trim後に判定する)', () {
      final store = ForgeStateStore({
        'items': const ForgeChecklistState([]),
        'new_item_text': const ForgeStringState('   '),
      });
      expect(store.addChecklistItem('items', 'new_item_text'), AddChecklistItemOutcome.emptySource);
    });

    test('targetがchecklist型で存在しない場合はtargetMissingを返す', () {
      final store = ForgeStateStore({
        'new_item_text': const ForgeStringState('牛乳'),
      });
      expect(store.addChecklistItem('items', 'new_item_text'), AddChecklistItemOutcome.targetMissing);
    });

    test('sourceがstring型で存在しない場合はsourceMissingを返す', () {
      final store = ForgeStateStore({
        'items': const ForgeChecklistState([]),
      });
      expect(store.addChecklistItem('items', 'new_item_text'), AddChecklistItemOutcome.sourceMissing);
    });

    test('targetの型がchecklistでない場合はtargetMissingを返す(型不一致)', () {
      final store = ForgeStateStore({
        'items': const ForgeStringState('checklistのはずが違う型'),
        'new_item_text': const ForgeStringState('牛乳'),
      });
      expect(store.addChecklistItem('items', 'new_item_text'), AddChecklistItemOutcome.targetMissing);
    });
  });

  group('存在しないStateでもクラッシュしない', () {
    test('read()は存在しないキーに対しnullを返す(例外を投げない)', () {
      final store = ForgeStateStore(<String, ForgeStateValue>{});
      expect(() => store.read('does_not_exist'), returnsNormally);
      expect(store.read('does_not_exist'), isNull);
    });

    test('toggleBoolean/resetは存在しないキーでfalseを返す', () {
      final store = ForgeStateStore(<String, ForgeStateValue>{});
      expect(store.toggleBoolean('missing'), isFalse);
      expect(store.reset('missing'), isFalse);
    });

    test('addChecklistItemは両方とも存在しないキーでtargetMissingを返す', () {
      final store = ForgeStateStore(<String, ForgeStateValue>{});
      expect(store.addChecklistItem('missing_target', 'missing_source'), AddChecklistItemOutcome.targetMissing);
    });
  });

  group('型不一致を安全に処理する', () {
    test('string型のキーへbooleanをwriteすると失敗する(型を変えない)', () {
      final store = ForgeStateStore({'note': const ForgeStringState('x')});
      final ok = store.write('note', true);
      expect(ok, isFalse);
      expect(store.read('note'), 'x');
    });

    test('boolean型のキーへstringをwriteすると失敗する', () {
      final store = ForgeStateStore({'flag': const ForgeBooleanState(false)});
      final ok = store.write('flag', 'not a bool');
      expect(ok, isFalse);
      expect(store.read('flag'), false);
    });
  });

  group('resetで初期値へ戻る', () {
    test('write後にreset()すると、コンストラクタに渡した初期値へ戻る', () {
      final store = ForgeStateStore({'note': const ForgeStringState('初期値')});
      store.write('note', '変更後の値');
      expect(store.read('note'), '変更後の値');

      final ok = store.reset('note');
      expect(ok, isTrue);
      expect(store.read('note'), '初期値');
    });

    test('複数回writeしても、resetは常に最初の初期値へ戻す(直近値ではない)', () {
      final store = ForgeStateStore({'n': const ForgeStringState('A')});
      store.write('n', 'B');
      store.write('n', 'C');
      store.reset('n');
      expect(store.read('n'), 'A');
    });
  });
}
