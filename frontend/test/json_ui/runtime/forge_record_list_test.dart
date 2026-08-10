// ForgeStateStore.addRecord() Unit Test(FORGE v0.7 Record Runtime Phase1)。
//
// 指示書「Runtime Test」節の4項目を網羅する:
// add_recordで1件追加される・2件追加できる・Field順が保持される・
// 空一覧から開始できる。
//
// 注記: Claudeのサンドボックスに Dart SDK が無いため、このファイルは
// 一度も `flutter test` で実行されていない。CEO環境での実行が必須。

import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/json_ui/runtime/forge_state_store.dart';
import 'package:forge_app/json_ui/schema/forge_document.dart';

void main() {
  group('空一覧から開始できる', () {
    test('record_list型のstateを空配列で初期化し、readRecordListで空を取得できる', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([]),
      });
      expect(store.readRecordList('records'), isEmpty);
    });
  });

  group('add_recordで1件追加される', () {
    test('field_bindingsの現在値が1つのRecordとしてtargetへ追加される', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([]),
        'field_species': const ForgeStringState('アジ'),
        'field_size': const ForgeStringState('30'),
      });

      final outcome = store.addRecord('records', {
        'species': 'field_species',
        'size': 'field_size',
      });

      expect(outcome, AddRecordOutcome.added);
      final records = store.readRecordList('records');
      expect(records, hasLength(1));
      expect(records.first.fields['species'], 'アジ');
      expect(records.first.fields['size'], '30');
      expect(records.first.id, isNotEmpty);
    });

    test('数値・真偽値型のsourceもFieldとして正しく取り込まれる', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([]),
        'field_amount': const ForgeNumberState(1200),
        'field_is_paid': const ForgeBooleanState(true),
      });

      final outcome = store.addRecord('records', {
        'amount': 'field_amount',
        'is_paid': 'field_is_paid',
      });

      expect(outcome, AddRecordOutcome.added);
      final record = store.readRecordList('records').first;
      expect(record.fields['amount'], 1200.0);
      expect(record.fields['is_paid'], isTrue);
    });
  });

  group('2件追加できる', () {
    test('add_recordを2回呼ぶと、既存の1件目を残したまま2件目が追加される', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([]),
        'field_species': const ForgeStringState('アジ'),
      });

      expect(store.addRecord('records', {'species': 'field_species'}), AddRecordOutcome.added);
      // 2件目を追加する前に、sourceの値を更新する(実際のUIでは
      // reset_state+ユーザーの再入力に相当)。
      store.writeTyped('field_species', const ForgeStringState('サバ'));
      expect(store.addRecord('records', {'species': 'field_species'}), AddRecordOutcome.added);

      final records = store.readRecordList('records');
      expect(records, hasLength(2));
      expect(records[0].fields['species'], 'アジ');
      expect(records[1].fields['species'], 'サバ');
      // 2件のidが重複しないこと。
      expect(records[0].id, isNot(equals(records[1].id)));
    });
  });

  group('Field順が保持される', () {
    test('field_bindingsに渡した順序で、Recordのfieldsが構築される', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([]),
        'field_species': const ForgeStringState('アジ'),
        'field_size': const ForgeStringState('30'),
        'field_weight': const ForgeStringState('200'),
        'field_location': const ForgeStringState('東京湾'),
      });

      // Dartの Map リテラルは挿入順を保持する(LinkedHashMap)ため、
      // field_bindingsの記述順がそのままfields.keysの順序になることを確認する。
      final outcome = store.addRecord('records', {
        'species': 'field_species',
        'size': 'field_size',
        'weight': 'field_weight',
        'location': 'field_location',
      });

      expect(outcome, AddRecordOutcome.added);
      final record = store.readRecordList('records').first;
      expect(record.fields.keys.toList(), ['species', 'size', 'weight', 'location']);
    });
  });

  group('存在しないStateでもクラッシュしない', () {
    test('targetがrecord_list型で存在しない場合はtargetMissingを返す', () {
      final store = ForgeStateStore({
        'field_species': const ForgeStringState('アジ'),
      });
      expect(
        store.addRecord('does_not_exist', {'species': 'field_species'}),
        AddRecordOutcome.targetMissing,
      );
    });

    test('targetの型がrecord_listでない場合はtargetMissingを返す(型不一致)', () {
      final store = ForgeStateStore({
        'records': const ForgeChecklistState([]), // わざと違う型
        'field_species': const ForgeStringState('アジ'),
      });
      expect(
        store.addRecord('records', {'species': 'field_species'}),
        AddRecordOutcome.targetMissing,
      );
    });

    test('field_bindingsのsourceが存在しない場合はsourceMissingを返す', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([]),
      });
      expect(
        store.addRecord('records', {'species': 'does_not_exist'}),
        AddRecordOutcome.sourceMissing,
      );
    });

    test('field_bindingsのsourceがrecord_list等の複合型の場合はsourceMissingを返す', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([]),
        'field_species': const ForgeChecklistState([]), // 単一値として使えない型
      });
      expect(
        store.addRecord('records', {'species': 'field_species'}),
        AddRecordOutcome.sourceMissing,
      );
    });

    test('sourceMissingの場合、target(records)は変更されない', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([]),
        'field_species': const ForgeStringState('アジ'),
      });
      store.addRecord('records', {
        'species': 'field_species',
        'size': 'does_not_exist', // 2番目のbindingが無効
      });
      expect(store.readRecordList('records'), isEmpty, reason: '一部でも失敗したら全体を追加しない');
    });
  });

  group('read()の共通APIからもrecord_listを取得できる', () {
    test('read()はList<ForgeRecordItem>を返す', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([]),
        'field_species': const ForgeStringState('アジ'),
      });
      store.addRecord('records', {'species': 'field_species'});
      final value = store.read('records');
      expect(value, isA<List<ForgeRecordItem>>());
      expect((value as List<ForgeRecordItem>).first.fields['species'], 'アジ');
    });
  });

  // --- FORGE v0.8(Record Runtime Phase2)+ FORGE v0.8.1(Hardening):
  //     select / update / delete ---

  group('selectできる', () {
    test('sourceのRecordをtargetのselected_recordへ設定する', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([
          ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'}),
        ]),
        'selected': const ForgeSelectedRecordState(null),
      });
      final outcome = store.selectRecord('records', 'selected', 'rec_1', const {});
      expect(outcome, RecordOperationOutcome.success);
      final selected = store.readSelectedRecord('selected');
      expect(selected, isNotNull);
      expect(selected!.fields['species'], 'アジ');
    });

    test('field_bindingsに従って編集用フィールドへ値が反映される', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([
          ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ', 'size': '30'}),
        ]),
        'selected': const ForgeSelectedRecordState(null),
        'edit_field_species': const ForgeStringState(''),
        'edit_field_size': const ForgeStringState(''),
      });
      store.selectRecord('records', 'selected', 'rec_1', const {
        'species': 'edit_field_species',
        'size': 'edit_field_size',
      });
      expect(store.read('edit_field_species'), 'アジ');
      expect(store.read('edit_field_size'), '30');
    });

    test('sourceがrecord_list型で存在しない場合はtargetStateNotFoundを返す', () {
      final store = ForgeStateStore({'selected': const ForgeSelectedRecordState(null)});
      final outcome = store.selectRecord('records', 'selected', 'rec_1', const {});
      expect(outcome, RecordOperationOutcome.targetStateNotFound);
    });

    test('targetがselected_record型で存在しない場合はtargetStateNotFoundを返す', () {
      final store = ForgeStateStore({'records': const ForgeRecordListState([])});
      final outcome = store.selectRecord('records', 'selected', 'rec_1', const {});
      expect(outcome, RecordOperationOutcome.targetStateNotFound);
    });

    test('targetのキーは存在するが型が違う場合はtargetStateTypeMismatchを返す', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([]),
        'selected': const ForgeStringState(''), // わざと違う型
      });
      final outcome = store.selectRecord('records', 'selected', 'rec_1', const {});
      expect(outcome, RecordOperationOutcome.targetStateTypeMismatch);
    });

    test('存在しないidを選択しようとするとrecordNotFoundを返す', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([]),
        'selected': const ForgeSelectedRecordState(null),
      });
      final outcome = store.selectRecord('records', 'selected', 'does_not_exist', const {});
      expect(outcome, RecordOperationOutcome.recordNotFound);
    });
  });

  // --- FORGE v0.8.1(Hardening)の核心: Select操作のAtomicity ---

  group('Bindingが全件成功した場合のみ選択状態が更新される', () {
    test('field_bindingsが全て有効な場合、selected_recordと編集Fieldがまとめて更新される', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([
          ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ', 'size': '30'}),
        ]),
        'selected': const ForgeSelectedRecordState(null),
        'edit_field_species': const ForgeStringState(''),
        'edit_field_size': const ForgeStringState(''),
      });
      final outcome = store.selectRecord('records', 'selected', 'rec_1', const {
        'species': 'edit_field_species',
        'size': 'edit_field_size',
      });
      expect(outcome, RecordOperationOutcome.success);
      expect(store.readSelectedRecord('selected')?.id, 'rec_1');
      expect(store.read('edit_field_species'), 'アジ');
      expect(store.read('edit_field_size'), '30');
    });
  });

  group('1件のBinding失敗で全Stateが変更されない', () {
    test('field_bindingsの宛先が1件でも存在しない場合、選択自体も含めて何も変更されない', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([
          ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ', 'size': '30'}),
        ]),
        'selected': const ForgeSelectedRecordState(null),
        'edit_field_species': const ForgeStringState(''),
        // edit_field_sizeを意図的に用意しない(宛先が存在しない状況を再現)。
      });
      final outcome = store.selectRecord('records', 'selected', 'rec_1', const {
        'species': 'edit_field_species',
        'size': 'edit_field_size',
      });
      expect(outcome, RecordOperationOutcome.invalidBinding);
      expect(store.readSelectedRecord('selected'), isNull, reason: '選択自体も行われないこと(Atomicity)');
      expect(store.read('edit_field_species'), '', reason: '一部成功していた側も反映されないこと');
    });

    test('field_bindingsが参照するRecord側のFieldが存在しない場合もinvalidBindingで、何も変更しない', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([
          ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'}), // sizeを持たない
        ]),
        'selected': const ForgeSelectedRecordState(null),
        'edit_field_species': const ForgeStringState(''),
        'edit_field_size': const ForgeStringState(''),
      });
      final outcome = store.selectRecord('records', 'selected', 'rec_1', const {
        'species': 'edit_field_species',
        'size': 'edit_field_size', // Recordがsizeを持たない
      });
      expect(outcome, RecordOperationOutcome.invalidBinding);
      expect(store.readSelectedRecord('selected'), isNull);
      expect(store.read('edit_field_species'), '');
    });

    test('宛先の型がstring型でない場合もinvalidBindingで、何も変更しない', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([
          ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'}),
        ]),
        'selected': const ForgeSelectedRecordState(null),
        'edit_field_species': const ForgeBooleanState(false), // わざと違う型
      });
      final outcome = store.selectRecord('records', 'selected', 'rec_1', const {
        'species': 'edit_field_species',
      });
      expect(outcome, RecordOperationOutcome.invalidBinding);
      expect(store.readSelectedRecord('selected'), isNull);
    });
  });

  group('前回選択したRecordの編集値が残らない', () {
    test('Record Aを選択後、Record Bを選択すると編集Fieldは完全にBの値へ置き換わる', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([
          ForgeRecordItem(id: 'rec_a', fields: {'species': 'アジ', 'size': '30'}),
          ForgeRecordItem(id: 'rec_b', fields: {'species': 'サバ', 'size': '25'}),
        ]),
        'selected': const ForgeSelectedRecordState(null),
        'edit_field_species': const ForgeStringState(''),
        'edit_field_size': const ForgeStringState(''),
      });
      const bindings = {'species': 'edit_field_species', 'size': 'edit_field_size'};

      store.selectRecord('records', 'selected', 'rec_a', bindings);
      expect(store.read('edit_field_species'), 'アジ');
      expect(store.read('edit_field_size'), '30');

      store.selectRecord('records', 'selected', 'rec_b', bindings);
      expect(store.read('edit_field_species'), 'サバ', reason: 'Aの値が残っていないこと');
      expect(store.read('edit_field_size'), '25', reason: 'Aの値が残っていないこと');
      expect(store.readSelectedRecord('selected')?.id, 'rec_b');
    });
  });

  group('Record A選択後、Record Bの選択失敗から誤更新できない', () {
    test('Aを選択後、Bの選択がinvalidBindingで失敗しても、選択状態はAのまま維持される', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([
          ForgeRecordItem(id: 'rec_a', fields: {'species': 'アジ'}),
          ForgeRecordItem(id: 'rec_b', fields: {'species': 'サバ'}), // 'size'を持たない
        ]),
        'selected': const ForgeSelectedRecordState(null),
        'edit_field_species': const ForgeStringState(''),
      });

      // Aを選択(成功)。
      expect(
        store.selectRecord('records', 'selected', 'rec_a', const {'species': 'edit_field_species'}),
        RecordOperationOutcome.success,
      );
      expect(store.read('edit_field_species'), 'アジ');

      // Bの選択を試みるが、'size'のbindingが存在しないFieldを参照しているため失敗する。
      final outcome = store.selectRecord('records', 'selected', 'rec_b', const {
        'species': 'edit_field_species',
        'size': 'does_not_exist_on_record_b',
      });
      expect(outcome, RecordOperationOutcome.invalidBinding);

      // 失敗後も、選択状態・編集Fieldは直前のA選択時のまま(Bへ書き換わっていない)。
      expect(store.readSelectedRecord('selected')?.id, 'rec_a', reason: '選択はAのまま維持される');
      expect(store.read('edit_field_species'), 'アジ', reason: '編集Fieldも書き換わっていない');

      // この状態で更新すると、Aが正しく更新される(Bの内容が誤って混ざらない)。
      store.writeTyped('edit_field_species', const ForgeStringState('イワシ'));
      final updateOutcome = store.updateRecord('records', 'selected', const {'species': 'edit_field_species'});
      expect(updateOutcome, RecordOperationOutcome.success);
      final records = store.readRecordList('records');
      expect(records.firstWhere((r) => r.id == 'rec_a').fields['species'], 'イワシ');
      expect(records.firstWhere((r) => r.id == 'rec_b').fields['species'], 'サバ', reason: 'Bは変更されていない');
    });
  });

  group('updateできる', () {
    test('選択中のRecordのFieldをfield_bindingsの現在値で丸ごと置き換える', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([
          ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ', 'size': '30'}),
        ]),
        'selected': const ForgeSelectedRecordState(ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'})),
        'edit_field_species': const ForgeStringState('サバ'),
        'edit_field_size': const ForgeStringState('25'),
      });
      final outcome = store.updateRecord('records', 'selected', {
        'species': 'edit_field_species',
        'size': 'edit_field_size',
      });
      expect(outcome, RecordOperationOutcome.success);
      final records = store.readRecordList('records');
      expect(records, hasLength(1), reason: '件数は変わらない');
      expect(records.first.id, 'rec_1', reason: 'idは維持される');
      expect(records.first.fields['species'], 'サバ');
      expect(records.first.fields['size'], '25');
    });

    test('無選択で更新しようとするとnoSelectionを返す(正常操作、失敗にしない)', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([
          ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'}),
        ]),
        'selected': const ForgeSelectedRecordState(null),
        'edit_field_species': const ForgeStringState('サバ'),
      });
      final outcome = store.updateRecord('records', 'selected', {'species': 'edit_field_species'});
      expect(outcome, RecordOperationOutcome.noSelection);
      expect(store.readRecordList('records').first.fields['species'], 'アジ', reason: '更新されていないこと');
    });
  });

  group('update後に一覧・selected_record・編集Fieldが一致する', () {
    test('更新成功直後、record_listとselected_recordの内容が完全に一致する', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([
          ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'}),
        ]),
        'selected': const ForgeSelectedRecordState(ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'})),
        'edit_field_species': const ForgeStringState('サバ'),
      });
      final outcome = store.updateRecord('records', 'selected', const {'species': 'edit_field_species'});
      expect(outcome, RecordOperationOutcome.success);

      final listRecord = store.readRecordList('records').first;
      final selectedRecord = store.readSelectedRecord('selected');
      expect(selectedRecord, isNotNull);
      expect(selectedRecord!.fields['species'], 'サバ', reason: 'selected_recordが更新前の値のまま残っていないこと');
      expect(selectedRecord.fields, listRecord.fields, reason: '一覧とselected_recordの内容が一致すること');
      expect(selectedRecord.id, listRecord.id);
    });
  });

  group('存在しないrecord更新失敗', () {
    test('選択中のidが実際にはtargetに存在しない場合、recordNotFoundを返す', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([]), // 空(選択後に別操作で削除された想定)
        'selected': const ForgeSelectedRecordState(ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'})),
        'edit_field_species': const ForgeStringState('サバ'),
      });
      final outcome = store.updateRecord('records', 'selected', {'species': 'edit_field_species'});
      expect(outcome, RecordOperationOutcome.recordNotFound);
    });
  });

  group('deleteできる', () {
    test('選択中のRecordがrecord_listから削除される', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([
          ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'}),
          ForgeRecordItem(id: 'rec_2', fields: {'species': 'サバ'}),
        ]),
        'selected': const ForgeSelectedRecordState(ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'})),
      });
      final outcome = store.deleteRecord('records', 'selected');
      expect(outcome, RecordOperationOutcome.success);
      final records = store.readRecordList('records');
      expect(records, hasLength(1));
      expect(records.first.id, 'rec_2', reason: '選択されていない方は残る');
    });

    test('無選択で削除しようとするとnoSelectionを返す(正常操作、失敗にしない)', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([
          ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'}),
        ]),
        'selected': const ForgeSelectedRecordState(null),
      });
      final outcome = store.deleteRecord('records', 'selected');
      expect(outcome, RecordOperationOutcome.noSelection);
      expect(store.readRecordList('records'), hasLength(1), reason: '削除されていないこと');
    });
  });

  group('選択中Recordの削除でselected_recordが解除される', () {
    test('削除成功後、selected_recordがnullへ解除される', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([
          ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'}),
        ]),
        'selected': const ForgeSelectedRecordState(ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'})),
      });
      expect(store.deleteRecord('records', 'selected'), RecordOperationOutcome.success);
      expect(store.readSelectedRecord('selected'), isNull);
    });
  });

  group('削除で編集Fieldがクリアされる', () {
    test('Compilerが生成するcomposite(delete_record + reset_state)を模して、削除後に編集Fieldが空へ戻ることを確認する', () {
      // Runtime自体はdeleteRecord()の引数に編集Fieldの参照を持たない
      // (責務分離: 編集Fieldのリセットは、Compilerが生成する`composite`
      // Actionの`reset_state`ステップが担う、FORGE-V0.8.1-report.md参照)。
      // ここでは、実際にCompilerが生成する順序(delete_record→reset_state)を
      // そのままRuntimeへ発行し、結果として編集Fieldが空になることを確認する。
      //
      // **FORGE v1.0 Candidate Patch2で修正した実バグ(このテスト自体の
      // 不備)**: `reset_state`は「screen読み込み時点(construction時)の
      // 値」へ戻す仕様であり(`ForgeStateStore.reset()`参照、
      // `_initialValues`を参照する)、「空文字列」へ戻す仕様ではない。
      // 実際にCompilerが生成する`edit_field_*`は常に空文字列を初期値
      // として構築される(`forge_language_compiler.py`
      // `_build_field_inputs()`参照)。以前のこのテストは、
      // `ForgeStateStore`のコンストラクタへ`edit_field_species`の
      // **construction時点の値として**'アジ'を直接渡してしまっており、
      // これは「選択によって実行時に書き込まれた値」を誤って
      // 「初期値」としてモデル化していた(Runtime側の不具合ではなく、
      // テストのセットアップが実際のライフサイクルを正しく再現して
      // いなかった)。今回、実際のライフサイクル(空文字列で構築 →
      // selectRecordが値を書き込む → delete → reset)を正しく
      // 再現するよう修正した。
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([
          ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'}),
        ]),
        'selected': const ForgeSelectedRecordState(null),
        // Compilerが実際に生成する初期値と同じ、空文字列で構築する。
        'edit_field_species': const ForgeStringState(''),
      });

      // 選択によって、実行時に編集Fieldへ値が書き込まれる(実際の
      // ライフサイクルの再現。selectRecordはconstruction時点の
      // _initialValuesには影響しない)。
      final selectOutcome = store.selectRecord(
        'records', 'selected', 'rec_1', const {'species': 'edit_field_species'},
      );
      expect(selectOutcome, RecordOperationOutcome.success);
      expect(store.read('edit_field_species'), 'アジ', reason: '選択直後は編集Fieldへ値が反映されている');

      expect(store.deleteRecord('records', 'selected'), RecordOperationOutcome.success);
      final resetOk = store.reset('edit_field_species');
      expect(resetOk, isTrue);
      expect(
        store.read('edit_field_species'), '',
        reason: 'reset_stateはconstruction時点の値(空文字列)へ戻す。選択によって'
            '書き込まれた値が構築時点の値として扱われてはならない。',
      );
    });
  });

  group('存在しないrecord削除失敗', () {
    test('選択中のidが実際にはtargetに存在しない場合、recordNotFoundを返す', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([]),
        'selected': const ForgeSelectedRecordState(ForgeRecordItem(id: 'rec_1', fields: {'species': 'アジ'})),
      });
      final outcome = store.deleteRecord('records', 'selected');
      expect(outcome, RecordOperationOutcome.recordNotFound);
    });
  });

  group('add -> select -> update -> delete が一連で動作する(Runtime単体)', () {
    test('1件追加し、選択し、更新し、削除するまでを状態変化で確認する', () {
      final store = ForgeStateStore({
        'records': const ForgeRecordListState([]),
        'selected': const ForgeSelectedRecordState(null),
        'field_species': const ForgeStringState('アジ'),
        'edit_field_species': const ForgeStringState(''),
      });

      expect(store.addRecord('records', {'species': 'field_species'}), AddRecordOutcome.added);
      final recordId = store.readRecordList('records').first.id;

      expect(store.selectRecord('records', 'selected', recordId, const {'species': 'edit_field_species'}),
          RecordOperationOutcome.success);
      expect(store.read('edit_field_species'), 'アジ');

      store.writeTyped('edit_field_species', const ForgeStringState('サバ'));
      expect(store.updateRecord('records', 'selected', {'species': 'edit_field_species'}),
          RecordOperationOutcome.success);
      expect(store.readRecordList('records').first.fields['species'], 'サバ');
      expect(store.readSelectedRecord('selected')?.fields['species'], 'サバ',
          reason: 'update後、selected_recordも一覧と一致する');

      expect(store.deleteRecord('records', 'selected'), RecordOperationOutcome.success);
      expect(store.readRecordList('records'), isEmpty);
      expect(store.readSelectedRecord('selected'), isNull, reason: '削除後、選択は解除される');
    });
  });
}
