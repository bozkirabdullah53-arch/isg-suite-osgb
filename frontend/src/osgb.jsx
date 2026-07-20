import React,{useEffect,useMemo,useState} from 'react';
import {api,downloadFile,uploadFile} from './api';
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
     {user.role==='global_admin'&&(
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
  {creds&&<M title="Profesyonel Giriş Bilgileri" close={()=>setCreds(null)}>
   <div className="form-grid single">
    <p style={{marginTop:0,color:'#64748b'}}>Bu bilgileri profesyonelle güvenli kanaldan paylaşın. İlk girişten sonra Güvenlik → Şifre Değiştir ile güncelleyebilir.</p>
    <p><strong>Kullanıcı adı (e-posta):</strong> <code>{creds.email}</code></p>
    <p><strong>Ad:</strong> {creds.full_name}</p>
    <p><strong>Geçici şifre:</strong> <code>{creds.temporary_password}</code></p>
    <p style={{color:'#166534'}}>{creds.message}</p>
    <div className="form-actions"><button type="button" onClick={()=>setCreds(null)}>Tamam</button></div>
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
 const[form,setForm]=useState({osgb_id:'',company_id:'',professional_id:'',professional_type:'safety_specialist',start_date:'',end_date:'',required_minutes_monthly:0,planned_minutes_monthly:0,actual_minutes_monthly:0,isg_katip_contract_number:''});
 const statusLabel={active:'Aktif',suspended:'Askıda',ended:'Sonlandı'};
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
 return <P title="İşyeri Görevlendirmeleri" action={<button onClick={()=>{setErr('');setContractFile(null);setOpen(true)}}><Plus/>Görevlendirme Yap</button>}>
  {err&&!open&&<p style={{color:'#b91c1c'}}>{err}</p>}
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
 const isOsgb=user.role==='global_admin';
 const canEdit=isField||isOsgb;
 const[orgs,setOrgs]=useState([]),[companies,setCompanies]=useState([]),[pros,setPros]=useState([]),[rows,setRows]=useState([]);
 const[open,setOpen]=useState(false),[editing,setEditing]=useState(null),[err,setErr]=useState(''),[busy,setBusy]=useState(false);
 const[notebookFile,setNotebookFile]=useState(null);
 const emptyForm={osgb_id:'',company_id:'',visit_date:'',start_time:'09:00',end_time:'10:00',duration_minutes:60,subject:'Periyodik saha ziyareti',notes:''};
 const[form,setForm]=useState(emptyForm);
 const load=async(preferredOid)=>{
  setErr('');
  try{
   const[o,c]=await Promise.all([api('/osgb').catch(()=>[]),api('/companies')]);
   setOrgs(o);setCompanies(c);
   const id=preferredOid||osgbId(user,o)||(c.find(x=>x.osgb_id)?.osgb_id)||'';
   setForm(x=>({...x,osgb_id:id||x.osgb_id}));
   if(isField){
    setRows(await api('/operations/visits'));
    return;
   }
   const oid=Number(preferredOid||id);
   if(!oid){setRows([]);return}
   const[p,v]=await Promise.all([
    api(`/osgb/professionals?osgb_id=${oid}`).catch(()=>[]),
    api(`/operations/visits?osgb_id=${oid}`),
   ]);
   setPros(p);setRows(v);
  }catch(ex){setErr(ex.message||'Liste yüklenemedi.');setRows([])}
 };
 useEffect(()=>{load()},[]);
 function openCreate(){
  setErr('');setNotebookFile(null);setEditing(null);
  setForm(f=>({...emptyForm,osgb_id:f.osgb_id||osgbId(user,orgs)||''}));
  setOpen(true);
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
    await uploadFile(`/operations/visits/${visitId}/notebook`,notebookFile);
   }
   setOpen(false);setEditing(null);setNotebookFile(null);
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
  try{await api(`/operations/visits/${id}/complete`,{method:'PATCH'});await load()}
  catch(ex){setErr(ex.message||'Tamamlanamadı.')}
 }
 async function downloadNotebook(row){
  try{await downloadFile(`/operations/visits/${row.id}/notebook`,row.notebook_file_name||'tespit-oneri-defteri')}
  catch(ex){setErr(ex.message||'Dosya indirilemedi.')}
 }
 return <P title={isOsgb?'Saha Ziyaretleri (OSGB İzleme)':'Saha Ziyaret Takvimi'} action={isField?<button onClick={openCreate}><Plus/>Ziyaret Kaydet</button>:null}>
  {isOsgb&&<p style={{margin:'0 0 12px',color:'#475569',fontSize:14}}>Uzman / hekim / DSP’nin kaydettiği saha ziyaretleri burada izlenir; gerekirse düzeltebilir veya silebilirsiniz.</p>}
  {user.role==='global_admin'&&orgs.length>1&&(
   <label className="field" style={{maxWidth:320,marginBottom:12}}>
    <span>OSGB</span>
    <select value={form.osgb_id} onChange={e=>load(e.target.value)}>
     {orgs.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}
    </select>
   </label>
  )}
  {err&&!open&&<p style={{color:'#b91c1c'}}>{err}</p>}
  <T rows={rows} cols={[
   {k:'visit_date',l:'Tarih'},
   {k:'company_id',l:'İşyeri',f:r=>companies.find(x=>x.id===r.company_id)?.name||r.company_id},
   ...(!isField?[{k:'professional_id',l:'Profesyonel',f:r=>pros.find(x=>x.id===r.professional_id)?.full_name||r.professional_id}]:[]),
   {k:'subject',l:'Konu'},
   {k:'notebook_file_name',l:'Tespit Defteri',f:r=>r.notebook_file_name?<button type="button" className="mini" onClick={()=>downloadNotebook(r)}>{r.notebook_file_name}</button>:'—'},
   {k:'duration_minutes',l:'Süre (dk.)'},
   {k:'status',l:'Durum'},
   ...(canEdit?[{k:'x',l:'İşlem',f:r=>(
    <div className="actions" style={{flexWrap:'wrap'}}>
     <button type="button" className="mini" onClick={()=>openEdit(r)}>Düzenle</button>
     <button type="button" className="mini" onClick={()=>remove(r)}>Sil</button>
     {isField&&r.status!=='completed'&&<button type="button" className="mini" onClick={()=>done(r.id)}>Tamamla</button>}
    </div>
   )}]:[])
  ]}/>
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
    </label>
    {err&&<p style={{color:'#b91c1c',gridColumn:'1/-1'}}>{err}</p>}
    <div className="form-actions"><button disabled={busy}>{busy?'Kaydediliyor...':(editing?'Güncelle':'Kaydet')}</button></div>
   </form>
  </M>}
 </P>
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
