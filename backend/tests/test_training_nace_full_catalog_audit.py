from scripts.audit_nace_training_catalog import audit_catalog


def test_every_active_nace_training_mapping_passes_fail_closed_audit():
    result = audit_catalog()

    assert result["official_nace_count"] == 2141
    assert result["unique_nace_count"] == 2141
    assert result["issues"] == []
    assert result["ok"] is True
