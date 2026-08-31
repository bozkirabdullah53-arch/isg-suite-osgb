import React, { useState } from 'react';
import { Settings, Sparkles } from 'lucide-react';
import { EisaSystemSettingsPage as ExistingSystemSettingsPage } from './eisa.jsx';
import { EisaAiSettingsPage } from './eisa_ai_settings.jsx';

export function EisaSystemSettingsPage() {
  const [section, setSection] = useState('ai');

  return (
    <>
      <div
        className="actions"
        style={{
          marginBottom: 16,
          padding: 8,
          border: '1px solid #dbe5ea',
          borderRadius: 12,
          background: '#f8fafc',
          justifyContent: 'flex-start',
          gap: 8,
        }}
      >
        <button
          type="button"
          className={section === 'ai' ? '' : 'secondary'}
          onClick={() => setSection('ai')}
        >
          <Sparkles size={16} /> Yapay Zekâ Yönetimi
        </button>
        <button
          type="button"
          className={section === 'platform' ? '' : 'secondary'}
          onClick={() => setSection('platform')}
        >
          <Settings size={16} /> Platform / Kullanıcı Ayarları
        </button>
      </div>

      {section === 'ai' ? <EisaAiSettingsPage /> : <ExistingSystemSettingsPage />}
    </>
  );
}
