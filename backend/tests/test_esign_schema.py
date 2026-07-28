"""E-imza orkestrasyon şema testleri (Desktop v0.10 birleşimi)."""
import pytest
from pydantic import ValidationError

from app.schemas.esign import ESignRequestCreate


def test_esign_sha256_validation():
    item = ESignRequestCreate(
        company_id=1,
        document_title="Risk Değerlendirmesi",
        document_sha256="a" * 64,
        required_signer_name="Ahmet Yılmaz",
        required_signer_role="İşveren",
    )
    assert item.document_sha256 == "a" * 64
    assert item.signing_format == "PAdES"


def test_esign_rejects_invalid_hash():
    with pytest.raises(ValidationError):
        ESignRequestCreate(
            company_id=1,
            document_title="Risk Raporu",
            document_sha256="xyz" * 22,
            required_signer_name="Ahmet Yılmaz",
            required_signer_role="İşveren",
        )


def test_esign_orch_router_separate_from_agent_pipeline():
    from app.api import esign, esign_orch

    assert esign.router.prefix == "/esign"
    assert esign_orch.router.prefix == "/esign-orch"
    agent_paths = {getattr(r, "path", None) for r in esign.router.routes}
    orch_paths = {getattr(r, "path", None) for r in esign_orch.router.routes}
    assert "/esign/complete" in agent_paths
    assert "/esign-orch/requests" in orch_paths
    assert "/esign-orch/requests/{request_id}/token" in orch_paths
