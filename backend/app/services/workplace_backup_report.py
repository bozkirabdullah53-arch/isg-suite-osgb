"""Build a self-contained, printable HTML view of a workplace backup."""
from __future__ import annotations

import json
from html import escape
from typing import Any


DOMAIN_LABELS = {
    "branches": "Şubeler",
    "employees": "Çalışanlar",
    "personnel_profiles": "Personel Profilleri",
    "health_records": "Sağlık Kayıtları",
    "risk_assessments": "Risk Değerlendirmeleri",
    "risk_revisions": "Risk Revizyonları",
    "risk_media": "Risk Belgeleri ve Görselleri",
    "field_inspections": "Saha Denetimleri",
    "ppe_assignments": "KKD Zimmetleri",
    "ppe_inventory": "KKD Envanteri",
    "chemical_products": "Kimyasal Ürünler / SDS-PKD",
    "training_sessions": "Eğitimler",
    "training_participants": "Eğitim Katılımcıları",
    "documents": "Belgeler",
    "incidents": "İş Kazaları ve Olaylar",
    "annual_plan_items": "Yıllık Plan Kayıtları",
    "annual_evaluations": "Yıllık Değerlendirmeler",
    "committee_meetings": "İSG Kurulu Toplantıları",
    "committee_members": "İSG Kurulu Üyeleri",
    "drills": "Tatbikatlar",
    "emergency_plans": "Acil Durum Planları",
    "emergency_teams": "Acil Durum Ekipleri",
    "work_permits": "Çalışma İzinleri",
    "contractors": "Alt İşverenler",
    "visitor_passes": "Ziyaretçi Kayıtları",
    "periodic_controls": "Periyodik Kontroller",
    "workplace_measurements": "Ortam Ölçümleri",
    "workplace_departments": "İşyeri Bölümleri",
    "workplace_assignments": "İşyeri Görevlendirmeleri",
    "service_contracts": "Hizmet Sözleşmeleri",
}

COLUMN_LABELS = {
    "id": "Kayıt No", "company_id": "İşyeri No", "branch_id": "Şube No",
    "employee_id": "Çalışan No", "training_id": "Eğitim No", "full_name": "Ad Soyad",
    "first_name": "Ad", "last_name": "Soyad", "name": "Adı", "title": "Başlık",
    "description": "Açıklama", "status": "Durum", "notes": "Notlar", "date": "Tarih",
    "created_at": "Oluşturulma Tarihi", "updated_at": "Güncellenme Tarihi",
    "start_date": "Başlangıç Tarihi", "end_date": "Bitiş Tarihi",
    "email": "E-posta", "phone": "Telefon", "national_id": "T.C. Kimlik No",
    "job_title": "Görevi", "department": "Bölüm", "is_active": "Aktif",
}


def _text(value: Any) -> str:
    if value is None:
        return "—"
    if value is True:
        return "Evet"
    if value is False:
        return "Hayır"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<p class="empty">Bu bölümde kayıt bulunmuyor.</p>'
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    head = "".join(f"<th>{escape(COLUMN_LABELS.get(key, key.replace('_', ' ').title()))}</th>" for key in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(_text(row.get(key)), quote=True)}</td>" for key in columns) + "</tr>"
        for row in rows
    )
    return f'<div class="table-scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def build_workplace_backup_report(manifest: dict[str, Any], domains: dict[str, list[dict[str, Any]]]) -> str:
    companies = manifest.get("companies") or []
    company_name = _text((companies[0] if companies else {}).get("name") or "İşyeri")
    created_at = _text(manifest.get("created_at"))
    total = sum(len(rows) for rows in domains.values())
    cards = "".join(
        f'<div class="card"><strong>{len(rows)}</strong><span>{escape(DOMAIN_LABELS.get(name, name))}</span></div>'
        for name, rows in domains.items() if rows
    ) or '<div class="card"><strong>0</strong><span>Kayıt</span></div>'
    sections = "".join(
        f'<section class="report-section"><h2>{escape(DOMAIN_LABELS.get(name, name.replace("_", " ").title()))}'
        f'<small>{len(rows)} kayıt</small></h2>{_table(rows)}</section>'
        for name, rows in domains.items()
    )
    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>İşyeri Yedek Raporu - {escape(company_name, quote=True)}</title>
<style>
:root{{--navy:#123047;--teal:#07877f;--line:#dbe5ea;--muted:#607386}}*{{box-sizing:border-box}}body{{margin:0;background:#eef4f6;color:#172b38;font:14px Arial,sans-serif}}.page{{max-width:1400px;margin:24px auto;background:#fff;padding:30px;box-shadow:0 8px 30px #16384d20}}header{{border-bottom:4px solid var(--teal);padding-bottom:18px}}h1{{color:var(--navy);margin:0 0 8px;font-size:28px}}.meta{{color:var(--muted);display:flex;gap:24px;flex-wrap:wrap}}.toolbar{{position:sticky;top:0;z-index:2;display:flex;gap:10px;padding:14px 0;background:#fff}}button,input{{border:1px solid #b8cbd4;border-radius:8px;padding:10px 14px;font:inherit}}input{{flex:1}}button{{background:var(--teal);color:#fff;border:0;font-weight:700;cursor:pointer}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:18px 0}}.card{{border:1px solid var(--line);border-radius:10px;padding:14px;background:#f8fbfc}}.card strong{{display:block;color:var(--teal);font-size:22px}}.card span{{color:var(--muted)}}section{{margin:24px 0;break-inside:avoid}}h2{{display:flex;justify-content:space-between;gap:10px;color:var(--navy);font-size:18px;border-left:4px solid var(--teal);padding-left:10px}}h2 small{{color:var(--muted);font-weight:400}}.table-scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:12px}}th,td{{border:1px solid var(--line);padding:7px;text-align:left;vertical-align:top;overflow-wrap:anywhere}}th{{background:#eaf5f4;color:#123047}}tr:nth-child(even){{background:#f8fafb}}.empty{{color:var(--muted);font-style:italic}}footer{{margin-top:30px;border-top:1px solid var(--line);padding-top:12px;color:var(--muted);font-size:12px}}@media print{{body{{background:#fff}}.page{{max-width:none;margin:0;padding:0;box-shadow:none}}.toolbar{{display:none}}.table-scroll{{overflow:visible}}table{{font-size:9px}}section{{break-inside:auto}}thead{{display:table-header-group}}tr{{break-inside:avoid}}}}
</style></head><body><main class="page"><header><h1>İşyeri Yedek Raporu</h1><div class="meta"><span><b>İşyeri:</b> {escape(company_name)}</span><span><b>Yedek tarihi:</b> {escape(created_at)}</span><span><b>Toplam kayıt:</b> {total}</span></div></header>
<div class="toolbar"><input id="search" type="search" placeholder="Rapor içinde ara…" aria-label="Rapor içinde ara"><button type="button" onclick="window.print()">Yazdır / PDF Kaydet</button></div><div class="cards">{cards}</div><div id="sections">{sections}</div>
<footer>Bu rapor ISG Suite işyeri yedeğinden oluşturulmuştur. Rapor kişisel ve sağlık verileri içerebilir; güvenli ortamda saklayınız.</footer></main>
<script>document.getElementById('search').addEventListener('input',function(){{var q=this.value.toLocaleLowerCase('tr');document.querySelectorAll('.report-section').forEach(function(s){{s.style.display=!q||s.textContent.toLocaleLowerCase('tr').includes(q)?'':'none';}});}});</script></body></html>"""
