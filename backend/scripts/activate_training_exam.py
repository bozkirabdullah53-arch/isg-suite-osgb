from pathlib import Path

# NACE -> özel eğitim profili eşlemeleri. Bu eşleme hem belge konularını hem
# yayımlanmış soru bankası kapsamını aynı sektör profiline bağlar.
topics_path = Path('app/services/training_topics.py')
topics_text = topics_path.read_text(encoding='utf-8')
profile_marker = '    raw = str(sektor or "").strip()\n'
profile_patch = '''    raw = str(sektor or "").strip()\n    explicit_nace_profiles = {\n        "nace_27_20_01": "aku_uretimi",\n        "27.20.01": "aku_uretimi",\n    }\n    if raw in explicit_nace_profiles:\n        return explicit_nace_profiles[raw]\n'''
if '"nace_27_20_01": "aku_uretimi"' not in topics_text:
    if profile_marker not in topics_text:
        raise RuntimeError('sektor_kodu_cozumle başlangıcı bulunamadı')
    topics_text = topics_text.replace(profile_marker, profile_patch, 1)
    topics_path.write_text(topics_text, encoding='utf-8')
    print('NACE 27.20.01 -> aku_uretimi profile mapping activated.')

path = Path('app/api/trainings.py')
text = path.read_text(encoding='utf-8')

import_line = 'from app.services.training_exam_pdf import build_exam_pdf\n'
if import_line not in text:
    marker = 'from app.services.training_pdfs import build_attendance_pdf, build_certificates_pdf\n'
    text = text.replace(marker, marker + import_line)

endpoint_marker = '@router.get("/{training_id}/exam.pdf")'
if endpoint_marker not in text:
    block = r'''

@router.get("/{training_id}/exam.pdf")
def training_exam_pdf(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Yayımlanmış soru bankasından 5 ortak + 5 teknik + 5 sektör soruluk sabit sınav üretir."""
    row = _load_training(db, training_id)
    ensure_access(db, user, row.company_id)
    company = db.get(Company, row.company_id)
    try:
        pdf_bytes = build_exam_pdf(
            company_name=company.name if company else str(row.company_id),
            training=row,
            db=db,
            created_by_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="egitim-{training_id}-isg-sinavi.pdf"'},
    )
'''
    text = text.rstrip() + block + '\n'
else:
    old = '''        pdf_bytes = build_exam_pdf(
            company_name=company.name if company else str(row.company_id),
            training=row,
        )'''
    new = '''        pdf_bytes = build_exam_pdf(
            company_name=company.name if company else str(row.company_id),
            training=row,
            db=db,
            created_by_id=user.id,
        )'''
    text = text.replace(old, new)

path.write_text(text, encoding='utf-8')
print('Training snapshot exam endpoint activated.')
