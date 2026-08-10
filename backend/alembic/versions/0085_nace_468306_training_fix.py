"""Correct NACE 46.83.06 training classification snapshots.

Revision ID: 0085_nace_468306_training_fix
Revises: 0084_regulatory_identity_vault
"""
from __future__ import annotations

import hashlib
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0085_nace_468306_training_fix"
down_revision: Union[str, None] = "0084_regulatory_identity_vault"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_PROFILE = "metal_yapi_elemanlari_toptan"
_NEW_PROFILE_NAME = "Metal Yapı Elemanları Toptan Ticareti"
_NEW_TOPICS = [
    "Uzun ve ağır metal yapı elemanlarının vinç, forklift ve uygun kaldırma aparatlarıyla güvenli yüklenmesi",
    "Konstrüksiyon elemanlarının devrilmeye ve kaymaya karşı takozlanması, bağlanması ve güvenli istiflenmesi",
    "Keskin kenarlar, çapaklar, sıkışma ve ezilmelere karşı el-göz-ayak koruması",
    "Araç-yaya yolları, yükleme sahası, dorse yanaşması ve kör nokta güvenliği",
    "Açık saha depolaması, hava koşulları, yük sabitleme ve sevkiyat öncesi kontroller",
]
_NEW_TAGS = ["lifting", "load_securing", "storage_stability", "vehicle_traffic", "sharp_edges"]
_NEW_SPECIAL = ["dropped_load", "load_collapse", "vehicle_collision"]

_OLD_PROFILE = "depo_lojistik"
_OLD_PROFILE_NAME = "Depo, Lojistik ve Dağıtım Merkezi"
_OLD_TOPICS = [
    "Forklift, transpalet ve yaya trafiği güvenliği",
    "Raf sistemleri, istif ve yük düşmesi riskleri",
    "Yükleme rampası, dorse ve araç sabitleme",
    "Elle taşıma, kaldırma yardımcıları ve ergonomi",
    "Akü şarj alanı, yangın ve acil çıkış düzeni",
]
_OLD_TAGS = ["forklifts", "storage_racking", "loading_docks", "traffic", "manual_handling"]


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _snapshot_table():
    return sa.table(
        "training_nace_snapshots",
        sa.column("id", sa.Integer()),
        sa.column("nace_code", sa.String()),
        sa.column("content_profile_code", sa.String()),
        sa.column("content_profile_name", sa.String()),
        sa.column("training_topics_json", sa.Text()),
        sa.column("technical_risk_tags_json", sa.Text()),
        sa.column("special_risks_json", sa.Text()),
        sa.column("classification_status", sa.String()),
        sa.column("catalog_hash", sa.String()),
        sa.column("source_snapshot_json", sa.Text()),
    )


def _rewrite(*, profile: str, profile_name: str, topics: list[str], tags: list[str], special: list[str]) -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("training_nace_snapshots"):
        return
    table = _snapshot_table()
    rows = bind.execute(
        sa.select(table.c.id, table.c.source_snapshot_json).where(table.c.nace_code == "46.83.06")
    ).all()
    for row in rows:
        try:
            source = json.loads(row.source_snapshot_json or "{}")
        except (TypeError, json.JSONDecodeError):
            source = {}
        if not isinstance(source, dict):
            source = {}
        source.update(
            {
                "content_profile_code": profile,
                "content_profile_name": profile_name,
                "training_topics": topics,
                "technical_risk_tags": tags,
                "special_risks": special,
                "risk_mapping": {
                    "status": "verified",
                    "source": "controlled_profile_map_v1",
                    "review_reasons": [],
                },
            }
        )
        topic_mapping = source.get("topic_mapping")
        if not isinstance(topic_mapping, dict):
            topic_mapping = {}
        topic_mapping.update(
            {
                "source": "canonical_training_topics_v1",
                "catalog_topics_overridden": True,
                "corrected_by": revision,
            }
        )
        source["topic_mapping"] = topic_mapping
        source_json = _canonical(source)
        bind.execute(
            table.update()
            .where(table.c.id == row.id)
            .values(
                content_profile_code=profile,
                content_profile_name=profile_name,
                training_topics_json=_canonical(topics),
                technical_risk_tags_json=_canonical(tags),
                special_risks_json=_canonical(special),
                classification_status="verified",
                catalog_hash=hashlib.sha256(source_json.encode("utf-8")).hexdigest(),
                source_snapshot_json=source_json,
            )
        )


def upgrade() -> None:
    _rewrite(
        profile=_NEW_PROFILE,
        profile_name=_NEW_PROFILE_NAME,
        topics=_NEW_TOPICS,
        tags=_NEW_TAGS,
        special=_NEW_SPECIAL,
    )


def downgrade() -> None:
    _rewrite(
        profile=_OLD_PROFILE,
        profile_name=_OLD_PROFILE_NAME,
        topics=_OLD_TOPICS,
        tags=_OLD_TAGS,
        special=[],
    )
