import React, {useEffect, useMemo, useRef, useState} from 'react';
import {Award, CheckCircle2, ClipboardList, Download, FileSpreadsheet, Search, ShieldCheck, Upload, Users} from 'lucide-react';
import {api, downloadFile, uploadFile} from './api';
import './training_pro.css';

const HAZARD_HOURS = {'Az Tehlikeli': 8, Tehlikeli: 12, 'Çok Tehlikeli': 16};
const MAX_HOURS_PER_DAY = 8;
const HAZARD_HINT = {
  'Az Tehlikeli': '8 ders saati · en az 1 gün · 3 yılda bir yenilenir',
  Tehlikeli: '12 ders saati · en az 2 güne yayılır · 2 yılda bir yenilenir',
  'Çok Tehlikeli': '16 ders saati · en az 2 güne yayılır (1 günde 16 saat olmaz) · her yıl yenilenir',
};
const STATUS = {planned: 'Planlandı', completed: 'Tamamlandı', cancelled: 'İptal'};
const TABS = [
  {id: 'temel', label: 'Temel İSG Eğitimi'},
  {id: 'ozel', label: 'Özel Eğitimler'},
  {id: 'yenileme', label: 'Yenileme Takibi'},
  {id: 'kayitlar', label: 'Kayıtlar'},
];

const STATUS_STYLES = {
  never: {bg: '#fee2e2', fg: '#991b1b', label: 'Eğitim kaydı yok'},
  expired: {bg: '#ffedd5', fg: '#9a3412', label: 'Süresi doldu'},
  due_soon: {bg: '#fef3c7', fg: '#92400e', label: 'Yaklaşıyor'},
  ok: {bg: '#dcfce7', fg: '#166534', label: 'Geçerli'},
};

function minTrainingDays(hours) {
  return Math.max(1, Math.ceil((hours || 8) / MAX_HOURS_PER_DAY));
}

function formatTrainingDates(row) {
  if (!row?.start_date) return '—';
  if (!row.end_date || row.end_date === row.start_date) return row.start_date;
  return `${row.start_date} – ${row.end_date}`;
}

function calendarDaysInclusive(start, end) {
  if (!start || !end) return 0;
  const a = new Date(`${start}T00:00:00`);
  const b = new Date(`${end}T00:00:00`);
  return Math.floor((b - a) / 86400000) + 1;
}

function apiBaseUrl() {
  const host =
    typeof window !== 'undefined' &&
    (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');
  return (
    import.meta.env.VITE_API_URL ||
    (host
      ? `${window.location.protocol}//${window.location.hostname}:8000/api/v1`
      : 'https://isg-suite-api-1u9t.onrender.com/api/v1')
  );
}

let _sectorsMem = null;
let _sectorsMemAt = 0;
const SECTORS_TTL_MS = 60 * 60 * 1000;
const SECTORS_CACHE_KEY = 'isg_sectors_v4_nace2026_risk';
const SECTORS_MIN_COUNT = 500; // eski 177 listesini reddet

export async function loadSectorsCatalog() {
  if (_sectorsMem && _sectorsMem.length >= SECTORS_MIN_COUNT && Date.now() - _sectorsMemAt < SECTORS_TTL_MS) {
    return _sectorsMem;
  }
  try {
    sessionStorage.removeItem('isg_sectors_v1');
    sessionStorage.removeItem('isg_sectors_v2');
    const raw = sessionStorage.getItem(SECTORS_CACHE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (
        parsed?.at &&
        Date.now() - parsed.at < SECTORS_TTL_MS &&
        Array.isArray(parsed.data) &&
        parsed.data.length >= SECTORS_MIN_COUNT
      ) {
        _sectorsMem = parsed.data;
        _sectorsMemAt = parsed.at;
        return parsed.data;
      }
    }
  } catch (_) { /* ignore */ }

  const base = apiBaseUrl();
  let data = [];

  // 1) API — önbelleği kırma (eski 177 response kalmasın)
  try {
    const r = await fetch(`${base}/trainings/sectors?v=nace2026-risk-v4`, {cache: 'no-store'});
    if (r.ok) {
      const json = await r.json();
      if (Array.isArray(json) && json.length >= SECTORS_MIN_COUNT) data = json;
    }
  } catch (_) { /* ignore */ }

  // 2) Auth’lu meta
  if (data.length < SECTORS_MIN_COUNT) {
    try {
      const meta = await api('/trainings/meta');
      if (meta?.sectors?.length >= SECTORS_MIN_COUNT) data = meta.sectors;
    } catch (_) { /* ignore */ }
  }

  // 3) Statik paket
  if (data.length < SECTORS_MIN_COUNT) {
    try {
      const local = await fetch('/training-sectors.json?v=nace2026-risk-v4', {cache: 'no-store'}).then((r) => r.json());
      if (Array.isArray(local) && local.length >= SECTORS_MIN_COUNT) data = local;
      else if (Array.isArray(local?.sectors) && local.sectors.length >= SECTORS_MIN_COUNT) data = local.sectors;
    } catch (_) { /* ignore */ }
  }

  if (data.length >= SECTORS_MIN_COUNT) {
    _sectorsMem = data;
    _sectorsMemAt = Date.now();
    try {
      sessionStorage.setItem(SECTORS_CACHE_KEY, JSON.stringify({at: _sectorsMemAt, data}));
    } catch (_) { /* ignore — quota */ }
  }
  return data;
}

function sectorLabel(sectors, code) {
  const s = sectors.find((x) => x.code === code || x.name === code || x.label === code);
  return s ? (s.label || s.name) : code || '—';
}

function emptyForm(user) {
  return {
    company_id: user.company_id || '',
    title: 'Temel İş Sağlığı ve Güvenliği Eğitimi',
    training_type: 'İlk Defa',
    delivery_method: 'Yüz yüze',
    location: 'İşyeri Eğitim Salonu',
    start_date: '',
    end_date: '',
    hazard_class: 'Çok Tehlikeli',
    sector: 'genel_uretim',
    instructor_name: '',
    instructor_qualification: '',
    workplace_physician: '',
    employer_representative: '',
    stamp_text:
      '6331 sayılı İş Sağlığı ve Güvenliği Kanunu ve Çalışanların İş Sağlığı ve Güvenliği Eğitimlerinin Usul ve Esasları Hakkında Yönetmelik kapsamında düzenlenmiştir.',
    evaluation_method: 'Sınav',
    passing_score: '',
    attendance_verified: true,
    success_verified: true,
    notes: '',
    participant_ids: [],
    special_duration_hours: null,
    special_duration_hint: '',
  };
}

function participantKey(payload) {
  return [...(payload?.participant_ids || [])].map(Number).sort((a, b) => a - b).join(',');
}

function sameExceptParticipants(a, b) {
  const strip = (p) => JSON.stringify({...p, participant_ids: undefined});
  return strip(a) === strip(b);
}

function EducationOutputPanel({
  savedTrainingId,
  participantCount,
  selectionDirty,
  dlBusy,
  onDownloadCertificates,
  onDownloadAttendance,
  onDownloadExam,
  onSaveAndPrepare,
  canEdit,
  busy,
}) {
  const ready = !!savedTrainingId;
  return (
    <section
      className={'education-output-panel' + (ready ? ' is-ready' : '')}
      aria-labelledby="educationOutputTitle"
    >
      <div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: 12, marginBottom: 14}}>
        <div>
          <div className="section-title" style={{marginBottom: 6}}>Eğitim Belgesi ve PDF Raporlama</div>
          <h3 id="educationOutputTitle" style={{margin: '0 0 6px', fontSize: 18}}>
            Belge ve katılım listesi çıktıları
          </h3>
          {ready ? (
            <p className="tp-help" style={{margin: 0}}>
              Kayıt <strong>#{savedTrainingId}</strong> · {participantCount || 0} katılımcı üzerinden PDF çıktıları hazır.
              {selectionDirty && (
                <strong style={{display: 'block', color: '#b45309'}}>
                  Personel seçimi değişti. PDF’ler kayıttaki listeyi bastığı için önce
                  «Eğitimi Kaydet ve PDF Hazırla»ya basın.
                </strong>
              )}
            </p>
          ) : (
            <p className="tp-help" style={{margin: 0}}>
              Önce Excel yükleyin veya ortak listeden personel seçip eğitimi kaydedin.
            </p>
          )}
        </div>
        <span
          style={{
            alignSelf: 'flex-start',
            padding: '8px 14px',
            borderRadius: 999,
            fontWeight: 800,
            fontSize: 12,
            background: ready ? '#d1fae5' : '#e2e8f0',
            color: ready ? '#066' : '#64748b',
          }}
        >
          {ready ? '✓ Çıktıya hazır' : 'Personel aktarımı bekleniyor'}
        </span>
      </div>

      <div className="education-output-row">
        {ready ? (
          <button
            type="button"
            className="education-output-button education-output-button--certificate"
            disabled={!!dlBusy}
            onClick={onDownloadCertificates}
          >
            <Award size={18} />
            {dlBusy === 'certs' ? 'İndiriliyor…' : 'Sertifika PDF (Katılım Belgeleri)'}
          </button>
        ) : (
          <div className="education-output-disabled" aria-disabled="true">
            Sertifika PDF (Katılım Belgeleri)
          </div>
        )}
        {ready ? (
          <button
            type="button"
            className="education-output-button education-output-button--exam"
            disabled={!!dlBusy}
            onClick={onDownloadExam}
          >
            <ShieldCheck size={18} />
            {dlBusy === 'exam' ? 'Hazırlanıyor…' : 'Sınav Oluştur (15 Soru)'}
          </button>
        ) : (
          <div className="education-output-disabled" aria-disabled="true">
            Sınav Oluştur (15 Soru)
          </div>
        )}
        {ready ? (
          <button
            type="button"
            className="education-output-button education-output-button--attendance"
            disabled={!!dlBusy}
            onClick={onDownloadAttendance}
          >
            <ClipboardList size={18} />
            {dlBusy === 'attendance' ? 'İndiriliyor…' : 'Katılım PDF (İmza Formu)'}
          </button>
        ) : (
          <div className="education-output-disabled" aria-disabled="true">
            Katılım PDF (İmza Formu)
          </div>
        )}
      </div>

      {canEdit && (
        <div style={{marginTop: 12}}>
          <button
            type="button"
            className="btn-premium"
            disabled={busy}
            onClick={onSaveAndPrepare}
          >
            {busy ? 'Kaydediliyor…' : 'Eğitimi Kaydet ve PDF Hazırla'}
          </button>
        </div>
      )}
    </section>
  );
}

export function TrainingPage({user}) {
  const canEdit = ['global_admin', 'company_admin', 'safety_specialist'].includes(user.role);
  const visibleTabs = TABS;
  const excelInputRef = useRef(null);
  const logoInputRef = useRef(null);
  const pendingLogoRef = useRef(null);
  const sectorPickerRef = useRef(null);

  const [tab, setTab] = useState('temel');
  const [companies, setCompanies] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [sectors, setSectors] = useState([]);
  const [specialProfiles, setSpecialProfiles] = useState([]);
  const [specialProfileCode, setSpecialProfileCode] = useState('');
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState('');
  const [form, setForm] = useState(() => emptyForm(user));
  const [err, setErr] = useState('');
  const [okMsg, setOkMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const [excelInfo, setExcelInfo] = useState('');
  const [excelPreview, setExcelPreview] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [savedTrainingId, setSavedTrainingId] = useState(null);
  // Kaydedilen anki payload: seçim değişince kaydı güncelleyip PDF'in eski listeyi
  // basmasını önler (PDF her zaman veritabanındaki katılımcıları kullanır).
  const [savedPayload, setSavedPayload] = useState(null);
  const [detail, setDetail] = useState(null);
  const [dlBusy, setDlBusy] = useState('');
  const [fileLabel, setFileLabel] = useState('.xlsx, .xlsm veya .csv dosyası seçin');
  // İşyerine görevlendirilmiş uzman/hekim — ad elle yazılmasın diye
  const [assignedTeam, setAssignedTeam] = useState(null);
  const autoFilledRef = useRef({});
  const [empQuery, setEmpQuery] = useState('');
  const [empDept, setEmpDept] = useState('');
  const [renewal, setRenewal] = useState(null);
  const [renewalFilter, setRenewalFilter] = useState('');
  const [renewalBusy, setRenewalBusy] = useState(false);
  const [renewalErr, setRenewalErr] = useState('');
  const [sectorQuery, setSectorQuery] = useState('');
  const [sectorPickerOpen, setSectorPickerOpen] = useState(false);

  const companyEmployees = useMemo(
    () =>
      employees.filter(
        (e) =>
          form.company_id &&
          String(e.company_id) === String(form.company_id) &&
          e.is_active !== false,
      ),
    [employees, form.company_id],
  );

  const departmentOptions = useMemo(() => {
    const set = new Set(
      companyEmployees.map((e) => (e.department || '').trim()).filter(Boolean),
    );
    return [...set].sort((a, b) => a.localeCompare(b, 'tr'));
  }, [companyEmployees]);

  const visibleEmployees = useMemo(() => {
    const needle = empQuery.trim().toLocaleLowerCase('tr');
    return companyEmployees.filter((e) => {
      if (empDept && (e.department || '').trim() !== empDept) return false;
      if (!needle) return true;
      const haystack = `${e.full_name || ''} ${e.job_title || ''} ${e.department || ''}`.toLocaleLowerCase('tr');
      return haystack.includes(needle);
    });
  }, [companyEmployees, empQuery, empDept]);

  const allEmployeesSelected = useMemo(() => {
    if (!companyEmployees.length) return false;
    const selected = new Set((form.participant_ids || []).map(Number));
    return companyEmployees.every((e) => selected.has(Number(e.id)));
  }, [companyEmployees, form.participant_ids]);

  // Kayıttaki katılımcılar ile ekrandaki seçim ayrıştıysa PDF eski listeyi basar.
  const selectionDirty = useMemo(
    () =>
      !!savedTrainingId &&
      !!savedPayload &&
      participantKey({participant_ids: form.participant_ids}) !== participantKey(savedPayload),
    [savedTrainingId, savedPayload, form.participant_ids],
  );

  const instructorOptions = useMemo(
    () => (Array.isArray(assignedTeam?.instructor_options) ? assignedTeam.instructor_options : []),
    [assignedTeam],
  );

  const instructorIsCustom = useMemo(
    () =>
      instructorOptions.length > 0 &&
      !instructorOptions.some((o) => o.value === form.instructor_name),
    [instructorOptions, form.instructor_name],
  );

  function pickInstructor(value) {
    if (value === '__custom__') {
      setForm((f) => ({...f, instructor_name: '', instructor_qualification: ''}));
      return;
    }
    const picked = instructorOptions.find((o) => o.value === value);
    setForm((f) => ({
      ...f,
      instructor_name: value,
      instructor_qualification: picked?.qualification || f.instructor_qualification,
    }));
  }

  const filteredSectors = useMemo(() => {
    const needle = sectorQuery.trim().toLocaleLowerCase('tr');
    const list = sectors.filter((item) => {
      if (!needle) return true;
      const searchable = `${item.nace || ''} ${item.name || ''} ${item.label || ''}`.toLocaleLowerCase('tr');
      return searchable.includes(needle);
    }).sort((a, b) =>
      String(a.label || a.name || '').localeCompare(String(b.label || b.name || ''), 'tr'),
    );
    return list.sort((a, b) => {
      const ah = a.hazard_class === form.hazard_class ? 0 : 1;
      const bh = b.hazard_class === form.hazard_class ? 0 : 1;
      if (ah !== bh) return ah - bh;
      return String(a.label || a.name || '').localeCompare(String(b.label || b.name || ''), 'tr');
    });
  }, [sectors, form.hazard_class, sectorQuery]);

  const visibleSectorResults = useMemo(() => filteredSectors.slice(0, 100), [filteredSectors]);

  const selectedSector = useMemo(
    () => sectors.find((s) => s.code === form.sector),
    [sectors, form.sector],
  );

  function pickSector(code) {
    const picked = sectors.find((item) => item.code === code);
    setForm((current) => ({
      ...current,
      sector: code,
      hazard_class: picked?.hazard_class || current.hazard_class,
    }));
    setSectorQuery('');
    setSectorPickerOpen(false);
  }

  useEffect(() => {
    const closePicker = (event) => {
      if (!sectorPickerRef.current?.contains(event.target)) setSectorPickerOpen(false);
    };
    document.addEventListener('pointerdown', closePicker);
    return () => document.removeEventListener('pointerdown', closePicker);
  }, []);

  const selectedProfile = useMemo(
    () => specialProfiles.find((p) => p.code === specialProfileCode),
    [specialProfiles, specialProfileCode],
  );

  const companyName = (id) => companies.find((c) => c.id === id)?.name || id;

  function defaultCompanyId(list = companies) {
    if (user.company_id) return String(user.company_id);
    if (list.length === 1) return String(list[0].id);
    return '';
  }

  const TEAM_FIELDS = ['instructor_name', 'instructor_qualification', 'workplace_physician', 'employer_representative'];

  /** Görevlendirmeden gelen adları forma yazar; kullanıcının elle yazdığını ezmez. */
  function applyTeamDefaults(info, {force = false} = {}) {
    const incoming = info?.defaults || {};
    const previous = autoFilledRef.current || {};
    setForm((f) => {
      const next = {...f};
      for (const key of TEAM_FIELDS) {
        const value = incoming[key] || '';
        const current = f[key] || '';
        const wasAuto = current === (previous[key] || '');
        if (force || !current || wasAuto) next[key] = value;
      }
      return next;
    });
    autoFilledRef.current = TEAM_FIELDS.reduce((acc, key) => {
      acc[key] = incoming[key] || '';
      return acc;
    }, {});
  }

  async function loadAssignedTeam(companyId, options) {
    if (!companyId) {
      setAssignedTeam(null);
      autoFilledRef.current = {};
      return null;
    }
    try {
      const info = await api(`/trainings/assigned-team?company_id=${Number(companyId)}`);
      setAssignedTeam(info);
      applyTeamDefaults(info, options);
      return info;
    } catch (_) {
      setAssignedTeam(null);
      return null;
    }
  }

  async function loadRenewal(companyId, status) {
    const cid = companyId || form.company_id;
    if (!cid) {
      setRenewal(null);
      return;
    }
    setRenewalBusy(true);
    setRenewalErr('');
    try {
      const params = new URLSearchParams({company_id: String(Number(cid))});
      if (status) params.set('status', status);
      setRenewal(await api(`/trainings/employee-status?${params}`));
    } catch (x) {
      setRenewal(null);
      setRenewalErr(x.message || 'Yenileme listesi alınamadı.');
    } finally {
      setRenewalBusy(false);
    }
  }

  /** Yenileme listesindeki kişileri yeni eğitim formuna taşır. */
  function planTrainingForListed() {
    const ids = (renewal?.rows || [])
      .filter((r) => r.status !== 'ok')
      .map((r) => Number(r.employee_id));
    if (!ids.length) return;
    setSavedTrainingId(null);
    setSavedPayload(null);
    setExcelPreview([]);
    setExcelInfo('');
    setForm((f) => ({
      ...f,
      training_type: 'Yenileme Eğitimi',
      participant_ids: ids,
    }));
    setTab('temel');
    setOkMsg(
      `${ids.length} kişi yeni eğitime aktarıldı. Tarih ve eğitici bilgisini kontrol edip kaydedin.`,
    );
  }

  async function refreshEmployees(companyId) {
    const cid = companyId || form.company_id;
    const path = cid ? `/employees?company_id=${Number(cid)}&active=true` : '/employees';
    const list = await api(path);
    setEmployees(Array.isArray(list) ? list : []);
    return Array.isArray(list) ? list : [];
  }

  const load = async (searchQ = q) => {
    setBusy(true);
    setErr('');
    try {
      const preferredCid =
        form.company_id ||
        (user.company_id ? String(user.company_id) : '');

      // Önce hafif istekler: firma + eğitim listesi + (önbellekli) sektör
      const [c, t, sec] = await Promise.all([
        api('/companies'),
        api('/trainings' + (searchQ ? `?q=${encodeURIComponent(searchQ)}` : '')),
        loadSectorsCatalog(),
      ]);
      setCompanies(c);
      setRows(Array.isArray(t) ? t : []);
      setSectors(sec);

      const cid =
        preferredCid ||
        (c.length === 1 ? String(c[0].id) : '');
      if (cid && !form.company_id) {
        setForm((f) => ({...f, company_id: cid}));
      }

      // Tüm firmaların personelini çekme — sadece seçili / tek firma
      if (cid) {
        const list = await api(`/employees?company_id=${Number(cid)}&active=true`);
        setEmployees(Array.isArray(list) ? list : []);
        await loadAssignedTeam(cid);
      } else {
        setEmployees([]);
        setAssignedTeam(null);
      }

      try {
        const sp = await api('/trainings/special-profiles');
        setSpecialProfiles(Array.isArray(sp?.profiles) ? sp.profiles : Array.isArray(sp) ? sp : []);
      } catch (_) {
        setSpecialProfiles([]);
      }
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    load().catch((x) => setErr(x.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (tab !== 'yenileme') return;
    loadRenewal(form.company_id, renewalFilter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, form.company_id, renewalFilter]);

  function validateDates(f = form) {
    if (!f.start_date || !f.end_date) {
      return 'Eğitim başlangıç ve bitiş tarihlerini girin (tarih aralığı zorunlu).';
    }
    if (f.end_date < f.start_date) {
      return 'Bitiş tarihi başlangıç tarihinden önce olamaz.';
    }
    const hours =
      Number(f.special_duration_hours) > 0
        ? Number(f.special_duration_hours)
        : HAZARD_HOURS[f.hazard_class] || 8;
    const needed = minTrainingDays(hours);
    const span = calendarDaysInclusive(f.start_date, f.end_date);
    if (span < needed) {
      return (
        `${hours} saatlik eğitim en az ${needed} güne yayılmalıdır ` +
        `(günde en fazla ${MAX_HOURS_PER_DAY} ders saati). Başlangıç–bitiş aralığını genişletin.`
      );
    }
    return '';
  }

  function buildPayload(f = form) {
    return {
      company_id: Number(f.company_id),
      title: (f.title || '').trim(),
      training_type: f.training_type,
      delivery_method: f.delivery_method,
      location: f.location || null,
      start_date: f.start_date,
      end_date: f.end_date,
      hazard_class: f.hazard_class,
      sector: f.sector,
      instructor_name: (f.instructor_name || '').trim(),
      instructor_qualification: f.instructor_qualification || null,
      workplace_physician: (f.workplace_physician || '').trim() || null,
      employer_representative: (f.employer_representative || '').trim() || null,
      stamp_text: (f.stamp_text || '').trim() || null,
      evaluation_method: f.evaluation_method,
      passing_score: f.passing_score === '' || f.passing_score == null ? null : Number(f.passing_score),
      attendance_verified: !!f.attendance_verified,
      success_verified: !!f.success_verified,
      notes: f.notes || null,
      participant_ids: (f.participant_ids || []).map(Number),
    };
  }

  async function maybeUploadLogo(trainingId) {
    const file = pendingLogoRef.current;
    if (!file || !trainingId) return;
    try {
      await uploadFile(`/trainings/${trainingId}/logo`, file);
      pendingLogoRef.current = null;
      if (logoInputRef.current) logoInputRef.current.value = '';
    } catch (x) {
      setErr('Eğitim kaydedildi ancak logo yüklenemedi: ' + (x.message || x));
    }
  }

  async function saveTraining({keepForm = true, switchToRecords = false} = {}) {
    setErr('');
    setOkMsg('');
    if (!canEdit) {
      setErr('Bu işlem için yetkiniz yok.');
      return null;
    }
    if (!form.company_id) {
      setErr('Firma seçiniz. Uzman yalnızca görevlendirildiği işyerleri için eğitim açabilir.');
      return null;
    }
    if (!form.sector || !selectedSector) {
      setErr('Sektör / iş kolunu resmî NACE listesinden seçiniz.');
      return null;
    }
    if (!(form.participant_ids || []).length) {
      setErr('Katılımcı seçin: Excel yükleyin (.xlsx) veya ortak personel listesinden seçin.');
      return null;
    }
    if (!(form.title || '').trim() || (form.title || '').trim().length < 3) {
      setErr('Eğitim adı en az 3 karakter olmalıdır.');
      return null;
    }
    if (!(form.instructor_name || '').trim() || (form.instructor_name || '').trim().length < 3) {
      setErr('Eğitici adı soyadı zorunludur.');
      return null;
    }
    if (!form.attendance_verified || !form.success_verified) {
      setErr('Katılım ve başarı doğrulama kutularını işaretleyin.');
      return null;
    }
    const dateErr = validateDates(form);
    if (dateErr) {
      setErr(dateErr);
      return null;
    }

    const payload = buildPayload(form);

    // Yalnızca katılımcı seçimi değiştiyse yeni kayıt açmak yerine mevcut kaydı
    // güncelle; aksi halde her tıklamada kopya eğitim oluşur ve PDF eski listeyi basar.
    if (savedTrainingId && savedPayload && sameExceptParticipants(payload, savedPayload)) {
      if (participantKey(payload) === participantKey(savedPayload)) {
        setOkMsg(`Kayıt #${savedTrainingId} güncel (${payload.participant_ids.length} katılımcı). PDF çıktıları hazır.`);
        return {id: savedTrainingId};
      }
      setBusy(true);
      try {
        const updated = await api(`/trainings/${savedTrainingId}`, {
          method: 'PATCH',
          body: JSON.stringify({participant_ids: payload.participant_ids}),
        });
        setSavedPayload(payload);
        setOkMsg(`Kayıt #${savedTrainingId} güncellendi: ${payload.participant_ids.length} katılımcı.`);
        await load();
        return updated;
      } catch (x) {
        setErr(x.message || 'Katılımcı listesi güncellenemedi');
        return null;
      } finally {
        setBusy(false);
      }
    }

    setBusy(true);
    try {
      const created = await api('/trainings', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      const id = created?.id;
      setSavedTrainingId(id || null);
      setSavedPayload(id ? payload : null);
      await maybeUploadLogo(id);
      setOkMsg(`Eğitim kaydedildi (#${id}). ${payload.participant_ids.length} katılımcı ile PDF çıktıları hazır.`);
      await load();
      if (switchToRecords) setTab('kayitlar');
      if (!keepForm) {
        setForm({...emptyForm(user), company_id: form.company_id || defaultCompanyId()});
        setExcelInfo('');
        setExcelPreview([]);
        setSavedTrainingId(null);
        setSavedPayload(null);
      }
      return created;
    } catch (x) {
      setErr(x.message || 'Kayıt başarısız');
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function downloadAttendance(id) {
    setDlBusy('attendance');
    try {
      await downloadFile(`/trainings/${id}/attendance.pdf`, `egitim-${id}-katilimci-imza-formu.pdf`);
    } catch (x) {
      setErr('İmza / yoklama PDF indirilemedi: ' + (x.message || x));
    } finally {
      setDlBusy('');
    }
  }

  async function downloadCertificates(id) {
    setDlBusy('certs');
    try {
      await downloadFile(`/trainings/${id}/certificates.pdf`, `egitim-${id}-katilim-belgeleri.pdf`);
    } catch (x) {
      const msg = x.message || '';
      if (/not found/i.test(msg) || msg === 'Not Found') {
        setErr(
          'Katılım belgesi PDF indirilemedi: API sürümü eski (certificates.pdf yok). ' +
            'Render’da Clear build cache & Deploy yapın.',
        );
      } else {
        setErr('Katılım belgesi PDF indirilemedi: ' + msg);
      }
    } finally {
      setDlBusy('');
    }
  }

  async function downloadExam(id) {
    setErr('');
    setDlBusy('exam');
    try {
      await downloadFile(
        `/trainings/${id}/exam.pdf`,
        `egitim-${id}-isg-sinavi.pdf`,
        {timeoutMs: 60_000},
      );
    } catch (x) {
      setErr('Sınav PDF oluşturulamadı: ' + (x.message || x));
    } finally {
      setDlBusy('');
    }
  }

  function pickExcel() {
    setErr('');
    if (!form.company_id) {
      setErr('Excel yüklemek için önce Firma seçiniz.');
      return;
    }
    excelInputRef.current?.click();
  }

  async function processExcelFile(file) {
    if (!file) return;
    if (!form.company_id) {
      setErr('Önce firma seçiniz. Uzman yalnızca görevlendirildiği işyerine Excel yükleyebilir.');
      return;
    }
    const name = (file.name || '').toLowerCase();
    if (name.endsWith('.xls') && !name.endsWith('.xlsx') && !name.endsWith('.xlsm') && !name.endsWith('.csv')) {
      setErr('Eski .xls desteklenmez. Excel’de .xlsx olarak kaydedip tekrar yükleyin.');
      return;
    }
    if (!name.endsWith('.xlsx') && !name.endsWith('.xlsm') && !name.endsWith('.csv')) {
      setErr('Geçersiz dosya. .xlsx, .xlsm veya .csv yükleyin.');
      return;
    }

    setErr('');
    setOkMsg('');
    setBusy(true);
    setFileLabel(file.name);
    try {
      const out = await uploadFile(
        `/trainings/parse-excel?company_id=${Number(form.company_id)}&create_missing=true`,
        file,
      );
      const ids = (out.participant_ids || []).map(Number).filter(Boolean);
      const preview = (out.participants || []).map((p) => ({
        name: p.full_name || p.name || '—',
        job: p.job_title || '',
        matched: !!p.employee_id,
      }));
      const meta = out.excel_meta || {};

      setForm((f) => ({
        ...f,
        participant_ids: ids,
        ...(meta.title ? {title: String(meta.title)} : {}),
        ...(meta.training_type ? {training_type: String(meta.training_type)} : {}),
      }));
      setExcelPreview(preview);
      setExcelInfo(
        `Excel: ${out.count || ids.length} kişi · ${out.created || 0} yeni personel · ${ids.length} seçildi`,
      );
      setOkMsg(
        `Dosya dönüştürüldü. ${out.count || ids.length} satır okundu, ${out.created || 0} yeni personel oluşturuldu, ` +
          `${ids.length} katılımcı seçildi` +
          (out.matched != null ? ` (${out.matched} eşleşti).` : '.'),
      );

      try {
        await refreshEmployees(form.company_id);
      } catch (_) { /* liste yenileme opsiyonel */ }

      if (!ids.length) {
        setErr(
          'Excel okundu ama personel seçilemedi. Sütun: Ad Soyad (veya Adı + Soyadı). Dosya .xlsx/.csv olmalı.',
        );
      }
    } catch (x) {
      setErr('Excel yüklenemedi: ' + (x.message || 'Bilinmeyen hata'));
    } finally {
      setBusy(false);
    }
  }

  async function onExcelInput(e) {
    const file = e.target.files?.[0];
    e.target.value = '';
    await processExcelFile(file);
  }

  function onDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer?.files?.[0];
    processExcelFile(file);
  }

  async function selectAllEmployees() {
    setErr('');
    setOkMsg('');
    if (!form.company_id) {
      setErr('Ortak personel listesi için önce Firma seçiniz.');
      return;
    }
    setBusy(true);
    try {
      const list = await refreshEmployees(form.company_id);
      const active = list.filter(
        (e) => String(e.company_id) === String(form.company_id) && e.is_active !== false,
      );
      if (!active.length) {
        setExcelPreview([]);
        setForm((f) => ({...f, participant_ids: []}));
        setExcelInfo('');
        setErr(
          'Bu firmada aktif personel yok. PC’den Excel yükleyin veya Personel menüsünden ekleyin.',
        );
        return;
      }
      setExcelPreview([]);
      setForm((f) => ({...f, participant_ids: active.map((e) => e.id)}));
      setExcelInfo(`${active.length} kişi ortak personel listesinden seçildi`);
      setOkMsg(`${active.length} personel eğitime eklendi (ortak liste).`);
    } catch (x) {
      setErr('Personel listesi alınamadı: ' + x.message);
    } finally {
      setBusy(false);
    }
  }

  /** «Seçilen Personelleri Eğitime Ekle»: işaretlenen kişileri kullanır, seçimi değiştirmez. */
  function applyCheckedEmployees() {
    setErr('');
    setOkMsg('');
    if (!form.company_id) {
      setErr('Önce Firma seçiniz.');
      return;
    }
    const count = (form.participant_ids || []).length;
    if (!count) {
      setErr('Ortak personel listesinden en az bir çalışan işaretleyin (tümü için «Tümünü Seç»).');
      return;
    }
    setExcelPreview([]);
    setExcelInfo(`${count} kişi ortak personel listesinden işaretlendi`);
    setOkMsg(`${count} personel eğitime eklendi (yalnızca işaretlediğiniz kişiler).`);
  }

  function clearParticipants() {
    setErr('');
    setOkMsg('');
    setExcelPreview([]);
    setExcelInfo('');
    setForm((f) => ({...f, participant_ids: []}));
  }

  /** Filtredeki kişileri mevcut seçime ekler; görünmeyenleri kaldırmaz. */
  function selectVisibleEmployees() {
    setErr('');
    setOkMsg('');
    setForm((f) => {
      const ids = new Set((f.participant_ids || []).map(Number));
      visibleEmployees.forEach((e) => ids.add(Number(e.id)));
      return {...f, participant_ids: [...ids]};
    });
  }

  function toggleParticipant(id) {
    const n = Number(id);
    setForm((f) => {
      const ids = (f.participant_ids || []).map(Number);
      return {
        ...f,
        participant_ids: ids.includes(n) ? ids.filter((x) => x !== n) : [...ids, n],
      };
    });
  }

  function applySpecialProfile(code) {
    setSpecialProfileCode(code);
    if (!code) {
      setForm((prev) => ({...prev, special_duration_hours: null, special_duration_hint: ''}));
      return;
    }
    const profile = specialProfiles.find((p) => p.code === code);
    if (!profile) return;
    const topicLines = (profile.topics || [])
      .map((t) => {
        if (typeof t === 'string') return `• ${t}`;
        const mode = t.mode === 'practice' ? 'Uygulama' : 'Teori';
        return `• [${mode}] ${t.title || t.name || ''}`;
      })
      .join('\n');
    const total =
      Number(profile.default_total_hours) ||
      (Number(profile.default_theory_hours || 0) + Number(profile.default_practice_hours || 0));
    const hint =
      profile.duration_hint ||
      (total
        ? `${total} ders saati (${profile.default_theory_hours || 0} teorik` +
          (profile.default_practice_hours
            ? ` + ${profile.default_practice_hours} uygulamalı)`
            : ')')
        : '');
    setForm((prev) => ({
      ...prev,
      title: profile.title || prev.title,
      training_type: profile.title || 'İşe Özel Eğitim',
      delivery_method: profile.training_method || prev.delivery_method,
      evaluation_method:
        (profile.evaluation_methods && profile.evaluation_methods[0]) || prev.evaluation_method,
      special_duration_hours: total || null,
      special_duration_hint: hint,
      notes: [
        profile.purpose || '',
        profile.disclaimer || '',
        topicLines ? `Konular (${total || ''} saat):\n${topicLines}` : '',
      ]
        .filter(Boolean)
        .join('\n\n'),
      stamp_text: profile.legal_basis || prev.stamp_text,
    }));
  }

  async function saveSpecialTraining(e) {
    e?.preventDefault?.();
    setErr('');
    setOkMsg('');
    if (!specialProfileCode || !selectedProfile) {
      setErr('Özel eğitim profili seçiniz.');
      return;
    }
    const created = await saveTraining({keepForm: true});
    if (created?.id) {
      setOkMsg(`Özel eğitim kaydedildi: ${selectedProfile.title} (#${created.id}).`);
    }
  }

  function openDetail(row) {
    setDetail(row);
    setTab('kayitlar');
  }

  function participantRows(training) {
    const list = training?.participants || [];
    return list.map((p, i) => {
      const emp = employees.find((e) => e.id === p.employee_id);
      return {
        sira: i + 1,
        name: emp?.full_name || `Personel #${p.employee_id}`,
        tc: emp?.national_id_masked || '—',
        job: emp?.job_title || '—',
        dept: emp?.department || '—',
        cert: p.certificate_number || '—',
      };
    });
  }

  async function complete(id) {
    try {
      await api(`/trainings/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({status: 'completed', attendance_verified: true, success_verified: true}),
      });
      await load();
      if (detail?.id === id) {
        const refreshed = await api('/trainings');
        const row = (Array.isArray(refreshed) ? refreshed : []).find((x) => x.id === id);
        if (row) setDetail(row);
      }
    } catch (x) {
      setErr(x.message);
    }
  }

  /* ───────── Temel İSG tab ───────── */
  function renderTemelTab() {
    return (
      <>
        <div className="hero-shell">
          <div className="hero-band">
            <div className="hero-layout">
              <div>
                <div className="hero-chip" style={{marginBottom: 14}}>
                  <Award size={14} />
                  Eğitim Belgesi Üretim Merkezi
                </div>
                <h1 style={{fontSize: 28, fontWeight: 800, margin: '0 0 12px', lineHeight: 1.25}}>
                  Çalışan listesini yükleyin, belgeleri tek akışta üretin.
                </h1>
                <p style={{margin: 0, opacity: 0.85, lineHeight: 1.55}}>
                  Excel dosyasından katılım belgesi, imza formu ve eğitim çıktıları için profesyonel,
                  kontrollü ve hızlı bir üretim akışı.
                </p>
                <div style={{marginTop: 18, display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center'}}>
                  <button
                    type="button"
                    className="btn-premium"
                    style={{width: 'auto', padding: '0 18px'}}
                    onClick={() => setTab('ozel')}
                  >
                    Yüksekte Çalışma ve Hijyen Eğitimleri
                  </button>
                  <span style={{fontSize: 12, opacity: 0.75}}>
                    Mevcut temel eğitimden ayrı uzmanlık eğitimleri
                  </span>
                </div>
              </div>
              <div className="hero-metrics" aria-label="Eğitim modülü özellikleri">
                <div className="hero-metric" role="note">
                  <div className="hero-metric-value">Excel</div>
                  <div className="hero-metric-label">.xlsx / .xlsm / .csv yükleme</div>
                </div>
                <div className="hero-metric" role="note">
                  <div className="hero-metric-value">PDF</div>
                  <div className="hero-metric-label">Belge ve imza formu çıktısı</div>
                </div>
                <div className="hero-metric" role="note">
                  <div className="hero-metric-value">Otomatik</div>
                  <div className="hero-metric-label">Tehlike sınıfına göre süre</div>
                </div>
                <div className="hero-metric" role="note">
                  <div className="hero-metric-value">Ortak Liste</div>
                  <div className="hero-metric-label">Aktif işyeri personeli</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="panel-card">
          <div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: 12, marginBottom: 18}}>
            <div>
              <div className="section-title" style={{marginBottom: 6}}>Belge Akışı</div>
              <h2 style={{margin: '0 0 6px', fontSize: 22}}>Çalışan listesi yükleme formu</h2>
              <p className="tp-help" style={{margin: 0}}>
                Firma, eğitim ve imza bilgilerini doğrulayın; ardından Excel dosyasını sisteme yükleyin.
              </p>
            </div>
            <span
              style={{
                padding: '8px 12px',
                borderRadius: 999,
                background: '#edf5f2',
                color: '#12634b',
                fontWeight: 800,
                fontSize: 12,
                alignSelf: 'flex-start',
              }}
            >
              <ShieldCheck size={14} style={{verticalAlign: -2, marginRight: 4}} />
              Gereksiz veri saklanmaz
            </span>
          </div>

          {err && <div className="tp-alert err">{err}</div>}
          {okMsg && <div className="tp-alert ok">{okMsg}</div>}

          <div className="tp-grid-2" style={{marginBottom: 12}}>
            <div className="field-card">
              <label className="tp-label" htmlFor="tp-firma">Firma Seç</label>
              <select
                id="tp-firma"
                className="tp-select"
                value={form.company_id}
                disabled={!canEdit}
                onChange={(e) => {
                  setExcelPreview([]);
                  setExcelInfo('');
                  setOkMsg('');
                  setErr('');
                  setSavedTrainingId(null);
                  const cid = e.target.value;
                  const picked = companies.find((c) => String(c.id) === String(cid));
                  setForm({
                    ...form,
                    company_id: cid,
                    participant_ids: [],
                    hazard_class: picked?.hazard_class || form.hazard_class,
                  });
                  if (cid) {
                    refreshEmployees(cid).catch((x) =>
                      setErr('Personel listesi alınamadı: ' + (x.message || x)),
                    );
                    loadAssignedTeam(cid, {force: true});
                  } else {
                    setAssignedTeam(null);
                  }
                }}
              >
                <option value="">Seçiniz</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              <div className="tp-help">Personel, eğitim kaydı ve belgeler seçtiğiniz firmaya bağlanır.</div>
            </div>
            <div className="field-card">
              <label className="tp-label" htmlFor="tp-logo">Firma logosu (opsiyonel)</label>
              <input
                id="tp-logo"
                ref={logoInputRef}
                className="tp-input"
                type="file"
                accept=".png,.jpg,.jpeg,.gif,.webp"
                disabled={!canEdit}
                onChange={(e) => {
                  pendingLogoRef.current = e.target.files?.[0] || null;
                }}
              />
              <div className="tp-help">PNG/JPG — kayıt sonrası belge sol üstüne basılır.</div>
            </div>
          </div>

          <div className="field-card" style={{marginBottom: 12}}>
            <div className="section-title" style={{marginBottom: 8}}>Gerçekleşme ve Kanıt Zinciri</div>
            <div className="tp-grid-2">
              <div>
                <label className="tp-label">Eğitimin adı *</label>
                <input
                  className="tp-input"
                  value={form.title}
                  disabled={!canEdit}
                  onChange={(e) => setForm({...form, title: e.target.value})}
                  placeholder="Örn: Temel İş Sağlığı ve Güvenliği Eğitimi"
                />
              </div>
              <div>
                <label className="tp-label">Eğitici adı soyadı *</label>
                {instructorOptions.length > 0 ? (
                  <select
                    className="tp-select"
                    value={instructorIsCustom ? '__custom__' : form.instructor_name}
                    disabled={!canEdit}
                    onChange={(e) => pickInstructor(e.target.value)}
                  >
                    {instructorOptions.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.value} — {o.qualification}
                      </option>
                    ))}
                    <option value="__custom__">Başka biri (elle yazacağım)</option>
                  </select>
                ) : null}
                {(instructorOptions.length === 0 || instructorIsCustom) && (
                  <input
                    className="tp-input"
                    style={instructorOptions.length > 0 ? {marginTop: 8} : undefined}
                    value={form.instructor_name}
                    disabled={!canEdit}
                    onChange={(e) => setForm({...form, instructor_name: e.target.value})}
                    placeholder="İSG uzmanı veya işyeri hekimi"
                  />
                )}
                <div className="tp-help">
                  {instructorOptions.length > 0
                    ? 'İşyerine görevlendirilmiş uzman ve hekim listelenir; ad elle yazılmaz.'
                    : 'Bu işyerine atanmış görevli bulunamadı — adı elle yazın veya Görevlendirmeler ekranından atama yapın.'}
                </div>
              </div>
              <div>
                <label className="tp-label">Eğitici unvanı / yeterlilik</label>
                <input
                  className="tp-input"
                  value={form.instructor_qualification}
                  disabled={!canEdit}
                  onChange={(e) => setForm({...form, instructor_qualification: e.target.value})}
                  placeholder="Örn: A Sınıfı İGU — belge no"
                />
              </div>
              <div>
                <label className="tp-label">Başarı değerlendirmesi</label>
                <select
                  className="tp-select"
                  value={form.evaluation_method}
                  disabled={!canEdit}
                  onChange={(e) => setForm({...form, evaluation_method: e.target.value})}
                >
                  <option>Sınav</option>
                  <option>Uygulama</option>
                  <option>Sözlü değerlendirme</option>
                  <option>Katılım yeterlidir</option>
                  <option>Yazılı ve uygulamalı değerlendirme</option>
                  <option>Sözlü ve uygulamalı değerlendirme</option>
                  <option>Yazılı değerlendirme</option>
                </select>
              </div>
              <div>
                <label className="tp-label">Başarı puanı (0–100)</label>
                <input
                  className="tp-input"
                  type="number"
                  min="0"
                  max="100"
                  value={form.passing_score}
                  disabled={!canEdit}
                  onChange={(e) => setForm({...form, passing_score: e.target.value})}
                  placeholder="0–100"
                />
              </div>
              <div>
                <label className="tp-label">Eğitim türü</label>
                <select
                  className="tp-select"
                  value={form.training_type}
                  disabled={!canEdit}
                  onChange={(e) => setForm({...form, training_type: e.target.value})}
                >
                  <option>İlk Defa</option>
                  <option>Tekrar</option>
                  <option>Temel İSG Eğitimi</option>
                  <option>İşe Özel Eğitim</option>
                  <option>Yenileme Eğitimi</option>
                </select>
              </div>
            </div>
            <div className="tp-grid-2" style={{marginTop: 12}}>
              <label className="check-box">
                <input
                  type="checkbox"
                  checked={!!form.attendance_verified}
                  disabled={!canEdit}
                  onChange={(e) => setForm({...form, attendance_verified: e.target.checked})}
                />
                <span>
                  <strong>Katılım doğrulandı</strong>
                  <small className="tp-help" style={{display: 'block'}}>
                    Katılımcıların eğitime devam/katılım kayıtlarının kontrol edildiğini onaylıyorum.
                  </small>
                </span>
              </label>
              <label className="check-box">
                <input
                  type="checkbox"
                  checked={!!form.success_verified}
                  disabled={!canEdit}
                  onChange={(e) => setForm({...form, success_verified: e.target.checked})}
                />
                <span>
                  <strong>Başarı koşulu sağlandı</strong>
                  <small className="tp-help" style={{display: 'block'}}>
                    Belge oluşturulacak kişilerin değerlendirmeyi başarıyla tamamladığını onaylıyorum.
                  </small>
                </span>
              </label>
            </div>
          </div>

          <div className="tp-grid-2" style={{marginBottom: 12}}>
            <div className="field-card">
              <div className="section-title" style={{marginBottom: 10}}>İmza Yetkilileri</div>
              <label className="tp-label">İşyeri hekimi</label>
              <input
                className="tp-input"
                value={form.workplace_physician}
                disabled={!canEdit}
                onChange={(e) => setForm({...form, workplace_physician: e.target.value})}
                placeholder="Ad Soyad"
              />
              <label className="tp-label" style={{marginTop: 10}}>İşveren / vekili</label>
              <input
                className="tp-input"
                value={form.employer_representative}
                disabled={!canEdit}
                onChange={(e) => setForm({...form, employer_representative: e.target.value})}
                placeholder="Ad Soyad"
              />
              <div className="tp-help" style={{marginTop: 8}}>
                Hekim adı işyerine atanmış görevliden, işveren vekili işyeri kartından gelir.
                {canEdit && form.company_id && (
                  <button
                    type="button"
                    className="btn-outline-premium"
                    style={{marginLeft: 8, width: 'auto', minHeight: 30, padding: '0 12px', fontSize: 12}}
                    onClick={() => loadAssignedTeam(form.company_id, {force: true})}
                  >
                    Görevlilerden yeniden doldur
                  </button>
                )}
              </div>
            </div>

            <div className="field-card">
              <div className="section-title" style={{marginBottom: 10}}>Eğitim Bilgileri</div>
              <div className="tp-grid-2">
                <div>
                  <label className="tp-label">Tehlike sınıfı</label>
                  <select
                    className="tp-select"
                    value={form.hazard_class}
                    disabled
                    aria-label="NACE faaliyetine göre otomatik tehlike sınıfı"
                  >
                    <option>Az Tehlikeli</option>
                    <option>Tehlikeli</option>
                    <option>Çok Tehlikeli</option>
                  </select>
                  <div className="tp-help">
                    Tehlike sınıfı seçilen resmî NACE faaliyetine göre otomatik belirlenir.
                  </div>
                </div>
                <div>
                  <label className="tp-label">Süre / yenileme</label>
                  <input className="tp-input" readOnly value={HAZARD_HINT[form.hazard_class] || ''} />
                </div>
                <div>
                  <label className="tp-label">Başlangıç tarihi *</label>
                  <input
                    className="tp-input"
                    type="date"
                    value={form.start_date}
                    disabled={!canEdit}
                    onChange={(e) => setForm({...form, start_date: e.target.value})}
                  />
                </div>
                <div>
                  <label className="tp-label">Bitiş tarihi *</label>
                  <input
                    className="tp-input"
                    type="date"
                    min={form.start_date || undefined}
                    value={form.end_date}
                    disabled={!canEdit}
                    onChange={(e) => setForm({...form, end_date: e.target.value})}
                  />
                </div>
                <div style={{gridColumn: '1 / -1'}}>
                  <label className="tp-label">Eğitim yeri</label>
                  <input
                    className="tp-input"
                    value={form.location}
                    disabled={!canEdit}
                    onChange={(e) => setForm({...form, location: e.target.value})}
                  />
                </div>
                <div style={{gridColumn: '1 / -1'}}>
                  <label className="tp-label">
                    Sektör / iş kolu — NACE ({filteredSectors.length} kayıt)
                  </label>
                  <div className="nace-picker" ref={sectorPickerRef}>
                    <div className="nace-search-wrap">
                      <Search size={18} aria-hidden="true" />
                      <input
                        className="tp-input nace-search-input"
                        type="search"
                        value={sectorQuery}
                        disabled={!canEdit}
                        placeholder="NACE kodu veya faaliyet adı yazın…"
                        role="combobox"
                        aria-expanded={sectorPickerOpen}
                        aria-controls="training-nace-results"
                        onFocus={() => setSectorPickerOpen(true)}
                        onChange={(event) => {
                          setSectorQuery(event.target.value);
                          setSectorPickerOpen(true);
                        }}
                      />
                    </div>
                    {sectorPickerOpen && canEdit && (
                      <div className="nace-results" id="training-nace-results" role="listbox">
                        {visibleSectorResults.map((item) => (
                          <button
                            key={item.code}
                            type="button"
                            className={`nace-result${item.code === form.sector ? ' active' : ''}`}
                            role="option"
                            aria-selected={item.code === form.sector}
                            onClick={() => pickSector(item.code)}
                          >
                            {item.label || `${item.nace || item.code} / ${item.name} / ${item.hazard_class || '—'}`}
                          </button>
                        ))}
                        {visibleSectorResults.length === 0 && (
                          <div className="nace-empty">Aramanızla eşleşen faaliyet bulunamadı.</div>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="nace-selected-label">
                    {selectedSector
                      ? selectedSector.label || `${selectedSector.nace || selectedSector.code} / ${selectedSector.name} / ${selectedSector.hazard_class || '—'}`
                      : 'Henüz NACE faaliyeti seçilmedi.'}
                  </div>
                  <div className="tp-help">
                    {filteredSectors.length > 100
                      ? `${filteredSectors.length} sonuç bulundu; ilk 100 sonuç gösteriliyor. Aramayı daraltın.`
                      : `${filteredSectors.length} faaliyet bulundu. Faaliyet adlarının tamamı okunabilir.`}
                  </div>
                </div>
              </div>
              <div className="tp-alert warn" style={{marginTop: 10}}>
                Günde en fazla {MAX_HOURS_PER_DAY} ders saati;
                {` ${HAZARD_HOURS[form.hazard_class] || 8} saatlik eğitim en az ${minTrainingDays(HAZARD_HOURS[form.hazard_class] || 8)} takvim gününe yayılmalıdır.`}
              </div>
              <div className="sector-topics" style={{marginTop: 10}}>
                <strong>
                  {form.hazard_class === 'Az Tehlikeli'
                    ? '4. Faaliyetin Genel Tehlike ve Riskleri'
                    : '4. İşe ve İşyerine Özgü Riskler ve Risk Değerlendirmesine Dayalı Konular'}
                </strong>
                <div className="tp-help" style={{marginBottom: 6}}>
                  {selectedSector
                    ? `${selectedSector.hazard_class} için beş özgün konu belge ve imza formuna aktarılır.`
                    : 'Sektör seçildiğinde belgeye yazılacak konular:'}
                </div>
                {(selectedSector?.topics || []).length ? (
                  <ol style={{margin: 0, paddingLeft: 18}}>
                    {(selectedSector.topics).map((t, i) => (
                      <li key={i}>{typeof t === 'string' ? t : t.title || t.name}</li>
                    ))}
                  </ol>
                ) : (
                  <div>Sektör seçildiğinde konular burada görünür.</div>
                )}
              </div>
            </div>
          </div>

          <div className="shared-personnel-panel">
            <div className="shared-personnel-head">
              <div>
                <div className="section-title" style={{marginBottom: 4}}>Ortak Personel Listesi</div>
                <h3 style={{margin: '0 0 4px', fontSize: 16}}>
                  {form.company_id ? companyName(Number(form.company_id)) : 'Aktif işyeri seçilmedi'}
                </h3>
                <div className="tp-help" style={{margin: 0}}>
                  Yalnız seçili işyerinin aktif çalışanları gösterilir. Eğitime eklenecek kişileri işaretleyin.
                </div>
              </div>
              {canEdit && companyEmployees.length > 0 && (
                <button
                  type="button"
                  className="btn-outline-premium"
                  style={{width: 'auto', minHeight: 40, padding: '0 16px'}}
                  onClick={allEmployeesSelected ? clearParticipants : selectAllEmployees}
                >
                  {allEmployeesSelected ? 'Seçimi Temizle' : 'Tümünü Seç'}
                </button>
              )}
            </div>
            {companyEmployees.length > 0 && (
              <div
                style={{
                  display: 'grid', gap: 10, padding: '0 1rem 12px',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))',
                }}
              >
                <div>
                  <label className="tp-label" htmlFor="tp-personel-ara">Personel ara</label>
                  <input
                    id="tp-personel-ara"
                    className="tp-input"
                    type="search"
                    value={empQuery}
                    placeholder="Ad soyad veya görev"
                    onChange={(e) => setEmpQuery(e.target.value)}
                  />
                </div>
                <div>
                  <label className="tp-label" htmlFor="tp-personel-bolum">Bölüm</label>
                  <select
                    id="tp-personel-bolum"
                    className="tp-select"
                    value={empDept}
                    onChange={(e) => setEmpDept(e.target.value)}
                  >
                    <option value="">Tüm bölümler</option>
                    {departmentOptions.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                </div>
                {canEdit && (empQuery || empDept) && (
                  <div style={{alignSelf: 'end', display: 'flex', gap: 8}}>
                    <button
                      type="button"
                      className="btn-outline-premium"
                      style={{width: 'auto', minHeight: 40, padding: '0 14px'}}
                      onClick={selectVisibleEmployees}
                      disabled={!visibleEmployees.length}
                    >
                      Görünenleri seç ({visibleEmployees.length})
                    </button>
                  </div>
                )}
              </div>
            )}
            {companyEmployees.length ? (
              <>
                <div className="shared-personnel-list">
                  {visibleEmployees.length === 0 && (
                    <div style={{padding: '8px 4px', fontSize: 13, color: '#6b7d90'}}>
                      Aramaya uyan personel yok. Filtreyi temizleyin.
                    </div>
                  )}
                  {visibleEmployees.map((emp) => {
                    const checked =
                      form.participant_ids.includes(emp.id) ||
                      form.participant_ids.includes(Number(emp.id));
                    return (
                      <label key={emp.id} className="shared-personnel-item">
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={!canEdit}
                          onChange={() => toggleParticipant(emp.id)}
                        />
                        <span>
                          <span className="shared-personnel-name">{emp.full_name}</span>
                          <span className="shared-personnel-meta">
                            {emp.job_title || 'Görev belirtilmemiş'}
                            {emp.department ? ` · ${emp.department}` : ''}
                          </span>
                        </span>
                      </label>
                    );
                  })}
                </div>
                <div style={{padding: '0 1rem 1rem', fontSize: 13, color: '#6b7d90'}}>
                  {form.participant_ids.length} / {companyEmployees.length} çalışan seçildi.
                  {visibleEmployees.length !== companyEmployees.length
                    ? ` · filtrede ${visibleEmployees.length} kişi görünüyor (seçim korunur)`
                    : ''}
                  {excelInfo ? ` · ${excelInfo}` : ''}
                </div>
              </>
            ) : (
              <div className="shared-personnel-empty">
                {excelPreview.length ? (
                  excelPreview.map((p, i) => (
                    <div key={i}>• {p.name}{p.job ? ` — ${p.job}` : ''}</div>
                  ))
                ) : (
                  <>
                    Bu işyerine ait aktif çalışan bulunamadı. Excel yükleyin veya Personel menüsünden ekleyin.
                  </>
                )}
              </div>
            )}
          </div>

          <div className="field-card" style={{marginBottom: 14}}>
            <div className="section-title" style={{marginBottom: 10}}>Excel Dosyası</div>
            <div
              className={'drop-zone' + (dragOver ? ' drag' : '')}
              role="button"
              tabIndex={0}
              onClick={() => canEdit && pickExcel()}
              onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && canEdit && pickExcel()}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={canEdit ? onDrop : undefined}
            >
              <Upload size={36} style={{opacity: 0.55}} />
              <p style={{fontWeight: 700, margin: '12px 0 4px'}}>{fileLabel}</p>
              <p className="tp-help" style={{margin: 0}}>
                Ad Soyad zorunludur. TC Kimlik, Branş/Görev ve Bölüm alanları önerilir.
                {!form.company_id ? ' · önce Firma seçin' : ''}
              </p>
              <input
                ref={excelInputRef}
                type="file"
                accept=".xlsx,.xlsm,.csv"
                hidden
                onChange={onExcelInput}
              />
            </div>
          </div>

          {canEdit && (
            <div style={{display: 'grid', gap: 10}}>
              <button
                type="button"
                className="btn-premium"
                disabled={busy}
                onClick={pickExcel}
              >
                <FileSpreadsheet size={18} style={{verticalAlign: -3, marginRight: 6}} />
                PC&apos;den Dosyayı Yükle ve Dönüştür
              </button>
              <button
                type="button"
                className="btn-outline-premium"
                disabled={busy}
                onClick={applyCheckedEmployees}
              >
                <Users size={18} style={{verticalAlign: -3, marginRight: 6}} />
                Seçilen Personelleri Eğitime Ekle
              </button>
              <div className="tp-help" style={{textAlign: 'center'}}>
                PC seçeneği Excel/CSV dosyasını okur. Ortak Personel seçeneği yalnızca yukarıda
                işaretlediğiniz çalışanları kullanır; tüm liste için «Tümünü Seç».
              </div>
            </div>
          )}

          <EducationOutputPanel
            savedTrainingId={savedTrainingId}
            participantCount={form.participant_ids.length}
            selectionDirty={selectionDirty}
            dlBusy={dlBusy}
            canEdit={canEdit}
            busy={busy}
            onDownloadCertificates={() => downloadCertificates(savedTrainingId)}
            onDownloadAttendance={() => downloadAttendance(savedTrainingId)}
            onDownloadExam={() => downloadExam(savedTrainingId)}
            onSaveAndPrepare={() => saveTraining({keepForm: true})}
          />
        </div>
      </>
    );
  }

  /* ───────── Özel Eğitimler tab ───────── */
  function renderOzelTab() {
    return (
      <>
        <div className="hero-shell">
          <div className="hero-band">
            <div className="hero-layout">
              <div>
                <div className="hero-chip" style={{marginBottom: 12}}>Uzmanlık Eğitimleri</div>
                <h1 style={{fontSize: 26, fontWeight: 800, margin: '0 0 10px'}}>
                  İki özel eğitim, mevcut temel eğitimden tamamen ayrı.
                </h1>
                <p style={{margin: 0, opacity: 0.85}}>
                  Gerçek katılımcı, doğrulanmış eğitici bilgisi ve kurumsal PDF üretimi.
                </p>
              </div>
              <div className="hero-metrics">
                {specialProfiles.slice(0, 4).map((p) => (
                  <div key={p.code} className="special-profile-card">
                    <b>{p.title}</b>
                    <small style={{opacity: 0.8, display: 'block', marginTop: 4}}>
                      {(p.default_total_hours || p.default_theory || '?')} saat · {p.training_method || 'Yüz yüze'}
                    </small>
                  </div>
                ))}
                {!specialProfiles.length && (
                  <div className="special-profile-card">
                    <b>Profiller yükleniyor…</b>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="panel-card">
          <div className="section-title" style={{marginBottom: 6}}>Eğitim ve Belge Hazırlama</div>
          <h2 style={{margin: '0 0 8px', fontSize: 20}}>Uzmanlık eğitim kaydı oluşturun</h2>
          <p className="tp-help">Profil kartından seçim yapın; eğitim türü profil başlığı olarak kaydedilir.</p>

          {err && <div className="tp-alert err">{err}</div>}
          {okMsg && <div className="tp-alert ok">{okMsg}</div>}

          <div className="tp-grid-2" style={{marginBottom: 14}}>
            {specialProfiles.map((p) => (
              <button
                key={p.code}
                type="button"
                className="field-card"
                style={{
                  textAlign: 'left',
                  cursor: 'pointer',
                  borderColor: specialProfileCode === p.code ? '#f6b800' : undefined,
                  boxShadow: specialProfileCode === p.code ? '0 0 0 2px rgba(246,184,0,.35)' : undefined,
                }}
                onClick={() => applySpecialProfile(p.code)}
              >
                <strong style={{display: 'block', marginBottom: 6}}>{p.title}</strong>
                <span className="tp-help">{p.purpose || p.disclaimer || 'Özel eğitim profili'}</span>
                <div style={{marginTop: 8}}>
                  {(p.topics || []).slice(0, 6).map((t, i) => (
                    <span key={i} className="topic-chip">
                      {typeof t === 'string' ? t : t.title || t.name}
                    </span>
                  ))}
                </div>
              </button>
            ))}
            {!specialProfiles.length && (
              <div className="tp-alert warn">Özel eğitim profilleri yüklenemedi.</div>
            )}
          </div>

          <form onSubmit={saveSpecialTraining}>
            <div className="tp-grid-2">
              <div>
                <label className="tp-label">Firma</label>
                <select
                  className="tp-select"
                  value={form.company_id}
                  disabled={!canEdit}
                  onChange={(e) => {
                    const cid = e.target.value;
                    setForm({...form, company_id: cid, participant_ids: []});
                    if (cid) refreshEmployees(cid).catch(() => {});
                  }}
                >
                  <option value="">Seçiniz</option>
                  {companies.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="tp-label">Eğitim profili</label>
                <select
                  className="tp-select"
                  value={specialProfileCode}
                  disabled={!canEdit}
                  onChange={(e) => applySpecialProfile(e.target.value)}
                >
                  <option value="">Seçiniz</option>
                  {specialProfiles.map((p) => (
                    <option key={p.code} value={p.code}>
                      {p.title} ({p.default_total_hours || '?'} saat)
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="tp-label">Süre (otomatik)</label>
                <input
                  className="tp-input"
                  readOnly
                  value={
                    form.special_duration_hint ||
                    (selectedProfile
                      ? selectedProfile.duration_hint ||
                        `${selectedProfile.default_total_hours || '?'} ders saati`
                      : 'Profil seçince süre gelir')
                  }
                />
                <div className="tp-help">
                  6331 ve ilgili yönetmeliklere göre profil süresi otomatik uygulanır; belgede bu saat basılır.
                </div>
              </div>
              <div>
                <label className="tp-label">Eğitici adı soyadı *</label>
                {instructorOptions.length > 0 ? (
                  <select
                    className="tp-select"
                    value={instructorIsCustom ? '__custom__' : form.instructor_name}
                    disabled={!canEdit}
                    onChange={(e) => pickInstructor(e.target.value)}
                  >
                    {instructorOptions.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.value} — {o.qualification}
                      </option>
                    ))}
                    <option value="__custom__">Başka biri (elle yazacağım)</option>
                  </select>
                ) : null}
                {(instructorOptions.length === 0 || instructorIsCustom) && (
                  <input
                    className="tp-input"
                    style={instructorOptions.length > 0 ? {marginTop: 8} : undefined}
                    required
                    value={form.instructor_name}
                    disabled={!canEdit}
                    onChange={(e) => setForm({...form, instructor_name: e.target.value})}
                  />
                )}
              </div>
              <div>
                <label className="tp-label">Yeterlilik / unvan</label>
                <input
                  className="tp-input"
                  value={form.instructor_qualification}
                  disabled={!canEdit}
                  onChange={(e) => setForm({...form, instructor_qualification: e.target.value})}
                />
              </div>
              <div>
                <label className="tp-label">Başlangıç *</label>
                <input
                  className="tp-input"
                  type="date"
                  required
                  value={form.start_date}
                  disabled={!canEdit}
                  onChange={(e) => setForm({...form, start_date: e.target.value})}
                />
              </div>
              <div>
                <label className="tp-label">Bitiş *</label>
                <input
                  className="tp-input"
                  type="date"
                  required
                  value={form.end_date}
                  disabled={!canEdit}
                  onChange={(e) => setForm({...form, end_date: e.target.value})}
                />
              </div>
              <div>
                <label className="tp-label">Eğitim yeri</label>
                <input
                  className="tp-input"
                  value={form.location}
                  disabled={!canEdit}
                  onChange={(e) => setForm({...form, location: e.target.value})}
                />
              </div>
              <div>
                <label className="tp-label">Değerlendirme</label>
                <select
                  className="tp-select"
                  value={form.evaluation_method}
                  disabled={!canEdit}
                  onChange={(e) => setForm({...form, evaluation_method: e.target.value})}
                >
                  {(selectedProfile?.evaluation_methods || []).length
                    ? selectedProfile.evaluation_methods.map((m) => (
                      <option key={m}>{m}</option>
                    ))
                    : (
                      <>
                        <option>Yazılı ve uygulamalı değerlendirme</option>
                        <option>Uygulama</option>
                        <option>Sınav</option>
                      </>
                    )}
                </select>
              </div>
            </div>

            <div className="shared-personnel-panel" style={{marginTop: 14}}>
              <div className="shared-personnel-head">
                <div>
                  <div className="section-title">Katılımcılar</div>
                  <div className="tp-help">Personel listesinden seçin.</div>
                </div>
                {canEdit && (
                  <button
                    type="button"
                    className="btn-outline-premium"
                    style={{width: 'auto', minHeight: 40, padding: '0 14px'}}
                    onClick={allEmployeesSelected ? clearParticipants : selectAllEmployees}
                  >
                    {allEmployeesSelected ? 'Seçimi Temizle' : 'Tümünü Seç'}
                  </button>
                )}
              </div>
              <div className="shared-personnel-list">
                {companyEmployees.length ? companyEmployees.map((emp) => {
                  const checked =
                    form.participant_ids.includes(emp.id) ||
                    form.participant_ids.includes(Number(emp.id));
                  return (
                    <label key={emp.id} className="shared-personnel-item">
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={!canEdit}
                        onChange={() => toggleParticipant(emp.id)}
                      />
                      <span>
                        <span className="shared-personnel-name">{emp.full_name}</span>
                        <span className="shared-personnel-meta">{emp.job_title || '—'}</span>
                      </span>
                    </label>
                  );
                }) : (
                  <div className="shared-personnel-empty">Firma seçip personel bekleyin.</div>
                )}
              </div>
            </div>

            {canEdit && (
              <button type="submit" className="btn-premium" style={{marginTop: 14}} disabled={busy}>
                {busy ? 'Kaydediliyor…' : 'Kaydı Doğrula ve Belgelere Hazırla'}
              </button>
            )}
          </form>

          <EducationOutputPanel
            savedTrainingId={savedTrainingId}
            participantCount={form.participant_ids.length}
            selectionDirty={selectionDirty}
            dlBusy={dlBusy}
            canEdit={canEdit}
            busy={busy}
            onDownloadCertificates={() => downloadCertificates(savedTrainingId)}
            onDownloadAttendance={() => downloadAttendance(savedTrainingId)}
            onDownloadExam={() => downloadExam(savedTrainingId)}
            onSaveAndPrepare={() => saveTraining({keepForm: true})}
          />
        </div>
      </>
    );
  }

  /* ───────── Yenileme takibi tab ───────── */
  function renderYenilemeTab() {
    const summary = renewal?.summary;
    const rowsToShow = renewal?.rows || [];
    const cards = [
      {key: 'never', value: summary?.never, label: 'Eğitim kaydı yok'},
      {key: 'expired', value: summary?.expired, label: 'Süresi dolmuş'},
      {key: 'due_soon', value: summary?.due_soon, label: `${summary?.due_soon_days || 60} gün içinde`},
      {key: 'ok', value: summary?.ok, label: 'Geçerli'},
    ];
    return (
      <div className="panel-card">
        <div className="section-title" style={{marginBottom: 6}}>Çalışan Bazlı Takip</div>
        <h2 style={{margin: '0 0 6px', fontSize: 20}}>Kimin eğitimi dolmuş?</h2>
        <p className="tp-help" style={{marginTop: 0}}>
          Temel İSG eğitimi tehlike sınıfına göre az tehlikeli 3, tehlikeli 2, çok tehlikeli 1 yılda bir
          yenilenir. Hiç eğitim kaydı olmayan personel de listelenir; yönetmelik eğitimin işe başlamadan
          önce verilmesini şart koşar. Yüksekte çalışma gibi özel eğitimler temel eğitim yerine geçmez.
        </p>

        {!form.company_id && (
          <div className="tp-alert">Önce Temel İSG sekmesinden bir işyeri seçin.</div>
        )}
        {renewalErr && <div className="tp-alert err">{renewalErr}</div>}

        {summary && (
          <div
            style={{
              display: 'grid', gap: 10, margin: '12px 0 16px',
              gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            }}
          >
            {cards.map((c) => {
              const s = STATUS_STYLES[c.key];
              const active = renewalFilter === c.key;
              return (
                <button
                  key={c.key}
                  type="button"
                  onClick={() => setRenewalFilter(active ? '' : c.key)}
                  style={{
                    textAlign: 'left', cursor: 'pointer', padding: '12px 14px', borderRadius: 12,
                    background: s.bg, color: s.fg,
                    border: active ? `2px solid ${s.fg}` : '1px solid transparent',
                  }}
                >
                  <div style={{fontSize: 26, fontWeight: 800, lineHeight: 1.1}}>{c.value ?? 0}</div>
                  <div style={{fontSize: 13, fontWeight: 600}}>{c.label}</div>
                </button>
              );
            })}
          </div>
        )}

        {summary && (
          <div className="tp-help" style={{marginBottom: 12}}>
            {summary.total_employees} aktif personel · uyumluluk %{summary.compliance_rate}
            {summary.action_needed > 0 && ` · ${summary.action_needed} kişi için işlem gerekiyor`}
            {renewalFilter && (
              <button
                type="button"
                className="btn-outline-premium"
                style={{marginLeft: 8, width: 'auto', minHeight: 30, padding: '0 12px', fontSize: 12}}
                onClick={() => setRenewalFilter('')}
              >
                Filtreyi kaldır
              </button>
            )}
          </div>
        )}

        {canEdit && rowsToShow.some((r) => r.status !== 'ok') && (
          <button
            type="button"
            className="btn-premium"
            style={{width: 'auto', minHeight: 44, padding: '0 18px', marginBottom: 14}}
            onClick={planTrainingForListed}
          >
            Listedeki {rowsToShow.filter((r) => r.status !== 'ok').length} kişiyi yeni eğitime aktar
          </button>
        )}

        <div style={{overflowX: 'auto'}}>
          <table className="records-table">
            <thead>
              <tr>
                <th>Personel</th>
                <th>Bölüm</th>
                <th>Son eğitim</th>
                <th>Yenileme tarihi</th>
                <th>Durum</th>
              </tr>
            </thead>
            <tbody>
              {rowsToShow.length ? rowsToShow.map((r) => {
                const s = STATUS_STYLES[r.status] || STATUS_STYLES.ok;
                return (
                  <tr key={r.employee_id}>
                    <td>
                      {r.full_name}
                      {r.job_title && (
                        <div style={{fontSize: 12, color: '#6b7d90'}}>{r.job_title}</div>
                      )}
                    </td>
                    <td>{r.department || '—'}</td>
                    <td>{r.last_training_end || '—'}</td>
                    <td>{r.next_due || '—'}</td>
                    <td>
                      <span
                        style={{
                          display: 'inline-block', padding: '3px 10px', borderRadius: 999,
                          background: s.bg, color: s.fg, fontSize: 12, fontWeight: 700,
                        }}
                      >
                        {r.status_label || s.label}
                      </span>
                      <div style={{fontSize: 12, color: '#6b7d90', marginTop: 4}}>{r.message}</div>
                    </td>
                  </tr>
                );
              }) : (
                <tr>
                  <td colSpan={5}>
                    {renewalBusy ? 'Yükleniyor…' : 'Gösterilecek personel yok.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  /* ───────── Kayıtlar tab ───────── */
  function renderKayitlarTab() {
    if (detail) {
      return (
        <div className="panel-card">
          <div style={{display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 16}}>
            <div>
              <div className="section-title">Belge Üretim Merkezi</div>
              <h2 style={{margin: '4px 0'}}>{detail.title}</h2>
              <p className="tp-help" style={{margin: 0}}>
                {companyName(detail.company_id)} · {formatTrainingDates(detail)} · {detail.hazard_class} ·{' '}
                {detail.duration_hours} saat
              </p>
            </div>
            <button type="button" className="btn-outline-premium" style={{width: 'auto', minHeight: 42, padding: '0 16px'}} onClick={() => setDetail(null)}>
              Listeye dön
            </button>
          </div>

          <div className="tp-grid-3" style={{marginBottom: 14, fontSize: 14}}>
            <div><span className="tp-help">Eğitici</span><div><strong>{detail.instructor_name}</strong></div></div>
            <div><span className="tp-help">Sektör</span><div><strong>{sectorLabel(sectors, detail.sector)}</strong></div></div>
            <div>
              <span className="tp-help">Durum</span>
              <div><strong>{STATUS[detail.status] || detail.status}</strong></div>
            </div>
          </div>

          <div className="sector-topics" style={{marginBottom: 14}}>
            <strong>Belgede basılacak konular (4. bölüm)</strong>
            {(sectors.find((s) => s.code === detail.sector)?.topics || []).length
              ? (sectors.find((s) => s.code === detail.sector).topics).map((t, i) => (
                <div key={i}>• {typeof t === 'string' ? t : t.title || t.name}</div>
              ))
              : <div>Sektör konuları yüklenemedi.</div>}
          </div>

          <div className="education-output-row" style={{marginBottom: 16}}>
            <button
              type="button"
              className="education-output-button education-output-button--certificate"
              disabled={!detail.participants?.length || !!dlBusy}
              onClick={() => downloadCertificates(detail.id)}
            >
              <Download size={16} /> Sertifika PDF
            </button>
            <button
              type="button"
              className="education-output-button education-output-button--attendance"
              disabled={!detail.participants?.length || !!dlBusy}
              onClick={() => downloadAttendance(detail.id)}
            >
              <Download size={16} /> Katılım PDF
            </button>
          </div>

          {canEdit && detail.status !== 'completed' && (
            <button
              type="button"
              className="btn-outline-premium"
              style={{marginBottom: 14}}
              onClick={() => complete(detail.id)}
            >
              <CheckCircle2 size={16} style={{verticalAlign: -3, marginRight: 6}} />
              Eğitimi Tamamla
            </button>
          )}

          <h4 style={{margin: '8px 0'}}>Katılımcılar ({detail.participants?.length || 0})</h4>
          <div style={{overflowX: 'auto'}}>
            <table className="records-table">
              <thead>
                <tr>
                  <th>Sıra</th>
                  <th>Ad Soyad</th>
                  <th>T.C.</th>
                  <th>Görev</th>
                  <th>Bölüm</th>
                  <th>Belge No</th>
                </tr>
              </thead>
              <tbody>
                {participantRows(detail).length ? participantRows(detail).map((p) => (
                  <tr key={p.sira}>
                    <td>{p.sira}</td>
                    <td>{p.name}</td>
                    <td>{p.tc}</td>
                    <td>{p.job}</td>
                    <td>{p.dept}</td>
                    <td>{p.cert}</td>
                  </tr>
                )) : (
                  <tr><td colSpan={6}>Katılımcı yok</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      );
    }

  return (
    <div className="panel-card">
      <div className="section-title" style={{marginBottom: 6}}>Eğitim Kayıtları</div>
      <div style={{marginBottom: 12}}>
        <button
          type="button"
          className="btn-outline-premium"
          style={{width: 'auto', minHeight: 40, padding: '0 14px'}}
          onClick={() => {
            const stamp = new Date().toISOString().slice(0, 10);
            const params = new URLSearchParams();
            if (form.company_id) params.set('company_id', String(form.company_id));
            if (q.trim()) params.set('q', q.trim());
            downloadFile(`/trainings/export.xlsx?${params}`, `egitim-listesi-${stamp}.xlsx`).catch((x) =>
              setErr(x.message || 'Excel indirilemedi.'),
            );
          }}
        >
          <Download size={16} style={{marginRight: 6}} /> Excel Rapor
        </button>
      </div>
      <h2 style={{margin: '0 0 12px', fontSize: 20}}>Kayıtlı oturumlar</h2>
        <div style={{display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap'}}>
          <div style={{flex: 1, minWidth: 200, display: 'flex', alignItems: 'center', gap: 8}}>
            <Search size={18} style={{opacity: 0.5}} />
            <input
              className="tp-input"
              placeholder="Eğitim, eğitici veya sektör ara..."
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && load().catch((x) => setErr(x.message))}
            />
          </div>
          <button
            type="button"
            className="btn-outline-premium"
            style={{width: 'auto', minHeight: 48, padding: '0 18px'}}
            onClick={() => load().catch((x) => setErr(x.message))}
          >
            Ara
          </button>
        </div>
        {err && <div className="tp-alert err">{err}</div>}
        <div style={{overflowX: 'auto'}}>
          <table className="records-table">
            <thead>
              <tr>
                <th>Eğitim</th>
                <th>Firma</th>
                <th>Tarih</th>
                <th>Tehlike</th>
                <th>Saat</th>
                <th>Katılımcı</th>
                <th>Durum</th>
                <th>İşlem</th>
              </tr>
            </thead>
            <tbody>
              {rows.length ? rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.title}</td>
                  <td>{companyName(r.company_id)}</td>
                  <td>{formatTrainingDates(r)}</td>
                  <td>{r.hazard_class}</td>
                  <td>{r.duration_hours}</td>
                  <td>{r.participants?.length || 0}</td>
                  <td>{STATUS[r.status] || r.status}</td>
                  <td>
                    <button
                      type="button"
                      className="btn-outline-premium"
                      style={{width: 'auto', minHeight: 36, padding: '0 12px', fontSize: 12}}
                      onClick={() => openDetail(r)}
                    >
                      Belgeler
                    </button>
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={8}>Henüz eğitim kaydı yok.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return (
    <div className="training-pro">
      {busy && (
        <div className="tp-alert" style={{marginBottom: 12, background: '#eef6ff', color: '#1e3a5f', border: '1px solid #bfdbfe'}}>
          Veriler yükleniyor… (ilk açılışta API uyanıyorsa 10–30 sn sürebilir)
        </div>
      )}
      <div className="tp-tabs" role="tablist">
        {visibleTabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={'tp-tab' + (tab === t.id ? ' active' : '')}
            onClick={() => {
              setErr('');
              setOkMsg('');
              if (t.id !== 'kayitlar') setDetail(null);
              if (t.id === 'temel') {
                setSpecialProfileCode('');
                setForm((prev) => ({
                  ...prev,
                  special_duration_hours: null,
                  special_duration_hint: '',
                }));
              }
              setTab(t.id);
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'temel' && renderTemelTab()}
      {tab === 'ozel' && renderOzelTab()}
      {tab === 'yenileme' && renderYenilemeTab()}
      {tab === 'kayitlar' && renderKayitlarTab()}
    </div>
  );
}

/** Kamuya açık eğitim belgesi doğrulama sayfası (?egitim-dogrula=KOD) */
export function TrainingVerifyPage({code, onClose}) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');
  const [input, setInput] = useState(code || '');

  async function run(c) {
    const clean = (c || input || '').trim().toUpperCase();
    if (!clean) {
      setErr('Doğrulama kodu girin.');
      return;
    }
    setErr('');
    setData(null);
    try {
      const base = apiBaseUrl();
      const r = await fetch(`${base}/trainings/verify/${encodeURIComponent(clean)}`);
      const json = await r.json();
      setData(json);
    } catch (x) {
      setErr(x.message || 'Doğrulama yapılamadı.');
    }
  }

  useEffect(() => {
    if (code) run(code);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  return (
    <main className="login-shell">
      <section className="login-card" style={{maxWidth: 520, textAlign: 'left'}}>
        <div className="brand-mark" style={{marginBottom: 8}}><ShieldCheck size={34} /></div>
        <h1 style={{fontSize: 22}}>Eğitim Belgesi Doğrulama</h1>
        <p style={{marginBottom: 16, color: '#64748b'}}>
          İSG Suite — kamuya açık doğrulama (giriş gerekmez)
        </p>
        <label className="field">
          <span>Doğrulama kodu</span>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Örn. A1B2C3D4E5F6G7H8"
          />
        </label>
        <div style={{display: 'flex', gap: 8, marginTop: 12}}>
          <button type="button" onClick={() => run()}>Doğrula</button>
          {onClose && (
            <button type="button" className="secondary" onClick={onClose}>Kapat</button>
          )}
        </div>
        {err && <div className="error" style={{marginTop: 12}}>{err}</div>}
        {data && (
          <div
            style={{
              marginTop: 16,
              padding: 14,
              background: data.valid ? '#ecfdf5' : '#fef2f2',
              borderRadius: 12,
            }}
          >
            <strong style={{color: data.valid ? '#087b67' : '#b91c1c'}}>
              {data.valid ? '✓ Belge doğrulandı' : '✗ Belge bulunamadı'}
            </strong>
            <p style={{margin: '8px 0 0', fontSize: 14}}>{data.message}</p>
            {data.valid && (
              <ul style={{margin: '12px 0 0', paddingLeft: 18, fontSize: 14, lineHeight: 1.6}}>
                <li><strong>Firma:</strong> {data.company_name}</li>
                <li><strong>Eğitim:</strong> {data.title}</li>
                <li>
                  <strong>Tarih:</strong> {formatTrainingDates(data)} · {data.duration_hours} saat ·{' '}
                  {data.hazard_class}
                </li>
                <li><strong>Eğitici:</strong> {data.instructor_name}</li>
                {data.workplace_physician && (
                  <li><strong>İşyeri Hekimi:</strong> {data.workplace_physician}</li>
                )}
                {data.employer_representative && (
                  <li><strong>İşveren:</strong> {data.employer_representative}</li>
                )}
                <li><strong>Katılımcı:</strong> {data.participant_count}</li>
              </ul>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
