import React, {useCallback, useEffect, useState} from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  Building2,
  CalendarDays,
  ClipboardCheck,
  FileText,
  HardHat,
  HeartPulse,
  RefreshCw,
  ShieldAlert,
  Stethoscope,
  Users,
  WalletCards,
} from 'lucide-react';
import {api} from './api';

const STATUS_LABELS = {ok: 'Uygun', warning: 'İzlem', critical: 'Kritik', unknown: 'Belirsiz'};
const EVENT_LABELS = {
  near_miss: 'Ramak kala',
  accident: 'İş kazası',
  hazard: 'Tehlike',
  emergency: 'Acil durum',
};

function statusStyle(status) {
  if (status === 'ok') return {bg: '#dcfce7', fg: '#166534'};
  if (status === 'warning') return {bg: '#fef3c7', fg: '#92400e'};
  if (status === 'critical') return {bg: '#fee2e2', fg: '#991b1b'};
  return {bg: '#e2e8f0', fg: '#475569'};
}

function StatusPill({status}) {
  const s = statusStyle(status);
  return (
    <span style={{
      display: 'inline-block', padding: '3px 10px', borderRadius: 999,
      background: s.bg, color: s.fg, fontSize: 12, fontWeight: 700,
    }}>
      {STATUS_LABELS[status] || status || '—'}
    </span>
  );
}

function Metric({label, value, tone}) {
  const color = tone === 'danger' ? '#b91c1c' : tone === 'warn' ? '#b45309' : undefined;
  return (
    <article className="metric">
      <span>{label}</span>
      <strong style={{color}}>{value ?? '—'}</strong>
    </article>
  );
}

function Panel({title, icon: Icon, children, action}) {
  return (
    <section className="panel" style={{marginBottom: 16}}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 12, flexWrap: 'wrap'}}>
        <h3 style={{margin: 0, display: 'flex', alignItems: 'center', gap: 8, fontSize: 16}}>
          {Icon && <Icon size={18} />}
          {title}
        </h3>
        {action}
      </div>
      {children}
    </section>
  );
}

function SimpleTable({cols, rows, empty = 'Kayıt yok.'}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{cols.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.length ? rows.map((r, i) => (
            <tr key={r.id ?? i}>
              {cols.map((c) => (
                <td key={c.key}>{c.render ? c.render(r) : String(r[c.key] ?? '—')}</td>
              ))}
            </tr>
          )) : (
            <tr><td colSpan={cols.length} className="empty">{empty}</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export function Customer360Page({companyId, onBack, onNavigate}) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!companyId) return;
    setBusy(true);
    setErr('');
    try {
      const res = await api(`/companies/${companyId}/overview`);
      setData(res);
    } catch (e) {
      setErr(e.message || 'Özet yüklenemedi.');
      setData(null);
    } finally {
      setBusy(false);
    }
  }, [companyId]);

  useEffect(() => { void load(); }, [load]);

  const c = data?.company;
  const counts = data?.counts || {};
  const compliance = data?.compliance || {};

  return (
    <div className="page">
      <header className="page-head" style={{marginBottom: 16}}>
        <div style={{display: 'flex', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap'}}>
          <button type="button" className="mini secondary" onClick={onBack} style={{marginTop: 4}}>
            <ArrowLeft size={16} style={{verticalAlign: 'middle', marginRight: 4}} />
            İşyerleri
          </button>
          <div style={{flex: 1, minWidth: 240}}>
            <h2 style={{margin: '0 0 4px', display: 'flex', alignItems: 'center', gap: 8}}>
              <Building2 size={22} />
              {c?.name || 'Müşteri 360'}
            </h2>
            <p style={{margin: 0, color: '#64748b', fontSize: 13}}>
              Tek ekranda operasyon, uyumluluk ve İSG özeti
              {c?.sgk_registry_no ? ` · Sicil: ${c.sgk_registry_no}` : ''}
              {c?.hazard_class ? ` · ${c.hazard_class}` : ''}
            </p>
          </div>
          <button type="button" className="mini" disabled={busy} onClick={load}>
            <RefreshCw size={14} style={{verticalAlign: 'middle', marginRight: 4}} />
            Yenile
          </button>
        </div>
      </header>

      {err && <p style={{color: '#b91c1c'}}>{err}</p>}
      {busy && !data && <p className="loading">Müşteri özeti yükleniyor…</p>}

      {data && (
        <>
          {(data.alerts || []).length > 0 && (
            <section className="panel" style={{marginBottom: 16, borderLeft: '4px solid #dc2626'}}>
              <h3 style={{margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 8}}>
                <AlertTriangle size={18} color="#b91c1c" />
                Dikkat gerektiren
              </h3>
              <ul style={{margin: 0, paddingLeft: 20, color: '#475569'}}>
                {data.alerts.map((a, i) => (
                  <li key={i} style={{marginBottom: 4}}>{a.text}</li>
                ))}
              </ul>
            </section>
          )}

          <div className="cards osgb-cards" style={{marginBottom: 16}}>
            <Metric label="Personel" value={counts.employees} />
            <Metric label="Şube" value={counts.branches} />
            <Metric label="Görevlendirme" value={counts.assignments} />
            <Metric
              label="6331 Skoru"
              value={compliance.worst_score != null ? `%${compliance.worst_score}` : '—'}
              tone={compliance.worst_status === 'critical' ? 'danger' : compliance.worst_status === 'warning' ? 'warn' : undefined}
            />
            <Metric label="Açık Risk" value={counts.open_risks} tone={counts.open_risks > 0 ? 'warn' : undefined} />
            <Metric label="Açık DÖF" value={counts.open_dofs} tone={counts.overdue_dofs > 0 ? 'danger' : undefined} />
            <Metric label="Gecikmiş Muayene" value={data.health?.overdue} tone={data.health?.overdue > 0 ? 'warn' : undefined} />
            <Metric label="Eğitim Kaydı" value={counts.trainings} />
          </div>

          <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16, marginBottom: 16}}>
            <Panel title="Profil" icon={Building2}>
              <dl style={{margin: 0, display: 'grid', gap: 8, fontSize: 14}}>
                <div><dt style={{color: '#64748b', fontSize: 12}}>Yetkili</dt><dd style={{margin: '2px 0 0'}}>{c?.authorized_person || '—'}</dd></div>
                <div><dt style={{color: '#64748b', fontSize: 12}}>Telefon</dt><dd style={{margin: '2px 0 0'}}>{c?.phone || '—'}</dd></div>
                <div><dt style={{color: '#64748b', fontSize: 12}}>Adres</dt><dd style={{margin: '2px 0 0'}}>{c?.address || '—'}</dd></div>
                <div><dt style={{color: '#64748b', fontSize: 12}}>Durum</dt><dd style={{margin: '2px 0 0'}}>{c?.is_active ? 'Aktif' : 'Pasif'}</dd></div>
              </dl>
            </Panel>

            <Panel
              title="6331 Uyumluluk"
              icon={ClipboardCheck}
              action={compliance.worst_status && <StatusPill status={compliance.worst_status} />}
            >
              {(compliance.professionals || []).length ? (
                <SimpleTable
                  cols={[
                    {key: 'professional_name', label: 'Profesyonel'},
                    {key: 'role_label', label: 'Rol'},
                    {key: 'score', label: 'Skor', render: (r) => `%${r.score}`},
                    {key: 'status', label: 'Durum', render: (r) => <StatusPill status={r.status} />},
                  ]}
                  rows={compliance.professionals}
                />
              ) : (
                <p style={{color: '#64748b', margin: 0}}>Aktif görevlendirme yok.</p>
              )}
              {(compliance.gaps || []).length > 0 && (
                <div style={{marginTop: 12}}>
                  <strong style={{fontSize: 13}}>Eksikler ({compliance.gap_count})</strong>
                  <ul style={{margin: '8px 0 0', paddingLeft: 18, fontSize: 13, color: '#475569'}}>
                    {compliance.gaps.slice(0, 5).map((g, i) => (
                      <li key={i} style={{marginBottom: 6}}>
                        <strong>{g.title}</strong> — {g.professional_name} ({g.role_label})
                        {g.detail && <div style={{fontSize: 12, color: '#64748b'}}>{g.detail}</div>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Panel>
          </div>

          <Panel
            title="Görevlendirmeler"
            icon={Users}
            action={onNavigate && (
              <button type="button" className="mini" onClick={() => onNavigate('assignments')}>Tümü</button>
            )}
          >
            <SimpleTable
              cols={[
                {key: 'professional_name', label: 'Profesyonel'},
                {key: 'role_label', label: 'Rol'},
                {key: 'required_minutes_monthly', label: 'Aylık dk'},
                {key: 'isg_katip_contract_number', label: 'İSG-KATİP'},
              ]}
              rows={data.assignments || []}
            />
          </Panel>

          <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16}}>
            <Panel
              title="Son Ziyaretler"
              icon={CalendarDays}
              action={onNavigate && (
                <button type="button" className="mini" onClick={() => onNavigate('visits')}>Saha takvimi</button>
              )}
            >
              <SimpleTable
                cols={[
                  {key: 'visit_date', label: 'Tarih'},
                  {key: 'professional_name', label: 'Profesyonel'},
                  {key: 'subject', label: 'Konu'},
                  {key: 'duration_minutes', label: 'Dk'},
                ]}
                rows={data.visits || []}
              />
            </Panel>

            <Panel title="Hizmet Sözleşmeleri" icon={FileText}>
              <SimpleTable
                cols={[
                  {key: 'contract_number', label: 'No'},
                  {key: 'end_date', label: 'Bitiş'},
                  {key: 'days_left', label: 'Kalan gün', render: (r) => (
                    <span style={{color: r.expiring_soon ? '#b45309' : undefined, fontWeight: r.expiring_soon ? 700 : undefined}}>
                      {r.days_left ?? '—'}
                    </span>
                  )},
                  {key: 'status', label: 'Durum'},
                ]}
                rows={data.contracts || []}
              />
            </Panel>
          </div>

          <Panel title="İSG Özeti (salt okunur)" icon={ShieldAlert}>
            <div className="cards osgb-cards" style={{marginBottom: 12}}>
              <Metric label="Açık risk" value={counts.open_risks} tone={counts.open_risks ? 'warn' : undefined} />
              <Metric label="Gecikmiş DÖF" value={counts.overdue_dofs} tone={counts.overdue_dofs ? 'danger' : undefined} />
              <Metric label="Gecikmiş muayene" value={data.health?.overdue} tone={data.health?.overdue ? 'warn' : undefined} />
              <Metric label="Yaklaşan muayene" value={data.health?.due_soon} />
              <Metric label="Gecikmiş plan" value={data.annual_plan?.delayed} tone={data.annual_plan?.delayed ? 'warn' : undefined} />
              <Metric label="KKD gecikmiş" value={data.ppe?.overdue} tone={data.ppe?.overdue ? 'warn' : undefined} />
              <Metric label="Süresi geçmiş doküman" value={counts.expired_documents} tone={counts.expired_documents ? 'warn' : undefined} />
              <Metric label="Yıllık plan tamamlanan" value={`${data.annual_plan?.completed || 0}/${data.annual_plan?.total || 0}`} />
            </div>
            {(data.incidents || []).length > 0 && (
              <>
                <strong style={{fontSize: 13}}>Son olaylar</strong>
                <SimpleTable
                  cols={[
                    {key: 'form_no', label: 'Form'},
                    {key: 'event_type', label: 'Tür', render: (r) => EVENT_LABELS[r.event_type] || r.event_type},
                    {key: 'summary', label: 'Özet'},
                    {key: 'event_date', label: 'Tarih'},
                  ]}
                  rows={data.incidents}
                />
              </>
            )}
          </Panel>

          {(data.finance?.recent || []).length > 0 && (
            <Panel
              title="Finans"
              icon={WalletCards}
              action={onNavigate && (
                <button type="button" className="mini" onClick={() => onNavigate('finance')}>Finans modülü</button>
              )}
            >
              <p style={{margin: '0 0 12px', fontSize: 13, color: '#64748b'}}>
                Bekleyen tutar: <strong>{data.finance.pending_amount?.toLocaleString('tr-TR')} ₺</strong>
              </p>
              <SimpleTable
                cols={[
                  {key: 'transaction_date', label: 'Tarih'},
                  {key: 'description', label: 'Açıklama'},
                  {key: 'amount', label: 'Tutar', render: (r) => `${r.amount?.toLocaleString('tr-TR')} ₺`},
                  {key: 'status', label: 'Durum'},
                ]}
                rows={data.finance.recent}
              />
            </Panel>
          )}
        </>
      )}
    </div>
  );
}

export default Customer360Page;
