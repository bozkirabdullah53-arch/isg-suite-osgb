import React,{useEffect,useMemo,useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {AlertTriangle,BarChart3,Bell,Building2,BriefcaseBusiness,CalendarDays,ClipboardCheck,CreditCard,Download,FileText,GitBranch,GraduationCap,HardHat,HeartPulse,KeyRound,LayoutDashboard,LogOut,Plus,RefreshCw,Search,ShieldAlert,ShieldCheck,Stethoscope,Upload,UserCog,Users,WalletCards,X} from 'lucide-react';
import {api, downloadFile} from './api';import {OsgbDashboard,ProfessionalsPage,AssignmentsPage,VisitsPage,CrmPage,FinancePage} from './osgb';import {OsgbOversightPage} from './osgb_oversight';
import {ProPerformancePage} from './pro_performance';
import {CsgbAuditPackPage} from './csgb_audit_pack';
import {TrainingPage, TrainingVerifyPage} from './training';import {RiskPage} from './risk';import {IncidentsPage, CapaPage} from './incidents';import {PpePage} from './ppe';import {AnnualPlansPage} from './annual_plans';import {HealthPage} from './health';
import {DutyDashboard} from './duty_dashboard';
import {
  EisaOverviewPage,
  EisaOsgbUsersPage,
  EisaSubscriptionsPage,
  EisaExpiringSubscriptionsPage,
  EisaExpiredSubscriptionsPage,
  EisaPaymentsPage,
  EisaPackagesPage,
  EisaNotificationsPage,
  EisaReportsPage,
  EisaAuditLogsPage,
  EisaArchivesPage,
  EisaSystemSettingsPage,
  OsgbApplyPage,
} from './eisa';
import './styles.css';
const roles={global_admin:'EİSA Yönetici',company_admin:'Firma Yöneticisi',safety_specialist:'İSG Uzmanı',workplace_physician:'İşyeri Hekimi',other_health_personnel:'Diğer Sağlık Personeli',read_only:'Salt Okunur'};
/**
 * Sol menü sırası (yukarı→aşağı): ana panel → günlük operasyon → master data →
 * İSG saha işleri (risk/olay yoğunluğu) → ticari → rapor/denetim → sistem ayarları.
 * Her rol yalnızca kendi listesini görür; sıra o rolün kullanım yoğunluğuna göredir.
 */
const roleModules={
  global_admin:[
    // SaaS-only EİSA kontrol paneli (operasyon modülleri yok)
    'eisa_overview',
    'eisa_osgb_users',
    'eisa_subscriptions',
    'eisa_subscriptions_expiring',
    'eisa_subscriptions_expired',
    'eisa_payments',
    'eisa_packages',
    'eisa_notifications',
    'eisa_reports',
    'eisa_archives',
    'eisa_audit_logs',
    'eisa_system_settings',
  ],
  company_admin:[
    'osgb_dashboard','dashboard',
    'professionals','assignments',
    'companies','branches','employees',
    'training','documents',
    'crm','finance',
    'reports',
    'notifications','users','subscription','security',
  ],
  safety_specialist:[
    'dashboard','visits',
    'risk','near_miss','accident','capa','ppe',
    'training','annual_plans','documents',
    'security',
  ],
  workplace_physician:[
    'dashboard','visits',
    'health','employees',
    'annual_plans','documents',
    'security',
  ],
  other_health_personnel:[
    'dashboard','visits',
    'health','employees',
    'annual_plans','documents',
    'security',
  ],
  read_only:['dashboard'],
};
const menuCatalog={
  eisa_overview:['Genel Bakış',LayoutDashboard],
  eisa_osgb_users:['OSGB Kullanıcıları',Users],
  eisa_subscriptions:['Abonelik Yönetimi',CreditCard],
  eisa_subscriptions_expiring:['Süresi Yaklaşan Abonelikler',CalendarDays],
  eisa_subscriptions_expired:['Süresi Dolan Abonelikler',AlertTriangle],
  eisa_payments:['Finans ve Ödemeler',WalletCards],
  eisa_packages:['Paket Yönetimi',BriefcaseBusiness],
  eisa_notifications:['Bilgilendirmeler',Bell],
  eisa_reports:['Raporlar',BarChart3],
  eisa_archives:['Merkezi Arşiv',Download],
  eisa_audit_logs:['İşlem Kayıtları',FileText],
  eisa_system_settings:['Sistem Ayarları',KeyRound],
  osgb_dashboard:['OSGB Ana Panel',LayoutDashboard],
  osgb_oversight:['Hizmet Denetimi',ClipboardCheck],
  pro_performance:['Performans Raporu',BarChart3],
  csgb_audit:['ÇSGB Belge Paketi',FileText],
  professionals:['İSG Profesyonelleri',Stethoscope],
  assignments:['Görevlendirmeler',BriefcaseBusiness],
  visits:['Saha Takvimi',CalendarDays],
  crm:['CRM / Teklif',BriefcaseBusiness],
  finance:['Finans',WalletCards],
  dashboard:['İSG Özeti',BarChart3],
  companies:['İşyerleri',Building2],
  branches:['Şubeler',GitBranch],
  employees:['Personel',Users],
  risk:['Risk Analizi',ShieldAlert],
  near_miss:['Ramak Kala',AlertTriangle],
  accident:['İş Kazaları',ShieldAlert],
  capa:['DÖF',ClipboardCheck],
  ppe:['KKD Takip',HardHat],
  training:['Eğitimler',GraduationCap],
  health:['Sağlık',HeartPulse],
  documents:['Dokümanlar',FileText],
  annual_plans:['Yıllık Plan',ClipboardCheck],
  reports:['Raporlar',BarChart3],
  notifications:['Bildirimler',Bell],
  subscription:['Abonelik',CreditCard],
  security:['Güvenlik',KeyRound],
  users:['Kullanıcılar',UserCog],
};
function Login({done,onApply}){const[email,setEmail]=useState(''),[password,setPassword]=useState(''),[err,setErr]=useState('');async function submit(e){e.preventDefault();setErr('');try{const r=await api('/auth/login',{method:'POST',body:JSON.stringify({email,password})});localStorage.setItem('isg_token',r.access_token);done()}catch(x){setErr(x.message)}}return <main className="login-shell"><div className="login-wrap"><div className="login-brand"><img src="/eisa-logo-horizontal.png" alt="EİSA PROGRAMLAMA" className="login-eisa-logo"/></div><section className="login-card"><h1>İSG Suite</h1><p>İş Sağlığı ve Güvenliği Yönetim Sistemi</p><form onSubmit={submit}><label>E-posta</label><input value={email} onChange={e=>setEmail(e.target.value)} type="email"/><label>Şifre</label><input value={password} onChange={e=>setPassword(e.target.value)} type="password"/>{err&&<div className="error">{err}</div>}<button>Giriş Yap</button></form><p style={{marginTop:16,fontSize:13,color:'#64748b'}}>OSGB merkezi misiniz? <button type="button" className="linkish" onClick={onApply}>Başvuru formu</button></p></section></div></main>}
function Modal({title,close,children}){return <div className="modal-bg" onMouseDown={e=>e.target===e.currentTarget&&close()}><section className="modal"><header><h3>{title}</h3><button className="icon" onClick={close}><X/></button></header>{children}</section></div>}
function Field({label,...p}){return <label className="field"><span>{label}</span><input {...p}/></label>}
function Select({label,children,...p}){return <label className="field"><span>{label}</span><select {...p}>{children}</select></label>}
function Table({cols,rows,empty='Kayıt bulunamadı.'}){return <div className="table-wrap"><table><thead><tr>{cols.map(c=><th key={c.key}>{c.label}</th>)}</tr></thead><tbody>{rows.length?rows.map((r,i)=><tr key={r.id??i}>{cols.map(c=><td key={c.key}>{c.render?c.render(r):String(r[c.key]??'—')}</td>)}</tr>):<tr><td colSpan={cols.length} className="empty">{empty}</td></tr>}</tbody></table></div>}
function Companies({canEdit, canAdd}){
  const[data,setData]=useState([]);
  const[open,setOpen]=useState(false);
  const[q,setQ]=useState('');
  const[busy,setBusy]=useState(false);
  const[err,setErr]=useState('');
  const[creds,setCreds]=useState(null);
  const[copyMsg,setCopyMsg]=useState('');
  const emptyForm={name:'',sgk_registry_no:'',address:'',phone:'',authorized_person:'',hazard_class:'Az Tehlikeli'};
  const[form,setForm]=useState(emptyForm);
  async function copyText(text){
    const v=String(text||'');
    if(!v) return false;
    try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(v);return true}}catch(_){/* */}
    try{
      const ta=document.createElement('textarea');
      ta.value=v;ta.setAttribute('readonly','');ta.style.position='fixed';ta.style.left='-9999px';
      document.body.appendChild(ta);ta.select();
      const ok=document.execCommand('copy');document.body.removeChild(ta);return ok;
    }catch(_){return false}
  }
  const load=()=>{
    setErr('');
    const p=new URLSearchParams();
    if(q) p.set('q',q);
    // Global yönetici aktif+pasif görsün (backend: active=None)
    return api('/companies'+(p.toString()?`?${p}`:'')).then(setData).catch(e=>setErr(e.message));
  };
  useEffect(()=>{void load()},[]);
  async function save(e){
    e.preventDefault();setBusy(true);setErr('');
    const payload={...form,sgk_registry_no:(form.sgk_registry_no||'').trim()};
    if(!payload.sgk_registry_no){setErr('İşyeri sicil numarası zorunludur.');setBusy(false);return}
    try{
      const created=await api('/companies',{method:'POST',body:JSON.stringify(payload)});
      setOpen(false);
      setForm(emptyForm);
      await load();
      if(created?.login_account){
        setCreds(created.login_account);
      }
    }catch(ex){setErr(ex.message)}
    finally{setBusy(false)}
  }
  async function act(row,action){
    if(action==='delete'){
      if(!window.confirm(`“${row.name}” işyerini KALICI olarak silmek istiyor musunuz?\n\nPersonel, eğitim, risk, sağlık ve diğer bağlı kayıtlar da silinir. Bu işlem geri alınamaz.`)) return;
    }else{
      const labels={deactivate:'pasife almak',activate:'yeniden aktifleştirmek'};
      if(!window.confirm(`“${row.name}” işyerini ${labels[action]||action} istiyor musunuz?`)) return;
    }
    setBusy(true);setErr('');
    try{
      if(action==='delete'){
        await api(`/companies/${row.id}`,{method:'DELETE'});
      }else{
        await api(`/companies/${row.id}/${action}`,{method:'PATCH'});
      }
      await load();
    }catch(ex){setErr(ex.message||'İşlem başarısız.')}
    finally{setBusy(false)}
  }
  return <Page title="Firma Yönetimi" action={canAdd&&<button type="button" disabled={busy} onClick={()=>{setErr('');setOpen(true)}}><Plus/>Firma Ekle</button>}>
    {err&&<p style={{color:'#b91c1c'}}>{err}</p>}
    <SearchBar q={q} setQ={setQ} go={load}/>
    <Table cols={[
      {key:'name',label:'Firma'},
      {key:'sgk_registry_no',label:'İşyeri Sicil No'},
      {key:'authorized_person',label:'Yetkili Kişi'},
      {key:'phone',label:'Telefon'},
      {key:'address',label:'Adres'},
      {key:'hazard_class',label:'Tehlike Sınıfı'},
      {key:'is_active',label:'Durum',render:r=><Badge ok={r.is_active}/>},
      ...(canEdit?[{key:'actions',label:'İşlem',render:r=>(
        <div className="actions" style={{gap:6,flexWrap:'wrap'}}>
          {r.is_active
            ? <button type="button" className="mini" disabled={busy} onClick={()=>act(r,'deactivate')}>Pasife Al</button>
            : <button type="button" className="mini" disabled={busy} onClick={()=>act(r,'activate')}>Aktifleştir</button>}
          <button type="button" className="mini" disabled={busy} onClick={()=>act(r,'delete')}>Sil</button>
        </div>
      )}]:[]),
    ]} rows={data}/>
    {open&&<Modal title="Yeni Firma" close={()=>setOpen(false)}>
      <form className="form-grid" onSubmit={save}>
        <Field label="Firma Adı" required value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/>
        <Field label="İşyeri Sicil No" required value={form.sgk_registry_no} onChange={e=>setForm({...form,sgk_registry_no:e.target.value})}/>
        <Field label="Yetkili Kişi" value={form.authorized_person} onChange={e=>setForm({...form,authorized_person:e.target.value})}/>
        <Field label="Telefon" value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/>
        <Field label="Adres" value={form.address} onChange={e=>setForm({...form,address:e.target.value})}/>
        <Select label="Tehlike Sınıfı" value={form.hazard_class} onChange={e=>setForm({...form,hazard_class:e.target.value})}>
          <option>Az Tehlikeli</option><option>Tehlikeli</option><option>Çok Tehlikeli</option>
        </Select>
        {err&&<p style={{color:'#b91c1c',gridColumn:'1/-1'}}>{err}</p>}
        <div className="form-actions"><button type="submit" disabled={busy}>{busy?'Kaydediliyor...':'Kaydet'}</button></div>
      </form>
    </Modal>}
    {creds&&<Modal title="İşyeri Giriş Bilgileri" close={()=>{setCreds(null);setCopyMsg('')}}>
      <div className="form-grid single">
        <p style={{marginTop:0,color:'#64748b'}}>Bu geçici bilgileri işyeri yetkilisine güvenli kanaldan iletin. İlk girişten sonra şifresini değiştirmesini isteyin.</p>
        <p style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap',marginBottom:0}}>
          <span><strong>Kullanıcı adı (e-posta):</strong> <code>{creds.email}</code></span>
          <button type="button" className="mini secondary" onClick={async()=>setCopyMsg((await copyText(creds.email))?'E-posta kopyalandı.':'Kopyalanamadı.')}>E-postayı kopyala</button>
        </p>
        <p><strong>Ad:</strong> {creds.full_name}</p>
        <p style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap',marginBottom:0}}>
          <span><strong>Geçici şifre:</strong> <code style={{userSelect:'all'}}>{creds.temporary_password}</code></span>
          <button type="button" className="mini" onClick={async()=>setCopyMsg((await copyText(creds.temporary_password))?'Şifre kopyalandı.':'Kopyalanamadı.')}>Şifreyi kopyala</button>
        </p>
        <div className="actions" style={{gap:8,flexWrap:'wrap'}}>
          <button type="button" className="secondary" onClick={async()=>{
            const text=`Kullanıcı adı: ${creds.email}\nGeçici şifre: ${creds.temporary_password}`;
            setCopyMsg((await copyText(text))?'E-posta ve şifre kopyalandı.':'Kopyalanamadı.');
          }}>E-posta + şifreyi kopyala</button>
        </div>
        {copyMsg&&<p style={{color:copyMsg.includes('amadı')?'#b91c1c':'#166534',margin:0}}>{copyMsg}</p>}
        <p style={{color:'#166534'}}>{creds.message}</p>
        <div className="form-actions"><button type="button" onClick={()=>{setCreds(null);setCopyMsg('')}}>Tamam</button></div>
      </div>
    </Modal>}
  </Page>;
}
function Branches({user}){const[companies,setCompanies]=useState([]),[data,setData]=useState([]),[open,setOpen]=useState(false),[form,setForm]=useState({company_id:user.company_id||'',name:'',sgk_registry_no:'',city:'',address:''});const load=()=>Promise.all([api('/companies'),api('/branches')]).then(([c,b])=>{setCompanies(c);setData(b)});useEffect(()=>{void load()},[]);async function save(e){e.preventDefault();await api('/branches',{method:'POST',body:JSON.stringify({...form,company_id:Number(form.company_id)})});setOpen(false);load()}return <Page title="Şube Yönetimi" action={<button onClick={()=>setOpen(true)}><Plus/>Şube Ekle</button>}><Table cols={[{key:'name',label:'Şube'},{key:'company_id',label:'Firma',render:r=>companies.find(c=>c.id===r.company_id)?.name||r.company_id},{key:'city',label:'Şehir'},{key:'sgk_registry_no',label:'SGK Sicil No'},{key:'is_active',label:'Durum',render:r=><Badge ok={r.is_active}/>}]} rows={data}/>{open&&<Modal title="Yeni Şube" close={()=>setOpen(false)}><form className="form-grid" onSubmit={save}><Select label="Firma" required value={form.company_id} onChange={e=>setForm({...form,company_id:e.target.value})}><option value="">Seçiniz</option>{companies.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</Select><Field label="Şube Adı" required value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/><Field label="Şehir" value={form.city} onChange={e=>setForm({...form,city:e.target.value})}/><Field label="SGK Sicil No" value={form.sgk_registry_no} onChange={e=>setForm({...form,sgk_registry_no:e.target.value})}/><Field label="Adres" value={form.address} onChange={e=>setForm({...form,address:e.target.value})}/><Submit/></form></Modal>}</Page>}
function UserPage({user}){
  const[companies,setCompanies]=useState([]),[data,setData]=useState([]),[open,setOpen]=useState(false),[err,setErr]=useState(''),[busy,setBusy]=useState(false);
  const[form,setForm]=useState({email:'',full_name:'',password:'',role:'workplace_physician',company_id:user.company_id||''});
  const load=()=>Promise.all([api('/companies'),api('/users')]).then(([c,u])=>{setCompanies(c);setData(u)}).catch(e=>setErr(e.message));
  useEffect(()=>{load()},[]);
  async function save(e){
    e.preventDefault();setErr('');setBusy(true);
    try{
      const field=['safety_specialist','workplace_physician','other_health_personnel'].includes(form.role);
      await api('/users',{method:'POST',body:JSON.stringify({
        ...form,
        company_id:form.role==='global_admin'?null:(form.company_id?Number(form.company_id):null),
      })});
      setOpen(false);
      setForm({email:'',full_name:'',password:'',role:'workplace_physician',company_id:user.company_id||''});
      await load();
      if(field){
        try{await api('/osgb/sync-field-roles',{method:'POST'})}catch(_){/* ignore */}
      }
    }catch(ex){setErr(ex.message)}
    finally{setBusy(false)}
  }
  async function setRole(row,role){
    if(row.id===user.id) return alert('Kendi rolünüzü buradan değiştiremezsiniz.');
    setErr('');
    try{
      await api(`/users/${row.id}`,{method:'PUT',body:JSON.stringify({role})});
      await load();
    }catch(ex){setErr(ex.message)}
  }
  async function syncRoles(){
    setErr('');setBusy(true);
    try{
      const r=await api('/osgb/sync-field-roles',{method:'POST'});
      alert(`Rol eşlemesi: ${r.users_linked||0} kullanıcı güncellendi (${r.professionals||0} profesyonel).`);
      await load();
    }catch(ex){setErr(ex.message)}
    finally{setBusy(false)}
  }
  async function suspend(row){
    if(row.id===user.id) return alert('Kendi hesabınızı askıya alamazsınız.');
    if(!window.confirm(`${row.full_name} askıya alınsın mı? Giriş yapamaz.`)) return;
    setErr('');
    try{await api(`/users/${row.id}/suspend`,{method:'PATCH'});await load()}
    catch(ex){setErr(ex.message)}
  }
  async function activate(row){
    setErr('');
    try{await api(`/users/${row.id}/activate`,{method:'PATCH'});await load()}
    catch(ex){setErr(ex.message)}
  }
  async function remove(row){
    if(row.id===user.id) return alert('Kendi hesabınızı silemezsiniz.');
    if(!window.confirm(`${row.full_name} kalıcı olarak silinsin mi? Bu işlem geri alınamaz.`)) return;
    setErr('');
    try{await api(`/users/${row.id}`,{method:'DELETE'});await load()}
    catch(ex){setErr(ex.message)}
  }
  const cols=[
    {key:'full_name',label:'Ad Soyad'},
    {key:'email',label:'E-posta'},
    {key:'role',label:'Rol',render:r=>(
      <select
        value={r.role}
        disabled={r.id===user.id}
        onChange={e=>setRole(r,e.target.value)}
        style={{maxWidth:180}}
        title="Rol değiştir"
      >
        {Object.entries(roles).filter(([k])=>user.role==='global_admin'||k!=='global_admin').map(([k,v])=><option key={k} value={k}>{v}</option>)}
      </select>
    )},
    {key:'company_id',label:'Firma',render:r=>companies.find(c=>c.id===r.company_id)?.name||'Sistem Geneli'},
    {key:'is_active',label:'Durum',render:r=><Badge ok={r.is_active}/>},
    {key:'action',label:'İşlem',render:r=>(
      <div className="actions" style={{gap:6,flexWrap:'wrap'}}>
        {r.is_active
          ? <button type="button" className="mini" disabled={r.id===user.id} onClick={()=>suspend(r)}>Askıya Al</button>
          : <button type="button" className="mini" onClick={()=>activate(r)}>Aktifleştir</button>}
        <button type="button" className="mini" disabled={r.id===user.id} onClick={()=>remove(r)}>Sil</button>
      </div>
    )},
  ];
  return <Page title="Kullanıcı ve Yetki Yönetimi" action={<div className="actions"><button type="button" className="secondary" disabled={busy} onClick={syncRoles}>Hekim/Uzman Rollerini Eşle</button><button onClick={()=>{setErr('');setOpen(true)}}><Plus/>Kullanıcı Ekle</button></div>}>
    <p style={{marginTop:0,color:'#475569',fontSize:14}}>Hekim / uzman / DSP için kullanıcı rolü <strong>İşyeri Hekimi</strong> / <strong>İSG Uzmanı</strong> / <strong>DSP</strong> olmalı. Görevlendirme sonrası e-posta veya ad eşleşirse otomatik düzelir; gerekirse aşağıdaki eşle butonunu kullanın.</p>
    {err&&<p style={{color:'#b91c1c'}}>{err}</p>}
    <Table cols={cols} rows={data}/>
    {open&&<Modal title="Yeni Kullanıcı" close={()=>setOpen(false)}>
      <form className="form-grid" onSubmit={save}>
        <Field label="Ad Soyad" required value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/>
        <Field label="E-posta" type="email" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/>
        <Field label="Geçici Şifre" type="password" minLength="10" required value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/>
        <Select label="Rol" value={form.role} onChange={e=>setForm({...form,role:e.target.value})}>
          {Object.entries(roles).filter(([k])=>user.role==='global_admin'||k!=='global_admin').map(([k,v])=><option key={k} value={k}>{v}</option>)}
        </Select>
        {form.role!=='global_admin'&&<Select label="Firma" value={form.company_id} onChange={e=>setForm({...form,company_id:e.target.value})} required={!['safety_specialist','workplace_physician','other_health_personnel'].includes(form.role)}>
          <option value="">Seçiniz / OSGB saha (opsiyonel)</option>{companies.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>}
        {err&&<p style={{color:'#b91c1c',gridColumn:'1/-1'}}>{err}</p>}
        <div className="form-actions"><button disabled={busy}>{busy?'Kaydediliyor...':'Kaydet'}</button></div>
      </form>
    </Modal>}
  </Page>
}function Employees({user}){const[companies,setCompanies]=useState([]),[branches,setBranches]=useState([]),[data,setData]=useState([]),[open,setOpen]=useState(false),[q,setQ]=useState(''),[form,setForm]=useState({company_id:user.company_id||'',branch_id:'',full_name:'',national_id_masked:'',job_title:'',department:'',start_date:'',special_status:''});const load=()=>Promise.all([api('/companies'),api('/branches'),api('/employees'+(q?`?q=${encodeURIComponent(q)}`:''))]).then(([c,b,e])=>{setCompanies(c);setBranches(b);setData(e)});useEffect(()=>{void load()},[]);async function save(e){e.preventDefault();const payload={...form,company_id:Number(form.company_id),branch_id:form.branch_id?Number(form.branch_id):null,start_date:form.start_date||null};await api('/employees',{method:'POST',body:JSON.stringify(payload)});setOpen(false);load()}async function upload(e){const f=e.target.files[0];if(!f)return;const cid=form.company_id||companies[0]?.id;if(!cid)return alert('Önce firma seçiniz.');const fd=new FormData();fd.append('file',f);const token=localStorage.getItem('isg_token');const base=import.meta.env.VITE_API_URL||'http://localhost:8000/api/v1';const r=await fetch(`${base}/employees/import-excel?company_id=${cid}`,{method:'POST',headers:{Authorization:`Bearer ${token}`},body:fd});const out=await r.json();alert(r.ok?`${out.created} personel aktarıldı.`:(out.detail||'Yükleme başarısız.'));load()}return <Page title="Personel Yönetimi" action={<div className="actions"><label className="button secondary"><Upload/>Excel Yükle<input type="file" accept=".xlsx" hidden onChange={upload}/></label><button onClick={()=>setOpen(true)}><Plus/>Personel Ekle</button></div>}><SearchBar q={q} setQ={setQ} go={load}/><Table cols={[{key:'full_name',label:'Ad Soyad'},{key:'job_title',label:'Görev'},{key:'department',label:'Departman'},{key:'branch_id',label:'Şube',render:r=>branches.find(b=>b.id===r.branch_id)?.name||'—'},{key:'start_date',label:'İşe Giriş'},{key:'is_active',label:'Durum',render:r=><Badge ok={r.is_active}/>}]} rows={data}/>{open&&<Modal title="Yeni Personel" close={()=>setOpen(false)}><form className="form-grid" onSubmit={save}><Select label="Firma" required value={form.company_id} onChange={e=>setForm({...form,company_id:e.target.value,branch_id:''})}><option value="">Seçiniz</option>{companies.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</Select><Select label="Şube" value={form.branch_id} onChange={e=>setForm({...form,branch_id:e.target.value})}><option value="">Şube seçilmedi</option>{branches.filter(b=>String(b.company_id)===String(form.company_id)).map(b=><option key={b.id} value={b.id}>{b.name}</option>)}</Select><Field label="Ad Soyad" required value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/><Field label="T.C. Kimlik (maskeli)" value={form.national_id_masked} onChange={e=>setForm({...form,national_id_masked:e.target.value})}/><Field label="Branş / Görev" value={form.job_title} onChange={e=>setForm({...form,job_title:e.target.value})}/><Field label="Departman" value={form.department} onChange={e=>setForm({...form,department:e.target.value})}/><Field label="İşe Giriş Tarihi" type="date" value={form.start_date} onChange={e=>setForm({...form,start_date:e.target.value})}/><Field label="Engelli / Hükümlü Durumu" value={form.special_status} onChange={e=>setForm({...form,special_status:e.target.value})}/><Submit/></form></Modal>}</Page>}

const moduleConfig={
  near_miss:{title:'Ramak Kala Kayıtları',severityLabel:'Olası Etki'},
  accident:{title:'İş Kazası Kayıtları',severityLabel:'Kaza Şiddeti'},
  capa:{title:'DÖF Yönetimi',severityLabel:'Öncelik'}
};
const statusNames={open:'Açık',in_progress:'Devam Ediyor',completed:'Tamamlandı',cancelled:'İptal'};

function IsgModulePage({user,module}){
  const cfg=moduleConfig[module];
  const[companies,setCompanies]=useState([]),[branches,setBranches]=useState([]),[data,setData]=useState([]),[open,setOpen]=useState(false),[q,setQ]=useState('');
  const empty={company_id:user.company_id||'',branch_id:'',module,title:'',description:'',status:'open',severity:'',event_date:'',due_date:'',responsible_name:'',probability:'',impact:'',participant_count:''};
  const[form,setForm]=useState(empty);
  const load=()=>Promise.all([api('/companies'),api('/branches'),api(`/isg-records?module=${module}${q?`&q=${encodeURIComponent(q)}`:''}`)]).then(([c,b,r])=>{setCompanies(c);setBranches(b);setData(r)});
  useEffect(()=>{setForm({...empty,module});load()},[module]);
  async function save(e){e.preventDefault();const payload={...form,company_id:Number(form.company_id),branch_id:form.branch_id?Number(form.branch_id):null,event_date:form.event_date||null,due_date:form.due_date||null,probability:form.probability?Number(form.probability):null,impact:form.impact?Number(form.impact):null,participant_count:form.participant_count?Number(form.participant_count):null};await api('/isg-records',{method:'POST',body:JSON.stringify(payload)});setOpen(false);setForm({...empty,module});load()}
  async function complete(id){await api(`/isg-records/${id}`,{method:'PATCH',body:JSON.stringify({status:'completed'})});load()}
  const cols=[{key:'title',label:'Başlık'},{key:'event_date',label:module==='training'?'Eğitim Tarihi':'Olay / Kayıt Tarihi'},{key:'severity',label:cfg.severityLabel},{key:'responsible_name',label:'Sorumlu'},{key:'status',label:'Durum',render:r=><span className={'badge '+(r.status==='completed'?'ok':'off')}>{statusNames[r.status]}</span>}];
  if(module==='risk')cols.splice(3,0,{key:'risk_score',label:'Risk Puanı'});
  cols.push({key:'action',label:'İşlem',render:r=>r.status!=='completed'?<button className="mini" onClick={()=>complete(r.id)}>Tamamla</button>:'—'});
  return <Page title={cfg.title} action={<button onClick={()=>setOpen(true)}><Plus/>Yeni Kayıt</button>}><SearchBar q={q} setQ={setQ} go={load}/><Table cols={cols} rows={data}/>{open&&<Modal title={'Yeni '+cfg.title+' Kaydı'} close={()=>setOpen(false)}><form className="form-grid" onSubmit={save}><Select label="Firma" required value={form.company_id} onChange={e=>setForm({...form,company_id:e.target.value,branch_id:''})}><option value="">Seçiniz</option>{companies.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</Select><Select label="Şube" value={form.branch_id} onChange={e=>setForm({...form,branch_id:e.target.value})}><option value="">Şube seçilmedi</option>{branches.filter(b=>String(b.company_id)===String(form.company_id)).map(b=><option key={b.id} value={b.id}>{b.name}</option>)}</Select><Field label="Başlık" required value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/><Field label="Açıklama" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/><Field label={module==='training'?'Eğitim Tarihi':'Olay / Kayıt Tarihi'} type="date" value={form.event_date} onChange={e=>setForm({...form,event_date:e.target.value})}/><Field label="Termin Tarihi" type="date" value={form.due_date} onChange={e=>setForm({...form,due_date:e.target.value})}/><Field label="Sorumlu Kişi" value={form.responsible_name} onChange={e=>setForm({...form,responsible_name:e.target.value})}/><Field label={cfg.severityLabel} value={form.severity} onChange={e=>setForm({...form,severity:e.target.value})}/>{module==='risk'&&<><Field label="Olasılık (1-5)" type="number" min="1" max="5" value={form.probability} onChange={e=>setForm({...form,probability:e.target.value})}/><Field label="Şiddet (1-5)" type="number" min="1" max="5" value={form.impact} onChange={e=>setForm({...form,impact:e.target.value})}/></>}{module==='training'&&<Field label="Katılımcı Sayısı" type="number" min="0" value={form.participant_count} onChange={e=>setForm({...form,participant_count:e.target.value})}/>}<Submit/></form></Modal>}</Page>
}


const documentNames={general:'Genel',risk:'Risk',training:'Eğitim',health:'Sağlık',emergency:'Acil Durum',legal:'Mevzuat',annual_plan:'Yıllık Plan'};

function DocumentsPage({user}){
  const[companies,setCompanies]=useState([]),[rows,setRows]=useState([]),[open,setOpen]=useState(false),[q,setQ]=useState(''),[busy,setBusy]=useState(false);
  const canEdit=['global_admin','company_admin','safety_specialist'].includes(user.role);
  const empty={company_id:user.company_id||'',branch_id:'',category:'general',title:'',file_name:'',description:'',valid_from:'',valid_until:'',version:'1.0'};
  const[form,setForm]=useState(empty);
  const load=()=>Promise.all([api('/companies'),api(`/documents${q?`?q=${encodeURIComponent(q)}`:''}`)]).then(([c,r])=>{setCompanies(c);setRows(r)});
  useEffect(()=>{load()},[]);
  async function save(e){e.preventDefault();const payload={...form,company_id:Number(form.company_id),branch_id:null,valid_from:form.valid_from||null,valid_until:form.valid_until||null};await api('/documents',{method:'POST',body:JSON.stringify(payload)});setOpen(false);setForm(empty);load()}
  async function deactivate(id){
    if(!window.confirm('Doküman pasife alınsın mı?\n\nBağlı dosya merkezi arşive kopyalanır; EİSA erişebilir.')) return;
    setBusy(true);
    try{
      await api(`/documents/${id}/deactivate`,{method:'PATCH'});
      await load();
    }catch(e){alert(e.message)}
    finally{setBusy(false)}
  }
  const cols=[
    {key:'title',label:'Doküman'},
    {key:'category',label:'Kategori',render:r=>documentNames[r.category]},
    {key:'file_name',label:'Dosya Adı'},
    {key:'version',label:'Versiyon'},
    {key:'valid_until',label:'Geçerlilik Sonu'},
    {key:'is_active',label:'Durum',render:r=>r.is_active===false?'Pasif':'Aktif'},
    ...(canEdit?[{key:'act',label:'',render:r=>r.is_active===false?null:<button type="button" className="mini secondary" disabled={busy} onClick={()=>deactivate(r.id)}>Pasife Al</button>}]:[]),
  ];
  return <Page title="Doküman Yönetimi" action={canEdit?<button onClick={()=>setOpen(true)}><Plus/>Yeni Doküman</button>:null}><SearchBar q={q} setQ={setQ} go={load}/><Table cols={cols} rows={rows}/>{open&&<Modal title="Yeni Doküman Kaydı" close={()=>setOpen(false)}><form className="form-grid" onSubmit={save}><Select label="Firma" required value={form.company_id} onChange={e=>setForm({...form,company_id:e.target.value})}><option value="">Seçiniz</option>{companies.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</Select><Select label="Kategori" value={form.category} onChange={e=>setForm({...form,category:e.target.value})}>{Object.entries(documentNames).map(([k,v])=><option key={k} value={k}>{v}</option>)}</Select><Field label="Doküman Başlığı" required value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/><Field label="Dosya Adı" value={form.file_name} onChange={e=>setForm({...form,file_name:e.target.value})}/><Field label="Açıklama" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/><Field label="Başlangıç Tarihi" type="date" value={form.valid_from} onChange={e=>setForm({...form,valid_from:e.target.value})}/><Field label="Geçerlilik Sonu" type="date" value={form.valid_until} onChange={e=>setForm({...form,valid_until:e.target.value})}/><Field label="Versiyon" value={form.version} onChange={e=>setForm({...form,version:e.target.value})}/><Submit/></form></Modal>}</Page>
}

function ReportsPage(){
  const[data,setData]=useState(null);
  useEffect(()=>{api('/reports/summary').then(setData)},[]);
  const items=[['Personel',data?.employee_count],['Açık Risk',data?.open_risks],['İş Kazası',data?.accident_count],['Sağlık Kaydı',data?.health_record_count],['Süresi Geçmiş Doküman',data?.expired_document_count],['Geciken Plan',data?.delayed_plan_count]];
  return <Page title="Yönetim Raporları"><div className="report-grid">{items.map(([t,v])=><Metric key={t} title={t} value={v??'—'}/>)}</div><section className="panel"><h3>Dışa Aktarım</h3><div className="export-actions"><button onClick={()=>downloadFile('/exports/employees.xlsx','personel-listesi.xlsx')}><Download/>Personel Excel</button><button onClick={()=>downloadFile('/exports/isg-summary.pdf','isg-ozet-raporu.pdf')}><Download/>İSG PDF</button></div></section></Page>
}


function SecurityPage({user}){
  const[form,setForm]=useState({current_password:'',new_password:''}),[message,setMessage]=useState(''),[logs,setLogs]=useState([]);
  const[archives,setArchives]=useState([]),[archMsg,setArchMsg]=useState(''),[archBusy,setArchBusy]=useState(false);
  const canView=['global_admin','company_admin'].includes(user.role);
  const canBackup=user.role==='company_admin';
  const loadArchives=()=>api('/archives').then(setArchives).catch(e=>setArchMsg(e.message));
  useEffect(()=>{if(canView)api('/security/audit-logs').then(setLogs)},[]);
  useEffect(()=>{if(canBackup)void loadArchives()},[]);
  async function save(e){e.preventDefault();setMessage('');try{const r=await api('/security/change-password',{method:'POST',body:JSON.stringify(form)});setMessage(r.message);setForm({current_password:'',new_password:''})}catch(err){setMessage(err.message)}}
  async function createBackup(){
    if(!window.confirm('Kurum verilerinizin tarihli yedeği alınsın mı?\n\nYedek merkezi arşive kaydedilir; EİSA de erişebilir.')) return;
    setArchBusy(true);setArchMsg('');
    try{
      await api('/archives/backup',{method:'POST',body:JSON.stringify({})});
      setArchMsg('Yedek oluşturuldu.');
      await loadArchives();
    }catch(e){setArchMsg(e.message)}
    finally{setArchBusy(false)}
  }
  async function downloadArchive(id,name){
    try{
      await downloadFile(`/archives/${id}/download`, name||`arsiv-${id}.zip`);
    }catch(e){setArchMsg(e.message)}
  }
  const cols=[{key:'created_at',label:'Tarih'},{key:'action',label:'İşlem'},{key:'entity_type',label:'Kayıt Türü'},{key:'description',label:'Açıklama'},{key:'ip_address',label:'IP'}];
  const archCols=[
    {key:'created_at',label:'Tarih',render:r=>new Date(r.created_at).toLocaleString('tr-TR')},
    {key:'kind',label:'Tür',render:r=>r.kind==='tenant_backup'?'Kurum yedeği':'Silinen dosya arşivi'},
    {key:'original_name',label:'Dosya'},
    {key:'size_bytes',label:'Boyut',render:r=>`${Math.max(1,Math.round((r.size_bytes||0)/1024))} KB`},
    {key:'notes',label:'Not'},
    {key:'dl',label:'',render:r=><button type="button" className="mini secondary" onClick={()=>downloadArchive(r.id,r.original_name)}>İndir</button>},
  ];
  return <Page title="Güvenlik ve Denetim"><div className="security-grid"><section className="panel"><h3>Şifre Değiştir</h3><form className="form-grid single" onSubmit={save}><Field label="Mevcut Şifre" type="password" required value={form.current_password} onChange={e=>setForm({...form,current_password:e.target.value})}/><Field label="Yeni Şifre" type="password" minLength="10" required value={form.new_password} onChange={e=>setForm({...form,new_password:e.target.value})}/><Submit/>{message&&<p>{message}</p>}</form></section><section className="panel"><h3>Güvenlik Notları</h3><ul><li>Yeni şifre en az 10 karakter olmalıdır.</li><li>Canlı ortamda MFA ve parola sıfırlama e-postası eklenmelidir.</li><li>Varsayılan demo şifresi mutlaka değiştirilmelidir.</li></ul></section></div>
  {canBackup&&<section className="panel" style={{marginTop:16}}><div className="page-title" style={{marginBottom:12}}><h3 style={{margin:0,fontSize:18}}>Kurum Yedekleme</h3><button type="button" disabled={archBusy} onClick={createBackup}>{archBusy?'Yedekleniyor…':'Yedek Oluştur'}</button></div><p style={{marginTop:0,color:'#64748b'}}>Yedekler tarihli olarak merkezi arşive kaydedilir. Siz indirirsiniz; EİSA de tüm kurum arşivlerine erişir. Silinen dosyalar da tarihli arşivde kalır.</p>{archMsg&&<p style={{color:archMsg.includes('oluştur')?'#166534':'#b91c1c'}}>{archMsg}</p>}<Table cols={archCols} rows={archives} empty="Henüz yedek yok."/></section>}
  {canView&&<section className="panel"><h3>Denetim Kayıtları</h3><Table cols={cols} rows={logs}/></section>}</Page>
}


const notificationTypeNames={info:'Bilgi',warning:'Uyarı',critical:'Kritik',success:'Başarılı'};
const planNames={demo:'Demo',starter:'Başlangıç',professional:'Profesyonel',enterprise:'Kurumsal'};
const subscriptionStatusNames={trial:'Deneme',active:'Aktif',past_due:'Salt Okunur',suspended:'Askıda',cancelled:'İptal'};

function NotificationsPage(){
  const[rows,setRows]=useState([]),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
  const load=()=>api('/notifications').then(setRows).catch(e=>setMessage(e.message));
  useEffect(()=>{load()},[]);
  async function refresh(){
    setBusy(true);setMessage('');
    try{
      const r=await api('/notifications/refresh',{method:'POST'});
      setMessage(`${r.count} bildirim oluşturuldu. ${r.message||''}`);
      await load();
    }catch(e){setMessage(e.message)}
    finally{setBusy(false)}
  }
  async function read(id){await api(`/notifications/${id}/read`,{method:'PATCH'});load()}
  const cols=[
    {key:'type',label:'Seviye',render:r=><span className={'notice '+r.type}>{notificationTypeNames[r.type]}</span>},
    {key:'title',label:'Başlık'},
    {key:'message',label:'Açıklama'},
    {key:'created_at',label:'Tarih',render:r=>String(r.created_at||'').slice(0,16).replace('T',' ')},
    {key:'action',label:'İşlem',render:r=>r.is_read?'Okundu':<button type="button" className="mini" onClick={()=>read(r.id)}>Okundu Yap</button>},
  ];
  return <Page title="Bildirim Merkezi" action={<button type="button" disabled={busy} onClick={refresh}><RefreshCw/>{busy?'Taranıyor...':'Süreleri Kontrol Et'}</button>}>
    <p style={{marginTop:0,color:'#64748b',fontSize:13,maxWidth:720}}>
      Bu merkez otomatik süre uyarısı üretir: görevlendirme / sözleşme bitişi, KATİP no eksikliği,
      atanmamış profesyonel, doküman geçerliliği, sağlık muayenesi ve geciken yıllık plan.
      Liste boşsa «Süreleri Kontrol Et» ile tarayın; gerçek kayıt yoksa bilgi bildirimi gelir.
    </p>
    {message&&<p style={{color:message.includes('oluşturuldu')?'#166534':'#b91c1c'}}>{message}</p>}
    <Table cols={cols} rows={rows} empty="Henüz bildirim yok. Süreleri Kontrol Et ile tarayın."/>
  </Page>;
}

function SubscriptionPage({user}){
  const[data,setData]=useState(null),[error,setError]=useState('');
  const isEisa=!!user?.is_eisa;
  useEffect(()=>{
    if(isEisa) return;
    api('/subscriptions/osgb/current').then(setData).catch(e=>setError(e.message));
  },[isEisa]);
  if(isEisa){
    return <Page title="Abonelik ve Paket"><p>OSGB abonelikleri <strong>EİSA Platform</strong> menüsünden yönetilir.</p></Page>;
  }
  if(error)return <Page title="Abonelik ve Paket"><p>{error}</p></Page>;
  if(!data)return <Page title="Abonelik ve Paket"><p>Abonelik bilgileri yükleniyor...</p></Page>;
  const end=data.effective_status==='trial'?data.trial_ends_at:data.current_period_ends_at;
  const planLabel=data.plan==='standard'?'Standart (Tüm Modüller)':(planNames[data.plan]||data.plan);
  return <Page title="Abonelik ve Paket">
    {!data.write_allowed&&<div className="error" style={{marginBottom:12}}>Salt okunur mod: abonelik süresi doldu. Veri girişi kapalı — EİSA ile iletişime geçin.</div>}
    <div className="subscription-card"><div><span>Mevcut Paket</span><h2>{planLabel}</h2><p className={'subscription-status '+data.effective_status}>{subscriptionStatusNames[data.effective_status]||data.effective_status}</p></div><CreditCard size={54}/></div>
    <div className="report-grid"><Metric title="Azami Kullanıcı" value={data.max_users}/><Metric title="Azami İşyeri" value={data.max_workplaces||data.max_employees}/><Metric title="Bitiş Tarihi" value={end?new Date(end).toLocaleDateString('tr-TR'):'—'}/></div>
    <section className="panel inner"><h3>Paket yönetimi</h3><p>Abonelik ve ödeme işlemleri EİSA platform yönetimi tarafından yürütülür.</p></section>
  </Page>
}

function SearchBar({q,setQ,go}){return <div className="search"><Search size={19}/><input placeholder="Ara..." value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&go()}/><button className="secondary" onClick={go}>Ara</button></div>}
function Badge({ok}){return <span className={'badge '+(ok?'ok':'off')}>{ok?'Aktif':'Pasif'}</span>};function Submit(){return <div className="form-actions"><button type="submit">Kaydet</button></div>};function Page({title,action,children}){return <><div className="page-title"><h3>{title}</h3>{action}</div><section className="panel">{children}</section></>}
function Dashboard({summary, user, onNavigate}){
  const field=['safety_specialist','workplace_physician','other_health_personnel'];
  if(field.includes(user?.role)){
    if(typeof DutyDashboard!=='function'){
      return <section className="panel"><h3>İSG Özeti</h3><p style={{color:'#b91c1c'}}>Saha paneli yüklenemedi. Sayfayı yenileyin (Ctrl+F5).</p></section>;
    }
    return <DutyDashboard user={user} summary={summary} onNavigate={onNavigate}/>;
  }
  return <AdminSummaryDashboard summary={summary}/>;
}
function Metric({title,value}){return <article className="metric"><span>{title}</span><strong>{value??'—'}</strong></article>}

class ErrorBoundary extends React.Component{
  constructor(props){super(props);this.state={err:null}}
  static getDerivedStateFromError(err){return{err}}
  componentDidCatch(err,info){console.error('UI ErrorBoundary',err,info)}
  render(){
    if(this.state.err){
      return (
        <section className="panel" style={{margin:16}}>
          <h3 style={{marginTop:0,color:'#991b1b'}}>Sayfa yüklenemedi</h3>
          <p style={{color:'#64748b'}}>{String(this.state.err?.message||this.state.err)}</p>
          <div className="actions">
            <button type="button" onClick={()=>{this.setState({err:null});this.props.onHome?.()}}>Ana panele dön</button>
            <button type="button" className="secondary" onClick={()=>window.location.reload()}>Sayfayı yenile</button>
          </div>
        </section>
      );
    }
    return this.props.children;
  }
}
function App(){
  const[logged,setLogged]=useState(!!localStorage.getItem('isg_token'));
  const[user,setUser]=useState(null);
  const[summary,setSummary]=useState(null);
  const[active,setActive]=useState(()=>{
    try{return sessionStorage.getItem('isg_active')||''}catch{return ''}
  });
  const navRef=useRef(null);
  const[applyMode,setApplyMode]=useState(false);
  const verifyCode=useMemo(()=>{
    try{return new URLSearchParams(window.location.search).get('egitim-dogrula')}
    catch{return null}
  },[]);

  function clearVerifyQuery(){
    try{
      const u=new URL(window.location.href);
      if(!u.searchParams.has('egitim-dogrula')) return;
      u.searchParams.delete('egitim-dogrula');
      const next=u.pathname+(u.search||'')+(u.hash||'');
      window.history.replaceState({},'',next||'/');
    }catch(_){ /* ignore */ }
  }

  function goModule(id){
    const allowed=roleModules[user?.role]||[];
    if(id && !allowed.includes(id)){
      // Yetkisiz / menüde olmayan modül — ana panele düş
      const home=allowed.includes('osgb_dashboard')
        ? 'osgb_dashboard'
        : (allowed.includes('dashboard') ? 'dashboard' : (allowed[0]||''));
      if(home){
        setActive(home);
        try{sessionStorage.setItem('isg_active',home)}catch(_){ /* ignore */ }
      }
      return;
    }
    setActive(id);
    try{sessionStorage.setItem('isg_active',id)}catch(_){ /* ignore */ }
  }

  function logout(){
    localStorage.removeItem('isg_token');
    try{sessionStorage.removeItem('isg_active')}catch(_){ /* ignore */ }
    setLogged(false);
    setUser(null);
    setActive('');
  }

  function goHome(){
    const allowed=roleModules[user?.role]||[];
    let home='';
    if(allowed.includes('eisa_overview')) home='eisa_overview';
    else if(allowed.includes('eisa')) home='eisa';
    else if(allowed.includes('osgb_dashboard')) home='osgb_dashboard';
    else if(allowed.includes('dashboard')) home='dashboard';
    else home=allowed[0]||'';
    if(home) goModule(home);
  }

  useEffect(()=>{
    if(!logged) return;
    // Oturum açıkken ?egitim-dogrula=... sol menüyü / uygulamayı ASLA bozmasın
    if(verifyCode) clearVerifyQuery();
    Promise.all([api('/auth/me'),api('/dashboard/summary')]).then(([u,s])=>{
      setUser(u);
      setSummary(s);
      const allowed=roleModules[u.role]||[];
      setActive((prev)=>{
        let next='';
        if(verifyCode && allowed.includes('training')) next='training';
        else if(prev && allowed.includes(prev)) next=prev;
        else {
          try{
            const saved=sessionStorage.getItem('isg_active');
            if(saved && allowed.includes(saved)) next=saved;
          }catch(_){ /* ignore */ }
        }
        if(!next) next=allowed[0]||'';
        try{if(next) sessionStorage.setItem('isg_active',next)}catch(_){ /* ignore */ }
        return next;
      });
    }).catch(()=>{
      localStorage.removeItem('isg_token');
      setLogged(false);
    });
  },[logged,verifyCode]);

  // Aktif menü (ör. Eğitimler) her zaman görünür olsun
  useEffect(()=>{
    if(!active || !navRef.current) return;
    const btn=navRef.current.querySelector(`button[data-nav="${active}"]`);
    if(btn) btn.scrollIntoView({block:'nearest',behavior:'smooth'});
  },[active,user]);

  // Kamuya açık doğrulama: yalnızca GİRİŞ YOKKEN (dış denetçi). Girişliyken shell korunur.
  if(verifyCode && !logged){
    return (
      <TrainingVerifyPage
        code={verifyCode}
        onClose={()=>{
          clearVerifyQuery();
          window.location.assign(window.location.pathname || '/');
        }}
      />
    );
  }
  if(applyMode) return <OsgbApplyPage onBack={()=>setApplyMode(false)}/>;
  if(!logged) return <Login done={()=>setLogged(true)} onApply={()=>setApplyMode(true)}/>;
  if(!user) return <div className="loading">Sistem yükleniyor...</div>;
  const allowed=roleModules[user.role]||[];
  const menu=allowed
    .filter((k)=>menuCatalog[k])
    .map((k)=>[k,menuCatalog[k][0],menuCatalog[k][1]]);
  const pages={
    eisa_overview:<EisaOverviewPage/>,
    eisa_osgb_users:<EisaOsgbUsersPage/>,
    eisa_subscriptions:<EisaSubscriptionsPage/>,
    eisa_subscriptions_expiring:<EisaExpiringSubscriptionsPage/>,
    eisa_subscriptions_expired:<EisaExpiredSubscriptionsPage/>,
    eisa_payments:<EisaPaymentsPage/>,
    eisa_packages:<EisaPackagesPage/>,
    eisa_notifications:<EisaNotificationsPage/>,
    eisa_reports:<EisaReportsPage/>,
    eisa_archives:<EisaArchivesPage/>,
    eisa_audit_logs:<EisaAuditLogsPage/>,
    eisa_system_settings:<EisaSystemSettingsPage/>,
    osgb_dashboard:<OsgbDashboard user={user}/>,
    osgb_oversight:<OsgbOversightPage user={user} onNavigate={goModule}/>,
    pro_performance:<ProPerformancePage user={user}/>,
    csgb_audit:<CsgbAuditPackPage user={user} onNavigate={goModule}/>,
    professionals:<ProfessionalsPage user={user} onNavigate={goModule}/>,
    assignments:<AssignmentsPage user={user}/>,
    visits:<VisitsPage user={user}/>,
    crm:<CrmPage user={user}/>,
    finance:<FinancePage user={user}/>,
    dashboard:<Dashboard summary={summary} user={user} onNavigate={goModule}/>,
    companies:<Companies canEdit={user.role==='global_admin'||user.role==='company_admin'} canAdd={user.role==='global_admin'||(user.role==='company_admin'&&!user.company_id)}/>,
    branches:<Branches user={user}/>,
    employees:<Employees user={user}/>,
    risk:<RiskPage user={user}/>,
    near_miss:<IncidentsPage user={user} menuKey="near_miss"/>,
    accident:<IncidentsPage user={user} menuKey="accident"/>,
    capa:<CapaPage user={user}/>,
    ppe:<PpePage user={user}/>,
    training:<TrainingPage user={user}/>,
    health:<HealthPage user={user}/>,
    documents:<DocumentsPage user={user}/>,
    annual_plans:<AnnualPlansPage user={user}/>,
    reports:<ReportsPage/>,
    notifications:<NotificationsPage/>,
    subscription:<SubscriptionPage user={user}/>,
    security:<SecurityPage user={user}/>,
    users:<UserPage user={user}/>,
  };
  return (
    <div className="app-shell">
      <aside>
        <button type="button" className="logo" onClick={goHome} title="Ana sayfa" aria-label="Ana sayfaya dön">
          <img
            src="/eisa-logo-icon.png"
            alt="EİSA PROGRAMLAMA"
            className="sidebar-logo eisa-logo-icon"
          />
          <span className="logo-caption">{user.role==='global_admin'?'EİSA Platform':'İSG Suite OSGB'}</span>
        </button>
        <nav ref={navRef}>
          {menu.map(([id,l,I])=>(
            <button
              key={id}
              type="button"
              data-nav={id}
              aria-current={active===id?'page':undefined}
              className={active===id?'active':''}
              onClick={()=>goModule(id)}
            >
              <I size={20}/><span>{l}</span>
            </button>
          ))}
        </nav>
        <button type="button" className="logout" onClick={logout}>
          <LogOut size={19}/><span>Çıkış</span>
        </button>
      </aside>
      <section className="workspace">
        <header>
          <div>
            <h2>{user.role==='global_admin'?'EİSA Platform':'İSG Suite OSGB'}</h2>
            <p>{user.role==='global_admin'?'OSGB abonelik ve platform yönetimi':'OSGB Operasyon ve İş Sağlığı Güvenliği Yönetimi'}</p>
          </div>
          <div className="header-actions">
            <button type="button" className="header-icon" onClick={goHome} title="Ana sayfa" aria-label="Ana sayfa">
              <LayoutDashboard size={18}/>
            </button>
          <div className="user-chip">
            <strong>{user.full_name}</strong>
            <span>{roles[user.role]}</span>
            </div>
            <button type="button" className="header-icon logout-mobile" onClick={logout} title="Çıkış" aria-label="Çıkış">
              <LogOut size={18}/>
            </button>
          </div>
        </header>
        <main className="content">
          {!user.is_eisa && user.subscription_write_allowed===false && (
            <div className="readonly-banner" role="status">
              Salt okunur mod: abonelik süresi doldu. Veri girişi kapalı — EİSA ile iletişime geçin.
            </div>
          )}
          <ErrorBoundary key={active||'none'} onHome={goHome}>
            {pages[active] || (
              <section className="panel">
                <h3 style={{marginTop:0}}>Modül bulunamadı</h3>
                <p style={{color:'#64748b'}}>Bu sayfa rolünüz için tanımlı değil veya geçersiz.</p>
                <button type="button" onClick={goHome}>Ana panele dön</button>
              </section>
            )}
          </ErrorBoundary>
        </main>
      </section>
    </div>
  );
}
createRoot(document.getElementById('root')).render(<App/>);


if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(console.error);
  });
}
