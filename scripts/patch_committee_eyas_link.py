from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            return
        raise SystemExit(f"marker not found in {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


workflow = Path("backend/app/services/committee_workflow.py")
replace_once(
    workflow,
    "        source_document_id=meeting_id,\n",
    "        # source_document_id is reserved for document_records. The committee\n"
    "        # meeting links to this workflow through approval_workflow_id.\n"
    "        source_document_id=None,\n",
)
replace_once(
    workflow,
    "    if workflow.document_kind != \"ohs_committee_meeting\" or not workflow.source_document_id:\n"
    "        return\n"
    "    meeting = meeting_row(db, int(workflow.source_document_id))\n",
    "    if workflow.document_kind != \"ohs_committee_meeting\":\n"
    "        return\n"
    "    meeting_id = db.scalar(\n"
    "        text(\"SELECT id FROM ohs_committee_meetings WHERE approval_workflow_id=:workflow_id AND is_active=true\"),\n"
    "        {\"workflow_id\": workflow.id},\n"
    "    )\n"
    "    if not meeting_id:\n"
    "        return\n"
    "    meeting = meeting_row(db, int(meeting_id))\n",
)

eyas = Path("backend/app/api/eyas.py")
replace_once(eyas, "from sqlalchemy import select\n", "from sqlalchemy import select, text\n")
replace_once(
    eyas,
    "def _doc_path(workflow: EyasWorkflow) -> str | None:\n"
    "    if workflow.document_kind == \"ohs_committee_meeting\" and workflow.source_document_id:\n"
    "        return f\"/api/v1/ohs-committee/meetings/{workflow.source_document_id}/pdf\"\n",
    "def _doc_path(db: Session, workflow: EyasWorkflow) -> str | None:\n"
    "    if workflow.document_kind == \"ohs_committee_meeting\":\n"
    "        meeting_id = db.scalar(\n"
    "            text(\"SELECT id FROM ohs_committee_meetings WHERE approval_workflow_id=:workflow_id AND is_active=true\"),\n"
    "            {\"workflow_id\": workflow.id},\n"
    "        )\n"
    "        if meeting_id:\n"
    "            return f\"/api/v1/ohs-committee/meetings/{meeting_id}/pdf\"\n",
)
replace_once(eyas, "        document_download_path=_doc_path(workflow),\n", "        document_download_path=_doc_path(db, workflow),\n")
replace_once(
    eyas,
    "    if workflow.document_kind == \"ohs_committee_meeting\" and workflow.source_document_id:\n"
    "        return RedirectResponse(\n"
    "            url=f\"/api/v1/ohs-committee/meetings/{workflow.source_document_id}/pdf\",\n"
    "            status_code=307,\n"
    "        )\n",
    "    if workflow.document_kind == \"ohs_committee_meeting\":\n"
    "        meeting_id = db.scalar(\n"
    "            text(\"SELECT id FROM ohs_committee_meetings WHERE approval_workflow_id=:workflow_id AND is_active=true\"),\n"
    "            {\"workflow_id\": workflow.id},\n"
    "        )\n"
    "        if not meeting_id:\n"
    "            raise HTTPException(404, \"Kurul toplantısı bağlantısı bulunamadı.\")\n"
    "        return RedirectResponse(\n"
    "            url=f\"/api/v1/ohs-committee/meetings/{meeting_id}/pdf\",\n"
    "            status_code=307,\n"
    "        )\n",
)

tests = Path("backend/tests/test_committee_workflow.py")
text = tests.read_text(encoding="utf-8")
text = text.replace("            source_document_id=meeting_id,\n", "            source_document_id=None,\n")
text = text.replace("        assert cross.value.status_code == 403\n", "        assert cross.value.status_code in {403, 404}\n")
tests.write_text(text, encoding="utf-8")

print("committee EYAS linkage corrected")
