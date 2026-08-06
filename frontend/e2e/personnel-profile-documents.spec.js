import {test,expect} from '@playwright/test';

const readiness={
  readiness_version:'personnel-profile-readiness-v1',company_id:35,enabled:true,visible:true,read_only:true,
  rollout:{global_enabled:true,force_off:false,allowlist_configured:true,pilot_company:true,active:true},
  capabilities:{employee_summary:true,professional_summary:true,profile_record_management:true,file_upload:true,cv_generation:false,external_sharing:false,restricted_data:false},
};
const summary={
  summary_version:'personnel-profile-summary-v1',subject:{type:'employee',id:41},
  scope:{company_id:35,company_name:'Test İşyerim',branch_id:null,branch_name:null},
  profile:{full_name:'Ayşe Yılmaz',national_identity_masked:'123******90',job_title:'Kaynakçı',department:'Üretim',employment_start_date:'2024-01-15',employment_status:'active'},
  privacy:{data_minimized:true,national_identity_full_included:false,special_status_included:false,health_data_included:false,criminal_record_included:false,restricted_documents_included:false},
};
const snapshot={
  profile:{id:55,osgb_id:4,company_id:35,branch_id:null,subject_type:'employee',employee_id:41,professional_id:null,user_id:null,status:'active',created_at:'2026-08-06T12:00:00',archived_at:null},
  contacts:[],competencies:[],experiences:[],
  privacy:{ordinary_professional_data_only:true,national_identity_included:false,home_address_included:false,emergency_contact_included:false,health_data_included:false,criminal_record_included:false,salary_included:false,disciplinary_data_included:false,documents_included:false,external_sharing_enabled:false},
};
const documents={items:[{
  id:301,profile_id:55,document_key:'11111111-1111-4111-a111-111111111111',version:1,supersedes_id:null,
  document_kind:'certificate',category:'first_aid_certificate',title:'İlk Yardımcı Belgesi',document_number:'IY-2026-15',issuing_organization:'Yetkili Eğitim Merkezi',issue_date:'2026-01-10',valid_from:'2026-01-10',expiration_date:'2029-01-10',no_expiration:false,mime_type:'application/pdf',file_extension:'.pdf',file_size:245760,checksum_sha256:'a'.repeat(64),access_classification:'internal_only',verification_status:'unverified',lifecycle_status:'active',validity_status:'valid',processing_purpose:'professional_profile_management',retention_policy:'personnel_profile_ordinary_v1',change_reason:null,created_at:'2026-08-06T12:10:00',
}]};

async function installRoutes(page){
  const json=(route,body)=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  await page.route('**/health',(route)=>json(route,{ok:true}));
  await page.route('**/api/v1/auth/me',(route)=>json(route,{id:2,full_name:'OSGB Yönetici',role:'company_admin',osgb_id:4}));
  await page.route('**/api/v1/osgb',(route)=>json(route,[{id:4,name:'Test OSGB'}]));
  await page.route('**/api/v1/companies',(route)=>json(route,[{id:35,name:'Test İşyerim'}]));
  await page.route('**/api/v1/osgb/professionals?osgb_id=4',(route)=>json(route,[]));
  await page.route('**/api/v1/osgb/assignments?osgb_id=4',(route)=>json(route,[]));
  await page.route('**/api/v1/personnel-profiles/readiness?company_id=35',(route)=>json(route,readiness));
  await page.route('**/api/v1/employees?company_id=35&include_inactive=true',(route)=>json(route,[{id:41,full_name:'Ayşe Yılmaz',national_id_masked:'12345678990',job_title:'Kaynakçı',department:'Üretim',is_active:true}]));
  await page.route('**/api/v1/personnel-profiles/employee/41/summary',(route)=>json(route,summary));
  await page.route('**/api/v1/personnel-profiles/55',(route)=>json(route,snapshot));
  await page.route('**/api/v1/personnel-profiles/55/documents?include_archived=false',(route)=>json(route,documents));
  await page.route('**/api/v1/personnel-profiles',(route)=>{
    if(route.request().method()==='POST') return json(route,{created:true,profile:snapshot.profile,privacy:snapshot.privacy});
    return route.fallback();
  });
}

async function injectDesktopShell(page){
  await page.evaluate(()=>{
    document.body.innerHTML=`<div class="app-shell"><aside><nav class="nav-desktop"><button data-nav="osgb_dashboard"><span>OSGB Ana Panel</span></button><button data-nav="companies"><span>İşyerleri</span></button><button data-nav="professionals"><span>İSG Profesyonelleri</span></button><button data-nav="assignments"><span>Görevlendirmeler</span></button></nav></aside><section class="workspace"><main><h3>OSGB Ana Panel</h3></main></section></div>`;
  });
}

test('document tab renders private metadata list and upload controls',async({page})=>{
  await installRoutes(page);
  await page.goto('/');
  await injectDesktopShell(page);
  await page.locator('[data-personnel-profile-nav="desktop"]').click();
  const manager=page.locator('[data-personnel-profile-manager="true"]');
  await manager.getByRole('button',{name:/Kartı başlat/}).click();
  await expect(manager.getByText('Profil #55',{exact:true})).toBeVisible();
  await manager.getByRole('button',{name:'Belgeler'}).click();
  await expect(manager.locator('[data-personnel-profile-documents-panel="true"]')).toBeVisible();
  await expect(manager.getByText('İlk Yardımcı Belgesi',{exact:true})).toBeVisible();
  await expect(manager.getByText('Yalnız iç kullanım',{exact:true})).toBeVisible();
  await expect(manager.getByRole('heading',{name:'Belge Yükle'})).toBeVisible();
  expect(await manager.innerHTML()).not.toContain('object_key');
  expect(await manager.innerHTML()).not.toContain('12345678990');
});
