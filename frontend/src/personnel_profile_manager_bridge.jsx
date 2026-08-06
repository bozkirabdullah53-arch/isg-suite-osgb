import React from 'react';
import {createRoot} from 'react-dom/client';
import {api} from './api';
import {PersonnelProfileManagerWithDocuments} from './personnel_profile_documents_bridge';
import './personnel_profile_manager_bridge.css';

let mounted=null;
let resizing=false;

function rows(payload){
  return Array.isArray(payload)?payload:Array.isArray(payload?.rows)?payload.rows:Array.isArray(payload?.items)?payload.items:[];
}

async function resolveContext(){
  const[osgbPayload,user]=await Promise.all([
    api('/osgb',{_retries:1}),
    api('/auth/me',{_retries:1}),
  ]);
  const osgbId=Number(rows(osgbPayload)[0]?.id||0);
  if(!osgbId) throw new Error('OSGB kapsamı bulunamadı.');
  const readiness=await api(`/osgb-personnel-profiles/readiness?osgb_id=${encodeURIComponent(osgbId)}`,{_retries:1});
  if(!readiness?.enabled||!readiness?.visible||readiness?.scope!=='osgb_professionals_only'){
    throw new Error('Dijital Profesyonel Kartı bu OSGB için aktif değil.');
  }
  return {osgbId,user};
}

function positionHost(){
  if(!mounted?.host||resizing) return;
  resizing=true;
  requestAnimationFrame(()=>{
    resizing=false;
    if(!mounted?.host) return;
    const workspace=document.querySelector('.workspace');
    const rect=workspace?.getBoundingClientRect();
    mounted.host.style.left=`${Math.max(0,Math.round(rect?.left||0))}px`;
    mounted.host.style.top='0px';
    mounted.host.style.right='0px';
    mounted.host.style.bottom='0px';
  });
}

function closeManager(){
  if(!mounted) return;
  window.removeEventListener('resize',positionHost);
  document.removeEventListener('keydown',mounted.onKeydown);
  mounted.root.unmount();
  mounted.host.remove();
  mounted=null;
  document.body.style.removeProperty('overflow');
  const returnFocus=document.querySelector('[data-personnel-profile-nav="desktop"]');
  if(returnFocus instanceof HTMLElement) returnFocus.focus();
}

function mountManager({osgbId,user}){
  closeManager();
  const host=document.createElement('div');
  host.className='ppm-bridge-host';
  host.setAttribute('data-personnel-profile-manager','true');
  host.setAttribute('role','region');
  host.setAttribute('aria-label','OSGB Dijital Profesyonel Kartları');
  document.body.appendChild(host);
  const root=createRoot(host);
  const onKeydown=(event)=>{if(event.key==='Escape') closeManager()};
  mounted={host,root,onKeydown};
  root.render(
    <PersonnelProfileManagerWithDocuments
      user={user}
      context={{osgbId}}
      onClose={closeManager}
    />,
  );
  document.body.style.overflow='hidden';
  document.addEventListener('keydown',onKeydown);
  window.addEventListener('resize',positionHost);
  positionHost();
}

async function openManager(button){
  button?.setAttribute('aria-busy','true');
  try{
    const context=await resolveContext();
    const mobileClose=document.querySelector('.mobile-nav-sheet-head button');
    if(mobileClose instanceof HTMLElement) mobileClose.click();
    mountManager(context);
  }catch(error){
    window.alert(error?.message||'Dijital Profesyonel Kartları açılamadı.');
  }finally{
    button?.removeAttribute('aria-busy');
  }
}

document.addEventListener('click',(event)=>{
  const nav=event.target.closest?.('[data-personnel-profile-nav]');
  const pageEntry=event.target.closest?.('.personnel-profile-readonly-entry__button');
  const trigger=nav||pageEntry;
  if(!trigger) return;
  event.preventDefault();
  event.stopPropagation();
  event.stopImmediatePropagation();
  void openManager(trigger);
},true);

window.addEventListener('isg:auth-lost',closeManager);
