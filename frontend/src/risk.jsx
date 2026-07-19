import React, {useEffect, useMemo, useState} from 'react';
import {BookOpen, Download, Plus, Search, X} from 'lucide-react';
import {api, downloadFile, uploadFile, authBlobUrl} from './api';

const LEVEL_COLORS = {
  'Kabul Edilebilir': '#95a5a6',
  'Düşük': '#2ecc71',
  'Orta': '#f1c40f',
  'Yüksek': '#f39c12',
  'Çok Yüksek': '#e74c3c',
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

function LevelBadge({level, score}) {
  const color = LEVEL_COLORS[level] || '#888';
  return (
    <span style={{display: 'inline-flex', alignItems: 'center', gap: 6}}>
      <span style={{width: 10, height: 10, borderRadius: 99, background: color}} />
      {level || '—'}{score != null ? ` (${score})` : ''}
    </span>
  );
}

function AuthThumb({path, alt}) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let alive = true;
    let url = null;
    authBlobUrl(path)
      .then((u) => {
        if (!alive) {
          URL.revokeObjectURL(u);
          return;
        }
        url = u;
        setSrc(u);
      })
      .catch(() => {});
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [path]);
  if (!src) {
    return <div style={{width: 96, height: 72, background: '#e2e8f0', borderRadius: 6}} />;
  }
  return (
    <img
      src={src}
      alt={alt || ''}
      style={{width: 96, height: 72, objectFit: 'cover', borderRadius: 6, border: '1px solid #cbd5e1'}}
    />
  );
}

export function RiskPage({user}) {
  const canEdit = ['global_admin', 'company_admin', 'safety_specialist'].includes(user.role);
  const empty = {
    company_id: user.company_id || '',
    branch_id: '',
    department_id: '',
    department_name: '',
    new_department: '',
    category_id: '',
    hazard_id: '',
    hazard_q: '',
    activity: '',
    risk_definition: '',
    affected_people: '',
    affected_group: 'Çalışan',
    existing_measures: '',
    additional_measures: '',
    probability: 3,
    severity: 3,
  };

  const [companies, setCompanies] = useState([]);
  const [branches, setBranches] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [categories, setCategories] = useState([]);
  const [hazards, setHazards] = useState([]);
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState(null);
  const [calc, setCalc] = useState(null);
  const [suggestions, setSuggestions] = useState(null);
  const [open, setOpen] = useState(false);
  const [libOpen, setLibOpen] = useState(false);
  const [detail, setDetail] = useState(null);
  const [q, setQ] = useState('');
  const [levelFilter, setLevelFilter] = useState('');
  const [form, setForm] = useState(empty);
  const [err, setErr] = useState('');
  const [libMsg, setLibMsg] = useState('');
  const [dofForm, setDofForm] = useState({
    description: '',
    responsible_person: '',
    responsible_department: '',
    term_date: '',
    cost_estimate: '',
  });
  const [busy, setBusy] = useState(false);
  const [dlBusy, setDlBusy] = useState('');
  const [reportCompanyId, setReportCompanyId] = useState(user.company_id || '');

  const loadDepartments = async (companyId) => {
    if (!companyId) { setDepartments([]); return; }
    try {
      const deps = await api(`/risks/departments?company_id=${companyId}`);
      setDepartments(deps);
    } catch (_) {
      setDepartments([]);
    }
  };

  const load = async () => {
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (levelFilter) params.set('level', levelFilter);
    const [c, b, cats, m] = await Promise.all([
      api('/companies'),
      api('/branches'),
      api('/risks/categories'),
      api('/risks/meta'),
    ]);
    setCompanies(c);
    setBranches(b);
    setCategories(cats);
    setMeta(m);
    const cid = reportCompanyId || user.company_id || c[0]?.id;
    if (cid && !reportCompanyId) setReportCompanyId(cid);
    if (!cid && user.role === 'global_admin') {
      setRows([]);
      setErr('Risk listesi için firma seçiniz.');
      return;
    }
    if (cid) params.set('company_id', String(cid));
    const qs = params.toString() ? `?${params}` : '';
    const risks = await api(`/risks${qs}`);
    setRows(risks);
    setErr('');
    if (cid) await loadDepartments(cid);
  };

  useEffect(() => {
    if (!user.company_id && !reportCompanyId) {
      // global admin: companies yüklenene kadar bekle
      load().catch((e) => setErr(e.message));
      return;
    }
    load().catch((e) => setErr(e.message));
  }, [reportCompanyId, levelFilter]);

  useEffect(() => {
    if (!form.company_id) { setDepartments([]); return; }
    loadDepartments(form.company_id);
  }, [form.company_id]);

  useEffect(() => {
    if (!form.category_id) { setHazards([]); return; }
    const params = new URLSearchParams({category_id: String(form.category_id)});
    if (form.hazard_q) params.set('q', form.hazard_q);
    api(`/risks/hazards?${params}`)
      .then(setHazards)
      .catch(() => setHazards([]));
  }, [form.category_id, form.hazard_q]);

  useEffect(() => {
    const p = Number(form.probability);
    const s = Number(form.severity);
    if (!p || !s) return;
    api('/risks/calculate', {method: 'POST', body: JSON.stringify({probability: p, severity: s})})
      .then(setCalc)
      .catch(() => setCalc(null));
  }, [form.probability, form.severity]);

  async function seedLibrary() {
    setBusy(true);
    setLibMsg('');
    try {
      const r = await api('/risks/seed-library', {method: 'POST'});
      setLibMsg(`Kütüphane yüklendi: ${r.categories} kategori, ${r.hazards_total || r.hazards_created} tehlike`);
      const cats = await api('/risks/categories');
      setCategories(cats);
    } catch (e) {
      setLibMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function onHazardPick(hazardId) {
    setForm((f) => ({...f, hazard_id: hazardId}));
    if (!hazardId) { setSuggestions(null); return; }
    try {
      const d = await api(`/risks/hazards/${hazardId}`);
      setSuggestions(d.suggestions || null);
      const h = d.hazard;
      setForm((f) => ({
        ...f,
        hazard_id: String(hazardId),
        category_id: String(h.category_id),
        risk_definition: h.description || h.name,
        probability: h.default_probability || f.probability,
        severity: h.default_severity || f.severity,
      }));
    } catch (_) { setSuggestions(null); }
  }

  async function save(e) {
    e.preventDefault();
    setErr('');
    if (!form.hazard_id) {
      setErr('Tehlike kütüphanesinden bir tehlike seçmelisiniz.');
      return;
    }
    const newDep = (form.new_department || '').trim();
    const payload = {
      company_id: Number(form.company_id),
      branch_id: form.branch_id ? Number(form.branch_id) : null,
      hazard_id: Number(form.hazard_id),
      activity: form.activity,
      risk_definition: form.risk_definition,
      affected_people: form.affected_people || null,
      affected_group: form.affected_group || null,
      existing_measures: form.existing_measures || null,
      additional_measures: form.additional_measures || null,
      probability: Number(form.probability),
      severity: Number(form.severity),
    };
    if (newDep) {
      payload.department_name = newDep;
      payload.department_id = null;
    } else if (form.department_id) {
      payload.department_id = Number(form.department_id);
    }
    try {
      await api('/risks', {method: 'POST', body: JSON.stringify(payload)});
      setOpen(false);
      setForm(empty);
      setSuggestions(null);
      load();
    } catch (x) {
      setErr(x.message);
    }
  }

  async function addDepartmentQuick() {
    const name = (form.new_department || '').trim();
    if (!name || !form.company_id) return;
    setBusy(true);
    try {
      const dep = await api('/risks/departments', {
        method: 'POST',
        body: JSON.stringify({company_id: Number(form.company_id), name}),
      });
      await loadDepartments(form.company_id);
      setForm((f) => ({...f, department_id: String(dep.id), new_department: '', department_name: dep.name}));
    } catch (x) {
      setErr(x.message);
    } finally {
      setBusy(false);
    }
  }

  async function complete(id) {
    await api(`/risks/${id}`, {method: 'PATCH', body: JSON.stringify({status: 'Tamamlandı'})});
    load();
  }

  async function openDetail(id) {
    const r = await api(`/risks/${id}`);
    setDetail(r);
    setDofForm({
      description: '',
      responsible_person: '',
      responsible_department: r.department_name || '',
      term_date: r.term_date || '',
      cost_estimate: '',
    });
  }

  async function addDof(e) {
    e.preventDefault();
    if (!detail || !dofForm.description.trim()) return;
    await api(`/risks/${detail.id}/dofs`, {
      method: 'POST',
      body: JSON.stringify({
        description: dofForm.description.trim(),
        responsible_person: dofForm.responsible_person.trim() || null,
        responsible_department: dofForm.responsible_department.trim() || null,
        term_date: dofForm.term_date || null,
        cost_estimate: dofForm.cost_estimate === '' ? null : Number(dofForm.cost_estimate),
      }),
    });
    openDetail(detail.id);
    load();
  }

  async function completeDof(dofId) {
    const note = window.prompt('Tamamlanma notu (isteğe bağlı):', '') || null;
    await api(`/risks/${detail.id}/dofs/${dofId}/complete`, {
      method: 'POST',
      body: JSON.stringify({completion_note: note}),
    });
    openDetail(detail.id);
    load();
  }

  async function uploadMedia(e) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file || !detail) return;
    try {
      await uploadFile(`/risks/${detail.id}/media`, file);
      openDetail(detail.id);
    } catch (ex) {
      window.alert(ex.message || 'Fotoğraf yüklenemedi.');
    }
  }

  async function removeMedia(mediaId) {
    if (!detail || !window.confirm('Bu fotoğrafı silmek istiyor musunuz?')) return;
    try {
      await api(`/risks/${detail.id}/media/${mediaId}`, {method: 'DELETE'});
      openDetail(detail.id);
    } catch (ex) {
      window.alert(ex.message || 'Silinemedi.');
    }
  }

  async function downloadReport(kind) {
    const cid = reportCompanyId || user.company_id || companies[0]?.id;
    if (!cid) {
      alert('Rapor için firma seçiniz.');
      return;
    }
    const params = new URLSearchParams({company_id: String(cid)});
    if (levelFilter) params.set('level', levelFilter);
    setDlBusy(kind);
    try {
      const ext = kind === 'pdf' ? 'pdf' : 'xlsx';
      await downloadFile(`/risks/report.${ext}?${params}`, `risk-raporu-${cid}.${ext}`);
    } catch (x) {
      alert((kind === 'pdf' ? 'PDF' : 'Excel') + ' indirilemedi:\n' + x.message);
    } finally {
      setDlBusy('');
    }
  }

  const companyBranches = useMemo(
    () => branches.filter((b) => String(b.company_id) === String(form.company_id)),
    [branches, form.company_id],
  );

  const selectedHazard = hazards.find((h) => String(h.id) === String(form.hazard_id));
  const totalHazards = categories.reduce((s, c) => s + (c.hazard_count || 0), 0);

  return (
    <>
      <div className="page-title">
        <h3>Risk Analizi</h3>
        <div className="actions">
          <button className="secondary" type="button" onClick={() => setLibOpen(true)}>
            <BookOpen size={16} /> Tehlike Kütüphanesi ({categories.length} kategori)
          </button>
          <button className="secondary" type="button" disabled={!!dlBusy} onClick={() => downloadReport('pdf')}>
            <Download size={16} /> {dlBusy === 'pdf' ? 'PDF…' : 'PDF Rapor'}
          </button>
          <button className="secondary" type="button" disabled={!!dlBusy} onClick={() => downloadReport('xlsx')}>
            <Download size={16} /> {dlBusy === 'xlsx' ? 'Excel…' : 'Excel Rapor'}
          </button>
          {canEdit && (
            <button type="button" onClick={() => {
              setForm({...empty, company_id: user.company_id || companies[0]?.id || ''});
              setOpen(true);
              setErr('');
            }}>
              <Plus /> Yeni Risk
            </button>
          )}
        </div>
      </div>
      <section className="panel" style={detail ? {display: 'none'} : undefined}>
        <div style={{marginBottom: 12, padding: '10px 12px', background: '#eef5fb', borderRadius: 10, fontSize: 14}}>
          Risk kaydı için <strong>tehlike kategorisi → tehlike</strong> seçimi zorunludur.
          İşyeri bölümlerini listeden seçin veya <strong>yeni bölüm</strong> yazarak kaydedin.
          PDF/Excel raporları seçili firmadaki (ve seviye filtresindeki) riskleri + DÖF’leri içerir.
          {categories.length === 0 && (
            <span> Kütüphane boş görünüyorsa “Tehlike Kütüphanesi”nden yükleyin.</span>
          )}
        </div>
        <div className="search" style={{marginBottom: 12, flexWrap: 'wrap'}}>
          <Search size={19} />
          <input placeholder="Faaliyet, kod veya tanım ara..." value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && load()} />
          <select value={levelFilter} onChange={(e) => setLevelFilter(e.target.value)} style={{minWidth: 160}}>
            <option value="">Tüm seviyeler</option>
            {Object.keys(LEVEL_COLORS).map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
          {!user.company_id && (
            <select
              value={reportCompanyId}
              onChange={(e) => {
                setReportCompanyId(e.target.value);
              }}
              style={{minWidth: 180}}
            >
              <option value="">Firma seçiniz</option>
              {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          )}
          <button className="secondary" type="button" onClick={() => load().catch((e) => setErr(e.message))}>Ara</button>
        </div>
        {err && <div className="error">{err}</div>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Kod</th>
                <th>Bölüm</th>
                <th>Faaliyet</th>
                <th>Tehlike</th>
                <th>Seviye</th>
                <th>Termin</th>
                <th>Durum</th>
                <th>İşlem</th>
              </tr>
            </thead>
            <tbody>
              {rows.length ? rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.risk_code}</td>
                  <td>{r.department_name || '—'}</td>
                  <td>{r.activity}</td>
                  <td>{r.hazard_code ? `${r.hazard_code} — ${r.hazard_name}` : r.hazard_id}</td>
                  <td><LevelBadge level={r.risk_level} score={r.risk_score} /></td>
                  <td>{r.term_date || '—'}</td>
                  <td>{r.status}</td>
                  <td>
                    <button className="mini" type="button" onClick={() => openDetail(r.id)}>Detay</button>
                    {canEdit && r.status === 'Açık' && (
                      <button className="mini" type="button" onClick={() => complete(r.id)}>Tamamla</button>
                    )}
                  </td>
                </tr>
              )) : (
                <tr><td colSpan={8} className="empty">Risk kaydı yok. Tehlike kütüphanesinden seçerek yeni kayıt ekleyin.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {libOpen && (
        <Modal title={`Tehlike Kütüphanesi — ${categories.length} kategori / ~${totalHazards} tehlike`} close={() => setLibOpen(false)} wide>
          <div style={{display: 'grid', gap: 12}}>
            <div style={{display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center'}}>
              {canEdit && (
                <button type="button" disabled={busy} onClick={seedLibrary}>
                  {busy ? 'Yükleniyor…' : 'Kütüphaneyi Yenile / Yükle (552 tehlike)'}
                </button>
              )}
              {libMsg && <span style={{fontSize: 13, color: '#087b67'}}>{libMsg}</span>}
            </div>
            <p style={{margin: 0, fontSize: 14, color: '#52677a'}}>
              Kategoriye tıklayınca o kategorinin tehlikeleri listelenir. Bir tehlikeye tıklayınca yeni risk formuna aktarılır.
            </p>
            <div style={{display: 'grid', gridTemplateColumns: '280px 1fr', gap: 12, minHeight: 360}}>
              <div style={{border: '1px solid #dbe4ee', borderRadius: 10, overflow: 'auto', maxHeight: 420}}>
                {categories.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    className={String(form.category_id) === String(c.id) ? 'active' : ''}
                    style={{
                      display: 'block', width: '100%', textAlign: 'left', padding: '10px 12px',
                      border: 'none', borderBottom: '1px solid #eef2f6', background: String(form.category_id) === String(c.id) ? '#e8f1fb' : 'transparent', cursor: 'pointer',
                    }}
                    onClick={() => setForm((f) => ({...f, category_id: String(c.id), hazard_id: '', hazard_q: ''}))}
                  >
                    <strong style={{fontSize: 13}}>{c.name}</strong>
                    <div style={{fontSize: 12, color: '#64748b'}}>{c.hazard_count || 0} tehlike</div>
                  </button>
                ))}
                {!categories.length && <div className="empty" style={{padding: 16}}>Kategori yok — yükleyin.</div>}
              </div>
              <div>
                <div className="search" style={{marginBottom: 8}}>
                  <Search size={16} />
                  <input
                    placeholder="Kod veya tehlike adı ara (ör. FZK-001, gürültü)..."
                    value={form.hazard_q}
                    onChange={(e) => setForm({...form, hazard_q: e.target.value})}
                    disabled={!form.category_id}
                  />
                </div>
                <div className="table-wrap" style={{maxHeight: 360, overflow: 'auto'}}>
                  <table>
                    <thead>
                      <tr><th>Kod</th><th>Tehlike</th><th>Varsayılan P/Ş</th><th></th></tr>
                    </thead>
                    <tbody>
                      {hazards.length ? hazards.map((h) => (
                        <tr key={h.id}>
                          <td>{h.code}</td>
                          <td>
                            <strong>{h.name}</strong>
                            <div style={{fontSize: 12, color: '#64748b'}}>{h.description?.slice(0, 120)}</div>
                          </td>
                          <td>{h.default_probability || '—'} / {h.default_severity || '—'}</td>
                          <td>
                            {canEdit && (
                              <button className="mini" type="button" onClick={() => {
                                onHazardPick(h.id);
                                setLibOpen(false);
                                setOpen(true);
                              }}>
                                Seç
                              </button>
                            )}
                          </td>
                        </tr>
                      )) : (
                        <tr><td colSpan={4} className="empty">{form.category_id ? 'Tehlike bulunamadı' : 'Soldan kategori seçin'}</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </Modal>
      )}

      {open && (
        <Modal title="Yeni Risk Değerlendirmesi" close={() => setOpen(false)} wide>
          <form className="form-grid" onSubmit={save}>
            <Select label="Firma / İşyeri" required value={form.company_id} onChange={(e) => setForm({...form, company_id: e.target.value, branch_id: '', department_id: '', new_department: ''})}>
              <option value="">Seçiniz</option>
              {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
            <Select label="Şube" value={form.branch_id} onChange={(e) => setForm({...form, branch_id: e.target.value})}>
              <option value="">Şube seçilmedi</option>
              {companyBranches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </Select>

            <Select
              label="İşyeri / Fabrika Bölümü"
              value={form.department_id}
              onChange={(e) => setForm({...form, department_id: e.target.value, new_department: ''})}
            >
              <option value="">Bölüm seçiniz</option>
              {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </Select>
            <div className="field">
              <span>Yeni bölüm (listede yoksa)</span>
              <div style={{display: 'flex', gap: 8}}>
                <input
                  placeholder="Örn: Üretim, Bakım, Boyahane..."
                  value={form.new_department}
                  onChange={(e) => setForm({...form, new_department: e.target.value, department_id: ''})}
                />
                <button type="button" className="secondary" disabled={busy || !form.new_department.trim()} onClick={addDepartmentQuick}>
                  Kaydet
                </button>
              </div>
              <small style={{color: '#64748b'}}>Yeni adı yazıp Kaydet veya doğrudan risk kaydederken otomatik oluşturulur.</small>
            </div>

            <div className="field" style={{gridColumn: '1 / -1'}}>
              <span>Tehlike kütüphanesi seçimi (zorunlu)</span>
              <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6}}>
                <button type="button" className="secondary" onClick={() => setLibOpen(true)}>
                  <BookOpen size={16} /> Kütüphaneden Seç
                </button>
                {selectedHazard && (
                  <span style={{alignSelf: 'center', fontSize: 14}}>
                    Seçili: <strong>{selectedHazard.code} — {selectedHazard.name}</strong>
                  </span>
                )}
              </div>
            </div>

            <Select label="Tehlike kategorisi" required value={form.category_id} onChange={(e) => setForm({...form, category_id: e.target.value, hazard_id: '', hazard_q: ''})}>
              <option value="">Seçiniz ({categories.length} kategori)</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.name} ({c.hazard_count || 0})</option>
              ))}
            </Select>
            <Field
              label="Tehlike ara"
              placeholder="FZK-001 veya gürültü..."
              value={form.hazard_q}
              onChange={(e) => setForm({...form, hazard_q: e.target.value})}
              disabled={!form.category_id}
            />
            <Select label="Tehlike" required value={form.hazard_id} onChange={(e) => onHazardPick(e.target.value)} style={{gridColumn: '1 / -1'}}>
              <option value="">Kütüphaneden seçiniz ({hazards.length})</option>
              {hazards.map((h) => <option key={h.id} value={h.id}>{h.code} — {h.name}</option>)}
            </Select>

            <Field label="Faaliyet" required value={form.activity} onChange={(e) => setForm({...form, activity: e.target.value})} />
            <TextArea label="Risk tanımı" required value={form.risk_definition} onChange={(e) => setForm({...form, risk_definition: e.target.value})} />
            <Field label="Etkilenen kişiler" value={form.affected_people} onChange={(e) => setForm({...form, affected_people: e.target.value})} />
            <Select label="Etkilenen grup" value={form.affected_group} onChange={(e) => setForm({...form, affected_group: e.target.value})}>
              {(meta?.affected_groups || ['Çalışan', 'Ziyaretçi', 'Müteahhit', 'Çevre']).map((g) => <option key={g}>{g}</option>)}
            </Select>
            <TextArea label="Mevcut önlemler" value={form.existing_measures} onChange={(e) => setForm({...form, existing_measures: e.target.value})} />
            <TextArea label="Ek önlemler" value={form.additional_measures} onChange={(e) => setForm({...form, additional_measures: e.target.value})} />
            <Select label="Olasılık (1-5)" value={form.probability} onChange={(e) => setForm({...form, probability: e.target.value})}>
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>{n} — {(meta?.probability_labels || {})[n] || n}</option>
              ))}
            </Select>
            <Select label="Şiddet (1-5)" value={form.severity} onChange={(e) => setForm({...form, severity: e.target.value})}>
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>{n} — {(meta?.severity_labels || {})[n] || n}</option>
              ))}
            </Select>
            {calc && (
              <div className="field" style={{gridColumn: '1 / -1'}}>
                <span>Hesaplanan risk</span>
                <div style={{display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap'}}>
                  <LevelBadge level={calc.risk_level} score={calc.risk_score} />
                  <span>Termin: {calc.term_label} ({calc.term_date})</span>
                </div>
              </div>
            )}
            {suggestions && (
              <div className="field" style={{gridColumn: '1 / -1'}}>
                <span>Öneri motoru (kategori)</span>
                <ul style={{margin: 0, paddingLeft: 18, fontSize: 13}}>
                  {(suggestions.ppe || []).slice(0, 3).map((x) => <li key={x}>KKD: {x}</li>)}
                  {(suggestions.engineering_measures || []).slice(0, 2).map((x) => <li key={x}>Müh.: {x}</li>)}
                </ul>
              </div>
            )}
            {err && <div className="error" style={{gridColumn: '1 / -1'}}>{err}</div>}
            <div className="form-actions" style={{gridColumn: '1 / -1'}}>
              <button type="submit">Kaydet</button>
            </div>
          </form>
        </Modal>
      )}

      {detail && (
        <section className="panel doc-workspace">
          <div className="doc-head">
            <div>
              <h3>{detail.risk_code} — Risk Detayı / DÖF</h3>
              <p style={{margin: '6px 0 0', color: '#64748b', fontSize: 14}}>
                Uygulama içinde kalın · DÖF ekle / tamamla
              </p>
            </div>
            <button type="button" className="secondary" onClick={() => setDetail(null)}>Listeye dön</button>
          </div>
          <div className="form-grid">
            <div className="field"><span>Bölüm</span><strong>{detail.department_name || '—'}</strong></div>
            <div className="field"><span>Faaliyet</span><strong>{detail.activity}</strong></div>
            <div className="field"><span>Tehlike</span><strong>{detail.hazard_code} — {detail.hazard_name}</strong></div>
            <div className="field"><span>Seviye</span><LevelBadge level={detail.risk_level} score={detail.risk_score} /></div>
            <div className="field"><span>Termin</span><strong>{detail.term_date || '—'}</strong></div>
            <div className="field" style={{gridColumn: '1 / -1'}}><span>Tanım</span><p>{detail.risk_definition}</p></div>
            <div className="field" style={{gridColumn: '1 / -1'}}><span>Mevcut önlemler</span><p>{detail.existing_measures || '—'}</p></div>
            <div className="field" style={{gridColumn: '1 / -1'}}><span>Ek önlemler</span><p>{detail.additional_measures || '—'}</p></div>
          </div>

          <h4 style={{marginTop: 16}}>Fotoğraf / medya</h4>
          <div style={{display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-start', marginBottom: 8}}>
            {(detail.media || []).map((m) => (
              <div key={m.id} style={{textAlign: 'center'}}>
                <AuthThumb path={`/risks/${detail.id}/media/${m.id}`} alt={m.original_name || ''} />
                <div style={{fontSize: 11, color: '#64748b', maxWidth: 96, overflow: 'hidden', textOverflow: 'ellipsis'}}>
                  {m.original_name || `#${m.id}`}
                </div>
                {canEdit && (
                  <button className="mini" type="button" onClick={() => removeMedia(m.id)} style={{marginTop: 4}}>
                    Sil
                  </button>
                )}
              </div>
            ))}
            {!((detail.media || []).length) && (
              <span style={{color: '#64748b', fontSize: 14}}>Henüz fotoğraf yok</span>
            )}
          </div>
          {canEdit && (
            <label className="field" style={{display: 'inline-flex', alignItems: 'center', gap: 8, cursor: 'pointer'}}>
              <span className="mini" style={{pointerEvents: 'none'}}>Fotoğraf ekle</span>
              <input type="file" accept="image/jpeg,image/png,image/webp,image/gif" onChange={uploadMedia} style={{display: 'none'}} />
            </label>
          )}

          <h4 style={{marginTop: 16}}>DÖF kayıtları</h4>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Kod</th>
                  <th>Yapılacak iş</th>
                  <th>Sorumlu</th>
                  <th>Termin</th>
                  <th>Maliyet</th>
                  <th>Durum</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {(detail.dofs || []).length ? detail.dofs.map((d) => (
                  <tr key={d.id}>
                    <td>{d.dof_code}</td>
                    <td>
                      <div>{d.description}</div>
                      {d.completion_note && (
                        <div style={{fontSize: 12, color: '#64748b', marginTop: 4}}>Not: {d.completion_note}</div>
                      )}
                    </td>
                    <td>
                      {d.responsible_person || '—'}
                      {d.responsible_department ? (
                        <div style={{fontSize: 12, color: '#64748b'}}>{d.responsible_department}</div>
                      ) : null}
                    </td>
                    <td>{d.term_date || '—'}</td>
                    <td>{d.cost_estimate != null ? `${d.cost_estimate} ${d.currency || 'TRY'}` : '—'}</td>
                    <td>{d.status}</td>
                    <td>
                      {canEdit && !d.is_completed && (
                        <button className="mini" type="button" onClick={() => completeDof(d.id)}>Tamamla</button>
                      )}
                    </td>
                  </tr>
                )) : (
                  <tr><td colSpan={7} className="empty">DÖF yok</td></tr>
                )}
              </tbody>
            </table>
          </div>
          {canEdit && (
            <form className="form-grid" onSubmit={addDof} style={{marginTop: 12}}>
              <TextArea
                label="Yapılacak iş / DÖF açıklaması"
                required
                value={dofForm.description}
                onChange={(e) => setDofForm({...dofForm, description: e.target.value})}
                style={{gridColumn: '1 / -1'}}
              />
              <Field
                label="Sorumlu kişi"
                value={dofForm.responsible_person}
                onChange={(e) => setDofForm({...dofForm, responsible_person: e.target.value})}
              />
              <Field
                label="Sorumlu bölüm"
                value={dofForm.responsible_department}
                onChange={(e) => setDofForm({...dofForm, responsible_department: e.target.value})}
              />
              <Field
                label="Termin tarihi"
                type="date"
                value={dofForm.term_date}
                onChange={(e) => setDofForm({...dofForm, term_date: e.target.value})}
              />
              <Field
                label="Maliyet tahmini (TRY)"
                type="number"
                min="0"
                value={dofForm.cost_estimate}
                onChange={(e) => setDofForm({...dofForm, cost_estimate: e.target.value})}
              />
              <div className="form-actions" style={{gridColumn: '1 / -1'}}>
                <button type="submit">DÖF Ekle</button>
              </div>
            </form>
          )}
        </section>
      )}
    </>
  );
}
