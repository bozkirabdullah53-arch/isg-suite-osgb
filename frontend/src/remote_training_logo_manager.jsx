import React, {useEffect, useMemo, useRef, useState} from 'react';
import {api, uploadFile} from './api';
import {isWorkplaceAccountUser} from './workplace_user_policy';

const LOGO_MANAGER_ROLES = new Set(['global_admin', 'company_admin', 'safety_specialist']);

export function RemoteTrainingLogoManager({user, companyId = ''}) {
  const [programs, setPrograms] = useState([]);
  const [loadedCompanyId, setLoadedCompanyId] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const requestSerial = useRef(0);

  const canManage = LOGO_MANAGER_ROLES.has(user?.role) && !isWorkplaceAccountUser(user);
  const parsedCompanyId = Number(companyId);
  const scopedCompanyId = Number.isSafeInteger(parsedCompanyId) && parsedCompanyId > 0
    ? String(parsedCompanyId)
    : '';
  const programsReady = Boolean(scopedCompanyId) && loadedCompanyId === scopedCompanyId;
  const visiblePrograms = programsReady ? programs : [];
  const programListLoading = Boolean(scopedCompanyId) && (!programsReady || loading);
  const selectedProgram = useMemo(
    () => visiblePrograms.find((row) => String(row.id) === String(selectedId)) || null,
    [visiblePrograms, selectedId],
  );

  async function refreshPrograms(preferredId = selectedId, targetCompanyId = scopedCompanyId) {
    const requestId = requestSerial.current + 1;
    requestSerial.current = requestId;
    if (!targetCompanyId) {
      setPrograms([]);
      setLoadedCompanyId('');
      setSelectedId('');
      return [];
    }
    setLoading(true);
    try {
      const rows = await api(`/trainings/remote/programs?company_id=${encodeURIComponent(targetCompanyId)}`);
      if (requestId !== requestSerial.current) return [];
      const next = Array.isArray(rows) ? rows : [];
      setPrograms(next);
      setLoadedCompanyId(targetCompanyId);
      const wanted = preferredId && next.some((row) => String(row.id) === String(preferredId))
        ? String(preferredId)
        : (next[0]?.id ? String(next[0].id) : '');
      setSelectedId(wanted);
      return next;
    } catch (err) {
      if (requestId !== requestSerial.current) return [];
      throw err;
    } finally {
      if (requestId === requestSerial.current) setLoading(false);
    }
  }

  useEffect(() => {
    setError('');
    setMessage('');
    if (!canManage || !scopedCompanyId) {
      requestSerial.current += 1;
      setPrograms([]);
      setLoadedCompanyId('');
      setSelectedId('');
      setLoading(false);
      return;
    }
    refreshPrograms('', scopedCompanyId).catch((err) => setError(err.message || 'Uzaktan eğitim programları alınamadı.'));
  }, [canManage, scopedCompanyId]);

  async function uploadLogo(file) {
    if (!file || !selectedProgram) return;
    const uploadCompanyId = scopedCompanyId;
    const uploadProgramId = selectedProgram.id;
    setBusy(true); setError(''); setMessage('');
    try {
      await uploadFile(`/trainings/remote/programs/${uploadProgramId}/logo`, file);
      if (uploadCompanyId === scopedCompanyId) await refreshPrograms(uploadProgramId, uploadCompanyId);
      setMessage('Belge logosu kaydedildi. Bundan sonra bu uzaktan eğitim programının PDF belgelerinde kullanılacak.');
    } catch (err) {
      setError(err.message || 'Belge logosu yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  async function removeLogo() {
    if (!selectedProgram?.logo_path || busy) return;
    const removeCompanyId = scopedCompanyId;
    const removeProgramId = selectedProgram.id;
    setBusy(true); setError(''); setMessage('');
    try {
      await api(`/trainings/remote/programs/${removeProgramId}/logo`, {method: 'DELETE'});
      if (removeCompanyId === scopedCompanyId) await refreshPrograms(removeProgramId, removeCompanyId);
      setMessage('Belge logosu kaldırıldı. Logo olmadan mevcut PDF üretimi çalışmaya devam edecek.');
    } catch (err) {
      setError(err.message || 'Belge logosu kaldırılamadı.');
    } finally {
      setBusy(false);
    }
  }

  if (!canManage) return null;

  return (
    <section style={{
      marginBottom: 16,
      padding: 16,
      border: '1px solid #dbe5ef',
      borderRadius: 14,
      background: '#fff',
      boxShadow: '0 3px 12px rgba(15, 35, 55, .05)',
    }} aria-label="Uzaktan eğitim belge logosu">
      <div style={{display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'flex-start'}}>
        <div>
          <div style={{fontSize: 12, color: '#547187', fontWeight: 800, letterSpacing: '.03em'}}>UZAKTAN EĞİTİM BELGE LOGOSU</div>
          <h3 style={{margin: '4px 0'}}>PDF belgesine kurum/işyeri logosu ekleyin</h3>
          <p style={{margin: 0, color: '#5e7485', fontSize: 13}}>Aşağıdaki firma seçiminden sonra o firmaya hazırlanmış eğitim programını seçin. Logo, katılım belgesindeki mevcut alanda oranı bozulmadan kullanılır.</p>
        </div>
        <button type="button" onClick={() => refreshPrograms().catch((err) => setError(err.message || 'Liste yenilenemedi.'))} disabled={busy || loading || !scopedCompanyId}>Programları yenile</button>
      </div>

      <div style={{display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginTop: 14}}>
        <label style={{fontWeight: 700}} htmlFor="remote-training-logo-program">Eğitim programı</label>
        <select
          id="remote-training-logo-program"
          value={programsReady ? selectedId : ''}
          onChange={(event) => { setSelectedId(event.target.value); setError(''); setMessage(''); }}
          disabled={busy || programListLoading || !scopedCompanyId || !visiblePrograms.length}
          style={{minWidth: 280}}
        >
          {!scopedCompanyId && <option value="">Önce firma seçin</option>}
          {scopedCompanyId && programListLoading && <option value="">Firma programları yükleniyor…</option>}
          {scopedCompanyId && !programListLoading && !visiblePrograms.length && <option value="">Bu firmada program bulunamadı</option>}
          {visiblePrograms.map((row) => (
            <option key={row.id} value={row.id}>{row.title || 'Adsız eğitim programı'}</option>
          ))}
        </select>

        <label style={{
          display: 'inline-flex',
          alignItems: 'center',
          minHeight: 36,
          padding: '0 12px',
          border: '1px solid #0f766e',
          borderRadius: 8,
          background: busy || !selectedProgram ? '#b8d8d5' : '#0f766e',
          color: '#fff',
          fontWeight: 800,
          cursor: busy || !selectedProgram ? 'not-allowed' : 'pointer',
        }}>
          {selectedProgram?.logo_path ? 'Logoyu değiştir' : 'Logo yükle'}
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            disabled={busy || !selectedProgram}
            style={{display: 'none'}}
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = '';
              if (file) void uploadLogo(file);
            }}
          />
        </label>
        {selectedProgram?.logo_path && (
          <button type="button" onClick={removeLogo} disabled={busy} style={{color: '#b42318'}}>Logoyu kaldır</button>
        )}
      </div>

      <div style={{marginTop: 9, color: selectedProgram?.logo_path ? '#087443' : '#64748b', fontSize: 12, fontWeight: 700}}>
        {!scopedCompanyId
          ? 'Logo yönetimi için aşağıdaki Firma / sektör atama alanından önce bir firma seçin.'
          : programListLoading
            ? 'Seçilen firmanın programları yükleniyor…'
            : !visiblePrograms.length
              ? 'Bu firma için henüz firma eğitim programı hazırlanmadı.'
              : selectedProgram?.logo_path
                ? 'Logo yüklü — PDF belgesinde kullanılacak.'
                : 'Bu program için henüz logo yüklenmedi.'}
      </div>
      <div style={{marginTop: 4, color: '#64748b', fontSize: 11}}>PNG, JPG/JPEG veya WebP · en fazla 2 MB</div>
      {error && <div role="alert" style={{marginTop: 10, color: '#b42318', fontWeight: 700}}>{error}</div>}
      {message && <div role="status" aria-live="polite" style={{marginTop: 10, color: '#087443', fontWeight: 700}}>{message}</div>}
    </section>
  );
}
