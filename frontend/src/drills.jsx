import React, {useEffect, useMemo, useState} from 'react';
import {Activity, Download, Plus, RefreshCw, Upload} from 'lucide-react';
import {api, downloadFile, uploadFile} from './api';

const STATUS_LABEL = {
  planlandi: 'Planlandı',
  yapildi: 'Yapıldı',
  eksik: 'Eksik Var',
  iptal: 'İptal',
};

function statusBadge(status) {
  if (status === 'yapildi') return <span className="status-badge badge-ok">Yapıldı</span>;
  if (status === 'eksik') return <span className="status-badge badge-warn">Eksik Var</span>;
  if (status === 'iptal') return <span className="status-badge badge-muted">İptal</span>;
  return <span className="status-badge badge-warn">Planlandı</span>;
}

const empty = {
  company_id: '',
  drill_type: 'Yangın',
  drill_date: '',
  start_time: '',
  end_time: '',
  responsible: '',
  participant_count: '',
  assembly_area: '',
  status: 'planlandi',
  scenario: '',
  gaps: '',
  result: '',
  employee_ids: [],
};

export function DrillsPage({user}) {
  const canEdit = user.role === 'safety_specialist' || user.role === 'global_admin';
  const [companies, setCompanies] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({types: [], statuses: []});
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({...empty, company_id: user.company_id || ''});
  const [photoFiles, setPhotoFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');

  const companyEmployees = useMemo(
    () => employees.filter((e) => String(e.company_id) === String(form.company_id)),
    [employees, form.company_id],
  );

  async function load(nextQ = q) {
    setBusy(true);
    setErr('');
    try {
      const qs = nextQ.trim() ? `?q=${encodeURIComponent(nextQ.trim())}` : '';
      const [c, e, r, m] = await Promise.all([
        api('/companies'),
        api('/employees'),
        api(`/drills${qs}`),
        api('/drills/meta'),
      ]);
      setCompanies(c);
      setEmployees(e);
      setRows(r);
      setMeta(m || {types: [], statuses: []});
    } catch (ex) {
      setErr(ex.message || 'Tatbikatlar yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function toggleEmployee(id) {
    setForm((f) => {
      const has = f.employee_ids.includes(id);
      return {
        ...f,
        employee_ids: has ? f.employee_ids.filter((x) => x !== id) : [...f.employee_ids, id],
      };
    });
  }

  async function save(e) {
    e.preventDefault();
    setErr('');
    setBusy(true);
    try {
      const created = await api('/drills', {
        method: 'POST',
        body: JSON.stringify({
          company_id: Number(form.company_id),
          drill_type: form.drill_type,
          drill_date: form.drill_date,
          start_time: form.start_time || null,
          end_time: form.end_time || null,
          responsible: form.responsible || null,
          participant_count: form.participant_count === '' ? null : Number(form.participant_count),
          assembly_area: form.assembly_area || null,
          status: form.status,
          scenario: form.scenario,
          gaps: form.gaps || null,
          result: form.result || null,
          employee_ids: form.employee_ids,
        }),
      });
      for (const file of photoFiles) {
        await uploadFile(`/drills/${created.id}/photos`, file);
      }
      setOpen(false);
      setPhotoFiles([]);
      setForm({...empty, company_id: form.company_id || user.company_id || ''});
      setMsg('Tatbikat kaydedildi.');
      await load();
    } catch (ex) {
      setErr(ex.message || 'Kayıt başarısız.');
    } finally {
      setBusy(false);
    }
  }

  async function remove(row) {
    if (!window.confirm(`“${row.drill_type} / ${row.drill_date}” kaydı silinsin mi?`)) return;
    setBusy(true);
    try {
      await api(`/drills/${row.id}`, {method: 'DELETE'});
      setMsg('Kayıt silindi.');
      await load();
    } catch (ex) {
      setErr(ex.message || 'Silinemedi.');
    } finally {
      setBusy(false);
    }
  }

  async function exportTxt(row) {
    try {
      await downloadFile(`/drills/${row.id}/export.txt`, `tatbikat-tutanagi-${row.id}.txt`);
    } catch (ex) {
      setErr(ex.message || 'Dışa aktarım başarısız.');
    }
  }

  const companyName = (id) => companies.find((c) => c.id === id)?.name || id;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2>
            <Activity size={22} style={{marginRight: 8, verticalAlign: 'middle'}} />
            Tatbikat Yönetimi
          </h2>
          <p className="muted">Yangın, deprem, tahliye ve diğer acil durum tatbikat kayıtları.</p>
        </div>
        <div className="actions">
          {canEdit && (
            <button type="button" onClick={() => setOpen(true)} disabled={busy}>
              <Plus size={16} /> Yeni Tatbikat
            </button>
          )}
          <button type="button" className="secondary" onClick={() => load()} disabled={busy}>
            <RefreshCw size={16} /> Yenile
          </button>
        </div>
      </div>

      {err && <div className="banner danger">{err}</div>}
      {msg && <div className="banner ok">{msg}</div>}

      <div className="toolbar" style={{marginBottom: 12}}>
        <input
          placeholder="Ara: tür, sorumlu, senaryo…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && load(q)}
        />
        <button type="button" className="secondary mini" onClick={() => load(q)} disabled={busy}>Ara</button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Tür</th>
              <th>İşyeri</th>
              <th>Tarih</th>
              <th>Saat</th>
              <th>Sorumlu</th>
              <th>Katılımcı</th>
              <th>Foto</th>
              <th>Durum</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={9} className="muted">Henüz tatbikat kaydı yok.</td></tr>
            )}
            {rows.map((r) => (
              <tr key={r.id}>
                <td><strong>{r.drill_type}</strong></td>
                <td>{companyName(r.company_id)}</td>
                <td>{r.drill_date}</td>
                <td>{(r.start_time || r.end_time) ? `${r.start_time || '?'}–${r.end_time || '?'}` : '—'}</td>
                <td>{r.responsible || '—'}</td>
                <td>
                  {r.participant_count}
                  {r.participants?.length ? (
                    <div className="muted" style={{fontSize: 11}}>
                      {r.participants.slice(0, 3).map((p) => p.full_name).join(', ')}
                      {r.participants.length > 3 ? '…' : ''}
                    </div>
                  ) : null}
                </td>
                <td>{r.photos?.length || 0}</td>
                <td>{statusBadge(r.status)}</td>
                <td>
                  <div className="actions">
                    <button type="button" className="secondary mini" onClick={() => exportTxt(r)}>
                      <Download size={14} /> Tutanak
                    </button>
                    {canEdit && (
                      <button type="button" className="secondary mini" disabled={busy} onClick={() => remove(r)}>
                        Sil
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {open && (
        <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && setOpen(false)}>
          <section className="modal" style={{maxWidth: 760}}>
            <header><h3>Yeni Tatbikat</h3></header>
            <form className="form-grid" onSubmit={save}>
              <label className="field"><span>İşyeri</span>
                <select required value={form.company_id} onChange={(e) => setForm({...form, company_id: e.target.value, employee_ids: []})}>
                  <option value="">Seçin</option>
                  {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </label>
              <label className="field"><span>Tatbikat türü</span>
                <select required value={form.drill_type} onChange={(e) => setForm({...form, drill_type: e.target.value})}>
                  {(meta.types || []).map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </label>
              <label className="field"><span>Tarih</span>
                <input required type="date" value={form.drill_date} onChange={(e) => setForm({...form, drill_date: e.target.value})} />
              </label>
              <label className="field"><span>Durum</span>
                <select value={form.status} onChange={(e) => setForm({...form, status: e.target.value})}>
                  {(meta.statuses || Object.keys(STATUS_LABEL)).map((s) => (
                    <option key={s} value={s}>{STATUS_LABEL[s] || s}</option>
                  ))}
                </select>
              </label>
              <label className="field"><span>Başlangıç</span>
                <input type="time" value={form.start_time} onChange={(e) => setForm({...form, start_time: e.target.value})} />
              </label>
              <label className="field"><span>Bitiş</span>
                <input type="time" value={form.end_time} onChange={(e) => setForm({...form, end_time: e.target.value})} />
              </label>
              <label className="field"><span>Sorumlu</span>
                <input value={form.responsible} onChange={(e) => setForm({...form, responsible: e.target.value})} />
              </label>
              <label className="field"><span>Katılımcı sayısı</span>
                <input type="number" min="0" placeholder="Boş = seçilen personel" value={form.participant_count}
                  onChange={(e) => setForm({...form, participant_count: e.target.value})} />
              </label>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Toplanma alanı</span>
                <input value={form.assembly_area} onChange={(e) => setForm({...form, assembly_area: e.target.value})} />
              </label>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Senaryo</span>
                <textarea required rows={3} value={form.scenario} onChange={(e) => setForm({...form, scenario: e.target.value})} />
              </label>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Eksikler</span>
                <textarea rows={2} value={form.gaps} onChange={(e) => setForm({...form, gaps: e.target.value})} />
              </label>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Sonuç</span>
                <textarea rows={2} value={form.result} onChange={(e) => setForm({...form, result: e.target.value})} />
              </label>
              <div style={{gridColumn: '1 / -1'}}>
                <div style={{fontSize: 13, fontWeight: 600, marginBottom: 6}}>Katılımcı personel</div>
                <div style={{maxHeight: 140, overflow: 'auto', border: '1px solid #e2e8f0', borderRadius: 8, padding: 8}}>
                  {companyEmployees.length === 0 && <div className="muted">Bu işyerinde personel yok veya seçilmedi.</div>}
                  {companyEmployees.map((emp) => (
                    <label key={emp.id} style={{display: 'flex', gap: 8, alignItems: 'center', fontSize: 13, marginBottom: 4}}>
                      <input
                        type="checkbox"
                        checked={form.employee_ids.includes(emp.id)}
                        onChange={() => toggleEmployee(emp.id)}
                      />
                      {emp.full_name}
                      {emp.job_title ? ` · ${emp.job_title}` : ''}
                    </label>
                  ))}
                </div>
              </div>
              <label className="field" style={{gridColumn: '1 / -1'}}><span>Fotoğraflar</span>
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={(e) => setPhotoFiles(Array.from(e.target.files || []))}
                />
                {photoFiles.length > 0 && (
                  <span className="muted" style={{fontSize: 12}}>
                    <Upload size={12} /> {photoFiles.length} dosya seçildi
                  </span>
                )}
              </label>
              <div className="form-actions">
                <button type="button" className="secondary" onClick={() => setOpen(false)}>İptal</button>
                <button type="submit" disabled={busy}>Kaydet</button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
