import React,{useEffect,useMemo,useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';

/** Apex â†’ www: Cloudflare 307, tarayÄ±cÄ± Authorization dÃ¼ÅŸÃ¼rÃ¼r â†’ Â«Oturum doÄŸrulanamadÄ±Â». */
(function ensureCanonicalWwwHost(){
  try{
    const host=String(window.location.hostname||'').toLowerCase();
    if(host==='isgsuite.tr' || host==='isgsuite.com.tr'){
      const next=new URL(window.location.href);
      next.hostname=`www.${host}`;
      window.location.replace(next.toString());
    }
  }catch{ /* ignore */ }
})();

import {AlertTriangle,BarChart3,Beaker,Bell,BookOpen,Building2,BriefcaseBusiness,CalendarDays,ClipboardCheck,Contrast,CreditCard,Download,Eye,FileText,Gauge,GitBranch,GraduationCap,HardHat,HeartPulse,Pill,KeyRound,LayoutDashboard,LogOut,Menu,Plus,QrCode,RefreshCw,Search,ShieldAlert,ShieldCheck,Sparkles,Stethoscope,Upload,UserCog,Users,WalletCards,X,Activity} from 'lucide-react';
import {api, apiWithBearer, downloadFile, reportClientError, setRefreshCookieMode, wakeApi} from './api';
import {clearOfflineQueue} from './field_offline';
import {LoginPasswordInput, PasswordField} from './password_field';
import {OsgbDashboard,ProfessionalsPage,AssignmentsPage,VisitsPage,CrmPage,ContractsPage,FinancePage} from './osgb';
import {EmployerOversightPage, EmployerOversightPanel} from './employer_oversight';
import {OsgbOversightPage} from './osgb_oversight';
import {LegalAcceptancesPanel} from './legal_acceptances';
import {MembershipsPanel} from './memberships_panel';
import {ProPerformancePage} from './pro_performance';
import {CsgbAuditPackPage} from './csgb_audit_pack';
import {MevzuatPanelPage} from './mevzuat_panel';
import {SdsRegisterPage} from './sds_register';
import {DrillsPage} from './drills';
import {EmergencyTeamsPage} from './emergency_teams';
import {
  PeriodicControlsPage,
  EmergencyPlansPage,
  WorkplaceMeasurementsPage,
  OhsCommitteePage,
  DocumentApprovalsPage,
  BelgeOnayHub,
} from './compliance_registers';
import {EyasDigitalApprovalPage} from './eyas_digital_approval';
import {AnnualEvalReportPage} from './annual_eval_report';
import {Customer360Page} from './customer_360';
import {CapacityEnginePage} from './capacity_engine';
import {TrainingPage, TrainingVerifyPage, loadSectorsCatalog} from './training';import {RiskPage} from './risk';import {IncidentsPage, CapaPage} from './incidents';import {PpePage} from './ppe';import {AnnualPlansPage} from './annual_plans';import {HealthPage} from './health';
import {PrescriptionPage} from './prescriptions';
import {TrainingQuestionBank} from './training_question_bank';
import {GLOBAL_ADMIN_MODULES} from './app_module_policy';
import {AdminSummaryDashboard,DutyDashboard} from './duty_dashboard';
import {AppModal} from './ui_modal';
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
  EisaErrorReportsPage,
  OsgbApplyPage,
} from './eisa';
import './styles.css';
import './theme-modern.css';
import {useUiTheme} from './theme';
const roles={global_admin:'EÄ°SA YÃ¶netici',company_admin:'OSGB YÃ¶neticisi',safety_specialist:'Ä°SG UzmanÄ±',workplace_physician:'Ä°ÅŸyeri Hekimi',other_health_personnel:'DiÄŸer SaÄŸlÄ±k Personeli',read_only:'Salt Okunur'};
/**
 * Sol menÃ¼ sÄ±rasÄ± (yukarÄ±â†’aÅŸaÄŸÄ±): ana panel â†’ gÃ¼nlÃ¼k operasyon â†’ master data â†’
 * Ä°SG saha iÅŸleri (risk/olay yoÄŸunluÄŸu) â†’ ticari â†’ rapor/denetim â†’ sistem ayarlarÄ±.
 * Her rol yalnÄ±zca kendi listesini gÃ¶rÃ¼r; sÄ±ra o rolÃ¼n kullanÄ±m yoÄŸunluÄŸuna gÃ¶redir.
 */
const roleModules={
  global_admin:GLOBAL_ADMIN_MODULES,
  // OSGB merkezi: yalnÄ±z OSGB yÃ¶netimi. Saha modÃ¼lleri ASLA burada olmamalÄ±.
  // SÄ±ra: gÃ¼nlÃ¼k operasyon â†’ insan/gÃ¶rev/performans â†’ denetim â†’ ticari â†’ ayarlar.
  company_admin:[
    // 1) Her gÃ¼n
    'osgb_dashboard',
    'visits',
    'notifications',
    'employer_oversight',
    'eyas_inbox',
    'companies',
    // 2) Ä°nsan, gÃ¶rev, performans (birbirini izler)
    'professionals',
    'assignments',
    'pro_performance',
    // 3) Denetim / kapasite / resmi paket
    'osgb_oversight',
    'capacity_engine',
    'csgb_audit',
    // 4) Ticari
    'crm',
    'contracts',
    'finance',
    // 5) Kurum & ayarlar (seyrek)
    'branches',
    'reports',
    'mevzuat',
    'users',
    'subscription',
    'security',
  ],
  safety_specialist:[
    'visits','belge_onay','dashboard',
    'risk','near_miss','accident','capa','ppe','sds','tatbikat','acil_ekipler','acil_plan',
    'periyodik_kontrol','ortam_olcum','isg_kurulu',
    'training','employees','annual_plans','annual_eval_report','documents',
    'security',
  ],
  workplace_physician:[
    'visits','belge_onay','eyas_inbox','dashboard',
    'health','prescriptions','employees','ortam_olcum',
    'annual_plans','annual_eval_report','documents',
    'security',
  ],
  other_health_personnel:[
    'visits','dashboard',
    'health','employees',
    'annual_plans','documents',
    'security',
  ],
  read_only:['dashboard','annual_eval_report','notifications','security'],
};

/** YalnÄ±z otomatik Ã¼retilen iÅŸyeri QR kiosk hesabÄ± â€” diÄŸer company_admin menÃ¼sÃ¼ bozulmaz. */
function isWorkplaceKioskUser(user){
  if(user?.role!=='company_admin' || !user.company_id) return false;
  const email=String(user.email||'').toLowerCase();
  return email.endsWith('@kiosk.isgsuite.tr');
}

/** OSGB / firma admin menÃ¼sÃ¼ aynÄ± kalÄ±r; kiosk hesabÄ± yalnÄ±z QR ekranÄ± gÃ¶rÃ¼r. */
function modulesForUser(user){
  if(isWorkplaceKioskUser(user)){
    return ['site_qr_kiosk'];
  }
  return roleModules[user?.role]||[];
}

/** Mobil alt bar: en sÄ±k 4 modÃ¼l + Â«MenÃ¼Â» (Ã§ok satÄ±rlÄ± Ä±zgara iÃ§eriÄŸi kapatmasÄ±n). */
const mobilePrimaryByRole={
  global_admin:['eisa_overview','eisa_osgb_users','eisa_subscriptions','eisa_payments'],
  company_admin:['osgb_dashboard','employer_oversight','visits','notifications'],
  safety_specialist:['visits','belge_onay','risk','training'],
  workplace_physician:['visits','health','prescriptions','employees'],
  other_health_personnel:['visits','health','employees','documents'],
  read_only:['dashboard','annual_eval_report','notifications','security'],
};

function mobilePrimaryMenu(menu, role, activeId){
  const preferred=(mobilePrimaryByRole[role]||[]).filter((id)=>menu.some((m)=>m[0]===id));
  const ids=[...preferred];
  if(activeId && !ids.includes(activeId) && menu.some((m)=>m[0]===activeId)){
    if(ids.length>=4) ids[ids.length-1]=activeId;
    else ids.push(activeId);
  }
  const set=new Set(ids.slice(0,4));
  return menu.filter((m)=>set.has(m[0]));
}

const menuCatalog={
  eisa_overview:['Genel BakÄ±ÅŸ',LayoutDashboard],
  eisa_osgb_users:['OSGB KullanÄ±cÄ±larÄ±',Users],
  eisa_subscriptions:['Abonelik YÃ¶netimi',CreditCard],
  eisa_subscriptions_expiring:['SÃ¼resi YaklaÅŸan Abonelikler',CalendarDays],
  eisa_subscriptions_expired:['SÃ¼resi Dolan Abonelikler',AlertTriangle],
  eisa_payments:['Finans ve Ã–demeler',WalletCards],
  eisa_packages:['Paket YÃ¶netimi',BriefcaseBusiness],
  eisa_question_bank:['NACE Soru BankasÄ±',BookOpen],
  eisa_error_reports:['Hata RaporlarÄ±',AlertTriangle],
  eisa_notifications:['Bilgilendirmeler',Bell],
  eisa_reports:['Raporlar',BarChart3],
  eisa_archives:['Merkezi ArÅŸiv',Download],
  eisa_audit_logs:['Ä°ÅŸlem KayÄ±tlarÄ±',FileText],
  eisa_system_settings:['Sistem AyarlarÄ±',KeyRound],
  osgb_dashboard:['OSGB Ana Panel',LayoutDashboard],
  osgb_oversight:['Hizmet Denetimi',ClipboardCheck],
  capacity_engine:['Kapasite Motoru',Gauge],
  pro_performance:['Performans Raporu',BarChart3],
  csgb_audit:['Ã‡SGB Belge Paketi',FileText],
  mevzuat:['Mevzuat Ã–zeti',BookOpen],
  professionals:['Ä°SG Profesyonelleri',Stethoscope],
  assignments:['GÃ¶revlendirmeler',BriefcaseBusiness],
  visits:['Saha Takvimi',CalendarDays],
  employer_oversight:['Ä°ÅŸyeri Denetim Durumu',ShieldCheck],
  site_qr_kiosk:['Ä°ÅŸyeri QR',QrCode],
  crm:['CRM / Teklif',BriefcaseBusiness],
  contracts:['SÃ¶zleÅŸmeler',FileText],
  finance:['Finans',WalletCards],
  dashboard:['Ä°SG Ã–zeti',BarChart3],
  companies:['Ä°ÅŸyerleri',Building2],
  branches:['Åžubeler',GitBranch],
  employees:['Personel',Users],
  risk:['Risk Analizi',ShieldAlert],
  near_miss:['Ramak Kala',AlertTriangle],
  accident:['Ä°ÅŸ KazalarÄ±',ShieldAlert],
  capa:['DÃ–F',ClipboardCheck],
  ppe:['KKD Takip',HardHat],
  sds:['SDS / PKD',Beaker],
  tatbikat:['Tatbikat YÃ¶netimi',Activity],
  acil_ekipler:['Acil Durum Ekipleri/Destek ElemanlarÄ±',Users],
  acil_plan:['Acil Durum PlanÄ± / Kroki',ShieldAlert],
  periyodik_kontrol:['Periyodik Kontrol',ClipboardCheck],
  ortam_olcum:['Ortam Ã–lÃ§Ã¼m',Gauge],
  isg_kurulu:['Ä°SG Kurulu',Users],
  belge_onay:['Belge Onay / Ä°mza',FileText],
  eyas_inbox:['Onay Kutum (Hekim/Ä°ÅŸveren)',FileText],
  training:['EÄŸitimler',GraduationCap],
  health:['SaÄŸlÄ±k',HeartPulse],
  prescriptions:['e-ReÃ§ete',Pill],
  documents:['DokÃ¼manlar',FileText],
  annual_plans:['YÄ±llÄ±k Plan',ClipboardCheck],
  annual_eval_report:['YÄ±llÄ±k Ã‡alÄ±ÅŸma DeÄŸerlendirme Raporu',FileText],
  reports:['OSGB YÃ¶netim Ã–zeti',BarChart3],
  notifications:['Bildirimler',Bell],
  subscription:['Abonelik',CreditCard],
  security:['GÃ¼venlik',KeyRound],
  users:['KullanÄ±cÄ±lar',UserCog],
};

function EisaQuestionBankPage({user}){
  const[sectors,setSectors]=useState([]);

  useEffect(()=>{
    let cancelled=false;
    loadSectorsCatalog().then((rows)=>{
      if(!cancelled && Array.isArray(rows)) setSectors(rows);
    }).catch(()=>{
      // Katalog alÄ±namazsa soru bankasÄ±nÄ±n listeleme ve yÃ¶netim iÅŸlevleri Ã§alÄ±ÅŸmayÄ± sÃ¼rdÃ¼rÃ¼r.
    });
    return()=>{cancelled=true};
  },[]);

  return <TrainingQuestionBank user={user} sectors={sectors}/>;
}

function Login({done,onApply}){
  const resetFromUrl=useMemo(()=>{
    try{return new URLSearchParams(window.location.search).get('sifre-sifirla')}catch{return null}
  },[]);
  const[mode,setMode]=useState(resetFromUrl?'reset':'login');
  const[email,setEmail]=useState('');
  const[password,setPassword]=useState('');
  const[code,setCode]=useState('');
  const[newPassword,setNewPassword]=useState('');
  const[resetToken,setResetToken]=useState(resetFromUrl||'');
  const[mfaToken,setMfaToken]=useState('');
  const[setupInfo,setSetupInfo]=useState(null);
  const[recoveryCodes,setRecoveryCodes]=useState(null);
  const[err,setErr]=useState('');
  const[msg,setMsg]=useState('');
  const[busy,setBusy]=useState(false);

  async function submitLogin(e){
    e.preventDefault();setErr('');setBusy(true);
    try{
      const r=await api('/auth/login',{method:'POST',body:JSON.stringify({email,password}),_retries:3});
      if(r.access_token){
        localStorage.setItem('isg_token',r.access_token);
        setRefreshCookieMode(!!r.refresh_cookie);
        done();
        return;
      }
      if(r.mfa_required&&r.mfa_token){setMfaToken(r.mfa_token);setMode('mfa');return}
      if(r.mfa_setup_required&&r.mfa_token){
        setMfaToken(r.mfa_token);
        localStorage.setItem('isg_mfa_setup_token',r.mfa_token);
        try{
          const setup=await apiWithBearer(r.mfa_token,'/security/mfa/setup',{method:'POST'});
          setSetupInfo(setup);setMode('mfa_setup');return
        }catch(setupErr){
          setErr(setupErr.message||'MFA kurulumu baÅŸlatÄ±lamadÄ±.');
          setMode('login');
          return
        }
      }
      setErr('GiriÅŸ yanÄ±tÄ± beklenmeyen biÃ§imde.');
    }catch(x){setErr(x.message)}
    finally{setBusy(false)}
  }

  async function submitMfa(e){
    e.preventDefault();setErr('');setBusy(true);
    try{
      const body=await apiWithBearer(mfaToken,'/auth/mfa/verify',{method:'POST',body:JSON.stringify({code}),_retries:3});
      localStorage.setItem('isg_token',body.access_token);
      setRefreshCookieMode(!!body.refresh_cookie);
      done();
    }catch(x){setErr(x.message)}
    finally{setBusy(false)}
  }

  async function restartMfaSetup(){
    setErr('');setMsg('');setBusy(true);
    try{
      if(!email||!password){
        setErr('Kurulum iÃ§in Ã¶nce giriÅŸ e-posta ve ÅŸifrenizi girin.');
        setMode('login');
        return;
      }
      const r=await api('/auth/mfa/restart-setup',{method:'POST',body:JSON.stringify({email,password}),_retries:2});
      if(!(r.mfa_setup_required&&r.mfa_token)){
        setErr('MFA kurulumu baÅŸlatÄ±lamadÄ±.');
        return;
      }
      setMfaToken(r.mfa_token);
      localStorage.setItem('isg_mfa_setup_token',r.mfa_token);
      const setup=await apiWithBearer(r.mfa_token,'/security/mfa/setup',{method:'POST'});
      setSetupInfo(setup);
      setCode('');
      setMode('mfa_setup');
    }catch(x){setErr(x.message||'MFA kurulumu baÅŸlatÄ±lamadÄ±.')}
    finally{setBusy(false)}
  }

  async function submitMfaSetup(e){
    e.preventDefault();setErr('');setBusy(true);
    try{
      const tok=mfaToken||localStorage.getItem('isg_mfa_setup_token');
      const body=await apiWithBearer(tok,'/security/mfa/enable',{method:'POST',body:JSON.stringify({code})});
      if(body.recovery_codes)setRecoveryCodes(body.recovery_codes);
      localStorage.setItem('isg_token',body.access_token);
      setRefreshCookieMode(!!body.refresh_cookie);
      localStorage.removeItem('isg_mfa_setup_token');
      if(body.recovery_codes?.length){setMode('recovery');return}
      done();
    }catch(x){setErr(x.message)}
    finally{setBusy(false)}
  }

  async function submitForgot(e){
    e.preventDefault();setErr('');setMsg('');setBusy(true);
    try{
      const r=await api('/auth/forgot-password',{method:'POST',body:JSON.stringify({email}),_retries:0});
      setMsg(r.message||'Ä°stek alÄ±ndÄ±.');
    }catch(x){setErr(x.message)}
    finally{setBusy(false)}
  }

  async function submitReset(e){
    e.preventDefault();setErr('');setMsg('');setBusy(true);
    try{
      const r=await api('/auth/reset-password',{method:'POST',body:JSON.stringify({token:resetToken,new_password:newPassword}),_retries:0});
      setMsg(r.message||'Åžifre gÃ¼ncellendi.');
      setMode('login');
      try{const u=new URL(window.location.href);u.searchParams.delete('sifre-sifirla');window.history.replaceState({},'',u.pathname)}catch{}
    }catch(x){setErr(x.message)}
    finally{setBusy(false)}
  }

  return (
    <main className={mode==='mfa_setup'||mode==='recovery'?'login-shell login-shell--form':'login-shell'}>
      <div className={mode==='mfa_setup'||mode==='recovery'?'login-wrap login-wrap--form':'login-wrap'}>
        <div className="login-brand"><img src="/eisa-logo-horizontal.png" alt="EÄ°SA PROGRAMLAMA" className="login-eisa-logo"/></div>
        <section className="login-card">
          <h1>Ä°SG Suite</h1>
          <p>Ä°ÅŸ SaÄŸlÄ±ÄŸÄ± ve GÃ¼venliÄŸi YÃ¶netim Sistemi</p>
          {mode==='login'&&(
            <form onSubmit={submitLogin}>
              <label>E-posta</label><input value={email} onChange={e=>setEmail(e.target.value)} type="email" required/>
              <LoginPasswordInput label="Åžifre" value={password} onChange={e=>setPassword(e.target.value)} required autoComplete="current-password"/>
              {err&&<div className="error">{err}</div>}
              <button disabled={busy}>GiriÅŸ Yap</button>
              <p style={{marginTop:12,fontSize:13}}><button type="button" className="linkish" onClick={()=>{setMode('forgot');setErr('');setMsg('')}}>Åžifremi unuttum</button></p>
            </form>
          )}
          {mode==='forgot'&&(
            <form onSubmit={submitForgot}>
              <p style={{color:'#64748b',fontSize:14}}>KayÄ±tlÄ± e-posta adresinize sÄ±fÄ±rlama baÄŸlantÄ±sÄ± gÃ¶nderilir.</p>
              <label>E-posta</label><input value={email} onChange={e=>setEmail(e.target.value)} type="email" required/>
              {err&&<div className="error">{err}</div>}
              {msg&&<p style={{color:'#166534'}}>{msg}</p>}
              <button disabled={busy}>GÃ¶nder</button>
              <p style={{marginTop:12,fontSize:13}}><button type="button" className="linkish" onClick={()=>setMode('login')}>GiriÅŸe dÃ¶n</button></p>
            </form>
          )}
          {mode==='reset'&&(
            <form onSubmit={submitReset}>
              <p style={{color:'#64748b',fontSize:14}}>Yeni ÅŸifrenizi belirleyin (en az 10 karakter).</p>
              <LoginPasswordInput label="Yeni ÅŸifre" value={newPassword} onChange={e=>setNewPassword(e.target.value)} minLength={10} required autoComplete="new-password"/>
              {err&&<div className="error">{err}</div>}
              {msg&&<p style={{color:'#166534'}}>{msg}</p>}
              <button disabled={busy}>Åžifreyi gÃ¼ncelle</button>
            </form>
          )}
          {mode==='mfa'&&(
            <form onSubmit={submitMfa}>
              <p style={{color:'#64748b',fontSize:14}}>Authenticator kodunu veya kurtarma kodunu girin.</p>
              <label>DoÄŸrulama kodu</label><input value={code} onChange={e=>setCode(e.target.value)} required/>
              {err&&<div className="error">{err}</div>}
              <button disabled={busy}>DoÄŸrula</button>
              <div style={{marginTop:14,padding:'12px 12px',borderRadius:10,background:'#f0fdfa',border:'1px solid #99f6e4'}}>
                <p style={{margin:'0 0 10px',fontSize:13,color:'#0f766e',fontWeight:600}}>
                  Telefonda Authenticator yok / QR gÃ¶rmediniz mi?
                </p>
                <button type="button" className="secondary" disabled={busy} onClick={restartMfaSetup} style={{width:'100%',justifyContent:'center'}}>
                  QR ve gizli anahtarÄ± gÃ¶ster (kurulumu baÅŸlat)
                </button>
              </div>
              <p style={{marginTop:10,fontSize:13}}><button type="button" className="linkish" onClick={()=>{setMode('login');setCode('');setErr('')}}>GiriÅŸe dÃ¶n</button></p>
            </form>
          )}
          {mode==='mfa_setup'&&(
            <form onSubmit={submitMfaSetup}>
              <p style={{color:'#64748b',fontSize:14,marginTop:0}}>
                YÃ¶netici hesaplarÄ± iÃ§in MFA zorunludur. QRâ€™Ä± veya gizli anahtarÄ± Authenticatorâ€™a ekleyin; sonra <strong>6 haneli kodu</strong> girin.
              </p>
              {setupInfo?(
                <>
                  <ol style={{fontSize:13,color:'#475569',paddingLeft:20,margin:'0 0 12px'}}>
                    <li>Google / Microsoft Authenticator uygulamasÄ±nÄ± aÃ§Ä±n</li>
                    <li><strong>+</strong> â†’ QR tara veya manuel kurulum anahtarÄ±</li>
                    <li>AÅŸaÄŸÄ±daki QR / gizli anahtarÄ± kullanÄ±n (doÄŸrulama alanÄ±na deÄŸil)</li>
                    <li>Uygulamada gÃ¶rÃ¼nen 6 haneli kodu aÅŸaÄŸÄ±ya yazÄ±n</li>
                  </ol>
                  {setupInfo.otpauth_uri&&(
                    <div style={{textAlign:'center',marginBottom:12}}>
                      <img
                        alt="MFA kurulum QR"
                        width={200}
                        height={200}
                        style={{borderRadius:12,background:'#fff',padding:8,border:'1px solid #e2e8f0'}}
                        src={
                          setupInfo.qr_data_url
                          || `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(setupInfo.otpauth_uri)}`
                        }
                      />
                      <p style={{margin:'8px 0 0',fontSize:12,color:'#64748b'}}>QR okutulamazsa gizli anahtarÄ± kullanÄ±n</p>
                    </div>
                  )}
                  <p style={{fontSize:13,wordBreak:'break-all',background:'#f8fafc',padding:10,borderRadius:8,border:'1px solid #e2e8f0'}}>
                    <strong>Gizli anahtar (Authenticatorâ€™a):</strong><br/>
                    <code style={{userSelect:'all',fontSize:14,letterSpacing:'.04em'}}>{setupInfo.secret}</code>
                  </p>
                  <button
                    type="button"
                    className="secondary"
                    style={{marginTop:8}}
                    onClick={async()=>{
                      try{
                        await navigator.clipboard.writeText(setupInfo.secret||'');
                        setMsg('Gizli anahtar kopyalandÄ±.');
                      }catch{setMsg('KopyalanamadÄ± â€” anahtarÄ± elle seÃ§in.')}
                    }}
                  >AnahtarÄ± kopyala</button>
                  {msg&&<p style={{color:'#166534',fontSize:13}}>{msg}</p>}
                </>
              ):(
                <p style={{color:'#b91c1c',fontSize:14}}>Kurulum anahtarÄ± yÃ¼klenemedi. GiriÅŸe dÃ¶nÃ¼p tekrar deneyin.</p>
              )}
              <label>6 haneli doÄŸrulama kodu</label>
              <input
                value={code}
                onChange={e=>setCode(e.target.value.replace(/\s/g,'').slice(0,8))}
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="000000"
                minLength={6}
                maxLength={8}
                pattern="[0-9A-Za-z-]{6,16}"
                required
              />
              <p style={{fontSize:12,color:'#64748b',margin:'6px 0 0'}}>Gizli anahtarÄ± buraya yapÄ±ÅŸtÄ±rmayÄ±n â€” yalnÄ±zca uygulamanÄ±n Ã¼rettiÄŸi kÄ±sa kod.</p>
              {err&&<div className="error">{err}</div>}
              <button disabled={busy||!setupInfo}>MFA etkinleÅŸtir</button>
            </form>
          )}
          {mode==='recovery'&&(
            <div>
              <p style={{color:'#166534'}}>MFA kuruldu. Kurtarma kodlarÄ±nÄ± gÃ¼venli yere kaydedin (bir kez gÃ¶sterilir):</p>
              <ul style={{fontFamily:'monospace',fontSize:13}}>{(recoveryCodes||[]).map(c=><li key={c}>{c}</li>)}</ul>
              <button type="button" onClick={()=>done()}>Devam et</button>
            </div>
          )}
          {mode==='login'&&(
            <p style={{marginTop:10,marginBottom:0,fontSize:12,color:'#64748b'}}>OSGB merkezi misiniz? <button type="button" className="linkish" onClick={onApply}>BaÅŸvuru formu</button></p>
          )}
        </section>
      </div>
    </main>
  );
}
function Modal({title,close,children}){return <AppModal title={title} close={close}>{children}</AppModal>}
function Field({label,...p}){return <label className="field"><span>{label}</span><input {...p}/></label>}
function Select({label,children,...p}){return <label className="field"><span>{label}</span><select {...p}>{children}</select></label>}
function Table({cols,rows,empty='KayÄ±t bulunamadÄ±.'}){return <div className="table-wrap"><table><thead><tr>{cols.map(c=><th key={c.key}>{c.label}</th>)}</tr></thead><tbody>{rows.length?rows.map((r,i)=><tr key={r.id??i}>{cols.map(c=><td key={c.key}>{c.render?c.render(r):String(r[c.key]??'â€”')}</td>)}</tr>):<tr><td colSpan={cols.length} className="empty">{empty}</td></tr>}</tbody></table></div>}

/** Ä°ÅŸyeri kiosk â€” QR + salt-okunur denetim durumu. MenÃ¼ yok; mÃ¼dahale yok. */
function SiteQrKioskPage({user,onLogout}){
  const companyId=user?.company_id;
  const[tab,setTab]=useState('qr');
  const[info,setInfo]=useState(null);
  const[err,setErr]=useState('');
  const[busy,setBusy]=useState(false);
  const[remainSec,setRemainSec]=useState(0);
  const timerRef=useRef(null);
  const refreshRef=useRef(null);

  const refreshQr=async()=>{
    if(!companyId) return;
    setBusy(true);setErr('');
    try{
      const row=await api(`/companies/${companyId}/site-qr/ephemeral`,{method:'POST'});
      setInfo(row);
      const exp=row.expires_at?new Date(row.expires_at).getTime():(Date.now()+((row.ttl_minutes||5)*60*1000));
      const tick=()=>{
        const left=Math.max(0,Math.floor((exp-Date.now())/1000));
        setRemainSec(left);
        if(left<=0){
          if(timerRef.current){clearInterval(timerRef.current);timerRef.current=null}
          refreshQr();
        }
      };
      tick();
      if(timerRef.current) clearInterval(timerRef.current);
      timerRef.current=setInterval(tick,1000);
      if(refreshRef.current) clearTimeout(refreshRef.current);
      const ms=Math.max(15_000,exp-Date.now()-5_000);
      refreshRef.current=setTimeout(()=>{refreshQr()},ms);
    }catch(ex){
      setErr(ex.message||'QR yÃ¼klenemedi.');
    }finally{setBusy(false)}
  };

  useEffect(()=>{
    if(tab!=='qr') return undefined;
    refreshQr();
    return ()=>{
      if(timerRef.current) clearInterval(timerRef.current);
      if(refreshRef.current) clearTimeout(refreshRef.current);
    };
  },[companyId,tab]);

  const mm=String(Math.floor(remainSec/60)).padStart(2,'0');
  const ss=String(remainSec%60).padStart(2,'0');
  const payload=info?.qr_payload||'';
  const title=info?.company_name||user?.full_name||'Ä°ÅŸyeri';

  return (
    <div style={{minHeight:'100vh',display:'flex',flexDirection:'column',alignItems:'center',padding:'20px 24px 32px',background:'linear-gradient(160deg,#0f766e 0%,#134e4a 45%,#0f172a 100%)',color:'#f8fafc'}}>
      <div style={{textAlign:'center',maxWidth:720,width:'100%'}}>
        <p style={{margin:0,opacity:.85,fontSize:14,letterSpacing:'.04em',textTransform:'uppercase'}}>Ä°ÅŸyeri paneli</p>
        <h1 style={{margin:'8px 0 4px',fontSize:28,fontWeight:700}}>{title}</h1>
        <p style={{margin:'0 0 16px',opacity:.9,fontSize:14}}>
          QR: uzman/hekim giriÅŸ-Ã§Ä±kÄ±ÅŸ Â· Denetim: onayda bekleyenleri onaylayÄ±n
        </p>
        <div style={{display:'flex',gap:8,justifyContent:'center',flexWrap:'wrap',marginBottom:18}}>
          <button type="button" onClick={()=>setTab('qr')} style={{
            background:tab==='qr'?'#fff':'rgba(255,255,255,.12)',
            color:tab==='qr'?'#0f172a':'#fff',
            border:'1px solid rgba(255,255,255,.35)',borderRadius:999,padding:'8px 16px',fontWeight:600,
          }}>QR kiosk</button>
          <button type="button" onClick={()=>setTab('status')} style={{
            background:tab==='status'?'#fff':'rgba(255,255,255,.12)',
            color:tab==='status'?'#0f172a':'#fff',
            border:'1px solid rgba(255,255,255,.35)',borderRadius:999,padding:'8px 16px',fontWeight:600,
          }}>Denetim durumu</button>
          <button type="button" className="mini" onClick={onLogout} style={{background:'rgba(255,255,255,.12)',color:'#fff',border:'1px solid rgba(255,255,255,.35)'}}>
            <LogOut size={14}/> Ã‡Ä±kÄ±ÅŸ
          </button>
        </div>

        {tab==='qr'&&(
          <>
            <div style={{background:'#fff',borderRadius:16,padding:20,display:'inline-block',boxShadow:'0 20px 50px rgba(0,0,0,.35)'}}>
              {payload?(
                <img
                  alt="Ä°ÅŸyeri QR"
                  width={320}
                  height={320}
                  style={{display:'block',width:Math.min(320,typeof window!=='undefined'?window.innerWidth-80:320),height:'auto'}}
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=320x320&data=${encodeURIComponent(payload)}`}
                />
              ):(
                <div style={{width:280,height:280,display:'grid',placeItems:'center',color:'#64748b'}}>{busy?'YÃ¼kleniyorâ€¦':'QR yok'}</div>
              )}
            </div>
            <p style={{margin:'18px 0 6px',fontSize:18,fontWeight:600}}>
              {remainSec>0?`Yenileniyorâ€¦ ${mm}:${ss}`:(busy?'Yenileniyorâ€¦':'â€”')}
            </p>
            {err&&<p style={{color:'#fecaca',marginTop:8}}>{err}</p>}
            <div style={{marginTop:16}}>
              <button type="button" className="mini secondary" disabled={busy} onClick={refreshQr} style={{background:'rgba(255,255,255,.12)',color:'#fff',border:'1px solid rgba(255,255,255,.35)'}}>
                <RefreshCw size={14}/> Åžimdi yenile
              </button>
            </div>
          </>
        )}

        {tab==='status'&&(
          <div style={{textAlign:'left',background:'rgba(15,23,42,.45)',borderRadius:16,padding:16,border:'1px solid rgba(255,255,255,.12)'}}>
            <EmployerOversightPanel companyId={companyId} user={user} compact dark />
          </div>
        )}
      </div>
    </div>
  );
}

function Companies({canEdit, canAdd, onOpen360}){
  const[data,setData]=useState([]);
  const[open,setOpen]=useState(false);
  const[q,setQ]=useState('');
  const[busy,setBusy]=useState(false);
  const[err,setErr]=useState('');
  const[creds,setCreds]=useState(null);
  const[copyMsg,setCopyMsg]=useState('');
  const[siteQr,setSiteQr]=useState(null);
  const[siteQrEphemeral,setSiteQrEphemeral]=useState(null);
  const[siteQrBusy,setSiteQrBusy]=useState(false);
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
    // Global yÃ¶netici aktif+pasif gÃ¶rsÃ¼n (backend: active=None)
    return api('/companies'+(p.toString()?`?${p}`:'')).then(setData).catch(e=>setErr(e.message));
  };
  useEffect(()=>{void load()},[]);
  async function save(e){
    e.preventDefault();setBusy(true);setErr('');
    const payload={...form,sgk_registry_no:(form.sgk_registry_no||'').trim()};
    if(!payload.sgk_registry_no){setErr('Ä°ÅŸyeri sicil numarasÄ± zorunludur.');setBusy(false);return}
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
      if(!window.confirm(`â€œ${row.name}â€ iÅŸyerini KALICI olarak silmek istiyor musunuz?\n\nPersonel, eÄŸitim, risk, saÄŸlÄ±k ve diÄŸer baÄŸlÄ± kayÄ±tlar da silinir. Bu iÅŸlem geri alÄ±namaz.`)) return;
    }else{
      const labels={deactivate:'pasife almak',activate:'yeniden aktifleÅŸtirmek'};
      if(!window.confirm(`â€œ${row.name}â€ iÅŸyerini ${labels[action]||action} istiyor musunuz?`)) return;
    }
    setBusy(true);setErr('');
    try{
      if(action==='delete'){
        await api(`/companies/${row.id}`,{method:'DELETE'});
      }else{
        await api(`/companies/${row.id}/${action}`,{method:'PATCH'});
      }
      await load();
    }catch(ex){setErr(ex.message||'Ä°ÅŸlem baÅŸarÄ±sÄ±z.')}
    finally{setBusy(false)}
  }
  async function openSiteQr(row){
    setSiteQrBusy(true);setErr('');setSiteQrEphemeral(null);setCopyMsg('');
    try{setSiteQr(await api(`/companies/${row.id}/site-qr`))}
    catch(ex){setErr(ex.message||'QR yÃ¼klenemedi.');setSiteQr(null)}
    finally{setSiteQrBusy(false)}
  }
  async function regenSiteQr(){
    if(!siteQr?.company_id) return;
    setSiteQrBusy(true);setErr('');
    try{setSiteQr(await api(`/companies/${siteQr.company_id}/site-qr/regenerate`,{method:'POST'}))}
    catch(ex){setErr(ex.message||'QR yenilenemedi.')}
    finally{setSiteQrBusy(false)}
  }
  async function createEphemeralSiteQr(){
    if(!siteQr?.company_id) return;
    setSiteQrBusy(true);setErr('');setCopyMsg('');
    try{setSiteQrEphemeral(await api(`/companies/${siteQr.company_id}/site-qr/ephemeral`,{method:'POST'}))}
    catch(ex){setErr(ex.message||'GeÃ§ici QR oluÅŸturulamadÄ±.');setSiteQrEphemeral(null)}
    finally{setSiteQrBusy(false)}
  }
  async function resetKioskLogin(row){
    if(!row?.id) return;
    if(!window.confirm(`â€œ${row.name}â€ kiosk ÅŸifresi sÄ±fÄ±rlansÄ±n mÄ±?\n\nEski ÅŸifre geÃ§ersiz olur. Yeni ÅŸifre bir kez gÃ¶sterilir â€” iÅŸyerine iletin.`)) return;
    setBusy(true);setErr('');setCopyMsg('');
    try{
      const acc=await api(`/companies/${row.id}/kiosk-login/reset`,{method:'POST'});
      setCreds(acc);
    }catch(ex){setErr(ex.message||'Kiosk ÅŸifresi sÄ±fÄ±rlanamadÄ±.')}
    finally{setBusy(false)}
  }
  return <Page title="Firma YÃ¶netimi" action={canAdd&&<button type="button" disabled={busy} onClick={()=>{setErr('');setOpen(true)}}><Plus/>Firma Ekle</button>}>
    {err&&<p style={{color:'#b91c1c'}}>{err}</p>}
    <SearchBar q={q} setQ={setQ} go={load}/>
    <Table cols={[
      {key:'name',label:'Firma'},
      {key:'sgk_registry_no',label:'Ä°ÅŸyeri Sicil No'},
      {key:'authorized_person',label:'Yetkili KiÅŸi'},
      {key:'phone',label:'Telefon'},
      {key:'address',label:'Adres'},
      {key:'hazard_class',label:'Tehlike SÄ±nÄ±fÄ±'},
      {key:'is_active',label:'Durum',render:r=><Badge ok={r.is_active}/>},
      ...(onOpen360?[{key:'c360',label:'360',render:r=>(
        <button type="button" className="mini" disabled={busy} onClick={()=>onOpen360(r.id)} title="MÃ¼ÅŸteri 360">
          <Eye size={14} style={{verticalAlign:'middle',marginRight:4}}/>360
        </button>
      )}]:[]),
      ...(canEdit?[{key:'qr',label:'Saha QR',render:r=>(
        <button type="button" className="mini secondary" disabled={busy||siteQrBusy} onClick={()=>openSiteQr(r)} title="Ä°ÅŸyeri QR kodu">
          <QrCode size={14} style={{verticalAlign:'middle',marginRight:4}}/>QR
        </button>
      )}]:[]),
      ...(canEdit?[{key:'actions',label:'Ä°ÅŸlem',render:r=>(
        <div className="actions" style={{gap:6,flexWrap:'wrap'}}>
          {r.is_active
            ? <button type="button" className="mini" disabled={busy} onClick={()=>act(r,'deactivate')}>Pasife Al</button>
            : <button type="button" className="mini" disabled={busy} onClick={()=>act(r,'activate')}>AktifleÅŸtir</button>}
          <button type="button" className="mini secondary" disabled={busy} onClick={()=>resetKioskLogin(r)} title="Kiosk giriÅŸ ÅŸifresini yenile">Kiosk ÅŸifresi</button>
          <button type="button" className="mini" disabled={busy} onClick={()=>act(r,'delete')}>Sil</button>
        </div>
      )}]:[]),
    ]} rows={data}/>
    {open&&<Modal title="Yeni Firma" close={()=>setOpen(false)}>
      <form className="form-grid" onSubmit={save}>
        <Field label="Firma AdÄ±" required value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/>
        <Field label="Ä°ÅŸyeri Sicil No" required value={form.sgk_registry_no} onChange={e=>setForm({...form,sgk_registry_no:e.target.value})}/>
        <Field label="Yetkili KiÅŸi" value={form.authorized_person} onChange={e=>setForm({...form,authorized_person:e.target.value})}/>
        <Field label="Telefon" value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/>
        <Field label="Adres" value={form.address} onChange={e=>setForm({...form,address:e.target.value})}/>
        <Select label="Tehlike SÄ±nÄ±fÄ±" value={form.hazard_class} onChange={e=>setForm({...form,hazard_class:e.target.value})}>
          <option>Az Tehlikeli</option><option>Tehlikeli</option><option>Ã‡ok Tehlikeli</option>
        </Select>
        {err&&<p style={{color:'#b91c1c',gridColumn:'1/-1'}}>{err}</p>}
        <div className="form-actions"><button type="submit" disabled={busy}>{busy?'Kaydediliyor...':'Kaydet'}</button></div>
      </form>
    </Modal>}
    {creds&&<Modal title="Ä°ÅŸyeri Kiosk GiriÅŸ Bilgileri" close={()=>{setCreds(null);setCopyMsg('')}}>
      <div className="form-grid single">
        <p style={{marginTop:0,color:'#64748b'}}>
          Bu e-posta ve ÅŸifre <strong>kalÄ±cÄ±dÄ±r</strong>. Ä°ÅŸyerine bir kez iletin; her giriÅŸte aynÄ± ÅŸifreyi kullanÄ±rlar.
          Åžifre yalnÄ±zca siz â€œKiosk ÅŸifresini sÄ±fÄ±rlaâ€ derseniz deÄŸiÅŸir.
        </p>
        <p style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap',marginBottom:0}}>
          <span><strong>KullanÄ±cÄ± adÄ± (e-posta):</strong> <code>{creds.email}</code></span>
          <button type="button" className="mini secondary" onClick={async()=>setCopyMsg((await copyText(creds.email))?'E-posta kopyalandÄ±.':'KopyalanamadÄ±.')}>E-postayÄ± kopyala</button>
        </p>
        <p><strong>Ad:</strong> {creds.full_name}</p>
        {(creds.password||creds.temporary_password)?(
          <p style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap',marginBottom:0}}>
            <span><strong>Åžifre:</strong> <code style={{userSelect:'all'}}>{creds.password||creds.temporary_password}</code></span>
            <button type="button" className="mini" onClick={async()=>setCopyMsg((await copyText(creds.password||creds.temporary_password))?'Åžifre kopyalandÄ±.':'KopyalanamadÄ±.')}>Åžifreyi kopyala</button>
          </p>
        ):(
          <p style={{color:'#b45309'}}>Åžifre bu ekranda bir kez gÃ¶sterilir. Unutulursa listeden â€œKiosk ÅŸifresini sÄ±fÄ±rlaâ€ kullanÄ±n.</p>
        )}
        <div className="actions" style={{gap:8,flexWrap:'wrap'}}>
          <button type="button" className="secondary" onClick={async()=>{
            const pw=creds.password||creds.temporary_password||'';
            const text=`KullanÄ±cÄ± adÄ±: ${creds.email}\nÅžifre: ${pw}`;
            setCopyMsg((await copyText(text))?'E-posta ve ÅŸifre kopyalandÄ±.':'KopyalanamadÄ±.');
          }}>E-posta + ÅŸifreyi kopyala</button>
        </div>
        {copyMsg&&<p style={{color:copyMsg.includes('amadÄ±')?'#b91c1c':'#166534',margin:0}}>{copyMsg}</p>}
        <p style={{color:'#166534'}}>{creds.message}</p>
        <div className="form-actions"><button type="button" onClick={()=>{setCreds(null);setCopyMsg('')}}>Tamam</button></div>
      </div>
    </Modal>}
    {siteQr&&<Modal title={`Saha QR â€” ${siteQr.company_name}`} close={()=>{setSiteQr(null);setSiteQrEphemeral(null);setCopyMsg('')}}>
      <div className="form-grid single">
        <p style={{marginTop:0,color:'#64748b'}}>KalÄ±cÄ± QR â€” iÅŸyerine asÄ±lÄ±r. Saha personeli ziyaret tamamlarken okutur.</p>
        <div style={{textAlign:'center'}}>
          <img alt="Ä°ÅŸyeri QR" width={220} height={220} src={`https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(siteQr.qr_payload)}`}/>
        </div>
        <p><strong>Kod:</strong> <code>{siteQr.site_verify_code}</code></p>
        <p style={{wordBreak:'break-all',fontSize:13,color:'#475569'}}><strong>Payload:</strong> {siteQr.qr_payload}</p>
        <div className="actions" style={{gap:8,flexWrap:'wrap'}}>
          <button type="button" className="mini secondary" disabled={siteQrBusy} onClick={async()=>setCopyMsg((await copyText(siteQr.qr_payload))?'Payload kopyalandÄ±.':'KopyalanamadÄ±.')}>Payload kopyala</button>
          <button type="button" className="mini" disabled={siteQrBusy} onClick={regenSiteQr}><RefreshCw size={14}/> KalÄ±cÄ± kodu yenile</button>
          <button type="button" className="mini secondary" disabled={siteQrBusy} onClick={createEphemeralSiteQr}><QrCode size={14}/> GeÃ§ici QR (30 dk)</button>
        </div>
        {siteQrEphemeral&&<>
          <hr style={{border:'none',borderTop:'1px solid #e2e8f0',margin:'8px 0'}}/>
          <p style={{marginTop:0,color:'#64748b'}}>GeÃ§ici QR â€” sÃ¼resi dolunca veya bir kez kullanÄ±lÄ±nca geÃ§ersiz olur. KalÄ±cÄ± QR deÄŸiÅŸmez.</p>
          <div style={{textAlign:'center'}}>
            <img alt="GeÃ§ici iÅŸyeri QR" width={220} height={220} src={`https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(siteQrEphemeral.qr_payload)}`}/>
          </div>
          <p><strong>BitiÅŸ:</strong> <code>{siteQrEphemeral.expires_at}</code> ({siteQrEphemeral.ttl_minutes} dk, tek kullanÄ±mlÄ±k)</p>
          <p style={{wordBreak:'break-all',fontSize:13,color:'#475569'}}><strong>Payload:</strong> {siteQrEphemeral.qr_payload}</p>
          <button type="button" className="mini secondary" disabled={siteQrBusy} onClick={async()=>setCopyMsg((await copyText(siteQrEphemeral.qr_payload))?'GeÃ§ici payload kopyalandÄ±.':'KopyalanamadÄ±.')}>GeÃ§ici payload kopyala</button>
        </>}
        {copyMsg&&<p style={{color:copyMsg.includes('amadÄ±')?'#b91c1c':'#166534',margin:0}}>{copyMsg}</p>}
        <div className="form-actions"><button type="button" onClick={()=>{setSiteQr(null);setSiteQrEphemeral(null);setCopyMsg('')}}>Kapat</button></div>
      </div>
    </Modal>}
  </Page>;
}
function Branches({user}){const[companies,setCompanies]=useState([]),[data,setData]=useState([]),[open,setOpen]=useState(false),[form,setForm]=useState({company_id:user.company_id||'',name:'',sgk_registry_no:'',city:'',address:''});const load=()=>Promise.all([api('/companies'),api('/branches')]).then(([c,b])=>{setCompanies(c);setData(b)});useEffect(()=>{void load()},[]);async function save(e){e.preventDefault();await api('/branches',{method:'POST',body:JSON.stringify({...form,company_id:Number(form.company_id)})});setOpen(false);load()}return <Page title="Åžube YÃ¶netimi" action={<button onClick={()=>setOpen(true)}><Plus/>Åžube Ekle</button>}><Table cols={[{key:'name',label:'Åžube'},{key:'company_id',label:'Firma',render:r=>companies.find(c=>c.id===r.company_id)?.name||r.company_id},{key:'city',label:'Åžehir'},{key:'sgk_registry_no',label:'SGK Sicil No'},{key:'is_active',label:'Durum',render:r=><Badge ok={r.is_active}/>}]} rows={data}/>{open&&<Modal title="Yeni Åžube" close={()=>setOpen(false)}><form className="form-grid" onSubmit={save}><Select label="Firma" required value={form.company_id} onChange={e=>setForm({...form,company_id:e.target.value})}><option value="">SeÃ§iniz</option>{companies.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</Select><Field label="Åžube AdÄ±" required value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/><Field label="Åžehir" value={form.city} onChange={e=>setForm({...form,city:e.target.value})}/><Field label="SGK Sicil No" value={form.sgk_registry_no} onChange={e=>setForm({...form,sgk_registry_no:e.target.value})}/><Field label="Adres" value={form.address} onChange={e=>setForm({...form,address:e.target.value})}/><Submit/></form></Modal>}</Page>}
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
    if(row.id===user.id) return alert('Kendi rolÃ¼nÃ¼zÃ¼ buradan deÄŸiÅŸtiremezsiniz.');
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
      alert(`Rol eÅŸlemesi: ${r.users_linked||0} kullanÄ±cÄ± gÃ¼ncellendi (${r.professionals||0} profesyonel).`);
      await load();
    }catch(ex){setErr(ex.message)}
    finally{setBusy(false)}
  }
  async function suspend(row){
    if(row.id===user.id) return alert('Kendi hesabÄ±nÄ±zÄ± askÄ±ya alamazsÄ±nÄ±z.');
    if(!window.confirm(`${row.full_name} askÄ±ya alÄ±nsÄ±n mÄ±? GiriÅŸ yapamaz.`)) return;
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
    if(row.id===user.id) return alert('Kendi hesabÄ±nÄ±zÄ± silemezsiniz.');
    if(!window.confirm(`${row.full_name} kalÄ±cÄ± olarak silinsin mi? Bu iÅŸlem geri alÄ±namaz.`)) return;
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
        title="Rol deÄŸiÅŸtir"
      >
        {Object.entries(roles).filter(([k])=>user.role==='global_admin'||k!=='global_admin').map(([k,v])=><option key={k} value={k}>{v}</option>)}
      </select>
    )},
    {key:'company_id',label:'Firma',render:r=>companies.find(c=>c.id===r.company_id)?.name||'Sistem Geneli'},
    {key:'is_active',label:'Durum',render:r=><Badge ok={r.is_active}/>},
    {key:'action',label:'Ä°ÅŸlem',render:r=>(
      <div className="actions" style={{gap:6,flexWrap:'wrap'}}>
        {r.is_active
          ? <button type="button" className="mini" disabled={r.id===user.id} onClick={()=>suspend(r)}>AskÄ±ya Al</button>
          : <button type="button" className="mini" onClick={()=>activate(r)}>AktifleÅŸtir</button>}
        <button type="button" className="mini" disabled={r.id===user.id} onClick={()=>remove(r)}>Sil</button>
      </div>
    )},
  ];
  return <Page title="KullanÄ±cÄ± ve Yetki YÃ¶netimi" action={<div className="actions"><button type="button" className="secondary" disabled={busy} onClick={syncRoles}>Hekim/Uzman Rollerini EÅŸle</button><button onClick={()=>{setErr('');setOpen(true)}}><Plus/>KullanÄ±cÄ± Ekle</button></div>}>
    <p style={{marginTop:0,color:'#475569',fontSize:14}}>Hekim / uzman / DSP iÃ§in kullanÄ±cÄ± rolÃ¼ <strong>Ä°ÅŸyeri Hekimi</strong> / <strong>Ä°SG UzmanÄ±</strong> / <strong>DSP</strong> olmalÄ±. GÃ¶revlendirme sonrasÄ± e-posta veya ad eÅŸleÅŸirse otomatik dÃ¼zelir; gerekirse aÅŸaÄŸÄ±daki eÅŸle butonunu kullanÄ±n.</p>
    {err&&<p style={{color:'#b91c1c'}}>{err}</p>}
    <Table cols={cols} rows={data}/>
    {open&&<Modal title="Yeni KullanÄ±cÄ±" close={()=>setOpen(false)}>
      <form className="form-grid" onSubmit={save}>
        <Field label="Ad Soyad" required value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/>
        <Field label="E-posta" type="email" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/>
        <PasswordField label="GeÃ§ici Åžifre" minLength="10" required value={form.password} onChange={e=>setForm({...form,password:e.target.value})} autoComplete="new-password"/>
        <Select label="Rol" value={form.role} onChange={e=>setForm({...form,role:e.target.value})}>
          {Object.entries(roles).filter(([k])=>user.role==='global_admin'||k!=='global_admin').map(([k,v])=><option key={k} value={k}>{v}</option>)}
        </Select>
        {form.role!=='global_admin'&&<Select label="Firma" value={form.company_id} onChange={e=>setForm({...form,company_id:e.target.value})} required={!['safety_specialist','workplace_physician','other_health_personnel'].includes(form.role)}>
          <option value="">SeÃ§iniz / OSGB saha (opsiyonel)</option>{companies.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>}
        {err&&<p style={{color:'#b91c1c',gridColumn:'1/-1'}}>{err}</p>}
        <div className="form-actions"><button disabled={busy}>{busy?'Kaydediliyor...':'Kaydet'}</button></div>
      </form>
    </Modal>}
  </Page>
}
function Employees({user}){
  const[companies,setCompanies]=useState([]);
  const[branches,setBranches]=useState([]);
  const[data,setData]=useState([]);
  const[selectedCompanyId,setSelectedCompanyId]=useState(user.company_id?String(user.company_id):'');
  const[selectedBranchId,setSelectedBranchId]=useState('');
  const[selectedIds,setSelectedIds]=useState([]);
  const[open,setOpen]=useState(false);
  const[q,setQ]=useState('');
  const[busy,setBusy]=useState(false);
  const[form,setForm]=useState({full_name:'',national_id_masked:'',job_title:'',department:'',start_date:'',special_status:''});

  const selectedCompany=companies.find(c=>String(c.id)===String(selectedCompanyId));
  const selectedBranches=branches.filter(b=>String(b.company_id)===String(selectedCompanyId));
  const visibleIds=data.map(r=>Number(r.id)).filter(Boolean);
  const allSelected=visibleIds.length>0&&visibleIds.every(id=>selectedIds.includes(id));

  async function loadCompanies(){
    const[c,b]=await Promise.all([api('/companies'),api('/branches')]);
    setCompanies(c||[]);
    setBranches(b||[]);
    if(user.company_id){
      setSelectedCompanyId(String(user.company_id));
    }
  }

  async function loadEmployees(companyId=selectedCompanyId,search=q){
    if(!companyId){setData([]);setSelectedIds([]);return}
    const params=new URLSearchParams({company_id:String(companyId)});
    if(search) params.set('q',search);
    const rows=await api(`/employees?${params.toString()}`);
    setData(rows||[]);
    setSelectedIds([]);
  }

  useEffect(()=>{void loadCompanies()},[]);
  useEffect(()=>{void loadEmployees(selectedCompanyId,'')},[selectedCompanyId]);

  function chooseCompany(value){
    setSelectedCompanyId(value);
    setSelectedBranchId('');
    setSelectedIds([]);
    setQ('');
    setData([]);
  }

  function requireCompany(){
    if(selectedCompanyId) return true;
    alert('Personel iÅŸlemi yapmadan Ã¶nce iÅŸyeri seÃ§melisiniz.');
    return false;
  }

  function toggleSelected(employeeId){
    const id=Number(employeeId);
    setSelectedIds(current=>current.includes(id)?current.filter(x=>x!==id):[...current,id]);
  }

  function toggleAll(){
    setSelectedIds(allSelected?[]:visibleIds);
  }

  function openCreate(){
    if(!requireCompany()) return;
    setForm({full_name:'',national_id_masked:'',job_title:'',department:'',start_date:'',special_status:''});
    setOpen(true);
  }

  async function save(e){
    e.preventDefault();
    if(!requireCompany()) return;
    setBusy(true);
    try{
      const payload={
        ...form,
        company_id:Number(selectedCompanyId),
        branch_id:selectedBranchId?Number(selectedBranchId):null,
        start_date:form.start_date||null,
      };
      await api('/employees',{method:'POST',body:JSON.stringify(payload)});
      setOpen(false);
      await loadEmployees();
    }catch(ex){alert(ex.message||'Personel kaydedilemedi.')}
    finally{setBusy(false)}
  }

  async function deleteOne(row){
    if(!requireCompany()) return;
    if(Number(row.company_id)!==Number(selectedCompanyId)){
      alert('Bu personel seÃ§ili iÅŸyerine ait deÄŸil. Ä°ÅŸlem durduruldu.');
      return;
    }
    if(!window.confirm(`â€œ${row.full_name}â€ adlÄ± personel silinsin mi?\n\nKayÄ±t gÃ¼venli ÅŸekilde pasife alÄ±nacak ve aktif listeden kaldÄ±rÄ±lacak.`)) return;
    setBusy(true);
    try{
      await api(`/employees/${row.id}`,{method:'DELETE'});
      await loadEmployees();
      alert('Personel silindi.');
    }catch(ex){alert(ex.message||'Personel silinemedi.')}
    finally{setBusy(false)}
  }

  async function deleteSelected(){
    if(!requireCompany()) return;
    if(!selectedIds.length){alert('Ã–nce silinecek personelleri seÃ§melisiniz.');return}
    const companyName=selectedCompany?.name||'seÃ§ili iÅŸyeri';
    if(!window.confirm(`${selectedIds.length} personel â€œ${companyName}â€ iÅŸyerinden silinsin mi?\n\nKayÄ±tlar gÃ¼venli ÅŸekilde pasife alÄ±nacak ve aktif listeden kaldÄ±rÄ±lacak.`)) return;
    setBusy(true);
    try{
      const result=await api('/employees/bulk-delete',{
        method:'POST',
        body:JSON.stringify({employee_ids:selectedIds,company_id:Number(selectedCompanyId)}),
      });
      await loadEmployees();
      alert(result?.message||`${selectedIds.length} personel silindi.`);
    }catch(ex){alert(ex.message||'SeÃ§ilen personeller silinemedi.')}
    finally{setBusy(false)}
  }

  async function upload(e){
    const f=e.target.files[0];
    e.target.value='';
    if(!f)return;
    if(!requireCompany())return;
    const companyName=selectedCompany?.name||'seÃ§ili iÅŸyeri';
    if(!window.confirm(`â€œ${companyName}â€ iÅŸyerine toplu personel yÃ¼klenecek.\n\nDosya: ${f.name}\n\nDevam edilsin mi?`)) return;
    setBusy(true);
    try{
      const fd=new FormData();
      fd.append('file',f);
      const token=localStorage.getItem('isg_token');
      const base=import.meta.env.VITE_API_URL||'http://localhost:8000/api/v1';
      const query=new URLSearchParams({company_id:String(selectedCompanyId)});
      if(selectedBranchId) query.set('branch_id',String(selectedBranchId));
      const r=await fetch(`${base}/employees/import-excel?${query.toString()}`,{method:'POST',headers:{Authorization:`Bearer ${token}`},body:fd});
      const out=await r.json().catch(()=>({}));
      if(!r.ok){
        alert(typeof out.detail==='string'?out.detail:(out.detail||'YÃ¼kleme baÅŸarÄ±sÄ±z. Åžablonu indirip tekrar deneyin.'));
        return;
      }
      const errN=(out.errors||[]).length;
      alert(`${out.created||0} personel â€œ${companyName}â€ iÅŸyerine aktarÄ±ldÄ±.${errN?` ${errN} satÄ±r atlandÄ±.`:''}`);
      await loadEmployees();
    }catch(x){alert(x.message||'YÃ¼kleme baÅŸarÄ±sÄ±z.')}
    finally{setBusy(false)}
  }

  function exportEmployees(){
    if(!requireCompany()) return;
    downloadFile(`/exports/employees.xlsx?company_id=${selectedCompanyId}`,
      `personel-listesi-${(selectedCompany?.name||'isyeri').replace(/[^a-zA-Z0-9Ã§ÄŸÄ±Ã¶ÅŸÃ¼Ã‡ÄžÄ°Ã–ÅžÃœ_-]+/g,'-')}.xlsx`);
  }

  return <Page title="Personel YÃ¶netimi" action={<div className="actions">
    <button type="button" className="secondary" disabled={busy||!selectedCompanyId} onClick={exportEmployees}><Download/>Excel Rapor</button>
    <button type="button" className="secondary" disabled={busy} onClick={()=>downloadFile('/employees/import-template.xlsx','personel-aktarim-sablonu.xlsx')}><Download/>Åžablon Ä°ndir</button>
    <label className="button secondary" style={{opacity:(busy||!selectedCompanyId)?0.55:1,pointerEvents:(busy||!selectedCompanyId)?'none':'auto'}}><Upload/>Excel YÃ¼kle<input type="file" accept=".xlsx" hidden disabled={busy||!selectedCompanyId} onChange={upload}/></label>
    <button type="button" className="secondary" disabled={busy||!selectedCompanyId||!selectedIds.length} onClick={deleteSelected}>SeÃ§ilenleri Sil ({selectedIds.length})</button>
    <button disabled={busy||!selectedCompanyId} onClick={openCreate}><Plus/>Personel Ekle</button>
  </div>}>
    <div className="form-grid" style={{gridTemplateColumns:'minmax(280px,1fr) minmax(220px,.7fr)',marginBottom:14}}>
      <Select label="Ä°ÅŸyeri SeÃ§ (zorunlu)" required value={selectedCompanyId} onChange={e=>chooseCompany(e.target.value)}>
        <option value="">Personel iÅŸlemi yapÄ±lacak iÅŸyerini seÃ§iniz</option>
        {companies.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
      </Select>
      <Select label="Åžube (isteÄŸe baÄŸlÄ±)" value={selectedBranchId} disabled={!selectedCompanyId} onChange={e=>setSelectedBranchId(e.target.value)}>
        <option value="">TÃ¼m iÅŸyeri / ÅŸube seÃ§ilmedi</option>
        {selectedBranches.map(b=><option key={b.id} value={b.id}>{b.name}</option>)}
      </Select>
    </div>

    {selectedCompanyId
      ? <div style={{padding:'12px 14px',marginBottom:12,borderRadius:12,background:'#ecfeff',border:'1px solid #99f6e4',color:'#115e59',fontWeight:700}}>
          SeÃ§ili Ä°ÅŸyeri: {selectedCompany?.name||'â€”'} â€” {data.length} personel gÃ¶rÃ¼ntÃ¼leniyor
          {selectedIds.length?` â€” ${selectedIds.length} personel seÃ§ildi`:''}
        </div>
      : <div style={{padding:'12px 14px',marginBottom:12,borderRadius:12,background:'#fff7ed',border:'1px solid #fed7aa',color:'#9a3412',fontWeight:700}}>
          Personel listesi, tekli ekleme ve toplu Excel yÃ¼kleme iÃ§in Ã¶nce iÅŸyeri seÃ§melisiniz.
        </div>}

    <p style={{margin:'0 0 12px',fontSize:13,color:'#475569'}}>
      Her Excel dosyasÄ± yalnÄ±zca yukarÄ±da seÃ§ilen iÅŸyerine aktarÄ±lÄ±r. Ä°ÅŸyerini deÄŸiÅŸtirdiÄŸinizde liste de otomatik olarak o iÅŸyerinin personeline geÃ§er.
      Åžablon sÃ¼tunlarÄ±: AdÄ± SoyadÄ±, TC Kimlik, GÃ¶revi, Ä°ÅŸe GiriÅŸ Tarihi, Engelli/HÃ¼kÃ¼mlÃ¼ Durumu.
    </p>
    <SearchBar q={q} setQ={setQ} go={()=>loadEmployees(selectedCompanyId,q)}/>
    <Table cols={[
      {key:'select',label:<input type="checkbox" checked={allSelected} onChange={toggleAll} aria-label="Listedeki tÃ¼m personelleri seÃ§"/>,render:r=><input type="checkbox" checked={selectedIds.includes(Number(r.id))} onChange={()=>toggleSelected(r.id)} aria-label={`${r.full_name} personelini seÃ§`}/>},
      {key:'full_name',label:'Ad Soyad'},
      {key:'job_title',label:'GÃ¶rev'},
      {key:'department',label:'Departman'},
      {key:'branch_id',label:'Åžube',render:r=>branches.find(b=>b.id===r.branch_id)?.name||'â€”'},
      {key:'start_date',label:'Ä°ÅŸe GiriÅŸ'},
      {key:'special_status',label:'Ã–zel Durum',render:r=>r.special_status||'â€”'},
      {key:'is_active',label:'Durum',render:r=><Badge ok={r.is_active}/>},
      {key:'actions',label:'Ä°ÅŸlem',render:r=><button type="button" className="mini secondary" disabled={busy} onClick={()=>deleteOne(r)}>Sil</button>}
    ]} rows={selectedCompanyId?data:[]}/>

    {open&&<Modal title={`Yeni Personel â€” ${selectedCompany?.name||''}`} close={()=>setOpen(false)}><form className="form-grid" onSubmit={save}>
      <div style={{gridColumn:'1/-1',padding:'10px 12px',borderRadius:10,background:'#f0fdfa',color:'#115e59'}}>
        Personel ÅŸu iÅŸyerine kaydedilecek: <strong>{selectedCompany?.name}</strong>
        {selectedBranchId&&<> / <strong>{selectedBranches.find(b=>String(b.id)===String(selectedBranchId))?.name}</strong></>}
      </div>
      <Field label="Ad Soyad" required value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/>
      <Field label="T.C. Kimlik (maskeli)" value={form.national_id_masked} onChange={e=>setForm({...form,national_id_masked:e.target.value})}/>
      <Field label="BranÅŸ / GÃ¶rev" value={form.job_title} onChange={e=>setForm({...form,job_title:e.target.value})}/>
      <Field label="Departman" value={form.department} onChange={e=>setForm({...form,department:e.target.value})}/>
      <Field label="Ä°ÅŸe GiriÅŸ Tarihi" type="date" value={form.start_date} onChange={e=>setForm({...form,start_date:e.target.value})}/>
      <Field label="Engelli / HÃ¼kÃ¼mlÃ¼ Durumu" value={form.special_status} onChange={e=>setForm({...form,special_status:e.target.value})}/>
      <Submit disabled={busy}/>
    </form></Modal>}
  </Page>;
}


const moduleConfig={
  near_miss:{title:'Ramak Kala KayÄ±tlarÄ±',severityLabel:'OlasÄ± Etki'},
  accident:{title:'Ä°ÅŸ KazasÄ± KayÄ±tlarÄ±',severityLabel:'Kaza Åžiddeti'},
  capa:{title:'DÃ–F YÃ¶netimi',severityLabel:'Ã–ncelik'}
};
const statusNames={open:'AÃ§Ä±k',in_progress:'Devam Ediyor',completed:'TamamlandÄ±',cancelled:'Ä°ptal'};

function IsgModulePage({user,module}){
  const cfg=moduleConfig[module];
  const[companies,setCompanies]=useState([]),[branches,setBranches]=useState([]),[data,setData]=useState([]),[open,setOpen]=useState(false),[q,setQ]=useState('');
  const empty={company_id:user.company_id||'',branch_id:'',module,title:'',description:'',status:'open',severity:'',event_date:'',due_date:'',responsible_name:'',probability:'',impact:'',participant_count:''};
  const[form,setForm]=useState(empty);
  const load=()=>Promise.all([api('/companies'),api('/branches'),api(`/isg-records?module=${module}${q?`&q=${encodeURIComponent(q)}`:''}`)]).then(([c,b,r])=>{setCompanies(c);setBranches(b);setData(r)});
  useEffect(()=>{setForm({...empty,module});load()},[module]);
  async function save(e){e.preventDefault();const payload={...form,company_id:Number(form.company_id),branch_id:form.branch_id?Number(form.branch_id):null,event_date:form.event_date||null,due_date:form.due_date||null,probability:form.probability?Number(form.probability):null,impact:form.impact?Number(form.impact):null,participant_count:form.participant_count?Number(form.participant_count):null};await api('/isg-records',{method:'POST',body:JSON.stringify(payload)});setOpen(false);setForm({...empty,module});load()}
  async function complete(id){await api(`/isg-records/${id}`,{method:'PATCH',body:JSON.stringify({status:'completed'})});load()}
  const cols=[{key:'title',label:'BaÅŸlÄ±k'},{key:'event_date',label:module==='training'?'EÄŸitim Tarihi':'Olay / KayÄ±t Tarihi'},{key:'severity',label:cfg.severityLabel},{key:'responsible_name',label:'Sorumlu'},{key:'status',label:'Durum',render:r=><span className={'badge '+(r.status==='completed'?'ok':'off')}>{statusNames[r.status]}</span>}];
  if(module==='risk')cols.splice(3,0,{key:'risk_score',label:'Risk PuanÄ±'});
  cols.push({key:'action',label:'Ä°ÅŸlem',render:r=>r.status!=='completed'?<button className="mini" onClick={()=>complete(r.id)}>Tamamla</button>:'â€”'});
  return <Page title={cfg.title} action={<button onClick={()=>setOpen(true)}><Plus/>Yeni KayÄ±t</button>}><SearchBar q={q} setQ={setQ} go={load}/><Table cols={cols} rows={data}/>{open&&<Modal title={'Yeni '+cfg.title+' KaydÄ±'} close={()=>setOpen(false)}><form className="form-grid" onSubmit={save}><Select label="Firma" required value={form.company_id} onChange={e=>setForm({...form,company_id:e.target.value,branch_id:''})}><option value="">SeÃ§iniz</option>{companies.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</Select><Select label="Åžube" value={form.branch_id} onChange={e=>setForm({...form,branch_id:e.target.value})}><option value="">Åžube seÃ§ilmedi</option>{branches.filter(b=>String(b.company_id)===String(form.company_id)).map(b=><option key={b.id} value={b.id}>{b.name}</option>)}</Select><Field label="BaÅŸlÄ±k" required value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/><Field label="AÃ§Ä±klama" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/><Field label={module==='training'?'EÄŸitim Tarihi':'Olay / KayÄ±t Tarihi'} type="date" value={form.event_date} onChange={e=>setForm({...form,event_date:e.target.value})}/><Field label="Termin Tarihi" type="date" value={form.due_date} onChange={e=>setForm({...form,due_date:e.target.value})}/><Field label="Sorumlu KiÅŸi" value={form.responsible_name} onChange={e=>setForm({...form,responsible_name:e.target.value})}/><Field label={cfg.severityLabel} value={form.severity} onChange={e=>setForm({...form,severity:e.target.value})}/>{module==='risk'&&<><Field label="OlasÄ±lÄ±k (1-5)" type="number" min="1" max="5" value={form.probability} onChange={e=>setForm({...form,probability:e.target.value})}/><Field label="Åžiddet (1-5)" type="number" min="1" max="5" value={form.impact} onChange={e=>setForm({...form,impact:e.target.value})}/></>}{module==='training'&&<Field label="KatÄ±lÄ±mcÄ± SayÄ±sÄ±" type="number" min="0" value={form.participant_count} onChange={e=>setForm({...form,participant_count:e.target.value})}/>}<Submit/></form></Modal>}</Page>
}


const documentNames={general:'Genel',risk:'Risk',training:'EÄŸitim',health:'SaÄŸlÄ±k',emergency:'Acil Durum',legal:'Mevzuat',annual_plan:'YÄ±llÄ±k Plan'};

function DocumentsPage({user}){
  const[companies,setCompanies]=useState([]),[rows,setRows]=useState([]),[open,setOpen]=useState(false),[q,setQ]=useState(''),[busy,setBusy]=useState(false);
  const canEdit=['global_admin','company_admin','safety_specialist'].includes(user.role);
  const empty={company_id:user.company_id||'',branch_id:'',category:'general',title:'',file_name:'',description:'',valid_from:'',valid_until:'',version:'1.0'};
  const[form,setForm]=useState(empty);
  const load=()=>Promise.all([api('/companies'),api(`/documents${q?`?q=${encodeURIComponent(q)}`:''}`)]).then(([c,r])=>{setCompanies(c);setRows(r)});
  useEffect(()=>{load()},[]);
  async function save(e){e.preventDefault();const payload={...form,company_id:Number(form.company_id),branch_id:null,valid_from:form.valid_from||null,valid_until:form.valid_until||null};await api('/documents',{method:'POST',body:JSON.stringify(payload)});setOpen(false);setForm(empty);load()}
  async function deactivate(id){
    if(!window.confirm('DokÃ¼man pasife alÄ±nsÄ±n mÄ±?\n\nBaÄŸlÄ± dosya merkezi arÅŸive kopyalanÄ±r; EÄ°SA eriÅŸebilir.')) return;
    setBusy(true);
    try{
      await api(`/documents/${id}/deactivate`,{method:'PATCH'});
      await load();
    }catch(e){alert(e.message)}
    finally{setBusy(false)}
  }
  const cols=[
    {key:'title',label:'DokÃ¼man'},
    {key:'category',label:'Kategori',render:r=>documentNames[r.category]},
    {key:'file_name',label:'Dosya AdÄ±'},
    {key:'version',label:'Versiyon'},
    {key:'valid_until',label:'GeÃ§erlilik Sonu'},
    {key:'is_active',label:'Durum',render:r=>r.is_active===false?'Pasif':'Aktif'},
    ...(canEdit?[{key:'act',label:'',render:r=>r.is_active===false?null:<button type="button" className="mini secondary" disabled={busy} onClick={()=>deactivate(r.id)}>Pasife Al</button>}]:[]),
  ];
  return <Page title="DokÃ¼man YÃ¶netimi" action={<div className="actions">
    <button type="button" className="secondary" onClick={()=>downloadFile(`/documents/export.xlsx${q?`?q=${encodeURIComponent(q)}`:''}`,`dokuman-kayitlari-${new Date().toISOString().slice(0,10)}.xlsx`)}><Download/>Excel Rapor</button>
    {canEdit?<button onClick={()=>setOpen(true)}><Plus/>Yeni DokÃ¼man</button>:null}
  </div>}><SearchBar q={q} setQ={setQ} go={load}/><Table cols={cols} rows={rows}/>{open&&<Modal title="Yeni DokÃ¼man KaydÄ±" close={()=>setOpen(false)}><form className="form-grid" onSubmit={save}><Select label="Firma" required value={form.company_id} onChange={e=>setForm({...form,company_id:e.target.value})}><option value="">SeÃ§iniz</option>{companies.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</Select><Select label="Kategori" value={form.category} onChange={e=>setForm({...form,category:e.target.value})}>{Object.entries(documentNames).map(([k,v])=><option key={k} value={k}>{v}</option>)}</Select><Field label="DokÃ¼man BaÅŸlÄ±ÄŸÄ±" required value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/><Field label="Dosya AdÄ±" value={form.file_name} onChange={e=>setForm({...form,file_name:e.target.value})}/><Field label="AÃ§Ä±klama" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/><Field label="BaÅŸlangÄ±Ã§ Tarihi" type="date" value={form.valid_from} onChange={e=>setForm({...form,valid_from:e.target.value})}/><Field label="GeÃ§erlilik Sonu" type="date" value={form.valid_until} onChange={e=>setForm({...form,valid_until:e.target.value})}/><Field label="Versiyon" value={form.version} onChange={e=>setForm({...form,version:e.target.value})}/><Submit/></form></Modal>}</Page>
}

function ReportsPage({user, onNavigate}){
  const[data,setData]=useState(null);
  const[finance,setFinance]=useState([]);
  const[err,setErr]=useState('');
  const isOsgb=['company_admin','global_admin'].includes(user?.role);
  useEffect(()=>{
    if(!isOsgb) return;
    (async()=>{
      setErr('');
      try{
        const orgs=await api('/osgb').catch(()=>[]);
        const oid=user?.osgb_id||orgs[0]?.id;
        if(!oid){setData(null);return}
        const[d,f]=await Promise.all([
          api(`/operations/dashboard?osgb_id=${oid}`),
          api(`/operations/finance?osgb_id=${oid}`).catch(()=>[]),
        ]);
        setData(d);
        setFinance(Array.isArray(f)?f:[]);
      }catch(e){setErr(e.message||'Ã–zet yÃ¼klenemedi.')}
    })();
  },[user?.id,user?.osgb_id,user?.role]);

  if(!isOsgb){
    return <Page title="Raporlar"><p>Bu ekran OSGB yÃ¶netimi iÃ§indir.</p></Page>;
  }

  const pendingAccrue=(finance||[])
    .filter(x=>x.category==='contract'&&x.status==='pending')
    .reduce((a,b)=>a+(Number(b.amount)||0),0);
  const moneyFmt=v=>new Intl.NumberFormat('tr-TR',{style:'currency',currency:'TRY',maximumFractionDigits:0}).format(v||0);
  const byType=data?.professionals_by_type||{};
  const go=(mod)=>{ if(typeof onNavigate==='function') onNavigate(mod); };
  const stamp=new Date().toISOString().slice(0,10);
  const oid=data?.osgb_id||user?.osgb_id;

  return <>
    <div className="page-title" style={{display:'flex',justifyContent:'space-between',gap:12,flexWrap:'wrap'}}>
      <div>
        <h3 style={{margin:0}}>OSGB YÃ¶netim Ã–zeti</h3>
        <p style={{margin:'4px 0 0',color:'#64748b',fontSize:13,maxWidth:720}}>
          Bu sayfa <strong>saha Ä°SG paneli deÄŸildir</strong> (personel / risk / kaza sayÄ±larÄ± burada amaÃ§lanmaz).
          OSGB merkezinin gÃ¼nlÃ¼k yÃ¶netimi iÃ§in Ã¶zet ve dÄ±ÅŸa aktarÄ±mlardÄ±r: iÅŸyerleri, profesyoneller, saha ziyaretleri, finans.
        </p>
      </div>
    </div>

    {err&&<p style={{color:'#b91c1c'}}>{err}</p>}

    <div className="cards osgb-cards" style={{marginBottom:14}}>
      <article className="metric" style={{cursor:'pointer'}} onClick={()=>go('companies')} title="Ä°ÅŸyerlerine git">
        <span>MÃ¼ÅŸteri iÅŸyeri</span><strong>{data?.workplaces??'â€”'}</strong>
      </article>
      <article className="metric" style={{cursor:'pointer'}} onClick={()=>go('professionals')} title="Profesyonellere git">
        <span>Ä°SG profesyoneli</span>
        <strong>
          {(byType.safety_specialist?.count||0)+(byType.workplace_physician?.count||0)+(byType.other_health_personnel?.count||0)||data?.professionals||'â€”'}
        </strong>
        <small style={{display:'block',marginTop:6,color:'#64748b',fontSize:11}}>
          Uzman {byType.safety_specialist?.count??0} Â· Hekim {byType.workplace_physician?.count??0} Â· DSP {byType.other_health_personnel?.count??0}
        </small>
      </article>
      <article className="metric" style={{cursor:'pointer'}} onClick={()=>go('visits')} title="Saha takvimine git">
        <span>Bu ay saha ziyareti</span><strong>{data?.visits_this_month??data?.visits??'â€”'}</strong>
      </article>
      <article className="metric" style={{cursor:'pointer'}} onClick={()=>go('assignments')} title="GÃ¶revlendirmelere git">
        <span>AtamasÄ± yapÄ±lmamÄ±ÅŸ</span>
        <strong style={{color:(data?.unassigned_professionals||0)>0?'#b91c1c':undefined}}>
          {data?.unassigned_professionals??0}
        </strong>
      </article>
      <article className="metric" style={{cursor:'pointer'}} onClick={()=>go('finance')} title="Finansa git">
        <span>Bekleyen tahakkuk</span><strong>{moneyFmt(pendingAccrue)}</strong>
      </article>
      <article className="metric" style={{cursor:'pointer'}} onClick={()=>go('pro_performance')} title="Performansa git">
        <span>Performans / iÅŸ tamamlama</span><strong style={{fontSize:16}}>AÃ§ â†’</strong>
      </article>
    </div>

    <section className="panel" style={{marginBottom:14,borderLeft:'4px solid #0f766e'}}>
      <h3 style={{marginTop:0,fontSize:15}}>Ne anlama geliyor?</h3>
      <ul style={{margin:0,paddingLeft:18,color:'#475569',fontSize:14,lineHeight:1.55}}>
        <li><strong>MÃ¼ÅŸteri iÅŸyeri:</strong> OSGBâ€™nizin hizmet verdiÄŸi firma / ÅŸube sayÄ±sÄ±.</li>
        <li><strong>Ä°SG profesyoneli:</strong> KayÄ±tlÄ± uzman, hekim ve DSP sayÄ±sÄ± (iÅŸyeri Ã§alÄ±ÅŸanÄ± / â€œpersonelâ€ deÄŸil).</li>
        <li><strong>Saha ziyareti:</strong> Bu ay QR / defter ile iÅŸlenen ziyaretler.</li>
        <li><strong>AtamasÄ± yapÄ±lmamÄ±ÅŸ:</strong> HenÃ¼z iÅŸyerine gÃ¶revlendirilmemiÅŸ profesyoneller.</li>
        <li><strong>Bekleyen tahakkuk:</strong> Ã–denmemiÅŸ sÃ¶zleÅŸme tahakkuk tutarÄ± (Finans).</li>
      </ul>
      <p style={{margin:'12px 0 0',fontSize:13,color:'#64748b'}}>
        Eski â€œPersonel / AÃ§Ä±k Risk / Ä°ÅŸ KazasÄ±â€ kartlarÄ± kaldÄ±rÄ±ldÄ± â€” bunlar saha rollerinin Ä°SG Ã¶zetine aittir; OSGB menÃ¼sÃ¼nde karÄ±ÅŸÄ±klÄ±k yaratÄ±yordu.
      </p>
    </section>

    <section className="panel">
      <h3 style={{marginTop:0}}>DÄ±ÅŸa aktarÄ±m & hÄ±zlÄ± geÃ§iÅŸ</h3>
      <div className="export-actions" style={{display:'flex',gap:8,flexWrap:'wrap'}}>
        <button type="button" disabled={!oid} onClick={()=>downloadFile(`/osgb/professionals/performance/export.csv?osgb_id=${oid}`,`csgb-pro-performans-${oid}-${stamp}.csv`).catch(e=>alert(e.message))}>
          <Download/> Profesyonel performans CSV
        </button>
        <button type="button" className="secondary" onClick={()=>go('csgb_audit')}>Ã‡SGB belge paketi</button>
        <button type="button" className="secondary" onClick={()=>go('osgb_oversight')}>Hizmet denetimi</button>
        <button type="button" className="secondary" onClick={()=>go('pro_performance')}>Performans raporu</button>
        <button type="button" className="secondary" onClick={()=>go('finance')}>Finans</button>
      </div>
    </section>
  </>;
}


function SecurityPage({user}){
  const[form,setForm]=useState({current_password:'',new_password:''}),[message,setMessage]=useState(''),[logs,setLogs]=useState([]);
  const[archives,setArchives]=useState([]),[archMsg,setArchMsg]=useState(''),[archBusy,setArchBusy]=useState(false);
  const[mfaStatus,setMfaStatus]=useState({mfa_enabled:false,mfa_required:false});
  const[mfaSetup,setMfaSetup]=useState(null);
  const[mfaCode,setMfaCode]=useState('');
  const[recoveryCodes,setRecoveryCodes]=useState(null);
  const[disableForm,setDisableForm]=useState({password:'',code:''});
  const canView=['global_admin','company_admin'].includes(user.role);
  const canBackup=user.role==='company_admin';
  const loadArchives=()=>api('/archives').then(setArchives).catch(e=>setArchMsg(e.message));
  const loadMfa=()=>api('/security/mfa/status').then(setMfaStatus).catch(()=>{});
  useEffect(()=>{if(canView)api('/security/audit-logs').then(setLogs)},[]);
  useEffect(()=>{if(canBackup)void loadArchives()},[]);
  useEffect(()=>{void loadMfa()},[]);
  async function save(e){e.preventDefault();setMessage('');try{const r=await api('/security/change-password',{method:'POST',body:JSON.stringify(form)});setMessage(r.message);setForm({current_password:'',new_password:''})}catch(err){setMessage(err.message)}}
  async function logoutAllDevices(){
    if(!window.confirm('TÃ¼m cihazlardaki oturumlar kapatÄ±lsÄ±n mÄ±?\n\nBu cihaz dahil yeniden giriÅŸ yapmanÄ±z gerekir.')) return;
    setMessage('');
    try{
      const r=await api('/auth/logout-all',{method:'POST'});
      setMessage(r.message||'TÃ¼m oturumlar kapatÄ±ldÄ±.');
      localStorage.removeItem('isg_token');
      localStorage.removeItem('isg_mfa_setup_token');
      clearOfflineQueue();
      setRefreshCookieMode(false);
      setTimeout(()=>window.location.reload(),800);
    }catch(err){setMessage(err.message)}
  }
  async function startMfa(){
    setMessage('');
    try{
      const s=await api('/security/mfa/setup',{method:'POST'});
      setMfaSetup(s);setRecoveryCodes(null);
    }catch(e){setMessage(e.message)}
  }
  async function enableMfa(e){
    e.preventDefault();setMessage('');
    try{
      const r=await api('/security/mfa/enable',{method:'POST',body:JSON.stringify({code:mfaCode})});
      setRecoveryCodes(r.recovery_codes||[]);
      setMfaSetup(null);setMfaCode('');
      await loadMfa();
      setMessage(r.message||'MFA etkinleÅŸtirildi.');
    }catch(err){setMessage(err.message)}
  }
  async function disableMfa(e){
    e.preventDefault();setMessage('');
    try{
      const r=await api('/security/mfa/disable',{method:'POST',body:JSON.stringify(disableForm)});
      setDisableForm({password:'',code:''});
      await loadMfa();
      setMessage(r.message||'MFA kapatÄ±ldÄ±.');
    }catch(err){setMessage(err.message)}
  }
  async function createBackup(){
    if(!window.confirm('Kurum verilerinizin tarihli yedeÄŸi alÄ±nsÄ±n mÄ±?\n\nYedek merkezi arÅŸive kaydedilir; EÄ°SA de eriÅŸebilir.')) return;
    setArchBusy(true);setArchMsg('');
    try{
      await api('/archives/backup',{method:'POST',body:JSON.stringify({})});
      setArchMsg('Yedek oluÅŸturuldu.');
      await loadArchives();
    }catch(e){setArchMsg(e.message)}
    finally{setArchBusy(false)}
  }
  async function downloadArchive(id,name){
    try{
      await downloadFile(`/archives/${id}/download`, name||`arsiv-${id}.zip`);
    }catch(e){setArchMsg(e.message)}
  }
  async function showRestorePlan(id){
    setArchBusy(true);setArchMsg('');
    try{
      const p=await api(`/archives/${id}/restore-plan`);
      const lines=[
        `Yedek: ${p.archive_name||id}`,
        `Tarih: ${p.created_at||'-'}`,
        `OSGB: ${p.osgb_name||p.osgb_id||'-'}`,
        `Ä°ÅŸyeri: ${(p.companies||[]).map(c=>c.name).join(', ')||'-'}`,
        `DokÃ¼man meta: ${p.document_count||0} | Personel meta: ${p.employee_count||0}`,
        `Dosya sayÄ±sÄ± (Ã¶rnek listelenen): ${(p.file_entries||[]).length}`,
        `GerÃ§ek restore aÃ§Ä±k mÄ±: ${p.restore_enabled?'EVET':'HAYIR (gÃ¼venlik â€” kapalÄ±)'}`,
        '',
        ...(p.notes||[]),
      ];
      window.alert(lines.join('\n'));
      setArchMsg('Restore planÄ± gÃ¶sterildi (yazma yok).');
    }catch(e){setArchMsg(e.message)}
    finally{setArchBusy(false)}
  }
  const cols=[{key:'created_at',label:'Tarih'},{key:'action',label:'Ä°ÅŸlem'},{key:'entity_type',label:'KayÄ±t TÃ¼rÃ¼'},{key:'description',label:'AÃ§Ä±klama'},{key:'ip_address',label:'IP'}];
  const archCols=[
    {key:'created_at',label:'Tarih',render:r=>new Date(r.created_at).toLocaleString('tr-TR')},
    {key:'kind',label:'TÃ¼r',render:r=>r.kind==='tenant_backup'?'Kurum yedeÄŸi':'Silinen dosya arÅŸivi'},
    {key:'original_name',label:'Dosya'},
    {key:'size_bytes',label:'Boyut',render:r=>`${Math.max(1,Math.round((r.size_bytes||0)/1024))} KB`},
    {key:'notes',label:'Not'},
    {key:'dl',label:'',render:r=>(
      <div className="actions" style={{gap:6,flexWrap:'wrap'}}>
        <button type="button" className="mini secondary" disabled={archBusy} onClick={()=>downloadArchive(r.id,r.original_name)}>Ä°ndir</button>
        {r.kind==='tenant_backup'&&<button type="button" className="mini" disabled={archBusy} onClick={()=>showRestorePlan(r.id)}>Ä°Ã§eriÄŸi gÃ¶r</button>}
      </div>
    )},
  ];
  return <Page title="GÃ¼venlik ve Denetim">
    <div className="security-grid">
      <section className="panel">
        <h3>Åžifre DeÄŸiÅŸtir</h3>
        <form className="form-grid single" onSubmit={save}>
          <PasswordField label="Mevcut Åžifre" required value={form.current_password} onChange={e=>setForm({...form,current_password:e.target.value})} autoComplete="current-password"/>
          <PasswordField label="Yeni Åžifre" minLength="10" required value={form.new_password} onChange={e=>setForm({...form,new_password:e.target.value})} autoComplete="new-password"/>
          <Submit/>{message&&<p>{message}</p>}
        </form>
        <p style={{marginTop:12,color:'#64748b',fontSize:13}}>YalnÄ±zca kendi ÅŸifrenizi deÄŸiÅŸtirebilirsiniz. HiÃ§bir yÃ¶netici (EÄ°SA dahil) baÅŸkasÄ±nÄ±n ÅŸifresine mÃ¼dahale edemez.</p>
        <div style={{marginTop:16,paddingTop:12,borderTop:'1px solid #e2e8f0'}}>
          <p style={{marginTop:0,color:'#64748b',fontSize:14}}>ÅžÃ¼pheli giriÅŸ veya kayÄ±p cihaz iÃ§in tÃ¼m oturumlarÄ± kapatÄ±n.</p>
          <button type="button" className="secondary" onClick={logoutAllDevices}>TÃ¼m cihazlardan Ã§Ä±kÄ±ÅŸ</button>
        </div>
      </section>
      <section className="panel">
        <h3>Ä°ki AdÄ±mlÄ± DoÄŸrulama (MFA)</h3>
        <p style={{color:'#64748b',marginTop:0}}>
          Durum: {mfaStatus.mfa_enabled?'AÃ§Ä±k':'KapalÄ±'}
          {mfaStatus.mfa_required?' Â· Bu rol iÃ§in zorunlu':''}
        </p>
        {!mfaStatus.mfa_enabled&&!mfaSetup&&(
          <button type="button" onClick={startMfa}>MFA kur</button>
        )}
        {mfaSetup&&(
          <form className="form-grid single" onSubmit={enableMfa}>
            <ol style={{fontSize:13,color:'#475569',paddingLeft:20,margin:'0 0 8px',gridColumn:'1 / -1'}}>
              <li>Telefonda Google / Microsoft Authenticatorâ€™Ä± aÃ§Ä±n</li>
              <li><strong>+</strong> â†’ QR kod tara</li>
              <li>AÅŸaÄŸÄ±daki QRâ€™Ä± okutun; uygulamadaki 6 haneli kodu girin</li>
            </ol>
            {(mfaSetup.qr_data_url||mfaSetup.otpauth_uri)&&(
              <div style={{textAlign:'center',marginBottom:8,gridColumn:'1 / -1'}}>
                <img
                  alt="MFA kurulum QR"
                  width={200}
                  height={200}
                  style={{borderRadius:12,background:'#fff',padding:8,border:'1px solid #e2e8f0'}}
                  src={
                    mfaSetup.qr_data_url
                    || `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(mfaSetup.otpauth_uri)}`
                  }
                />
                <p style={{margin:'8px 0 0',fontSize:12,color:'#64748b'}}>QR okutulamazsa gizli anahtarÄ± elle girin</p>
              </div>
            )}
            <p style={{fontSize:13,wordBreak:'break-all',background:'#f8fafc',padding:10,borderRadius:8,border:'1px solid #e2e8f0',gridColumn:'1 / -1'}}>
              <strong>Gizli anahtar:</strong> <code style={{userSelect:'all'}}>{mfaSetup.secret}</code>
            </p>
            <Field label="Authenticator kodu" value={mfaCode} onChange={e=>setMfaCode(e.target.value)} required/>
            <button type="submit">EtkinleÅŸtir</button>
          </form>
        )}
        {recoveryCodes&&(
          <div>
            <p>Kurtarma kodlarÄ± (bir kez gÃ¶sterilir):</p>
            <ul style={{fontFamily:'monospace',fontSize:13}}>{recoveryCodes.map(c=><li key={c}>{c}</li>)}</ul>
          </div>
        )}
        {mfaStatus.mfa_enabled&&(
          <form className="form-grid single" onSubmit={disableMfa} style={{marginTop:12}}>
            <PasswordField label="Åžifre" required value={disableForm.password} onChange={e=>setDisableForm({...disableForm,password:e.target.value})} autoComplete="current-password"/>
            <Field label="Authenticator kodu" value={disableForm.code} onChange={e=>setDisableForm({...disableForm,code:e.target.value})} required/>
            <button type="submit" className="secondary">MFA kapat</button>
          </form>
        )}
      </section>
      <section className="panel">
        <h3>GÃ¼venlik NotlarÄ±</h3>
        <ul>
          <li>Yeni ÅŸifre en az 10 karakter olmalÄ±dÄ±r.</li>
          <li>EÄ°SA / OSGB yÃ¶neticilerinde MFA zorunludur.</li>
          <li>Åžifre yalnÄ±zca hesap sahibi tarafÄ±ndan deÄŸiÅŸtirilir veya e-posta ile sÄ±fÄ±rlanÄ±r; yÃ¶neticiler baÅŸkasÄ±nÄ±n ÅŸifresini gÃ¶remez/deÄŸiÅŸtiremez.</li>
          <li>VarsayÄ±lan demo ÅŸifresi mutlaka deÄŸiÅŸtirilmelidir.</li>
        </ul>
      </section>
    </div>
    {canBackup&&<section className="panel" style={{marginTop:16}}><div className="page-title" style={{marginBottom:12}}><h3 style={{margin:0,fontSize:18}}>Kurum Yedekleme</h3><button type="button" disabled={archBusy} onClick={createBackup}>{archBusy?'Yedekleniyorâ€¦':'Yedek OluÅŸtur'}</button></div><p style={{marginTop:0,color:'#64748b'}}>Yedekler tarihli olarak merkezi arÅŸive kaydedilir. <strong>Ä°Ã§eriÄŸi gÃ¶r</strong> ile yedekte ne olduÄŸunu yazmadan incelersiniz. CanlÄ±ya otomatik geri yÃ¼kleme kapalÄ±dÄ±r.</p>{archMsg&&<p style={{color:archMsg.includes('oluÅŸtur')||archMsg.includes('gÃ¶sterildi')?'#166534':'#b91c1c'}}>{archMsg}</p>}<Table cols={archCols} rows={archives} empty="HenÃ¼z yedek yok."/></section>}
    <LegalAcceptancesPanel/>
    <MembershipsPanel user={user}/>
    {canView&&<section className="panel"><h3>Denetim KayÄ±tlarÄ±</h3><Table cols={cols} rows={logs}/></section>}
  </Page>
}


const notificationTypeNames={info:'Bilgi',warning:'UyarÄ±',critical:'Kritik',success:'BaÅŸarÄ±lÄ±'};
const planNames={demo:'Demo',starter:'BaÅŸlangÄ±Ã§',professional:'Profesyonel',enterprise:'Kurumsal'};
const subscriptionStatusNames={trial:'Deneme',active:'Aktif',past_due:'Salt Okunur',suspended:'AskÄ±da',cancelled:'Ä°ptal'};

function NotificationsPage(){
  const[rows,setRows]=useState([]),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
  const load=()=>api('/notifications').then(setRows).catch(e=>setMessage(e.message));
  useEffect(()=>{load()},[]);
  async function refresh(){
    setBusy(true);setMessage('');
    try{
      const r=await api('/notifications/refresh',{method:'POST'});
      setMessage(`${r.count} bildirim oluÅŸturuldu. ${r.message||''}`);
      await load();
    }catch(e){setMessage(e.message)}
    finally{setBusy(false)}
  }
  async function read(id){await api(`/notifications/${id}/read`,{method:'PATCH'});load()}
  const cols=[
    {key:'type',label:'Seviye',render:r=><span className={'notice '+r.type}>{notificationTypeNames[r.type]}</span>},
    {key:'title',label:'BaÅŸlÄ±k'},
    {key:'message',label:'AÃ§Ä±klama'},
    {key:'created_at',label:'Tarih',render:r=>String(r.created_at||'').slice(0,16).replace('T',' ')},
    {key:'action',label:'Ä°ÅŸlem',render:r=>r.is_read?'Okundu':<button type="button" className="mini" onClick={()=>read(r.id)}>Okundu Yap</button>},
  ];
  return <Page title="Bildirim Merkezi" action={<button type="button" disabled={busy} onClick={refresh}><RefreshCw/>{busy?'TaranÄ±yor...':'SÃ¼releri Kontrol Et'}</button>}>
    <p style={{marginTop:0,color:'#64748b',fontSize:13,maxWidth:720}}>
      Bu merkez otomatik sÃ¼re uyarÄ±sÄ± Ã¼retir: gÃ¶revlendirme / sÃ¶zleÅŸme bitiÅŸi, KATÄ°P no eksikliÄŸi,
      atanmamÄ±ÅŸ profesyonel, dokÃ¼man geÃ§erliliÄŸi, saÄŸlÄ±k muayenesi, geciken yÄ±llÄ±k plan ve SDS / PKD
      gÃ¶zden geÃ§irme terminleri. Liste boÅŸsa Â«SÃ¼releri Kontrol EtÂ» ile tarayÄ±n; gerÃ§ek kayÄ±t yoksa bilgi bildirimi gelir.
    </p>
    {message&&<p style={{color:message.includes('oluÅŸturuldu')?'#166534':'#b91c1c'}}>{message}</p>}
    <Table cols={cols} rows={rows} empty="HenÃ¼z bildirim yok. SÃ¼releri Kontrol Et ile tarayÄ±n."/>
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
    return <Page title="Abonelik ve Paket"><p>OSGB abonelikleri <strong>EÄ°SA Platform</strong> menÃ¼sÃ¼nden yÃ¶netilir.</p></Page>;
  }
  if(error)return <Page title="Abonelik ve Paket"><p>{error}</p></Page>;
  if(!data)return <Page title="Abonelik ve Paket"><p>Abonelik bilgileri yÃ¼kleniyor...</p></Page>;
  const end=data.effective_status==='trial'?data.trial_ends_at:data.current_period_ends_at;
  const planLabel=data.plan==='standard'?'Standart (TÃ¼m ModÃ¼ller)':(planNames[data.plan]||data.plan);
  return <Page title="Abonelik ve Paket">
    {!data.write_allowed&&<div className="error" style={{marginBottom:12}}>Salt okunur mod: abonelik sÃ¼resi doldu. Veri giriÅŸi kapalÄ± â€” EÄ°SA ile iletiÅŸime geÃ§in.</div>}
    <div className="subscription-card"><div><span>Mevcut Paket</span><h2>{planLabel}</h2><p className={'subscription-status '+data.effective_status}>{subscriptionStatusNames[data.effective_status]||data.effective_status}</p></div><CreditCard size={54}/></div>
    <div className="report-grid"><Metric title="Azami KullanÄ±cÄ±" value={data.max_users}/><Metric title="Azami Ä°ÅŸyeri" value={data.max_workplaces||data.max_employees}/><Metric title="BitiÅŸ Tarihi" value={end?new Date(end).toLocaleDateString('tr-TR'):'â€”'}/></div>
    <section className="panel inner"><h3>Paket yÃ¶netimi</h3><p>Abonelik ve Ã¶deme iÅŸlemleri EÄ°SA platform yÃ¶netimi tarafÄ±ndan yÃ¼rÃ¼tÃ¼lÃ¼r.</p></section>
  </Page>
}

function SearchBar({q,setQ,go}){return <div className="search"><Search size={19}/><input placeholder="Ara..." value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&go()}/><button className="secondary" onClick={go}>Ara</button></div>}
function Badge({ok}){return <span className={'badge '+(ok?'ok':'off')}>{ok?'Aktif':'Pasif'}</span>};function Submit(){return <div className="form-actions"><button type="submit">Kaydet</button></div>};function Page({title,action,children}){return <><div className="page-title"><h3>{title}</h3>{action}</div><section className="panel">{children}</section></>}
function Dashboard({summary, user, onNavigate}){
  const field=['safety_specialist','workplace_physician','other_health_personnel'];
  if(field.includes(user?.role)){
    if(typeof DutyDashboard!=='function'){
      return <section className="panel"><h3>Ä°SG Ã–zeti</h3><p style={{color:'#b91c1c'}}>Saha paneli yÃ¼klenemedi. SayfayÄ± yenileyin (Ctrl+F5).</p></section>;
    }
    return <DutyDashboard user={user} summary={summary} onNavigate={onNavigate}/>;
  }
  return <AdminSummaryDashboard summary={summary}/>;
}
function Metric({title,value}){return <article className="metric"><span>{title}</span><strong>{value??'â€”'}</strong></article>}

class ErrorBoundary extends React.Component{
  constructor(props){super(props);this.state={err:null}}
  static getDerivedStateFromError(err){return{err}}
  componentDidCatch(err,info){
    console.error('UI ErrorBoundary',err,info);
    reportClientError({
      source:'ui_crash',
      title:'Sayfa Ã§Ã¶kmesi',
      message:String(err?.message||err),
      stack_trace:[err?.stack,info?.componentStack].filter(Boolean).join('\n\n'),
      page_path:typeof window!=='undefined'?window.location.pathname:null,
    });
  }
  render(){
    if(this.state.err){
      return (
        <section className="panel" style={{margin:16}}>
          <h3 style={{marginTop:0,color:'#991b1b'}}>Sayfa yÃ¼klenemedi</h3>
          <p style={{color:'#64748b'}}>{String(this.state.err?.message||this.state.err)}</p>
          <p style={{color:'#64748b',fontSize:13}}>Hata EÄ°SA destek paneline iletildi.</p>
          <div className="actions">
            <button type="button" onClick={()=>{this.setState({err:null});this.props.onHome?.()}}>Ana panele dÃ¶n</button>
            <button type="button" className="secondary" onClick={()=>window.location.reload()}>SayfayÄ± yenile</button>
          </div>
        </section>
      );
    }
    return this.props.children;
  }
}

function ReportIssueButton(){
  const[open,setOpen]=useState(false);
  const[busy,setBusy]=useState(false);
  const[msg,setMsg]=useState('');
  const[form,setForm]=useState({title:'',user_note:''});
  async function submit(e){
    e.preventDefault();
    setBusy(true);setMsg('');
    try{
      await api('/eisa/error-reports',{
        method:'POST',
        body:JSON.stringify({
          source:'user_report',
          title:form.title.trim()||'KullanÄ±cÄ± sorun bildirimi',
          user_note:form.user_note.trim()||null,
          message:form.user_note.trim()||null,
          page_path:window.location.pathname,
        }),
      });
      setForm({title:'',user_note:''});
      setOpen(false);
      setMsg('Bildiriminiz alÄ±ndÄ±. TeÅŸekkÃ¼rler.');
      setTimeout(()=>setMsg(''),4000);
    }catch(err){
      setMsg(err.message||'GÃ¶nderilemedi');
    }finally{
      setBusy(false);
    }
  }
  return (
    <>
      <button type="button" className="header-icon" onClick={()=>setOpen(true)} title="Sorun bildir" aria-label="Sorun bildir">
        <AlertTriangle size={18}/>
      </button>
      {msg && !open ? <span style={{fontSize:12,color:'#0f766e',alignSelf:'center'}}>{msg}</span> : null}
      {open && (
        <AppModal title="Sorun bildir" close={() => setOpen(false)}>
            <form className="form-grid" onSubmit={submit}>
              <label className="field"><span>BaÅŸlÄ±k</span>
                <input required minLength={2} value={form.title} onChange={(ev)=>setForm({...form,title:ev.target.value})} placeholder="KÄ±sa Ã¶zet"/>
              </label>
              <label className="field"><span>AÃ§Ä±klama</span>
                <textarea required minLength={5} rows={4} value={form.user_note} onChange={(ev)=>setForm({...form,user_note:ev.target.value})} placeholder="Ne yaptÄ±nÄ±z, ne oldu?"/>
              </label>
              {msg ? <p style={{color:'#b91c1c',margin:0}}>{msg}</p> : null}
              <div className="form-actions">
                <button type="button" className="secondary" onClick={()=>setOpen(false)}>Ä°ptal</button>
                <button type="submit" disabled={busy}>GÃ¶nder</button>
              </div>
            </form>
        </AppModal>
      )}
    </>
  );
}
function ThemeToggle({theme,onToggle,floating}){
  const modern=theme==='modern';
  const label=modern?'Klasik arayÃ¼ze dÃ¶n':'Premium arayÃ¼ze geÃ§';
  return (
    <button
      type="button"
      className={floating?'theme-toggle theme-toggle-floating':'theme-toggle'}
      onClick={onToggle}
      title={label}
      aria-label={label}
    >
      {modern?<Contrast size={15}/>:<Sparkles size={15}/>}
      <span>{modern?'Klasik':'Premium'}</span>
    </button>
  );
}

/** MenÃ¼ geÃ§miÅŸi â€” tarayÄ±cÄ± Geri/Ä°leri uygulamada kalsÄ±n */
function readModuleFromLocation(){
  try{
    const h=String(window.location.hash||'').replace(/^#/, '');
    if(h.startsWith('m=')) return decodeURIComponent(h.slice(2).split('&')[0]||'');
    if(h.startsWith('/')) return decodeURIComponent(h.slice(1).split(/[?#]/)[0]||'');
    const q=new URLSearchParams(window.location.search).get('m');
    if(q) return q;
  }catch(_){ /* ignore */ }
  return '';
}
function writeModuleToLocation(id,{replace=false}={}){
  try{
    const u=new URL(window.location.href);
    u.searchParams.delete('m');
    u.hash=id?`m=${encodeURIComponent(id)}`:'';
    const url=u.pathname+(u.search||'')+(u.hash||'');
    if(replace) window.history.replaceState({module:id||''},'',url||'/');
    else window.history.pushState({module:id||''},'',url||'/');
  }catch(_){ /* ignore */ }
}

function App(){
  const[uiTheme,toggleUiTheme]=useUiTheme();
  const[logged,setLogged]=useState(!!localStorage.getItem('isg_token'));
  const[user,setUser]=useState(null);
  const[summary,setSummary]=useState(null);
  const[active,setActive]=useState(()=>{
    const fromUrl=readModuleFromLocation();
    if(fromUrl) return fromUrl;
    try{return sessionStorage.getItem('isg_active')||''}catch{return ''}
  });
  const[c360Id,setC360Id]=useState(null);
  const[mobileMoreOpen,setMobileMoreOpen]=useState(false);
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

  function goModule(id,{replace=false}={}){
    setMobileMoreOpen(false);
    if(id!=='customer_360') setC360Id(null);
    const allowed=modulesForUser(user);
    if(id && id!=='customer_360' && !allowed.includes(id)){
      // Yetkisiz / menÃ¼de olmayan modÃ¼l â€” ana panele dÃ¼ÅŸ
      const home=allowed.includes('osgb_dashboard')
        ? 'osgb_dashboard'
        : (allowed.includes('dashboard') ? 'dashboard' : (allowed[0]||''));
      if(home){
        setActive(home);
        try{sessionStorage.setItem('isg_active',home)}catch(_){ /* ignore */ }
        writeModuleToLocation(home,{replace:true});
      }
      return;
    }
    setActive(id);
    try{sessionStorage.setItem('isg_active',id)}catch(_){ /* ignore */ }
    writeModuleToLocation(id,{replace});
  }

  function openCustomer360(companyId){
    setC360Id(companyId);
    setActive('customer_360');
    try{sessionStorage.setItem('isg_active','customer_360')}catch(_){ /* ignore */ }
    writeModuleToLocation('customer_360');
  }

  function closeCustomer360(){
    setC360Id(null);
    setActive('companies');
    try{sessionStorage.setItem('isg_active','companies')}catch(_){ /* ignore */ }
    writeModuleToLocation('companies');
  }

  useEffect(()=>{
    function onAuthLost(){
      clearOfflineQueue();
      setLogged(false);
      setUser(null);
      setSummary(null);
      setActive('');
    }
    window.addEventListener('isg:auth-lost', onAuthLost);
    return ()=>window.removeEventListener('isg:auth-lost', onAuthLost);
  },[]);

  async function logout(){
    try{
      await api('/auth/logout',{method:'POST'});
    }catch(_){ /* aÄŸ hatasÄ± olsa da yerel oturumu kapat */ }
    localStorage.removeItem('isg_token');
    localStorage.removeItem('isg_mfa_setup_token');
    clearOfflineQueue();
    setRefreshCookieMode(false);
    try{sessionStorage.removeItem('isg_active')}catch(_){ /* ignore */ }
    setLogged(false);
    setUser(null);
    setActive('');
  }

  function goHome(){
    const allowed=modulesForUser(user);
    const fieldRoles=['safety_specialist','workplace_physician','other_health_personnel'];
    let home='';
    if(allowed.includes('eisa_overview')) home='eisa_overview';
    else if(allowed.includes('eisa')) home='eisa';
    else if(allowed.includes('osgb_dashboard')) home='osgb_dashboard';
    else if(fieldRoles.includes(user?.role) && allowed.includes('visits')) home='visits';
    else if(allowed.includes('dashboard')) home='dashboard';
    else home=allowed[0]||'';
    if(home) goModule(home);
  }

  useEffect(()=>{
    if(!logged) return;
    // Oturum aÃ§Ä±kken ?egitim-dogrula=... sol menÃ¼yÃ¼ / uygulamayÄ± ASLA bozmasÄ±n
    if(verifyCode) clearVerifyQuery();
    let cancelled=false;
    (async()=>{
      try{
        await wakeApi();
        if(cancelled) return;
        const[u,s]=await Promise.all([api('/auth/me'),api('/dashboard/summary')]);
        if(cancelled) return;
        setUser(u);
        setSummary(s);
        const allowed=modulesForUser(u);
        const fieldRoles=['safety_specialist','workplace_physician','other_health_personnel'];
        const fromUrl=readModuleFromLocation();
        let next='';
        if(verifyCode && allowed.includes('training')) next='training';
        else if(fromUrl && (fromUrl==='customer_360' || allowed.includes(fromUrl))) next=fromUrl;
        else if(active && (active==='customer_360' || allowed.includes(active))) next=active;
        else {
          try{
            const saved=sessionStorage.getItem('isg_active');
            if(saved && (saved==='customer_360' || allowed.includes(saved))) next=saved;
          }catch(_){ /* ignore */ }
        }
        if(!next){
          if(fieldRoles.includes(u.role) && allowed.includes('visits')) next='visits';
          else next=allowed[0]||'';
        }
        setActive(next);
        try{if(next) sessionStorage.setItem('isg_active',next)}catch(_){ /* ignore */ }
        if(next) writeModuleToLocation(next,{replace:true});
      }catch(_){
        if(cancelled) return;
        localStorage.removeItem('isg_token');
        clearOfflineQueue();
        setRefreshCookieMode(false);
        setLogged(false);
      }
    })();
    return ()=>{cancelled=true};
  },[logged,verifyCode]);

  // TarayÄ±cÄ± Geri/Ä°leri: uygulama iÃ§inde Ã¶nceki menÃ¼ye dÃ¶n
  useEffect(()=>{
    if(!user) return undefined;
    function onPop(){
      const id=readModuleFromLocation();
      const allowed=modulesForUser(user);
      if(id && (id==='customer_360' || allowed.includes(id))){
        setActive(id);
        if(id!=='customer_360') setC360Id(null);
        try{sessionStorage.setItem('isg_active',id)}catch(_){ /* ignore */ }
        return;
      }
      const fieldRoles=['safety_specialist','workplace_physician','other_health_personnel'];
      let home='';
      if(allowed.includes('eisa_overview')) home='eisa_overview';
      else if(allowed.includes('osgb_dashboard')) home='osgb_dashboard';
      else if(fieldRoles.includes(user.role) && allowed.includes('visits')) home='visits';
      else if(allowed.includes('dashboard')) home='dashboard';
      else home=allowed[0]||'';
      if(home){
        setActive(home);
        try{sessionStorage.setItem('isg_active',home)}catch(_){ /* ignore */ }
        writeModuleToLocation(home,{replace:true});
      }
    }
    window.addEventListener('popstate',onPop);
    return ()=>window.removeEventListener('popstate',onPop);
  },[user]);

  // Aktif menÃ¼ (Ã¶r. EÄŸitimler) her zaman gÃ¶rÃ¼nÃ¼r olsun
  useEffect(()=>{
    if(!active || !navRef.current) return;
    const btn=navRef.current.querySelector(`button[data-nav="${active}"]`);
    if(btn) btn.scrollIntoView({block:'nearest',behavior:'smooth'});
  },[active,user]);

  // Kamuya aÃ§Ä±k doÄŸrulama: yalnÄ±zca GÄ°RÄ°Åž YOKKEN (dÄ±ÅŸ denetÃ§i). GiriÅŸliyken shell korunur.
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
  if(!logged) return (
    <>
      <Login done={()=>setLogged(true)} onApply={()=>setApplyMode(true)}/>
      <ThemeToggle theme={uiTheme} onToggle={toggleUiTheme} floating/>
    </>
  );
  if(!user) return <div className="loading">Sistem yÃ¼kleniyor...</div>;
  const allowed=modulesForUser(user);
  const isWorkplaceKiosk=isWorkplaceKioskUser(user);
  if(isWorkplaceKiosk){
    return <SiteQrKioskPage user={user} onLogout={logout}/>;
  }
  const fieldRoles=['safety_specialist','workplace_physician','other_health_personnel'];
  const menu=allowed
    .filter((k)=>menuCatalog[k] && !(fieldRoles.includes(user.role) && (k==='reports' || k==='pro_performance')))
    .map((k)=>{
      const [label, Icon]=menuCatalog[k];
      if(k==='dashboard' && fieldRoles.includes(user.role)) return [k, 'Ana Sayfa', LayoutDashboard];
      return [k, label, Icon];
    });
  const pages={
    eisa_overview:<EisaOverviewPage/>,
    eisa_osgb_users:<EisaOsgbUsersPage/>,
    eisa_subscriptions:<EisaSubscriptionsPage/>,
    eisa_subscriptions_expiring:<EisaExpiringSubscriptionsPage/>,
    eisa_subscriptions_expired:<EisaExpiredSubscriptionsPage/>,
    eisa_payments:<EisaPaymentsPage/>,
    eisa_packages:<EisaPackagesPage/>,
    eisa_error_reports:<EisaErrorReportsPage/>,
    eisa_notifications:<EisaNotificationsPage/>,
    eisa_reports:<EisaReportsPage/>,
    eisa_archives:<EisaArchivesPage/>,
    eisa_audit_logs:<EisaAuditLogsPage/>,
    eisa_system_settings:<EisaSystemSettingsPage/>,
    eisa_question_bank:<EisaQuestionBankPage user={user}/>,
    osgb_dashboard:<OsgbDashboard user={user} onNavigate={goModule}/>,
    osgb_oversight:<OsgbOversightPage user={user} onNavigate={goModule}/>,
    capacity_engine:<CapacityEnginePage user={user} onNavigate={goModule}/>,
    pro_performance:<ProPerformancePage user={user} onNavigate={goModule}/>,
    csgb_audit:<CsgbAuditPackPage user={user} onNavigate={goModule}/>,
    mevzuat:<MevzuatPanelPage/>,
    professionals:<ProfessionalsPage user={user} onNavigate={goModule}/>,
    assignments:<AssignmentsPage user={user}/>,
    visits:<VisitsPage user={user} onNavigate={goModule}/>,
    employer_oversight:<EmployerOversightPage user={user}/>,
    site_qr_kiosk:<SiteQrKioskPage user={user} onLogout={logout}/>,
    crm:<CrmPage user={user} onNavigate={goModule}/>,
    contracts:<ContractsPage user={user}/>,
    finance:<FinancePage user={user}/>,
    dashboard:<Dashboard summary={summary} user={user} onNavigate={goModule}/>,
    companies:<Companies canEdit={user.role==='global_admin'||user.role==='company_admin'} canAdd={user.role==='global_admin'||(user.role==='company_admin'&&!user.company_id)} onOpen360={user.role==='company_admin'?openCustomer360:undefined}/>,
    branches:<Branches user={user}/>,
    employees:<Employees user={user}/>,
    risk:<RiskPage user={user}/>,
    near_miss:<IncidentsPage user={user} menuKey="near_miss"/>,
    accident:<IncidentsPage user={user} menuKey="accident"/>,
    capa:<CapaPage user={user}/>,
    ppe:<PpePage user={user}/>,
    sds:<SdsRegisterPage user={user}/>,
    tatbikat:<DrillsPage user={user}/>,
    acil_ekipler:<EmergencyTeamsPage user={user}/>,
    acil_plan:<EmergencyPlansPage user={user}/>,
    periyodik_kontrol:<PeriodicControlsPage user={user}/>,
    ortam_olcum:<WorkplaceMeasurementsPage user={user}/>,
    isg_kurulu:<OhsCommitteePage user={user}/>,
    belge_onay:<BelgeOnayHub user={user}/>,
    eyas_inbox:<EyasDigitalApprovalPage user={user} mode="inbox"/>,
    training:<TrainingPage user={user}/>,
    health:<HealthPage user={user}/>,
      prescriptions:<PrescriptionPage user={user}/>,
    documents:<DocumentsPage user={user}/>,
    annual_plans:<AnnualPlansPage user={user}/>,
    annual_eval_report:<AnnualEvalReportPage user={user} onNavigate={goModule}/>,
    reports:<ReportsPage user={user} onNavigate={goModule}/>,
    notifications:<NotificationsPage/>,
    subscription:<SubscriptionPage user={user}/>,
    security:<SecurityPage user={user}/>,
    users:<UserPage user={user}/>,
  };
  const mobilePrimary=mobilePrimaryMenu(menu, user.role, active);
  return (
    <div className={`app-shell${mobileMoreOpen?' mobile-nav-open':''}`}>
      <aside>
        <button type="button" className="logo" onClick={goHome} title="Ana sayfa" aria-label="Ana sayfaya dÃ¶n">
          <img
            src="/eisa-logo-icon.png"
            alt="EÄ°SA PROGRAMLAMA"
            className="sidebar-logo eisa-logo-icon"
          />
          <span className="logo-caption">{user.role==='global_admin'?'EÄ°SA Platform':'Ä°SG Suite OSGB'}</span>
        </button>
        <nav className="nav-desktop" ref={navRef}>
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
        <nav className="nav-mobile-primary" aria-label="Ana menÃ¼">
          {mobilePrimary.map(([id,l,I])=>(
            <button
              key={id}
              type="button"
              data-nav={id}
              aria-current={active===id?'page':undefined}
              className={active===id?'active':''}
              onClick={()=>goModule(id)}
              title={l}
            >
              <I size={22}/><span>{l}</span>
            </button>
          ))}
          <button
            type="button"
            className={mobileMoreOpen?'active':''}
            aria-expanded={mobileMoreOpen}
            aria-controls="mobile-nav-sheet"
            onClick={()=>setMobileMoreOpen((o)=>!o)}
            title="TÃ¼m menÃ¼"
          >
            {mobileMoreOpen?<X size={22}/>:<Menu size={22}/>}
            <span>{mobileMoreOpen?'Kapat':'MenÃ¼'}</span>
          </button>
        </nav>
        <button type="button" className="logout" onClick={logout}>
          <LogOut size={19}/><span>Ã‡Ä±kÄ±ÅŸ</span>
        </button>
      </aside>
      {mobileMoreOpen&&(
        <>
          <button type="button" className="mobile-nav-backdrop" aria-label="MenÃ¼yÃ¼ kapat" onClick={()=>setMobileMoreOpen(false)}/>
          <div className="mobile-nav-sheet" id="mobile-nav-sheet" role="dialog" aria-label="TÃ¼m modÃ¼ller">
            <div className="mobile-nav-sheet-head">
              <strong>ModÃ¼ller</strong>
              <button type="button" className="mini secondary" onClick={()=>setMobileMoreOpen(false)}>Kapat</button>
            </div>
            <div className="mobile-nav-sheet-grid">
              {menu.map(([id,l,I])=>(
                <button
                  key={id}
                  type="button"
                  className={active===id?'active':''}
                  onClick={()=>goModule(id)}
                >
                  <I size={22}/><span>{l}</span>
                </button>
              ))}
            </div>
          </div>
        </>
      )}
      <section className="workspace">
        <header>
          <div>
            <h2>{user.role==='global_admin'?'EÄ°SA Platform':'Ä°SG Suite OSGB'}</h2>
            <p>{user.role==='global_admin'?'OSGB abonelik ve platform yÃ¶netimi':'OSGB Operasyon ve Ä°ÅŸ SaÄŸlÄ±ÄŸÄ± GÃ¼venliÄŸi YÃ¶netimi'}</p>
          </div>
          <div className="header-actions">
            <ThemeToggle theme={uiTheme} onToggle={toggleUiTheme}/>
            <ReportIssueButton/>
            <button type="button" className="header-icon" onClick={goHome} title="Ana sayfa" aria-label="Ana sayfa">
              <LayoutDashboard size={18}/>
            </button>
            {allowed.includes('security')&&(
              <button type="button" className="header-icon" onClick={()=>goModule('security')} title="Åžifre deÄŸiÅŸtir / GÃ¼venlik" aria-label="Åžifre deÄŸiÅŸtir">
                <KeyRound size={18}/>
              </button>
            )}
          <div className="user-chip">
            <strong>{user.full_name}</strong>
            <span>{roles[user.role]}</span>
            </div>
            <button type="button" className="header-icon logout-mobile" onClick={logout} title="Ã‡Ä±kÄ±ÅŸ" aria-label="Ã‡Ä±kÄ±ÅŸ">
              <LogOut size={18}/>
            </button>
          </div>
        </header>
        <main className="content">
          {!user.is_eisa && user.subscription_write_allowed===false && (
            <div className="readonly-banner" role="status">
              Salt okunur mod: abonelik sÃ¼resi doldu. Veri giriÅŸi kapalÄ± â€” EÄ°SA ile iletiÅŸime geÃ§in.
            </div>
          )}
          <ErrorBoundary key={active==='customer_360'?`c360-${c360Id}`:(active||'none')} onHome={goHome}>
            {active==='customer_360' && c360Id ? (
              <Customer360Page companyId={c360Id} onBack={closeCustomer360} onNavigate={goModule} user={user}/>
            ) : pages[active] || (
              <section className="panel">
                <h3 style={{marginTop:0}}>ModÃ¼l bulunamadÄ±</h3>
                <p style={{color:'#64748b'}}>Bu sayfa rolÃ¼nÃ¼z iÃ§in tanÄ±mlÄ± deÄŸil veya geÃ§ersiz.</p>
                <button type="button" onClick={goHome}>Ana panele dÃ¶n</button>
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

