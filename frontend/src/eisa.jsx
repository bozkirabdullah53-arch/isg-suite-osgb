import React, { useEffect, useState } from 'react';
import { api, downloadFile } from './api';
import { Check, RefreshCw, Trash2, X } from 'lucide-react';

export function Page({ title, action, children }) {
  return (
    <>
      <div className="page-title">
        <h3>{title}</h3>
        {action}
      </div>
      <section className="panel">{children}</section>
    </>
  );
}

export const statusLabels = {
  pending: 'Bekliyor',
  approved: 'Onaylandı',
  rejected: 'Reddedildi',
  trial: 'Deneme',
  active: 'Aktif',
  past_due: 'Süresi doldu',
  suspended: 'Askıda',
  cancelled: 'İptal',
  completed: 'Tamamlandı',
  failed: 'Başarısız',
  refunded: 'İade',
  queued: 'Kuyrukta',
  sent: 'Gönderildi',
  read: 'Okundu',
};

export const paymentChannels = [
  ['iyzico', 'İyzico'],
  ['stripe', 'Stripe'],
  ['bank_transfer', 'Havale'],
  ['invoice', 'Fatura'],
];

export const notificationChannels = [
  ['in_app', 'Uygulama içi'],
  ['email', 'E-posta'],
  ['sms', 'SMS'],
];

export function RefreshButton({ busy, onClick }) {
  return (
    <button type="button" className="secondary" disabled={busy} onClick={onClick}>
      <RefreshCw size={16} /> Yenile
    </button>
  );
}

export function StatusBadge({ status }) {
  const label = statusLabels[status] || status;
  const cls =
    status === 'active' || status === 'completed' || status === 'sent' || status === 'approved'
      ? 'badge-ok'
      : status === 'trial' || status === 'pending' || status === 'queued'
        ? 'badge-warn'
        : status === 'past_due' || status === 'failed' || status === 'rejected' || status === 'suspended'
          ? 'badge-danger'
          : 'badge-muted';
  return <span className={`status-badge ${cls}`}>{label}</span>;
}

export function MetricGrid({ items }) {
  return (
    <div className="report-grid" style={{ marginBottom: 16 }}>
      {items.map((item) => (
        <article className="metric" key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </article>
      ))}
    </div>
  );
}

export function SearchBar({ value, onChange, placeholder = 'Ara…' }) {
  return (
    <label className="field" style={{ maxWidth: 320, marginBottom: 12 }}>
      <span>Arama</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
    </label>
  );
}

export function Msg({ text }) {
  if (!text) return null;
  const ok = /onay|güncell|kayded|gönderildi|aktif/i.test(text);
  return <p style={{ color: ok ? '#166534' : '#b91c1c' }}>{text}</p>;
}

function toDatetimeLocalValue(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromDatetimeLocalValue(value) {
  const s = (value || '').trim();
  if (!s || s === '—') return null;
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(s)) return `${s}:00`;
  return s;
}

function ApplicationsPanel({ apps, busy, onApprove, onReject, onDelete, showActions = true }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>OSGB</th>
            <th>Yetki No</th>
            <th>Vergi No</th>
            <th>Başvuran</th>
            <th>Durum</th>
            <th>Eşleşme</th>
            <th>Tarih</th>
            {showActions && <th></th>}
          </tr>
        </thead>
        <tbody>
          {apps.length ? apps.map((a) => (
            <tr key={a.id}>
              <td>{a.name}</td>
              <td>{a.authorization_number}</td>
              <td>{a.tax_number}</td>
              <td>{a.applicant_name}<br /><small>{a.applicant_email}</small></td>
              <td><StatusBadge status={a.status} /></td>
              <td>{a.auto_matched ? 'Otomatik (mevcut)' : (a.matched_osgb_id ? 'Eşleşti' : 'Yeni kayıt')}</td>
              <td>{a.created_at ? new Date(a.created_at).toLocaleString('tr-TR') : '—'}</td>
              {showActions && (
                <td style={{ whiteSpace: 'nowrap' }}>
                  {a.status === 'pending' && (
                    <>
                      <button type="button" className="icon" title="Onayla" disabled={busy} onClick={() => onApprove(a.id)}><Check size={16} /></button>
                      <button type="button" className="icon" title="Reddet" disabled={busy} onClick={() => onReject(a.id)}><X size={16} /></button>
                    </>
                  )}
                  <button type="button" className="icon" title="Başvuru kaydını sil" disabled={busy} onClick={() => onDelete(a)}>
                    <Trash2 size={16} />
                  </button>
                </td>
              )}
            </tr>
          )) : (
            <tr><td colSpan={showActions ? 8 : 7} className="empty">Bu filtrede başvuru yok.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function AdminCredentialsModal({ data, onClose }) {
  if (!data) return null;
  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <section className="modal">
        <header><h3>OSGB Giriş Bilgileri</h3></header>
        <div className="form-grid single">
          <p style={{ marginTop: 0, color: '#64748b' }}>
            Bu geçici şifreyi OSGB yöneticisine güvenli kanaldan iletin. İlk girişten sonra şifresini değiştirmesini isteyin.
          </p>
          <p><strong>OSGB:</strong> {data.osgb_name}</p>
          <p><strong>E-posta:</strong> {data.email}</p>
          <p><strong>Ad:</strong> {data.full_name}</p>
          <p><strong>Geçici şifre:</strong> <code>{data.temporary_password}</code></p>
          <p style={{ color: '#166534' }}>{data.message}</p>
          <div className="form-actions">
            <button type="button" onClick={onClose}>Tamam</button>
          </div>
        </div>
      </section>
    </div>
  );
}

export function EisaOverviewPage() {
  const [dash, setDash] = useState(null);
  const [apps, setApps] = useState([]);
  const [appStatus, setAppStatus] = useState('pending');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [adminCreds, setAdminCreds] = useState(null);

  const load = async (status = appStatus) => {
    setBusy(true);
    setMsg('');
    const errors = [];
    const statusParam = status === 'all' ? 'all' : status;
    try {
      const d = await api('/eisa/dashboard');
      setDash(d);
    } catch (e) {
      errors.push(`Özet: ${e.message}`);
    }
    try {
      const a = await api(`/eisa/applications?status=${statusParam}`);
      setApps(Array.isArray(a) ? a : []);
    } catch (e) {
      errors.push(`Başvurular: ${e.message}`);
      setApps([]);
    }
    if (errors.length) setMsg(errors.join(' · '));
    setBusy(false);
  };

  useEffect(() => { void load(appStatus); }, [appStatus]);

  async function approve(id) {
    if (!window.confirm('Başvuruyu onaylayıp 10 günlük deneme başlatılsın mı?')) return;
    setBusy(true);
    try {
      const r = await api(`/eisa/applications/${id}/approve`, { method: 'POST' });
      await load();
      if (r.admin_account) {
        setAdminCreds({ ...r.admin_account, osgb_name: r.application?.name });
      }
      setMsg('Başvuru onaylandı.');
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function reject(id) {
    const reason = window.prompt('Red gerekçesi:');
    if (!reason?.trim()) return;
    setBusy(true);
    try {
      await api(`/eisa/applications/${id}/reject`, { method: 'POST', body: JSON.stringify({ reason: reason.trim() }) });
      await load();
      setMsg('Başvuru reddedildi.');
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function removeApplication(app) {
    const name = app?.name || `#${app?.id}`;
    if (!window.confirm(
      `"${name}" başvuru kaydı listeden silinsin mi?\n\nNot: Onaylanmış OSGB hesabı ve kullanıcılar silinmez; yalnızca bu başvuru satırı kaldırılır.`,
    )) return;
    setBusy(true);
    try {
      await api(`/eisa/applications/${app.id}`, { method: 'DELETE' });
      await load();
      setMsg('Başvuru kaydı silindi.');
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page title="Genel Bakış" action={<RefreshButton busy={busy} onClick={() => load()} />}>
      <Msg text={msg} />
      <div style={{ marginBottom: 20, padding: 16, borderRadius: 12, background: '#f0fdfa', border: '1px solid #99f6e4' }}>
        <h4 style={{ margin: '0 0 8px' }}>
          OSGB Başvuru Onayı
          {dash?.pending_applications != null ? ` — ${dash.pending_applications} bekleyen` : ''}
        </h4>
        <p style={{ marginTop: 0, color: '#64748b' }}>
          Aşağıdaki listeden başvuruyu onaylayın, reddedin veya kaydı silin. Onayda geçici şifre ekranda gösterilir.
        </p>
        <div className="actions" style={{ marginBottom: 12 }}>
          {[
            ['pending', 'Bekleyen'],
            ['approved', 'Onaylanan'],
            ['rejected', 'Reddedilen'],
            ['all', 'Tümü'],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={appStatus === value ? '' : 'secondary'}
              disabled={busy}
              onClick={() => setAppStatus(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <ApplicationsPanel apps={apps} busy={busy} onApprove={approve} onReject={reject} onDelete={removeApplication} />
      </div>
      <p style={{ marginTop: 0, color: '#64748b', maxWidth: 720 }}>
        Platform özeti: OSGB sayıları, abonelik durumları ve tahsilat metrikleri.
      </p>
      {dash && (
        <MetricGrid items={[
          { label: 'Bekleyen başvuru', value: dash.pending_applications },
          { label: 'Toplam OSGB', value: dash.osgb_total },
          { label: 'Aktif abonelik', value: dash.active_subscriptions },
          { label: 'Deneme', value: dash.trial_subscriptions },
          { label: 'Süresi yaklaşan', value: dash.expiring_subscriptions },
          { label: 'Süresi dolmuş', value: dash.expired_subscriptions },
          { label: 'Askıda hesap', value: dash.suspended_accounts },
          { label: 'Bu ay tahsilat', value: `${dash.payments_this_month?.toLocaleString('tr-TR')} ₺` },
          { label: 'Toplam tahsilat', value: `${dash.payments_total_collected?.toLocaleString('tr-TR')} ₺` },
          { label: 'Bekleyen ödeme', value: dash.pending_payments },
        ]} />
      )}
      <AdminCredentialsModal data={adminCreds} onClose={() => setAdminCreds(null)} />
    </Page>
  );
}

export function EisaOsgbUsersPage() {
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [adminCreds, setAdminCreds] = useState(null);
  const [provision, setProvision] = useState(null);

  const load = async () => {
    setBusy(true);
    setMsg('');
    try {
      const p = new URLSearchParams();
      if (q) p.set('q', q);
      const data = await api(`/eisa/osgb-users${p.toString() ? `?${p}` : ''}`);
      setRows(data);
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { void load(); }, []);

  async function toggleActive(row) {
    const action = row.is_active ? 'pasife almak' : 'yeniden aktifleştirmek';
    if (!window.confirm(`“${row.name}” OSGB hesabını ${action} istiyor musunuz?`)) return;
    setBusy(true);
    try {
      const path = row.is_active ? 'deactivate' : 'activate';
      await api(`/eisa/osgb-users/${row.id}/${path}`, { method: 'PATCH' });
      await load();
      setMsg(row.is_active ? 'OSGB pasife alındı.' : 'OSGB aktifleştirildi.');
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function provisionAdmin(row) {
    setProvision({
      osgb_id: row.id,
      osgb_name: row.name,
      email: row.admin_email || row.contact_email || '',
      full_name: row.admin_name || row.responsible_manager || row.name,
    });
  }

  async function submitProvision(e) {
    e.preventDefault();
    if (!provision) return;
    setBusy(true);
    setMsg('');
    try {
      const r = await api(`/eisa/osgb-users/${provision.osgb_id}/provision-admin`, {
        method: 'POST',
        body: JSON.stringify({
          email: provision.email,
          full_name: provision.full_name,
        }),
      });
      setProvision(null);
      setAdminCreds({ ...r, osgb_name: provision.osgb_name });
      await load();
      setMsg(r.message);
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page title="OSGB Kullanıcıları" action={<RefreshButton busy={busy} onClick={load} />}>
      <p style={{ marginTop: 0, color: '#64748b' }}>
        OSGB hesapları kalıcı silinmez; pasif/arşiv yaklaşımı kullanılır. Yönetici hesabı başvuru onayında otomatik oluşturulur;
        mevcut OSGB’ler için aşağıdan geçici şifre atayabilirsiniz.
      </p>
      <SearchBar value={q} onChange={setQ} placeholder="OSGB adı, e-posta, yetki no…" />
      <button type="button" disabled={busy} onClick={load} style={{ marginBottom: 12 }}>Ara</button>
      <Msg text={msg} />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>OSGB</th>
              <th>Yetkili</th>
              <th>İletişim</th>
              <th>Paket</th>
              <th>Abonelik</th>
              <th>Yönetici</th>
              <th>Hesap</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.name}</td>
                <td>{r.responsible_manager || '—'}</td>
                <td>{r.contact_email || '—'}<br /><small>{r.contact_phone || ''}</small></td>
                <td>{r.package_name || '—'}</td>
                <td><StatusBadge status={r.effective_status || r.subscription_status} /></td>
                <td>{r.admin_email || '—'}</td>
                <td>{r.is_active ? 'Aktif' : 'Pasif'}</td>
                <td>
                  <div className="actions">
                    <button type="button" className="secondary" disabled={busy} onClick={() => provisionAdmin(r)}>
                      {r.has_admin_user ? 'Şifre Sıfırla' : 'Yönetici Oluştur'}
                    </button>
                    <button type="button" className="secondary" disabled={busy} onClick={() => toggleActive(r)}>
                      {r.is_active ? 'Pasife Al' : 'Aktifleştir'}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {provision && (
        <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && setProvision(null)}>
          <section className="modal">
            <header><h3>{provision.osgb_name} — Yönetici Hesabı</h3></header>
            <form className="form-grid" onSubmit={submitProvision}>
              <label className="field"><span>Yönetici e-posta</span>
                <input required type="email" value={provision.email} onChange={(e) => setProvision({ ...provision, email: e.target.value })} />
              </label>
              <label className="field"><span>Ad soyad</span>
                <input required value={provision.full_name} onChange={(e) => setProvision({ ...provision, full_name: e.target.value })} />
              </label>
              <div className="form-actions">
                <button type="button" className="secondary" onClick={() => setProvision(null)}>İptal</button>
                <button type="submit" disabled={busy}>Geçici Şifre Oluştur</button>
              </div>
            </form>
          </section>
        </div>
      )}
      <AdminCredentialsModal data={adminCreds} onClose={() => setAdminCreds(null)} />
    </Page>
  );
}

function SubscriptionTable({ rows, busy, onEdit }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>OSGB</th>
            <th>Paket</th>
            <th>Durum</th>
            <th>Etkin</th>
            <th>Kalan gün</th>
            <th>Son ödeme</th>
            <th>Yazma</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.length ? rows.map((s) => (
            <tr key={s.id}>
              <td>{s.osgb_name || s.osgb_id}</td>
              <td>{s.package_name || s.plan}</td>
              <td><StatusBadge status={s.status} /></td>
              <td><StatusBadge status={s.effective_status} /></td>
              <td>{s.days_remaining ?? '—'}</td>
              <td>{s.last_payment_date ? new Date(s.last_payment_date).toLocaleDateString('tr-TR') : '—'}</td>
              <td>{s.write_allowed ? 'Açık' : 'Salt okunur'}</td>
              <td>
                <button type="button" className="secondary" disabled={busy} onClick={() => onEdit(s)}>Düzenle</button>
              </td>
            </tr>
          )) : (
            <tr><td colSpan={8} className="empty">Kayıt bulunamadı.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function SubscriptionEditModal({ edit, setEdit, busy, packages, onSave }) {
  if (!edit) return null;
  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && setEdit(null)}>
      <section className="modal">
        <header><h3>Abonelik — {edit.osgb_name}</h3></header>
        <form className="form-grid" onSubmit={onSave}>
          <label className="field"><span>Durum</span>
            <select value={edit.status} onChange={(e) => setEdit({ ...edit, status: e.target.value })}>
              {['trial', 'active', 'past_due', 'suspended', 'cancelled'].map((k) => (
                <option key={k} value={k}>{statusLabels[k]}</option>
              ))}
            </select>
          </label>
          <label className="field"><span>Paket</span>
            <select value={edit.package_id || ''} onChange={(e) => setEdit({ ...edit, package_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">—</option>
              {packages.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label className="field"><span>Ödeme kanalı</span>
            <select value={edit.last_payment_channel || ''} onChange={(e) => setEdit({ ...edit, last_payment_channel: e.target.value || null })}>
              <option value="">—</option>
              {paymentChannels.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label className="field"><span>Deneme bitiş</span>
            <input type="datetime-local" value={edit.trial_ends_at || ''} onChange={(e) => setEdit({ ...edit, trial_ends_at: e.target.value })} />
          </label>
          <label className="field"><span>Dönem bitiş</span>
            <input type="datetime-local" value={edit.current_period_ends_at || ''} onChange={(e) => setEdit({ ...edit, current_period_ends_at: e.target.value })} />
          </label>
          <label className="field"><span>Ödeme notu</span>
            <input value={edit.payment_notes || ''} onChange={(e) => setEdit({ ...edit, payment_notes: e.target.value })} />
          </label>
          <label className="field"><span>Otomatik yenileme</span>
            <input type="checkbox" checked={!!edit.is_auto_renew} onChange={(e) => setEdit({ ...edit, is_auto_renew: e.target.checked })} />
          </label>
          <div className="form-actions">
            <button type="button" className="secondary" onClick={() => setEdit(null)}>İptal</button>
            <button type="submit" disabled={busy}>Kaydet</button>
          </div>
        </form>
      </section>
    </div>
  );
}

function useSubscriptions(filter) {
  const [rows, setRows] = useState([]);
  const [packages, setPackages] = useState([]);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [edit, setEdit] = useState(null);

  const load = async () => {
    setBusy(true);
    setMsg('');
    try {
      const p = new URLSearchParams({ filter });
      if (q) p.set('q', q);
      const [subs, pkgs] = await Promise.all([
        api(`/eisa/subscriptions?${p}`),
        api('/eisa/packages?active_only=true'),
      ]);
      setRows(subs);
      setPackages(pkgs);
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { void load(); }, [filter]);

  async function saveSub(e) {
    e.preventDefault();
    if (!edit) return;
    setBusy(true);
    try {
      await api(`/eisa/subscriptions/${edit.osgb_id}`, {
        method: 'PUT',
        body: JSON.stringify({
          status: edit.status,
          package_id: edit.package_id,
          trial_ends_at: fromDatetimeLocalValue(edit.trial_ends_at),
          current_period_ends_at: fromDatetimeLocalValue(edit.current_period_ends_at),
          last_payment_channel: edit.last_payment_channel || null,
          payment_notes: edit.payment_notes || null,
          is_auto_renew: edit.is_auto_renew,
        }),
      });
      setEdit(null);
      await load();
      setMsg('Abonelik güncellendi.');
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  function openEdit(s) {
    setEdit({
      ...s,
      trial_ends_at: toDatetimeLocalValue(s.trial_ends_at),
      current_period_ends_at: toDatetimeLocalValue(s.current_period_ends_at),
    });
  }

  return { rows, packages, q, setQ, busy, msg, edit, setEdit, load, saveSub, openEdit };
}

export function EisaSubscriptionsPage() {
  const s = useSubscriptions('all');
  return (
    <Page title="Abonelik Yönetimi" action={<RefreshButton busy={s.busy} onClick={s.load} />}>
      <SearchBar value={s.q} onChange={s.setQ} />
      <button type="button" disabled={s.busy} onClick={s.load} style={{ marginBottom: 12 }}>Ara</button>
      <Msg text={s.msg} />
      <SubscriptionTable rows={s.rows} busy={s.busy} onEdit={s.openEdit} />
      <SubscriptionEditModal edit={s.edit} setEdit={s.setEdit} busy={s.busy} packages={s.packages} onSave={s.saveSub} />
    </Page>
  );
}

export function EisaExpiringSubscriptionsPage() {
  const s = useSubscriptions('expiring');
  return (
    <Page title="Süresi Yaklaşan Abonelikler" action={<RefreshButton busy={s.busy} onClick={s.load} />}>
      <Msg text={s.msg} />
      <SubscriptionTable rows={s.rows} busy={s.busy} onEdit={s.openEdit} />
      <SubscriptionEditModal edit={s.edit} setEdit={s.setEdit} busy={s.busy} packages={s.packages} onSave={s.saveSub} />
    </Page>
  );
}

export function EisaExpiredSubscriptionsPage() {
  const s = useSubscriptions('expired');
  return (
    <Page title="Süresi Dolan Abonelikler" action={<RefreshButton busy={s.busy} onClick={s.load} />}>
      <Msg text={s.msg} />
      <SubscriptionTable rows={s.rows} busy={s.busy} onEdit={s.openEdit} />
      <SubscriptionEditModal edit={s.edit} setEdit={s.setEdit} busy={s.busy} packages={s.packages} onSave={s.saveSub} />
    </Page>
  );
}

export function EisaPaymentsPage() {
  const [rows, setRows] = useState([]);
  const [osgbUsers, setOsgbUsers] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    osgb_id: '', amount: '', payment_method: 'bank_transfer', description: '',
  });

  const load = async () => {
    setBusy(true);
    try {
      const [payments, users] = await Promise.all([
        api('/eisa/payments'),
        api('/eisa/osgb-users'),
      ]);
      setRows(payments);
      setOsgbUsers(users);
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { void load(); }, []);

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api('/eisa/payments', {
        method: 'POST',
        body: JSON.stringify({
          osgb_id: Number(form.osgb_id),
          amount: Number(form.amount),
          payment_method: form.payment_method,
          description: form.description || null,
        }),
      });
      setOpen(false);
      setForm({ osgb_id: '', amount: '', payment_method: 'bank_transfer', description: '' });
      await load();
      setMsg('Ödeme kaydı eklendi.');
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page
      title="Finans ve Ödemeler"
      action={
        <div className="actions">
          <button type="button" onClick={() => setOpen(true)}>Manuel Ödeme Ekle</button>
          <RefreshButton busy={busy} onClick={load} />
        </div>
      }
    >
      <Msg text={msg} />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Referans</th>
              <th>OSGB</th>
              <th>Tutar</th>
              <th>Yöntem</th>
              <th>Durum</th>
              <th>Tarih</th>
              <th>Kaydeden</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.reference_no}</td>
                <td>{r.osgb_name}</td>
                <td>{Number(r.amount).toLocaleString('tr-TR')} {r.currency}</td>
                <td>{paymentChannels.find(([v]) => v === r.payment_method)?.[1] || r.payment_method || '—'}</td>
                <td><StatusBadge status={r.payment_status} /></td>
                <td>{new Date(r.payment_date).toLocaleDateString('tr-TR')}</td>
                <td>{r.recorded_by_name || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {open && (
        <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && setOpen(false)}>
          <section className="modal">
            <header><h3>Manuel Ödeme Kaydı</h3></header>
            <form className="form-grid" onSubmit={save}>
              <label className="field"><span>OSGB</span>
                <select required value={form.osgb_id} onChange={(e) => setForm({ ...form, osgb_id: e.target.value })}>
                  <option value="">Seçin</option>
                  {osgbUsers.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
                </select>
              </label>
              <label className="field"><span>Tutar (TRY)</span>
                <input required type="number" min="0" step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
              </label>
              <label className="field"><span>Ödeme yöntemi</span>
                <select value={form.payment_method} onChange={(e) => setForm({ ...form, payment_method: e.target.value })}>
                  {paymentChannels.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </label>
              <label className="field"><span>Açıklama</span>
                <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              </label>
              <div className="form-actions">
                <button type="button" className="secondary" onClick={() => setOpen(false)}>İptal</button>
                <button type="submit" disabled={busy}>Kaydet</button>
              </div>
            </form>
          </section>
        </div>
      )}
    </Page>
  );
}

export function EisaPackagesPage() {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [open, setOpen] = useState(false);
  const empty = { code: '', name: '', description: '', price_monthly: '0', price_yearly: '0', max_users: '50', max_workplaces: '100' };
  const [form, setForm] = useState(empty);

  const load = async () => {
    setBusy(true);
    try {
      setRows(await api('/eisa/packages'));
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { void load(); }, []);

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api('/eisa/packages', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          price_monthly: Number(form.price_monthly),
          price_yearly: Number(form.price_yearly),
          max_users: Number(form.max_users),
          max_workplaces: Number(form.max_workplaces),
        }),
      });
      setOpen(false);
      setForm(empty);
      await load();
      setMsg('Paket oluşturuldu.');
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggle(pkg) {
    setBusy(true);
    try {
      await api(`/eisa/packages/${pkg.id}`, {
        method: 'PUT',
        body: JSON.stringify({ is_active: !pkg.is_active }),
      });
      await load();
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page
      title="Paket Yönetimi"
      action={
        <div className="actions">
          <button type="button" onClick={() => setOpen(true)}>Yeni Paket</button>
          <RefreshButton busy={busy} onClick={load} />
        </div>
      }
    >
      <Msg text={msg} />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Kod</th>
              <th>Ad</th>
              <th>Aylık</th>
              <th>Yıllık</th>
              <th>Kullanıcı</th>
              <th>İşyeri</th>
              <th>Durum</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.id}>
                <td>{p.code}</td>
                <td>{p.name}</td>
                <td>{Number(p.price_monthly).toLocaleString('tr-TR')} ₺</td>
                <td>{Number(p.price_yearly).toLocaleString('tr-TR')} ₺</td>
                <td>{p.max_users}</td>
                <td>{p.max_workplaces}</td>
                <td>{p.is_active ? 'Aktif' : 'Pasif'}</td>
                <td>
                  <button type="button" className="secondary" disabled={busy} onClick={() => toggle(p)}>
                    {p.is_active ? 'Pasife Al' : 'Aktifleştir'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {open && (
        <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && setOpen(false)}>
          <section className="modal">
            <header><h3>Yeni Paket</h3></header>
            <form className="form-grid" onSubmit={save}>
              {['code', 'name', 'description'].map((k) => (
                <label className="field" key={k}><span>{k}</span>
                  <input required={k !== 'description'} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
                </label>
              ))}
              {['price_monthly', 'price_yearly', 'max_users', 'max_workplaces'].map((k) => (
                <label className="field" key={k}><span>{k}</span>
                  <input required type="number" value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
                </label>
              ))}
              <div className="form-actions">
                <button type="button" className="secondary" onClick={() => setOpen(false)}>İptal</button>
                <button type="submit" disabled={busy}>Kaydet</button>
              </div>
            </form>
          </section>
        </div>
      )}
    </Page>
  );
}

export function EisaNotificationsPage() {
  const [rows, setRows] = useState([]);
  const [osgbUsers, setOsgbUsers] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    channel: 'in_app', target_scope: 'all_osgb', target_osgb_id: '', title: '', message: '',
  });

  const load = async () => {
    setBusy(true);
    try {
      const [notes, users] = await Promise.all([api('/eisa/notifications'), api('/eisa/osgb-users')]);
      setRows(notes);
      setOsgbUsers(users);
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { void load(); }, []);

  async function send(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api('/eisa/notifications', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          target_osgb_id: form.target_osgb_id ? Number(form.target_osgb_id) : null,
        }),
      });
      setOpen(false);
      setForm({ channel: 'in_app', target_scope: 'all_osgb', target_osgb_id: '', title: '', message: '' });
      await load();
      setMsg('Bildirim gönderildi.');
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function resend(id) {
    setBusy(true);
    try {
      await api(`/eisa/notifications/${id}/resend`, { method: 'POST' });
      await load();
      setMsg('Bildirim yeniden gönderildi.');
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page
      title="Bilgilendirmeler"
      action={
        <div className="actions">
          <button type="button" onClick={() => setOpen(true)}>Yeni Bildirim</button>
          <RefreshButton busy={busy} onClick={load} />
        </div>
      }
    >
      <Msg text={msg} />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Başlık</th>
              <th>Kanal</th>
              <th>Hedef</th>
              <th>Durum</th>
              <th>Tarih</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.title}</td>
                <td>{notificationChannels.find(([v]) => v === r.channel)?.[1] || r.channel}</td>
                <td>{r.target_scope === 'all_osgb' ? 'Tüm OSGB' : r.target_osgb_name}</td>
                <td><StatusBadge status={r.status} /></td>
                <td>{new Date(r.created_at).toLocaleString('tr-TR')}</td>
                <td><button type="button" className="secondary" disabled={busy} onClick={() => resend(r.id)}>Yeniden Gönder</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {open && (
        <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && setOpen(false)}>
          <section className="modal">
            <header><h3>Yeni Bildirim</h3></header>
            <form className="form-grid" onSubmit={send}>
              <label className="field"><span>Kanal</span>
                <select value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })}>
                  {notificationChannels.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </label>
              <label className="field"><span>Hedef</span>
                <select value={form.target_scope} onChange={(e) => setForm({ ...form, target_scope: e.target.value })}>
                  <option value="all_osgb">Tüm OSGB</option>
                  <option value="selected_osgb">Seçili OSGB</option>
                </select>
              </label>
              {form.target_scope === 'selected_osgb' && (
                <label className="field"><span>OSGB</span>
                  <select required value={form.target_osgb_id} onChange={(e) => setForm({ ...form, target_osgb_id: e.target.value })}>
                    <option value="">Seçin</option>
                    {osgbUsers.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
                  </select>
                </label>
              )}
              <label className="field"><span>Başlık</span>
                <input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
              </label>
              <label className="field"><span>Mesaj</span>
                <input required value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} />
              </label>
              <div className="form-actions">
                <button type="button" className="secondary" onClick={() => setOpen(false)}>İptal</button>
                <button type="submit" disabled={busy}>Gönder</button>
              </div>
            </form>
          </section>
        </div>
      )}
    </Page>
  );
}

export function EisaReportsPage() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const load = async () => {
    setBusy(true);
    try {
      setData(await api('/eisa/reports/summary'));
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { void load(); }, []);

  function exportJson() {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `eisa-rapor-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Page
      title="Raporlar"
      action={
        <div className="actions">
          <button type="button" disabled={!data || busy} onClick={exportJson}>JSON Dışa Aktar</button>
          <RefreshButton busy={busy} onClick={load} />
        </div>
      }
    >
      <Msg text={msg} />
      {data && (
        <>
          <MetricGrid items={[
            { label: 'Toplam OSGB', value: data.dashboard.osgb_total },
            { label: 'Aktif abonelik', value: data.dashboard.active_subscriptions },
            { label: 'Süresi dolmuş', value: data.dashboard.expired_subscriptions },
            { label: 'Bu ay tahsilat', value: `${data.dashboard.payments_this_month?.toLocaleString('tr-TR')} ₺` },
          ]} />
          <p style={{ color: '#64748b' }}>
            Rapor oluşturulma: {new Date(data.generated_at).toLocaleString('tr-TR')}
            {' · '}
            {data.subscriptions?.length || 0} abonelik, {data.expiring?.length || 0} yaklaşan, {data.expired?.length || 0} dolmuş.
          </p>
        </>
      )}
    </Page>
  );
}

export function EisaAuditLogsPage() {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const load = async () => {
    setBusy(true);
    try {
      setRows(await api('/eisa/audit-logs?module=eisa'));
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { void load(); }, []);

  return (
    <Page title="İşlem Kayıtları" action={<RefreshButton busy={busy} onClick={load} />}>
      <Msg text={msg} />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Tarih</th>
              <th>Kullanıcı</th>
              <th>İşlem</th>
              <th>Modül</th>
              <th>Açıklama</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{new Date(r.created_at).toLocaleString('tr-TR')}</td>
                <td>{r.user_name || r.user_id || '—'}</td>
                <td>{r.action}</td>
                <td>{r.module || '—'}</td>
                <td>{r.description || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Page>
  );
}

export function EisaArchivesPage() {
  const [rows, setRows] = useState([]);
  const [kind, setKind] = useState('all');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const load = async () => {
    setBusy(true);
    setMsg('');
    try {
      const q = kind === 'all' ? '' : `?kind=${kind}`;
      setRows(await api(`/archives${q}`));
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { void load(); }, [kind]);

  return (
    <Page title="Merkezi Arşiv" action={<RefreshButton busy={busy} onClick={load} />}>
      <p style={{ marginTop: 0, color: '#64748b', maxWidth: 720 }}>
        Tüm kurum yedekleri ve silinen dosya kopyaları burada tutulur. Kullanıcı silse bile tarihli arşiv EİSA elinde kalır.
      </p>
      <Msg text={msg} />
      <div className="actions" style={{ marginBottom: 12 }}>
        {[
          ['all', 'Tümü'],
          ['tenant_backup', 'Kurum yedekleri'],
          ['deleted_file', 'Silinen dosyalar'],
        ].map(([v, l]) => (
          <button key={v} type="button" className={kind === v ? '' : 'secondary'} disabled={busy} onClick={() => setKind(v)}>{l}</button>
        ))}
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Tarih</th>
              <th>Tür</th>
              <th>OSGB</th>
              <th>Firma</th>
              <th>Dosya</th>
              <th>Boyut</th>
              <th>Not</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? rows.map((r) => (
              <tr key={r.id}>
                <td>{new Date(r.created_at).toLocaleString('tr-TR')}</td>
                <td>{r.kind === 'tenant_backup' ? 'Yedek' : 'Silinen dosya'}</td>
                <td>{r.osgb_id || '—'}</td>
                <td>{r.company_id || '—'}</td>
                <td>{r.original_name || '—'}</td>
                <td>{Math.max(1, Math.round((r.size_bytes || 0) / 1024))} KB</td>
                <td>{r.notes || '—'}</td>
                <td>
                  <button type="button" className="secondary" disabled={busy} onClick={() => downloadFile(`/archives/${r.id}/download`, r.original_name || `arsiv-${r.id}`)}>
                    İndir
                  </button>
                </td>
              </tr>
            )) : (
              <tr><td colSpan={8} className="empty">Arşiv kaydı yok.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Page>
  );
}

export function EisaSystemSettingsPage() {
  const [settings, setSettings] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const load = async () => {
    setBusy(true);
    try {
      setSettings(await api('/eisa/settings'));
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { void load(); }, []);

  async function save(e) {
    e.preventDefault();
    if (!settings) return;
    setBusy(true);
    try {
      const updated = await api('/eisa/settings', {
        method: 'PUT',
        body: JSON.stringify({
          trial_days: Number(settings.trial_days),
          expiring_window_days: Number(settings.expiring_window_days),
          support_email: settings.support_email,
          support_phone: settings.support_phone,
        }),
      });
      setSettings(updated);
      setMsg('Ayarlar kaydedildi.');
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!settings) return <Page title="Sistem Ayarları"><p>Yükleniyor…</p></Page>;

  return (
    <Page title="Sistem Ayarları" action={<RefreshButton busy={busy} onClick={load} />}>
      <Msg text={msg} />
      <form className="form-grid" onSubmit={save} style={{ maxWidth: 480 }}>
        <label className="field"><span>Deneme süresi (gün)</span>
          <input type="number" min="1" value={settings.trial_days} onChange={(e) => setSettings({ ...settings, trial_days: e.target.value })} />
        </label>
        <label className="field"><span>Yaklaşan abonelik penceresi (gün)</span>
          <input type="number" min="1" value={settings.expiring_window_days} onChange={(e) => setSettings({ ...settings, expiring_window_days: e.target.value })} />
        </label>
        <label className="field"><span>Destek e-posta</span>
          <input type="email" value={settings.support_email} onChange={(e) => setSettings({ ...settings, support_email: e.target.value })} />
        </label>
        <label className="field"><span>Destek telefon</span>
          <input value={settings.support_phone} onChange={(e) => setSettings({ ...settings, support_phone: e.target.value })} />
        </label>
        <div className="form-actions">
          <button type="submit" disabled={busy}>Kaydet</button>
        </div>
      </form>
    </Page>
  );
}

const API_URL =
  import.meta.env.VITE_API_URL ||
  (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? `${window.location.protocol}//${window.location.hostname}:8000/api/v1`
    : 'https://isg-suite-api-1u9t.onrender.com/api/v1');

export function OsgbApplyPage({ onBack }) {
  const [form, setForm] = useState({
    name: '', authorization_number: '', tax_number: '', responsible_manager: '',
    contact_email: '', contact_phone: '', address: '',
    applicant_name: '', applicant_email: '', notes: '',
    contract_accepted: false,
    personal_data_accepted: false,
  });
  const [busy, setBusy] = useState(false);
  const [ok, setOk] = useState(false);
  const [submittedId, setSubmittedId] = useState(null);
  const [err, setErr] = useState('');

  function formatApiError(detail, fallback = 'Başvuru gönderilemedi.') {
    if (!detail) return fallback;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          if (typeof d === 'string') return d;
          const field = Array.isArray(d.loc) ? d.loc.filter((x) => x !== 'body').join('.') : '';
          const msg = d.msg || JSON.stringify(d);
          return field ? `${field}: ${msg}` : msg;
        })
        .join(' · ');
    }
    if (typeof detail === 'object') return detail.msg || detail.message || JSON.stringify(detail);
    return String(detail);
  }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr('');
    if (!form.contract_accepted || !form.personal_data_accepted) {
      setErr('Sözleşme ve kişisel verilerin korunması onayı zorunludur.');
      setBusy(false);
      return;
    }
    if ((form.tax_number || '').trim().length < 8) {
      setErr('Vergi numarası en az 8 karakter olmalıdır.');
      setBusy(false);
      return;
    }
    try {
      const r = await fetch(`${API_URL}/osgb-applications`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(formatApiError(data.detail));
      setOk(true);
      setSubmittedId(data.id ?? null);
    } catch (ex) {
      setErr(ex.message || 'Başvuru gönderilemedi.');
    } finally {
      setBusy(false);
    }
  }

  if (ok) {
    return (
      <main className="login-shell">
        <section className="login-card" style={{ maxWidth: 480 }}>
          <h1>Başvuru alındı</h1>
          <p>EİSA ekibi başvurunuzu inceleyecek. Onay sonrası 10 günlük deneme süreniz başlar.</p>
          {submittedId && <p style={{ color: '#64748b' }}>Başvuru no: <strong>#{submittedId}</strong></p>}
          <button type="button" onClick={onBack}>Giriş sayfasına dön</button>
        </section>
      </main>
    );
  }

  return (
    <main className="login-shell">
      <div className="login-wrap" style={{ maxWidth: 560 }}>
        <div className="login-brand">
          <img src="/eisa-logo-horizontal.png" alt="EİSA PROGRAMLAMA" className="login-eisa-logo" />
        </div>
        <section className="login-card">
          <h1>OSGB Başvuru Formu</h1>
          <p>İSG Suite platformuna OSGB merkezi olarak başvurun. Yetki no ve vergi no ile mevcut kaydınız otomatik eşleşir.</p>
          <form className="form-grid" onSubmit={submit}>
            <label className="field"><span>OSGB adı *</span><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
            <label className="field"><span>Yetki numarası *</span><input required value={form.authorization_number} onChange={(e) => setForm({ ...form, authorization_number: e.target.value })} /></label>
            <label className="field"><span>Vergi numarası * (en az 8 hane)</span><input required minLength={8} value={form.tax_number} onChange={(e) => setForm({ ...form, tax_number: e.target.value })} /></label>
            <label className="field"><span>Sorumlu müdür</span><input value={form.responsible_manager} onChange={(e) => setForm({ ...form, responsible_manager: e.target.value })} /></label>
            <label className="field"><span>İletişim e-posta *</span><input type="email" required placeholder="ornek@firma.com" value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })} /></label>
            <label className="field"><span>Telefon</span><input value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} /></label>
            <label className="field"><span>Adres</span><input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} /></label>
            <label className="field"><span>Başvuran adı *</span><input required value={form.applicant_name} onChange={(e) => setForm({ ...form, applicant_name: e.target.value })} /></label>
            <label className="field"><span>Başvuran e-posta *</span><input type="email" required placeholder="ornek@firma.com" value={form.applicant_email} onChange={(e) => setForm({ ...form, applicant_email: e.target.value })} /></label>
            <label className="field"><span>Not</span><input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label>
            <label className="field">
              <span>
                <input type="checkbox" checked={form.contract_accepted} onChange={(e) => setForm({ ...form, contract_accepted: e.target.checked })} />{' '}
                Sözleşmeyi kabul ediyorum.
              </span>
            </label>
            <label className="field">
              <span>
                <input type="checkbox" checked={form.personal_data_accepted} onChange={(e) => setForm({ ...form, personal_data_accepted: e.target.checked })} />{' '}
                Kişisel verilerimin korunmasını kabul ediyorum.
              </span>
            </label>
            {err && <div className="error">{err}</div>}
            <div className="form-actions">
              <button type="button" className="secondary" onClick={onBack}>Geri</button>
              <button type="submit" disabled={busy}>{busy ? 'Gönderiliyor…' : 'Başvuruyu Gönder'}</button>
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}
