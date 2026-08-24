import React, {useCallback, useEffect, useState} from 'react';
import {Bell, CheckCircle2, ClipboardList, HardHat, HeartPulse, RefreshCw, ShieldCheck} from 'lucide-react';
import {api} from './api';
import {
  completedSelfServiceTraining,
  formatSelfServiceDate,
  rememberEmployeeTrainingAssignment,
  normalizeSelfServicePayload,
  totalSelfServiceTraining,
} from './employee_self_service_logic';
import './employee_self_service.css';

function statusLabel(value) {
  const labels = {
    not_started: 'Başlamadı',
    in_progress: 'Devam ediyor',
    completed: 'Tamamlandı',
    failed: 'Başarısız',
    planned: 'Planlandı',
    attended: 'Katıldı',
  };
  return labels[value] || value || '—';
}

function StatusBadge({value}) {
  const kind = value === 'completed' || value === 'successful' ? 'ok' : 'pending';
  return <span className={`ess-badge ${kind}`}>{statusLabel(value)}</span>;
}

function Empty({children}) {
  return <div className="ess-empty">{children}</div>;
}

export function EmployeeSelfServicePage({onOpenTraining}) {
  const [summary, setSummary] = useState(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setBusy(true);
    setError('');
    try {
      const payload = await api('/self-service/me');
      setSummary(normalizeSelfServicePayload(payload));
    } catch (err) {
      setError(err?.httpStatus === 404
        ? 'Çalışan paneli henüz bu hesap için etkin değil.'
        : String(err?.message || 'Çalışan paneli yüklenemedi.'));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (busy && !summary) {
    return <div className="employee-self-service-page"><div className="ess-state">Panel yükleniyor…</div></div>;
  }
  if (error && !summary) {
    return (
      <div className="employee-self-service-page">
        <div className="ess-state ess-state-error">
          <ShieldCheck size={24}/>
          <strong>{error}</strong>
          <button type="button" className="ess-button" onClick={() => void load()}>
            <RefreshCw size={16}/> Tekrar dene
          </button>
        </div>
      </div>
    );
  }

  const data = summary || normalizeSelfServicePayload({});
  const totalTraining = totalSelfServiceTraining(data);
  const completedTraining = completedSelfServiceTraining(data);

  return (
    <div className="employee-self-service-page">
      <div className="ess-header">
        <div>
          <span className="ess-eyebrow">İSG Suite · Çalışan erişimi</span>
          <h1>Çalışan Panelim</h1>
          <p>
            {data.employee.fullName} · {data.scope.companyName}
            {data.scope.branchName ? ` · ${data.scope.branchName}` : ''}
          </p>
        </div>
        <button type="button" className="ess-button secondary" onClick={() => void load()} disabled={busy}>
          <RefreshCw size={16} className={busy ? 'ess-spin' : ''}/> Yenile
        </button>
      </div>

      <div className="ess-identity-strip">
        <div><span>Görev</span><strong>{data.employee.jobTitle}</strong></div>
        <div><span>Bölüm</span><strong>{data.employee.department}</strong></div>
        <div><span>İşe başlangıç</span><strong>{formatSelfServiceDate(data.employee.startDate)}</strong></div>
        <div className="ess-read-only-mark"><ShieldCheck size={18}/><span>Salt okunur</span></div>
      </div>

      {error && <div className="ess-inline-error">{error}</div>}

      <div className="ess-stat-grid">
        <div className="ess-stat-card"><ClipboardList size={22}/><span>Eğitim kaydı</span><strong>{totalTraining}</strong></div>
        <div className="ess-stat-card"><CheckCircle2 size={22}/><span>Tamamlanan</span><strong>{completedTraining}</strong></div>
        <div className="ess-stat-card"><HardHat size={22}/><span>KKD kaydı</span><strong>{data.ppe.total}</strong></div>
        <div className="ess-stat-card"><Bell size={22}/><span>Okunmamış bildirim</span><strong>{data.notifications.unread}</strong></div>
      </div>

      <div className="ess-content-grid">
        <section className="ess-card">
          <div className="ess-card-title"><ClipboardList size={20}/><h2>Eğitimlerim</h2></div>
          {data.training.remote.available && data.training.remote.assignments.length > 0 && (
            <div className="ess-list">
              {data.training.remote.assignments.map((item) => (
                <div className="ess-list-row ess-training-row" key={`remote-${item.id}`}>
                  <div><strong>{item.title}</strong><small>Uzaktan eğitim · Son tarih: {formatSelfServiceDate(item.due_date)}</small></div>
                  <div className="ess-training-actions">
                    <StatusBadge value={item.status}/>
                    <button
                      type="button"
                      className="ess-button ess-button-small"
                      disabled={typeof onOpenTraining !== 'function'}
                      onClick={() => {
                        rememberEmployeeTrainingAssignment(item.id);
                        onOpenTraining?.(item.id);
                      }}
                    >
                      {item.status === 'in_progress' ? 'Devam et' : item.status === 'completed' ? 'Tekrar görüntüle' : 'Eğitimi aç'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
          {data.training.classroom.history.length > 0 && (
            <div className="ess-list">
              {data.training.classroom.history.map((item) => (
                <div className="ess-list-row" key={`classroom-${item.id}`}>
                  <div><strong>{item.title}</strong><small>{formatSelfServiceDate(item.start_date)} · {item.training_type || 'Eğitim'}</small></div>
                  <StatusBadge value={item.successful === true ? 'completed' : item.attended ? 'attended' : 'planned'}/>
                </div>
              ))}
            </div>
          )}
          {!data.training.remote.assignments.length && !data.training.classroom.history.length && (
            <Empty>Henüz size atanmış eğitim kaydı yok.</Empty>
          )}
        </section>

        <section className="ess-card">
          <div className="ess-card-title"><HardHat size={20}/><h2>KKD kayıtlarım</h2></div>
          {data.ppe.items.length ? (
            <div className="ess-list">
              {data.ppe.items.map((item) => (
                <div className="ess-list-row" key={item.id}>
                  <div><strong>{item.item_type}</strong><small>{item.category} · Adet: {item.quantity}</small></div>
                  <div className="ess-date-stack"><span>{formatSelfServiceDate(item.delivery_date)}</span><small>teslim</small></div>
                </div>
              ))}
            </div>
          ) : <Empty>Henüz KKD teslim kaydı yok.</Empty>}
        </section>

        <section className="ess-card">
          <div className="ess-card-title"><Bell size={20}/><h2>Bildirimler</h2></div>
          {data.notifications.items.length ? (
            <div className="ess-list">
              {data.notifications.items.map((item) => (
                <div className={`ess-list-row ${item.is_read ? '' : 'unread'}`} key={item.id}>
                  <div><strong>{item.title}</strong><small>{item.message}</small></div>
                  <span className="ess-notification-date">{formatSelfServiceDate(item.created_at)}</span>
                </div>
              ))}
            </div>
          ) : <Empty>Görüntülenecek bildirim yok.</Empty>}
        </section>

        <section className="ess-card ess-health-card">
          <div className="ess-card-title"><HeartPulse size={20}/><h2>Sağlık takvimi</h2></div>
          {data.health.hasRecord ? (
            <>
              <p className="ess-health-label">Sonraki muayene tarihi</p>
              <strong className="ess-health-date">{formatSelfServiceDate(data.health.nextExaminationDate)}</strong>
              <small>Bu panelde klinik sonuç, tanı, kısıt veya rapor içeriği gösterilmez.</small>
            </>
          ) : <Empty>Henüz sağlık takvimi kaydı bulunmuyor.</Empty>}
        </section>
      </div>
    </div>
  );
}
