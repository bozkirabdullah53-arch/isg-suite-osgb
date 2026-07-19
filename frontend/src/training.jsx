import React, {useEffect, useMemo, useRef, useState} from 'react';
import {Download, Plus, Search, ShieldCheck, Upload, Users, X} from 'lucide-react';
import {api, downloadFile, uploadFile} from './api';

const HAZARD_HINT = {
  'Az Tehlikeli': '8 ders saati · 3 yılda bir yenilenir',
  'Tehlikeli': '12 ders saati · 2 yılda bir yenilenir',
  'Çok Tehlikeli': '16 ders saati · her yıl yenilenir',
};
const STATUS = {planned: 'Planlandı', completed: 'Tamamlandı', cancelled: 'İptal'};

function Modal({title, close, children, wide}) {
  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <section className={'modal' + (wide ? ' wide' : '')}>
        <header>
          <h3>{title}</h3>
          <button className="icon" type="button" onClick={close}><X /></button>
        </header>
        <div className="modal-body">{children}</div>
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

async function loadSectorsCatalog() {
  const host =
    typeof window !== 'undefined' &&
    (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');
  const base =
    import.meta.env.VITE_API_URL ||
    (host ? `${window.location.protocol}//${window.location.hostname}:8000/api/v1` : 'https://isg-suite-api-1u9t.onrender.com/api/v1');

  // 1) Yeni API /sectors
  try {
    const r = await fetch(`${base}/trainings/sectors`);
    if (r.ok) {
      const data = await r.json();
      if (Array.isArray(data) && data.length > 10) return data;
    }
  } catch (_) { /* ignore */ }
  // 2) Auth’lu meta
  try {
    const meta = await api('/trainings/meta');
    if (meta?.sectors?.length > 10) return meta.sectors;
  } catch (_) { /* ignore */ }
  // 3) Statik paket
  const local = await fetch('/training-sectors.json').then((r) => r.json());
  return Array.isArray(local) ? local : [];
}

function sectorLabel(sectors, code) {
  const s = sectors.find((x) => x.code === code || x.name === code || x.label === code);
  return s ? (s.label || s.name) : code || '—';
}

export function TrainingPage({user}) {
  const canEdit = ['global_admin', 'company_admin', 'safety_specialist'].includes(user.role);
  const empty = {
    company_id: user.company_id || '',
    title: '',
    training_type: 'İlk Defa',
    delivery_method: 'Yüz yüze',
    location: '',
    start_date: '',
    hazard_class: 'Çok Tehlikeli',
    sector: 'genel_uretim',
    instructor_name: '',
    instructor_qualification: '',
    workplace_physician: '',
    employer_representative: '',
    stamp_text: '6331 sayılı İş Sağlığı ve Güvenliği Kanunu ve Çalışanların İş Sağlığı ve Güvenliği Eğitimlerinin Usul ve Esasları Hakkında Yönetmelik kapsamında düzenlenmiştir.',
    evaluation_method: 'Sınav',
    passing_score: '',
    attendance_verified: true,
    success_verified: true,
    notes: '',
    participant_ids: [],
  };

  const [companies, setCompanies] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [sectors, setSectors] = useState([]);
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [form, setForm] = useState(empty);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [excelInfo, setExcelInfo] = useState('');
  const [excelPreview, setExcelPreview] = useState([]);
  const [detail, setDetail] = useState(null);
  const [dlBusy, setDlBusy] = useState('');
  const [docForm, setDocForm] = useState({workplace_physician: '', employer_representative: '', stamp_text: ''});
  const [verifyPreview, setVerifyPreview] = useState(null);
  const excelInputRef = useRef(null);

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

  function defaultCompanyId(list = companies) {
    if (user.company_id) return String(user.company_id);
    if (list.length === 1) return String(list[0].id);
    return '';
  }

  function openNewTraining() {
    setErr('');
    setExcelInfo('');
    setExcelPreview([]);
    const cid = defaultCompanyId() || (companies[0] ? String(companies[0].id) : '');
    setForm({...empty, company_id: cid});
    setOpen(true);
    if (cid) {
      refreshEmployees(cid).catch(() => {});
    }
  }

  async function refreshEmployees(companyId) {
    const cid = companyId || form.company_id;
    const path = cid
      ? `/employees?company_id=${Number(cid)}&active=true`
      : '/employees';
    const list = await api(path);
    setEmployees(Array.isArray(list) ? list : []);
    return Array.isArray(list) ? list : [];
  }

  const filteredSectors = useMemo(() => {
    const list = [...sectors].sort((a, b) =>
      String(a.label || a.name || '').localeCompare(String(b.label || b.name || ''), 'tr'),
    );
    // Tehlike sınıfına göre önerilenler üstte; hepsi listede kalır
    return list.sort((a, b) => {
      const ah = a.hazard_class === form.hazard_class ? 0 : 1;
      const bh = b.hazard_class === form.hazard_class ? 0 : 1;
      if (ah !== bh) return ah - bh;
      return String(a.label || a.name || '').localeCompare(String(b.label || b.name || ''), 'tr');
    });
  }, [sectors, form.hazard_class]);

  const selectedSector = useMemo(
    () => sectors.find((s) => s.code === form.sector),
    [sectors, form.sector],
  );

  const load = async () => {
    const [c, e, t, sec] = await Promise.all([
      api('/companies'),
      api('/employees'),
      api('/trainings' + (q ? `?q=${encodeURIComponent(q)}` : '')),
      loadSectorsCatalog(),
    ]);
    setCompanies(c);
    setEmployees(e);
    setRows(t);
    setSectors(sec);
  };

  useEffect(() => {
    load().catch((x) => setErr(x.message));
  }, []);

  async function save(e) {
    e.preventDefault();
    setErr('');
    if (!form.company_id) {
      setErr('Firma seçiniz. Uzman yalnızca görevlendirildiği işyerleri için eğitim açabilir.');
      return;
    }
    if (!form.participant_ids.length) {
      setErr('Katılımcı seçin: Excel yükleyin (.xlsx) veya ortak personel listesinden seçin.');
      return;
    }
    setBusy(true);
    try {
      await api('/trainings', {
        method: 'POST',
        body: JSON.stringify({
          company_id: Number(form.company_id),
          title: form.title.trim(),
          training_type: form.training_type,
          delivery_method: form.delivery_method,
          location: form.location || null,
          start_date: form.start_date,
          hazard_class: form.hazard_class,
          sector: form.sector || 'genel_uretim',
          instructor_name: form.instructor_name.trim(),
          instructor_qualification: form.instructor_qualification || null,
          workplace_physician: form.workplace_physician.trim() || null,
          employer_representative: form.employer_representative.trim() || null,
          stamp_text: form.stamp_text.trim() || null,
          evaluation_method: form.evaluation_method,
          passing_score: form.passing_score === '' ? null : Number(form.passing_score),
          attendance_verified: !!form.attendance_verified,
          success_verified: !!form.success_verified,
          notes: form.notes || null,
          participant_ids: form.participant_ids.map(Number),
        }),
      });
      setOpen(false);
      setExcelInfo('');
      setExcelPreview([]);
      setForm({...empty, company_id: form.company_id || defaultCompanyId()});
      await load();
    } catch (x) {
      setErr(x.message);
    } finally {
      setBusy(false);
    }
  }

  async function complete(id) {
    try {
      await api(`/trainings/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({status: 'completed', attendance_verified: true, success_verified: true}),
      });
      await load();
    } catch (x) {
      alert(x.message);
    }
  }

  async function downloadAttendance(id) {
    setDlBusy('attendance-' + id);
    try {
      await downloadFile(`/trainings/${id}/attendance.pdf`, `egitim-${id}-katilimci-imza-formu.pdf`);
    } catch (x) {
      alert('İmza / yoklama PDF indirilemedi:\n' + x.message);
    } finally {
      setDlBusy('');
    }
  }

  async function downloadCertificates(id) {
    setDlBusy('certs-' + id);
    try {
      await downloadFile(`/trainings/${id}/certificates.pdf`, `egitim-${id}-katilim-belgeleri.pdf`);
    } catch (x) {
      const msg = x.message || '';
      if (/not found/i.test(msg) || msg === 'Not Found') {
        alert(
          'Katılım belgesi PDF indirilemedi: API sürümü eski (certificates.pdf yok).\n\n'
          + 'Render’da isg-suite-api için Clear build cache & Deploy yapın.\n'
          + 'Deploy sonrası tehlike sınıfı + sektör seçimine göre 4. bölüm konuları belgede basılır.',
        );
      } else {
        alert('Katılım belgesi PDF indirilemedi:\n' + msg);
      }
    } finally {
      setDlBusy('');
    }
  }

  function openDetail(row) {
    setDetail(row);
    setDocForm({
      workplace_physician: row.workplace_physician || '',
      employer_representative: row.employer_representative || '',
      stamp_text: row.stamp_text || '6331 sayılı İş Sağlığı ve Güvenliği Kanunu ve Çalışanların İş Sağlığı ve Güvenliği Eğitimlerinin Usul ve Esasları Hakkında Yönetmelik kapsamında düzenlenmiştir.',
    });
    setVerifyPreview(null);
  }

  function verifyUrl(code) {
    if (!code) return '';
    const origin = typeof window !== 'undefined' ? window.location.origin : '';
    return `${origin}/?egitim-dogrula=${encodeURIComponent(code)}`;
  }

  async function saveDocFields() {
    if (!detail) return;
    setBusy(true);
    setErr('');
    try {
      const updated = await api(`/trainings/${detail.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          workplace_physician: docForm.workplace_physician.trim() || null,
          employer_representative: docForm.employer_representative.trim() || null,
          stamp_text: docForm.stamp_text.trim() || null,
        }),
      });
      setDetail(updated);
      setRows((list) => list.map((r) => (r.id === updated.id ? updated : r)));
    } catch (x) {
      setErr(x.message);
    } finally {
      setBusy(false);
    }
  }

  async function onLogo(e) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file || !detail) return;
    setBusy(true);
    try {
      const updated = await uploadFile(`/trainings/${detail.id}/logo`, file);
      setDetail(updated);
      setRows((list) => list.map((r) => (r.id === updated.id ? updated : r)));
    } catch (x) {
      alert('Logo yüklenemedi:\n' + x.message);
    } finally {
      setBusy(false);
    }
  }

  async function checkVerify() {
    if (!detail?.verification_code) return;
    setBusy(true);
    try {
      const host =
        typeof window !== 'undefined' &&
        (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');
      const base =
        import.meta.env.VITE_API_URL ||
        (host ? `${window.location.protocol}//${window.location.hostname}:8000/api/v1` : 'https://isg-suite-api-1u9t.onrender.com/api/v1');
      const r = await fetch(`${base}/trainings/verify/${detail.verification_code}`);
      const data = await r.json();
      setVerifyPreview(data);
    } catch (x) {
      setVerifyPreview({valid: false, message: x.message});
    } finally {
      setBusy(false);
    }
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

  function pickExcel() {
    setErr('');
    if (!form.company_id) {
      setErr('Excel yüklemek için önce Firma seçiniz.');
      return;
    }
    excelInputRef.current?.click();
  }

  async function onExcel(e) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    if (!form.company_id) {
      setErr('Önce firma seçiniz. Uzman yalnızca görevlendirildiği işyerine Excel yükleyebilir.');
      return;
    }
    const name = (file.name || '').toLowerCase();
    if (name.endsWith('.xls') && !name.endsWith('.xlsx') && !name.endsWith('.xlsm')) {
      setErr('Eski .xls desteklenmez. Excel’de .xlsx olarak kaydedip tekrar yükleyin.');
      return;
    }
    setErr('');
    setBusy(true);
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
      // Önce seçimi yaz — personel listesi yenilenmesi başarısız olsa bile kayıt mümkün olsun
      setForm((f) => ({...f, participant_ids: ids}));
      setExcelPreview(preview);
      setExcelInfo(
        `Excel: ${out.count || ids.length} kişi · ${out.created || 0} yeni personel · ${ids.length} seçildi`,
      );
      try {
        await refreshEmployees(form.company_id);
      } catch (_) {
        /* liste yenileme opsiyonel */
      }
      if (!ids.length) {
        setErr(
          'Excel okundu ama personel seçilemedi. Sütun: Ad Soyad (veya Adı + Soyadı). Dosya .xlsx olmalı.',
        );
      }
    } catch (x) {
      setErr('Excel yüklenemedi: ' + (x.message || 'Bilinmeyen hata'));
    } finally {
      setBusy(false);
    }
  }

  async function selectAllEmployees() {
    setErr('');
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
          'Bu firmada aktif personel yok. PC’den Excel yükleyin veya Personel menüsünden ekleyin (PRO ortak liste gibi).',
        );
        return;
      }
      setExcelPreview([]);
      setForm((f) => ({...f, participant_ids: active.map((e) => e.id)}));
      setExcelInfo(`${active.length} kişi ortak personel listesinden seçildi`);
    } catch (x) {
      setErr('Personel listesi alınamadı: ' + x.message);
    } finally {
      setBusy(false);
    }
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

  const companyName = (id) => companies.find((c) => c.id === id)?.name || id;

  const cols = [
    {key: 'title', label: 'Eğitim'},
    {key: 'company_id', label: 'Firma', render: (r) => companyName(r.company_id)},
    {key: 'start_date', label: 'Tarih'},
    {key: 'hazard_class', label: 'Tehlike'},
    {key: 'duration_hours', label: 'Saat'},
    {key: 'instructor_name', label: 'Eğitici'},
    {key: 'participants', label: 'Katılımcı', render: (r) => r.participants?.length || 0},
    {
      key: 'status',
      label: 'Durum',
      render: (r) => (
        <span className={'badge ' + (r.status === 'completed' ? 'ok' : 'off')}>
          {STATUS[r.status] || r.status}
        </span>
      ),
    },
    {
      key: 'action',
      label: 'İşlem',
      render: (r) => (
        <div className="actions" style={{flexWrap: 'wrap'}}>
          <button className="mini" type="button" onClick={() => openDetail(r)}>
            Belgeler
          </button>
          {canEdit && r.status !== 'completed' && (
            <button className="mini" type="button" onClick={() => complete(r.id)}>Tamamla</button>
          )}
        </div>
      ),
    },
  ];

  return (
    <>
      <div className="page-title">
        <h3>Eğitim Yönetimi</h3>
        {canEdit && (
          <button type="button" onClick={openNewTraining}>
            <Plus /> Yeni Eğitim
          </button>
        )}
      </div>
      {detail ? (
        <section className="panel doc-workspace">
          <div className="doc-head">
            <div>
              <h3>{detail.title} — Belge Üretim Merkezi</h3>
              <p style={{margin: '6px 0 0', color: '#64748b', fontSize: 14}}>
                Uygulama içinde kalın · PRO uyumlu imza formu + katılım belgesi (konular dahil)
              </p>
            </div>
            <button type="button" className="secondary" onClick={() => setDetail(null)}>Listeye dön</button>
          </div>

          <div style={{display: 'grid', gap: 14}}>
            <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, fontSize: 14}}>
              <div><span style={{color: '#64748b'}}>Firma</span><div><strong>{companyName(detail.company_id)}</strong></div></div>
              <div><span style={{color: '#64748b'}}>Tarih</span><div><strong>{detail.start_date}</strong></div></div>
              <div><span style={{color: '#64748b'}}>Tehlike / Süre</span><div><strong>{detail.hazard_class} · {detail.duration_hours} saat</strong></div></div>
              <div><span style={{color: '#64748b'}}>Eğitici</span><div><strong>{detail.instructor_name}</strong></div></div>
              <div><span style={{color: '#64748b'}}>Sektör</span><div><strong>{sectorLabel(sectors, detail.sector)}</strong></div></div>
              <div><span style={{color: '#64748b'}}>Doğrulama</span><div><strong>{detail.verification_code || '—'}</strong></div></div>
            </div>

            <div>
              <strong style={{fontSize: 14}}>Belgede basılacak konular (4. bölüm — sektöre özgü)</strong>
              <div className="doc-topics">
                <div style={{marginBottom: 6, color: '#52677a'}}>
                  1. Genel · 2. Teknik · 3. Sağlık (sabit) + aşağıdaki işyerine özgü konular
                </div>
                {(sectors.find((s) => s.code === detail.sector)?.topics || []).length
                  ? (sectors.find((s) => s.code === detail.sector).topics).map((t, i) => (
                    <div key={i}>• {t}</div>
                  ))
                  : <div>Sektör konuları yüklenemedi. Yeni eğitimde sektör seçimini kontrol edin.</div>}
              </div>
            </div>

            {canEdit && (
              <div style={{padding: 12, background: '#f8fafc', borderRadius: 10, display: 'grid', gap: 10}}>
                <strong style={{fontSize: 14}}>Belge imza / kaşe alanları</strong>
                <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10}}>
                  <Field label="İşyeri Hekimi" value={docForm.workplace_physician} onChange={(e) => setDocForm({...docForm, workplace_physician: e.target.value})} />
                  <Field label="İşveren / Vekili" value={docForm.employer_representative} onChange={(e) => setDocForm({...docForm, employer_representative: e.target.value})} />
                </div>
                <label className="field">
                  <span>Mevzuat dipnotu (kanun / yönetmelik)</span>
                  <input value={docForm.stamp_text} onChange={(e) => setDocForm({...docForm, stamp_text: e.target.value})} />
                </label>
                <div style={{display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center'}}>
                  <button type="button" className="secondary" disabled={busy} onClick={saveDocFields}>
                    {busy ? 'Kaydediliyor…' : 'İmza alanlarını kaydet'}
                  </button>
                  <label className="button secondary" style={{display: 'inline-flex'}}>
                    <Upload size={16} /> {detail.logo_path ? 'Logoyu değiştir' : 'Logo yükle (PNG/JPG)'}
                    <input type="file" accept=".png,.jpg,.jpeg,.webp" hidden onChange={onLogo} disabled={busy} />
                  </label>
                  <label className="button secondary" style={{display: 'inline-flex'}}>
                    <Upload size={16} /> Excel ile katılımcı ekle
                    <input
                      type="file"
                      accept=".xlsx,.xlsm"
                      hidden
                      disabled={busy}
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        e.target.value = '';
                        if (!file) return;
                        setBusy(true);
                        try {
                          await uploadFile(`/trainings/${detail.id}/upload-participants?create_missing=true`, file);
                          setEmployees(await api('/employees'));
                          const refreshed = await api('/trainings');
                          setRows(refreshed);
                          const row = refreshed.find((x) => x.id === detail.id);
                          if (row) openDetail(row);
                        } catch (x) {
                          alert('Katılımcı yüklenemedi:\n' + x.message);
                        } finally {
                          setBusy(false);
                        }
                      }}
                    />
                  </label>
                  {detail.logo_path && <span style={{fontSize: 12, color: '#087b67'}}>Logo kayıtlı</span>}
                </div>
              </div>
            )}

            {detail.verification_code && (
              <div style={{padding: 12, background: '#eef5fb', borderRadius: 10, fontSize: 13, lineHeight: 1.55}}>
                <strong>Doğrulama linki (paylaşılabilir):</strong>{' '}
                <code style={{userSelect: 'all'}}>{verifyUrl(detail.verification_code)}</code>
                <div style={{marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap'}}>
                  <button type="button" className="secondary" onClick={() => navigator.clipboard?.writeText(verifyUrl(detail.verification_code))}>
                    Linki kopyala
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => window.open(verifyUrl(detail.verification_code), '_blank', 'noopener,noreferrer')}
                  >
                    Yeni sekmede aç
                  </button>
                  <button type="button" className="secondary" disabled={busy} onClick={checkVerify}>
                    Doğrulamayı test et
                  </button>
                </div>
                <p style={{margin: '8px 0 0', fontSize: 12, color: '#64748b'}}>
                  Linki aynı sekmede açmayın — girişliyken sol menü bozulmasın diye paylaşım yeni sekmede / kopyala ile yapılır.
                </p>
                {verifyPreview && (
                  <div style={{marginTop: 10, padding: 10, background: '#fff', borderRadius: 8}}>
                    {verifyPreview.valid ? (
                      <>
                        <div style={{color: '#087b67', fontWeight: 600}}>✓ {verifyPreview.message}</div>
                        <div>{verifyPreview.company_name} · {verifyPreview.title}</div>
                        <div>{verifyPreview.participant_count} katılımcı · {verifyPreview.start_date}</div>
                      </>
                    ) : (
                      <div className="error">{verifyPreview.message || 'Doğrulanamadı'}</div>
                    )}
                  </div>
                )}
              </div>
            )}

            {!(detail.participants?.length) && (
              <div className="error">
                Katılımcı yok. Yukarıdan Excel yükleyin veya yeni eğitim oluştururken personel seçin.
              </div>
            )}

            <div style={{display: 'flex', gap: 10, flexWrap: 'wrap'}}>
              <button
                type="button"
                disabled={!detail.participants?.length || !!dlBusy}
                onClick={() => downloadAttendance(detail.id)}
              >
                <Download size={16} /> {dlBusy === 'attendance-' + detail.id ? 'İndiriliyor…' : 'İmza / Yoklama Formu PDF'}
              </button>
              <button
                type="button"
                disabled={!detail.participants?.length || !!dlBusy}
                onClick={() => downloadCertificates(detail.id)}
              >
                <Download size={16} /> {dlBusy === 'certs-' + detail.id ? 'İndiriliyor…' : 'Katılım Belgesi PDF (konular dahil)'}
              </button>
            </div>

            <div>
              <h4 style={{margin: '4px 0 8px'}}>Katılımcı listesi ({detail.participants?.length || 0})</h4>
              <div className="table-wrap">
                <table>
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
                      <tr><td colSpan={6} className="empty">Katılımcı yok</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>
      ) : (
      <section className="panel">
        <div style={{marginBottom: 14, padding: '12px 14px', background: '#eef5fb', borderRadius: 10, fontSize: 14, lineHeight: 1.55, color: '#243447'}}>
          <strong>Bakanlık denetimi için zorunlu belgeler:</strong>{' '}
          satırdan <strong>Belgeler</strong> açın → imza formu ve katılım belgesi PDF indirin.
          Belge ekranı uygulama içinde açılır; konular orada görünür.
        </div>
        <div className="search">
          <Search size={19} />
          <input
            placeholder="Eğitim, eğitici veya sektör ara..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && load()}
          />
          <button className="secondary" type="button" onClick={() => load().catch((x) => setErr(x.message))}>Ara</button>
        </div>
        {err && !open && <div className="error">{err}</div>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>{cols.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
            </thead>
            <tbody>
              {rows.length ? rows.map((r) => (
                <tr key={r.id}>
                  {cols.map((c) => (
                    <td key={c.key}>{c.render ? c.render(r) : String(r[c.key] ?? '—')}</td>
                  ))}
                </tr>
              )) : (
                <tr><td colSpan={cols.length} className="empty">Henüz eğitim kaydı yok. Yeni Eğitim ile katılımcılı kayıt oluşturun.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
      )}

      {open && (
        <Modal title="Yeni Eğitim Oturumu" close={() => setOpen(false)}>
          <form className="form-grid" onSubmit={save}>
            <Select
              label="Firma (görevlendirildiğiniz işyerleri)"
              required
              value={form.company_id}
              onChange={(e) => {
                setExcelPreview([]);
                setExcelInfo('');
                setErr('');
                const cid = e.target.value;
                setForm({...form, company_id: cid, participant_ids: []});
                if (cid) {
                  refreshEmployees(cid).catch((x) =>
                    setErr('Personel listesi alınamadı: ' + (x.message || x)),
                  );
                } else {
                  setEmployees([]);
                }
              }}
            >
              <option value="">Seçiniz</option>
              {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
            {!companies.length && (
              <div style={{gridColumn: '1 / -1', fontSize: 13, color: '#9a3412', background: '#fff7ed', padding: '10px 12px', borderRadius: 8}}>
                Listede işyeri yok. Global yönetici <strong>Görevlendirmeler</strong>’den size firma atamalı.
                Ayrıca <strong>İSG Profesyonelleri</strong> kaydınızın e-postası, giriş yaptığınız kullanıcı e-postası ile aynı olmalı.
              </div>
            )}
            <Field label="Eğitim Adı" required minLength={3} value={form.title} onChange={(e) => setForm({...form, title: e.target.value})} />
            <Select label="Eğitim Türü" value={form.training_type} onChange={(e) => setForm({...form, training_type: e.target.value})}>
              <option>İlk Defa</option>
              <option>Tekrar</option>
              <option>Temel İSG Eğitimi</option>
              <option>İşe Özel Eğitim</option>
              <option>Yenileme Eğitimi</option>
              <option>Acil Durum / Tatbikat</option>
            </Select>
            <Select label="Eğitim Şekli" value={form.delivery_method} onChange={(e) => setForm({...form, delivery_method: e.target.value})}>
              <option>Yüz yüze</option>
              <option>Uzaktan</option>
            </Select>
            <Field label="Eğitim Tarihi" type="date" required value={form.start_date} onChange={(e) => setForm({...form, start_date: e.target.value})} />
            <Field label="Eğitim Yeri" value={form.location} onChange={(e) => setForm({...form, location: e.target.value})} />
            <Select label="Tehlike Sınıfı" value={form.hazard_class} onChange={(e) => setForm({...form, hazard_class: e.target.value})}>
              <option>Az Tehlikeli</option>
              <option>Tehlikeli</option>
              <option>Çok Tehlikeli</option>
            </Select>
            <label className="field">
              <span>Süre / Yenileme (otomatik)</span>
              <input readOnly value={HAZARD_HINT[form.hazard_class] || ''} />
            </label>
            <Select
              label={`Sektör / İş Kolu — A→Z (${filteredSectors.length} sektör, belge konuları)`}
              value={form.sector}
              onChange={(e) => setForm({...form, sector: e.target.value})}
            >
              {filteredSectors.length === 0 && <option value="genel_uretim">Yükleniyor…</option>}
              {filteredSectors.map((s) => (
                <option key={s.code} value={s.code}>
                  {(s.label || s.name)} [{s.hazard_class || '—'}]
                </option>
              ))}
            </Select>
            <label className="field" style={{gridColumn: '1 / -1'}}>
              <span>Bu sektörün belge konuları (4. bölüm — Çalışma Bakanlığı)</span>
              <div style={{marginTop: 8, padding: 12, background: '#f4f7fb', borderRadius: 12, fontSize: 13, lineHeight: 1.5}}>
                {(selectedSector?.topics || []).length
                  ? (selectedSector.topics).map((t, i) => <div key={i}>• {t}</div>)
                  : 'Sektör seçildiğinde konular burada görünür. Belge PDF’te genel+teknik+sağlık+bu konular basılır.'}
              </div>
            </label>
            <Field label="Eğitici Ad Soyad" required minLength={3} value={form.instructor_name} onChange={(e) => setForm({...form, instructor_name: e.target.value})} />
            <Field label="Eğitici Yeterlilik / Unvan" value={form.instructor_qualification} onChange={(e) => setForm({...form, instructor_qualification: e.target.value})} />
            <Field label="İşyeri Hekimi (belge imza)" value={form.workplace_physician} onChange={(e) => setForm({...form, workplace_physician: e.target.value})} placeholder="Ad Soyad" />
            <Field label="İşveren / Vekili (belge imza)" value={form.employer_representative} onChange={(e) => setForm({...form, employer_representative: e.target.value})} placeholder="Ad Soyad" />
            <label className="field" style={{gridColumn: '1 / -1'}}>
              <span>Mevzuat dipnotu (kanun / yönetmelik)</span>
              <input value={form.stamp_text} onChange={(e) => setForm({...form, stamp_text: e.target.value})} />
            </label>
            <Select label="Başarı Değerlendirme" value={form.evaluation_method} onChange={(e) => setForm({...form, evaluation_method: e.target.value})}>
              <option>Sınav</option>
              <option>Uygulama</option>
              <option>Sözlü değerlendirme</option>
              <option>Katılım yeterlidir</option>
            </Select>
            <Field label="Geçme Puanı (0-100)" type="number" min="0" max="100" value={form.passing_score} onChange={(e) => setForm({...form, passing_score: e.target.value})} />

            <div style={{gridColumn: '1 / -1', display: 'grid', gap: 12}}>
              <div style={{fontWeight: 700, color: '#243447'}}>Katılımcı kaynağı (PRO 2026 gibi)</div>
              <div
                role="button"
                tabIndex={0}
                onClick={pickExcel}
                onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && pickExcel()}
                style={{
                  border: '2px dashed #9bb8c2',
                  borderRadius: 14,
                  padding: '18px 16px',
                  background: '#f7fbfc',
                  cursor: busy ? 'wait' : 'pointer',
                  textAlign: 'center',
                }}
              >
                <div style={{display: 'inline-flex', alignItems: 'center', gap: 8, fontWeight: 700, color: '#0f766e'}}>
                  <Upload size={20} /> PC’den Excel Yükle (.xlsx / .xlsm)
                </div>
                <div style={{marginTop: 6, fontSize: 13, color: '#5b7380'}}>
                  Ad Soyad zorunlu · TC Kimlik, Branş/Görev, Bölüm önerilir
                  {!form.company_id ? ' · önce Firma seçin' : ''}
                </div>
                <input
                  ref={excelInputRef}
                  type="file"
                  accept=".xlsx,.xlsm"
                  hidden
                  onChange={onExcel}
                />
              </div>
              <div style={{display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center'}}>
                <button type="button" className="secondary" disabled={busy} onClick={selectAllEmployees}>
                  <Users size={16} /> Ortak personel listesinin tamamını seç
                  {form.company_id ? ` (${companyEmployees.length})` : ''}
                </button>
                {excelInfo && <span style={{fontSize: 13, color: '#087b67'}}>{excelInfo}</span>}
              </div>
              {!form.company_id && (
                <div style={{fontSize: 13, color: '#9a3412', background: '#fff7ed', padding: '8px 10px', borderRadius: 8}}>
                  Firma seçmeden Excel / ortak liste çalışmaz. Uzman yalnızca görevlendirildiği işyerlerini görür.
                </div>
              )}
            </div>

            <label className="field" style={{gridColumn: '1 / -1'}}>
              <span>Katılımcılar ({form.participant_ids.length} seçili)</span>
              <div className="check-grid" style={{maxHeight: 220, overflow: 'auto', marginTop: 8}}>
                {companyEmployees.length ? companyEmployees.map((emp) => (
                  <label key={emp.id} style={{display: 'flex', gap: 8, alignItems: 'center'}}>
                    <input
                      type="checkbox"
                      checked={form.participant_ids.includes(emp.id) || form.participant_ids.includes(Number(emp.id))}
                      onChange={() => toggleParticipant(emp.id)}
                    />
                    <span>{emp.full_name}{emp.job_title ? ` — ${emp.job_title}` : ''}</span>
                  </label>
                )) : excelPreview.length ? (
                  excelPreview.map((p, i) => (
                    <div key={i} style={{fontSize: 13, color: '#334155'}}>
                      • {p.name}{p.job ? ` — ${p.job}` : ''}
                    </div>
                  ))
                ) : (
                  <span className="empty">
                    Personel yok. Excel yükleyin veya Ortak personel listesini kullanın (önce Personel menüsünden eklenmiş olmalı).
                  </span>
                )}
              </div>
            </label>
            <label className="field">
              <span><input type="checkbox" checked={form.attendance_verified} onChange={(e) => setForm({...form, attendance_verified: e.target.checked})} /> Katılım doğrulandı</span>
            </label>
            <label className="field">
              <span><input type="checkbox" checked={form.success_verified} onChange={(e) => setForm({...form, success_verified: e.target.checked})} /> Başarı doğrulandı</span>
            </label>
            {err && <div className="error" style={{gridColumn: '1 / -1'}}>{err}</div>}
            <div className="form-actions">
              <button type="submit" disabled={busy}>{busy ? 'Kaydediliyor...' : 'Kaydet'}</button>
            </div>
          </form>
        </Modal>
      )}
    </>
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
      const host =
        typeof window !== 'undefined' &&
        (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');
      const base =
        import.meta.env.VITE_API_URL ||
        (host ? `${window.location.protocol}//${window.location.hostname}:8000/api/v1` : 'https://isg-suite-api-1u9t.onrender.com/api/v1');
      const r = await fetch(`${base}/trainings/verify/${encodeURIComponent(clean)}`);
      const json = await r.json();
      setData(json);
    } catch (x) {
      setErr(x.message || 'Doğrulama yapılamadı.');
    }
  }

  useEffect(() => {
    if (code) run(code);
  }, [code]);

  return (
    <main className="login-shell">
      <section className="login-card" style={{maxWidth: 520, textAlign: 'left'}}>
        <div className="brand-mark" style={{marginBottom: 8}}><ShieldCheck size={34} /></div>
        <h1 style={{fontSize: 22}}>Eğitim Belgesi Doğrulama</h1>
        <p style={{marginBottom: 16, color: '#64748b'}}>İSG Suite — kamuya açık doğrulama (giriş gerekmez)</p>
        <label className="field">
          <span>Doğrulama kodu</span>
          <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Örn. A1B2C3D4E5F6G7H8" />
        </label>
        <div style={{display: 'flex', gap: 8, marginTop: 12}}>
          <button type="button" onClick={() => run()}>Doğrula</button>
          {onClose && <button type="button" className="secondary" onClick={onClose}>Kapat</button>}
        </div>
        {err && <div className="error" style={{marginTop: 12}}>{err}</div>}
        {data && (
          <div style={{marginTop: 16, padding: 14, background: data.valid ? '#ecfdf5' : '#fef2f2', borderRadius: 12}}>
            <strong style={{color: data.valid ? '#087b67' : '#b91c1c'}}>
              {data.valid ? '✓ Belge doğrulandı' : '✗ Belge bulunamadı'}
            </strong>
            <p style={{margin: '8px 0 0', fontSize: 14}}>{data.message}</p>
            {data.valid && (
              <ul style={{margin: '12px 0 0', paddingLeft: 18, fontSize: 14, lineHeight: 1.6}}>
                <li><strong>Firma:</strong> {data.company_name}</li>
                <li><strong>Eğitim:</strong> {data.title}</li>
                <li><strong>Tarih:</strong> {data.start_date} · {data.duration_hours} saat · {data.hazard_class}</li>
                <li><strong>Eğitici:</strong> {data.instructor_name}</li>
                {data.workplace_physician && <li><strong>İşyeri Hekimi:</strong> {data.workplace_physician}</li>}
                {data.employer_representative && <li><strong>İşveren:</strong> {data.employer_representative}</li>}
                <li><strong>Katılımcı:</strong> {data.participant_count}</li>
              </ul>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
