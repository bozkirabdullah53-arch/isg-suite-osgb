import React from 'react';
import {HealthPage as ClinicalHealthPage} from './health.jsx';
import {isWorkplaceManagerUser} from './workplace_user_policy';
import {WorkplaceHealthCardsPage} from './workplace_health_cards.jsx';

/**
 * ``main.jsx`` extensionless ``./health`` importu için güvenli facade.
 * Klinik roller mevcut HealthPage'i aynen kullanır; tek işyerine bağlı
 * company_admin hesabı ise yalnız GET-only sağlık kartı özetini görür.
 */
export function HealthPage({user, ...props}) {
  const Page = isWorkplaceManagerUser(user) ? WorkplaceHealthCardsPage : ClinicalHealthPage;
  return React.createElement(Page, {user, ...props});
}
