"""Revision Unit Of Work — **1回の変更を、まとめて成立させる単位**
(FORGE-019C §4、2026-08-25)。

---

## 019B の順序では閉じきらなかった

019B は `validate → stage → commit → publish` を入れ、Feedback が
失敗したときの孤児を消した。方向は正しかったが、**失敗しうる段が
追記より後ろに残っていた**。

```
admit
→ RevisionRecord を stage
→ Feedback.record()   ← 追記専用。ここで書いたら戻せない
→ advance_to_revision()  ← ここが落ちると…
```

落ちると `RevisionRecord` は巻き戻せるが、**CORRECTED の Feedback と
その Learning Event は残る**。019B の文書はそれを仕様として書いていた
——「追記専用だから巻き戻せない」。

しかし**追記していなければ巻き戻す必要も無い。**

## この UoW の順序

```
prepare   何も書かずに、書けるかどうかを全部調べる
          - capability（handle）
          - 期待する版（version token）
          - 期待する中身（document binding）
          - Feedback を書けるか（prepare → staged）

stage     まだ誰にも見えない形で置く
          - RevisionRecord（observe=False。Learning は出ない）

commit    ここで初めて外から見える。落ちうるのは CAS だけ
          1. artifact を CAS で前進（競合すればここで落ちる）
          2. staged Feedback を追記        ← 追記は最後
          （2 で落ちたら 1 を restore する。lock 内なので誰も見ていない）

project   Learning Outbox へ入れる
          - 失敗しても Revision は成功のまま（pending として残る）
```

**落ちうる段を追記より前に集めた**のが 019C の要点である。

## ネットワークI/Oを transaction へ入れない

`project()` を分けてあるのは、将来 Learning が別プロセス・別ストアへ
出て行くからである。**確定の可否を、届くかどうかに依存させない。**

## DB化するときの移行境界

| いま | DB化したら |
|---|---|
| `registry.lock_for()` | `SELECT ... FOR UPDATE` / optimistic version |
| CAS（3値の比較） | `UPDATE ... WHERE version = ?` の affected rows |
| `commit()` の中身 | 1つの DB transaction |
| `LearningProjectionOutbox` | 同じ transaction 内の outbox 行 + 別 worker |
| `registry.restore()` | 不要（ROLLBACK が行う） |
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.ai.gateway.artifact_feedback import (
    ArtifactCasConflict,
    ArtifactFeedbackService,
    ArtifactHandle,
    ArtifactRegistry,
    FeedbackRejected,
    FeedbackSource,
    StagedFeedbackEvent,
    default_artifact_registry,
    default_feedback_service,
)
from app.ai.gateway.learning_foundation import AcceptanceSignal
from app.ai.gateway.revision_evidence import (
    RevisionEvidenceStore,
    RevisionRecord,
    default_revision_store,
)

__all__ = [
    "ArtifactCasConflict",
    "FeedbackCommitFailed",
    "RevisionCommit",
    "RevisionUnitOfWork",
    "UnitOfWorkStage",
]


class UnitOfWorkStage(str, Enum):
    """UoW がいまどこに居るか。**曖昧な中間状態を作らない。**"""

    OPEN = "open"
    PREPARED = "prepared"
    STAGED = "staged"
    COMMITTED = "committed"
    DISCARDED = "discarded"


class FeedbackCommitFailed(RuntimeError):
    """`prepare()` を通ったのに追記できなかった（FORGE-019C §4）。

    **想定外である。** `prepare()` は「書ける」と言ったので、ここで
    落ちるのは Forge 側の不整合を意味する。利用者には「記録できない
    ので成功にしない」として返す——記録の無い成功は、あとから
    `NO_FEEDBACK` に見える孤児を作る（019A §4）。
    """


@dataclass(frozen=True)
class RevisionCommit:
    """確定した1回の変更。"""

    record: RevisionRecord
    handle: ArtifactHandle
    """前進したあとの capability。"""


class RevisionUnitOfWork:
    """1回の変更の`prepare / stage / commit / project`。

    **使い捨てである。** 1つのインスタンスで2回 commit しない
    ——段の状態を持つので、使い回すと「どこまで進んだか」が壊れる。
    """

    def __init__(
        self,
        *,
        registry: ArtifactRegistry | None = None,
        revisions: RevisionEvidenceStore | None = None,
        feedback: ArtifactFeedbackService | None = None,
    ) -> None:
        self._registry = registry or default_artifact_registry()
        self._revisions = revisions or default_revision_store()
        self._feedback = feedback or default_feedback_service()
        self.stage_state = UnitOfWorkStage.OPEN
        self._expected: ArtifactHandle | None = None
        self._staged_feedback: StagedFeedbackEvent | None = None
        self._staged_record: RevisionRecord | None = None
        self._committed_event: object | None = None

    # -- prepare ----------------------------------------------------------

    def prepare(
        self,
        *,
        capability: ArtifactHandle,
        signal: AcceptanceSignal = AcceptanceSignal.CORRECTED,
        source: FeedbackSource = FeedbackSource.USER_EXPLICIT,
        idempotency_key: str = "",
    ) -> FeedbackRejected | None:
        """**1バイトも書かずに**、書けるかどうかを調べる。

        理由が返ればその時点で断る。`None` なら次へ進める。
        """
        prepared = self._feedback.prepare(
            signal=signal, handle=capability, source=source,
            idempotency_key=idempotency_key,
        )
        if isinstance(prepared, FeedbackRejected):
            return prepared
        self._expected = capability
        self._staged_feedback = prepared
        self.stage_state = UnitOfWorkStage.PREPARED
        return None

    # -- stage ------------------------------------------------------------

    def stage(self, record: RevisionRecord) -> RevisionRecord:
        """まだ誰にも見えない形で `RevisionRecord` を置く。

        `observe=False` なので **Learning Event はまだ出ない**。
        """
        if self.stage_state is not UnitOfWorkStage.PREPARED:
            msg = "stage() before prepare()"
            raise RuntimeError(msg)
        self._staged_record = self._revisions.record(record, observe=False)
        self.stage_state = UnitOfWorkStage.STAGED
        return self._staged_record

    # -- commit -----------------------------------------------------------

    def commit(self, *, revised_document: dict) -> RevisionCommit:
        """事実を確定する。**落ちうるのは CAS だけ**にしてある。

        呼び出し側は `registry.lock_for(handle)` を握った状態で呼ぶこと
        ——CAS が「誰かが先に進めた」を検出できても、検査と更新の間に
        別の要求を通してよい理由にはならない（後勝ちで消える変更が
        増えるだけである）。
        """
        if self.stage_state is not UnitOfWorkStage.STAGED:
            msg = "commit() before stage()"
            raise RuntimeError(msg)
        assert self._expected is not None
        assert self._staged_record is not None
        assert self._staged_feedback is not None

        # 1. 版を進める。**ここが唯一「競合で落ちる」段である。**
        advanced = self._registry.advance_to_revision(
            handle=self._expected.handle,
            revision_ref=self._staged_record.ref,
            revision_uid=self._staged_record.uid,
            document=revised_document,
            expected=self._expected,
        )

        # 2. 追記する。**追記は最後**——ここまで来れば戻す必要が無い。
        try:
            result = self._feedback.commit_prepared(self._staged_feedback)
            if not result.recorded:
                msg = "prepared correction could not be committed"
                raise FeedbackCommitFailed(msg)
            self._committed_event = result.event
        except Exception:
            # lock を握ったままなので、進めた版はまだ誰にも見えていない。
            self._registry.restore(self._expected)
            raise

        self.stage_state = UnitOfWorkStage.COMMITTED
        return RevisionCommit(record=self._staged_record, handle=advanced)

    # -- project ----------------------------------------------------------

    def project(self) -> None:
        """確定した事実を Learning へ投影する。

        **失敗しても例外を出さない。** 投影は Outbox に `pending` として
        残り、あとで `drain()` できる（019C §6）。
        """
        if self.stage_state is not UnitOfWorkStage.COMMITTED:
            msg = "project() before commit()"
            raise RuntimeError(msg)
        from app.ai.gateway.learning_outbox import (  # noqa: PLC0415
            default_projection_outbox,
        )

        outbox = default_projection_outbox()
        assert self._staged_record is not None
        self._record_episode()
        try:
            # 訂正が先、変更が後。**起きた順に投影する。**
            if self._committed_event is not None:
                outbox.submit(self._committed_event)
            self._revisions.publish(self._staged_record)
        except Exception as error:  # noqa: BLE001 — 確定した変更を投影で壊さない
            # **投影の段そのものが落ちた**（FORGE-019C §3.2）。
            #
            # ここで例外を通すと「サーバでは成功したが利用者には失敗」が
            # 復活する。事実は既に確定しており、取り消す方が嘘になる。
            # 保留として残し、`drain()` でやり直せるようにする。
            outbox.enqueue(self._staged_record, error=error)
            if self._committed_event is not None:
                outbox.enqueue(self._committed_event, error=error)

    def _record_episode(self) -> None:
        """この変更を **GenerationEpisode** として残す（FORGE-020 §18・§39）。

        ---

        ## なぜ本番の経路へ置くのか

        Forge は「作ったが本番から呼ばれない」を6回繰り返している
        （TD59 / 007 §10 / 010 Phase B / TD64 / TD69 / 016A）。共通するのは
        **呼び出し側が忘れずに呼ぶ設計**だったことである。

        Episode を「Agent が回ったときだけ記録する」形にすると、Agent が
        動かない今は**1件も生まれない**——`evaluate_for_export()` が
        テストからしか呼ばれていないのと同じ状態になる。

        変更は**本番が必ず通る**ので、ここへ置く。

        ## 記録するものと、しないもの

        * 直した対象の Evidence uid ・ 実際に変えた Provider → 残す
        * 利用者の発話・変更要求文・Document 本文 → **残さない**（006 §22）

        ## `training_use` は `UNKNOWN`

        本番の変更は「収集してよい」だけであって、「学習に使ってよい」
        ではない（§40）。同意の記録が無い以上 `UNKNOWN` にする
        ——Dataset Gate はこれを落とす。**楽観側へ倒さない。**
        """
        from app.ai.gateway.learning_events import (  # noqa: PLC0415
            Deployment,
            LearningDataProvenance,
            TrainingUse,
        )
        from app.ai.learning.episode import (  # noqa: PLC0415
            EpisodeOutcome,
            EpisodeStep,
            GenerationEpisode,
            StepKind,
            VerificationOutcome,
            default_episode_store,
        )

        record = self._staged_record
        if record is None:  # pragma: no cover — commit 済みなら必ず在る
            return
        try:
            episode = GenerationEpisode(
                task_id="forge.revision",
                provider=record.provider_id,
                deployment=(
                    Deployment.LOCAL if record.provider_id == "forge_deterministic"
                    else Deployment.UNKNOWN
                ),
                revision_evidence_uids=(record.uid,),
                validator_outcome=(
                    VerificationOutcome.PASSED if record.validator_passed
                    else VerificationOutcome.FAILED
                ),
                # build / test / runtime / visual は**この経路では測っていない**。
                # 既定の `UNKNOWN` のままにする（`PASSED` へ倒さない）。
                final_outcome=EpisodeOutcome.SUCCEEDED,
                provenance=LearningDataProvenance.USER_CORRECTION,
                training_use=TrainingUse.UNKNOWN,
            )
            episode.record_step(EpisodeStep(
                kind=StepKind.REPAIR, name=record.patch_mode.value,
                succeeded=True, references=(record.uid,),
            ))
            default_episode_store().start(episode)
        except Exception:  # noqa: BLE001, S110 — 記録の失敗で確定を壊さない
            pass

    # -- discard ----------------------------------------------------------

    def discard(self) -> None:
        """commit 前に諦める。**何も残さない。**"""
        if self.stage_state is UnitOfWorkStage.COMMITTED:
            msg = "a committed revision cannot be discarded"
            raise RuntimeError(msg)
        if self._staged_record is not None:
            self._revisions.discard(self._staged_record.ref)
            self._staged_record = None
        if self._staged_feedback is not None:
            self._feedback.discard_prepared(self._staged_feedback)
            self._staged_feedback = None
        self.stage_state = UnitOfWorkStage.DISCARDED
