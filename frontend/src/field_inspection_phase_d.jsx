import React,{useMemo,useState} from 'react';
import {WifiOff} from 'lucide-react';
import {FieldInspectionPage as LegacyFieldInspectionPage} from './field_inspection';
import {readFieldOfflineOptIn,writeFieldOfflineOptIn} from './field_offline_preference';

export function FieldInspectionPremiumPage({user}){
  const scope=useMemo(()=>({user_id:Number(user?.id)||0,osgb_id:Number(user?.osgb_id)||0}),[user?.id,user?.osgb_id]);
  const[enabled,setEnabled]=useState(()=>readFieldOfflineOptIn(scope));
  const offline=typeof navigator!=='undefined'&&navigator.onLine===false;
  if(offline&&!enabled){
    return <section className="field-inspection-page"><div className="field-empty"><WifiOff size={30}/><h2>Çevrimdışı saha modu kapalı</h2><p>Çalışan online akış değişmedi. İnternet yokken kayıtları cihazda tutmak için bu cihazda çevrimdışı saha moduna açıkça izin verin.</p><button type="button" onClick={()=>{writeFieldOfflineOptIn(scope,true);setEnabled(true)}}>Bu cihazda çevrimdışı modu aç</button></div></section>;
  }
  return <><div style={{display:'flex',justifyContent:'flex-end',padding:'6px 0 10px'}}><label style={{display:'flex',gap:8,alignItems:'center',fontSize:13}}><input type="checkbox" checked={enabled} onChange={e=>{writeFieldOfflineOptIn(scope,e.target.checked);setEnabled(e.target.checked)}}/> Çevrimdışı saha kuyruğuna izin ver</label></div><LegacyFieldInspectionPage user={user}/></>;
}
