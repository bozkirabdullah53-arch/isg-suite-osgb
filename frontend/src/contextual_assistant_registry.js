/* Stable semantic page/capability registry for the independent OSGB app. */
function truthy(value) { return String(value || '').trim().toLowerCase() === 'true'; }

export function assistantFeatureEnabled(env = import.meta.env) {
  if (truthy(env?.VITE_CONTEXTUAL_ASSISTANT_FORCE_OFF)) return false;
  return true;
}

const PAGES = {
  eisa_overview: {title: 'Genel Bakış', purpose: 'İDEA platform özetini ve yönetim durumunu gösterir.', suggestions: ['Bu panel ne işe yarar?', 'İşyeri yönetimine git', 'Eğitimlere git'], capabilities: ['dashboard.open_companies', 'dashboard.open_training']},
  osgb_dashboard: {title: 'OSGB Ana Panel', purpose: 'OSGB operasyonlarını ve günlük işleri özetler.', suggestions: ['İşyeri nasıl eklenir?', 'Personel yönetimine git', 'Eğitimlere git'], capabilities: ['company.create', 'dashboard.open_employees', 'dashboard.open_training']},
  dashboard: {title: 'İSG Özeti', purpose: 'Günlük İSG durumunu ve öncelikli işleri özetler.', suggestions: ['Bugün nereden başlamalıyım?', 'Risk analizini aç', 'Personel yönetimine git'], capabilities: ['dashboard.open_risk', 'dashboard.open_employees', 'dashboard.open_training']},
  companies: {title: 'İşyerleri', purpose: 'İşyeri kayıtlarını, NACE bilgisini ve erişimleri yönetir.', suggestions: ['Yeni işyeri nasıl eklenir?', 'NACE kodu ne işe yarar?', 'İşyeri durumunu aç'], capabilities: ['company.create', 'company.edit', 'company.select', 'company.open_status']},
  employees: {title: 'Personel', purpose: 'Seçili işyerinin çalışan kayıtlarını yönetir.', suggestions: ['Personel nasıl eklenir?', 'Excel ile personel nasıl yüklenir?', 'Neden personel görünmüyor?'], capabilities: ['employee.create', 'employee.import_excel', 'employee.edit', 'employee.training.assign']},
  training: {title: 'Eğitimler', purpose: 'İSG eğitimlerini planlar, katılımcıları ve belgeleri takip eder.', suggestions: ['Eğitim nasıl oluşturulur?', 'Çalışanlara eğitim nasıl atanır?', 'Sınav nasıl oluşturulur?'], capabilities: ['training.create', 'training.assign', 'exam.generate', 'training.remote']},
  remote_training: {title: 'Uzaktan Eğitim / Belgeler', purpose: 'Uzaktan eğitim paketlerini ve belge çıktılarını yönetir.', suggestions: ['Uzaktan eğitim nedir?', 'Belge çıktıları nerede?', 'Eğitimlere dön'], capabilities: ['training.remote', 'training.create']},
  risk: {title: 'Risk Analizi', purpose: 'Risk değerlendirmelerini, tehlikeleri ve DÖF kayıtlarını yönetir.', suggestions: ['Risk kaydı nasıl oluşturulur?', 'Risk puanı ne anlama gelir?', 'DÖF bölümüne git'], capabilities: ['risk.create', 'risk.review', 'corrective_action.create', 'risk.report']},
  near_miss: {title: 'Ramak Kala', purpose: 'Ramak kala olaylarını kaydetmeye ve izlemeye yarar.', suggestions: ['Ramak kala kaydı nasıl açılır?', 'Bir sonraki adım ne?', 'Risk analizine git'], capabilities: ['near_miss.create', 'risk.open']},
  accident: {title: 'İş Kazaları', purpose: 'İş kazası ve olay kayıtlarını takip eder.', suggestions: ['Kaza kaydı nasıl oluşturulur?', 'Eksik alanları nasıl kontrol ederim?', 'Raporlara git'], capabilities: ['accident.create', 'accident.review', 'reports.open']},
  capa: {title: 'DÖF', purpose: 'Düzeltici ve önleyici faaliyetleri takip eder.', suggestions: ['Yeni DÖF nasıl açılır?', 'Açık faaliyetleri göster', 'Risk analizine git'], capabilities: ['corrective_action.create', 'corrective_action.complete', 'risk.open']},
  visits: {title: 'Saha Takvimi', purpose: 'İSG saha ziyaretlerini ve planlanan işleri gösterir.', suggestions: ['Bugünkü ziyaretleri göster', 'Saha denetimine git', 'QR işlemleri nerede?'], capabilities: ['visit.view', 'field_inspection.open']},
  field_inspection: {title: 'Saha Denetimi', purpose: 'Fotoğraflı saha tespitlerini ve denetim raporlarını yönetir.', suggestions: ['Denetime nasıl başlarım?', 'Fotoğraf nasıl eklenir?', 'Tespit kaydı nasıl tamamlanır?'], capabilities: ['field_inspection.create', 'field_inspection.add_photo', 'risk.open']},
  health: {title: 'Sağlık', purpose: 'Yetkili sağlık kullanıcıları için sağlık kayıtlarını gösterir.', suggestions: ['Bu ekranda hangi kayıtlar var?', 'Muayeneye nasıl ulaşırım?', 'Yetki neden gerekli?'], capabilities: ['medical_exam.view', 'health.record.view']},
  documents: {title: 'Dokümanlar', purpose: 'İSG dokümanlarının arşiv ve geçerlilik takibini yapar.', suggestions: ['Yeni doküman nasıl eklenir?', 'Geçerlilik tarihi ne işe yarar?', 'Raporlara git'], capabilities: ['document.create', 'document.view', 'reports.open']},
  reports: {title: 'Raporlar', purpose: 'OSGB operasyon ve performans özetlerini sunar.', suggestions: ['Bu rapor neyi gösteriyor?', 'Personel raporuna git', 'Risk raporuna git'], capabilities: ['reports.open', 'employee.report', 'risk.report']},
};

const TITLES = {professionals: 'İSG Profesyonelleri', assignments: 'Görevlendirmeler', employer_oversight: 'İşyeri Denetim Durumu', workplace_status: 'İşyeri Durum Merkezi', pro_performance: 'Performans Raporu', csgb_audit: 'ÇSGB Belge Paketi', capacity_engine: 'Kapasite Motoru', mevzuat: 'Mevzuat Özeti', branches: 'Şubeler', ppe: 'KKD Takip', sds: 'SDS / PKD', tatbikat: 'Tatbikat Yönetimi', acil_ekipler: 'Acil Durum Ekipleri', acil_plan: 'Acil Durum Planı', periyodik_kontrol: 'Periyodik Kontrol', ortam_olcum: 'Ortam Ölçüm', isg_kurulu: 'İSG Kurulu', belge_onay: 'Belge Onay / İmza', employee_training: 'Çalışan Eğitimleri', employee_self_service: 'Çalışan Panelim', prescriptions: 'e-Reçete', annual_plans: 'Yıllık Plan', annual_eval_report: 'Yıllık Değerlendirme Raporu', specialist_reports: 'Uzman Rapor Merkezi', notifications: 'Bildirimler', subscription: 'Abonelik', security: 'Güvenlik', users: 'Kullanıcılar', work_permits: 'Çalışma İzinleri', contractors: 'Taşeron Yönetimi', visitors: 'Ziyaretçiler', customer_portal: 'Müşteri Portalı', finance: 'Finans', contracts: 'Sözleşmeler', crm: 'CRM / Teklif'};

const CAPABILITIES = {
  'dashboard.open_risk': {id: 'dashboard.open_risk', label: 'Risk Analizini Aç', module: 'risk', targetId: 'navigation.risk'},
  'dashboard.open_companies': {id: 'dashboard.open_companies', label: 'İşyeri Yönetimine Git', module: 'companies', targetId: 'navigation.companies'},
  'dashboard.open_employees': {id: 'dashboard.open_employees', label: 'Personel Yönetimine Git', module: 'employees', targetId: 'navigation.employees'},
  'dashboard.open_training': {id: 'dashboard.open_training', label: 'Eğitimlere Git', module: 'training', targetId: 'navigation.training'},
  'employee.create': {id: 'employee.create', label: 'Personel Ekle', module: 'employees', targetId: 'employee.create'},
  'employee.import_excel': {id: 'employee.import_excel', label: 'Excel ile Yükle', module: 'employees', targetId: 'employee.import_excel'},
  'employee.edit': {id: 'employee.edit', label: 'Personeli Düzenle', module: 'employees', targetId: 'employee.edit'},
  'employee.training.assign': {id: 'employee.training.assign', label: 'Eğitim Ata', module: 'training', targetId: 'navigation.training'},
  'company.create': {id: 'company.create', label: 'İşyeri Ekle', module: 'companies', targetId: 'company.create'},
  'company.edit': {id: 'company.edit', label: 'İşyeri Düzenle', module: 'companies', targetId: 'company.edit'},
  'company.select': {id: 'company.select', label: 'İşyeri Seç', module: 'companies', targetId: 'company.select'},
  'company.open_status': {id: 'company.open_status', label: 'İşyeri Durumunu Aç', module: 'workplace_status', targetId: 'navigation.workplace_status'},
  'training.create': {id: 'training.create', label: 'Eğitim Oluştur', module: 'training', targetId: 'training.create'},
  'training.assign': {id: 'training.assign', label: 'Çalışanlara Ata', module: 'training', targetId: 'training.assign'},
  'exam.generate': {id: 'exam.generate', label: 'Sınav Oluştur', module: 'training', targetId: 'training.generate_exam'},
  'training.remote': {id: 'training.remote', label: 'Uzaktan Eğitim Belgelerine Git', module: 'remote_training', targetId: 'navigation.remote_training'},
  'risk.create': {id: 'risk.create', label: 'Risk Kaydı Oluştur', module: 'risk', targetId: 'risk.create'},
  'risk.review': {id: 'risk.review', label: 'Risk Kayıtlarını İncele', module: 'risk', targetId: 'risk.review'},
  'corrective_action.create': {id: 'corrective_action.create', label: 'DÖF Oluştur', module: 'capa', targetId: 'corrective_action.create'},
  'corrective_action.complete': {id: 'corrective_action.complete', label: 'DÖF Durumunu Güncelle', module: 'capa', targetId: 'capa.complete'},
  'risk.report': {id: 'risk.report', label: 'Risk Raporuna Git', module: 'risk', targetId: 'navigation.risk'},
  'risk.open': {id: 'risk.open', label: 'Risk Analizini Aç', module: 'risk', targetId: 'navigation.risk'},
  'near_miss.create': {id: 'near_miss.create', label: 'Ramak Kala Kaydı Aç', module: 'near_miss', targetId: 'near_miss.create'},
  'accident.create': {id: 'accident.create', label: 'Kaza Kaydı Aç', module: 'accident', targetId: 'accident.create'},
  'accident.review': {id: 'accident.review', label: 'Kaza Kayıtlarını İncele', module: 'accident', targetId: 'accident.review'},
  'reports.open': {id: 'reports.open', label: 'Raporlara Git', module: 'reports', targetId: 'navigation.reports'},
  'visit.view': {id: 'visit.view', label: 'Ziyaretleri Gör', module: 'visits', targetId: 'navigation.visits'},
  'field_inspection.open': {id: 'field_inspection.open', label: 'Saha Denetimine Git', module: 'field_inspection', targetId: 'navigation.field_inspection'},
  'field_inspection.create': {id: 'field_inspection.create', label: 'Denetim Başlat', module: 'field_inspection', targetId: 'field_inspection.create'},
  'field_inspection.add_photo': {id: 'field_inspection.add_photo', label: 'Fotoğraf Ekle', module: 'field_inspection', targetId: 'field_inspection.add_photo'},
  'medical_exam.view': {id: 'medical_exam.view', label: 'Muayene Kayıtlarını Gör', module: 'health', targetId: 'navigation.health'},
  'health.record.view': {id: 'health.record.view', label: 'Sağlık Kayıtlarını Gör', module: 'health', targetId: 'navigation.health'},
  'document.create': {id: 'document.create', label: 'Doküman Ekle', module: 'documents', targetId: 'document.create'},
  'document.view': {id: 'document.view', label: 'Dokümanları Gör', module: 'documents', targetId: 'navigation.documents'},
  'employee.report': {id: 'employee.report', label: 'Personel Raporuna Git', module: 'employees', targetId: 'navigation.employees'},
};

export function getAssistantPageDefinition(active) { const page = PAGES[active]; return page ? {id: active, ...page} : {id: active || 'unknown', title: TITLES[active] || active || 'Uygulama', module: active || 'unknown', purpose: `${TITLES[active] || active || 'Bu'} modülündeki mevcut işlemleri yönetir.`, suggestions: ['Bu sayfada ne yapabilirim?', 'Bir sonraki adım ne?', 'Bu modül için yetkim var mı?'], capabilities: []}; }
export function getCapability(id) { return CAPABILITIES[id] || null; }
export function collectSafePageState() { return {}; }
export function getAssistantPageContext(active, user, allowedModules = []) { const page = getAssistantPageDefinition(active); return {currentPage: {id: page.id, module: page.module, title: page.title, purpose: page.purpose}, user: {role: user?.role || 'unknown', accessibleModules: allowedModules.slice(0, 80)}, state: collectSafePageState(), capabilities: page.capabilities.map(getCapability).filter(Boolean).filter((item) => allowedModules.includes(item.module)).map((item) => item.id)}; }
export function findCapabilityForQuestion(question, active, allowedModules = []) { const q = String(question || '').toLocaleLowerCase('tr-TR'); const page = getAssistantPageDefinition(active); const patterns = [[/excel|içe aktar|yükle/, 'employee.import_excel'], [/personel.*ekle|çalışan.*ekle/, 'employee.create'], [/eğitim.*ata|atama/, 'training.assign'], [/sınav|soru üret/, 'exam.generate'], [/risk.*oluştur|risk.*kayıt/, 'risk.create'], [/döf|düzeltici/, 'corrective_action.create'], [/işyeri.*ekle|firma.*ekle/, 'company.create']]; const match = patterns.find(([pattern]) => pattern.test(q)); const orderedIds = match ? [match[1], ...page.capabilities.filter((id) => id !== match[1])] : page.capabilities; return orderedIds.map(getCapability).find((item) => item && allowedModules.includes(item.module)) || null; }
