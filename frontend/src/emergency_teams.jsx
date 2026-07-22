import React from 'react';
import {Users} from 'lucide-react';

/** Yer tutucu — içerik sonraki adımda eklenecek. */
export function EmergencyTeamsPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2>
            <Users size={22} style={{marginRight: 8, verticalAlign: 'middle'}} />
            Acil Durum Ekipleri/Destek Elemanları
          </h2>
          <p className="muted">
            Bu bölüm yakında eklenecek. Söndürme, kurtarma, koruma ve ilk yardım ekipleri ile destek elemanı kayıtları burada yönetilecek.
          </p>
        </div>
      </div>
      <section className="panel">
        <p style={{margin: 0, color: '#64748b'}}>İçerik hazırlanıyor.</p>
      </section>
    </div>
  );
}
