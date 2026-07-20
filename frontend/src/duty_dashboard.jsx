import React, {useEffect, useState} from 'react';
import {
  AlertTriangle,
  BellRing,
  CalendarClock,
  CheckCircle2,
  Clock3,
  Download,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react';
import {api, downloadFile} from './api';

const SEV = {
  overdue: {
    label: 'Günü geçen',
    bg: '#fff1f2',
    border: '#fecaca',
    fg: '#991b1b',
    icon: AlertTriangle,
  },
  due_soon: {
    label: 'Yaklaşan',
    bg: '#fffbeb',
    border: '#fde68a',
    fg: '#92400e',
    icon: CalendarClock,
  },
  missing: {
    label: 'Yapılmayan',
    bg: '#f8fafc',
    border: '#cbd5e1',
    fg: '#334155',
    icon: Clock3,
  },
  done: {
    label: 'Yapılan',
    bg: '#ecfdf5',
    border: '#a7f3d0',
    fg: '#065f46',
    icon: CheckCircle2,
  },
};

function AlertCard({a, onGo}) {
  const s = SEV[a.severity] || SEV.missing;
  const Icon = s.icon;
  return (
    <article
      style={{
        border: `1px solid ${s.border}`,
        background: s.bg,
        borderRadius: 12,
        padding: '12px 14px',
        display: 'grid',
        gap: 6,
      }}
    >
      <div style={{display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start'}}>
        <div style={{display: 'flex', gap: 8, alignItems: 'center', color: s.fg, fontWeight: 700}}>
          <Icon size={16} />
          <span>{a.title}</span>
        </div>
        <span style={{fontSize: 12, fontWeight: 700, color: s.fg, whiteSpace: 'nowrap'}}>{s.label}</span>
      </div>
      <div style={{fontSize: 13, color: '#475569'}}>
        <strong>{a.company_name}</strong>
        {a.due_date ? ` · Termin: ${a.due_date}` : ''}
        {typeof a.days_left === 'number'
          ? (a.days_left < 0 ? ` · ${Math.abs(a.days_left)} gün gecikmiş` : ` · ${a.days_left} gün kaldı`)
          : ''}
      </div>
      <div style={{fontSize: 13, color: '#334155'}}>{a.detail}</div>
      {a.legal && <div style={{fontSize: 12, color: '#64748b'}}>{a.legal}</div>}
      {a.severity !== 'done' && a.module && (
        <div>
          <button type="button" className="mini" onClick={() => onGo?.(a.module)}>
            İşleme git → {a.module_label || a.module}
          </button>
        </div>
      )}
    </article>
  );
}

function AlertColumn({title, items, tone, onGo}) {
  const s = SEV[tone] || SEV.missing;
  return (
    <section className="panel" style={{margin: 0, borderColor: s.border, background: '#fff'}}>
      <h3 style={{marginTop: 0, marginBottom: 10, color: s.fg, display: 'flex', alignItems: 'center', gap: 8}}>
        <s.icon size={18} /> {title}
        <span style={{marginLeft: 'auto', fontSize: 13, fontWeight: 700}}>{items.length}</span>
      </h3>
      {items.length ? (
        <div style={{display: 'grid', gap: 10, maxHeight: 420, overflow: 'auto'}}>
          {items.map((a, i) => (
            <AlertCard key={`${a.check_code}-${a.company_id}-${a.due_date}-${a.severity}-${i}`} a={a} onGo={onGo} />
          ))}
        </div>
      ) : (
        <p style={{margin: 0, color: '#64748b', fontSize: 13}}>Bu kategoride kayıt yok.</p>
      )}
    </section>
  );
}

/** Ana sayfa — uzman / hekim / DSP görev durumu */
export function DutyDashboard({user, summary, onNavigate}) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    setErr('');
    try {
      setData(await api('/dashboard/my-duties'));
    } catch (e) {
      setErr(e.message || 'Uyarılar yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const sm = data?.summary || {};
  const alerts = data?.alerts || {overdue: [], due_soon: [], missing: [], done: []};
  const boardError = data?.error || err;
  const pct = sm.completion_pct ?? 0;

  async function exportReport() {
    try {
      await downloadFile('/dashboard/my-duties/export.txt', `gorev-durum-${new Date().toISOString().slice(0, 10)}.txt`);
    } catch (e) {
      setErr(e.message || 'Rapor indirilemedi.');
    }
  }

  return (
    <>
      <div className="welcome" style={{background: 'linear-gradient(120deg,#0f766e,#0e7490)'}}>
        <div>
          <h3 style={{marginBottom: 6}}>Ana sayfa — görev durumum</h3>
          <p style={{margin: 0, opacity: 0.95}}>
            {data?.role_label || 'İSG Profesyoneli'} — yapılan, yapılmayan, yaklaşan ve süresi geçen
            faaliyetler tek bakışta. Eksiklere tıklayıp ilgili modülde kayıt açabilirsiniz.
          </p>
        </div>
        <ShieldAlert size={54} />
      </div>

      <div className="page-title" style={{marginTop: 8}}>
        <h3 style={{fontSize: 16, fontWeight: 650}}>
          {user?.full_name}
          {data?.professional?.certificate_class ? ` · Sınıf ${data.professional.certificate_class}` : ''}
          {typeof data?.workplace_count === 'number' ? ` · ${data.workplace_count} işyeri` : ''}
        </h3>
        <div className="actions" style={{gap: 8, flexWrap: 'wrap'}}>
          <button type="button" className="secondary" disabled={busy} onClick={() => void load()}>
            <RefreshCw size={16} /> Yenile
          </button>
          <button type="button" disabled={busy || !data} onClick={() => void exportReport()}>
            <Download size={16} /> Durum raporu (TXT)
          </button>
        </div>
      </div>

      {boardError && <div className="error" style={{marginBottom: 12}}>{boardError}</div>}

      <div className="cards" style={{marginBottom: 16}}>
        <article className="metric" style={{borderTop: '3px solid #dc2626'}}>
          <span>Günü geçen</span>
          <strong style={{color: '#991b1c'}}>{sm.overdue ?? '—'}</strong>
        </article>
        <article className="metric" style={{borderTop: '3px solid #d97706'}}>
          <span>Yaklaşan (14 gün)</span>
          <strong style={{color: '#92400e'}}>{sm.due_soon ?? '—'}</strong>
        </article>
        <article className="metric" style={{borderTop: '3px solid #64748b'}}>
          <span>Yapılmayan</span>
          <strong>{sm.missing ?? '—'}</strong>
        </article>
        <article className="metric" style={{borderTop: '3px solid #059669'}}>
          <span>Yapılan</span>
          <strong style={{color: '#065f46'}}>{sm.done ?? '—'}</strong>
        </article>
        <article className="metric" style={{borderTop: '3px solid #0f766e'}}>
          <span>Tamamlanma</span>
          <strong>%{pct}</strong>
        </article>
      </div>

      {(sm.overdue > 0 || sm.due_soon > 0 || sm.missing > 0) && (
        <section
          className="panel"
          style={{
            marginBottom: 16,
            borderColor: sm.overdue ? '#fecaca' : '#fde68a',
            background: sm.overdue ? '#fff1f2' : '#fffbeb',
          }}
        >
          <div style={{display: 'flex', gap: 10, alignItems: 'center'}}>
            <BellRing size={20} color={sm.overdue ? '#b91c1c' : '#b45309'} />
            <div>
              <strong>
                {sm.overdue > 0
                  ? `${sm.overdue} süresi geçen faaliyet — öncelikli`
                  : sm.due_soon > 0
                    ? `${sm.due_soon} yaklaşan faaliyet`
                    : `${sm.missing} yapılmayan kontrol`}
              </strong>
              <div style={{fontSize: 13, color: '#64748b', marginTop: 2}}>
                Karttaki “İşleme git” ile ilgili sayfada kayıt oluşturun veya tamamlayın. Durum raporunu indirip OSGB’ye iletebilirsiniz.
              </div>
            </div>
          </div>
        </section>
      )}

      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))', gap: 14, marginBottom: 16}}>
        <AlertColumn title="Günü geçenler" items={alerts.overdue || []} tone="overdue" onGo={onNavigate} />
        <AlertColumn title="Yaklaşanlar" items={alerts.due_soon || []} tone="due_soon" onGo={onNavigate} />
        <AlertColumn title="Yapılmayanlar" items={alerts.missing || []} tone="missing" onGo={onNavigate} />
        <AlertColumn title="Yapılanlar" items={alerts.done || []} tone="done" onGo={onNavigate} />
      </div>

      {!busy && data?.supported && (sm.overdue || 0) === 0 && (sm.due_soon || 0) === 0 && (sm.missing || 0) === 0 && data.workplace_count > 0 && (
        <section className="panel" style={{marginBottom: 0, borderColor: '#a7f3d0', background: '#ecfdf5'}}>
          <p style={{margin: 0, color: '#065f46', fontWeight: 650, display: 'flex', alignItems: 'center', gap: 8}}>
            <CheckCircle2 size={18} /> Bu dönemde kritik eksik / gecikme görünmüyor. Yapılan kontroller sağdaki listede.
          </p>
        </section>
      )}
    </>
  );
}

/** Yönetici / diğer roller — özet metrikler */
export function AdminSummaryDashboard({summary}) {
  return (
    <>
      <div className="welcome">
        <div>
          <h3>Hoş geldiniz</h3>
          <p>İSG faaliyetlerini, riskleri, kazaları, DÖF süreçlerini ve eğitimleri tek merkezden yönetin.</p>
        </div>
      </div>
      <div className="cards">
        <article className="metric"><span>Aktif Firma</span><strong>{summary?.company_count ?? '—'}</strong></article>
        <article className="metric"><span>Aktif Personel</span><strong>{summary?.employee_count ?? '—'}</strong></article>
        <article className="metric"><span>Açık Risk</span><strong>{summary?.open_risks ?? '—'}</strong></article>
        <article className="metric"><span>Açık DÖF</span><strong>{summary?.open_capa ?? '—'}</strong></article>
      </div>
    </>
  );
}
