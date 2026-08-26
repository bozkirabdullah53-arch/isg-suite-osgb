import React, {useCallback, useEffect, useState} from 'react';
import {
  AlertTriangle,
  ArrowRight,
  ArrowLeft,
  Building2,
  CalendarDays,
  ClipboardCheck,
  Download,
  FileText,
  Gavel,
  HardHat,
  HeartPulse,
  Lightbulb,
  Printer,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Users,
  WalletCards,
  X,
} from 'lucide-react';
import {api, downloadFile} from './api';

const STATUS_LABELS = {ok: 'Uygun', warning: 'Ä°zlem', critical: 'Kritik', unknown: 'Belirsiz'};
const EVENT_LABELS = {
  near_miss: 'Ramak kala',
  accident: 'Ä°ÅŸ kazasÄ±',
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
      {STATUS_LABELS[status] || status || 'â€”'}
    </span>
  );
}

function Metric({label, value, tone}) {
  const color = tone === 'danger' ? '#b91c1c' : tone === 'warn' ? '#b45309' : undefined;
  return (
    <article className="metric">
      <span>{label}</span>
      <strong style={{color}}>{value ?? 'â€”'}</strong>
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

function SimpleTable({cols, rows, empty = 'KayÄ±t yok.'}) {
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
                <td key={c.key}>{c.render ? c.render(r) : String(r[c.key] ?? 'â€”')}</td>
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
  const [inspReport, setInspReport] = useState(null);
  const [inspBusy, setInspBusy] = useState(false);
  const [inspErr, setInspErr] = useState('');
  const [inspOpen, setInspOpen] = useState(false);

  async function runInspector() {
    setInspOpen(true);
    setInspBusy(true);
    setInspErr('');
    setInspReport(null);
    try {
      const r = await api('/risks/virtual-inspector', {
        method: 'POST',
        body: JSON.stringify({company_id: Number(companyId)}),
      });
      setInspReport(r);
    } catch (e) {
      setInspErr(e.message || 'Sanal MÃ¼fettiÅŸ Ã§alÄ±ÅŸtÄ±rÄ±lamadÄ±.');
    } finally {
      setInspBusy(false);
    }
  }

  const load = useCallback(async () => {
    if (!companyId) return;
    setBusy(true);
    setErr('');
    try {
      const res = await api(`/companies/${companyId}/status`);
      setData(res);
    } catch (e) {
      setErr(e.message || 'Ã–zet yÃ¼klenemedi.');
      setData(null);
    } finally {
      setBusy(false);
    }
  }, [companyId]);

  useEffect(() => { void load(); }, [load]);

  const c = data?.company;
  const counts = data?.counts || {};
  const compliance = data?.compliance || {};
  const statusCenter = data?.status_center || {};

  function goToModule(moduleId) {
    if (!moduleId || !onNavigate) return;
    try { sessionStorage.setItem('isg_status_company_id', String(companyId)); } catch (_) { /* ignore */ }
    onNavigate(moduleId);
  }

  async function exportReport(type) {
    setErr('');
    try {
      await downloadFile(
        `/companies/${companyId}/status/report.${type}`,
        `isyeri-durum-${companyId}.${type}`,
      );
    } catch (e) {
      setErr(e.message || 'Rapor oluÅŸturulamadÄ±.');
    }
  }

  return (
    <div className="page">
      <header className="page-head" style={{marginBottom: 16}}>
        <div style={{display: 'flex', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap'}}>
          {onBack && (
            <button type="button" className="mini secondary" onClick={onBack} style={{marginTop: 4}}>
              <ArrowLeft size={16} style={{verticalAlign: 'middle', marginRight: 4}} />
              Ä°ÅŸyerleri
            </button>
          )}
          <div style={{flex: 1, minWidth: 240}}>
            <h2 style={{margin: '0 0 4px', display: 'flex', alignItems: 'center', gap: 8}}>
              <Building2 size={22} />
              {c?.name || 'Ä°ÅŸyeri Durum Merkezi'}
            </h2>
            <p style={{margin: 0, color: '#64748b', fontSize: 13}}>
              Ä°ÅŸyeri Durum Merkezi Â· gerÃ§ek Ã¼retim kayÄ±tlarÄ±ndan birleÅŸik gÃ¶rÃ¼nÃ¼m
              {c?.sgk_registry_no ? ` Â· Sicil: ${c.sgk_registry_no}` : ''}
              {c?.hazard_class ? ` Â· ${c.hazard_class}` : ''}
            </p>
          </div>
          <div style={{display: 'flex', gap: 8, flexWrap: 'wrap'}}>
            <button type="button" className="mini secondary" disabled={busy} onClick={() => void exportReport('pdf')}>
              <Download size={14} style={{verticalAlign: 'middle', marginRight: 4}} />PDF
            </button>
            <button type="button" className="mini secondary" disabled={busy} onClick={() => void exportReport('xlsx')}>
              <Download size={14} style={{verticalAlign: 'middle', marginRight: 4}} />Excel
            </button>
            <button type="button" className="mini secondary" onClick={() => window.print()}>
              <Printer size={14} style={{verticalAlign: 'middle', marginRight: 4}} />YazdÄ±r
            </button>
            <button type="button" className="mini" disabled={busy} onClick={load}>
              <RefreshCw size={14} style={{verticalAlign: 'middle', marginRight: 4}} />Yenile
            </button>
            <button type="button" className="mini" disabled={inspBusy} onClick={runInspector}>
              <Gavel size={14} style={{verticalAlign: 'middle', marginRight: 4}} />Sanal MÃ¼fettiÅŸ
            </button>
          </div>
        </div>
      </header>

      {err && <p style={{color: '#b91c1c'}}>{err}</p>}
      {busy && !data && <p className="loading">MÃ¼ÅŸteri Ã¶zeti yÃ¼kleniyorâ€¦</p>}

      {data && (
        <>
          <section className="panel" style={{marginBottom: 16, borderLeft: `4px solid ${statusCenter.overall_status === 'critical' ? '#dc2626' : statusCenter.overall_status === 'warning' ? '#d97706' : '#16a34a'}`}}>
            <div style={{display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center', flexWrap: 'wrap'}}>
              <div>
                <h3 style={{margin: '0 0 4px'}}>Genel uyum durumu</h3>
                <p style={{margin: 0, color: '#475569'}}>{statusCenter.overall_label || 'HesaplanÄ±yor'}</p>
              </div>
              <div style={{textAlign: 'right'}}>
                <strong style={{fontSize: 28, color: '#0f4c81'}}>%{statusCenter.completion_pct ?? 0}</strong>
                <div style={{fontSize: 12, color: '#64748b'}}>Ã¶lÃ§Ã¼lebilir sÃ¼reÃ§ tamamlanmasÄ±</div>
              </div>
            </div>
            <div className="cards osgb-cards" style={{marginTop: 14}}>
              <Metric label="Tamamlanan" value={statusCenter.summary?.completed || 0} />
              <Metric label="Eksik" value={statusCenter.summary?.missing || 0} tone={statusCenter.summary?.missing ? 'danger' : undefined} />
              <Metric label="GecikmiÅŸ" value={statusCenter.summary?.overdue || 0} tone={statusCenter.summary?.overdue ? 'danger' : undefined} />
              <Metric label="YaklaÅŸan" value={statusCenter.summary?.due_soon || 0} tone={statusCenter.summary?.due_soon ? 'warn' : undefined} />
            </div>
            <p style={{margin: '12px 0 0', fontSize: 12, color: '#64748b'}}>
              Ä°BYS durumu: ResmÃ® doÄŸrulama ve kabul bekleniyor. Bu ekran â€œÄ°BYS Readyâ€ beyanÄ± deÄŸildir.
            </p>
          </section>

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

          <Panel title="Eksikler, tamamlanan sÃ¼reÃ§ler ve sorumlular" icon={ClipboardCheck}>
            <SimpleTable
              cols={[
                {key: 'title', label: 'SÃ¼reÃ§'},
                {key: 'status_label', label: 'Durum', render: (r) => (
                  <span style={{fontWeight: 700, color: r.critical ? '#b91c1c' : r.status === 'completed' ? '#166534' : '#92400e'}}>
                    {r.status_label}
                  </span>
                )},
                {key: 'detail', label: 'GerÃ§ek veri sonucu'},
                {key: 'responsible_role', label: 'Sorumlu'},
                {key: 'module', label: 'Kaynak', render: (r) => (
                  <button type="button" className="mini secondary" onClick={() => goToModule(r.module)}>
                    ModÃ¼le git <ArrowRight size={13} style={{verticalAlign: 'middle'}} />
                  </button>
                )},
              ]}
              rows={statusCenter.items || []}
              empty="Durum verisi bulunamadÄ±."
            />
          </Panel>

          <Panel title="YaklaÅŸan ve gecikmiÅŸ terminler" icon={CalendarDays}>
            <SimpleTable
              cols={[
                {key: 'source', label: 'Kaynak'},
                {key: 'title', label: 'Konu'},
                {key: 'due_date', label: 'Termin'},
                {key: 'days_left', label: 'Kalan gÃ¼n', render: (r) => (
                  <strong style={{color: r.days_left < 0 ? '#b91c1c' : r.days_left <= 30 ? '#b45309' : undefined}}>{r.days_left}</strong>
                )},
                {key: 'responsible_role', label: 'Sorumlu'},
                {key: 'module', label: 'Ä°ÅŸlem', render: (r) => (
                  <button type="button" className="mini secondary" onClick={() => goToModule(r.module)}>AÃ§</button>
                )},
              ]}
              rows={statusCenter.deadlines || []}
              empty="Takip edilen yaklaÅŸan veya gecikmiÅŸ termin yok."
            />
          </Panel>

          <div className="cards osgb-cards" style={{marginBottom: 16}}>
            <Metric label="Personel" value={counts.employees} />
            <Metric label="Åžube" value={counts.branches} />
            <Metric label="GÃ¶revlendirme" value={counts.assignments} />
            <Metric
              label="6331 Skoru"
              value={compliance.worst_score != null ? `%${compliance.worst_score}` : 'â€”'}
              tone={compliance.worst_status === 'critical' ? 'danger' : compliance.worst_status === 'warning' ? 'warn' : undefined}
            />
            <Metric label="AÃ§Ä±k Risk" value={counts.open_risks} tone={counts.open_risks > 0 ? 'warn' : undefined} />
            <Metric label="AÃ§Ä±k DÃ–F" value={counts.open_dofs} tone={counts.overdue_dofs > 0 ? 'danger' : undefined} />
            <Metric label="GecikmiÅŸ Muayene" value={data.health?.overdue} tone={data.health?.overdue > 0 ? 'warn' : undefined} />
            <Metric label="EÄŸitim KaydÄ±" value={counts.trainings} />
          </div>

          <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16, marginBottom: 16}}>
            <Panel title="Profil" icon={Building2}>
              <dl style={{margin: 0, display: 'grid', gap: 8, fontSize: 14}}>
                <div><dt style={{color: '#64748b', fontSize: 12}}>Yetkili</dt><dd style={{margin: '2px 0 0'}}>{c?.authorized_person || 'â€”'}</dd></div>
                <div><dt style={{color: '#64748b', fontSize: 12}}>Telefon</dt><dd style={{margin: '2px 0 0'}}>{c?.phone || 'â€”'}</dd></div>
                <div><dt style={{color: '#64748b', fontSize: 12}}>Adres</dt><dd style={{margin: '2px 0 0'}}>{c?.address || 'â€”'}</dd></div>
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
                <p style={{color: '#64748b', margin: 0}}>Aktif gÃ¶revlendirme yok.</p>
              )}
              {(compliance.gaps || []).length > 0 && (
                <div style={{marginTop: 12}}>
                  <strong style={{fontSize: 13}}>Eksikler ({compliance.gap_count})</strong>
                  <ul style={{margin: '8px 0 0', paddingLeft: 18, fontSize: 13, color: '#475569'}}>
                    {compliance.gaps.slice(0, 5).map((g, i) => (
                      <li key={i} style={{marginBottom: 6}}>
                        <strong>{g.title}</strong> â€” {g.professional_name} ({g.role_label})
                        {g.detail && <div style={{fontSize: 12, color: '#64748b'}}>{g.detail}</div>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Panel>
          </div>

          <Panel
            title="GÃ¶revlendirmeler"
            icon={Users}
            action={onNavigate && (
              <button type="button" className="mini" onClick={() => onNavigate('assignments')}>TÃ¼mÃ¼</button>
            )}
          >
            <SimpleTable
              cols={[
                {key: 'professional_name', label: 'Profesyonel'},
                {key: 'role_label', label: 'Rol'},
                {key: 'required_minutes_monthly', label: 'Otomatik aylÄ±k sÃ¼re', render: (r) => (
                  <span>
                    <strong>{Number(r.required_minutes_monthly) || 0} dk</strong>
                    {r.required_equivalent && <small style={{display: 'block', color: '#64748b', marginTop: 3}}>{r.required_equivalent}</small>}
                  </span>
                )},
                {key: 'isg_katip_contract_number', label: 'Ä°SG-KATÄ°P'},
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

            <Panel title="Hizmet SÃ¶zleÅŸmeleri" icon={FileText}>
              <SimpleTable
                cols={[
                  {key: 'contract_number', label: 'No'},
                  {key: 'end_date', label: 'BitiÅŸ'},
                  {key: 'days_left', label: 'Kalan gÃ¼n', render: (r) => (
                    <span style={{color: r.expiring_soon ? '#b45309' : undefined, fontWeight: r.expiring_soon ? 700 : undefined}}>
                      {r.days_left ?? 'â€”'}
                    </span>
                  )},
                  {key: 'status', label: 'Durum'},
                ]}
                rows={data.contracts || []}
              />
            </Panel>
          </div>

          <Panel title="Ä°SG Ã–zeti (salt okunur)" icon={ShieldAlert}>
            <div className="cards osgb-cards" style={{marginBottom: 12}}>
              <Metric label="AÃ§Ä±k risk" value={counts.open_risks} tone={counts.open_risks ? 'warn' : undefined} />
              <Metric label="GecikmiÅŸ DÃ–F" value={counts.overdue_dofs} tone={counts.overdue_dofs ? 'danger' : undefined} />
              <Metric label="GecikmiÅŸ muayene" value={data.health?.overdue} tone={data.health?.overdue ? 'warn' : undefined} />
              <Metric label="YaklaÅŸan muayene" value={data.health?.due_soon} />
              <Metric label="GecikmiÅŸ plan" value={data.annual_plan?.delayed} tone={data.annual_plan?.delayed ? 'warn' : undefined} />
              <Metric label="KKD gecikmiÅŸ" value={data.ppe?.overdue} tone={data.ppe?.overdue ? 'warn' : undefined} />
              <Metric label="SÃ¼resi geÃ§miÅŸ dokÃ¼man" value={counts.expired_documents} tone={counts.expired_documents ? 'warn' : undefined} />
              <Metric label="YÄ±llÄ±k plan tamamlanan" value={`${data.annual_plan?.completed || 0}/${data.annual_plan?.total || 0}`} />
            </div>
            {(data.incidents || []).length > 0 && (
              <>
                <strong style={{fontSize: 13}}>Son olaylar</strong>
                <SimpleTable
                  cols={[
                    {key: 'form_no', label: 'Form'},
                    {key: 'event_type', label: 'TÃ¼r', render: (r) => EVENT_LABELS[r.event_type] || r.event_type},
                    {key: 'summary', label: 'Ã–zet'},
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
                <button type="button" className="mini" onClick={() => onNavigate('finance')}>Finans modÃ¼lÃ¼</button>
              )}
            >
              <p style={{margin: '0 0 12px', fontSize: 13, color: '#64748b'}}>
                Bekleyen tutar: <strong>{data.finance.pending_amount?.toLocaleString('tr-TR')} â‚º</strong>
              </p>
              <SimpleTable
                cols={[
                  {key: 'transaction_date', label: 'Tarih'},
                  {key: 'description', label: 'AÃ§Ä±klama'},
                  {key: 'amount', label: 'Tutar', render: (r) => `${r.amount?.toLocaleString('tr-TR')} â‚º`},
                  {key: 'status', label: 'Durum'},
                ]}
                rows={data.finance.recent}
              />
            </Panel>
          )}
        </>
      )}

      {inspOpen && (
        <div
          className="modal-bg"
          onMouseDown={(e) => e.target === e.currentTarget && setInspOpen(false)}
          style={{position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16}}
        >
          <section className="modal" role="dialog" aria-modal="true" style={{maxWidth: 760, width: '100%', maxHeight: '88vh', overflow: 'auto', background: '#fff', color: '#1f2937', borderRadius: 12, padding: 0}}>
            <header style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderBottom: '1px solid #e2e8f0', position: 'sticky', top: 0, background: '#fff', zIndex: 1}}>
              <div style={{display: 'flex', alignItems: 'center', gap: 10}}>
                <Gavel size={20} style={{color: '#dc2626'}} />
                <div>
                  <h3 style={{margin: 0}}>Sanal MÃ¼fettiÅŸ â€” {c?.name || 'Ä°ÅŸyeri'}</h3>
                  <p style={{margin: 0, fontSize: 12, color: '#64748b'}}>6331 sayÄ±lÄ± Kanun mevzuat uyum denetimi</p>
                </div>
              </div>
              <button type="button" className="icon" onClick={() => setInspOpen(false)} aria-label="Kapat" style={{border: 'none', background: 'none', cursor: 'pointer', padding: 4}}>
                <X size={20} />
              </button>
            </header>
            <div style={{padding: '20px'}}>
              {inspBusy && <p className="loading" style={{textAlign: 'center', padding: 24}}>Denetim yapÄ±lÄ±yorâ€¦</p>}
              {inspErr && <p style={{color: '#b91c1c'}}>{inspErr}</p>}
              {inspReport && (
                <div style={{display: 'flex', flexDirection: 'column', gap: 16}}>
                  <div style={{display: 'flex', gap: 14, flexWrap: 'wrap'}}>
                    <div style={{flex: '0 0 auto', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10, padding: '14px 22px', textAlign: 'center', minWidth: 130}}>
                      <div style={{fontSize: 11, color: '#64748b'}}>Uyum skoru</div>
                      <div style={{fontSize: 38, fontWeight: 800, color: inspReport.compliance_score >= 80 ? '#16a34a' : inspReport.compliance_score >= 60 ? '#ca8a04' : inspReport.compliance_score >= 40 ? '#ea580c' : '#dc2626', lineHeight: 1.1}}>
                        {inspReport.compliance_score}<span style={{fontSize: 16, color: '#94a3b8'}}>/100</span>
                      </div>
                    </div>
                    <div style={{flex: '1 1 240px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10, padding: '14px 18px'}}>
                      <div style={{fontSize: 11, color: '#64748b', marginBottom: 4}}>Tahmini idari para cezasÄ± riski</div>
                      <div style={{fontSize: 18, fontWeight: 700, color: '#0f172a'}}>
                        {inspReport.penalty_estimate?.min_tl?.toLocaleString('tr-TR')} â€“ {inspReport.penalty_estimate?.max_tl?.toLocaleString('tr-TR')} TL
                      </div>
                      <p style={{fontSize: 11, color: '#9ca3af', margin: '4px 0 0'}}>{inspReport.penalty_estimate?.note}</p>
                    </div>
                  </div>
                  <div style={{background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 10, padding: '12px 16px', color: '#92400e', fontSize: 13}}>
                    <strong style={{display: 'block', marginBottom: 4}}>Ã–zet</strong>
                    {inspReport.summary}
                    <div style={{fontSize: 11, color: '#9ca3af', marginTop: 4}}>Denetim: {inspReport.inspection_date} Â· {inspReport.engine}</div>
                  </div>
                  {(inspReport.findings || []).length > 0 ? (
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr><th>Kod</th><th>Ã–nem</th><th>BaÅŸlÄ±k</th><th>Mevzuat</th><th>Detay</th><th>Aksiyon</th></tr>
                        </thead>
                        <tbody>
                          {inspReport.findings.map((f) => {
                            const sev = f.severity === 'kritik' ? {bg: '#fee2e2', fg: '#991b1b', label: 'Kritik'} : f.severity === 'orta' ? {bg: '#fef3c7', fg: '#92400e', label: 'Orta'} : {bg: '#e0f2fe', fg: '#1e40af', label: 'DÃ¼ÅŸÃ¼k'};
                            return (
                              <tr key={f.code}>
                                <td><strong>{f.code}</strong></td>
                                <td><span style={{background: sev.bg, color: sev.fg, borderRadius: 6, padding: '2px 8px', fontSize: 11, fontWeight: 700}}>{sev.label}</span></td>
                                <td>{f.title}</td>
                                <td>{f.regulation_ref}</td>
                                <td style={{fontSize: 12, color: '#64748b'}}>{f.detail}</td>
                                <td style={{fontSize: 12}}>{f.suggested_action}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div style={{background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 10, padding: 14, color: '#166534'}}>
                      <ShieldCheck size={18} style={{verticalAlign: 'middle', marginRight: 6}} />Bu iÅŸyerinde mevzuat uyum ihlali tespit edilmedi. Tam uyumlu.
                    </div>
                  )}
                </div>
              )}
            </div>
          </section>
        </div>
      )}

    </div>
  );
}

export function WorkplaceStatusPage({user, onNavigate}) {
  const [companies, setCompanies] = useState([]);
  const [companyId, setCompanyId] = useState(user?.company_id ? String(user.company_id) : '');
  const [err, setErr] = useState('');

  useEffect(() => {
    let cancelled = false;
    api('/companies?active=true')
      .then((rows) => {
        if (cancelled) return;
        const list = Array.isArray(rows) ? rows : [];
        setCompanies(list);
        setCompanyId((current) => current || (list[0]?.id ? String(list[0].id) : ''));
      })
      .catch((e) => { if (!cancelled) setErr(e.message || 'Ä°ÅŸyerleri yÃ¼klenemedi.'); });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="page">
      <section className="panel" style={{marginBottom: 16}}>
        <label style={{display: 'grid', gap: 6, maxWidth: 520}}>
          <strong>Ä°ÅŸyeri seÃ§in</strong>
          <select value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
            <option value="">EriÅŸilebilir iÅŸyeri yok</option>
            {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
          </select>
        </label>
        {err && <p style={{color: '#b91c1c', marginBottom: 0}}>{err}</p>}
      </section>
      {companyId ? (
        <Customer360Page companyId={Number(companyId)} onNavigate={onNavigate} />
      ) : (
        <section className="panel"><p className="empty">RolÃ¼nÃ¼ze atanmÄ±ÅŸ aktif iÅŸyeri bulunamadÄ±.</p></section>
      )}
    </div>
  );
}

export default Customer360Page;
