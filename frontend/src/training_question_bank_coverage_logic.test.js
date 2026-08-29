import {describe, expect, it} from 'vitest';
import {
  SMART_QUESTION_COUNT,
  buildSmartSectorIndex,
  coveragePagination,
  smartCoverageSummary,
  smartReadinessForItem,
} from './training_question_bank_coverage_logic.js';

describe('EİSA smart question bank coverage', () => {
  const sectors = [
    {code: 'metal', nace: '25.11.01', topics: ['A', 'B', 'C', 'D', 'E']},
    {code: 'office', nace: '69.10.01', topics: ['A', 'B', 'C']},
  ];

  it('marks a NACE with five frozen workplace topics as smart-ready for 15 questions', () => {
    const index = buildSmartSectorIndex(sectors);
    const readiness = smartReadinessForItem({code: 'metal', nace: '25.11.01'}, index);
    expect(readiness.ready).toBe(true);
    expect(readiness.questionCount).toBe(SMART_QUESTION_COUNT);
  });

  it('does not claim smart readiness when the five-topic prerequisite is missing', () => {
    const index = buildSmartSectorIndex(sectors);
    const readiness = smartReadinessForItem({code: 'office', nace: '69.10.01'}, index);
    expect(readiness.ready).toBe(false);
    expect(readiness.questionCount).toBe(0);
  });

  it('summarizes the full NACE catalog without hiding records that need review', () => {
    expect(smartCoverageSummary(sectors)).toEqual({catalogCount: 2, readyCount: 1, reviewCount: 1});
  });

  it('calculates real previous and next pages from API offset metadata', () => {
    const page = coveragePagination({items_total: 2141, limit: 50, offset: 50});
    expect(page.currentPage).toBe(2);
    expect(page.totalPages).toBe(43);
    expect(page.previousOffset).toBe(0);
    expect(page.nextOffset).toBe(100);
    expect(page.hasPrevious).toBe(true);
    expect(page.hasNext).toBe(true);
  });
});
