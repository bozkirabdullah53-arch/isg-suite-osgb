"""Çalışan listesi, uzaktan eğitim atamalarının özetini göstermeli (iptal edilenler hariç)."""
from test_faz0_security import client  # noqa: F401  (paylaşılan istemci ve tohum veri)


def test_employee_list_shows_remote_training_assignment_summary(client):
    import app.core.database as dbmod
    from app.core.security import create_access_token
    from app.models.entities import Employee, User
    from app.models.remote_training import RemoteTrainingAssignment, RemoteTrainingProgram

    with dbmod.SessionLocal() as db:
        employee = db.query(Employee).filter(Employee.is_active.is_(True)).order_by(Employee.id).first()
        uzman = db.query(User).filter_by(email="uzman@example.com").one()
        # Aynı program ve çalışan için tek atama olabilir; her durum ayrı programa bağlanır.
        for status in ("completed", "in_progress", "cancelled"):
            program = RemoteTrainingProgram(
                company_id=employee.company_id,
                workplace_assignment_allowed=True,
                title=f"Özet testi uzaktan eğitimi ({status})",
                training_type="Yüksekte Çalışma",
                status="published",
            )
            db.add(program)
            db.flush()
            db.add(
                RemoteTrainingAssignment(
                    company_id=employee.company_id,
                    program_id=program.id,
                    employee_id=employee.id,
                    employee_name_snapshot=employee.full_name,
                    status=status,
                )
            )
        db.commit()
        employee_id = employee.id
        uzman_id = uzman.id

    token = create_access_token(str(uzman_id))
    result = client.get("/api/v1/employees", headers={"Authorization": f"Bearer {token}"})
    assert result.status_code == 200, result.text
    row = next(item for item in result.json() if item["id"] == employee_id)
    # İptal edilen atama sayılmaz: 3 kayıttan 2'si (tamamlanan + devam eden) görünür.
    assert row["remote_training"] == {"total": 2, "completed": 1, "in_progress": 1}
