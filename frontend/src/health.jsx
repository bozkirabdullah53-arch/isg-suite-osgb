import React, {useEffect, useMemo, useState} from 'react';
import {Download, FileText, HeartPulse, Plus, Printer, RefreshCw, Search, Upload, X} from 'lucide-react';
import {api, downloadFile, uploadFile} from './api';

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

const EXPOSURE_FALLBACK = [
  'Kurşun', 'Kimyasal', 'Solvent', 'Toz', 'Gürültü', 'Titreşim', 'Ergonomi',
  'Yüksekte çalışma', 'Elektrik', 'Biyolojik', 'Radyasyon', 'Sıcak ortam',
  'Soğuk ortam', 'Kapalı alan', 'Gece çalışması',
];

function Modal({title, close, children}) {
  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <section className="modal" style={{maxWidth: 980}}>
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
    exposures: [],
    follow_up_note: '',
    other_biological_test: '',
    period_note: '',
    meslek_label: '',
  };
}

function fitnessBadge(status, overdue) {
  const color =
    status === 'fit' ? '#16a34a'
      : status === 'unfit' ? '#b91c1c'
        : status === 'conditional' || status === 'tracking' ? '#d97706'
          : '#64748b';
  return (
    <span style={{display: 'inline-flex', alignItems: 'center', gap: 6, flexWrap: 'wrap'}}>
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

function MiniTable({title, rows, empty}) {
  return (
    <section className="panel" style={{marginBottom: 12}}>
      <h4 style={{marginTop: 0}}>{title} ({rows?.length || 0})</h4>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Personel</th>
              <th>Görev</th>
              <th>Detay</th>
            </tr>
          </thead>
          <tbody>
            {(rows || []).length ? rows.map((r, i) => (
              <tr key={r.id || r.employee_id || i}>
                <td>{r.employee_name || r.full_name || '—'}</td>
                <td>{r.job_title || '—'}</td>
                <td style={{fontSize: 12}}>
                  {r.blood_lead_value != null
                    ? `${r.blood_lead_value} ${r.blood_lead_unit || ''} · ${r.lead_label || ''}`
                    : (r.department || r.smart_summary || '—')}
                </td>
              </tr>
            )) : (
              <tr><td colSpan={3} className="empty">{empty || 'Kayıt yok.'}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function HealthPage({user}) {
  const canEdit = ['global_admin', 'company_admin', 'workplace_physician', 'other_health_personnel'].includes(user.role);
  const isPhysician = ['global_admin', 'workplace_physician'].includes(user.role);
  const isGlobal = user.role === 'global_admin';

  const [companies, setCompanies] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [physicians, setPhysicians] = useState([]);
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [meta, setMeta] = useState({record_types: [], fitness_statuses: [], exposure_options: []});
  const [companyId, setCompanyId] = useState(user.company_id ? String(user.company_id) : '');
  const [q, setQ] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [tab, setTab] = useState('kayitlar');
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(() => emptyForm(user));
  const [reportFile, setReportFile] = useState(null);
  const [leadLive, setLeadLive] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [physicianCustom, setPhysicianCustom] = useState(false);

  const typeMap = useMemo(() => {
    const m = {...TYPE_FALLBACK};
    for (const t of meta.record_types || []) m[t.code] = t.label;
    return m;
  }, [meta]);

  const fitnessOpts = useMemo(() => {
    if (meta.fitness_statuses?.length) return meta.fitness_statuses;
    return Object.entries(FITNESS_FALLBACK).map(([code, label]) => ({code, label}));
  }, [meta]);

  const exposureOpts = meta.exposure_options?.length ? meta.exposure_options : EXPOSURE_FALLBACK;

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
      const [c, e, r, s, m, a] = await Promise.all([
        api('/companies'),
        api('/employees?active=true'),
        api(`/health-records?${qs}`),
        api(`/health-records/summary?${sumQs}`),
        api('/health-records/meta'),
        api(`/health-records/analysis?${sumQs}`),
      ]);
      setCompanies(c);
      setEmployees(e);
      setRows(r);
      setSummary(s);
      setMeta(m);
      setAnalysis(a);
      const nextCid = companyId || String(user.company_id || c[0]?.id || '');
      if (!companyId && nextCid) setCompanyId(nextCid);

      // İşyeri hekimleri: OSGB profesyonelleri + personel listesi
      let hekimler = [];
      try {
        const oid = user.osgb_id || c.find((x) => String(x.id) === String(nextCid))?.osgb_id;
        const pros = oid
          ? await api(`/osgb/professionals?osgb_id=${oid}`).catch(() => [])
          : await api('/osgb/professionals').catch(() => []);
        hekimler = (pros || []).filter(
          (p) => p.is_active !== false && (
            p.professional_type === 'workplace_physician'
            || user.role === 'workplace_physician'
          ),
        );
      } catch (_) { /* ignore */ }
      setPhysicians(hekimler);
    } catch (err) {
      setMessage(err.message || 'Yükleme başarısız.');
    }
  }

  useEffect(() => { load(); }, [qs]);

  useEffect(() => {
    const v = form.blood_lead_value;
    if (v === '' || v == null) {
      setLeadLive(null);
      return;
    }
    const t = setTimeout(() => {
      api(`/health-records/lead-eval?value=${encodeURIComponent(v)}&ref=${encodeURIComponent(form.blood_lead_ref || 30)}`)
        .then(setLeadLive)
        .catch(() => setLeadLive(null));
    }, 250);
    return () => clearTimeout(t);
  }, [form.blood_lead_value, form.blood_lead_ref]);

  const companyEmployees = useMemo(
    () => employees.filter((x) => String(x.company_id) === String(form.company_id || companyId) && x.is_active !== false),
    [employees, form.company_id, companyId],
  );

  const physicianOptions = useMemo(() => {
    const seen = new Set();
    const out = [];
    const add = (name, note) => {
      const n = (name || '').trim();
      const key = n.toLocaleLowerCase('tr');
      if (!n || seen.has(key)) return;
      seen.add(key);
      out.push({name: n, note});
    };
    for (const p of physicians) add(p.full_name, 'İşyeri hekimi');
    if (user.role === 'workplace_physician' && user.full_name) add(user.full_name, 'Ben');
    // Firma personel listesinden seçim (PRO parity)
    for (const e of companyEmployees) add(e.full_name, e.job_title || 'Personel');
    return out;
  }, [physicians, companyEmployees, user]);

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
        exposures: sug.exposures || [],
        period_note: sug.period_note || '',
        meslek_label: sug.label || '',
      }));
    } catch {
      setForm((f) => ({...f, employee_id: empId, company_id: company || f.company_id}));
    }
  }

  function toggleExposure(name) {
    setForm((f) => {
      const cur = Array.isArray(f.exposures) ? f.exposures : String(f.exposures || '').split(',').map((x) => x.trim()).filter(Boolean);
      return {
        ...f,
        exposures: cur.includes(name) ? cur.filter((x) => x !== name) : [...cur, name],
      };
    });
  }

  function openCreate() {
    setEditing(null);
    setReportFile(null);
    setLeadLive(null);
    setPhysicianCustom(false);
    const cid = companyId || user.company_id || '';
    const base = {...emptyForm(user), company_id: cid};
    // Hekim kendi adını listeden seçili getir
    if (user.role === 'workplace_physician' && user.full_name) {
      base.physician_name = user.full_name;
    }
    setForm(base);
    setOpen(true);
  }

  function openEdit(row) {
    setEditing(row);
    setReportFile(null);
    const exp = row.exposures
      ? (Array.isArray(row.exposures) ? row.exposures : String(row.exposures).split(',').map((x) => x.trim()).filter(Boolean))
      : [];
    const inList = physicianOptions.some((p) => p.name === (row.physician_name || ''));
    setPhysicianCustom(!!(row.physician_name && !inList));
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
      exposures: exp,
      follow_up_note: row.follow_up_note || '',
      other_biological_test: row.other_biological_test || '',
      period_note: '',
      meslek_label: '',
    });
    setOpen(true);
  }

  function payloadFromForm() {
    const numOrNull = (v) => (v === '' || v == null ? null : Number(v));
    const exposures = Array.isArray(form.exposures) ? form.exposures.join(', ') : (form.exposures || null);
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
      exposures,
      follow_up_note: form.follow_up_note || null,
      other_biological_test: form.other_biological_test || null,
    };
  }

  async function save(e) {
    e.preventDefault();
    if (!form.employee_id && !editing) {
      setMessage('Personeli listeden seçiniz.');
      return;
    }
    if (!(form.physician_name || '').trim()) {
      setMessage('İşyeri hekimini listeden seçiniz.');
      return;
    }
    setBusy(true);
    setMessage('');
    try {
      const payload = payloadFromForm();
      let id = editing?.id;
      if (editing) {
        const {company_id: _c, employee_id: _e, ...patch} = payload;
        await api(`/health-records/${editing.id}`, {method: 'PATCH', body: JSON.stringify(patch)});
      } else {
        const created = await api('/health-records', {method: 'POST', body: JSON.stringify(payload)});
        id = created.id;
      }
      if (reportFile && id) {
        await uploadFile(`/health-records/${id}/report`, reportFile);
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

  function companyQs() {
    const p = new URLSearchParams();
    if (isGlobal && companyId) p.set('company_id', companyId);
    return p.toString();
  }

  async function exportTxt() {
    try { await downloadFile(`/health-records/export.txt?${companyQs()}`, 'saglik-gozetimi.txt'); }
    catch (err) { setMessage(err.message); }
  }
  async function exportXlsx() {
    try { await downloadFile(`/health-records/export.xlsx?${companyQs()}`, 'saglik-gozetimi.xlsx'); }
    catch (err) { setMessage(err.message); }
  }
  async function exportAnalysis() {
    try { await downloadFile(`/health-records/analysis.txt?${companyQs()}`, 'saglik-analiz-raporu.txt'); }
    catch (err) { setMessage(err.message); }
  }
  async function openForm(row) {
    try {
      const token = localStorage.getItem('isg_token');
      const base = import.meta.env.VITE_API_URL
        || ((window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
          ? `${window.location.protocol}//${window.location.hostname}:8000/api/v1`
          : 'https://isg-suite-api-1u9t.onrender.com/api/v1');
      const r = await fetch(`${base}/health-records/${row.id}/form.html`, {
        headers: token ? {Authorization: `Bearer ${token}`} : {},
      });
      if (!r.ok) throw new Error('Form açılamadı.');
      const html = await r.text();
      const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const w = window.open(url, '_blank');
      if (!w) {
        URL.revokeObjectURL(url);
        throw new Error('Pop-up engellendi; yazdırma penceresine izin verin.');
      }
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      setMessage(err.message);
    }
  }
  async function downloadReport(row) {
    try { await downloadFile(`/health-records/${row.id}/report`, row.report_file_name || 'saglik-raporu'); }
    catch (err) { setMessage(err.message); }
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

  const selectedExposures = Array.isArray(form.exposures)
    ? form.exposures
    : String(form.exposures || '').split(',').map((x) => x.trim()).filter(Boolean);

  return (
    <>
      <div className="page-title">
        <h3>Sağlık Gözetimi</h3>
        <div className="actions">
          <button type="button" className="secondary" onClick={load} disabled={busy}><RefreshCw size={16} /> Yenile</button>
          <button type="button" className="secondary" onClick={exportTxt}><Download size={16} /> TXT</button>
          <button type="button" className="secondary" onClick={exportXlsx}><Download size={16} /> Excel</button>
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
        {message && <p style={{marginTop: 12, color: '#b91c1c'}}>{message}</p>}
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
          Sağlık Analiz Merkezi
        </button>
      </div>

      {tab === 'analiz' ? (
        <>
          <section className="panel" style={{marginBottom: 12}}>
            <div style={{display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center'}}>
              <div>
                <h3 style={{margin: 0}}>Sağlık Analiz Merkezi</h3>
                <p style={{margin: '6px 0 0', color: '#64748b', fontSize: 14}}>
                  {analysis?.company_name || 'Firma'} — kurşun maruziyeti, tetkik takip ve eksik kayıtlar
                </p>
              </div>
              <button type="button" className="secondary" onClick={exportAnalysis}><Download size={16} /> Analiz TXT</button>
            </div>
            <div className="cards" style={{marginTop: 14}}>
              <article className="metric"><span>Kurşun ölçümü</span><strong>{analysis?.total_lead ?? 0}</strong></article>
              <article className="metric"><span>≥30 µg/dL</span><strong style={{color: '#d97706'}}>{analysis?.over30?.length ?? 0} ({analysis?.pct30 ?? 0}%)</strong></article>
              <article className="metric"><span>≥40</span><strong style={{color: '#b91c1c'}}>{analysis?.over40?.length ?? 0} ({analysis?.pct40 ?? 0}%)</strong></article>
              <article className="metric"><span>≥45</span><strong style={{color: '#991b1b'}}>{analysis?.over45?.length ?? 0} ({analysis?.pct45 ?? 0}%)</strong></article>
            </div>
            <div className="cards" style={{marginTop: 12}}>
              {(analysis?.ranges || []).map((r) => (
                <article className="metric" key={r.label}><span>{r.label}</span><strong>{r.count}</strong></article>
              ))}
            </div>
          </section>
          <MiniTable title="≥30 Kurşun listesi" rows={analysis?.over30} />
          <MiniTable title="Odyometri takip" rows={analysis?.odyo_follow} />
          <MiniTable title="SFT takip" rows={analysis?.sft_follow} />
          <MiniTable title="Akciğer takip" rows={analysis?.chest_follow} />
          <MiniTable title="Kurşun maruziyeti var, değer yok" rows={analysis?.missing_lead} />
          <MiniTable title="Sağlık kaydı eksik personel" rows={analysis?.missing_employees} empty="Tüm aktif personelin kaydı var." />
        </>
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
                  <th>Akıllı özet</th>
                  <th>Durum</th>
                  <th>İşlem</th>
                </tr>
              </thead>
              <tbody>
                {rows.length ? rows.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <div>{r.employee_name || `#${r.employee_id}`}</div>
                      <div style={{fontSize: 12, color: '#64748b'}}>{r.job_title || r.department || ''}</div>
                    </td>
                    <td>{typeMap[r.record_type] || r.record_type}</td>
                    <td>{r.examination_date}</td>
                    <td>{r.next_examination_date || '—'}</td>
                    <td>{r.physician_name || '—'}</td>
                    <td style={{fontSize: 12, maxWidth: 180}}>{r.tetkik_summary || '—'}</td>
                    <td style={{fontSize: 12, maxWidth: 200}}>{r.smart_summary || '—'}</td>
                    <td>{fitnessBadge(r.fitness_status, r.is_overdue)}</td>
                    <td>
                      <div className="actions" style={{gap: 6, flexWrap: 'wrap'}}>
                        <button type="button" className="mini" onClick={() => openEdit(r)}>Düzenle</button>
                        <button type="button" className="mini" onClick={() => openForm(r)}><Printer size={12} /> Form</button>
                        {r.has_report && (
                          <button type="button" className="mini" onClick={() => downloadReport(r)}><FileText size={12} /> Rapor</button>
                        )}
                        <button type="button" className="mini" onClick={() => remove(r)}>Sil</button>
                      </div>
                    </td>
                  </tr>
                )) : (
                  <tr><td colSpan={9} className="empty">Kayıt yok. Yeni muayene ekleyebilirsiniz.</td></tr>
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
                <Select label="Firma" required value={form.company_id} onChange={(e) => setForm({...form, company_id: e.target.value, employee_id: '', physician_name: form.physician_name})}>
                  <option value="">Seçiniz</option>
                  {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </Select>
                <Select
                  label="Personel (listeden seçin)"
                  required
                  value={form.employee_id}
                  onChange={(e) => applySuggest(e.target.value, form.company_id)}
                >
                  <option value="">{form.company_id ? (companyEmployees.length ? 'Seçiniz' : 'Bu firmada personel yok — Personel menüsünden ekleyin') : 'Önce firma seçin'}</option>
                  {companyEmployees.map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.full_name}{x.job_title ? ` — ${x.job_title}` : ''}
                    </option>
                  ))}
                </Select>
              </>
            )}
            {(form.meslek_label || form.period_note) && (
              <div style={{gridColumn: '1/-1', background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 10, padding: 12}}>
                <strong>{form.meslek_label || 'Meslek önerisi'}</strong>
                {form.period_note && <p style={{margin: '6px 0 0', fontSize: 13, color: '#0c4a6e'}}>{form.period_note}</p>}
              </div>
            )}
            <Select label="Muayene türü" value={form.record_type} onChange={(e) => setForm({...form, record_type: e.target.value})}>
              {Object.entries(typeMap).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
            <Field label="Muayene tarihi" type="date" required value={form.examination_date} onChange={(e) => setForm({...form, examination_date: e.target.value})} />
            <Field label="Sonraki muayene" type="date" value={form.next_examination_date} onChange={(e) => setForm({...form, next_examination_date: e.target.value})} />
            <Select label="Uygunluk" value={form.fitness_status} onChange={(e) => setForm({...form, fitness_status: e.target.value})}>
              {fitnessOpts.map((s) => <option key={s.code} value={s.code}>{s.label}</option>)}
            </Select>
            {!physicianCustom ? (
              <Select
                label="İşyeri hekimi (listeden seçin)"
                required
                value={form.physician_name}
                onChange={(e) => {
                  if (e.target.value === '__custom__') {
                    setPhysicianCustom(true);
                    setForm({...form, physician_name: ''});
                  } else {
                    setForm({...form, physician_name: e.target.value});
                  }
                }}
              >
                <option value="">Seçiniz</option>
                {physicianOptions.map((p) => (
                  <option key={p.name} value={p.name}>{p.name}{p.note ? ` (${p.note})` : ''}</option>
                ))}
                <option value="__custom__">Listede yok — elle yaz…</option>
              </Select>
            ) : (
              <Field
                label="İşyeri hekimi (elle)"
                required
                value={form.physician_name}
                onChange={(e) => setForm({...form, physician_name: e.target.value})}
                placeholder="Ad Soyad"
              />
            )}
            {physicianCustom && (
              <button type="button" className="mini" style={{alignSelf: 'end'}} onClick={() => { setPhysicianCustom(false); setForm({...form, physician_name: ''}); }}>
                Listeye dön
              </button>
            )}
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
            {leadLive?.code && (
              <div style={{gridColumn: '1/-1', fontSize: 13, color: leadLive.code === 'normal' ? '#166534' : '#9a3412'}}>
                Canlı kurşun değerlendirme: <strong>{leadLive.label}</strong>
              </div>
            )}
            <TextArea label="Önerilen tetkikler" value={form.suggested_tests} onChange={(e) => setForm({...form, suggested_tests: e.target.value})} />
            <div style={{gridColumn: '1/-1'}}>
              <div style={{fontSize: 13, color: '#64748b', marginBottom: 8}}>Maruziyetler (çoklu seçim)</div>
              <div style={{display: 'flex', flexWrap: 'wrap', gap: 8}}>
                {exposureOpts.map((name) => (
                  <label key={name} style={{display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, background: selectedExposures.includes(name) ? '#ecfdf5' : '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '6px 10px'}}>
                    <input type="checkbox" checked={selectedExposures.includes(name)} onChange={() => toggleExposure(name)} />
                    {name}
                  </label>
                ))}
              </div>
            </div>
            <TextArea label="Diğer biyolojik tetkik" value={form.other_biological_test} onChange={(e) => setForm({...form, other_biological_test: e.target.value})} />
            <TextArea label="Takip notu" value={form.follow_up_note} onChange={(e) => setForm({...form, follow_up_note: e.target.value})} />
            <label className="field" style={{gridColumn: '1/-1'}}>
              <span>Muayene / tetkik raporu (pdf / jpg / png / docx){editing?.report_file_name ? ` — mevcut: ${editing.report_file_name}` : ''}</span>
              <input type="file" accept=".pdf,.jpg,.jpeg,.png,.docx" onChange={(e) => setReportFile(e.target.files?.[0] || null)} />
              {reportFile && <small style={{color: '#475569'}}><Upload size={12} /> {reportFile.name}</small>}
            </label>
            <div className="form-actions">
              <button type="submit" disabled={busy}>{editing ? 'Güncelle' : 'Kaydet'}</button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
