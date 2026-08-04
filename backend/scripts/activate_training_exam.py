from pathlib import Path

# Tüm NACE kayıtlarını merkezi sektör profiline dönüştür.
# Böylece eğitim belgesi ve soru bankası aynı profil kodunu kullanır.
topics_path = Path('app/services/training_topics.py')
topics_text = topics_path.read_text(encoding='utf-8')
old_resolver = '''def sektor_kodu_cozumle(sektor: str | None) -> str:
    if not sektor:
        return "genel_uretim"
    raw = sektor.strip()
    if raw in SEKTOREL_EGITIM_KONULARI:
        return raw
    nace_code = "nace_" + raw.replace(".", "_")
    if nace_code in SEKTOREL_EGITIM_KONULARI:
        return nace_code
    for kod, ad in SEKTOR_SECENEKLERI:
        if ad.casefold() == raw.casefold():
            return kod
    for kod, ad in PROFIL_ADLARI.items():
        if ad.casefold() == raw.casefold():
            return kod
    if raw in ("01", "02", "03", "04", "05"):
        return "genel_uretim"
    return "genel_uretim"
'''
new_resolver = '''def sektor_kodu_cozumle(sektor: str | None) -> str:
    if not sektor:
        return "genel_uretim"
    raw = sektor.strip()
    # Katalogdaki NACE kaydı varsa doğrudan bağlı olduğu merkezi profile dön.
    if raw in SEKTOR_PROFIL:
        return SEKTOR_PROFIL[raw]
    if raw in SEKTOREL_EGITIM_KONULARI:
        return raw
    nace_code = "nace_" + raw.replace(".", "_")
    if nace_code in SEKTOR_PROFIL:
        return SEKTOR_PROFIL[nace_code]
    if nace_code in SEKTOREL_EGITIM_KONULARI:
        return nace_code
    for kod, ad in SEKTOR_SECENEKLERI:
        if ad.casefold() == raw.casefold():
            return SEKTOR_PROFIL.get(kod, kod)
    for kod, ad in PROFIL_ADLARI.items():
        if ad.casefold() == raw.casefold():
            return kod
    if raw in ("01", "02", "03", "04", "05"):
        return "genel_uretim"
    return "genel_uretim"
'''
if old_resolver in topics_text:
    topics_text = topics_text.replace(old_resolver, new_resolver)
elif new_resolver not in topics_text:
    raise RuntimeError('sektor_kodu_cozumle gövdesi beklenen yapıda değil')
topics_path.write_text(topics_text, encoding='utf-8')
print('All NACE records now resolve to central sector profiles.')

# Sınav endpoint'ini yayımlanmış soru bankası + snapshot üreticisine bağla.
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
