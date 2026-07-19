import React, {useEffect, useMemo, useState} from 'react';
import {Download, HeartPulse, Plus, RefreshCw, Search, X} from 'lucide-react';
import {api, downloadFile} from './api';

const TYPE_FALLBACK = {
  entry_exam: 'İşe Giriş',
  periodic_exam: 'Periyodik',
  return_exam: 'İşe Dönüş',
  job_change: 'İş Değişikliği',
  night_work: 'Gece Çalışması',
  heavy_hazardous: 'Ağır-Tehlikeli',
  lab_test: 'Tetkik',
  vaccination: 'Aşı',
  fitness_report: 'Uygunluk',
  other: 'Diğer',
};

const FITNESS_FALLBACK = {
  fit: 'Uygun',
  conditional: 'Kısıtlı',
  tracking: 'Takip',
  unfit: 'Uygun Değil',
  pending: 'Bekliyor',
};

function Modal({title, close, children}) {
  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <section className="modal" style={{maxWidth: 920}}>
        <header>
          <h3>{title}</h3>
          <button className="icon" type="button" onClick={close}><X /></button>
        </header>
        {children}
      </section>
    </div>
  );
}

function Field({label, ...p}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input {...p} />
    </label>
  );
}

function Select({label, children, ...p}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select {...p}>{children}</select>
    </label>
  );
}

function TextArea({label, ...p}) {
  return (
    <label className="field">
      <span>{label}</span>
      <textarea rows={2} {...p} />
    </label>
  );
}

function emptyForm(user) {
  return {
    company_id: user.company_id || '',
    employee_id: '',
    record_type: 'periodic_exam',
    examination_date: new Date().toISOString().slice(0, 10),
    next_examination_date: '',
    fitness_status: 'pending',
    physician_name: user.role === 'workplace_physician' ? (user.full_name || '') : '',
    summary: '',
    confidential_note: '',
    audiometry_date: '',
    audiometry_result: '',
    spirometry_date: '',
    spirometry_result: '',
    chest_xray_date: '',
    chest_xray_result: '',
    blood_lead_date: '',
    blood_lead_value: '',
    blood_lead_unit: 'µg/dL',
    blood_lead_ref: '30',
    suggested_tests: '',
    exposures: '',
    follow_up_note: '',
  };
}

function fitnessBadge(status, overdue) {
  const color =
    status === 'fit' ? '#16a34a'
      : status === 'unfit' ? '#b91c1c'
        : status === 'conditional' || status === 'tracking' ? '#d97706'
          : '#64748b';
  return (
    <span style={{display: 'inline-flex', alignItems: 'center', gap: 6}}>
      <span className="badge" style={{background: color + '22', color}}>{FITNESS_FALLBACK[status] || status}</span>
      {overdue && (
        <span style={{
          padding: '2px 8px', borderRadius: 999, background: '#fee2e2', color: '#b91c1c',
          fontSize: 11, fontWeight: 800,
        }}>Gecikti</span>
      )}
    </span>
  );
}

export function HealthPage({user}) {
  const canEdit = ['global_admin', 'company_admin', 'workplace_physician', 'other_health_personnel'].includes(user.role);
  const isPhysician = ['global_admin', 'workplace_physician'].includes(user.role);
  const isGlobal = user.role === 'global_admin';

  const [companies, setCompanies] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);
  const [meta, setMeta] = useState({record_types: [], fitness_statuses: []});
  const [companyId, setCompanyId] = useState(user.company_id ? String(user.company_id) : '');
  const [q, setQ] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [tab, setTab] = useState('kayitlar');
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(() => emptyForm(user));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const typeMap = useMemo(() => {
    const m = {...TYPE_FALLBACK};
    for (const t of meta.record_types || []) m[t.code] = t.label;
    return m;
  }, [meta]);

  const fitnessOpts = useMemo(() => {
    if (meta.fitness_statuses?.length) return meta.fitness_statuses;
    return Object.entries(FITNESS_FALLBACK).map(([code, label]) => ({code, label}));
  }, [meta]);

  const qs = useMemo(() => {
    const p = new URLSearchParams();
    if (isGlobal && companyId) p.set('company_id', companyId);
    if (q) p.set('q', q);
    if (typeFilter) p.set('record_type', typeFilter);
    if (overdueOnly) p.set('overdue_only', 'true');
    return p.toString();
  }, [companyId, q, typeFilter, overdueOnly, isGlobal]);

  async function load() {
    if (!canEdit) return;
    setMessage('');
    try {
      const sumQs = new URLSearchParams();
      if (isGlobal && companyId) sumQs.set('company_id', companyId);
      const [c, e, r, s, m] = await Promise.all([
        api('/companies'),
        api('/employees'),
        api(`/health-records?${qs}`),
        api(`/health-records/summary?${sumQs}`),
        api('/health-records/meta'),
      ]);
      setCompanies(c);
      setEmployees(e);
      setRows(r);
      setSummary(s);
      setMeta(m);
      if (!companyId && c.length) setCompanyId(String(user.company_id || c[0].id));
    } catch (err) {
      setMessage(err.message || 'Yükleme başarısız.');
    }
  }

  useEffect(() => { load(); }, [qs]);

  const companyEmployees = useMemo(
    () => employees.filter((x) => String(x.company_id) === String(form.company_id || companyId)),
    [employees, form.company_id, companyId],
  );

  async function applySuggest(empId, company) {
    const emp = employees.find((x) => String(x.id) === String(empId));
    if (!emp) return;
    try {
      const sug = await api(
        `/health-records/suggest?job_title=${encodeURIComponent(emp.job_title || '')}`
        + `&department=${encodeURIComponent(emp.department || '')}`,
      );
      setForm((f) => ({
        ...f,
        employee_id: empId,
        company_id: company || f.company_id,
        suggested_tests: (sug.suggested_tests || []).join(', '),
        exposures: (sug.exposures || []).join(', '),
      }));
    } catch {
      setForm((f) => ({...f, employee_id: empId, company_id: company || f.company_id}));
    }
  }

  function openCreate() {
    setEditing(null);
    const base = {...emptyForm(user), company_id: companyId || user.company_id || ''};
    setForm(base);
    setOpen(true);
  }

  function openEdit(row) {
    setEditing(row);
    setForm({
      company_id: row.company_id,
      employee_id: row.employee_id,
      record_type: row.record_type,
      examination_date: row.examination_date || '',
      next_examination_date: row.next_examination_date || '',
      fitness_status: row.fitness_status || 'pending',
      physician_name: row.physician_name || '',
      summary: row.summary || '',
      confidential_note: row.confidential_note || '',
      audiometry_date: row.audiometry_date || '',
      audiometry_result: row.audiometry_result || '',
      spirometry_date: row.spirometry_date || '',
      spirometry_result: row.spirometry_result || '',
      chest_xray_date: row.chest_xray_date || '',
      chest_xray_result: row.chest_xray_result || '',
      blood_lead_date: row.blood_lead_date || '',
      blood_lead_value: row.blood_lead_value ?? '',
      blood_lead_unit: row.blood_lead_unit || 'µg/dL',
      blood_lead_ref: row.blood_lead_ref ?? '30',
      suggested_tests: row.suggested_tests || '',
      exposures: row.exposures || '',
      follow_up_note: row.follow_up_note || '',
    });
    setOpen(true);
  }

  function payloadFromForm() {
    const numOrNull = (v) => (v === '' || v == null ? null : Number(v));
    return {
      company_id: Number(form.company_id),
      employee_id: Number(form.employee_id),
      record_type: form.record_type,
      examination_date: form.examination_date,
      next_examination_date: form.next_examination_date || null,
      fitness_status: form.fitness_status,
      physician_name: form.physician_name || null,
      summary: form.summary || null,
      confidential_note: form.confidential_note || null,
      audiometry_date: form.audiometry_date || null,
      audiometry_result: form.audiometry_result || null,
      spirometry_date: form.spirometry_date || null,
      spirometry_result: form.spirometry_result || null,
      chest_xray_date: form.chest_xray_date || null,
      chest_xray_result: form.chest_xray_result || null,
      blood_lead_date: form.blood_lead_date || null,
      blood_lead_value: numOrNull(form.blood_lead_value),
      blood_lead_unit: form.blood_lead_unit || null,
      blood_lead_ref: numOrNull(form.blood_lead_ref),
      suggested_tests: form.suggested_tests || null,
      exposures: form.exposures || null,
      follow_up_note: form.follow_up_note || null,
    };
  }

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setMessage('');
    try {
      const payload = payloadFromForm();
      if (editing) {
        const {company_id: _c, employee_id: _e, ...patch} = payload;
        await api(`/health-records/${editing.id}`, {method: 'PATCH', body: JSON.stringify(patch)});
      } else {
        await api('/health-records', {method: 'POST', body: JSON.stringify(payload)});
      }
      setOpen(false);
      await load();
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(row) {
    if (!window.confirm(`${row.employee_name || 'Kayıt'} silinsin mi?`)) return;
    setBusy(true);
    try {
      await api(`/health-records/${row.id}`, {method: 'DELETE'});
      await load();
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function exportTxt() {
    try {
      const p = new URLSearchParams();
      if (isGlobal && companyId) p.set('company_id', companyId);
      await downloadFile(`/health-records/export.txt?${p}`, 'saglik-gozetimi.txt');
    } catch (err) {
      setMessage(err.message);
    }
  }

  if (!canEdit) {
    return (
      <div className="page-title">
        <h3>Sağlık Gözetimi</h3>
        <section className="panel" style={{marginTop: 16}}>
          <p>Sağlık kayıtları yalnızca hekim, DSP, firma yöneticisi ve global yönetici tarafından görüntülenir.</p>
        </section>
      </div>
    );
  }

  return (
    <>
      <div className="page-title">
        <h3>Sağlık Gözetimi</h3>
        <div className="actions">
          <button type="button" className="secondary" onClick={load} disabled={busy}><RefreshCw size={16} /> Yenile</button>
          <button type="button" className="secondary" onClick={exportTxt}><Download size={16} /> TXT</button>
          <button type="button" onClick={openCreate} disabled={busy}><Plus size={16} /> Yeni Kayıt</button>
        </div>
      </div>

      <section className="panel" style={{marginBottom: 16}}>
        <div className="form-grid" style={{gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', marginBottom: 0}}>
          {isGlobal && (
            <Select label="Firma" value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
              <option value="">Seçiniz</option>
              {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          )}
          <label className="field">
            <span>Ara</span>
            <div className="search" style={{margin: 0}}>
              <Search size={16} />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Personel / hekim..." />
            </div>
          </label>
          <Select label="Muayene türü" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
            <option value="">Tümü</option>
            {Object.entries(typeMap).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
          <Select label="Filtre" value={overdueOnly ? '1' : ''} onChange={(e) => setOverdueOnly(!!e.target.value)}>
            <option value="">Tüm kayıtlar</option>
            <option value="1">Yalnız geciken</option>
          </Select>
        </div>
        {message && <p style={{marginTop: 12}}>{message}</p>}
      </section>

      <div className="cards" style={{marginBottom: 16}}>
        <article className="metric"><span>Toplam</span><strong>{summary?.total ?? '—'}</strong></article>
        <article className="metric"><span>Geciken</span><strong style={{color: '#b91c1c'}}>{summary?.overdue ?? '—'}</strong></article>
        <article className="metric"><span>30 gün içinde</span><strong style={{color: '#d97706'}}>{summary?.due_soon ?? '—'}</strong></article>
        <article className="metric"><span>Kurşun yüksek</span><strong style={{color: '#b91c1c'}}>{summary?.lead_high ?? '—'}</strong></article>
      </div>

      <div className="actions" style={{marginBottom: 12, gap: 8}}>
        <button type="button" className={tab === 'kayitlar' ? '' : 'secondary'} onClick={() => setTab('kayitlar')}>
          <HeartPulse size={16} /> Kayıtlar
        </button>
        <button type="button" className={tab === 'analiz' ? '' : 'secondary'} onClick={() => setTab('analiz')}>
          Analiz Özeti
        </button>
      </div>

      {tab === 'analiz' ? (
        <section className="panel">
          <h3 style={{marginTop: 0}}>Sağlık Analiz Merkezi</h3>
          <div className="cards">
            <article className="metric"><span>Uygun</span><strong>{summary?.fit ?? 0}</strong></article>
            <article className="metric"><span>Kısıtlı</span><strong>{summary?.conditional ?? 0}</strong></article>
            <article className="metric"><span>Takip</span><strong>{summary?.tracking ?? 0}</strong></article>
            <article className="metric"><span>Uygun değil</span><strong>{summary?.unfit ?? 0}</strong></article>
          </div>
          <div className="cards" style={{marginTop: 12}}>
            <article className="metric"><span>Odyometri kaydı</span><strong>{summary?.with_audiometry ?? 0}</strong></article>
            <article className="metric"><span>SFT kaydı</span><strong>{summary?.with_spirometry ?? 0}</strong></article>
            <article className="metric"><span>Akciğer grafisi</span><strong>{summary?.with_chest_xray ?? 0}</strong></article>
            <article className="metric"><span>Kan kurşun</span><strong>{summary?.with_blood_lead ?? 0}</strong></article>
          </div>
        </section>
      ) : (
        <section className="panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Personel</th>
                  <th>Muayene</th>
                  <th>Tarih</th>
                  <th>Sonraki</th>
                  <th>Hekim</th>
                  <th>Tetkik</th>
                  <th>Durum</th>
                  <th>İşlem</th>
                </tr>
              </thead>
              <tbody>
                {rows.length ? rows.map((r) => {
                  const tetkik = [
                    r.audiometry_result && `Odyo: ${r.audiometry_result}`,
                    r.spirometry_result && `SFT: ${r.spirometry_result}`,
                    r.chest_xray_result && `AG: ${r.chest_xray_result}`,
                    r.blood_lead_value != null && `Pb: ${r.blood_lead_value} (${r.blood_lead_eval || '—'})`,
                  ].filter(Boolean).join(' · ');
                  return (
                    <tr key={r.id}>
                      <td>
                        <div>{r.employee_name || `#${r.employee_id}`}</div>
                        <div style={{fontSize: 12, color: '#64748b'}}>{r.job_title || r.department || ''}</div>
                      </td>
                      <td>{typeMap[r.record_type] || r.record_type}</td>
                      <td>{r.examination_date}</td>
                      <td>{r.next_examination_date || '—'}</td>
                      <td>{r.physician_name || '—'}</td>
                      <td style={{fontSize: 12, maxWidth: 220}}>{tetkik || '—'}</td>
                      <td>{fitnessBadge(r.fitness_status, r.is_overdue)}</td>
                      <td>
                        <div className="actions" style={{gap: 6}}>
                          <button type="button" className="mini" onClick={() => openEdit(r)}>Düzenle</button>
                          <button type="button" className="mini" onClick={() => remove(r)}>Sil</button>
                        </div>
                      </td>
                    </tr>
                  );
                }) : (
                  <tr><td colSpan={8} className="empty">Kayıt yok. Yeni muayene ekleyebilirsiniz.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {open && (
        <Modal title={editing ? 'Sağlık Kaydını Düzenle' : 'Yeni Sağlık Kaydı'} close={() => setOpen(false)}>
          <form className="form-grid" onSubmit={save}>
            {!editing && (
              <>
                <Select label="Firma" required value={form.company_id} onChange={(e) => setForm({...form, company_id: e.target.value, employee_id: ''})}>
                  <option value="">Seçiniz</option>
                  {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </Select>
                <Select
                  label="Personel"
                  required
                  value={form.employee_id}
                  onChange={(e) => applySuggest(e.target.value, form.company_id)}
                >
                  <option value="">Seçiniz</option>
                  {companyEmployees.map((x) => <option key={x.id} value={x.id}>{x.full_name}</option>)}
                </Select>
              </>
            )}
            <Select label="Muayene türü" value={form.record_type} onChange={(e) => setForm({...form, record_type: e.target.value})}>
              {Object.entries(typeMap).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
            <Field label="Muayene tarihi" type="date" required value={form.examination_date} onChange={(e) => setForm({...form, examination_date: e.target.value})} />
            <Field label="Sonraki muayene" type="date" value={form.next_examination_date} onChange={(e) => setForm({...form, next_examination_date: e.target.value})} />
            <Select label="Uygunluk" value={form.fitness_status} onChange={(e) => setForm({...form, fitness_status: e.target.value})}>
              {fitnessOpts.map((s) => <option key={s.code} value={s.code}>{s.label}</option>)}
            </Select>
            <Field label="İşyeri hekimi" value={form.physician_name} onChange={(e) => setForm({...form, physician_name: e.target.value})} />
            <TextArea label="Özet" value={form.summary} onChange={(e) => setForm({...form, summary: e.target.value})} />
            {isPhysician && (
              <TextArea label="Gizli hekim notu" value={form.confidential_note} onChange={(e) => setForm({...form, confidential_note: e.target.value})} />
            )}
            <Field label="Odyometri tarihi" type="date" value={form.audiometry_date} onChange={(e) => setForm({...form, audiometry_date: e.target.value})} />
            <Field label="Odyometri sonuç" value={form.audiometry_result} onChange={(e) => setForm({...form, audiometry_result: e.target.value})} />
            <Field label="SFT tarihi" type="date" value={form.spirometry_date} onChange={(e) => setForm({...form, spirometry_date: e.target.value})} />
            <Field label="SFT sonuç" value={form.spirometry_result} onChange={(e) => setForm({...form, spirometry_result: e.target.value})} />
            <Field label="Akciğer grafisi tarihi" type="date" value={form.chest_xray_date} onChange={(e) => setForm({...form, chest_xray_date: e.target.value})} />
            <Field label="Akciğer sonuç" value={form.chest_xray_result} onChange={(e) => setForm({...form, chest_xray_result: e.target.value})} />
            <Field label="Kan kurşun tarihi" type="date" value={form.blood_lead_date} onChange={(e) => setForm({...form, blood_lead_date: e.target.value})} />
            <Field label="Kan kurşun değer" type="number" step="0.1" value={form.blood_lead_value} onChange={(e) => setForm({...form, blood_lead_value: e.target.value})} />
            <Field label="Birim" value={form.blood_lead_unit} onChange={(e) => setForm({...form, blood_lead_unit: e.target.value})} />
            <Field label="Referans" type="number" step="0.1" value={form.blood_lead_ref} onChange={(e) => setForm({...form, blood_lead_ref: e.target.value})} />
            <TextArea label="Önerilen tetkikler" value={form.suggested_tests} onChange={(e) => setForm({...form, suggested_tests: e.target.value})} />
            <TextArea label="Maruziyetler" value={form.exposures} onChange={(e) => setForm({...form, exposures: e.target.value})} />
            <TextArea label="Takip notu" value={form.follow_up_note} onChange={(e) => setForm({...form, follow_up_note: e.target.value})} />
            <div className="form-actions">
              <button type="submit" disabled={busy}>{editing ? 'Güncelle' : 'Kaydet'}</button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
