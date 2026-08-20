import {describe, expect, it} from 'vitest';
import {chooseAnnualEvalCompanyId} from './annual_eval_company_selection';

describe('annual evaluation company selection', () => {
  const companies = [{id: 12, name: 'İlk işyeri'}, {id: 19, name: 'İkinci işyeri'}];

  it('keeps an accessible current selection', () => {
    expect(chooseAnnualEvalCompanyId(companies, '19', '')).toBe('19');
  });

  it('falls back to the user company and then the first accessible company', () => {
    expect(chooseAnnualEvalCompanyId(companies, '', 19)).toBe('19');
    expect(chooseAnnualEvalCompanyId(companies, '', 99)).toBe('12');
    expect(chooseAnnualEvalCompanyId([], '', '')).toBe('');
  });
});
