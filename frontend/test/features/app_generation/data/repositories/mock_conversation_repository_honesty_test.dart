// 疑似出力は、**疑似だと名乗る**（Universal Quality §3、Constitution §4）。
//
// ---
//
// 2026-09-02 の実機描画（Chromium、`USE_MOCK_GENERATION=true` ビルド）で
// 見つけた実バグの回帰テスト。`MockConversationRepository` が
// `simulated: true` を付けていなかったため、画面には
// `SimulatedOutputBanner` も「お試し用の疑似データ」表記も出ず、
// 疑似データが実 AI の生成物と同じ見た目で表示されていた。
//
// **このファイルは修正前のコードでは落ちる。**

import 'package:flutter_test/flutter_test.dart';
import 'package:forge_app/features/app_generation/data/datasources/mock_generation_datasource.dart';
import 'package:forge_app/features/app_generation/data/repositories/mock_conversation_repository.dart';

void main() {
  test('Mock の会話結果は simulated=true と名乗る', () async {
    const repository = MockConversationRepository(MockGenerationDataSource());

    final outcome = await repository.converse(message: '鍵の持ち出しを記録したい');

    expect(
      outcome.simulated,
      isTrue,
      reason: '疑似データを、実 AI の生成物と見分けが付かない形で返している',
    );
  });
}
