import React, {useEffect, useMemo, useRef, useState} from 'react';
import {AlertTriangle, CalendarPlus, Download, Filter, Plus, RefreshCw, Search, ShieldCheck, Trash2, UserCheck, Users, XCircle} from 'lucide-react';
import {api, downloadFile} from './api';
import {AppModal} from './ui_modal';
import {CommitteeApprovalQueue} from './committee_approval_queue';
import './ohs-committee-page.css';

const REMOVAL_REASONS = [
  ['assignment_ended', 'Görevlendirme sona erdi'],
  ['employment_ended', 'İş ilişkisi sona erdi'],
  ['workplace_changed', 'İşyeri değişti'],
  ['role_changed', 'Görevi değişti'],
  ['incorrectly_added', 'Hatalı eklendi'],
  ['committee_restructured', 'Kurul yeniden yapılandırıldı'],
  ['other', 'Diğer'],
];

function initials(name) {
  return (name || '?').split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase();
}

function Field({label, children, className = '', ...inputProps}) {
  return <label className={`field ${className}`}><span>{label}</span>{children || <input {...inputProps} />}</label>;
}

export function OhsCommitteePage({user}) {
  const canManage = ['global_admin', 'safety_specialist', 'company_admin'].includes(user.role);
  const [companies, setCompanies] = useState([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState(user.company_id ? String(user.company_id) : '');
  const [candidates, setCandidates] = useState({mandatory: [], other: [], missing_mandatory: []});
  const [members, setMembers] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [meta, setMeta] = useState({roles: []});
  const [tab, setTab] = useState('members');
  const [open, setOpen] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [success, setSuccess] = useState('');
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [removingMember, setRemovingMember] = useState(null);
  const removalInFlight = useRef(false);
  const [removalForm, setRemovalForm] = useState({reason_code: 'assignment_ended', reason_text: ''});
  const [memberForm, setMemberForm] = useState({role_code: 'calisan_temsilcisi', start_date: '', notes: ''});
  const [meetingForm, setMeetingForm] = useState({
    meeting_date: '', next_meeting_date: '', title: 'İSG Kurulu Toplantısı', meeting_no: '',
    document_no: '', revision_no: '00', status: 'draft', signature_status: 'not_signed',
    start_time: '', end_time: '', location: '', meeting_type: 'Olağan', agenda: '', decisions: '', notes: '',
  });

  const selectedCompany = companies.find((company) => String(company.id) === String(selectedCompanyId));
  const selectedKeys = useMemo(() => new Set(members.map((member) => member.identity_key).filter(Boolean)), [members]);
  const mandatoryComplete = (candidates.missing_mandatory || []).length === 0;
  const plannedCount = meetings.filter((meeting) => meeting.meeting_date && new Date(meeting.meeting_date) >= new Date(new Date().toDateString())).length;

  async function loadCompanies() {
    try {
      const data = await api('/companies');
      setCompanies(Array.isArray(data) ? data : []);
      if (!selectedCompanyId && data?.length === 1) setSelectedCompanyId(String(data[0].id));
    } catch (error) {
      setErr(error.message || 'İşyeri listesi alınamadı.');
    }
  }

  async function load(companyId = selectedCompanyId) {
    setBusy(true); setErr('');
    try {
      const metadata = await api('/ohs-committee/meta');
      setMeta(metadata || {roles: []});
      if (!companyId) {
        setCandidates({mandatory: [], other: [], missing_mandatory: []});
        setMembers([]); setMeetings([]);
        return;
      }
      const query = `?company_id=${encodeURIComponent(companyId)}`;
      const [candidateData, memberData, meetingData] = await Promise.all([
        api(`/ohs-committee/candidates${query}`),
        api(`/ohs-committee/members/detail${query}`),
        api(`/ohs-committee/meetings${query}`),
      ]);
      setCandidates(candidateData || {mandatory: [], other: [], missing_mandatory: []});
      setMembers(Array.isArray(memberData) ? memberData : []);
      setMeetings(Array.isArray(meetingData) ? meetingData : []);
    } catch (error) {
      setErr(error.message || 'İSG Kurulu bilgileri yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void loadCompanies(); }, []);
  useEffect(() => { void load(selectedCompanyId); }, [selectedCompanyId]);

  function chooseCompany(value) {
    setSelectedCompanyId(value);
    setOpen(''); setSelectedCandidate(null); setRemovingMember(null);
    setErr(''); setSuccess('');
    setMeetingForm((current) => ({...current, meeting_date: '', next_meeting_date: '', agenda: '', decisions: '', notes: ''}));
  }

  function roleLabel(code) {
    return meta.roles?.find((item) => item.code === code)?.label || ({sekreter: 'Kurul Sekreteri', baskan: 'Kurul Başkanı'}[code] || code);
  }

  const filteredOther = (candidates.other || []).filter((candidate) => {
    const haystack = `${candidate.full_name || ''} ${candidate.job_title || ''} ${candidate.department || ''}`.toLocaleLowerCase('tr-TR');
    return (!search || haystack.includes(search.toLocaleLowerCase('tr-TR'))) && (!roleFilter || candidate.suggested_role_code === roleFilter);
  });

  function selectCandidate(candidate) {
    if (!candidate || candidate.missing) return;
    if (candidate.selected || selectedKeys.has(candidate.identity_key)) {
      setErr('Bu kişi kurula daha önce eklenmiştir.');
      return;
    }
    setErr('');
    setSelectedCandidate(candidate);
    setMemberForm({role_code: candidate.suggested_role_code || 'diger', start_date: '', notes: ''});
  }

  async function saveMember(event) {
    event.preventDefault();
    if (!selectedCandidate || busy) return;
    setBusy(true); setErr(''); setSuccess('');
    try {
      await api('/ohs-committee/members/validated', {
        method: 'POST',
        body: JSON.stringify({
          company_id: Number(selectedCompanyId),
          role_code: memberForm.role_code,
          source_type: selectedCandidate.source_type,
          source_id: selectedCandidate.source_id || null,
          full_name: selectedCandidate.full_name || null,
          corporate_email: selectedCandidate.corporate_email || null,
          start_date: memberForm.start_date || null,
          notes: memberForm.notes || null,
        }),
      });
      setSelectedCandidate(null);
      setSuccess('Kurul üyesi güvenli biçimde eklendi.');
      await load(selectedCompanyId);
    } catch (error) {
      setErr(error.message || 'Kurul üyesi kaydedilemedi.');
    } finally {
      setBusy(false);
    }
  }

  function askRemove(member) {
    setErr('');
    setRemovalForm({reason_code: member.is_mandatory ? 'assignment_ended' : 'committee_restructured', reason_text: ''});
    setRemovingMember(member);
  }

  async function confirmRemove(event) {
    event.preventDefault();
    if (!removingMember || busy || removalInFlight.current) return;
    if (removalForm.reason_code === 'other' && !removalForm.reason_text.trim()) {
      setErr('“Diğer” nedeni seçildiğinde açıklama zorunludur.');
      return;
    }
    removalInFlight.current = true;
    setBusy(true); setErr(''); setSuccess('');
    try {
      const result = await api(`/ohs-committee/members/${removingMember.id}/remove`, {
        method: 'POST',
        body: JSON.stringify(removalForm),
      });
      setRemovingMember(null);
      setSuccess(result.message || 'Kurul üyesi başarıyla çıkarıldı.');
      await load(selectedCompanyId);
    } catch (error) {
      setErr(error.message || 'Üyelik sonlandırılamadı. Sayfa durumu korunmuştur.');
    } finally {
      removalInFlight.current = false;
      setBusy(false);
    }
  }

  async function saveMeeting(event) {
    event.preventDefault();
    if (!selectedCompanyId || busy) return;
    setBusy(true); setErr(''); setSuccess('');
    try {
      await api('/ohs-committee/meetings/validated', {
        method: 'POST',
        body: JSON.stringify({
          ...meetingForm,
          company_id: Number(selectedCompanyId),
          next_meeting_date: meetingForm.next_meeting_date || null,
          start_time: meetingForm.start_time || null,
          end_time: meetingForm.end_time || null,
          location: meetingForm.location || null,
          meeting_no: meetingForm.meeting_no || null,
          document_no: meetingForm.document_no || null,
        }),
      });
      setOpen('');
      setSuccess('Toplantı kaydedildi; katılımcılar tarihsel snapshot olarak sabitlendi.');
      await load(selectedCompanyId);
    } catch (error) {
      setErr(error.message || 'Kurul toplantısı kaydedilemedi.');
    } finally {
      setBusy(false);
    }
  }

  function CandidateCard({candidate}) {
    if (candidate.missing) {
      return <div className="committee-v2-missing" role="alert"><AlertTriangle size={20} /><span><strong>{roleLabel(candidate.suggested_role_code)}</strong><small>{candidate.message}</small></span></div>;
    }
    const disabled = candidate.selected || selectedKeys.has(candidate.identity_key);
    return <button type="button" className={`committee-v2-person ${disabled ? 'is-disabled' : ''}`} disabled={disabled} onClick={() => selectCandidate(candidate)} aria-label={`${candidate.full_name} kişisini kurul üyesi olarak seç`}>
      <span className="committee-v2-avatar">{candidate.initials || initials(candidate.full_name)}</span>
      <span className="committee-v2-person-copy"><strong>{candidate.full_name}</strong><small>{candidate.job_title || candidate.professional_role || 'Personel'}</small><em>{candidate.company_name}</em></span>
      <span className="committee-v2-badges">{candidate.mandatory && <b className="is-mandatory">Zorunlu</b>}<b className={disabled ? 'is-selected' : 'is-eligible'}>{disabled ? 'Seçildi' : 'Seçilebilir'}</b></span>
    </button>;
  }

  return <div className="committee-v2-page">
    <header className="committee-v2-hero">
      <div><span><ShieldCheck size={16} /> Kurumsal İSG Kurul Yönetimi</span><h2><Users size={28} /> İSG Kurulu Toplantıları</h2><p>Üyeleri, gündemleri, kararları, dijital onayları, elektronik imzaları ve tarihsel belge sürümlerini tek merkezden yönetin.</p></div>
      <div className="committee-v2-hero-actions"><button type="button" className="secondary" disabled={busy} onClick={() => void load()}><RefreshCw size={16} /> Yenile</button>{canManage && <button type="button" disabled={!selectedCompanyId || busy} onClick={() => {setTab('members'); setOpen('member');}}><UserCheck size={16} /> Üye Yönet</button>}{canManage && <button type="button" disabled={!selectedCompanyId || busy} onClick={() => {setTab('meetings'); setOpen('meeting');}}><CalendarPlus size={16} /> Toplantı Planla</button>}</div>
    </header>

    <section className="committee-v2-workplace"><div><span>Aktif işyeri bağlamı</span><strong>Kurul adayları, toplantılar ve onaycılar yalnız seçilen işyerinden gelir.</strong></div><label><span>İşyeri</span><select value={selectedCompanyId} onChange={(event) => chooseCompany(event.target.value)}><option value="">İşyeri seçiniz</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}</select></label></section>

    {selectedCompanyId && <div className="committee-v2-summary"><article><span>Aktif Üyeler</span><strong>{members.length}</strong><small>Gelecek toplantı varsayılanları</small></article><article><span>Planlı Toplantılar</span><strong>{plannedCount}</strong><small>Bugün ve sonrası</small></article><article><span>Toplam Toplantı</span><strong>{meetings.length}</strong><small>Tarihsel kayıtlar dahil</small></article><article className={mandatoryComplete ? 'complete' : 'incomplete'}><span>Zorunlu Üyeler</span><strong>{mandatoryComplete ? 'Tam' : `${candidates.missing_mandatory?.length || 0} Eksik`}</strong><small>{mandatoryComplete ? 'Resmî akışa hazır' : 'Yalnız taslak kaydedilebilir'}</small></article></div>}

    {err && <div className="error" role="alert">{err}</div>}
    {success && <div className="info" role="status">{success}</div>}

    {selectedCompanyId && <CommitteeApprovalQueue user={user} companyId={selectedCompanyId} compact onChanged={() => void load(selectedCompanyId)} />}

    <section className="committee-v2-content">
      <nav className="committee-v2-tabs"><button type="button" className={tab === 'members' ? 'active' : ''} onClick={() => setTab('members')}><Users size={16} /> Kurul Üyeleri <b>{members.length}</b></button><button type="button" className={tab === 'meetings' ? 'active' : ''} onClick={() => setTab('meetings')}><CalendarPlus size={16} /> Toplantılar <b>{meetings.length}</b></button></nav>
      {!selectedCompanyId ? <div className="committee-v2-empty"><Filter size={34} /><strong>Önce işyeri seçin</strong><span>Kurul üyeleri ve toplantılar işyeri bağlamında güvenli biçimde yüklenir.</span></div> : tab === 'members' ? <div className="committee-v2-member-list">{!mandatoryComplete && <div className="committee-v2-incomplete"><AlertTriangle /><span><strong>Kurul eksik</strong><small>Eksik zorunlu üyeler: {(candidates.missing_mandatory || []).join(', ')}</small></span></div>}{members.length ? members.map((member) => <article key={member.id}><span className="committee-v2-avatar">{member.initials || initials(member.full_name)}</span><span className="committee-v2-member-copy"><strong>{member.full_name}</strong><small>{member.job_title_snapshot || member.professional_role_snapshot || 'Görev bilgisi yok'}</small><em>{roleLabel(member.role_code)}</em></span><span className="committee-v2-member-actions">{member.is_mandatory && <b>Zorunlu üye</b>}{canManage && <button type="button" className="danger-secondary" disabled={busy} onClick={() => askRemove(member)} aria-label={`${member.full_name} kişisini kuruldan çıkar`}><Trash2 size={15} /> Kuruldan Çıkar</button>}</span></article>) : <div className="committee-v2-empty"><Users size={34} /><strong>Aktif kurul üyesi bulunmuyor</strong><span>Üye Yönet düğmesiyle zorunlu ve diğer üyeleri ekleyin.</span></div>}</div> : <div className="committee-v2-table-wrap"><table><thead><tr><th>Tarih</th><th>Toplantı No</th><th>Gündem</th><th>Kararlar</th><th>Katılımcılar</th><th>Sonraki</th><th>Belge</th></tr></thead><tbody>{meetings.length ? meetings.map((meeting) => <tr key={meeting.id}><td>{meeting.meeting_date}</td><td>{meeting.meeting_no || meeting.id}</td><td>{meeting.agenda || '—'}</td><td>{meeting.decisions || '—'}</td><td>{meeting.attendees || '—'}</td><td>{meeting.next_meeting_date || '—'}</td><td><button type="button" className="mini secondary" onClick={() => downloadFile(`/ohs-committee/meetings/${meeting.id}/pdf`, `ISG_Kurulu_${meeting.id}.pdf`).catch((error) => setErr(error.message))}><Download size={14} /> PDF</button></td></tr>) : <tr><td colSpan={7} className="empty">Toplantı kaydı yok.</td></tr>}</tbody></table></div>}
    </section>

    {open === 'member' && <AppModal title={`Kurul Üyesi Seçimi — ${selectedCompany?.name || ''}`} close={() => {setOpen(''); setSelectedCandidate(null);}} wide><div className="committee-v2-picker"><section className="committee-v2-available"><div className="committee-v2-tools"><label><Search size={17} /><input placeholder="Ad, görev veya departman ara" value={search} onChange={(event) => setSearch(event.target.value)} /></label><select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}><option value="">Tüm görevler</option><option value="calisan_temsilcisi">Çalışan Temsilcisi</option><option value="destek">Destek Elemanı</option><option value="diger">Diğer</option></select></div><div className="committee-v2-section-title"><span>Zorunlu Kurul Üyeleri</span><small>İşyeri görevlendirmelerinden otomatik çözülür</small></div><div className="committee-v2-candidate-list">{(candidates.mandatory || []).map((candidate, index) => <CandidateCard key={candidate.identity_key || `missing-${index}`} candidate={candidate} />)}</div><div className="committee-v2-section-title"><span>Diğer Kurul Üyeleri</span><small>Aktif işyeri personeli</small></div><div className="committee-v2-candidate-list">{filteredOther.length ? filteredOther.map((candidate) => <CandidateCard key={candidate.identity_key} candidate={candidate} />) : <div className="committee-v2-empty small"><Users size={28} /><strong>Uygun personel bulunamadı</strong><span>Arama veya görev filtresini değiştirin.</span></div>}</div></section><aside className="committee-v2-selection"><div className="committee-v2-section-title"><span>Seçilen Kişi</span><small>Kurul görevini doğrulayın</small></div>{selectedCandidate ? <form onSubmit={saveMember}><div className="committee-v2-selected-person"><span className="committee-v2-avatar">{selectedCandidate.initials || initials(selectedCandidate.full_name)}</span><span><strong>{selectedCandidate.full_name}</strong><small>{selectedCandidate.job_title || selectedCandidate.professional_role || '—'}</small></span></div><Field label="Kurul görevi"><select required value={memberForm.role_code} onChange={(event) => setMemberForm({...memberForm, role_code: event.target.value})}>{(meta.roles || []).map((role) => <option key={role.code} value={role.code}>{role.label}</option>)}<option value="baskan">Kurul Başkanı</option><option value="sekreter">Kurul Sekreteri</option></select></Field><Field label="Başlangıç tarihi" type="date" value={memberForm.start_date} onChange={(event) => setMemberForm({...memberForm, start_date: event.target.value})} /><Field label="Not"><textarea rows={4} value={memberForm.notes} onChange={(event) => setMemberForm({...memberForm, notes: event.target.value})} /></Field><div className="form-actions"><button type="submit" disabled={busy}>{busy ? 'Kaydediliyor…' : <><Plus size={16} /> Kurula Ekle</>}</button></div></form> : <div className="committee-v2-empty"><UserCheck size={34} /><strong>Bir kişi seçin</strong><span>Soldaki listeden seçtiğiniz kişi burada ayrıntılı görünür.</span></div>}</aside></div></AppModal>}

    {open === 'meeting' && <AppModal title={`Yeni İSG Kurulu Toplantısı — ${selectedCompany?.name || ''}`} close={() => setOpen('')} wide><form className="form-grid committee-v2-meeting-form" onSubmit={saveMeeting}>{!mandatoryComplete && <div className="committee-v2-incomplete committee-span"><AlertTriangle /><span><strong>Resmî durum engeli</strong><small>Eksik zorunlu üyeler tamamlanmadan toplantı yalnız Taslak olarak kaydedilebilir.</small></span></div>}<Field label="Toplantı tarihi" type="date" required value={meetingForm.meeting_date} onChange={(event) => setMeetingForm({...meetingForm, meeting_date: event.target.value})} /><Field label="Toplantı no" value={meetingForm.meeting_no} onChange={(event) => setMeetingForm({...meetingForm, meeting_no: event.target.value})} /><Field label="Belge no" value={meetingForm.document_no} onChange={(event) => setMeetingForm({...meetingForm, document_no: event.target.value})} /><Field label="Revizyon" value={meetingForm.revision_no} onChange={(event) => setMeetingForm({...meetingForm, revision_no: event.target.value})} /><Field label="Başlangıç" type="time" value={meetingForm.start_time} onChange={(event) => setMeetingForm({...meetingForm, start_time: event.target.value})} /><Field label="Bitiş" type="time" value={meetingForm.end_time} onChange={(event) => setMeetingForm({...meetingForm, end_time: event.target.value})} /><Field label="Toplantı yeri" value={meetingForm.location} onChange={(event) => setMeetingForm({...meetingForm, location: event.target.value})} /><Field label="Sonraki toplantı" type="date" value={meetingForm.next_meeting_date} onChange={(event) => setMeetingForm({...meetingForm, next_meeting_date: event.target.value})} /><Field label="Durum"><select required value={meetingForm.status} onChange={(event) => setMeetingForm({...meetingForm, status: event.target.value})}><option value="draft">Taslak</option><option value="active" disabled={!mandatoryComplete}>Aktif</option><option value="completed" disabled={!mandatoryComplete}>Tamamlandı</option></select></Field><Field label="Gündem" className="committee-span"><textarea rows={5} value={meetingForm.agenda} onChange={(event) => setMeetingForm({...meetingForm, agenda: event.target.value})} /></Field><Field label="Kararlar" className="committee-span"><textarea rows={6} value={meetingForm.decisions} onChange={(event) => setMeetingForm({...meetingForm, decisions: event.target.value})} /></Field><Field label="Notlar" className="committee-span"><textarea rows={3} value={meetingForm.notes} onChange={(event) => setMeetingForm({...meetingForm, notes: event.target.value})} /></Field><div className="form-actions committee-span"><button type="submit" disabled={busy || !meetingForm.meeting_date}>{busy ? 'Kaydediliyor…' : 'Toplantıyı Kaydet'}</button></div></form></AppModal>}

    {removingMember && <AppModal title="Kurul Üyeliğini Sonlandır" close={() => !busy && setRemovingMember(null)}><form className="committee-v2-removal" onSubmit={confirmRemove}><div className="committee-v2-removal-icon"><Trash2 /></div><h3>{removingMember.full_name}</h3><p><strong>{roleLabel(removingMember.role_code)}</strong> görevindeki kişi kurulun aktif üye listesinden çıkarılacaktır. Tarihsel toplantı, katılım, onay, PDF ve elektronik imza kayıtları silinmez.</p>{removingMember.is_mandatory && <div className="committee-v2-incomplete"><AlertTriangle /><span><strong>Zorunlu üye uyarısı</strong><small>Bu üyelik sonlandırılırsa kurul eksik duruma döner ve yeni resmî toplantılar tamamlanamaz. Aktif onay/imza akışı varsa işlem backend tarafından engellenir.</small></span></div>}<Field label="Sonlandırma nedeni"><select required value={removalForm.reason_code} onChange={(event) => setRemovalForm({...removalForm, reason_code: event.target.value})}>{REMOVAL_REASONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field><Field label={removalForm.reason_code === 'other' ? 'Açıklama (zorunlu)' : 'Ek açıklama'}><textarea rows={4} required={removalForm.reason_code === 'other'} value={removalForm.reason_text} onChange={(event) => setRemovalForm({...removalForm, reason_text: event.target.value})} /></Field><div className="form-actions"><button type="button" className="secondary" disabled={busy} onClick={() => setRemovingMember(null)}>Vazgeç</button><button type="submit" className="danger" disabled={busy || (removalForm.reason_code === 'other' && !removalForm.reason_text.trim())}>{busy ? 'İşleniyor…' : <><XCircle size={16} /> Üyeliği Sonlandır</>}</button></div></form></AppModal>}
  </div>;
}
