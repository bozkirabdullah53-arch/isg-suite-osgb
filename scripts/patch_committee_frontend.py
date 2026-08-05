from pathlib import Path

jsx_path = Path("frontend/src/compliance_registers.jsx")
css_path = Path("frontend/src/theme-modern.css")
ci_path = Path(".github/workflows/ci.yml")

jsx = jsx_path.read_text(encoding="utf-8")
start = jsx.index("/** İSG Kurulu + çalışan temsilcisi */")
end = jsx.index("/** Belge onay / imza hazırlık", start)
replacement = r'''/** İSG Kurulu + çalışan temsilcisi — profesyonel üye seçimi ve toplantı yönetimi */
export function OhsCommitteePage({user}) {
  const canEdit = ['safety_specialist', 'global_admin'].includes(user.role);
  const companies = useCompanies(user);
  const [selectedCompanyId, setSelectedCompanyId] = useState(user.company_id ? String(user.company_id) : '');
  const [candidates, setCandidates] = useState({mandatory: [], other: [], missing_mandatory: []});
  const [members, setMembers] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [meta, setMeta] = useState({roles: []});
  const [tab, setTab] = useState('uyeler');
  const [open, setOpen] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [success, setSuccess] = useState('');
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [memberForm, setMemberForm] = useState({role_code: 'calisan_temsilcisi', start_date: '', notes: ''});
  const [meetingForm, setMeetingForm] = useState({
    meeting_date: '', next_meeting_date: '', title: 'İSG Kurulu Toplantısı', meeting_no: '',
    document_no: '', revision_no: '00', status: 'draft', signature_status: 'not_signed',
    start_time: '', end_time: '', location: '', meeting_type: 'Olağan', agenda: '', decisions: '', notes: '',
  });

  const selectedCompany = companies.find((c) => String(c.id) === String(selectedCompanyId));
  const selectedKeys = new Set(members.map((m) => m.identity_key).filter(Boolean));
  const mandatoryComplete = (candidates.missing_mandatory || []).length === 0;

  async function load(companyId = selectedCompanyId) {
    setBusy(true); setErr('');
    try {
      const m = await api('/ohs-committee/meta'); setMeta(m);
      if (!companyId) { setCandidates({mandatory: [], other: [], missing_mandatory: []}); setMembers([]); setMeetings([]); return; }
      const qs = `?company_id=${encodeURIComponent(companyId)}`;
      const [cand, mem, meet] = await Promise.all([
        api(`/ohs-committee/candidates${qs}`),
        api(`/ohs-committee/members/detail${qs}`),
        api(`/ohs-committee/meetings${qs}`),
      ]);
      setCandidates(cand || {mandatory: [], other: [], missing_mandatory: []});
      setMembers(mem || []); setMeetings(meet || []);
    } catch (e) { setErr(e.message || 'İSG Kurulu bilgileri yüklenemedi.'); }
    finally { setBusy(false); }
  }
  useEffect(() => { void load(selectedCompanyId); }, [selectedCompanyId]);

  function chooseCompany(value) {
    setSelectedCompanyId(value); setOpen(''); setSelectedCandidate(null); setErr(''); setSuccess('');
    setMeetingForm((f) => ({...f, meeting_date: '', next_meeting_date: '', agenda: '', decisions: '', notes: ''}));
  }

  function selectCandidate(candidate) {
    if (!candidate || candidate.missing) return;
    if (candidate.selected || selectedKeys.has(candidate.identity_key)) {
      setErr('Bu kişi kurula daha önce eklenmiştir.'); return;
    }
    setErr(''); setSelectedCandidate(candidate);
    setMemberForm({role_code: candidate.suggested_role_code || 'diger', start_date: '', notes: ''});
  }

  async function saveMember(e) {
    e.preventDefault();
    if (!selectedCandidate || busy) return;
    setBusy(true); setErr(''); setSuccess('');
    try {
      await api('/ohs-committee/members/validated', {method: 'POST', body: JSON.stringify({
        company_id: Number(selectedCompanyId), role_code: memberForm.role_code,
        source_type: selectedCandidate.source_type, source_id: selectedCandidate.source_id || null,
        full_name: selectedCandidate.full_name || null, corporate_email: selectedCandidate.corporate_email || null,
        start_date: memberForm.start_date || null, notes: memberForm.notes || null,
      })});
      setSelectedCandidate(null); setSuccess('Kurul üyesi güvenli biçimde eklendi.'); await load(selectedCompanyId);
    } catch (e) { setErr(e.message || 'Kurul üyesi kaydedilemedi.'); }
    finally { setBusy(false); }
  }

  async function removeMember(row) {
    if (!window.confirm(`${row.full_name} kurul üyeliğinden çıkarılsın mı? Tarihsel toplantı snapshotları korunur.`)) return;
    setBusy(true); setErr('');
    try { await api(`/ohs-committee/members/${row.id}`, {method: 'DELETE'}); await load(selectedCompanyId); }
    catch (e) { setErr(e.message || 'Üye çıkarılamadı.'); }
    finally { setBusy(false); }
  }

  async function saveMeeting(e) {
    e.preventDefault(); if (!selectedCompanyId || busy) return;
    setBusy(true); setErr(''); setSuccess('');
    try {
      await api('/ohs-committee/meetings/validated', {method: 'POST', body: JSON.stringify({
        ...meetingForm, company_id: Number(selectedCompanyId), next_meeting_date: meetingForm.next_meeting_date || null,
        start_time: meetingForm.start_time || null, end_time: meetingForm.end_time || null,
        location: meetingForm.location || null, meeting_no: meetingForm.meeting_no || null,
        document_no: meetingForm.document_no || null,
      })});
      setOpen(''); setSuccess('Toplantı kaydedildi ve üye listesi tarihsel snapshot olarak sabitlendi.'); await load(selectedCompanyId);
    } catch (e) { setErr(e.message || 'Kurul toplantısı kaydedilemedi.'); }
    finally { setBusy(false); }
  }

  const roleLabel = (code) => meta.roles?.find((x) => x.code === code)?.label || ({sekreter:'Kurul Sekreteri', baskan:'Kurul Başkanı'}[code] || code);
  const filteredOther = (candidates.other || []).filter((c) => {
    const hay = `${c.full_name || ''} ${c.job_title || ''} ${c.department || ''}`.toLocaleLowerCase('tr-TR');
    return (!search || hay.includes(search.toLocaleLowerCase('tr-TR'))) && (!roleFilter || c.suggested_role_code === roleFilter);
  });
  const plannedCount = meetings.filter((m) => m.meeting_date && new Date(m.meeting_date) >= new Date(new Date().toDateString())).length;

  function CandidateCard({candidate}) {
    if (candidate.missing) return <div className="committee-warning" role="alert"><strong>{roleLabel(candidate.suggested_role_code)}</strong><span>{candidate.message}</span></div>;
    const disabled = candidate.selected || selectedKeys.has(candidate.identity_key);
    const initials = (candidate.full_name || '?').split(/\s+/).slice(0,2).map((x) => x[0]).join('').toUpperCase();
    return <button type="button" className={`committee-person-card ${disabled ? 'is-disabled' : ''}`} disabled={disabled} onClick={() => selectCandidate(candidate)} aria-label={`${candidate.full_name} kurul üyesi olarak seç`}>
      <span className="committee-avatar" aria-hidden="true">{initials}</span>
      <span className="committee-person-main"><strong>{candidate.full_name}</strong><small>{candidate.job_title || candidate.professional_role || 'Personel'}</small><small>{candidate.company_name}</small></span>
      <span className="committee-person-meta">{candidate.mandatory && <span className="status-badge badge-warn">Zorunlu</span>}<span className={`status-badge ${disabled ? 'badge-muted' : 'badge-ok'}`}>{disabled ? 'Seçildi' : 'Seçilebilir'}</span></span>
    </button>;
  }

  return <>
    <div className="page-title committee-page-title">
      <div><h3><Users size={20} /> İSG Kurulu Toplantıları</h3><p>İSG kurullarını, üyeleri, gündemleri, kararları, imza ve takip süreçlerini yönetin.</p></div>
      <div className="actions">
        <button type="button" className="secondary" disabled={busy} onClick={() => void load()}><RefreshCw size={16}/> Yenile</button>
        {canEdit && <button type="button" disabled={!selectedCompanyId || busy} onClick={() => {setTab('uyeler'); setOpen('member');}}><Plus size={16}/> Üye Yönet</button>}
        {canEdit && <button type="button" disabled={!selectedCompanyId || busy} onClick={() => {setTab('toplantilar'); setOpen('meeting');}}><Plus size={16}/> Toplantı Planla</button>}
      </div>
    </div>
    <section className="panel committee-filter-panel">
      <Field label="İşyeri (zorunlu)" required><select required value={selectedCompanyId} onChange={(e) => chooseCompany(e.target.value)}><option value="">İşyeri seçiniz</option>{companies.map((c)=><option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
    </section>
    {selectedCompanyId && <div className="committee-summary-grid">
      <div className="committee-summary"><span>Aktif Üyeler</span><strong>{members.length}</strong></div>
      <div className="committee-summary"><span>Planlı Toplantılar</span><strong>{plannedCount}</strong></div>
      <div className="committee-summary"><span>Toplam Toplantı</span><strong>{meetings.length}</strong></div>
      <div className={`committee-summary ${mandatoryComplete ? 'is-complete' : 'is-alert'}`}><span>Zorunlu Üyeler</span><strong>{mandatoryComplete ? 'Tam' : `${candidates.missing_mandatory?.length || 0} Eksik`}</strong></div>
    </div>}
    {err && <div className="error" role="alert">{err}</div>}{success && <div className="info" role="status">{success}</div>}
    <section className="panel">
      <div className="committee-tabs"><button type="button" className={tab==='uyeler'?'':'secondary'} onClick={()=>setTab('uyeler')}>Kurul Üyeleri ({members.length})</button><button type="button" className={tab==='toplantilar'?'':'secondary'} onClick={()=>setTab('toplantilar')}>Toplantılar ({meetings.length})</button></div>
      {!selectedCompanyId ? <div className="empty">Kurul verilerini görüntülemek için işyeri seçiniz.</div> : tab === 'uyeler' ? <div className="committee-selected-list">
        {!mandatoryComplete && <div className="committee-warning" role="alert"><strong>Kurul eksik</strong><span>Eksik zorunlu üyeler: {(candidates.missing_mandatory || []).join(', ')}</span></div>}
        {members.length ? members.map((m)=><div key={m.id} className="committee-selected-card"><span className="committee-avatar">{m.full_name.split(/\s+/).slice(0,2).map((x)=>x[0]).join('').toUpperCase()}</span><span><strong>{m.full_name}</strong><small>{m.job_title_snapshot || m.professional_role_snapshot || '—'}</small><small>{roleLabel(m.role_code)}</small></span><span className="committee-person-meta">{m.is_mandatory && <span className="status-badge badge-warn">Zorunlu</span>}{canEdit && <button type="button" className="mini secondary" disabled={busy} onClick={()=>void removeMember(m)} aria-label={`${m.full_name} üyesini kaldır`}><Trash2 size={14}/> Kaldır</button>}</span></div>) : <div className="empty">Bu işyerinde kurul üyesi bulunmuyor.</div>}
      </div> : <div className="table-wrap"><table><thead><tr><th>Tarih</th><th>Gündem</th><th>Kararlar</th><th>Katılımcılar</th><th>Sonraki</th><th>İşlem</th></tr></thead><tbody>{meetings.length ? meetings.map((m)=><tr key={m.id}><td>{m.meeting_date}</td><td>{m.agenda || '—'}</td><td>{m.decisions || '—'}</td><td>{m.attendees || '—'}</td><td>{m.next_meeting_date || '—'}</td><td><button type="button" className="mini secondary" onClick={()=>downloadFile(`/ohs-committee/meetings/${m.id}/pdf`, `OHS_Committee_Meeting_${selectedCompany?.name || 'Workplace'}_${m.id}.pdf`).catch((e)=>setErr(e.message))}><Download size={14}/> PDF</button></td></tr>) : <tr><td colSpan={6} className="empty">Toplantı kaydı yok.</td></tr>}</tbody></table></div>}
    </section>
    {open === 'member' && <Modal title={`Kurul Üyesi Seçimi — ${selectedCompany?.name || ''}`} close={()=>{setOpen(''); setSelectedCandidate(null);}} wide>
      <div className="committee-member-picker">
        <div className="committee-available"><div className="committee-picker-tools"><input placeholder="Ad, görev veya departman ara" value={search} onChange={(e)=>setSearch(e.target.value)}/><select value={roleFilter} onChange={(e)=>setRoleFilter(e.target.value)}><option value="">Tüm görevler</option><option value="calisan_temsilcisi">Çalışan Temsilcisi</option><option value="destek">Destek Elemanı</option><option value="diger">Diğer</option></select></div><h4>Zorunlu Kurul Üyeleri</h4><div className="committee-card-list">{(candidates.mandatory || []).map((c,i)=><CandidateCard key={c.identity_key || `missing-${i}`} candidate={c}/>)}</div><h4>Diğer Kurul Üyeleri</h4><div className="committee-card-list">{filteredOther.length ? filteredOther.map((c)=><CandidateCard key={c.identity_key} candidate={c}/>) : <div className="empty">Uygun personel bulunamadı.</div>}</div></div>
        <div className="committee-selection"><h4>Seçilen Kişi</h4>{selectedCandidate ? <form onSubmit={saveMember} className="form-grid"><div className="committee-selected-card"><span className="committee-avatar">{selectedCandidate.full_name.split(/\s+/).slice(0,2).map((x)=>x[0]).join('').toUpperCase()}</span><span><strong>{selectedCandidate.full_name}</strong><small>{selectedCandidate.job_title || selectedCandidate.professional_role || '—'}</small></span></div><Field label="Kurul görevi" required><select value={memberForm.role_code} onChange={(e)=>setMemberForm({...memberForm,role_code:e.target.value})}>{(meta.roles || []).map((r)=><option key={r.code} value={r.code}>{r.label}</option>)}<option value="baskan">Kurul Başkanı</option><option value="sekreter">Kurul Sekreteri</option></select></Field><Field label="Başlangıç" type="date" value={memberForm.start_date} onChange={(e)=>setMemberForm({...memberForm,start_date:e.target.value})}/><label className="field"><span>Not</span><textarea rows={3} value={memberForm.notes} onChange={(e)=>setMemberForm({...memberForm,notes:e.target.value})}/></label><div className="form-actions"><button type="submit" disabled={busy}>{busy ? 'Kaydediliyor…' : 'Kurula Ekle'}</button></div></form> : <div className="empty">Soldaki listeden bir kişi seçiniz.</div>}</div>
      </div>
    </Modal>}
    {open === 'meeting' && <Modal title={`Yeni İSG Kurulu Toplantısı — ${selectedCompany?.name || ''}`} close={()=>setOpen('')} wide><form className="form-grid committee-meeting-form" onSubmit={saveMeeting}>{!mandatoryComplete && <div className="committee-warning" role="alert"><strong>Resmî durum engeli</strong><span>Eksik zorunlu üyeler tamamlanmadan toplantı yalnız Taslak olarak kaydedilebilir.</span></div>}<Field label="Toplantı tarihi" type="date" required value={meetingForm.meeting_date} onChange={(e)=>setMeetingForm({...meetingForm,meeting_date:e.target.value})}/><Field label="Toplantı no" value={meetingForm.meeting_no} onChange={(e)=>setMeetingForm({...meetingForm,meeting_no:e.target.value})}/><Field label="Belge no" value={meetingForm.document_no} onChange={(e)=>setMeetingForm({...meetingForm,document_no:e.target.value})}/><Field label="Revizyon" value={meetingForm.revision_no} onChange={(e)=>setMeetingForm({...meetingForm,revision_no:e.target.value})}/><Field label="Başlangıç" type="time" value={meetingForm.start_time} onChange={(e)=>setMeetingForm({...meetingForm,start_time:e.target.value})}/><Field label="Bitiş" type="time" value={meetingForm.end_time} onChange={(e)=>setMeetingForm({...meetingForm,end_time:e.target.value})}/><Field label="Toplantı yeri" value={meetingForm.location} onChange={(e)=>setMeetingForm({...meetingForm,location:e.target.value})}/><Field label="Sonraki toplantı" type="date" value={meetingForm.next_meeting_date} onChange={(e)=>setMeetingForm({...meetingForm,next_meeting_date:e.target.value})}/><Field label="Durum" required><select value={meetingForm.status} onChange={(e)=>setMeetingForm({...meetingForm,status:e.target.value})}><option value="draft">Taslak</option><option value="active" disabled={!mandatoryComplete}>Aktif</option><option value="completed" disabled={!mandatoryComplete}>Tamamlandı</option></select></Field><label className="field committee-span"><span>Gündem</span><textarea rows={5} value={meetingForm.agenda} onChange={(e)=>setMeetingForm({...meetingForm,agenda:e.target.value})}/></label><label className="field committee-span"><span>Kararlar</span><textarea rows={6} value={meetingForm.decisions} onChange={(e)=>setMeetingForm({...meetingForm,decisions:e.target.value})}/></label><label className="field committee-span"><span>Notlar</span><textarea rows={3} value={meetingForm.notes} onChange={(e)=>setMeetingForm({...meetingForm,notes:e.target.value})}/></label><div className="form-actions committee-span"><button type="submit" disabled={busy || !meetingForm.meeting_date}>{busy ? 'Kaydediliyor…' : 'Toplantıyı Kaydet'}</button></div></form></Modal>}
  </>;
}

'''
jsx = jsx[:start] + replacement + jsx[end:]
jsx_path.write_text(jsx, encoding="utf-8")

marker = "/* committee-professional-v1 */"
css = css_path.read_text(encoding="utf-8")
if marker not in css:
    css += r'''

/* committee-professional-v1 */
.committee-page-title>div:first-child p{margin:4px 0 0;color:#64748b;font-size:14px}.committee-page-title h3{display:flex;align-items:center;gap:8px}.committee-filter-panel{display:grid;grid-template-columns:minmax(260px,520px);margin-bottom:14px}.committee-summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:14px}.committee-summary{background:#fff;border:1px solid #dbe3ec;border-radius:14px;padding:14px 16px;box-shadow:0 4px 14px rgba(15,23,42,.05)}.committee-summary span{display:block;color:#64748b;font-size:12px;font-weight:700}.committee-summary strong{display:block;margin-top:5px;font-size:23px;color:#0f3d63}.committee-summary.is-complete{border-color:#86efac;background:#f0fdf4}.committee-summary.is-alert{border-color:#fdba74;background:#fff7ed}.committee-tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}.committee-warning{display:flex;flex-direction:column;gap:4px;border:1px solid #fdba74;background:#fff7ed;color:#9a3412;border-radius:12px;padding:12px;margin-bottom:10px;text-align:left}.committee-member-picker{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(280px,.8fr);gap:16px;min-height:520px;max-height:72vh}.committee-available,.committee-selection{min-width:0;overflow:auto;padding:2px}.committee-selection{border-left:1px solid #e2e8f0;padding-left:16px}.committee-picker-tools{display:grid;grid-template-columns:1fr minmax(160px,.35fr);gap:8px;position:sticky;top:0;background:#fff;padding-bottom:10px;z-index:1}.committee-card-list,.committee-selected-list{display:flex;flex-direction:column;gap:8px}.committee-person-card,.committee-selected-card{width:100%;display:grid;grid-template-columns:44px minmax(0,1fr) auto;align-items:center;gap:10px;border:1px solid #dbe3ec;background:#fff;border-radius:12px;padding:10px 12px;text-align:left;color:#0f172a}.committee-person-card{cursor:pointer;transition:border-color .15s,box-shadow .15s,transform .15s}.committee-person-card:hover:not(:disabled),.committee-person-card:focus-visible{border-color:#2563eb;box-shadow:0 0 0 3px rgba(37,99,235,.13);transform:translateY(-1px);outline:none}.committee-person-card.is-disabled{opacity:.62;cursor:not-allowed;background:#f8fafc}.committee-avatar{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#e0f2fe;color:#075985;font-weight:800;font-size:13px}.committee-person-main,.committee-selected-card>span:nth-child(2){display:flex;flex-direction:column;min-width:0}.committee-person-main small,.committee-selected-card small{color:#64748b;white-space:normal}.committee-person-meta{display:flex;align-items:center;justify-content:flex-end;gap:6px;flex-wrap:wrap}.committee-selection .form-grid{grid-template-columns:1fr}.committee-meeting-form .committee-span{grid-column:1/-1}@media(max-width:980px){.committee-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.committee-member-picker{grid-template-columns:1fr;max-height:none}.committee-selection{border-left:0;border-top:1px solid #e2e8f0;padding-left:2px;padding-top:14px}}@media(max-width:620px){.committee-summary-grid{grid-template-columns:1fr 1fr}.committee-person-card,.committee-selected-card{grid-template-columns:40px minmax(0,1fr)}.committee-person-meta{grid-column:1/-1;justify-content:flex-start}.committee-picker-tools{grid-template-columns:1fr}.committee-member-picker{min-height:0}.committee-page-title .actions{width:100%}.committee-page-title .actions button{flex:1;min-height:44px}.committee-summary{padding:12px}.committee-summary strong{font-size:19px}}
'''
    css_path.write_text(css, encoding="utf-8")

ci = ci_path.read_text(encoding="utf-8")
needle = "          tests/test_training_runtime_patches.py\n"
if "tests/test_committee_professional.py" not in ci:
    if needle not in ci:
        raise SystemExit("CI insertion point not found")
    ci = ci.replace(needle, needle + "          tests/test_committee_professional.py\n")
    ci_path.write_text(ci, encoding="utf-8")
