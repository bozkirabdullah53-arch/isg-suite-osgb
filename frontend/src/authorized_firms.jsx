import {useEffect, useMemo, useState} from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Building2,
  CalendarDays,
  CheckCircle2,
  ClipboardCheck,
  Download,
  Eye,
  FileArchive,
  FileText,
  Plus,
  Printer,
  RefreshCw,
  Save,
  Search,
  ShieldCheck,
  Stethoscope,
  XCircle,
} from 'lucide-react';

import {api, downloadFile} from './api';
import {AppModal} from './ui_modal';
import {
  PROFESSIONAL_STATUS_LABELS,
  READINESS_LABELS,
  buildAuthorizedFirmQuery,
  normalizeProfilePayload,
  readinessTone,
  toggleCompletedStep,
  validateDateRange,
  validityTone,
} from './authorized_firm_logic';
import './authorized_firms.css';


const EMPTY_PROFILE = {
  company_id: '',
  firm_name: '',
  firm_type: '',
  province: '',
  district: '',
  address: '',
  authorized_representative: '',
  contact_email: '',
  contact_phone: '',
  employee_count_declared: '',
  hazard_class: '',
  authorization_scope: '',
  authorization_number: '',
  authorization_issue_date: '',
  authorization_start_date: '',
  authorization_expiry_date: '',
  last_review_date: '',
  review_state: 'internal_record',
  notes: '',
  is_active: true,
};

const EMPTY_DOCUMENT = {
  document_type: 'yetki_belgesi',
  title: '',
  mandatory: true,
  start_date: '',
  expiry_date: '',
  review_date: '',
  renewal_date: '',
  notes: '',
  is_active: true,
};

let pendingCompanyContext = null;

function dateText(value) {
  if (!value) return '—';
  const [year, month, day] = String(value).slice(0, 10).split('-');
  return year && month && day ? `${day}.${month}.${year}` : String(value);
}

function TonePill({tone = 'neutral', children}) {
  return <span className={`af-pill af-${tone}`}>{children || '—'}</span>;
}

function ValidityPill({validity}) {
  if (!validity) return <TonePill>—</TonePill>;
  const days = validity.days_left;
  return (
    <TonePill tone={validityTone(validity.code)}>
      {validity.label}{days != null ? ` · ${days} gün` : ''}
    </TonePill>
  );
}

function ScoreGauge({value = 0, tone = 'neutral', label = 'Skor'}) {
  const safe = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div className={`af-score af-${tone}`}>
      <div><span>{label}</span><strong>{safe}/100</strong></div>
      <div className="af-score-track"><span style={{width: `${safe}%`}} /></div>
    </div>
  );
}

function Metric({label, value, tone = 'neutral', hint}) {
  return (
    <article className={`metric af-metric af-${tone}`}>
      <span>{label}</span>
      <strong>{value ?? '—'}</strong>
      {hint && <small>{hint}</small>}
    </article>
  );
}

function Field({label, children, span = false}) {
  return <label className={`field${span ? ' af-span' : ''}`}><span>{label}</span>{children}</label>;
}

function DetailTable({headers, rows, empty = 'Kayıt bulunmuyor.'}) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{headers.map((item) => <th key={item.key}>{item.label}</th>)}</tr></thead>
        <tbody>
          {rows.length ? rows.map((row, index) => (
            <tr key={row.id ?? row.code ?? index}>
              {headers.map((item) => <td key={item.key}>{item.render ? item.render(row) : String(row[item.key] ?? '—')}</td>)}
            </tr>
          )) : <tr><td colSpan={headers.length} className="empty">{empty}</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

export function AuthorizedFirmDashboardPanel({user, onNavigate}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (user?.role !== 'company_admin' || user?.company_id) return;
    api('/authorized-firms/dashboard')
      .then(setData)
      .catch((err) => setError(err.message || 'Yetkili firma özeti yüklenemedi.'));
  }, [user]);

  if (user?.role !== 'company_admin' || user?.company_id) return null;
  return (
    <section className="panel af-dashboard-panel">
      <div className="af-section-head">
        <div>
          <h3><Building2 size={19} /> Yetkili Firma Uygunluğu</h3>
          <p>Belge tarihleri, profesyonel uygunluğu ve görünür kategori skoru.</p>
        </div>
        <button type="button" className="secondary" onClick={() => onNavigate?.('authorized_firms')}>
          Firma yönetimine git <ArrowRight size={16} />
        </button>
      </div>
      {error && <p className="af-error">{error}</p>}
      {data && (
        <div className="cards osgb-cards">
          <Metric label="Toplam firma" value={data.total_firms} />
          <Metric label="30 gün içinde" value={data.expiring_30} tone={data.expiring_30 ? 'warn' : 'good'} />
          <Metric label="Süresi dolan" value={data.expired_authorizations} tone={data.expired_authorizations ? 'danger' : 'good'} />
          <Metric label="Kritik firma" value={data.critical_firms} tone={data.critical_firms ? 'danger' : 'good'} />
          <Metric label="Ortalama skor" value={`${data.average_score || 0}/100`} />
        </div>
      )}
    </section>
  );
}

export function AuthorizedFirmCompanyCard({companyId, onNavigate}) {
  const [data, setData] = useState(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    if (!companyId) return;
    api(`/authorized-firms/by-company/${companyId}`)
      .then((result) => { setData(result); setMissing(false); })
      .catch((error) => {
        if (error?.httpStatus === 404) setMissing(true);
      });
  }, [companyId]);

  function open() {
    pendingCompanyContext = data?.id
      ? {profileId: data.id}
      : {companyId: Number(companyId)};
    onNavigate?.('authorized_firms');
  }

  if (!data && !missing) return null;
  if (missing) {
    return (
      <section className="panel af-company-card">
        <div><strong>Yetkili firma kartı oluşturulmamış</strong><p>Bu işyeri için tarih ve uygunluk takibini başlatabilirsiniz.</p></div>
        <button type="button" className="secondary" onClick={open}>Kart oluştur</button>
      </section>
    );
  }
  const score = data.compliance_score || {};
  return (
    <section className="panel af-company-card">
      <div>
        <span className="af-eyebrow">Yetkili firma kartı</span>
        <h3>{data.firm_name}</h3>
        <p>{data.record_notice}</p>
      </div>
      <div className="af-company-card-stats">
        <ScoreGauge value={score.overall_score} tone={readinessTone(score.status)} label="Uygunluk" />
        <ValidityPill validity={data.authorization_validity} />
        <button type="button" onClick={open}>Kartı aç <ArrowRight size={15} /></button>
      </div>
    </section>
  );
}

export function AuthorizedFirmsPage({user, onNavigate}) {
  const [orgs, setOrgs] = useState([]);
  const [osgbId, setOsgbId] = useState(user?.osgb_id ? String(user.osgb_id) : '');
  const [companies, setCompanies] = useState([]);
  const [rows, setRows] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [detail, setDetail] = useState(null);
  const [filters, setFilters] = useState({q: '', province: '', district: '', active: '', hazard_class: '', document_status: '', professional_status: '', readiness: '', expiry_to: ''});
  const [profileModal, setProfileModal] = useState(false);
  const [profileForm, setProfileForm] = useState({...EMPTY_PROFILE});
  const [editingProfile, setEditingProfile] = useState(false);
  const [documentModal, setDocumentModal] = useState(false);
  const [documentForm, setDocumentForm] = useState({...EMPTY_DOCUMENT});
  const [professionalModal, setProfessionalModal] = useState(null);
  const [professionalForm, setProfessionalForm] = useState({certificate_issue_date: '', certificate_expiry_date: '', document_review_date: '', document_renewal_date: '', required_documents_status: 'review_required', required_documents_note: ''});
  const [inspectionDay, setInspectionDay] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const lockedOsgb = user?.role === 'company_admin';

  const availableCompanies = useMemo(
    () => companies.filter((item) => !osgbId || String(item.osgb_id) === String(osgbId)),
    [companies, osgbId],
  );

  async function refresh(targetId = osgbId, nextFilters = filters) {
    if (!targetId) return;
    setBusy(true);
    setError('');
    try {
      const query = buildAuthorizedFirmQuery({osgb_id: targetId, ...nextFilters});
      const [list, summary] = await Promise.all([
        api(`/authorized-firms${query}`),
        api(`/authorized-firms/dashboard?osgb_id=${encodeURIComponent(targetId)}`),
      ]);
      setRows(list.items || []);
      setDashboard(summary);
      if (detail?.id) {
        const updated = await api(`/authorized-firms/${detail.id}`).catch(() => null);
        if (updated) setDetail(updated);
      }
      return list.items || [];
    } catch (err) {
      setError(err.message || 'Yetkili firma kayıtları yüklenemedi.');
      return [];
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    let active = true;
    async function boot() {
      setBusy(true);
      try {
        const [organizations, companyRows] = await Promise.all([api('/osgb'), api('/companies')]);
        if (!active) return;
        setOrgs(organizations || []);
        setCompanies(companyRows || []);
        const target = lockedOsgb && user?.osgb_id
          ? String(user.osgb_id)
          : osgbId || (organizations?.[0] ? String(organizations[0].id) : '');
        setOsgbId(target);
        const loaded = target ? await refresh(target, filters) : [];
        const pending = pendingCompanyContext;
        pendingCompanyContext = null;
        if (!active || !pending) return;
        if (pending.profileId && loaded.some((item) => item.id === pending.profileId)) {
          setDetail(await api(`/authorized-firms/${pending.profileId}`));
        } else if (
          pending.companyId
          && companyRows.some(
            (item) => item.id === pending.companyId && String(item.osgb_id) === String(target),
          )
        ) {
          setEditingProfile(false);
          setProfileForm({...EMPTY_PROFILE, company_id: String(pending.companyId)});
          setProfileModal(true);
        }
      } catch (err) {
        if (active) setError(err.message || 'Başlangıç verileri yüklenemedi.');
      } finally {
        if (active) setBusy(false);
      }
    }
    void boot();
    return () => { active = false; };
    // İlk yüklemede oturum kapsamı sabittir.
  }, []);

  async function openDetail(id) {
    setBusy(true);
    setError('');
    try {
      const payload = await api(`/authorized-firms/${id}`);
      setDetail(payload);
    } catch (err) {
      setError(err.message || 'Firma kartı açılamadı.');
    } finally {
      setBusy(false);
    }
  }

  function startCreate() {
    setEditingProfile(false);
    setProfileForm({...EMPTY_PROFILE, company_id: availableCompanies[0]?.id ? String(availableCompanies[0].id) : ''});
    setProfileModal(true);
  }

  function startEdit() {
    if (!detail) return;
    const next = {...EMPTY_PROFILE};
    for (const key of Object.keys(next)) next[key] = detail[key] ?? '';
    next.company_id = String(detail.company_id);
    setProfileForm(next);
    setEditingProfile(true);
    setProfileModal(true);
  }

  async function saveProfile(event) {
    event.preventDefault();
    const periodError = validateDateRange(profileForm.authorization_start_date, profileForm.authorization_expiry_date, 'Yetki');
    if (periodError) { setError(periodError); return; }
    setBusy(true);
    setError('');
    try {
      const payload = normalizeProfilePayload({...profileForm, osgb_id: osgbId});
      let saved;
      if (editingProfile && detail?.id) {
        delete payload.osgb_id;
        delete payload.company_id;
        saved = await api(`/authorized-firms/${detail.id}`, {method: 'PATCH', body: JSON.stringify(payload)});
      } else {
        saved = await api('/authorized-firms', {method: 'POST', body: JSON.stringify(payload)});
      }
      setDetail(saved);
      setProfileModal(false);
      setMessage(editingProfile ? 'Firma kartı güncellendi.' : 'Firma kartı oluşturuldu.');
      await refresh(osgbId, filters);
    } catch (err) {
      setError(err.message || 'Firma kartı kaydedilemedi.');
    } finally {
      setBusy(false);
    }
  }

  async function saveDocument(event) {
    event.preventDefault();
    const periodError = validateDateRange(documentForm.start_date, documentForm.expiry_date, 'Belge');
    const reviewError = validateDateRange(documentForm.review_date, documentForm.renewal_date, 'Belge yenileme');
    if (periodError || reviewError) { setError(periodError || reviewError); return; }
    setBusy(true);
    setError('');
    try {
      const saved = await api(`/authorized-firms/${detail.id}/documents`, {
        method: 'POST', body: JSON.stringify(normalizeProfilePayload(documentForm)),
      });
      setDetail(saved);
      setDocumentModal(false);
      setDocumentForm({...EMPTY_DOCUMENT});
      setMessage('Belge geçerlilik kaydı eklendi.');
      await refresh(osgbId, filters);
    } catch (err) {
      setError(err.message || 'Belge kaydedilemedi.');
    } finally {
      setBusy(false);
    }
  }

  function editProfessional(item) {
    setProfessionalModal(item);
    setProfessionalForm({
      certificate_issue_date: item.certificate_issue_date || '',
      certificate_expiry_date: item.certificate_expiry_date || '',
      document_review_date: item.document_review_date || '',
      document_renewal_date: item.document_renewal_date || '',
      required_documents_status: item.required_documents_status || 'review_required',
      required_documents_note: item.required_documents_note || '',
    });
  }

  async function saveProfessional(event) {
    event.preventDefault();
    const periodError = validateDateRange(professionalForm.certificate_issue_date, professionalForm.certificate_expiry_date, 'Profesyonel belgesi');
    if (periodError) { setError(periodError); return; }
    setBusy(true);
    setError('');
    try {
      await api(`/authorized-firms/${detail.id}/professionals/${professionalModal.professional_id}/compliance`, {
        method: 'PUT', body: JSON.stringify(normalizeProfilePayload(professionalForm)),
      });
      const updated = await api(`/authorized-firms/${detail.id}`);
      setDetail(updated);
      setProfessionalModal(null);
      setMessage('Profesyonel belge uygunluğu güncellendi.');
      await refresh(osgbId, filters);
    } catch (err) {
      setError(err.message || 'Profesyonel uygunluğu kaydedilemedi.');
    } finally {
      setBusy(false);
    }
  }

  async function saveOnboarding() {
    if (!detail) return;
    const completed = detail.onboarding?.completed_steps || [];
    const status = completed.length === 11 ? 'completed' : 'in_progress';
    const current = completed.length === 11 ? 11 : Math.min(11, Math.max(1, ...completed, 0) + 1);
    setBusy(true);
    try {
      const updated = await api(`/authorized-firms/${detail.id}/onboarding`, {
        method: 'PATCH',
        body: JSON.stringify({current_step: current, completed_steps: completed, status}),
      });
      setDetail(updated);
      setMessage('Onboarding ilerlemesi kaydedildi.');
    } catch (err) {
      setError(err.message || 'Onboarding kaydedilemedi.');
    } finally {
      setBusy(false);
    }
  }

  function toggleStep(step) {
    setDetail((current) => ({
      ...current,
      onboarding: {
        ...current.onboarding,
        completed_steps: toggleCompletedStep(current.onboarding?.completed_steps, step),
      },
    }));
  }

  async function snapshot() {
    setBusy(true);
    try {
      await api(`/authorized-firms/${detail.id}/score-snapshots`, {method: 'POST'});
      setDetail(await api(`/authorized-firms/${detail.id}`));
      setMessage('Skor anlık görüntüsü geçmişe kaydedildi.');
    } catch (err) {
      setError(err.message || 'Skor kaydedilemedi.');
    } finally {
      setBusy(false);
    }
  }

  async function exportFile(extension) {
    try {
      await downloadFile(
        `/authorized-firms/${detail.id}/export.${extension}`,
        `yetkili-firma-${detail.id}.${extension}`,
      );
    } catch (err) {
      setError(err.message || 'Dosya indirilemedi.');
    }
  }

  async function openInspectionDay() {
    setBusy(true);
    try {
      setInspectionDay(await api(`/authorized-firms/${detail.id}/inspection-day`));
    } catch (err) {
      setError(err.message || 'Denetim Günü görünümü açılamadı.');
    } finally {
      setBusy(false);
    }
  }

  const score = detail?.compliance_score || {};
  const completedSteps = detail?.onboarding?.completed_steps || [];

  return (
    <div className="af-page">
      <div className="page-title af-page-title">
        <div>
          <span className="af-eyebrow">OSGB operasyon merkezi</span>
          <h3>Yetkili Firma Yönetimi</h3>
          <p>Firma kartı, belge tarihleri, profesyonel uygunluğu, şeffaf skor ve denetim hazırlığı.</p>
        </div>
        <div className="actions">
          <button type="button" className="secondary" disabled={busy || !osgbId} onClick={() => downloadFile(`/authorized-firms/status-report.xlsx?osgb_id=${encodeURIComponent(osgbId)}`, `yetkili-firma-durum-${osgbId}.xlsx`).catch((err) => setError(err.message))}>
            <Download size={16} /> Durum raporu
          </button>
          <button type="button" disabled={busy || !osgbId} onClick={startCreate}><Plus size={17} /> Firma kartı ekle</button>
        </div>
      </div>

      {error && <div className="af-banner af-banner-error"><AlertTriangle size={17} />{error}<button type="button" onClick={() => setError('')} aria-label="Kapat">×</button></div>}
      {message && <div className="af-banner af-banner-good"><CheckCircle2 size={17} />{message}<button type="button" onClick={() => setMessage('')} aria-label="Kapat">×</button></div>}

      <section className="panel af-filter-panel">
        <form onSubmit={(event) => { event.preventDefault(); void refresh(osgbId, filters); }}>
          {!lockedOsgb && (
            <Field label="OSGB">
              <select value={osgbId} onChange={(event) => { setOsbgAndRefresh(event.target.value); }}>
                <option value="">Seçiniz</option>
                {orgs.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </Field>
          )}
          <Field label="Arama"><input value={filters.q} onChange={(event) => setFilters({...filters, q: event.target.value})} placeholder="Firma veya yetki no" /></Field>
          <Field label="İl"><input value={filters.province} onChange={(event) => setFilters({...filters, province: event.target.value})} /></Field>
          <Field label="İlçe"><input value={filters.district} onChange={(event) => setFilters({...filters, district: event.target.value})} /></Field>
          <Field label="Firma durumu">
            <select value={filters.active} onChange={(event) => setFilters({...filters, active: event.target.value})}>
              <option value="">Tümü</option><option value="true">Aktif</option><option value="false">Pasif</option>
            </select>
          </Field>
          <Field label="Belge durumu">
            <select value={filters.document_status} onChange={(event) => setFilters({...filters, document_status: event.target.value})}>
              <option value="">Tümü</option><option value="valid">Geçerli</option><option value="expiring">Süresi yaklaşıyor</option><option value="expired">Süresi dolmuş</option><option value="missing">Eksik</option>
            </select>
          </Field>
          <Field label="Profesyonel durumu">
            <select value={filters.professional_status} onChange={(event) => setFilters({...filters, professional_status: event.target.value})}>
              <option value="">Tümü</option>{Object.entries(PROFESSIONAL_STATUS_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </select>
          </Field>
          <Field label="Hazırlık">
            <select value={filters.readiness} onChange={(event) => setFilters({...filters, readiness: event.target.value})}>
              <option value="">Tümü</option>{Object.entries(READINESS_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </select>
          </Field>
          <button type="submit" disabled={busy}><Search size={16} /> Filtrele</button>
          <button type="button" className="secondary" onClick={() => { const clean = {q: '', province: '', district: '', active: '', hazard_class: '', document_status: '', professional_status: '', readiness: '', expiry_to: ''}; setFilters(clean); void refresh(osgbId, clean); }}>Temizle</button>
        </form>
      </section>

      {dashboard && (
        <div className="cards osgb-cards af-summary-cards">
          <Metric label="Toplam firma" value={dashboard.total_firms} />
          <Metric label="Aktif firma" value={dashboard.active_firms} tone="good" />
          <Metric label="30 gün" value={dashboard.expiring_30} tone={dashboard.expiring_30 ? 'warn' : 'good'} hint="Yetki bitişi" />
          <Metric label="60 gün" value={dashboard.expiring_60} tone={dashboard.expiring_60 ? 'warn' : 'good'} hint="Yetki bitişi" />
          <Metric label="90 gün" value={dashboard.expiring_90} tone="info" hint="Yetki bitişi" />
          <Metric label="Süresi dolan" value={dashboard.expired_authorizations} tone={dashboard.expired_authorizations ? 'danger' : 'good'} />
          <Metric label="Kritik" value={dashboard.critical_firms} tone={dashboard.critical_firms ? 'danger' : 'good'} />
          <Metric label="Ortalama" value={`${dashboard.average_score}/100`} />
        </div>
      )}

      <section className="panel">
        <div className="af-section-head"><div><h3><Building2 size={18} /> Firma kayıtları</h3><p>{rows.length} kayıt gösteriliyor.</p></div><button type="button" className="mini secondary" disabled={busy} onClick={() => void refresh()}><RefreshCw size={15} /> Yenile</button></div>
        <DetailTable
          rows={rows}
          headers={[
            {key: 'firm_name', label: 'Firma', render: (row) => <><strong>{row.firm_name}</strong><small className="af-cell-sub">{row.company_name}</small></>},
            {key: 'location', label: 'Konum', render: (row) => `${row.province || '—'} / ${row.district || '—'}`},
            {key: 'authorization_expiry_date', label: 'Yetki bitiş', render: (row) => <><div>{dateText(row.authorization_expiry_date)}</div><ValidityPill validity={row.authorization_validity} /></>},
            {key: 'document_status', label: 'Belge', render: (row) => <TonePill tone={row.document_status === 'valid' ? 'good' : row.document_status === 'expired' ? 'danger' : 'warn'}>{row.document_status}</TonePill>},
            {key: 'professional_count', label: 'Profesyonel'},
            {key: 'compliance_score', label: 'Uygunluk', render: (row) => <ScoreGauge value={row.compliance_score} tone={readinessTone(row.readiness_status)} label="" />},
            {key: 'action', label: 'İşlem', render: (row) => <button type="button" className="mini" onClick={() => void openDetail(row.id)}><Eye size={14} /> Aç</button>},
          ]}
          empty="Filtreye uyan yetkili firma kaydı yok."
        />
      </section>

      {detail && (
        <div className="af-detail">
          <section className="panel af-detail-hero">
            <div>
              <span className="af-eyebrow">Firma kartı #{detail.id}</span>
              <h2>{detail.firm_name}</h2>
              <p>{detail.company_name} · {detail.province || '—'} / {detail.district || '—'}</p>
              <div className="af-notice"><ShieldCheck size={16} />{detail.record_notice}</div>
            </div>
            <div className="af-detail-actions">
              <button type="button" className="secondary" onClick={startEdit}>Düzenle</button>
              <button type="button" className="secondary" onClick={() => void exportFile('pdf')}><Download size={15} /> PDF</button>
              <button type="button" className="secondary" onClick={() => void exportFile('xlsx')}><Download size={15} /> Excel</button>
              <button type="button" className="secondary" onClick={() => downloadFile(`/authorized-firms/${detail.id}/inspection-package.zip`, `denetim-hazirlik-${detail.id}.zip`).catch((err) => setError(err.message))}><FileArchive size={15} /> Denetim paketi</button>
              <button type="button" onClick={() => void openInspectionDay()}><Printer size={15} /> Denetim Günü</button>
            </div>
          </section>

          <div className="af-two-column">
            <section className="panel">
              <div className="af-section-head"><div><h3>Şeffaf uygunluk skoru</h3><p>{score.calculation}</p></div><button type="button" className="mini secondary" onClick={() => void snapshot()}><Save size={14} /> Geçmişe kaydet</button></div>
              <div className="af-score-duo">
                <ScoreGauge value={score.overall_score} tone={readinessTone(score.status)} label="Uygunluk" />
                <ScoreGauge value={score.quality_score} tone={score.quality_score >= 80 ? 'good' : score.quality_score >= 60 ? 'warn' : 'danger'} label="Kalite" />
              </div>
              <TonePill tone={readinessTone(score.status)}>{score.status_label}</TonePill>
              <p className="af-method-note">Kara kutu: <strong>{score.black_box ? 'Evet' : 'Hayır'}</strong>. Her kategori puanı ve ağırlığı aşağıda görünür.</p>
            </section>
            <section className="panel">
              <h3><CalendarDays size={18} /> Yetki ve iletişim</h3>
              <dl className="af-definition-grid">
                <div><dt>Yetki numarası</dt><dd>{detail.authorization_number || '—'}</dd></div>
                <div><dt>Yetki kapsamı</dt><dd>{detail.authorization_scope || '—'}</dd></div>
                <div><dt>Başlangıç</dt><dd>{dateText(detail.authorization_start_date)}</dd></div>
                <div><dt>Bitiş</dt><dd>{dateText(detail.authorization_expiry_date)}</dd></div>
                <div><dt>Temsilci</dt><dd>{detail.authorized_representative || '—'}</dd></div>
                <div><dt>İletişim</dt><dd>{detail.contact_email || detail.contact_phone || '—'}</dd></div>
                <div><dt>Çalışan</dt><dd>{detail.employee_count}</dd></div>
                <div><dt>Tehlike sınıfı</dt><dd>{detail.hazard_class || '—'}</dd></div>
              </dl>
            </section>
          </div>

          {(detail.alerts || []).length > 0 && (
            <section className="panel af-alert-panel">
              <h3><AlertTriangle size={18} /> Geçerlilik uyarıları</h3>
              <div className="af-alert-list">
                {detail.alerts.map((item) => (
                  <article key={item.code} className={`af-alert af-${item.severity === 'critical' ? 'danger' : item.severity === 'warning' ? 'warn' : 'info'}`}>
                    <div><strong>{item.title}</strong><span>{item.suggested_action}</span></div>
                    <TonePill tone={item.severity === 'critical' ? 'danger' : item.severity === 'warning' ? 'warn' : 'info'}>{item.days_left != null ? `${item.days_left} gün` : item.status}</TonePill>
                  </article>
                ))}
              </div>
            </section>
          )}

          <section className="panel">
            <h3><ClipboardCheck size={18} /> Kategori puanları ve aksiyonlar</h3>
            <DetailTable
              rows={score.categories || []}
              headers={[
                {key: 'label', label: 'Kategori'},
                {key: 'score', label: 'Puan', render: (row) => <strong className={row.score < 50 ? 'af-text-danger' : ''}>{row.score}/100</strong>},
                {key: 'weight', label: 'Ağırlık'},
                {key: 'detail', label: 'Hesap sonucu'},
                {key: 'recommended_action', label: 'Önerilen aksiyon'},
              ]}
            />
          </section>

          <div className="af-two-column">
            <section className="panel">
              <div className="af-section-head"><div><h3><FileText size={18} /> Firma belgeleri</h3><p>Zorunlu belgeler ve 30/60/90 günlük geçerlilik.</p></div><button type="button" className="mini" onClick={() => setDocumentModal(true)}><Plus size={14} /> Belge ekle</button></div>
              <DetailTable
                rows={detail.documents || []}
                headers={[
                  {key: 'title', label: 'Belge'},
                  {key: 'mandatory', label: 'Zorunlu', render: (row) => row.mandatory ? 'Evet' : 'Hayır'},
                  {key: 'expiry_date', label: 'Bitiş', render: (row) => dateText(row.expiry_date)},
                  {key: 'validity', label: 'Durum', render: (row) => <ValidityPill validity={row.validity} />},
                ]}
                empty="Belge geçerlilik kaydı yok."
              />
            </section>
            <section className="panel">
              <h3><Stethoscope size={18} /> Profesyonel belge uygunluğu</h3>
              <DetailTable
                rows={detail.professionals || []}
                headers={[
                  {key: 'full_name', label: 'Profesyonel'},
                  {key: 'certificate_number', label: 'Belge no'},
                  {key: 'certificate_expiry_date', label: 'Bitiş', render: (row) => dateText(row.certificate_expiry_date)},
                  {key: 'status', label: 'Durum', render: (row) => <TonePill tone={row.status === 'compliant' ? 'good' : row.status === 'expired_documents' ? 'danger' : 'warn'}>{row.status_label}</TonePill>},
                  {key: 'action', label: 'İşlem', render: (row) => <button type="button" className="mini secondary" onClick={() => editProfessional(row)}>Belge kontrolü</button>},
                ]}
                empty="Bu işyerine bağlı profesyonel bulunmuyor."
              />
            </section>
          </div>

          <section className="panel">
            <div className="af-section-head"><div><h3>11 adımlı onboarding</h3><p>Otomatik kontrol sonucu ve yönetici ilerlemesi birlikte görünür.</p></div><button type="button" onClick={() => void saveOnboarding()} disabled={busy}><Save size={15} /> İlerlemeyi kaydet</button></div>
            <div className="af-onboarding-grid">
              {(detail.onboarding?.steps || []).map((item) => {
                const checked = completedSteps.includes(item.step);
                return (
                  <label key={item.step} className={`af-onboarding-step${checked ? ' is-checked' : ''}`}>
                    <input type="checkbox" checked={checked} onChange={() => toggleStep(item.step)} />
                    <span className="af-step-number">{item.step}</span>
                    <span><strong>{item.title}</strong><small>{item.completed ? 'Otomatik kontrol: tamam' : item.recommended_action}</small></span>
                    {item.completed ? <CheckCircle2 size={18} className="af-text-good" /> : <XCircle size={18} className="af-text-warn" />}
                  </label>
                );
              })}
            </div>
          </section>

          <div className="af-two-column">
            <section className="panel">
              <h3>Otomatik eksik / görev listesi</h3>
              {(detail.automatic_task_checklist || []).length ? (
                <ul className="af-task-list">
                  {detail.automatic_task_checklist.map((item) => <li key={item.code}><TonePill tone={item.priority === 'critical' ? 'danger' : 'warn'}>{item.priority === 'critical' ? 'Kritik' : 'Görev'}</TonePill><span><strong>{item.title}</strong><small>{item.recommended_action}</small></span></li>)}
                </ul>
              ) : <p className="empty">Açık otomatik görev yok.</p>}
            </section>
            <section className="panel">
              <h3>OSGB içi kalite karşılaştırması</h3>
              <p className="af-method-note">{dashboard?.quality_comparison?.method}</p>
              <DetailTable
                rows={(dashboard?.quality_comparison?.ranking || []).slice(0, 10)}
                headers={[
                  {key: 'rank', label: 'Sıra'},
                  {key: 'firm_name', label: 'Firma'},
                  {key: 'quality_score', label: 'Kalite'},
                  {key: 'compliance_score', label: 'Uygunluk'},
                ]}
                empty="Karşılaştırma için kayıt yok."
              />
            </section>
          </div>

          <div className="af-two-column">
            <section className="panel">
              <h3>Skor geçmişi</h3>
              <DetailTable rows={detail.score_history || []} headers={[
                {key: 'created_at', label: 'Tarih', render: (row) => String(row.created_at || '').slice(0, 16).replace('T', ' ')},
                {key: 'overall_score', label: 'Uygunluk'},
                {key: 'quality_score', label: 'Kalite'},
                {key: 'status', label: 'Durum'},
              ]} empty="Henüz skor geçmişi yok." />
            </section>
            <section className="panel">
              <h3>Bağlı iş akışları</h3>
              <div className="af-module-links">
                <button type="button" className="secondary" onClick={() => onNavigate?.('assignments')}>Görevlendirmeler <ArrowRight size={15} /></button>
                <button type="button" className="secondary" onClick={() => onNavigate?.('contracts')}>Sözleşmeler <ArrowRight size={15} /></button>
                <button type="button" className="secondary" onClick={() => onNavigate?.('notifications')}>Bildirimler <ArrowRight size={15} /></button>
                <button type="button" className="secondary" onClick={() => onNavigate?.('csgb_audit')}>Denetim belgesi <ArrowRight size={15} /></button>
              </div>
            </section>
          </div>
        </div>
      )}

      {profileModal && (
        <AppModal title={editingProfile ? 'Yetkili firma kartını düzenle' : 'Yeni yetkili firma kartı'} close={() => setProfileModal(false)} wide>
          <form className="form-grid af-form" onSubmit={saveProfile}>
            {!editingProfile && <Field label="Bağlı işyeri"><select required value={profileForm.company_id} onChange={(event) => setProfileForm({...profileForm, company_id: event.target.value})}><option value="">Seçiniz</option>{availableCompanies.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>}
            <Field label="Firma adı"><input required value={profileForm.firm_name} onChange={(event) => setProfileForm({...profileForm, firm_name: event.target.value})} /></Field>
            <Field label="Firma türü"><input value={profileForm.firm_type} onChange={(event) => setProfileForm({...profileForm, firm_type: event.target.value})} /></Field>
            <Field label="İl"><input value={profileForm.province} onChange={(event) => setProfileForm({...profileForm, province: event.target.value})} /></Field>
            <Field label="İlçe"><input value={profileForm.district} onChange={(event) => setProfileForm({...profileForm, district: event.target.value})} /></Field>
            <Field label="Adres" span><textarea rows={2} value={profileForm.address} onChange={(event) => setProfileForm({...profileForm, address: event.target.value})} /></Field>
            <Field label="Yetkili temsilci"><input value={profileForm.authorized_representative} onChange={(event) => setProfileForm({...profileForm, authorized_representative: event.target.value})} /></Field>
            <Field label="E-posta"><input type="email" value={profileForm.contact_email} onChange={(event) => setProfileForm({...profileForm, contact_email: event.target.value})} /></Field>
            <Field label="Telefon"><input value={profileForm.contact_phone} onChange={(event) => setProfileForm({...profileForm, contact_phone: event.target.value})} /></Field>
            <Field label="Çalışan sayısı"><input type="number" min="0" value={profileForm.employee_count_declared} onChange={(event) => setProfileForm({...profileForm, employee_count_declared: event.target.value})} /></Field>
            <Field label="Tehlike sınıfı"><select value={profileForm.hazard_class} onChange={(event) => setProfileForm({...profileForm, hazard_class: event.target.value})}><option value="">Seçiniz</option><option>Az Tehlikeli</option><option>Tehlikeli</option><option>Çok Tehlikeli</option></select></Field>
            <Field label="Yetki numarası"><input value={profileForm.authorization_number} onChange={(event) => setProfileForm({...profileForm, authorization_number: event.target.value})} /></Field>
            <Field label="Düzenlenme tarihi"><input type="date" value={profileForm.authorization_issue_date} onChange={(event) => setProfileForm({...profileForm, authorization_issue_date: event.target.value})} /></Field>
            <Field label="Yetki başlangıç"><input type="date" value={profileForm.authorization_start_date} onChange={(event) => setProfileForm({...profileForm, authorization_start_date: event.target.value})} /></Field>
            <Field label="Yetki bitiş"><input type="date" value={profileForm.authorization_expiry_date} onChange={(event) => setProfileForm({...profileForm, authorization_expiry_date: event.target.value})} /></Field>
            <Field label="Son inceleme tarihi"><input type="date" value={profileForm.last_review_date} onChange={(event) => setProfileForm({...profileForm, last_review_date: event.target.value})} /></Field>
            <Field label="Kayıt inceleme durumu"><select value={profileForm.review_state} onChange={(event) => setProfileForm({...profileForm, review_state: event.target.value})}><option value="internal_record">İç kayıt</option><option value="manually_reviewed">Yönetici incelemiş</option></select></Field>
            <Field label="Yetki kapsamı" span><textarea required rows={3} value={profileForm.authorization_scope} onChange={(event) => setProfileForm({...profileForm, authorization_scope: event.target.value})} /></Field>
            <Field label="Notlar" span><textarea rows={3} value={profileForm.notes} onChange={(event) => setProfileForm({...profileForm, notes: event.target.value})} /></Field>
            <div className="form-actions"><button type="button" className="secondary" onClick={() => setProfileModal(false)}>Vazgeç</button><button type="submit" disabled={busy}><Save size={16} /> Kaydet</button></div>
          </form>
        </AppModal>
      )}

      {documentModal && (
        <AppModal title="Belge geçerlilik kaydı ekle" close={() => setDocumentModal(false)}>
          <form className="form-grid af-form" onSubmit={saveDocument}>
            <Field label="Belge türü"><input required value={documentForm.document_type} onChange={(event) => setDocumentForm({...documentForm, document_type: event.target.value})} /></Field>
            <Field label="Belge adı"><input required value={documentForm.title} onChange={(event) => setDocumentForm({...documentForm, title: event.target.value})} /></Field>
            <Field label="Başlangıç"><input type="date" value={documentForm.start_date} onChange={(event) => setDocumentForm({...documentForm, start_date: event.target.value})} /></Field>
            <Field label="Bitiş"><input type="date" value={documentForm.expiry_date} onChange={(event) => setDocumentForm({...documentForm, expiry_date: event.target.value})} /></Field>
            <Field label="Gözden geçirme"><input type="date" value={documentForm.review_date} onChange={(event) => setDocumentForm({...documentForm, review_date: event.target.value})} /></Field>
            <Field label="Yenileme"><input type="date" value={documentForm.renewal_date} onChange={(event) => setDocumentForm({...documentForm, renewal_date: event.target.value})} /></Field>
            <Field label="Zorunlu"><select value={String(documentForm.mandatory)} onChange={(event) => setDocumentForm({...documentForm, mandatory: event.target.value === 'true'})}><option value="true">Evet</option><option value="false">Hayır</option></select></Field>
            <Field label="Not" span><textarea rows={3} value={documentForm.notes} onChange={(event) => setDocumentForm({...documentForm, notes: event.target.value})} /></Field>
            <div className="form-actions"><button type="button" className="secondary" onClick={() => setDocumentModal(false)}>Vazgeç</button><button type="submit" disabled={busy}>Belgeyi kaydet</button></div>
          </form>
        </AppModal>
      )}

      {professionalModal && (
        <AppModal title={`${professionalModal.full_name} · belge uygunluğu`} close={() => setProfessionalModal(null)}>
          <form className="form-grid af-form" onSubmit={saveProfessional}>
            <Field label="Belge düzenlenme"><input type="date" value={professionalForm.certificate_issue_date} onChange={(event) => setProfessionalForm({...professionalForm, certificate_issue_date: event.target.value})} /></Field>
            <Field label="Belge bitiş"><input type="date" value={professionalForm.certificate_expiry_date} onChange={(event) => setProfessionalForm({...professionalForm, certificate_expiry_date: event.target.value})} /></Field>
            <Field label="Doküman inceleme"><input type="date" value={professionalForm.document_review_date} onChange={(event) => setProfessionalForm({...professionalForm, document_review_date: event.target.value})} /></Field>
            <Field label="Doküman yenileme"><input type="date" value={professionalForm.document_renewal_date} onChange={(event) => setProfessionalForm({...professionalForm, document_renewal_date: event.target.value})} /></Field>
            <Field label="Zorunlu belge durumu"><select value={professionalForm.required_documents_status} onChange={(event) => setProfessionalForm({...professionalForm, required_documents_status: event.target.value})}><option value="complete">Tam</option><option value="incomplete">Eksik</option><option value="review_required">İnceleme gerekli</option></select></Field>
            <Field label="Belge notu" span><textarea rows={3} value={professionalForm.required_documents_note} onChange={(event) => setProfessionalForm({...professionalForm, required_documents_note: event.target.value})} /></Field>
            <div className="form-actions"><button type="button" className="secondary" onClick={() => setProfessionalModal(null)}>Vazgeç</button><button type="submit" disabled={busy}>Uygunluğu kaydet</button></div>
          </form>
        </AppModal>
      )}

      {inspectionDay && (
        <AppModal title="Denetim Günü görünümü" close={() => setInspectionDay(null)} wide className="af-inspection-overlay">
          <div className="af-inspection-day">
            <div className="af-inspection-toolbar"><button type="button" onClick={() => window.print()}><Printer size={16} /> Yazdır</button><button type="button" className="secondary" onClick={() => setInspectionDay(null)}>Kapat</button></div>
            <header><span>DENETİM GÜNÜ</span><h2>{inspectionDay.profile?.firm_name}</h2><p>{inspectionDay.profile?.record_notice}</p></header>
            <div className="cards osgb-cards"><Metric label="Uygunluk" value={`${inspectionDay.compliance_score?.overall_score || 0}/100`} /><Metric label="Kalite" value={`${inspectionDay.compliance_score?.quality_score || 0}/100`} /><Metric label="Kritik engel" value={inspectionDay.compliance_score?.critical_blockers?.length || 0} tone="danger" /><Metric label="Uyarı" value={inspectionDay.alerts?.length || 0} tone="warn" /></div>
            <h3>Kritik engeller</h3>
            <ul>{(inspectionDay.compliance_score?.critical_blockers || []).map((item) => <li key={item.code}><strong>{item.title}</strong> — {item.recommended_action}</li>)}</ul>
            <h3>Otomatik kontrol listesi</h3>
            <ul>{(inspectionDay.automatic_task_checklist || []).map((item) => <li key={item.code}><strong>{item.title}</strong> — {item.recommended_action}</li>)}</ul>
            <footer>Sağlık verileri yalnız anonim toplamlarla değerlendirilir; kişi ve klinik ayrıntı gösterilmez.</footer>
          </div>
        </AppModal>
      )}
    </div>
  );

  function setOsbgAndRefresh(value) {
    setOsgbId(value);
    setDetail(null);
    if (value) void refresh(value, filters);
  }
}

export default AuthorizedFirmsPage;
