import React from 'react';
import {EyasDigitalApprovalPage as BaseEyasDigitalApprovalPage} from './eyas_digital_approval';
import {CommitteeApprovalQueue} from './committee_approval_queue';

/**
 * Backward-compatible wrapper: existing EYAS remains untouched while assigned
 * committee meetings are surfaced in the same authorized inbox/dashboard.
 */
export function EyasDigitalApprovalPage(props) {
  return (
    <>
      <CommitteeApprovalQueue user={props.user} compact />
      <BaseEyasDigitalApprovalPage {...props} />
    </>
  );
}
