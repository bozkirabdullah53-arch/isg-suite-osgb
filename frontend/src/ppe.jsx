import React, {useEffect, useMemo, useState} from 'react';
import {Download, Plus, Printer, Search, Trash2, Upload, X} from 'lucide-react';
import {api, downloadFile, uploadFile} from './api';

function Modal({title, close, children, wide}) {
  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <section className="modal" style={{maxWidth: wide ? 1100 : 960}}>
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

function emptyForm(user) {
  return {
    company_id: user.company_id || '',
    branch_id: '',
    employee_id: '',
    delivery_date: new Date().toISOString().slice(0, 10),
    category: '',
    item_type: '',
    quantity: 1,
    brand: '',
    model: '',
    size: '',
    serial_no: '',
    shelf_life_text: '',
    expiry_date: '',
    warranty_text: '',
    renewal_date: '',
    status: 'teslim',
    delivered_by: user.full_name || '',
    risk_note: '',
    notes: '',
  };
}

export function PpePage({user}) {
  const canEdit = ['global_admin', 'company_admin', 'safety_specialist'].includes(user.role);
  const [companies, setCompanies] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [catalog, setCatalog] = useState({categories: [], statuses: []});
  const [rows, setRows] = useState([]);
  const [due, setDue] = useState(null);
  const [companyId, setCompanyId] = useState(user.company_id || '');
  const [q, setQ] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [open, setOpen] = useState(false);
  const [zimmet, setZimmet] = useState(null);
  const [form, setForm] = useState(() => emptyForm(user));
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const typesForCategory = useMemo(() => {
    const cat = catalog.categories.find((c) => c.name === form.category);
    return cat?.types || [];
  }, [catalog, form.category]);

  const companyEmployees = useMemo(
    () => employees.filter((e) => String(e.company_id) === String(form.company_id || companyId)),
    [employees, form.company_id, companyId],
  );

  const load = async () => {
    setErr('');
    const [c, e, cat] = await Promise.all([
      api('/companies'),
      api('/employees'),
      api('/ppe/catalog'),
    ]);
    setCompanies(c);
    setEmployees(e);
    setCatalog(cat);
    const cid = companyId || user.company_id || c[0]?.id;
    if (cid && !companyId) setCompanyId(String(cid));
    if (!cid) {
      setRows([]);
      setDue(null);
      if (user.role === 'global_admin') setErr('KKD listesi için firma seçiniz.');
      return;
    }
    const params = new URLSearchParams({company_id: String(cid)});
    if (q) params.set('q', q);
    if (statusFilter) params.set('status', statusFilter);
    const [list, summary] = await Promise.all([
      api(`/ppe/assignments?${params}`),
      api(`/ppe/due-summary?company_id=${cid}`),
    ]);
    setRows(list);
    setDue(summary);
  };

  useEffect(() => {
    load().catch((x) => setErr(x.message));
  }, [companyId, statusFilter]);

  async function save(e) {
    e.preventDefault();
    setErr('');
    setBusy(true);
    try {
      const payload = {
        ...form,
        company_id: Number(form.company_id || companyId),
        employee_id: Number(form.employee_id),
        branch_id: form.branch_id ? Number(form.branch_id) : null,
        quantity: Number(form.quantity) || 1,
        expiry_date: form.expiry_date || null,
        renewal_date: form.renewal_date || null,
        brand: form.brand || null,
        model: form.model || null,
        size: form.size || null,
        serial_no: form.serial_no || null,
        shelf_life_text: form.shelf_life_text || null,
        warranty_text: form.warranty_text || null,
        risk_note: form.risk_note || null,
        notes: form.notes || null,
      };
      await api('/ppe/assignments', {method: 'POST', body: JSON.stringify(payload)});
      setOpen(false);
      setForm(emptyForm(user));
      await load();
    } catch (x) {
      setErr(x.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id) {
    if (!window.confirm('Bu KKD zimmet kaydını silmek istiyor musunuz?')) return;
    await api(`/ppe/assignments/${id}`, {method: 'DELETE'});
    load();
  }

  async function onPhoto(id, file) {
    if (!file) return;
    setBusy(true);
    try {
      await uploadFile(`/ppe/assignments/${id}/photos`, file);
      await load();
      if (zimmet?.id === id) {
        const detail = await api(`/ppe/assignments/${id}`);
        setZimmet(detail);
      }
    } catch (x) {
      alert(x.message);
    } finally {
      setBusy(false);
    }
  }

  async function exportExcel() {
    const cid = companyId || user.company_id;
    if (!cid) return alert('Firma seçiniz.');
    await downloadFile(`/ppe/export.xlsx?company_id=${cid}`, `kkd-kayitlari-${cid}.xlsx`);
  }

  function openZimmet(row) {
    setZimmet(row);
  }

  function printZimmet() {
    window.print();
  }

  if (zimmet) {
    return (
      <>
        <div className="page-title no-print">
          <h3>KKD Zimmet Formu</h3>
          <div className="actions">
            <button type="button" className="secondary" onClick={printZimmet}><Printer size={16} /> Yazdır / PDF</button>
            <button type="button" className="secondary" onClick={() => setZimmet(null)}>Listeye dön</button>
          </div>
        </div>
        <section className="panel" id="ppe-zimmet-print">
          <h3 style={{marginTop: 0}}>KKD Zimmet ve Teslim Formu</h3>
          <div className="form-grid" style={{marginBottom: 16}}>
            <div className="field"><span>Kayıt No</span><strong>{zimmet.id}</strong></div>
            <div className="field"><span>Teslim Tarihi</span><strong>{zimmet.delivery_date}</strong></div>
            <div className="field"><span>Personel</span><strong>{zimmet.employee_name || zimmet.employee_id}</strong></div>
            <div className="field"><span>Bölüm / Görev</span><strong>{[zimmet.employee_department, zimmet.employee_job_title].filter(Boolean).join(' / ') || '—'}</strong></div>
            <div className="field"><span>Kategori</span><strong>{zimmet.category}</strong></div>
            <div className="field"><span>KKD Türü</span><strong>{zimmet.item_type}</strong></div>
            <div className="field"><span>Adet</span><strong>{zimmet.quantity}</strong></div>
            <div className="field"><span>Marka / Model / Beden</span><strong>{[zimmet.brand, zimmet.model, zimmet.size].filter(Boolean).join(' ') || '—'}</strong></div>
            <div className="field"><span>Seri No</span><strong>{zimmet.serial_no || '—'}</strong></div>
            <div className="field"><span>Yenileme</span><strong>{zimmet.renewal_date || '—'}</strong></div>
            <div className="field"><span>SKT</span><strong>{zimmet.expiry_date || '—'}</strong></div>
            <div className="field"><span>Durum</span><strong>{zimmet.status_label}</strong></div>
            <div className="field" style={{gridColumn: '1 / -1'}}><span>Risk / Kullanım Alanı</span><p>{zimmet.risk_note || '—'}</p></div>
            <div className="field" style={{gridColumn: '1 / -1'}}><span>Açıklama</span><p>{zimmet.notes || '—'}</p></div>
          </div>
          <p style={{fontSize: 13, lineHeight: 1.5}}>
            Yukarıda bilgileri yer alan kişisel koruyucu donanımı eksiksiz teslim aldım.
            Kullanım, bakım ve muhafaza kurallarına uygun hareket edeceğimi; kayıp, hasar veya
            yenileme ihtiyacını işverene / İSG birimine bildireceğimi kabul ederim.
          </p>
          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginTop: 28}}>
            {[
              ['Teslim Eden (İSG)', zimmet.delivered_by],
              ['Teslim Alan (Çalışan)', zimmet.employee_name],
              ['İşveren / Vekili', ''],
            ].map(([t, n]) => (
              <div key={t} style={{border: '1px solid #d0dbe3', borderRadius: 10, padding: 12, minHeight: 90}}>
                <strong style={{fontSize: 13}}>{t}</strong>
                <div style={{marginTop: 8}}>{n || ' '}</div>
                <div style={{marginTop: 28, borderTop: '1px solid #999', paddingTop: 6, fontSize: 12, color: '#666'}}>Kaşe / İmza</div>
              </div>
            ))}
          </div>
          {canEdit && (
            <div className="no-print" style={{marginTop: 16}}>
              <label className="button secondary" style={{display: 'inline-flex'}}>
                <Upload size={16} /> Fotoğraf ekle
                <input type="file" accept=".png,.jpg,.jpeg,.webp,.gif" hidden disabled={busy} onChange={(e) => onPhoto(zimmet.id, e.target.files?.[0])} />
              </label>
              <span style={{marginLeft: 10, fontSize: 13, color: '#64748b'}}>{zimmet.photos?.length || 0} fotoğraf</span>
            </div>
          )}
        </section>
      </>
    );
  }

  return (
    <>
      <div className="page-title">
        <h3>KKD Takip</h3>
        <div className="actions">
          <button className="secondary" type="button" onClick={() => exportExcel().catch((x) => alert(x.message))}>
            <Download size={16} /> Excel
          </button>
          {canEdit && (
            <button type="button" onClick={() => {
              setForm({...emptyForm(user), company_id: companyId || user.company_id || companies[0]?.id || ''});
              setErr('');
              setOpen(true);
            }}>
              <Plus /> Yeni Zimmet
            </button>
          )}
        </div>
      </div>
      <section className="panel">
        <div style={{marginBottom: 12, padding: '10px 12px', background: '#eef5fb', borderRadius: 10, fontSize: 14, lineHeight: 1.5}}>
          PRO uyumlu KKD zimmet: kategori → tür, yenileme / SKT takibi, zimmet formu ve Excel.
          {due && (
            <span> · Aktif {due.total_active} · yaklaşan {due.due_soon} · geciken {due.overdue}</span>
          )}
        </div>
        <div className="search" style={{marginBottom: 12, flexWrap: 'wrap'}}>
          <Search size={19} />
          <input placeholder="Tür, marka, seri ara..." value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && load()} />
          {!user.company_id && (
            <select value={companyId} onChange={(e) => setCompanyId(e.target.value)} style={{minWidth: 180}}>
              <option value="">Firma seçiniz</option>
              {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          )}
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{minWidth: 150}}>
            <option value="">Tüm durumlar</option>
            {(catalog.statuses || []).map((s) => <option key={s.code} value={s.code}>{s.label}</option>)}
          </select>
          <button className="secondary" type="button" onClick={() => load().catch((x) => setErr(x.message))}>Ara</button>
        </div>
        {err && <div className="error">{err}</div>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>No</th>
                <th>Teslim</th>
                <th>Personel</th>
                <th>KKD</th>
                <th>Adet</th>
                <th>Marka/Model</th>
                <th>Yenileme</th>
                <th>Durum</th>
                <th>İşlem</th>
              </tr>
            </thead>
            <tbody>
              {rows.length ? rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  <td>{r.delivery_date}</td>
                  <td>
                    <div>{r.employee_name || r.employee_id}</div>
                    <div style={{fontSize: 12, color: '#64748b'}}>{r.employee_department || ''}</div>
                  </td>
                  <td>
                    <div><strong>{r.item_type}</strong></div>
                    <div style={{fontSize: 12, color: '#64748b'}}>{r.category}</div>
                  </td>
                  <td>{r.quantity}</td>
                  <td>{[r.brand, r.model, r.size].filter(Boolean).join(' ') || '—'}</td>
                  <td>{r.renewal_date || '—'}</td>
                  <td><span className={'badge ' + (r.status === 'teslim' ? 'ok' : 'off')}>{r.status_label}</span></td>
                  <td>
                    <button className="mini" type="button" onClick={() => openZimmet(r)}>Zimmet</button>
                    {canEdit && (
                      <button className="mini" type="button" style={{marginLeft: 6}} onClick={() => remove(r.id)}><Trash2 size={12} /></button>
                    )}
                  </td>
                </tr>
              )) : (
                <tr><td colSpan={9} className="empty">KKD kaydı yok. Yeni zimmet ekleyin.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {open && (
        <Modal title="Yeni KKD Zimmet Kaydı" close={() => setOpen(false)} wide>
          <form className="form-grid" onSubmit={save}>
            <Select label="Firma" required value={form.company_id} onChange={(e) => setForm({...form, company_id: e.target.value, employee_id: ''})}>
              <option value="">Seçiniz</option>
              {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
            <Select label="Personel" required value={form.employee_id} onChange={(e) => setForm({...form, employee_id: e.target.value})}>
              <option value="">Seçiniz</option>
              {companyEmployees.map((e) => <option key={e.id} value={e.id}>{e.full_name}</option>)}
            </Select>
            <Field label="Teslim Tarihi" type="date" required value={form.delivery_date} onChange={(e) => setForm({...form, delivery_date: e.target.value})} />
            <Field label="Adet" type="number" min="1" required value={form.quantity} onChange={(e) => setForm({...form, quantity: e.target.value})} />
            <Select label="KKD Kategorisi" required value={form.category} onChange={(e) => setForm({...form, category: e.target.value, item_type: ''})}>
              <option value="">Seçiniz</option>
              {(catalog.categories || []).map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
            </Select>
            <Select label="KKD Türü" required value={form.item_type} onChange={(e) => setForm({...form, item_type: e.target.value})}>
              <option value="">Önce kategori seçin</option>
              {typesForCategory.map((t) => <option key={t} value={t}>{t}</option>)}
            </Select>
            <Field label="Marka" value={form.brand} onChange={(e) => setForm({...form, brand: e.target.value})} />
            <Field label="Model" value={form.model} onChange={(e) => setForm({...form, model: e.target.value})} />
            <Field label="Beden" value={form.size} onChange={(e) => setForm({...form, size: e.target.value})} />
            <Field label="Seri No" value={form.serial_no} onChange={(e) => setForm({...form, serial_no: e.target.value})} />
            <Field label="Raf Ömrü" value={form.shelf_life_text} onChange={(e) => setForm({...form, shelf_life_text: e.target.value})} />
            <Field label="Garanti" value={form.warranty_text} onChange={(e) => setForm({...form, warranty_text: e.target.value})} />
            <Field label="Son Kullanma" type="date" value={form.expiry_date} onChange={(e) => setForm({...form, expiry_date: e.target.value})} />
            <Field label="Yenileme / Kontrol" type="date" value={form.renewal_date} onChange={(e) => setForm({...form, renewal_date: e.target.value})} />
            <Select label="Durum" value={form.status} onChange={(e) => setForm({...form, status: e.target.value})}>
              {(catalog.statuses || []).map((s) => <option key={s.code} value={s.code}>{s.label}</option>)}
            </Select>
            <Field label="Teslim Eden" value={form.delivered_by} onChange={(e) => setForm({...form, delivered_by: e.target.value})} />
            <TextArea label="Risk / Kullanım Alanı" value={form.risk_note} onChange={(e) => setForm({...form, risk_note: e.target.value})} />
            <TextArea label="Açıklama" value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})} />
            {err && <div className="error" style={{gridColumn: '1 / -1'}}>{err}</div>}
            <div className="form-actions" style={{gridColumn: '1 / -1'}}>
              <button type="submit" disabled={busy}>{busy ? 'Kaydediliyor…' : 'Kaydet'}</button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
