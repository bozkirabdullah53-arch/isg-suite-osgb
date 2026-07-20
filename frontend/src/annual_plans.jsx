import React, {useEffect, useMemo, useState} from 'react';
import {ClipboardCheck, Download, Plus, RefreshCw, Sparkles, X} from 'lucide-react';
import {api, downloadFile, wakeApi} from './api';

const MONTHS = [
  '', 'Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
  'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık',
];

const CATEGORY_FALLBACK = {
  yillik_calisma: 'Yıllık Çalışma Planı',
  egitim: 'Eğitim',
  saglik: 'Sağlık',
  periyodik: 'Periyodik Kontrol',
  tatbikat: 'Tatbikat / Acil Durum',
  kkd: 'KKD',
  diger: 'Diğer',
};

const STATUS_FALLBACK = {
  planned: 'Planlandı',
  in_progress: 'Devam Ediyor',
  completed: 'Tamamlandı',
  delayed: 'Gecikti',
  cancelled: 'İptal',
};

function Modal({title, close, children}) {
  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <section className="modal" style={{maxWidth: 720}}>
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
      <textarea rows={3} {...p} />
    </label>
  );
}

function statusBadge(status) {
  const cls =
    status === 'completed' ? 'ok'
      : status === 'delayed' ? 'off'
        : status === 'cancelled' ? 'off'
          : '';
  return (
    <span className={`badge ${cls || 'off'}`}>
      {STATUS_FALLBACK[status] || status}
    </span>
  );
}

function emptyForm(user, year) {
  return {
    company_id: user.company_id || '',
    year,
    month: new Date().getMonth() + 1,
    category: 'yillik_calisma',
    activity: '',
    description: '',
    responsible_name: '',
    target_date: '',
    status: 'planned',
    completion_date: '',
    notes: '',
  };
}

export function AnnualPlansPage({user}) {
  const nowYear = new Date().getFullYear();
  const canEdit = [
    'global_admin',
    'company_admin',
    'safety_specialist',
    'workplace_physician',
    'other_health_personnel',
  ].includes(user.role);
  const fieldRole = ['safety_specialist', 'workplace_physician', 'other_health_personnel'].includes(user.role);

  const [companies, setCompanies] = useState([]);
  const [companyId, setCompanyId] = useState(user.company_id ? String(user.company_id) : '');
  const [year, setYear] = useState(nowYear);
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);
  const [categories, setCategories] = useState([]);
  const [statuses, setStatuses] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(() => emptyForm(user, nowYear));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const catMap = useMemo(() => {
    const m = {...CATEGORY_FALLBACK};
    for (const c of categories) m[c.code] = c.label;
    return m;
  }, [categories]);

  const statusOpts = useMemo(() => {
    if (statuses.length) return statuses;
    return Object.entries(STATUS_FALLBACK).map(([code, label]) => ({code, label}));
  }, [statuses]);

  function pickCompanyId(list, preferred) {
    const ids = list.map((c) => String(c.id));
    if (preferred && ids.includes(String(preferred))) return String(preferred);
    if (user.company_id && ids.includes(String(user.company_id))) return String(user.company_id);
    return ids[0] || '';
  }

  async function load() {
    setMessage('');
    try {
      await wakeApi();
      const c = await api('/companies');
      setCompanies(Array.isArray(c) ? c : []);
      const cid = pickCompanyId(Array.isArray(c) ? c : [], companyId);
      if (cid && cid !== companyId) {
        setCompanyId(cid);
        return;
      }
      if (!cid) {
        setMessage(
          fieldRole
            ? 'Atanmış firma yok. Görevlendirmeler’den işyeriniz bağlanmalı.'
            : 'Önce firma seçiniz.',
        );
        setRows([]);
        setSummary(null);
        return;
      }
      const planQs = new URLSearchParams({year: String(year), company_id: cid});
      // Sıralı yükle — biri düşerse hangisi olduğu görünsün
      const meta = await api('/annual-plans/meta');
      setCategories(meta.categories || []);
      setStatuses(meta.statuses || []);
      const r = await api(`/annual-plans?${planQs}`);
      setRows(Array.isArray(r) ? r : []);
      const s = await api(`/annual-plans/summary?${planQs}`);
      setSummary(s);
    } catch (e) {
      setMessage(e.message || 'Yükleme başarısız.');
    }
  }

  useEffect(() => { load(); }, [year, companyId]);

  function openCreate() {
    const cid = companyId || user.company_id || '';
    setEditing(null);
    setForm({...emptyForm(user, year), company_id: cid, year});
    setOpen(true);
  }

  function openEdit(row) {
    setEditing(row);
    setForm({
      company_id: row.company_id,
      year: row.year,
      month: row.month,
      category: row.category || 'yillik_calisma',
      activity: row.activity || '',
      description: row.description || '',
      responsible_name: row.responsible_name || '',
      target_date: row.target_date || '',
      status: row.status || 'planned',
      completion_date: row.completion_date || '',
      notes: row.notes || '',
    });
    setOpen(true);
  }

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setMessage('');
    try {
      const payload = {
        ...form,
        company_id: Number(form.company_id),
        year: Number(form.year),
        month: Number(form.month),
        target_date: form.target_date || null,
        completion_date: form.completion_date || null,
        description: form.description || null,
        responsible_name: form.responsible_name || null,
        notes: form.notes || null,
      };
      if (editing) {
        const {company_id: _c, ...patch} = payload;
        await api(`/annual-plans/${editing.id}`, {method: 'PATCH', body: JSON.stringify(patch)});
      } else {
        await api('/annual-plans', {method: 'POST', body: JSON.stringify(payload)});
      }
      setOpen(false);
      setEditing(null);
      await load();
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(row) {
    if (!window.confirm(`"${row.activity}" maddesini silmek istiyor musunuz?`)) return;
    setBusy(true);
    try {
      await api(`/annual-plans/${row.id}`, {method: 'DELETE'});
      await load();
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function generate() {
    const cid = Number(pickCompanyId(companies, companyId) || companyId || user.company_id);
    if (!cid) {
      setMessage(
        fieldRole
          ? 'Atanmış firma yok — Görevlendirmeler’den bağlanmalı, sonra Otomatik Plan Üret’e basın.'
          : 'Önce firma seçiniz.',
      );
      return;
    }
    if (!window.confirm(
      `${year} yılı için otomatik yıllık plan üretmek istiyor musunuz?\n`
      + 'Hedef tarihler hafta sonu ve resmi tatillere denk gelmeyecek şekilde iş gününe kaydırılır.\n'
      + 'Mevcut aynı maddeler atlanır.',
    )) {
      return;
    }
    setBusy(true);
    setMessage('Sunucu hazırlanıyor, plan üretiliyor…');
    try {
      await wakeApi();
      const r = await api('/annual-plans/generate', {
        method: 'POST',
        body: JSON.stringify({company_id: cid, year: Number(year)}),
        _retries: 3,
      });
      setMessage(r.message || `${r.created} madde eklendi. Hedef tarihler iş gününe göre ayarlandı.`);
      if (String(companyId) !== String(cid)) setCompanyId(String(cid));
      else await load();
    } catch (err) {
      setMessage(err.message || 'Üretim başarısız.');
    } finally {
      setBusy(false);
    }
  }

  async function exportExcel() {
    const cid = companyId || user.company_id;
    if (!cid) {
      setMessage('Dışa aktarım için firma seçiniz.');
      return;
    }
    try {
      const p = new URLSearchParams({year: String(year), company_id: String(cid)});
      await downloadFile(`/annual-plans/export.xlsx?${p}`, `yillik-plan-${year}.xlsx`);
    } catch (err) {
      setMessage(err.message);
    }
  }

  const monthBars = summary?.by_month || {};

  return (
    <>
      <div className="page-title">
        <h3>Yıllık Çalışma Planı</h3>
        <div className="actions">
          <button type="button" className="secondary" onClick={load} disabled={busy}>
            <RefreshCw size={16} /> Yenile
          </button>
          <button type="button" className="secondary" onClick={exportExcel} disabled={busy}>
            <Download size={16} /> Excel Aktar
          </button>
          {canEdit && (
            <button type="button" className="secondary" onClick={generate} disabled={busy || !companyId}>
              <Sparkles size={16} /> Otomatik Plan Üret
            </button>
          )}
          {canEdit && (
            <button type="button" onClick={openCreate} disabled={busy}>
              <Plus size={16} /> Yeni Madde
            </button>
          )}
        </div>
      </div>

      <section className="panel" style={{marginBottom: 16}}>
        <div className="form-grid" style={{gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', marginBottom: 0}}>
          <Select label="Firma" value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
              <option value="">Seçiniz</option>
              {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          <Field
            label="Yıl"
            type="number"
            min="2020"
            max="2100"
            value={year}
            onChange={(e) => setYear(Number(e.target.value) || nowYear)}
          />
        </div>
        {message && (
          <p style={{
            marginTop: 12,
            color: /eklendi|ayarlandı/i.test(message) ? '#166534' : '#b91c1c',
          }}
          >
            {message}
          </p>
        )}
      </section>

      <div className="cards" style={{marginBottom: 16}}>
        <article className="metric"><span>Toplam Madde</span><strong>{summary?.total ?? '—'}</strong></article>
        <article className="metric"><span>Tamamlanan</span><strong style={{color: '#16a34a'}}>{summary?.completed ?? '—'}</strong></article>
        <article className="metric"><span>Bekleyen</span><strong>{summary?.waiting ?? '—'}</strong></article>
        <article className="metric"><span>Geciken</span><strong style={{color: '#b91c1c'}}>{summary?.delayed ?? '—'}</strong></article>
      </div>

      <section className="panel" style={{marginBottom: 16}}>
        <h3 style={{display: 'flex', alignItems: 'center', gap: 8, marginTop: 0}}>
          <ClipboardCheck size={18} /> Aylık Dağılım ({year})
        </h3>
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(6,1fr)', gap: 8}}>
          {Array.from({length: 12}, (_, i) => i + 1).map((m) => (
            <div
              key={m}
              style={{
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                padding: '10px 8px',
                textAlign: 'center',
                background: monthBars[m] ? '#f8fafc' : '#fff',
              }}
            >
              <div style={{fontSize: 12, color: '#64748b'}}>{MONTHS[m]}</div>
              <strong style={{fontSize: 18}}>{monthBars[m] || 0}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Ay</th>
                <th>Kategori</th>
                <th>Faaliyet</th>
                <th>Sorumlu</th>
                <th>Hedef</th>
                <th>Durum</th>
                {canEdit && <th>İşlem</th>}
              </tr>
            </thead>
            <tbody>
              {rows.length ? rows.map((r) => (
                <tr key={r.id}>
                  <td>{MONTHS[r.month] || r.month}</td>
                  <td>{catMap[r.category] || r.category || '—'}</td>
                  <td>
                    <div>{r.activity}</div>
                    {r.description && (
                      <div style={{fontSize: 12, color: '#64748b', marginTop: 2}}>{r.description}</div>
                    )}
                  </td>
                  <td>{r.responsible_name || '—'}</td>
                  <td>{r.target_date || '—'}</td>
                  <td>{statusBadge(r.status)}</td>
                  {canEdit && (
                    <td>
                      <div className="actions" style={{gap: 6}}>
                        <button type="button" className="mini" onClick={() => openEdit(r)}>Düzenle</button>
                        <button type="button" className="mini" onClick={() => remove(r)}>Sil</button>
                      </div>
                    </td>
                  )}
                </tr>
              )) : (
                <tr>
                  <td colSpan={canEdit ? 7 : 6} className="empty">
                    Bu yıl için plan maddesi yok. “Otomatik Plan Üret” ile 6331 şablonunu ekleyebilirsiniz.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {open && (
        <Modal title={editing ? 'Plan Maddesini Düzenle' : 'Yeni Plan Maddesi'} close={() => setOpen(false)}>
          <form className="form-grid" onSubmit={save}>
            {!editing && (
              <Select
                label="Firma"
                required
                value={form.company_id}
                onChange={(e) => setForm({...form, company_id: e.target.value})}
              >
                <option value="">Seçiniz</option>
                {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </Select>
            )}
            <Field label="Yıl" type="number" required min="2020" max="2100" value={form.year} onChange={(e) => setForm({...form, year: e.target.value})} />
            <Select label="Ay" required value={form.month} onChange={(e) => setForm({...form, month: e.target.value})}>
              {Array.from({length: 12}, (_, i) => i + 1).map((m) => (
                <option key={m} value={m}>{MONTHS[m]}</option>
              ))}
            </Select>
            <Select label="Kategori" value={form.category} onChange={(e) => setForm({...form, category: e.target.value})}>
              {Object.entries(catMap).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
            <Field label="Faaliyet" required value={form.activity} onChange={(e) => setForm({...form, activity: e.target.value})} />
            <TextArea label="Açıklama" value={form.description} onChange={(e) => setForm({...form, description: e.target.value})} />
            <Field label="Sorumlu" value={form.responsible_name} onChange={(e) => setForm({...form, responsible_name: e.target.value})} />
            <Field label="Hedef Tarih" type="date" value={form.target_date} onChange={(e) => setForm({...form, target_date: e.target.value})} />
            <Select label="Durum" value={form.status} onChange={(e) => setForm({...form, status: e.target.value})}>
              {statusOpts.map((s) => <option key={s.code} value={s.code}>{s.label}</option>)}
            </Select>
            <Field label="Tamamlanma" type="date" value={form.completion_date} onChange={(e) => setForm({...form, completion_date: e.target.value})} />
            <TextArea label="Notlar" value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})} />
            <div className="form-actions">
              <button type="submit" disabled={busy}>{editing ? 'Güncelle' : 'Kaydet'}</button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
