import React, {useEffect, useMemo, useState} from 'react';
import {Download, Plus, Search, X} from 'lucide-react';
import {api, downloadFile} from './api';

const TYPE_DEFAULT = {
  near_miss: 'ramak_kala',
  accident: 'is_kazasi',
};

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

function Check({label, checked, onChange}) {
  return (
    <label className="field" style={{display: 'flex', alignItems: 'center', gap: 8}}>
      <input type="checkbox" checked={!!checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

function emptyForm(user, eventType) {
  return {
    company_id: user.company_id || '',
    branch_id: '',
    event_type: eventType,
    short_summary: '',
    event_date: new Date().toISOString().slice(0, 10),
    event_time: '',
    department: '',
    location: '',
    area: '',
    work_being_done: '',
    related_people: '',
    has_witness: false,
    witness_names: '',
    equipment_used: '',
    chemical_used: '',
    detail: '',
    classification: '',
    injury_occurred: false,
    health_complaint: false,
    medical_intervention: false,
    work_incapacity_report: false,
    equipment_damage: false,
    would_have_injured: true,
    probability: 3,
    severity: 3,
    risk_analysis_status: '',
    risk_analysis_note: '',
    emergency_relation: '',
    emergency_note: '',
    evaluation_text: '',
    safety_specialist: '',
    workplace_physician: '',
    employer_representative: '',
    sgk_reported: false,
    sgk_report_date: '',
    police_reported: false,
    accident_type: '',
    injury_type: '',
    intervention_detail: '',
    report_days: '',
  };
}

export function IncidentsPage({user, menuKey = 'near_miss'}) {
  const canEdit = ['global_admin', 'company_admin', 'safety_specialist'].includes(user.role);
  const defaultType = TYPE_DEFAULT[menuKey] || 'ramak_kala';
  const pageTitle = menuKey === 'accident' ? 'İş Kazası Kayıtları' : 'Ramak Kala / Olay Kayıtları';

  const [companies, setCompanies] = useState([]);
  const [branches, setBranches] = useState([]);
  const [meta, setMeta] = useState(null);
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState('');
  const [typeFilter, setTypeFilter] = useState(defaultType);
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState(null);
  const [form, setForm] = useState(() => emptyForm(user, defaultType));
  const [err, setErr] = useState('');
  const [rootForm, setRootForm] = useState({
    why_1: '', why_2: '', why_3: '', why_4: '', why_5: '',
    root_cause: '', root_cause_category: '', systemic_gap: '',
  });
  const [dofForm, setDofForm] = useState({
    finding: '', root_cause: '', corrective_action: '', preventive_action: '',
    responsible_person: '', term_date: '', priority: 'Orta',
  });
  const [tab, setTab] = useState('olay');
  const [dlBusy, setDlBusy] = useState(false);

  useEffect(() => {
    setTypeFilter(defaultType);
    setForm(emptyForm(user, defaultType));
  }, [menuKey]);

  const load = async () => {
    const params = new URLSearchParams();
    if (typeFilter) params.set('event_type', typeFilter);
    if (q) params.set('q', q);
    const qs = params.toString() ? `?${params}` : '';
    const [c, b, m, list] = await Promise.all([
      api('/companies'),
      api('/branches'),
      api('/incidents/meta'),
      api(`/incidents${qs}`),
    ]);
    setCompanies(c);
    setBranches(b);
    setMeta(m);
    setRows(list);
  };

  useEffect(() => {
    load().catch((e) => setErr(e.message));
  }, [typeFilter]);

  const companyBranches = useMemo(
    () => branches.filter((b) => String(b.company_id) === String(form.company_id)),
    [branches, form.company_id],
  );

  const typeLabel = (code) => meta?.event_types?.find((t) => t.code === code)?.label || code;

  async function save(e) {
    e.preventDefault();
    setErr('');
    try {
      const payload = {
        ...form,
        company_id: Number(form.company_id),
        branch_id: form.branch_id ? Number(form.branch_id) : null,
        probability: Number(form.probability) || 0,
        severity: Number(form.severity) || 0,
        report_days: form.report_days === '' ? 0 : Number(form.report_days),
        sgk_report_date: form.sgk_report_date || null,
        event_time: form.event_time || null,
      };
      await api('/incidents', {method: 'POST', body: JSON.stringify(payload)});
      setOpen(false);
      setForm(emptyForm(user, typeFilter || defaultType));
      await load();
    } catch (x) {
      setErr(x.message);
    }
  }

  async function openDetail(id) {
    const r = await api(`/incidents/${id}`);
    setDetail(r);
    setTab('olay');
    const rc = r.root_cause || {};
    setRootForm({
      why_1: rc.why_1 || '',
      why_2: rc.why_2 || '',
      why_3: rc.why_3 || '',
      why_4: rc.why_4 || '',
      why_5: rc.why_5 || '',
      root_cause: rc.root_cause || '',
      root_cause_category: rc.root_cause_category || '',
      systemic_gap: rc.systemic_gap || '',
    });
    setDofForm({
      finding: '',
      root_cause: rc.root_cause || '',
      corrective_action: '',
      preventive_action: '',
      responsible_person: '',
      term_date: '',
      priority: 'Orta',
    });
  }

  async function closeIncident() {
    if (!detail) return;
    await api(`/incidents/${detail.id}`, {method: 'PATCH', body: JSON.stringify({status: 'Kapalı'})});
    openDetail(detail.id);
    load();
  }

  async function saveRoot(e) {
    e.preventDefault();
    if (!detail) return;
    await api(`/incidents/${detail.id}/root-cause`, {
      method: 'PUT',
      body: JSON.stringify(rootForm),
    });
    openDetail(detail.id);
  }

  async function addDof(e) {
    e.preventDefault();
    if (!detail || !dofForm.finding.trim()) return;
    await api(`/incidents/${detail.id}/dofs`, {
      method: 'POST',
      body: JSON.stringify({
        finding: dofForm.finding.trim(),
        root_cause: dofForm.root_cause || null,
        corrective_action: dofForm.corrective_action || null,
        preventive_action: dofForm.preventive_action || null,
        responsible_person: dofForm.responsible_person || null,
        term_date: dofForm.term_date || null,
        priority: dofForm.priority,
      }),
    });
    openDetail(detail.id);
    load();
  }

  async function completeDof(dofId) {
    const note = window.prompt('Etkinlik kontrol notu (isteğe bağlı):', '') || null;
    await api(`/incidents/${detail.id}/dofs/${dofId}/complete`, {
      method: 'POST',
      body: JSON.stringify({effectiveness_note: note}),
    });
    openDetail(detail.id);
    load();
  }

  async function downloadPdf() {
    if (!detail) return;
    setDlBusy(true);
    setErr('');
    try {
      await downloadFile(`/incidents/${detail.id}/report.pdf`, `olay-${detail.form_no}.pdf`);
    } catch (x) {
      setErr(x.message || 'PDF indirilemedi.');
    } finally {
      setDlBusy(false);
    }
  }

  if (detail) {
    return (
      <>
        <div className="page-title">
          <h3>{pageTitle}</h3>
        </div>
        <section className="panel doc-workspace">
          <div className="doc-head">
            <div>
              <h3>{detail.form_no} — {typeLabel(detail.event_type)}</h3>
              <p style={{margin: '6px 0 0', color: '#64748b', fontSize: 14}}>
                Uygulama içinde kalın · kök neden (5N) · olay DÖF · PDF rapor
              </p>
            </div>
            <div className="actions">
              <button type="button" className="secondary" disabled={dlBusy} onClick={downloadPdf}>
                <Download size={16} /> {dlBusy ? 'PDF…' : 'Olay PDF'}
              </button>
              <button type="button" className="secondary" onClick={() => setDetail(null)}>Listeye dön</button>
            </div>
          </div>

          <div style={{display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap'}}>
            {['olay', 'kok', 'dof'].map((t) => (
              <button
                key={t}
                type="button"
                className={tab === t ? '' : 'secondary'}
                onClick={() => setTab(t)}
              >
                {t === 'olay' ? 'Olay' : t === 'kok' ? 'Kök Neden (5N)' : 'Olay DÖF'}
              </button>
            ))}
            {canEdit && detail.status !== 'Kapalı' && (
              <button type="button" className="secondary" onClick={closeIncident}>Kaydı kapat</button>
            )}
          </div>

          {err && <div className="error" style={{marginBottom: 12}}>{err}</div>}
          {detail.auto_warning && (
            <div className="error" style={{whiteSpace: 'pre-wrap', marginBottom: 12}}>{detail.auto_warning}</div>
          )}

          {tab === 'olay' && (
            <div className="form-grid">
              <div className="field"><span>Tarih</span><strong>{detail.event_date} {detail.event_time || ''}</strong></div>
              <div className="field"><span>Risk</span><strong>{detail.risk_level || '—'} ({detail.risk_score})</strong></div>
              <div className="field"><span>Bölüm</span><strong>{detail.department || '—'}</strong></div>
              <div className="field"><span>Yer</span><strong>{detail.location || '—'}</strong></div>
              <div className="field" style={{gridColumn: '1 / -1'}}><span>Sınıflandırma</span><strong>{detail.classification || '—'}</strong></div>
              <div className="field" style={{gridColumn: '1 / -1'}}><span>Özet</span><p>{detail.short_summary}</p></div>
              <div className="field" style={{gridColumn: '1 / -1'}}><span>Detay</span><p>{detail.detail || '—'}</p></div>
              {detail.event_type === 'is_kazasi' && (
                <>
                  <div className="field"><span>SGK</span><strong>{detail.sgk_reported ? `Evet (${detail.sgk_report_date || '—'})` : 'Hayır'}</strong></div>
                  <div className="field"><span>Kolluk</span><strong>{detail.police_reported ? 'Evet' : 'Hayır'}</strong></div>
                  <div className="field"><span>Kaza türü</span><strong>{detail.accident_type || '—'}</strong></div>
                </>
              )}
            </div>
          )}

          {tab === 'kok' && (
            <form className="form-grid" onSubmit={saveRoot}>
              <TextArea label="Neden 1" value={rootForm.why_1} onChange={(e) => setRootForm({...rootForm, why_1: e.target.value})} />
              <TextArea label="Neden 2" value={rootForm.why_2} onChange={(e) => setRootForm({...rootForm, why_2: e.target.value})} />
              <TextArea label="Neden 3" value={rootForm.why_3} onChange={(e) => setRootForm({...rootForm, why_3: e.target.value})} />
              <TextArea label="Neden 4" value={rootForm.why_4} onChange={(e) => setRootForm({...rootForm, why_4: e.target.value})} />
              <TextArea label="Neden 5" value={rootForm.why_5} onChange={(e) => setRootForm({...rootForm, why_5: e.target.value})} />
              <Select
                label="Kök neden kategorisi"
                required
                value={rootForm.root_cause_category}
                onChange={(e) => setRootForm({...rootForm, root_cause_category: e.target.value})}
              >
                <option value="">Seçiniz</option>
                {(meta?.root_cause_categories || []).map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
              <TextArea label="Kök neden" value={rootForm.root_cause} onChange={(e) => setRootForm({...rootForm, root_cause: e.target.value})} />
              <TextArea label="Sistemsel eksiklik" value={rootForm.systemic_gap} onChange={(e) => setRootForm({...rootForm, systemic_gap: e.target.value})} />
              {canEdit && (
                <div className="form-actions" style={{gridColumn: '1 / -1'}}>
                  <button type="submit">Kök nedeni kaydet</button>
                </div>
              )}
            </form>
          )}

          {tab === 'dof' && (
            <div style={{display: 'grid', gap: 14}}>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>DÖF No</th>
                      <th>Tespit</th>
                      <th>Düzeltici</th>
                      <th>Sorumlu</th>
                      <th>Termin</th>
                      <th>Durum</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {(detail.dofs || []).length ? detail.dofs.map((d) => (
                      <tr key={d.id}>
                        <td>{d.dof_no}</td>
                        <td>{d.finding}</td>
                        <td>{d.corrective_action || '—'}</td>
                        <td>{d.responsible_person || '—'}</td>
                        <td>{d.term_date || '—'}</td>
                        <td>{d.status}</td>
                        <td>
                          {canEdit && d.status !== 'Tamamlandı' && (
                            <button className="mini" type="button" onClick={() => completeDof(d.id)}>Tamamla</button>
                          )}
                        </td>
                      </tr>
                    )) : (
                      <tr><td colSpan={7} className="empty">Olay DÖF yok</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
              {canEdit && (
                <form className="form-grid" onSubmit={addDof}>
                  <TextArea label="Tespit edilen uygunsuzluk (min. 10 karakter)" required value={dofForm.finding} onChange={(e) => setDofForm({...dofForm, finding: e.target.value})} />
                  <TextArea label="Kök neden" value={dofForm.root_cause} onChange={(e) => setDofForm({...dofForm, root_cause: e.target.value})} />
                  <TextArea label="Düzeltici faaliyet" required value={dofForm.corrective_action} onChange={(e) => setDofForm({...dofForm, corrective_action: e.target.value})} />
                  <TextArea label="Önleyici faaliyet" required value={dofForm.preventive_action} onChange={(e) => setDofForm({...dofForm, preventive_action: e.target.value})} />
                  <Field label="Sorumlu" required value={dofForm.responsible_person} onChange={(e) => setDofForm({...dofForm, responsible_person: e.target.value})} />
                  <Field label="Termin" type="date" required value={dofForm.term_date} onChange={(e) => setDofForm({...dofForm, term_date: e.target.value})} />
                  <Select label="Öncelik" value={dofForm.priority} onChange={(e) => setDofForm({...dofForm, priority: e.target.value})}>
                    <option>Düşük</option>
                    <option>Orta</option>
                    <option>Yüksek</option>
                    <option>Acil</option>
                  </Select>
                  <div className="form-actions" style={{gridColumn: '1 / -1'}}>
                    <button type="submit">DÖF Ekle</button>
                  </div>
                </form>
              )}
            </div>
          )}
        </section>
      </>
    );
  }

  return (
    <>
      <div className="page-title">
        <h3>{pageTitle}</h3>
        {canEdit && (
          <button type="button" onClick={() => {
            setForm(emptyForm(user, typeFilter || defaultType));
            setErr('');
            setOpen(true);
          }}>
            <Plus /> Yeni Olay Kaydı
          </button>
        )}
      </div>
      <section className="panel">
        <div style={{marginBottom: 12, padding: '10px 12px', background: '#eef5fb', borderRadius: 10, fontSize: 14, lineHeight: 1.5}}>
          PRO uyumlu olay kaydı: sınıflandırma, otomatik uyarı, <strong>5N kök neden</strong> ve <strong>olay DÖF</strong>.
          Detay satırından PDF indirilir. İş kazasında SGK / kolluk alanları görünür.
        </div>
        <div className="search" style={{marginBottom: 12, flexWrap: 'wrap'}}>
          <Search size={19} />
          <input
            placeholder="Form no, özet, yer, bölüm ara..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && load()}
          />
          <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} style={{minWidth: 200}}>
            {(meta?.event_types || [
              {code: 'ramak_kala', label: 'Ramak Kala'},
              {code: 'is_kazasi', label: 'İş Kazası'},
            ]).map((t) => (
              <option key={t.code} value={t.code}>{t.label}</option>
            ))}
            <option value="">Tüm tipler</option>
          </select>
          <button className="secondary" type="button" onClick={() => load().catch((e) => setErr(e.message))}>Ara</button>
        </div>
        {err && <div className="error">{err}</div>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Form No</th>
                <th>Tip</th>
                <th>Tarih</th>
                <th>Özet</th>
                <th>Sınıf</th>
                <th>Risk</th>
                <th>Durum</th>
                <th>İşlem</th>
              </tr>
            </thead>
            <tbody>
              {rows.length ? rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.form_no}</td>
                  <td>{typeLabel(r.event_type)}</td>
                  <td>{r.event_date}</td>
                  <td>{r.short_summary}</td>
                  <td>{r.classification || '—'}</td>
                  <td>{r.risk_level ? `${r.risk_level} (${r.risk_score})` : '—'}</td>
                  <td>
                    <span className={'badge ' + (r.status === 'Kapalı' ? 'ok' : 'off')}>{r.status}</span>
                  </td>
                  <td>
                    <button className="mini" type="button" onClick={() => openDetail(r.id)}>Detay</button>
                  </td>
                </tr>
              )) : (
                <tr><td colSpan={8} className="empty">Olay kaydı yok. Yeni kayıt ekleyin.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {open && (
        <Modal title="Yeni Olay Kaydı" close={() => setOpen(false)} wide>
          <form className="form-grid" onSubmit={save}>
            <Select label="Firma" required value={form.company_id} onChange={(e) => setForm({...form, company_id: e.target.value, branch_id: ''})}>
              <option value="">Seçiniz</option>
              {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
            <Select label="Olay tipi" required value={form.event_type} onChange={(e) => setForm({...form, event_type: e.target.value})}>
              {(meta?.event_types || []).map((t) => <option key={t.code} value={t.code}>{t.label}</option>)}
            </Select>
            <Select label="Şube" value={form.branch_id} onChange={(e) => setForm({...form, branch_id: e.target.value})}>
              <option value="">Şube seçilmedi</option>
              {companyBranches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </Select>
            <Field label="Olay tarihi" type="date" required value={form.event_date} onChange={(e) => setForm({...form, event_date: e.target.value})} />
            <Field label="Saat" value={form.event_time} onChange={(e) => setForm({...form, event_time: e.target.value})} placeholder="14:30" />
            <Field label="Departman / Bölüm" value={form.department} onChange={(e) => setForm({...form, department: e.target.value})} />
            <Field label="Olay yeri" required value={form.location} onChange={(e) => setForm({...form, location: e.target.value})} />
            <Field label="Alan" value={form.area} onChange={(e) => setForm({...form, area: e.target.value})} />
            <Select label="Sınıflandırma" required value={form.classification} onChange={(e) => setForm({...form, classification: e.target.value})}>
              <option value="">Seçiniz</option>
              {(meta?.classifications || []).map((c) => <option key={c} value={c}>{c}</option>)}
            </Select>
            <Field label="Yapılan iş" value={form.work_being_done} onChange={(e) => setForm({...form, work_being_done: e.target.value})} style={{gridColumn: '1 / -1'}} />
            <TextArea label="Kısa özet (min. 20 karakter)" required value={form.short_summary} onChange={(e) => setForm({...form, short_summary: e.target.value})} />
            <TextArea label="Detay (min. 30 karakter)" required value={form.detail} onChange={(e) => setForm({...form, detail: e.target.value})} />
            <Field label="İlgili kişiler" value={form.related_people} onChange={(e) => setForm({...form, related_people: e.target.value})} />
            <Check label="Şahit var" checked={form.has_witness} onChange={(v) => setForm({...form, has_witness: v})} />
            {form.has_witness && (
              <Field label="Şahit isimleri" value={form.witness_names} onChange={(e) => setForm({...form, witness_names: e.target.value})} />
            )}
            <Field label="Ekipman" value={form.equipment_used} onChange={(e) => setForm({...form, equipment_used: e.target.value})} />
            <Field label="Kimyasal" value={form.chemical_used} onChange={(e) => setForm({...form, chemical_used: e.target.value})} />

            <Check label="Yaralanma oldu" checked={form.injury_occurred} onChange={(v) => setForm({...form, injury_occurred: v})} />
            <Check label="Sağlık şikayeti" checked={form.health_complaint} onChange={(v) => setForm({...form, health_complaint: v})} />
            <Check label="Tıbbi müdahale" checked={form.medical_intervention} onChange={(v) => setForm({...form, medical_intervention: v})} />
            <Check label="İş göremezlik raporu" checked={form.work_incapacity_report} onChange={(v) => setForm({...form, work_incapacity_report: v})} />
            <Check label="Ekipman hasarı" checked={form.equipment_damage} onChange={(v) => setForm({...form, equipment_damage: v})} />
            <Check label="Farklı gelse yaralanma olurdu" checked={form.would_have_injured} onChange={(v) => setForm({...form, would_have_injured: v})} />

            <Field label="Olasılık (0-5)" type="number" min="0" max="5" value={form.probability} onChange={(e) => setForm({...form, probability: e.target.value})} />
            <Field label="Şiddet (0-5)" type="number" min="0" max="5" value={form.severity} onChange={(e) => setForm({...form, severity: e.target.value})} />
            <Select label="Risk analizinde var mı?" value={form.risk_analysis_status} onChange={(e) => setForm({...form, risk_analysis_status: e.target.value})}>
              <option value="">Seçiniz</option>
              {(meta?.risk_analysis_options || []).map((o) => <option key={o.code} value={o.code}>{o.label}</option>)}
            </Select>
            <Select label="Acil durum ilişkisi" value={form.emergency_relation} onChange={(e) => setForm({...form, emergency_relation: e.target.value})}>
              <option value="">Seçiniz</option>
              {(meta?.emergency_options || []).map((o) => <option key={o} value={o}>{o}</option>)}
            </Select>

            {form.event_type === 'is_kazasi' && (
              <>
                <Select label="Kaza türü" value={form.accident_type} onChange={(e) => setForm({...form, accident_type: e.target.value})}>
                  <option value="">Seçiniz</option>
                  {(meta?.accident_types || []).map((o) => <option key={o} value={o}>{o}</option>)}
                </Select>
                <Field label="Yaralanma türü" value={form.injury_type} onChange={(e) => setForm({...form, injury_type: e.target.value})} />
                <Check label="SGK bildirildi" checked={form.sgk_reported} onChange={(v) => setForm({...form, sgk_reported: v})} />
                <Field label="SGK bildirim tarihi" type="date" value={form.sgk_report_date} onChange={(e) => setForm({...form, sgk_report_date: e.target.value})} />
                <Check label="Kolluk bildirildi" checked={form.police_reported} onChange={(v) => setForm({...form, police_reported: v})} />
                <Field label="Rapor süresi (gün)" type="number" min="0" value={form.report_days} onChange={(e) => setForm({...form, report_days: e.target.value})} />
                <TextArea label="Müdahale detayı" value={form.intervention_detail} onChange={(e) => setForm({...form, intervention_detail: e.target.value})} />
              </>
            )}

            <Field label="İSG uzmanı" value={form.safety_specialist} onChange={(e) => setForm({...form, safety_specialist: e.target.value})} />
            <Field label="İşyeri hekimi" value={form.workplace_physician} onChange={(e) => setForm({...form, workplace_physician: e.target.value})} />
            <Field label="İşveren / vekili" value={form.employer_representative} onChange={(e) => setForm({...form, employer_representative: e.target.value})} />

            {err && <div className="error" style={{gridColumn: '1 / -1'}}>{err}</div>}
            <div className="form-actions" style={{gridColumn: '1 / -1'}}>
              <button type="submit">Kaydet</button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}

/** DÖF merkezi — olay + risk açık DÖF’lerini tek listede toplar (stub isg-records yerine). */
export function CapaPage({user}) {
  const [rows, setRows] = useState([]);
  const [err, setErr] = useState('');
  const [q, setQ] = useState('');
  const [companies, setCompanies] = useState([]);
  const [companyId, setCompanyId] = useState(user.company_id || '');

  const load = async () => {
    setErr('');
    const companiesList = await api('/companies');
    setCompanies(companiesList);
    const cid = companyId || user.company_id || companiesList[0]?.id;
    if (!cid && user.role === 'global_admin') {
      setErr('DÖF listesi için firma seçiniz.');
      setRows([]);
      return;
    }
    if (cid && !companyId) setCompanyId(cid);

    const riskQs = new URLSearchParams();
    if (cid) riskQs.set('company_id', String(cid));
    const [incidents, risks] = await Promise.all([
      api('/incidents'),
      api(`/risks?${riskQs}`).catch(() => []),
    ]);

    const incidentDofs = [];
    for (const inc of incidents) {
      for (const d of (inc.dofs || [])) {
        incidentDofs.push({
          key: `i-${d.id}`,
          source: 'Olay',
          code: d.dof_no,
          title: d.finding,
          action: d.corrective_action,
          responsible: d.responsible_person,
          term: d.term_date,
          status: d.status,
          priority: d.priority,
          parent: inc.form_no,
          parentSummary: inc.short_summary,
        });
      }
    }
    const riskDofs = [];
    for (const r of risks) {
      for (const d of (r.dofs || [])) {
        riskDofs.push({
          key: `r-${d.id}`,
          source: 'Risk',
          code: d.dof_code,
          title: d.description,
          action: d.description,
          responsible: d.responsible_person,
          term: d.term_date,
          status: d.is_completed ? 'Tamamlandı' : (d.status || 'Açık'),
          priority: '—',
          parent: r.risk_code,
          parentSummary: r.activity,
        });
      }
    }
    setRows([...incidentDofs, ...riskDofs]);
  };

  useEffect(() => {
    load().catch((e) => setErr(e.message));
  }, [companyId]);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return rows;
    return rows.filter((r) =>
      [r.code, r.title, r.responsible, r.parent, r.parentSummary, r.source]
        .filter(Boolean)
        .some((x) => String(x).toLowerCase().includes(s)),
    );
  }, [rows, q]);

  const openCount = filtered.filter((r) => r.status !== 'Tamamlandı').length;

  return (
    <>
      <div className="page-title">
        <h3>DÖF Yönetimi</h3>
      </div>
      <section className="panel">
        <div style={{marginBottom: 12, padding: '10px 12px', background: '#eef5fb', borderRadius: 10, fontSize: 14, lineHeight: 1.5}}>
          Açık düzeltici faaliyetler <strong>olay</strong> ve <strong>risk</strong> kayıtlarından birleştirilir.
          Yeni DÖF eklemek için ilgili olay veya risk detayına gidin.
        </div>
        <div className="search" style={{marginBottom: 12, flexWrap: 'wrap'}}>
          <Search size={19} />
          <input
            placeholder="DÖF no, tespit, sorumlu ara..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          {!user.company_id && (
            <select value={companyId} onChange={(e) => setCompanyId(e.target.value)} style={{minWidth: 180}}>
              <option value="">Firma (risk DÖF)</option>
              {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          )}
          <button className="secondary" type="button" onClick={() => load().catch((e) => setErr(e.message))}>Yenile</button>
        </div>
        {err && <div className="error">{err}</div>}
        <p style={{fontSize: 14, color: '#64748b', marginBottom: 10}}>
          Toplam {filtered.length} DÖF · açık {openCount}
        </p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Kaynak</th>
                <th>DÖF No</th>
                <th>Bağlı kayıt</th>
                <th>Tespit / iş</th>
                <th>Sorumlu</th>
                <th>Termin</th>
                <th>Durum</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length ? filtered.map((r) => (
                <tr key={r.key}>
                  <td>{r.source}</td>
                  <td>{r.code}</td>
                  <td>
                    <div>{r.parent}</div>
                    <div style={{fontSize: 12, color: '#64748b'}}>{r.parentSummary}</div>
                  </td>
                  <td>{r.title}</td>
                  <td>{r.responsible || '—'}</td>
                  <td>{r.term || '—'}</td>
                  <td>
                    <span className={'badge ' + (r.status === 'Tamamlandı' ? 'ok' : 'off')}>{r.status}</span>
                  </td>
                </tr>
              )) : (
                <tr><td colSpan={7} className="empty">Açık veya kayıtlı DÖF yok. Olay / Risk detayından ekleyin.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

