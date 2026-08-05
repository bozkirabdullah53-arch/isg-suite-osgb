from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.training_nace_registry import (
    CATALOG_SCHEMA_VERSION,
    DURATION_RULES,
    build_registry,
    classify_catalog_row,
    legacy_training_report,
    materialize_registry,
    normalize_nace_code,
    registry_content_hash,
    registry_report,
)


def test_exact_nace_normalization_preserves_six_digit_activity():
    assert normalize_nace_code("27.20.01") == "27.20.01"
    assert normalize_nace_code("nace_27_20_01") == "27.20.01"
    assert normalize_nace_code("272001") == "27.20.01"
    assert normalize_nace_code("27.20") is None
    assert normalize_nace_code("aku_uretimi") is None


def test_registry_contains_every_official_catalog_record_once():
    rows = build_registry()
    assert len(rows) == 2141
    assert len({row.nace_code for row in rows}) == 2141
    assert all(len(row.nace_code) == 8 for row in rows)
    assert all(row.description for row in rows)


def test_registry_hash_is_deterministic():
    first = registry_content_hash()
    second = registry_content_hash()
    assert first == second
    assert len(first) == 64


def test_duration_rules_separate_instruction_and_scheduled_time():
    assert DURATION_RULES["Az Tehlikeli"] == {
        "lesson_hours": 8,
        "instruction_minutes": 360,
        "scheduled_minutes": 480,
        "sector_lesson_hours": 2,
        "sector_instruction_minutes": 90,
        "sector_scheduled_minutes": 120,
    }
    assert DURATION_RULES["Tehlikeli"]["instruction_minutes"] == 540
    assert DURATION_RULES["Tehlikeli"]["scheduled_minutes"] == 720
    assert DURATION_RULES["Çok Tehlikeli"]["instruction_minutes"] == 720
    assert DURATION_RULES["Çok Tehlikeli"]["scheduled_minutes"] == 960


def test_battery_activity_keeps_exact_nace_and_explicit_risks():
    row = next(item for item in build_registry() if item.nace_code == "27.20.01")
    assert row.nace_key == "nace_27_20_01"
    assert row.profile_code == "aku_uretimi"
    assert {"lead", "sulfuric_acid", "hydrogen", "electrical"} <= set(row.risk_tags)
    assert row.mapping_status == "mapped"


def test_salon_profile_never_inherits_industrial_explosive_risks():
    row = classify_catalog_row({
        "nace": "96.23.01",
        "name": "Kuaförlük ve güzellik salonu faaliyetleri",
        "hazard_class": "Tehlikeli",
        "profile": "guzellik_kuafor_spa",
        "topics": ["Kozmetik ürünlerle güvenli çalışma"],
    })
    assert "cosmetic_chemical" in row.risk_tags
    assert "explosive_atmosphere" not in row.risk_tags
    assert "process_safety" not in row.risk_tags


def test_fishing_profile_never_inherits_tractor_or_pesticide_risks():
    row = classify_catalog_row({
        "nace": "03.11.01",
        "name": "Deniz balıkçılığı",
        "hazard_class": "Tehlikeli",
        "profile": "balikcilik_su_urunleri",
        "topics": ["Teknede güvenli çalışma ve denize düşme"],
    })
    assert {"marine_work", "drowning"} <= set(row.risk_tags)
    assert "tractor" not in row.risk_tags
    assert "pesticide" not in row.risk_tags


def test_unmapped_profile_is_review_required_not_compliant():
    row = classify_catalog_row({
        "nace": "69.10.01",
        "name": "Hukuk faaliyetleri",
        "hazard_class": "Az Tehlikeli",
        "profile": "not_reviewed_profile",
        "topics": ["Ofis ergonomisi"],
    })
    assert row.mapping_status == "review_required"
    assert "risk_mapping_review_required" in row.validation_errors


def test_invalid_nace_or_missing_topics_is_blocked():
    row = classify_catalog_row({
        "nace": "invalid",
        "name": "Geçersiz kayıt",
        "hazard_class": "Tehlikeli",
        "profile": "genel_uretim",
        "topics": [],
    })
    assert row.mapping_status == "blocked"
    assert "invalid_exact_nace" in row.validation_errors
    assert "missing_topics" in row.validation_errors


def test_report_never_marks_entire_catalog_compliant():
    report = registry_report()
    assert report["schema_version"] == CATALOG_SCHEMA_VERSION
    assert report["entry_count"] == 2141
    assert report["all_compliant"] is False
    assert sum(report["status_counts"].values()) == 2141
    assert report["status_counts"]["review_required"] + report["status_counts"]["blocked"] > 0


def _create_registry_tables(db: Session) -> None:
    db.execute(text("""
        CREATE TABLE training_nace_catalog_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_code VARCHAR(80) NOT NULL,
            content_hash VARCHAR(64) NOT NULL UNIQUE,
            source_label VARCHAR(300) NOT NULL,
            source_url VARCHAR(1000) NOT NULL,
            status VARCHAR(20) NOT NULL,
            entry_count INTEGER NOT NULL,
            created_by_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            activated_by_id INTEGER,
            activated_at DATETIME
        )
    """))
    db.execute(text("""
        CREATE TABLE training_nace_catalog_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL,
            nace_code VARCHAR(10) NOT NULL,
            nace_key VARCHAR(20) NOT NULL,
            description VARCHAR(1000) NOT NULL,
            division_code VARCHAR(2) NOT NULL,
            activity_group_code VARCHAR(5) NOT NULL,
            main_sector_code VARCHAR(2) NOT NULL,
            main_sector_name VARCHAR(300) NOT NULL,
            profile_code VARCHAR(140) NOT NULL,
            profile_name VARCHAR(300) NOT NULL,
            hazard_class VARCHAR(30) NOT NULL,
            risk_tags_json TEXT NOT NULL,
            special_risks_json TEXT NOT NULL,
            topics_json TEXT NOT NULL,
            lesson_hours INTEGER NOT NULL,
            instruction_minutes INTEGER NOT NULL,
            scheduled_minutes INTEGER NOT NULL,
            sector_lesson_hours INTEGER NOT NULL,
            sector_instruction_minutes INTEGER NOT NULL,
            sector_scheduled_minutes INTEGER NOT NULL,
            mapping_status VARCHAR(30) NOT NULL,
            validation_errors_json TEXT NOT NULL,
            UNIQUE(version_id, nace_code)
        )
    """))


def test_materialization_is_immutable_and_idempotent():
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as db:
        _create_registry_tables(db)
        first = materialize_registry(db, created_by_id=1)
        db.commit()
        second = materialize_registry(db, created_by_id=1)
        assert first["created"] is True
        assert first["status"] == "candidate"
        assert first["entry_count"] == 2141
        assert second["created"] is False
        assert second["content_hash"] == first["content_hash"]
        version_count = db.execute(text("SELECT COUNT(*) FROM training_nace_catalog_versions")).scalar_one()
        entry_count = db.execute(text("SELECT COUNT(*) FROM training_nace_catalog_entries")).scalar_one()
        assert version_count == 1
        assert entry_count == 2141


def test_legacy_profile_is_reported_without_guessing_exact_nace():
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as db:
        db.execute(text("""
            CREATE TABLE training_sessions (
                id INTEGER PRIMARY KEY,
                company_id INTEGER NOT NULL,
                branch_id INTEGER,
                sector VARCHAR(140),
                hazard_class VARCHAR(30),
                duration_hours INTEGER,
                status VARCHAR(30),
                created_at DATETIME
            )
        """))
        db.execute(text("""
            INSERT INTO training_sessions
                (id, company_id, branch_id, sector, hazard_class, duration_hours, status, created_at)
            VALUES
                (1, 10, NULL, 'tarim', 'Tehlikeli', 12, 'PLANNED', CURRENT_TIMESTAMP)
        """))
        report = legacy_training_report(db)
        item = report["items"][0]
        assert item["resolved_nace_code"] is None
        assert item["candidate_nace_count"] > 1
        assert "legacy_exact_nace_missing" in item["errors"]
        assert "legacy_profile_ambiguous" in item["errors"]
        assert "workplace_missing" in item["errors"]
        assert item["status"] == "review_required"
