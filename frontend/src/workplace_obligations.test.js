import {describe, expect, it, vi} from 'vitest';
import {
  buildObligationQuery,
  consumeSelectedObligation,
  defaultObligationFilters,
  obligationDaysText,
  obligationStatusLabel,
  rememberSelectedObligation,
} from './workplace_obligations';

describe('workplace obligation helpers', () => {
  it('uses the approved 30-day default horizon', () => {
    expect(defaultObligationFilters(new Date(2026, 8, 19)).date_to).toBe('2026-10-19');
  });

  it('builds a paginated query without empty filters', () => {
    const query = new URLSearchParams(buildObligationQuery({
      branch_id: '4', category: 'ppe', status: '', date_from: '', date_to: '2026-10-19',
    }, 3, 50));
    expect(Object.fromEntries(query)).toEqual({
      page: '3', page_size: '50', branch_id: '4', category: 'ppe', date_to: '2026-10-19',
    });
  });

  it('renders exact 7/30-day status wording', () => {
    expect(obligationStatusLabel('very_soon')).toBe('Çok Yakın');
    expect(obligationStatusLabel('approaching')).toBe('Yaklaşıyor');
    expect(obligationDaysText({status: 'overdue', days_left: -3})).toBe('3 gün gecikti');
    expect(obligationDaysText({status: 'very_soon', days_left: 0})).toBe('Bugün');
    expect(obligationDaysText({status: 'completed', days_left: -20})).toBe('Tamamlandı');
  });

  it('hands an exact selected record to the status page once', () => {
    const storage = new Map();
    vi.stubGlobal('sessionStorage', {
      getItem: (key) => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: (key) => storage.delete(key),
    });
    const row = {key: 'ppe_assignment:9:renewal:2026-09-20', company_id: 12};
    rememberSelectedObligation(row);
    expect(consumeSelectedObligation(12)).toEqual(row);
    expect(consumeSelectedObligation(12)).toBeNull();
    vi.unstubAllGlobals();
  });
});
