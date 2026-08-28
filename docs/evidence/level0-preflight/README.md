# Level 0 Probe Preflight Evidence

`FORGE-020A4` で追加した **実モデル実測の前段**。

`python scripts/preflight_local_model_level0.py` は production `/generate` を
`provider=mock` で通し、software structure の仕事が本当に
`entity_synthesis` stage へ渡る Need かを typed Evidence で確認する。

## これは Level 0 の証拠ではない

ここに出る JSON は **Test Double による適格性確認**である。

- `eligible_for_real_run=true` でも `Real Local Model runs` は増えない
- Local Model が同じ構造を生成できる保証ではない
- Local Model の性能評価でもない
- Promotion / Dataset positive example に使わない

本当の Level 0 Evidence は `docs/evidence/level0/` に置く。

## 意味

`eligible_for_real_run=true` が言えるのは次だけ。

> この Need は Curated / deterministic path に先取りされず、production path が
> AI Entity Synthesis を実際に呼び、Test Double の構造を採用した。したがって
> **実 Local Model に structure generation の仕事を渡す測定候補として適格**。

その後に Runtime-capable Execution Host で
`python scripts/verify_local_model_level0.py` を実行して初めて Level 0 を測る。
