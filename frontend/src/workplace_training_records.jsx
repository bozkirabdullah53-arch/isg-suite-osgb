import React, {useEffect, useState} from 'react';
import {Download, FileText, GraduationCap, Search, ShieldCheck, User} from 'lucide-react';
import {api, downloadFile} from './api';

/**
 * İşyeri Kullanıcısı — Personel Eğitim Kayıtları & Sertifika PDF İndirme
 *
 * Sadece işyeri yöneticisi (company_admin + company_id) erişebilir.
 * Kendi firmasına ait personelin eğitim bilgilerini listeler ve
 * katılım belgesi PDF'ini indirebilir.
 */
export function WorkplaceTrainingRecordsPage({user}) {
  const [personnel, setPersonnel] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [search, setSearch] = useState('');
  const [expandedEmp, setExpandedEmp] = useState(null);
  const [downloadingId, setDownloadingId] = useState(null);

  async function loadData(searchTerm = '') {
    setLoading(true);
    setErr('');
    try {
      const params = searchTerm ? `?search=${encodeURIComponent(searchTerm)}` : '';
      const data = await api(`/workplace/training-records${params}`);
      setPersonnel(data.personnel || []);
    } catch (e) {
      setErr(e.message || 'Veri yüklenemedi.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadData(); }, []);

  let searchTimer = null;
  function handleSearchChange(val) {
    setSearch(val);
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => void loadData(val), 400);
  }

  async function handleDownloadPdf(employeeId, employeeName, trainingId = null) {
    const key = `${employeeId}-${trainingId || 'all'}`;
    setDownloadingId(key);
    try {
      const params = trainingId ? `?training_id=${trainingId}` : '';
      const safeName = (employeeName || 'personel').replace(/\s+/g, '_');
      const filename = trainingId
        ? `${safeName}-egitim-${trainingId}-katilim-belgesi.pdf`
        : `${safeName}-tum-egitim-belgeleri.pdf`;
      await downloadFile(
        `/workplace/training-records/${employeeId}/certificates.pdf${params}`,
        filename,
      );
    } catch (e) {
      alert(e.message || 'PDF indirilemedi.');
    } finally {
      setDownloadingId(null);
    }
  }

  function toggleExpand(empId) {
    setExpandedEmp(prev => prev === empId ? null : empId);
  }

  function statusBadge(status) {
    if (status === 'completed') return <span style={{...badgeStyle, background: '#dcfce7', color: '#166534'}}>Tamamlandı</span>;
    if (status === 'in_progress') return <span style={{...badgeStyle, background: '#fef9c3', color: '#854d0e'}}>Devam Ediyor</span>;
    if (status === 'cancelled') return <span style={{...badgeStyle, background: '#fee2e2', color: '#991b1b'}}>İptal</span>;
    return <span style={badgeStyle}>{status || '—'}</span>;
  }

  function passBadge(passed) {
    if (passed === true) return <span style={{...badgeStyle, background: '#dcfce7', color: '#166534'}}>Geçti</span>;
    if (passed === false) return <span style={{...badgeStyle, background: '#fee2e2', color: '#991b1b'}}>Kaldı</span>;
    return <span style={badgeStyle}>—</span>;
  }

  return (
    <>
      <div className="page-title">
        <h3><GraduationCap size={20} /> Personel Eğitim Kayıtları & Belgelendirme</h3>
      </div>

      <section className="panel">
        <p style={{marginTop: 0, color: '#64748b', fontSize: 14}}>
          İşyerinize ait personelin eğitim geçmişini görüntüleyin ve katılım belgelerini PDF olarak indirin.
        </p>

        {err && <div className="error">{err}</div>}

        {/* Arama */}
        <div style={{marginBottom: 16}}>
          <label className="field" style={{maxWidth: 420}}>
            <span style={{display: 'flex', alignItems: 'center', gap: 6}}>
              <Search size={14} /> Personel Ara
            </span>
            <input
              type="text"
              placeholder="Ad soyad ile arayın…"
              value={search}
              onChange={(e) => handleSearchChange(e.target.value)}
            />
          </label>
        </div>

        {loading && <p style={{color: '#64748b'}}>Yükleniyor…</p>}

        {!loading && personnel.length === 0 && (
          <p style={{color: '#64748b'}}>
            {search ? 'Aramanızla eşleşen personel bulunamadı.' : 'Henüz personel kaydı yok.'}
          </p>
        )}

        {/* Personel Listesi */}
        <div style={{display: 'flex', flexDirection: 'column', gap: 8}}>
          {personnel.map((emp) => {
            const isExpanded = expandedEmp === emp.employee_id;
            const hasTrainings = emp.trainings && emp.trainings.length > 0;

            return (
              <div key={emp.employee_id} style={{
                border: '1px solid #e2e8f0',
                borderRadius: 12,
                overflow: 'hidden',
                background: isExpanded ? '#f8fafc' : '#fff',
              }}>
                {/* Personel Header */}
                <div
                  onClick={() => toggleExpand(emp.employee_id)}
                  style={{
                    padding: '12px 16px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 12,
                    userSelect: 'none',
                  }}
                >
                  <div style={{display: 'flex', alignItems: 'center', gap: 10}}>
                    <div style={{
                      width: 36, height: 36, borderRadius: '50%',
                      background: '#0f766e', color: '#fff',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontWeight: 700, fontSize: 14, flexShrink: 0,
                    }}>
                      {(emp.full_name || '?')[0].toUpperCase()}
                    </div>
                    <div>
                      <div style={{fontWeight: 700, fontSize: 14}}>{emp.full_name}</div>
                      <div style={{fontSize: 12, color: '#64748b'}}>
                        {emp.job_title || '—'}{emp.department ? ` · ${emp.department}` : ''}
                      </div>
                    </div>
                  </div>

                  <div style={{display: 'flex', alignItems: 'center', gap: 8}}>
                    <span style={{
                      fontSize: 12, fontWeight: 600, color: '#0f766e',
                      background: '#ccfbf1', padding: '2px 8px', borderRadius: 12,
                    }}>
                      {hasTrainings ? `${emp.trainings.length} Eğitim` : 'Eğitim Yok'}
                    </span>
                    <span style={{fontSize: 16, color: '#94a3b8', transform: isExpanded ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform .2s'}}>▼</span>
                  </div>
                </div>

                {/* Expanded: Training Records */}
                {isExpanded && (
                  <div style={{padding: '0 16px 16px', borderTop: '1px solid #e2e8f0'}}>
                    {!hasTrainings ? (
                      <p style={{color: '#64748b', fontSize: 13, marginTop: 12}}>Bu personelin henüz eğitim kaydı bulunmuyor.</p>
                    ) : (
                      <>
                        {/* Tümünü İndir Butonu */}
                        <div style={{marginTop: 12, marginBottom: 12}}>
                          <button
                            className="mini"
                            disabled={downloadingId === `${emp.employee_id}-all`}
                            onClick={() => void handleDownloadPdf(emp.employee_id, emp.full_name)}
                            style={{display: 'inline-flex', alignItems: 'center', gap: 6}}
                          >
                            {downloadingId === `${emp.employee_id}-all` ? (
                              <>⏳ İndiriliyor…</>
                            ) : (
                              <><Download size={14} /> Tüm Eğitim Belgelerini İndir (PDF)</>
                            )}
                          </button>
                        </div>

                        {/* Eğitim Tablosu */}
                        <div style={{overflowX: 'auto'}}>
                          <table style={{width: '100%', borderCollapse: 'collapse', fontSize: 13}}>
                            <thead>
                              <tr style={{borderBottom: '2px solid #e2e8f0', textAlign: 'left'}}>
                                <th style={thStyle}>Eğitim</th>
                                <th style={thStyle}>Tarih</th>
                                <th style={thStyle}>Süre</th>
                                <th style={thStyle}>Sertifika No</th>
                                <th style={thStyle}>Sınav</th>
                                <th style={thStyle}>Durum</th>
                                <th style={{...thStyle, textAlign: 'center'}}>PDF</th>
                              </tr>
                            </thead>
                            <tbody>
                              {emp.trainings.map((t, idx) => {
                                const dlKey = `${emp.employee_id}-${t.training_id}`;
                                return (
                                  <tr key={idx} style={{borderBottom: '1px solid #f1f5f9'}}>
                                    <td style={tdStyle}>
                                      <div style={{fontWeight: 600}}>{t.title || '—'}</div>
                                      {t.hazard_class && <div style={{fontSize: 11, color: '#64748b'}}>{t.hazard_class}</div>}
                                    </td>
                                    <td style={tdStyle}>{t.start_date || '—'}</td>
                                    <td style={tdStyle}>{t.duration_hours ? `${t.duration_hours} saat` : '—'}</td>
                                    <td style={{...tdStyle, fontFamily: 'monospace', fontSize: 12}}>{t.certificate_number || '—'}</td>
                                    <td style={tdStyle}>
                                      {passBadge(t.exam_passed)}
                                      {t.exam_score != null && <div style={{fontSize: 11, color: '#64748b'}}>{t.exam_score} puan</div>}
                                    </td>
                                    <td style={tdStyle}>{statusBadge(t.status)}</td>
                                    <td style={{...tdStyle, textAlign: 'center'}}>
                                      <button
                                        className="mini"
                                        disabled={downloadingId === dlKey}
                                        onClick={() => void handleDownloadPdf(emp.employee_id, emp.full_name, t.training_id)}
                                        title="Bu eğitimin katılım belgesini indir"
                                        style={{padding: '4px 8px'}}
                                      >
                                        {downloadingId === dlKey ? '⏳' : <FileText size={14} />}
                                      </button>
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>
    </>
  );
}

const badgeStyle = {
  display: 'inline-block',
  padding: '2px 8px',
  borderRadius: 12,
  fontSize: 11,
  fontWeight: 700,
};

const thStyle = {
  padding: '8px 10px',
  color: '#64748b',
  fontWeight: 600,
  fontSize: 12,
};

const tdStyle = {
  padding: '8px 10px',
  verticalAlign: 'middle',
};
