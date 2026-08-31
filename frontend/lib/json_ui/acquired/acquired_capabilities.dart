// 獲得した Capability の登録を、**本番が必ず通る場所**で行う。
//
// 「呼び出し側が忘れずに呼ぶ」設計にしない（`CLAUDE.md` §3、同じ失敗を
// 8回以上している）。Parser が未知の型を見たときと、Widget Registry を
// 組むときの**両方**からここを通るので、登録を呼び忘れる経路が無い。

import 'acquired_capability.dart';
import 'acquired_registrations.g.dart';

bool _registered = false;

/// まだなら登録する。**何度呼んでも安全。**
void ensureAcquiredCapabilitiesRegistered() {
  if (_registered) {
    return;
  }
  _registered = true;
  registerAcquiredCapabilities();
}

/// テスト用の巻き戻し。**本番経路は使わない。**
void resetAcquiredCapabilityRegistrationForTest() {
  _registered = false;
  clearAcquiredCapabilities();
}
