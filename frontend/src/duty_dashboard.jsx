import React, {useEffect, useState} from 'react';
import {AlertTriangle, BellRing, CalendarClock, CheckCircle2, Clock3, Mail, RefreshCw, ShieldAlert} from 'lucide-react';
import {api} from './api';

const SEV = {
  overdue: {
    label: 'Günü geçen',
    bg: '#fff1f2',
    border: '#fecaca',
    fg: '#991b1b',
    icon: AlertTriangle,
  },
  due_soon: {
    label: 'Günü yaklaşıyor',
    bg: '#fffbeb',
    border: '#fde68a',
    fg: '#92400e',
    icon: CalendarClock,
  },
  missing: {
    label: 'Yapılmayan / eksik',
    bg: '#f8fafc',
    border: '#cbd5e1',
    fg: '#334155',
    icon: Clock3,
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
      <div>
        <button type="button" className="mini" onClick={() => onGo?.(a.module)}>
          Git → {a.module_label || a.module}
        </button>
      </div>
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
        <div style={{display: 'grid', gap: 10}}>
          {items.map((a, i) => (
            <AlertCard key={`${a.check_code}-${a.company_id}-${a.due_date}-${i}`} a={a} onGo={onGo} />
          ))}
        </div>
      ) : (
        <p style={{margin: 0, color: '#64748b', fontSize: 13}}>Bu kategoride kayıt yok.</p>
      )}
    </section>
  );
}

/** İSG Özeti — uzman / hekim / DSP sorumluluk paneli */
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

  useEffect(() => { load(); }, []);

  const sm = data?.summary || {};
  const alerts = data?.alerts || {overdue: [], due_soon: [], missing: []};

  return (
    <>
      <div className="welcome" style={{background: 'linear-gradient(120deg,#0f766e,#0e7490)'}}>
        <div>
          <h3 style={{marginBottom: 6}}>Sorumluluk panelim</h3>
          <p style={{margin: 0, opacity: 0.95}}>
            {data?.role_label || 'İSG Profesyoneli'} — yalnızca görevlendirildiğiniz işyerlerindeki
            günü geçen, yaklaşan ve yapılmayan 6331 faaliyetleri.
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
        <div className="actions">
          <button type="button" className="secondary" disabled={busy} onClick={load}>
            <RefreshCw size={16} /> Yenile
          </button>
        </div>
      </div>

      {err && <div className="error" style={{marginBottom: 12}}>{err}</div>}

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
        <article className="metric" style={{borderTop: '3px solid #0f766e'}}>
          <span>Atanan işyeri</span>
          <strong>{data?.workplace_count ?? summary?.company_count ?? '—'}</strong>
        </article>
      </div>

      {(sm.overdue > 0 || sm.due_soon > 0) && (
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
                  ? `${sm.overdue} geciken faaliyet — öncelikli müdahale`
                  : `${sm.due_soon} yaklaşan faaliyet — planlayın`}
              </strong>
              <div style={{fontSize: 13, color: '#64748b', marginTop: 2}}>
                Kartlara tıklayarak ilgili modüle gidin. OSGB yönetimi aynı sinyalleri Hizmet Denetimi’nde görür.
              </div>
            </div>
          </div>
        </section>
      )}

      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 14, marginBottom: 16}}>
        <AlertColumn title="Günü geçenler" items={alerts.overdue || []} tone="overdue" onGo={onNavigate} />
        <AlertColumn title="Günü yaklaşanlar" items={alerts.due_soon || []} tone="due_soon" onGo={onNavigate} />
        <AlertColumn title="Yapılmayanlar" items={alerts.missing || []} tone="missing" onGo={onNavigate} />
      </div>

      {!busy && data?.supported && sm.total === 0 && data.workplace_count > 0 && (
        <section className="panel" style={{marginBottom: 16, borderColor: '#a7f3d0', background: '#ecfdf5'}}>
          <p style={{margin: 0, color: '#065f46', fontWeight: 650, display: 'flex', alignItems: 'center', gap: 8}}>
            <CheckCircle2 size={18} /> Bu dönemde görevlendirildiğiniz işyerlerinde kritik eksik görünmüyor.
          </p>
        </section>
      )}

      <section className="panel" style={{marginBottom: 0}}>
        <h3 style={{marginTop: 0, display: 'flex', alignItems: 'center', gap: 8}}>
          <Mail size={18} /> Bildirim (OSGB bağlantısı)
        </h3>
        <p style={{marginTop: 0, color: '#475569', fontSize: 14, lineHeight: 1.55}}>
          Bu panel, OSGB Hizmet Denetimi ile aynı sorumluluk sinyallerini kullanır.
          İleride yaklaşan ve günü geçen faaliyetler, OSGB yönetimi onayıyla
          <strong> e-posta</strong> olarak profesyonelin adresine gönderilecek.
          E-posta altyapısı henüz kapalı — önce ekran uyarılarını netleştiriyoruz.
        </p>
        <div style={{fontSize: 12, color: '#64748b'}}>
          Durum: {data?.email_notifications?.enabled ? 'Aktif' : 'Planlandı (kapalı)'}
          {data?.period?.today ? ` · Bugün: ${data.period.today}` : ''}
        </div>
      </section>
    </>
  );
}

/** Yönetici / diğer roller — özet metrikler (özellik listesi yok) */
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
