import React, {useCallback, useEffect, useState} from 'react';
import {AlertTriangle, Gauge, RefreshCw, Scale} from 'lucide-react';
import {api} from './api';

const STATUS = {ok: 'Uygun', warning: 'İzlem', critical: 'Kritik', unknown: '—'};
const STATUS_COLOR = {
  ok: '#166534',
  warning: '#b45309',
  critical: '#b91c1c',
  unknown: '#64748b',
};

export const NORMAL_CAPACITY_MINUTES = 11_700;

export function capacityHoursText(value) {
  if (value == null) return '—';
  const total = Math.max(0, Number(value) || 0);
  const hours = Math.floor(total / 60);
  const minutes = total % 60;
  return minutes ? `${hours} saat ${String(minutes).padStart(2, '0')} dk` : `${hours} saat`;
}

export function capacityPercentValue(value) {
  return Number(((Math.max(0, Number(value) || 0) / NORMAL_CAPACITY_MINUTES) * 100).toFixed(1));
}

export function capacityPercentText(value) {
  const number = Number(value) || 0;
  return `%${Number.isInteger(number) ? number : number.toLocaleString('tr-TR', {minimumFractionDigits: 1, maximumFractionDigits: 1})}`;
}

function percentText(value) {
  return capacityPercentText(Math.round(Number(value) || 0));
}

function CapacityMetric({label, minutes, tone}) {
  if (minutes == null) {
    return <article className="metric"><span>{label}</span><strong>—</strong></article>;
  }
  const percent = capacityPercentValue(minutes);
  return (
    <article className="metric" style={tone ? {borderColor: tone} : undefined}>
      <span>{label}</span>
      <strong>{capacityHoursText(minutes)}</strong>
      <small style={{display: 'block', marginTop: 4, color: tone || '#64748b', fontWeight: 700}}>{percentText(percent)} kapasite</small>
    </article>
  );
}

function CapacityCell({minutes, tone}) {
  if (minutes == null) return '—';
  const percent = capacityPercentValue(minutes);
  return (
    <span style={{color: tone || undefined}}>
      <strong>{capacityHoursText(minutes)}</strong>
      <small style={{display: 'block', color: tone || '#64748b', marginTop: 3}}>{percentText(percent)}</small>
    </span>
  );
}

function displayRequirement(requirement) {
  if (!requirement || requirement.required_minutes == null || requirement.equivalent === 'Hesaplanamadı') return 'Hesaplanamadı';
  const hours = Number(requirement.hours) || 0;
  const minutes = String(Number(requirement.remaining_minutes) || 0).padStart(2, '0');
  return `${Number(requirement.required_minutes) || 0} dk/ay · ${hours} s ${minutes} dk`;
}

function fullTimeDescription(requirement) {
  const threshold = Number(requirement?.full_time_threshold_employees) || 0;
  if (!threshold) return '';
  const units = Number(requirement?.full_time_units) || 0;
  const remainder = Number(requirement?.full_time_remainder_employees) || 0;
  if (units > 0) return remainder > 0
    ? `${units} tam süreli eşik · kalan ${remainder} çalışan için kısmi süre`
    : `${units} tam süreli eşik`;
  return `Tam süreli eşik: ${threshold.toLocaleString('tr-TR')} çalışan`;
}

function RequirementCell({requirement}) {
  return (
    <span>
      <strong>{displayRequirement(requirement)}</strong>
      {requirement?.calculation && (
        <small style={{display: 'block', color: '#64748b', marginTop: 3}}>{requirement.calculation}</small>
      )}
      {fullTimeDescription(requirement) && (
        <small style={{display: 'block', color: '#475569', marginTop: 3}}>{fullTimeDescription(requirement)}</small>
      )}
    </span>
  );
}

function StatusBadge({status}) {
  return (
    <span style={{
      fontSize: 12, fontWeight: 700, padding: '3px 8px', borderRadius: 999,
      color: STATUS_COLOR[status] || STATUS_COLOR.unknown,
      background: `${STATUS_COLOR[status] || STATUS_COLOR.unknown}18`,
    }}>
      {STATUS[status] || status}
    </span>
  );
}

function Table({cols, rows, empty}) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{cols.map((c) => <th key={c.key}>{c.label}</th>)}</tr></thead>
        <tbody>
          {rows.length ? rows.map((r, i) => (
            <tr key={r.assignment_id ?? r.professional_id ?? i}>
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

export function CapacityEnginePage({user, onNavigate}) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    setErr('');
    try {
      const q = user?.osgb_id ? `?osgb_id=${user.osgb_id}` : '';
      setData(await api(`/osgb/capacity${q}`));
    } catch (e) {
      setErr(e.message || 'Kapasite verisi yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }, [user?.osgb_id]);

  useEffect(() => { void load(); }, [load]);

  const s = data?.summary || {};

  return (
    <div className="page">
      <header className="page-head" style={{marginBottom: 16, display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12}}>
        <div>
          <h2 style={{margin: '0 0 4px', display: 'flex', alignItems: 'center', gap: 8}}>
            <Gauge size={22} />
            Kapasite Motoru
          </h2>
          <p style={{margin: 0, color: '#64748b', fontSize: 13}}>
            NACE / tehlike sınıfı ve aktif çalışan sayısından aylık asgari süre otomatik hesaplanır
            {data?.period ? ` · Dönem: ${data.period}` : ''}
          </p>
        </div>
        <div style={{display: 'flex', gap: 8, flexWrap: 'wrap'}}>
          <button type="button" className="mini" disabled={busy} onClick={load}><RefreshCw size={14} /> Yenile</button>
          {onNavigate && (
            <>
              <button type="button" className="mini secondary" onClick={() => onNavigate('assignments')}>Görevlendirmeler</button>
              <button type="button" className="mini secondary" onClick={() => onNavigate('visits')}>Saha takvimi</button>
            </>
          )}
        </div>
      </header>

      {err && <p style={{color: '#b91c1c'}}>{err}</p>}

      {data && (
        <>
          <div className="cards osgb-cards" style={{marginBottom: 16}}>
            <article className="metric"><span>Aktif görevlendirme</span><strong>{s.assignments ?? 0}</strong></article>
            <article className="metric"><span>İSG profesyoneli</span><strong>{s.professionals ?? 0}</strong></article>
            <article className="metric"><span>Eksik hizmet işyeri</span><strong style={{color: s.under_served_firms ? '#b91c1c' : undefined}}>{s.under_served_firms ?? 0}</strong></article>
            <article className="metric"><span>Normal kapasite aşımı</span><strong style={{color: s.capacity_overloaded_professionals ? '#b91c1c' : '#166534'}}>{s.capacity_overloaded_professionals ?? 0}</strong></article>
            <article className="metric"><span>Tehlike sınıfı eksik</span><strong style={{color: s.unknown_hazard_workplaces ? '#b91c1c' : undefined}}>{s.unknown_hazard_workplaces ?? 0}</strong></article>
          </div>

          {(s.under_served_firms > 0 || s.stored_mismatch > 0) && (
            <section className="panel" style={{marginBottom: 16, borderLeft: '4px solid #d97706'}}>
              <h3 style={{margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 15}}>
                <AlertTriangle size={18} color="#b45309" />
                Önerilen aksiyonlar
              </h3>
              <ul style={{margin: 0, paddingLeft: 20, color: '#475569', fontSize: 14}}>
                {s.under_served_firms > 0 && <li>Kritik işyerlerinde saha ziyaret süresini artırın veya görevlendirme kontrol edin.</li>}
                {s.stored_mismatch > 0 && <li>Eski kayıtlı dakika değerleri farklı; geçerli hedef sunucu tarafından otomatik hesaplanıyor.</li>}
              </ul>
            </section>
          )}

          <section className="panel" style={{marginBottom: 16}}>
            <h3 style={{margin: '0 0 6px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 16}}>
              Aylık İSG hizmet gereksinimi
            </h3>
            <p style={{margin: '0 0 12px', color: '#64748b', fontSize: 13}}>
              NACE → tehlike sınıfı → aktif çalışan sayısı zinciri kullanılır. Süreler dakikadır; saat gösterimi yalnızca sunum içindir.
            </p>
            <Table
              empty="Aktif işyeri bulunamadı."
              rows={data.workplaces || []}
              cols={[
                {key: 'company_name', label: 'İşyeri'},
                {key: 'nace_code', label: 'NACE'},
                {key: 'hazard_class', label: 'Tehlike', render: (r) => (
                  <span>
                    <strong>{r.hazard_class || 'Belirlenemedi'}</strong>
                    {r.hazard_warning && <small style={{display: 'block', color: '#b45309', marginTop: 3}}>{r.hazard_warning}</small>}
                  </span>
                )},
                {key: 'employee_count', label: 'Aktif çalışan'},
                {key: 'specialist_requirement', label: 'İSG uzmanı', render: (r) => <RequirementCell requirement={r.specialist_requirement} />},
                {key: 'physician_requirement', label: 'İşyeri hekimi', render: (r) => <RequirementCell requirement={r.physician_requirement} />},
              ]}
            />
          </section>

          <section className="panel" style={{marginBottom: 16}}>
            <h3 style={{margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 16}}>
              <Scale size={18} />
              İşyeri kapasitesi
            </h3>
            <Table
              empty="Aktif görevlendirme yok."
              rows={data.firms || []}
              cols={[
                {key: 'company_name', label: 'İşyeri'},
                {key: 'role_label', label: 'Rol'},
                {key: 'hazard_class', label: 'Tehlike'},
                {key: 'employee_count', label: 'Çalışan'},
                {key: 'legal_required_minutes', label: 'Otomatik dk', render: (r) => (
                  <span>
                    <strong>{r.legal_required_minutes || 0} dk</strong>
                    <small style={{display: 'block', color: '#64748b', marginTop: 3}}>{r.required_hours || 0} s {String(r.required_remaining_minutes || 0).padStart(2, '0')} dk</small>
                  </span>
                )},
                {key: 'stored_required_minutes', label: 'Eski kayıt', render: (r) => (
                  <span style={{color: r.stored_mismatch ? '#b45309' : undefined, fontWeight: r.stored_mismatch ? 700 : undefined}}>
                    {r.stored_required_minutes || '—'}
                  </span>
                )},
                {key: 'planned_minutes', label: 'Planlanan dk'},
                {key: 'actual_minutes', label: 'Gerçekleşen dk'},
                {key: 'remaining_minutes', label: 'Kalan/boş dk'},
                {key: 'completion_pct', label: 'Hedef doluluğu', render: (r) => percentText(r.completion_pct)},
                {key: 'gap_minutes', label: 'Fark', render: (r) => (
                  <span style={{color: r.gap_minutes > 0 ? '#b91c1c' : '#166534', fontWeight: 700}}>
                    {r.gap_minutes > 0 ? `-${r.gap_minutes}` : r.gap_minutes}
                  </span>
                )},
                {key: 'status', label: 'Durum', render: (r) => <StatusBadge status={r.status} />},
              ]}
            />
          </section>

          <section className="panel">
            <h3 style={{margin: '0 0 6px', fontSize: 16}}>İSG profesyonelleri — kullanılan ve kalan süre</h3>
            <p style={{margin: '0 0 12px', color: '#64748b', fontSize: 13}}>
              Kullanılan süre, aktif görevlendirmelerin aylık toplamıdır. Kalan süre, 195 saatlik normal aylık kapasitedir.
            </p>
            <Table
              empty="Profesyonel yük verisi yok."
              rows={data.professionals || []}
              cols={[
                {key: 'full_name', label: 'Profesyonel'},
                {key: 'role_label', label: 'Rol'},
                {key: 'firm_count', label: 'İşyeri', render: (r) => (
                  <span style={{color: r.overload_firms ? '#b91c1c' : undefined, fontWeight: r.overload_firms ? 700 : undefined}}>
                    {r.firm_count}{r.firm_limit ? ` / ${r.firm_limit}` : ''}
                  </span>
                )},
                {key: 'capacity_used_minutes', label: 'Kullanılan süre', render: (r) => (
                  <CapacityCell minutes={r.capacity_used_minutes} tone={r.capacity_overloaded ? '#b91c1c' : undefined} />
                )},
                {key: 'capacity_remaining_minutes', label: 'Kalan süre', render: (r) => (
                  <CapacityCell minutes={r.capacity_remaining_minutes} tone={r.capacity_overloaded ? '#b91c1c' : '#166534'} />
                )},
                {key: 'capacity_overloaded', label: 'Durum', render: (r) => r.capacity_overloaded
                  ? <StatusBadge status="critical" />
                  : (r.capacity_remaining_minutes != null ? <StatusBadge status="ok" /> : '—')},
              ]}
            />
          </section>

          <p style={{fontSize: 12, color: '#94a3b8', marginTop: 12}}>
            {data.legal_basis}. Yeni uzman/hekim görevlendirmesi, ilgili profesyonelin kalan süresini aşacaksa kaydedilmez. Yıllık fazla çalışma sınırı bu sabit aylık kapasiteye eklenmez.
          </p>
        </>
      )}
    </div>
  );
}

/** Uzman/hekim ana sayfası — yalnızca giriş yapan profesyonelin kapasitesi. */
export function ProfessionalCapacityPanel({user}) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const supported = user?.role === 'safety_specialist' || user?.role === 'workplace_physician';

  const load = useCallback(async () => {
    if (!supported) return;
    setBusy(true);
    setErr('');
    try {
      setData(await api('/dashboard/my-capacity'));
    } catch (e) {
      setErr(e.message || 'Aylık kapasite verisi yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }, [supported]);

  useEffect(() => { void load(); }, [load]);

  if (!supported) return null;
  if (err) {
    return <section className="panel" style={{marginBottom: 16, borderColor: '#fecaca', color: '#991b1b'}}>{err}</section>;
  }
  if (!data) {
    return <section className="panel" style={{marginBottom: 16, color: '#64748b'}}>Aylık görevlendirme kapasitesi yükleniyor…</section>;
  }

  const professional = data.professionals?.[0] || null;
  const viewer = data.professional || professional;
  const usedMinutes = professional?.capacity_used_minutes ?? professional?.planned_total ?? 0;
  const capacityRemaining = professional?.capacity_remaining_minutes;

  return (
    <section className="panel" style={{marginBottom: 16, borderTop: '3px solid #0f766e'}}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap'}}>
        <div>
          <h3 style={{margin: '0 0 5px', fontSize: 16}}>
            Aylık görevlendirme sürem{data.period ? ` · ${data.period}` : ''}
          </h3>
          <p style={{margin: 0, color: '#64748b', fontSize: 13}}>
            {viewer?.role_label || 'İSG profesyoneli'}{viewer?.full_name ? ` · ${viewer.full_name}` : ''}
            {viewer?.certificate_class ? ` · Sınıf ${viewer.certificate_class}` : ''}
          </p>
        </div>
        <button type="button" className="mini" disabled={busy} onClick={() => void load()}><RefreshCw size={14} /> Yenile</button>
      </div>

      {data.error && <p style={{margin: '10px 0 0', color: '#b45309', fontSize: 13}}>{data.error}</p>}

      <div className="cards" style={{margin: '14px 0 16px'}}>
        <CapacityMetric label="Kullanılan süre" minutes={professional ? usedMinutes : null} tone={professional?.capacity_overloaded ? '#b91c1c' : undefined} />
        <CapacityMetric label="Kalan süre" minutes={professional ? capacityRemaining : null} tone={professional?.capacity_overloaded ? '#b91c1c' : '#166534'} />
      </div>

      <p style={{fontSize: 12, color: '#64748b', margin: '12px 0 0'}}>
        Kullanılan süre = aktif görevlendirmelerinizin aylık toplamı. Kalan süre = 195 saatlik normal aylık kapasite − kullanılan süre.
      </p>
    </section>
  );
}

export default CapacityEnginePage;
