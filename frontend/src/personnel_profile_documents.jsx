import React,{useEffect,useMemo,useRef,useState} from 'react';
import {
  Archive,
  Camera,
  Download,
  FileCheck2,
  FileClock,
  FileText,
  FileUp,
  History,
  RefreshCw,
  ShieldCheck,
  Upload,
  X,
} from 'lucide-react';
import {api,authBlobUrl} from './api';
import {
  DOCUMENT_KIND_OPTIONS,
  acceptForDocumentKind,
  asDocumentRows,
  categoriesForKind,
  documentCategoryLabel,
  documentKindLabel,
  formatDocumentBytes,
  maxBytesForDocumentKind,
  newIdempotencyKey,
  normalizeCategoryForKind,
  safeDocumentFilename,
  validateDocumentFile,
  validityLabel,
  validityTone,
  verificationLabel,
} from './personnel_profile_documents_logic';
import './personnel_profile_documents.css';

const EMPTY_FORM={
  document_kind:'certificate',
  category:'occupational_safety_certificate',
  title:'',
  document_key:'',
  document_number:'',
  issuing_organization:'',
  issue_date:'',
  valid_from:'',
  expiration_date:'',
  no_expiration:false,
  access_classification:'internal_only',
  change_reason:'',
};

function Badge({children,tone='neutral'}){
  return <span className={`ppd-badge ppd-badge--${tone}`}>{children}</span>;
}

function DocumentIcon({kind}){
  if(kind==='profile_photo') return <Camera size={22}/>;
  if(kind==='cv') return <FileText size={22}/>;
  return <FileCheck2 size={22}/>;
}

function formatDate(value){
  if(!value) return '';
  const raw=String(value);
  const date=new Date(raw.includes('T')?raw:`${raw}T00:00:00`);
  if(Number.isNaN(date.getTime())) return raw;
  return new Intl.DateTimeFormat('tr-TR').format(date);
}

function metadataLine(row){
  return [
    row.document_number?`No: ${row.document_number}`:'',
    row.issuing_organization||'',
    row.issue_date?`Düzenlenme: ${formatDate(row.issue_date)}`:'',
    row.expiration_date?`Bitiş: ${formatDate(row.expiration_date)}`:row.no_expiration?'Süresiz':'',
  ].filter(Boolean).join(' · ');
}

export function PersonnelProfileDocumentsPanel({profileId,canWrite,onError,onMessage,onCountChange}){
  const[documents,setDocuments]=useState([]);
  const[loading,setLoading]=useState(true);
  const[actionBusy,setActionBusy]=useState(false);
  const[showArchived,setShowArchived]=useState(false);
  const[form,setForm]=useState(EMPTY_FORM);
  const[file,setFile]=useState(null);
  const[versions,setVersions]=useState([]);
  const[versionsFor,setVersionsFor]=useState(null);
  const fileInputRef=useRef(null);

  const categories=useMemo(()=>categoriesForKind(form.document_kind),[form.document_kind]);
  const maxMb=Math.round(maxBytesForDocumentKind(form.document_kind)/(1024*1024));

  async function loadDocuments(){
    if(!profileId){setDocuments([]);setLoading(false);return}
    setLoading(true);
    try{
      const payload=await api(`/personnel-profiles/${encodeURIComponent(profileId)}/documents?include_archived=${showArchived?'true':'false'}`,{_retries:1});
      const rows=asDocumentRows(payload);
      setDocuments(rows);
      onError?.('');
      onCountChange?.(rows.filter((row)=>row.lifecycle_status!=='archived').length);
    }catch(error){
      onError?.(error?.message||'Personel belgeleri yüklenemedi.');
    }finally{setLoading(false)}
  }

  useEffect(()=>{void loadDocuments()},[profileId,showArchived]);

  function resetForm(){
    setForm(EMPTY_FORM);
    setFile(null);
    if(fileInputRef.current) fileInputRef.current.value='';
  }

  function changeKind(kind){
    setForm((current)=>({
      ...current,
      document_kind:kind,
      category:normalizeCategoryForKind(kind,current.category),
      title:current.document_key?current.title:'',
    }));
    setFile(null);
    if(fileInputRef.current) fileInputRef.current.value='';
  }

  function startNewVersion(row){
    setForm({
      document_kind:row.document_kind,
      category:row.category,
      title:row.title||'',
      document_key:row.document_key,
      document_number:row.document_number||'',
      issuing_organization:row.issuing_organization||'',
      issue_date:row.issue_date||'',
      valid_from:row.valid_from||'',
      expiration_date:row.expiration_date||'',
      no_expiration:Boolean(row.no_expiration),
      access_classification:row.access_classification||'internal_only',
      change_reason:'Belgenin yeni sürümü yüklendi',
    });
    setFile(null);
    if(fileInputRef.current) fileInputRef.current.value='';
    fileInputRef.current?.closest('.ppd-upload-card')?.scrollIntoView({behavior:'smooth',block:'start'});
  }

  async function submitUpload(event){
    event.preventDefault();
    if(!canWrite||!profileId) return;
    const fileError=validateDocumentFile(file,form.document_kind);
    if(fileError){onError?.(fileError);return}
    setActionBusy(true);onError?.('');onMessage?.('');
    try{
      const body=new FormData();
      body.append('file',file);
      for(const[key,value] of Object.entries(form)){
        if(key==='expiration_date'&&form.no_expiration) continue;
        if(value===''||value===null||value===undefined) continue;
        body.append(key,String(value));
      }
      await api(`/personnel-profiles/${encodeURIComponent(profileId)}/documents/upload`,{
        method:'POST',
        headers:{'Idempotency-Key':newIdempotencyKey()},
        body,
        _retries:0,
      });
      const wasVersion=Boolean(form.document_key);
      resetForm();
      await loadDocuments();
      onMessage?.(wasVersion?'Belgenin yeni sürümü kaydedildi; önceki sürüm korundu.':'Belge private depolamaya sürümlü olarak yüklendi.');
    }catch(error){onError?.(error?.message||'Belge yüklenemedi.')}
    finally{setActionBusy(false)}
  }

  async function archiveDocument(row){
    if(!canWrite||!profileId||!row?.document_key) return;
    const reason=String(window.prompt('Arşivleme gerekçesini yazın:','Belge kullanım dışı kaldı')||'').trim();
    if(!reason) return;
    if(reason.length<3){onError?.('Arşivleme gerekçesi en az 3 karakter olmalıdır.');return}
    setActionBusy(true);onError?.('');onMessage?.('');
    try{
      await api(`/personnel-profiles/${encodeURIComponent(profileId)}/documents/${encodeURIComponent(row.document_key)}/archive`,{
        method:'POST',
        headers:{'Idempotency-Key':newIdempotencyKey()},
        body:JSON.stringify({reason}),
        _retries:0,
      });
      await loadDocuments();
      onMessage?.('Belge fiziksel olarak silinmeden arşiv sürümüyle kapatıldı.');
    }catch(error){onError?.(error?.message||'Belge arşivlenemedi.')}
    finally{setActionBusy(false)}
  }

  async function downloadVersion(row){
    if(!profileId||!row?.id) return;
    setActionBusy(true);onError?.('');
    let url='';
    try{
      url=await authBlobUrl(`/personnel-profiles/${encodeURIComponent(profileId)}/document-versions/${encodeURIComponent(row.id)}/download`);
      const anchor=document.createElement('a');
      anchor.href=url;
      anchor.download=safeDocumentFilename(row);
      anchor.style.display='none';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      const completedUrl=url;
      window.setTimeout(()=>URL.revokeObjectURL(completedUrl),1000);
      url='';
      onMessage?.(`Belge sürüm ${row.version} indirildi.`);
    }catch(error){onError?.(error?.message||'Belge indirilemedi.')}
    finally{
      if(url) URL.revokeObjectURL(url);
      setActionBusy(false);
    }
  }

  async function openVersions(row){
    setActionBusy(true);onError?.('');onMessage?.('');
    try{
      const payload=await api(`/personnel-profiles/${encodeURIComponent(profileId)}/documents/${encodeURIComponent(row.document_key)}/versions`,{_retries:1});
      setVersions(asDocumentRows(payload));
      setVersionsFor(row);
    }catch(error){onError?.(error?.message||'Belge sürüm geçmişi yüklenemedi.')}
    finally{setActionBusy(false)}
  }

  if(loading) return <div className="ppd-loading"><RefreshCw className="is-spinning" size={22}/> Belgeler yükleniyor…</div>;

  return (
    <div className="ppd-layout">
      <section className="ppd-list-card">
        <div className="ppd-heading">
          <div><h5>Sertifikalar ve Belgeler</h5><p>Yalnız standart profesyonel belgeler; private R2/S3 depolama ve değişmez sürüm geçmişi.</p></div>
          <label className="ppd-archived-toggle"><input type="checkbox" checked={showArchived} onChange={(event)=>setShowArchived(event.target.checked)}/><span>Arşivlileri göster</span></label>
        </div>
        <div className="ppd-security-note"><ShieldCheck size={18}/><span>Sağlık, adli sicil, maaş, disiplin ve biyometrik belge yüklenemez. Dosyalar kalıcı public URL ile paylaşılmaz.</span></div>
        {documents.length===0?(
          <div className="ppd-empty"><FileText size={34}/><strong>Henüz belge yok</strong><p>Yönetici yetkisiyle ilk standart profesyonel belgeyi yükleyin.</p></div>
        ):(
          <div className="ppd-document-list">
            {documents.map((row)=><article key={`${row.document_key}-${row.version}`} className={row.lifecycle_status==='archived'?'is-archived':''}>
              <span className="ppd-document-icon"><DocumentIcon kind={row.document_kind}/></span>
              <div className="ppd-document-copy">
                <div><strong>{row.title}</strong><Badge>{documentCategoryLabel(row.category)}</Badge></div>
                <span>{metadataLine(row)||documentKindLabel(row.document_kind)}</span>
                <small>{formatDocumentBytes(row.file_size)} · Sürüm {row.version} · {verificationLabel(row.verification_status)}</small>
                <div><Badge tone={validityTone(row.validity_status)}>{validityLabel(row.validity_status)}</Badge><Badge>{row.access_classification==='internal_only'?'Yalnız iç kullanım':row.access_classification==='cv_eligible'?'CV için seçilebilir':'Paylaşım için seçilebilir'}</Badge></div>
              </div>
              <div className="ppd-actions">
                <button type="button" className="mini secondary" onClick={()=>downloadVersion(row)} disabled={actionBusy}><Download size={15}/>İndir</button>
                <button type="button" className="mini secondary" onClick={()=>openVersions(row)} disabled={actionBusy}><History size={15}/>Sürümler</button>
                {canWrite&&row.lifecycle_status!=='archived'&&<button type="button" className="mini secondary" onClick={()=>startNewVersion(row)} disabled={actionBusy}><FileUp size={15}/>Yeni sürüm</button>}
                {canWrite&&row.lifecycle_status!=='archived'&&<button type="button" className="mini danger" onClick={()=>archiveDocument(row)} disabled={actionBusy}><Archive size={15}/>Arşivle</button>}
              </div>
            </article>)}
          </div>
        )}
      </section>

      {canWrite&&<form className="ppd-upload-card" onSubmit={submitUpload}>
        <div className="ppd-heading"><div><h5>{form.document_key?'Yeni Belge Sürümü':'Belge Yükle'}</h5><p>{form.document_key?'Önceki dosya ve metadata geçmişte korunur.':'Dosya türü, içerik ve zararlı yazılım kontrollerinden sonra kaydedilir.'}</p></div>{form.document_key&&<button type="button" className="icon secondary" onClick={resetForm} aria-label="Yeni sürüm formunu kapat"><X size={18}/></button>}</div>
        <label><span>Belge türü</span><select value={form.document_kind} onChange={(event)=>changeKind(event.target.value)} disabled={Boolean(form.document_key)}>{DOCUMENT_KIND_OPTIONS.map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
        <label><span>Kategori</span><select value={form.category} onChange={(event)=>setForm({...form,category:event.target.value})} disabled={Boolean(form.document_key)}>{categories.map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
        <label><span>Başlık</span><input required minLength={2} maxLength={220} value={form.title} onChange={(event)=>setForm({...form,title:event.target.value})} placeholder="Örn. A Sınıfı İş Güvenliği Uzmanlığı Belgesi"/></label>
        <label className="ppd-file-input"><span>Dosya</span><input ref={fileInputRef} required type="file" accept={acceptForDocumentKind(form.document_kind)} onChange={(event)=>setFile(event.target.files?.[0]||null)}/><small>En fazla {maxMb} MB. Sunucu uzantı, gerçek içerik, AV ve bütünlük kontrolü yapar.</small></label>
        <div className="ppd-form-row"><label><span>Belge numarası</span><input maxLength={120} value={form.document_number} onChange={(event)=>setForm({...form,document_number:event.target.value})}/></label><label><span>Düzenleyen kurum</span><input maxLength={220} value={form.issuing_organization} onChange={(event)=>setForm({...form,issuing_organization:event.target.value})}/></label></div>
        <div className="ppd-form-row"><label><span>Düzenlenme tarihi</span><input type="date" value={form.issue_date} onChange={(event)=>setForm({...form,issue_date:event.target.value})}/></label><label><span>Geçerlilik başlangıcı</span><input type="date" value={form.valid_from} onChange={(event)=>setForm({...form,valid_from:event.target.value})}/></label></div>
        <label><span>Son geçerlilik tarihi</span><input type="date" value={form.expiration_date} disabled={form.no_expiration} onChange={(event)=>setForm({...form,expiration_date:event.target.value})}/></label>
        <label className="ppd-check"><input type="checkbox" checked={form.no_expiration} onChange={(event)=>setForm({...form,no_expiration:event.target.checked,expiration_date:event.target.checked?'':form.expiration_date})}/><span>Belge süresiz</span></label>
        <label><span>Görünürlük</span><select value={form.access_classification} onChange={(event)=>setForm({...form,access_classification:event.target.value})}><option value="internal_only">Yalnız iç kullanım</option><option value="cv_eligible">CV için seçilebilir</option><option value="share_eligible">Paylaşım için seçilebilir</option></select></label>
        {form.document_key&&<label><span>Değişiklik gerekçesi</span><input required minLength={3} maxLength={500} value={form.change_reason} onChange={(event)=>setForm({...form,change_reason:event.target.value})}/></label>}
        <button type="submit" disabled={actionBusy||!file}><Upload size={17}/>{actionBusy?'Yükleniyor…':form.document_key?'Yeni sürümü yükle':'Belgeyi yükle'}</button>
      </form>}

      {versionsFor&&<div className="ppd-version-overlay" role="dialog" aria-modal="true" aria-label="Belge sürüm geçmişi">
        <section className="ppd-version-dialog">
          <div className="ppd-heading"><div><h5>{versionsFor.title}</h5><p>Değişmez belge sürüm geçmişi</p></div><button type="button" className="icon secondary" onClick={()=>{setVersionsFor(null);setVersions([])}} aria-label="Sürüm geçmişini kapat"><X size={19}/></button></div>
          <div className="ppd-version-list">{versions.map((row)=><article key={row.id}><FileClock size={20}/><div><strong>Sürüm {row.version}</strong><span>{formatDate(row.created_at)} · {formatDocumentBytes(row.file_size)} · {validityLabel(row.validity_status)}</span><small>{row.change_reason||'İlk belge sürümü'}</small></div><button type="button" className="mini secondary" onClick={()=>downloadVersion(row)} disabled={actionBusy}><Download size={15}/>İndir</button></article>)}</div>
        </section>
      </div>}
    </div>
  );
}
