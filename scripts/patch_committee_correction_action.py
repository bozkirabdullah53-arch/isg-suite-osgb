from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            return
        raise SystemExit(f"marker not found in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


api = Path("backend/app/api/committee_professional.py")
replace_once(
    api,
    "from app.services.committee_meeting_pdf import build_committee_meeting_pdf\n",
    "from app.services.committee_correction import return_for_correction\n"
    "from app.services.committee_meeting_pdf import build_committee_meeting_pdf\n",
)
replace_once(
    api,
    "class MemberRemovalBody(BaseModel):\n"
    "    reason_code: str = Field(min_length=3, max_length=60)\n"
    "    reason_text: str | None = Field(default=None, max_length=1000)\n\n\n",
    "class MemberRemovalBody(BaseModel):\n"
    "    reason_code: str = Field(min_length=3, max_length=60)\n"
    "    reason_text: str | None = Field(default=None, max_length=1000)\n\n\n"
    "class CorrectionBody(BaseModel):\n"
    "    reason: str = Field(min_length=3, max_length=1000)\n"
    "    device_note: str | None = Field(default=None, max_length=240)\n\n\n",
)
submit_marker = '''@router.post("/meetings/{meeting_id}/signature-request")
def request_committee_signature(
'''
correction_endpoint = '''@router.post("/meetings/{meeting_id}/return-correction")
def return_committee_meeting_for_correction(
    meeting_id: int,
    payload: CorrectionBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW)),
):
    return return_for_correction(
        db,
        meeting_id=meeting_id,
        user=user,
        reason=payload.reason,
        device_note=payload.device_note,
        ip=_client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:500] or None,
    )


@router.post("/meetings/{meeting_id}/signature-request")
def request_committee_signature(
'''
replace_once(api, submit_marker, correction_endpoint)

workflow = Path("backend/app/services/committee_workflow.py")
replace_once(
    workflow,
    'meeting.get("approval_status") in {"draft", "rejected", "revision_required", "incomplete"}',
    'meeting.get("approval_status") in {"draft", "rejected", "returned_for_correction", "revision_required", "incomplete"}',
)

frontend = Path("frontend/src/committee_approval_queue.jsx")
replace_once(frontend, "  rejected: 'Reddedildi',\n", "  rejected: 'Reddedildi',\n  returned_for_correction: 'Düzeltmeye İade Edildi',\n")
replace_once(
    frontend,
    "  if (['incomplete', 'revision_required'].includes(value)) return 'warning';\n",
    "  if (['incomplete', 'revision_required', 'returned_for_correction'].includes(value)) return 'warning';\n",
)
replace_once(
    frontend,
    "    if (decision.action === 'reject' && !note.trim()) {\n"
    "      setErr('Red veya düzeltmeye iade için gerekçe zorunludur.');\n",
    "    if (decision.action !== 'approve' && !note.trim()) {\n"
    "      setErr('Red veya düzeltmeye iade için gerekçe zorunludur.');\n",
)
old_request = '''      await api(`/eyas/workflows/${workflowId}/${decision.action === 'approve' ? 'approve' : 'reject'}`, {
        method: 'POST',
        body: JSON.stringify({
          note: note.trim() || null,
          device_note: typeof navigator !== 'undefined' ? navigator.userAgent.slice(0, 200) : null,
        }),
      });
      setDecision(null); setNote('');
      setSuccess(decision.action === 'approve' ? 'Onay adımınız tamamlandı.' : 'Toplantı gerekçeli olarak reddedildi ve taslağa döndü.');
'''
new_request = '''      const deviceNote = typeof navigator !== 'undefined' ? navigator.userAgent.slice(0, 200) : null;
      if (decision.action === 'return') {
        await api(`/ohs-committee/meetings/${decision.row.id}/return-correction`, {
          method: 'POST',
          body: JSON.stringify({reason: note.trim(), device_note: deviceNote}),
        });
      } else {
        await api(`/eyas/workflows/${workflowId}/${decision.action === 'approve' ? 'approve' : 'reject'}`, {
          method: 'POST',
          body: JSON.stringify({note: note.trim() || null, device_note: deviceNote}),
        });
      }
      setDecision(null); setNote('');
      setSuccess(
        decision.action === 'approve'
          ? 'Onay adımınız tamamlandı.'
          : decision.action === 'return'
            ? 'Toplantı gerekçeli olarak düzeltmeye iade edildi.'
            : 'Toplantı gerekçeli olarak reddedildi ve taslağa döndü.'
      );
'''
replace_once(frontend, old_request, new_request)
replace_once(
    frontend,
    "              {row.pending_action === 'approve' && <button type=\"button\" className=\"danger\" disabled={busy} onClick={() => openDecision(row, 'reject')}><XCircle size={15} /> Reddet / İade</button>}\n",
    "              {row.pending_action === 'approve' && <button type=\"button\" className=\"warning-secondary\" disabled={busy} onClick={() => openDecision(row, 'return')}><RefreshCw size={15} /> Düzeltmeye İade</button>}\n"
    "              {row.pending_action === 'approve' && <button type=\"button\" className=\"danger\" disabled={busy} onClick={() => openDecision(row, 'reject')}><XCircle size={15} /> Reddet</button>}\n",
)
replace_once(
    frontend,
    "      {decision && <AppModal title={decision.action === 'approve' ? 'Toplantıyı Onayla' : 'Toplantıyı Reddet / Düzeltmeye İade Et'} close={() => !busy && setDecision(null)}>\n",
    "      {decision && <AppModal title={decision.action === 'approve' ? 'Toplantıyı Onayla' : decision.action === 'return' ? 'Toplantıyı Düzeltmeye İade Et' : 'Toplantıyı Reddet'} close={() => !busy && setDecision(null)}>\n",
)
replace_once(
    frontend,
    "          <p>{decision.action === 'approve' ? 'Belgeyi incelediğinizi ve kendi onay adımınızı tamamladığınızı doğrulayın.' : 'Toplantının neden reddedildiğini veya hangi düzeltmenin gerektiğini açıkça yazın.'}</p>\n",
    "          <p>{decision.action === 'approve' ? 'Belgeyi incelediğinizi ve kendi onay adımınızı tamamladığınızı doğrulayın.' : decision.action === 'return' ? 'Toplantıda yapılması gereken düzeltmeleri açık ve uygulanabilir biçimde yazın.' : 'Toplantının neden reddedildiğini açıkça yazın.'}</p>\n",
)
replace_once(
    frontend,
    "          <label className=\"field\"><span>{decision.action === 'approve' ? 'Onay notu (isteğe bağlı)' : 'Red / düzeltme gerekçesi (zorunlu)'}</span><textarea rows={4} value={note} onChange={(event) => setNote(event.target.value)} /></label>\n",
    "          <label className=\"field\"><span>{decision.action === 'approve' ? 'Onay notu (isteğe bağlı)' : decision.action === 'return' ? 'Düzeltme gerekçesi (zorunlu)' : 'Red gerekçesi (zorunlu)'}</span><textarea rows={4} value={note} onChange={(event) => setNote(event.target.value)} /></label>\n",
)
replace_once(
    frontend,
    "disabled={busy || (decision.action === 'reject' && !note.trim())}",
    "disabled={busy || (decision.action !== 'approve' && !note.trim())}",
)
replace_once(
    frontend,
    "{busy ? 'İşleniyor…' : decision.action === 'approve' ? 'Onayımı Tamamla' : 'Gerekçeli Olarak İade Et'}",
    "{busy ? 'İşleniyor…' : decision.action === 'approve' ? 'Onayımı Tamamla' : decision.action === 'return' ? 'Düzeltmeye İade Et' : 'Gerekçeli Olarak Reddet'}",
)

css = Path("frontend/src/committee-workflow.css")
text = css.read_text(encoding="utf-8")
if ".warning-secondary" not in text:
    text += "\n.committee-flow-actions .warning-secondary{background:#fff8e6;color:#9a5b00;border-color:#f3cf78}.committee-flow-actions .warning-secondary:hover{background:#fff1cc}\n"
css.write_text(text, encoding="utf-8")

tests = Path("backend/tests/test_committee_workflow.py")
text = tests.read_text(encoding="utf-8")
text = text.replace(
    "from app.services import committee_signature, committee_workflow\n",
    "from app.services import committee_correction, committee_signature, committee_workflow\n",
)
if "def test_return_for_correction_has_distinct_status_and_audit" not in text:
    text += r'''


def test_return_for_correction_has_distinct_status_and_audit():
    with SessionLocal() as db:
        company, users = _create_company_and_users(db)
        users["specialist"].mfa_enabled = True
        db.commit()
        meeting_id = _insert_meeting(db, company.id, users["admin"].id)
        workflow = EyasWorkflow(
            company_id=company.id,
            title="Düzeltmeye İade Kurul Akışı",
            document_kind="ohs_committee_meeting",
            source_document_id=None,
            source_sha256="d" * 64,
            status="in_progress",
            current_step_order=1,
            created_by_id=users["admin"].id,
            is_active=True,
        )
        db.add(workflow)
        db.flush()
        db.add_all([
            EyasStep(
                workflow_id=workflow.id,
                company_id=company.id,
                step_order=index,
                assignee_user_id=users[key].id,
                role_label=role_label,
                status="active" if index == 1 else "pending",
            )
            for index, key, role_label in (
                (1, "specialist", "İş Güvenliği Uzmanı"),
                (2, "physician", "İşyeri Hekimi"),
                (3, "employer", "İşveren / vekili"),
            )
        ])
        db.execute(
            text("UPDATE ohs_committee_meetings SET approval_workflow_id=:workflow_id, approval_status='waiting_for_review' WHERE id=:id"),
            {"workflow_id": workflow.id, "id": meeting_id},
        )
        db.commit()

        result = committee_correction.return_for_correction(
            db,
            meeting_id=meeting_id,
            user=users["specialist"],
            reason="Gündem maddesi sorumlu ve termin bilgisiyle düzeltilmelidir.",
            device_note="pytest",
        )
        assert result["approval_status"] == "returned_for_correction"
        status, approval_status = db.execute(
            text("SELECT status, approval_status FROM ohs_committee_meetings WHERE id=:id"),
            {"id": meeting_id},
        ).one()
        assert status == "draft"
        assert approval_status == "returned_for_correction"
        step_status, step_note = db.execute(
            text("SELECT status, note FROM eyas_steps WHERE workflow_id=:workflow_id AND step_order=1"),
            {"workflow_id": workflow.id},
        ).one()
        assert step_status == "rejected"
        assert step_note.startswith("[DÜZELTMEYE İADE]")
        assert db.scalar(
            text("SELECT id FROM audit_logs WHERE action='committee.meeting.return_for_correction' AND entity_id=:entity_id ORDER BY id DESC LIMIT 1"),
            {"entity_id": str(meeting_id)},
        )
'''
tests.write_text(text, encoding="utf-8")

print("committee correction action applied")
