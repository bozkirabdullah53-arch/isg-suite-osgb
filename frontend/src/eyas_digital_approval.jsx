import React, {useEffect, useState} from 'react';
import {CheckCircle2, Plus, RefreshCw, ShieldAlert, Inbox, Download} from 'lucide-react';
import {api} from './api';
import {AppModal} from './ui_modal';

/**
 * Eyas Digital Approval — işyeri bazlı belge + sıralı onay.
 * Sıra: İş Güvenliği → Hekim → İşveren/vekil. QES değildir.
 */
export function EyasDigitalApprovalPage({user, mode = 'full', autoOpenCreate = false, onAutoOpenHandled}) {
  const canCreate = ['global_admin', 'safety_specialist'].includes(user.role);
  const [meta, setMeta] = useState(null);
  const [rows, setRows] = useState([]);
  const [inbox, setInbox] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [docs, setDocs] = useState([]);
  const [assignees, setAssignees] = useState(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    company_id: user.company_id || '',
    source_key: '',
  });

  async function load() {
    setBusy(true);
    setErr('');
    try {
      const m = await api('/eyas/meta');
      setMeta(m);
      if (!m.enabled) {
        setRows([]);
        setInbox([]);
        return;
      }
      const [wf, ib, cos] = await Promise.all([
        api('/eyas/workflows'),
        api('/eyas/inbox'),
        api('/companies'),
      ]);
      setRows(wf);
      setInbox(ib);
      setCompanies(cos);
    } catch (e) {
      setErr(e.message || 'Eyas yüklenemedi');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(); }, []);

  useEffect(() => {
    if (!autoOpenCreate || !canCreate) return;
    let cancelled = false;
    void (async () => {
      try {
        if (!companies.length) {
          const cos = await api('/companies');
          if (cancelled) return;
          setCompanies(cos);
          const cid = form.company_id || (cos[0] && cos[0].id) || '';
          setOpen(true);
          if (cid) await onWorkplaceChange(String(cid));
        } else {
          await openCreate();
        }
      } catch (e) {
        if (!cancelled) setErr(e.message || 'Akış açılamadı');
      } finally {
        if (!cancelled && typeof onAutoOpenHandled === 'function') onAutoOpenHandled();
      }
    })();
    return () => { cancelled = true; };
  }, [autoOpenCreate]);

  async function onWorkplaceChange(companyId) {
    setForm({company_id: companyId, source_key: ''});
    setDocs([]);
    setAssignees(null);
    if (!companyId) return;
    setBusy(true);
    setErr('');
    try {
      const [d, a] = await Promise.all([
        api(`/eyas/workplaces/${companyId}/documents`),
        api(`/eyas/workplaces/${companyId}/assignees`),
      ]);
      setDocs(d.items || []);
      setAssignees(a);
    } catch (e) {
      setErr(e.message || 'İşyeri bilgisi alınamadı');
    } finally {
      setBusy(false);
    }
  }

  async function openCreate() {
    setOpen(true);
    const cid = form.company_id || (companies[0] && companies[0].id) || '';
    if (cid) await onWorkplaceChange(String(cid));
  }

  async function create(e) {
    e.preventDefault();
    if (!form.company_id || !form.source_key) {
      setErr('İşyeri ve belge seçilmelidir.');
      return;
    }
    const selected = docs.find((d) => d.source_key === form.source_key);
    if (selected && !selected.selectable) {
      setErr(selected.readiness_detail || 'Rapor hazır değil.');
      return;
    }
    setBusy(true);
    setErr('');
    try {
      await api('/eyas/workflows', {
        method: 'POST',
        body: JSON.stringify({
          company_id: Number(form.company_id),
          source_key: form.source_key,
          auto_assignees: true,
        }),
      });
      setOpen(false);
      await load();
    } catch (x) {
      setErr(x.message);
    } finally {
      setBusy(false);
    }
  }

  async function decide(wfId, approve) {
    const note = window.prompt(approve ? 'Onay notu (isteğe bağlı):' : 'Red nedeni:') || '';
    if (!approve && !note.trim()) {
      setErr('Red için not gerekli.');
      return;
    }
    setBusy(true);
    setErr('');
    try {
      await api(`/eyas/workflows/${wfId}/${approve ? 'approve' : 'reject'}`, {
        method: 'POST',
        body: JSON.stringify({
          note: note || null,
          device_note: typeof navigator !== 'undefined' ? navigator.userAgent.slice(0, 200) : null,
        }),
      });
      await load();
    } catch (x) {
      setErr(x.message);
    } finally {
      setBusy(false);
    }
  }

  async function downloadDoc(wf) {
    if (!wf?.source_key) {
      setErr('Bu akışa bağlı belge yok.');
      return;
    }
    setBusy(true);
    setErr('');
    try {
      const d = await api(`/eyas/workplaces/${wf.company_id}/documents`);
      const item = (d.items || []).find((i) => i.source_key === wf.source_key);
      if (!item) {
        setErr('Kaynak belge bulunamadı.');
        return;
      }
      if (item.readiness === 'missing') {
        setErr(item.readiness_detail || 'Rapor hazır değil.');
        return;
      }
      if (!item.download_path) {
        setErr('Bu belge için indirme yolu yok.');
        return;
      }
      const token = localStorage.getItem('isg_token');
      const isLocal =
        window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
      const apiBase = isLocal
        ? `${window.location.protocol}//${window.location.hostname}:8000/api/v1`
        : `${window.location.origin}/api/v1`;
      const rel = item.download_path.replace(/^\/api\/v1/, '');
      const res = await fetch(`${apiBase}${rel}`, {
        headers: token ? {Authorization: `Bearer ${token}`} : {},
        credentials: 'include',
      });
      if (!res.ok) {
        throw new Error(item.readiness_detail || `İndirme başarısız (${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${(wf.title || 'belge').slice(0, 60)}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (x) {
      setErr(x.message || 'Belge indirilemedi');
    } finally {
      setBusy(false);
    }
  }

  async function remove(wf) {
    const title = wf.title || `#${wf.id}`;
    if (!window.confirm(`“${title}” onay akışı silinsin mi?`)) return;
    setBusy(true);
    setErr('');
    try {
      await api(`/eyas/workflows/${wf.id}`, {method: 'DELETE'});
      await load();
    } catch (x) {
      setErr(x.message || 'Silinemedi');
    } finally {
      setBusy(false);
    }
  }

  if (meta && meta.enabled === false) {
    return (
      <section className="panel">
        <p style={{margin: 0, color: '#64748b'}}>
          Eyas Digital Approval şu an kapalı (yönetici bayrağı). Mevcut Belge Onay / e-imza sekmeleri etkilenmez.
        </p>
      </section>
    );
  }

  const readyDocs = docs.filter((d) => d.selectable);
  const blockedDocs = docs.filter((d) => !d.selectable);

  function renderTable(list, emptyMsg) {
    return (
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Belge</th><th>Durum</th><th>Sıra</th><th>Adımlar</th><th></th>
            </tr>
          </thead>
          <tbody>
            {list.length ? list.map((w) => {
              const active = (w.steps || []).find((s) => s.status === 'active');
              const mine = active && active.assignee_user_id === user.id;
              return (
                <tr key={w.id}>
                  <td>
                    <b>{w.title}</b>
                    <div style={{fontSize: 11, color: '#64748b'}}>
                      {w.document_kind} · Dijital Onay (QES değil)
                      {w.source_key ? ` · ${w.source_key}` : ''}
                    </div>
                    {w.archive_path && <div style={{fontSize: 11, color: '#166534'}}>Arşiv: {w.archive_path}</div>}
                  </td>
                  <td>{w.status}</td>
                  <td>{w.current_step_order}</td>
                  <td style={{fontSize: 12}}>
                    {(w.steps || []).map((s) => (
                      <div key={s.id}>
                        {s.step_order}. {s.role_label} — {s.assignee_name || s.assignee_user_id} [{s.status}]
                      </div>
                    ))}
                  </td>
                  <td style={{whiteSpace: 'nowrap'}}>
                    {mine && w.status === 'in_progress' && (
                      <>
                        <button type="button" className="mini" disabled={busy} onClick={() => void decide(w.id, true)}>Onayla</button>{' '}
                        <button type="button" className="mini secondary" disabled={busy} onClick={() => void decide(w.id, false)}>Reddet</button>{' '}
                      </>
                    )}
                    {w.source_key && (
                      <button type="button" className="mini secondary" disabled={busy} onClick={() => void downloadDoc(w)} title="Kaynak belgeyi indir">
                        <Download size={14} /> Belge
                      </button>
                    )}
                    {(canCreate || w.created_by_id === user.id) && mode !== 'inbox' && (
                      <>
                        {' '}
                        <button
                          type="button"
                          className="mini secondary"
                          disabled={busy}
                          onClick={() => void remove(w)}
                          title="Akışı listeden kaldır"
                        >
                          Sil
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              );
            }) : <tr><td colSpan={5} className="empty">{emptyMsg}</td></tr>}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <>
      <div className="page-title">
        <h3><CheckCircle2 size={20} /> Onay Akışı (Uzman → Hekim → İşveren)</h3>
        <div className="actions">
          <button type="button" className="secondary" onClick={() => void load()}><RefreshCw size={16} /> Yenile</button>
          {mode === 'full' && canCreate && (
            <button type="button" onClick={() => void openCreate()}><Plus size={16} /> Akışı Başlat</button>
          )}
        </div>
      </div>
      <section className="panel">
        <div className="info" style={{marginBottom: 12}}>
          <ShieldAlert size={18} />
          <span>
            {meta?.notice || 'İşyeri seç → belge listeden gelir → İş Güvenliği → Hekim → İşveren/vekil onaylar.'}
            {' '}MFA (Authenticator) zorunludur.
          </span>
        </div>
        {err && <div className="error">{err}</div>}
        {mode !== 'inbox' && (
          <>
            <h4 style={{margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 8}}><Inbox size={16} /> Bekleyen onaylarım</h4>
            {renderTable(inbox, 'Size atanmış bekleyen adım yok.')}
            <h4 style={{margin: '20px 0 8px'}}>Akışlar</h4>
            {renderTable(rows, 'Henüz Eyas akışı yok.')}
          </>
        )}
        {mode === 'inbox' && (
          <>
            <h4 style={{margin: '0 0 8px'}}>Dijital Onay Kutum</h4>
            {renderTable(inbox, 'Bekleyen onayınız yok.')}
          </>
        )}
      </section>
      {open && (
        <AppModal title="Onay Akışı Başlat — Uzman → Hekim → İşveren/Vekil" close={() => setOpen(false)} wide>
          <form className="form-grid" onSubmit={create}>
            <p style={{gridColumn: '1 / -1', margin: 0, color: '#334155', fontSize: 14}}>
              İşyeri seçin. Belge listesi ve onaycılar (uzman, hekim, işveren/vekil) o işyerinden otomatik gelir.
              Elle isim yazılmaz. Hazır olmayan rapor seçilemez.
            </p>
            <label className="field"><span>İşyeri</span>
              <select
                required
                value={form.company_id}
                onChange={(e) => void onWorkplaceChange(e.target.value)}
              >
                <option value="">Seçiniz</option>
                {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label className="field" style={{gridColumn: '1 / -1'}}>
              <span>Belge (modülden — elle yazılmaz)</span>
              <select
                required
                value={form.source_key}
                onChange={(e) => setForm({...form, source_key: e.target.value})}
                disabled={!form.company_id}
              >
                <option value="">Seçiniz</option>
                {readyDocs.length > 0 && (
                  <optgroup label="Hazır belgeler">
                    {readyDocs.map((d) => (
                      <option key={d.source_key} value={d.source_key}>
                        {d.kind_label}: {d.title}
                      </option>
                    ))}
                  </optgroup>
                )}
                {blockedDocs.length > 0 && (
                  <optgroup label="Hazır değil (seçilemez)">
                    {blockedDocs.map((d) => (
                      <option key={d.source_key} value={d.source_key} disabled>
                        {d.kind_label}: {d.readiness_detail}
                      </option>
                    ))}
                  </optgroup>
                )}
              </select>
            </label>
            {assignees && (
              <div style={{gridColumn: '1 / -1', fontSize: 13, background: '#f8fafc', padding: 12, borderRadius: 8, border: '1px solid #e2e8f0'}}>
                <b>Onay sırası (bu işyerinden):</b>
                <ol style={{margin: '8px 0 0', paddingLeft: 18}}>
                  {(assignees.steps || []).map((s) => (
                    <li key={s.step_order} style={{marginBottom: 4}}>
                      {s.role_label}:{' '}
                      {s.suggested_user_name
                        ? <b>{s.suggested_user_name}</b>
                        : <span style={{color: '#b91c1c'}}>{(s.warnings || []).join(' ') || 'atanamadı'}</span>}
                    </li>
                  ))}
                </ol>
                {assignees.authorized_person_text && (
                  <div style={{marginTop: 8, color: '#64748b'}}>
                    Yetkili kişi (kayıt): {assignees.authorized_person_text}
                  </div>
                )}
              </div>
            )}
            <div className="form-actions" style={{gridColumn: '1 / -1'}}>
              <button type="submit" disabled={busy || !form.source_key}>Akışı Başlat</button>
            </div>
          </form>
        </AppModal>
      )}
    </>
  );
}
