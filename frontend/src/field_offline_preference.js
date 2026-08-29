const KEY='isg_field_offline_opt_in_v1';

function scopedKey(scope={}){
  const user=Number(scope.user_id)||0;
  const osgb=Number(scope.osgb_id)||0;
  return `${KEY}:${user}:${osgb}`;
}

export function readFieldOfflineOptIn(scope={}){
  try{return globalThis.localStorage?.getItem(scopedKey(scope))==='1'}catch{return false}
}

export function writeFieldOfflineOptIn(scope={},enabled=false){
  try{globalThis.localStorage?.setItem(scopedKey(scope),enabled?'1':'0')}catch{/* storage unavailable */}
  return !!enabled;
}
