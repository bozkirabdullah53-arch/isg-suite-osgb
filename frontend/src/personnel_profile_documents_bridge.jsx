import React,{useEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {PersonnelProfileManagerPage} from './personnel_profile_manager';
import {PersonnelProfileDocumentsPanel} from './personnel_profile_documents';

function parseVisibleProfileId(container){
  const pills=[...container.querySelectorAll('.ppm-status--info')];
  for(const pill of pills){
    const match=String(pill.textContent||'').trim().match(/^Profil\s+#(\d+)$/i);
    if(match) return Number(match[1]);
  }
  return 0;
}

function documentsTabIsActive(container){
  return [...container.querySelectorAll('.ppm-tabs button')].some((button)=>
    button.classList.contains('is-active')&&String(button.textContent||'').trim()==='Belgeler',
  );
}

function findDocumentsPlaceholder(container){
  return [...container.querySelectorAll('.ppm-tab-content .ppm-capability-notice')].find((node)=>
    String(node.textContent||'').includes('Sertifikalar ve Belgeler'),
  )||null;
}

export function PersonnelProfileManagerWithDocuments(props){
  const wrapperRef=useRef(null);
  const[portalTarget,setPortalTarget]=useState(null);
  const[profileId,setProfileId]=useState(0);
  const[panelError,setPanelError]=useState('');
  const[panelMessage,setPanelMessage]=useState('');
  const canWrite=['global_admin','company_admin'].includes(String(props?.user?.role||''));

  useEffect(()=>{
    const container=wrapperRef.current;
    if(!container) return undefined;
    let currentTarget=null;
    let currentPlaceholder=null;

    const cleanupTarget=()=>{
      if(currentPlaceholder) currentPlaceholder.hidden=false;
      currentPlaceholder=null;
      if(currentTarget?.isConnected) currentTarget.remove();
      currentTarget=null;
      setPortalTarget(null);
      setProfileId(0);
      setPanelError('');
      setPanelMessage('');
    };

    const sync=()=>{
      const active=documentsTabIsActive(container);
      const resolvedProfileId=parseVisibleProfileId(container);
      const placeholder=findDocumentsPlaceholder(container);
      if(!active||!resolvedProfileId||!placeholder){
        if(currentTarget) cleanupTarget();
        return;
      }
      if(currentTarget&&currentTarget.isConnected&&resolvedProfileId===profileId) return;
      cleanupTarget();
      const target=document.createElement('div');
      target.setAttribute('data-personnel-profile-documents-panel','true');
      placeholder.hidden=true;
      placeholder.insertAdjacentElement('afterend',target);
      currentPlaceholder=placeholder;
      currentTarget=target;
      setProfileId(resolvedProfileId);
      setPortalTarget(target);
    };

    const observer=new MutationObserver(sync);
    observer.observe(container,{childList:true,subtree:true,attributes:true,attributeFilter:['class','hidden']});
    const clickHandler=()=>window.setTimeout(sync,0);
    container.addEventListener('click',clickHandler);
    sync();
    return()=>{
      observer.disconnect();
      container.removeEventListener('click',clickHandler);
      if(currentPlaceholder) currentPlaceholder.hidden=false;
      if(currentTarget?.isConnected) currentTarget.remove();
    };
  },[profileId]);

  return (
    <div ref={wrapperRef} style={{height:'100%'}}>
      <PersonnelProfileManagerPage {...props}/>
      {portalTarget&&profileId>0&&createPortal(
        <div>
          {panelError&&<div className="ppm-alert ppm-alert--error" role="alert">{panelError}</div>}
          {panelMessage&&<div className="ppm-alert ppm-alert--success" role="status">{panelMessage}</div>}
          <PersonnelProfileDocumentsPanel
            profileId={profileId}
            canWrite={canWrite}
            onError={setPanelError}
            onMessage={setPanelMessage}
          />
        </div>,
        portalTarget,
      )}
    </div>
  );
}

export const personnelProfileDocumentsBridgeTestables={
  parseVisibleProfileId,
  documentsTabIsActive,
  findDocumentsPlaceholder,
};
