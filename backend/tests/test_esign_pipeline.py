"""OSGB e-imza hattı — birim testler (mevcut akışları bozmadan)."""
from __future__ import annotations

import sys
from pathlib import Path

from app.services import esign_pipeline as pipe


def test_one_time_token_unique():
    a = pipe.new_one_time_token()
    b = pipe.new_one_time_token()
    assert a != b
    assert len(a) >= 32


def test_sha256_stable():
    assert pipe.sha256_hex(b"abc") == pipe.sha256_hex(b"abc")
    assert pipe.sha256_hex(b"abc") != pipe.sha256_hex(b"abd")


def test_pipeline_rejects_non_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(pipe, "upload_root", lambda: tmp_path)
    try:
        pipe.store_esign_bytes(1, "source", b"not-a-pdf")
        assert False, "should raise"
    except ValueError as exc:
        assert "PDF" in str(exc)


def test_pipeline_demo_structural(tmp_path, monkeypatch):
    monkeypatch.setattr(pipe, "upload_root", lambda: tmp_path)
    # Minimal unsigned PDF — structural verify without ByteRange → failed unless demo mode
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    # Fake signed with ByteRange marker for structural path
    signed = pdf + b"\n/ByteRange [0 1 2 3]\n/Contents <00>\n"
    result = pipe.pipeline_complete(
        source_pdf=pdf,
        signed_pdf=signed,
        source_sha256=pipe.sha256_hex(pdf),
        agent_meta={"mode": "demo-pfx", "signer_cn": "Demo", "signature_id": "abc"},
    )
    assert result["verification_status"] in ("demo_accepted", "failed")
    assert result["qualified_claim"] is False
    assert result["ocsp_status"]
    assert result["crl_status"]
    assert result["timestamp_status"]


def test_esign_router_mounted():
    from app.api import esign

    assert esign.router.prefix == "/esign"
    paths = {getattr(r, "path", None) for r in esign.router.routes}
    assert "/esign/requests" in paths
    assert "/esign/complete" in paths
    assert "/esign/meta" in paths


def test_approve_route_still_exists():
    from app.api.compliance_registers import da_router

    paths = {getattr(r, "path", None) for r in da_router.routes}
    assert "/document-approvals/{item_id}/approve" in paths


def test_agent_origins_isgsuite_not_ibysis():
    root = Path(__file__).resolve().parents[2] / "tools" / "isg-suite-signer"
    sys.path.insert(0, str(root))
    from agent.config import DEFAULT_ORIGINS, DEFAULT_PORT

    assert DEFAULT_PORT == 17000
    assert "https://www.isgsuite.tr" in DEFAULT_ORIGINS
    assert "https://uygulama.ibysis.com" not in DEFAULT_ORIGINS
