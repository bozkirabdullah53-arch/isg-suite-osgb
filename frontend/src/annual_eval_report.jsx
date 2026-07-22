import React from 'react';
import {FileText} from 'lucide-react';

/** Yer tutucu — içerik sonraki adımda eklenecek. */
export function AnnualEvalReportPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2>
            <FileText size={22} style={{marginRight: 8, verticalAlign: 'middle'}} />
            Yıllık Çalışma Değerlendirme Raporu
          </h2>
          <p className="muted">
            Bu bölüm yakında eklenecek. Yıllık çalışma değerlendirme raporlarının hazırlanması ve takibi burada yönetilecek.
          </p>
        </div>
      </div>
      <section className="panel">
        <p style={{margin: 0, color: '#64748b'}}>İçerik hazırlanıyor.</p>
      </section>
    </div>
  );
}
