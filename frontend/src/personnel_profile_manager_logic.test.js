import {describe, expect, it} from 'vitest';
import {
  activeProfileRows,
  archivedProfileRows,
  buildPersonnelSubjects,
  buildProfileHistory,
  filterPersonnelSubjects,
  managerCanWrite,
  safeInitials,
} from './personnel_profile_manager_logic';


describe('personnel profile manager logic', () => {
  it('builds a deterministic employee and actively assigned professional list', () => {
    const rows = buildPersonnelSubjects({
      companyId: 35,
      employees: [
        {id: 41, full_name: 'Ayşe Yılmaz', job_title: 'Kaynakçı', department: 'Üretim', is_active: true},
      ],
      professionals: [
        {id: 7, full_name: 'Mehmet Uzman', professional_type: 'safety_specialist', is_active: true},
        {id: 8, full_name: 'Atamasız Hekim', professional_type: 'workplace_physician', is_active: true},
      ],
      assignments: [
        {professional_id: 7, company_id: 35, status: 'active'},
        {professional_id: 8, company_id: 99, status: 'active'},
      ],
    });

    expect(rows.map((row) => row.subjectKey)).toEqual(['employee:41', 'professional:7']);
    expect(rows[0].subtitle).toContain('Kaynakçı');
    expect(rows[1].subtitle).toBe('İş Güvenliği Uzmanı');
  });

  it('filters by name, role, department and title', () => {
    const rows = [
      {fullName: 'Ayşe Yılmaz', subtitle: 'Kaynakçı · Üretim'},
      {fullName: 'Mehmet Uzman', subtitle: 'İş Güvenliği Uzmanı'},
    ];
    expect(filterPersonnelSubjects(rows, 'üretim')).toHaveLength(1);
    expect(filterPersonnelSubjects(rows, 'güvenliği')).toHaveLength(1);
    expect(filterPersonnelSubjects(rows, '')).toHaveLength(2);
  });

  it('separates active and archived latest rows', () => {
    const rows = [
      {id: 1, lifecycle_status: 'active'},
      {id: 2, lifecycle_status: 'archived'},
    ];
    expect(activeProfileRows(rows).map((row) => row.id)).toEqual([1]);
    expect(archivedProfileRows(rows).map((row) => row.id)).toEqual([2]);
  });

  it('creates a newest-first audit-friendly view history', () => {
    const history = buildProfileHistory({
      profile: {id: 9, status: 'active', created_at: '2026-01-01T09:00:00'},
      contacts: [{id: 1, entry_key: 'a', version: 2, label: 'Kurumsal', lifecycle_status: 'active', created_at: '2026-02-01T09:00:00'}],
      competencies: [{id: 2, entry_key: 'b', version: 1, name: 'Makine Güvenliği', lifecycle_status: 'active', created_at: '2026-03-01T09:00:00'}],
      experiences: [],
    });
    expect(history.map((row) => row.category)).toEqual(['Yeterlilik', 'İletişim', 'Profil']);
    expect(history[0].title).toBe('Makine Güvenliği');
  });

  it('limits writes to admin roles and produces safe initials', () => {
    expect(managerCanWrite({role: 'company_admin'})).toBe(true);
    expect(managerCanWrite({role: 'safety_specialist'})).toBe(false);
    expect(safeInitials('eflatun bozkır')).toBe('EB');
    expect(safeInitials('')).toBe('PK');
  });
});
