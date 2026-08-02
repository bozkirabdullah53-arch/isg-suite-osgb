import {describe, expect, it} from 'vitest';
import {
  emptyQuestionDraft,
  questionDraftPayload,
  questionToDraft,
  validateQuestionDraft,
} from './training_question_bank_logic.js';

function validDraft() {
  return {
    ...emptyQuestionDraft(),
    question_code: 'NACE-30.11-001',
    topic_code: 'PPE',
    topic_label: 'Kişisel koruyucu donanım',
    question_text: 'Tersanede taşlama sırasında hangi koruma birlikte kullanılmalıdır?',
    options: {
      A: 'Yüz siperi ve koruyucu gözlük',
      B: 'Yalnız pamuklu eldiven',
      C: 'Yalnız reflektif yelek',
      D: 'Koruyucu donanım gerektirmez',
    },
    correct_option: 'A',
    answer_explanation: 'Taşlama parçacık ve kıvılcım oluşturduğu için göz ve yüz birlikte korunmalıdır.',
    scopes: [{type: 'nace', value: '30.11'}],
    sources: [{
      title: 'Kişisel Koruyucu Donanımlar Yönetmeliği',
      url: 'https://www.resmigazete.gov.tr/ornek',
      reference: 'Madde 6',
      effective_date: '2025-01-01',
    }],
  };
}

describe('training question bank form rules', () => {
  it('accepts a sourced, scoped and complete question', () => {
    expect(validateQuestionDraft(validDraft())).toEqual([]);
  });

  it('rejects duplicate answers, missing source and invalid scope', () => {
    const draft = validDraft();
    draft.options.B = draft.options.A;
    draft.sources = [];
    draft.scopes = [{type: 'nace', value: ''}];
    const errors = validateQuestionDraft(draft).join(' ');
    expect(errors).toContain('birbirinden farklı');
    expect(errors).toContain('kaynak');
    expect(errors).toContain('kapsam');
  });

  it('normalizes API payload without inventing an effective date', () => {
    const draft = validDraft();
    draft.question_code = 'nace-30.11-001';
    draft.sources[0].effective_date = '';
    const payload = questionDraftPayload(draft);
    expect(payload.question_code).toBe('NACE-30.11-001');
    expect(payload.options).toHaveLength(4);
    expect(payload.sources[0]).not.toHaveProperty('effective_date');
  });

  it('prepares a published question as a higher immutable version', () => {
    const source = questionDraftPayload(validDraft());
    const draft = questionToDraft({...source, options: {A: 'a', B: 'b', C: 'c', D: 'd'}}, {nextVersion: true});
    expect(draft.version).toBe(2);
    expect(draft.question_code).toBe('NACE-30.11-001');
  });
});
