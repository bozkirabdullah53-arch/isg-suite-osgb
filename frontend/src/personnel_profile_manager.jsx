// OSGB_PROFESSIONAL_CARDS_ONLY_V2
import React,{useEffect,useMemo,useState} from 'react';
import {
  Archive,
  ArrowLeft,
  BriefcaseBusiness,
  CheckCircle2,
  Clock3,
  FileText,
  GraduationCap,
  History,
  IdCard,
  Mail,
  Plus,
  Search,
  ShieldCheck,
  UserRound,
} from 'lucide-react';
import {api} from './api';
import {
  employmentStatusLabel,
  formatProfileDate,
  normalizePersonnelProfileSummary,
} from './personnel_profile_readonly_logic';
import {
  PROFILE_MANAGER_TABS,
  activeProfileRows,
  archivedProfileRows,
  asRows,
  buildOsgbProfessionalSubjects,
  buildProfileHistory,
  filterPersonnelSubjects,
  managerCanWrite,
  safeInitials,
} from './personnel_profile_manager_logic';
import './personnel_profile_manager.css';


const EMPTY_CONTACT = {
  entry_key: '',
  contact_type: 'corporate_email',
  label: '',
  contact_value: '',
  is_primary: false,
  visibility: 'internal_only',
  change_reason: '',
};
const EMPTY_COMPETENCY = {
  entry_key: '',
  category: 'professional_duty',
  name: '',
  start_date: '',
  end_date: '',
  certificate_number: '',
  issuing_organization: '',
  description: '',
  change_reason: '',
};
const EMPTY_EXPERIENCE = {
  entry_key: '',
  organization_name: '',
  position: '',
  start_date: '',
  end_date: '',
  employment_type: '',
  sector: '',
  nace_activity: '',
  project_name: '',
  professional_summary: '',
  responsibilities: '',
  visibility: 'internal_only',
  change_reason: '',
};

function cleanBody(values) {
  return Object.fromEntries(Object.entries(values).filter(([, value]) => value !== '' && value !== null && value !== undefined));
}

function StatusPill({children,tone='neutral'}) {
  return <span className={`ppm-status ppm-status--${tone}`}>{children}</span>;
}

function EmptyState({title,description}) {
  return (
    <div className="ppm-empty">
      <FileText size={34}/>
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}

function SummaryField({label,value}) {
  if(value===null || value===undefined || value==='') return null;
  return (
    <div className="ppm-summary-field">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function FormActions({editing,onCancel,busy}) {
  return (
    <div className="ppm-form-actions">
      {editing&&<button type="button" className="secondary" onClick={onCancel} disabled={busy}>Vazgeç</button>}
      <button type="submit" disabled={busy}>{busy?'Kaydediliyor…':editing?'Yeni sürümü kaydet':'Ekle'}</button>
    </div>
  );
}

function CapabilityNotice({icon:Icon,title,description,nextPhase}) {
  return (
    <div className="ppm-capability-notice">
      <Icon size={28}/>
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
        <small>{nextPhase}</small>
      </div>
    </div>
  );
}

export function PersonnelProfileManagerPage({user,context,onClose}) {
  const canWrite=managerCanWrite(user);
  const[loading,setLoading]=useState(true);
  const[busy,setBusy]=useState(false);
  const[error,setError]=useState('');
  const[message,setMessage]=useState('');
  const[assignments,setAssignments]=useState([]);
  const[osgbId,setOsgbId]=useState(null);
  const[subjects,setSubjects]=useState([]);
  const[selectedKey,setSelectedKey]=useState('');
  const[query,setQuery]=useState('');
  const[summary,setSummary]=useState(null);
  const[snapshot,setSnapshot]=useState(null);
  const[tab,setTab]=useState('overview');
  const[contactForm,setContactForm]=useState(EMPTY_CONTACT);
  const[competencyForm,setCompetencyForm]=useState(EMPTY_COMPETENCY);
  const[experienceForm,setExperienceForm]=useState(EMPTY_EXPERIENCE);

  const selectedSubject=useMemo(()=>subjects.find((row)=>row.subjectKey===selectedKey)||null,[subjects,selectedKey]);
  const filteredSubjects=useMemo(()=>filterPersonnelSubjects(subjects,query),[subjects,query]);
  const activeContacts=useMemo(()=>activeProfileRows(snapshot?.contacts),[snapshot]);
  const activeCompetencies=useMemo(()=>activeProfileRows(snapshot?.competencies),[snapshot]);
  const activeExperiences=useMemo(()=>activeProfileRows(snapshot?.experiences),[snapshot]);
  const history=useMemo(()=>buildProfileHistory(snapshot),[snapshot]);

  useEffect(()=>{
    let cancelled=false;
    (async()=>{
      setLoading(true);setError('');
      try{
        const resolvedOsgbId=Number(context?.osgbId||0) || Number(asRows(await api('/osgb',{_retries:1}))[0]?.id||0);
        if(!resolvedOsgbId) throw new Error('OSGB kapsamı bulunamadı.');
        const[professionalPayload,assignmentPayload]=await Promise.all([
          api(`/osgb-personnel-profiles/professionals?osgb_id=${encodeURIComponent(resolvedOsgbId)}`,{_retries:1}),
          api(`/osgb/assignments?osgb_id=${encodeURIComponent(resolvedOsgbId)}`,{_retries:1}),
        ]);
        if(cancelled) return;
        const rows=buildOsgbProfessionalSubjects(asRows(professionalPayload),resolvedOsgbId);
        setOsgbId(resolvedOsgbId);
        setAssignments(asRows(assignmentPayload));
        setSubjects(rows);
        setSelectedKey((current)=>rows.some((row)=>row.subjectKey===current)?current:(rows[0]?.subjectKey||''));
      }catch(x){
        if(!cancelled) setError(x?.message||'OSGB profesyonel kartları yüklenemedi.');
      }finally{
        if(!cancelled) setLoading(false);
      }
    })();
    return()=>{cancelled=true};
  },[context]);


  useEffect(()=>{
    if(!selectedSubject){setSummary(null);setSnapshot(null);return undefined}
    let cancelled=false;
    (async()=>{
      setBusy(true);setError('');setMessage('');setSnapshot(null);setTab('overview');
      try{
        const payload=await api(`/osgb-personnel-profiles/professional/${selectedSubject.id}/summary`);
        const normalized=normalizePersonnelProfileSummary(payload);
        if(normalized.restrictedDataIncluded) throw new Error('Güvenlik kontrolü restricted veri işareti bulunan profil yanıtını engelledi.');
        if(!cancelled) setSummary(normalized);
      }catch(x){
        if(!cancelled) setError(x?.message||'Profil özeti yüklenemedi.');
      }finally{
        if(!cancelled) setBusy(false);
      }
    })();
    return()=>{cancelled=true};
  },[selectedSubject]);

  async function reloadSnapshot(profileId=snapshot?.profile?.id){
    if(!profileId) return;
    const payload=await api(`/osgb-personnel-profiles/${encodeURIComponent(profileId)}`,{_retries:1});
    setSnapshot(payload);
  }

  async function startProfile(){
    if(!selectedSubject||!osgbId||!canWrite) return;
    setBusy(true);setError('');setMessage('');
    try{
      const result=await api(`/osgb-personnel-profiles/professionals/${selectedSubject.id}`,{method:'POST'});
      const profileId=Number(result?.profile?.id||0);
      if(!profileId) throw new Error('Profil kimliği oluşturulamadı.');
      await reloadSnapshot(profileId);
      setMessage(result?.created?'Dijital personel kartı oluşturuldu.':'Mevcut dijital personel kartı açıldı.');
    }catch(x){setError(x?.message||'Dijital personel kartı başlatılamadı.')}
    finally{setBusy(false)}
  }

  async function saveContact(event){
    event.preventDefault();
    if(!snapshot?.profile?.id) return;
    setBusy(true);setError('');setMessage('');
    try{
      await api(`/osgb-personnel-profiles/${snapshot.profile.id}/contacts`,{
        method:'POST',
        body:JSON.stringify(cleanBody(contactForm)),
      });
      await reloadSnapshot();
      setContactForm(EMPTY_CONTACT);
      setMessage(contactForm.entry_key?'İletişim bilgisinin yeni sürümü kaydedildi.':'İletişim bilgisi eklendi.');
    }catch(x){setError(x?.message||'İletişim bilgisi kaydedilemedi.')}
    finally{setBusy(false)}
  }

  async function saveCompetency(event){
    event.preventDefault();
    if(!snapshot?.profile?.id) return;
    setBusy(true);setError('');setMessage('');
    try{
      await api(`/osgb-personnel-profiles/${snapshot.profile.id}/competencies`,{
        method:'POST',
        body:JSON.stringify(cleanBody(competencyForm)),
      });
      await reloadSnapshot();
      setCompetencyForm(EMPTY_COMPETENCY);
      setMessage(competencyForm.entry_key?'Görev/yeterlilik yeni sürüm olarak kaydedildi.':'Görev/yeterlilik eklendi.');
    }catch(x){setError(x?.message||'Görev veya yeterlilik kaydedilemedi.')}
    finally{setBusy(false)}
  }

  async function saveExperience(event){
    event.preventDefault();
    if(!snapshot?.profile?.id) return;
    setBusy(true);setError('');setMessage('');
    try{
      await api(`/osgb-personnel-profiles/${snapshot.profile.id}/experiences`,{
        method:'POST',
        body:JSON.stringify(cleanBody(experienceForm)),
      });
      await reloadSnapshot();
      setExperienceForm(EMPTY_EXPERIENCE);
      setMessage(experienceForm.entry_key?'Deneyim yeni sürüm olarak kaydedildi.':'Deneyim eklendi.');
    }catch(x){setError(x?.message||'Deneyim kaydedilemedi.')}
    finally{setBusy(false)}
  }

  async function archiveEntry(entryType,row,label){
    if(!snapshot?.profile?.id||!row?.entry_key||!canWrite) return;
    if(!window.confirm(`${label} kaydını arşivlemek istediğinizden emin misiniz? Geçmiş sürümler korunacaktır.`)) return;
    setBusy(true);setError('');setMessage('');
    try{
      await api(`/osgb-personnel-profiles/${snapshot.profile.id}/entries/${entryType}/${encodeURIComponent(row.entry_key)}/archive`,{
        method:'POST',
        body:JSON.stringify({reason:`${label} OSGB yöneticisi tarafından personel kartından arşivlendi.`}),
      });
      await reloadSnapshot();
      setMessage(`${label} arşivlendi; tarihsel sürümler korundu.`);
    }catch(x){setError(x?.message||`${label} arşivlenemedi.`)}
    finally{setBusy(false)}
  }

  function editContact(row){
    setContactForm({
      entry_key:row.entry_key,
      contact_type:row.contact_type,
      label:row.label||'',
      contact_value:row.contact_value||'',
      is_primary:Boolean(row.is_primary),
      visibility:row.visibility||'internal_only',
      change_reason:'İletişim bilgisi güncellendi',
    });
    setTab('contacts');
  }

  function editCompetency(row){
    setCompetencyForm({
      entry_key:row.entry_key,
      category:row.category||'professional_duty',
      name:row.name||'',
      start_date:row.start_date||'',
      end_date:row.end_date||'',
      certificate_number:row.certificate_number||'',
      issuing_organization:row.issuing_organization||'',
      description:row.description||'',
      change_reason:'Görev veya yeterlilik bilgisi güncellendi',
    });
    setTab('competencies');
  }

  function editExperience(row){
    setExperienceForm({
      entry_key:row.entry_key,
      organization_name:row.organization_name||'',
      position:row.position||'',
      start_date:row.start_date||'',
      end_date:row.end_date||'',
      employment_type:row.employment_type||'',
      sector:row.sector||'',
      nace_activity:row.nace_activity||'',
      project_name:row.project_name||'',
      professional_summary:row.professional_summary||'',
      responsibilities:row.responsibilities||'',
      visibility:row.visibility||'internal_only',
      change_reason:'Deneyim bilgisi güncellendi',
    });
    setTab('experience');
  }

  const subjectAssignments=useMemo(()=>{
    if(selectedSubject?.subjectType!=='professional') return [];
    return assignments.filter((row)=>Number(row?.professional_id)===Number(selectedSubject.id));
  },[assignments,selectedSubject]);

  if(loading){
    return <section className="ppm-page"><div className="ppm-loading">Dijital personel yönetimi hazırlanıyor…</div></section>;
  }

  return (
    <section className="ppm-page" aria-label="Dijital Personel Yönetimi">
      <header className="ppm-page__header">
        <div>
          <span>OSGB PERSONEL YÖNETİMİ</span>
          <h3>Dijital Personel Kartları</h3>
          <p>Yalnız OSGB bünyesindeki iş güvenliği uzmanı, işyeri hekimi ve diğer sağlık personeli.</p>
        </div>
        <button type="button" className="secondary ppm-back" onClick={onClose}><ArrowLeft size={18}/> Önceki ekrana dön</button>
      </header>

      <div className="ppm-safety" role="status">
        <ShieldCheck size={20}/>
        <div><strong>Standart profesyonel veriler</strong><span>Sağlık, adli sicil, maaş, disiplin, ev adresi ve acil kişi bu ekranda işlenmez.</span></div>
      </div>

      {error&&<div className="ppm-alert ppm-alert--error" role="alert">{error}</div>}
      {message&&<div className="ppm-alert ppm-alert--success" role="status">{message}</div>}

      <div className="ppm-toolbar">
        <label className="ppm-search">
          <span>İSG profesyoneli ara</span>
          <div><Search size={18}/><input value={query} onChange={(event)=>setQuery(event.target.value)} placeholder="Ad, profesyonel türü veya belge sınıfı"/></div>
        </label>
      </div>

      <div className="ppm-layout">
        <aside className="ppm-subjects" aria-label="OSGB İSG profesyonelleri listesi">
          <div className="ppm-subjects__head"><strong>{filteredSubjects.length} kayıt</strong><small>OSGB bünyesindeki İSG profesyonelleri</small></div>
          {filteredSubjects.length===0?<EmptyState title="Kayıt bulunamadı" description="Arama ölçütünü değiştirin veya İSG Profesyonelleri ekranından OSGB kadrosuna kayıt ekleyin."/>:
            filteredSubjects.map((row)=>(
              <button key={row.subjectKey} type="button" className={selectedKey===row.subjectKey?'is-selected':''} onClick={()=>setSelectedKey(row.subjectKey)}>
                <span className="ppm-mini-avatar">{safeInitials(row.fullName)}</span>
                <span><strong>{row.fullName}</strong><small>{row.subtitle}</small><em>{row.active?'Aktif':'Pasif / Askıda'}</em></span>
              </button>
            ))}
        </aside>

        <div className="ppm-card-workspace">
          {!selectedSubject||!summary?<EmptyState title="İSG profesyoneli seçin" description="Dijital kartı görüntülemek için OSGB profesyonelleri listesinden bir kayıt seçin."/>:(
            <>
              <section className="ppm-identity">
                <div className="ppm-avatar">{safeInitials(summary.fullName)}</div>
                <div className="ppm-identity__copy">
                  <span>OSGB Profesyonel Dijital Kartı</span>
                  <h4>{summary.fullName}</h4>
                  <p>{summary.professionalTypeLabel}</p>
                  <div><StatusPill tone="success">{employmentStatusLabel(summary.employmentStatus)}</StatusPill>{snapshot?.profile?.id&&<StatusPill tone="info">Profil #{snapshot.profile.id}</StatusPill>}</div>
                </div>
                {!snapshot&&canWrite&&<button type="button" onClick={startProfile} disabled={busy}><IdCard size={18}/>{busy?'Hazırlanıyor…':'Kartı başlat / aç'}</button>}
                {!snapshot&&!canWrite&&<StatusPill>Yönetici yetkisi gerekli</StatusPill>}
              </section>

              <nav className="ppm-tabs" aria-label="Profesyonel kartı bölümleri">
                {PROFILE_MANAGER_TABS.map(([id,label])=><button key={id} type="button" className={tab===id?'is-active':''} onClick={()=>setTab(id)}>{label}</button>)}
              </nav>

              <div className="ppm-tab-content">
                {tab==='overview'&&(
                  <div className="ppm-section-stack">
                    <section className="ppm-summary-grid">
                      <SummaryField label="Görev / Unvan" value={summary.jobTitle||summary.professionalTypeLabel}/>
                      <SummaryField label="E-posta" value={summary.email}/>
                      <SummaryField label="Telefon" value={summary.phone}/>
                      <SummaryField label="Belge sınıfı" value={summary.certificateClass}/>
                      <SummaryField label="Belge numarası" value={summary.certificateNumber}/>
                      <SummaryField label="Belge tarihi" value={formatProfileDate(summary.certificateDate)}/>
                      <SummaryField label="Aktif görevlendirme" value={String(summary.activeAssignmentCount)}/>
                    </section>
                    <section className="ppm-metrics">
                      <div><Mail size={22}/><strong>{activeContacts.length}</strong><span>Aktif iletişim</span></div>
                      <div><GraduationCap size={22}/><strong>{activeCompetencies.length}</strong><span>Görev/yeterlilik</span></div>
                      <div><BriefcaseBusiness size={22}/><strong>{activeExperiences.length}</strong><span>Deneyim</span></div>
                      <div><History size={22}/><strong>{history.length}</strong><span>Profil olayı</span></div>
                    </section>
                    {!snapshot&&<div className="ppm-start-card"><IdCard size={32}/><div><strong>Profil uzantısı henüz başlatılmadı</strong><p>Mevcut İSG profesyoneli kaydı değişmez. Kartı başlattığınızda iletişim, görev/yeterlilik ve deneyim sürümleri ayrı tablolarda güvenle tutulur.</p></div>{canWrite&&<button type="button" onClick={startProfile} disabled={busy}>Dijital kartı oluştur</button>}</div>}
                  </div>
                )}

                {tab==='contacts'&&(
                  !snapshot?<EmptyState title="Önce kartı başlatın" description="İletişim sürümleri, dijital personel kartı oluşturulduktan sonra yönetilebilir."/>:
                  <div className="ppm-management-grid">
                    <section>
                      <div className="ppm-section-title"><div><h5>İletişim Bilgileri</h5><p>Kurumsal ve profesyonel iletişim alanları yeni sürüm olarak kaydedilir.</p></div><StatusPill tone="info">{activeContacts.length} aktif</StatusPill></div>
                      <div className="ppm-record-list">
                        {activeContacts.length===0?<EmptyState title="İletişim bilgisi yok" description="Kurumsal e-posta veya telefon ekleyin."/>:activeContacts.map((row)=><article key={row.entry_key}><div><strong>{row.label||row.contact_type}</strong><span>{row.contact_value}</span><small>Sürüm {row.version} · {row.verification_status}</small></div>{canWrite&&<div><button type="button" className="mini secondary" onClick={()=>editContact(row)}>Düzenle</button><button type="button" className="mini danger" onClick={()=>archiveEntry('contacts',row,'İletişim bilgisi')}><Archive size={15}/>Arşivle</button></div>}</article>)}
                      </div>
                    </section>
                    {canWrite&&<form className="ppm-form" onSubmit={saveContact}>
                      <h5>{contactForm.entry_key?'İletişim bilgisi güncelle':'Yeni iletişim bilgisi'}</h5>
                      <label><span>Tür</span><select value={contactForm.contact_type} onChange={(e)=>setContactForm({...contactForm,contact_type:e.target.value})} disabled={Boolean(contactForm.entry_key)}><option value="corporate_email">Kurumsal e-posta</option><option value="alternative_email">Alternatif e-posta</option><option value="business_phone">İş telefonu</option><option value="mobile_phone">Cep telefonu</option></select></label>
                      <label><span>Etiket</span><input value={contactForm.label} onChange={(e)=>setContactForm({...contactForm,label:e.target.value})} placeholder="Örn. Kurumsal"/></label>
                      <label><span>İletişim bilgisi</span><input required value={contactForm.contact_value} onChange={(e)=>setContactForm({...contactForm,contact_value:e.target.value})}/></label>
                      <label><span>Görünürlük</span><select value={contactForm.visibility} onChange={(e)=>setContactForm({...contactForm,visibility:e.target.value})}><option value="internal_only">Yalnız iç kullanım</option><option value="cv_eligible">CV için seçilebilir</option><option value="share_eligible">Paylaşım için seçilebilir</option></select></label>
                      <label className="ppm-check"><input type="checkbox" checked={contactForm.is_primary} onChange={(e)=>setContactForm({...contactForm,is_primary:e.target.checked})}/><span>Birincil iletişim</span></label>
                      {contactForm.entry_key&&<label><span>Değişiklik nedeni</span><input required minLength={3} value={contactForm.change_reason} onChange={(e)=>setContactForm({...contactForm,change_reason:e.target.value})}/></label>}
                      <FormActions editing={Boolean(contactForm.entry_key)} onCancel={()=>setContactForm(EMPTY_CONTACT)} busy={busy}/>
                    </form>}
                  </div>
                )}

                {tab==='competencies'&&(
                  !snapshot?<EmptyState title="Önce kartı başlatın" description="Görev, uzmanlık ve yeterlilik kayıtları kart oluşturulduktan sonra eklenebilir."/>:
                  <div className="ppm-management-grid">
                    <section>
                      <div className="ppm-section-title"><div><h5>Görevler ve Mesleki Yeterlilikler</h5><p>Uygulama giriş rolünden ayrı mesleki görev, uzmanlık ve eğitim yetkileri.</p></div><StatusPill tone="info">{activeCompetencies.length} aktif</StatusPill></div>
                      <div className="ppm-record-list">
                        {activeCompetencies.length===0?<EmptyState title="Görev veya yeterlilik yok" description="Personelin profesyonel görevini, uzmanlığını ya da sertifika temelli yeterliliğini ekleyin."/>:activeCompetencies.map((row)=><article key={row.entry_key}><div><strong>{row.name}</strong><span>{row.issuing_organization||row.category}</span><small>{formatProfileDate(row.start_date)} {row.end_date?`– ${formatProfileDate(row.end_date)}`:''} · Sürüm {row.version}</small></div>{canWrite&&<div><button type="button" className="mini secondary" onClick={()=>editCompetency(row)}>Düzenle</button><button type="button" className="mini danger" onClick={()=>archiveEntry('competencies',row,'Görev/yeterlilik')}><Archive size={15}/>Arşivle</button></div>}</article>)}
                      </div>
                    </section>
                    {canWrite&&<form className="ppm-form" onSubmit={saveCompetency}>
                      <h5>{competencyForm.entry_key?'Görev/yeterlilik güncelle':'Yeni görev veya yeterlilik'}</h5>
                      <label><span>Kategori</span><select value={competencyForm.category} onChange={(e)=>setCompetencyForm({...competencyForm,category:e.target.value})} disabled={Boolean(competencyForm.entry_key)}><option value="professional_duty">Mesleki görev</option><option value="certificate_based">Belge temelli yeterlilik</option><option value="technical_specialization">Teknik uzmanlık</option><option value="training_authority">Eğitim verme yetkisi</option><option value="other">Diğer</option></select></label>
                      <label><span>Görev / yeterlilik adı</span><input required minLength={2} value={competencyForm.name} onChange={(e)=>setCompetencyForm({...competencyForm,name:e.target.value})}/></label>
                      <div className="ppm-form-row"><label><span>Başlangıç</span><input type="date" value={competencyForm.start_date} onChange={(e)=>setCompetencyForm({...competencyForm,start_date:e.target.value})}/></label><label><span>Bitiş</span><input type="date" value={competencyForm.end_date} onChange={(e)=>setCompetencyForm({...competencyForm,end_date:e.target.value})}/></label></div>
                      <label><span>Belge numarası</span><input value={competencyForm.certificate_number} onChange={(e)=>setCompetencyForm({...competencyForm,certificate_number:e.target.value})}/></label>
                      <label><span>Veren kurum</span><input value={competencyForm.issuing_organization} onChange={(e)=>setCompetencyForm({...competencyForm,issuing_organization:e.target.value})}/></label>
                      <label><span>Açıklama</span><textarea rows={3} value={competencyForm.description} onChange={(e)=>setCompetencyForm({...competencyForm,description:e.target.value})}/></label>
                      {competencyForm.entry_key&&<label><span>Değişiklik nedeni</span><input required minLength={3} value={competencyForm.change_reason} onChange={(e)=>setCompetencyForm({...competencyForm,change_reason:e.target.value})}/></label>}
                      <FormActions editing={Boolean(competencyForm.entry_key)} onCancel={()=>setCompetencyForm(EMPTY_COMPETENCY)} busy={busy}/>
                    </form>}
                  </div>
                )}

                {tab==='experience'&&(
                  !snapshot?<EmptyState title="Önce kartı başlatın" description="Profesyonel deneyim kayıtları kart oluşturulduktan sonra eklenebilir."/>:
                  <div className="ppm-management-grid">
                    <section>
                      <div className="ppm-section-title"><div><h5>Profesyonel Deneyim</h5><p>Gizli müşteri dokümanı içermeyen iş ve proje deneyimi özetleri.</p></div><StatusPill tone="info">{activeExperiences.length} aktif</StatusPill></div>
                      <div className="ppm-record-list">
                        {activeExperiences.length===0?<EmptyState title="Deneyim kaydı yok" description="Kurum, görev, sektör ve profesyonel sorumluluk özetini ekleyin."/>:activeExperiences.map((row)=><article key={row.entry_key}><div><strong>{row.position}</strong><span>{row.organization_name}{row.project_name?` · ${row.project_name}`:''}</span><small>{formatProfileDate(row.start_date)} {row.end_date?`– ${formatProfileDate(row.end_date)}`:'– Devam'} · Sürüm {row.version}</small></div>{canWrite&&<div><button type="button" className="mini secondary" onClick={()=>editExperience(row)}>Düzenle</button><button type="button" className="mini danger" onClick={()=>archiveEntry('experiences',row,'Deneyim')}><Archive size={15}/>Arşivle</button></div>}</article>)}
                      </div>
                    </section>
                    {canWrite&&<form className="ppm-form" onSubmit={saveExperience}>
                      <h5>{experienceForm.entry_key?'Deneyim güncelle':'Yeni deneyim'}</h5>
                      <label><span>Firma / kuruluş</span><input required minLength={2} value={experienceForm.organization_name} onChange={(e)=>setExperienceForm({...experienceForm,organization_name:e.target.value})}/></label>
                      <label><span>Görev / pozisyon</span><input required minLength={2} value={experienceForm.position} onChange={(e)=>setExperienceForm({...experienceForm,position:e.target.value})}/></label>
                      <div className="ppm-form-row"><label><span>Başlangıç</span><input type="date" value={experienceForm.start_date} onChange={(e)=>setExperienceForm({...experienceForm,start_date:e.target.value})}/></label><label><span>Bitiş</span><input type="date" value={experienceForm.end_date} onChange={(e)=>setExperienceForm({...experienceForm,end_date:e.target.value})}/></label></div>
                      <div className="ppm-form-row"><label><span>Çalışma türü</span><input value={experienceForm.employment_type} onChange={(e)=>setExperienceForm({...experienceForm,employment_type:e.target.value})}/></label><label><span>Sektör</span><input value={experienceForm.sector} onChange={(e)=>setExperienceForm({...experienceForm,sector:e.target.value})}/></label></div>
                      <label><span>NACE alanı</span><input value={experienceForm.nace_activity} onChange={(e)=>setExperienceForm({...experienceForm,nace_activity:e.target.value})}/></label>
                      <label><span>Proje adı</span><input value={experienceForm.project_name} onChange={(e)=>setExperienceForm({...experienceForm,project_name:e.target.value})}/></label>
                      <label><span>Profesyonel özet</span><textarea rows={3} value={experienceForm.professional_summary} onChange={(e)=>setExperienceForm({...experienceForm,professional_summary:e.target.value})}/></label>
                      <label><span>Sorumluluklar</span><textarea rows={4} value={experienceForm.responsibilities} onChange={(e)=>setExperienceForm({...experienceForm,responsibilities:e.target.value})}/></label>
                      <label><span>Görünürlük</span><select value={experienceForm.visibility} onChange={(e)=>setExperienceForm({...experienceForm,visibility:e.target.value})}><option value="internal_only">Yalnız iç kullanım</option><option value="cv_eligible">CV için seçilebilir</option></select></label>
                      {experienceForm.entry_key&&<label><span>Değişiklik nedeni</span><input required minLength={3} value={experienceForm.change_reason} onChange={(e)=>setExperienceForm({...experienceForm,change_reason:e.target.value})}/></label>}
                      <FormActions editing={Boolean(experienceForm.entry_key)} onCancel={()=>setExperienceForm(EMPTY_EXPERIENCE)} busy={busy}/>
                    </form>}
                  </div>
                )}

                {tab==='assignments'&&(
                  <div className="ppm-section-stack">
                    <div className="ppm-section-title"><div><h5>Atamalar ve Görev Geçmişi</h5><p>Mevcut görevlendirme kayıtları kopyalanmadan salt okunur gösterilir.</p></div></div>
                    {selectedSubject.subjectType==='professional'?(
                      subjectAssignments.length?subjectAssignments.map((row,index)=><article className="ppm-assignment" key={row.id||index}><BriefcaseBusiness size={22}/><div><strong>{row.company_name||row.companyName||`İşyeri #${row.company_id||''}`}</strong><span>{row.professional_type||summary.professionalTypeLabel}</span><small>{formatProfileDate(row.start_date)} {row.end_date?`– ${formatProfileDate(row.end_date)}`:'– Devam'} · {row.status||'active'}</small></div></article>):<EmptyState title="Aktif görevlendirme bulunamadı" description="Profesyonel profil erişimi yalnız aktif görevlendirmesi olan işyerleriyle sınırlandırılır."/>
                    ):<div className="ppm-assignment"><UserRound size={22}/><div><strong>{summary.companyName}</strong><span>{summary.jobTitle||'İşyeri personeli'}</span><small>{summary.branchName||'Şube bilgisi yok'} · {employmentStatusLabel(summary.employmentStatus)}</small></div></div>}
                  </div>
                )}

                {tab==='documents'&&<CapabilityNotice icon={FileText} title="Sertifikalar ve Belgeler" description="Diploma, mesleki belge, MYK, operatör ve diğer standart belgeler private Cloudflare R2 üzerinde sürümlü yönetilecektir." nextPhase="Dosya yükleme bu sürümde bilerek kapalıdır; doğrulanmış MIME, checksum, AV taraması ve atomik rollback Faz 4B’de kurulacaktır."/>}
                {tab==='cv'&&<CapabilityNotice icon={IdCard} title="CV ve Profesyonel Profil" description="Mevcut CV yükleme, eski sürümleri koruma ve seçili alanlardan A4 PDF CV üretimi ayrı güvenlik kapısında uygulanacaktır." nextPhase="T.C. kimlik, sağlık, adli sicil, özel adres, maaş ve disiplin verileri standart CV’ye otomatik eklenmeyecektir."/>}
                {tab==='sharing'&&<CapabilityNotice icon={ShieldCheck} title="Kontrollü Paylaşım" description="Alıcı, amaç, seçili alanlar ve son kullanma tarihi tanımlanmadan hiçbir profil paketi paylaşılmayacaktır." nextPhase="Kalıcı public URL ve varsayılan hassas belge seçimi yoktur. Dış paylaşım feature flag’i kapalı kalır."/>}

                {tab==='history'&&(
                  !snapshot?<EmptyState title="Henüz profil geçmişi yok" description="Dijital kart başlatıldığında profil ve sürüm olayları burada gösterilir."/>:
                  <div className="ppm-section-stack">
                    <div className="ppm-section-title"><div><h5>Denetim ve Değişiklik Geçmişi</h5><p>Bu görünüm son sürümlerin meta geçmişidir; ayrıntılı güvenlik audit kayıtları mevcut merkezi audit sisteminde tutulur.</p></div><StatusPill>{archivedProfileRows([...(snapshot.contacts||[]),...(snapshot.competencies||[]),...(snapshot.experiences||[])]).length} arşivli</StatusPill></div>
                    <div className="ppm-timeline">{history.map((row,index)=><article key={`${row.category}-${row.id}-${index}`}><span className="ppm-timeline__icon">{row.status==='archived'?<Archive size={16}/>:<CheckCircle2 size={16}/>}</span><div><strong>{row.title}</strong><span>{row.category} · Sürüm {row.version} · {row.status==='archived'?'Arşivlendi':'Aktif'}</span><small><Clock3 size={13}/>{formatProfileDate(row.createdAt)}</small></div></article>)}</div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
