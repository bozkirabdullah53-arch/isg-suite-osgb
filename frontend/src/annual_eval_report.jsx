import React, {useEffect, useState} from 'react';
import {Download, FileText, Link2, Plus, RefreshCw} from 'lucide-react';
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

export function AnnualEvalReportPage({user, onNavigate}) {
  const canEdit = user.role === 'safety_specialist' || user.role === 'global_admin';
  const isPhysician = user.role === 'workplace_physician';
  const [companies, setCompanies] = useState([]);
  const [companyId, setCompanyId] = useState(user.company_id ? String(user.company_id) : '');
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [overview, setOverview] = useState(null);
  const [items, setItems] = useState([]);
  const [unplanned, setUnplanned] = useState([]);
  const [capas, setCapas] = useState([]);
  const [suggestions, setSuggestions] = useState(null);
  const [related, setRelated] = useState(null);
  const [q, setQ] = useState('');
  const [filterOutcome, setFilterOutcome] = useState('');
  const [missingEv, setMissingEv] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [edit, setEdit] = useState(null);
  const [form, setForm] = useState({});
  const [unplannedOpen, setUnplannedOpen] = useState(false);
  const [capaOpen, setCapaOpen] = useState(null);
  const [capaForm, setCapaForm] = useState({title: '', root_cause: '', action: '', responsible: '', due_date: '', priority: 'orta'});
  const [upForm, setUpForm] = useState({activity: '', category: '', done_date: '', reason: '', result_text: '', responsible_name: '', suggest_next_year: false});
  const [selectedSuggest, setSelectedSuggest] = useState({});
  const [period, setPeriod] = useState('month');
  const [analytics, setAnalytics] = useState(null);
  const [monthFrom, setMonthFrom] = useState('');
  const [monthTo, setMonthTo] = useState('');
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [selectedIds, setSelectedIds] = useState({});
  const [bulkNote, setBulkNote] = useState('');

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
      setRelated(await api(`/annual-evals/related-evidence?company_id=${companyId}&year=${year}`).catch(() => null));
      setSuggestions(await api(`/annual-evals/next-year-suggestions?company_id=${companyId}&year=${year}`).catch(() => null));
      setAnalytics(await api(`/annual-evals/analytics?company_id=${companyId}&year=${year}&period=${period}`).catch(() => null));
      if (!ov.evaluation_id) {
        setItems([]);
        setUnplanned([]);
        setCapas([]);
        return;
      }
      const qs = new URLSearchParams({company_id: companyId, year});
      if (filterOutcome) qs.set('outcome', filterOutcome);
      if (missingEv) qs.set('missing_evidence', 'true');
      if (overdueOnly) qs.set('overdue', 'true');
      if (q.trim()) qs.set('q', q.trim());
      if (monthFrom) qs.set('month_from', monthFrom);
      if (monthTo) qs.set('month_to', monthTo);
      setItems(await api(`/annual-evals/items?${qs}`));
      setUnplanned(await api(`/annual-evals/${ov.evaluation_id}/unplanned`));
      setCapas(await api(`/annual-evals/${ov.evaluation_id}/capas`));
    } catch (e) {
      setErr(e.message || 'Değerlendirme yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void loadCompanies(); }, []);
  useEffect(() => { void loadAll(); }, [companyId, year, filterOutcome, missingEv, period, monthFrom, monthTo, overdueOnly]);

  async function runBulk(action) {
    const ids = Object.keys(selectedIds).filter((k) => selectedIds[k]).map(Number);
    if (!ids.length) {
      setErr('Toplu işlem için satır seçin.');
      return;
    }
    setBusy(true);
    try {
      const body = {item_ids: ids, action};
      if (action === 'note') body.specialist_note = bulkNote || 'Toplu değerlendirme notu';
      if (action === 'suggest_next') body.next_year_suggestion = bulkNote || 'Bir sonraki yıl planına aktarılsın.';
      if (action === 'complete') {
        body.actual_end = new Date().toISOString().slice(0, 10);
        body.result_text = bulkNote || 'Toplu tamamlandı';
      }
      const res = await api('/annual-evals/bulk', {method: 'POST', body: JSON.stringify(body)});
      setMsg(`Toplu işlem: ${res.updated} güncellendi` + (res.skipped?.length ? `, ${res.skipped.length} atlandı (kanıt eksik)` : ''));
      setSelectedIds({});
      await loadAll();
    } catch (ex) {
      setErr(ex.message || 'Toplu işlem başarısız.');
    } finally {
      setBusy(false);
    }
  }
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
      setMsg('Değerlendirme başlatıldı / senkronize edildi. Plan bilgileri burada değiştirilmez.');
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
      const body = isPhysician
        ? {physician_note: form.physician_note || null}
        : {
            ...form,
            actual_start: form.actual_start || null,
            actual_end: form.actual_end || null,
            completion_pct: form.completion_pct === '' ? null : Number(form.completion_pct),
          };
      await api(`/annual-evals/items/${edit.id}`, {method: 'PUT', body: JSON.stringify(body)});
      setEdit(null);
      setMsg(isPhysician ? 'Hekim görüşü kaydedildi.' : 'Değerlendirme kaydedildi.');
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

  async function linkRelated(mod, id, title) {
    if (!edit) return;
    try {
      await api(`/annual-evals/items/${edit.id}/evidences/link`, {
        method: 'POST',
        body: JSON.stringify({source_module: mod, source_id: id, title}),
      });
      setMsg('Modül kaydı kanıt olarak bağlandı.');
      await loadAll();
    } catch (ex) {
      setErr(ex.message || 'Bağlanamadı.');
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

  async function saveCapa(e) {
    e.preventDefault();
    if (!overview?.evaluation_id) return;
    setBusy(true);
    try {
      await api(`/annual-evals/${overview.evaluation_id}/capas`, {
        method: 'POST',
        body: JSON.stringify({
          ...capaForm,
          due_date: capaForm.due_date || null,
          evaluation_item_id: capaOpen?.id || null,
        }),
      });
      setCapaOpen(null);
      setMsg('Düzeltici faaliyet oluşturuldu.');
      await loadAll();
    } catch (ex) {
      setErr(ex.message || 'CAPA kaydedilemedi.');
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

  async function transferSelected() {
    const picked = (suggestions?.items || []).filter((_, i) => selectedSuggest[i]);
    if (!picked.length) {
      setErr('Aktarılacak öneri seçin.');
      return;
    }
    setBusy(true);
    try {
      const res = await api('/annual-evals/transfer-to-next-year', {
        method: 'POST',
        body: JSON.stringify({
          company_id: Number(companyId),
          from_year: Number(year),
          items: picked.map((s) => ({
            activity: s.activity,
            category: s.category || null,
            month: s.month || 1,
            responsible_name: s.responsible_name || null,
            description: s.suggestion || null,
            source_eval_item_id: s.source_eval_item_id || null,
            source_unplanned_id: s.source_unplanned_id || null,
          })),
        }),
      });
      setMsg(`${res.created_count} kalem ${res.to_year} planına aktarıldı (eski değerlendirme değişmedi).`);
      setSelectedSuggest({});
    } catch (ex) {
      setErr(ex.message || 'Aktarım başarısız.');
    } finally {
      setBusy(false);
    }
  }

  const k = overview?.kpis || {};
  const locked = overview?.report_status === 'onaylandi' || overview?.report_status === 'arsiv';
  const needResult = ['tamam', 'gecikmeli_tamam', 'kismi'].includes(form.outcome_status);
  const needDeviation = ['ertelendi', 'gerceklesmedi', 'iptal'].includes(form.outcome_status);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2><FileText size={22} style={{marginRight: 8, verticalAlign: 'middle'}} />Yıllık Çalışma Değerlendirme Raporu</h2>
          <p className="muted">Bu ekran, seçilen yıllık çalışma planındaki faaliyetlerin gerçekleşme durumunu değerlendirir. Plan bilgileri burada değiştirilmez.</p>
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
          <label className="field"><span>Ara</span>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Faaliyet / sorumlu" onKeyDown={(e) => e.key === 'Enter' && loadAll()} />
          </label>
          <label className="field"><span>Dönem görünümü</span>
            <select value={period} onChange={(e) => setPeriod(e.target.value)}>
              <option value="month">Aylık</option>
              <option value="quarter">Üç aylık</option>
              <option value="half">Altı aylık</option>
              <option value="year">Yıllık</option>
            </select>
          </label>
          <div className="field" style={{alignSelf: 'end', display: 'flex', gap: 8}}>
            <button type="button" className="secondary" onClick={loadAll} disabled={busy}>Filtre uygula</button>
            <button type="button" className="secondary" onClick={() => { setMonthFrom(''); setMonthTo(''); setOverdueOnly(false); setFilterOutcome(''); setMissingEv(false); setQ(''); }}>Temizle</button>
          </div>
        </div>
      </section>

      {analytics && (
        <section className="panel" style={{marginBottom: 12}}>
          <h3 style={{marginTop: 0, fontSize: 15}}>Dönem özeti (tıklayınca filtrele)</h3>
          <div style={{display: 'flex', flexWrap: 'wrap', gap: 8}}>
            {(analytics.buckets || []).map((b) => (
              <button
                key={b.key}
                type="button"
                className="secondary"
                style={{minWidth: 110, textAlign: 'left'}}
                onClick={() => { setMonthFrom(String(b.month_from)); setMonthTo(String(b.month_to)); }}
              >
                <div style={{fontSize: 11}}>{b.label}</div>
                <div style={{fontWeight: 700}}>{b.completed}/{b.planned}</div>
                <div style={{height: 6, background: '#e2e8f0', borderRadius: 4, marginTop: 4}}>
                  <div style={{height: 6, width: `${b.rate || 0}%`, background: '#0f766e', borderRadius: 4}} />
                </div>
              </button>
            ))}
          </div>
          {(analytics.by_category || []).length > 0 && (
            <div style={{marginTop: 12, fontSize: 13}}>
              <strong>Kategori:</strong>{' '}
              {analytics.by_category.slice(0, 8).map((c) => (
                <button key={c.key} type="button" className="secondary mini" style={{margin: 2}} onClick={() => { setQ(''); setFilterOutcome(''); /* period clear */ setMonthFrom(''); setMonthTo(''); void (async () => {
                  const qs = new URLSearchParams({company_id: companyId, year, category: c.key});
                  setItems(await api(`/annual-evals/items?${qs}`));
                })(); }}>
                  {c.key} {c.completed}/{c.planned}
                </button>
              ))}
            </div>
          )}
        </section>
      )}

      {canEdit && overview?.evaluation_id && !locked && Object.values(selectedIds).some(Boolean) && (
        <section className="panel" style={{marginBottom: 12}}>
          <div className="form-grid">
            <label className="field" style={{gridColumn: '1 / -1'}}><span>Toplu not / sonuç</span>
              <input value={bulkNote} onChange={(e) => setBulkNote(e.target.value)} placeholder="Not veya tamamlanma sonucu" />
            </label>
          </div>
          <div className="actions" style={{marginTop: 8}}>
            <button type="button" className="secondary" onClick={() => runBulk('note')}>Seçilenlere not</button>
            <button type="button" className="secondary" onClick={() => runBulk('suggest_next')}>Sonraki yıla öner</button>
            <button type="button" className="secondary" onClick={() => runBulk('mark_capa')}>DÖF gerekli</button>
            <button type="button" className="secondary" onClick={() => runBulk('complete')}>Kanıtlıysa tamamla</button>
            <button type="button" className="secondary" onClick={() => setOverdueOnly(true)}>Gecikenleri göster</button>
          </div>
        </section>
      )}

      {overview && (
        <section className="panel" style={{marginBottom: 12, fontSize: 13}}>
          <div style={{display: 'flex', flexWrap: 'wrap', gap: 16}}>
            <div><strong>{overview.company_name}</strong></div>
            <div>SGK: {overview.sgk_registry_no || '—'}</div>
            <div>Adres: {overview.address || '—'}</div>
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
          <p>Seçilen yıl için değerlendirilecek onaylı bir yıllık çalışma planı bulunamadı. Değerlendirme oluşturabilmek için önce yıllık çalışma planını hazırlayın ve onaylayın.</p>
          {typeof onNavigate === 'function' && (
            <button type="button" onClick={() => onNavigate('annual_plans')}>Yıllık Çalışma Planına Git</button>
          )}
        </section>
      )}

      {overview && (
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(130px,1fr))', gap: 8, marginBottom: 12}}>
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
            ['on_time_rate', 'Zamanında %', null],
            ['evidence_rate', 'Kanıtlı %', null],
          ].map(([key, label, outcome]) => (
            <button
              key={key}
              type="button"
              className="panel"
              title={(k.formulas && k.formulas[key]) || ''}
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
      {k.note && <p className="muted" style={{marginTop: -4}}>{k.note}</p>}

      {canEdit && overview?.evaluation_id && !locked && (
        <div className="actions" style={{marginBottom: 12}}>
          <button type="button" className="secondary" onClick={() => setUnplannedOpen(true)}><Plus size={14} /> Plan Dışı Faaliyet</button>
          <button type="button" className="secondary" onClick={() => workflow('submit-specialist')}>Uzman → Hekim</button>
          {(canEdit || isPhysician) && <button type="button" className="secondary" onClick={() => workflow('approve-physician')}>Hekim onayladı</button>}
          {canEdit && <button type="button" className="secondary" onClick={() => workflow('approve-employer')}>İşveren onayladı</button>}
          <button type="button" className="secondary" onClick={() => workflow('request-revision')}>Revizyon iste</button>
        </div>
      )}
      {canEdit && locked && (
        <div className="actions" style={{marginBottom: 12}}>
          <button type="button" className="secondary" onClick={() => workflow('create-revision')}>Yeni revizyon aç</button>
          <button type="button" className="secondary" onClick={() => workflow('archive')}>Arşivle</button>
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th></th>
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
            {items.length === 0 && <tr><td colSpan={13} className="muted">Kayıt yok. Değerlendirmeyi başlatın.</td></tr>}
            {items.map((r, idx) => (
              <tr key={r.id}>
                <td>
                  {canEdit && !locked && (
                    <input
                      type="checkbox"
                      checked={!!selectedIds[r.id]}
                      onChange={(e) => setSelectedIds({...selectedIds, [r.id]: e.target.checked})}
                    />
                  )}
                </td>
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
                <td>{r.evidence_count > 0 ? 'Var' : <span style={{color: '#b45309'}}>Eksik</span>}</td>
                <td style={{whiteSpace: 'nowrap'}}>
                  {(canEdit || isPhysician) && !locked && (
                    <button type="button" className="secondary mini" onClick={() => openEdit(r)}>Değerlendir</button>
                  )}
                  {canEdit && !locked && (
                    <button type="button" className="secondary mini" onClick={() => { setCapaOpen(r); setCapaForm({title: `${r.plan?.activity || 'Faaliyet'} — düzeltici`, root_cause: '', action: '', responsible: r.plan?.responsible_name || '', due_date: '', priority: 'orta'}); }}>DÖF</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {related && (
        <section className="panel" style={{marginTop: 16}}>
          <h3>İlgili modül kanıt önerileri</h3>
          <p className="muted" style={{fontSize: 12}}>{related.note}</p>
          <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: 10, fontSize: 13}}>
            <div>Eğitim: <strong>{related.trainings?.count || 0}</strong> (tamam: {related.trainings?.completed || 0})</div>
            <div>Tatbikat: <strong>{related.drills?.count || 0}</strong></div>
            <div>Olay: <strong>{related.incidents?.count || 0}</strong> (kaza {related.incidents?.accident || 0} / ramak {related.incidents?.near_miss || 0})</div>
            <div>Risk: <strong>{related.risks?.count || 0}</strong></div>
            <div>Sağlık (toplu): muayene {related.health_summary?.exams_completed || 0}</div>
          </div>
        </section>
      )}

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

      {capas.length > 0 && (
        <section className="panel" style={{marginTop: 16}}>
          <h3>Düzeltici Faaliyetler</h3>
          <ul style={{margin: 0, paddingLeft: 18, fontSize: 13}}>
            {capas.map((c) => (
              <li key={c.id}><strong>{c.title}</strong> — {c.status} / {c.responsible || '—'} / {c.due_date || '—'}</li>
            ))}
          </ul>
        </section>
      )}

      {suggestions && (suggestions.items || []).length > 0 && (
        <section className="panel" style={{marginTop: 16}}>
          <h3>Bir sonraki yıl önerileri ({suggestions.year})</h3>
          <p className="muted" style={{fontSize: 12}}>{suggestions.note}</p>
          <ul style={{listStyle: 'none', padding: 0, margin: 0}}>
            {suggestions.items.map((s, i) => (
              <li key={i} style={{display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 6, fontSize: 13}}>
                {canEdit && (
                  <input type="checkbox" checked={!!selectedSuggest[i]} onChange={(e) => setSelectedSuggest({...selectedSuggest, [i]: e.target.checked})} />
                )}
                <span><strong>{s.activity}</strong> — {s.reason} {s.suggestion ? `· ${s.suggestion}` : ''}</span>
              </li>
            ))}
          </ul>
          {canEdit && (
            <button type="button" style={{marginTop: 8}} onClick={transferSelected} disabled={busy}>Seçilenleri yeni yıl planına aktar</button>
          )}
        </section>
      )}

      {edit && (
        <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && setEdit(null)}>
          <section className="modal" style={{maxWidth: 780}}>
            <header><h3>Faaliyet Değerlendirme</h3></header>
            <div className="panel" style={{marginBottom: 12, background: '#f8fafc', fontSize: 13}}>
              <div><strong>{edit.plan?.activity}</strong></div>
              <div>Kategori: {edit.plan?.category} · Ay: {edit.plan?.month} · Hedef: {edit.plan?.target_date || '—'}</div>
              <div>Sorumlu: {edit.plan?.responsible_name || '—'} · Plan durumu: {edit.plan?.plan_status}</div>
              <div className="muted">Plan alanları salt okunurdur.</div>
              {edit.evidence_count < 1 && !['planlandi', 'iptal', 'plan_revizyonuyla_kaldirildi'].includes(edit.outcome_status) && (
                <div style={{color: '#b45309', marginTop: 6}}>Kanıt belgesi eklenmedi.</div>
              )}
            </div>
            <form className="form-grid" onSubmit={saveEdit}>
              {!isPhysician && (
                <>
                  <label className="field"><span>Gerçekleşme durumu</span>
                    <select value={form.outcome_status} onChange={(e) => setForm({...form, outcome_status: e.target.value})}>
                      {Object.entries(OUTCOME_LABEL).map(([kk, v]) => <option key={kk} value={kk}>{v}</option>)}
                    </select>
                  </label>
                  <label className="field"><span>Fiilî tamamlanma {needResult ? '*' : ''}</span>
                    <input type="date" value={form.actual_end} onChange={(e) => setForm({...form, actual_end: e.target.value})} required={needResult && form.outcome_status !== 'kismi'} />
                  </label>
                  <label className="field"><span>Fiilî başlangıç</span>
                    <input type="date" value={form.actual_start} onChange={(e) => setForm({...form, actual_start: e.target.value})} />
                  </label>
                  <label className="field"><span>Gerçekleşme oranı % {(form.outcome_status === 'kismi' || form.outcome_status === 'devam') ? '*' : ''}</span>
                    <input type="number" min="0" max="100" value={form.completion_pct} onChange={(e) => setForm({...form, completion_pct: e.target.value})} required={form.outcome_status === 'kismi'} />
                  </label>
                  <label className="field" style={{gridColumn: '1 / -1'}}><span>Sonuç {needResult ? '*' : ''}</span>
                    <textarea rows={3} value={form.result_text} onChange={(e) => setForm({...form, result_text: e.target.value})} required={needResult} />
                  </label>
                  <label className="field" style={{gridColumn: '1 / -1'}}><span>Sapma / gerekçe {needDeviation ? '*' : ''}</span>
                    <textarea rows={2} value={form.deviation_reason} onChange={(e) => setForm({...form, deviation_reason: e.target.value})} required={needDeviation} />
                  </label>
                  <label className="field" style={{gridColumn: '1 / -1'}}><span>Uzman notu</span>
                    <textarea rows={2} value={form.specialist_note} onChange={(e) => setForm({...form, specialist_note: e.target.value})} />
                  </label>
                  <label className="field" style={{gridColumn: '1 / -1'}}><span>Sonraki yıl önerisi {form.outcome_status === 'gerceklesmedi' ? '*' : ''}</span>
                    <textarea rows={2} value={form.next_year_suggestion} onChange={(e) => setForm({...form, next_year_suggestion: e.target.value})} required={form.outcome_status === 'gerceklesmedi'} />
                  </label>
                  <label className="field" style={{gridColumn: '1 / -1'}}><span>Kanıt dosyası</span>
                    <input type="file" accept=".pdf,image/*" onChange={(e) => uploadEvidence(e.target.files?.[0])} />
                  </label>
                  <label style={{display: 'flex', gap: 8, alignItems: 'center', fontSize: 13}}>
                    <input type="checkbox" checked={!!form.capa_needed} onChange={(e) => setForm({...form, capa_needed: e.target.checked})} />
                    Düzeltici faaliyet gerekli
                  </label>
                </>
              )}
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Hekim görüşü</span>
                <textarea rows={2} value={form.physician_note} onChange={(e) => setForm({...form, physician_note: e.target.value})} />
              </label>
              {canEdit && related && (
                <div style={{gridColumn: '1 / -1', fontSize: 12}}>
                  <div style={{fontWeight: 600, marginBottom: 4}}><Link2 size={14} /> Kanıt olarak bağla</div>
                  <div style={{display: 'flex', flexWrap: 'wrap', gap: 6}}>
                    {(related.trainings?.items || []).slice(0, 3).map((t) => (
                      <button key={`t${t.id}`} type="button" className="secondary mini" onClick={() => linkRelated('training', t.id, t.title)}>{t.title?.slice(0, 28)}</button>
                    ))}
                    {(related.drills?.items || []).slice(0, 3).map((d) => (
                      <button key={`d${d.id}`} type="button" className="secondary mini" onClick={() => linkRelated('drill', d.id, d.title)}>{d.title}</button>
                    ))}
                  </div>
                </div>
              )}
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

      {capaOpen && (
        <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && setCapaOpen(null)}>
          <section className="modal">
            <header><h3>Düzeltici Faaliyet</h3></header>
            <form className="form-grid" onSubmit={saveCapa}>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Başlık</span>
                <input required value={capaForm.title} onChange={(e) => setCapaForm({...capaForm, title: e.target.value})} />
              </label>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Kök neden</span>
                <textarea rows={2} value={capaForm.root_cause} onChange={(e) => setCapaForm({...capaForm, root_cause: e.target.value})} />
              </label>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Önlem</span>
                <textarea rows={2} value={capaForm.action} onChange={(e) => setCapaForm({...capaForm, action: e.target.value})} />
              </label>
              <label className="field"><span>Sorumlu</span>
                <input value={capaForm.responsible} onChange={(e) => setCapaForm({...capaForm, responsible: e.target.value})} />
              </label>
              <label className="field"><span>Hedef tarih</span>
                <input type="date" value={capaForm.due_date} onChange={(e) => setCapaForm({...capaForm, due_date: e.target.value})} />
              </label>
              <div className="form-actions">
                <button type="button" className="secondary" onClick={() => setCapaOpen(null)}>İptal</button>
                <button type="submit" disabled={busy}>Kaydet</button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
