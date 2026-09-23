import {describe, expect, it} from 'vitest';
import {
  osgbDashboardCompanyOptions,
  osgbDashboardInitialOrganizationId,
} from './osgb_company_scope';

const companies = [
  {id: 1, name: 'A', osgb_id: 10, is_active: true},
  {id: 2, name: 'B', osgb_id: 20, is_active: true},
  {id: 3, name: 'C', osgb_id: 10, is_active: false},
];

describe('OSGB dashboard company options', () => {
  it('keeps API-authorized company choices when the organization hint is absent or mismatched', () => {
    expect(osgbDashboardCompanyOptions(companies, {role: 'company_admin', osgbId: 99}).map((row) => row.id))
      .toEqual([1, 2]);
  });

  it('limits the choices to active companies in the selected OSGB', () => {
    expect(osgbDashboardCompanyOptions(companies, {role: 'global_admin', osgbId: 10}).map((row) => row.id))
      .toEqual([1]);
  });

  it('does not show global company names until an OSGB is selected', () => {
    expect(osgbDashboardCompanyOptions(companies, {role: 'global_admin'})).toEqual([]);
  });

  it('does not guess an OSGB for a company admin from the first organization row', () => {
    expect(osgbDashboardInitialOrganizationId(
      {role: 'company_admin'},
      [{id: 20, name: 'Başka OSGB'}],
    )).toBe('');
  });

  it('keeps an explicit company admin OSGB id and existing global admin default', () => {
    expect(osgbDashboardInitialOrganizationId(
      {role: 'company_admin', osgb_id: 10},
      [{id: 20}],
    )).toBe('10');
    expect(osgbDashboardInitialOrganizationId(
      {role: 'global_admin'},
      [{id: 20}],
    )).toBe('20');
  });
});
