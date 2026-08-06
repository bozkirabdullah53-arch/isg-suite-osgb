import React from 'react';
import {createRoot} from 'react-dom/client';
import {api} from './api';
import {shouldRenderPersonnelProfileEntry} from './personnel_profile_readonly_logic';
import {PersonnelProfileManagerPage} from './personnel_profile_manager';
import './personnel_profile_manager_bridge.css';

let mounted=null;
let resizing=false;

function rows(payload){
  return Array.isArray(payload)?payload:Array.isArray(payload?.rows)?payload.rows:[];
}

async function resolveContext(){
  const[osgbPayload,companyPayload,user]=await Promise.all([
    api('/osgb',{_retries:1}),
    api('/companies',{_retries:1}),
    api('/auth/me',{_retries:1}),
  ]);
  const osgbId=Number(rows(osgbPayload)[0]?.id||0);
  if(!osgbId) throw new Error('OSGB kapsamı bulunamadı.');
  const companyIds=rows(companyPayload).map((row)=>Number(row?.id||0)).filter((id)=>id>0).slice(0,50);
  const readiness=await Promise.all(companyIds.map(async(companyId)=>{
    try{
      const payload=await api(`/personnel-profiles/readiness?company_id=${encodeURIComponent(companyId)}`,{_retries:1});
      return shouldRenderPersonnelProfileEntry(payload)?companyId:null;
    }catch{return null}
  }));
  const pilotCompanyIds=readiness.filter((id)=>Number(id)>0);
  if(!pilotCompanyIds.length) throw new Error('Dijital Personel Kartı bu OSGB için aktif değil.');
  return {osgbId,pilotCompanyIds,user};
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

function mountManager({osgbId,pilotCompanyIds,user}){
  closeManager();
  const host=document.createElement('div');
  host.className='ppm-bridge-host';
  host.setAttribute('data-personnel-profile-manager','true');
  host.setAttribute('role','region');
  host.setAttribute('aria-label','Dijital Personel Yönetimi');
  document.body.appendChild(host);
  const root=createRoot(host);
  const onKeydown=(event)=>{if(event.key==='Escape') closeManager()};
  mounted={host,root,onKeydown};
  root.render(
    <PersonnelProfileManagerPage
      user={user}
      context={{osgbId,pilotCompanyIds}}
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
    window.alert(error?.message||'Dijital Personel Yönetimi açılamadı.');
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
