import {describe, expect, it} from 'vitest';
import {GLOBAL_ADMIN_MODULES} from './app_module_policy.js';

describe('global administrator module policy', () => {
  it('exposes the governed question bank as a standalone EİSA module', () => {
    expect(GLOBAL_ADMIN_MODULES).toContain('eisa_question_bank');
  });

  it('does not expose workplace operation modules to the global administrator', () => {
    expect(GLOBAL_ADMIN_MODULES).not.toContain('training');
    expect(GLOBAL_ADMIN_MODULES).not.toContain('employees');
    expect(GLOBAL_ADMIN_MODULES).not.toContain('risk');
  });

  it('does not contain duplicate module identifiers', () => {
    expect(new Set(GLOBAL_ADMIN_MODULES).size).toBe(GLOBAL_ADMIN_MODULES.length);
  });
});
