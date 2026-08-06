import {
  normalizeEmployeeRows,
  normalizeProfessionalRows,
} from './personnel_profile_readonly_logic';

export const PROFILE_MANAGER_TABS = [
  ['overview', 'Genel Bakış'],
  ['contacts', 'İletişim'],
  ['competencies', 'Görevler ve Yeterlilikler'],
  ['documents', 'Belgeler'],
  ['cv', 'CV'],
  ['experience', 'Deneyim'],
  ['assignments', 'Atamalar'],
  ['sharing', 'Paylaşımlar'],
  ['history', 'Geçmiş'],
];

export function asRows(payload) {
  return Array.isArray(payload) ? payload : Array.isArray(payload?.rows) ? payload.rows : [];
}

export function buildPersonnelSubjects({employees, professionals, assignments, companyId}) {
  const normalizedEmployees = normalizeEmployeeRows(employees).map((row) => ({
    ...row,
    subjectType: 'employee',
    subjectKey: `employee:${row.id}`,
    companyId: Number(companyId),
    subtitle: [row.jobTitle, row.department].filter(Boolean).join(' · ') || 'İşyeri personeli',
  }));
  const normalizedProfessionals = normalizeProfessionalRows(
    professionals,
    assignments,
    new Set([Number(companyId)]),
  ).map((row) => ({
    ...row,
    subjectType: 'professional',
    subjectKey: `professional:${row.id}`,
    companyId: Number(companyId),
    subtitle: row.professionalTypeLabel,
  }));
  return [...normalizedEmployees, ...normalizedProfessionals]
    .sort((a, b) => String(a.fullName).localeCompare(String(b.fullName), 'tr'));
}

export function filterPersonnelSubjects(rows, query) {
  const needle = String(query || '').trim().toLocaleLowerCase('tr-TR');
  if (!needle) return rows;
  return rows.filter((row) => [
    row.fullName,
    row.subtitle,
    row.jobTitle,
    row.department,
    row.professionalTypeLabel,
  ].some((value) => String(value || '').toLocaleLowerCase('tr-TR').includes(needle)));
}

export function activeProfileRows(rows) {
  return asRows(rows).filter((row) => row?.lifecycle_status !== 'archived');
}

export function archivedProfileRows(rows) {
  return asRows(rows).filter((row) => row?.lifecycle_status === 'archived');
}

export function buildProfileHistory(snapshot = {}) {
  const collections = [
    ['İletişim', asRows(snapshot.contacts)],
    ['Yeterlilik', asRows(snapshot.competencies)],
    ['Deneyim', asRows(snapshot.experiences)],
  ];
  const events = [];
  for (const [category, rows] of collections) {
    for (const row of rows) {
      events.push({
        category,
        id: row.id,
        entryKey: row.entry_key,
        version: Number(row.version || 0),
        status: String(row.lifecycle_status || 'active'),
        title: row.label || row.name || row.position || row.organization_name || category,
        createdAt: row.created_at || null,
      });
    }
  }
  if (snapshot?.profile?.created_at) {
    events.push({
      category: 'Profil',
      id: snapshot.profile.id,
      entryKey: null,
      version: 1,
      status: snapshot.profile.status || 'active',
      title: 'Dijital personel kartı oluşturuldu',
      createdAt: snapshot.profile.created_at,
    });
  }
  return events.sort((a, b) => String(b.createdAt || '').localeCompare(String(a.createdAt || '')));
}

export function managerCanWrite(user) {
  return ['global_admin', 'company_admin'].includes(String(user?.role || ''));
}

export function safeInitials(fullName) {
  const letters = String(fullName || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toLocaleUpperCase('tr-TR');
  return letters || 'PK';
}
