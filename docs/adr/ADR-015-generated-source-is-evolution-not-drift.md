# ADR-015: 生成 Source は Gate 付きの副経路である（Typed IR が主経路）

**Status:** **PROVISIONAL**（2026-09-04 に `ACCEPTED` から格下げ）

**なぜ格下げしたか:** 初版は「現在の Typed IR では GEN-09/10/11 を表現できない」
を根拠に Generated Source を必要と結論した。しかし
**「現在の語彙で表現できない」と「Typed IR を拡張しても表現できない」は
別の主張**である。初版はその区別をせずに ACCEPTED を名乗っていた。過剰である。

**この ADR が ACCEPTED へ戻る条件:** §7 の Decision Experiment を実施し、
Extended Typed IR で届く範囲を実測すること。

**既存の Generated Dart 経路は削除しない。** 動いているものを止めずに
Architecture を決める（CEO 指示 §3）。

---

## 1. 問い

初期原則の Trust Boundary は次だった。

```text
Natural Language → AI → JSON Schema → Validator → Flutter Renderer
```

現在は Self-Extension で **AI が Dart を書き、Build し、Forge 本体へ install
する**経路が実在する。これは意図的進化か、Drift か。

---

## 2. 三案

### A. Extended Typed IR Route

JSON / Typed IR を、Behavior / State Machine / Animation / Interaction /
Game Rule / Physics・Collision / Event / Data・Service / Native Capability まで
拡張し、**決定論的 Compiler** が Dart へ変換する。AI が出すのは JSON だけ。

### B. Generated Source Route

AI が Source を書き、Sandbox → 静的解析 → Permission → Build → Runtime probe
→ Digest → Promotion を通す。

### C. Hybrid Route

大部分を Typed IR で作り、**本当に表現不能な能力だけ** Source synthesis へ落とす。

---

## 3. 比較（14 軸）

`A` = Extended Typed IR / `B` = Generated Source / `C` = Hybrid。
◎ 強い / ○ 可 / △ 弱い / ✕ 困難。

| 軸 | A | B | C | 判断根拠 |
|---|:--:|:--:|:--:|---|
| 2億円 Target 到達能力 | ？ | ◎ | ◎ | **A は未知**。§4 で検討。B は原理的に上限が無い |
| Security | ◎ | △ | ○ | A は実行される Dart が Forge 製。B は Sandbox / Permission / 供給元の 4 つを全部閉じて初めて成立 |
| Determinism | ◎ | △ | ○ | 同じ IR → 同じ Dart。B は生成のたびに違う Source |
| Validation | ◎ | ○ | ◎ | A は Schema で全数検査できる。B は「書かれた物」を検査するので網羅性が構造的に落ちる |
| Reuse | ◎ | △ | ◎ | IR は正規化でき、意味が同じものを同じものと判定できる。Source は表記揺れで別物に見える |
| Debuggability | ○ | △ | ○ | A は IR を見れば分かる。B は生成 Source を読む必要がある |
| Performance | ○ | ◎ | ◎ | B は必要な最適化を直接書ける。A は Compiler の表現力に縛られる |
| Maintainability | △ | ○ | △ | **A は Forge 本体が肥大する**（IR と Compiler が増え続ける）。B は Forge 本体が薄い |
| Extension speed | ✕ | ◎ | ○ | A の新能力は Forge の release を待つ。B は会話の中で増える |
| AI dependence | ◎ | △ | ○ | A は小さい Model でも JSON なら書ける。B は Source を書ける Model が要る（Local-first に不利） |
| Offline feasibility | ◎ | △ | ○ | A は Compiler がローカル。B は Build tool chain が要る |
| Zero-budget feasibility | △ | ○ | ○ | A は Forge 側の実装工数が大きい。B は生成側へ寄せられる |
| Evidence strength | ◎ | ○ | ◎ | A は IR の性質を証明できる。B は個別 Artifact ごとに証明が要る |
| Future scalability | △ | ◎ | ◎ | A は「まだ無い表現」に弱い。未知の Need に構造的に届かない |

**A が強いのは Security / Determinism / Validation / Reuse / AI dependence /
Offline。** これは Forge の中核価値とほぼ一致する。
**B が強いのは Extension speed / Future scalability / Performance。**

---

## 4. GEN-09/10/11 は本当に Source 生成を要するのか

初版はここを「要る」と断定した。**再検討する。**

| ID | 能力 | Typed IR で届きうるか | 判断 |
|---|---|---|---|
| GEN-09 特殊 UI | Template なしの Encoding / View / Interaction | **届きうる。** 「特殊」は既存 widget 語彙の外という意味であって、宣言不能という意味ではない。Encoding（値→視覚属性の写像）と View（レイアウト規則）は宣言で書ける領域である | **A で届く可能性が高い** |
| GEN-10 ゲーム | Loop / Rule / Input / Collision / State / Persistence | **届きうる。** Game Rule IR（entity / component / rule / event）+ 決定論的 engine は既存技術（ECS、rule engine）で確立している。**Loop や Collision は Forge が書き、Rule だけ宣言させる**のが自然 | **A で届く可能性が高い。むしろ A の方が安全**（無限ループが構造的に書けない） |
| GEN-11 インタラクティブ UI | Drag / Animation / Realtime / Keyboard / Touch | **届きうる。** Declarative Animation は Flutter 自身が既にその形（`AnimatedContainer` は宣言）。Drag も `onDragUpdate → state 更新` の宣言で書ける | **A で届く可能性が高い** |
| EXT-04 コード生成 | 定義上 Source を書く能力 | — | **B が要る**（定義そのもの） |
| EXT-06 Flutter Runtime 登録 | 新しい型を Runtime へ載せる | **A なら不要になる。** IR が表現できるなら新しい widget 型を足す必要が無い | **A で不要化しうる** |

> **初版の結論は誤りではないが、根拠が弱かった。**
> 「いま無い」を「原理的にできない」と読んでいた。GEN-09/10/11 の 3 つは、
> Game Rule IR / Interaction IR / Animation IR を足せば届く見込みが十分ある。

残るのは **EXT-04（コード生成そのもの）**である。これは定義上 B を要する。
ただし EXT-04 は「Forge が任意の Source を書ける」ことが Target なのか、
「Forge が能力の隙間を自分で埋められる」ことが Target なのかで重みが変わる。
後者なら A の拡張でも満たしうる。

---

## 5. 決定（暫定）

> **C（Hybrid）を採る。ただし「Typed IR を先に拡張する」を既定の向きとし、
> Source 生成は最後の手段とする。**

初版の C は「表現不能なら B」だったが、**何が表現不能かを確かめずに B へ
落ちていた**。以後は次を順に試す。

```text
1. 既存 Typed IR で作れるか       → 作れるなら作る（Reuse-first）
2. Typed IR の拡張で作れるか       → 作れるなら **IR を拡張する**（Forge 本体の仕事）
3. どうしても表現できないか        → **理由を Evidence として残したうえで** Source 生成
```

3 へ落ちるたびに「なぜ IR で表現できなかったか」を記録する。記録が溜まれば、
それは次に拡張すべき IR の設計材料になる。**落ちた理由を残さない Source 生成を
禁止する**——それが Drift の始まりである。

---

## 6. Gate の現況（2026-09-04 実測）

### 閉じた（このセッションで実装）

| Gate | 実装 | 破壊試験 |
|---|---|---|
| **Sandbox（network / env / CPU / memory / file size / PID）** | `forge_ai/core/sandbox/runner.py` | network / env / CPU / memory / file size / fail-open の 6 種で検出 |
| **本番経路が Sandbox を通ること** | `build_time_workspace._execute` | 素の `subprocess.run` へ戻すと 2 件 FAIL |
| **Permission Manifest** | `forge_ai/core/sandbox/policy.py` | 6 種で検出 |
| **Capability Tier の強制**（Tier C は Human Gate） | 同上 | 同上 |
| **依存 allowlist と獲得行為の禁止** | 同上 | 同上 |

### 以前から閉じていた

隔離生成 / Digest 固定（検査した物 == 載せる物）/ 静的解析（`dart analyze`）/
生成テスト実行 / 実 Build / Runtime probe（loaded）/ Validator 語彙拡張の制限 /
出荷物の空検査。

### まだ閉じていない

| 欠けているもの | 状態 |
|---|---|
| **Windows / macOS の Sandbox backend** | 未実装。その環境では実行を**拒否**する（fail closed）。Linux だけ通ったことを「完成」と読まない |
| Sandbox と Promotion の接続 | `_execute` は隔離するが、`PermissionManifest` を Promotion 判定へまだ配線していない |
| 生成物の AST / Import / Secret / Effect 検査 | 未実装（SEC-05） |
| root 実行時の process 数上限 | `RLIMIT_NPROC` は root で強制されない（実測）。PID namespace で隔離はするが、数は止まらない |

---

## 7. Decision Experiment（この ADR を ACCEPTED へ戻す条件）

**設計論だけで決めない。** 次を実測する。

| # | 実験 | 判定 |
|---|---|---|
| E1 | Game Rule IR の最小案（entity / rule / event / collision）を書き、決定論的 engine で「当たり判定のあるゲーム」を 1 本作る | 作れたら GEN-10 は A で届く |
| E2 | Interaction / Animation IR の最小案で Drag と Animation を 1 本作る | 作れたら GEN-11 は A で届く |
| E3 | Encoding IR で「Template に無い表現」を 1 本作る | 作れたら GEN-09 は A で届く |
| E4 | E1〜E3 で表現できなかった要求を集め、**なぜ表現できなかったか**を分類する | B が本当に要る領域の輪郭が出る |

E1〜E3 が通れば、**B は EXT-04 のためだけの経路**へ縮小できる。
そのとき Security / Determinism / Reuse / Offline / AI dependence が同時に改善する。

---

## 8. 却下した案

| 案 | 却下理由 |
|---|---|
| JSON only へ即座に戻す | 現に動いている経路を止める。EXT-04 の行き先が無い。CEO 指示 §3「既存 Generated Dart 経路を削除してはいけない」 |
| B を主経路にする | Security / Determinism / Reuse / Offline / AI dependence の 5 軸で A に劣る。**Forge の中核価値と逆向き** |
| Sandbox が無いまま Tier B を自動化 | 2026-09-03 まで実際にこの状態だった。本 ADR と同時に塞いだ |
| Windows backend が無いまま「Sandbox 完成」と書く | Windows は主配布対象である。Linux だけで完成扱いにしない |
