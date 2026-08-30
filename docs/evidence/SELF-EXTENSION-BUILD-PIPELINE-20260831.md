# Self-Extension — 生成から実 build/probe/PROMOTED までの実証（020E-2）

- 日付: 2026-08-31
- Branch: `claude/forge-master-handoff-k46jns`
- 対象: `SynthesizingBuildTimeImplementer`（本番の `ExtensionImplementer`）
- Canonical CI: run `33339800860` / head `d8a93410` / **4 jobs すべて success**
- 関連 commit: `0e24a25`（生成段）/ `5827f2d`（実 build 接続）/ `83683e1`（必須項目の宣言化）/ `d8a9341`（通し）

> **この文書は「Self-Extension E2E が完成した」とは言わない。**
> 証明できた範囲と、**まだ証明していない範囲**を分けて書く。
> シミュレーション／Test Double が混ざっている箇所は明示する。

---

## 0. 前提となる判定（先に済ませたもの）

`view.map` は **既存コードの activation であって生成ではない**と判定済み
（`docs/reports/FORGE-020E-CAPABILITY-ARTIFACT-SYNTHESIS-report.md` §0）。

そのため E2E の証明対象を `view.map` にしない。map の実装は先行 commit で
人が書いて出荷済みであり、それを PROMOTED にしても
「Forge が能力を作った」ことにはならない。

証明用には **`view.calendar`**（静的実装が無い能力）を使う。
専用テンプレート化はしていない——後述のとおり capability 専用分岐は
静的テストで禁止してある。

---

## 1. 何が実際に走ったか（**実 subprocess**）

`ManagedBuildWorkspaceRunner` が隔離 workspace へ materialize し、
`shell=False` / cwd 固定 / timeout つきで**本物のプロセス**を起動した。

| 段 | argv | exit |
|---|---|---|
| test | `python -m unittest discover -s . -p *_test.py` | **0** |
| build | `python -m compileall -q .` | **0** |
| runtime_probe | `python probe.py` | **0** |

`runtime_probe` の**実際の標準出力**:

```
runtime probe ok
```

これは生成された `capability_impl.py` を import して実行した結果であり、
モックの戻り値ではない。

### 具体的な Evidence 値（1回の実行例）

```
capability_id       : view.calendar
route               : build_time
manifest status     : promoted
promotion_blockers  : ()          ← 空＝全 Gate 通過
activation loaded   : True (view.calendar)
build_id            : build-7d815ba044a64ab7a518fb8f2d80dac1
source_digest       : d5b4fd4a3afc27cc16984c0d4df8350b06f3bb7951b3566cf23ae8013b37a0f4
runtime_fingerprint : 69628e740c670aaab496866238347d7e07e134604b9f84b93ac973c196d91a0d
synthesis_count     : 1
build_count         : 1
```

`build_id` / `source_digest` / `runtime_fingerprint` は実行ごとに変わる
（`build_id` は uuid、fingerprint はコマンド結果を含む）。上は一例である。

### 生成されたファイル

```
capability_impl.py        実装
capability_impl_test.py   その実装を検証するテスト
probe.py                  起動確認
```

`BuildTimeCapabilityArtifact` は**実装だけ / テストだけ**を受け取らない。
検証できない実装は、通っても「動いた」の証拠にならないためである。

---

## 2. Negative proof（**落ちるべきものが落ちること**）

| 壊したもの | 結果 |
|---|---|
| 生成テストを失敗させる | **PROMOTED されない**／`activation is None`／blockers が残る |
| `probe.py` を `SystemExit(3)` にする | **PROMOTED されない** |
| 実装を構文エラーにする | **PROMOTED されない** |
| 試験が落ちた後 | **`runtime_probe` が実行されない**（落ちた後の段を証拠に数えない） |
| 生成物が空 / 使えない | `CapabilityImplementationUnavailable`（「作れた」と言わない） |
| 契約が capability identity を変える | `BuildTimeExtensionError` |
| 未対応言語 | `CapabilityImplementationUnavailable`（「とりあえず python で」をしない） |
| 既存 Source の丸写し | `PreexistingSourceError`（改行・末尾空白の差では逃がさない） |

`build_id` / `source_digest` / `runtime_fingerprint` の不一致で activation が
拒否されることは、先行の `test_managed_build_time_implementer.py`
（commit `8733900`）が実 subprocess で証明済みである。

---

## 3. Capability 専用分岐が無いこと

`if capability_id == "view.map": return hardcoded_map_source` を一般機構
として書いた時点で、これは Template を1つ増やしたのと同じになる。

静的テストで固定した:

- `capability_artifact_synthesis.py` の実行コードに
  `view.` / `data.` / `effect.` / `interact.` / `simulate.` が現れない
- `synthesizing_build_time_implementer.py` も同じ
- コマンド計画は **実装先の言語**で引く（能力では引かない）。
  行が増えるのは対応言語を足したときだけである
- 異なる2つの能力が同じ道を通ることを実行して確認

---

## 3.5 通し（未知要求 → 獲得 → retry → 別要求で再利用）

`forge_ai/tests/test_self_extension_e2e_real_build.py`。
Capability Plan も retry も**本番の関数**であり、build は**実 subprocess**。

実行結果（実測）:

```
BEFORE   : missing = ('view.calendar',)          ← 獲得前は MISSING
build_id : build-0a5cea3f69304b309654595cdda3000e
manifest : promoted     blockers: ()             ← 全 Gate 通過
RETRY #1 : missing = ()   views = ('view.calendar',)
REUSE #2 : missing = ()   views = ('view.calendar',)
counts   : synthesis=1  build=1  provider_calls=1
```

- **1回目の要求**「通院した日をカレンダーで確認したい」
- **2回目の要求**「会議の予定を登録してカレンダーで見たい」（別の文・別の題材）
- 2回目で **生成も build も Provider 呼び出しも増えていない**

retry が本物であることは配線破壊試験で確認した——`capability_plan.py` が
Registry を見る行を外すと、retry と再利用の2件が落ちる。

Negative proof（通し側）:

- `runtime_probe` を失敗させると activation が出ず、`install()` が
  `ValueError` で拒否し、**gap は開いたまま残る**
- `requested` に入っているだけでは PROMOTED にならない（`6da20fc` の境界）

---

## 3.6 獲得した能力は、まだ**生成物には届いていない**（実測）

§3.5 で `view.calendar` を獲得したあと、実際に確かめた。

```
plan.views                       : ('view.calendar',)   ← 計画には載る
compiler が calendar に言及するか : False               ← 出力には出ない
compiler が view.map に言及するか : True
```

**獲得は Capability Plan の gap を閉じるが、Forge Document に widget を
出すところまでは届いていない。**

理由ははっきりしている。

1. 生成した Artifact の実装先は **Python** である。一方、Document の
   emission と Runtime は **Dart** 側にある
2. `forge_language_compiler.py` は **`if "view.map"` という能力名の枝**で
   widget を出している。`view.map` にだけ人が書いた枝があり、
   **獲得した能力には枝が無い**

これは §0 の判定（map は activation であって生成ではない）が、出力側で
もう一度現れたものである。Planner 側の同じ枝は `83683e1` で宣言へ移した
が、**Compiler 側にはまだ残っている。**

### したがって CEO の E2E 項目 #4 は未達である

「生成された Forge Document に当該 widget が含まれること」は、
**獲得した能力については満たしていない**。満たしているのは
`view.map`——すなわち最初から実装があったものだけである。

### 直した（020E-5）

Compiler の枝を消し、**宣言表**へ移した
（`capability_document_contribution.py`）。

```python
# 以前
if "view.map" in promoted_capabilities:
    document = self._attach_map_view(document, entity)

# いま
document = apply_capability_contributions(
    document, promoted_capabilities, entity,
)
```

**表であることが本質である。** 枝は人が書き足すものだが、表は獲得した
能力が `register_document_contribution()` で自分で登録できる。
獲得した能力が widget を出せることは実際に確かめた
（`TestAnAcquiredCapabilityCanRegisterItsOwn`）。

`view.map` の出力は**属性の順序まで1バイトも変えていない**——変えると
Dart 側（Validator / Parser / Widget Registry）の契約が壊れる。

#### この経路には**テストが1つも無かった**

宣言の登録を外しても、**backend 1984 件も forge_ai 全件も素通りした**。
つまり `_attach_map_view` の時代から、`view.map` の**出力経路そのものが
無検査**だった。実際に compile して widget が出ることを確かめる
テストを足した（登録を外すと落ちる）。

これは §0 の判定を補強する事実である——map は実装が先に在っただけで
なく、**その出力経路も検査されていなかった。**

#### まだ残ること — そして**どこで証明できないか**

宣言は「この能力はこの widget を出す」と言っているだけであり、
**その widget を Dart Runtime が描けるかどうかは別の事実**である。
新しい能力を実際に描けるようにするには、BUILD_TIME で Dart 側を
ビルドし直す必要がある。

**それはこの CI 構成では証明できない。** 確認した事実:

- `forge_ai` / `backend` のテストは **Python job** で走る。
  その job に `dart` も `flutter` も無い
- Flutter が在るのは **frontend job** だけであり、そちらは
  Python 側の Self-Extension 経路を実行しない

したがって、生成した Dart を隔離 workspace でビルドする command plan を
足しても、**Python job では skip されるだけ**である。
**skip されたテストは何も証明しない**ので、それを「Dart も通した」の
証拠にしてはならない。

証明するには次のどちらかが要る。

1. Flutter を持つ job（または実機）で Self-Extension 経路を走らせる
2. 生成 Dart を既存 Flutter プロジェクトへ組み込んでビルドする
   ——隔離 workspace 単体のビルドでは、Widget Registry への登録を
   含む「実際に描ける」の証明にならない

どちらも設計判断が要るので、ここでは**着手せずに残す**。
半端に足して skip を「通った」と数える方が危険である。

---

## 4. **証明していないこと**（ここが本題）

| 項目 | 状態 |
|---|---|
| **その Source を実 Model が書いたこと** | **未証明。** ここでの Provider は **Test Double** であり、実装文字列はテストが与えている。**Forge が自律生成したとは言えない** |
| 自然言語の未知要求 → 獲得 → retry → 別要求で再利用 | **証明済み**（§3.5。ただし Source は Test Double 由来） |
| retry 後に生成された Forge Document に当該 Widget が入ること | **未証明** |
| Backend Validator PASS までの通し | **未証明** |
| Flutter runtime での実描画 | **未証明** |
| 2つ目の別要求での再利用（再 build 無し） | **証明済み**（§3.5。synthesis=1 / build=1 のまま） |
| **Real Local Model runs** | **0**（増やしていない） |

> **いちばん重要な未証明点は1つ目である。**
> 「生成 → 実 build → 実 probe → PROMOTED」の**配管は本物**になったが、
> その入口へ実装文字列を入れているのが Test Double である限り、
> 「Forge 自身が実装を作った」ことは証明されていない。
> ここは Real Model を1回動かすまで **UNPROVEN のまま**にする。

---

## 5. 次の本当のボトルネック

**Real Model による capability_implementation stage の実行**である。

配管・Gate・Negative proof は揃った。足りないのは
「実際にモデルへ書かせて、その出力が実 build/probe を通るか」という
1点であり、それには Local Model を実行できる環境が要る
（`docs/MACHINE-INDEPENDENT-POLICY.md`）。

その次が、cycle 全体（自然言語 → retry → 再利用）への接続である。
