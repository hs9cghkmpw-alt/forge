"""AI Gateway — Forge Brain と Provider の間に立つ層。

構成(FORGE-AI-FOUNDATION-010 Phase B時点):

* `tasks.py` — `ForgeTask`。Forgeが行う仕事の単位。
* `ai_router.py` — `AIRouter`。Taskごとに使えるProviderを選び、
  失敗したら次を試す。**AI呼び出しの唯一の出口**である
  (`tests/test_router_anti_bypass.py`が迂回経路の不在を固定している)。
* `ai_errors.py` — 失敗の分類(`ErrorKind`)。「次に何をすべきか」で分ける。
* `provider_state.py` — Quota / Circuit Breakerの状態。
* `benchmark.py` / `impact_benchmark.py` — Task単位の実測。

`model_gateway.py`(`ModelGateway`)はPhase Bで削除した。`AIRouter`と
責務が重複しており、**本番から一度も呼ばれないまま**Unit Testだけが
通り続けていた(TD59)。同じことをする層を2つ残さない。
"""
