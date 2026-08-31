import {describe, expect, it} from 'vitest';
import {assistantFeatureEnabled, findCapabilityForQuestion, getAssistantPageContext, getAssistantPageDefinition} from './contextual_assistant_registry';

describe('independent contextual assistant registry', () => {
  it('uses page-specific suggestions', () => {
    expect(getAssistantPageDefinition('employees').suggestions[0]).toMatch(/Personel/);
    expect(getAssistantPageDefinition('training').suggestions[0]).toMatch(/Eğitim/);
  });
  it('filters capabilities by allowed modules', () => {
    expect(getAssistantPageContext('employees', {role: 'read_only'}, ['security']).capabilities).toEqual([]);
  });
  it('maps an Excel question to a stable capability id', () => {
    expect(findCapabilityForQuestion('Excel nereden yüklenir?', 'employees', ['employees'])?.id).toBe('employee.import_excel');
  });
  it('supports an emergency frontend kill switch', () => {
    expect(assistantFeatureEnabled({VITE_CONTEXTUAL_ASSISTANT_FORCE_OFF: 'true'})).toBe(false);
  });
});
