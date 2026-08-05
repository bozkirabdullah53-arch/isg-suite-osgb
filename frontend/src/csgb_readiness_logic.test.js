import {describe, expect, it} from 'vitest';
import {buildCsgbReadinessView, normalizePriorityItem} from './csgb_readiness_logic';

describe('ÇSGB readiness card helpers', () => {
  it('normalizes priority records and preserves action guidance', () => {
    expect(normalizePriorityItem({
      code: 'risk_degerlendirme',
      title: 'Risk değerlendirme kayıtları',
      status: 'missing',
      detail: 'Risk değerlendirme kaydı yok.',
      action_module: 'risk',
      action_label: 'Risk değerlendirmesi kaydı oluşturun',
    })).toEqual({
      code: 'risk_degerlendirme',
      title: 'Risk değerlendirme kayıtları',
      status: 'missing',
      detail: 'Risk değerlendirme kaydı yok.',
      actionLabel: 'Risk değerlendirmesi kaydı oluşturun',
      actionModule: 'risk',
      contextReview: false,
    });
  });

  it('builds all priorities and committee threshold context without changing score', () => {
    const view = buildCsgbReadinessView({
      readiness_pct: 45,
      gap_count: 11,
      score_changed: false,
      priority_items: [
        {code: 'isg_kurulu', title: 'İSG kurulu', status: 'missing', context_review: true},
      ],
      contextual_notes: [
        {
          code: 'isg_kurulu',
          title: 'İSG kurulu çalışan eşiği',
          detail: 'Toplam 2 aktif çalışan var.',
          legal_basis: '50 ve daha fazla çalışan.',
        },
      ],
    });

    expect(view.readinessPct).toBe(45);
    expect(view.priorityCount).toBe(11);
    expect(view.priorities).toHaveLength(1);
    expect(view.priorities[0].contextReview).toBe(true);
    expect(view.contextualNotes).toHaveLength(1);
    expect(view.scoreChanged).toBe(false);
    expect(view.hasDetails).toBe(true);
  });
});
