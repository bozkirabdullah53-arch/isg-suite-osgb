export const DOCUMENT_KIND_OPTIONS = [
  ['profile_photo', 'Profil fotoğrafı'],
  ['cv', 'Mevcut CV'],
  ['qualification', 'Diploma / yeterlilik'],
  ['certificate', 'Mesleki sertifika'],
];

export const DOCUMENT_CATEGORY_OPTIONS = [
  ['profile_photo', 'Profil fotoğrafı', ['profile_photo']],
  ['cv', 'CV', ['cv']],
  ['diploma', 'Diploma', ['qualification']],
  ['graduation_certificate', 'Mezuniyet belgesi', ['qualification']],
  ['occupational_safety_certificate', 'İş güvenliği uzmanlığı belgesi', ['qualification', 'certificate']],
  ['workplace_physician_certificate', 'İşyeri hekimliği belgesi', ['qualification', 'certificate']],
  ['other_health_personnel_certificate', 'Diğer sağlık personeli belgesi', ['qualification', 'certificate']],
  ['trainer_certificate', 'Eğitici belgesi', ['qualification', 'certificate']],
  ['myk_certificate', 'MYK belgesi', ['qualification', 'certificate']],
  ['mastership_certificate', 'Ustalık belgesi', ['qualification', 'certificate']],
  ['journeyman_certificate', 'Kalfalık belgesi', ['qualification', 'certificate']],
  ['operator_certificate', 'Operatör belgesi', ['qualification', 'certificate']],
  ['first_aid_certificate', 'İlk yardımcı belgesi', ['certificate']],
  ['working_at_height_certificate', 'Yüksekte çalışma belgesi', ['certificate']],
  ['fire_safety_certificate', 'Yangın güvenliği belgesi', ['certificate']],
  ['emergency_response_certificate', 'Acil durum müdahale belgesi', ['certificate']],
  ['explosion_protection_certificate', 'Patlamadan korunma belgesi', ['certificate']],
  ['risk_assessment_certificate', 'Risk değerlendirmesi belgesi', ['certificate']],
  ['electrical_work_certificate', 'Elektrik işleri belgesi', ['certificate']],
  ['scaffolding_certificate', 'İskele belgesi', ['certificate']],
  ['welding_certificate', 'Kaynakçılık belgesi', ['certificate']],
  ['hygiene_certificate', 'Hijyen belgesi', ['certificate']],
  ['language_certificate', 'Yabancı dil belgesi', ['certificate']],
  ['other_professional_document', 'Diğer profesyonel belge', ['qualification', 'certificate']],
];

const KIND_DEFAULT_CATEGORY = {
  profile_photo: 'profile_photo',
  cv: 'cv',
  qualification: 'diploma',
  certificate: 'occupational_safety_certificate',
};

const KIND_ACCEPT = {
  profile_photo: '.png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp',
  cv: '.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  qualification: '.pdf,.png,.jpg,.jpeg,.webp,application/pdf,image/png,image/jpeg,image/webp',
  certificate: '.pdf,.png,.jpg,.jpeg,.webp,application/pdf,image/png,image/jpeg,image/webp',
};

const KIND_MAX_BYTES = {
  profile_photo: 5 * 1024 * 1024,
  cv: 10 * 1024 * 1024,
  qualification: 15 * 1024 * 1024,
  certificate: 15 * 1024 * 1024,
};

export function asDocumentRows(payload) {
  return Array.isArray(payload) ? payload : Array.isArray(payload?.items) ? payload.items : [];
}

export function documentKindLabel(value) {
  return DOCUMENT_KIND_OPTIONS.find(([id]) => id === value)?.[1] || String(value || 'Belge');
}

export function documentCategoryLabel(value) {
  return DOCUMENT_CATEGORY_OPTIONS.find(([id]) => id === value)?.[1] || String(value || 'Belge');
}

export function categoriesForKind(kind) {
  return DOCUMENT_CATEGORY_OPTIONS.filter(([, , kinds]) => kinds.includes(kind));
}

export function normalizeCategoryForKind(kind, currentCategory) {
  const allowed = categoriesForKind(kind);
  if (allowed.some(([id]) => id === currentCategory)) return currentCategory;
  return KIND_DEFAULT_CATEGORY[kind] || allowed[0]?.[0] || '';
}

export function acceptForDocumentKind(kind) {
  return KIND_ACCEPT[kind] || '';
}

export function maxBytesForDocumentKind(kind) {
  return KIND_MAX_BYTES[kind] || 0;
}

export function formatDocumentBytes(value) {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 KB';
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(bytes >= 10 * 1024 * 1024 ? 0 : 1)} MB`;
}

export function validateDocumentFile(file, kind) {
  if (!file) return 'Yüklenecek dosyayı seçin.';
  const max = maxBytesForDocumentKind(kind);
  if (max && Number(file.size || 0) > max) {
    return `Dosya ${Math.round(max / (1024 * 1024))} MB sınırını aşıyor.`;
  }
  const extension = String(file.name || '').toLocaleLowerCase('tr-TR').match(/\.[^.]+$/)?.[0] || '';
  const allowed = {
    profile_photo: ['.png', '.jpg', '.jpeg', '.webp'],
    cv: ['.pdf', '.docx'],
    qualification: ['.pdf', '.png', '.jpg', '.jpeg', '.webp'],
    certificate: ['.pdf', '.png', '.jpg', '.jpeg', '.webp'],
  }[kind] || [];
  if (!allowed.includes(extension)) return `${documentKindLabel(kind)} için desteklenmeyen dosya uzantısı.`;
  return '';
}

export function validityLabel(value) {
  return {
    valid: 'Geçerli',
    expiring_soon: '30 gün içinde sona erecek',
    expired: 'Süresi dolmuş',
    no_expiration: 'Süresiz',
    incomplete: 'Geçerlilik tarihi eksik',
    archived: 'Arşivli',
  }[value] || 'Durum bilinmiyor';
}

export function validityTone(value) {
  return {
    valid: 'success',
    no_expiration: 'success',
    expiring_soon: 'warning',
    expired: 'danger',
    archived: 'neutral',
    incomplete: 'warning',
  }[value] || 'neutral';
}

export function verificationLabel(value) {
  return {
    verified: 'Doğrulandı',
    rejected: 'Reddedildi',
    unverified: 'Doğrulanmadı',
  }[value] || 'Doğrulanmadı';
}

export function safeDocumentFilename(row) {
  const base = String(row?.title || 'personel-belgesi')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9._-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80) || 'personel-belgesi';
  const extension = String(row?.file_extension || '').startsWith('.') ? row.file_extension : '';
  return `${base}-v${Number(row?.version || 1)}${extension}`;
}

export function newIdempotencyKey() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const random = () => Math.floor(Math.random() * 0x10000).toString(16).padStart(4, '0');
  return `${random()}${random()}-${random()}-4${random().slice(1)}-a${random().slice(1)}-${random()}${random()}${random()}`;
}
