import React, {useEffect, useMemo, useState} from 'react';
import {api, uploadFile} from './api';
import {isWorkplaceAccountUser} from './workplace_user_policy';

const LOGO_MANAGER_ROLES = new Set(['global_admin', 'company_admin', 'safety_specialist']);

export function RemoteTrainingLogoManager({user}) {
  const [programs, setPrograms] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const canManage = LOGO_MANAGER_ROLES.has(user?.role) && !isWorkplaceAccountUser(user);
  const selectedProgram = useMemo(
    () => programs.find((row) => String(row.id) === String(selectedId)) || null,
    [programs, selectedId],
  );

  async function refreshPrograms(preferredId = selectedId) {
    const rows = await api('/trainings/remote/programs');
    const next = Array.isArray(rows) ? rows : [];
    setPrograms(next);
    const wanted = preferredId && next.some((row) => String(row.id) === String(preferredId))
      ? String(preferredId)
      : (next[0]?.id ? String(next[0].id) : '');
    setSelectedId(wanted);
    return next;
  }

  useEffect(() => {
    if (!canManage) return;
    refreshPrograms('').catch((err) => setError(err.message || 'Uzaktan eğitim programları alınamadı.'));
  }, [canManage]);

  async function uploadLogo(file) {
    if (!file || !selectedProgram) return;
    setBusy(true); setError(''); setMessage('');
    try {
      await uploadFile(`/trainings/remote/programs/${selectedProgram.id}/logo`, file);
      await refreshPrograms(selectedProgram.id);
      setMessage('Belge logosu kaydedildi. Bundan sonra bu uzaktan eğitim programının PDF belgelerinde kullanılacak.');
    } catch (err) {
      setError(err.message || 'Belge logosu yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  async function removeLogo() {
    if (!selectedProgram?.logo_path || busy) return;
    setBusy(true); setError(''); setMessage('');
    try {
      await api(`/trainings/remote/programs/${selectedProgram.id}/logo`, {method: 'DELETE'});
      await refreshPrograms(selectedProgram.id);
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
          <p style={{margin: 0, color: '#5e7485', fontSize: 13}}>Logo, katılım belgesindeki mevcut logo alanında oranı bozulmadan kullanılır. Logo yüklenmezse mevcut belge düzeni aynen devam eder.</p>
        </div>
        <button type="button" onClick={() => refreshPrograms().catch((err) => setError(err.message || 'Liste yenilenemedi.'))} disabled={busy}>Programları yenile</button>
      </div>

      <div style={{display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginTop: 14}}>
        <label style={{fontWeight: 700}} htmlFor="remote-training-logo-program">Eğitim programı</label>
        <select
          id="remote-training-logo-program"
          value={selectedId}
          onChange={(event) => { setSelectedId(event.target.value); setError(''); setMessage(''); }}
          disabled={busy || !programs.length}
          style={{minWidth: 280}}
        >
          {!programs.length && <option value="">Firma programı bulunamadı</option>}
          {programs.map((row) => (
            <option key={row.id} value={row.id}>{row.title} · Firma #{row.company_id}</option>
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
        {selectedProgram?.logo_path ? 'Logo yüklü — PDF belgesinde kullanılacak.' : 'Bu program için henüz logo yüklenmedi.'}
      </div>
      <div style={{marginTop: 4, color: '#64748b', fontSize: 11}}>PNG, JPG/JPEG veya WebP · en fazla 2 MB</div>
      {error && <div role="alert" style={{marginTop: 10, color: '#b42318', fontWeight: 700}}>{error}</div>}
      {message && <div role="status" aria-live="polite" style={{marginTop: 10, color: '#087443', fontWeight: 700}}>{message}</div>}
    </section>
  );
}
