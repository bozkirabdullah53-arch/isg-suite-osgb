import {describe, expect, it} from 'vitest';
import {canManageTrainingPackage, canOperateTraining} from './training_role_policy';

describe('classic training role policy', () => {
  it('allows only OSGB-scope managers to manage the package lifecycle', () => {
    expect(canManageTrainingPackage({role: 'global_admin'})).toBe(true);
    expect(canManageTrainingPackage({role: 'company_admin', osgb_id: 7})).toBe(true);
    expect(canManageTrainingPackage({role: 'company_admin', osgb_id: 7, company_id: 42})).toBe(false);
    expect(canManageTrainingPackage({role: 'company_admin', company_id: 42})).toBe(false);
    expect(canManageTrainingPackage({role: 'safety_specialist', osgb_id: 7})).toBe(false);
  });

  it('keeps operational completion access for specialists without package access', () => {
    expect(canOperateTraining({role: 'safety_specialist', osgb_id: 7})).toBe(true);
    expect(canOperateTraining({role: 'company_admin', company_id: 42})).toBe(true);
    expect(canOperateTraining({role: 'workplace_physician', osgb_id: 7})).toBe(false);
  });
});
