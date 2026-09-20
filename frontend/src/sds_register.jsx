import React, {useEffect, useMemo, useState} from 'react';
import {
  AlertTriangle,
  Beaker,
  Building2,
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  Download,
  FileCheck2,
  FileText,
  Flame,
  Hash,
  Layers3,
  MapPin,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Tag,
  Upload,
} from 'lucide-react';
import {api, downloadFile, uploadFile} from './api';
import {AppModal} from './ui_modal';
import {isWorkplaceAccountUser} from './workplace_user_policy';
import './sds_register.css';

function Modal({title, close, children, className = ''}) {
  return (
    <AppModal title={title} close={close} className={className}>
      {children}
    </AppModal>
  );
}

function Field({label, children, className = '', hint = '', icon: Icon, requiredLabel = false, ...rest}) {
  const required = requiredLabel || !!rest.required;
  if (children) {
    return (
      <label className={`field sds-modern-field${className ? ` ${className}` : ''}`}>
        <span className="sds-modern-field-label">
          {Icon ? <Icon size={15} aria-hidden="true" /> : null}
          <span>{label}{required ? <b aria-hidden="true">*</b> : null}</span>
        </span>
        {children}
        {hint ? <small className="sds-field-hint">{hint}</small> : null}
      </label>
    );
  }
  return (
    <label className={`field sds-modern-field${className ? ` ${className}` : ''}`}>
      <span className="sds-modern-field-label">
        {Icon ? <Icon size={15} aria-hidden="true" /> : null}
        <span>{label}{required ? <b aria-hidden="true">*</b> : null}</span>
      </span>
      <input {...rest} />
      {hint ? <small className="sds-field-hint">{hint}</small> : null}
    </label>
  );
}

function reviewBadge(status) {
  if (status === 'overdue') return <span className="status-badge badge-danger">Gecikmiş</span>;
  if (status === 'due_soon') return <span className="status-badge badge-warn">Yaklaşıyor</span>;
  if (status === 'ok') return <span className="status-badge badge-ok">Güncel</span>;
  return <span className="status-badge badge-muted">Tarih yok</span>;
}

const empty = {
  company_id: '',
  branch_id: '',
  product_name: '',
  cas_number: '',
  has_sds_file: false,
  next_review_date: '',
  notes: '',
};

const PKD_EMPTY = {
  id: null,
  company_id: '',
  branch_id: '',
  document_no: '',
  area_name: '',
  process_name: '',
  atmosphere_type: 'gas_vapour_mist',
  hazardous_materials: '',
  zone_classifications: [],
  ignition_sources: [],
  control_measures: [],
  responsible_person: '',
  prepared_by: '',
  approved_by: '',
  document_date: '',
  revision_no: '1.0',
  next_review_date: '',
  status: 'draft',
  notes: '',
};

const PKD_FALLBACK_ZONES = [
  {code: 'zone_0', label: 'Zone 0'},
  {code: 'zone_1', label: 'Zone 1'},
  {code: 'zone_2', label: 'Zone 2'},
  {code: 'zone_20', label: 'Zone 20'},
  {code: 'zone_21', label: 'Zone 21'},
  {code: 'zone_22', label: 'Zone 22'},
];

const PKD_FALLBACK_IGNITION = [
  {code: 'hot_work', label: 'Sıcak çalışma / açık alev'},
  {code: 'electrical', label: 'Elektriksel ekipman'},
  {code: 'static', label: 'Statik elektrik'},
  {code: 'mechanical', label: 'Mekanik kıvılcım / sıcak yüzey'},
  {code: 'vehicles', label: 'Araç ve hareketli ekipman'},
  {code: 'lightning', label: 'Yıldırım / atmosferik etki'},
];

const PKD_FALLBACK_CONTROLS = [
  {code: 'ventilation', label: 'Yeterli havalandırma'},
  {code: 'ex_equipment', label: 'Uygun Ex ekipman seçimi'},
  {code: 'grounding', label: 'Topraklama ve eşpotansiyel bağlantı'},
  {code: 'hot_work_permit', label: 'Sıcak çalışma izin sistemi'},
  {code: 'gas_detection', label: 'Gaz / toz algılama ve alarm'},
  {code: 'housekeeping', label: 'Toz birikimi ve temizlik kontrolü'},
  {code: 'maintenance', label: 'Periyodik bakım ve muayene'},
  {code: 'training', label: 'Çalışan eğitimi ve bilgilendirme'},
];

function pkdDateStatus(row) {
  if (row.review_status === 'overdue') return <span className="status-badge badge-danger">Gecikmiş</span>;
  if (row.review_status === 'due_soon') return <span className="status-badge badge-warn">Yaklaşıyor</span>;
  if (row.review_status === 'revision_pending') return <span className="status-badge badge-warn">Revizyon bekliyor</span>;
  if (row.review_status === 'draft') return <span className="status-badge badge-muted">Taslak</span>;
  if (row.review_status === 'archived') return <span className="status-badge badge-muted">Arşiv</span>;
  if (row.review_status === 'ok') return <span className="status-badge badge-ok">Güncel</span>;
  return <span className="status-badge badge-muted">Tarih yok</span>;
}

function pkdStatusLabel(status) {
  return {
    draft: 'Taslak',
    active: 'Aktif',
    revision_pending: 'Revizyon Bekliyor',
    archived: 'Arşiv',
  }[status] || status;
}

function displayPkdAtmosphere(value) {
  return {
    gas_vapour_mist: 'Gaz / buhar / sis',
    dust: 'Yanıcı toz',
    mixed: 'Gaz ve toz',
  }[value] || value || '—';
}

function PkdChoiceGrid({label, hint, options, selected, onToggle}) {
  return (
    <div className="pkd-choice-field">
      <div className="pkd-field-heading">
        <strong>{label}</strong>
        <small>{hint}</small>
      </div>
      <div className="pkd-choice-grid">
        {options.map((option) => {
          const active = selected.includes(option.code);
          return (
            <button
              key={option.code}
              type="button"
              className={`pkd-choice${active ? ' is-selected' : ''}`}
              aria-pressed={active}
              onClick={() => onToggle(option.code)}
            >
              <span className="pkd-choice-check" aria-hidden="true">
                {active ? <CheckCircle2 size={15} /> : <span />}
              </span>
              <span>{option.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function PkdModal({
  form,
  setForm,
  onSubmit,
  onClose,
  busy,
  workplaceAccount,
  workplaceBranches,
  companies,
  meta,
}) {
  const zones = (meta?.zones && !Array.isArray(meta.zones))
    ? Object.entries(meta.zones).map(([code, label]) => ({code, label}))
    : PKD_FALLBACK_ZONES;
  const ignitionSources = meta?.ignition_sources?.length ? meta.ignition_sources : PKD_FALLBACK_IGNITION;
  const controlMeasures = meta?.control_measures?.length ? meta.control_measures : PKD_FALLBACK_CONTROLS;
  const update = (key, value) => setForm((current) => ({...current, [key]: value}));
  const toggle = (key, code) => setForm((current) => ({
    ...current,
    [key]: current[key].includes(code)
      ? current[key].filter((item) => item !== code)
      : [...current[key], code],
  }));
  const isEditing = Boolean(form.id);

  return (
    <Modal
      className="sds-product-modal pkd-document-modal"
      title={(
        <span className="sds-modal-heading">
          <span className="sds-modal-heading-icon pkd-modal-icon" aria-hidden="true"><Flame size={22} /></span>
          <span>
            <strong>{isEditing ? 'PKD Kaydını Düzenle' : 'Yeni PKD Kaydı'}</strong>
            <small>Patlamadan korunma dokümanını kontrollü ve izlenebilir yönetin</small>
          </span>
        </span>
      )}
      close={onClose}
    >
      <form className="sds-product-form pkd-form" onSubmit={onSubmit}>
        <div className="sds-modal-intro pkd-modal-intro">
          <span className="sds-modal-intro-icon" aria-hidden="true"><ShieldAlert size={21} /></span>
          <span className="sds-modal-intro-copy">
            <strong>PKD künyesi ve risk profili</strong>
            <small>Bu kayıt, teknik PKD dosyasının işyeri ve proses bazında yönetim kaydını oluşturur.</small>
          </span>
          <span className="sds-required-note"><b>*</b> Zorunlu alan</span>
        </div>

        <div className="pkd-form-section">
          <div className="pkd-section-title"><span><FileText size={16} /></span><div><strong>Doküman künyesi</strong><small>PKD’nin hangi işyeri, alan ve revizyona ait olduğunu tanımlayın.</small></div></div>
          <div className="sds-product-grid pkd-grid">
            {workplaceAccount ? (
              <Field
                label="Şube"
                icon={MapPin}
                requiredLabel
                hint={workplaceBranches.length ? 'Kayıt seçtiğiniz şubeye bağlanacaktır.' : 'Bu işyerine tanımlanmış aktif şube bulunamadı.'}
              >
                <select required disabled={workplaceBranches.length === 0} value={form.branch_id} onChange={(e) => update('branch_id', e.target.value)}>
                  <option value="">{workplaceBranches.length ? 'Şube seçiniz' : 'Tanımlı şube bulunamadı'}</option>
                  {workplaceBranches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
                </select>
              </Field>
            ) : (
              <Field label="Firma" icon={Building2} requiredLabel>
                <select required value={form.company_id} onChange={(e) => update('company_id', e.target.value)}>
                  <option value="">Seçiniz</option>
                  {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
                </select>
              </Field>
            )}
            <Field label="PKD doküman no" icon={Hash} required value={form.document_no} placeholder="Örn. PKD-2026-001" onChange={(e) => update('document_no', e.target.value)} />
            <Field label="Bölüm / tehlikeli alan" icon={MapPin} required value={form.area_name} placeholder="Örn. Solvent Deposu" onChange={(e) => update('area_name', e.target.value)} />
            <Field label="Proses / faaliyet" icon={Layers3} value={form.process_name} placeholder="Örn. Dolum ve transfer hattı" onChange={(e) => update('process_name', e.target.value)} />
            <Field label="Ortam türü" icon={Flame} required>
              <select required value={form.atmosphere_type} onChange={(e) => update('atmosphere_type', e.target.value)}>
                <option value="gas_vapour_mist">Gaz / buhar / sis</option>
                <option value="dust">Yanıcı toz</option>
                <option value="mixed">Gaz ve toz birlikte</option>
              </select>
            </Field>
            <Field label="Revizyon no" icon={RotateCcw} value={form.revision_no} placeholder="Örn. 1.0" onChange={(e) => update('revision_no', e.target.value)} />
            <Field label="Doküman tarihi" icon={CalendarClock} type="date" value={form.document_date} onChange={(e) => update('document_date', e.target.value)} />
            <Field label="Sonraki gözden geçirme" icon={CalendarClock} type="date" value={form.next_review_date} onChange={(e) => update('next_review_date', e.target.value)} />
            <Field label="İş akışı durumu" icon={ClipboardCheck} required>
              <select required value={form.status} onChange={(e) => update('status', e.target.value)}>
                <option value="draft">Taslak</option>
                <option value="active">Aktif</option>
                <option value="revision_pending">Revizyon Bekliyor</option>
                <option value="archived">Arşiv</option>
              </select>
            </Field>
          </div>
        </div>

        <div className="pkd-form-section">
          <div className="pkd-section-title"><span><ShieldAlert size={16} /></span><div><strong>Patlayıcı ortam değerlendirmesi</strong><small>Dokümanda yer alan temel teknik risk başlıklarını işaretleyin.</small></div></div>
          <div className="pkd-form-stack">
            <Field label="Tehlikeli maddeler / karışımlar" icon={Beaker} hint="Yanıcı sıvı, gaz, buhar veya tozları belirtin.">
              <textarea rows={3} value={form.hazardous_materials} placeholder="Örn. Tiner, solvent buharı, elektrostatik toz boya…" onChange={(e) => update('hazardous_materials', e.target.value)} />
            </Field>
            <PkdChoiceGrid label="Tehlikeli bölge sınıfları" hint="PKD ve zone sınıflandırmanızda yer alan bölgeleri seçin." options={zones} selected={form.zone_classifications} onToggle={(code) => toggle('zone_classifications', code)} />
            <PkdChoiceGrid label="Muhtemel tutuşturucu kaynaklar" hint="Sahada kontrol edilmesi gereken kaynakları işaretleyin." options={ignitionSources} selected={form.ignition_sources} onToggle={(code) => toggle('ignition_sources', code)} />
            <PkdChoiceGrid label="Kontrol ve korunma önlemleri" hint="Teknik ve organizasyonel önlemleri kayıt altına alın." options={controlMeasures} selected={form.control_measures} onToggle={(code) => toggle('control_measures', code)} />
          </div>
        </div>

        <div className="pkd-form-section">
          <div className="pkd-section-title"><span><CheckCircle2 size={16} /></span><div><strong>Sorumluluk ve onay</strong><small>Dokümanın hazırlanması ve işletme içindeki sorumluluğu izlenebilir olsun.</small></div></div>
          <div className="sds-product-grid pkd-grid">
            <Field label="Sorumlu kişi" icon={ShieldCheck} value={form.responsible_person} placeholder="Ad soyad / görev" onChange={(e) => update('responsible_person', e.target.value)} />
            <Field label="Hazırlayan" icon={FileText} value={form.prepared_by} placeholder="Ad soyad / unvan" onChange={(e) => update('prepared_by', e.target.value)} />
            <Field label="Onaylayan" icon={CheckCircle2} value={form.approved_by} placeholder="Ad soyad / unvan" onChange={(e) => update('approved_by', e.target.value)} />
            <Field label="Notlar ve aksiyonlar" icon={AlertTriangle} className="sds-notes-field">
              <textarea rows={4} value={form.notes} placeholder="Eksikler, aksiyonlar, ekler veya saha notları…" onChange={(e) => update('notes', e.target.value)} />
            </Field>
          </div>
        </div>

        <div className="sds-product-actions">
          <button type="button" className="sds-cancel-button" disabled={busy} onClick={onClose}>Vazgeç</button>
          <button type="submit" className="sds-save-button pkd-save-button" disabled={busy || (workplaceAccount && !form.branch_id)}>
            <Save size={17} aria-hidden="true" />
            {busy ? 'Kaydediliyor…' : isEditing ? 'PKD Kaydını Güncelle' : 'PKD Kaydını Oluştur'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function PkdRegisterPanel({user, workplaceAccount, workplaceBranches, companies, canEdit}) {
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);
  const [meta, setMeta] = useState(null);
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({...PKD_EMPTY, company_id: user.company_id || ''});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');

  async function load(nextQ = q) {
    setBusy(true);
    setErr('');
    try {
      const qs = nextQ.trim() ? `?q=${encodeURIComponent(nextQ.trim())}` : '';
      const [list, totals, options] = await Promise.all([
        api(`/sds/pkd${qs}`),
        api('/sds/pkd/summary'),
        api('/sds/pkd/meta'),
      ]);
      setRows(Array.isArray(list) ? list : []);
      setSummary(totals);
      setMeta(options);
    } catch (e) {
      setErr(e.message || 'PKD sicili yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!workplaceAccount) return;
    setForm((current) => {
      const companyId = String(user.company_id || '');
      const validBranch = workplaceBranches.some((branch) => String(branch.id) === String(current.branch_id));
      const branchId = validBranch ? String(current.branch_id) : workplaceBranches.length === 1 ? String(workplaceBranches[0].id) : '';
      if (String(current.company_id) === companyId && String(current.branch_id) === branchId) return current;
      return {...current, company_id: companyId, branch_id: branchId};
    });
  }, [user.company_id, workplaceAccount, workplaceBranches]);

  function openNew() {
    setForm({...PKD_EMPTY, company_id: workplaceAccount ? String(user.company_id || '') : '', branch_id: workplaceAccount && workplaceBranches.length === 1 ? String(workplaceBranches[0].id) : ''});
    setErr('');
    setOpen(true);
  }

  function openEdit(row) {
    setForm({
      ...PKD_EMPTY,
      ...row,
      document_date: row.document_date || '',
      next_review_date: row.next_review_date || '',
      company_id: String(row.company_id || ''),
      branch_id: row.branch_id ? String(row.branch_id) : '',
      zone_classifications: [...(row.zone_classifications || [])],
      ignition_sources: [...(row.ignition_sources || [])],
      control_measures: [...(row.control_measures || [])],
    });
    setErr('');
    setOpen(true);
  }

  async function save(e) {
    e.preventDefault();
    setErr('');
    setBusy(true);
    try {
      const payload = {
        company_id: Number(workplaceAccount ? user.company_id : form.company_id),
        branch_id: form.branch_id ? Number(form.branch_id) : null,
        document_no: form.document_no,
        area_name: form.area_name,
        process_name: form.process_name || null,
        atmosphere_type: form.atmosphere_type,
        hazardous_materials: form.hazardous_materials || null,
        zone_classifications: form.zone_classifications,
        ignition_sources: form.ignition_sources,
        control_measures: form.control_measures,
        responsible_person: form.responsible_person || null,
        prepared_by: form.prepared_by || null,
        approved_by: form.approved_by || null,
        document_date: form.document_date || null,
        revision_no: form.revision_no || null,
        next_review_date: form.next_review_date || null,
        status: form.status,
        notes: form.notes || null,
      };
      const saved = await api(form.id ? `/sds/pkd/${form.id}` : '/sds/pkd', {
        method: form.id ? 'PATCH' : 'POST',
        body: JSON.stringify(form.id ? {...payload, company_id: undefined} : payload),
      });
      setOpen(false);
      setMsg(form.id ? `PKD güncellendi: ${saved.document_no}` : `PKD kaydı oluşturuldu: ${saved.document_no}`);
      await load();
    } catch (ex) {
      setErr(ex.message || 'PKD kaydı başarısız.');
    } finally {
      setBusy(false);
    }
  }

  async function ensureDocOnly(row) {
    setBusy(true);
    setErr('');
    try {
      await api(`/sds/pkd/${row.id}/ensure-document`, {method: 'POST'});
      setMsg('PKD doküman kaydı hazır — teknik dosyayı yükleyebilirsiniz.');
      await load();
    } catch (ex) {
      setErr(ex.message || 'PKD doküman kaydı oluşturulamadı.');
    } finally {
      setBusy(false);
    }
  }

  async function uploadPkd(row, file) {
    if (!file) return;
    setBusy(true);
    setErr('');
    setMsg('');
    try {
      let linked = row;
      if (!row.document_id) linked = await api(`/sds/pkd/${row.id}/ensure-document`, {method: 'POST'});
      await uploadFile(`/files/documents/${linked.document_id}`, file);
      const marked = await api(`/sds/pkd/${row.id}/mark-file-uploaded`, {method: 'POST'});
      setMsg(`PKD dosyası yüklendi: ${marked.document_no}`);
      await load();
    } catch (ex) {
      setErr(ex.message || 'PKD dosyası yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  async function downloadPkd(row) {
    if (!row.document_id) return;
    setBusy(true);
    setErr('');
    try {
      const safe = String(row.document_no || 'pkd').replace(/[^a-z0-9-_]+/gi, '-').replace(/^-+|-+$/g, '') || 'pkd';
      await downloadFile(`/files/documents/${row.document_id}/download`, `${safe}.pdf`);
    } catch (ex) {
      setErr(ex.message || 'PKD dosyası indirilemedi.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="pkd-register-shell">
      <div className="pkd-toolbar">
        <div>
          <p className="pkd-eyebrow"><Sparkles size={13} /> PREMIUM PKD YÖNETİMİ</p>
          <h4>Patlamadan Korunma Dokümanı Sicili</h4>
          <p>İşyeri, bölüm ve proses bazında PKD künyelerini; zone sınıflarını, tutuşturucu kaynakları ve korunma önlemlerini tek merkezden izleyin.</p>
        </div>
        <div className="pkd-toolbar-actions">
          <button type="button" className="secondary" disabled={busy} onClick={() => downloadFile(`/sds/pkd/export.xlsx${q.trim() ? `?q=${encodeURIComponent(q.trim())}` : ''}`, `pkd-sicili-${new Date().toISOString().slice(0, 10)}.xlsx`).catch((e) => setErr(e.message || 'Excel indirilemedi.'))}>
            <Download size={16} /> Excel Rapor
          </button>
          <button type="button" className="secondary" disabled={busy} onClick={() => void load()}><RefreshCw size={16} /> Yenile</button>
          {canEdit && <button type="button" disabled={busy} onClick={openNew}><Plus size={16} /> Yeni PKD Kaydı</button>}
        </div>
      </div>

      {summary && (
        <div className="pkd-summary-grid">
          <div className="pkd-summary-card pkd-summary-primary"><span className="pkd-summary-icon"><Flame size={18} /></span><div><strong>{summary.total}</strong><small>Toplam PKD</small></div><span className="pkd-summary-accent">sicil</span></div>
          <div className="pkd-summary-card"><span className="pkd-summary-icon is-green"><CheckCircle2 size={18} /></span><div><strong>{summary.active}</strong><small>Aktif doküman</small></div></div>
          <div className="pkd-summary-card"><span className="pkd-summary-icon is-blue"><FileCheck2 size={18} /></span><div><strong>{summary.with_file}</strong><small>Dosyası mevcut</small></div><span className="pkd-summary-foot">{summary.missing_file} eksik</span></div>
          <div className="pkd-summary-card"><span className="pkd-summary-icon is-amber"><RotateCcw size={18} /></span><div><strong>{summary.revision_pending + summary.due_soon}</strong><small>Takip gerekiyor</small></div><span className="pkd-summary-foot">{summary.revision_pending} revizyon</span></div>
          <div className="pkd-summary-card pkd-summary-danger"><span className="pkd-summary-icon is-red"><AlertTriangle size={18} /></span><div><strong>{summary.overdue}</strong><small>Gecikmiş inceleme</small></div></div>
        </div>
      )}

      <div className="pkd-register-note"><ShieldCheck size={17} /><span><strong>Denetim hazırlığı:</strong> PKD teknik dosyasını, revizyonunu ve saha önlemlerini aynı kayıt üzerinden izleyin. Yüklenen dosya, mevcut Dokümanlar güvenlik ve yetki altyapısıyla korunur.</span></div>

      <div className="search pkd-search">
        <FileText size={16} />
        <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && void load()} placeholder="Doküman no, bölüm, proses veya madde ara…" />
        <button type="button" className="secondary mini" onClick={() => void load()}>Ara</button>
      </div>

      {err && <p style={{color: '#b91c1c'}}>{err}</p>}
      {msg && <p style={{color: '#08744f'}}>{msg}</p>}

      <div className="table-wrap pkd-table-wrap">
        <table>
          <thead><tr><th>Doküman</th><th>Bölüm / Proses</th><th>Ortam</th><th>Zone</th><th>Revizyon / İnceleme</th><th>Dosya</th><th>Durum</th>{canEdit && <th>İşlem</th>}</tr></thead>
          <tbody>
            {rows.length === 0 ? <tr><td colSpan={canEdit ? 8 : 7}><div className="pkd-empty-state"><span><Flame size={24} /></span><strong>Henüz PKD kaydı bulunmuyor</strong><small>İlk dokümanınızı oluşturarak patlamadan korunma kayıtlarını merkezi olarak yönetmeye başlayın.</small>{canEdit && <button type="button" onClick={openNew}><Plus size={15} /> Yeni PKD Kaydı</button>}</div></td></tr> : rows.map((row) => (
              <tr key={row.id}>
                <td><div className="pkd-document-cell"><span className="pkd-row-icon"><Flame size={15} /></span><div><strong>{row.document_no}</strong><small>Rev. {row.revision_no || '—'}</small></div></div></td>
                <td><div className="pkd-area-cell"><strong>{row.area_name}</strong><small>{row.process_name || 'Proses belirtilmedi'}</small></div></td>
                <td><span className="pkd-atmosphere">{displayPkdAtmosphere(row.atmosphere_type)}</span></td>
                <td><div className="pkd-zone-list">{(row.zone_classifications || []).length ? row.zone_classifications.map((zone) => <span key={zone}>{zone.replace('zone_', 'Zone ')}</span>) : <em>Belirtilmedi</em>}</div></td>
                <td><div className="pkd-review-cell"><strong>{row.next_review_date || 'Tarih yok'}</strong>{pkdDateStatus(row)}</div></td>
                <td>{row.has_pkd_file ? <span className="pkd-file-state is-ready"><FileCheck2 size={14} /> Hazır</span> : <span className="pkd-file-state"><FileText size={14} /> Eksik</span>}</td>
                <td><span className={`pkd-status-pill status-${row.status}`}><span />{pkdStatusLabel(row.status)}</span></td>
                {canEdit && <td><div className="pkd-row-actions"><button type="button" className="mini secondary" disabled={busy} onClick={() => openEdit(row)}><RotateCcw size={13} /> Düzenle</button>{row.has_pkd_file && row.document_id && <button type="button" className="mini secondary" disabled={busy} onClick={() => void downloadPkd(row)}><Download size={13} /> İndir</button>}{!row.document_id && <button type="button" className="mini secondary" disabled={busy} onClick={() => void ensureDocOnly(row)}>Doküman oluştur</button>}<label className="mini secondary pkd-upload-button"><Upload size={13} /> Dosya yükle<input type="file" accept=".pdf,.doc,.docx,.png,.jpg,.jpeg" style={{display: 'none'}} disabled={busy} onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ''; if (file) void uploadPkd(row, file); }} /></label></div></td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {open && <PkdModal form={form} setForm={setForm} onSubmit={save} onClose={() => setOpen(false)} busy={busy} workplaceAccount={workplaceAccount} workplaceBranches={workplaceBranches} companies={companies} meta={meta} />}
    </section>
  );
}

export function SdsRegisterPage({user}) {
  const workplaceAccount = isWorkplaceAccountUser(user);
  const canEdit = user.role === 'safety_specialist'
    || user.role === 'global_admin'
    || workplaceAccount;
  const [companies, setCompanies] = useState([]);
  const [branches, setBranches] = useState([]);
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);
  const [catalog, setCatalog] = useState([]);
  const [q, setQ] = useState('');
  const [activeTab, setActiveTab] = useState('sds');
  const [open, setOpen] = useState(false);
  const [ghsRow, setGhsRow] = useState(null);
  const [ghsSelected, setGhsSelected] = useState([]);
  const [form, setForm] = useState({...empty, company_id: user.company_id || ''});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const workplaceBranches = useMemo(() => (
    workplaceAccount ? branches.filter((branch) => (
      branch.is_active !== false
      && String(branch.company_id) === String(user.company_id)
    )) : []
  ), [branches, user.company_id, workplaceAccount]);

  async function load(nextQ = q) {
    setBusy(true);
    setErr('');
    try {
      const qs = nextQ.trim() ? `?q=${encodeURIComponent(nextQ.trim())}` : '';
      const [c, b, r, s, meta] = await Promise.all([
        workplaceAccount ? Promise.resolve([]) : api('/companies'),
        workplaceAccount
          ? api(`/branches?company_id=${Number(user.company_id)}`)
          : Promise.resolve([]),
        api(`/sds${qs}`),
        api('/sds/due-summary'),
        api('/sds/meta'),
      ]);
      setCompanies(Array.isArray(c) ? c : []);
      setBranches(Array.isArray(b) ? b : []);
      setRows(r);
      setSummary(s);
      setCatalog(meta?.ghs_pictograms || []);
    } catch (e) {
      setErr(e.message || 'SDS sicili yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!workplaceAccount) return;
    setForm((current) => {
      const companyId = String(user.company_id || '');
      const currentBranchIsValid = workplaceBranches.some(
        (branch) => String(branch.id) === String(current.branch_id),
      );
      const branchId = currentBranchIsValid
        ? String(current.branch_id)
        : workplaceBranches.length === 1
          ? String(workplaceBranches[0].id)
          : '';
      if (String(current.company_id) === companyId && String(current.branch_id) === branchId) {
        return current;
      }
      return {...current, company_id: companyId, branch_id: branchId};
    });
  }, [user.company_id, workplaceAccount, workplaceBranches]);

  async function save(e) {
    e.preventDefault();
    setErr('');
    setBusy(true);
    try {
      await api('/sds', {
        method: 'POST',
        body: JSON.stringify({
          company_id: Number(workplaceAccount ? user.company_id : form.company_id),
          branch_id: form.branch_id ? Number(form.branch_id) : null,
          product_name: form.product_name,
          cas_number: form.cas_number || null,
          has_sds_file: !!form.has_sds_file,
          next_review_date: form.next_review_date || null,
          notes: form.notes || null,
        }),
      });
      setOpen(false);
      setForm({
        ...empty,
        company_id: workplaceAccount ? String(user.company_id) : form.company_id || '',
        branch_id: workplaceAccount ? form.branch_id : '',
      });
      setMsg('Kimyasal ürün eklendi.');
      await load();
    } catch (ex) {
      setErr(ex.message || 'Kayıt başarısız.');
    } finally {
      setBusy(false);
    }
  }

  async function ensureDocAndUpload(row, file) {
    if (!file) return;
    setBusy(true);
    setErr('');
    setMsg('');
    try {
      let linked = row;
      if (!row.document_id) {
        linked = await api(`/sds/${row.id}/ensure-document`, {method: 'POST'});
      }
      await uploadFile(`/files/documents/${linked.document_id}`, file);
      const marked = await api(`/sds/${row.id}/mark-sds-uploaded`, {method: 'POST'});
      setMsg(`SDS yüklendi: ${marked.product_name}`);
      await load();
    } catch (ex) {
      setErr(ex.message || 'SDS yükleme başarısız.');
    } finally {
      setBusy(false);
    }
  }

  async function ensureDocOnly(row) {
    setBusy(true);
    setErr('');
    try {
      await api(`/sds/${row.id}/ensure-document`, {method: 'POST'});
      setMsg('Doküman kaydı hazır — SDS dosyasını yükleyebilirsiniz.');
      await load();
    } catch (ex) {
      setErr(ex.message || 'Doküman oluşturulamadı.');
    } finally {
      setBusy(false);
    }
  }

  function openGhs(row) {
    setGhsRow(row);
    setGhsSelected([...(row.ghs_selected || [])]);
  }

  function toggleGhs(code) {
    setGhsSelected((prev) => (
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    ));
  }

  async function saveGhs(e) {
    e.preventDefault();
    if (!ghsRow) return;
    setBusy(true);
    setErr('');
    try {
      await api(`/sds/${ghsRow.id}/ghs-checklist`, {
        method: 'PUT',
        body: JSON.stringify({selected: ghsSelected}),
      });
      setMsg(`Tehlike etiketi güncellendi: ${ghsRow.product_name}`);
      setGhsRow(null);
      await load();
    } catch (ex) {
      setErr(ex.message || 'Etiket kaydı başarısız.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-title">
        <div>
          <h3>SDS / PKD Sicili</h3>
          <small className="sds-page-subtitle">Kimyasal güvenlik ve patlamadan korunma dokümanları için merkezi kayıt yönetimi</small>
        </div>
        {activeTab === 'sds' && <div className="actions">
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => {
              const stamp = new Date().toISOString().slice(0, 10);
              downloadFile(
                `/sds/export.xlsx${q.trim() ? `?q=${encodeURIComponent(q.trim())}` : ''}`,
                `sds-sicili-${stamp}.xlsx`,
              ).catch((e) => setErr(e.message || 'Excel indirilemedi.'));
            }}
          >
            <Download size={16} /> Excel Rapor
          </button>
          <button type="button" className="secondary" disabled={busy} onClick={() => void load()}>
            <RefreshCw size={16} /> Yenile
          </button>
          {canEdit && (
            <button type="button" disabled={busy} onClick={() => setOpen(true)}>
              <Plus size={16} /> Yeni Ürün
            </button>
          )}
        </div>}
      </div>

      <section className="sds-premium-hero">
        <div className="sds-premium-hero-mark"><ShieldCheck size={25} /></div>
        <div className="sds-premium-hero-copy">
          <span className="sds-premium-eyebrow"><Sparkles size={13} /> PREMIUM İSG KAYIT MERKEZİ</span>
          <h4>Kimyasal güvenliği ve patlamadan korunma tek merkezde</h4>
          <p>Güvenlik Bilgi Formlarını ve Patlamadan Korunma Dokümanlarını; belge, revizyon, saha riski ve gözden geçirme takibiyle birlikte yönetin.</p>
        </div>
        <div className="sds-premium-hero-points"><span><CheckCircle2 size={14} /> Denetlenebilir</span><span><ShieldCheck size={14} /> Yetki kontrollü</span></div>
      </section>

      <nav className="sds-register-tabs" aria-label="Kimyasal ve PKD kayıt türleri">
        <button type="button" className={activeTab === 'sds' ? 'is-active' : ''} aria-selected={activeTab === 'sds'} onClick={() => setActiveTab('sds')}>
          <span className="sds-tab-icon"><Beaker size={17} /></span><span><strong>SDS / GBF Sicili</strong><small>Kimyasal ürün ve güvenlik bilgi formları</small></span>
        </button>
        <button type="button" className={activeTab === 'pkd' ? 'is-active' : ''} aria-selected={activeTab === 'pkd'} onClick={() => setActiveTab('pkd')}>
          <span className="sds-tab-icon pkd-tab-icon"><Flame size={17} /></span><span><strong>PKD Sicili</strong><small>Patlamadan korunma dokümanları ve zone takibi</small></span>
        </button>
      </nav>

      {activeTab === 'sds' && <div className="sds-tab-content">
      <section className="panel sds-overview-panel" style={{marginBottom: 16}}>
        <p style={{margin: '0 0 12px', color: '#475569', fontSize: 14, lineHeight: 1.5}}>
          <strong>Güvenlik Bilgi Formu (GBF / SDS) yönetimi:</strong> ürün adı, CAS numarası, SDS dosya durumu, gözden geçirme tarihi
          ve GHS/CLP tehlike etiketi kontrolü. Dosya yükleme mevcut Dokümanlar altyapısıyla güvenli şekilde çalışır.
        </p>
        {summary && (
          <div className="report-grid" style={{marginBottom: 0}}>
            <div className="metric"><strong>{summary.total}</strong><span>Toplam ürün</span></div>
            <div className="metric"><strong>{summary.with_sds}</strong><span>SDS var</span></div>
            <div className="metric"><strong>{summary.missing_sds}</strong><span>SDS eksik</span></div>
            <div className="metric"><strong>{summary.with_ghs_label ?? 0}</strong><span>Etiket işaretli</span></div>
            <div className="metric"><strong>{summary.due_soon}</strong><span>Yaklaşan</span></div>
            <div className="metric"><strong>{summary.overdue}</strong><span>Gecikmiş</span></div>
          </div>
        )}
      </section>

      <div className="search">
        <Beaker size={16} />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void load()}
          placeholder="Ürün veya CAS ara…"
        />
        <button type="button" className="secondary mini" onClick={() => void load()}>Ara</button>
      </div>

      {err && <p style={{color: '#b91c1c'}}>{err}</p>}
      {msg && <p style={{color: '#08744f'}}>{msg}</p>}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Ürün</th>
              <th>CAS</th>
              <th>SDS</th>
              <th>GHS</th>
              <th>Gözden geçirme</th>
              <th>Durum</th>
              {canEdit && <th>İşlem</th>}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={canEdit ? 7 : 6}>Kayıt yok.</td></tr>
            ) : rows.map((r) => (
              <tr key={r.id}>
                <td>{r.product_name}</td>
                <td>{r.cas_number || '—'}</td>
                <td>{r.has_sds_file ? 'Var' : 'Yok'}</td>
                <td>{r.ghs_count ? `${r.ghs_count} piktogram` : '—'}</td>
                <td>{r.next_review_date || '—'}</td>
                <td>{reviewBadge(r.review_status)}</td>
                {canEdit && (
                  <td>
                    <div style={{display: 'flex', gap: 6, flexWrap: 'wrap'}}>
                      <button type="button" className="mini secondary" disabled={busy} onClick={() => openGhs(r)}>
                        <Tag size={14} /> Etiket
                      </button>
                      {!r.document_id && (
                        <button type="button" className="mini secondary" disabled={busy} onClick={() => void ensureDocOnly(r)}>
                          Doküman oluştur
                        </button>
                      )}
                      <label className="mini secondary" style={{cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4}}>
                        <Upload size={14} /> SDS yükle
                        <input
                          type="file"
                          accept=".pdf,.doc,.docx,.png,.jpg,.jpeg"
                          style={{display: 'none'}}
                          disabled={busy}
                          onChange={(e) => {
                            const f = e.target.files?.[0];
                            e.target.value = '';
                            if (f) void ensureDocAndUpload(r, f);
                          }}
                        />
                      </label>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {open && (
        <Modal
          className="sds-product-modal"
          title={(
            <span className="sds-modal-heading">
              <span className="sds-modal-heading-icon" aria-hidden="true"><Beaker size={22} /></span>
              <span>
                <strong>Yeni Kimyasal Ürün</strong>
                <small>SDS siciline güvenli ve izlenebilir ürün kaydı</small>
              </span>
            </span>
          )}
          close={() => setOpen(false)}
        >
          <form className="sds-product-form" onSubmit={save}>
            <div className="sds-modal-intro">
              <span className="sds-modal-intro-icon" aria-hidden="true"><ShieldCheck size={21} /></span>
              <span className="sds-modal-intro-copy">
                <strong>Ürün ve takip bilgileri</strong>
                <small>Kimyasalı tanımlayın; SDS durumu ve gözden geçirme tarihini kaydedin.</small>
              </span>
              <span className="sds-required-note"><b>*</b> Zorunlu alan</span>
            </div>

            <div className="sds-product-grid">
              {workplaceAccount ? (
                <Field
                  label="Şube"
                  icon={MapPin}
                  requiredLabel
                  hint={workplaceBranches.length
                    ? 'Kimyasal ürün seçtiğiniz şubeye kaydedilecektir.'
                    : 'Bu işyerine tanımlanmış aktif şube bulunamadı.'}
                >
                  <select
                    required
                    disabled={workplaceBranches.length === 0}
                    value={form.branch_id}
                    onChange={(e) => setForm({...form, branch_id: e.target.value})}
                  >
                    <option value="">
                      {workplaceBranches.length ? 'Şube seçiniz' : 'Tanımlı şube bulunamadı'}
                    </option>
                    {workplaceBranches.map((branch) => (
                      <option key={branch.id} value={branch.id}>{branch.name}</option>
                    ))}
                  </select>
                </Field>
              ) : (
                <Field label="Firma" icon={Building2} requiredLabel>
                  <select
                    required
                    value={form.company_id}
                    onChange={(e) => setForm({...form, company_id: e.target.value})}
                  >
                    <option value="">Seçiniz</option>
                    {companies.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </Field>
              )}
              <Field
                label="Ürün adı"
                icon={Beaker}
                required
                placeholder="Örn. Aseton"
                value={form.product_name}
                onChange={(e) => setForm({...form, product_name: e.target.value})}
              />
              <Field
                label="CAS (isteğe bağlı)"
                icon={Hash}
                placeholder="Örn. 67-64-1"
                value={form.cas_number}
                onChange={(e) => setForm({...form, cas_number: e.target.value})}
              />
              <Field
                label="Sonraki gözden geçirme"
                icon={CalendarClock}
                type="date"
                value={form.next_review_date}
                onChange={(e) => setForm({...form, next_review_date: e.target.value})}
              />
              <label className={`sds-file-card${form.has_sds_file ? ' is-active' : ''}`}>
                <input
                  className="sds-toggle-input"
                  type="checkbox"
                  checked={!!form.has_sds_file}
                  onChange={(e) => setForm({...form, has_sds_file: e.target.checked})}
                />
                <span className="sds-file-card-icon" aria-hidden="true"><FileCheck2 size={21} /></span>
                <span className="sds-file-card-copy">
                  <strong>SDS dosyası mevcut</strong>
                  <small>Güvenlik bilgi formu hazırsa bu seçeneği etkinleştirin.</small>
                </span>
                <span className="sds-toggle-ui" aria-hidden="true"><span /></span>
              </label>
              <Field label="Not" className="sds-notes-field">
                <textarea
                  rows={3}
                  placeholder="Ürün, kullanım alanı veya takip süreciyle ilgili kısa not ekleyin…"
                  value={form.notes}
                  onChange={(e) => setForm({...form, notes: e.target.value})}
                />
              </Field>
            </div>

            <div className="sds-product-actions">
              <button
                type="button"
                className="sds-cancel-button"
                disabled={busy}
                onClick={() => setOpen(false)}
              >
                Vazgeç
              </button>
              <button
                type="submit"
                className="sds-save-button"
                disabled={busy || (workplaceAccount && !form.branch_id)}
              >
                <Save size={17} aria-hidden="true" />
                {busy ? 'Kaydediliyor…' : 'Ürünü Kaydet'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {ghsRow && (
        <Modal title={`Tehlike etiketi — ${ghsRow.product_name}`} close={() => setGhsRow(null)}>
          <form onSubmit={saveGhs}>
            <p style={{marginTop: 0, color: '#475569', fontSize: 14}}>
              GHS/CLP piktogram checklist (stub). Sahada etiket üzerindeki işaretleri seçin.
            </p>
            <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16}}>
              {(catalog.length ? catalog : []).map((p) => (
                <label key={p.code} style={{display: 'flex', gap: 8, alignItems: 'center', fontSize: 14}}>
                  <input
                    type="checkbox"
                    checked={ghsSelected.includes(p.code)}
                    onChange={() => toggleGhs(p.code)}
                  />
                  <span><strong>{p.code}</strong> — {p.label}</span>
                </label>
              ))}
            </div>
            <div className="form-actions">
              <button type="submit" disabled={busy}>Kaydet</button>
            </div>
          </form>
        </Modal>
      )}
      </div>}

      {activeTab === 'pkd' && (
        <PkdRegisterPanel
          user={user}
          workplaceAccount={workplaceAccount}
          workplaceBranches={workplaceBranches}
          companies={companies}
          canEdit={canEdit}
        />
      )}
    </>
  );
}
