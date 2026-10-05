import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {describe, expect, it} from 'vitest';
import {TeamMinimum, TeamRequirementsSummary} from './emergency_team_requirements';

function render(component, props) {
  const node = document.createElement('div');
  node.innerHTML = renderToStaticMarkup(React.createElement(component, props));
  return node;
}

describe('automatic emergency team requirements', () => {
  it('shows the computed count and primary shortage instead of the saved legacy two', () => {
    const node = render(TeamMinimum, {team: {name: 'İlk Yardım', min_members: 2, required_members: 7, missing_members: 5, minimum_source: 'legal', minimum_basis: 'İlkyardım Yönetmeliği m.19'}});
    expect(node.textContent).toContain('Asgari: 7 kişi');
    expect(node.textContent).toContain('Eksik asıl: 5 kişi');
    expect(node.textContent).not.toContain('2 kişi');
  });

  it('does not display missing input as zero or a made-up minimum', () => {
    const node = render(TeamMinimum, {team: {name: 'İlk Yardım', min_members: 2, required_members: null, missing_members: null, minimum_source: 'incomplete'}});
    expect(node.textContent).toContain('Hesaplanamadı');
    expect(node.textContent).not.toContain('Eksik asıl');
    expect(node.textContent).not.toContain('0 kişi');
  });

  it('identifies optional teams as plan-based', () => {
    const node = render(TeamMinimum, {team: {name: 'Tahliye', min_members: 2, required_members: null, minimum_source: 'risk_assessment'}});
    expect(node.textContent).toContain('Planla belirlenir');
    expect(node.textContent).not.toContain('2 kişi');
  });

  it('keeps a zero workplace target distinct from unknown data', () => {
    const node = render(TeamMinimum, {team: {name: 'Özel Ekip', required_members: 0, missing_members: 0, minimum_source: 'workplace'}});
    expect(node.textContent).toContain('İşyeri hedefi: 0 kişi');
    expect(node.textContent).not.toContain('Hesaplanamadı');
  });

  it('clears the calculation when no company is loaded and explains the small-workplace exception', () => {
    expect(render(TeamRequirementsSummary, {overview: null}).textContent).toBe('');
    const node = render(TeamRequirementsSummary, {overview: {company: {hazard_class: 'Çok Tehlikeli'}, employee_count: 9, shared_support_allowed: true}});
    expect(node.textContent).toContain('9 aktif çalışan');
    expect(node.textContent).toContain('aynı eğitimli destek elemanı');
    expect(node.textContent).toContain('m.11/4');
  });
});
