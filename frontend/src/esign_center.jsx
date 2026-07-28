import React, {useEffect, useState} from 'react';
import {api} from './api';
import {KeyRound, Plus, RefreshCw, ShieldCheck, Usb, AlertTriangle} from 'lucide-react';
import {AppModal} from './ui_modal';

/** Desktop v0.10 orkestrasyon UI — API: /esign-orch (mevcut /esign agent hattına dokunmaz). */

function hashOk(v) {
  return /^[a-fA-F0-9]{64}$/.test(String(v || ''));
}

function badge(v) {
  const cls = v === 'verified' ? 'badge-ok' : v === 'signed' ? 'badge-warn' : v === 'ready' || v === 'token_issued' ? 'badge-muted' : 'badge-danger';
  return <span className={`status-badge ${cls}`}>{v || '—'}</span>;
}

export function ESignCenterPage({user}) {
  const canEdit = ['global_admin', 'safety_specialist', 'workplace_physician'].includes(user.role);
  const [companies, setCompanies] = useState([]);
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [agent, setAgent] = useState('Kontrol edilmedi');
  const [form, setForm] = useState({
    company_id: user.company_id || '',
    document_title: '',
    document_kind: 'risk',
    document_version: '1',
    document_sha256: '',
    signing_format: 'PAdES',
    required_signer_name: '',
    required_signer_role: 'İşveren / vekili',
    signing_order: 1,
  });

  async function load() {
    setBusy(true);
    setErr('');
    try {
      const [m, c, r] = await Promise.all([
        api('/esign-orch/meta'),
        api('/companies'),
        api('/esign-orch/requests'),
      ]);
      setMeta(m);
      setCompanies(c);
      setRows(r);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function save(e) {
    e.preventDefault();
    if (!hashOk(form.document_sha256)) {
      setErr('Belge SHA-256 değeri 64 karakter hexadecimal olmalıdır.');
      return;
    }
    setBusy(true);
    try {
      await api('/esign-orch/requests', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          company_id: Number(form.company_id),
          signing_order: Number(form.signing_order),
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

  async function token(id) {
    try {
      const t = await api(`/esign-orch/requests/${id}/token`, {method: 'POST'});
      await navigator.clipboard?.writeText(JSON.stringify(t));
      alert('Tek kullanımlık imza talebi panoya kopyalandı. OSGB Signer (17000) / agent bu talebi kullanabilir. Anahtar 5 dakika geçerlidir.');
    } catch (e) {
      setErr(e.message);
    }
  }

  async function verify(id) {
    try {
      await api(`/esign-orch/requests/${id}/verify`, {method: 'POST'});
      await load();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function checkAgent() {
    setAgent('Kontrol ediliyor…');
    const base = meta?.agent_url || 'https://127.0.0.1:17000';
    try {
      const r = await fetch(`${base}/health`, {method: 'GET'});
      setAgent(r.ok ? 'Agent çalışıyor (17000)' : 'Agent yanıtı geçersiz');
    } catch {
      setAgent('Agent bulunamadı — KUR.bat ile OSGB Signer kurun');
    }
  }

  return (
    <>
      <div className="page-title">
        <h3><KeyRound size={20} /> E‑İmza Orkestrasyon</h3>
        <div className="actions">
          <button type="button" className="secondary" onClick={() => void checkAgent()}><Usb size={16} /> Agent Kontrol</button>
          <button type="button" className="secondary" onClick={() => void load()}><RefreshCw size={16} /> Yenile</button>
          {canEdit && <button type="button" onClick={() => setOpen(true)}><Plus size={16} /> İmza Talebi</button>}
        </div>
      </div>
      <section className="panel">
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 12, marginBottom: 14}}>
          <div className="stat-card"><strong>Yerel Agent</strong><div>{agent}</div></div>
          <div className="stat-card"><strong>Önerilen format</strong><div>{meta?.recommended || 'PAdES-B-LT/LTA'}</div></div>
          <div className="stat-card"><strong>Güvenlik</strong><div>Tek kullanımlık anahtar + SHA‑256 belge kilidi</div></div>
        </div>
        <div className="info" style={{marginBottom: 12}}><ShieldCheck size={18} /><span>{meta?.legal_notice || 'Basit onay, nitelikli elektronik imza değildir.'}</span></div>
        <div className="warning" style={{marginBottom: 12}}><AlertTriangle size={18} /><span>PIN ve özel anahtar sunucuya gönderilmez. PDF PAdES için “Süreç Onayı” sekmesindeki Kart/PDF İmzala kullanılır.</span></div>
        {err && <div className="error">{err}</div>}
        {busy && !rows.length ? <p>Yükleniyor…</p> : null}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Belge</th><th>Tür / Sürüm</th><th>İmzacı</th><th>Format</th>
                <th>Durum</th><th>Doğrulama</th><th>Sertifika</th><th></th>
              </tr>
            </thead>
            <tbody>
              {rows.length ? rows.map((r) => (
                <tr key={r.id}>
                  <td><b>{r.document_title}</b><br /><small>{r.document_sha256.slice(0, 12)}…</small></td>
                  <td>{r.document_kind} / {r.document_version}</td>
                  <td>{r.required_signer_name}<br /><small>{r.required_signer_role}</small></td>
                  <td>{r.signing_format}</td>
                  <td>{badge(r.status)}</td>
                  <td>{badge(r.verification_status)}</td>
                  <td>{r.certificate_qualified === true ? 'Nitelikli' : r.certificate_qualified === false ? 'Nitelikli değil' : '—'}</td>
                  <td>
                    {canEdit && !['signed', 'verified'].includes(r.status) && (
                      <button type="button" className="mini" onClick={() => void token(r.id)}>Agent Talebi</button>
                    )}{' '}
                    {r.status === 'signed' && (
                      <button type="button" className="mini" onClick={() => void verify(r.id)}>Doğrula</button>
                    )}
                  </td>
                </tr>
              )) : <tr><td colSpan={8} className="empty">Henüz e‑imza orkestrasyon talebi yok.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
      {open && (
        <AppModal title="Yeni E‑İmza Talebi" close={() => setOpen(false)} wide>
          <form className="form-grid" onSubmit={save}>
            <label className="field"><span>İşyeri</span>
              <select required value={form.company_id} onChange={(e) => setForm({...form, company_id: e.target.value})}>
                <option value="">Seçiniz</option>
                {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label className="field"><span>Belge başlığı</span>
              <input required value={form.document_title} onChange={(e) => setForm({...form, document_title: e.target.value})} />
            </label>
            <label className="field"><span>Belge türü</span>
              <select value={form.document_kind} onChange={(e) => setForm({...form, document_kind: e.target.value})}>
                {['risk', 'training', 'health', 'emergency', 'committee', 'annual_plan', 'incident', 'periodic_control', 'measurement', 'general'].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </label>
            <label className="field"><span>Belge sürümü</span>
              <input value={form.document_version} onChange={(e) => setForm({...form, document_version: e.target.value})} />
            </label>
            <label className="field" style={{gridColumn: '1 / -1'}}><span>Belge SHA‑256 özeti</span>
              <input required maxLength={64} placeholder="64 karakter hexadecimal" value={form.document_sha256} onChange={(e) => setForm({...form, document_sha256: e.target.value.trim()})} />
            </label>
            <label className="field"><span>İmza formatı</span>
              <select value={form.signing_format} onChange={(e) => setForm({...form, signing_format: e.target.value})}>
                <option>PAdES</option><option>XAdES</option><option>CAdES</option>
              </select>
            </label>
            <label className="field"><span>İmza sırası</span>
              <input type="number" min="1" max="100" value={form.signing_order} onChange={(e) => setForm({...form, signing_order: e.target.value})} />
            </label>
            <label className="field"><span>İmzalayacak kişi</span>
              <input required value={form.required_signer_name} onChange={(e) => setForm({...form, required_signer_name: e.target.value})} />
            </label>
            <label className="field"><span>Görevi / rolü</span>
              <input required value={form.required_signer_role} onChange={(e) => setForm({...form, required_signer_role: e.target.value})} />
            </label>
            <div className="form-actions" style={{gridColumn: '1 / -1'}}>
              <button type="submit" disabled={busy}>Talebi Oluştur</button>
            </div>
          </form>
        </AppModal>
      )}
    </>
  );
}
