import React,{useEffect,useState} from 'react';
import {AlertTriangle,ArrowRight,RefreshCw,ShieldCheck} from 'lucide-react';
import {api} from './api';
import {controlTowerActionFor,controlTowerActionHref,controlTowerCompanyContextHref} from './control_tower_actions';

function Metric({label,value,warning=false,dark=false}){return <div style={{padding:12,borderRadius:12,border:dark?'1px solid rgba(255,255,255,.14)':'1px solid #e2e8f0',background:dark?'rgba(15,23,42,.45)':'#fff'}}><small style={{opacity:.72}}>{label}</small><div style={{fontSize:24,fontWeight:800,color:warning&&Number(value)>0?'#f59e0b':undefined}}>{value??0}</div></div>}

function ScoreCard({data,dark}){const score=Number(data?.compliance_score??0);return <div style={{padding:16,borderRadius:16,border:dark?'1px solid rgba(255,255,255,.14)':'1px solid #dbeafe',background:dark?'rgba(15,23,42,.55)':'linear-gradient(135deg,#eff6ff,#f8fafc)',marginBottom:12,display:'flex',alignItems:'center',justifyContent:'space-between',gap:16,flexWrap:'wrap'}}><div><small style={{opacity:.7}}>İşyeri İSG operasyon skoru</small><div style={{fontSize:38,fontWeight:900,lineHeight:1}}>{score}<span style={{fontSize:18,opacity:.6}}>/100</span></div></div><div style={{minWidth:170}}><strong>{data?.compliance_band||'—'}</strong><div style={{fontSize:12,opacity:.7,marginTop:4}}>Açıklanabilir · salt okunur · sağlık klinik verisi puana dahil edilmez</div></div></div>}

function AttentionQueue({items=[],dark=false,userRole='',companyId=null}){
  if(!items.length)return <div style={{marginTop:10,fontSize:13,opacity:.75}}>Bugün için kritik operasyon kuyruğu temiz görünüyor.</div>;
  const contextHref=controlTowerCompanyContextHref(companyId);
  return <div style={{marginTop:12,display:'grid',gap:7}}>{items.slice(0,6).map((item,index)=>{
    const action=controlTowerActionFor(item,userRole);
    const href=controlTowerActionHref(item,userRole);
    return <div key={`${item.domain}-${item.title}-${index}`} style={{padding:'10px 12px',borderRadius:10,border:dark?'1px solid rgba(255,255,255,.12)':'1px solid #e2e8f0',display:'flex',gap:10,alignItems:'flex-start',justifyContent:'space-between',flexWrap:'wrap'}}><div style={{display:'flex',gap:10,alignItems:'flex-start',minWidth:0,flex:'1 1 260px'}}><AlertTriangle size={16} style={{marginTop:2,flex:'0 0 auto'}}/><div style={{minWidth:0}}><strong style={{fontSize:13}}>{item.title}</strong><div style={{fontSize:12,opacity:.72}}>{item.count} kayıt · {item.reason}</div></div></div><div style={{display:'flex',gap:6,alignItems:'center',flexWrap:'wrap'}}>{contextHref&&<a href={contextHref} className="mini secondary" style={{textDecoration:'none',display:'inline-flex',alignItems:'center',gap:5,whiteSpace:'nowrap'}}>İşyeri bağlamı<ArrowRight size={13}/></a>}{action&&href&&<a href={href} className="mini secondary" style={{textDecoration:'none',display:'inline-flex',alignItems:'center',gap:5,whiteSpace:'nowrap'}}>{action.label}<ArrowRight size={13}/></a>}</div></div>;
  })}</div>;
}

export function FacilityComplianceSummaryPanel({companyId,dark=false,compact=false,userRole=''}){
  const[data,setData]=useState(null);const[err,setErr]=useState('');const[busy,setBusy]=useState(false);
  async function load(){if(!companyId)return;setBusy(true);setErr('');try{setData(await api(`/facility-compliance-summary?company_id=${companyId}`))}catch(e){setErr(e.message);setData(null)}finally{setBusy(false)}}
  useEffect(()=>{void load()},[companyId]);
  if(!companyId)return null;
  return <div style={{marginTop:compact?12:0,color:dark?'#f8fafc':undefined}}>
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:12,marginBottom:10}}><div><strong style={{display:'flex',alignItems:'center',gap:7}}><ShieldCheck size={18}/> Tesis Uygunluk Özeti · İSG Control Tower</strong><small style={{opacity:.7}}>Salt okunur · Taşeron + PTW + periyodik kontrol + saha denetimi + birleşik DÖF/aksiyon + profesyonel kapasite</small></div><button type="button" className="mini secondary" onClick={()=>void load()} disabled={busy}><RefreshCw size={14}/> Yenile</button></div>
    {err&&<div className="error">{err}</div>}
    {data&&<><ScoreCard data={data} dark={dark}/><div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))',gap:8}}><Metric dark={dark} label="Toplam dikkat" value={data.attention_count} warning/><Metric dark={dark} label="Aktif taşeron" value={data.contractors?.active}/><Metric dark={dark} label="Taşeron belge" value={data.contractors?.expired_documents} warning/><Metric dark={dark} label="PTW dikkat" value={data.ptw?.attention} warning/><Metric dark={dark} label="Periyodik gecikmiş" value={data.periodic?.overdue} warning/><Metric dark={dark} label="Denetim aksiyonu" value={data.inspections?.open_actions}/><Metric dark={dark} label="Açık birleşik aksiyon" value={data.actions?.open}/><Metric dark={dark} label="Gecikmiş aksiyon" value={data.actions?.overdue} warning/><Metric dark={dark} label="Kapasite kritik" value={data.capacity?.critical_assignments} warning/><Metric dark={dark} label="Kapasite uyarı" value={data.capacity?.warning_assignments} warning/><Metric dark={dark} label="Kapasite aşımı" value={data.capacity?.overloaded_professionals} warning/></div>{data.attention_count>0&&<div style={{marginTop:10,display:'flex',gap:7,alignItems:'center',fontSize:13}}><AlertTriangle size={16}/> {data.attention_count} kayıt gözden geçirme gerektiriyor.</div>}<AttentionQueue items={data.control_tower?.today_attention||[]} dark={dark} userRole={userRole} companyId={companyId}/></>}
  </div>;
}

export function FacilityComplianceSummaryPage({user}){
  const[companies,setCompanies]=useState([]);const[companyId,setCompanyId]=useState(user.company_id||'');const[err,setErr]=useState('');
  useEffect(()=>{api('/companies').then(rows=>{setCompanies(rows||[]);if(!companyId&&rows?.length)setCompanyId(String(rows[0].id))}).catch(e=>setErr(e.message))},[]);
  return <><div className="page-title"><h3><ShieldCheck size={20}/> Tesis Uygunluk Özeti · İSG Control Tower</h3></div><section className="panel"><p className="muted">Bu ekran kayıt değiştirmez; mevcut saha modüllerinin durumunu tek bakışta toplar ve “bugün neye müdahale etmeliyim?” önceliği ile açıklanabilir 0–100 operasyon skoru üretir. Uygun kısayollar yalnız mevcut modülleri açar; yeni veya paralel iş akışı oluşturmaz. “İşyeri bağlamı” seçili işyerinin mevcut Durum Merkezi'ni açar ve yanlış işyerine geçiş riskini azaltır.</p>{!user.company_id&&<label className="field" style={{maxWidth:460}}><span>İşyeri</span><select value={companyId} onChange={e=>setCompanyId(e.target.value)}><option value="">Seçiniz</option>{companies.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>}{err&&<div className="error">{err}</div>}<FacilityComplianceSummaryPanel companyId={companyId?Number(companyId):null} userRole={user.role}/></section></>;
}
