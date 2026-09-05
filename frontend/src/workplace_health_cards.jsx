import React, {useEffect, useState} from 'react';
import {HeartPulse, RefreshCw, Search} from 'lucide-react';
import {api} from './api';

const RECORD_TYPE_LABELS = {
  entry_exam: 'İşe Giriş Muayenesi',
  periodic_exam: 'Periyodik Muayene',
  return_exam: 'İşe Dönüş Muayenesi',
  job_change: 'İş Değişikliği Muayenesi',
  night_work: 'Gece Çalışması Muayenesi',
  heavy_hazardous: 'Ağır / Tehlikeli İşler',
  special_risk: 'Özel Risk',
  occupational_disease_suspect: 'Meslek Hastalığı Şüphesi',
  lab_test: 'Tetkik',
  vaccination: 'Aşı',
  fitness_report: 'Uygunluk Raporu',
  other: 'Diğer',
};

const FITNESS_LABELS = {
  fit: 'Uygun',
  conditional: 'Kısıtlı / Şartlı',
  tracking: 'Takip',
  unfit: 'Uygun Değil',
  pending: 'Bekliyor',
};

function fmt(value) {
  if (!value) return '—';
  try {
    return new Intl.DateTimeFormat('tr-TR').format(new Date(`${value}T00:00:00`));
  } catch {
    return value;
  }
}

export function WorkplaceHealthCardsPage() {
  const [rows, setRows] = useState([]);
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  async function load(query = search) {
    setBusy(true);
    setErr('');
    try {
      const qs = query.trim() ? `?search=${encodeURIComponent(query.trim())}` : '';
      const payload = await api(`/workplace/health-cards${qs}`);
      setRows(payload?.personnel || []);
    } catch (e) {
      setErr(e?.message || 'Sağlık kartları yüklenemedi.');
      setRows([]);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(''); }, []);

  return (
    <>
      <div className="page-title">
        <h3><HeartPulse size={20} /> Çalışan Sağlık Kartları</h3>
        <button type="button" className="secondary" disabled={busy} onClick={() => void load()}>
          <RefreshCw size={16} /> Yenile
        </button>
      </div>

      <section className="panel">
        <div style={{marginBottom: 14, padding: 12, borderRadius: 10, background: '#f8fafc', color: '#475569', fontSize: 13}}>
          <strong>Sadece görüntüleme.</strong> Bu ekran yalnız kendi işyerinizdeki çalışanların son muayene tarih/tür/uygunluk özetini gösterir. Klinik not, tanı, tetkik sonucu ve sağlık raporu içeriği gösterilmez.
        </div>

        <div style={{display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap'}}>
          <label className="field" style={{minWidth: 260, flex: 1, margin: 0}}>
            <span>Personel ara</span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  void load();
                }
              }}
              placeholder="Ad soyad"
            />
          </label>
          <button type="button" className="secondary" disabled={busy} onClick={() => void load()} style={{alignSelf: 'end'}}>
            <Search size={16} /> Ara
          </button>
        </div>

        {err && <div className="error" style={{marginBottom: 12}}>{err}</div>}
        {busy && rows.length === 0 ? (
          <p>Yükleniyor…</p>
        ) : rows.length === 0 ? (
          <p style={{color: '#64748b'}}>Gösterilecek çalışan bulunamadı.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Çalışan</th>
                  <th>Görev / Departman</th>
                  <th>Son Muayene</th>
                  <th>Kayıt Türü</th>
                  <th>Uygunluk</th>
                  <th>Sonraki Muayene</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.employee_id}>
                    <td><strong>{row.full_name}</strong></td>
                    <td>{[row.job_title, row.department].filter(Boolean).join(' · ') || '—'}</td>
                    <td>{fmt(row.last_examination_date)}</td>
                    <td>{RECORD_TYPE_LABELS[row.record_type] || row.record_type || '—'}</td>
                    <td>{FITNESS_LABELS[row.fitness_status] || row.fitness_status || '—'}</td>
                    <td>{fmt(row.next_examination_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
