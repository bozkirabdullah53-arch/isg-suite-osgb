import {useEffect, useMemo, useState} from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  CircleAlert,
  ClipboardCheck,
  Download,
  FileCheck2,
  FileText,
  Filter,
  Info,
  Map,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
  Users,
  X,
} from 'lucide-react';

import {api, downloadFile, uploadFile} from './api';
import {AppModal} from './ui_modal';
import {EmergencyKrokiEditor} from './emergency_kroki_editor';
import {
  EMERGENCY_SCENARIOS,
  cloneDetails,
  createEmptyPlan,
  formatPlanDate,
  getReadiness,
  planFormFromRow,
  readinessTone,
  scenarioLabel,
} from './emergency_plan_logic';

const EDIT_ROLES = ['safety_specialist', 'global_admin'];
const MIN_DATE = '2000-01-01';
const MAX_DATE = '2100-12-31';

function useEmergencyCompanies() {
  const [companies, setCompanies] = useState([]);
  useEffect(() => {
    api('/companies').then(setCompanies).catch(() => setCompanies([]));
  }, []);
  return companies;
}

function companyFor(companies, id) {
  return companies.find((company) => String(company.id) === String(id)) || null;
}

function updateDetails(form, setForm, key, value) {
  setForm({...form, details: {...cloneDetails(form.details), [key]: value}});
}

function dateIsValid(value) {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split('-').map(Number);
  const dt = new Date(year, month - 1, day);
  return year >= 2000 && year <= 2100 && dt.getFullYear() === year && dt.getMonth() === month - 1 && dt.getDate() === day;
}

function ReadinessBadge({readiness}) {
  const tone = readinessTone(readiness);
  return (
    <span className={`ep-readiness-badge ep-readiness-${tone}`}>
      {tone === 'ready' ? <CheckCircle2 size={14} /> : <CircleAlert size={14} />}
      {readiness?.label || 'İnceleme gerekli'}
    </span>
  );
}

function StatCard({icon: Icon, label, value, note, tone = 'blue'}) {
  return (
    <div className={`ep-stat-card ep-stat-${tone}`}>
      <div className="ep-stat-icon"><Icon size={18} /></div>
      <div>
        <div className="ep-stat-label">{label}</div>
        <div className="ep-stat-value">{value}</div>
        <div className="ep-stat-note">{note}</div>
      </div>
    </div>
  );
}

function ScenarioPicker({details, setForm, form}) {
  const selected = new Set(details.emergency_types || []);
  function toggle(code) {
    const next = new Set(selected);
    if (next.has(code)) next.delete(code);
    else next.add(code);
    setForm({...form, details: {...details, emergency_types: [...next]}});
  }
  return (
    <div className="ep-scenario-grid">
      {EMERGENCY_SCENARIOS.map((scenario) => (
        <label className={`ep-check-card ${selected.has(scenario.code) ? 'is-selected' : ''}`} key={scenario.code}>
          <input type="checkbox" checked={selected.has(scenario.code)} onChange={() => toggle(scenario.code)} />
          <span className="ep-check-mark"><Check size={13} /></span>
          <span>{scenario.label}</span>
        </label>
      ))}
    </div>
  );
}

function ContactEditor({details, setForm, form}) {
  const contacts = Array.isArray(details.external_contacts) ? details.external_contacts : [];
  function setContact(index, key, value) {
    const next = contacts.map((contact, i) => i === index ? {...contact, [key]: value} : contact);
    setForm({...form, details: {...details, external_contacts: next}});
  }
  function addContact() {
    setForm({...form, details: {...details, external_contacts: [...contacts, {name: '', phone: '', note: ''}]}});
  }
  function removeContact(index) {
    setForm({...form, details: {...details, external_contacts: contacts.filter((_, i) => i !== index)}});
  }
  return (
    <div className="ep-contacts">
      <div className="ep-contact-head">
        <div>
          <strong>Acil iletişim listesi</strong>
          <span>112 yanında işyerine uygun yerel ve tesis irtibatlarını ekleyin.</span>
        </div>
        <button type="button" className="ep-link-button" onClick={addContact}><Plus size={15} /> İrtibat ekle</button>
      </div>
      {contacts.map((contact, index) => (
        <div className="ep-contact-row" key={`${index}-${contact.name}`}>
          <input aria-label="Kurum veya kişi" placeholder="Kurum / kişi" value={contact.name || ''} onChange={(e) => setContact(index, 'name', e.target.value)} />
          <input aria-label="Telefon" placeholder="Telefon" value={contact.phone || ''} onChange={(e) => setContact(index, 'phone', e.target.value)} />
          <input aria-label="Not" placeholder="Not / açıklama" value={contact.note || ''} onChange={(e) => setContact(index, 'note', e.target.value)} />
          <button type="button" className="ep-icon-button" aria-label="İrtibatı kaldır" onClick={() => removeContact(index)}><X size={16} /></button>
        </div>
      ))}
      {!contacts.length && <div className="ep-empty-inline">Henüz iletişim kaydı yok.</div>}
    </div>
  );
}

function PlanFormModal({mode, form, setForm, companies, busy, error, onClose, onSave}) {
  const [step, setStep] = useState(0);
  const details = cloneDetails(form.details);
  const selectedCompany = companyFor(companies, form.company_id);
  const steps = [
    {label: 'Künye', note: 'İşyeri ve geçerlilik'},
    {label: 'Risk', note: 'Senaryo ve tedbir'},
    {label: 'Uygulama', note: 'Tahliye ve iletişim'},
  ];

  function setField(key, value) {
    setForm({...form, [key]: value});
  }
  function nextStep() {
    if (step === 0 && (!form.company_id || !String(form.title || '').trim())) return;
    if (step < steps.length - 1) setStep(step + 1);
  }
  function submit(event) {
    event.preventDefault();
    if (step < steps.length - 1) {
      nextStep();
      return;
    }
    onSave(event);
  }

  return (
    <AppModal
      title={mode === 'edit' ? 'Acil durum planını düzenle' : 'Yeni acil durum planı'}
      close={busy ? undefined : onClose}
      wide
      className="ep-plan-modal"
    >
      <form className="ep-form" onSubmit={submit}>
        <div className="ep-form-intro">
          <div className="ep-form-intro-icon"><ShieldCheck size={20} /></div>
          <div>
            <strong>Mevzuat odaklı plan künye ve uygulama akışı</strong>
            <span>Eksik alanlar kaydedilebilir; kontrol merkezi sonraki aksiyonları görünür tutar.</span>
          </div>
        </div>
        <div className="ep-stepper" aria-label="Plan hazırlama adımları">
          {steps.map((item, index) => (
            <button key={item.label} type="button" className={`ep-step ${index === step ? 'is-active' : ''} ${index < step ? 'is-done' : ''}`} onClick={() => setStep(index)}>
              <span className="ep-step-number">{index < step ? <Check size={14} /> : index + 1}</span>
              <span><strong>{item.label}</strong><small>{item.note}</small></span>
            </button>
          ))}
        </div>

        {step === 0 && (
          <div className="ep-form-section">
            <div className="ep-section-heading"><div><span className="ep-kicker">01 / KÜNYE</span><h4>Plan hangi işyerine ait?</h4><p>Planın işyeri adresi ve işveren / vekil bilgisi firma kartından beslenir.</p></div></div>
            <div className="ep-form-grid">
              <label className="ep-field ep-field-wide"><span>İşyeri <b>*</b></span><select required disabled={mode === 'edit'} value={form.company_id || ''} onChange={(e) => setField('company_id', e.target.value)}><option value="">İşyeri seçin</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}</select>{mode === 'edit' && <small className="ep-field-help">Planın işyeri değişikliği için yeni kayıt oluşturun.</small>}</label>
              <label className="ep-field"><span>Plan başlığı <b>*</b></span><input required value={form.title || ''} onChange={(e) => setField('title', e.target.value)} placeholder="Örn. Merkez bina acil durum planı" /></label>
              <label className="ep-field"><span>Revizyon</span><input value={form.revision_no || ''} onChange={(e) => setField('revision_no', e.target.value)} placeholder="00" /></label>
              <label className="ep-field"><span>Plan tarihi <b>*</b></span><input type="date" required min={MIN_DATE} max={MAX_DATE} value={form.plan_date || ''} onChange={(e) => setField('plan_date', e.target.value)} /></label>
              <label className="ep-field"><span>Gözden geçirme tarihi <b>*</b></span><input type="date" required min={form.plan_date || MIN_DATE} max={MAX_DATE} value={form.next_review_date || ''} onChange={(e) => setField('next_review_date', e.target.value)} /></label>
            </div>
            {selectedCompany && (
              <div className="ep-company-context">
                <div><span>İşyeri adresi</span><strong>{selectedCompany.address || 'Firma kartında adres bilgisi eksik'}</strong></div>
                <div><span>Tehlike sınıfı</span><strong>{selectedCompany.hazard_class || 'Belirtilmemiş'}</strong></div>
                <div><span>İşveren / vekil</span><strong>{selectedCompany.authorized_person || 'Firma kartında tanımlı değil'}</strong></div>
              </div>
            )}
          </div>
        )}

        {step === 1 && (
          <div className="ep-form-section">
            <div className="ep-section-heading"><div><span className="ep-kicker">02 / RİSK VE TEDBİR</span><h4>Hangi senaryolara hazırlanıyorsunuz?</h4><p>Risk değerlendirmesi ve işyerinin özel koşullarına göre bir veya daha fazla senaryo seçin.</p></div></div>
            <ScenarioPicker details={details} form={form} setForm={setForm} />
            <label className="ep-field"><span>Önleyici ve sınırlandırıcı tedbirler</span><textarea rows={5} value={details.preventive_measures || ''} onChange={(e) => updateDetails(form, setForm, 'preventive_measures', e.target.value)} placeholder="Örn. yanıcı malzemelerin depolama koşulları, periyodik kontroller, alarm ve enerji izolasyonu..." /></label>
            <div className="ep-split-fields"><label className="ep-field"><span>Ölçüm ve değerlendirme notu</span><textarea rows={4} value={details.measurement_evaluation || ''} onChange={(e) => updateDetails(form, setForm, 'measurement_evaluation', e.target.value)} placeholder="Gerekli ölçümler, mevcut raporlar veya neden uygulanamaz olduğu" /></label><label className="ep-field"><span>Acil durum ekipmanı ve KKD listesi</span><textarea rows={4} value={details.equipment_inventory || ''} onChange={(e) => updateDetails(form, setForm, 'equipment_inventory', e.target.value)} placeholder="Yangın, ilk yardım, kurtarma ve gerekiyorsa KKD ekipmanları" /></label></div>
            <div className="ep-split-fields">
              <div className="ep-choice-panel"><span className="ep-field-label">Özel risk alanları</span><div className="ep-choice-row"><label><input type="radio" name="special-risk" checked={details.special_risk_mode === 'not_evaluated'} onChange={() => updateDetails(form, setForm, 'special_risk_mode', 'not_evaluated')} /> Değerlendirilmedi</label><label><input type="radio" name="special-risk" checked={details.special_risk_mode === 'not_applicable'} onChange={() => updateDetails(form, setForm, 'special_risk_mode', 'not_applicable')} /> Uygulanamaz</label><label><input type="radio" name="special-risk" checked={details.special_risk_mode === 'present'} onChange={() => updateDetails(form, setForm, 'special_risk_mode', 'present')} /> Var</label></div>{details.special_risk_mode === 'present' && <textarea rows={3} value={details.special_risk_areas || ''} onChange={(e) => updateDetails(form, setForm, 'special_risk_areas', e.target.value)} placeholder="Kimyasal, patlama, biyolojik veya diğer özel riskli alanlar" />}</div>
              <div className="ep-choice-panel"><span className="ep-field-label">Enerji kesme / vana noktaları</span><div className="ep-choice-row"><label><input type="radio" name="energy-control" checked={details.energy_controls_mode === 'not_evaluated'} onChange={() => updateDetails(form, setForm, 'energy_controls_mode', 'not_evaluated')} /> Değerlendirilmedi</label><label><input type="radio" name="energy-control" checked={details.energy_controls_mode === 'not_applicable'} onChange={() => updateDetails(form, setForm, 'energy_controls_mode', 'not_applicable')} /> Uygulanamaz</label><label><input type="radio" name="energy-control" checked={details.energy_controls_mode === 'present'} onChange={() => updateDetails(form, setForm, 'energy_controls_mode', 'present')} /> Var</label></div>{details.energy_controls_mode === 'present' && <textarea rows={3} value={details.energy_shutoff_points || ''} onChange={(e) => updateDetails(form, setForm, 'energy_shutoff_points', e.target.value)} placeholder="Elektrik ana kesici, gaz vanası, proses izolasyonu ve sorumlusu" />}</div>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="ep-form-section">
            <div className="ep-section-heading"><div><span className="ep-kicker">03 / UYGULAMA</span><h4>Tahliye anında herkes ne yapacak?</h4><p>Bu bilgiler kroki, ekip ve tatbikat süreçleriyle birlikte kullanılır.</p></div></div>
            <div className="ep-form-grid">
              <label className="ep-field ep-field-wide"><span>Müdahale, haberleşme ve tahliye yöntemi</span><textarea rows={6} value={details.response_methods || ''} onChange={(e) => updateDetails(form, setForm, 'response_methods', e.target.value)} placeholder="İhbar yöntemi, ilk müdahale, ekiplerin görev sırası, tahliye, toplanma ve yoklama adımlarını yazın." /></label>
              <label className="ep-field ep-field-wide"><span>Toplanma alanı / alanları</span><textarea rows={3} value={form.assembly_areas || ''} onChange={(e) => setField('assembly_areas', e.target.value)} placeholder="Alan adı, adres veya koordinat; mümkünse alternatif alanı da belirtin." /></label>
              <label className="ep-field ep-field-wide"><span>Özel desteğe ihtiyaç duyan kişiler için yöntem</span><textarea rows={3} value={details.special_groups || ''} onChange={(e) => updateDetails(form, setForm, 'special_groups', e.target.value)} placeholder="Engelli, yaşlı, gebe, çocuk veya refakat ihtiyacı olan kişiler için destek yöntemi" /></label>
            </div>
            <div className="ep-toggle-row"><label className={`ep-toggle-card ${details.visitors_included ? 'is-on' : ''}`}><input type="checkbox" checked={!!details.visitors_included} onChange={(e) => updateDetails(form, setForm, 'visitors_included', e.target.checked)} /><span><strong>Ziyaretçiler dahil</strong><small>Girişte bilgilendirme / refakat akışı</small></span></label><label className={`ep-toggle-card ${details.temporary_workers_included ? 'is-on' : ''}`}><input type="checkbox" checked={!!details.temporary_workers_included} onChange={(e) => updateDetails(form, setForm, 'temporary_workers_included', e.target.checked)} /><span><strong>Geçici çalışanlar dahil</strong><small>İşe başlama ve saha bilgilendirmesi</small></span></label><label className={`ep-toggle-card ${details.shared_workplace ? 'is-on' : ''}`}><input type="checkbox" checked={!!details.shared_workplace} onChange={(e) => updateDetails(form, setForm, 'shared_workplace', e.target.checked)} /><span><strong>Birden fazla işveren / ortak saha</strong><small>Koordinasyon kontrolü gerektirir</small></span></label></div>{details.shared_workplace && <label className="ep-field"><span>Ortak saha koordinasyon notu</span><textarea rows={3} value={details.shared_workplace_note || ''} onChange={(e) => updateDetails(form, setForm, 'shared_workplace_note', e.target.value)} placeholder="Ana işveren, alt işverenler ve ortak acil durum düzenlemeleri" /></label>}
            <ContactEditor details={details} form={form} setForm={setForm} />
            <div className="ep-implementation-panel"><div className="ep-contact-head"><div><strong>Yayın, onay ve tatbikat doğrulaması</strong><span>Tatbikat modülünde “Yapıldı” kaydı varsa sistem onu öncelikli kaynak kabul eder. Onay seçimi belgeyle ayrıca doğrulanmalıdır.</span></div></div><div className="ep-form-grid"><label className="ep-field"><span>Onay / imza durumu</span><select value={details.approval_status || 'not_confirmed'} onChange={(e) => updateDetails(form, setForm, 'approval_status', e.target.value)}><option value="not_confirmed">Onay kaydı yok</option><option value="employer_signed">İşveren imza kaydı mevcut</option><option value="secure_esign">Güvenli e-imza / EYAS kaydı mevcut</option></select></label><label className="ep-field"><span>Son tatbikat (manuel kayıt)</span><input type="date" min={MIN_DATE} max={MAX_DATE} value={details.last_drill_date || ''} onChange={(e) => updateDetails(form, setForm, 'last_drill_date', e.target.value)} /></label><label className="ep-field"><span>Planlanan sonraki tatbikat</span><input type="date" min={MIN_DATE} max={MAX_DATE} value={details.next_drill_date || ''} onChange={(e) => updateDetails(form, setForm, 'next_drill_date', e.target.value)} /></label><label className="ep-field"><span>Tutanak / kayıt referansı</span><input value={details.drill_record_ref || ''} onChange={(e) => updateDetails(form, setForm, 'drill_record_ref', e.target.value)} placeholder="Örn. TAT-2026-004" /></label></div><div className="ep-confirm-row"><label><input type="checkbox" checked={!!details.posted_confirmed} onChange={(e) => updateDetails(form, setForm, 'posted_confirmed', e.target.checked)} /><span><strong>Krokiler görünür yerlere asıldı</strong><small>Giriş, çıkış ve kat seviyeleri saha doğrulaması</small></span></label><label><input type="checkbox" checked={!!details.employees_informed} onChange={(e) => updateDetails(form, setForm, 'employees_informed', e.target.checked)} /><span><strong>Çalışan bilgilendirmesi tamamlandı</strong><small>Yeni ve geçici çalışanlar dahil</small></span></label></div></div>
            <label className="ep-field"><span>Ek not</span><textarea rows={3} value={form.notes || ''} onChange={(e) => setField('notes', e.target.value)} placeholder="Planın saha uygulamasına ilişkin ek notlar" /></label>
          </div>
        )}

        {error && <div className="ep-form-error"><AlertTriangle size={16} /> {error}</div>}
        <div className="ep-form-footer">
          <div className="ep-form-hint"><Info size={15} /> <span>{step === 2 ? 'Kaydettikten sonra Kroki Studio ile kat planlarını ve tahliye işaretlerini tamamlayabilirsiniz.' : 'İlerleyen adımlarda eksik başlıklar hazırlık kontrolünde işaretlenir.'}</span></div>
          <div className="ep-form-actions"><button type="button" className="ep-secondary-button" disabled={busy} onClick={step ? () => setStep(step - 1) : onClose}>{step ? <><ArrowLeft size={15} /> Geri</> : 'Vazgeç'}</button>{step < steps.length - 1 ? <button type="submit" className="ep-primary-button">Devam et <ArrowRight size={15} /></button> : <button type="submit" className="ep-primary-button" disabled={busy}>{busy ? 'Kaydediliyor…' : <><FileCheck2 size={16} /> Planı kaydet</>}</button>}</div>
        </div>
      </form>
    </AppModal>
  );
}

export function EmergencyPlansPage({user}) {
  const canEdit = EDIT_ROLES.includes(user.role);
  const companies = useEmergencyCompanies();
  const [rows, setRows] = useState([]);
  const [companyFilter, setCompanyFilter] = useState(user.company_id ? String(user.company_id) : '');
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [modalMode, setModalMode] = useState(null);
  const [form, setForm] = useState(createEmptyPlan({companyId: user.company_id || ''}));
  const [editPlanId, setEditPlanId] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  async function load() {
    setBusy(true);
    try {
      setRows(await api('/emergency-plans'));
      setError('');
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => { void load(); }, []);

  const visibleRows = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase('tr-TR');
    return rows.filter((row) => {
      const companyMatch = !companyFilter || String(row.company_id) === String(companyFilter);
      if (!companyMatch) return false;
      if (!needle) return true;
      const haystack = [row.title, row.company_name, row.company_address, row.assembly_areas, row.scenario_summary].filter(Boolean).join(' ').toLocaleLowerCase('tr-TR');
      return haystack.includes(needle);
    });
  }, [rows, companyFilter, query]);

  const metrics = useMemo(() => {
    const readiness = rows.map(getReadiness);
    return {
      total: rows.length,
      ready: readiness.filter((item) => item.status === 'ready').length,
      action: readiness.filter((item) => ['action', 'draft'].includes(item.status)).length,
      overdue: rows.filter((row) => row.review_status === 'overdue').length,
    };
  }, [rows]);

  function openCreate() {
    const selected = companyFor(companies, user.company_id) || companies[0];
    setForm(createEmptyPlan({companyId: selected?.id || '', hazardClass: selected?.hazard_class}));
    setError('');
    setModalMode('create');
  }
  function openEdit(row) {
    setForm(planFormFromRow(row, companyFor(companies, row.company_id)));
    setError('');
    setModalMode('edit');
  }
  function closeForm() {
    if (!busy) setModalMode(null);
  }
  async function savePlan(event) {
    event.preventDefault();
    setError('');
    if (!dateIsValid(form.plan_date) || !dateIsValid(form.next_review_date)) {
      setError('Plan ve gözden geçirme tarihleri 2000–2100 arasında gerçek bir tarih olmalı.');
      return;
    }
    if (form.next_review_date < form.plan_date) {
      setError('Gözden geçirme tarihi plan tarihinden önce olamaz.');
      return;
    }
    if (!form.company_id || !String(form.title || '').trim()) {
      setError('İşyeri ve plan başlığı zorunludur.');
      return;
    }
    setBusy(true);
    try {
      const details = cloneDetails(form.details);
      const payload = {
        title: String(form.title || '').trim(),
        revision_no: String(form.revision_no || '00').trim() || '00',
        plan_date: form.plan_date,
        next_review_date: form.next_review_date,
        assembly_areas: String(form.assembly_areas || '').trim() || null,
        scenario_summary: String(form.scenario_summary || '').trim() || (details.emergency_types || []).map(scenarioLabel).join(', ') || null,
        notes: String(form.notes || '').trim() || null,
        details,
      };
      const saved = modalMode === 'edit'
        ? await api(`/emergency-plans/${form.id}`, {method: 'PATCH', body: JSON.stringify(payload)})
        : await api('/emergency-plans', {method: 'POST', body: JSON.stringify({...payload, company_id: Number(form.company_id)})});
      setModalMode(null);
      await load();
      if (modalMode === 'create' && saved?.id) setEditPlanId(saved.id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function uploadPoster(row, file) {
    if (!file) return;
    setBusy(true);
    try {
      await uploadFile(`/emergency-plans/${row.id}/kroki`, file);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function removePlan(row) {
    if (!window.confirm(`“${row.title || `Plan #${row.id}`}” listeden kaldırılsın mı?`)) return;
    setBusy(true);
    try {
      await api(`/emergency-plans/${row.id}`, {method: 'DELETE'});
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function downloadPlanPdf(row) {
    try {
      await downloadFile(`/emergency-plans/${row.id}/export.pdf`, `acil-durum-plani-${row.id}.pdf`);
    } catch (e) {
      setError(e.message);
    }
  }

  if (editPlanId) {
    return (
      <div className="ep-workspace">
        <div className="ep-editor-toolbar"><button type="button" className="ep-back-button" onClick={() => { setEditPlanId(null); void load(); }}><ArrowLeft size={16} /> Plan listesine dön</button><div><span className="ep-kicker">KROKİ STUDIO</span><h3><Map size={20} /> Kat bazlı tahliye planı</h3></div><span className="ep-live-pill"><span /> Çalışma alanı</span></div>
        <section className="ep-editor-shell"><EmergencyKrokiEditor planId={editPlanId} user={user} onClose={() => { setEditPlanId(null); void load(); }} /></section>
      </div>
    );
  }

  return (
    <div className="emergency-plan-page">
      <div className="ep-hero">
        <div className="ep-hero-glow" />
        <div className="ep-hero-content">
          <div className="ep-hero-kicker"><span className="ep-orb"><Sparkles size={13} /></span> MEVZUAT ODAKLI ÇALIŞMA ALANI <span className="ep-hero-version">v1.0</span></div>
          <h1>Acil durum planı,<br /><span>hazır olduğunuz anda</span> değerli.</h1>
          <p>İşyeri künyesinden senaryolara, ekiplerden tahliye krokisine kadar tüm kritik başlıkları tek bir kontrol merkezinde yönetin.</p>
          <div className="ep-hero-proof"><span><ShieldCheck size={14} /> Md. 5 · 10 · 11 · 12 · 13 · 14 · 15</span><span><FileCheck2 size={14} /> Denetlenebilir çıktı</span></div>
        </div>
        <div className="ep-hero-actions"><button type="button" className="ep-hero-secondary" onClick={() => downloadFile('/emergency-plans/export.xlsx', 'acil-durum-planlari.xlsx').catch((e) => setError(e.message))}><Download size={16} /> Excel dışa aktar</button>{canEdit && <button type="button" className="ep-hero-primary" onClick={openCreate}><Plus size={17} /> Yeni plan oluştur</button>}</div>
      </div>

      <div className="ep-notice"><div className="ep-notice-icon"><Info size={17} /></div><div><strong>Hazırlık düzeyi hukuki uygunluk beyanı değildir.</strong><span>Kontrol merkezi mevzuat başlıklarının belgelenmesini yönlendirir; saha doğrulaması, işveren onayı, ekip eğitimleri ve tatbikat kayıtları ayrıca tamamlanmalıdır.</span></div><a href="https://www.mevzuat.gov.tr/Metin.Aspx?MevzuatKod=7.5.18493&MevzuatIliski=0&sourceXmlSearch=" target="_blank" rel="noreferrer">Yönetmelik kaynağı <ArrowRight size={14} /></a></div>

      <div className="ep-stat-grid"><StatCard icon={ClipboardCheck} label="Toplam plan" value={metrics.total} note="Erişiminizdeki kayıtlar" /><StatCard icon={CheckCircle2} label="Hazır" value={metrics.ready} note="Zorunlu kontroller tamam" tone="green" /><StatCard icon={AlertTriangle} label="Aksiyon gerekli" value={metrics.action} note="Eksik başlık veya krokiler" tone="amber" /><StatCard icon={RefreshCw} label="Gözden geçirme" value={metrics.overdue} note="Termin geçmiş kayıt" tone="red" /></div>

      <section className="ep-control-bar"><div className="ep-control-title"><Filter size={16} /><span>Plan görünümü</span></div><label className="ep-select-control"><span>İşyeri</span><select value={companyFilter} onChange={(e) => setCompanyFilter(e.target.value)}><option value="">Tüm işyerleri</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}</select></label><label className="ep-search-control"><Search size={17} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Plan, işyeri veya toplanma alanı ara" /></label><button type="button" className="ep-refresh-button" onClick={() => void load()} disabled={busy}><RefreshCw size={16} className={busy ? 'ep-spin' : ''} /> Yenile</button></section>

      {error && <div className="ep-page-error"><AlertTriangle size={16} /> {error}<button type="button" onClick={() => setError('')} aria-label="Uyarıyı kapat"><X size={15} /></button></div>}

      <section className="ep-list-section"><div className="ep-section-topline"><div><span className="ep-kicker">PLAN PORTFÖYÜ</span><h2>İşyerlerinizin acil durum hazırlığı</h2></div><span className="ep-result-count">{visibleRows.length} plan gösteriliyor</span></div><div className="ep-plan-grid">{visibleRows.length ? visibleRows.map((row) => {
        const readiness = getReadiness(row);
        const tone = readinessTone(readiness);
        const companyName = row.company_name || companyFor(companies, row.company_id)?.name || `İşyeri #${row.company_id}`;
        const missing = (readiness.missing || []).slice(0, 2);
        return (
          <article className="ep-plan-card" key={row.id}>
            <div className="ep-card-head"><div className="ep-card-company"><div className="ep-company-mark">{companyName.slice(0, 1).toLocaleUpperCase('tr-TR')}</div><div><strong>{companyName}</strong><span>{row.company_address || companyFor(companies, row.company_id)?.address || 'Adres belirtilmemiş'}</span></div></div><ReadinessBadge readiness={readiness} /></div>
            <div className="ep-card-title-row"><div><h3>{row.title}</h3><span>Revizyon {row.revision_no || '00'} · {row.status || 'Aktif'}</span></div><div className={`ep-score ep-score-${tone}`}><strong>%{readiness.pct || 0}</strong><small>hazırlık</small></div></div>
            <div className={`ep-progress ep-progress-${tone}`}><span style={{width: `${Math.max(0, Math.min(100, readiness.pct || 0))}%`}} /></div>
            <div className="ep-card-metadata"><div><span>Gözden geçirme</span><strong className={row.review_status === 'overdue' ? 'is-overdue' : ''}>{formatPlanDate(row.next_review_date)}</strong></div><div><span>Kroki</span><strong>{row.has_scene || row.kroki_file_name ? 'Hazır' : 'Eksik'}</strong></div><div><span>Toplanma</span><strong>{row.assembly_areas ? 'Tanımlı' : 'Eksik'}</strong></div></div>
            <div className="ep-card-chips"><span><Map size={14} /> {row.floor_count || 0} kat</span><span><Users size={14} /> {readiness.team_summary?.member_count || 0} aktif üye</span><span><FileText size={14} /> {readiness.required_passed || 0}/{readiness.required_total || 0} kontrol</span><span><ClipboardCheck size={14} /> {readiness.drill_summary?.last_date ? 'Tatbikat kayıtlı' : 'Tatbikat eksik'}</span></div>
            {missing.length > 0 ? <div className="ep-card-missing"><CircleAlert size={15} /><span>{missing[0]}{missing.length > 1 ? ` +${missing.length - 1} başlık` : ''}</span></div> : <div className="ep-card-ready"><CheckCircle2 size={15} /><span>Zorunlu başlıklar tamamlandı; saha doğrulamasını sürdürün.</span></div>}
            {expandedId === row.id && <div className="ep-check-list">{(readiness.checks || []).map((check) => <div className={`ep-check-line ep-check-line-${check.status}`} key={check.id}><span>{check.status === 'ok' ? <CheckCircle2 size={14} /> : <CircleAlert size={14} />}</span><div><strong>{check.label}</strong><small>{check.detail}</small></div><em>{check.reference || 'Kontrol'}</em></div>)}</div>}
            <div className="ep-card-actions"><button type="button" className="ep-action-primary" onClick={() => setEditPlanId(row.id)}><Map size={15} /> Kroki Studio</button><button type="button" className="ep-action-secondary" onClick={() => setExpandedId(expandedId === row.id ? null : row.id)}><ClipboardCheck size={15} /> {expandedId === row.id ? 'Kontrolü kapat' : 'Kontrol detayı'}</button>{canEdit && <button type="button" className="ep-action-secondary" onClick={() => openEdit(row)}><Pencil size={15} /> Düzenle</button>}<button type="button" className="ep-action-icon" title="Plan PDF'i indir" aria-label="Plan PDF'i indir" onClick={() => void downloadPlanPdf(row)}><Download size={16} /></button><label className="ep-action-icon ep-upload-action" title="Poster dosyası yükle"><Upload size={16} /><input type="file" hidden accept=".png,.jpg,.jpeg,.pdf,.webp" onChange={(e) => { void uploadPoster(row, e.target.files?.[0]); e.target.value = ''; }} /></label>{canEdit && <button type="button" className="ep-action-icon ep-danger-action" title="Planı listeden kaldır" aria-label="Planı listeden kaldır" onClick={() => void removePlan(row)}><Trash2 size={16} /></button>}</div>
          </article>
        );
      }) : <div className="ep-empty-state"><div className="ep-empty-icon"><FileText size={26} /></div><h3>{rows.length ? 'Filtreye uyan plan bulunamadı' : 'Henüz bir acil durum planı yok'}</h3><p>{rows.length ? 'İşyeri filtresini veya arama ifadenizi değiştirin.' : 'İlk planı oluşturarak mevzuat odaklı kontrol akışını başlatın.'}</p>{canEdit && !rows.length && <button type="button" className="ep-primary-button" onClick={openCreate}><Plus size={16} /> İlk planı oluştur</button>}</div>}</div></section>

      <div className="ep-bottom-note"><div className="ep-bottom-icon"><ShieldCheck size={18} /></div><div><strong>Profesyonel kontrol notu</strong><p>Bu modül; İşyerlerinde Acil Durumlar Hakkında Yönetmelik'in plan içeriği, ekipler, bilgilendirme, tatbikat ve yenileme başlıklarını görünür kılar. Krokiler göz hizasında görünür yerlere asılmalı; ekip görevlendirmeleri ve eğitim geçerlilikleri ayrıca doğrulanmalıdır.</p><div className="ep-related-links"><a href="#m=acil_ekipler">Acil ekipleri yönet <ArrowRight size={13} /></a><a href="#m=tatbikat">Tatbikat kaydı aç <ArrowRight size={13} /></a></div></div></div>

      {modalMode && <PlanFormModal mode={modalMode} form={form} setForm={setForm} companies={companies} busy={busy} error={error} onClose={closeForm} onSave={savePlan} />}
    </div>
  );
}
