# backend/app/ai/native/ — ステータス

**Status: EXPERIMENTAL — NOT CONNECTED — NOT USED IN PRODUCTION PATH**
**マイルストーン: M006以降(未定)。M004・M005ではない。**

`docs/spec/FORGE_AI_ARCHITECTURE_V1.md`(Architecture Freeze、2026-07-14確定)
により、このディレクトリの位置づけが正式に決まった。

- 「M004」= `forge_ai/`(Forge AI Core)のみを指す。
- 「M005」= `backend/app/ai/runtime/`(Backend AI Integration)を指す。
- このディレクトリ(`backend/app/ai/native/`)は、いずれにも属さない
  **M006以降の候補、現時点ではExperimental**という扱いになった。

**制約(Architecture Freeze以降)**: CEO承認を得るまで、このディレクトリへの
追加実装・他モジュール(`forge_ai/`・`backend/app/ai/runtime/`・
Backend API・Flutter Runtime)からの参照は行わないこと。

`backend/app/ai/runtime/README.md`と同じく、CEOがChrome実機で確認した
生成フローからは一度も呼び出されていない。

このディレクトリの経緯(いつ・どの依頼で作られたか)は、
`docs/spec/FORGE_AI_ARCHITECTURE_V1.md` 2章に記録した実際の
ファイルタイムスタンプ調査を参照。正規の報告書には記載が無く、
由来は完全には確認できていない。

現時点で確実に言えることは以下のみ。

- 実LLM・実Native AIモデルへの接続は無い(ルールベース/Stub)。
- 本番の生成フロー(Mock Generator経由)には一切関与していない。
- Unit Testでの検証はあるが、AI推論としての妥当性を検証したものではない。

