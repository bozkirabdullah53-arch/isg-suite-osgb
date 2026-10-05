import React from 'react';

export function TeamMinimum({team}) {
  const known = team.required_members != null;
  const planned = team.minimum_source === 'risk_assessment';
  const label = team.minimum_source === 'workplace' ? 'İşyeri hedefi' : 'Asgari';
  return (
    <div
      aria-label={`${team.name} asgari kişi hesabı`}
      style={{marginTop: 10, padding: '10px 12px', borderRadius: 10, background: '#f0f7f8', border: '1px solid #d5e7ea'}}
    >
      <div style={{display: 'flex', gap: 10, flexWrap: 'wrap', fontSize: 13}}>
        <span><strong>{label}:</strong> {known ? `${team.required_members} kişi` : planned ? 'Planla belirlenir' : 'Hesaplanamadı'}</span>
        {team.missing_members != null && (
          <span style={{color: team.missing_members > 0 ? '#b91c1c' : '#166534'}}>
            <strong>Eksik asıl:</strong> {team.missing_members} kişi
          </span>
        )}
      </div>
      <div style={{fontSize: 11, color: '#47646d', marginTop: 6}}>{team.minimum_basis}</div>
      <div style={{fontSize: 12, color: '#47646d', marginTop: 4, lineHeight: 1.5}}>{team.minimum_note}</div>
    </div>
  );
}

export function TeamRequirementsSummary({overview}) {
  if (!overview?.company) return null;
  return (
    <section className="panel" aria-label="Otomatik asgari kişi hesabı" style={{marginBottom: 14, borderLeft: '4px solid #22a447'}}>
      <div style={{fontWeight: 700, marginBottom: 6}}>Otomatik asgari kişi hesabı</div>
      <div style={{fontSize: 13, lineHeight: 1.6}}>
        <strong>{overview.employee_count} aktif çalışan</strong> · {overview.company.hazard_class || 'Tehlike sınıfı eksik'}
      </div>
      <p className="muted" style={{fontSize: 12, margin: '6px 0', lineHeight: 1.6}}>
        Firma ve çalışan kayıtlarına göre hesaplanır. Küsuratlar yukarı yuvarlanır; yedekler asıl üye eksiğini kapatmaz.
      </p>
      {overview.shared_support_allowed && (
        <p style={{fontSize: 12, color: '#166534', margin: '8px 0', lineHeight: 1.6}}>
          10’dan az çalışanı olan bu işyerinde aynı eğitimli destek elemanı söndürme, kurtarma ve koruma görevlerinin tamamını üstlenebilir (m.11/4). İlk yardım görevlendirmesi ayrıca değerlendirilir.
        </p>
      )}
      <details style={{fontSize: 12, marginTop: 8}}>
        <summary style={{cursor: 'pointer', fontWeight: 600}}>Hesaplama oranları ve mevzuat dayanağı</summary>
        <div className="table-wrap" style={{marginTop: 8}}>
          <table style={{fontSize: 12}}>
            <thead><tr><th>Tehlike sınıfı</th><th>Söndürme / kurtarma / koruma (her ekip)</th><th>İlk yardım</th></tr></thead>
            <tbody>
              <tr><td>Az tehlikeli</td><td>50 çalışana kadar 1 kişi</td><td>20 çalışana kadar 1 kişi</td></tr>
              <tr><td>Tehlikeli</td><td>40 çalışana kadar 1 kişi</td><td>15 çalışana kadar 1 kişi</td></tr>
              <tr><td>Çok tehlikeli</td><td>30 çalışana kadar 1 kişi</td><td>10 çalışana kadar 1 kişi</td></tr>
            </tbody>
          </table>
        </div>
        <p className="muted" style={{lineHeight: 1.6}}>
          İşyerlerinde Acil Durumlar Hakkında Yönetmelik (İADY) m.11/3–5 ve İlkyardım Yönetmeliği m.19.
          {' '}{overview.minimum_scope_note}
        </p>
      </details>
    </section>
  );
}
