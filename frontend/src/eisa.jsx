import React, { useEffect, useState } from 'react';
import { api } from './api';
import { Check, X, RefreshCw } from 'lucide-react';

function Page({ title, action, children }) {
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

const statusLabels = {
  pending: 'Bekliyor',
  approved: 'Onaylandı',
  rejected: 'Reddedildi',
  trial: 'Deneme',
  active: 'Aktif',
  past_due: 'Salt okunur',
  suspended: 'Askıda',
  cancelled: 'İptal',
};

const paymentChannels = [
  ['iyzico', 'İyzico'],
  ['stripe', 'Stripe'],
  ['bank_transfer', 'Havale'],
  ['invoice', 'Fatura'],
];

export function EisaPage() {
  const [tab, setTab] = useState('applications');
  const [apps, setApps] = useState([]);
  const [subs, setSubs] = useState([]);
  const [dash, setDash] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [edit, setEdit] = useState(null);

  const load = async () => {
    setBusy(true);
    setMsg('');
    try {
      const [d, a, s] = await Promise.all([
        api('/eisa/dashboard'),
        api('/eisa/applications?status=pending'),
        api('/eisa/subscriptions'),
      ]);
      setDash(d);
      setApps(a);
      setSubs(s);
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  async function approve(id) {
    if (!window.confirm('Başvuruyu onaylayıp 10 günlük deneme başlatılsın mı?')) return;
    setBusy(true);
    try {
      await api(`/eisa/applications/${id}/approve`, { method: 'POST' });
      await load();
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
      await api(`/eisa/applications/${id}/reject`, {
        method: 'POST',
        body: JSON.stringify({ reason: reason.trim() }),
      });
      await load();
      setMsg('Başvuru reddedildi.');
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveSub(e) {
    e.preventDefault();
    if (!edit) return;
    setBusy(true);
    try {
      await api(`/eisa/subscriptions/${edit.osgb_id}`, {
        method: 'PUT',
        body: JSON.stringify({
          status: edit.status,
          trial_ends_at: edit.trial_ends_at || null,
          current_period_ends_at: edit.current_period_ends_at || null,
          last_payment_channel: edit.last_payment_channel || null,
          payment_notes: edit.payment_notes || null,
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

  return (
    <Page
      title="EİSA — Platform Yönetimi"
      action={
        <button type="button" className="secondary" disabled={busy} onClick={load}>
          <RefreshCw size={16} /> Yenile
        </button>
      }
    >
      <p style={{ marginTop: 0, color: '#64748b', maxWidth: 720 }}>
        EİSA üst yönetim paneli: OSGB başvurularını onaylayın, abonelik ve ödeme kayıtlarını yönetin.
        Yetki no / vergi no ile mevcut OSGB otomatik eşleşir.
      </p>
      {dash && (
        <div className="report-grid" style={{ marginBottom: 16 }}>
          <article className="metric">
            <span>Bekleyen başvuru</span>
            <strong>{dash.pending_applications}</strong>
          </article>
          <article className="metric">
            <span>Toplam OSGB</span>
            <strong>{dash.osgb_total}</strong>
          </article>
          <article className="metric">
            <span>Abonelik kaydı</span>
            <strong>{dash.subscriptions_total}</strong>
          </article>
        </div>
      )}
      {msg && <p style={{ color: msg.includes('onay') || msg.includes('güncell') ? '#166534' : '#b91c1c' }}>{msg}</p>}
      <div className="actions" style={{ marginBottom: 12 }}>
        <button type="button" className={tab === 'applications' ? '' : 'secondary'} onClick={() => setTab('applications')}>
          Başvurular
        </button>
        <button type="button" className={tab === 'subscriptions' ? '' : 'secondary'} onClick={() => setTab('subscriptions')}>
          Abonelikler
        </button>
      </div>
      {tab === 'applications' && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>OSGB</th>
                <th>Yetki No</th>
                <th>Vergi No</th>
                <th>Başvuran</th>
                <th>Eşleşme</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {apps.length ? apps.map((a) => (
                <tr key={a.id}>
                  <td>{a.name}</td>
                  <td>{a.authorization_number}</td>
                  <td>{a.tax_number}</td>
                  <td>{a.applicant_name}<br /><small>{a.applicant_email}</small></td>
                  <td>{a.auto_matched ? 'Otomatik (mevcut)' : 'Yeni kayıt'}</td>
                  <td>
                    <button type="button" className="icon" title="Onayla" onClick={() => approve(a.id)}><Check size={16} /></button>
                    <button type="button" className="icon" title="Reddet" onClick={() => reject(a.id)}><X size={16} /></button>
                  </td>
                </tr>
              )) : (
                <tr><td colSpan={6} className="empty">Bekleyen başvuru yok.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {tab === 'subscriptions' && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>OSGB</th>
                <th>Durum</th>
                <th>Etkin</th>
                <th>Yazma</th>
                <th>Deneme bitiş</th>
                <th>Dönem bitiş</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {subs.map((s) => (
                <tr key={s.id}>
                  <td>{s.osgb_name || s.osgb_id}</td>
                  <td>{statusLabels[s.status] || s.status}</td>
                  <td>{statusLabels[s.effective_status] || s.effective_status}</td>
                  <td>{s.write_allowed ? 'Açık' : 'Salt okunur'}</td>
                  <td>{s.trial_ends_at ? new Date(s.trial_ends_at).toLocaleDateString('tr-TR') : '—'}</td>
                  <td>{s.current_period_ends_at ? new Date(s.current_period_ends_at).toLocaleDateString('tr-TR') : '—'}</td>
                  <td><button type="button" className="secondary" onClick={() => setEdit({ ...s, trial_ends_at: s.trial_ends_at?.slice(0, 16), current_period_ends_at: s.current_period_ends_at?.slice(0, 16) })}>Düzenle</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {edit && (
        <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && setEdit(null)}>
          <section className="modal">
            <header><h3>Abonelik — {edit.osgb_name}</h3></header>
            <form className="form-grid" onSubmit={saveSub}>
              <label className="field"><span>Durum</span>
                <select value={edit.status} onChange={(e) => setEdit({ ...edit, status: e.target.value })}>
                  {['trial', 'active', 'past_due', 'suspended', 'cancelled'].map((k) => (
                    <option key={k} value={k}>{statusLabels[k]}</option>
                  ))}
                </select>
              </label>
              <label className="field"><span>Ödeme kanalı</span>
                <select value={edit.last_payment_channel || ''} onChange={(e) => setEdit({ ...edit, last_payment_channel: e.target.value || null })}>
                  <option value="">—</option>
                  {paymentChannels.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </label>
              <label className="field"><span>Deneme bitiş (ISO)</span>
                <input value={edit.trial_ends_at || ''} onChange={(e) => setEdit({ ...edit, trial_ends_at: e.target.value })} placeholder="2026-07-30T12:00" />
              </label>
              <label className="field"><span>Dönem bitiş (ISO)</span>
                <input value={edit.current_period_ends_at || ''} onChange={(e) => setEdit({ ...edit, current_period_ends_at: e.target.value })} />
              </label>
              <label className="field"><span>Ödeme notu</span>
                <input value={edit.payment_notes || ''} onChange={(e) => setEdit({ ...edit, payment_notes: e.target.value })} />
              </label>
              <div className="form-actions">
                <button type="button" className="secondary" onClick={() => setEdit(null)}>İptal</button>
                <button type="submit" disabled={busy}>Kaydet</button>
              </div>
            </form>
          </section>
        </div>
      )}
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
  });
  const [busy, setBusy] = useState(false);
  const [ok, setOk] = useState(false);
  const [err, setErr] = useState('');

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      const r = await fetch(`${API_URL}/osgb-applications`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || 'Başvuru gönderilemedi.');
      setOk(true);
    } catch (ex) {
      setErr(ex.message);
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
          <label className="field"><span>Vergi numarası *</span><input required value={form.tax_number} onChange={(e) => setForm({ ...form, tax_number: e.target.value })} /></label>
          <label className="field"><span>Sorumlu müdür</span><input value={form.responsible_manager} onChange={(e) => setForm({ ...form, responsible_manager: e.target.value })} /></label>
          <label className="field"><span>İletişim e-posta *</span><input type="email" required value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })} /></label>
          <label className="field"><span>Telefon</span><input value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} /></label>
          <label className="field"><span>Adres</span><input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} /></label>
          <label className="field"><span>Başvuran adı *</span><input required value={form.applicant_name} onChange={(e) => setForm({ ...form, applicant_name: e.target.value })} /></label>
          <label className="field"><span>Başvuran e-posta *</span><input type="email" required value={form.applicant_email} onChange={(e) => setForm({ ...form, applicant_email: e.target.value })} /></label>
          <label className="field"><span>Not</span><input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label>
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
