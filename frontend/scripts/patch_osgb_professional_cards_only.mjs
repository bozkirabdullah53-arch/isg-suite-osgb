import {readFileSync,writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const target=fileURLToPath(new URL('../src/personnel_profile_manager.jsx',import.meta.url));
let source=readFileSync(target,'utf8');
const marker='// OSGB_PROFESSIONAL_CARDS_ONLY_V1';
if(source.includes(marker)){
  console.log('OSGB professional card scope already applied.');
  process.exit(0);
}

function replaceExact(before,after,label){
  if(!source.includes(before)) throw new Error(`OSGB card patch target not found: ${label}`);
  source=source.replace(before,after);
}
function replaceRegex(pattern,after,label){
  if(!pattern.test(source)) throw new Error(`OSGB card patch target not found: ${label}`);
  source=source.replace(pattern,after);
}

source=`${marker}\n${source}`;
replaceExact('  buildPersonnelSubjects,','  buildOsgbProfessionalSubjects,','logic import');
replaceExact("  const[companies,setCompanies]=useState([]);\n",'', 'companies state');
replaceExact("  const[companyId,setCompanyId]=useState(null);\n",'  const[osgbId,setOsgbId]=useState(null);\n','scope state');
replaceExact("  const pilotIds=useMemo(()=>new Set(asRows(context?.pilotCompanyIds).map(Number).filter((id)=>id>0)),[context]);\n",'','pilot company state');

replaceRegex(
  /  useEffect\(\(\)=>\{\n    let cancelled=false;\n    \(async\(\)=>\{\n      setLoading\(true\);setError\(''\);\n      try\{[\s\S]*?\n  \},\[context,pilotIds\]\);/,
`  useEffect(()=>{\n    let cancelled=false;\n    (async()=>{\n      setLoading(true);setError('');\n      try{\n        const resolvedOsgbId=Number(context?.osgbId||0) || Number(asRows(await api('/osgb',{_retries:1}))[0]?.id||0);\n        if(!resolvedOsgbId) throw new Error('OSGB kapsamı bulunamadı.');\n        const[professionalPayload,assignmentPayload]=await Promise.all([\n          api(\`/osgb-personnel-profiles/professionals?osgb_id=\${encodeURIComponent(resolvedOsgbId)}\`,{_retries:1}),\n          api(\`/osgb/assignments?osgb_id=\${encodeURIComponent(resolvedOsgbId)}\`,{_retries:1}),\n        ]);\n        if(cancelled) return;\n        const professionalRows=asRows(professionalPayload);\n        const rows=buildOsgbProfessionalSubjects(professionalRows,resolvedOsgbId);\n        setOsgbId(resolvedOsgbId);\n        setProfessionals(professionalRows);\n        setAssignments(asRows(assignmentPayload));\n        setSubjects(rows);\n        setSelectedKey((current)=>rows.some((row)=>row.subjectKey===current)?current:(rows[0]?.subjectKey||''));\n      }catch(x){\n        if(!cancelled) setError(x?.message||'OSGB profesyonel kartları yüklenemedi.');\n      }finally{\n        if(!cancelled) setLoading(false);\n      }\n    })();\n    return()=>{cancelled=true};\n  },[context]);`,
  'initial OSGB load',
);

replaceRegex(
  /\n  useEffect\(\(\)=>\{\n    if\(!companyId\)\{setSubjects\(\[\]\);setSelectedKey\(''\);return undefined\}[\s\S]*?\n  \},\[companyId,professionals,assignments\]\);/,
  '',
  'employee/company load effect',
);

replaceExact(
`        const payload=selectedSubject.subjectType==='professional'\n          ? await api(\`/personnel-profiles/professional/\${selectedSubject.id}/summary?company_id=\${encodeURIComponent(companyId)}\`)\n          : await api(\`/personnel-profiles/employee/\${selectedSubject.id}/summary\`);`,
`        const payload=await api(\`/osgb-personnel-profiles/professional/\${selectedSubject.id}/summary\`);`,
'summary endpoint');
replaceExact('  },[selectedSubject,companyId]);','  },[selectedSubject]);','summary dependency');
replaceExact('    if(!selectedSubject||!companyId||!canWrite) return;','    if(!selectedSubject||!osgbId||!canWrite) return;','start guard');
replaceRegex(
  /      const result=await api\('\/personnel-profiles',\{\n        method:'POST',\n        body:JSON\.stringify\(\{[\s\S]*?\n        \}\),\n      \}\);/,
`      const result=await api(\`/osgb-personnel-profiles/professionals/\${selectedSubject.id}\`,{method:'POST'});`,
  'profile initialize',
);
replaceExact(
"    return assignments.filter((row)=>Number(row?.professional_id)===Number(selectedSubject.id)&&Number(row?.company_id)===Number(companyId));\n  },[assignments,selectedSubject,companyId]);",
"    return assignments.filter((row)=>Number(row?.professional_id)===Number(selectedSubject.id));\n  },[assignments,selectedSubject]);",
'assignment filter');

replaceExact('          <p>Mevcut personel ve İSG profesyoneli kayıtlarına bağlı, sürümlü ve yetki kontrollü profil yönetimi.</p>','          <p>Yalnız OSGB bünyesindeki iş güvenliği uzmanı, işyeri hekimi ve diğer sağlık personeli.</p>','header description');
replaceRegex(
  /        <label>\n          <span>İşyeri<\/span>[\s\S]*?        <\/label>\n/,
  '',
  'workplace selector',
);
replaceExact('<span>Personel ara</span>','<span>İSG profesyoneli ara</span>','search label');
replaceExact('placeholder="Ad, görev, meslek veya departman"','placeholder="Ad, profesyonel türü veya belge sınıfı"','search placeholder');
replaceExact('aria-label="Personel ve profesyonel listesi"','aria-label="OSGB İSG profesyonelleri listesi"','list aria');
replaceExact('<small>Personel + aktif atanmış profesyoneller</small>','<small>OSGB bünyesindeki İSG profesyonelleri</small>','list scope label');
replaceExact('description="Arama ölçütünü değiştirin veya mevcut Personel/İSG Profesyonelleri ekranından kayıt ekleyin."','description="Arama ölçütünü değiştirin veya İSG Profesyonelleri ekranından OSGB kadrosuna kayıt ekleyin."','empty list');
replaceExact('title="Personel seçin" description="Kart ayrıntılarını görüntülemek için soldaki listeden bir kayıt seçin."','title="İSG profesyoneli seçin" description="Dijital kartı görüntülemek için OSGB profesyonelleri listesinden bir kayıt seçin."','selection empty');
replaceExact("                  <span>{summary.subjectType==='professional'?'Profesyonel Personel Profili':'İşyeri Personel Kartı'}</span>","                  <span>OSGB Profesyonel Dijital Kartı</span>",'identity type');
replaceExact("                  <p>{summary.subjectType==='professional'?summary.professionalTypeLabel:[summary.jobTitle,summary.department].filter(Boolean).join(' · ')||'İşyeri personeli'}</p>","                  <p>{summary.professionalTypeLabel}</p>",'identity subtitle');
replaceExact('                      <SummaryField label="İşyeri" value={summary.companyName}/>\n','', 'workplace summary');
replaceExact('                      <SummaryField label="Şube" value={summary.branchName}/>\n','', 'branch summary');
replaceExact('                      <SummaryField label="Maskeli kimlik" value={summary.nationalIdentityMasked}/>\n','', 'employee identity summary');
replaceExact('                      <SummaryField label="Departman" value={summary.department}/>\n','', 'employee department summary');
replaceExact('                      <SummaryField label="İşe giriş" value={formatProfileDate(summary.employmentStartDate)}/>\n','', 'employee start summary');
replaceExact('                      <SummaryField label="Aktif görevlendirme" value={summary.subjectType===\'professional\'?String(summary.activeAssignmentCount):\'\'}/>','                      <SummaryField label="Aktif görevlendirme" value={String(summary.activeAssignmentCount)}/>','assignment summary');
replaceExact('Mevcut personel kaydı değişmez. Kartı başlattığınızda','Mevcut İSG profesyoneli kaydı değişmez. Kartı başlattığınızda','start copy');
replaceExact('aria-label="Personel kartı bölümleri"','aria-label="Profesyonel kartı bölümleri"','tabs aria');
replaceExact("<strong>{summary.companyName}</strong>","<strong>{row.company_name||row.companyName||`İşyeri #${row.company_id||''}`}</strong>",'assignment company');

if(source.includes('/employees?company_id=')||source.includes('Personel + aktif atanmış profesyoneller')||source.includes('const[companyId')){
  throw new Error('OSGB card patch failed closed: workplace employee/company code remains.');
}
writeFileSync(target,source,'utf8');
console.log('OSGB professional-only digital card scope applied.');
