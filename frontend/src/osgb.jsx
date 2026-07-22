import React,{useEffect,useMemo,useRef,useState} from 'react';
import {api,downloadFile,uploadFile} from './api';
import {Plus} from 'lucide-react';
import {enqueueOfflineComplete,flushOfflineCompletes,listOfflineCompletes,removeOfflineItem} from './field_offline';

const ptypes={safety_specialist:'İş Güvenliği Uzmanı',workplace_physician:'İşyeri Hekimi',other_health_personnel:'Diğer Sağlık Personeli'};
const stages={new:'Yeni',contacted:'Görüşüldü',proposal:'Teklif',negotiation:'Müzakere',won:'Kazanıldı',lost:'Kaybedildi'};
const money=v=>new Intl.NumberFormat('tr-TR',{style:'currency',currency:'TRY',maximumFractionDigits:0}).format(v||0);
function F({label,...p}){return <label className="field"><span>{label}</span><input {...p}/></label>}
function S({label,children,...p}){return <label className="field"><span>{label}</span><select {...p}>{children}</select></label>}
function M({title,close,children}){return <div className="modal-bg"><section className="modal"><header><h3>{title}</h3><button className="icon" onClick={close}>×</button></header>{children}</section></div>}
function T({cols,rows}){return <div className="table-wrap"><table><thead><tr>{cols.map(c=><th key={c.k}>{c.l}</th>)}</tr></thead><tbody>{rows.length?rows.map((r,i)=><tr key={r.id||i}>{cols.map(c=><td key={c.k}>{c.f?c.f(r):String(r[c.k]??'—')}</td>)}</tr>):<tr><td colSpan={cols.length} className="empty">Henüz kayıt bulunmuyor.</td></tr>}</tbody></table></div>}
function P({title,action,children}){return <><div className="page-title"><h3>{title}</h3>{action}</div><section className="panel">{children}</section></>}
function osgbId(user,orgs){return user.osgb_id||orgs[0]?.id||''}

/** Tarayıcı GPS — izin yoksa null döner (tamamlama yine yapılabilir). */
function captureGps(timeoutMs=12000){
  return new Promise((resolve)=>{
    if(typeof navigator==='undefined'||!navigator.geolocation){
      resolve(null);return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos)=>{
        resolve({
          gps_lat:pos.coords.latitude,
          gps_lng:pos.coords.longitude,
          gps_accuracy_m:typeof pos.coords.accuracy==='number'?pos.coords.accuracy:null,
        });
      },
      ()=>resolve(null),
      {enableHighAccuracy:true,timeout:timeoutMs,maximumAge:30000}
    );
  });
}

function fmtGps(row){
  if(row?.gps_lat==null||row?.gps_lng==null) return '—';
  const acc=row.gps_accuracy_m!=null?` ±${Math.round(row.gps_accuracy_m)}m`:'';
  return `${Number(row.gps_lat).toFixed(5)}, ${Number(row.gps_lng).toFixed(5)}${acc}`;
}

function parseSiteInput(raw){
  const text=String(raw||'').trim();
  if(!text) return '';
  const prefix='ISGSUITE:WP:';
  if(text.toUpperCase().startsWith(prefix)){
    const tail=text.slice(prefix.length);
    const parts=tail.split(':');
    if(parts.length>=2) return parts.slice(1).join(':').replace(/[^A-Za-z0-9]/g,'').toUpperCase();
  }
  return text.replace(/[^A-Za-z0-9]/g,'').toUpperCase();
}

function SignaturePad({onChange}){
  const canvasRef=useRef(null);
  const drawing=useRef(false);
  const last=useRef(null);

  useEffect(()=>{
    const c=canvasRef.current; if(!c) return;
    const ctx=c.getContext('2d');
    ctx.fillStyle='#fff';
    ctx.fillRect(0,0,c.width,c.height);
    ctx.strokeStyle='#0f172a';
    ctx.lineWidth=2.2;
    ctx.lineCap='round';
    ctx.lineJoin='round';
    onChange?.(null);
  },[]);

  function pos(e){
    const c=canvasRef.current;
    const r=c.getBoundingClientRect();
    const t=e.touches?.[0];
    const x=(t?t.clientX:e.clientX)-r.left;
    const y=(t?t.clientY:e.clientY)-r.top;
    return {x:x*(c.width/r.width),y:y*(c.height/r.height)};
  }
  function start(e){e.preventDefault();drawing.current=true;last.current=pos(e)}
  function move(e){
    if(!drawing.current) return;
    e.preventDefault();
    const c=canvasRef.current; const ctx=c.getContext('2d');
    const p=pos(e); const l=last.current;
    ctx.beginPath(); ctx.moveTo(l.x,l.y); ctx.lineTo(p.x,p.y); ctx.stroke();
    last.current=p;
    onChange?.(c.toDataURL('image/png'));
  }
  function end(e){e?.preventDefault?.();drawing.current=false;last.current=null}
  function clear(){
    const c=canvasRef.current; if(!c) return;
    const ctx=c.getContext('2d');
    ctx.fillStyle='#fff'; ctx.fillRect(0,0,c.width,c.height);
    onChange?.(null);
  }
  return <div style={{gridColumn:'1/-1'}}>
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}>
      <span style={{fontSize:13,fontWeight:600,color:'#334155'}}>Saha imzası</span>
      <button type="button" className="mini secondary" onClick={clear}>Temizle</button>
    </div>
    <canvas
      ref={canvasRef}
      width={640}
      height={220}
      style={{width:'100%',height:160,border:'1px solid #cbd5e1',borderRadius:10,touchAction:'none',background:'#fff',cursor:'crosshair'}}
      onMouseDown={start} onMouseMove={move} onMouseUp={end} onMouseLeave={end}
      onTouchStart={start} onTouchMove={move} onTouchEnd={end}
    />
  </div>
}

async function copyText(text){
  const v=String(text||'');
  if(!v) return false;
  try{
    if(navigator.clipboard?.writeText){
      await navigator.clipboard.writeText(v);
      return true;
    }
  }catch(_){/* fallback */}
  try{
    const ta=document.createElement('textarea');
    ta.value=v;
    ta.setAttribute('readonly','');
    ta.style.position='fixed';
    ta.style.left='-9999px';
    document.body.appendChild(ta);
    ta.select();
    const ok=document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  }catch(_){return false}
}

export function OsgbDashboard({user, onNavigate}){
 const[orgs,setOrgs]=useState([]),[data,setData]=useState(null),[oid,setOid]=useState('');
 const[ops,setOps]=useState(null);
 const[kpis,setKpis]=useState(null);
 const[csgb,setCsgb]=useState(null);
 const[csgbDlBusy,setCsgbDlBusy]=useState(false);
 const[integ,setInteg]=useState(null);
 const[adapterStatus,setAdapterStatus]=useState(null);
 const[dryRunBusy,setDryRunBusy]=useState('');
 const[probeBusy,setProbeBusy]=useState('');
 const[liveBusy,setLiveBusy]=useState('');
 const[probeResult,setProbeResult]=useState(null);
 const[liveResult,setLiveResult]=useState(null);
 const[unassignedOpen,setUnassignedOpen]=useState(false);
 const[unassignedType,setUnassignedType]=useState('safety_specialist');
 const[contractsOpen,setContractsOpen]=useState(false);

 async function load(id){
  if(!id){setData(null);setOps(null);setKpis(null);setCsgb(null);setInteg(null);setAdapterStatus(null);return}
  setData(await api(`/operations/dashboard?osgb_id=${id}`));
  try{
   setOps(await api(`/osgb/oversight?osgb_id=${id}`));
  }catch(_){setOps(null)}
  try{
   setKpis(await api(`/operations/module-kpis?osgb_id=${id}`));
  }catch(_){setKpis(null)}
  try{
   setCsgb(await api(`/osgb/csgb-audit-pack/summary?osgb_id=${id}`));
  }catch(_){setCsgb(null)}
  try{
   setInteg(await api(`/osgb/integration-readiness?osgb_id=${id}`));
  }catch(_){setInteg(null)}
  try{
   setAdapterStatus(await api(`/osgb/integrations/status?osgb_id=${id}`));
  }catch(_){setAdapterStatus(null)}
 }

 async function runDryExport(adapter){
  if(!oid||dryRunBusy||probeBusy||liveBusy) return;
  setDryRunBusy(adapter);
  try{
   await api(`/osgb/integrations/${adapter}/dry-run?osgb_id=${oid}`,{method:'POST'});
   setAdapterStatus(await api(`/osgb/integrations/status?osgb_id=${oid}`));
  }catch(e){alert(e.message||'Dry-run başarısız')}
  finally{setDryRunBusy('')}
 }

 async function runProbe(adapter){
  if(probeBusy||dryRunBusy||liveBusy) return;
  setProbeBusy(adapter);
  try{
   const res=await api(`/osgb/integrations/${adapter}/probe`,{method:'POST'});
   setProbeResult(res);
  }catch(e){alert(e.message||'Bağlantı denemesi başarısız');setProbeResult(null)}
  finally{setProbeBusy('')}
 }

 async function runLiveSend(adapter){
  if(!oid||liveBusy||dryRunBusy||probeBusy) return;
  const label=adapter==='ibys'?'İBYS':'KATİP';
  if(!window.confirm(`${label} canlı gönderim denensin mi? Kimlik yoksa ağ çağrısı yapılmaz.`)) return;
  setLiveBusy(adapter);
  try{
   const res=await api(`/osgb/integrations/${adapter}/live-send?osgb_id=${oid}`,{method:'POST'});
   setLiveResult(res);
   setAdapterStatus(await api(`/osgb/integrations/status?osgb_id=${oid}`));
  }catch(e){alert(e.message||'Canlı gönderim başarısız');setLiveResult(null)}
  finally{setLiveBusy('')}
 }

 useEffect(()=>{
  api('/osgb').then(o=>{
   setOrgs(o);
   const id=String(osgbId(user,o)||'');
   setOid(id);
   if(id) load(id);
  });
 },[]);

 const byType=data?.professionals_by_type||{};
 const unBy=data?.unassigned_by_type||{};
 const unSelected=unBy[unassignedType]||{count:0,items:[],label:ptypes[unassignedType]};
 const contracts=data?.upcoming_contracts||[];
 const sum=ops?.summary||{};
 const rk=kpis?.risk||{};
 const tr=kpis?.training||{};
 const hl=kpis?.health||{};
 const go=(mod)=>{ if(typeof onNavigate==='function') onNavigate(mod); };
 const csgbPct=csgb?.readiness_pct??csgb?.summary?.readiness_pct;
 const csgbGaps=csgb?.missing_items||[];

 async function downloadCsgbZip(){
  if(!oid) return;
  setCsgbDlBusy(true);
  try{
   const stamp=new Date().toISOString().slice(0,10);
   await downloadFile(`/osgb/csgb-audit-pack/bundle?osgb_id=${oid}`,`csgb-denetim-paketi-${stamp}.zip`);
  }catch(e){alert(e.message||'ZIP indirilemedi')}
  finally{setCsgbDlBusy(false)}
 }

 return <>
  <div className="welcome"><div>
   <h3>OSGB Ana Panel</h3>
   <p>Günlük hizmet süreçlerini anlık izleyin; eksik/kritik noktalara buradan müdahale edin.</p>
  </div></div>

  {orgs.length>1&&user.role==='global_admin'&&<section className="panel" style={{marginBottom:16}}>
   <label className="field"><span>OSGB</span>
    <select value={oid} onChange={e=>{const v=e.target.value;setOid(v);load(v)}}>
     {orgs.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}
    </select>
   </label>
  </section>}

  {integ&&(
   <section className="panel" style={{marginBottom:16}}>
    <div style={{display:'flex',justifyContent:'space-between',gap:12,flexWrap:'wrap',alignItems:'flex-start'}}>
     <div>
      <h3 style={{margin:'0 0 4px'}}>Entegrasyon hazırlık</h3>
      <p style={{margin:0,color:'#64748b',fontSize:13}}>
       İBYS / KATİP stub kontrol listesi · gerçek resmi API yok; CSV, eksik KATİP ve ÇSGB paketi durumu.
      </p>
     </div>
     <div style={{
       minWidth:88,textAlign:'center',padding:'8px 12px',borderRadius:10,
       background:integ.overall_ready?'#dcfce7':(integ.summary?.items_ok||0)>=2?'#fef3c7':'#fee2e2',
       color:integ.overall_ready?'#166534':(integ.summary?.items_ok||0)>=2?'#92400e':'#991b1b',
     }}>
      <div style={{fontSize:22,fontWeight:800}}>{integ.summary?.items_ok??0}/{integ.summary?.items_total??3}</div>
      <div style={{fontSize:11,fontWeight:700}}>Hazır</div>
     </div>
    </div>
    <ul style={{margin:'12px 0 0',paddingLeft:0,fontSize:13,color:'#334155',listStyle:'none'}}>
     {(integ.checklist||[]).map((item)=>(
      <li key={item.code} style={{marginBottom:8,display:'flex',gap:10,alignItems:'flex-start'}}>
       <span style={{
         flexShrink:0,minWidth:64,textAlign:'center',padding:'2px 8px',borderRadius:6,fontSize:11,fontWeight:700,
         background:item.status==='ready'?'#dcfce7':item.status==='partial'?'#fef3c7':'#fee2e2',
         color:item.status==='ready'?'#166534':item.status==='partial'?'#92400e':'#991b1b',
       }}>
        {item.status==='ready'?'Hazır':item.status==='partial'?'Kısmi':'Eksik'}
       </span>
       <div>
        <strong>{item.title}</strong>
        {item.code==='katip_gaps'&&item.gap_count!=null?` · ${item.gap_count} eksik`:''}
        {item.code==='csgb_pack'&&item.readiness_pct!=null?` · %${item.readiness_pct}`:''}
        <div style={{color:'#64748b',fontSize:12,marginTop:2}}>{item.detail}</div>
       </div>
      </li>
     ))}
    </ul>
    <div style={{display:'flex',gap:8,flexWrap:'wrap',marginTop:12}}>
     <button type="button" className="mini secondary" onClick={()=>go('csgb_audit')}>İBYS / ÇSGB paketi</button>
     <button type="button" className="mini secondary" onClick={()=>go('assignments')}>KATİP / görevlendirme</button>
    </div>
    {adapterStatus&&(
     <div style={{marginTop:12,paddingTop:10,borderTop:'1px solid #e2e8f0',fontSize:12,color:'#64748b'}}>
      <span>Adapter: </span>
      <strong style={{color:adapterStatus.summary?.ibys_configured?'#166534':'#92400e'}}>
       İBYS {adapterStatus.summary?.ibys_configured?'yapılandırıldı':'stub'}
      </strong>
      <span> · </span>
      <strong style={{color:adapterStatus.summary?.katip_configured?'#166534':'#92400e'}}>
       KATİP {adapterStatus.summary?.katip_configured?'yapılandırıldı':'stub'}
      </strong>
      <div style={{display:'flex',gap:8,flexWrap:'wrap',marginTop:8}}>
       <button type="button" className="mini secondary" disabled={!!dryRunBusy||!!probeBusy||!!liveBusy}
         onClick={()=>runDryExport('ibys')}>
        {dryRunBusy==='ibys'?'İBYS dry-run…':'İBYS dry-run'}
       </button>
       <button type="button" className="mini secondary" disabled={!!dryRunBusy||!!probeBusy||!!liveBusy}
         onClick={()=>runDryExport('katip')}>
        {dryRunBusy==='katip'?'KATİP dry-run…':'KATİP dry-run'}
       </button>
       <button type="button" className="mini secondary" disabled={!!dryRunBusy||!!probeBusy||!!liveBusy}
         onClick={()=>runProbe('ibys')}>
        {probeBusy==='ibys'?'İBYS bağlantı…':'İBYS bağlantı dene'}
       </button>
       <button type="button" className="mini secondary" disabled={!!dryRunBusy||!!probeBusy||!!liveBusy}
         onClick={()=>runProbe('katip')}>
        {probeBusy==='katip'?'KATİP bağlantı…':'KATİP bağlantı dene'}
       </button>
       <button type="button" className="mini secondary" disabled={!!dryRunBusy||!!probeBusy||!!liveBusy}
         onClick={()=>runLiveSend('ibys')}>
        {liveBusy==='ibys'?'İBYS canlı…':'İBYS canlı gönder'}
       </button>
       <button type="button" className="mini secondary" disabled={!!dryRunBusy||!!probeBusy||!!liveBusy}
         onClick={()=>runLiveSend('katip')}>
        {liveBusy==='katip'?'KATİP canlı…':'KATİP canlı gönder'}
       </button>
      </div>
      {probeResult&&(
       <div style={{
         marginTop:8,fontSize:12,fontWeight:600,
         color:probeResult.ok?'#166534':probeResult.status==='missing_credentials'?'#92400e':'#991b1b',
       }}>
        Son probe · {String(probeResult.adapter||'').toUpperCase()}: {probeResult.status}
        {probeResult.http_status!=null?` · HTTP ${probeResult.http_status}`:''}
        {probeResult.elapsed_ms!=null?` · ${probeResult.elapsed_ms} ms`:''}
       </div>
      )}
      {liveResult&&(
       <div style={{
         marginTop:8,fontSize:12,fontWeight:600,
         color:liveResult.ok?'#166534':liveResult.status==='missing_credentials'?'#92400e':'#991b1b',
       }}>
        Son canlı · {String(liveResult.adapter||'').toUpperCase()}: {liveResult.status}
        {liveResult.http_status!=null?` · HTTP ${liveResult.http_status}`:''}
        {liveResult.elapsed_ms!=null?` · ${liveResult.elapsed_ms} ms`:''}
        {liveResult.note?` — ${liveResult.note}`:''}
       </div>
      )}
      {(adapterStatus.last_dry_runs||[]).length>0&&(
       <div style={{marginTop:10,overflowX:'auto'}}>
        <div style={{fontWeight:700,color:'#475569',marginBottom:4}}>Son dry-run’lar</div>
        <table style={{width:'100%',borderCollapse:'collapse',fontSize:11}}>
         <thead>
          <tr style={{textAlign:'left',color:'#94a3b8'}}>
           <th style={{padding:'2px 6px 4px 0'}}>Ne zaman</th>
           <th style={{padding:'2px 6px 4px'}}>Kim</th>
           <th style={{padding:'2px 6px 4px'}}>Adapter</th>
           <th style={{padding:'2px 6px 4px'}}>Durum</th>
           <th style={{padding:'2px 0 4px 6px',textAlign:'right'}}>Kayıt</th>
          </tr>
         </thead>
         <tbody>
          {adapterStatus.last_dry_runs.slice(0,8).map(row=>(
           <tr key={row.id} style={{borderTop:'1px solid #f1f5f9'}}>
            <td style={{padding:'4px 6px 4px 0',whiteSpace:'nowrap'}}>{row.when||'—'}</td>
            <td style={{padding:'4px 6px'}}>{row.who||'—'}</td>
            <td style={{padding:'4px 6px',textTransform:'uppercase'}}>{row.adapter}</td>
            <td style={{padding:'4px 6px'}}>{row.status}</td>
            <td style={{padding:'4px 0 4px 6px',textAlign:'right'}}>{row.record_count??0}</td>
           </tr>
          ))}
         </tbody>
        </table>
       </div>
      )}
      {(adapterStatus.adapters?.ibys?.last_stub_export_at||adapterStatus.adapters?.katip?.last_stub_export_at)&&(
       <div style={{marginTop:4,color:'#94a3b8'}}>
        Son stub export:
        {adapterStatus.adapters?.ibys?.last_stub_export_at?` İBYS ${adapterStatus.adapters.ibys.last_stub_export_at}`:''}
        {adapterStatus.adapters?.katip?.last_stub_export_at?` · KATİP ${adapterStatus.adapters.katip.last_stub_export_at}`:''}
       </div>
      )}
     </div>
    )}
    {integ.stub&&(
     <p style={{margin:'10px 0 0',color:'#94a3b8',fontSize:12}}>
      Not: Resmi İBYS/KATİP API entegrasyonu henüz yok — bu kart hazırlık durumunu gösterir.
     </p>
    )}
   </section>
  )}

  {csgb&&(
   <section className="panel" style={{marginBottom:16}}>
    <div style={{display:'flex',justifyContent:'space-between',gap:12,flexWrap:'wrap',alignItems:'flex-start'}}>
     <div>
      <h3 style={{margin:'0 0 4px'}}>ÇSGB denetim hazırlığı</h3>
      <p style={{margin:0,color:'#64748b',fontSize:13}}>
       Öncelikli eksikler · müfettiş paketi / işyeri snapshot ÇSGB Belge Paketi’nden.
      </p>
     </div>
     <div style={{display:'flex',gap:8,flexWrap:'wrap',alignItems:'center'}}>
      <div style={{
        minWidth:88,textAlign:'center',padding:'8px 12px',borderRadius:10,
        background:(csgbPct??0)>=70?'#dcfce7':(csgbPct??0)>=40?'#fef3c7':'#fee2e2',
        color:(csgbPct??0)>=70?'#166534':(csgbPct??0)>=40?'#92400e':'#991b1b',
      }}>
       <div style={{fontSize:22,fontWeight:800}}>%{csgbPct??0}</div>
       <div style={{fontSize:11,fontWeight:700}}>Hazırlık</div>
      </div>
      <button type="button" className="mini" disabled={csgbDlBusy} onClick={()=>void downloadCsgbZip()}>
       {csgbDlBusy?'Hazırlanıyor…':'ZIP indir'}
      </button>
      <button type="button" className="mini secondary" onClick={()=>go('csgb_audit')}>Pakete git</button>
     </div>
    </div>
    <div style={{display:'flex',gap:14,flexWrap:'wrap',marginTop:10,fontSize:13}}>
     <span>Hazır <strong>{csgb.summary?.ready??0}</strong></span>
     <span>Kısmi <strong>{csgb.summary?.partial??0}</strong></span>
     <span style={{color:(csgb.summary?.missing||0)?'#991b1b':undefined}}>Eksik <strong>{csgb.summary?.missing??0}</strong></span>
     <span>Öncelik <strong>{csgb.gap_count??csgbGaps.length}</strong></span>
    </div>
    {csgbGaps.length>0&&(
     <ul style={{margin:'12px 0 0',paddingLeft:18,fontSize:13,color:'#334155'}}>
      {csgbGaps.slice(0,5).map((g,i)=>(
       <li key={g.code||i} style={{marginBottom:4}}>
        <strong>{g.title||'Kalem'}</strong>
        {g.status?` (${g.status==='missing'?'eksik':g.status==='partial'?'kısmi':g.status})`:''}
        {g.detail?` — ${g.detail}`:''}
       </li>
      ))}
     </ul>
    )}
    {!csgbGaps.length&&(
     <p style={{margin:'12px 0 0',color:'#166534',fontSize:13,fontWeight:600}}>Öncelikli eksik/kısmi kalem yok.</p>
    )}
   </section>
  )}

  <div className="cards osgb-cards" style={{marginBottom:16}}>
   <article className="metric" style={{cursor:'pointer'}} onClick={()=>go('finance')} title="Finansa git">
    <span>Vadesi geçmiş tahakkuk</span>
    <strong style={{color:(data?.finance_overdue_count||0)>0?'#b91c1c':undefined}}>{data?.finance_overdue_count??0}</strong>
    <small style={{display:'block',marginTop:6,color:'#64748b',fontSize:11,fontWeight:600}}>{money(data?.finance_overdue_amount||0)}</small>
   </article>
   <article className="metric" style={{cursor:'pointer'}} onClick={()=>go('finance')} title="Finansa git">
    <span>30 günde vadeli</span>
    <strong style={{color:(data?.finance_due_soon_count||0)>0?'#b45309':undefined}}>{data?.finance_due_soon_count??0}</strong>
    <small style={{display:'block',marginTop:6,color:'#64748b',fontSize:11,fontWeight:600}}>{money(data?.finance_due_soon_amount||0)}</small>
   </article>
   <article className="metric" style={{cursor:'pointer'}} onClick={()=>go('mevzuat')} title="Mevzuat özetine git">
    <span>Mevzuat özeti</span>
    <strong style={{fontSize:16}}>Öne çıkanlar</strong>
    <small style={{display:'block',marginTop:6,color:'#64748b',fontSize:11,fontWeight:600}}>6331 / yönetmelik kısa notlar</small>
   </article>
   <article className="metric" style={{cursor:'pointer'}} onClick={()=>go('notifications')} title="Bildirim merkezine git — SDS tarama">
    <span>SDS gözden geçirme</span>
    <strong style={{color:(data?.sds_overdue_count||0)>0?'#b91c1c':(data?.sds_due_soon_count||0)>0?'#b45309':undefined}}>
     {(data?.sds_overdue_count||0)+(data?.sds_due_soon_count||0)}
    </strong>
    <small style={{display:'block',marginTop:6,color:'#64748b',fontSize:11,fontWeight:600}}>
     Gecikmiş {data?.sds_overdue_count??0} · 30 günde {data?.sds_due_soon_count??0}
    </small>
   </article>
  </div>
  {((data?.finance_alerts||[]).length>0||(data?.contract_alerts||[]).length>0||(data?.sds_alerts||[]).length>0)&&(
   <div style={{display:'grid',gap:8,marginBottom:16}}>
    {(data?.finance_alerts||[]).map((a,i)=>(
     <div key={'f'+i} style={{padding:'10px 12px',borderRadius:10,background:a.level==='critical'?'#fee2e2':'#fef3c7',color:a.level==='critical'?'#991b1b':'#92400e',fontSize:13,fontWeight:600,cursor:'pointer'}} onClick={()=>go('finance')}>
      {a.text}
     </div>
    ))}
    {(data?.contract_alerts||[]).map((a,i)=>(
     <div key={'c'+i} style={{padding:'10px 12px',borderRadius:10,background:a.level==='critical'?'#fee2e2':'#fef3c7',color:a.level==='critical'?'#991b1b':'#92400e',fontSize:13,fontWeight:600,cursor:'pointer'}} onClick={()=>go('contracts')}>
      {a.text}
     </div>
    ))}
    {(data?.sds_alerts||[]).map((a,i)=>(
     <div key={'s'+i} style={{padding:'10px 12px',borderRadius:10,background:a.level==='critical'?'#fee2e2':'#fef3c7',color:a.level==='critical'?'#991b1b':'#92400e',fontSize:13,fontWeight:600,cursor:'pointer'}} onClick={()=>go('notifications')}>
      {a.text}
     </div>
    ))}
   </div>
  )}

  <div className="cards osgb-cards" style={{marginBottom:16}}>
   <article className="metric" style={{cursor:'pointer'}} onClick={()=>go('osgb_oversight')} title="Hizmet denetimine git">
    <span>Kritik Profesyonel</span>
    <strong style={{color:(sum.critical||0)>0?'#b91c1c':undefined}}>{sum.critical??'—'}</strong>
   </article>
   <article className="metric" style={{cursor:'pointer'}} onClick={()=>go('osgb_oversight')} title="Hizmet denetimine git">
    <span>İzlem Gereken</span>
    <strong style={{color:(sum.warning||0)>0?'#b45309':undefined}}>{sum.warning??'—'}</strong>
   </article>
   <article className="metric" style={{cursor:'pointer'}} onClick={()=>go('osgb_oversight')} title="Hizmet denetimine git">
    <span>Açık Eksik</span>
    <strong style={{color:(ops?.gap_count||0)>0?'#b91c1c':undefined}}>{ops?.gap_count??'—'}</strong>
   </article>
   <article className="metric" style={{cursor:'pointer'}} onClick={()=>go('visits')} title="Saha takvimine git">
    <span>Saha Takvimi</span>
    <strong style={{fontSize:16}}>İzle / Müdahale</strong>
   </article>
  </div>

  <section className="panel" style={{marginBottom:16}}>
   <div style={{display:'flex',justifyContent:'space-between',gap:12,flexWrap:'wrap',alignItems:'center',marginBottom:12}}>
    <div>
     <h3 style={{margin:'0 0 4px'}}>Modül KPI özeti</h3>
     <p style={{margin:0,color:'#64748b',fontSize:13}}>Risk/DÖF, eğitim yenileme ve sağlık periyodik takip — OSGB geneli salt okunur izleme.</p>
    </div>
   </div>
   {(kpis?.alerts||[]).length>0&&(
    <div style={{display:'grid',gap:8,marginBottom:12}}>
     {kpis.alerts.map((a,i)=>(
      <div key={i} style={{padding:'10px 12px',borderRadius:10,background:a.level==='critical'?'#fee2e2':'#fef3c7',color:a.level==='critical'?'#991b1b':'#92400e',fontSize:13,fontWeight:600}}>
       {a.text}
      </div>
     ))}
    </div>
   )}
   <div className="cards osgb-cards" style={{marginBottom:12}}>
    <article className="metric" title="Açık risk kayıtları">
     <span>Açık Risk</span>
     <strong style={{color:(rk.open_risks||0)>0?'#b45309':undefined}}>{rk.open_risks??'—'}</strong>
     <small style={{display:'block',marginTop:6,color:'#64748b',fontSize:11,fontWeight:600}}>Çok yüksek {rk.very_high??0} · Yüksek {rk.high??0}</small>
    </article>
    <article className="metric" title="Açık ve gecikmiş DÖF">
     <span>Açık DÖF</span>
     <strong>{rk.open_dofs??'—'}</strong>
     <small style={{display:'block',marginTop:6,color:'#64748b',fontSize:11,fontWeight:600}}>Gecikmiş {rk.overdue_dofs??0} · 7 gün {rk.due_soon_dofs??0}</small>
    </article>
    <article className="metric" title="Eğitim yenileme tarihleri">
     <span>Eğitim Yenileme</span>
     <strong style={{color:(tr.overdue_renewal||0)>0?'#b91c1c':undefined}}>{tr.overdue_renewal??0}</strong>
     <small style={{display:'block',marginTop:6,color:'#64748b',fontSize:11,fontWeight:600}}>30 gün içinde {tr.due_soon_renewal??0} · Planlı {tr.planned??0}</small>
    </article>
    <article className="metric" title="Periyodik sağlık muayeneleri">
     <span>Sağlık Muayene</span>
     <strong style={{color:(hl.overdue||0)>0?'#b91c1c':undefined}}>{hl.overdue??0}</strong>
     <small style={{display:'block',marginTop:6,color:'#64748b',fontSize:11,fontWeight:600}}>30 gün {hl.due_soon??0} · Uygunsuz {hl.unfit??0} · Kurşun {hl.lead_high??0}</small>
    </article>
   </div>
   {(kpis?.top_companies||[]).length>0&&(
    <div className="table-wrap">
     <table>
      <thead><tr><th>İşyeri</th><th>Risk/DÖF</th><th>Eğitim</th><th>Sağlık</th><th>Toplam</th></tr></thead>
      <tbody>
       {kpis.top_companies.map(row=>(
        <tr key={row.company_id}>
         <td>{row.company_name}</td>
         <td>{row.risk_issues}</td>
         <td>{row.training_issues}</td>
         <td>{row.health_issues}</td>
         <td><strong>{row.total_issues}</strong></td>
        </tr>
       ))}
      </tbody>
     </table>
    </div>
   )}
  </section>

  <section className="panel" style={{marginBottom:16}}>
   <div style={{display:'flex',justifyContent:'space-between',gap:12,flexWrap:'wrap',alignItems:'center'}}>
    <div>
     <h3 style={{margin:'0 0 4px'}}>Günlük operasyon</h3>
     <p style={{margin:0,color:'#64748b',fontSize:13}}>Süreçleri takip edin, eksikleri kapatın, profesyonel performansına bakın.</p>
    </div>
    <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
     <button type="button" className="mini" onClick={()=>go('osgb_oversight')}>Hizmet Denetimi</button>
     <button type="button" className="mini" onClick={()=>go('pro_performance')}>Performans</button>
     <button type="button" className="mini" onClick={()=>go('visits')}>Saha Takvimi</button>
     <button type="button" className="mini" onClick={()=>go('csgb_audit')}>ÇSGB Paketi</button>
     <button type="button" className="mini" onClick={()=>go('professionals')}>Profesyoneller</button>
     <button type="button" className="mini" onClick={()=>go('assignments')}>Görevlendirmeler</button>
    </div>
   </div>
  </section>

  <div className="cards osgb-cards" style={{marginBottom:16}}>
   <article className="metric"><span>Müşteri İşyerleri</span><strong>{data?.workplaces??0}</strong></article>
   <article className="metric"><span>İş Güvenliği Uzmanları</span><strong>{byType.safety_specialist?.count??0}</strong></article>
   <article className="metric"><span>İşyeri Hekimleri</span><strong>{byType.workplace_physician?.count??0}</strong></article>
   <article className="metric"><span>Diğer Sağlık Personeli</span><strong>{byType.other_health_personnel?.count??0}</strong></article>
  </div>

  <div className="cards osgb-cards" style={{marginBottom:16}}>
   <article
    className="metric"
    style={{cursor:'pointer', outline: unassignedOpen ? '2px solid #0f766e' : undefined}}
    onClick={()=>setUnassignedOpen(o=>!o)}
    title="Tıklayınca atanmamış listesini açar"
   >
    <span>Ataması Yapılmamış</span>
    <strong style={{color:(data?.unassigned_professionals||0)>0?'#b91c1c':undefined}}>
      {data?.unassigned_professionals??0}
    </strong>
    <small style={{display:'block',marginTop:6,color:'#64748b',fontSize:11,fontWeight:600}}>
      Uzman {unBy.safety_specialist?.count??0} · Hekim {unBy.workplace_physician?.count??0} · DSP {unBy.other_health_personnel?.count??0}
    </small>
   </article>
   <article
    className="metric"
    style={{cursor:'pointer', outline: contractsOpen ? '2px solid #0f766e' : undefined}}
    onClick={()=>setContractsOpen(o=>!o)}
    title="Tıklayınca sözleşme listesini açar"
   >
    <span>Bitmesi Yaklaşan Sözleşmeler</span>
    <strong style={{color:(data?.upcoming_contract_expiries||0)>0?'#b45309':undefined}}>
      {data?.upcoming_contract_expiries??0}
    </strong>
    <small style={{display:'block',marginTop:6,color:'#64748b',fontSize:11,fontWeight:600}}>
      Önümüzdeki {data?.period_days??30} gün
    </small>
   </article>
  </div>

  {unassignedOpen&&(
   <section className="panel" style={{marginBottom:16}}>
    <div style={{display:'flex',justifyContent:'space-between',gap:12,flexWrap:'wrap',alignItems:'center',marginBottom:12}}>
     <h3 style={{margin:0}}>Ataması yapılmamış profesyoneller</h3>
     <label className="field" style={{margin:0,minWidth:260}}>
      <span>Rol seçin</span>
      <select value={unassignedType} onChange={e=>setUnassignedType(e.target.value)}>
       <option value="safety_specialist">İş Güvenliği Uzmanları ({unBy.safety_specialist?.count??0})</option>
       <option value="workplace_physician">İşyeri Hekimleri ({unBy.workplace_physician?.count??0})</option>
       <option value="other_health_personnel">Diğer Sağlık Personeli ({unBy.other_health_personnel?.count??0})</option>
      </select>
     </label>
    </div>
    <p style={{marginTop:0,color:'#64748b',fontSize:13}}>
      Seçili: <strong>{unSelected.label||ptypes[unassignedType]}</strong> — {unSelected.count??0} kişi
    </p>
    <T
     cols={[
      {k:'full_name',l:'Ad Soyad'},
      {k:'certificate_class',l:'Sınıf',f:r=>r.certificate_class||'—'},
      {k:'certificate_number',l:'Belge No',f:r=>r.certificate_number||'—'},
      {k:'email',l:'E-posta',f:r=>r.email||'—'},
      {k:'phone',l:'Telefon',f:r=>r.phone||'—'},
     ]}
     rows={unSelected.items||[]}
    />
   </section>
  )}

  {contractsOpen&&(
   <section className="panel">
    <h3 style={{marginTop:0}}>Bitmesi yaklaşan sözleşmeler (30 gün)</h3>
    <T
     cols={[
      {k:'company_name',l:'İşyeri'},
      {k:'contract_number',l:'Sözleşme No'},
      {k:'end_date',l:'Bitiş',f:r=>r.end_date||'—'},
      {k:'days_left',l:'Kalan gün',f:r=>r.days_left==null?'—':`${r.days_left} gün`},
      {k:'status',l:'Durum',f:r=>r.status||'—'},
     ]}
     rows={contracts}
    />
   </section>
  )}
 </>
}

export function ProfessionalsPage({user, onNavigate}){
 const tabs=[
  {id:'safety_specialist',label:'İş Güvenliği Uzmanları'},
  {id:'workplace_physician',label:'İşyeri Hekimleri'},
  {id:'other_health_personnel',label:'Diğer Sağlık Personeli'},
 ];
 const[orgs,setOrgs]=useState([]),[rows,setRows]=useState([]),[assignments,setAssignments]=useState([]);
 const[oid,setOid]=useState('');
 const[tab,setTab]=useState('safety_specialist');
 const[q,setQ]=useState('');
 const[statusFilter,setStatusFilter]=useState('active'); // active | suspended | all
 const[open,setOpen]=useState(false);
 const[editRow,setEditRow]=useState(null);
 const[creds,setCreds]=useState(null);
 const[copyMsg,setCopyMsg]=useState('');
 const[err,setErr]=useState('');
 const[busy,setBusy]=useState(false);
 const emptyForm={full_name:'',email:'',phone:'',professional_type:'safety_specialist',certificate_class:'',certificate_number:'',certificate_date:''};
 const[form,setForm]=useState(emptyForm);

 const load=async(preferredOid)=>{
  setErr('');
  try{
   const o=await api('/osgb');
   setOrgs(o);
   const id=String(preferredOid||oid||osgbId(user,o)||'');
   if(id && !oid) setOid(id);
   const useId=preferredOid||id;
   if(!useId){setRows([]);setAssignments([]);return}
   setOid(String(useId));
   const[p,a]=await Promise.all([
    api(`/osgb/professionals?osgb_id=${useId}`),
    api('/osgb/assignments').catch(()=>[]),
   ]);
   setRows(p||[]);
   setAssignments((a||[]).filter(x=>Number(x.osgb_id)===Number(useId)));
  }catch(ex){setErr(ex.message||'Yükleme başarısız.')}
 };

 useEffect(()=>{void load()},[]);
 useEffect(()=>{
  setForm(f=>({
   ...f,
   professional_type:tab,
   certificate_class:tab==='safety_specialist'?(f.certificate_class||'A'):'',
  }));
 },[tab]);

 const assignedIds=useMemo(()=>{
  const s=new Set();
  for(const a of assignments){
   if(a.status==='active' || a.status==='ACTIVE') s.add(Number(a.professional_id));
  }
  return s;
 },[assignments]);

 const counts=useMemo(()=>Object.fromEntries(tabs.map(t=>[t.id,rows.filter(r=>r.professional_type===t.id).length])),[rows]);

 const filtered=useMemo(()=>{
  let list=rows.filter(r=>r.professional_type===tab);
  if(statusFilter==='active') list=list.filter(r=>r.is_active!==false);
  if(statusFilter==='suspended') list=list.filter(r=>r.is_active===false);
  const needle=q.trim().toLocaleLowerCase('tr');
  if(needle){
   list=list.filter(r=>[
    r.full_name,r.email,r.phone,r.certificate_number,r.certificate_class,
   ].some(v=>String(v||'').toLocaleLowerCase('tr').includes(needle)));
  }
  return list;
 },[rows,tab,statusFilter,q]);

 function openCreate(){
  setErr('');
  setEditRow(null);
  setForm({...emptyForm,professional_type:tab,certificate_class:tab==='safety_specialist'?'A':''});
  setOpen(true);
 }
 function openEdit(row){
  setErr('');
  setEditRow(row);
  const ptype=row.professional_type||tab;
  setForm({
   full_name:row.full_name||'',
   email:row.email||'',
   phone:row.phone||'',
   professional_type:ptype,
   certificate_class:ptype==='safety_specialist'?(row.certificate_class||''):'',
   certificate_number:row.certificate_number||'',
   certificate_date:row.certificate_date||'',
  });
  setOpen(true);
 }

 async function save(e){
  e.preventDefault();setErr('');setBusy(true);
  try{
   const ptype=form.professional_type||tab;
   const email=(form.email||'').trim();
   if(!email){setErr('Giriş için e-posta zorunludur.');setBusy(false);return}
   const body={
    full_name:form.full_name,
    email,
    phone:form.phone||null,
    professional_type:ptype,
    certificate_class:ptype==='safety_specialist'?(form.certificate_class||null):null,
    certificate_number:form.certificate_number||null,
    certificate_date:form.certificate_date||null,
   };
   if(editRow){
    await api(`/osgb/professionals/${editRow.id}`,{method:'PATCH',body:JSON.stringify(body)});
    setOpen(false);setEditRow(null);
   }else{
    const created=await api('/osgb/professionals',{method:'POST',body:JSON.stringify({...body,osgb_id:Number(oid)})});
    setOpen(false);setEditRow(null);
    if(created?.login_account) setCreds(created.login_account);
   }
   await load(oid);
  }catch(ex){setErr(ex.message)}
  finally{setBusy(false)}
 }

 async function suspend(row){
  if(!window.confirm(`${row.full_name} askıya alınsın mı?`)) return;
  try{await api(`/osgb/professionals/${row.id}/suspend`,{method:'PATCH'});await load(oid)}
  catch(ex){setErr(ex.message)}
 }
 async function activate(row){
  try{await api(`/osgb/professionals/${row.id}/activate`,{method:'PATCH'});await load(oid)}
  catch(ex){setErr(ex.message)}
 }
 async function remove(row){
  if(!window.confirm(`${row.full_name} silinsin mi? Aktif görevlendirme varsa silinemez.`)) return;
  try{await api(`/osgb/professionals/${row.id}`,{method:'DELETE'});await load(oid)}
  catch(ex){setErr(ex.message)}
 }
 function goPerformance(row){
  try{sessionStorage.setItem('pro_performance_id',String(row.id))}catch(_){}
  if(typeof onNavigate==='function') onNavigate('pro_performance');
 }

 return <P title="İSG Profesyonelleri" action={<button onClick={openCreate}><Plus/>Profesyonel Ekle</button>}>
  <p style={{marginTop:0,color:'#64748b',fontSize:13}}>
   OSGB kadrosu: uzman, hekim ve DSP. Eklemede e-posta ile otomatik giriş hesabı ve geçici şifre oluşur; profesyonel kendi bölümüne bu bilgilerle girer, Güvenlik menüsünden şifresini değiştirebilir.
  </p>

  {orgs.length>1&&(
   <label className="field" style={{maxWidth:360,marginBottom:12}}>
    <span>OSGB</span>
    <select value={oid} onChange={e=>{setOid(e.target.value);void load(e.target.value)}}>
     {orgs.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}
    </select>
   </label>
  )}

  <div className="actions" style={{marginBottom:12,gap:8,flexWrap:'wrap'}}>
   {tabs.map(t=>(
    <button key={t.id} type="button" className={tab===t.id?'':'secondary'} onClick={()=>setTab(t.id)}>
     {t.label} ({counts[t.id]||0})
    </button>
   ))}
  </div>

  <div className="form-grid" style={{gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',marginBottom:14}}>
   <label className="field" style={{margin:0}}>
    <span>Ara</span>
    <input value={q} onChange={e=>setQ(e.target.value)} placeholder="Ad, belge no, e-posta…"/>
   </label>
   <label className="field" style={{margin:0}}>
    <span>Durum</span>
    <select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}>
     <option value="active">Aktif</option>
     <option value="suspended">Askıda</option>
     <option value="all">Tümü</option>
    </select>
   </label>
  </div>

  {err&&!open&&<p style={{color:'#b91c1c'}}>{err}</p>}

  <T rows={filtered} cols={[
   {k:'full_name',l:'Ad Soyad',f:r=>(
    <div>
     <strong>{r.full_name}</strong>
     {!assignedIds.has(Number(r.id))&&r.is_active!==false&&(
      <div style={{fontSize:11,color:'#b91c1c',fontWeight:650}}>Atamasız</div>
     )}
    </div>
   )},
   ...(tab==='safety_specialist'?[{k:'certificate_class',l:'Sınıf',f:r=>r.certificate_class||'—'}]:[]),
   {k:'certificate_number',l:'Belge No',f:r=>r.certificate_number||'—'},
   {k:'certificate_date',l:'Belge Tarihi',f:r=>r.certificate_date||'—'},
   {k:'phone',l:'Telefon',f:r=>r.phone||'—'},
   {k:'email',l:'E-posta',f:r=>r.email||'—'},
   {k:'is_active',l:'Durum',f:r=><span className={'badge '+(r.is_active?'ok':'off')}>{r.is_active?'Aktif':'Askıda'}</span>},
   {k:'x',l:'İşlem',f:r=>(
    <div className="actions" style={{gap:6,flexWrap:'wrap'}}>
     <button type="button" className="mini" onClick={()=>openEdit(r)}>Düzenle</button>
     {['global_admin','company_admin'].includes(user.role)&&(
      <button type="button" className="mini" onClick={()=>goPerformance(r)}>Performans</button>
     )}
     {r.is_active
      ? <button type="button" className="mini" onClick={()=>suspend(r)}>Askıya Al</button>
      : <button type="button" className="mini" onClick={()=>activate(r)}>Aktifleştir</button>}
     <button type="button" className="mini" onClick={()=>remove(r)}>Sil</button>
    </div>
   )},
  ]}/>

  {open&&<M title={editRow?`Düzenle — ${editRow.full_name}`:`Yeni ${ptypes[form.professional_type||tab]||'Profesyonel'}`} close={()=>{setOpen(false);setEditRow(null)}}>
   <form className="form-grid" onSubmit={save}>
    <F label="Ad Soyad" required value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/>
    <S label="Meslek" value={form.professional_type} onChange={e=>{
     const ptype=e.target.value;
     setForm({
      ...form,
      professional_type:ptype,
      certificate_class:ptype==='safety_specialist'?(form.certificate_class||'A'):'',
     });
    }}>
     {Object.entries(ptypes).map(([k,v])=><option key={k} value={k}>{v}</option>)}
    </S>
    <F label="E-posta (kullanıcı adı)" type="email" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/>
    <F label="Telefon" value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/>
    {form.professional_type==='safety_specialist'&&(
     <S label="Belge Sınıfı (A / B / C)" required value={form.certificate_class} onChange={e=>setForm({...form,certificate_class:e.target.value})}>
      <option value="">Seçiniz</option>
      <option value="A">A</option>
      <option value="B">B</option>
      <option value="C">C</option>
     </S>
    )}
    <F label="Belge No" value={form.certificate_number} onChange={e=>setForm({...form,certificate_number:e.target.value})}/>
    <F label="Belge Tarihi" type="date" value={form.certificate_date} onChange={e=>setForm({...form,certificate_date:e.target.value})}/>
    {!editRow&&<p style={{gridColumn:'1/-1',margin:0,color:'#64748b',fontSize:13}}>Kayıtta e-posta kullanıcı adı ve geçici şifre otomatik oluşturulur.</p>}
    {err&&<p style={{color:'#b91c1c',gridColumn:'1/-1'}}>{err}</p>}
    <div className="form-actions"><button disabled={busy}>{busy?'Kaydediliyor...':(editRow?'Güncelle':'Kaydet')}</button></div>
   </form>
  </M>}
  {creds&&<M title="Profesyonel Giriş Bilgileri" close={()=>{setCreds(null);setCopyMsg('')}}>
   <div className="form-grid single">
    <p style={{marginTop:0,color:'#64748b'}}>Bu bilgileri profesyonelle güvenli kanaldan paylaşın. İlk girişten sonra Güvenlik → Şifre Değiştir ile güncelleyebilir.</p>
    <p style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap',marginBottom:0}}>
      <span><strong>Kullanıcı adı (e-posta):</strong> <code>{creds.email}</code></span>
      <button type="button" className="mini secondary" onClick={async()=>{const ok=await copyText(creds.email);setCopyMsg(ok?'E-posta kopyalandı.':'Kopyalanamadı.');}}>E-postayı kopyala</button>
    </p>
    <p><strong>Ad:</strong> {creds.full_name}</p>
    <p style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap',marginBottom:0}}>
      <span><strong>Geçici şifre:</strong> <code style={{userSelect:'all'}}>{creds.temporary_password}</code></span>
      <button type="button" className="mini" onClick={async()=>{const ok=await copyText(creds.temporary_password);setCopyMsg(ok?'Şifre kopyalandı.':'Kopyalanamadı.');}}>Şifreyi kopyala</button>
    </p>
    <div className="actions" style={{gap:8,flexWrap:'wrap'}}>
      <button type="button" className="secondary" onClick={async()=>{
        const text=`Kullanıcı adı: ${creds.email}\nGeçici şifre: ${creds.temporary_password}`;
        const ok=await copyText(text);
        setCopyMsg(ok?'E-posta ve şifre kopyalandı.':'Kopyalanamadı.');
      }}>E-posta + şifreyi kopyala</button>
    </div>
    {copyMsg&&<p style={{color:copyMsg.includes('amadı')?'#b91c1c':'#166534',margin:0}}>{copyMsg}</p>}
    <p style={{color:'#166534'}}>{creds.message}</p>
    <div className="form-actions"><button type="button" onClick={()=>{setCreds(null);setCopyMsg('')}}>Tamam</button></div>
   </div>
  </M>}
 </P>
}

export function AssignmentsPage({user}){
 const isGlobal=user.role==='global_admin';
 const[orgs,setOrgs]=useState([]),[companies,setCompanies]=useState([]),[pros,setPros]=useState([]),[rows,setRows]=useState([]);
 const[open,setOpen]=useState(false),[err,setErr]=useState(''),[busy,setBusy]=useState(false);
 const[statusFilter,setStatusFilter]=useState('active'); // active | suspended | ended | all
 const[contractFile,setContractFile]=useState(null);
 const[katipPrep,setKatipPrep]=useState(null);
 const[form,setForm]=useState({osgb_id:'',company_id:'',professional_id:'',professional_type:'safety_specialist',start_date:'',end_date:'',required_minutes_monthly:0,planned_minutes_monthly:0,actual_minutes_monthly:0,isg_katip_contract_number:''});
 const statusLabel={active:'Aktif',suspended:'Askıda',ended:'Sonlandı'};
 const loadKatipPrep=async(oid)=>{
  try{
   const q=oid?`?osgb_id=${oid}`:'';
   setKatipPrep(await api(`/osgb/katip-prep${q}`));
  }catch(_){setKatipPrep(null)}
 };
 const load=async(preferredOid)=>{
  setErr('');
  try{
   const[o,c]=await Promise.all([api('/osgb'),api('/companies')]);
   const id=preferredOid||osgbId(user,o);
   setOrgs(o);setCompanies(c);
   setForm(x=>({...x,osgb_id:id||x.osgb_id}));
   const oid=Number(preferredOid||id);
   if(oid){
    const[p,a]=await Promise.all([api(`/osgb/professionals?osgb_id=${oid}`),api('/osgb/assignments')]);
    setPros(p);setRows(a);
    await loadKatipPrep(oid);
   }else{
    setKatipPrep(null);
   }
  }catch(ex){setErr(ex.message||'Liste yüklenemedi.')}
 };
 useEffect(()=>{load()},[]);
 const companyOpts=companies.filter(x=>{
  const oid=Number(form.osgb_id);
  if(!oid) return true;
  return !x.osgb_id || Number(x.osgb_id)===oid;
 });
 const filtered=rows.filter(r=>{
  if(statusFilter==='all') return true;
  return (r.status||'active')===statusFilter;
 });
 function resetFormExtras(){
  setContractFile(null);
  setForm(f=>({...f,company_id:'',professional_id:'',start_date:'',end_date:'',required_minutes_monthly:0,planned_minutes_monthly:0,actual_minutes_monthly:0,isg_katip_contract_number:''}));
 }
 async function save(e){
  e.preventDefault();
  setErr('');setBusy(true);
  try{
   if(!form.osgb_id) throw new Error('OSGB seçiniz.');
   if(!form.company_id) throw new Error('İşyeri seçiniz.');
   if(!form.professional_id) throw new Error('Profesyonel seçiniz.');
   if(!form.start_date) throw new Error('Başlangıç tarihi zorunlu.');
   const katip=(form.isg_katip_contract_number||'').trim();
   if(!katip) throw new Error('İSG-KATİP sözleşme numarası zorunlu.');
   if(!contractFile) throw new Error('Sözleşme dosyası zorunlu (pdf/jpg/png).');
   const ext=(contractFile.name||'').split('.').pop()?.toLowerCase();
   if(!['pdf','jpg','jpeg','png'].includes(ext||'')) throw new Error('Sadece pdf, jpg veya png yükleyin.');
   const pro=pros.find(x=>x.id===Number(form.professional_id));
   const created=await api('/osgb/assignments',{method:'POST',body:JSON.stringify({
    osgb_id:Number(form.osgb_id),
    company_id:Number(form.company_id),
    professional_id:Number(form.professional_id),
    professional_type:pro?.professional_type||form.professional_type,
    start_date:form.start_date,
    end_date:form.end_date||null,
    required_minutes_monthly:Number(form.required_minutes_monthly)||0,
    planned_minutes_monthly:Number(form.planned_minutes_monthly)||0,
    actual_minutes_monthly:Number(form.actual_minutes_monthly)||0,
    isg_katip_contract_number:katip,
   })});
   await uploadFile(`/osgb/assignments/${created.id}/contract`,contractFile);
   setOpen(false);
   resetFormExtras();
   await load(form.osgb_id);
  }catch(ex){setErr(ex.message||'Kayıt başarısız.')}
  finally{setBusy(false)}
 }
 async function onOsgbChange(oid){
  setForm(f=>({...f,osgb_id:oid,company_id:'',professional_id:''}));
  await load(oid);
 }
 async function downloadContract(row){
  try{
   await downloadFile(`/osgb/assignments/${row.id}/contract`,row.contract_file_name||'sozlesme');
  }catch(ex){setErr(ex.message||'Sözleşme indirilemedi.')}
 }
 async function exportKatipCsv(){
  const oid=Number(form.osgb_id);
  if(!oid){setErr('CSV için OSGB seçiniz.');return}
  setBusy(true);setErr('');
  try{
   await downloadFile(`/osgb/katip-prep/export.csv?osgb_id=${oid}`,`katip-hazirlik-${oid}.csv`);
  }catch(ex){setErr(ex.message||'CSV indirilemedi.')}
  finally{setBusy(false)}
 }
 async function act(row,action){
  const labels={end:'sonlandırmak',suspend:'askıya almak',activate:'yeniden aktifleştirmek',delete:'silmek'};
  if(!window.confirm(`Bu görevlendirmeyi ${labels[action]||action} istiyor musunuz?`)) return;
  setBusy(true);setErr('');
  try{
   if(action==='delete'){
    const r=await api(`/osgb/assignments/${row.id}`,{method:'DELETE'});
    if(r.soft_ended) window.alert(r.message||'Görevlendirme sonlandırıldı.');
   }else{
    await api(`/osgb/assignments/${row.id}/${action}`,{method:'PATCH'});
   }
   await load(form.osgb_id);
  }catch(ex){setErr(ex.message||'İşlem başarısız.')}
  finally{setBusy(false)}
 }
 const prepSum=katipPrep?.summary;
 return <P title="İşyeri Görevlendirmeleri" action={<button onClick={()=>{setErr('');setContractFile(null);setOpen(true)}}><Plus/>Görevlendirme Yap</button>}>
  {err&&!open&&<p style={{color:'#b91c1c'}}>{err}</p>}
  {prepSum&&(
   <div style={{marginBottom:14,padding:'12px 14px',border:'1px solid #e2e8f0',borderRadius:8,background:'#f8fafc'}}>
    <div style={{display:'flex',justifyContent:'space-between',gap:12,flexWrap:'wrap',alignItems:'center',marginBottom:8}}>
     <div>
      <strong>KATİP hazırlık</strong>
      <span style={{marginLeft:8,color:'#64748b',fontSize:13}}>stub · gerçek API yok</span>
     </div>
     <button type="button" className="secondary" disabled={busy||!form.osgb_id} onClick={exportKatipCsv}>Eksikleri CSV indir</button>
    </div>
    <div style={{display:'flex',gap:16,flexWrap:'wrap',fontSize:14}}>
     <span>Aktif: <strong>{prepSum.active_assignments}</strong></span>
     <span>Tamam: <strong style={{color:'#166534'}}>{prepSum.complete}</strong></span>
     <span>Eksik toplam: <strong style={{color:prepSum.gaps?'#b45309':'#166534'}}>{prepSum.gaps}</strong></span>
     <span>KATİP no eksik: <strong>{prepSum.missing_katip_number}</strong></span>
     <span>Dosya eksik: <strong>{prepSum.missing_contract_file}</strong></span>
     <span>Hatırlatılacak: <strong>{katipPrep?.reminder_counts?.ready_to_remind??0}</strong></span>
    </div>
    {(katipPrep.gaps||[]).length>0&&(
     <div className="table-wrap" style={{marginTop:10}}>
      <table>
       <thead><tr>
        <th>İşyeri</th><th>Profesyonel</th><th>KATİP No</th><th>Dosya</th><th>Eksik</th>
       </tr></thead>
       <tbody>
        {katipPrep.gaps.slice(0,25).map(g=>(
         <tr key={g.assignment_id}>
          <td>{g.company_name}</td>
          <td>{g.professional_name}</td>
          <td>{g.isg_katip_contract_number||'—'}</td>
          <td>{g.contract_file_name||'—'}</td>
          <td>{g.reminder_hint}</td>
         </tr>
        ))}
       </tbody>
      </table>
      {katipPrep.gaps.length>25&&<p style={{margin:'8px 0 0',color:'#64748b',fontSize:13}}>İlk 25 kayıt gösteriliyor; tamamı için CSV indirin.</p>}
     </div>
    )}
   </div>
  )}
  <div style={{display:'flex',gap:10,flexWrap:'wrap',marginBottom:12,alignItems:'center'}}>
   <label className="field" style={{margin:0,minWidth:180}}>
    <span>Durum filtresi</span>
    <select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)} disabled={busy}>
     <option value="active">Aktif</option>
     <option value="suspended">Askıda</option>
     <option value="ended">Sonlandı</option>
     <option value="all">Tümü</option>
    </select>
   </label>
   <button type="button" className="secondary" disabled={busy} onClick={()=>load(form.osgb_id)}>Yenile</button>
  </div>
  <T rows={filtered} cols={[
   {k:'company_id',l:'İşyeri',f:r=>companies.find(x=>x.id===r.company_id)?.name||r.company_id},
   {k:'professional_id',l:'Profesyonel',f:r=>pros.find(x=>x.id===r.professional_id)?.full_name||r.professional_id},
   {k:'professional_type',l:'Görev',f:r=>ptypes[r.professional_type]},
   {k:'isg_katip_contract_number',l:'İSG-KATİP No'},
   {k:'contract_file_name',l:'Sözleşme',f:r=>r.contract_file_name?<button type="button" className="mini" onClick={()=>downloadContract(r)}>{r.contract_file_name}</button>:'—'},
   {k:'start_date',l:'Başlangıç'},
   {k:'end_date',l:'Bitiş',f:r=>r.end_date||'—'},
   {k:'required_minutes_monthly',l:'Zorunlu dk.'},
   {k:'status',l:'Durum',f:r=><span className={`badge ${r.status==='active'?'ok':'off'}`}>{statusLabel[r.status]||r.status}</span>},
   {k:'actions',l:'İşlem',f:r=>(
    <div className="actions" style={{gap:6,flexWrap:'wrap'}}>
     {r.status==='active'&&<>
      <button type="button" className="mini" disabled={busy} onClick={()=>act(r,'suspend')}>Askıya Al</button>
      <button type="button" className="mini" disabled={busy} onClick={()=>act(r,'end')}>Sonlandır</button>
     </>}
     {(r.status==='suspended'||r.status==='ended')&&(
      <button type="button" className="mini" disabled={busy} onClick={()=>act(r,'activate')}>Aktifleştir</button>
     )}
     <button type="button" className="mini" disabled={busy} onClick={()=>act(r,'delete')}>Sil</button>
    </div>
   )},
  ]}/>
  {open&&<M title="Yeni Görevlendirme" close={()=>setOpen(false)}>
   <form className="form-grid" onSubmit={save}>
    {isGlobal&&<S label="OSGB" required value={form.osgb_id} onChange={e=>onOsgbChange(e.target.value)}>
     <option value="">Seçiniz</option>
     {orgs.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}
    </S>}
    <S label="İşyeri" required value={form.company_id} onChange={e=>setForm({...form,company_id:e.target.value})}>
     <option value="">Seçiniz</option>
     {companyOpts.map(x=><option key={x.id} value={x.id}>{x.name}{!x.osgb_id?' (OSGB bağlanacak)':''}</option>)}
    </S>
    <S label="Profesyonel" required value={form.professional_id} onChange={e=>setForm({...form,professional_id:e.target.value})}>
     <option value="">Seçiniz</option>
     {pros.map(x=><option key={x.id} value={x.id}>{x.full_name} — {ptypes[x.professional_type]}</option>)}
    </S>
    <F label="Başlangıç" type="date" required value={form.start_date} onChange={e=>setForm({...form,start_date:e.target.value})}/>
    <F label="Bitiş" type="date" value={form.end_date} onChange={e=>setForm({...form,end_date:e.target.value})}/>
    <F label="Aylık Zorunlu Dakika" type="number" value={form.required_minutes_monthly} onChange={e=>setForm({...form,required_minutes_monthly:e.target.value})}/>
    <F label="Aylık Planlanan Dakika" type="number" value={form.planned_minutes_monthly} onChange={e=>setForm({...form,planned_minutes_monthly:e.target.value})}/>
    <F label="İSG-KATİP Sözleşme No" required value={form.isg_katip_contract_number} onChange={e=>setForm({...form,isg_katip_contract_number:e.target.value})}/>
    <label className="field" style={{gridColumn:'1/-1'}}>
     <span>Sözleşme Dosyası (pdf / jpg / png)</span>
     <input type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" required onChange={e=>setContractFile(e.target.files?.[0]||null)}/>
     {contractFile&&<small style={{color:'#475569'}}>{contractFile.name}</small>}
    </label>
    {err&&<p style={{color:'#b91c1c',gridColumn:'1/-1'}}>{err}</p>}
    <div className="form-actions"><button disabled={busy}>{busy?'Kaydediliyor...':'Kaydet'}</button></div>
   </form>
  </M>}
 </P>
}

export function VisitsPage({user}){
 const isField=['safety_specialist','workplace_physician','other_health_personnel'].includes(user.role);
 const isOsgb=['global_admin','company_admin'].includes(user.role);
 const canEdit=isField||isOsgb;
 const[orgs,setOrgs]=useState([]),[companies,setCompanies]=useState([]),[pros,setPros]=useState([]),[rows,setRows]=useState([]);
 const[cal,setCal]=useState(null),[month,setMonth]=useState(()=>new Date().toISOString().slice(0,7)),[selectedDay,setSelectedDay]=useState('');
 const[open,setOpen]=useState(false),[planOpen,setPlanOpen]=useState(false),[verifyOpen,setVerifyOpen]=useState(false),[verifyVisitId,setVerifyVisitId]=useState(null),[verifyCode,setVerifyCode]=useState(''),[signatureData,setSignatureData]=useState(null),[editing,setEditing]=useState(null),[err,setErr]=useState(''),[busy,setBusy]=useState(false);
 const[notebookFile,setNotebookFile]=useState(null);
 const[siteVerifyInput,setSiteVerifyInput]=useState('');
 const[offlineQueue,setOfflineQueue]=useState(()=>listOfflineCompletes());
 const refreshOffline=()=>setOfflineQueue(listOfflineCompletes());
 const emptyForm={osgb_id:'',company_id:'',visit_date:'',start_time:'09:00',end_time:'10:00',duration_minutes:60,subject:'Periyodik saha ziyareti',notes:''};
 const emptyPlan={osgb_id:'',company_id:'',professional_id:'',visit_date:'',start_time:'09:00',end_time:'10:00',duration_minutes:60,subject:'Planlı saha ziyareti',notes:''};
 const[form,setForm]=useState(emptyForm),[planForm,setPlanForm]=useState(emptyPlan);
 const weekday=['Pzt','Sal','Çar','Per','Cum','Cmt','Paz'];
 async function loadCalendar(oid){
  try{
   const q=`?month=${encodeURIComponent(month)}${oid?`&osgb_id=${oid}`:''}`;
   setCal(await api(`/operations/visits/calendar${q}`));
  }catch(_){setCal(null)}
 }
 const load=async(preferredOid)=>{
  setErr('');
  try{
   const[o,c]=await Promise.all([api('/osgb').catch(()=>[]),api('/companies')]);
   setOrgs(o);setCompanies(c);
   const id=preferredOid||osgbId(user,o)||(c.find(x=>x.osgb_id)?.osgb_id)||'';
   setForm(x=>({...x,osgb_id:id||x.osgb_id}));
   setPlanForm(x=>({...x,osgb_id:id||x.osgb_id}));
   if(isField){
    setRows(await api('/operations/visits'));
    await loadCalendar('');
    return;
   }
   const oid=Number(preferredOid||id);
   if(!oid){setRows([]);setCal(null);return}
   const[p,v]=await Promise.all([
    api(`/osgb/professionals?osgb_id=${oid}`).catch(()=>[]),
    api(`/operations/visits?osgb_id=${oid}`),
   ]);
   setPros(p);setRows(v);
   await loadCalendar(oid);
  }catch(ex){setErr(ex.message||'Liste yüklenemedi.');setRows([])}
 };
 useEffect(()=>{load()},[]);
 useEffect(()=>{if(form.osgb_id||isField) loadCalendar(isField?'':Number(form.osgb_id)||'')},[month]);
 function shiftMonth(delta){
  const [y,m]=month.split('-').map(Number);
  const d=new Date(y,m-1+delta,1);
  setMonth(`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`);
  setSelectedDay('');
 }
 function openCreate(){
  setErr('');setNotebookFile(null);setSiteVerifyInput('');setEditing(null);
  setForm(f=>({...emptyForm,osgb_id:f.osgb_id||osgbId(user,orgs)||''}));
  setOpen(true);
 }
 function openPlan(){
  setErr('');
  setPlanForm(f=>({...emptyPlan,osgb_id:f.osgb_id||osgbId(user,orgs)||'',visit_date:selectedDay||''}));
  setPlanOpen(true);
 }
 function openEdit(row){
  setErr('');setNotebookFile(null);setEditing(row);
  setForm({
   osgb_id:row.osgb_id||'',
   company_id:String(row.company_id||''),
   visit_date:row.visit_date||'',
   start_time:row.start_time||'09:00',
   end_time:row.end_time||'10:00',
   duration_minutes:row.duration_minutes??60,
   subject:row.subject||'',
   notes:row.notes||'',
  });
  setOpen(true);
 }
 async function save(e){
  e.preventDefault();
  setErr('');setBusy(true);
  try{
   if(!canEdit) throw new Error('Bu işlem için yetkiniz yok.');
   if(isOsgb&&!editing) throw new Error('Yeni ziyaret kaydı yalnızca uzman / hekim / DSP tarafından yapılır.');
   if(!form.company_id) throw new Error('İşyeri seçiniz.');
   if(!form.visit_date) throw new Error('Tarih zorunlu.');
   if(!editing&&!notebookFile) throw new Error('Tespit öneri defteri dosyası zorunlu (pdf/jpg/png).');
   if(isField&&!editing&&!parseSiteInput(siteVerifyInput)) throw new Error('İşyeri QR kodu zorunlu.');
   if(notebookFile){
    const ext=(notebookFile.name||'').split('.').pop()?.toLowerCase();
    if(!['pdf','jpg','jpeg','png'].includes(ext||'')) throw new Error('Sadece pdf, jpg veya png yükleyin.');
   }
   const company=companies.find(x=>x.id===Number(form.company_id));
   const oid=Number(company?.osgb_id||form.osgb_id||user.osgb_id||0);
   if(!oid) throw new Error('İşyerinin OSGB bağlantısı yok. Önce işyerini OSGB’ye bağlayın.');
   const body={
    company_id:Number(form.company_id),
    visit_date:form.visit_date,
    start_time:form.start_time||null,
    end_time:form.end_time||null,
    duration_minutes:Number(form.duration_minutes)||0,
    subject:form.subject,
    notes:form.notes||null,
   };
   let visitId=editing?.id;
   if(editing){
    await api(`/operations/visits/${editing.id}`,{method:'PATCH',body:JSON.stringify(body)});
   }else{
    const created=await api('/operations/visits',{method:'POST',body:JSON.stringify({...body,osgb_id:oid})});
    visitId=created.id;
   }
   if(notebookFile&&visitId){
    const gps=isField?await captureGps():null;
    const extra={...(gps||{})};
    if(isField&&siteVerifyInput) extra.site_verify_code=parseSiteInput(siteVerifyInput);
    await uploadFile(`/operations/visits/${visitId}/notebook`,notebookFile,Object.keys(extra).length?extra:undefined);
   }
   setOpen(false);setEditing(null);setNotebookFile(null);setSiteVerifyInput('');
   setForm(f=>({...emptyForm,osgb_id:f.osgb_id||oid||''}));
   await load();
  }catch(ex){setErr(ex.message||'Kayıt başarısız.')}
  finally{setBusy(false)}
 }
 async function remove(row){
  if(!canEdit) return;
  if(!window.confirm(`Bu saha ziyaretini silmek istiyor musunuz?\n${row.visit_date||''} — ${row.subject||''}`)) return;
  setErr('');
  try{
   await api(`/operations/visits/${row.id}`,{method:'DELETE'});
   if(editing?.id===row.id){setOpen(false);setEditing(null)}
   await load();
  }catch(ex){setErr(ex.message||'Silinemedi.')}
 }
 async function done(id){
  setVerifyVisitId(id);setVerifyCode('');setSignatureData(null);setVerifyOpen(true);setErr('');
 }
 async function confirmComplete(e){
  e?.preventDefault?.();
  if(!verifyVisitId) return;
  setErr('');setBusy(true);
  try{
   const code=parseSiteInput(verifyCode);
   if(!code) throw new Error('İşyeri QR kodunu okutun veya kodu girin.');
   if(!signatureData) throw new Error('Saha imzası zorunlu.');
   const gps=await captureGps();
   const payload={...(gps||{}),site_verify_code:code,signature_data_url:signatureData};
   try{
    await api(`/operations/visits/${verifyVisitId}/complete`,{method:'PATCH',body:JSON.stringify(payload)});
   }catch(ex){
    const msg=String(ex.message||'');
    if(/bağlan|network|fetch|sunucu/i.test(msg) || ex instanceof TypeError){
     enqueueOfflineComplete({visit_id:verifyVisitId,...payload});
     refreshOffline();
     setVerifyOpen(false);setVerifyVisitId(null);setVerifyCode('');setSignatureData(null);
     setErr('Çevrimdışı: tamamlama kuyruğa alındı. Bağlantı gelince senkronlayın.');
     return;
    }
    throw ex;
   }
   setVerifyOpen(false);setVerifyVisitId(null);setVerifyCode('');setSignatureData(null);
   await load();
  }catch(ex){setErr(ex.message||'Tamamlanamadı.')}
  finally{setBusy(false)}
 }
 async function syncOffline(){
  setBusy(true);setErr('');
  try{
   const results=await flushOfflineCompletes(api);
   refreshOffline();
   const fail=results.filter(r=>!r.ok);
   if(fail.length) setErr(`Senkron: ${results.length-fail.length} başarılı, ${fail.length} bekliyor.`);
   await load();
  }catch(ex){setErr(ex.message||'Senkron başarısız.')}
  finally{setBusy(false)}
 }
 async function downloadNotebook(row){
  try{await downloadFile(`/operations/visits/${row.id}/notebook`,row.notebook_file_name||'tespit-oneri-defteri')}
  catch(ex){setErr(ex.message||'Dosya indirilemedi.')}
 }
 async function savePlan(e){
  e.preventDefault();setErr('');setBusy(true);
  try{
   const oid=Number(planForm.osgb_id||form.osgb_id||user.osgb_id||0);
   if(!planForm.company_id||!planForm.professional_id||!planForm.visit_date) throw new Error('İşyeri, profesyonel ve tarih zorunlu.');
   await api('/operations/visits/plan',{method:'POST',body:JSON.stringify({
    osgb_id:oid,
    company_id:Number(planForm.company_id),
    professional_id:Number(planForm.professional_id),
    visit_date:planForm.visit_date,
    start_time:planForm.start_time||null,
    end_time:planForm.end_time||null,
    duration_minutes:Number(planForm.duration_minutes)||60,
    subject:planForm.subject,
    notes:planForm.notes||null,
   })});
   setPlanOpen(false);await load(form.osgb_id);
  }catch(ex){setErr(ex.message||'Plan kaydedilemedi.')}
  finally{setBusy(false)}
 }
 const filteredRows=selectedDay?rows.filter(r=>r.visit_date===selectedDay):rows;
 const calDays=cal?.days||[];
 const padStart=calDays.length?((calDays[0].weekday+6)%7):0;
 const todayIso=new Date().toISOString().slice(0,10);
 const fieldQueue=isField?rows.filter(r=>r.status!=='completed').sort((a,b)=>String(a.visit_date).localeCompare(String(b.visit_date))):[];
 const overdueQueue=fieldQueue.filter(r=>r.visit_date&&r.visit_date<todayIso);
 const todayQueue=fieldQueue.filter(r=>r.visit_date===todayIso);
 const upcomingQueue=fieldQueue.filter(r=>r.visit_date&&r.visit_date>todayIso).slice(0,6);
 return <P title={isOsgb?'Saha Ziyaretleri (OSGB İzleme)':'Saha Ziyaret Takvimi'} action={<div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
  {isOsgb&&<button type="button" onClick={openPlan}><Plus/>Planlı Ziyaret</button>}
  {isField&&<button onClick={openCreate}><Plus/>Ziyaret Kaydet</button>}
 </div>}>
  {isField&&(
   <section className="panel field-portal" style={{marginBottom:12}}>
    <div style={{display:'flex',justifyContent:'space-between',gap:10,flexWrap:'wrap',alignItems:'flex-start',marginBottom:10}}>
     <div>
      <h3 style={{margin:'0 0 4px',fontSize:16}}>Saha portalı</h3>
      <p style={{margin:0,color:'#64748b',fontSize:13}}>Planlı ziyaretleri buradan tamamlayın. QR + GPS + imza damgası alınır.</p>
     </div>
     <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
      {offlineQueue.length>0&&<button type="button" className="mini secondary" disabled={busy} onClick={syncOffline}>Senkron ({offlineQueue.length})</button>}
      <button type="button" className="mini" disabled={busy} onClick={openCreate}>+ Hızlı kayıt</button>
     </div>
    </div>
    {offlineQueue.length>0&&(
     <div style={{marginBottom:10,padding:'10px 12px',borderRadius:10,background:'#fff7ed',color:'#9a3412',fontSize:13}}>
      {offlineQueue.length} çevrimdışı tamamlama bekliyor.
      <button type="button" className="mini" style={{marginLeft:8}} disabled={busy} onClick={syncOffline}>Şimdi gönder</button>
      <button type="button" className="mini secondary" style={{marginLeft:6}} onClick={()=>{offlineQueue.forEach(x=>removeOfflineItem(x.id));refreshOffline()}}>Temizle</button>
     </div>
    )}
    <div className="cards osgb-cards" style={{marginBottom:10}}>
     <article className="metric"><span>Gecikmiş</span><strong style={{color:overdueQueue.length?'#b91c1c':undefined}}>{overdueQueue.length}</strong></article>
     <article className="metric"><span>Bugün</span><strong>{todayQueue.length}</strong></article>
     <article className="metric"><span>Yaklaşan</span><strong>{upcomingQueue.length}</strong></article>
     <article className="metric"><span>Açık iş</span><strong>{fieldQueue.length}</strong></article>
    </div>
    {fieldQueue.length===0?(
     <p style={{margin:0,color:'#64748b',fontSize:14}}>Açık planlı ziyaret yok. Yeni saha kaydı için “Ziyaret Kaydet” kullanın.</p>
    ):(
     <div className="field-queue">
      {[...overdueQueue,...todayQueue,...upcomingQueue].map(r=>{
       const name=companies.find(x=>x.id===r.company_id)?.name||`İşyeri #${r.company_id}`;
       const late=r.visit_date&&r.visit_date<todayIso;
       return (
        <article key={r.id} className="field-card" style={{borderLeft:late?'4px solid #b91c1c':'4px solid #0f766e'}}>
         <div>
          <strong style={{display:'block',fontSize:15}}>{name}</strong>
          <span style={{color:'#64748b',fontSize:13}}>{r.visit_date} · {r.subject||'Ziyaret'}{late?' · Gecikmiş':''}</span>
         </div>
         <div className="actions" style={{flexWrap:'wrap'}}>
          <button type="button" className="mini secondary" onClick={()=>openEdit(r)}>Düzenle</button>
          <button type="button" className="mini" disabled={busy} onClick={()=>done(r.id)}>{busy?'…':'QR + GPS + İmza'}</button>
         </div>
        </article>
       );
      })}
     </div>
    )}
   </section>
  )}
  {isOsgb&&<p style={{margin:'0 0 12px',color:'#475569',fontSize:14}}>Takvimde planlı ziyaretleri izleyin; gecikmiş ve eksik süre uyarılarını kapatın. Saha kaydı uzman/hekim/DSP tarafından defter ile yapılır.</p>}
  {user.role==='global_admin'&&orgs.length>1&&(
   <label className="field" style={{maxWidth:320,marginBottom:12}}>
    <span>OSGB</span>
    <select value={form.osgb_id} onChange={e=>load(e.target.value)}>
     {orgs.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}
    </select>
   </label>
  )}
  {err&&!open&&!planOpen&&<p style={{color:'#b91c1c'}}>{err}</p>}
  {cal&&<>
   <div className="cards osgb-cards" style={{marginBottom:12}}>
    <article className="metric"><span>Toplam ziyaret</span><strong>{cal.summary?.total_visits??0}</strong></article>
    <article className="metric"><span>Planlı</span><strong>{cal.summary?.planned??0}</strong></article>
    <article className="metric"><span>Tamamlanan</span><strong>{cal.summary?.completed??0}</strong></article>
    <article className="metric"><span>Gecikmiş</span><strong style={{color:(cal.summary?.overdue||0)?'#b91c1c':undefined}}>{cal.summary?.overdue??0}</strong></article>
    <article className="metric"><span>Eksik süre (işyeri)</span><strong style={{color:(cal.summary?.missing_coverage||0)?'#b45309':undefined}}>{cal.summary?.missing_coverage??0}</strong></article>
   </div>
   {(cal.alerts||[]).length>0&&<section className="panel" style={{marginBottom:12,borderLeft:'4px solid #d97706'}}>
    <ul style={{margin:0,paddingLeft:20,color:'#475569',fontSize:14}}>{cal.alerts.map((a,i)=><li key={i}>{a.text}</li>)}</ul>
   </section>}
   <section className="panel" style={{marginBottom:12}}>
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:8,flexWrap:'wrap',marginBottom:12}}>
     <h3 style={{margin:0,fontSize:16}}>{cal.period} — Saha Takvimi</h3>
     <div style={{display:'flex',gap:8}}>
      <button type="button" className="mini secondary" onClick={()=>shiftMonth(-1)}>← Önceki</button>
      <button type="button" className="mini secondary" onClick={()=>{setMonth(new Date().toISOString().slice(0,7));setSelectedDay('')}}>Bugün</button>
      <button type="button" className="mini secondary" onClick={()=>shiftMonth(1)}>Sonraki →</button>
      {selectedDay&&<button type="button" className="mini" onClick={()=>setSelectedDay('')}>Tümünü göster</button>}
     </div>
    </div>
    <div style={{display:'grid',gridTemplateColumns:'repeat(7,1fr)',gap:6,marginBottom:6,fontSize:11,color:'#64748b',fontWeight:700}}>
     {weekday.map(w=><div key={w} style={{textAlign:'center'}}>{w}</div>)}
    </div>
    <div style={{display:'grid',gridTemplateColumns:'repeat(7,1fr)',gap:6}}>
     {Array.from({length:padStart}).map((_,i)=><div key={`p${i}`}/>)}
     {calDays.map(day=>{
      const active=selectedDay===day.date;
      const hasOverdue=day.visits?.some(v=>v.status==='planned'&&day.date<new Date().toISOString().slice(0,10));
      return <button key={day.date} type="button" onClick={()=>setSelectedDay(active?'':day.date)} style={{
        minHeight:72,padding:6,borderRadius:8,border:active?'2px solid #0f766e':'1px solid #e2e8f0',
        background:day.is_today?'#ecfdf5':(active?'#f0fdfa':'#fff'),cursor:'pointer',textAlign:'left'
      }}>
        <div style={{fontSize:12,fontWeight:700,color:hasOverdue?'#b91c1c':'#334155'}}>{day.date.slice(8)}</div>
        {day.visit_count>0&&<div style={{fontSize:11,color:'#0f766e',marginTop:4}}>{day.visit_count} ziyaret</div>}
        {day.planned_count>0&&<div style={{fontSize:10,color:'#64748b'}}>{day.planned_count} planlı</div>}
      </button>
     })}
    </div>
   </section>
   {(cal.missing||[]).length>0&&<section className="panel" style={{marginBottom:12}}>
    <h3 style={{margin:'0 0 8px',fontSize:15}}>Eksik saha süresi — plan önerisi</h3>
    <T rows={cal.missing.slice(0,8)} cols={[
     {k:'company_name',l:'İşyeri'},
     {k:'professional_name',l:'Profesyonel'},
     {k:'gap_minutes',l:'Eksik dk'},
     {k:'has_future_plan',l:'Plan',f:r=>r.has_future_plan?'Var':'Yok'},
    ]}/>
   </section>}
  </>}
  <T rows={filteredRows} cols={[
   {k:'visit_date',l:'Tarih'},
   {k:'company_id',l:'İşyeri',f:r=>companies.find(x=>x.id===r.company_id)?.name||r.company_id},
   ...(!isField?[{k:'professional_id',l:'Profesyonel',f:r=>pros.find(x=>x.id===r.professional_id)?.full_name||r.professional_id}]:[]),
   {k:'subject',l:'Konu'},
   {k:'notebook_file_name',l:'Tespit Defteri',f:r=>r.notebook_file_name?<button type="button" className="mini" onClick={()=>downloadNotebook(r)}>{r.notebook_file_name}</button>:'—'},
   {k:'duration_minutes',l:'Süre (dk.)'},
   {k:'status',l:'Durum'},
   {k:'gps',l:'GPS',f:r=>fmtGps(r)},
   {k:'site',l:'QR',f:r=>r.site_verified_at?'✓':'—'},
   {k:'sig',l:'İmza',f:r=>r.signature_captured_at?'✓':'—'},
   ...(canEdit?[{k:'x',l:'İşlem',f:r=>(
    <div className="actions" style={{flexWrap:'wrap'}}>
     <button type="button" className="mini" onClick={()=>openEdit(r)}>Düzenle</button>
     <button type="button" className="mini" onClick={()=>remove(r)}>Sil</button>
     {isField&&r.status!=='completed'&&<button type="button" className="mini" disabled={busy} onClick={()=>done(r.id)}>QR + GPS + İmza</button>}
    </div>
   )}]:[])
  ]}/>
  {verifyOpen&&isField&&<M title="Saha doğrulama ve imza" close={()=>{setVerifyOpen(false);setVerifyVisitId(null);setVerifyCode('');setSignatureData(null);setErr('')}}>
   <form className="form-grid single" onSubmit={confirmComplete}>
    <p style={{margin:0,color:'#64748b',fontSize:14}}>QR kodu girin, imzalayın. GPS otomatik alınır. Çevrimdışıysa kuyruğa düşer.</p>
    <F label="QR / doğrulama kodu" required value={verifyCode} onChange={e=>setVerifyCode(e.target.value)} placeholder="ISGSUITE:WP:… veya kod"/>
    <SignaturePad onChange={setSignatureData}/>
    {err&&<p style={{color:'#b91c1c',margin:0}}>{err}</p>}
    <div className="form-actions"><button disabled={busy}>{busy?'Tamamlanıyor…':'Doğrula ve Tamamla'}</button></div>
   </form>
  </M>}
  {open&&canEdit&&(isField||editing)&&<M title={editing?'Saha Ziyaretini Düzenle':'Yeni Saha Ziyareti'} close={()=>{setOpen(false);setEditing(null);setErr('')}}>
   <form className="form-grid" onSubmit={save}>
    <S label="İşyeri" required value={form.company_id} onChange={e=>setForm({...form,company_id:e.target.value})} disabled={isOsgb&&!!editing}>
     <option value="">Seçiniz</option>
     {companies.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}
    </S>
    <F label="Tarih" type="date" required value={form.visit_date} onChange={e=>setForm({...form,visit_date:e.target.value})}/>
    <F label="Başlangıç" type="time" value={form.start_time} onChange={e=>setForm({...form,start_time:e.target.value})}/>
    <F label="Bitiş" type="time" value={form.end_time} onChange={e=>setForm({...form,end_time:e.target.value})}/>
    <F label="Süre (dk.)" type="number" value={form.duration_minutes} onChange={e=>setForm({...form,duration_minutes:e.target.value})}/>
    <F label="Ziyaret Konusu" required value={form.subject} onChange={e=>setForm({...form,subject:e.target.value})}/>
    <F label="Notlar" value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/>
    <label className="field" style={{gridColumn:'1/-1'}}>
     <span>{editing?'Tespit Öneri Defteri (opsiyonel — yeni dosya seçerseniz değişir)':'Tespit Öneri Defteri (pdf / jpg / png)'}</span>
     <input type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" required={!editing} onChange={e=>setNotebookFile(e.target.files?.[0]||null)}/>
     {notebookFile&&<small style={{color:'#475569'}}>{notebookFile.name}</small>}
     {!notebookFile&&editing?.notebook_file_name&&<small style={{color:'#475569'}}>Mevcut: {editing.notebook_file_name}</small>}
     {isField&&<small style={{display:'block',marginTop:6,color:'#0f766e'}}>Defter yüklenince konum (GPS) ve QR doğrulama kaydedilir.</small>}
    </label>
    {isField&&!editing&&<F label="İşyeri QR kodu" required value={siteVerifyInput} onChange={e=>setSiteVerifyInput(e.target.value)} placeholder="QR okutun veya kodu yapıştırın"/>}
    {err&&<p style={{color:'#b91c1c',gridColumn:'1/-1'}}>{err}</p>}
    <div className="form-actions"><button disabled={busy}>{busy?'Kaydediliyor...':(editing?'Güncelle':'Kaydet')}</button></div>
   </form>
  </M>}
  {planOpen&&<M title="Planlı Saha Ziyareti" close={()=>setPlanOpen(false)}>
   <form className="form-grid" onSubmit={savePlan}>
    <S label="İşyeri" required value={planForm.company_id} onChange={e=>setPlanForm({...planForm,company_id:e.target.value})}>
     <option value="">Seçiniz</option>
     {companies.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}
    </S>
    <S label="Profesyonel" required value={planForm.professional_id} onChange={e=>setPlanForm({...planForm,professional_id:e.target.value})}>
     <option value="">Seçiniz</option>
     {pros.map(x=><option key={x.id} value={x.id}>{x.full_name}</option>)}
    </S>
    <F label="Tarih" type="date" required value={planForm.visit_date} onChange={e=>setPlanForm({...planForm,visit_date:e.target.value})}/>
    <F label="Başlangıç" type="time" value={planForm.start_time} onChange={e=>setPlanForm({...planForm,start_time:e.target.value})}/>
    <F label="Bitiş" type="time" value={planForm.end_time} onChange={e=>setPlanForm({...planForm,end_time:e.target.value})}/>
    <F label="Süre (dk.)" type="number" value={planForm.duration_minutes} onChange={e=>setPlanForm({...planForm,duration_minutes:e.target.value})}/>
    <F label="Konu" required value={planForm.subject} onChange={e=>setPlanForm({...planForm,subject:e.target.value})}/>
    <F label="Notlar" value={planForm.notes} onChange={e=>setPlanForm({...planForm,notes:e.target.value})}/>
    {err&&<p style={{color:'#b91c1c',gridColumn:'1/-1'}}>{err}</p>}
    <div className="form-actions"><button disabled={busy}>{busy?'Kaydediliyor...':'Planla'}</button></div>
   </form>
  </M>}
 </P>
}

export function CrmPage({user,onNavigate}){
 const[orgs,setOrgs]=useState([]),[rows,setRows]=useState([]),[open,setOpen]=useState(false),[busyId,setBusyId]=useState(null);
 const[stageFilter,setStageFilter]=useState('open'); // open | won | lost | all
 const[form,setForm]=useState({osgb_id:'',company_name:'',contact_name:'',phone:'',email:'',employee_count:0,hazard_class:'Tehlikeli',stage:'new',estimated_monthly_value:0,next_action_date:'',notes:''});
 const load=async()=>{const o=await api('/osgb');const id=osgbId(user,o);setOrgs(o);setForm(x=>({...x,osgb_id:id}));if(id)setRows(await api(`/operations/leads?osgb_id=${id}`))};useEffect(()=>{load()},[]);
 async function save(e){e.preventDefault();await api('/operations/leads',{method:'POST',body:JSON.stringify({...form,osgb_id:Number(form.osgb_id),employee_count:Number(form.employee_count),estimated_monthly_value:Number(form.estimated_monthly_value),next_action_date:form.next_action_date||null})});setOpen(false);load()}
 async function changeStage(row,stage){
  if(stage===row.stage) return;
  setBusyId(row.id);
  try{
   await api(`/operations/leads/${row.id}`,{method:'PATCH',body:JSON.stringify({stage})});
   await load();
  }catch(ex){alert(ex.message||'Aşama güncellenemedi.')}
  finally{setBusyId(null)}
 }
 async function convertLead(row){
  if(row.stage==='lost'){alert('Kaybedilmiş fırsat sözleşmeye dönüştürülemez.');return}
  if(row.stage==='won'){alert('Bu fırsat zaten kazanıldı. Yeniden dönüştürme idempotent çalışır.');}
  if(!window.confirm(`${row.company_name} için sözleşme oluşturulsun mu?\nTeklif tutarı: ${money(row.estimated_monthly_value)}`)) return;
  setBusyId(row.id);
  try{
   const res=await api(`/operations/leads/${row.id}/convert-to-contract`,{method:'POST',body:'{}'});
   const msg=res.already_converted
    ? `Zaten dönüştürülmüş: sözleşme ${res.contract?.contract_number||('CRM-'+row.id)}`
    : `Sözleşme oluşturuldu: ${res.contract?.contract_number||('CRM-'+row.id)}${res.finance_id?` · ilk ay tahakkuk #${res.finance_id}`:''}`;
   alert(msg);
   await load();
   const cid=res.contract?.company_id;
   if(cid && typeof onNavigate==='function' && window.confirm('Finans kaydına gitmek ister misiniz? (işyeri filtresi uygulanır)')){
    try{sessionStorage.setItem('isg_finance_company_id',String(cid))}catch(_){ /* ignore */ }
    onNavigate('finance');
   }
  }catch(ex){alert(ex.message||'Dönüştürme başarısız.')}
  finally{setBusyId(null)}
 }
 const filteredRows=rows.filter(r=>{
  if(stageFilter==='open') return r.stage!=='won'&&r.stage!=='lost';
  if(stageFilter==='won') return r.stage==='won';
  if(stageFilter==='lost') return r.stage==='lost';
  return true;
 });
 const stageCounts={open:rows.filter(r=>r.stage!=='won'&&r.stage!=='lost').length,won:rows.filter(r=>r.stage==='won').length,lost:rows.filter(r=>r.stage==='lost').length,all:rows.length};
 return <P title="CRM ve Teklif Fırsatları" action={<button onClick={()=>setOpen(true)}><Plus/>Fırsat Ekle</button>}>
  <div className="finance-summary" style={{marginBottom:12}}>
   <b style={{cursor:'pointer'}} onClick={()=>setStageFilter('open')}>Acik: {stageCounts.open}</b>
   <b style={{cursor:'pointer'}} onClick={()=>setStageFilter('won')}>Kazanildi: {stageCounts.won}</b>
   <b style={{cursor:'pointer'}} onClick={()=>setStageFilter('lost')}>Kaybedildi: {stageCounts.lost}</b>
   <b style={{cursor:'pointer'}} onClick={()=>setStageFilter('all')}>Tumu: {stageCounts.all}</b>
  </div>
  <T rows={filteredRows} cols={[
   {k:'company_name',l:'Firma'},
   {k:'contact_name',l:'Yetkili'},
   {k:'employee_count',l:'Çalışan'},
   {k:'stage',l:'Aşama',f:r=>(
    <select className="mini-select" disabled={busyId===r.id||r.stage==='won'} value={r.stage} onChange={e=>changeStage(r,e.target.value)}>
     {Object.entries(stages).map(([k,v])=><option key={k} value={k}>{v}</option>)}
    </select>
   )},
   {k:'estimated_monthly_value',l:'Teklif tutarı (aylık)',f:r=>money(r.estimated_monthly_value)},
   {k:'next_action_date',l:'Sonraki İşlem'},
   {k:'x',l:'İşlem',f:r=>(
    <div className="actions" style={{gap:6,flexWrap:'wrap'}}>
     <button type="button" className="mini" disabled={busyId===r.id||r.stage==='lost'} onClick={()=>convertLead(r)}>
      {r.stage==='won'?'Sözleşme (tekrar)':'Sözleşme oluştur'}
     </button>
    </div>
   )},
  ]}/>
  {open&&<M title="Yeni Satış Fırsatı" close={()=>setOpen(false)}><form className="form-grid" onSubmit={save}>
   <F label="Firma" required value={form.company_name} onChange={e=>setForm({...form,company_name:e.target.value})}/>
   <F label="Yetkili" value={form.contact_name} onChange={e=>setForm({...form,contact_name:e.target.value})}/>
   <F label="Telefon" value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/>
   <F label="E-posta" type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/>
   <F label="Çalışan Sayısı" type="number" value={form.employee_count} onChange={e=>setForm({...form,employee_count:e.target.value})}/>
   <S label="Aşama" value={form.stage} onChange={e=>setForm({...form,stage:e.target.value})}>{Object.entries(stages).map(([k,v])=><option key={k} value={k}>{v}</option>)}</S>
   <F label="Teklif tutarı (aylık)" type="number" value={form.estimated_monthly_value} onChange={e=>setForm({...form,estimated_monthly_value:e.target.value})}/>
   <F label="Sonraki İşlem" type="date" value={form.next_action_date} onChange={e=>setForm({...form,next_action_date:e.target.value})}/>
   <div className="form-actions"><button>Kaydet</button></div>
  </form></M>}
 </P>
}

export function ContractsPage({user}){
 const[orgs,setOrgs]=useState([]),[companies,setCompanies]=useState([]),[rows,setRows]=useState([]),[open,setOpen]=useState(false),[busyId,setBusyId]=useState(null);
 const[filter,setFilter]=useState('all'); // all | active | expiring | expired | suspended
 const[form,setForm]=useState({osgb_id:'',company_id:'',contract_number:'',start_date:'',end_date:'',monthly_fee:0});
 const today=()=>new Date().toISOString().slice(0,10);
 const daysLeft=(end)=>{
  if(!end) return null;
  const a=new Date(today()+'T00:00:00');
  const b=new Date(String(end).slice(0,10)+'T00:00:00');
  return Math.round((b-a)/86400000);
 };
 const load=async()=>{
  const[o,c]=await Promise.all([api('/osgb'),api('/companies')]);
  const id=osgbId(user,o);
  setOrgs(o);setCompanies(c);
  setForm(x=>({...x,osgb_id:id,start_date:x.start_date||today()}));
  if(id) setRows(await api('/osgb/contracts'));
 };
 useEffect(()=>{load()},[]);
 async function save(e){
  e.preventDefault();
  await api('/osgb/contracts',{method:'POST',body:JSON.stringify({
   osgb_id:Number(form.osgb_id),
   company_id:Number(form.company_id),
   contract_number:form.contract_number.trim(),
   start_date:form.start_date,
   end_date:form.end_date||null,
   monthly_fee:form.monthly_fee===''||form.monthly_fee==null?null:Number(form.monthly_fee),
  })});
  setOpen(false);
  setForm(x=>({...x,company_id:'',contract_number:'',end_date:'',monthly_fee:0,start_date:today()}));
  load();
 }
 async function act(row,action){
  const labels={end:'sonlandırmak',suspend:'askıya almak',activate:'yeniden aktifleştirmek'};
  if(!window.confirm(`Bu sözleşmeyi ${labels[action]||action} istiyor musunuz?`)) return;
  setBusyId(row.id);
  try{
   await api(`/osgb/contracts/${row.id}/${action}`,{method:'PATCH'});
   await load();
  }catch(ex){alert(ex.message||'İşlem başarısız.')}
  finally{setBusyId(null)}
 }
 const statusLabel={active:'Aktif',ended:'Sona erdi',suspended:'Askıda',cancelled:'İptal'};
 const enriched=rows.map(r=>{
  const d=daysLeft(r.end_date);
  return {...r,_days:d,_expiring:r.status==='active'&&d!=null&&d>=0&&d<=30,_expired:d!=null&&d<0};
 });
 const activeCount=enriched.filter(r=>r.status==='active').length;
 const expiringCount=enriched.filter(r=>r._expiring).length;
 const expiredCount=enriched.filter(r=>r._expired||r.status==='ended').length;
 const suspendedCount=enriched.filter(r=>r.status==='suspended').length;
 const mrr=enriched.filter(r=>r.status==='active').reduce((a,b)=>a+(Number(b.monthly_fee)||0),0);
 const filtered=enriched.filter(r=>{
  if(filter==='active') return r.status==='active';
  if(filter==='expiring') return r._expiring;
  if(filter==='expired') return r._expired||r.status==='ended';
  if(filter==='suspended') return r.status==='suspended';
  return true;
 });
 const statusBadge=(r)=>{
  if(r._expired||r.status==='ended') return 'badge-danger';
  if(r.status==='suspended') return 'badge-muted';
  if(r._expiring) return 'badge-warn';
  if(r.status==='active') return 'badge-ok';
  return 'badge-muted';
 };
 
 async function accrueMonth(){
  if(!form.osgb_id){alert('OSGB secili degil.');return}
  if(!window.confirm('Aktif sozlesmeler icin bu ay tahakkuklari olusturulsun mu?\n(Zaten olusmus olanlar atlanir.)')) return;
  setBusyId('accrue');
  try{
   const res=await api(`/operations/finance/accrue-month?osgb_id=${form.osgb_id}`,{method:'POST',body:'{}'});
   alert(`Tahakkuk: ${res.created_count||0} yeni / ${res.skipped_count||0} atlandi (${res.month||''})`);
   await load();
  }catch(ex){alert(ex.message||'Tahakkuk olusturulamadi.')}
  finally{setBusyId(null)}
 }
return <P title="Hizmet Sözleşmeleri" action={<div className="actions" style={{gap:8}}><button type="button" className="secondary" disabled={busyId==='accrue'} onClick={accrueMonth}>Bu ay tahakkuk</button><button onClick={()=>setOpen(true)}><Plus/>Sözleşme Ekle</button></div>}>
  <div className="finance-summary" style={{marginBottom:12}}>
   <b style={{cursor:'pointer'}} onClick={()=>setFilter('active')}>Aktif: {activeCount}</b>
   <b style={{cursor:'pointer'}} onClick={()=>setFilter('expiring')}>30 günde biten: {expiringCount}</b>
   <b style={{cursor:'pointer'}} onClick={()=>setFilter('suspended')}>Askıda: {suspendedCount}</b>
   <b style={{cursor:'pointer'}} onClick={()=>setFilter('expired')}>Süresi dolan: {expiredCount}</b>
   <b>Aylık ciro (aktif): {money(mrr)}</b>
   {filter!=='all'&&<button type="button" className="mini secondary" onClick={()=>setFilter('all')}>Tümünü göster</button>}
  </div>
  <T rows={filtered} cols={[
   {k:'contract_number',l:'Sözleşme No'},
   {k:'company_id',l:'İşyeri',f:r=>companies.find(x=>x.id===r.company_id)?.name||r.company_id},
   {k:'start_date',l:'Başlangıç'},
   {k:'end_date',l:'Bitiş',f:r=>r.end_date||'—'},
   {k:'days',l:'Kalan gün',f:r=>r._days==null?'—':(r._days<0?`${Math.abs(r._days)} gün geçti`:`${r._days} gün`)},
   {k:'monthly_fee',l:'Aylık ücret',f:r=>r.monthly_fee==null?'—':money(r.monthly_fee)},
   {k:'status',l:'Durum',f:r=><span className={`status-badge ${statusBadge(r)}`}>{statusLabel[r.status]||r.status}{r._expiring?' · yaklaşıyor':''}</span>},
   {k:'source',l:'Kaynak',f:r=>String(r.contract_number||'').startsWith('CRM-')?'CRM dönüşüm':'Manuel'},
   {k:'act',l:'İşlem',f:r=>(
    <div className="actions" style={{gap:6,flexWrap:'wrap'}}>
     {r.status==='active'&&<>
      <button type="button" className="mini" disabled={busyId===r.id} onClick={()=>act(r,'suspend')}>Askıya Al</button>
      <button type="button" className="mini" disabled={busyId===r.id} onClick={()=>act(r,'end')}>Sonlandır</button>
     </>}
     {(r.status==='suspended'||r.status==='ended')&&(
      <button type="button" className="mini" disabled={busyId===r.id} onClick={()=>act(r,'activate')}>Aktifleştir</button>
     )}
    </div>
   )},
  ]}/>
  {open&&<M title="Yeni Hizmet Sözleşmesi" close={()=>setOpen(false)}><form className="form-grid" onSubmit={save}>
   <S label="İşyeri" required value={form.company_id} onChange={e=>setForm({...form,company_id:e.target.value})}>
    <option value="">Seçiniz</option>
    {companies.filter(x=>!form.osgb_id||x.osgb_id==null||Number(x.osgb_id)===Number(form.osgb_id)).map(x=><option key={x.id} value={x.id}>{x.name}</option>)}
   </S>
   <F label="Sözleşme No" required value={form.contract_number} onChange={e=>setForm({...form,contract_number:e.target.value})}/>
   <F label="Başlangıç" type="date" required value={form.start_date} onChange={e=>setForm({...form,start_date:e.target.value})}/>
   <F label="Bitiş" type="date" value={form.end_date} onChange={e=>setForm({...form,end_date:e.target.value})}/>
   <F label="Aylık ücret (TL)" type="number" value={form.monthly_fee} onChange={e=>setForm({...form,monthly_fee:e.target.value})}/>
   <div className="form-actions"><button>Kaydet</button></div>
  </form></M>}
 </P>
}

export function FinancePage({user}){
 const[orgs,setOrgs]=useState([]),[companies,setCompanies]=useState([]),[rows,setRows]=useState([]),[open,setOpen]=useState(false),[busyId,setBusyId]=useState(null);
 const[companyFilter,setCompanyFilter]=useState(()=>{
  try{return sessionStorage.getItem('isg_finance_company_id')||''}catch{return ''}
 });
 const[form,setForm]=useState({osgb_id:'',company_id:'',transaction_type:'income',category:'service',amount:0,transaction_date:'',due_date:'',status:'pending',description:''});
 const catLabel={service:'Hizmet',contract:'Sözleşme tahakkuku',salary:'Maaş',expense:'Gider',other:'Diğer'};
 const statusLabel={pending:'Bekliyor',paid:'Ödendi',cancelled:'İptal'};
 const load=async()=>{
  const[o,c]=await Promise.all([api('/osgb'),api('/companies')]);
  const id=osgbId(user,o);
  setOrgs(o);setCompanies(c);setForm(x=>({...x,osgb_id:id}));
  if(id)setRows(await api(`/operations/finance?osgb_id=${id}`));
 };
 useEffect(()=>{load()},[]);
 useEffect(()=>{
  if(!companyFilter) return;
  try{sessionStorage.removeItem('isg_finance_company_id')}catch(_){ /* ignore */ }
 },[companyFilter]);
 async function save(e){e.preventDefault();await api('/operations/finance',{method:'POST',body:JSON.stringify({...form,osgb_id:Number(form.osgb_id),company_id:form.company_id?Number(form.company_id):null,amount:Number(form.amount),due_date:form.due_date||null})});setOpen(false);load()}
 async function setStatus(row,status){
  setBusyId(row.id);
  try{
   await api(`/operations/finance/${row.id}`,{method:'PATCH',body:JSON.stringify({status})});
   await load();
  }catch(ex){alert(ex.message||'Durum güncellenemedi.')}
  finally{setBusyId(null)}
 }
 const visible=companyFilter?rows.filter(r=>String(r.company_id)===String(companyFilter)):rows;
 async function accrueMonth(){
  if(!form.osgb_id){alert('OSGB seçili değil.');return}
  if(!window.confirm('Aktif sözleşmeler için bu ay tahakkukları oluşturulsun mu?\n(Zaten oluşmuş olanlar atlanır.)')) return;
  setBusyId('accrue');
  try{
   const res=await api(`/operations/finance/accrue-month?osgb_id=${form.osgb_id}`,{method:'POST',body:'{}'});
   alert(`Tahakkuk: ${res.created_count||0} yeni · ${res.skipped_count||0} atlandı (${res.month||''})`);
   await load();
  }catch(ex){alert(ex.message||'Tahakkuk oluşturulamadı.')}
  finally{setBusyId(null)}
 }
 return <P title="Finans ve Cari Takip" action={<div className="actions" style={{gap:8}}>
  <button type="button" className="secondary" disabled={busyId==='accrue'} onClick={accrueMonth}>Bu ay tahakkuk</button>
  <button onClick={()=>setOpen(true)}><Plus/>Finans Kaydı</button>
 </div>}>
  <div className="finance-summary">
   <b>Toplam Gelir: {money(visible.filter(x=>x.transaction_type==='income'&&x.status==='paid').reduce((a,b)=>a+b.amount,0))}</b>
   <b>Toplam Gider: {money(visible.filter(x=>x.transaction_type==='expense'&&x.status==='paid').reduce((a,b)=>a+b.amount,0))}</b>
   <b>Bekleyen sözleşme tahakkuku: {money(visible.filter(x=>x.category==='contract'&&x.status==='pending').reduce((a,b)=>a+b.amount,0))}</b>
  </div>
  <div style={{display:'flex',gap:10,flexWrap:'wrap',marginBottom:12,alignItems:'center'}}>
   <label className="field" style={{margin:0,minWidth:200}}>
    <span>İşyeri filtresi</span>
    <select value={companyFilter} onChange={e=>setCompanyFilter(e.target.value)}>
     <option value="">Tümü</option>
     {companies.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}
    </select>
   </label>
   {companyFilter&&<button type="button" className="mini secondary" onClick={()=>setCompanyFilter('')}>Filtreyi temizle</button>}
  </div>
  <T rows={visible} cols={[
   {k:'transaction_date',l:'Tarih'},
   {k:'company_id',l:'İşyeri',f:r=>companies.find(x=>x.id===r.company_id)?.name||'Genel'},
   {k:'transaction_type',l:'Tür',f:r=>r.transaction_type==='income'?'Gelir':'Gider'},
   {k:'category',l:'Kategori',f:r=>catLabel[r.category]||r.category},
   {k:'amount',l:'Tutar',f:r=>money(r.amount)},
   {k:'status',l:'Durum',f:r=>statusLabel[r.status]||r.status},
   {k:'description',l:'Açıklama',f:r=>r.description||'—'},
   {k:'act',l:'İşlem',f:r=>(
    <div className="actions" style={{gap:6,flexWrap:'wrap'}}>
     {r.status==='pending'&&<>
      <button type="button" className="mini" disabled={busyId===r.id} onClick={()=>setStatus(r,'paid')}>Ödendi</button>
      <button type="button" className="mini secondary" disabled={busyId===r.id} onClick={()=>setStatus(r,'cancelled')}>İptal</button>
     </>}
    </div>
   )},
  ]}/>
  {open&&<M title="Yeni Finans Kaydı" close={()=>setOpen(false)}><form className="form-grid" onSubmit={save}>
   <S label="Tür" value={form.transaction_type} onChange={e=>setForm({...form,transaction_type:e.target.value})}><option value="income">Gelir</option><option value="expense">Gider</option></S>
   <S label="İşyeri" value={form.company_id} onChange={e=>setForm({...form,company_id:e.target.value})}><option value="">Genel</option>{companies.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</S>
   <S label="Kategori" value={form.category} onChange={e=>setForm({...form,category:e.target.value})}>
    <option value="service">Hizmet</option>
    <option value="contract">Sözleşme tahakkuku</option>
    <option value="salary">Maaş</option>
    <option value="other">Diğer</option>
   </S>
   <F label="Tutar (TL)" type="number" required value={form.amount} onChange={e=>setForm({...form,amount:e.target.value})}/>
   <F label="İşlem Tarihi" type="date" required value={form.transaction_date} onChange={e=>setForm({...form,transaction_date:e.target.value})}/>
   <F label="Vade Tarihi" type="date" value={form.due_date} onChange={e=>setForm({...form,due_date:e.target.value})}/>
   <S label="Durum" value={form.status} onChange={e=>setForm({...form,status:e.target.value})}><option value="pending">Bekliyor</option><option value="paid">Ödendi</option><option value="cancelled">İptal</option></S>
   <F label="Açıklama" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/>
   <div className="form-actions"><button>Kaydet</button></div>
  </form></M>}
 </P>
}
