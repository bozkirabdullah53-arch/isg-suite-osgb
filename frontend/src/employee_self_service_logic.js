const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export function formatSelfServiceDate(value) {
  const raw = String(value || '').slice(0, 10);
  if (!DATE_RE.test(raw)) return 'Belirlenmedi';
  const [year, month, day] = raw.split('-').map(Number);
  return new Intl.DateTimeFormat('tr-TR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(new Date(year, month - 1, day));
}

export function selfServiceFeatureEnabled(value) {
  return String(value || '').trim().toLowerCase() === 'true';
}

export const EMPLOYEE_TRAINING_ASSIGNMENT_STORAGE_KEY = 'isg_employee_training_assignment';

export function rememberEmployeeTrainingAssignment(assignmentId) {
  const value = String(assignmentId || '').trim();
  if (!value || typeof sessionStorage === 'undefined') return;
  try {
    sessionStorage.setItem(EMPLOYEE_TRAINING_ASSIGNMENT_STORAGE_KEY, value);
  } catch (_) {
    // Navigation remains usable when browser storage is unavailable.
  }
}

export function consumeEmployeeTrainingAssignment() {
  if (typeof sessionStorage === 'undefined') return '';
  try {
    const value = String(sessionStorage.getItem(EMPLOYEE_TRAINING_ASSIGNMENT_STORAGE_KEY) || '').trim();
    sessionStorage.removeItem(EMPLOYEE_TRAINING_ASSIGNMENT_STORAGE_KEY);
    return value;
  } catch (_) {
    return '';
  }
}

const EMPLOYEE_HIDDEN_NOTIFICATION_TYPES = new Set([
  'annual_plan',
  'annual_eval',
  'annual_plan_item',
  'annual_plan_evaluation',
  'annual_plan_evaluation_item',
]);

export function isEmployeeNotificationVisible(item) {
  const entityType = String(item?.entity_type || '').trim().toLowerCase();
  const title = String(item?.title || '').trim().toLocaleLowerCase('tr-TR');
  if (EMPLOYEE_HIDDEN_NOTIFICATION_TYPES.has(entityType)) return false;
  return !title.includes('yıllık plan') && !title.includes('yıllık değerlendirme');
}

export function normalizeSelfServicePayload(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const scope = source.scope && typeof source.scope === 'object' ? source.scope : {};
  const employee = source.employee && typeof source.employee === 'object' ? source.employee : {};
  const training = source.training && typeof source.training === 'object' ? source.training : {};
  const classroom = training.classroom && typeof training.classroom === 'object' ? training.classroom : {};
  const remote = training.remote && typeof training.remote === 'object' ? training.remote : {};
  const ppe = source.ppe && typeof source.ppe === 'object' ? source.ppe : {};
  const notifications = source.notifications && typeof source.notifications === 'object'
    ? source.notifications
    : {};
  const health = source.health && typeof source.health === 'object' ? source.health : {};
  const notificationItems = (Array.isArray(notifications.items) ? notifications.items : [])
    .filter(isEmployeeNotificationVisible);

  return {
    scope: {
      companyName: String(scope.company_name || 'İşyeri'),
      branchName: String(scope.branch_name || ''),
    },
    employee: {
      fullName: String(employee.full_name || 'Çalışan'),
      jobTitle: String(employee.job_title || 'Görev belirtilmedi'),
      department: String(employee.department || 'Bölüm belirtilmedi'),
      startDate: employee.start_date || null,
    },
    training: {
      classroom: {
        total: Number(classroom.total || 0),
        completed: Number(classroom.completed || 0),
        history: Array.isArray(classroom.history) ? classroom.history : [],
      },
      remote: {
        available: Boolean(remote.available),
        total: Number(remote.total || 0),
        completed: Number(remote.completed || 0),
        assignments: Array.isArray(remote.assignments) ? remote.assignments : [],
      },
    },
    ppe: {
      total: Number(ppe.total || 0),
      items: Array.isArray(ppe.items) ? ppe.items : [],
    },
    notifications: {
      unread: notificationItems.filter((item) => !item.is_read).length,
      items: notificationItems,
    },
    health: {
      hasRecord: Boolean(health.has_record),
      lastExaminationDate: health.last_examination_date || null,
      nextExaminationDate: health.next_examination_date || null,
      detailsIncluded: Boolean(health.details_included),
    },
  };
}

export function totalSelfServiceTraining(summary) {
  return Number(summary?.training?.classroom?.total || 0)
    + Number(summary?.training?.remote?.total || 0);
}

export function completedSelfServiceTraining(summary) {
  return Number(summary?.training?.classroom?.completed || 0)
    + Number(summary?.training?.remote?.completed || 0);
}
