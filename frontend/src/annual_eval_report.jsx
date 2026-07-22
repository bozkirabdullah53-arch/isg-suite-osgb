import React, {useEffect, useState} from 'react';
import {Download, FileText, Plus, RefreshCw} from 'lucide-react';
import {api, downloadFile, uploadFile} from './api';

const OUTCOME_LABEL = {
  planlandi: 'Planlandı',
  devam: 'Devam Ediyor',
  tamam: 'Tamamlandı',
  kismi: 'Kısmen Tamamlandı',
  gecikmeli_tamam: 'Gecikmeli Tamamlandı',
  ertelendi: 'Ertelendi',
  gerceklesmedi: 'Gerçekleştirilmedi',
  iptal: 'İptal',
  plan_revizyonuyla_kaldirildi: 'Plan Revizyonuyla Kaldırıldı',
};

const REPORT_LABEL = {
  hazirlanmadi: 'Hazırlanmadı',
  hazirlaniyor: 'Hazırlanıyor',
  uzman_tamam: 'Uzman tamamladı',
  hekim_bekliyor: 'Hekim bekleniyor',
  isveren_bekliyor: 'İşveren onayı bekleniyor',
  onaylandi: 'Onaylandı',
  revizyon: 'Revizyon istendi',
  arsiv: 'Arşivlendi',
};

function badge(outcome) {
  if (outcome === 'tamam' || outcome === 'gecikmeli_tamam') return <span className="status-badge badge-ok">{OUTCOME_LABEL[outcome]}</span>;
  if (outcome === 'gerceklesmedi' || outcome === 'iptal') return <span className="status-badge badge-danger">{OUTCOME_LABEL[outcome] || outcome}</span>;
  if (outcome === 'ertelendi' || outcome === 'kismi' || outcome === 'devam') return <span className="status-badge badge-warn">{OUTCOME_LABEL[outcome]}</span>;
  return <span className="status-badge badge-muted">{OUTCOME_LABEL[outcome] || outcome}</span>;
}

export function AnnualEvalReportPage({user}) {
  const canEdit = user.role === 'safety_specialist' || user.role === 'global_admin';
  const [companies, setCompanies] = useState([]);
  const [companyId, setCompanyId] = useState(user.company_id ? String(user.company_id) : '');
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [overview, setOverview] = useState(null);
  const [items, setItems] = useState([]);
  const [unplanned, setUnplanned] = useState([]);
  const [filterOutcome, setFilterOutcome] = useState('');
  const [missingEv, setMissingEv] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [edit, setEdit] = useState(null);
  const [form, setForm] = useState({});
  const [unplannedOpen, setUnplannedOpen] = useState(false);
  const [upForm, setUpForm] = useState({activity: '', category: '', done_date: '', reason: '', result_text: '', responsible_name: '', suggest_next_year: false});

  async function loadCompanies() {
    try {
      setCompanies(await api('/companies'));
    } catch (e) {
      setErr(e.message || 'Firmalar yüklenemedi.');
    }
  }

  async function loadAll() {
    if (!companyId) return;
    setBusy(true);
    setErr('');
    try {
      const ov = await api(`/annual-evals/overview?company_id=${companyId}&year=${year}`);
      setOverview(ov);
      if (!ov.evaluation_id) {
        setItems([]);
        setUnplanned([]);
        return;
      }
      const qs = new URLSearchParams({company_id: companyId, year});
      if (filterOutcome) qs.set('outcome', filterOutcome);
      if (missingEv) qs.set('missing_evidence', 'true');
      setItems(await api(`/annual-evals/items?${qs}`));
      setUnplanned(await api(`/annual-evals/${ov.evaluation_id}/unplanned`));
    } catch (e) {
      setErr(e.message || 'Değerlendirme yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void loadCompanies(); }, []);
  useEffect(() => { void loadAll(); }, [companyId, year, filterOutcome, missingEv]);

  async function start() {
    if (!companyId) return;
    setBusy(true);
    setErr('');
    try {
      const ov = await api('/annual-evals/start', {
        method: 'POST',
        body: JSON.stringify({company_id: Number(companyId), year: Number(year)}),
      });
      setOverview(ov);
      setMsg('Değerlendirme başlatıldı / senkronize edildi. Plan alanları değiştirilmez.');
      await loadAll();
    } catch (e) {
      setErr(e.message || 'Başlatılamadı.');
    } finally {
      setBusy(false);
    }
  }

  function openEdit(row) {
    setEdit(row);
    setForm({
      outcome_status: row.outcome_status || 'planlandi',
      actual_start: row.actual_start || '',
      actual_end: row.actual_end || '',
      completion_pct: row.completion_pct ?? '',
      result_text: row.result_text || '',
      deviation_reason: row.deviation_reason || '',
      specialist_note: row.specialist_note || '',
      physician_note: row.physician_note || '',
      employer_note: row.employer_note || '',
      next_year_suggestion: row.next_year_suggestion || '',
      target_met: row.target_met ?? null,
      capa_needed: !!row.capa_needed,
    });
  }

  async function saveEdit(e) {
    e.preventDefault();
    if (!edit) return;
    setBusy(true);
    setErr('');
    try {
      await api(`/annual-evals/items/${edit.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          ...form,
          actual_start: form.actual_start || null,
          actual_end: form.actual_end || null,
          completion_pct: form.completion_pct === '' ? null : Number(form.completion_pct),
        }),
      });
      setEdit(null);
      setMsg('Değerlendirme kaydedildi.');
      await loadAll();
    } catch (ex) {
      setErr(ex.message || 'Kayıt başarısız.');
    } finally {
      setBusy(false);
    }
  }

  async function uploadEvidence(file) {
    if (!edit || !file) return;
    try {
      await uploadFile(`/annual-evals/items/${edit.id}/evidences`, file, {title: file.name, doc_type: 'diger'});
      setMsg('Kanıt yüklendi.');
      await loadAll();
    } catch (ex) {
      setErr(ex.message || 'Kanıt yüklenemedi.');
    }
  }

  async function saveUnplanned(e) {
    e.preventDefault();
    if (!overview?.evaluation_id) return;
    setBusy(true);
    try {
      await api(`/annual-evals/${overview.evaluation_id}/unplanned`, {
        method: 'POST',
        body: JSON.stringify({
          ...upForm,
          done_date: upForm.done_date || null,
          category: upForm.category || null,
        }),
      });
      setUnplannedOpen(false);
      setUpForm({activity: '', category: '', done_date: '', reason: '', result_text: '', responsible_name: '', suggest_next_year: false});
      setMsg('Plan dışı faaliyet eklendi (gerçekleşme oranına girmez).');
      await loadAll();
    } catch (ex) {
      setErr(ex.message || 'Eklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  async function workflow(action) {
    if (!overview?.evaluation_id) return;
    setBusy(true);
    try {
      await api(`/annual-evals/${overview.evaluation_id}/workflow/${action}`, {method: 'POST'});
      setMsg('İş akışı güncellendi.');
      await loadAll();
    } catch (ex) {
      setErr(ex.message || 'İş akışı başarısız.');
    } finally {
      setBusy(false);
    }
  }

  const k = overview?.kpis || {};
  const locked = overview?.report_status === 'onaylandi' || overview?.report_status === 'arsiv';

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2><FileText size={22} style={{marginRight: 8, verticalAlign: 'middle'}} />Yıllık Çalışma Değerlendirme Raporu</h2>
          <p className="muted">Bu ekran yıllık çalışma planındaki faaliyetlerin gerçekleşmesini değerlendirir. Plan bilgileri burada değiştirilmez.</p>
        </div>
        <div className="actions">
          {canEdit && <button type="button" onClick={start} disabled={busy || !companyId}>Değerlendirmeyi Başlat / Senkronize Et</button>}
          <button type="button" className="secondary" disabled={busy || !companyId} onClick={() => downloadFile(`/annual-evals/export.xlsx?company_id=${companyId}&year=${year}`, `yillik-degerlendirme-${year}.xlsx`)}>
            <Download size={16} /> Excel
          </button>
          <button type="button" className="secondary" disabled={busy || !companyId} onClick={() => downloadFile(`/annual-evals/export.pdf?company_id=${companyId}&year=${year}`, `yillik-degerlendirme-${year}.pdf`)}>
            <Download size={16} /> PDF
          </button>
          <button type="button" className="secondary" onClick={loadAll} disabled={busy}><RefreshCw size={16} /> Yenile</button>
        </div>
      </div>

      {err && <div className="banner danger">{err}</div>}
      {msg && <div className="banner ok">{msg}</div>}

      <section className="panel" style={{marginBottom: 12}}>
        <div className="form-grid">
          <label className="field"><span>Firma</span>
            <select value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
              <option value="">Seçin</option>
              {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label className="field"><span>Değerlendirme yılı</span>
            <input type="number" value={year} onChange={(e) => setYear(e.target.value)} min="2020" max="2100" />
          </label>
        </div>
      </section>

      {overview && (
        <section className="panel" style={{marginBottom: 12, fontSize: 13}}>
          <div style={{display: 'flex', flexWrap: 'wrap', gap: 16}}>
            <div><strong>{overview.company_name}</strong></div>
            <div>SGK: {overview.sgk_registry_no || '—'}</div>
            <div>Tehlike: {overview.hazard_class || '—'}</div>
            <div>Çalışan: {overview.employee_count}</div>
            <div>Plan kalemi: {overview.plan_item_count}</div>
            <div>Durum: <strong>{REPORT_LABEL[overview.report_status] || overview.report_status}</strong></div>
          </div>
          {(overview.warnings || []).length > 0 && (
            <ul style={{margin: '10px 0 0', color: '#92400e', fontSize: 12}}>
              {overview.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          )}
        </section>
      )}

      {overview && overview.plan_item_count === 0 && (
        <section className="panel" style={{marginBottom: 12}}>
          <p>Seçilen yıl için değerlendirilecek yıllık çalışma planı kalemi bulunamadı. Önce <strong>Yıllık Plan</strong> menüsünden planı oluşturun.</p>
        </section>
      )}

      {overview && (
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(140px,1fr))', gap: 8, marginBottom: 12}}>
          {[
            ['planned_total', 'Planlanan', ''],
            ['tamam', 'Tamamlanan', 'tamam'],
            ['kismi', 'Kısmi', 'kismi'],
            ['devam', 'Devam', 'devam'],
            ['ertelendi', 'Ertelenen', 'ertelendi'],
            ['gerceklesmedi', 'Gerçekleşmeyen', 'gerceklesmedi'],
            ['missing_evidence', 'Kanıt eksik', null],
            ['unplanned', 'Plan dışı', null],
            ['completion_rate', 'Gerçekleşme %', null],
          ].map(([key, label, outcome]) => (
            <button
              key={key}
              type="button"
              className="panel"
              style={{padding: 10, textAlign: 'left', cursor: outcome !== null ? 'pointer' : 'default'}}
              onClick={() => {
                if (key === 'missing_evidence') { setMissingEv(true); setFilterOutcome(''); return; }
                if (outcome === '') { setFilterOutcome(''); setMissingEv(false); return; }
                if (outcome) { setFilterOutcome(outcome); setMissingEv(false); }
              }}
            >
              <div style={{fontSize: 11, color: '#64748b'}}>{label}</div>
              <div style={{fontSize: 20, fontWeight: 800}}>{k[key] ?? '—'}</div>
            </button>
          ))}
        </div>
      )}

      {canEdit && overview?.evaluation_id && !locked && (
        <div className="actions" style={{marginBottom: 12}}>
          <button type="button" className="secondary" onClick={() => setUnplannedOpen(true)}><Plus size={14} /> Plan Dışı Faaliyet</button>
          <button type="button" className="secondary" onClick={() => workflow('submit-specialist')}>Uzman → Hekim</button>
          <button type="button" className="secondary" onClick={() => workflow('approve-physician')}>Hekim onayladı</button>
          <button type="button" className="secondary" onClick={() => workflow('approve-employer')}>İşveren onayladı</button>
          <button type="button" className="secondary" onClick={() => workflow('request-revision')}>Revizyon iste</button>
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Kategori</th>
              <th>Faaliyet</th>
              <th>Dönem</th>
              <th>Planlanan</th>
              <th>Sorumlu</th>
              <th>Durum</th>
              <th>Gerçekleşme</th>
              <th>Oran</th>
              <th>Gecikme</th>
              <th>Kanıt</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && <tr><td colSpan={12} className="muted">Kayıt yok. Değerlendirmeyi başlatın.</td></tr>}
            {items.map((r, idx) => (
              <tr key={r.id}>
                <td>{idx + 1}</td>
                <td>{r.plan?.category || '—'}</td>
                <td><strong>{r.plan?.activity}</strong></td>
                <td>{r.plan?.month}</td>
                <td>{r.plan?.target_date || '—'}</td>
                <td>{r.plan?.responsible_name || '—'}</td>
                <td>{badge(r.outcome_status)}</td>
                <td>{r.actual_end || '—'}</td>
                <td>{r.completion_pct != null ? `${r.completion_pct}%` : '—'}</td>
                <td>{r.delay_days != null ? `${r.delay_days} g` : '—'}</td>
                <td>{r.evidence_count > 0 ? 'Var' : 'Eksik'}</td>
                <td>
                  {canEdit && !locked && (
                    <button type="button" className="secondary mini" onClick={() => openEdit(r)}>Değerlendir</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {unplanned.length > 0 && (
        <section className="panel" style={{marginTop: 16}}>
          <h3>Plan Dışı Faaliyetler</h3>
          <ul style={{margin: 0, paddingLeft: 18, fontSize: 13}}>
            {unplanned.map((u) => (
              <li key={u.id}><strong>{u.activity}</strong> — {u.done_date || '—'} {u.suggest_next_year ? '(sonraki yıla önerilir)' : ''}</li>
            ))}
          </ul>
        </section>
      )}

      {edit && (
        <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && setEdit(null)}>
          <section className="modal" style={{maxWidth: 760}}>
            <header><h3>Faaliyet Değerlendirme</h3></header>
            <div className="panel" style={{marginBottom: 12, background: '#f8fafc', fontSize: 13}}>
              <div><strong>{edit.plan?.activity}</strong></div>
              <div>Kategori: {edit.plan?.category} · Ay: {edit.plan?.month} · Hedef: {edit.plan?.target_date || '—'}</div>
              <div>Sorumlu: {edit.plan?.responsible_name || '—'} · Plan durumu: {edit.plan?.plan_status}</div>
              <div className="muted">Plan alanları salt okunurdur.</div>
            </div>
            <form className="form-grid" onSubmit={saveEdit}>
              <label className="field"><span>Gerçekleşme durumu</span>
                <select value={form.outcome_status} onChange={(e) => setForm({...form, outcome_status: e.target.value})}>
                  {Object.entries(OUTCOME_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </label>
              <label className="field"><span>Fiilî tamamlanma</span>
                <input type="date" value={form.actual_end} onChange={(e) => setForm({...form, actual_end: e.target.value})} />
              </label>
              <label className="field"><span>Fiilî başlangıç</span>
                <input type="date" value={form.actual_start} onChange={(e) => setForm({...form, actual_start: e.target.value})} />
              </label>
              <label className="field"><span>Gerçekleşme oranı %</span>
                <input type="number" min="0" max="100" value={form.completion_pct} onChange={(e) => setForm({...form, completion_pct: e.target.value})} />
              </label>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Sonuç</span>
                <textarea rows={3} value={form.result_text} onChange={(e) => setForm({...form, result_text: e.target.value})} />
              </label>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Sapma / gerekçe</span>
                <textarea rows={2} value={form.deviation_reason} onChange={(e) => setForm({...form, deviation_reason: e.target.value})} />
              </label>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Uzman notu</span>
                <textarea rows={2} value={form.specialist_note} onChange={(e) => setForm({...form, specialist_note: e.target.value})} />
              </label>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Sonraki yıl önerisi</span>
                <textarea rows={2} value={form.next_year_suggestion} onChange={(e) => setForm({...form, next_year_suggestion: e.target.value})} />
              </label>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Kanıt dosyası</span>
                <input type="file" accept=".pdf,image/*" onChange={(e) => uploadEvidence(e.target.files?.[0])} />
              </label>
              <label style={{display: 'flex', gap: 8, alignItems: 'center', fontSize: 13}}>
                <input type="checkbox" checked={!!form.capa_needed} onChange={(e) => setForm({...form, capa_needed: e.target.checked})} />
                Düzeltici faaliyet gerekli
              </label>
              <div className="form-actions">
                <button type="button" className="secondary" onClick={() => setEdit(null)}>İptal</button>
                <button type="submit" disabled={busy}>Kaydet</button>
              </div>
            </form>
          </section>
        </div>
      )}

      {unplannedOpen && (
        <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && setUnplannedOpen(false)}>
          <section className="modal">
            <header><h3>Plan Dışı Faaliyet</h3></header>
            <form className="form-grid" onSubmit={saveUnplanned}>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Faaliyet</span>
                <input required value={upForm.activity} onChange={(e) => setUpForm({...upForm, activity: e.target.value})} />
              </label>
              <label className="field"><span>Tarih</span>
                <input type="date" value={upForm.done_date} onChange={(e) => setUpForm({...upForm, done_date: e.target.value})} />
              </label>
              <label className="field"><span>Sorumlu</span>
                <input value={upForm.responsible_name} onChange={(e) => setUpForm({...upForm, responsible_name: e.target.value})} />
              </label>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Neden</span>
                <textarea rows={2} value={upForm.reason} onChange={(e) => setUpForm({...upForm, reason: e.target.value})} />
              </label>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Sonuç</span>
                <textarea rows={2} value={upForm.result_text} onChange={(e) => setUpForm({...upForm, result_text: e.target.value})} />
              </label>
              <label style={{display: 'flex', gap: 8, alignItems: 'center', fontSize: 13}}>
                <input type="checkbox" checked={upForm.suggest_next_year} onChange={(e) => setUpForm({...upForm, suggest_next_year: e.target.checked})} />
                Sonraki yıl planına öner
              </label>
              <div className="form-actions">
                <button type="button" className="secondary" onClick={() => setUnplannedOpen(false)}>İptal</button>
                <button type="submit" disabled={busy}>Kaydet</button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
