import React, {useEffect, useState} from 'react';
import {ClipboardCheck, Download, FileWarning, Plus, RefreshCw, Upload, Users} from 'lucide-react';
import {
  downloadBase64Pdf,
  probeIsgSigner,
  signPdfWithIsgSigner,
} from './isg_signer_agent';
import {api, downloadFile, uploadFile} from './api';
import {AppModal} from './ui_modal';
import {ESignCenterPage} from './esign_center';

/** Belge Onay hub: süreç onayı (mevcut) + e-imza orkestrasyon (Desktop birleşimi). Bozmadan yan yana. */
export function BelgeOnayHub({user}) {
  const [tab, setTab] = useState('surec');
  return (
    <>
      <div className="actions" style={{marginBottom: 12, gap: 8, display: 'flex', flexWrap: 'wrap'}}>
        <button type="button" className={tab === 'surec' ? '' : 'secondary'} onClick={() => setTab('surec')}>
          Süreç Onayı / PDF İmza
        </button>
        <button type="button" className={tab === 'orch' ? '' : 'secondary'} onClick={() => setTab('orch')}>
          E‑İmza Orkestrasyon
        </button>
      </div>
      {tab === 'surec' ? <DocumentApprovalsPage user={user} /> : <ESignCenterPage user={user} />}
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
    setBusy(true);
    try {
      await api('/emergency-plans', {
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
        <p style={{margin: '0 0 12px', color: '#475569', fontSize: 14}}>
          Onaylı acil durum planı, revizyon ve kroki. Mevcut <strong>Acil Ekipler</strong> ve <strong>Tatbikat</strong> kayıtlarıyla birlikte kullanılır; onları değiştirmez.
        </p>
        {err && <div className="error">{err}</div>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Başlık</th><th>Rev</th><th>Plan</th><th>Gözden geçirme</th><th>Toplanma</th><th>Kroki</th><th>Durum</th><th></th></tr>
            </thead>
            <tbody>
              {rows.length ? rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.title}</td>
                  <td>{r.revision_no}</td>
                  <td>{r.plan_date || '—'}</td>
                  <td>{r.next_review_date || '—'} {dueBadge(r.review_status)}</td>
                  <td>{r.assembly_areas || '—'}</td>
                  <td>{r.kroki_file_name || '—'}</td>
                  <td>{r.status}</td>
                  <td>
                    {canEdit && (
                      <label className="button secondary mini" style={{cursor: 'pointer'}}>
                        <Upload size={14} /> Kroki
                        <input type="file" hidden accept=".png,.jpg,.jpeg,.pdf,.webp" onChange={(e) => { uploadKroki(r, e.target.files?.[0]); e.target.value = ''; }} />
                      </label>
                    )}
                  </td>
                </tr>
              )) : <tr><td colSpan={8} className="empty">Plan kaydı yok.</td></tr>}
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
            <Field label="Plan tarihi" type="date" value={form.plan_date} onChange={(e) => setForm({...form, plan_date: e.target.value})} />
            <Field label="Gözden geçirme" type="date" value={form.next_review_date} onChange={(e) => setForm({...form, next_review_date: e.target.value})} />
            <Field label="Toplanma alanları" value={form.assembly_areas} onChange={(e) => setForm({...form, assembly_areas: e.target.value})} />
            <label className="field" style={{gridColumn: '1 / -1'}}>
              <span>Senaryo özeti</span>
              <textarea rows={4} value={form.scenario_summary} onChange={(e) => setForm({...form, scenario_summary: e.target.value})} />
            </label>
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

/** İSG Kurulu + çalışan temsilcisi */
export function OhsCommitteePage({user}) {
  const canEdit = ['safety_specialist', 'global_admin'].includes(user.role);
  const companies = useCompanies(user);
  const [members, setMembers] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [meta, setMeta] = useState({roles: []});
  const [tab, setTab] = useState('uyeler');
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [memberForm, setMemberForm] = useState({
    company_id: user.company_id || '',
    role_code: 'calisan_temsilcisi',
    full_name: '',
    start_date: '',
    notes: '',
  });
  const [meetingForm, setMeetingForm] = useState({
    company_id: user.company_id || '',
    meeting_date: '',
    agenda: '',
    decisions: '',
    attendees: '',
    next_meeting_date: '',
  });

  async function load() {
    setBusy(true);
    try {
      const [m, mem, meet] = await Promise.all([
        api('/ohs-committee/meta'),
        api('/ohs-committee/members'),
        api('/ohs-committee/meetings'),
      ]);
      setMeta(m);
      setMembers(mem);
      setMeetings(meet);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => { void load(); }, []);

  async function saveMember(e) {
    e.preventDefault();
    await api('/ohs-committee/members', {
      method: 'POST',
      body: JSON.stringify({
        ...memberForm,
        company_id: Number(memberForm.company_id),
        start_date: memberForm.start_date || null,
      }),
    });
    setOpen(false);
    await load();
  }

  async function saveMeeting(e) {
    e.preventDefault();
    await api('/ohs-committee/meetings', {
      method: 'POST',
      body: JSON.stringify({
        ...meetingForm,
        company_id: Number(meetingForm.company_id),
        meeting_date: meetingForm.meeting_date,
        next_meeting_date: meetingForm.next_meeting_date || null,
      }),
    });
    setOpen(false);
    await load();
  }

  const roleLabel = (c) => meta.roles?.find((x) => x.code === c)?.label || c;

  return (
    <>
      <div className="page-title">
        <h3><Users size={20} style={{marginRight: 8, verticalAlign: 'middle'}} />İSG Kurulu / Temsilci</h3>
        <div className="actions">
          <button type="button" className="secondary" onClick={() => downloadFile('/ohs-committee/export.xlsx', 'isg-kurulu.xlsx').catch((e) => setErr(e.message))}><Download size={16} /> Excel</button>
          <button type="button" className="secondary" onClick={() => void load()}><RefreshCw size={16} /> Yenile</button>
          {canEdit && (
            <button type="button" onClick={() => setOpen(true)}>
              <Plus size={16} /> {tab === 'uyeler' ? 'Üye Ekle' : 'Toplantı Ekle'}
            </button>
          )}
        </div>
      </div>
      <section className="panel">
        <div style={{display: 'flex', gap: 8, marginBottom: 12}}>
          <button type="button" className={tab === 'uyeler' ? '' : 'secondary'} onClick={() => setTab('uyeler')}>Üyeler</button>
          <button type="button" className={tab === 'toplantilar' ? '' : 'secondary'} onClick={() => setTab('toplantilar')}>Toplantılar</button>
        </div>
        {err && <div className="error">{err}</div>}
        {tab === 'uyeler' ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Rol</th><th>Ad Soyad</th><th>Başlangıç</th><th>Not</th></tr></thead>
              <tbody>
                {members.length ? members.map((m) => (
                  <tr key={m.id}><td>{roleLabel(m.role_code)}</td><td>{m.full_name}</td><td>{m.start_date || '—'}</td><td>{m.notes || '—'}</td></tr>
                )) : <tr><td colSpan={4} className="empty">Üye yok.</td></tr>}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Tarih</th><th>Gündem</th><th>Kararlar</th><th>Katılımcılar</th><th>Sonraki</th></tr></thead>
              <tbody>
                {meetings.length ? meetings.map((m) => (
                  <tr key={m.id}>
                    <td>{m.meeting_date}</td>
                    <td>{m.agenda || '—'}</td>
                    <td>{m.decisions || '—'}</td>
                    <td>{m.attendees || '—'}</td>
                    <td>{m.next_meeting_date || '—'}</td>
                  </tr>
                )) : <tr><td colSpan={5} className="empty">Toplantı yok.</td></tr>}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {open && tab === 'uyeler' && (
        <Modal title="Kurul Üyesi" close={() => setOpen(false)}>
          <form className="form-grid" onSubmit={saveMember}>
            <Field label="Firma" required>
              <select required value={memberForm.company_id} onChange={(e) => setMemberForm({...memberForm, company_id: e.target.value})}>
                <option value="">Seçiniz</option>
                {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </Field>
            <Field label="Rol" required>
              <select value={memberForm.role_code} onChange={(e) => setMemberForm({...memberForm, role_code: e.target.value})}>
                {(meta.roles || []).map((r) => <option key={r.code} value={r.code}>{r.label}</option>)}
              </select>
            </Field>
            <Field label="Ad Soyad" required value={memberForm.full_name} onChange={(e) => setMemberForm({...memberForm, full_name: e.target.value})} />
            <Field label="Başlangıç" type="date" value={memberForm.start_date} onChange={(e) => setMemberForm({...memberForm, start_date: e.target.value})} />
            <div className="form-actions" style={{gridColumn: '1 / -1'}}><button type="submit" disabled={busy}>Kaydet</button></div>
          </form>
        </Modal>
      )}
      {open && tab === 'toplantilar' && (
        <Modal title="Kurul Toplantısı" close={() => setOpen(false)} wide>
          <form className="form-grid" onSubmit={saveMeeting}>
            <Field label="Firma" required>
              <select required value={meetingForm.company_id} onChange={(e) => setMeetingForm({...meetingForm, company_id: e.target.value})}>
                <option value="">Seçiniz</option>
                {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </Field>
            <Field label="Toplantı tarihi" type="date" required value={meetingForm.meeting_date} onChange={(e) => setMeetingForm({...meetingForm, meeting_date: e.target.value})} />
            <Field label="Sonraki toplantı" type="date" value={meetingForm.next_meeting_date} onChange={(e) => setMeetingForm({...meetingForm, next_meeting_date: e.target.value})} />
            <label className="field" style={{gridColumn: '1 / -1'}}><span>Gündem</span><textarea rows={3} value={meetingForm.agenda} onChange={(e) => setMeetingForm({...meetingForm, agenda: e.target.value})} /></label>
            <label className="field" style={{gridColumn: '1 / -1'}}><span>Kararlar</span><textarea rows={3} value={meetingForm.decisions} onChange={(e) => setMeetingForm({...meetingForm, decisions: e.target.value})} /></label>
            <Field label="Katılımcılar" value={meetingForm.attendees} onChange={(e) => setMeetingForm({...meetingForm, attendees: e.target.value})} />
            <div className="form-actions" style={{gridColumn: '1 / -1'}}><button type="submit" disabled={busy}>Kaydet</button></div>
          </form>
        </Modal>
      )}
    </>
  );
}

/** Belge onay / imza hazırlık (5070 sağlayıcı olmadan süreç) */
export function DocumentApprovalsPage({user}) {
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
          {canEdit && <button type="button" onClick={() => setOpen(true)}><Plus size={16} /> Onay Kaydı</button>}
        </div>
      </div>
      <section className="panel">
        <p style={{margin: '0 0 12px', color: '#475569', fontSize: 14}}>
          Onay zinciri takibi + isteğe bağlı OSGB Signer hattı (web → tek kullanımlık talep → Windows agent /
          PKCS#11 kart → sunucu doğrulama/OCSP/CRL/TSA/kilit/denetim). Mevcut “Onayla”, PDF indirme ve ziyaret
          canvas imzası değişmez. IBYSIS HSNSigner (16999) ile çakışmaz (bu köprü 17000).
        </p>
        <div style={{
          marginBottom: 12, padding: '10px 12px', borderRadius: 8,
          background: signer.ok ? '#ecfdf5' : '#f8fafc', border: '1px solid #e2e8f0', fontSize: 13,
        }}>
          <strong>OSGB Signer:</strong>{' '}
          {signer.checking ? 'kontrol ediliyor…' : signer.ok
            ? `Bağlı (${signer.data?.product || 'OSGB Signer'} v${signer.data?.version || '?'}${signer.data?.pkcs11_configured ? ', PKCS#11 hazır' : ''}${signer.data?.demo_mode ? ', demo sertifika' : ''})`
            : `Kapalı (${signer.error || 'https://127.0.0.1:17000/health'}). Kurulum: tools/isg-suite-signer → KUR.bat`}
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
                          disabled={signBusy === r.id}
                          title={signer.ok ? 'PDF seç → yerel imza → indir + kayda işle' : 'Köprü kapalı'}
                          onClick={() => void localSign(r)}
                        >
                          {signBusy === r.id ? 'İmzalanıyor…' : 'Kart / PDF İmzala'}
                        </button>
                      </>
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
