import React, {useEffect, useState} from 'react';
import {
  AlertTriangle, ArrowRight, Beaker, BellRing, CalendarDays, CheckCircle2,
  ClipboardCheck, FileText, Gauge, GraduationCap, HardHat, QrCode, RefreshCw,
  ShieldAlert, Users,
} from 'lucide-react';
import {api} from './api';
import {
  isWorkplaceManagerUser,
} from './workplace_user_policy';
import {
  workplaceAlertDeadlines,
  workplaceDateText,
  workplaceDeadlineText,
  workplaceStatusTone,
} from './workplace_alert_center';
import {rememberSelectedObligation} from './workplace_obligations';
import './workplace_home.css';

const MODULE_CARDS = [
  {id: 'employees', title: 'Personel', hint: 'Personel ekleyin, çalışan bilgilerini düzenleyin.', icon: Users, countKey: 'employees'},
  {id: 'remote_training', title: 'Uzaktan Eğitim', hint: 'Uzmanınızın işyerine tanımladığı paketleri çalışanlara atayın.', icon: GraduationCap, footer: 'Tanımlı eğitimleri aç'},
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
  const [statusCenter, setStatusCenter] = useState(null);
  const [statusError, setStatusError] = useState('');
  const [statusLoading, setStatusLoading] = useState(true);
  const [obligationFeed, setObligationFeed] = useState(null);
  const [obligationError, setObligationError] = useState('');
  const [obligationLoading, setObligationLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const moduleCards = MODULE_CARDS.filter(
    (card) => card.id !== 'remote_training' || isWorkplaceManagerUser(user),
  );
  const alertDeadlines = obligationFeed?.items?.filter((row) => row.status !== 'completed')
    || workplaceAlertDeadlines(statusCenter);
  const statusTone = workplaceStatusTone(statusCenter?.overall_status);

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

    setStatusLoading(true);
    setStatusError('');
    setStatusCenter(null);
    if (Number(user?.company_id) > 0) {
      api(`/companies/${user.company_id}/status`).then((body) => {
        if (!cancelled) setStatusCenter(body?.status_center || null);
      }).catch((err) => {
        if (!cancelled) setStatusError(err.message || 'İşyeri uyarıları yüklenemedi.');
      }).finally(() => {
        if (!cancelled) setStatusLoading(false);
      });
    } else {
      setStatusLoading(false);
    }

    setObligationLoading(true);
    setObligationError('');
    setObligationFeed(null);
    if (Number(user?.company_id) > 0) {
      const horizon = new Date();
      horizon.setDate(horizon.getDate() + 90);
      const dateTo = `${horizon.getFullYear()}-${String(horizon.getMonth() + 1).padStart(2, '0')}-${String(horizon.getDate()).padStart(2, '0')}`;
      api(`/companies/${user.company_id}/status/obligations?page=1&page_size=6&date_to=${dateTo}`).then((body) => {
        if (!cancelled) setObligationFeed(body);
      }).catch((err) => {
        if (!cancelled) setObligationError(err.message || 'Yükümlülük takvimi yüklenemedi.');
      }).finally(() => {
        if (!cancelled) setObligationLoading(false);
      });
    } else {
      setObligationLoading(false);
    }
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
          <button type="button" onClick={() => onNavigate?.('workplace_status')}>
            <BellRing size={18}/> İşyeri Durumu
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
      <section className={`workplace-alert-center workplace-alert-center--${statusTone}`} aria-busy={statusLoading || obligationLoading}>
        <div className="workplace-alert-header">
          <div>
            <span className="workplace-alert-eyebrow"><BellRing size={15}/> İSG UYARI MERKEZİ</span>
            <h3>{statusLoading ? 'Yükümlülükler kontrol ediliyor…' : (statusCenter?.overall_label || 'İşyeri durumu')}</h3>
            <p>Geciken ve yaklaşan tüm İSG tarihleri, mevcut modül kayıtlarından otomatik toplanır.</p>
          </div>
          <button type="button" className="secondary" onClick={() => onNavigate?.('workplace_status')}>
            Tüm durumu aç <ArrowRight size={17}/>
          </button>
        </div>

        {(statusError || obligationError) && (
          <div className="workplace-alert-error" role="alert">
            Uyarılar şu anda tam yüklenemedi: {statusError || obligationError}
          </div>
        )}

        {!(statusError && obligationError) && (
          <>
            <div className="workplace-alert-metrics">
              <article className="workplace-alert-metric workplace-alert-metric--danger">
                <span>Gecikmiş kayıt</span>
                <strong>{obligationLoading ? '—' : (obligationFeed?.summary?.overdue ?? statusCenter?.deadline_summary?.overdue ?? 0)}</strong>
              </article>
              <article className="workplace-alert-metric workplace-alert-metric--warning">
                <span>Çok Yakın (0–7 gün)</span>
                <strong>{obligationLoading ? '—' : (obligationFeed?.summary?.very_soon ?? 0)}</strong>
              </article>
              <article className="workplace-alert-metric">
                <span>Yaklaşıyor (8–30 gün)</span>
                <strong>{obligationLoading ? '—' : (obligationFeed?.summary?.approaching ?? statusCenter?.deadline_summary?.due_soon ?? 0)}</strong>
              </article>
              <article className="workplace-alert-metric workplace-alert-metric--success">
                <span>Tamamlanan kayıt</span>
                <strong>{obligationLoading ? '—' : (obligationFeed?.summary?.completed ?? 0)}</strong>
              </article>
            </div>

            {!statusLoading && !obligationLoading && alertDeadlines.length > 0 && (
              <div className="workplace-alert-list" aria-label="Öncelikli işyeri uyarıları">
                {alertDeadlines.map((row, index) => {
                  return (
                    <div className={`workplace-alert-row workplace-alert-row--${row.status}`} key={`${row.source}-${row.reference_id || index}-${row.due_date}`}>
                      <span className="workplace-alert-row-icon">
                        {row.status === 'overdue' ? <AlertTriangle size={18}/> : <CalendarDays size={18}/>}
                      </span>
                      <span className="workplace-alert-row-content">
                        <strong>{row.title}</strong>
                        <small>{row.source} · {workplaceDateText(row.due_date)} · {row.responsible_role}</small>
                      </span>
                      <span className="workplace-alert-row-days">{workplaceDeadlineText(row)}</span>
                      <button type="button" className="mini secondary" onClick={() => {
                        rememberSelectedObligation({
                          ...row,
                          company_id: row.company_id || Number(user?.company_id),
                          target: row.target || {
                            company_id: Number(user?.company_id),
                            module: row.module,
                            entity_type: row.source,
                            record_id: row.reference_id || null,
                          },
                        });
                        onNavigate?.('workplace_status');
                      }}>
                        Kaydı aç <ArrowRight size={14}/>
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            {!statusLoading && !obligationLoading && alertDeadlines.length === 0 && (
              <div className="workplace-alert-empty">
                <CheckCircle2 size={20}/>
                <span>Önümüzdeki 90 gün içinde gecikmiş veya yaklaşan kayıt görünmüyor.</span>
              </div>
            )}
          </>
        )}
      </section>
      <div className="workplace-module-grid" aria-busy={loading}>
        {moduleCards.map((card) => {
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
                <span>{card.countKey ? (loading ? 'Yükleniyor…' : error || count == null ? 'Sayı alınamadı' : `${count} kayıt`) : (card.footer || 'Üyeler ve toplantılar')}</span>
                <ArrowRight size={18}/>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
