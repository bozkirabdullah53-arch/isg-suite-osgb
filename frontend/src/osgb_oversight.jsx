import React, {useEffect, useMemo, useState} from 'react';
import {AlertTriangle, CheckCircle2, ClipboardCheck, RefreshCw, ShieldAlert, Stethoscope} from 'lucide-react';
import {api} from './api';

const TYPE_LABELS = {
  safety_specialist: 'İş Güvenliği Uzmanı',
  workplace_physician: 'İşyeri Hekimi',
  other_health_personnel: 'Diğer Sağlık Personeli',
};

const STATUS_LABELS = {
  ok: 'Uygun',
  warning: 'İzlem',
  critical: 'Kritik',
  unknown: 'Belirsiz',
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
      {STATUS_LABELS[status] || status}
    </span>
  );
}

function ScoreBar({score, status}) {
  const s = statusStyle(status);
  return (
    <div style={{minWidth: 120}}>
      <div style={{display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4}}>
        <span>Skor</span><strong>{score}%</strong>
      </div>
      <div style={{height: 8, background: '#e2e8f0', borderRadius: 99, overflow: 'hidden'}}>
        <div style={{width: `${Math.max(0, Math.min(100, score))}%`, height: '100%', background: s.fg}} />
      </div>
    </div>
  );
}

export function OsgbOversightPage({user}) {
  const [orgs, setOrgs] = useState([]);
  const [osgbId, setOsgbId] = useState('');
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  if (user.role !== 'global_admin') {
    return (
      <>
        <div className="page-title"><h3>OSGB Hizmet Denetimi</h3></div>
        <section className="panel">
          <p>Bu ekran yalnızca global yönetici tarafından görüntülenebilir.</p>
        </section>
      </>
    );
  }

  async function load(oid = osgbId) {
    setBusy(true);
    setError('');
    try {
      const o = await api('/osgb');
      setOrgs(o);
      const id = oid || (o[0] ? String(o[0].id) : '');
      if (!osgbId && id) setOsgbId(id);
      const q = id ? `?osgb_id=${id}` : '';
      const r = await api(`/osgb/oversight${q}`);
      setData(r);
      if (selected) {
        const again = (r.professionals || []).find((p) => p.professional_id === selected.professional_id);
        setSelected(again || null);
      }
    } catch (e) {
      setError(e.message || 'Yükleme başarısız.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { load(); }, []);

  const rows = useMemo(() => {
    let list = data?.professionals || [];
    if (typeFilter) list = list.filter((p) => p.professional_type === typeFilter);
    if (statusFilter) list = list.filter((p) => p.status === statusFilter);
    return list;
  }, [data, typeFilter, statusFilter]);

  const summary = data?.summary || {};

  return (
    <>
      <div className="page-title">
        <h3>OSGB Hizmet Denetimi</h3>
        <div className="actions">
          <button type="button" className="secondary" onClick={() => load()} disabled={busy}>
            <RefreshCw size={16} /> Yenile
          </button>
        </div>
      </div>

      <section className="panel" style={{marginBottom: 16}}>
        <p style={{marginTop: 0, color: '#475569'}}>
          6331 ve İSG hizmetleri yönetmeliği çerçevesinde, görevlendirilmiş uzman/hekim/DSP’nin
          atanmış işyerlerindeki zorunlu faaliyetleri yerine getirip getirmediğini izlersiniz.
          Bu panel yalnızca global yöneticiye açıktır.
        </p>
        <div className="form-grid" style={{gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', marginBottom: 0}}>
          <label className="field">
            <span>OSGB</span>
            <select
              value={osgbId}
              onChange={(e) => {
                setOsgbId(e.target.value);
                load(e.target.value);
              }}
            >
              {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Meslek</span>
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="">Tümü</option>
              {Object.entries(TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Durum</span>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">Tümü</option>
              {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
        </div>
        {data?.period && (
          <p style={{marginBottom: 0, fontSize: 13, color: '#64748b'}}>
            Dönem: {data.period.month}/{data.period.year} ({data.period.month_start} — {data.period.month_end})
          </p>
        )}
        {error && <p style={{color: '#b91c1c'}}>{error}</p>}
      </section>

      <div className="cards" style={{marginBottom: 16}}>
        <article className="metric"><span>Profesyonel</span><strong>{summary.professionals ?? 0}</strong></article>
        <article className="metric"><span>Görevlendirme</span><strong>{summary.assignments ?? 0}</strong></article>
        <article className="metric"><span>Uygun</span><strong style={{color: '#166534'}}>{summary.ok ?? 0}</strong></article>
        <article className="metric"><span>İzlem</span><strong style={{color: '#92400e'}}>{summary.warning ?? 0}</strong></article>
        <article className="metric"><span>Kritik</span><strong style={{color: '#991b1b'}}>{summary.critical ?? 0}</strong></article>
      </div>

      <div style={{display: 'grid', gridTemplateColumns: selected ? '1.1fr 1fr' : '1fr', gap: 16}}>
        <section className="panel">
          <h3 style={{marginTop: 0, display: 'flex', alignItems: 'center', gap: 8}}>
            <ClipboardCheck size={18} /> Profesyonel özet
          </h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Profesyonel</th>
                  <th>Görev</th>
                  <th>İşyeri</th>
                  <th>Skor</th>
                  <th>Durum</th>
                </tr>
              </thead>
              <tbody>
                {rows.length ? rows.map((p) => (
                  <tr
                    key={p.professional_id}
                    onClick={() => setSelected(p)}
                    style={{
                      cursor: 'pointer',
                      background: selected?.professional_id === p.professional_id ? '#f0fdfa' : undefined,
                    }}
                  >
                    <td>
                      <strong>{p.full_name}</strong>
                      {p.certificate_class && (
                        <div style={{fontSize: 12, color: '#64748b'}}>Sınıf {p.certificate_class}</div>
                      )}
                    </td>
                    <td>
                      <span style={{display: 'inline-flex', alignItems: 'center', gap: 6}}>
                        {p.professional_type === 'safety_specialist' ? <ShieldAlert size={14} /> : <Stethoscope size={14} />}
                        {TYPE_LABELS[p.professional_type] || p.professional_type}
                      </span>
                    </td>
                    <td>{p.firm_count}</td>
                    <td><ScoreBar score={p.score} status={p.status} /></td>
                    <td><StatusPill status={p.status} /></td>
                  </tr>
                )) : (
                  <tr><td colSpan={5} className="empty">Aktif görevlendirme bulunamadı.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {selected && (
          <section className="panel">
            <h3 style={{marginTop: 0}}>{selected.full_name}</h3>
            <p style={{color: '#64748b', marginTop: 0}}>
              {TYPE_LABELS[selected.professional_type]} · {selected.firm_count} işyeri · skor {selected.score}%
            </p>
            {selected.firms.map((f) => (
              <div
                key={f.assignment_id}
                style={{
                  border: '1px solid #e2e8f0',
                  borderRadius: 12,
                  padding: 14,
                  marginBottom: 12,
                  background: '#fff',
                }}
              >
                <div style={{display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start'}}>
                  <div>
                    <strong>{f.company_name}</strong>
                    <div style={{fontSize: 12, color: '#64748b'}}>
                      {f.hazard_class || 'Tehlike sınıfı —'}
                      {f.isg_katip_contract_number ? ` · İSG-KATİP ${f.isg_katip_contract_number}` : ''}
                    </div>
                  </div>
                  <div style={{textAlign: 'right'}}>
                    <StatusPill status={f.status} />
                    <div style={{fontSize: 12, marginTop: 6}}>{f.score}% · {f.failed_count} eksik</div>
                  </div>
                </div>
                <div style={{marginTop: 12, display: 'grid', gap: 8}}>
                  {f.checks.map((c) => (
                    <div
                      key={c.code}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '20px 1fr',
                        gap: 8,
                        alignItems: 'start',
                        padding: '8px 10px',
                        borderRadius: 8,
                        background: c.passed ? '#f8fafc' : '#fff1f2',
                      }}
                    >
                      {c.passed
                        ? <CheckCircle2 size={16} color="#16a34a" />
                        : <AlertTriangle size={16} color="#b91c1c" />}
                      <div>
                        <div style={{fontWeight: 650}}>{c.title}</div>
                        <div style={{fontSize: 12, color: '#64748b'}}>{c.legal}</div>
                        <div style={{fontSize: 13, marginTop: 2}}>{c.detail}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            {data?.legal_basis && (
              <div style={{fontSize: 12, color: '#64748b', marginTop: 8}}>
                Dayanak: {data.legal_basis.join(' · ')}
              </div>
            )}
          </section>
        )}
      </div>
    </>
  );
}
