import React, {useEffect, useState} from 'react';
import {ClipboardCheck, Download, FileWarning, Map, Plus, RefreshCw, Trash2, Upload, Users} from 'lucide-react';
import {
  downloadBase64Pdf,
  probeIsgSigner,
  signPdfWithIsgSigner,
} from './isg_signer_agent';
import {api, downloadFile, uploadFile} from './api';
import {AppModal} from './ui_modal';
import {ESignCenterPage} from './esign_center';
import {EyasDigitalApprovalPage} from './eyas_digital_approval';
import {EmergencyKrokiEditor} from './emergency_kroki_editor';

/** Belge Onay hub: varsayılan = Eyas (Uzman→Hekim→İşveren). Eski süreç ayrı sekmede. */
export function BelgeOnayHub({user}) {
  const [tab, setTab] = useState('eyas');
  const [eyasOn, setEyasOn] = useState(true);
  const [eyasOpenCreate, setEyasOpenCreate] = useState(false);

  useEffect(() => {
    api('/eyas/meta')
      .then((m) => {
        const on = !!m?.enabled;
        setEyasOn(on);
        if (!on) setTab('surec');
      })
      .catch(() => {
        setEyasOn(false);
        setTab('surec');
      });
  }, []);

  function startEyasFlow() {
    setTab('eyas');
    setEyasOpenCreate(true);
  }

  return (
    <>
      <div className="info" style={{marginBottom: 12}}>
        <span>
          <b>İmza / onay akışı:</b> İş Güvenliği Uzmanı → İşyeri Hekimi → İşveren / vekili.
          İşyeri seçince o işyerinin belgeleri ve onaycıları otomatik gelir. Kart/PDF imza ayrıdır.
        </span>
      </div>
      <div className="actions" style={{marginBottom: 12, gap: 8, display: 'flex', flexWrap: 'wrap'}}>
        {eyasOn && (
          <button type="button" className={tab === 'eyas' ? '' : 'secondary'} onClick={() => setTab('eyas')}>
            Onay Akışı (Uzman → Hekim → İşveren)
          </button>
        )}
        <button type="button" className={tab === 'surec' ? '' : 'secondary'} onClick={() => setTab('surec')}>
          Eski kayıt / PDF (pasif kart)
        </button>
        <button type="button" className={tab === 'orch' ? '' : 'secondary'} onClick={() => setTab('orch')}>
          E‑İmza Orkestrasyon
        </button>
      </div>
      {tab === 'eyas' && eyasOn && (
        <EyasDigitalApprovalPage
          user={user}
          mode="full"
          autoOpenCreate={eyasOpenCreate}
          onAutoOpenHandled={() => setEyasOpenCreate(false)}
        />
      )}
      {tab === 'surec' && (
        <DocumentApprovalsPage user={user} onStartSequentialApproval={eyasOn ? startEyasFlow : undefined} />
      )}
      {tab === 'orch' && <ESignCenterPage user={user} />}
    </>
  );
}

function Modal({title, close, children, wide}) {
  return <AppModal title={title} close={close} wide={wide}>{children}</AppModal>;
}

function Field({label, children, ...rest}) {
  if (children) {
    return <label className="field"><span>{label}</span>{children}</label>;
  }
  return <label className="field"><span>{label}</span><input {...rest} /></label>;
}

function dueBadge(status) {
  if (status === 'overdue') return <span className="status-badge badge-danger">Gecikmiş</span>;
  if (status === 'due_soon') return <span className="status-badge badge-warn">Yaklaşıyor</span>;
  if (status === 'ok') return <span className="status-badge badge-ok">Güncel</span>;
  return <span className="status-badge badge-muted">Termin yok</span>;
}

/** ISO yyyy-mm-dd; yıl 2000–2100, takvimde gerçek gün. */
function isSensibleBizDate(value) {
  if (!value) return true;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [y, m, d] = value.split('-').map(Number);
  if (y < 2000 || y > 2100) return false;
  const dt = new Date(y, m - 1, d);
  return dt.getFullYear() === y && dt.getMonth() === m - 1 && dt.getDate() === d;
}

const BIZ_DATE_MIN = '2000-01-01';
const BIZ_DATE_MAX = '2100-12-31';

function useCompanies(user) {
  const [companies, setCompanies] = useState([]);
  useEffect(() => {
    api('/companies').then(setCompanies).catch(() => setCompanies([]));
  }, []);
  return companies;
}

/** Periyodik kontrol + yangın ekipmanı sicili */
export function PeriodicControlsPage({user}) {
  const canEdit = ['safety_specialist', 'global_admin'].includes(user.role);
  const companies = useCompanies(user);
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({categories: []});
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [form, setForm] = useState({
    company_id: user.company_id || '',
    category: 'elektrik',
    equipment_name: '',
    location: '',
    serial_no: '',
    last_control_date: '',
    next_due_date: '',
    control_firm: '',
    report_ref: '',
    result: 'Uygun',
    notes: '',
  });

  async function load() {
    setBusy(true);
    setErr('');
    try {
      const qs = q.trim() ? `?q=${encodeURIComponent(q.trim())}` : '';
      const [m, r] = await Promise.all([
        api('/periodic-controls/meta'),
        api(`/periodic-controls${qs}`),
      ]);
      setMeta(m);
      setRows(r);
    } catch (e) {
      setErr(e.message || 'Yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api('/periodic-controls', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          company_id: Number(form.company_id),
          last_control_date: form.last_control_date || null,
          next_due_date: form.next_due_date || null,
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

  const catLabel = (c) => meta.categories?.find((x) => x.code === c)?.label || c;

  return (
    <>
      <div className="page-title">
        <h3><ClipboardCheck size={20} style={{marginRight: 8, verticalAlign: 'middle'}} />Periyodik Kontrol Sicili</h3>
        <div className="actions">
          <button type="button" className="secondary" disabled={busy} onClick={() => downloadFile('/periodic-controls/export.xlsx', `periyodik-kontrol.xlsx`).catch((e) => setErr(e.message))}>
            <Download size={16} /> Excel
          </button>
          <button type="button" className="secondary" disabled={busy} onClick={() => void load()}><RefreshCw size={16} /> Yenile</button>
          {canEdit && <button type="button" disabled={busy} onClick={() => setOpen(true)}><Plus size={16} /> Yeni Kayıt</button>}
        </div>
      </div>
      <section className="panel">
        <p style={{margin: '0 0 12px', color: '#475569', fontSize: 14}}>
          İş ekipmanı, elektrik, kaldırma, basınçlı kap, asansör ve yangın ekipmanı periyodik kontrolleri.
          Termin yaklaşınca bildirim üretilir. Mevcut risk/plan/tatbikat modüllerini bozmaz.
        </p>
        <div className="search" style={{marginBottom: 12}}>
          <input placeholder="Ekipman, yer, seri no..." value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && load()} />
          <button type="button" className="secondary" onClick={() => void load()}>Ara</button>
        </div>
        {err && <div className="error">{err}</div>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Kategori</th><th>Ekipman</th><th>Yer</th><th>Son Kontrol</th><th>Sonraki</th><th>Firma</th><th>Durum</th>
              </tr>
            </thead>
            <tbody>
              {rows.length ? rows.map((r) => (
                <tr key={r.id}>
                  <td>{catLabel(r.category)}</td>
                  <td>{r.equipment_name}</td>
                  <td>{r.location || '—'}</td>
                  <td>{r.last_control_date || '—'}</td>
                  <td>{r.next_due_date || '—'}</td>
                  <td>{r.control_firm || '—'}</td>
                  <td>{dueBadge(r.review_status)}</td>
                </tr>
              )) : <tr><td colSpan={7} className="empty">Kayıt yok.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
      {open && (
        <Modal title="Periyodik Kontrol Kaydı" close={() => setOpen(false)}>
          <form className="form-grid" onSubmit={save}>
            <Field label="Firma" required>
              <select required value={form.company_id} onChange={(e) => setForm({...form, company_id: e.target.value})}>
                <option value="">Seçiniz</option>
                {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </Field>
            <Field label="Kategori" required>
              <select value={form.category} onChange={(e) => setForm({...form, category: e.target.value})}>
                {(meta.categories || []).map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
              </select>
            </Field>
            <Field label="Ekipman adı" required value={form.equipment_name} onChange={(e) => setForm({...form, equipment_name: e.target.value})} />
            <Field label="Konum" value={form.location} onChange={(e) => setForm({...form, location: e.target.value})} />
            <Field label="Seri / plaka" value={form.serial_no} onChange={(e) => setForm({...form, serial_no: e.target.value})} />
            <Field label="Son kontrol" type="date" value={form.last_control_date} onChange={(e) => setForm({...form, last_control_date: e.target.value})} />
            <Field label="Sonraki termin" type="date" value={form.next_due_date} onChange={(e) => setForm({...form, next_due_date: e.target.value})} />
            <Field label="Kontrol firması" value={form.control_firm} onChange={(e) => setForm({...form, control_firm: e.target.value})} />
            <Field label="Rapor no" value={form.report_ref} onChange={(e) => setForm({...form, report_ref: e.target.value})} />
            <Field label="Sonuç" value={form.result} onChange={(e) => setForm({...form, result: e.target.value})} />
            <Field label="Not" value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})} />
            <div className="form-actions" style={{gridColumn: '1 / -1'}}><button type="submit" disabled={busy}>Kaydet</button></div>
          </form>
        </Modal>
      )}
    </>
  );
}

/** Acil durum planı + kroki */
export function EmergencyPlansPage({user}) {
  const canEdit = ['safety_specialist', 'global_admin'].includes(user.role);
  const companies = useCompanies(user);
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [editPlanId, setEditPlanId] = useState(null);
  const [form, setForm] = useState({
    company_id: user.company_id || '',
    title: 'Acil Durum Planı',
    revision_no: '00',
    plan_date: '',
    next_review_date: '',
    assembly_areas: '',
    scenario_summary: '',
    notes: '',
  });

  async function load() {
    setBusy(true);
    try {
      setRows(await api('/emergency-plans'));
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => { void load(); }, []);

  async function save(e) {
    e.preventDefault();
    setErr('');
    if (!isSensibleBizDate(form.plan_date)) {
      setErr('Plan tarihi geçersiz. 2000–2100 arası gerçek bir tarih girin.');
      return;
    }
    if (!isSensibleBizDate(form.next_review_date)) {
      setErr('Gözden geçirme tarihi geçersiz. 2000–2100 arası gerçek bir tarih girin.');
      return;
    }
    if (form.plan_date && form.next_review_date && form.next_review_date < form.plan_date) {
      setErr('Gözden geçirme tarihi, plan tarihinden önce olamaz.');
      return;
    }
    setBusy(true);
    try {
      const created = await api('/emergency-plans', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          company_id: Number(form.company_id),
          plan_date: form.plan_date || null,
          next_review_date: form.next_review_date || null,
        }),
      });
      setOpen(false);
      await load();
      if (created?.id) setEditPlanId(created.id);
    } catch (x) {
      setErr(x.message);
    } finally {
      setBusy(false);
    }
  }

  async function uploadKroki(row, file) {
    if (!file) return;
    setBusy(true);
    try {
      await uploadFile(`/emergency-plans/${row.id}/kroki`, file);
      await load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function removePlan(row) {
    if (!canEdit || !row?.id) return;
    const label = row.title || `Plan #${row.id}`;
    if (!window.confirm(`«${label}» silinsin mi? Listeden kaldırılır.`)) return;
    setBusy(true);
    setErr('');
    try {
      await api(`/emergency-plans/${row.id}`, {method: 'DELETE'});
      if (editPlanId === row.id) setEditPlanId(null);
      await load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (editPlanId) {
    return (
      <div style={{margin: '0 -8px', width: 'calc(100% + 16px)', maxWidth: 'none'}}>
        <div className="page-title">
          <h3><Map size={20} style={{marginRight: 8, verticalAlign: 'middle'}} />Acil Durum Kroki Studio</h3>
        </div>
        <section className="panel" style={{borderTop: '3px solid #0f766e', padding: 12, maxWidth: 'none'}}>
          <EmergencyKrokiEditor
            planId={editPlanId}
            user={user}
            onClose={() => { setEditPlanId(null); void load(); }}
          />
        </section>
      </div>
    );
  }

  return (
    <>
      <div className="page-title">
        <h3><FileWarning size={20} style={{marginRight: 8, verticalAlign: 'middle'}} />Acil Durum Planı</h3>
        <div className="actions">
          <button type="button" className="secondary" onClick={() => downloadFile('/emergency-plans/export.xlsx', 'acil-durum-plani.xlsx').catch((e) => setErr(e.message))}><Download size={16} /> Excel</button>
          <button type="button" className="secondary" onClick={() => void load()}><RefreshCw size={16} /> Yenile</button>
          {canEdit && <button type="button" onClick={() => setOpen(true)}><Plus size={16} /> Yeni Plan</button>}
        </div>
      </div>
      <section className="panel">
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0,1.4fr) minmax(220px,0.8fr)',
          gap: 16,
          marginBottom: 18,
          padding: '16px 18px',
          borderRadius: 14,
          border: '1px solid #d1e7e3',
          background: 'linear-gradient(135deg, #f0fdfa 0%, #f8fafc 55%, #fff 100%)',
        }}>
          <div>
            <div style={{fontSize: 12, letterSpacing: '.06em', textTransform: 'uppercase', color: '#0f766e', fontWeight: 700, marginBottom: 6}}>
              Akıllı Acil Durum Krokisi · v2.2 Pro (ISO 7010 / 23601)
            </div>
            <div style={{fontSize: 18, fontWeight: 760, color: '#0f172a', marginBottom: 6}}>
              Acil Durum Kroki Studio
            </div>
            <p style={{margin: 0, color: '#475569', fontSize: 14, lineHeight: 1.55, maxWidth: 640}}>
              Kat planı yükleyin, ofis/atölye şablonu veya akıllı tahliye asistanı kullanın; çizgi kaçış okları, ölçü, hilal ilk yardım ve mevzuat paneliyle duvar posteri üretin.
            </p>
          </div>
          <div style={{display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 8, fontSize: 13, color: '#334155'}}>
            <div><strong>A.</strong> Yeni Plan → plan fotoğrafı veya şablon</div>
            <div><strong>B.</strong> Akıllı tahliye → kontrol skoru</div>
            <div><strong>C.</strong> PNG poster · kilitle · Eyas onayı</div>
          </div>
        </div>
        {err && <div className="error">{err}</div>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Plan</th>
                <th>Rev</th>
                <th>Tarihler</th>
                <th>Toplanma</th>
                <th>Kroki durumu</th>
                <th>Durum</th>
                <th style={{minWidth: 220}}>İşlem</th>
              </tr>
            </thead>
            <tbody>
              {rows.length ? rows.map((r) => {
                const krokiReady = !!(r.has_scene || r.kroki_file_name);
                return (
                  <tr key={r.id}>
                    <td>
                      <div style={{fontWeight: 650}}>{r.title}</div>
                      <div style={{fontSize: 12, color: '#64748b'}}>{r.floor_count ?? 0} kat</div>
                    </td>
                    <td>{r.revision_no}</td>
                    <td style={{fontSize: 13}}>
                      <div>Plan: {r.plan_date || '—'}</div>
                      <div>Gözden geçirme: {r.next_review_date || '—'} {dueBadge(r.review_status)}</div>
                    </td>
                    <td>{r.assembly_areas || '—'}</td>
                    <td>
                      <div style={{display: 'flex', flexWrap: 'wrap', gap: 6}}>
                        <span className={`badge ${krokiReady ? 'ok' : 'off'}`}>
                          {krokiReady ? 'Kroki hazır' : 'Kroki yok'}
                        </span>
                        {r.locked_at && <span className="badge off">Kilitli</span>}
                        {r.kroki_file_name && (
                          <span style={{fontSize: 12, color: '#64748b'}} title={r.kroki_file_name}>Poster dosyası</span>
                        )}
                      </div>
                    </td>
                    <td>{r.status}</td>
                    <td>
                      <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center'}}>
                        <button
                          type="button"
                          className="mini"
                          onClick={() => setEditPlanId(r.id)}
                          style={{display: 'inline-flex', alignItems: 'center', gap: 6}}
                        >
                          <Map size={14} /> Kroki Studio
                        </button>
                        {canEdit && (
                          <label className="button secondary mini" style={{cursor: 'pointer'}} title="Hazır PNG/PDF yükle (opsiyonel)">
                            <Upload size={14} /> Dosya yükle
                            <input type="file" hidden accept=".png,.jpg,.jpeg,.pdf,.webp" onChange={(e) => { uploadKroki(r, e.target.files?.[0]); e.target.value = ''; }} />
                          </label>
                        )}
                        {canEdit && (
                          <button type="button" className="mini" disabled={busy} onClick={() => void removePlan(r)}>
                            <Trash2 size={14} /> Sil
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              }) : (
                <tr>
                  <td colSpan={7} className="empty">
                    Henüz plan yok. Yeni Plan ile kaydı oluşturun; ardından <strong>Kroki Studio</strong> açılır.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
      {open && (
        <Modal title="Acil Durum Planı" close={() => setOpen(false)} wide>
          <form className="form-grid" onSubmit={save}>
            <Field label="Firma" required>
              <select required value={form.company_id} onChange={(e) => setForm({...form, company_id: e.target.value})}>
                <option value="">Seçiniz</option>
                {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </Field>
            <Field label="Başlık" required value={form.title} onChange={(e) => setForm({...form, title: e.target.value})} />
            <Field label="Revizyon" value={form.revision_no} onChange={(e) => setForm({...form, revision_no: e.target.value})} />
            <Field
              label="Plan tarihi"
              type="date"
              min={BIZ_DATE_MIN}
              max={BIZ_DATE_MAX}
              value={form.plan_date}
              onChange={(e) => setForm({...form, plan_date: e.target.value})}
            />
            <Field
              label="Gözden geçirme"
              type="date"
              min={form.plan_date || BIZ_DATE_MIN}
              max={BIZ_DATE_MAX}
              value={form.next_review_date}
              onChange={(e) => setForm({...form, next_review_date: e.target.value})}
            />
            <Field label="Toplanma alanları" value={form.assembly_areas} onChange={(e) => setForm({...form, assembly_areas: e.target.value})} />
            <label className="field" style={{gridColumn: '1 / -1'}}>
              <span>Senaryo özeti</span>
              <textarea rows={4} value={form.scenario_summary} onChange={(e) => setForm({...form, scenario_summary: e.target.value})} />
            </label>
            {err && <div className="error" style={{gridColumn: '1 / -1'}}>{err}</div>}
            <div className="form-actions" style={{gridColumn: '1 / -1'}}><button type="submit" disabled={busy}>Kaydet</button></div>
          </form>
        </Modal>
      )}
    </>
  );
}

/** Ortam ölçüm defteri */
export function WorkplaceMeasurementsPage({user}) {
  const canEdit = ['safety_specialist', 'global_admin'].includes(user.role);
  const physicianReadOnly = user.role === 'workplace_physician';
  const companies = useCompanies(user);
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({types: []});
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [form, setForm] = useState({
    company_id: user.company_id || '',
    measurement_type: 'gurultu',
    location: '',
    measured_at: '',
    value: '',
    unit: '',
    limit_value: '',
    lab_name: '',
    report_ref: '',
    next_due_date: '',
    notes: '',
  });

  async function load() {
    setBusy(true);
    try {
      const [m, r] = await Promise.all([api('/workplace-measurements/meta'), api('/workplace-measurements')]);
      setMeta(m);
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
    setBusy(true);
    try {
      await api('/workplace-measurements', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          company_id: Number(form.company_id),
          measured_at: form.measured_at,
          next_due_date: form.next_due_date || null,
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

  const typeLabel = (c) => meta.types?.find((x) => x.code === c)?.label || c;

  return (
    <>
      <div className="page-title">
        <h3>Ortam Ölçüm Defteri</h3>
        <div className="actions">
          <button type="button" className="secondary" onClick={() => downloadFile('/workplace-measurements/export.xlsx', 'ortam-olcum.xlsx').catch((e) => setErr(e.message))}><Download size={16} /> Excel</button>
          <button type="button" className="secondary" onClick={() => void load()}><RefreshCw size={16} /> Yenile</button>
          {canEdit && <button type="button" onClick={() => setOpen(true)}><Plus size={16} /> Yeni Ölçüm</button>}
        </div>
      </div>
      {physicianReadOnly && <p className="muted" style={{margin: '0 0 12px'}}>
        Atandığınız işyerinin ortam ölçüm kayıtları iş güvenliği uzmanı tarafından girilir; bu ekranda yalnızca görüntüleyebilirsiniz.
      </p>}
      <section className="panel">
        <p style={{margin: '0 0 12px', color: '#475569', fontSize: 14}}>
          Gürültü, toz, kimyasal, aydınlatma vb. ölçümleri; laboratuvar, limit ve sonraki ölçüm terminleri.
        </p>
        {err && <div className="error">{err}</div>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Tür</th><th>Yer</th><th>Tarih</th><th>Değer</th><th>Limit</th><th>Laboratuvar</th><th>Sonraki</th><th>Durum</th></tr>
            </thead>
            <tbody>
              {rows.length ? rows.map((r) => (
                <tr key={r.id}>
                  <td>{typeLabel(r.measurement_type)}</td>
                  <td>{r.location || '—'}</td>
                  <td>{r.measured_at}</td>
                  <td>{r.value || '—'} {r.unit || ''}</td>
                  <td>{r.limit_value || '—'}</td>
                  <td>{r.lab_name || '—'}</td>
                  <td>{r.next_due_date || '—'}</td>
                  <td>{dueBadge(r.review_status)}</td>
                </tr>
              )) : <tr><td colSpan={8} className="empty">Ölçüm kaydı yok.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
      {open && (
        <Modal title="Ortam Ölçümü" close={() => setOpen(false)}>
          <form className="form-grid" onSubmit={save}>
            <Field label="Firma" required>
              <select required value={form.company_id} onChange={(e) => setForm({...form, company_id: e.target.value})}>
                <option value="">Seçiniz</option>
                {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </Field>
            <Field label="Tür" required>
              <select value={form.measurement_type} onChange={(e) => setForm({...form, measurement_type: e.target.value})}>
                {(meta.types || []).map((t) => <option key={t.code} value={t.code}>{t.label}</option>)}
              </select>
            </Field>
            <Field label="Yer" value={form.location} onChange={(e) => setForm({...form, location: e.target.value})} />
            <Field label="Ölçüm tarihi" type="date" required value={form.measured_at} onChange={(e) => setForm({...form, measured_at: e.target.value})} />
            <Field label="Değer" value={form.value} onChange={(e) => setForm({...form, value: e.target.value})} />
            <Field label="Birim" value={form.unit} onChange={(e) => setForm({...form, unit: e.target.value})} />
            <Field label="Limit" value={form.limit_value} onChange={(e) => setForm({...form, limit_value: e.target.value})} />
            <Field label="Laboratuvar" value={form.lab_name} onChange={(e) => setForm({...form, lab_name: e.target.value})} />
            <Field label="Rapor no" value={form.report_ref} onChange={(e) => setForm({...form, report_ref: e.target.value})} />
            <Field label="Sonraki ölçüm" type="date" value={form.next_due_date} onChange={(e) => setForm({...form, next_due_date: e.target.value})} />
            <div className="form-actions" style={{gridColumn: '1 / -1'}}><button type="submit" disabled={busy}>Kaydet</button></div>
          </form>
        </Modal>
      )}
    </>
  );
}

/** İSG Kurulu + çalışan temsilcisi — profesyonel üye seçimi ve toplantı yönetimi */
export function OhsCommitteePage({user}) {
  const canEdit = ['safety_specialist', 'global_admin'].includes(user.role);
  const companies = useCompanies(user);
  const [selectedCompanyId, setSelectedCompanyId] = useState(user.company_id ? String(user.company_id) : '');
  const [candidates, setCandidates] = useState({mandatory: [], other: [], missing_mandatory: []});
  const [members, setMembers] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [meta, setMeta] = useState({roles: []});
  const [tab, setTab] = useState('uyeler');
  const [open, setOpen] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [success, setSuccess] = useState('');
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [memberForm, setMemberForm] = useState({role_code: 'calisan_temsilcisi', start_date: '', notes: ''});
  const [meetingForm, setMeetingForm] = useState({
    meeting_date: '', next_meeting_date: '', title: 'İSG Kurulu Toplantısı', meeting_no: '',
    document_no: '', revision_no: '00', status: 'draft', signature_status: 'not_signed',
    start_time: '', end_time: '', location: '', meeting_type: 'Olağan', agenda: '', decisions: '', notes: '',
  });

  const selectedCompany = companies.find((c) => String(c.id) === String(selectedCompanyId));
  const selectedKeys = new Set(members.map((m) => m.identity_key).filter(Boolean));
  const mandatoryComplete = (candidates.missing_mandatory || []).length === 0;

  async function load(companyId = selectedCompanyId) {
    setBusy(true); setErr('');
    try {
      const m = await api('/ohs-committee/meta'); setMeta(m);
      if (!companyId) { setCandidates({mandatory: [], other: [], missing_mandatory: []}); setMembers([]); setMeetings([]); return; }
      const qs = `?company_id=${encodeURIComponent(companyId)}`;
      const [cand, mem, meet] = await Promise.all([
        api(`/ohs-committee/candidates${qs}`),
        api(`/ohs-committee/members/detail${qs}`),
        api(`/ohs-committee/meetings${qs}`),
      ]);
      setCandidates(cand || {mandatory: [], other: [], missing_mandatory: []});
      setMembers(mem || []); setMeetings(meet || []);
    } catch (e) { setErr(e.message || 'İSG Kurulu bilgileri yüklenemedi.'); }
    finally { setBusy(false); }
  }
  useEffect(() => { void load(selectedCompanyId); }, [selectedCompanyId]);

  function chooseCompany(value) {
    setSelectedCompanyId(value); setOpen(''); setSelectedCandidate(null); setErr(''); setSuccess('');
    setMeetingForm((f) => ({...f, meeting_date: '', next_meeting_date: '', agenda: '', decisions: '', notes: ''}));
  }

  function selectCandidate(candidate) {
    if (!candidate || candidate.missing) return;
    if (candidate.selected || selectedKeys.has(candidate.identity_key)) {
      setErr('Bu kişi kurula daha önce eklenmiştir.'); return;
    }
    setErr(''); setSelectedCandidate(candidate);
    setMemberForm({role_code: candidate.suggested_role_code || 'diger', start_date: '', notes: ''});
  }

  async function saveMember(e) {
    e.preventDefault();
    if (!selectedCandidate || busy) return;
    setBusy(true); setErr(''); setSuccess('');
    try {
      await api('/ohs-committee/members/validated', {method: 'POST', body: JSON.stringify({
        company_id: Number(selectedCompanyId), role_code: memberForm.role_code,
        source_type: selectedCandidate.source_type, source_id: selectedCandidate.source_id || null,
        full_name: selectedCandidate.full_name || null, corporate_email: selectedCandidate.corporate_email || null,
        start_date: memberForm.start_date || null, notes: memberForm.notes || null,
      })});
      setSelectedCandidate(null); setSuccess('Kurul üyesi güvenli biçimde eklendi.'); await load(selectedCompanyId);
    } catch (e) { setErr(e.message || 'Kurul üyesi kaydedilemedi.'); }
    finally { setBusy(false); }
  }

  async function removeMember(row) {
    if (!window.confirm(`${row.full_name} kurul üyeliğinden çıkarılsın mı? Tarihsel toplantı snapshotları korunur.`)) return;
    setBusy(true); setErr('');
    try { await api(`/ohs-committee/members/${row.id}`, {method: 'DELETE'}); await load(selectedCompanyId); }
    catch (e) { setErr(e.message || 'Üye çıkarılamadı.'); }
    finally { setBusy(false); }
  }

  async function saveMeeting(e) {
    e.preventDefault(); if (!selectedCompanyId || busy) return;
    setBusy(true); setErr(''); setSuccess('');
    try {
      await api('/ohs-committee/meetings/validated', {method: 'POST', body: JSON.stringify({
        ...meetingForm, company_id: Number(selectedCompanyId), next_meeting_date: meetingForm.next_meeting_date || null,
        start_time: meetingForm.start_time || null, end_time: meetingForm.end_time || null,
        location: meetingForm.location || null, meeting_no: meetingForm.meeting_no || null,
        document_no: meetingForm.document_no || null,
      })});
      setOpen(''); setSuccess('Toplantı kaydedildi ve üye listesi tarihsel snapshot olarak sabitlendi.'); await load(selectedCompanyId);
    } catch (e) { setErr(e.message || 'Kurul toplantısı kaydedilemedi.'); }
    finally { setBusy(false); }
  }

  const roleLabel = (code) => meta.roles?.find((x) => x.code === code)?.label || ({sekreter:'Kurul Sekreteri', baskan:'Kurul Başkanı'}[code] || code);
  const filteredOther = (candidates.other || []).filter((c) => {
    const hay = `${c.full_name || ''} ${c.job_title || ''} ${c.department || ''}`.toLocaleLowerCase('tr-TR');
    return (!search || hay.includes(search.toLocaleLowerCase('tr-TR'))) && (!roleFilter || c.suggested_role_code === roleFilter);
  });
  const plannedCount = meetings.filter((m) => m.meeting_date && new Date(m.meeting_date) >= new Date(new Date().toDateString())).length;

  function CandidateCard({candidate}) {
    if (candidate.missing) return <div className="committee-warning" role="alert"><strong>{roleLabel(candidate.suggested_role_code)}</strong><span>{candidate.message}</span></div>;
    const disabled = candidate.selected || selectedKeys.has(candidate.identity_key);
    const initials = (candidate.full_name || '?').split(/\s+/).slice(0,2).map((x) => x[0]).join('').toUpperCase();
    return <button type="button" className={`committee-person-card ${disabled ? 'is-disabled' : ''}`} disabled={disabled} onClick={() => selectCandidate(candidate)} aria-label={`${candidate.full_name} kurul üyesi olarak seç`}>
      <span className="committee-avatar" aria-hidden="true">{initials}</span>
      <span className="committee-person-main"><strong>{candidate.full_name}</strong><small>{candidate.job_title || candidate.professional_role || 'Personel'}</small><small>{candidate.company_name}</small></span>
      <span className="committee-person-meta">{candidate.mandatory && <span className="status-badge badge-warn">Zorunlu</span>}<span className={`status-badge ${disabled ? 'badge-muted' : 'badge-ok'}`}>{disabled ? 'Seçildi' : 'Seçilebilir'}</span></span>
    </button>;
  }

  return <>
    <div className="page-title committee-page-title">
      <div><h3><Users size={20} /> İSG Kurulu Toplantıları</h3><p>İSG kurullarını, üyeleri, gündemleri, kararları, imza ve takip süreçlerini yönetin.</p></div>
      <div className="actions">
        <button type="button" className="secondary" disabled={busy} onClick={() => void load()}><RefreshCw size={16}/> Yenile</button>
        {canEdit && <button type="button" disabled={!selectedCompanyId || busy} onClick={() => {setTab('uyeler'); setOpen('member');}}><Plus size={16}/> Üye Yönet</button>}
        {canEdit && <button type="button" disabled={!selectedCompanyId || busy} onClick={() => {setTab('toplantilar'); setOpen('meeting');}}><Plus size={16}/> Toplantı Planla</button>}
      </div>
    </div>
    <section className="panel committee-filter-panel">
      <Field label="İşyeri (zorunlu)" required><select required value={selectedCompanyId} onChange={(e) => chooseCompany(e.target.value)}><option value="">İşyeri seçiniz</option>{companies.map((c)=><option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
    </section>
    {selectedCompanyId && <div className="committee-summary-grid">
      <div className="committee-summary"><span>Aktif Üyeler</span><strong>{members.length}</strong></div>
      <div className="committee-summary"><span>Planlı Toplantılar</span><strong>{plannedCount}</strong></div>
      <div className="committee-summary"><span>Toplam Toplantı</span><strong>{meetings.length}</strong></div>
      <div className={`committee-summary ${mandatoryComplete ? 'is-complete' : 'is-alert'}`}><span>Zorunlu Üyeler</span><strong>{mandatoryComplete ? 'Tam' : `${candidates.missing_mandatory?.length || 0} Eksik`}</strong></div>
    </div>}
    {err && <div className="error" role="alert">{err}</div>}{success && <div className="info" role="status">{success}</div>}
    <section className="panel">
      <div className="committee-tabs"><button type="button" className={tab==='uyeler'?'':'secondary'} onClick={()=>setTab('uyeler')}>Kurul Üyeleri ({members.length})</button><button type="button" className={tab==='toplantilar'?'':'secondary'} onClick={()=>setTab('toplantilar')}>Toplantılar ({meetings.length})</button></div>
      {!selectedCompanyId ? <div className="empty">Kurul verilerini görüntülemek için işyeri seçiniz.</div> : tab === 'uyeler' ? <div className="committee-selected-list">
        {!mandatoryComplete && <div className="committee-warning" role="alert"><strong>Kurul eksik</strong><span>Eksik zorunlu üyeler: {(candidates.missing_mandatory || []).join(', ')}</span></div>}
        {members.length ? members.map((m)=><div key={m.id} className="committee-selected-card"><span className="committee-avatar">{m.full_name.split(/\s+/).slice(0,2).map((x)=>x[0]).join('').toUpperCase()}</span><span><strong>{m.full_name}</strong><small>{m.job_title_snapshot || m.professional_role_snapshot || '—'}</small><small>{roleLabel(m.role_code)}</small></span><span className="committee-person-meta">{m.is_mandatory && <span className="status-badge badge-warn">Zorunlu</span>}{canEdit && <button type="button" className="mini secondary" disabled={busy} onClick={()=>void removeMember(m)} aria-label={`${m.full_name} üyesini kaldır`}><Trash2 size={14}/> Kaldır</button>}</span></div>) : <div className="empty">Bu işyerinde kurul üyesi bulunmuyor.</div>}
      </div> : <div className="table-wrap"><table><thead><tr><th>Tarih</th><th>Gündem</th><th>Kararlar</th><th>Katılımcılar</th><th>Sonraki</th><th>İşlem</th></tr></thead><tbody>{meetings.length ? meetings.map((m)=><tr key={m.id}><td>{m.meeting_date}</td><td>{m.agenda || '—'}</td><td>{m.decisions || '—'}</td><td>{m.attendees || '—'}</td><td>{m.next_meeting_date || '—'}</td><td><button type="button" className="mini secondary" onClick={()=>downloadFile(`/ohs-committee/meetings/${m.id}/pdf`, `OHS_Committee_Meeting_${selectedCompany?.name || 'Workplace'}_${m.id}.pdf`).catch((e)=>setErr(e.message))}><Download size={14}/> PDF</button></td></tr>) : <tr><td colSpan={6} className="empty">Toplantı kaydı yok.</td></tr>}</tbody></table></div>}
    </section>
    {open === 'member' && <Modal title={`Kurul Üyesi Seçimi — ${selectedCompany?.name || ''}`} close={()=>{setOpen(''); setSelectedCandidate(null);}} wide>
      <div className="committee-member-picker">
        <div className="committee-available"><div className="committee-picker-tools"><input placeholder="Ad, görev veya departman ara" value={search} onChange={(e)=>setSearch(e.target.value)}/><select value={roleFilter} onChange={(e)=>setRoleFilter(e.target.value)}><option value="">Tüm görevler</option><option value="calisan_temsilcisi">Çalışan Temsilcisi</option><option value="destek">Destek Elemanı</option><option value="diger">Diğer</option></select></div><h4>Zorunlu Kurul Üyeleri</h4><div className="committee-card-list">{(candidates.mandatory || []).map((c,i)=><CandidateCard key={c.identity_key || `missing-${i}`} candidate={c}/>)}</div><h4>Diğer Kurul Üyeleri</h4><div className="committee-card-list">{filteredOther.length ? filteredOther.map((c)=><CandidateCard key={c.identity_key} candidate={c}/>) : <div className="empty">Uygun personel bulunamadı.</div>}</div></div>
        <div className="committee-selection"><h4>Seçilen Kişi</h4>{selectedCandidate ? <form onSubmit={saveMember} className="form-grid"><div className="committee-selected-card"><span className="committee-avatar">{selectedCandidate.full_name.split(/\s+/).slice(0,2).map((x)=>x[0]).join('').toUpperCase()}</span><span><strong>{selectedCandidate.full_name}</strong><small>{selectedCandidate.job_title || selectedCandidate.professional_role || '—'}</small></span></div><Field label="Kurul görevi" required><select value={memberForm.role_code} onChange={(e)=>setMemberForm({...memberForm,role_code:e.target.value})}>{(meta.roles || []).map((r)=><option key={r.code} value={r.code}>{r.label}</option>)}<option value="baskan">Kurul Başkanı</option><option value="sekreter">Kurul Sekreteri</option></select></Field><Field label="Başlangıç" type="date" value={memberForm.start_date} onChange={(e)=>setMemberForm({...memberForm,start_date:e.target.value})}/><label className="field"><span>Not</span><textarea rows={3} value={memberForm.notes} onChange={(e)=>setMemberForm({...memberForm,notes:e.target.value})}/></label><div className="form-actions"><button type="submit" disabled={busy}>{busy ? 'Kaydediliyor…' : 'Kurula Ekle'}</button></div></form> : <div className="empty">Soldaki listeden bir kişi seçiniz.</div>}</div>
      </div>
    </Modal>}
    {open === 'meeting' && <Modal title={`Yeni İSG Kurulu Toplantısı — ${selectedCompany?.name || ''}`} close={()=>setOpen('')} wide><form className="form-grid committee-meeting-form" onSubmit={saveMeeting}>{!mandatoryComplete && <div className="committee-warning" role="alert"><strong>Resmî durum engeli</strong><span>Eksik zorunlu üyeler tamamlanmadan toplantı yalnız Taslak olarak kaydedilebilir.</span></div>}<Field label="Toplantı tarihi" type="date" required value={meetingForm.meeting_date} onChange={(e)=>setMeetingForm({...meetingForm,meeting_date:e.target.value})}/><Field label="Toplantı no" value={meetingForm.meeting_no} onChange={(e)=>setMeetingForm({...meetingForm,meeting_no:e.target.value})}/><Field label="Belge no" value={meetingForm.document_no} onChange={(e)=>setMeetingForm({...meetingForm,document_no:e.target.value})}/><Field label="Revizyon" value={meetingForm.revision_no} onChange={(e)=>setMeetingForm({...meetingForm,revision_no:e.target.value})}/><Field label="Başlangıç" type="time" value={meetingForm.start_time} onChange={(e)=>setMeetingForm({...meetingForm,start_time:e.target.value})}/><Field label="Bitiş" type="time" value={meetingForm.end_time} onChange={(e)=>setMeetingForm({...meetingForm,end_time:e.target.value})}/><Field label="Toplantı yeri" value={meetingForm.location} onChange={(e)=>setMeetingForm({...meetingForm,location:e.target.value})}/><Field label="Sonraki toplantı" type="date" value={meetingForm.next_meeting_date} onChange={(e)=>setMeetingForm({...meetingForm,next_meeting_date:e.target.value})}/><Field label="Durum" required><select value={meetingForm.status} onChange={(e)=>setMeetingForm({...meetingForm,status:e.target.value})}><option value="draft">Taslak</option><option value="active" disabled={!mandatoryComplete}>Aktif</option><option value="completed" disabled={!mandatoryComplete}>Tamamlandı</option></select></Field><label className="field committee-span"><span>Gündem</span><textarea rows={5} value={meetingForm.agenda} onChange={(e)=>setMeetingForm({...meetingForm,agenda:e.target.value})}/></label><label className="field committee-span"><span>Kararlar</span><textarea rows={6} value={meetingForm.decisions} onChange={(e)=>setMeetingForm({...meetingForm,decisions:e.target.value})}/></label><label className="field committee-span"><span>Notlar</span><textarea rows={3} value={meetingForm.notes} onChange={(e)=>setMeetingForm({...meetingForm,notes:e.target.value})}/></label><div className="form-actions committee-span"><button type="submit" disabled={busy || !meetingForm.meeting_date}>{busy ? 'Kaydediliyor…' : 'Toplantıyı Kaydet'}</button></div></form></Modal>}
  </>;
}

/** Belge onay / imza hazırlık (5070 sağlayıcı olmadan süreç) */
export function DocumentApprovalsPage({user, onStartSequentialApproval}) {
  const canEdit = ['safety_specialist', 'global_admin'].includes(user.role);
  const companies = useCompanies(user);
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState('');
  const [signer, setSigner] = useState({ok: false, checking: true, data: null, error: ''});
  const [signBusy, setSignBusy] = useState(null);
  const [form, setForm] = useState({
    company_id: user.company_id || '',
    document_title: '',
    document_kind: 'risk',
    approver_name: '',
    approver_role: 'İşveren / vekili',
    status: 'Bekliyor',
  });

  async function refreshSigner() {
    setSigner((s) => ({...s, checking: true}));
    const r = await probeIsgSigner();
    setSigner({ok: !!r.ok, checking: false, data: r.data || null, error: r.error || ''});
  }

  async function load() {
    try {
      setRows(await api('/document-approvals'));
    } catch (e) {
      setErr(e.message);
    }
  }
  useEffect(() => { void load(); void refreshSigner(); }, []);

  async function save(e) {
    e.preventDefault();
    await api('/document-approvals', {
      method: 'POST',
      body: JSON.stringify({...form, company_id: Number(form.company_id)}),
    });
    setOpen(false);
    await load();
  }

  async function approve(id) {
    await api(`/document-approvals/${id}/approve`, {method: 'POST'});
    await load();
  }

  async function remove(row) {
    const title = row.document_title || `#${row.id}`;
    if (!window.confirm(`“${title}” onay kaydı silinsin mi?`)) return;
    setErr('');
    try {
      await api(`/document-approvals/${row.id}`, {method: 'DELETE'});
      await load();
    } catch (e) {
      setErr(e.message || 'Silinemedi.');
    }
  }

  async function localSign(row) {
    if (!signer.ok) {
      setErr('OSGB Signer bağlı değil. tools/isg-suite-signer → KUR.bat çalıştırın (port 17000).');
      return;
    }
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'application/pdf,.pdf';
    input.onchange = async () => {
      const file = input.files && input.files[0];
      if (!file) return;
      setSignBusy(row.id);
      setErr('');
      try {
        // 1) Sunucu: tek kullanımlık imza talebi
        const req = await uploadFile('/esign/requests', file, {
          company_id: row.company_id,
          document_title: row.document_title || file.name,
          document_kind: row.document_kind || 'genel',
          approval_id: row.id,
        });

        // 2) Agent: PKCS#11 veya demo (PIN yalnızca yerelde)
        const buf = await file.arrayBuffer();
        const usePkcs11 = !!(signer.data && signer.data.pkcs11_configured);
        let pin;
        if (usePkcs11) {
          pin = window.prompt('E-imza kartı PIN (yalnızca bu bilgisayarda kullanılır, sunucuya gitmez):') || '';
          if (!pin) throw new Error('PIN girilmedi.');
        }
        const signed = await signPdfWithIsgSigner(buf, {
          documentTitle: row.document_title,
          reason: `OSGB — ${row.document_title}`,
          requestToken: req.one_time_token,
          expectedSha256: req.source_sha256,
          certId: usePkcs11 ? 'pkcs11' : 'demo',
          pin,
        });

        // 3) Sunucu: doğrulama · OCSP/CRL · TSA · kilit · denetim
        await api('/esign/complete', {
          method: 'POST',
          body: JSON.stringify({
            one_time_token: req.one_time_token,
            signed_pdf_base64: signed.signed_pdf_base64,
            agent_mode: signed.mode,
            agent_signature_id: signed.signature_id,
            signer_cn: signed.signer?.common_name,
            signer_subject: signed.signer?.subject,
            cert_serial: signed.signer?.serial,
            cert_sha256: signed.signer?.sha256,
            mark_approval: true,
          }),
        });
        downloadBase64Pdf(signed.signed_pdf_base64, `${row.document_title || 'belge'}-imzali.pdf`);
        await load();
      } catch (e) {
        setErr(e.message || 'E-imza hattı başarısız.');
      } finally {
        setSignBusy(null);
      }
    };
    input.click();
  }

  return (
    <>
      <div className="page-title">
        <h3>Belge Onay / İmza Hazırlık</h3>
        <div className="actions">
          <button type="button" className="secondary" onClick={() => { void load(); void refreshSigner(); }}><RefreshCw size={16} /> Yenile</button>
          {canEdit && onStartSequentialApproval && (
            <button type="button" onClick={() => onStartSequentialApproval()}>
              <Plus size={16} /> Onay Akışı Başlat (Uzman→Hekim→İşveren)
            </button>
          )}
          {canEdit && !onStartSequentialApproval && (
            <button type="button" onClick={() => setOpen(true)}><Plus size={16} /> Onay Kaydı</button>
          )}
        </div>
      </div>
      <section className="panel">
        <p style={{margin: '0 0 12px', color: '#475569', fontSize: 14}}>
          Bu ekranda şimdilik yalnızca <b>Onayla</b> kullanın. Sıralı onay (uzman → hekim → işveren) için üstteki
          <b> Dijital Onay (Eyas)</b> sekmesine geçin. Kart / PDF imza geçici olarak kapalıdır.
        </p>
        <div style={{
          marginBottom: 12, padding: '10px 12px', borderRadius: 8,
          background: '#f8fafc', border: '1px solid #e2e8f0', fontSize: 13, color: '#64748b',
        }}>
          <strong>Kart / PDF İmzala:</strong> şimdilik pasif (kart yok / hatası var). İleride açılacak.
          {signer.ok ? ` OSGB Signer bağlı (${signer.data?.version || '?'}${signer.data?.demo_mode ? ', demo' : ''}).` : ''}
        </div>
        {err && <div className="error">{err}</div>}
        <div className="table-wrap">
          <table>
            <thead><tr><th>Belge</th><th>Tür</th><th>Onaylayan</th><th>Rol</th><th>Durum</th><th>Tarih</th><th></th></tr></thead>
            <tbody>
              {rows.length ? rows.map((r) => (
                <tr key={r.id}>
                  <td>
                    {r.document_title}
                    {r.signature_note && <div style={{fontSize: 11, color: '#64748b', marginTop: 4}}>{r.signature_note}</div>}
                  </td>
                  <td>{r.document_kind}</td>
                  <td>{r.approver_name}</td>
                  <td>{r.approver_role || '—'}</td>
                  <td>{r.status}</td>
                  <td>{r.approved_at || '—'}</td>
                  <td style={{whiteSpace: 'nowrap'}}>
                    {canEdit && r.status !== 'Onaylandı' && (
                      <>
                        <button type="button" className="mini" onClick={() => approve(r.id)}>Onayla</button>{' '}
                        <button
                          type="button"
                          className="mini secondary"
                          disabled
                          title="Geçici olarak kapalı — kart/PDF imza kullanılmıyor. Onayla veya Eyas sekmesini kullanın."
                        >
                          Kart / PDF İmzala (pasif)
                        </button>{' '}
                      </>
                    )}
                    {canEdit && (
                      <button type="button" className="mini secondary" onClick={() => void remove(r)} title="Kaydı listeden kaldır">
                        Sil
                      </button>
                    )}
                  </td>
                </tr>
              )) : <tr><td colSpan={7} className="empty">Onay kaydı yok.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
      {open && (
        <Modal title="Belge Onay Kaydı" close={() => setOpen(false)}>
          <form className="form-grid" onSubmit={save}>
            <Field label="Firma" required>
              <select required value={form.company_id} onChange={(e) => setForm({...form, company_id: e.target.value})}>
                <option value="">Seçiniz</option>
                {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </Field>
            <Field label="Belge başlığı" required value={form.document_title} onChange={(e) => setForm({...form, document_title: e.target.value})} />
            <Field label="Tür" value={form.document_kind} onChange={(e) => setForm({...form, document_kind: e.target.value})} />
            <Field label="Onaylayan" required value={form.approver_name} onChange={(e) => setForm({...form, approver_name: e.target.value})} />
            <Field label="Rol" value={form.approver_role} onChange={(e) => setForm({...form, approver_role: e.target.value})} />
            <div className="form-actions" style={{gridColumn: '1 / -1'}}><button type="submit">Kaydet</button></div>
          </form>
        </Modal>
      )}
    </>
  );
}
