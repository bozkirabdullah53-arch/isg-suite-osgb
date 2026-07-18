import React, {useEffect, useMemo, useState} from 'react';
import {Download, Plus, Search, Upload, Users, X} from 'lucide-react';
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
      <section className="modal" style={{maxWidth: wide ? 1100 : 920}}>
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
  const [detail, setDetail] = useState(null);
  const [dlBusy, setDlBusy] = useState('');

  const companyEmployees = useMemo(
    () => employees.filter((e) => String(e.company_id) === String(form.company_id) && e.is_active !== false),
    [employees, form.company_id],
  );

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
    if (!form.participant_ids.length) {
      setErr('Katılımcı seçin: Excel yükleyin veya ortak personel listesinden seçin.');
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
      alert('Katılım belgesi PDF indirilemedi:\n' + x.message);
    } finally {
      setDlBusy('');
    }
  }

  function openDetail(row) {
    setDetail(row);
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
      let out;
      try {
        out = await uploadFile(
          `/trainings/parse-excel?company_id=${Number(form.company_id)}&create_missing=true`,
          file,
        );
      } catch (first) {
        // Eski canlı API: önce boş eğitim oluşturup upload-participants dene
        throw first;
      }
      setEmployees(await api('/employees'));
      setForm((f) => ({...f, participant_ids: out.participant_ids || []}));
      setExcelInfo(
        `Excel: ${out.count} kişi · ${out.created || 0} yeni personel · ${out.participant_ids?.length || 0} seçildi`,
      );
    } catch (x) {
      setErr('Excel yüklenemedi: ' + x.message);
    } finally {
      setBusy(false);
    }
  }

  function selectAllEmployees() {
    setForm((f) => ({...f, participant_ids: companyEmployees.map((e) => e.id)}));
    setExcelInfo(`${companyEmployees.length} kişi ortak personel listesinden seçildi`);
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
            Katılımcılar & Belgeler
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
          <button type="button" onClick={() => { setErr(''); setExcelInfo(''); setOpen(true); }}>
            <Plus /> Yeni Eğitim
          </button>
        )}
      </div>
      <section className="panel">
        <div style={{marginBottom: 14, padding: '12px 14px', background: '#eef5fb', borderRadius: 10, fontSize: 14, lineHeight: 1.55, color: '#243447'}}>
          <strong>Bakanlık denetimi için zorunlu belgeler:</strong>{' '}
          her eğitimde önce katılımcı ekleyin, sonra satırdan{' '}
          <strong>Katılımcılar & Belgeler</strong> açın →{' '}
          <strong>İmza / Yoklama Formu PDF</strong> ve <strong>Katılım Belgesi PDF</strong> indirin.
          Katılım belgesinde eğitim konuları basılır.
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

      {detail && (
        <Modal title={`${detail.title} — Katılımcılar ve Belgeler`} close={() => setDetail(null)} wide>
          <div style={{display: 'grid', gap: 14}}>
            <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, fontSize: 14}}>
              <div><span style={{color: '#64748b'}}>Firma</span><div><strong>{companyName(detail.company_id)}</strong></div></div>
              <div><span style={{color: '#64748b'}}>Tarih</span><div><strong>{detail.start_date}</strong></div></div>
              <div><span style={{color: '#64748b'}}>Tehlike / Süre</span><div><strong>{detail.hazard_class} · {detail.duration_hours} saat</strong></div></div>
              <div><span style={{color: '#64748b'}}>Eğitici</span><div><strong>{detail.instructor_name}</strong></div></div>
              <div><span style={{color: '#64748b'}}>Doğrulama kodu</span><div><strong>{detail.verification_code || '—'}</strong></div></div>
              <div><span style={{color: '#64748b'}}>Katılımcı sayısı</span><div><strong>{detail.participants?.length || 0}</strong></div></div>
            </div>

            {!(detail.participants?.length) && (
              <div className="error">
                Bu eğitimde katılımcı yok. Belge üretilemez. Yeni eğitim oluştururken Excel veya personel listesinden katılımcı seçin.
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
              <h4 style={{margin: '4px 0 8px'}}>Katılımcı listesi</h4>
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
        </Modal>
      )}

      {open && (
        <Modal title="Yeni Eğitim Oturumu" close={() => setOpen(false)}>
          <form className="form-grid" onSubmit={save}>
            <Select label="Firma" required value={form.company_id} onChange={(e) => setForm({...form, company_id: e.target.value, participant_ids: []})}>
              <option value="">Seçiniz</option>
              {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
            <Field label="Eğitim Adı" required minLength={3} value={form.title} onChange={(e) => setForm({...form, title: e.target.value})} />
            <Select label="Eğitim Türü" value={form.training_type} onChange={(e) => setForm({...form, training_type: e.target.value})}>
              <option>Temel İSG Eğitimi</option>
              <option>İşe Özel Eğitim</option>
              <option>Yenileme Eğitimi</option>
              <option>Acil Durum / Tatbikat</option>
            </Select>
            <Select label="Eğitim Şekli" value={form.delivery_method} onChange={(e) => setForm({...form, delivery_method: e.target.value})}>
              <option>Yüz yüze</option>
              <option>Uzaktan</option>
              <option>Hibrit</option>
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
            <Select label="Başarı Değerlendirme" value={form.evaluation_method} onChange={(e) => setForm({...form, evaluation_method: e.target.value})}>
              <option>Sınav</option>
              <option>Uygulama</option>
              <option>Sözlü değerlendirme</option>
              <option>Katılım yeterlidir</option>
            </Select>
            <Field label="Geçme Puanı (0-100)" type="number" min="0" max="100" value={form.passing_score} onChange={(e) => setForm({...form, passing_score: e.target.value})} />

            <div style={{gridColumn: '1 / -1', display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center'}}>
              <label className="button secondary" style={{display: 'inline-flex'}}>
                <Upload size={16} /> PC’den Excel Yükle (.xlsx)
                <input type="file" accept=".xlsx,.xlsm" hidden onChange={onExcel} disabled={busy || !form.company_id} />
              </label>
              <button type="button" className="secondary" disabled={!companyEmployees.length} onClick={selectAllEmployees}>
                <Users size={16} /> Ortak personel listesinin tamamını seç ({companyEmployees.length})
              </button>
              {excelInfo && <span style={{fontSize: 13, color: '#087b67'}}>{excelInfo}</span>}
            </div>

            <label className="field" style={{gridColumn: '1 / -1'}}>
              <span>Katılımcılar ({form.participant_ids.length} seçili)</span>
              <div className="check-grid" style={{maxHeight: 180, overflow: 'auto', marginTop: 8}}>
                {companyEmployees.length ? companyEmployees.map((emp) => (
                  <label key={emp.id} style={{display: 'flex', gap: 8, alignItems: 'center'}}>
                    <input type="checkbox" checked={form.participant_ids.includes(emp.id)} onChange={() => toggleParticipant(emp.id)} />
                    <span>{emp.full_name}{emp.job_title ? ` — ${emp.job_title}` : ''}</span>
                  </label>
                )) : (
                  <span className="empty">Personel yok. Excel yükleyin veya Personel menüsünden ekleyin.</span>
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
