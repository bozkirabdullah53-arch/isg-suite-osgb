import React, {useEffect, useState} from 'react';
import {
  AlertTriangle,
  Beaker,
  ClipboardCheck,
  FileText,
  Gauge,
  HardHat,
  ShieldAlert,
  Users,
} from 'lucide-react';
import {api} from './api';

const MODULE_CARDS = [
  {id: 'employees', title: 'Personel', hint: 'Çalışan ekle / düzenle', icon: Users, countKey: 'employees'},
  {id: 'ppe', title: 'KKD Takip', hint: 'Teslim ve stok kayıtları', icon: HardHat, countKey: 'ppe'},
  {id: 'sds', title: 'SDS / PKD', hint: 'Kimyasal ürün kayıtları', icon: Beaker, countKey: 'sds'},
  {id: 'periyodik_kontrol', title: 'Periyodik Kontrol', hint: 'Ekipman kontrolleri', icon: ClipboardCheck, countKey: 'periodic'},
  {id: 'ortam_olcum', title: 'Ortam Ölçüm', hint: 'Gürültü, toz, gaz ölçümleri', icon: Gauge, countKey: 'measurements'},
  {id: 'near_miss', title: 'Ramak Kala', hint: 'Olay kayıtları', icon: AlertTriangle, countKey: 'nearMiss'},
  {id: 'accident', title: 'İş Kazaları', hint: 'Kaza bildirimleri', icon: ShieldAlert, countKey: 'accidents'},
  {id: 'capa', title: 'DÖF', hint: 'Düzeltici / önleyici faaliyet', icon: ClipboardCheck, countKey: 'capa'},
  {id: 'isg_kurulu', title: 'İSG Kurulu', hint: 'Kurul üyeleri ve toplantılar', icon: Users, countKey: 'committee'},
  {id: 'employer_oversight', title: 'Denetim Durumu', hint: 'Onay ve hazırlık özeti', icon: FileText, countKey: null},
];

function countRows(value) {
  return Array.isArray(value) ? value.length : 0;
}

export function WorkplaceHomePage({user, onNavigate}) {
  const [counts, setCounts] = useState({});
  const [companyName, setCompanyName] = useState('');

  useEffect(() => {
    let cancelled = false;
    const companyId = Number(user?.company_id || 0);
    const query = companyId ? `?company_id=${companyId}` : '';
    Promise.all([
      api('/companies').catch(() => []),
      api(`/employees${query}`).catch(() => []),
      api(`/ppe/assignments${query}`).catch(() => []),
      api(`/sds${query}`).catch(() => []),
      api(`/periodic-controls${query}`).catch(() => []),
      api(`/workplace-measurements${query}`).catch(() => []),
      api(`/incidents${query}`).catch(() => []),
    ]).then(([companies, employees, ppe, sds, periodic, measurements, incidents]) => {
      if (cancelled) return;
      const company = (Array.isArray(companies) ? companies : []).find(
        (row) => Number(row.id) === companyId,
      );
      const incidentRows = Array.isArray(incidents) ? incidents : [];
      setCompanyName(company?.name || '');
      setCounts({
        employees: countRows(employees),
        ppe: countRows(ppe),
        sds: countRows(sds),
        periodic: countRows(periodic),
        measurements: countRows(measurements),
        nearMiss: incidentRows.filter((row) => row.event_type === 'ramak_kala').length,
        accidents: incidentRows.filter((row) => row.event_type === 'is_kazasi').length,
        capa: incidentRows.reduce((total, row) => total + countRows(row.dofs), 0),
      });
    });
    return () => {
      cancelled = true;
    };
  }, [user?.company_id]);

  return (
    <>
      <div className="welcome">
        <div>
          <h3>İşyeri Ana Panel</h3>
          <p>
            {companyName ? `${companyName} · ` : ''}
            Personel, KKD, SDS/PKD, ramak kala, ortam ölçümü, periyodik kontrol, İSG Kurulu, iş kazaları ve DÖF kayıtlarını buradan yönetin.
          </p>
        </div>
      </div>
      <div className="cards osgb-cards" style={{marginBottom: 16}}>
        {MODULE_CARDS.map((card) => {
          const Icon = card.icon;
          const count = card.countKey ? counts[card.countKey] : null;
          return (
            <article
              key={card.id}
              className="metric"
              style={{cursor: 'pointer'}}
              onClick={() => onNavigate?.(card.id)}
              title={card.title}
            >
              <span style={{display: 'inline-flex', alignItems: 'center', gap: 8}}>
                <Icon size={16} />
                {card.title}
              </span>
              <strong>{count == null ? 'Aç' : count}</strong>
              <small style={{display: 'block', marginTop: 6, color: '#64748b', fontSize: 11, fontWeight: 600}}>
                {card.hint}
              </small>
            </article>
          );
        })}
      </div>
    </>
  );
}
