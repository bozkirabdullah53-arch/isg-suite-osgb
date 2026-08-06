import {readFileSync,writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const target=fileURLToPath(new URL('../src/personnel_profile_readonly_bridge.js',import.meta.url));
let source=readFileSync(target,'utf8');
const marker='// OSGB_CONTEXT_ERROR_DIAGNOSTIC_V1';
if(source.includes(marker)){
  console.log('OSGB context error diagnostic already applied.');
  process.exit(0);
}
const before='.catch(() => null)';
if(!source.includes(before)){
  throw new Error('OSGB context diagnostic target not found; refusing silent fallback.');
}
source=`${marker}\n${source.replace(
  before,
  ".catch((error) => { console.error('OSGB professional card context failed', error); return null; })",
)}`;
writeFileSync(target,source,'utf8');
console.log('OSGB context errors are now visible while remaining fail-closed.');
