from pathlib import Path

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
    """Seçili NACE, tehlike sınıfı ve eğitim konu havuzundan 15 soruluk sınav üretir."""
    row = _load_training(db, training_id)
    ensure_access(db, user, row.company_id)
    company = db.get(Company, row.company_id)
    try:
        pdf_bytes = build_exam_pdf(
            company_name=company.name if company else str(row.company_id),
            training=row,
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

path.write_text(text, encoding='utf-8')
print('Training exam endpoint activated.')
