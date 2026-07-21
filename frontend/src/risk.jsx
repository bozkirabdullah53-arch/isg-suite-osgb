import React, {useEffect, useMemo, useState} from 'react';
import {AlertTriangle, BookOpen, Building2, ClipboardList, Download, LayoutDashboard, Plus, Search, X} from 'lucide-react';
import {api, downloadFile, uploadFile, authBlobUrl} from './api';

const LEVEL_COLORS = {
  'Kabul Edilebilir': '#95a5a6',
  'Düşük': '#2ecc71',
  'Orta': '#f1c40f',
  'Yüksek': '#f39c12',
  'Çok Yüksek': '#e74c3c',
};

const SUGGESTED_FALLBACK = [
  'İdari Ofis', 'Üretim', 'Bakım', 'Depo', 'Sevkiyat', 'Laboratuvar',
  'Kimyasal Depo', 'Elektrik Odası', 'Kazan Dairesi', 'Atölye',
  'İnşaat Sahası', 'Çatı', 'Vinç Sahası',
];

function isOverdueDate(d) {
  if (!d) return false;
  try {
    const t = new Date(d);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return t < today;
  } catch {
    return false;
  }
}

function OverdueBadge() {
  return (
    <span style={{
      display: 'inline-block', marginLeft: 6, padding: '2px 8px', borderRadius: 999,
      background: '#fee2e2', color: '#b91c1c', fontSize: 11, fontWeight: 800,
    }}>
      Gecikti
    </span>
  );
}

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
  const fieldRole = ['safety_specialist', 'workplace_physician', 'other_health_personnel'].includes(user.role);
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
  const [editId, setEditId] = useState(null);
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
  const [tab, setTab] = useState('panel');
  const [stats, setStats] = useState(null);
  const [dofs, setDofs] = useState([]);
  const [dofFilter, setDofFilter] = useState('open');
  const [statusFilter, setStatusFilter] = useState('');
  const [depForm, setDepForm] = useState({name: '', description: ''});
  const [hazardHint, setHazardHint] = useState(null);
  const [hintBusy, setHintBusy] = useState(false);
  const [photoTagCatalog, setPhotoTagCatalog] = useState([]);
  const [selectedPhotoTags, setSelectedPhotoTags] = useState([]);

  const effectiveCompanyId = reportCompanyId || user.company_id || companies[0]?.id || '';

  const loadStats = async (cid) => {
    const id = cid || effectiveCompanyId;
    if (!id) { setStats(null); return; }
    try {
      setStats(await api(`/risks/stats?company_id=${id}`));
    } catch (_) {
      setStats(null);
    }
  };

  const loadDofs = async (cid) => {
    const id = cid || effectiveCompanyId;
    if (!id) { setDofs([]); return; }
    const params = new URLSearchParams({company_id: String(id)});
    if (dofFilter === 'open') params.set('status', 'open');
    if (dofFilter === 'done') params.set('status', 'done');
    if (dofFilter === 'overdue') params.set('overdue_only', 'true');
    try {
      setDofs(await api(`/risks/dofs?${params}`));
    } catch (_) {
      setDofs([]);
    }
  };
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
    if (cid) {
      await loadDepartments(cid);
      await loadStats(cid);
    }
  };

  useEffect(() => {
    if (!canEdit) return;
    api('/risks/photo-tag-catalog')
      .then((r) => setPhotoTagCatalog(r.items || []))
      .catch(() => setPhotoTagCatalog([]));
  }, [canEdit]);

  useEffect(() => {
    if (!user.company_id && !reportCompanyId) {
      // global admin: companies yüklenene kadar bekle
      load().catch((e) => setErr(e.message));
      return;
    }
    load().catch((e) => setErr(e.message));
  }, [reportCompanyId, levelFilter]);

  useEffect(() => {
    if (tab === 'dofs' || tab === 'panel') {
      loadDofs().catch(() => {});
    }
  }, [tab, dofFilter, reportCompanyId, effectiveCompanyId]);
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

  useEffect(() => {
    if (!fieldRole || !open) {
      setHazardHint(null);
      return;
    }
    const activity = (form.activity || '').trim();
    const definition = (form.risk_definition || '').trim();
    if (activity.length + definition.length < 4) {
      setHazardHint(null);
      return;
    }
    let cancelled = false;
    const t = setTimeout(() => {
      setHintBusy(true);
      api('/risks/hazard-hint', {
        method: 'POST',
        body: JSON.stringify({activity, risk_definition: definition}),
      })
        .then((h) => { if (!cancelled) setHazardHint(h); })
        .catch(() => { if (!cancelled) setHazardHint(null); })
        .finally(() => { if (!cancelled) setHintBusy(false); });
    }, 450);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [fieldRole, open, form.activity, form.risk_definition]);

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
    } else if (!editId) {
      setErr('Bölüm seçiniz veya yeni bölüm adı giriniz.');
      return;
    }
    try {
      if (editId) {
        await api(`/risks/${editId}`, {method: 'PATCH', body: JSON.stringify(payload)});
      } else {
        await api('/risks', {
          method: 'POST',
          body: JSON.stringify({...payload, company_id: Number(form.company_id)}),
        });
      }
      const savedId = editId;
      setOpen(false);
      setEditId(null);
      setForm(empty);
      setSuggestions(null);
      await load();
      if (savedId) await openDetail(savedId);
    } catch (x) {
      setErr(x.message);
    }
  }

  function openCreate() {
    setEditId(null);
    setErr('');
    setSuggestions(null);
    setHazardHint(null);
    setForm({
      ...empty,
      company_id: reportCompanyId || user.company_id || companies[0]?.id || '',
    });
    setOpen(true);
  }

  function applyHazardHint(hint) {
    if (!hint?.suggested_category) return;
    const catId = hint.category_id
      || categories.find((c) => c.name === hint.suggested_category)?.id;
    setForm((f) => ({
      ...f,
      category_id: catId ? String(catId) : f.category_id,
      hazard_id: catId && String(catId) !== String(f.category_id) ? '' : f.hazard_id,
      probability: hint.probability_hint || f.probability,
    }));
  }

  async function openEdit(riskOrId) {
    setErr('');
    setBusy(true);
    try {
      const id = typeof riskOrId === 'object' ? riskOrId.id : riskOrId;
      const r = typeof riskOrId === 'object' && riskOrId.risk_code
        ? riskOrId
        : await api(`/risks/${id}`);
      setEditId(r.id);
      setDetail(null);
      setForm({
        ...empty,
        company_id: String(r.company_id || ''),
        branch_id: r.branch_id ? String(r.branch_id) : '',
        department_id: r.department_id ? String(r.department_id) : '',
        department_name: r.department_name || '',
        new_department: '',
        category_id: '',
        hazard_id: String(r.hazard_id || ''),
        hazard_q: '',
        activity: r.activity || '',
        risk_definition: r.risk_definition || '',
        affected_people: r.affected_people || '',
        affected_group: r.affected_group || 'Çalışan',
        existing_measures: r.existing_measures || '',
        additional_measures: r.additional_measures || '',
        probability: r.probability || 3,
        severity: r.severity || 3,
      });
      if (r.hazard_id) {
        try {
          const d = await api(`/risks/hazards/${r.hazard_id}`);
          setSuggestions(d.suggestions || null);
          setForm((f) => ({
            ...f,
            category_id: String(d.hazard?.category_id || ''),
            hazard_id: String(r.hazard_id),
          }));
        } catch (_) {
          setSuggestions(null);
        }
      }
      setOpen(true);
    } catch (x) {
      setErr(x.message);
    } finally {
      setBusy(false);
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
    setTab('risks');
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
      const extra = selectedPhotoTags.length
        ? {tags: JSON.stringify(selectedPhotoTags)}
        : null;
      await uploadFile(`/risks/${detail.id}/media`, file, extra);
      setSelectedPhotoTags([]);
      openDetail(detail.id);
    } catch (ex) {
      window.alert(ex.message || 'Fotoğraf yüklenemedi.');
    }
  }

  function togglePhotoTag(code) {
    setSelectedPhotoTags((prev) => (
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    ));
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

  async function removeRisk(id) {
    if (!window.confirm('Bu risk kaydını silmek istiyor musunuz?')) return;
    try {
      await api(`/risks/${id}`, {method: 'DELETE'});
      setDetail(null);
      await load();
      await loadDofs();
    } catch (x) {
      alert(x.message);
    }
  }

  async function removeDof(riskId, dofId) {
    if (!window.confirm('Bu DÖF kaydını silmek istiyor musunuz?')) return;
    try {
      await api(`/risks/${riskId}/dofs/${dofId}`, {method: 'DELETE'});
      if (detail?.id === riskId) await openDetail(riskId);
      await loadDofs();
      await loadStats();
    } catch (x) {
      alert(x.message);
    }
  }

  async function saveDepartment(e) {
    e?.preventDefault?.();
    const name = (depForm.name || '').trim();
    if (!name || !effectiveCompanyId) {
      setErr('Bölüm adı ve firma gerekli.');
      return;
    }
    setBusy(true);
    try {
      await api('/risks/departments', {
        method: 'POST',
        body: JSON.stringify({
          company_id: Number(effectiveCompanyId),
          name,
          description: depForm.description || null,
        }),
      });
      setDepForm({name: '', description: ''});
      await loadDepartments(effectiveCompanyId);
      await loadStats(effectiveCompanyId);
    } catch (x) {
      setErr(x.message);
    } finally {
      setBusy(false);
    }
  }

  async function addSuggestedDept(name) {
    if (!effectiveCompanyId) return;
    setBusy(true);
    try {
      await api('/risks/departments', {
        method: 'POST',
        body: JSON.stringify({company_id: Number(effectiveCompanyId), name}),
      });
      await loadDepartments(effectiveCompanyId);
      await loadStats(effectiveCompanyId);
    } catch (x) {
      setErr(x.message);
    } finally {
      setBusy(false);
    }
  }

  async function deactivateDepartment(id) {
    if (!window.confirm('Bölümü pasifleştirmek istiyor musunuz?')) return;
    try {
      await api(`/risks/departments/${id}`, {method: 'DELETE'});
      await loadDepartments(effectiveCompanyId);
      await loadStats(effectiveCompanyId);
    } catch (x) {
      alert(x.message);
    }
  }

  const filteredRows = useMemo(() => {
    if (!statusFilter) return rows;
    return rows.filter((r) => (r.status || '') === statusFilter);
  }, [rows, statusFilter]);

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
            <button type="button" onClick={openCreate}>
              <Plus /> Yeni Risk
            </button>
          )}
        </div>
      </div>

      <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14}}>
        {[
          ['panel', 'Ana Panel', LayoutDashboard],
          ['risks', 'Riskler', AlertTriangle],
          ['dofs', 'DÖF Listesi', ClipboardList],
          ['departments', 'Bölümler', Building2],
        ].map(([id, label, Icon]) => (
          <button
            key={id}
            type="button"
            className={tab === id ? '' : 'secondary'}
            onClick={() => { setTab(id); setDetail(null); }}
            style={{display: 'inline-flex', alignItems: 'center', gap: 8}}
          >
            <Icon size={16} /> {label}
          </button>
        ))}
        {!user.company_id && (
          <select
            value={reportCompanyId}
            onChange={(e) => setReportCompanyId(e.target.value)}
            style={{minWidth: 180, marginLeft: 'auto', borderRadius: 10, padding: '8px 10px', border: '1px solid #cbdde1'}}
          >
            <option value="">Firma seçiniz</option>
            {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        )}
      </div>

      {tab === 'panel' && !detail && (
        <section className="panel" style={{marginBottom: 16}}>
          <div className="welcome" style={{marginBottom: 16}}>
            <div>
              <h3>Risk Değerlendirme Paneli</h3>
              <p>PRO 2026 uyumlu özet: açık riskler, seviye dağılımı ve geciken DÖF kayıtları.</p>
            </div>
          </div>
          <div className="cards">
            <article className="metric"><span>Toplam Risk</span><strong>{stats?.total_risks ?? '—'}</strong></article>
            <article className="metric"><span>Çok Yüksek</span><strong style={{color: '#e74c3c'}}>{stats?.very_high ?? '—'}</strong></article>
            <article className="metric"><span>Açık DÖF</span><strong>{stats?.open_dofs ?? '—'}</strong></article>
            <article className="metric"><span>Geciken DÖF</span><strong style={{color: '#b91c1c'}}>{stats?.overdue_dofs ?? '—'}</strong></article>
          </div>
          <div className="cards" style={{marginTop: 0}}>
            <article className="metric"><span>Açık Risk</span><strong>{stats?.open_risks ?? '—'}</strong></article>
            <article className="metric"><span>Yüksek</span><strong style={{color: '#f39c12'}}>{stats?.high ?? '—'}</strong></article>
            <article className="metric"><span>Geciken Termin</span><strong>{stats?.overdue_terms ?? '—'}</strong></article>
            <article className="metric"><span>7 Gün İçinde DÖF</span><strong>{stats?.due_soon_dofs ?? '—'}</strong></article>
          </div>
          {(stats?.departments || []).length > 0 && (
            <div style={{marginTop: 8}}>
              <h4 style={{marginTop: 0}}>Bölüm yoğunluğu</h4>
              <div style={{display: 'flex', flexWrap: 'wrap', gap: 8}}>
                {stats.departments.slice(0, 12).map((d) => (
                  <span key={d.name} style={{padding: '6px 10px', background: '#f1f5f9', borderRadius: 999, fontSize: 13}}>
                    {d.name}: <strong>{d.count}</strong>
                  </span>
                ))}
              </div>
            </div>
          )}
          {err && <div className="error" style={{marginTop: 12}}>{err}</div>}
        </section>
      )}

      {tab === 'departments' && !detail && (
        <section className="panel" style={{marginBottom: 16}}>
          <h3 style={{marginTop: 0}}>Bölüm Yönetimi</h3>
          <p style={{color: '#64748b', fontSize: 14}}>PRO gibi işyeri bölümlerini ekleyin, önerilenlerden tek tıkla oluşturun.</p>
          <div style={{display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: 16}}>
            <form className="form-grid" onSubmit={saveDepartment} style={{alignContent: 'start'}}>
              <Field label="Bölüm Adı" required value={depForm.name} onChange={(e) => setDepForm({...depForm, name: e.target.value})} placeholder="Üretim, Depo..." />
              <Field label="Açıklama" value={depForm.description} onChange={(e) => setDepForm({...depForm, description: e.target.value})} />
              <div className="form-actions" style={{gridColumn: '1 / -1'}}>
                <button type="submit" disabled={busy}>Bölüm Ekle</button>
              </div>
              <div className="field" style={{gridColumn: '1 / -1'}}>
                <span>Önerilen bölümler</span>
                <div style={{display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6}}>
                  {(stats?.suggested_departments || SUGGESTED_FALLBACK)
                    .filter((n) => !departments.some((d) => d.name === n))
                    .map((n) => (
                      <button key={n} type="button" className="mini secondary" disabled={busy} onClick={() => addSuggestedDept(n)}>
                        + {n}
                      </button>
                    ))}
                </div>
              </div>
            </form>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Bölüm</th><th>Açıklama</th><th>Risk</th><th></th></tr>
                </thead>
                <tbody>
                  {departments.length ? departments.map((d) => (
                    <tr key={d.id}>
                      <td>{d.name}</td>
                      <td>{d.description || '—'}</td>
                      <td>{d.risk_count ?? 0}</td>
                      <td>
                        {canEdit && (
                          <button className="mini" type="button" onClick={() => deactivateDepartment(d.id)}>Pasifleştir</button>
                        )}
                      </td>
                    </tr>
                  )) : (
                    <tr><td colSpan={4} className="empty">Bölüm yok</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
          {err && <div className="error" style={{marginTop: 12}}>{err}</div>}
        </section>
      )}

      {tab === 'dofs' && !detail && (
        <section className="panel" style={{marginBottom: 16}}>
          <div style={{display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 12}}>
            <h3 style={{margin: 0}}>Firma Geneli DÖF Listesi</h3>
            <select value={dofFilter} onChange={(e) => setDofFilter(e.target.value)}>
              <option value="open">Açık</option>
              <option value="overdue">Geciken</option>
              <option value="done">Tamamlanan</option>
              <option value="all">Tümü</option>
            </select>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>DÖF</th>
                  <th>Risk</th>
                  <th>Açıklama</th>
                  <th>Sorumlu</th>
                  <th>Termin</th>
                  <th>Durum</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {dofs.length ? dofs.map((d) => (
                  <tr key={d.id}>
                    <td>{d.dof_code}</td>
                    <td>
                      <button className="mini" type="button" onClick={() => { setTab('risks'); openDetail(d.risk_id); }}>
                        {d.risk_code || d.risk_id}
                      </button>
                    </td>
                    <td>{d.description}</td>
                    <td>{d.responsible_person || '—'}</td>
                    <td>
                      {d.term_date || '—'}
                      {(d.is_overdue || (!d.is_completed && isOverdueDate(d.term_date))) && <OverdueBadge />}
                    </td>
                    <td>{d.status}</td>
                    <td>
                      {canEdit && !d.is_completed && (
                        <button
                          className="mini"
                          type="button"
                          onClick={async () => {
                            const note = window.prompt('Tamamlanma notu (isteğe bağlı):', '') || null;
                            try {
                              await api(`/risks/${d.risk_id}/dofs/${d.id}/complete`, {
                                method: 'POST',
                                body: JSON.stringify({completion_note: note}),
                              });
                              await loadDofs();
                              await loadStats();
                            } catch (x) {
                              alert(x.message);
                            }
                          }}
                        >
                          Tamamla
                        </button>
                      )}
                      {canEdit && (
                        <button className="mini" type="button" onClick={() => removeDof(d.risk_id, d.id)}>Sil</button>
                      )}
                    </td>
                  </tr>
                )) : (
                  <tr><td colSpan={7} className="empty">DÖF kaydı yok</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {(tab === 'risks' || tab === 'panel') && (
      <section className="panel" style={detail || tab === 'panel' ? {display: 'none'} : undefined}>
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
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{minWidth: 140}}>
            <option value="">Tüm durumlar</option>
            <option value="Açık">Açık</option>
            <option value="Tamamlandı">Tamamlandı</option>
          </select>
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
                <th>O</th>
                <th>Ş</th>
                <th>Seviye</th>
                <th>Termin</th>
                <th>DÖF</th>
                <th>Durum</th>
                <th>İşlem</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.length ? filteredRows.map((r) => (
                <tr key={r.id}>
                  <td>{r.risk_code}</td>
                  <td>{r.department_name || '—'}</td>
                  <td>{r.activity}</td>
                  <td>{r.hazard_code ? `${r.hazard_code} — ${r.hazard_name}` : r.hazard_id}</td>
                  <td>{r.probability}</td>
                  <td>{r.severity}</td>
                  <td><LevelBadge level={r.risk_level} score={r.risk_score} /></td>
                  <td>
                    {r.term_date || '—'}
                    {r.status === 'Açık' && isOverdueDate(r.term_date) && <OverdueBadge />}
                  </td>
                  <td>{r.dofs?.length || 0}</td>
                  <td>{r.status}</td>
                  <td>
                    <button className="mini" type="button" onClick={() => openDetail(r.id)}>Detay</button>
                    {canEdit && (
                      <button className="mini" type="button" onClick={() => openEdit(r)}>Düzenle</button>
                    )}
                    {canEdit && r.status === 'Açık' && (
                      <button className="mini" type="button" onClick={() => complete(r.id)}>Tamamla</button>
                    )}
                    {canEdit && (
                      <button className="mini" type="button" onClick={() => removeRisk(r.id)}>Sil</button>
                    )}
                  </td>
                </tr>
              )) : (
                <tr><td colSpan={11} className="empty">Risk kaydı yok. Tehlike kütüphanesinden seçerek yeni kayıt ekleyin.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
      )}

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
        <Modal
          title={editId ? `Risk Düzenle #${editId}` : 'Yeni Risk Değerlendirmesi'}
          close={() => { setOpen(false); setEditId(null); setErr(''); setHazardHint(null); }}
          wide
        >
          <form className="form-grid" onSubmit={save}>
            <Select
              label="Firma / İşyeri"
              required
              value={form.company_id}
              disabled={!!editId}
              onChange={(e) => setForm({...form, company_id: e.target.value, branch_id: '', department_id: '', new_department: ''})}
            >
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
            {fieldRole && open && (
              <div
                className="field"
                style={{
                  gridColumn: '1 / -1',
                  background: '#f0f7ff',
                  border: '1px solid #bfdbfe',
                  borderRadius: 8,
                  padding: '10px 12px',
                }}
              >
                <span style={{display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700}}>
                  <AlertTriangle size={16} /> Tehlike önerisi
                  <span style={{fontWeight: 500, color: '#64748b', fontSize: 12}}>(anahtar kelime · onay sizde)</span>
                </span>
                {hintBusy && <p style={{margin: '8px 0 0', fontSize: 13, color: '#64748b'}}>Öneri hesaplanıyor…</p>}
                {!hintBusy && hazardHint?.matched && (
                  <div style={{marginTop: 8, fontSize: 13}}>
                    <div>
                      Önerilen kategori: <strong>{hazardHint.suggested_category}</strong>
                      {hazardHint.probability_hint != null && (
                        <> · Olasılık ipucu: <strong>{hazardHint.probability_hint}/5</strong></>
                      )}
                      {hazardHint.confidence != null && (
                        <span style={{color: '#64748b'}}> · güven {Math.round(hazardHint.confidence * 100)}%</span>
                      )}
                    </div>
                    {(hazardHint.matched_keywords || []).length > 0 && (
                      <div style={{marginTop: 4, color: '#475569'}}>
                        Anahtarlar: {(hazardHint.matched_keywords || []).slice(0, 6).join(', ')}
                      </div>
                    )}
                    <button
                      type="button"
                      className="secondary"
                      style={{marginTop: 8}}
                      onClick={() => applyHazardHint(hazardHint)}
                    >
                      Kategori ve olasılığı uygula
                    </button>
                    <p style={{margin: '6px 0 0', color: '#64748b', fontSize: 12}}>{hazardHint.note}</p>
                  </div>
                )}
                {!hintBusy && hazardHint && !hazardHint.matched && (
                  <p style={{margin: '8px 0 0', fontSize: 13, color: '#64748b'}}>{hazardHint.note || 'Eşleşme yok.'}</p>
                )}
                {!hintBusy && !hazardHint && (
                  <p style={{margin: '8px 0 0', fontSize: 13, color: '#64748b'}}>
                    Faaliyet veya risk tanımına yazdıkça kategori önerisi çıkar.
                  </p>
                )}
              </div>
            )}
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
              <button type="submit">{editId ? 'Güncelle' : 'Kaydet'}</button>
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
                Revizyon: {detail.revision_no ?? 0} · Uygulama içinde düzenleme ve DÖF
              </p>
            </div>
            <div className="actions">
              {canEdit && (
                <button type="button" onClick={() => openEdit(detail)}>Düzenle</button>
              )}
              {canEdit && (
                <button type="button" className="secondary" onClick={() => removeRisk(detail.id)}>Sil</button>
              )}
              <button type="button" className="secondary" onClick={() => setDetail(null)}>Listeye dön</button>
            </div>
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
              <div key={m.id} style={{textAlign: 'center', maxWidth: 140}}>
                <AuthThumb path={`/risks/${detail.id}/media/${m.id}`} alt={m.original_name || ''} />
                <div style={{fontSize: 11, color: '#64748b', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis'}}>
                  {m.original_name || `#${m.id}`}
                </div>
                {(m.tag_labels || []).length > 0 && (
                  <div style={{fontSize: 10, color: '#0f766e', marginTop: 2, lineHeight: 1.3}}>
                    {(m.tag_labels || []).join(' · ')}
                  </div>
                )}
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
            <div style={{marginBottom: 10}}>
              <div style={{fontSize: 13, color: '#475569', marginBottom: 6}}>
                Tehlike etiketi (isteğe bağlı — yüklemeden önce seçin)
              </div>
              <div style={{display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8}}>
                {photoTagCatalog.map((t) => {
                  const on = selectedPhotoTags.includes(t.code);
                  return (
                    <button
                      key={t.code}
                      type="button"
                      className="mini"
                      onClick={() => togglePhotoTag(t.code)}
                      style={{
                        background: on ? '#0f766e' : '#f1f5f9',
                        color: on ? '#fff' : '#334155',
                        border: on ? '1px solid #0f766e' : '1px solid #cbd5e1',
                      }}
                    >
                      {t.label}
                    </button>
                  );
                })}
              </div>
              <label className="field" style={{display: 'inline-flex', alignItems: 'center', gap: 8, cursor: 'pointer'}}>
                <span className="mini" style={{pointerEvents: 'none'}}>Fotoğraf ekle</span>
                <input type="file" accept="image/jpeg,image/png,image/webp,image/gif" onChange={uploadMedia} style={{display: 'none'}} />
              </label>
            </div>
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
                      {canEdit && (
                        <button className="mini" type="button" onClick={() => removeDof(detail.id, d.id)}>Sil</button>
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
