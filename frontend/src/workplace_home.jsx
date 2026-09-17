import React, {useEffect, useState} from 'react';
import {
  AlertTriangle, ArrowRight, Beaker, ClipboardCheck, FileText, Gauge,
  HardHat, QrCode, RefreshCw, ShieldAlert, Users,
} from 'lucide-react';
import {api} from './api';
import './workplace_home.css';

const MODULE_CARDS = [
  {id: 'employees', title: 'Personel', hint: 'Personel ekleyin, çalışan bilgilerini düzenleyin.', icon: Users, countKey: 'employees'},
  {id: 'ppe', title: 'KKD Takip', hint: 'Zimmet, teslim ve stok kayıtlarını yönetin.', icon: HardHat, countKey: 'ppe'},
  {id: 'sds', title: 'SDS / PKD', hint: 'Kimyasal ürünleri ve güvenlik belgelerini takip edin.', icon: Beaker, countKey: 'sds'},
  {id: 'periyodik_kontrol', title: 'Periyodik Kontrol', hint: 'Ekipman kontrollerini ve raporlarını kaydedin.', icon: ClipboardCheck, countKey: 'periodic'},
  {id: 'ortam_olcum', title: 'Ortam Ölçüm', hint: 'Gürültü, toz ve gaz ölçüm sonuçlarını izleyin.', icon: Gauge, countKey: 'measurements'},
  {id: 'near_miss', title: 'Ramak Kala', hint: 'Ramak kala olaylarını ve alınan önlemleri kaydedin.', icon: AlertTriangle, countKey: 'nearMiss'},
  {id: 'accident', title: 'İş Kazaları', hint: 'Kaza bildirimlerini ve incelemeleri takip edin.', icon: ShieldAlert, countKey: 'accidents'},
  {id: 'capa', title: 'DÖF', hint: 'Olay ve risk kayıtlarına bağlı faaliyetleri izleyin.', icon: ClipboardCheck, countKey: 'capa'},
  {id: 'isg_kurulu', title: 'İSG Kurulu', hint: 'Kurul üyelerini, toplantıları ve kararları yönetin.', icon: Users},
];

export function WorkplaceHomePage({user, onNavigate}) {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    setSummary(null);
    api('/workplace-portal/summary').then((body) => {
      if (!cancelled) setSummary(body);
    }).catch((err) => {
      if (!cancelled) setError(err.message || 'İşyeri özeti yüklenemedi.');
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [user?.company_id, reload]);

  return (
    <div className="workplace-home">
      <section className="workplace-home-heading panel">
        <div>
          <span className="workplace-home-eyebrow">İŞYERİ ANA PANELİ</span>
          <h3>{summary?.company_name || 'İşyeri kayıtlarınız'}</h3>
          <p>İş sağlığı ve güvenliği işlemlerinizi aşağıdaki kartlardan veya sol menüden yönetin.</p>
        </div>
        <div className="workplace-home-actions">
          <button type="button" className="secondary" onClick={() => onNavigate?.('site_qr_kiosk')}>
            <QrCode size={18}/> İşyeri QR
          </button>
          <button type="button" className="secondary" onClick={() => onNavigate?.('employer_oversight')}>
            <FileText size={18}/> Denetim durumu
          </button>
        </div>
      </section>
      <div className="workplace-home-status">
        <p>Yalnız bağlı olduğunuz işyerinin kayıtları gösterilir.</p>
        <button type="button" className="mini secondary" disabled={loading} onClick={() => setReload((value) => value + 1)}>
          <RefreshCw size={15}/> Özeti yenile
        </button>
      </div>
      {error && (
        <div className="workplace-home-error" role="alert">
          <strong>Kayıt sayıları yüklenemedi.</strong> {error} Modülleri açabilir veya özeti yeniden yükleyebilirsiniz.
        </div>
      )}
      <div className="workplace-module-grid" aria-busy={loading}>
        {MODULE_CARDS.map((card) => {
          const Icon = card.icon;
          const count = summary?.counts?.[card.countKey];
          return (
            <button
              type="button"
              key={card.id}
              className="workplace-module-card"
              onClick={() => onNavigate?.(card.id)}
              aria-label={`${card.title} modülünü aç`}
            >
              <span className="workplace-module-icon"><Icon size={22}/></span>
              <span className="workplace-module-title">{card.title}</span>
              <span className="workplace-module-hint">{card.hint}</span>
              <span className="workplace-module-footer">
                <span>{card.countKey ? (loading ? 'Yükleniyor…' : error || count == null ? 'Sayı alınamadı' : `${count} kayıt`) : 'Üyeler ve toplantılar'}</span>
                <ArrowRight size={18}/>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
