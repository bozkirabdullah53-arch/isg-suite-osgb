import React, {useEffect, useMemo, useState} from 'react';
import {AlertTriangle, CheckCircle2, FilePenLine, Pill, Plus, RefreshCw, Send, Trash2, XCircle} from 'lucide-react';
import {api} from './api';
import {AppModal} from './ui_modal';

const STATUS = {
  draft: ['Taslak', '#64748b'],
  ready: ['Hazır', '#2563eb'],
  sending: ['Gönderiliyor', '#d97706'],
  approved: ['Onaylandı', '#16a34a'],
  rejected: ['Reddedildi', '#b91c1c'],
  cancelled: ['İptal', '#7f1d1d'],
};

function emptyItem() {
  return {
    medication_name: '',
    medication_code: '',
    dose: '',
    frequency: '',
    route: '',
    duration: '',
    quantity: 1,
    usage_instruction: '',
    sort_order: 0,
  };
}

function emptyForm(user, companyId = '') {
  return {
    company_id: companyId || user.company_id || '',
    employee_id: '',
    health_record_id: '',
    prescription_date: new Date().toISOString().slice(0, 10),
    diagnosis_code: '',
    diagnosis_text: '',
    clinical_note: '',
    items: [emptyItem()],
  };
}

function Badge({status}) {
  const [label, color] = STATUS[status] || [status || '—', '#64748b'];
  return <span className="badge" style={{background: `${color}18`, color}}>{label}</span>;
}

function Field({label, children}) {
  return <label className="field"><span>{label}</span>{children}</label>;
}

export function PrescriptionPage({user}) {
  const isPhysician = user.role === 'workplace_physician';
  const canRead = isPhysician || user.role === 'global_admin';

  const [companies, setCompanies] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [records, setRecords] = useState([]);
  const [rows, setRows] = useState([]);
  const [companyId, setCompanyId] = useState(user.company_id ? String(user.company_id) : '');
  const [statusFilter, setStatusFilter] = useState('');
  const [q, setQ] = useState('');
  const [form, setForm] = useState(() => emptyForm(user));
  const [editing, setEditing] = useState(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function load() {
    if (!canRead) return;
    setMessage('');
    try {
      const c = await api('/companies');
      const nextCompany = companyId || String(user.company_id || c?.[0]?.id || '');
      setCompanies(Array.isArray(c) ? c : []);
      if (!nextCompany) {
        setRows([]);
        setEmployees([]);
        setRecords([]);
        setMessage('Önce bir işyeri seçiniz.');
        return;
      }
      if (!companyId) setCompanyId(nextCompany);

      const [e, h, p] = await Promise.all([
        api(`/employees?active=true&company_id=${encodeURIComponent(nextCompany)}`),
        api(`/health-records?company_id=${encodeURIComponent(nextCompany)}`),
        api(`/prescriptions?company_id=${encodeURIComponent(nextCompany)}${statusFilter ? `&status=${encodeURIComponent(statusFilter)}` : ''}`),
      ]);
      setEmployees(Array.isArray(e) ? e : []);
      setRecords(Array.isArray(h) ? h : []);
      setRows(Array.isArray(p) ? p : []);
    } catch (err) {
      setMessage(err.message || 'e-Reçete verileri yüklenemedi.');
    }
  }

  useEffect(() => { load(); }, [companyId, statusFilter]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLocaleLowerCase('tr');
    if (!needle) return rows;
    return rows.filter((r) => `${r.employee_name || ''} ${r.diagnosis_text || ''} ${r.diagnosis_code || ''}`
      .toLocaleLowerCase('tr').includes(needle));
  }, [rows, q]);

  function openCreate() {
    const base = emptyForm(user, companyId);
    setEditing(null);
    setForm(base);
    setOpen(true);
  }

  function openEdit(row) {
    setEditing(row);
    setForm({
      company_id: row.company_id,
      employee_id: row.employee_id,
      health_record_id: row.health_record_id || '',
      prescription_date: row.prescription_date,
      diagnosis_code: row.diagnosis_code || '',
      diagnosis_text: row.diagnosis_text || '',
      clinical_note: row.clinical_note || '',
      items: (row.items || []).map((x, i) => ({
        medication_name: x.medication_name || '',
        medication_code: x.medication_code || '',
        dose: x.dose || '',
        frequency: x.frequency || '',
        route: x.route || '',
        duration: x.duration || '',
        quantity: x.quantity || 1,
        usage_instruction: x.usage_instruction || '',
        sort_order: i,
      })),
    });
    setOpen(true);
  }

  function updateItem(index, key, value) {
    setForm((f) => ({
      ...f,
      items: f.items.map((item, i) => i === index ? {...item, [key]: value} : item),
    }));
  }

  function addItem() {
    setForm((f) => ({...f, items: [...f.items, {...emptyItem(), sort_order: f.items.length}]}));
  }

  function removeItem(index) {
    setForm((f) => ({...f, items: f.items.filter((_, i) => i !== index).map((x, i) => ({...x, sort_order: i}))}));
  }

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setMessage('');
    try {
      const payload = {
        ...form,
        company_id: Number(form.company_id),
        employee_id: Number(form.employee_id),
        health_record_id: form.health_record_id ? Number(form.health_record_id) : null,
        items: form.items.map((x, i) => ({
          ...x,
          quantity: Number(x.quantity || 1),
          sort_order: i,
          medication_code: x.medication_code || null,
          route: x.route || null,
          duration: x.duration || null,
          usage_instruction: x.usage_instruction || null,
        })),
      };
      if (editing) {
        await api(`/prescriptions/${editing.id}`, {method: 'PATCH', body: JSON.stringify(payload)});
      } else {
        await api('/prescriptions', {method: 'POST', body: JSON.stringify(payload)});
      }
      setOpen(false);
      await load();
      setMessage('Reçete taslağı kaydedildi.');
    } catch (err) {
      setMessage(err.message || 'Reçete kaydedilemedi.');
    } finally {
      setBusy(false);
    }
  }

  async function markReady(row) {
    if (!window.confirm('Reçete gönderime hazır olarak kilitlensin mi?')) return;
    setBusy(true);
    try {
      await api(`/prescriptions/${row.id}/ready`, {method: 'POST'});
      await load();
      setMessage('Reçete gönderime hazırlandı.');
    } catch (err) {
      setMessage(err.message || 'İşlem tamamlanamadı.');
    } finally {
      setBusy(false);
    }
  }

  async function cancel(row) {
    const reason = window.prompt('İptal nedenini yazınız:');
    if (!reason) return;
    setBusy(true);
    try {
      await api(`/prescriptions/${row.id}/cancel`, {method: 'POST', body: JSON.stringify({reason})});
      await load();
      setMessage('Reçete iptal edildi.');
    } catch (err) {
      setMessage(err.message || 'İptal işlemi tamamlanamadı.');
    } finally {
      setBusy(false);
    }
  }

  async function submitMedula(row) {
    setBusy(true);
    try {
      await api(`/prescriptions/${row.id}/submit`, {method: 'POST'});
    } catch (err) {
      setMessage(err.message || 'MEDULA bağlantısı henüz yapılandırılmadı.');
    } finally {
      setBusy(false);
    }
  }

  if (!canRead) {
    return <section className="panel"><h2>e-Reçete</h2><p>Bu modüle erişim yetkiniz bulunmuyor.</p></section>;
  }

  const selectedEmployee = employees.find((e) => String(e.id) === String(form.employee_id));
  const matchingRecords = records.filter((r) => String(r.employee_id) === String(form.employee_id));

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 style={{display: 'flex', alignItems: 'center', gap: 10}}><Pill size={28}/> e-Reçete</h1>
          <p className="muted">İşyeri hekimi reçete taslağı, ilaç kalemleri ve MEDULA hazırlık takibi.</p>
        </div>
        {isPhysician && <button className="primary" onClick={openCreate}><Plus size={17}/> Yeni Reçete</button>}
      </div>

      <section className="panel" style={{borderLeft: '4px solid #d97706'}}>
        <div style={{display: 'flex', gap: 10, alignItems: 'flex-start'}}>
          <AlertTriangle size={22}/>
          <div>
            <strong>MEDULA bağlantısı henüz yapılandırılmadı.</strong>
            <div className="muted" style={{marginTop: 4}}>Reçeteler güvenle kaydedilir; SGK'ya gerçek gönderim yapılmaz.</div>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="toolbar" style={{display: 'flex', gap: 10, flexWrap: 'wrap'}}>
          <select value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
            <option value="">İşyeri seçiniz</option>
            {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">Tüm durumlar</option>
            {Object.entries(STATUS).map(([code, x]) => <option key={code} value={code}>{x[0]}</option>)}
          </select>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Çalışan, tanı veya kod ara"/>
          <button onClick={load}><RefreshCw size={16}/> Yenile</button>
        </div>
      </section>

      {message && <div className="notice" style={{marginBottom: 12}}>{message}</div>}

      <section className="panel">
        <div className="table-wrap">
          <table>
            <thead><tr>
              <th>Tarih</th><th>Çalışan</th><th>Tanı</th><th>İlaç</th><th>Durum</th><th>Hekim</th><th>İşlemler</th>
            </tr></thead>
            <tbody>
              {filtered.length ? filtered.map((r) => (
                <tr key={r.id}>
                  <td>{r.prescription_date}</td>
                  <td><strong>{r.employee_name || '—'}</strong></td>
                  <td>{r.diagnosis_code ? `${r.diagnosis_code} · ` : ''}{r.diagnosis_text || '—'}</td>
                  <td>{r.items?.length || 0} kalem</td>
                  <td><Badge status={r.status}/></td>
                  <td>{r.physician_name || '—'}</td>
                  <td>
                    <div style={{display: 'flex', gap: 6, flexWrap: 'wrap'}}>
                      {isPhysician && r.status === 'draft' && <button onClick={() => openEdit(r)}><FilePenLine size={15}/> Düzenle</button>}
                      {isPhysician && r.status === 'draft' && <button onClick={() => markReady(r)}><CheckCircle2 size={15}/> Hazırla</button>}
                      {isPhysician && ['draft','ready','rejected'].includes(r.status) && <button onClick={() => cancel(r)}><XCircle size={15}/> İptal</button>}
                      {isPhysician && r.status === 'ready' && <button className="primary" onClick={() => submitMedula(r)}><Send size={15}/> MEDULA'ya Gönder</button>}
                    </div>
                  </td>
                </tr>
              )) : <tr><td colSpan={7} className="empty">Reçete kaydı bulunamadı.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      {open && (
        <AppModal title={editing ? 'Reçete Taslağını Düzenle' : 'Yeni Reçete Taslağı'} close={() => setOpen(false)} wide>
          <form onSubmit={save}>
            <div className="form-grid">
              <Field label="İşyeri">
                <select required value={form.company_id} onChange={(e) => setForm({...form, company_id: e.target.value, employee_id: '', health_record_id: ''})}>
                  <option value="">Seçiniz</option>
                  {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </Field>
              <Field label="Çalışan">
                <select required value={form.employee_id} onChange={(e) => setForm({...form, employee_id: e.target.value, health_record_id: ''})}>
                  <option value="">Seçiniz</option>
                  {employees.filter((e) => String(e.company_id) === String(form.company_id)).map((e) => <option key={e.id} value={e.id}>{e.full_name}</option>)}
                </select>
              </Field>
              <Field label="Reçete tarihi">
                <input type="date" required value={form.prescription_date} onChange={(e) => setForm({...form, prescription_date: e.target.value})}/>
              </Field>
              <Field label="Muayene kaydı">
                <select value={form.health_record_id} onChange={(e) => setForm({...form, health_record_id: e.target.value})}>
                  <option value="">Bağlantısız</option>
                  {matchingRecords.map((r) => <option key={r.id} value={r.id}>{r.examination_date} · {r.record_type}</option>)}
                </select>
              </Field>
              <Field label="Tanı kodu">
                <input value={form.diagnosis_code} onChange={(e) => setForm({...form, diagnosis_code: e.target.value})} maxLength={32} placeholder="Örn. ICD kodu"/>
              </Field>
              <Field label="Tanı açıklaması">
                <input value={form.diagnosis_text} onChange={(e) => setForm({...form, diagnosis_text: e.target.value})} maxLength={1000} placeholder="Tanı kodu yoksa zorunlu"/>
              </Field>
            </div>

            <Field label="Klinik not">
              <textarea rows={3} value={form.clinical_note} onChange={(e) => setForm({...form, clinical_note: e.target.value})} maxLength={2000}/>
            </Field>

            <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 18}}>
              <h3 style={{margin: 0}}>İlaç Kalemleri</h3>
              <button type="button" onClick={addItem}><Plus size={15}/> İlaç Ekle</button>
            </div>

            {form.items.map((item, index) => (
              <section key={index} className="panel" style={{marginTop: 10, background: 'var(--surface-subtle, #f8fafc)'}}>
                <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                  <strong>{index + 1}. ilaç</strong>
                  {form.items.length > 1 && <button type="button" onClick={() => removeItem(index)}><Trash2 size={15}/> Sil</button>}
                </div>
                <div className="form-grid" style={{marginTop: 10}}>
                  <Field label="İlaç adı"><input required value={item.medication_name} onChange={(e) => updateItem(index, 'medication_name', e.target.value)}/></Field>
                  <Field label="İlaç kodu"><input value={item.medication_code} onChange={(e) => updateItem(index, 'medication_code', e.target.value)}/></Field>
                  <Field label="Doz"><input required value={item.dose} onChange={(e) => updateItem(index, 'dose', e.target.value)} placeholder="Örn. 500 mg"/></Field>
                  <Field label="Sıklık"><input required value={item.frequency} onChange={(e) => updateItem(index, 'frequency', e.target.value)} placeholder="Örn. günde 2 kez"/></Field>
                  <Field label="Uygulama yolu"><input value={item.route} onChange={(e) => updateItem(index, 'route', e.target.value)} placeholder="Oral, topikal..."/></Field>
                  <Field label="Süre"><input value={item.duration} onChange={(e) => updateItem(index, 'duration', e.target.value)} placeholder="Örn. 7 gün"/></Field>
                  <Field label="Kutu/adet"><input type="number" min="1" max="99" required value={item.quantity} onChange={(e) => updateItem(index, 'quantity', e.target.value)}/></Field>
                  <Field label="Kullanım talimatı"><input value={item.usage_instruction} onChange={(e) => updateItem(index, 'usage_instruction', e.target.value)}/></Field>
                </div>
              </section>
            ))}

            <div className="modal-actions">
              <button type="button" onClick={() => setOpen(false)}>Vazgeç</button>
              <button className="primary" disabled={busy} type="submit">{busy ? 'Kaydediliyor…' : 'Taslağı Kaydet'}</button>
            </div>
          </form>
        </AppModal>
      )}
    </div>
  );
}
