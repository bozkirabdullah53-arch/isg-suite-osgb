"""ISG Suite / OSGB Signer agent — unit smoke."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = ROOT / "tools" / "isg-suite-signer"
sys.path.insert(0, str(AGENT_ROOT))


def test_demo_pades_sign_roundtrip(tmp_path):
    from agent.signing import ensure_demo_signing_cert, sign_pdf_pades

    try:
        import endesive  # noqa: F401
    except ImportError:
        import pytest

        pytest.skip("endesive not installed in test env")

    pfx = tmp_path / "demo.pfx"
    key, cert, extras = ensure_demo_signing_cert(pfx, "test-pass")
    pdf = b"""%PDF-1.4
1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj
2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj
3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents 4 0 R >>endobj
4 0 obj<< /Length 0 >>stream
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000068 00000 n 
0000000125 00000 n 
0000000224 00000 n 
trailer<< /Size 5 /Root 1 0 R >>
startxref
300
%%EOF
"""
    signed = sign_pdf_pades(pdf, key, cert, extras, reason="unit-test")
    assert signed.startswith(b"%PDF")
    assert len(signed) > len(pdf)
    assert b"/ByteRange" in signed or b"ByteRange" in signed


def test_document_approvals_has_local_sign_route():
    from app.api.compliance_registers import da_router

    paths = {getattr(r, "path", None) for r in da_router.routes}
    assert "/document-approvals/{item_id}/record-local-sign" in paths
    assert "/document-approvals/{item_id}/approve" in paths
