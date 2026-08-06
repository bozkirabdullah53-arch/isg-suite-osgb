import {readFileSync,writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

function patchFile(relativePath,marker,apply){
  const target=fileURLToPath(new URL(relativePath,import.meta.url));
  let source=readFileSync(target,'utf8');
  if(source.includes(marker)){
    console.log(`${relativePath} OSGB professional scope already applied.`);
    return;
  }
  const replaceExact=(before,after,label)=>{
    if(!source.includes(before)) throw new Error(`${relativePath} target not found: ${label}`);
    source=source.replace(before,after);
  };
  const replaceRegex=(pattern,after,label)=>{
    if(!pattern.test(source)) throw new Error(`${relativePath} target not found: ${label}`);
    source=source.replace(pattern,after);
  };
  source=`${marker}\n${source}`;
  apply({replaceExact,replaceRegex,getSource:()=>source,setSource:(value)=>{source=value;}});
  writeFileSync(target,source,'utf8');
  console.log(`${relativePath} OSGB professional-only scope applied.`);
}

patchFile('../src/personnel_profile_manager.jsx','// OSGB_PROFESSIONAL_CARDS_ONLY_V2',({replaceExact,replaceRegex,getSource,setSource})=>{
  replaceExact('  buildPersonnelSubjects,','  buildOsgbProfessionalSubjects,','logic import');
  replaceExact("  const[companies,setCompanies]=useState([]);\n",'', 'companies state');
  replaceExact("  const[professionals,setProfessionals]=useState([]);\n",'', 'professionals state');
  replaceExact("  const[companyId,setCompanyId]=useState(null);\n",'  const[osgbId,setOsgbId]=useState(null);\n','scope state');
  replaceExact("  const pilotIds=useMemo(()=>new Set(asRows(context?.pilotCompanyIds).map(Number).filter((id)=>id>0)),[context]);\n",'','pilot company state');

  replaceRegex(
    /  useEffect\(\(\)=>\{\n    let cancelled=false;\n    \(async\(\)=>\{\n      setLoading\(true\);setError\(''\);\n      try\{[\s\S]*?\n  \},\[context,pilotIds\]\);/,
`  useEffect(()=>{\n    let cancelled=false;\n    (async()=>{\n      setLoading(true);setError('');\n      try{\n        const resolvedOsgbId=Number(context?.osgbId||0) || Number(asRows(await api('/osgb',{_retries:1}))[0]?.id||0);\n        if(!resolvedOsgbId) throw new Error('OSGB kapsamı bulunamadı.');\n        const[professionalPayload,assignmentPayload]=await Promise.all([\n          api(\`/osgb-personnel-profiles/professionals?osgb_id=\${encodeURIComponent(resolvedOsgbId)}\`,{_retries:1}),\n          api(\`/osgb/assignments?osgb_id=\${encodeURIComponent(resolvedOsgbId)}\`,{_retries:1}),\n        ]);\n        if(cancelled) return;\n        const rows=buildOsgbProfessionalSubjects(asRows(professionalPayload),resolvedOsgbId);\n        setOsgbId(resolvedOsgbId);\n        setAssignments(asRows(assignmentPayload));\n        setSubjects(rows);\n        setSelectedKey((current)=>rows.some((row)=>row.subjectKey===current)?current:(rows[0]?.subjectKey||''));\n      }catch(x){\n        if(!cancelled) setError(x?.message||'OSGB profesyonel kartları yüklenemedi.');\n      }finally{\n        if(!cancelled) setLoading(false);\n      }\n    })();\n    return()=>{cancelled=true};\n  },[context]);`,
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
    'summary endpoint',
  );
  replaceExact('  },[selectedSubject,companyId]);','  },[selectedSubject]);','summary dependency');
  replaceExact('    if(!selectedSubject||!companyId||!canWrite) return;','    if(!selectedSubject||!osgbId||!canWrite) return;','start guard');
  replaceRegex(
    /      const result=await api\('\/personnel-profiles',\{\n        method:'POST',\n        body:JSON\.stringify\(\{[\s\S]*?\n        \}\),\n      \}\);/,
`      const result=await api(\`/osgb-personnel-profiles/professionals/\${selectedSubject.id}\`,{method:'POST'});`,
    'profile initialize',
  );
  replaceExact(
"      await api(`/personnel-profiles/${snapshot.profile.id}/${entryType}/${encodeURIComponent(row.entry_key)}/archive`,{",
"      await api(`/osgb-personnel-profiles/${snapshot.profile.id}/entries/${entryType}/${encodeURIComponent(row.entry_key)}/archive`,{",
    'entry archive endpoint',
  );
  replaceExact(
"    return assignments.filter((row)=>Number(row?.professional_id)===Number(selectedSubject.id)&&Number(row?.company_id)===Number(companyId));\n  },[assignments,selectedSubject,companyId]);",
"    return assignments.filter((row)=>Number(row?.professional_id)===Number(selectedSubject.id));\n  },[assignments,selectedSubject]);",
    'assignment filter',
  );

  replaceExact('          <p>Mevcut personel ve İSG profesyoneli kayıtlarına bağlı, sürümlü ve yetki kontrollü profil yönetimi.</p>','          <p>Yalnız OSGB bünyesindeki iş güvenliği uzmanı, işyeri hekimi ve diğer sağlık personeli.</p>','header description');
  replaceRegex(/        <label>\n          <span>İşyeri<\/span>[\s\S]*?        <\/label>\n/,'','workplace selector');
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

  let current=getSource().replaceAll('/personnel-profiles/','/osgb-personnel-profiles/');
  setSource(current);
  const leftovers={
    employeeRoute:current.includes('/employees?company_id='),
    mergedHeading:current.includes('Personel + aktif atanmış profesyoneller'),
    companyState:current.includes('const[companyId'),
    legacyProfileRoute:current.includes('/personnel-profiles/'),
  };
  if(Object.values(leftovers).some(Boolean)){
    throw new Error(`OSGB manager patch failed closed: ${JSON.stringify(leftovers)}`);
  }
});

patchFile('../src/personnel_profile_documents.jsx','// OSGB_PROFESSIONAL_DOCUMENTS_ONLY_V1',({getSource,setSource})=>{
  const current=getSource().replaceAll('/personnel-profiles/','/osgb-personnel-profiles/');
  setSource(current);
  if(current.includes('/personnel-profiles/')) throw new Error('OSGB document patch failed closed.');
});

patchFile('../src/personnel_profile_readonly_bridge.js','// OSGB_PROFESSIONAL_NAV_ONLY_V1',({replaceExact,replaceRegex,getSource,setSource})=>{
  replaceExact(
`import {\n  employmentStatusLabel,\n  formatProfileDate,\n  normalizeEmployeeRows,\n  normalizePersonnelProfileSummary,\n  normalizeProfessionalRows,\n  shouldRenderPersonnelProfileEntry,\n} from './personnel_profile_readonly_logic';`,
`import {\n  employmentStatusLabel,\n  formatProfileDate,\n  normalizePersonnelProfileSummary,\n} from './personnel_profile_readonly_logic';\nimport {buildOsgbProfessionalSubjects} from './personnel_profile_manager_logic';`,
    'readonly imports',
  );
  replaceExact('const readinessCache = new Map();\n','', 'company readiness cache');
  replaceRegex(/\nasync function readiness\(companyId\) \{[\s\S]*?\n\}\n\nfunction entryAnchor/,'\nfunction entryAnchor','company readiness function');
  replaceRegex(/\nasync function attachEmployeeEntry\(heading\) \{[\s\S]*?\n\}\n\nasync function activeProfessionalContext/,'\nasync function activeProfessionalContext','employee card entry');
  replaceRegex(
    /async function activeProfessionalContext\(osgbId\) \{[\s\S]*?\n\}\n\nasync function resolveOsgbId/,
`async function activeProfessionalContext(osgbId) {\n  if (!osgbId) return null;\n  if (!osgbContextCache.has(osgbId)) {\n    const request = Promise.all([\n      api(\`/osgb-personnel-profiles/readiness?osgb_id=\${encodeURIComponent(osgbId)}\`, {_retries: 1}),\n      api(\`/osgb-personnel-profiles/professionals?osgb_id=\${encodeURIComponent(osgbId)}\`, {_retries: 1}),\n    ])\n      .then(([readinessPayload, professionalPayload]) => ({\n        active: Boolean(readinessPayload?.enabled && readinessPayload?.visible && readinessPayload?.scope === 'osgb_professionals_only'),\n        rows: buildOsgbProfessionalSubjects(professionalPayload, osgbId),\n      }))\n      .catch(() => null)\n      .then((context) => {\n        if (!context) osgbContextCache.delete(osgbId);\n        return context;\n      });\n    osgbContextCache.set(osgbId, request);\n  }\n  return osgbContextCache.get(osgbId);\n}\n\nasync function resolveOsgbId`,
    'OSGB professional context',
  );
  replaceExact("  if (!context?.rows?.length) {","  if (!context?.active || !context?.rows?.length) {",'professional entry active check');
  replaceExact("    title: 'Profesyonel Personel Profilleri',","    title: 'OSGB Profesyonel Dijital Kartları',",'professional entry title');
  replaceExact("    description: 'Pilot işyerlerine aktif atanmış uzman, hekim ve diğer sağlık personelinin minimum özetlerini görüntüler.',","    description: 'Yalnız OSGB bünyesindeki iş güvenliği uzmanı, işyeri hekimi ve diğer sağlık personeli.',",'professional entry description');
  replaceExact("    actionLabel: 'Profesyonel Profilleri Görüntüle',","    actionLabel: 'Profesyonel Kartlarını Görüntüle',",'professional entry action');
  replaceExact("        title: 'Profesyonel Personel Profilleri',","        title: 'OSGB Profesyonel Dijital Kartları',",'professional dialog title');
  replaceExact("        subtitle: `${context.rows.length} profesyonel · aktif görevlendirme kontrolü`,","        subtitle: `${context.rows.length} OSGB profesyoneli`,",'professional dialog subtitle');
  replaceExact(
`        loadSummary: (row) => api(\n          \`/personnel-profiles/professional/\${row.id}/summary?company_id=\${encodeURIComponent(row.companyId)}\`,\n        ),`,
`        loadSummary: (row) => api(\`/osgb-personnel-profiles/professional/\${row.id}/summary\`),`,
    'professional summary',
  );
  replaceRegex(
    /async function openNavigationCenter\(osgbId\) \{[\s\S]*?\n\}\n\nasync function attachNavigationEntries/,
`async function openNavigationCenter(osgbId) {\n  osgbContextCache.delete(osgbId);\n  const context = await activeProfessionalContext(osgbId);\n  if (!context?.active) throw new Error('Dijital Profesyonel Kartı bu OSGB için aktif değil.');\n  openDialog({\n    title: 'OSGB Profesyonel Dijital Kartları',\n    subtitle: \`\${context.rows.length} OSGB profesyoneli\`,\n    rows: context.rows,\n    emptyMessage: 'OSGB bünyesinde aktif İSG profesyoneli bulunamadı.',\n    loadSummary: (row) => api(\`/osgb-personnel-profiles/professional/\${row.id}/summary\`),\n  });\n}\n\nasync function attachNavigationEntries`,
    'navigation center',
  );
  replaceExact("  if (!context?.pilotCompanyIds?.length) {","  if (!context?.active) {",'navigation readiness');
  replaceExact("    button.title = 'Dijital Personel Kartı';","    button.title = 'OSGB Profesyonel Dijital Kartları';",'nav title');
  replaceExact("    button.innerHTML = `${navigationIcon()}<span>Dijital Personel Kartı</span>`;","    button.innerHTML = `${navigationIcon()}<span>Dijital Profesyonel Kartları</span>`;",'nav label');
  replaceExact("      openErrorDialog('Dijital Personel Kartı', error?.message || 'Kart merkezi yüklenemedi.');","      openErrorDialog('OSGB Profesyonel Dijital Kartları', error?.message || 'Kart merkezi yüklenemedi.');",'nav error');
  replaceExact(
`    const employeeHeading = pageHeading('Personel Yönetimi');\n    if (employeeHeading) {\n      await attachEmployeeEntry(employeeHeading);\n      return;\n    }`,
`    const employeeHeading = pageHeading('Personel Yönetimi');\n    if (employeeHeading) {\n      removeEntriesExcept('');\n      return;\n    }`,
    'disable workplace employee entry',
  );
  const current=getSource().replaceAll('/personnel-profiles/professional/','/osgb-personnel-profiles/professional/');
  setSource(current);
  const leftovers={
    employeeRoute:current.includes('/employees?company_id='),
    pilotCompany:current.includes('pilotCompanyIds'),
    employeeNormalizer:current.includes('normalizeEmployeeRows'),
    assignmentNormalizer:current.includes('normalizeProfessionalRows'),
  };
  if(Object.values(leftovers).some(Boolean)){
    throw new Error(`OSGB navigation patch failed closed: ${JSON.stringify(leftovers)}`);
  }
});
