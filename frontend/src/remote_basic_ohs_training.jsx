import React from 'react';
import {RemoteBasicOhsTrainingPanel as CoreRemoteBasicOhsTrainingPanel} from './remote_basic_ohs_training_core.jsx';
import {RemoteTrainingLogoManager} from './remote_training_logo_manager.jsx';

export * from './remote_basic_ohs_training_core.jsx';

export function RemoteBasicOhsTrainingPanel({user}) {
  return (
    <>
      <RemoteTrainingLogoManager user={user} />
      <CoreRemoteBasicOhsTrainingPanel user={user} />
    </>
  );
}
