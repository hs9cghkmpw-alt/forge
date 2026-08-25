"""Revisionテストの共通土台（FORGE-019A）。

---

## なぜ共通化したか

019Aで`/update`と`/converse`のUPDATEは、**本物のartifact capabilityと
Document bindingが揃っていなければ通らなくなった**（§1・§5）。

つまり「適当なJSONを投げて更新を試す」テストはもう書けない。
`/generate`で本物を1つ作り、返ってきた文書とハンドルをそのまま使う
——**利用者が実際に通る順序**である。

各テストがこの手順を書き写すと、束縛の仕様が変わったときに直す場所が
散らばる。1箇所にしておく。
"""

from __future__ import annotations

__all__ = ["ProvisionedArtifact", "provision_artifact"]

from dataclasses import dataclass


@dataclass(frozen=True)
class ProvisionedArtifact:
    """`/generate`が実際に返したもの。**手書きしない。**"""

    document: dict
    artifact_id: str
    version_token: str

    def update_payload(self, change_request: str, **overrides) -> dict:
        payload = {
            "forge_document": self.document,
            "change_request": change_request,
            "artifact_id": self.artifact_id,
            "seen_version_token": self.version_token,
        }
        payload.update(overrides)
        return payload


def provision_artifact(
    client, *, need: str = "毎日の収入と支出を記録して残高を見たい", provider: str = "mock",
) -> ProvisionedArtifact:
    """本番の`/generate`で1件作り、そのcapabilityを返す。"""
    response = client.post(
        "/api/v1/ai/generate",
        json={"input": {"natural_language": need,
                        "generation_options": {"provider": provider}}},
    )
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    artifact = result.get("artifact")
    assert artifact, "生成結果にartifact capabilityが付いていない"
    return ProvisionedArtifact(
        document=result["forge_document"],
        artifact_id=artifact["artifact_id"],
        version_token=artifact["version_token"],
    )
