import React, {useEffect, useMemo, useState} from 'react';
import {createPortal} from 'react-dom';
import {
  AlertTriangle,
  BookOpen,
  Building2,
  ClipboardList,
  Download,
  FileSpreadsheet,
  FileText,
  LayoutDashboard,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  X,
} from 'lucide-react';
import {api, downloadFile, uploadFile, authBlobUrl} from './api';
import './risk_pro.css';

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

function Modal({title, close, children, wide, layer}) {
  return createPortal(
    <div
      className={`modal-bg risk-modal-bg${layer === 'top' ? ' risk-modal-top' : ''}`}
      onMouseDown={(e) => e.target === e.currentTarget && close()}
    >
      <section className={`modal risk-modal${wide ? ' risk-modal-wide' : ''}`} role="dialog" aria-modal="true">
        <header className="risk-modal-head">
          <div>
            <p className="risk-modal-kicker">Risk değerlendirme</p>
            <h3>{title}</h3>
          </div>
          <button className="icon risk-modal-close" type="button" onClick={close} aria-label="Kapat">
            <X />
          </button>
        </header>
        <div className="risk-modal-body">{children}</div>
      </section>
    </div>,
    document.body,
  );
}

function Field({label, style, className, ...p}) {
  return (
    <label className={`field${className ? ` ${className}` : ''}`} style={style}>
      <span>{label}</span>
      <input {...p} />
    </label>
  );
}

function Select({label, children, style, className, ...p}) {
  return (
    <label className={`field${className ? ` ${className}` : ''}`} style={style}>
      <span>{label}</span>
      <select {...p}>{children}</select>
    </label>
  );
}

function TextArea({label, style, className, ...p}) {
  return (
    <label className={`field${className ? ` ${className}` : ''}`} style={style}>
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

function levelClass(level) {
  if (level === 'Çok Yüksek') return 'critical';
  if (level === 'Yüksek') return 'high';
  if (level === 'Orta') return 'medium';
  if (level === 'Düşük') return 'low';
  return 'acceptable';
}

function RiskMatrixGuide({probability, severity}) {
  const active = Number(probability) && Number(severity) ? Number(probability) * Number(severity) : null;
  return (
    <div className="risk-matrix-wrap">
      <div className="risk-matrix" aria-label="5x5 risk matrisi">
        <div className="risk-matrix-label">Ş\O</div>
        {[1, 2, 3, 4, 5].map((p) => (
          <div key={`p${p}`} className="risk-matrix-label">{p}</div>
        ))}
        {[1, 2, 3, 4, 5].map((s) => (
          <React.Fragment key={`row${s}`}>
            <div className="risk-matrix-label">{s}</div>
            {[1, 2, 3, 4, 5].map((p) => {
              const score = s * p;
              const cls = score <= 9 ? 'low' : score <= 14 ? 'medium' : score <= 19 ? 'high' : 'critical';
              const isActive = active === score && Number(severity) === s && Number(probability) === p;
              return (
                <div key={`${s}-${p}`} className={`risk-matrix-cell ${cls}${isActive ? ' active' : ''}`}>
                  {score}
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

export function RiskPage({user}) {
  const canEdit = ['global_admin', 'safety_specialist'].includes(user.role);
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

  async function applyHazardFromLibrary(hazard) {
    if (!hazard?.id) return;
    await onHazardPick(hazard.id);
    setLibOpen(false);
    setOpen(true);
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
    if (levelFilter && kind !== 'dof') params.set('level', levelFilter);
    const stamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '');
    setDlBusy(kind);
    try {
      if (kind === 'dof') {
        await downloadFile(`/risks/report/dof.xlsx?${params}`, `dof-listesi-${cid}-${stamp}.xlsx`);
      } else {
        const ext = kind === 'pdf' ? 'pdf' : 'xlsx';
        await downloadFile(`/risks/report.${ext}?${params}`, `risk-raporu-${cid}-${stamp}.${ext}`);
      }
    } catch (x) {
      const label = kind === 'pdf' ? 'PDF' : kind === 'dof' ? 'DÖF Excel' : 'Excel';
      alert(label + ' indirilemedi:\n' + x.message);
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
  const hazardCount = totalHazards;
  const companyName =
    companies.find((c) => String(c.id) === String(effectiveCompanyId))?.name ||
    'İşyeri';
  const companyHazard =
    companies.find((c) => String(c.id) === String(effectiveCompanyId))?.hazard_class || '';

  const priorityRisks = useMemo(() => {
    return [...rows]
      .filter((r) => (r.status || 'Açık') !== 'Tamamlandı' && (r.status || '') !== 'İptal')
      .filter((r) => r.risk_level === 'Çok Yüksek' || r.risk_level === 'Yüksek')
      .sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0))
      .slice(0, 8);
  }, [rows]);

  const recentRisks = useMemo(() => [...rows].slice(0, 8), [rows]);

  async function refreshAll() {
    setErr('');
    try {
      await Promise.all([
        load(),
        loadStats(effectiveCompanyId),
        loadDofs(effectiveCompanyId),
        loadDepartments(effectiveCompanyId),
        api('/risks/categories').then(setCategories).catch(() => {}),
      ]);
    } catch (x) {
      setErr(x.message || 'Yenileme başarısız');
    }
  }

  const TABS = [
    {id: 'panel', label: 'Merkez', Icon: LayoutDashboard},
    {id: 'risks', label: 'Kayıtlar', Icon: AlertTriangle},
    {id: 'library', label: 'Kütüphane', Icon: BookOpen, count: hazardCount || null},
    {id: 'dofs', label: 'Aksiyon', Icon: ClipboardList},
    {id: 'reports', label: 'Raporlar', Icon: FileText},
    {id: 'departments', label: 'Bölümler', Icon: Building2},
  ];

  return (
    <div className="risk-pro-root">
      <div className="risk-top">
        <div>
          <h1>Risk Değerlendirme</h1>
          <p>Tehlike puanlama, aksiyon takibi ve raporlama.</p>
          <div className="risk-scope">
            <span><Building2 size={12} /> {companyName}</span>
            {companyHazard ? <span><ShieldAlert size={12} /> {companyHazard}</span> : null}
            <span>5×5 matris</span>
          </div>
        </div>
        <div className="risk-top-actions">
          {!user.company_id && (
            <select
              value={reportCompanyId}
              onChange={(e) => setReportCompanyId(e.target.value)}
              aria-label="Firma seçimi"
            >
              <option value="">Firma seçiniz</option>
              {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          )}
          <button type="button" className="btn" onClick={refreshAll}>
            <RefreshCw size={14} /> Yenile
          </button>
          {canEdit && (
            <button type="button" className="btn btn-primary" onClick={openCreate}>
              <Plus size={14} /> Yeni Risk
            </button>
          )}
        </div>
      </div>

      <div className="risk-module-bar">
        <div className="risk-module-tabs">
          {TABS.map(({id, label, Icon, count}) => (
            <button
              key={id}
              type="button"
              className={`risk-module-tab${tab === id ? ' active' : ''}`}
              onClick={() => { setTab(id); setDetail(null); }}
            >
              <Icon size={14} /> {label}
              {count != null && count > 0 ? <span className="risk-tab-count">{count}</span> : null}
            </button>
          ))}
        </div>
      </div>

      {tab === 'panel' && !detail && (
        <>
          <section className="risk-kpi-grid" aria-label="Risk özeti">
            <div className="risk-kpi">
              <div className="risk-kpi-value">{stats?.total_risks ?? 0}</div>
              <div className="risk-kpi-label">Toplam risk</div>
              <div className="risk-kpi-note">{stats?.open_risks ?? 0} açık</div>
            </div>
            <div className="risk-kpi critical">
              <div className="risk-kpi-value">{stats?.very_high ?? 0}</div>
              <div className="risk-kpi-label">Çok yüksek</div>
              <div className="risk-kpi-note">Acil öncelik</div>
            </div>
            <div className="risk-kpi warning">
              <div className="risk-kpi-value">{stats?.open_dofs ?? 0}</div>
              <div className="risk-kpi-label">Açık DÖF</div>
              <div className="risk-kpi-note">{stats?.due_soon_dofs ?? 0} / 7 gün</div>
            </div>
            <div className={`risk-kpi ${(stats?.overdue_dofs || 0) > 0 ? 'critical' : 'success'}`}>
              <div className="risk-kpi-value">{stats?.overdue_dofs ?? 0}</div>
              <div className="risk-kpi-label">Geciken DÖF</div>
              <div className="risk-kpi-note">{stats?.overdue_terms ?? 0} risk termin</div>
            </div>
          </section>

          <section className="risk-work-grid">
            <article className="risk-panel">
              <div className="risk-panel-head">
                <div>
                  <h2>Öncelikli riskler</h2>
                  <p>Yüksek ve çok yüksek açık kayıtlar</p>
                </div>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setTab('risks')}>
                  Tümü
                </button>
              </div>
              <div className="risk-priority-list">
                {priorityRisks.length ? priorityRisks.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    className={`risk-priority-item${r.risk_level === 'Yüksek' ? ' high' : ''}`}
                    onClick={() => openDetail(r.id)}
                  >
                    <div className="risk-priority-mark">{r.risk_score}</div>
                    <div>
                      <div className="risk-priority-title">{r.activity}</div>
                      <div className="risk-priority-meta">
                        {r.risk_code} · {r.department_name || '—'}
                        {r.hazard_name ? ` · ${r.hazard_name}` : ''}
                      </div>
                    </div>
                    <div style={{textAlign: 'right'}}>
                      <span className={`risk-level-badge risk-level-${levelClass(r.risk_level)}`}>
                        {r.risk_level}
                      </span>
                      {r.term_date ? (
                        <div className="risk-priority-meta" style={{marginTop: 3}}>
                          {r.term_date}{isOverdueDate(r.term_date) ? ' · gecikti' : ''}
                        </div>
                      ) : null}
                    </div>
                  </button>
                )) : (
                  <div className="risk-empty">
                    <div>
                      <h3>Öncelikli açık risk yok</h3>
                      <p>Yeni kayıt ekleyebilir veya tüm listeyi inceleyebilirsiniz.</p>
                      {canEdit && (
                        <button type="button" className="btn btn-primary btn-sm" onClick={openCreate}>
                          İlk riski ekle
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </article>

            <aside className="risk-panel">
              <div className="risk-panel-head">
                <div>
                  <h2>5×5 matris</h2>
                  <p>Olasılık × şiddet</p>
                </div>
              </div>
              <RiskMatrixGuide />
              <div className="risk-distribution">
                {[
                  ['Çok yüksek', stats?.very_high || stats?.levels?.['Çok Yüksek'] || 0, '#b91c1c'],
                  ['Yüksek', stats?.high || stats?.levels?.Yüksek || 0, '#c2410c'],
                  ['Orta', stats?.levels?.Orta || 0, '#a16207'],
                  ['Düşük / Kabul', (stats?.levels?.Düşük || 0) + (stats?.levels?.['Kabul Edilebilir'] || 0), '#047857'],
                ].map(([label, count, color]) => {
                  const den = Math.max(stats?.total_risks || 1, 1);
                  return (
                    <div key={label} className="risk-distribution-row">
                      <span>{label}</span>
                      <div className="risk-progress">
                        <span style={{width: `${Math.round((count * 100) / den)}%`, background: color}} />
                      </div>
                      <strong>{count}</strong>
                    </div>
                  );
                })}
              </div>
            </aside>
          </section>

          <section className="risk-work-grid">
            <article className="risk-panel">
              <div className="risk-panel-head">
                <div>
                  <h2>Son kayıtlar</h2>
                  <p>En güncel riskler</p>
                </div>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setTab('risks')}>
                  Liste
                </button>
              </div>
              {recentRisks.length ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Kayıt</th>
                        <th>Faaliyet</th>
                        <th>Skor</th>
                        <th>Termin</th>
                        <th>Durum</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentRisks.map((r) => (
                        <tr key={r.id} onClick={() => openDetail(r.id)} style={{cursor: 'pointer'}}>
                          <td>
                            <strong>{r.risk_code}</strong>
                            <div style={{fontSize: 12, color: '#5b6b7c'}}>{r.department_name || '—'}</div>
                          </td>
                          <td>
                            <div>{r.activity}</div>
                            <div style={{fontSize: 12, color: '#5b6b7c'}}>{r.hazard_name || '—'}</div>
                          </td>
                          <td>
                            <span className={`risk-level-badge risk-level-${levelClass(r.risk_level)}`}>
                              {r.risk_score} · {r.risk_level}
                            </span>
                          </td>
                          <td>{r.term_date || '—'}</td>
                          <td>{r.status || 'Açık'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="risk-empty">
                  <div>
                    <h3>Henüz risk kaydı yok</h3>
                    <p>İlk kaydı oluşturarak değerlendirmeyi başlatın.</p>
                    {canEdit && (
                      <button type="button" className="btn btn-primary btn-sm" onClick={openCreate}>
                        Yeni risk
                      </button>
                    )}
                  </div>
                </div>
              )}
            </article>

            <aside className="risk-panel">
              <div className="risk-panel-head">
                <div>
                  <h2>Bölüm yoğunluğu</h2>
                  <p>Kayıt dağılımı</p>
                </div>
              </div>
              <div className="risk-distribution">
                {(stats?.departments || []).length ? (stats.departments.slice(0, 8).map((d) => {
                  const max = Math.max(...stats.departments.map((x) => x.count || 0), 1);
                  return (
                    <div key={d.name} className="risk-distribution-row">
                      <span title={d.name}>{String(d.name).slice(0, 16)}</span>
                      <div className="risk-progress">
                        <span style={{width: `${Math.round(((d.count || 0) * 100) / max)}%`}} />
                      </div>
                      <strong>{d.count}</strong>
                    </div>
                  );
                })) : (
                  <div className="risk-empty" style={{minHeight: 120}}>
                    <div>
                      <h3>Bölüm yok</h3>
                      <button type="button" className="btn btn-ghost btn-sm" onClick={() => setTab('departments')}>
                        Bölümleri yönet
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </aside>
          </section>
          {err && <div className="error" style={{marginTop: 12}}>{err}</div>}
        </>
      )}

      {tab === 'reports' && !detail && (
        <section>
          <h2 className="risk-section-title">
            Raporlar
            <span>PDF, Excel ve DÖF listesi çıktıları</span>
          </h2>
          <div className="risk-report-grid">
            <article className="risk-report-card">
              <h3>Risk PDF</h3>
              <p>Skorlar ve DÖF özeti ile yazdırılabilir rapor.</p>
              <button type="button" className="btn btn-primary" disabled={!!dlBusy} onClick={() => downloadReport('pdf')}>
                <Download size={14} /> {dlBusy === 'pdf' ? '…' : 'PDF indir'}
              </button>
            </article>
            <article className="risk-report-card">
              <h3>Risk Excel</h3>
              <p>Risk + DÖF + istatistik sayfaları.</p>
              <button type="button" className="btn btn-primary" disabled={!!dlBusy} onClick={() => downloadReport('xlsx')}>
                <FileSpreadsheet size={14} /> {dlBusy === 'xlsx' ? '…' : 'Excel indir'}
              </button>
            </article>
            <article className="risk-report-card">
              <h3>DÖF Excel</h3>
              <p>Yalnız düzeltici / önleyici faaliyet listesi.</p>
              <button type="button" className="btn btn-primary" disabled={!!dlBusy} onClick={() => downloadReport('dof')}>
                <ClipboardList size={14} /> {dlBusy === 'dof' ? '…' : 'DÖF indir'}
              </button>
            </article>
          </div>
        </section>
      )}

      {tab === 'library' && !detail && (
        <section>
          <div className="risk-top" style={{marginBottom: 12, alignItems: 'center'}}>
            <h2 className="risk-section-title" style={{marginBottom: 0}}>
              Tehlike kütüphanesi
              <span>{categories.length} kategori · {hazardCount || '—'} tehlike</span>
            </h2>
            {canEdit && (
              <div className="risk-top-actions">
                <button type="button" className="btn" disabled={busy} onClick={seedLibrary}>
                  Senkronize et
                </button>
              </div>
            )}
          </div>
          {libMsg && <div className="ok" style={{marginBottom: 12}}>{libMsg}</div>}
          <div className="risk-lib-grid">
            <div className="risk-lib-cats">
              {categories.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className={`risk-lib-cat${String(form.category_id) === String(c.id) ? ' active' : ''}`}
                  onClick={() => setForm((f) => ({...f, category_id: String(c.id), hazard_id: '', hazard_q: ''}))}
                >
                  <span>{c.name}</span>
                  <strong>{c.hazard_count ?? 0}</strong>
                </button>
              ))}
              {!categories.length && (
                <div className="risk-empty" style={{minHeight: 100}}>
                  <p>Kategori yok. Senkronize edin.</p>
                </div>
              )}
            </div>
            <div className="risk-panel">
              <div className="risk-panel-head">
                <div>
                  <h2>Tehlikeler</h2>
                  <p>Seçip forma aktarın</p>
                </div>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>Kod</th><th>Ad</th><th></th></tr>
                  </thead>
                  <tbody>
                    {hazards.length ? hazards.map((h) => (
                      <tr key={h.id}>
                        <td>{h.code}</td>
                        <td>{h.name}</td>
                        <td>
                          {canEdit && (
                            <button
                              type="button"
                              className="mini"
                              onClick={() => {
                                setEditId(null);
                                setErr('');
                                setSuggestions(null);
                                setForm({
                                  ...empty,
                                  company_id: reportCompanyId || user.company_id || companies[0]?.id || '',
                                  category_id: String(h.category_id || ''),
                                  hazard_id: String(h.id),
                                  risk_definition: h.description || h.name || '',
                                  probability: h.default_probability || 3,
                                  severity: h.default_severity || 3,
                                });
                                onHazardPick(h.id);
                                setOpen(true);
                                setTab('risks');
                              }}
                            >
                              Forma aktar
                            </button>
                          )}
                        </td>
                      </tr>
                    )) : (
                      <tr><td colSpan={3} className="empty">Kategori seçin</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
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
        <Modal
          title={`Tehlike Kütüphanesi — ${categories.length} kategori / ~${totalHazards} tehlike`}
          close={() => setLibOpen(false)}
          wide
          layer="top"
        >
          <div className="risk-lib-picker">
            <div className="risk-lib-picker-toolbar">
              {canEdit && (
                <button type="button" className="btn" disabled={busy} onClick={seedLibrary}>
                  {busy ? 'Yükleniyor…' : `Kütüphaneyi Yenile / Yükle (${totalHazards || 552} tehlike)`}
                </button>
              )}
              {libMsg && <span className="risk-lib-picker-msg">{libMsg}</span>}
            </div>
            <p className="risk-lib-picker-help">
              Soldan kategori seçin, sağdaki tehlikeye tıklayın veya <strong>Seç</strong> ile forma aktarın.
            </p>
            <div className="risk-lib-picker-grid">
              <div className="risk-lib-picker-cats" role="listbox" aria-label="Tehlike kategorileri">
                {categories.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    role="option"
                    aria-selected={String(form.category_id) === String(c.id)}
                    className={`risk-lib-picker-cat${String(form.category_id) === String(c.id) ? ' active' : ''}`}
                    onClick={() => setForm((f) => ({...f, category_id: String(c.id), hazard_id: '', hazard_q: ''}))}
                  >
                    <strong>{c.name}</strong>
                    <span>{c.hazard_count || 0} tehlike</span>
                  </button>
                ))}
                {!categories.length && <div className="risk-empty" style={{minHeight: 80}}><p>Kategori yok — yükleyin.</p></div>}
              </div>
              <div className="risk-lib-picker-list">
                <div className="search risk-lib-picker-search">
                  <Search size={16} />
                  <input
                    placeholder="Kod veya tehlike adı ara (ör. FZK-001, gürültü)..."
                    value={form.hazard_q}
                    onChange={(e) => setForm({...form, hazard_q: e.target.value})}
                    disabled={!form.category_id}
                  />
                </div>
                <div className="risk-lib-picker-items" role="listbox" aria-label="Tehlikeler">
                  {hazards.length ? hazards.map((h) => (
                    <button
                      key={h.id}
                      type="button"
                      role="option"
                      className="risk-lib-picker-item"
                      onClick={() => applyHazardFromLibrary(h)}
                    >
                      <span className="risk-lib-picker-code">{h.code}</span>
                      <span className="risk-lib-picker-body">
                        <strong>{h.name}</strong>
                        {h.description ? <em>{String(h.description).slice(0, 140)}</em> : null}
                        <small>Varsayılan P/Ş: {h.default_probability || '—'} / {h.default_severity || '—'}</small>
                      </span>
                      <span className="risk-lib-picker-pick">Seç</span>
                    </button>
                  )) : (
                    <div className="risk-empty" style={{minHeight: 120}}>
                      <p>{form.category_id ? 'Tehlike bulunamadı' : 'Soldan kategori seçin'}</p>
                    </div>
                  )}
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
          <form className="risk-form-shell" onSubmit={save}>
            <div className="risk-form-main form-grid">
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
                <small style={{color: '#64748b'}}>Yeni adı yazıp Kaydet veya risk kaydında otomatik oluşturulur.</small>
              </div>

              <div className="field risk-form-span">
                <span>Tehlike kütüphanesi seçimi (zorunlu)</span>
                <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6}}>
                  <button type="button" className="secondary" onClick={() => setLibOpen(true)}>
                    <BookOpen size={16} /> Kütüphaneden Seç
                  </button>
                  {selectedHazard && (
                    <span className="risk-hazard-chip">
                      {selectedHazard.code} — {selectedHazard.name}
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
              <Select
                label="Tehlike"
                required
                value={form.hazard_id}
                onChange={(e) => onHazardPick(e.target.value)}
                style={{gridColumn: '1 / -1'}}
              >
                <option value="">Kütüphaneden seçiniz ({hazards.length})</option>
                {hazards.map((h) => <option key={h.id} value={h.id}>{h.code} — {h.name}</option>)}
              </Select>

              <Field label="Faaliyet" required value={form.activity} onChange={(e) => setForm({...form, activity: e.target.value})} />
              <TextArea label="Risk tanımı" required value={form.risk_definition} onChange={(e) => setForm({...form, risk_definition: e.target.value})} />
              {fieldRole && open && (
                <div className="field risk-hint-card risk-form-span">
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
                      {(hazardHint.suggested_photo_tags || []).length > 0 && (
                        <div style={{marginTop: 4, color: '#0f766e'}}>
                          Foto etiket ipucu: {(hazardHint.suggested_photo_tags || []).join(', ')}
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
              {suggestions && (
                <div className="field risk-form-span">
                  <span>Öneri motoru (kategori)</span>
                  <ul style={{margin: 0, paddingLeft: 18, fontSize: 13}}>
                    {(suggestions.ppe || []).slice(0, 3).map((x) => <li key={x}>KKD: {x}</li>)}
                    {(suggestions.engineering_measures || []).slice(0, 2).map((x) => <li key={x}>Müh.: {x}</li>)}
                  </ul>
                </div>
              )}
            </div>

            <aside className="risk-form-score" aria-live="polite">
              <div className="risk-score-card">
                <div className={`risk-score-hero risk-score-${levelClass(calc?.risk_level)}`}>
                  <span>Canlı skor</span>
                  <strong>{calc?.risk_score ?? '—'}</strong>
                  <em>{calc?.risk_level || 'Olasılık × şiddet'}</em>
                </div>
                <div className="risk-score-matrix">
                  <p>5×5 matris</p>
                  <RiskMatrixGuide probability={form.probability} severity={form.severity} />
                </div>
                <div className="risk-score-meta">
                  <div>
                    <span>Olasılık</span>
                    <strong>{form.probability || '—'}</strong>
                  </div>
                  <div>
                    <span>Şiddet</span>
                    <strong>{form.severity || '—'}</strong>
                  </div>
                  <div>
                    <span>Termin</span>
                    <strong>{calc?.term_label || '—'}</strong>
                  </div>
                </div>
                {calc?.term_date ? (
                  <p className="risk-score-term">{calc.term_date}</p>
                ) : null}
              </div>
            </aside>

            <div className="risk-form-footer">
              {err && <div className="error">{err}</div>}
              <div className="form-actions">
                <button type="button" className="secondary" onClick={() => { setOpen(false); setEditId(null); setErr(''); setHazardHint(null); }}>
                  Vazgeç
                </button>
                <button type="submit">{editId ? 'Güncelle' : 'Kaydet'}</button>
              </div>
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
            {(detail.media || []).map((m) => {
              const isPhoto = !m.file_type || m.file_type === 'photo';
              return (
              <div key={m.id} style={{textAlign: 'center', maxWidth: 140}}>
                {isPhoto ? (
                  <AuthThumb path={`/risks/${detail.id}/media/${m.id}`} alt={m.original_name || ''} />
                ) : (
                  <div style={{
                    width: 120, height: 80, borderRadius: 8, background: '#f1f5f9',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 12, color: '#334155', border: '1px solid #cbd5e1',
                  }}>
                    {(m.file_type || 'dosya').toUpperCase()}
                  </div>
                )}
                <div style={{fontSize: 11, color: '#64748b', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis'}}>
                  {m.original_name || `#${m.id}`}
                </div>
                {m.description && (
                  <div style={{fontSize: 10, color: '#64748b', marginTop: 2}}>{m.description}</div>
                )}
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
              );
            })}
            {!((detail.media || []).length) && (
              <span style={{color: '#64748b', fontSize: 14}}>Henüz medya yok</span>
            )}
          </div>
          {canEdit && (
            <div style={{marginBottom: 10}}>
              <div style={{fontSize: 13, color: '#475569', marginBottom: 6}}>
                Tehlike etiketi (isteğe bağlı — fotoğraf yüklemeden önce)
              </div>
              <div style={{display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8, alignItems: 'center'}}>
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
                <button
                  type="button"
                  className="mini"
                  onClick={async () => {
                    try {
                      const hint = await api('/risks/hazard-hint', {
                        method: 'POST',
                        body: JSON.stringify({
                          activity: detail.activity || '',
                          risk_definition: detail.risk_definition || '',
                        }),
                      });
                      const codes = hint.suggested_photo_tags || [];
                      if (!codes.length) {
                        window.alert('Metinden etiket önerisi çıkmadı.');
                        return;
                      }
                      setSelectedPhotoTags((prev) => [...new Set([...prev, ...codes])]);
                    } catch (ex) {
                      window.alert(ex.message || 'Öneri alınamadı.');
                    }
                  }}
                >
                  Metinden öner
                </button>
              </div>
              <label className="field" style={{display: 'inline-flex', alignItems: 'center', gap: 8, cursor: 'pointer'}}>
                <span className="mini" style={{pointerEvents: 'none'}}>Dosya ekle</span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif,application/pdf,video/mp4,.doc,.docx,.xls,.xlsx"
                  onChange={uploadMedia}
                  style={{display: 'none'}}
                />
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

          <h4 style={{marginTop: 20}}>Revizyon geçmişi</h4>
          {(detail.revisions || []).length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Rev</th>
                    <th>Alan</th>
                    <th>Eski</th>
                    <th>Yeni</th>
                    <th>Neden</th>
                    <th>Tarih</th>
                  </tr>
                </thead>
                <tbody>
                  {(detail.revisions || []).slice(0, 20).map((r) => (
                    <tr key={r.id}>
                      <td>v{r.revision_no}</td>
                      <td>{r.field_name || '—'}</td>
                      <td style={{maxWidth: 160, fontSize: 12}}>{(r.old_value || '—').slice(0, 80)}</td>
                      <td style={{maxWidth: 160, fontSize: 12}}>{(r.new_value || '—').slice(0, 80)}</td>
                      <td style={{fontSize: 12}}>{r.change_reason || '—'}</td>
                      <td style={{fontSize: 12}}>{r.changed_at ? String(r.changed_at).slice(0, 19).replace('T', ' ') : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p style={{color: '#64748b', fontSize: 14}}>Henüz alan değişikliği kaydı yok.</p>
          )}
        </section>
      )}
    </div>
  );
}
