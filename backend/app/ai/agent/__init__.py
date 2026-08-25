"""Local Agent — Forge の Local AI が**道具を使って仕事をする**ための層
(FORGE-020B、2026-08-25)。

```
Local AI（Base Model は交換可能）
   ↓  structured tool call
Agent Loop            生成 → 検証 → build/test → 診断 → 修正 → 再検証
   ↓
Tool Broker           どの道具が在るか / 呼び出しの形を守らせる
   ↓
Permission Broker     AUTO / SANDBOX / CONFIRM / FORBIDDEN
   ↓
Tool                  file / search / build / test / web / browser
```

**Modelへ直接OS権限を渡さない。** Model が言えるのは「この道具を、
この引数で使いたい」までであり、実行してよいかを決めるのは Forge である。
"""
