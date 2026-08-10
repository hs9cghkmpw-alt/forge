# Diagram 8: Confidence Escalation Flow(CEO監査により優先順位を統一、2026-07-15）

以前は「confidence 0.3〜0.5未満はGenericへ」(本図)と「Domain
confidence 0.5未満はHIGH(確認)」(4.3節)が0.3〜0.5の範囲で矛盾して
いた。4.3節の3段階優先順位を必ず先に評価し、その後にconfidence帯を
見る、という順序へ統一した(0.3という閾値は廃止)。

```mermaid
flowchart TD
    START[段階のconfidence算出 + basis記録] --> P1{Priority1:<br/>Privacy/Safety/Permission<br/>関連のHIGH ambiguityか?}
    P1 -->|yes、confidenceの値に関係なく| ASK["Human Confirmation/Escalation<br/>(2.6節 Human Override)"]
    P1 -->|no| Q{overall_confidenceの範囲}
    Q -->|0.8以上| CONT[そのまま継続]
    Q -->|0.5〜0.8未満| MULTI[複数案を保持し仮設計<br/>Ambiguity MEDIUM相当]
    Q -->|0.5未満| P3{Priority3:<br/>低リスクかつ後から<br/>安全に変更可能か?}
    P3 -->|yes| GEN[Genericへ仮設計<br/>Priority3のcarve-out]
    P3 -->|no、Priority2適用| ASK

    MULTI --> CRITIC[Design Criticスコアで<br/>複数案から選択]
    CRITIC -->|それでも決着しない| ASK

    style CONT fill:#d4edda
    style MULTI fill:#fff3cd
    style GEN fill:#ffe5b4
    style ASK fill:#f8d7da
    style P1 fill:#f8d7da
    style P3 fill:#d1ecf1
```

14章(Confidence Model)・4.3節(Ambiguity Detectionの優先順位)・
ADR-007に対応。**Priority1(Privacy/Safety/Permission)は
confidenceの値を一切見ずに最優先で評価される**点が、以前の図との
最大の違いである。0.5未満の場合も、無条件でGenericへ落ちるのではなく、
Priority3(低リスクかつ安全に変更可能)のcarve-outを満たさない限り
確認要求(ASK)へ進む。
