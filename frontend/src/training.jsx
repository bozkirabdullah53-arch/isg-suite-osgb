import React, {useEffect, useMemo, useState} from 'react';
import {Download, Plus, Search, Upload, X} from 'lucide-react';
import {api, downloadFile, uploadFile} from './api';

const HAZARD_HINT = {
  'Az Tehlikeli': '8 ders saati · 3 yılda bir yenilenir',
  'Tehlikeli': '12 ders saati · 2 yılda bir yenilenir',
  'Çok Tehlikeli': '16 ders saati · her yıl yenilenir',
};

const STATUS = {planned: 'Planlandı', completed: 'Tamamlandı', cancelled: 'İptal'};

function Modal({title, close, children}) {
  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <section className="modal">
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

export function TrainingPage({user}) {
  const canEdit = ['global_admin', 'company_admin', 'safety_specialist'].includes(user.role);
  const empty = {
    company_id: user.company_id || '',
    title: '',
    training_type: 'Temel İSG Eğitimi',
    delivery_method: 'Yüz yüze',
    location: '',
    start_date: '',
    hazard_class: 'Çok Tehlikeli',
    sector: 'genel_uretim',
    instructor_name: '',
    instructor_qualification: '',
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

  const companyEmployees = useMemo(
    () => employees.filter((e) => String(e.company_id) === String(form.company_id) && e.is_active !== false),
    [employees, form.company_id],
  );

  const load = () =>
    Promise.all([
      api('/companies'),
      api('/employees'),
      api('/trainings' + (q ? `?q=${encodeURIComponent(q)}` : '')),
      api('/trainings/meta'),
    ]).then(([c, e, t, meta]) => {
      setCompanies(c);
      setEmployees(e);
      setRows(t);
      setSectors(meta.sectors || []);
    });

  useEffect(() => {
    load().catch((x) => setErr(x.message));
  }, []);

  async function save(e) {
    e.preventDefault();
    setErr('');
    if (!form.participant_ids.length) {
      setErr('En az bir katılımcı seçin veya Excel yükleyin.');
      return;
    }
    setBusy(true);
    try {
      const payload = {
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
        evaluation_method: form.evaluation_method,
        passing_score: form.passing_score === '' ? null : Number(form.passing_score),
        attendance_verified: !!form.attendance_verified,
        success_verified: !!form.success_verified,
        notes: form.notes || null,
        participant_ids: form.participant_ids.map(Number),
      };
      await api('/trainings', {method: 'POST', body: JSON.stringify(payload)});
      setOpen(false);
      setExcelInfo('');
      setForm({...empty, company_id: form.company_id || user.company_id || ''});
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
    try {
      await downloadFile(`/trainings/${id}/attendance.pdf`, `egitim-${id}-imza-listesi.pdf`);
    } catch (x) {
      alert(x.message);
    }
  }

  async function downloadCertificates(id) {
    try {
      await downloadFile(`/trainings/${id}/certificates.pdf`, `egitim-${id}-katilim-belgeleri.pdf`);
    } catch (x) {
      alert(x.message);
    }
  }

  async function onExcel(e) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    if (!form.company_id) {
      setErr('Önce firma seçiniz.');
      return;
    }
    setErr('');
    setBusy(true);
    try {
      const out = await uploadFile(
        `/trainings/parse-excel?company_id=${Number(form.company_id)}&create_missing=true`,
        file,
      );
      setEmployees(await api('/employees'));
      setForm((f) => ({...f, participant_ids: out.participant_ids || []}));
      setExcelInfo(
        `${out.count} kişi okundu · ${out.matched - (out.created || 0)} eşleşti · ${out.created || 0} yeni personel eklendi`,
      );
    } catch (x) {
      setErr(x.message);
    } finally {
      setBusy(false);
    }
  }

  function toggleParticipant(id) {
    const n = Number(id);
    setForm((f) => ({
      ...f,
      participant_ids: f.participant_ids.includes(n)
        ? f.participant_ids.filter((x) => x !== n)
        : [...f.participant_ids, n],
    }));
  }

  const companyName = (id) => companies.find((c) => c.id === id)?.name || id;

  const cols = [
    {key: 'title', label: 'Eğitim'},
    {key: 'company_id', label: 'Firma', render: (r) => companyName(r.company_id)},
    {key: 'start_date', label: 'Tarih'},
    {key: 'hazard_class', label: 'Tehlike'},
    {key: 'sector', label: 'Sektör'},
    {key: 'duration_hours', label: 'Süre (saat)'},
    {key: 'instructor_name', label: 'Eğitici'},
    {
      key: 'participants',
      label: 'Katılımcı',
      render: (r) => (r.participants ? r.participants.length : 0),
    },
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
        <div className="actions">
          <button className="mini" type="button" onClick={() => downloadAttendance(r.id)} title="İmza listesi">
            <Download size={14} /> İmza PDF
          </button>
          <button className="mini" type="button" onClick={() => downloadCertificates(r.id)} title="Katılım belgeleri">
            <Download size={14} /> Belge PDF
          </button>
          {canEdit && r.status !== 'completed' && (
            <button className="mini" type="button" onClick={() => complete(r.id)}>
              Tamamla
            </button>
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
          <button
            type="button"
            onClick={() => {
              setErr('');
              setExcelInfo('');
              setOpen(true);
            }}
          >
            <Plus /> Yeni Eğitim
          </button>
        )}
      </div>
      <section className="panel">
        <div className="search">
          <Search size={19} />
          <input
            placeholder="Eğitim, eğitici veya sektör ara..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && load()}
          />
          <button className="secondary" type="button" onClick={load}>Ara</button>
        </div>
        {err && !open && <div className="error">{err}</div>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>{cols.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
            </thead>
            <tbody>
              {rows.length ? (
                rows.map((r) => (
                  <tr key={r.id}>
                    {cols.map((c) => (
                      <td key={c.key}>{c.render ? c.render(r) : String(r[c.key] ?? '—')}</td>
                    ))}
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={cols.length} className="empty">Henüz eğitim kaydı yok.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {open && (
        <Modal title="Yeni Eğitim Oturumu" close={() => setOpen(false)}>
          <form className="form-grid" onSubmit={save}>
            <Select
              label="Firma"
              required
              value={form.company_id}
              onChange={(e) => setForm({...form, company_id: e.target.value, participant_ids: []})}
            >
              <option value="">Seçiniz</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </Select>
            <Field
              label="Eğitim Adı"
              required
              minLength={3}
              value={form.title}
              onChange={(e) => setForm({...form, title: e.target.value})}
            />
            <Select
              label="Eğitim Türü"
              value={form.training_type}
              onChange={(e) => setForm({...form, training_type: e.target.value})}
            >
              <option>Temel İSG Eğitimi</option>
              <option>İşe Özel Eğitim</option>
              <option>Yenileme Eğitimi</option>
              <option>Acil Durum / Tatbikat</option>
            </Select>
            <Select
              label="Eğitim Şekli"
              value={form.delivery_method}
              onChange={(e) => setForm({...form, delivery_method: e.target.value})}
            >
              <option>Yüz yüze</option>
              <option>Uzaktan</option>
              <option>Hibrit</option>
            </Select>
            <Field
              label="Eğitim Tarihi"
              type="date"
              required
              value={form.start_date}
              onChange={(e) => setForm({...form, start_date: e.target.value})}
            />
            <Field
              label="Eğitim Yeri"
              value={form.location}
              onChange={(e) => setForm({...form, location: e.target.value})}
            />
            <Select
              label="Tehlike Sınıfı"
              value={form.hazard_class}
              onChange={(e) => setForm({...form, hazard_class: e.target.value})}
            >
              <option>Az Tehlikeli</option>
              <option>Tehlikeli</option>
              <option>Çok Tehlikeli</option>
            </Select>
            <label className="field">
              <span>Süre / Yenileme (otomatik)</span>
              <input readOnly value={HAZARD_HINT[form.hazard_class] || ''} />
            </label>
            <Select
              label="Sektör / İş Kolu (belge konuları)"
              value={form.sector}
              onChange={(e) => setForm({...form, sector: e.target.value})}
            >
              {(sectors.length ? sectors : [{code: 'genel_uretim', label: 'Genel Fabrika / Üretim'}]).map((s) => (
                <option key={s.code} value={s.code}>{s.label}</option>
              ))}
            </Select>
            <Field
              label="Eğitici Ad Soyad"
              required
              minLength={3}
              value={form.instructor_name}
              onChange={(e) => setForm({...form, instructor_name: e.target.value})}
            />
            <Field
              label="Eğitici Yeterlilik / Unvan"
              value={form.instructor_qualification}
              onChange={(e) => setForm({...form, instructor_qualification: e.target.value})}
            />
            <Select
              label="Başarı Değerlendirme"
              value={form.evaluation_method}
              onChange={(e) => setForm({...form, evaluation_method: e.target.value})}
            >
              <option>Sınav</option>
              <option>Uygulama</option>
              <option>Sözlü değerlendirme</option>
              <option>Katılım yeterlidir</option>
            </Select>
            <Field
              label="Geçme Puanı (0-100)"
              type="number"
              min="0"
              max="100"
              value={form.passing_score}
              onChange={(e) => setForm({...form, passing_score: e.target.value})}
            />

            <label className="field" style={{gridColumn: '1 / -1'}}>
              <span>Excel çalışan listesi (.xlsx)</span>
              <label className="button secondary" style={{display: 'inline-flex', width: 'fit-content', marginTop: 8}}>
                <Upload size={16} /> Excel Yükle
                <input type="file" accept=".xlsx,.xlsm" hidden onChange={onExcel} disabled={busy || !form.company_id} />
              </label>
              {excelInfo && <div className="form-text" style={{marginTop: 8}}>{excelInfo}</div>}
            </label>

            <label className="field" style={{gridColumn: '1 / -1'}}>
              <span>Katılımcılar ({form.participant_ids.length} seçili)</span>
              <div className="check-grid" style={{maxHeight: 160, overflow: 'auto', marginTop: 8}}>
                {companyEmployees.length ? (
                  companyEmployees.map((emp) => (
                    <label key={emp.id} style={{display: 'flex', gap: 8, alignItems: 'center'}}>
                      <input
                        type="checkbox"
                        checked={form.participant_ids.includes(emp.id)}
                        onChange={() => toggleParticipant(emp.id)}
                      />
                      <span>{emp.full_name}{emp.job_title ? ` — ${emp.job_title}` : ''}</span>
                    </label>
                  ))
                ) : (
                  <span className="empty">Personel yok — Excel yükleyin veya Personel menüsünden ekleyin.</span>
                )}
              </div>
            </label>
            <label className="field">
              <span>
                <input
                  type="checkbox"
                  checked={form.attendance_verified}
                  onChange={(e) => setForm({...form, attendance_verified: e.target.checked})}
                />{' '}
                Katılım doğrulandı
              </span>
            </label>
            <label className="field">
              <span>
                <input
                  type="checkbox"
                  checked={form.success_verified}
                  onChange={(e) => setForm({...form, success_verified: e.target.checked})}
                />{' '}
                Başarı doğrulandı
              </span>
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
