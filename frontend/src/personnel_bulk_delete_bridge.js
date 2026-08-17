const TOOLBAR_ATTR='data-personnel-bulk-toolbar';
const FILTER_ATTR='data-personnel-status-filter';
const PROXY_DELETE_ATTR='data-personnel-bulk-delete-proxy';
const PROXY_CLEAR_ATTR='data-personnel-bulk-clear-proxy';
const PROXY_SELECT_ALL_ATTR='data-personnel-bulk-select-all-proxy';
let observer=null;
let timer=null;
let applying=false;

function isEmployeesRoute(){
  const hash=String(window.location.hash||'').replace(/^#/,'');
  const params=new URLSearchParams(hash);
  return params.get('m')==='employees';
}

function norm(value){
  return String(value||'').replace(/\s+/g,' ').trim();
}

function findEmployeeTable(){
  return Array.from(document.querySelectorAll('table')).find((table)=>{
    const head=norm(table.querySelector('thead')?.textContent).toLocaleUpperCase('tr-TR');
    return head.includes('AD SOYAD')&&head.includes('DURUM')&&head.includes('İŞLEM');
  })||null;
}

function findOriginalDeleteButton(){
  return Array.from(document.querySelectorAll('button')).find((button)=>{
    if(button.hasAttribute(PROXY_DELETE_ATTR)) return false;
    return /^Seçilenleri Kalıcı Sil\s*\(\d+\)$/i.test(norm(button.textContent));
  })||null;
}

function selectedCount(original){
  const match=norm(original?.textContent).match(/\((\d+)\)\s*$/);
  return match?Number(match[1]):0;
}

function clearSelection(table){
  const checked=Array.from(table?.querySelectorAll('tbody input[type="checkbox"]:checked')||[]);
  for(const box of checked){
    if(box instanceof HTMLInputElement) box.click();
  }
}

function selectVisibleRows(table){
  const rows=Array.from(table?.querySelectorAll('tbody tr')||[]);
  for(const row of rows){
    if(row.hidden||row.style.display==='none') continue;
    const box=row.querySelector('input[type="checkbox"]');
    if(box instanceof HTMLInputElement&&!box.checked&&!box.disabled) box.click();
  }
}

function rowStatus(row){
  const text=norm(row?.textContent).toLocaleLowerCase('tr-TR');
  if(text.includes('pasif')) return 'inactive';
  if(text.includes('aktif')) return 'active';
  return 'unknown';
}

function applyFilter(table,filter){
  if(!table) return;
  const rows=Array.from(table.querySelectorAll('tbody tr'));
  let visible=0;
  for(const row of rows){
    const status=rowStatus(row);
    const show=filter==='all'||(filter==='active'&&status!=='inactive')||(filter==='inactive'&&status==='inactive');
    row.hidden=!show;
    row.style.display=show?'':'none';
    if(show) visible+=1;
  }
  const toolbar=document.querySelector(`[${TOOLBAR_ATTR}]`);
  const countNode=toolbar?.querySelector('[data-personnel-visible-count]');
  if(countNode) countNode.textContent=`${visible} kayıt gösteriliyor`;
}

function installStyles(){
  if(document.getElementById('personnel-bulk-delete-bridge-style')) return;
  const style=document.createElement('style');
  style.id='personnel-bulk-delete-bridge-style';
  style.textContent=`
    [${TOOLBAR_ATTR}] {
      display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;
      margin:12px 0; padding:12px 14px; border:1px solid rgba(15,118,110,.24);
      border-radius:14px; background:rgba(240,253,250,.92); box-shadow:0 8px 24px rgba(15,118,110,.08);
    }
    [${TOOLBAR_ATTR}] .personnel-bulk-left,[${TOOLBAR_ATTR}] .personnel-bulk-right{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
    [${TOOLBAR_ATTR}] label{display:flex;align-items:center;gap:8px;font-weight:700;color:#134e4a}
    [${TOOLBAR_ATTR}] select{min-width:150px;padding:9px 34px 9px 10px;border:1px solid #99d8d0;border-radius:10px;background:#fff;color:#0f3f3a;font:inherit}
    [${PROXY_DELETE_ATTR}]{background:#b91c1c!important;border-color:#991b1b!important;color:#fff!important;font-weight:800!important;box-shadow:0 8px 20px rgba(185,28,28,.18)!important}
    [${PROXY_DELETE_ATTR}]:disabled{opacity:.45!important;cursor:not-allowed!important;box-shadow:none!important}
    [${PROXY_CLEAR_ATTR}]{font-weight:700!important}
    [data-personnel-visible-count]{font-size:13px;font-weight:700;color:#52706d}
    @media (max-width:760px){[${TOOLBAR_ATTR}]{align-items:stretch}[${TOOLBAR_ATTR}] .personnel-bulk-left,[${TOOLBAR_ATTR}] .personnel-bulk-right{width:100%}[${PROXY_DELETE_ATTR}],[${PROXY_CLEAR_ATTR}]{flex:1}}
  `;
  document.head.appendChild(style);
}

function buildToolbar(table){
  const toolbar=document.createElement('div');
  toolbar.setAttribute(TOOLBAR_ATTR,'');
  toolbar.setAttribute('role','region');
  toolbar.setAttribute('aria-label','Personel toplu işlemleri');

  const left=document.createElement('div');
  left.className='personnel-bulk-left';
  const label=document.createElement('label');
  label.textContent='Personel görünümü';
  const filter=document.createElement('select');
  filter.setAttribute(FILTER_ATTR,'');
  filter.setAttribute('aria-label','Personel durum filtresi');
  filter.innerHTML='<option value="active">Aktif personel</option><option value="inactive">Pasif / arşiv</option><option value="all">Tümü</option>';
  filter.value='active';
  filter.addEventListener('change',()=>{
    clearSelection(table);
    applyFilter(table,filter.value);
  });
  label.appendChild(filter);
  const count=document.createElement('span');
  count.setAttribute('data-personnel-visible-count','');
  left.append(label,count);

  const right=document.createElement('div');
  right.className='personnel-bulk-right';
  const selectAll=document.createElement('button');
  selectAll.type='button';
  selectAll.className='secondary';
  selectAll.setAttribute(PROXY_SELECT_ALL_ATTR,'');
  selectAll.textContent='Görünenlerin Tümünü Seç';
  selectAll.addEventListener('click',()=>selectVisibleRows(table));

  const clear=document.createElement('button');
  clear.type='button';
  clear.className='secondary';
  clear.setAttribute(PROXY_CLEAR_ATTR,'');
  clear.textContent='Seçimi Temizle';
  clear.addEventListener('click',()=>clearSelection(table));

  const remove=document.createElement('button');
  remove.type='button';
  remove.setAttribute(PROXY_DELETE_ATTR,'');
  remove.textContent='Seçilenleri Kalıcı Sil (0)';
  remove.disabled=true;
  remove.title='Seçili aktif veya pasif bağlantısız personelleri kalıcı olarak siler.';
  remove.addEventListener('click',()=>{
    const original=findOriginalDeleteButton();
    if(!original||original.disabled) return;
    original.click();
  });

  right.append(selectAll,clear,remove);
  toolbar.append(left,right);
  const parent=table.parentElement||table;
  parent.insertBefore(toolbar,table);
  return toolbar;
}

function syncToolbar(){
  if(applying||!isEmployeesRoute()) return;
  applying=true;
  try{
    installStyles();
    const table=findEmployeeTable();
    if(!table) return;
    let toolbar=document.querySelector(`[${TOOLBAR_ATTR}]`);
    if(!toolbar||!toolbar.isConnected) toolbar=buildToolbar(table);

    const original=findOriginalDeleteButton();
    const proxy=toolbar.querySelector(`[${PROXY_DELETE_ATTR}]`);
    const clear=toolbar.querySelector(`[${PROXY_CLEAR_ATTR}]`);
    const count=selectedCount(original);
    if(proxy){
      proxy.textContent=`Seçilenleri Kalıcı Sil (${count})`;
      proxy.disabled=!original||original.disabled||count<1;
    }
    if(clear) clear.disabled=count<1;

    const filter=toolbar.querySelector(`[${FILTER_ATTR}]`);
    applyFilter(table,filter?.value||'active');
  }finally{
    applying=false;
  }
}

function cleanupOutsideRoute(){
  if(isEmployeesRoute()) return;
  document.querySelectorAll(`[${TOOLBAR_ATTR}]`).forEach((node)=>node.remove());
}

function scheduleSync(){
  if(timer) return;
  timer=window.setTimeout(()=>{
    timer=null;
    cleanupOutsideRoute();
    syncToolbar();
  },90);
}

observer=new MutationObserver(scheduleSync);
observer.observe(document.documentElement,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:['disabled','checked']});
window.addEventListener('hashchange',scheduleSync);
scheduleSync();

if(import.meta.hot){
  import.meta.hot.dispose(()=>{
    observer?.disconnect();
    window.removeEventListener('hashchange',scheduleSync);
    if(timer) window.clearTimeout(timer);
    document.querySelectorAll(`[${TOOLBAR_ATTR}]`).forEach((node)=>node.remove());
    document.getElementById('personnel-bulk-delete-bridge-style')?.remove();
  });
}
