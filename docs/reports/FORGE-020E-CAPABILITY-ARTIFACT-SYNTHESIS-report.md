# FORGE-020E — Capability Gap から実装 Source を作る段を埋める

- Task: FORGE-020E（CEO指示、2026-08-30。スマホから）
- Branch: `claude/forge-master-handoff-k46jns`
- 起点 HEAD: `8733900`

---

## 0. 最初に命じられた判定

> 「今回の処理は本当に新しい Capability の生成なのか、
> それとも既存コードの activation なのか」

### 判定: **既存コードの activation である。生成ではない。**

根拠を4つ挙げる。すべて repo の現物である。

**1. 実装 Artifact を作っている本番コードが1行も無い。**

`BuildTimeCapabilityArtifact(...)` の構築点を全 repo で探すと、
**3件すべてがテストの中**である。

```
forge_ai/tests/test_managed_build_time_implementer.py:34
forge_ai/tests/test_build_time_extension.py:33
forge_ai/tests/test_build_time_workspace.py:17
```

本番の構築点は**ゼロ**だった。

**2. `ExtensionImplementer` は Protocol であって実装ではない。**

`extension_cycle.py` の

```python
class ExtensionImplementer(Protocol):
    def __call__(self, manifest: ExtensionManifest) -> ExtensionImplementation: ...
```

は呼び出し側が注入する契約である。注入している実体は**テストの
`_implement()` だけ**であり、本番の実装者は存在しない。

**3. `view.map` は DECLARATIVE route で promote されている。**

`test_self_extension_loop.py` は

```python
select_route=lambda c: ExtensionRoute.DECLARATIVE,
```

でテスト側の `_implement` を通す。**Source は1バイトも生成されていない。**

**4. map の実装は既に出荷済みの repo source である。**

Forge Language v1.16 / `map_view` / Backend Validator / Dart Parser /
Widget Registry / Flutter map runtime / OpenStreetMap marker /
Compiler wiring は、すべて**先行 commit で人が書いて repo に入っている**。
実行時に生成されたものではない。

### したがって

`ManagedBuildTimeImplementer` が証明しているのは
**「与えられた Artifact を、実 build と実 runtime probe で検証して
取り込める」**ことであり、これは本物である（実 subprocess を使っている）。

しかし **「足りない能力の実装を Forge 自身が作った」ことは、まだ
1度も証明されていない。** CEO の認識と一致する。

---

## 1. 埋めた段

```
Capability Gap
 → 【ここが空いていた】実装 Source Artifact の生成
 → BUILD_TIME（実 test / 実 build / runtime probe / exact 照合）
 → PROMOTED
```

`forge_ai/core/orchestration/capability_artifact_synthesis.py` を新設。

### Capability 専用の分岐を持たない

受け取るのは Canonical Catalog から機械的に引いた契約だけである。

```python
CapabilityImplementationContract(
    capability_id, intent, data_contract, host_language, binding_targets,
)
```

`if capability_id == "view.map"` を書いた瞬間、これは Template を1つ
増やしたのと同じになる。**実行コードが capability id を名指ししていない
ことを静的テストで固定した**（`view.` / `data.` / `effect.` /
`interact.` / `simulate.` のどれも現れない）。

能力を変えても通る道が変わらないことも、2つの異なる能力で確認している。

### 既存コードの丸写しを「生成」と数えない

**ここが今回いちばん危うい点である。**

Model に実装を書かせると、**repo に既にある実装をそのまま書き戻して
くる**ことがある。それを通すと

> 「Forge が view.map を自律生成した」

という**嘘の実績**になる。実際には既存能力の activation でしかない
——まさに §0 で判定したのと同じ形が、今度は自動で量産される。

対策:

* `known_source_digests` を**必須引数**にした（既定値なし）。
  渡し忘れた呼び出しは**そもそも書けない**
* 生成物が既存 Source と一致したら `PreexistingSourceError`
* 改行コード・末尾空白だけの差では逃がさない（正規化して digest）

### 作れなかったものを「作れた」と言わない

| 入力 | 結果 |
|---|---|
| 空の応答 | `None` |
| 実装だけ（テスト無し） | `None`（検証できない実装は受け取らない） |
| テストだけ（実装無し） | `None` |
| 危険なパス | そのファイルを落とす |
| identity のすり替え | 契約側の id が勝つ |

`entity_synthesizer.py` と同じ形である——AI の出力を決定的に検証し、
通らなければ落とす。

### 自分のテストで実バグを1件見つけて直した

絶対パス `/abs/path.dart` を `lstrip("/")` して `abs/path.dart` に
**「直して」通していた**。怪しい入力を正規化して受け入れるのは
楽観側へ倒すことである（`CLAUDE.md` §3）。落とす形にした。

---

## 2. 配線破壊試験

| 壊したもの | 結果 |
|---|---|
| 丸写しチェックを外す | 2件 FAIL |
| `if capability_id == "view.map"` を入れる | 1件 FAIL |

---

## 3. 検証（LOCAL の実測）

| 対象 | 結果 |
|---|---|
| `forge_ai` 全件 | **677 passed** |
| `backend` 全件 | **1984 passed / 16 skipped** |
| `ruff`（変更した全ファイル） | All checks passed |

---

## 4. **まだ証明していないこと**（盛らない）

この commit は「Self-Extension が完成した」という意味では**ない**。

| 項目 | 状態 |
|---|---|
| 未知要求 → 実 Source 生成 → PROMOTED の E2E | **未証明** |
| 生成した Source が実 build/probe を通ること | **未証明**（機構は在るが繋いでいない） |
| 2つ目の異なる要求で再利用され、再 build が起きないこと | **未証明** |
| Real Local Model runs | **0**（増やしていない） |

次は、この Synthesizer を `ManagedBuildTimeImplementer` へ繋いで、
**実際に生成した Source が実 build と runtime probe を通る**ところまで
証明することである。そこを通して初めて
「足りない能力を作った」と言える。

### geocoding は別能力のまま

`view.map` は明示的な `latitude` / `longitude` を要る。
場所名から座標を導く経路は作っていないし、Prompt にも
「書かれていない入力を推測して補わない（場所の名前から座標を導かない
——それは別の能力である）」と明記した。
