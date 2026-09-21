"""RiskAssessment.exposed_worker_count — İBYS tehlike kaynakları sayısal maruziyet alanı."""
from __future__ import annotations

import pytest
from pydantic import ValidationError


def _base_create_payload(**overrides):
    payload = {
        "company_id": 1,
        "hazard_id": 1,
        "activity": "Kaynak işlemi",
        "risk_definition": "Kaynak dumanına maruziyet",
        "department_name": "Üretim",
    }
    payload.update(overrides)
    return payload


def test_risk_create_accepts_exposed_worker_count():
    from app.schemas.risk import RiskCreate

    model = RiskCreate(**_base_create_payload(exposed_worker_count=12))
    assert model.exposed_worker_count == 12


def test_risk_create_exposed_worker_count_defaults_none():
    from app.schemas.risk import RiskCreate

    model = RiskCreate(**_base_create_payload())
    assert model.exposed_worker_count is None


def test_risk_create_rejects_negative_exposed_worker_count():
    from app.schemas.risk import RiskCreate

    with pytest.raises(ValidationError):
        RiskCreate(**_base_create_payload(exposed_worker_count=-1))


def test_risk_update_carries_exposed_worker_count():
    from app.schemas.risk import RiskUpdate

    model = RiskUpdate(exposed_worker_count=7)
    data = model.model_dump(exclude_unset=True)
    assert data == {"exposed_worker_count": 7}


def test_model_column_roundtrip(tmp_path):
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from app.models.entities import Base, RiskAssessment

    engine = create_engine(f"sqlite:///{(tmp_path / 'risk.db').as_posix()}")
    Base.metadata.create_all(bind=engine, tables=[RiskAssessment.__table__])
    Session = sessionmaker(bind=engine)

    with Session() as db:
        db.add(
            RiskAssessment(
                risk_code="R-TEST-1",
                company_id=1,
                hazard_id=1,
                activity="Yüksekte çalışma",
                risk_definition="Düşme riski",
                probability=3,
                severity=4,
                risk_score=12,
                risk_level="Orta",
                created_by_id=1,
                exposed_worker_count=9,
            )
        )
        db.add(
            RiskAssessment(
                risk_code="R-TEST-2",
                company_id=1,
                hazard_id=1,
                activity="Depo taşıma",
                risk_definition="Forklift çarpması",
                probability=2,
                severity=3,
                risk_score=6,
                risk_level="Düşük",
                created_by_id=1,
            )
        )
        db.commit()

    with Session() as db:
        rows = {r.risk_code: r for r in db.scalars(select(RiskAssessment)).all()}
        assert rows["R-TEST-1"].exposed_worker_count == 9
        assert rows["R-TEST-2"].exposed_worker_count is None
