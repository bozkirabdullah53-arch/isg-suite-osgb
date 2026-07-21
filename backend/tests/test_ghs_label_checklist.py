"""0.9.121 — GHS/CLP tehlike etiketi checklist stub."""
from __future__ import annotations

from app.services.ghs_label_checklist import (
    GHS_ENGINE,
    parse_checklist,
    serialize_selected,
)


def test_parse_and_serialize_roundtrip():
    raw = serialize_selected(["GHS02", "ghs05", "GHS99", "GHS02"])
    body = parse_checklist(raw)
    assert body["engine"] == GHS_ENGINE
    assert body["selected"] == ["GHS02", "GHS05"]
    assert body["count"] == 2
    assert any(i["code"] == "GHS02" and i["checked"] for i in body["items"])
    assert any(i["code"] == "GHS01" and not i["checked"] for i in body["items"])


def test_parse_empty():
    body = parse_checklist(None)
    assert body["selected"] == []
    assert body["count"] == 0
    assert len(body["items"]) == 9
