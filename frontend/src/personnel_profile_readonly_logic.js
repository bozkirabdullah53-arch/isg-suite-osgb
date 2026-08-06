export function normalizePersonnelReadiness(payload = {}) {
  const rollout = payload?.rollout && typeof payload.rollout === 'object' ? payload.rollout : {};
  return {
    companyId: Number(payload?.company_id || 0) || null,
    enabled: Boolean(payload?.enabled),
    visible: Boolean(payload?.visible),
    readOnly: payload?.read_only !== false,
    active: Boolean(rollout?.active),
    forceOff: Boolean(rollout?.force_off),
    pilotCompany: Boolean(rollout?.pilot_company),
    capabilities: payload?.capabilities && typeof payload.capabilities === 'object'
      ? payload.capabilities
      : {},
  };
}

export function shouldRenderPersonnelProfileEntry(payload = {}) {
  const readiness = normalizePersonnelReadiness(payload);
  return Boolean(
    readiness.enabled
    && readiness.visible
    && readiness.readOnly
    && readiness.active
    && readiness.pilotCompany
    && !readiness.forceOff
    && readiness.capabilities.employee_summary !== false,
  );
}

export function normalizeEmployeeRows(payload) {
  const rows = Array.isArray(payload) ? payload : Array.isArray(payload?.rows) ? payload.rows : [];
  return rows
    .map((row) => ({
      id: Number(row?.id || 0),
      fullName: String(row?.full_name || '').trim(),
      jobTitle: String(row?.job_title || '').trim(),
      department: String(row?.department || '').trim(),
      active: row?.is_active !== false,
    }))
    .filter((row) => row.id > 0 && row.fullName);
}

export function professionalTypeLabel(value) {
  return {
    safety_specialist: 'İş Güvenliği Uzmanı',
    workplace_physician: 'İşyeri Hekimi',
    other_health_personnel: 'Diğer Sağlık Personeli',
  }[String(value || '').toLowerCase()] || String(value || 'Profesyonel');
}

export function normalizeProfessionalRows(professionalsPayload, assignmentsPayload, pilotCompanyIds) {
  const professionals = Array.isArray(professionalsPayload)
    ? professionalsPayload
    : Array.isArray(professionalsPayload?.rows) ? professionalsPayload.rows : [];
  const assignments = Array.isArray(assignmentsPayload)
    ? assignmentsPayload
    : Array.isArray(assignmentsPayload?.rows) ? assignmentsPayload.rows : [];
  const pilotIds = new Set([...pilotCompanyIds].map((value) => Number(value)).filter((value) => value > 0));
  const companiesByProfessional = new Map();

  for (const assignment of assignments) {
    const status = String(assignment?.status || '').toLowerCase();
    const professionalId = Number(assignment?.professional_id || 0);
    const companyId = Number(assignment?.company_id || 0);
    if (status && status !== 'active') continue;
    if (!professionalId || !pilotIds.has(companyId)) continue;
    if (!companiesByProfessional.has(professionalId)) companiesByProfessional.set(professionalId, new Set());
    companiesByProfessional.get(professionalId).add(companyId);
  }

  return professionals
    .map((row) => {
      const id = Number(row?.id || 0);
      const companyIds = [...(companiesByProfessional.get(id) || [])].sort((a, b) => a - b);
      return {
        id,
        fullName: String(row?.full_name || '').trim(),
        professionalType: String(row?.professional_type || '').trim(),
        professionalTypeLabel: professionalTypeLabel(row?.professional_type),
        certificateClass: String(row?.certificate_class || '').trim(),
        active: row?.is_active !== false,
        companyIds,
        companyId: companyIds[0] || null,
      };
    })
    .filter((row) => row.id > 0 && row.fullName && row.companyId);
}

export function normalizePersonnelProfileSummary(payload = {}) {
  const subject = payload?.subject && typeof payload.subject === 'object' ? payload.subject : {};
  const scope = payload?.scope && typeof payload.scope === 'object' ? payload.scope : {};
  const profile = payload?.profile && typeof payload.profile === 'object' ? payload.profile : {};
  const privacy = payload?.privacy && typeof payload.privacy === 'object' ? payload.privacy : {};
  const type = String(subject?.type || 'employee');
  return {
    summaryVersion: String(payload?.summary_version || ''),
    subjectType: type,
    subjectId: Number(subject?.id || 0) || null,
    companyId: Number(scope?.company_id || 0) || null,
    companyName: String(scope?.company_name || '').trim(),
    branchName: String(scope?.branch_name || '').trim(),
    osgbId: Number(scope?.osgb_id || 0) || null,
    fullName: String(profile?.full_name || '').trim(),
    nationalIdentityMasked: String(profile?.national_identity_masked || '').trim(),
    jobTitle: String(profile?.job_title || '').trim(),
    department: String(profile?.department || '').trim(),
    employmentStartDate: String(profile?.employment_start_date || '').trim(),
    employmentStatus: String(profile?.employment_status || '').trim(),
    professionalType: String(profile?.professional_type || '').trim(),
    professionalTypeLabel: professionalTypeLabel(profile?.professional_type),
    email: String(profile?.email || '').trim(),
    phone: String(profile?.phone || '').trim(),
    certificateClass: String(profile?.certificate_class || '').trim(),
    certificateNumber: String(profile?.certificate_number || '').trim(),
    certificateDate: String(profile?.certificate_date || '').trim(),
    activeAssignmentCount: Math.max(0, Number(profile?.active_assignment_count || 0) || 0),
    dataMinimized: privacy?.data_minimized !== false,
    restrictedDataIncluded: Boolean(
      privacy?.health_data_included
      || privacy?.criminal_record_included
      || privacy?.restricted_documents_included
      || privacy?.special_status_included
      || privacy?.national_identity_full_included,
    ),
  };
}

export function employmentStatusLabel(value) {
  return {
    active: 'Aktif',
    inactive: 'Pasif',
    suspended: 'Askıda',
  }[String(value || '').toLowerCase()] || String(value || 'Belirtilmedi');
}

export function formatProfileDate(value) {
  if (!value) return '';
  try {
    const date = new Date(value.length <= 10 ? `${value}T00:00:00` : value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat('tr-TR', {dateStyle: 'medium'}).format(date);
  } catch {
    return String(value);
  }
}
