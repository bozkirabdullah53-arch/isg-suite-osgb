import {describe, expect, it} from 'vitest';
import {filterCompanyDirectoryRows} from './company_directory_scope';

const companies = [
  {id: 1, name: 'Erdil Akü'},
  {id: 2, name: 'Uludağ OSB'},
  {id: 3, name: 'Uludağ OSB Müdürlüğü'},
];

describe('company directory selection scope', () => {
  it('shows only the company selected from the shared company context', () => {
    expect(filterCompanyDirectoryRows(companies, {selectedCompanyId: '2', selectionRequired: true}))
      .toEqual([companies[1]]);
  });

  it('does not show every company before a required selection is made', () => {
    expect(filterCompanyDirectoryRows(companies, {selectedCompanyId: '', selectionRequired: true}))
      .toEqual([]);
  });

  it('keeps the full directory for users who are not scoped by a selection', () => {
    expect(filterCompanyDirectoryRows(companies, {selectionRequired: false})).toEqual(companies);
  });
});
