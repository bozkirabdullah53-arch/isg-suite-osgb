import {describe, expect, it} from 'vitest';
import {osgbDashboardCompanyOptions} from './osgb_company_scope';

const companies = [
  {id: 1, name: 'A', osgb_id: 10, is_active: true},
  {id: 2, name: 'B', osgb_id: 20, is_active: true},
  {id: 3, name: 'C', osgb_id: 10, is_active: false},
];

describe('OSGB dashboard company options', () => {
  it('keeps API-authorized company choices available if an OSGB id is missing', () => {
    expect(osgbDashboardCompanyOptions(companies, {role: 'company_admin'}).map((row) => row.id))
      .toEqual([1, 2]);
  });

  it('limits the choices to active companies in the selected OSGB', () => {
    expect(osgbDashboardCompanyOptions(companies, {role: 'company_admin', osgbId: 10}).map((row) => row.id))
      .toEqual([1]);
  });

  it('does not show global company names until an OSGB is selected', () => {
    expect(osgbDashboardCompanyOptions(companies, {role: 'global_admin'})).toEqual([]);
  });
});
