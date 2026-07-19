import React,{useEffect,useState} from 'react';
import {api} from './api';
import {Plus} from 'lucide-react';

const ptypes={safety_specialist:'İş Güvenliği Uzmanı',workplace_physician:'İşyeri Hekimi',other_health_personnel:'Diğer Sağlık Personeli'};
const stages={new:'Yeni',contacted:'Görüşüldü',proposal:'Teklif',negotiation:'Müzakere',won:'Kazanıldı',lost:'Kaybedildi'};
const money=v=>new Intl.NumberFormat('tr-TR',{style:'currency',currency:'TRY',maximumFractionDigits:0}).format(v||0);
function F({label,...p}){return <label className="field"><span>{label}</span><input {...p}/></label>}
function S({label,children,...p}){return <label className="field"><span>{label}</span><select {...p}>{children}</select></label>}
function M({title,close,children}){return <div className="modal-bg"><section className="modal"><header><h3>{title}</h3><button className="icon" onClick={close}>×</button></header>{children}</section></div>}
function T({cols,rows}){return <div className="table-wrap"><table><thead><tr>{cols.map(c=><th key={c.k}>{c.l}</th>)}</tr></thead><tbody>{rows.length?rows.map((r,i)=><tr key={r.id||i}>{cols.map(c=><td key={c.k}>{c.f?c.f(r):String(r[c.k]??'—')}</td>)}</tr>):<tr><td colSpan={cols.length} className="empty">Henüz kayıt bulunmuyor.</td></tr>}</tbody></table></div>}
function P({title,action,children}){return <><div className="page-title"><h3>{title}</h3>{action}</div><section className="panel">{children}</section></>}
function osgbId(user,orgs){return user.osgb_id||orgs[0]?.id||''}

export function OsgbDashboard({user}){
 const[orgs,setOrgs]=useState([]),[data,setData]=useState(null),[oid,setOid]=useState('');
 const[unassignedOpen,setUnassignedOpen]=useState(false);
 const[unassignedType,setUnassignedType]=useState('safety_specialist');
 const[contractsOpen,setContractsOpen]=useState(false);

 async function load(id){
  if(!id){setData(null);return}
  setData(await api(`/operations/dashboard?osgb_id=${id}`));
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

 return <>
  <div className="welcome"><div>
   <h3>OSGB Ana Panel</h3>
   <p>Müşteri işyerleri, İSG kadrosu, atanmamış profesyoneller ve bitmesi yaklaşan sözleşmeler.</p>
  </div></div>

  {orgs.length>1&&<section className="panel" style={{marginBottom:16}}>
   <label className="field"><span>OSGB</span>
    <select value={oid} onChange={e=>{const v=e.target.value;setOid(v);load(v)}}>
     {orgs.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}
    </select>
   </label>
  </section>}

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

export function ProfessionalsPage({user}){
 const tabs=[
  {id:'safety_specialist',label:'İş Güvenliği Uzmanları'},
  {id:'workplace_physician',label:'İşyeri Hekimleri'},
  {id:'other_health_personnel',label:'DSP'},
 ];
 const[orgs,setOrgs]=useState([]),[rows,setRows]=useState([]),[tab,setTab]=useState('safety_specialist');
 const[open,setOpen]=useState(false),[err,setErr]=useState(''),[busy,setBusy]=useState(false);
 const[form,setForm]=useState({osgb_id:'',full_name:'',email:'',phone:'',professional_type:'safety_specialist',certificate_class:'',certificate_number:'',certificate_date:''});
 const load=async()=>{
  setErr('');
  const o=await api('/osgb');
  setOrgs(o);
  const id=osgbId(user,o);
  setForm(x=>({...x,osgb_id:id,professional_type:tab}));
  if(id) setRows(await api(`/osgb/professionals?osgb_id=${id}`));
 };
 useEffect(()=>{load()},[]);
 useEffect(()=>{setForm(x=>({...x,professional_type:tab}))},[tab]);
 const filtered=rows.filter(r=>r.professional_type===tab);
 const counts=Object.fromEntries(tabs.map(t=>[t.id,rows.filter(r=>r.professional_type===t.id).length]));
 async function save(e){
  e.preventDefault();setErr('');setBusy(true);
  try{
   await api('/osgb/professionals',{method:'POST',body:JSON.stringify({
    ...form,
    osgb_id:Number(form.osgb_id),
    professional_type:form.professional_type||tab,
    certificate_date:form.certificate_date||null,
    email:form.email||null,
   })});
   setOpen(false);
   setForm(f=>({...f,full_name:'',email:'',phone:'',certificate_class:'',certificate_number:'',certificate_date:'',professional_type:tab}));
   await load();
  }catch(ex){setErr(ex.message)}
  finally{setBusy(false)}
 }
 async function suspend(row){
  if(!window.confirm(`${row.full_name} askıya alınsın mı?`)) return;
  try{await api(`/osgb/professionals/${row.id}/suspend`,{method:'PATCH'});await load()}
  catch(ex){setErr(ex.message)}
 }
 async function activate(row){
  try{await api(`/osgb/professionals/${row.id}/activate`,{method:'PATCH'});await load()}
  catch(ex){setErr(ex.message)}
 }
 async function remove(row){
  if(!window.confirm(`${row.full_name} silinsin mi? Aktif görevlendirme varsa silinemez.`)) return;
  try{await api(`/osgb/professionals/${row.id}`,{method:'DELETE'});await load()}
  catch(ex){setErr(ex.message)}
 }
 return <P title="İSG Profesyonelleri" action={<button onClick={()=>{setErr('');setForm(f=>({...f,professional_type:tab}));setOpen(true)}}><Plus/>Profesyonel Ekle</button>}>
  <div className="actions" style={{marginBottom:14,gap:8,flexWrap:'wrap'}}>
   {tabs.map(t=>(
    <button key={t.id} type="button" className={tab===t.id?'':'secondary'} onClick={()=>setTab(t.id)}>
     {t.label} ({counts[t.id]||0})
    </button>
   ))}
  </div>
  {err&&<p style={{color:'#b91c1c'}}>{err}</p>}
  <T rows={filtered} cols={[
   {k:'full_name',l:'Ad Soyad'},
   {k:'certificate_class',l:'Sınıf'},
   {k:'certificate_number',l:'Belge No'},
   {k:'phone',l:'Telefon'},
   {k:'email',l:'E-posta'},
   {k:'is_active',l:'Durum',f:r=><span className={'badge '+(r.is_active?'ok':'off')}>{r.is_active?'Aktif':'Askıda'}</span>},
   {k:'x',l:'İşlem',f:r=>(
    <div className="actions" style={{gap:6,flexWrap:'wrap'}}>
     {r.is_active
      ? <button type="button" className="mini" onClick={()=>suspend(r)}>Askıya Al</button>
      : <button type="button" className="mini" onClick={()=>activate(r)}>Aktifleştir</button>}
     <button type="button" className="mini" onClick={()=>remove(r)}>Sil</button>
    </div>
   )},
  ]}/>
  {open&&<M title={`Yeni ${ptypes[tab]||'Profesyonel'}`} close={()=>setOpen(false)}>
   <form className="form-grid" onSubmit={save}>
    <F label="Ad Soyad" required value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/>
    <S label="Meslek" value={form.professional_type} onChange={e=>setForm({...form,professional_type:e.target.value})}>
     {Object.entries(ptypes).map(([k,v])=><option key={k} value={k}>{v}</option>)}
    </S>
    <F label="E-posta" type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/>
    <F label="Telefon" value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/>
    <F label="Belge Sınıfı" value={form.certificate_class} onChange={e=>setForm({...form,certificate_class:e.target.value})}/>
    <F label="Belge No" value={form.certificate_number} onChange={e=>setForm({...form,certificate_number:e.target.value})}/>
    <F label="Belge Tarihi" type="date" value={form.certificate_date} onChange={e=>setForm({...form,certificate_date:e.target.value})}/>
    {err&&<p style={{color:'#b91c1c',gridColumn:'1/-1'}}>{err}</p>}
    <div className="form-actions"><button disabled={busy}>{busy?'Kaydediliyor...':'Kaydet'}</button></div>
   </form>
  </M>}
 </P>
}

export function AssignmentsPage({user}){
 const isGlobal=user.role==='global_admin';
 const[orgs,setOrgs]=useState([]),[companies,setCompanies]=useState([]),[pros,setPros]=useState([]),[rows,setRows]=useState([]);
 const[open,setOpen]=useState(false),[err,setErr]=useState(''),[busy,setBusy]=useState(false);
 const[form,setForm]=useState({osgb_id:'',company_id:'',professional_id:'',professional_type:'safety_specialist',start_date:'',end_date:'',required_minutes_monthly:0,planned_minutes_monthly:0,actual_minutes_monthly:0,isg_katip_contract_number:''});
 const load=async(preferredOid)=>{
  const[o,c]=await Promise.all([api('/osgb'),api('/companies')]);
  const id=preferredOid||osgbId(user,o);
  setOrgs(o);setCompanies(c);
  setForm(x=>({...x,osgb_id:id||x.osgb_id}));
  const oid=Number(preferredOid||id);
  if(oid){
   const[p,a]=await Promise.all([api(`/osgb/professionals?osgb_id=${oid}`),api('/osgb/assignments')]);
   setPros(p);setRows(a);
  }
 };
 useEffect(()=>{load()},[]);
 const companyOpts=companies.filter(x=>{
  const oid=Number(form.osgb_id);
  if(!oid) return true;
  return !x.osgb_id || Number(x.osgb_id)===oid;
 });
 async function save(e){
  e.preventDefault();
  setErr('');setBusy(true);
  try{
   if(!form.osgb_id) throw new Error('OSGB seçiniz.');
   if(!form.company_id) throw new Error('İşyeri seçiniz.');
   if(!form.professional_id) throw new Error('Profesyonel seçiniz.');
   if(!form.start_date) throw new Error('Başlangıç tarihi zorunlu.');
   const pro=pros.find(x=>x.id===Number(form.professional_id));
   await api('/osgb/assignments',{method:'POST',body:JSON.stringify({
    osgb_id:Number(form.osgb_id),
    company_id:Number(form.company_id),
    professional_id:Number(form.professional_id),
    professional_type:pro?.professional_type||form.professional_type,
    start_date:form.start_date,
    end_date:form.end_date||null,
    required_minutes_monthly:Number(form.required_minutes_monthly)||0,
    planned_minutes_monthly:Number(form.planned_minutes_monthly)||0,
    actual_minutes_monthly:Number(form.actual_minutes_monthly)||0,
    isg_katip_contract_number:form.isg_katip_contract_number||null,
   })});
   setOpen(false);
   setForm(f=>({...f,company_id:'',professional_id:'',start_date:'',end_date:'',required_minutes_monthly:0,planned_minutes_monthly:0,actual_minutes_monthly:0,isg_katip_contract_number:''}));
   await load(form.osgb_id);
  }catch(ex){setErr(ex.message||'Kayıt başarısız.')}
  finally{setBusy(false)}
 }
 async function onOsgbChange(oid){
  setForm(f=>({...f,osgb_id:oid,company_id:'',professional_id:''}));
  await load(oid);
 }
 return <P title="İşyeri Görevlendirmeleri" action={<button onClick={()=>{setErr('');setOpen(true)}}><Plus/>Görevlendirme Yap</button>}>
  {err&&!open&&<p style={{color:'#b91c1c'}}>{err}</p>}
  <T rows={rows} cols={[
   {k:'company_id',l:'İşyeri',f:r=>companies.find(x=>x.id===r.company_id)?.name||r.company_id},
   {k:'professional_id',l:'Profesyonel',f:r=>pros.find(x=>x.id===r.professional_id)?.full_name||r.professional_id},
   {k:'professional_type',l:'Görev',f:r=>ptypes[r.professional_type]},
   {k:'start_date',l:'Başlangıç'},
   {k:'required_minutes_monthly',l:'Zorunlu dk.'},
   {k:'actual_minutes_monthly',l:'Gerçekleşen dk.'},
   {k:'status',l:'Durum'}
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
    <F label="İSG-KATİP Sözleşme No" value={form.isg_katip_contract_number} onChange={e=>setForm({...form,isg_katip_contract_number:e.target.value})}/>
    {err&&<p style={{color:'#b91c1c',gridColumn:'1/-1'}}>{err}</p>}
    <div className="form-actions"><button disabled={busy}>{busy?'Kaydediliyor...':'Kaydet'}</button></div>
   </form>
  </M>}
 </P>
}

export function VisitsPage({user}){
 const[orgs,setOrgs]=useState([]),[companies,setCompanies]=useState([]),[pros,setPros]=useState([]),[rows,setRows]=useState([]),[open,setOpen]=useState(false),[form,setForm]=useState({osgb_id:'',company_id:'',professional_id:'',visit_date:'',start_time:'09:00',end_time:'10:00',duration_minutes:60,subject:'Periyodik saha ziyareti',notes:''});
 const load=async()=>{const[o,c]=await Promise.all([api('/osgb'),api('/companies')]);const id=osgbId(user,o);setOrgs(o);setCompanies(c);setForm(x=>({...x,osgb_id:id}));if(id){const[p,v]=await Promise.all([api(`/osgb/professionals?osgb_id=${id}`),api(`/operations/visits?osgb_id=${id}`)]);setPros(p);setRows(v)}};useEffect(()=>{load()},[]);
 async function save(e){e.preventDefault();await api('/operations/visits',{method:'POST',body:JSON.stringify({...form,osgb_id:Number(form.osgb_id),company_id:Number(form.company_id),professional_id:Number(form.professional_id),duration_minutes:Number(form.duration_minutes)})});setOpen(false);load()}
 async function done(id){await api(`/operations/visits/${id}/complete`,{method:'PATCH'});load()}
 return <P title="Saha Ziyaret Takvimi" action={<button onClick={()=>setOpen(true)}><Plus/>Ziyaret Planla</button>}><T rows={rows} cols={[{k:'visit_date',l:'Tarih'},{k:'company_id',l:'İşyeri',f:r=>companies.find(x=>x.id===r.company_id)?.name||r.company_id},{k:'professional_id',l:'Profesyonel',f:r=>pros.find(x=>x.id===r.professional_id)?.full_name||r.professional_id},{k:'subject',l:'Konu'},{k:'duration_minutes',l:'Süre (dk.)'},{k:'status',l:'Durum'},{k:'x',l:'İşlem',f:r=>r.status==='completed'?'Tamamlandı':<button className="mini" onClick={()=>done(r.id)}>Tamamla</button>}]}/>{open&&<M title="Yeni Saha Ziyareti" close={()=>setOpen(false)}><form className="form-grid" onSubmit={save}><S label="İşyeri" required value={form.company_id} onChange={e=>setForm({...form,company_id:e.target.value})}><option value="">Seçiniz</option>{companies.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</S><S label="Profesyonel" required value={form.professional_id} onChange={e=>setForm({...form,professional_id:e.target.value})}><option value="">Seçiniz</option>{pros.map(x=><option key={x.id} value={x.id}>{x.full_name}</option>)}</S><F label="Tarih" type="date" required value={form.visit_date} onChange={e=>setForm({...form,visit_date:e.target.value})}/><F label="Başlangıç" type="time" value={form.start_time} onChange={e=>setForm({...form,start_time:e.target.value})}/><F label="Bitiş" type="time" value={form.end_time} onChange={e=>setForm({...form,end_time:e.target.value})}/><F label="Süre (dk.)" type="number" value={form.duration_minutes} onChange={e=>setForm({...form,duration_minutes:e.target.value})}/><F label="Ziyaret Konusu" required value={form.subject} onChange={e=>setForm({...form,subject:e.target.value})}/><F label="Notlar" value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/><div className="form-actions"><button>Kaydet</button></div></form></M>}</P>
}

export function CrmPage({user}){
 const[orgs,setOrgs]=useState([]),[rows,setRows]=useState([]),[open,setOpen]=useState(false),[form,setForm]=useState({osgb_id:'',company_name:'',contact_name:'',phone:'',email:'',employee_count:0,hazard_class:'Tehlikeli',stage:'new',estimated_monthly_value:0,next_action_date:'',notes:''});
 const load=async()=>{const o=await api('/osgb');const id=osgbId(user,o);setOrgs(o);setForm(x=>({...x,osgb_id:id}));if(id)setRows(await api(`/operations/leads?osgb_id=${id}`))};useEffect(()=>{load()},[]);
 async function save(e){e.preventDefault();await api('/operations/leads',{method:'POST',body:JSON.stringify({...form,osgb_id:Number(form.osgb_id),employee_count:Number(form.employee_count),estimated_monthly_value:Number(form.estimated_monthly_value),next_action_date:form.next_action_date||null})});setOpen(false);load()}
 return <P title="CRM ve Teklif Fırsatları" action={<button onClick={()=>setOpen(true)}><Plus/>Fırsat Ekle</button>}><T rows={rows} cols={[{k:'company_name',l:'Firma'},{k:'contact_name',l:'Yetkili'},{k:'employee_count',l:'Çalışan'},{k:'stage',l:'Aşama',f:r=>stages[r.stage]||r.stage},{k:'estimated_monthly_value',l:'Aylık Değer',f:r=>money(r.estimated_monthly_value)},{k:'next_action_date',l:'Sonraki İşlem'}]}/>{open&&<M title="Yeni Satış Fırsatı" close={()=>setOpen(false)}><form className="form-grid" onSubmit={save}><F label="Firma" required value={form.company_name} onChange={e=>setForm({...form,company_name:e.target.value})}/><F label="Yetkili" value={form.contact_name} onChange={e=>setForm({...form,contact_name:e.target.value})}/><F label="Telefon" value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/><F label="E-posta" type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/><F label="Çalışan Sayısı" type="number" value={form.employee_count} onChange={e=>setForm({...form,employee_count:e.target.value})}/><S label="Aşama" value={form.stage} onChange={e=>setForm({...form,stage:e.target.value})}>{Object.entries(stages).map(([k,v])=><option key={k} value={k}>{v}</option>)}</S><F label="Tahmini Aylık Değer" type="number" value={form.estimated_monthly_value} onChange={e=>setForm({...form,estimated_monthly_value:e.target.value})}/><F label="Sonraki İşlem" type="date" value={form.next_action_date} onChange={e=>setForm({...form,next_action_date:e.target.value})}/><div className="form-actions"><button>Kaydet</button></div></form></M>}</P>
}

export function FinancePage({user}){
 const[orgs,setOrgs]=useState([]),[companies,setCompanies]=useState([]),[rows,setRows]=useState([]),[open,setOpen]=useState(false),[form,setForm]=useState({osgb_id:'',company_id:'',transaction_type:'income',category:'service',amount:0,transaction_date:'',due_date:'',status:'pending',description:''});
 const load=async()=>{const[o,c]=await Promise.all([api('/osgb'),api('/companies')]);const id=osgbId(user,o);setOrgs(o);setCompanies(c);setForm(x=>({...x,osgb_id:id}));if(id)setRows(await api(`/operations/finance?osgb_id=${id}`))};useEffect(()=>{load()},[]);
 async function save(e){e.preventDefault();await api('/operations/finance',{method:'POST',body:JSON.stringify({...form,osgb_id:Number(form.osgb_id),company_id:form.company_id?Number(form.company_id):null,amount:Number(form.amount),due_date:form.due_date||null})});setOpen(false);load()}
 return <P title="Finans ve Cari Takip" action={<button onClick={()=>setOpen(true)}><Plus/>Finans Kaydı</button>}><div className="finance-summary"><b>Toplam Gelir: {money(rows.filter(x=>x.transaction_type==='income'&&x.status==='paid').reduce((a,b)=>a+b.amount,0))}</b><b>Toplam Gider: {money(rows.filter(x=>x.transaction_type==='expense'&&x.status==='paid').reduce((a,b)=>a+b.amount,0))}</b></div><T rows={rows} cols={[{k:'transaction_date',l:'Tarih'},{k:'company_id',l:'İşyeri',f:r=>companies.find(x=>x.id===r.company_id)?.name||'Genel'},{k:'transaction_type',l:'Tür',f:r=>r.transaction_type==='income'?'Gelir':'Gider'},{k:'category',l:'Kategori'},{k:'amount',l:'Tutar',f:r=>money(r.amount)},{k:'status',l:'Durum'}]}/>{open&&<M title="Yeni Finans Kaydı" close={()=>setOpen(false)}><form className="form-grid" onSubmit={save}><S label="Tür" value={form.transaction_type} onChange={e=>setForm({...form,transaction_type:e.target.value})}><option value="income">Gelir</option><option value="expense">Gider</option></S><S label="İşyeri" value={form.company_id} onChange={e=>setForm({...form,company_id:e.target.value})}><option value="">Genel</option>{companies.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</S><F label="Kategori" value={form.category} onChange={e=>setForm({...form,category:e.target.value})}/><F label="Tutar (TL)" type="number" required value={form.amount} onChange={e=>setForm({...form,amount:e.target.value})}/><F label="İşlem Tarihi" type="date" required value={form.transaction_date} onChange={e=>setForm({...form,transaction_date:e.target.value})}/><F label="Vade Tarihi" type="date" value={form.due_date} onChange={e=>setForm({...form,due_date:e.target.value})}/><S label="Durum" value={form.status} onChange={e=>setForm({...form,status:e.target.value})}><option value="pending">Bekliyor</option><option value="paid">Ödendi</option><option value="cancelled">İptal</option></S><F label="Açıklama" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/><div className="form-actions"><button>Kaydet</button></div></form></M>}</P>
}
