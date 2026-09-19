import React, {useState} from 'react';
import {RemoteBasicOhsTrainingPanel as CoreRemoteBasicOhsTrainingPanel} from './remote_basic_ohs_training_core.jsx';
import {RemoteTrainingLogoManager} from './remote_training_logo_manager.jsx';

export * from './remote_basic_ohs_training_core.jsx';

export function RemoteBasicOhsTrainingPanel({user}) {
  const [selectedCompanyId, setSelectedCompanyId] = useState('');

  return (
    <>
      <RemoteTrainingLogoManager user={user} companyId={selectedCompanyId} />
      <CoreRemoteBasicOhsTrainingPanel
        user={user}
        onCompanySelectionChange={setSelectedCompanyId}
      />
    </>
  );
}
