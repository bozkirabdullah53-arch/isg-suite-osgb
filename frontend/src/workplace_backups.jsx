import React, {useEffect, useState} from 'react';
import {Download, Eye, HardDrive, RefreshCw, ShieldCheck} from 'lucide-react';
import {api, downloadFile} from './api';
import {backupSourceLabel, backupStatusLabel, formatBackupSize} from './workplace_backups_logic';
import './workplace_backups.css';

export function WorkplaceBackupsPage() {
  const [rows, setRows] = useState([]); const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [contents, setContents] = useState(null);
  async function load() {
    setError('');
    try { const [list, info] = await Promise.all([api('/workplace-backups'), api('/workplace-backups/status')]); setRows(list || []); setStatus(info); }
    catch (e) { setError(e.message); }
  }
  useEffect(() => { load(); }, []);
  async function createBackup() {
    setBusy(true); setError('');
    try { await api('/workplace-backups', {method:'POST', body:JSON.stringify({})}); await load(); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function inspect(row) {
    setError('');
    try { setContents(await api(`/workplace-backups/${row.id}/contents`)); }
    catch (e) { setError(e.message); }
  }
  return <div className="workplace-backups-page">
    <div className="workplace-backups-head">
      <div><h1>Yedeklerim</h1><p>Yalnızca kendi işyerinize ait güvenli yedekleri yönetin ve indirin.</p></div>
      <button type="button" disabled={busy} onClick={createBackup}><HardDrive size={18}/>{busy?'Yedek hazırlanıyor…':'Şimdi yedek al'}</button>
    </div>
    {error && <div className="alert error">{error}</div>}
    <div className="backup-policy"><ShieldCheck size={24}/><div><strong>Otomatik koruma aktif</strong><span>Her gece saat {String(status?.backup_hour_tr ?? 2).padStart(2,'0')}:00 · Otomatik yedekler {status?.retention_days ?? 30} gün saklanır. Manuel yedekler otomatik silinmez.</span><span>İndirilen standart ZIP, ISG Suite olmadan açılabilir. Personel ve sağlık verileri içerebildiği için güvenli bir yerde saklayın.</span></div><button className="secondary mini" onClick={load}><RefreshCw size={15}/> Yenile</button></div>
    <div className="table-wrap"><table><thead><tr><th>Tarih</th><th>Tür</th><th>Durum</th><th>Boyut</th><th>İşlem</th></tr></thead><tbody>
      {rows.length ? rows.map(row => <tr key={row.id}><td>{new Date(row.created_at).toLocaleString('tr-TR')}</td><td>{backupSourceLabel(row.backup_source)}</td><td><span className={`backup-state ${row.backup_status}`}>{backupStatusLabel(row.backup_status)}</span>{row.error_summary && <small>{row.error_summary}</small>}</td><td>{formatBackupSize(row.size_bytes)}</td><td className="backup-actions"><button className="mini secondary" disabled={row.backup_status!=='completed'} onClick={()=>inspect(row)}><Eye size={15}/> İçerik</button><button className="mini" disabled={row.backup_status!=='completed'} onClick={()=>downloadFile(`/workplace-backups/${row.id}/download`, row.original_name||`isyeri-yedegi-${row.id}.zip`).catch(e=>setError(e.message))}><Download size={15}/> İndir</button></td></tr>) : <tr><td colSpan="5" className="empty">Henüz yedek oluşturulmadı.</td></tr>}
    </tbody></table></div>
    {contents && <div className="backup-contents"><div><h3>Yedek içeriği</h3><button className="mini secondary" onClick={()=>setContents(null)}>Kapat</button></div><p>Firma kapsamı doğrulandı. Biçim sürümü: <strong>{contents.manifest?.format_version}</strong></p><ul>{Object.entries(contents.manifest?.domain_counts||{}).map(([name,count])=><li key={name}><span>{name}</span><strong>{count}</strong></li>)}</ul></div>}
  </div>;
}
