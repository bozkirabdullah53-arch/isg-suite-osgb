import React, {useEffect, useState} from 'react';
import {CheckCircle2, Plus, RefreshCw, ShieldAlert, Inbox} from 'lucide-react';
import {api} from './api';
import {AppModal} from './ui_modal';

/**
 * Eyas Digital Approval — hesap bazlı sıralı dijital onay.
 * Nitelikli e-imza değildir. OSGB Signer /esign bozulmaz.
 */
export function EyasDigitalApprovalPage({user, mode = 'full'}) {
  const canCreate = ['global_admin', 'safety_specialist'].includes(user.role);
  const [meta, setMeta] = useState(null);
  const [rows, setRows] = useState([]);
  const [inbox, setInbox] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [users, setUsers] = useState([]);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    company_id: user.company_id || '',
    title: '',
    document_kind: 'risk',
    uzman_id: '',
    hekim_id: '',
    isveren_id: '',
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
      if (canCreate) {
        try {
          setUsers(await api('/users'));
        } catch {
          setUsers([]);
        }
      }
    } catch (e) {
      setErr(e.message || 'Eyas yüklenemedi');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function create(e) {
    e.preventDefault();
    if (!form.uzman_id || !form.hekim_id || !form.isveren_id) {
      setErr('Üç onaycı kullanıcı da seçilmelidir.');
      return;
    }
    setBusy(true);
    setErr('');
    try {
      await api('/eyas/workflows', {
        method: 'POST',
        body: JSON.stringify({
          company_id: Number(form.company_id),
          title: form.title,
          document_kind: form.document_kind,
          steps: [
            {assignee_user_id: Number(form.uzman_id), role_label: 'İSG Uzmanı', step_order: 1},
            {assignee_user_id: Number(form.hekim_id), role_label: 'İşyeri Hekimi', step_order: 2},
            {assignee_user_id: Number(form.isveren_id), role_label: 'İşveren / vekili', step_order: 3},
          ],
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

  if (meta && meta.enabled === false) {
    return (
      <section className="panel">
        <p style={{margin: 0, color: '#64748b'}}>
          Eyas Digital Approval şu an kapalı (yönetici bayrağı). Mevcut Belge Onay / e-imza sekmeleri etkilenmez.
        </p>
      </section>
    );
  }

  const byRole = (role) => users.filter((u) => u.role === role && u.is_active !== false);

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
                    <div style={{fontSize: 11, color: '#64748b'}}>{w.document_kind} · Dijital Onay (QES değil)</div>
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
                        <button type="button" className="mini secondary" disabled={busy} onClick={() => void decide(w.id, false)}>Reddet</button>
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
        <h3><CheckCircle2 size={20} /> Eyas Digital Approval</h3>
        <div className="actions">
          <button type="button" className="secondary" onClick={() => void load()}><RefreshCw size={16} /> Yenile</button>
          {mode === 'full' && canCreate && (
            <button type="button" onClick={() => setOpen(true)}><Plus size={16} /> Onay Akışı</button>
          )}
        </div>
      </div>
      <section className="panel">
        <div className="info" style={{marginBottom: 12}}>
          <ShieldAlert size={18} />
          <span>
            {meta?.notice || 'Bu süreç Dijital Onaydır; nitelikli elektronik imza değildir. Her kullanıcı yalnızca kendi hesabı ile onaylar.'}
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
        <AppModal title="Yeni Eyas Dijital Onay Akışı" close={() => setOpen(false)} wide>
          <form className="form-grid" onSubmit={create}>
            <label className="field"><span>İşyeri</span>
              <select required value={form.company_id} onChange={(e) => setForm({...form, company_id: e.target.value})}>
                <option value="">Seçiniz</option>
                {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label className="field"><span>Belge başlığı</span>
              <input required value={form.title} onChange={(e) => setForm({...form, title: e.target.value})} />
            </label>
            <label className="field"><span>Tür</span>
              <input value={form.document_kind} onChange={(e) => setForm({...form, document_kind: e.target.value})} />
            </label>
            <label className="field"><span>1) İSG Uzmanı hesabı</span>
              <select required value={form.uzman_id} onChange={(e) => setForm({...form, uzman_id: e.target.value})}>
                <option value="">Seçiniz</option>
                {byRole('safety_specialist').map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
              </select>
            </label>
            <label className="field"><span>2) İşyeri Hekimi hesabı</span>
              <select required value={form.hekim_id} onChange={(e) => setForm({...form, hekim_id: e.target.value})}>
                <option value="">Seçiniz</option>
                {byRole('workplace_physician').map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
              </select>
            </label>
            <label className="field"><span>3) İşveren / vekil hesabı</span>
              <select required value={form.isveren_id} onChange={(e) => setForm({...form, isveren_id: e.target.value})}>
                <option value="">Seçiniz</option>
                {users.filter((u) => u.is_active !== false).map((u) => (
                  <option key={u.id} value={u.id}>{u.full_name} ({u.role})</option>
                ))}
              </select>
            </label>
            <div className="form-actions" style={{gridColumn: '1 / -1'}}>
              <button type="submit" disabled={busy}>Akışı Başlat</button>
            </div>
          </form>
        </AppModal>
      )}
    </>
  );
}
