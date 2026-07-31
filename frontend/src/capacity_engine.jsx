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
  const [msg, setMsg] = useState('');

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

  async function syncOne(id) {
    setBusy(true);
    setMsg('');
    try {
      const r = await api(`/osgb/assignments/${id}/sync-required`, {method: 'POST'});
      setMsg(r.message || 'Güncellendi.');
      await load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function syncAll() {
    if (!window.confirm('Tüm aktif görevlendirmelerin zorunlu dakikası mevzuat tablosuna göre güncellenecek. Devam?')) return;
    setBusy(true);
    setMsg('');
    try {
      const q = user?.osgb_id ? `?osgb_id=${user.osgb_id}` : '';
      const r = await api(`/osgb/capacity/sync-all-required${q}`, {method: 'POST'});
      setMsg(r.message || 'Toplu güncelleme tamam.');
      await load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

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
            6331 / İSG Hizmetleri Yönetmeliği — mevzuat asgari süre vs fiili saha yükü
            {data?.period ? ` · Dönem: ${data.period}` : ''}
          </p>
        </div>
        <div style={{display: 'flex', gap: 8, flexWrap: 'wrap'}}>
          <button type="button" className="mini" disabled={busy} onClick={load}><RefreshCw size={14} /> Yenile</button>
          <button type="button" className="mini" disabled={busy} onClick={syncAll}>Mevzuata göre toplu güncelle</button>
          {onNavigate && (
            <>
              <button type="button" className="mini secondary" onClick={() => onNavigate('assignments')}>Görevlendirmeler</button>
              <button type="button" className="mini secondary" onClick={() => onNavigate('visits')}>Saha takvimi</button>
            </>
          )}
        </div>
      </header>

      {err && <p style={{color: '#b91c1c'}}>{err}</p>}
      {msg && <p style={{color: '#166534'}}>{msg}</p>}

      {data && (
        <>
          <div className="cards osgb-cards" style={{marginBottom: 16}}>
            <article className="metric"><span>Aktif görevlendirme</span><strong>{s.assignments ?? 0}</strong></article>
            <article className="metric"><span>Kritik eksik işyeri</span><strong style={{color: s.under_served_firms ? '#b91c1c' : undefined}}>{s.under_served_firms ?? 0}</strong></article>
            <article className="metric"><span>İzlemde işyeri</span><strong style={{color: s.at_risk_firms ? '#b45309' : undefined}}>{s.at_risk_firms ?? 0}</strong></article>
            <article className="metric"><span>Kayıt ≠ mevzuat</span><strong style={{color: s.stored_mismatch ? '#b45309' : undefined}}>{s.stored_mismatch ?? 0}</strong></article>
            <article className="metric"><span>Aşırı yüklü profesyonel</span><strong style={{color: s.overloaded_professionals ? '#b91c1c' : undefined}}>{s.overloaded_professionals ?? 0}</strong></article>
          </div>

          {(s.under_served_firms > 0 || s.stored_mismatch > 0) && (
            <section className="panel" style={{marginBottom: 16, borderLeft: '4px solid #d97706'}}>
              <h3 style={{margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 15}}>
                <AlertTriangle size={18} color="#b45309" />
                Önerilen aksiyonlar
              </h3>
              <ul style={{margin: 0, paddingLeft: 20, color: '#475569', fontSize: 14}}>
                {s.under_served_firms > 0 && <li>Kritik işyerlerinde saha ziyaret süresini artırın veya görevlendirme kontrol edin.</li>}
                {s.stored_mismatch > 0 && <li>Kayıtlı zorunlu dakika mevzuattan farklı — &quot;Mevzuata göre toplu güncelle&quot; kullanın.</li>}
              </ul>
            </section>
          )}

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
                {key: 'legal_required_minutes', label: 'Mevzuat dk'},
                {key: 'stored_required_minutes', label: 'Kayıtlı dk', render: (r) => (
                  <span style={{color: r.stored_mismatch ? '#b45309' : undefined, fontWeight: r.stored_mismatch ? 700 : undefined}}>
                    {r.stored_required_minutes || '—'}
                  </span>
                )},
                {key: 'actual_minutes', label: 'Fiili dk'},
                {key: 'gap_minutes', label: 'Fark', render: (r) => (
                  <span style={{color: r.gap_minutes > 0 ? '#b91c1c' : '#166534', fontWeight: 700}}>
                    {r.gap_minutes > 0 ? `-${r.gap_minutes}` : r.gap_minutes}
                  </span>
                )},
                {key: 'status', label: 'Durum', render: (r) => <StatusBadge status={r.status} />},
                {key: 'sync', label: '', render: (r) => (
                  <button type="button" className="mini" disabled={busy} onClick={() => syncOne(r.assignment_id)}>Güncelle</button>
                )},
              ]}
            />
          </section>

          <section className="panel">
            <h3 style={{margin: '0 0 12px', fontSize: 16}}>Profesyonel yük özeti</h3>
            <Table
              empty="Profesyonel yük verisi yok."
              rows={data.professionals || []}
              cols={[
                {key: 'full_name', label: 'Profesyonel'},
                {key: 'certificate_class', label: 'Sınıf'},
                {key: 'firm_count', label: 'İşyeri', render: (r) => (
                  <span style={{color: r.overload_firms ? '#b91c1c' : undefined, fontWeight: r.overload_firms ? 700 : undefined}}>
                    {r.firm_count}{r.firm_limit ? ` / ${r.firm_limit}` : ''}
                  </span>
                )},
                {key: 'legal_total', label: 'Mevzuat toplam dk'},
                {key: 'required_total', label: 'Hedef toplam dk'},
                {key: 'actual_total', label: 'Fiili toplam dk'},
                {key: 'utilization_pct', label: 'Doluluk', render: (r) => `%${r.utilization_pct}`},
                {key: 'status', label: 'Durum', render: (r) => <StatusBadge status={r.status} />},
              ]}
            />
          </section>

          <p style={{fontSize: 12, color: '#94a3b8', marginTop: 12}}>
            {data.legal_basis}. Fiili süre: bu ay tamamlanan / defter yüklenen saha ziyaretleri.
          </p>
        </>
      )}
    </div>
  );
}

export default CapacityEnginePage;
