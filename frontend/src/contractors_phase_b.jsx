import {useEffect, useMemo, useState} from "react";
import {api, downloadFile, uploadFile} from "./api";

const emptyContractor = {name:"", contract_number:"", contract_start:"", contract_end:"", contact_name:"", contact_phone:"", workers:[]};
const emptyDocument = {document_type:"general", title:"", valid_until:"", notes:""};
const permitLabels = {hot_work:"Sıcak iş", work_at_height:"Yüksekte çalışma", confined_space:"Kapalı alan", electrical:"Elektrik", general:"Genel"};

export function ContractorsPhaseBPage(){
  const [companies,setCompanies]=useState([]);
  const [rows,setRows]=useState([]);
  const [companyId,setCompanyId]=useState("");
  const [selectedId,setSelectedId]=useState(null);
  const [form,setForm]=useState(emptyContractor);
  const [workerName,setWorkerName]=useState("");
  const [newWorker,setNewWorker]=useState({full_name:"",job_title:"",national_id_masked:""});
  const [docForm,setDocForm]=useState(emptyDocument);
  const [docFile,setDocFile]=useState(null);
  const [permits,setPermits]=useState([]);
  const [permitId,setPermitId]=useState("");
  const [eligibility,setEligibility]=useState(null);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);

  const selected=useMemo(()=>rows.find((item)=>item.id===selectedId)||null,[rows,selectedId]);
  const companyName=(id)=>companies.find((item)=>item.id===id)?.name||String(id||"—");

  async function load(filter=companyId){
    const result=await api(filter?`/contractors?company_id=${filter}`:"/contractors");
    const items=result.items||[];
    setRows(items);
    if(selectedId&&!items.some((item)=>item.id===selectedId)) setSelectedId(null);
  }

  useEffect(()=>{
    Promise.all([api("/companies"),api("/contractors")])
      .then(([companyData,contractorData])=>{
        setCompanies(Array.isArray(companyData)?companyData:companyData.items||[]);
        setRows(contractorData.items||[]);
      })
      .catch((ex)=>setError(ex.message));
  },[]);

  useEffect(()=>{load().catch((ex)=>setError(ex.message));},[companyId]);

  useEffect(()=>{
    setEligibility(null); setPermitId(""); setPermits([]);
    if(!selected) return;
    Promise.all([
      api(`/contractors/${selected.id}/eligibility`),
      api(`/work-permits?company_id=${selected.company_id}`),
    ]).then(([eligible,permitData])=>{
      setEligibility(eligible);
      setPermits((permitData.items||[]).filter((item)=>!item.contractor_id||item.contractor_id===selected.id));
    }).catch((ex)=>setError(ex.message));
  },[selected?.id]);

  function updateForm(name,value){setForm((current)=>({...current,[name]:value}));}

  async function saveContractor(event){
    event.preventDefault();
    if(!companyId){setError("Önce işyeri seçin.");return;}
    setBusy(true);setError("");
    try{
      await api("/contractors",{method:"POST",body:JSON.stringify({...form,company_id:Number(companyId),contract_start:form.contract_start||null,contract_end:form.contract_end||null,workers:form.workers.map((full_name)=>({full_name}))})});
      setForm(emptyContractor);setWorkerName("");await load();
    }catch(ex){setError(ex.message);}finally{setBusy(false);}
  }

  async function addWorker(event){
    event.preventDefault(); if(!selected||!newWorker.full_name.trim()) return;
    setBusy(true);setError("");
    try{
      await api(`/contractors/${selected.id}/workers`,{method:"POST",body:JSON.stringify({...newWorker,national_id_masked:newWorker.national_id_masked||null,job_title:newWorker.job_title||null})});
      setNewWorker({full_name:"",job_title:"",national_id_masked:""});await load();
    }catch(ex){setError(ex.message);}finally{setBusy(false);}
  }

  async function deactivateWorker(workerId){
    if(!window.confirm("Bu taşeron çalışanını pasife almak istiyor musunuz?")) return;
    try{await api(`/contractors/${selected.id}/workers/${workerId}/deactivate`,{method:"PATCH"});await load();}
    catch(ex){setError(ex.message);}
  }

  async function addDocument(event){
    event.preventDefault(); if(!selected) return;
    setBusy(true);setError("");
    try{
      const created=await api(`/contractors/${selected.id}/documents`,{method:"POST",body:JSON.stringify({...docForm,valid_until:docForm.valid_until||null})});
      if(docFile) await uploadFile(`/contractors/${selected.id}/documents/${created.id}/file`,docFile);
      setDocForm(emptyDocument);setDocFile(null);await load();
    }catch(ex){setError(ex.message);}finally{setBusy(false);}
  }

  async function copyToDocuments(documentId){
    try{await api(`/contractors/${selected.id}/documents/${documentId}/copy-to-documents`,{method:"POST"});await load();}
    catch(ex){setError(ex.message);}
  }

  async function attachPermit(){
    if(!selected||!permitId) return;
    try{await api(`/contractors/${selected.id}/permits/${permitId}`,{method:"POST"});setPermitId("");const p=await api(`/work-permits?company_id=${selected.company_id}`);setPermits(p.items||[]);}
    catch(ex){setError(ex.message);}
  }

  async function deactivateContractor(){
    if(!selected||!window.confirm(`${selected.name} taşeron kaydını pasife almak istiyor musunuz?`)) return;
    try{await api(`/contractors/${selected.id}/deactivate`,{method:"PATCH",body:JSON.stringify({reason:"Kullanıcı tarafından pasife alındı"})});setSelectedId(null);await load();}
    catch(ex){setError(ex.message);}
  }

  return <section className="page-shell">
    <div className="page-title"><div><h3>Taşeron Yönetimi</h3><p className="muted">Sözleşme, çalışan, belge ve çalışma izni uygunluğunu işyeri bazında yönetin.</p></div><span className="badge ok">Saha İSG</span></div>
    {error&&<p className="error">{error}</p>}

    <section className="panel">
      <div className="panel-title"><h4>Taşeron firma kaydı</h4><span className="muted">Taşeron çalışanları ana personel sayısına eklenmez.</span></div>
      <form className="form-grid" onSubmit={saveContractor}>
        <label className="field"><span>İşyeri</span><select required value={companyId} onChange={(e)=>setCompanyId(e.target.value)}><option value="">İşyeri seçin</option>{companies.map((item)=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="field"><span>Taşeron firma</span><input required value={form.name} onChange={(e)=>updateForm("name",e.target.value)}/></label>
        <label className="field"><span>Sözleşme no</span><input value={form.contract_number} onChange={(e)=>updateForm("contract_number",e.target.value)}/></label>
        <label className="field"><span>Sözleşme başlangıç</span><input type="date" value={form.contract_start} onChange={(e)=>updateForm("contract_start",e.target.value)}/></label>
        <label className="field"><span>Sözleşme bitiş</span><input type="date" value={form.contract_end} onChange={(e)=>updateForm("contract_end",e.target.value)}/></label>
        <label className="field"><span>Yetkili</span><input value={form.contact_name} onChange={(e)=>updateForm("contact_name",e.target.value)}/></label>
        <label className="field"><span>Telefon</span><input value={form.contact_phone} onChange={(e)=>updateForm("contact_phone",e.target.value)}/></label>
        <label className="field"><span>İlk çalışanlar</span><input value={workerName} onChange={(e)=>setWorkerName(e.target.value)} onKeyDown={(e)=>{if(e.key==="Enter"&&workerName.trim()){e.preventDefault();updateForm("workers",[...form.workers,workerName.trim()]);setWorkerName("");}}} placeholder="Yazıp Enter'a basın"/></label>
        <div className="form-actions"><button type="submit" disabled={busy}>Taşeronu kaydet</button></div>
      </form>
      {form.workers.length>0&&<p className="muted">İlk çalışanlar: {form.workers.join(", ")}</p>}
    </section>

    <section className="panel">
      <div className="panel-title"><h4>Aktif taşeronlar</h4><span className="badge">{rows.length} kayıt</span></div>
      <div className="table-wrap"><table><thead><tr><th>Firma</th><th>İşyeri</th><th>Sözleşme</th><th>Çalışan</th><th>Belge</th><th>Durum</th><th></th></tr></thead><tbody>
        {rows.map((row)=><tr key={row.id}><td><strong>{row.name}</strong><br/><span className="muted">{row.contact_name||"Yetkili yok"}</span></td><td>{companyName(row.company_id)}</td><td>{row.contract_number||"—"}<br/><span className="muted">{row.contract_end||"Bitiş tarihi yok"}</span></td><td>{row.workers?.length||0}</td><td>{row.documents?.length||0}</td><td><span className="badge ok">Aktif</span></td><td><button type="button" onClick={()=>setSelectedId(row.id)}>Yönet</button></td></tr>)}
        {!rows.length&&<tr><td colSpan="7"><p className="muted">Bu kapsamda aktif taşeron kaydı bulunmuyor.</p></td></tr>}
      </tbody></table></div>
    </section>

    {selected&&<>
      <section className="panel">
        <div className="panel-title"><div><h4>{selected.name}</h4><span className="muted">{companyName(selected.company_id)} · Sözleşme {selected.contract_end||"bitiş tarihi yok"}</span></div><div>{eligibility&&<span className={`badge ${eligibility.eligible?"ok":"warn"}`}>{eligibility.eligible?"Uygun":"Eksik var"}</span>} <button type="button" onClick={deactivateContractor}>Taşeronu pasife al</button></div></div>
        {eligibility&&!eligibility.eligible&&<p className="error">{eligibility.reasons.join(" · ")}</p>}
      </section>

      <section className="panel"><div className="panel-title"><h4>Taşeron çalışanları</h4><span className="muted">Ana employees listesine eklenmez.</span></div>
        <form className="form-grid" onSubmit={addWorker}><label className="field"><span>Ad soyad</span><input required value={newWorker.full_name} onChange={(e)=>setNewWorker({...newWorker,full_name:e.target.value})}/></label><label className="field"><span>Görev</span><input value={newWorker.job_title} onChange={(e)=>setNewWorker({...newWorker,job_title:e.target.value})}/></label><label className="field"><span>Maskeli kimlik no</span><input value={newWorker.national_id_masked} onChange={(e)=>setNewWorker({...newWorker,national_id_masked:e.target.value})}/></label><div className="form-actions"><button disabled={busy}>Çalışan ekle</button></div></form>
        <div className="table-wrap"><table><thead><tr><th>Ad soyad</th><th>Görev</th><th></th></tr></thead><tbody>{(selected.workers||[]).map((item)=><tr key={item.id}><td>{item.full_name}</td><td>{item.job_title||"—"}</td><td><button type="button" onClick={()=>deactivateWorker(item.id)}>Pasife al</button></td></tr>)}</tbody></table></div>
      </section>

      <section className="panel"><div className="panel-title"><h4>Belge ve geçerlilik</h4><span className="muted">Dosya güvenli taşeron depolamasında kalır; kayıt Dokümanlar'a kopyalanabilir.</span></div>
        <form className="form-grid" onSubmit={addDocument}><label className="field"><span>Belge türü</span><input required value={docForm.document_type} onChange={(e)=>setDocForm({...docForm,document_type:e.target.value})}/></label><label className="field"><span>Belge başlığı</span><input required value={docForm.title} onChange={(e)=>setDocForm({...docForm,title:e.target.value})}/></label><label className="field"><span>Geçerlilik sonu</span><input type="date" value={docForm.valid_until} onChange={(e)=>setDocForm({...docForm,valid_until:e.target.value})}/></label><label className="field"><span>Dosya</span><input type="file" accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx" onChange={(e)=>setDocFile(e.target.files?.[0]||null)}/></label><label className="field"><span>Not</span><input value={docForm.notes} onChange={(e)=>setDocForm({...docForm,notes:e.target.value})}/></label><div className="form-actions"><button disabled={busy}>Belge ekle</button></div></form>
        <div className="table-wrap"><table><thead><tr><th>Belge</th><th>Geçerlilik</th><th>Dosya</th><th>Dokümanlar</th></tr></thead><tbody>{(selected.documents||[]).map((doc)=><tr key={doc.id}><td>{doc.title}<br/><span className="muted">{doc.document_type}</span></td><td>{doc.valid_until||"—"}</td><td>{doc.has_file?<button type="button" onClick={()=>downloadFile(`/contractors/${selected.id}/documents/${doc.id}/file`,doc.file_name||"taseron-belgesi")}>İndir</button>:<span className="muted">Dosya yok</span>}</td><td>{doc.document_record_id?<span className="badge ok">Kopyalandı #{doc.document_record_id}</span>:<button type="button" onClick={()=>copyToDocuments(doc.id)}>Dokümanlar'a kopyala</button>}</td></tr>)}</tbody></table></div>
      </section>

      <section className="panel"><div className="panel-title"><h4>Çalışma izni bağlantıları</h4><span className="muted">PTW bağı mevcut iş izni kaydını değiştirmez; yalnız taşeron bağlantısını kurar.</span></div><div className="form-grid"><label className="field"><span>İş izni</span><select value={permitId} onChange={(e)=>setPermitId(e.target.value)}><option value="">İş izni seçin</option>{permits.map((permit)=><option key={permit.id} value={permit.id}>{permit.permit_no} · {permitLabels[permit.permit_type]||permit.permit_type} · {permit.status}</option>)}</select></label><div className="form-actions"><button type="button" disabled={!permitId} onClick={attachPermit}>Taşerona bağla</button></div></div></section>
    </>}
  </section>;
}
