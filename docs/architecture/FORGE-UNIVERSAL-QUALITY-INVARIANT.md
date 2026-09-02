# Forge Universal Quality Invariant

**Status:** CEO Product Directive / Architecture Invariant

**Date:** 2026-09-02

**Scope:** All Forge clients, execution hosts, model profiles, plans, and generated tools

## 0. One rule

> **Forgeは、PC・GPU・RAM・OS・端末・無料/有料・Local/別Hostの違いを、
> 利用者が受け取る品質の違いにしない。全員へ同じ高品質基準を提供する。**

## 1. 同一でなければならないもの

同じ要求と、利用者が合意した同じScope（作る範囲）には、すべての経路で次を
同一にする。

端末やPlanが違っても、同じProduct Quality Contract（製品品質の合格基準）で
判定する。

- 意味理解と必須要件
- 提供機能と利用者のTask達成
- Generated AppのDesignと情報設計
- Validator、Repair、Runtimeの合格基準
- Safety、Permission、Privacy、Data protection
- Reliability、保存、Backup、Recovery
- Accessibility（利用しやすさの基準）
- Evidence（検証証拠）とRelease Gate

## 2. 端末差で変えてよいもの

品質を維持するため、内部では次を変えてよい。

- Runtime、Model、Quantization（量子化）の組み合わせ
- Local、LAN上のPersonal Host、利用者が明示許可した別Host
- CPU/GPU/分割実行/非同期実行
- Cache、Reuse、Queue、Warm-up
- 消費電力、内部並列度
- 公開された最大時間内の待ち時間

高性能端末は同じ品質へ早く到達できる。低資源端末は処理を分割または別Hostへ
委譲できる。**どちらも受け取る成果物の品質基準は同じ**である。

## 3. 禁止する実装

- `low quality mode`、`lite quality`、端末別Design簡略化
- RAM不足を理由に、同一Gateを通らない小型Modelへ切り替える
- 低資源端末だけ機能、検証、Repair、安全検査を省く
- 無料利用者だけ粗いUI、弱い意味理解、低い成功率を提供する
- 未対応Capabilityを黙って削り、生成成功として表示する
- Mobile、Tablet、Webを閲覧専用のsecond-class client（下位クライアント）にする
- CloudがなければCore Taskの品質が落ちる構成を恒久化する

## 4. 最小限の道具との両立

「最小限の道具から始める」は品質縮小ではなく、Scopeの段階化である。

1. Forgeが、利用者の目的を最短で解決する小さなScopeを提案する。
2. 利用者の明示承認または安全な委任規則でScopeを確定する。
3. 確定したScopeには、通常版と同じ全品質Gateを適用する。
4. 後の会話で機能を増やしても、既存データと品質を守る。

必須意味を無断で削ること、作れたように見せること、低品質な代用品を渡すことは
Smallest Useful Tool（最小限で役立つ道具）ではない。

## 5. Free / Paid

無料・有料で変えてよいのは、主に利用量、同時実行数、追加の高度Capability、
組織向け管理、Support、利便機能である。**提供対象となった同じTaskの品質下限、
Core UX（中核の使い心地）、Safety、Privacyは変えない。**

## 6. Execution Resolver

Model Profile Managerは、品質Tierを選ぶ機構ではなく、同一品質へ到達する
Execution Resolver（実行経路の選択機構）として実装する。

```text
同じUser Contract
  -> 利用可能なRuntime/Host候補
  -> 同一品質Gateを証明済みの候補だけ残す
  -> Privacy/Permission/時間/資源で最適経路を選ぶ
  -> 全Gateを再検証
  -> 同じ品質の成果物を渡す
```

同一品質を満たす経路がまだない要求は、低品質な成功へ落とさず、能力獲得、修復、
安全なScope確認、または許可済みHostへの委譲へ進める。

## 7. Release hard gates

次は平均値で相殺しない。

1. Profile間の必須意味差: 0件
2. Profile間の機能欠落: 0件
3. Profile間のVisual/Accessibility Gate差: 0件
4. Profile間のSafety/Privacy Gate差: 0件
5. 無料・有料間のCore Task品質Gate差: 0件
6. Mobile/Tablet/Desktop/WebのCore UX欠落: 0件
7. 端末差による無言の代替成功: 0件

性能測定はProfile別に行うが、品質合否は一つの共通Contractで判定する。

## 8. 他のCEO方針との整合

この不変条件は、次を同時に守る。

- Conversation is the product（会話そのものが製品）
- 話すだけ。あとはForgeが考える
- AIは意味を決める。Forgeは品質を保証する
- CapabilityはWidgetやTemplateと同義ではない
- 自由度のために安全を捨てず、精度のために自由度を捨てない
- Local First / Privacy First / Provider Independent
- 使いながら育て、内部の複雑さを利用者へ見せない
- Mock、未計測、文書だけを実成功として扱わない

## 9. Core UX invariants

端末やPlanに関係なく、Forge自身の中核体験にも次を適用する。

- 音声でも文字でも、自然にNeedを伝えられる
- 質問攻めにせず、今必要な質問だけをする
- 「話す→理解する→考える→作る→渡す」の進行を正直に示す
- 内部のModel、Runtime、Port、SDK、環境変数を通常利用者へ選ばせない
- Navigation、History、Saved Apps、Back、Retry、Cancelを飾りにしない
- 押せるControl（操作部品）は実際に動き、動かないControlを表示しない
- Completion summary（完了説明）は、実際に作成・保存・検証した内容だけを示す
- Regeneration（再生成）は古いCacheではなく現在の会話・修正・保存状態を使う
- 生成後も会話で育て、既存データと利用者の修正を保持する

これらは見た目だけの要件ではなく、同一品質を構成するRelease Gateである。
