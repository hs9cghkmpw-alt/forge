/// TRANSFORM Primitive: グループごとの集計
/// (FORGE-USER-GUIDED-SELF-EXTENSION-006 Phase 4、2026-08-13新設)。
///
/// ---
///
/// ## なぜ独立した関数なのか
///
/// これは**Widgetではない**。`bar_chart`のプロパティとして実装すれば
/// 手っ取り早いが、それでは「TRANSFORMはVIEWとは別の層である」という
/// 設計(`docs/spec/FORGE-SELF-EXTENSION-ARCH-REVIEW-v2.md` §4)が
/// 名ばかりになる——集計が特定のWidgetに閉じ込められ、他のViewから
/// 再利用できなくなるからである。
///
/// したがって集計は**どのWidgetからでも呼べる純粋関数**として置く。
/// `bar_chart`は最初の利用者にすぎない。
///
/// ## これが埋める空白
///
/// Runtime監査(2026-08-13)で判明した事実:
///
/// * `ForgeRuntimeState`に派生状態(derived / computed / aggregate)の
///   仕組みが1つも無い。
/// * `bar_chart`は**Record 1件につき棒1本**で、グループ化しない。
///
/// このため「場所ごとの釣果数」「カテゴリごとの支出合計」
/// 「月ごとの平均体重」という、ごく一般的な要求が1つも表現できなかった
/// (TD57)。
///
/// ## 純粋関数である(状態を持たない)
///
/// 入力のRecordリストを変更せず、同じ入力なら常に同じ出力を返す。
/// State Storeへ書き込まないので、**保存されるデータは1バイトも増えない**
/// ——集計結果は表示のたびに導出される。これは`missing`をフィールドでは
/// なくプロパティにしたのと同じ判断である(導出できる値を保存しない)。
library;

import '../schema/forge_document.dart';

/// 集計方法。
enum ForgeAggregateOp {
  /// 件数を数える。`valueField`は不要。
  count,

  /// 数値Fieldの合計。
  sum,

  /// 数値Fieldの平均。
  average;

  static ForgeAggregateOp? fromJson(String? raw) => switch (raw) {
        'count' => ForgeAggregateOp.count,
        'sum' => ForgeAggregateOp.sum,
        'average' => ForgeAggregateOp.average,
        _ => null,
      };

  String get jsonValue => name;
}

/// 集計結果1グループ分。
class ForgeAggregatedGroup {
  /// グループ化キーの値(そのまま表示ラベルになる)。
  final String label;

  /// 集計値。
  final double value;

  /// このグループに含まれたRecord件数(`count`以外でも保持する。
  /// 平均の分母が何件だったかを、呼び出し側が知りたい場合があるため)。
  final int recordCount;

  const ForgeAggregatedGroup({
    required this.label,
    required this.value,
    required this.recordCount,
  });

  @override
  String toString() => 'ForgeAggregatedGroup($label: $value / $recordCount件)';
}

/// Recordを`groupBy`でまとめ、`op`で集計する。
///
/// 決定的である: 同じ入力なら常に同じ順序・同じ値を返す。
/// **並び順は最初に出現したグループ順**とする。件数降順に並べ替えたい
/// 場合は呼び出し側で行う——それは並べ替え(`transform.sort`)という
/// 別のPrimitiveの仕事であり、ここで一緒にやると2つの関心が混ざる。
///
/// 次の場合、そのRecordは**静かに無視される**(例外にしない):
///
/// * `groupBy`のFieldが存在しない、または値が`null`
/// * `op`が`sum`/`average`で、`valueField`の値が数値でない
///
/// Validatorが通常は弾くが、Runtimeは壊れた文書でも落ちない方が良い
/// ——他のWidget(`_RecordCard`・`buildBarChart`)が既に採っている
/// 「無ければ表示しない」という方針に合わせる。
List<ForgeAggregatedGroup> aggregateRecords(
  List<ForgeRecordItem> records, {
  required String groupBy,
  required ForgeAggregateOp op,
  String? valueField,
}) {
  if (groupBy.isEmpty) return const [];
  if (op != ForgeAggregateOp.count && (valueField == null || valueField.isEmpty)) {
    // sum/average に値Fieldが無いのは呼び出し側の誤りだが、
    // 例外で画面を落とすほどのことではない。何も集計しない。
    return const [];
  }

  // 出現順を保つため LinkedHashMap(Dartのmapリテラルは挿入順を保つ)。
  final sums = <String, double>{};
  final counts = <String, int>{};

  for (final record in records) {
    final rawKey = record.fields[groupBy];
    if (rawKey == null) continue;
    final key = rawKey.toString();
    if (key.isEmpty) continue;

    if (op == ForgeAggregateOp.count) {
      sums[key] = (sums[key] ?? 0) + 1;
      counts[key] = (counts[key] ?? 0) + 1;
      continue;
    }

    final rawValue = record.fields[valueField];
    if (rawValue is! num) continue;
    sums[key] = (sums[key] ?? 0) + rawValue.toDouble();
    counts[key] = (counts[key] ?? 0) + 1;
  }

  return [
    for (final entry in sums.entries)
      ForgeAggregatedGroup(
        label: entry.key,
        value: op == ForgeAggregateOp.average
            ? entry.value / counts[entry.key]!
            : entry.value,
        recordCount: counts[entry.key]!,
      ),
  ];
}

/// 1つの数値へ畳む集計(グループ化しない)。v1.11新規(FORGE-R1、TD69)。
///
/// ---
///
/// ## なぜ`aggregateRecords`と別関数なのか
///
/// `groupBy: ''`のような「グループ化しない」呼び出しを許すこともできた
/// が、そうすると**返り値の要素数が呼び出し方によって変わる**関数に
/// なる。呼び出し側は毎回「1件のはずだ」と仮定して`.first`を書くことに
/// なり、その仮定は型に現れない。
///
/// ここは**常に1つの値を返す**別の問いである。だから別の関数にして、
/// 返り値も`List`ではなく単一の`double?`にした。
///
/// ## Recordが0件のときは`null`を返す(0ではない)
///
/// 「合計0円」と「まだ記録が無い」は違う。0を返すと、呼び出し側が
/// その区別を復元できない——`metric_view`は前者を「0円使った」と
/// 表示してしまう。**分からないものを楽観側へ倒さない**
/// (`CLAUDE.md` §3)。
///
/// `count`だけは0件でも0を返す。「0件である」は正しく数えた結果で
/// あって、欠落ではないからである。
double? aggregateAll(
  List<ForgeRecordItem> records, {
  required ForgeAggregateOp op,
  String? valueField,
}) {
  if (op == ForgeAggregateOp.count) {
    return records.length.toDouble();
  }
  if (valueField == null || valueField.isEmpty) {
    // sum/average に値Fieldが無いのは呼び出し側の誤り。例外で画面を
    // 落とすほどのことではないが、**0を返して「合計0」に化けさせない**。
    return null;
  }

  double total = 0;
  int counted = 0;
  for (final record in records) {
    final raw = record.fields[valueField];
    if (raw is! num) continue; // 未入力・型不一致は静かに無視(他Widgetと同方針)
    total += raw.toDouble();
    counted += 1;
  }
  if (counted == 0) return null;
  return op == ForgeAggregateOp.average ? total / counted : total;
}
