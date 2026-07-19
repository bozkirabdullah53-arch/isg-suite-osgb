import React, {useEffect, useMemo, useState} from 'react';
import {AlertTriangle, CheckCircle2, ClipboardCheck, RefreshCw, ShieldAlert, Sparkles, Stethoscope} from 'lucide-react';
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
  if (status === 'ok') return {bg: '#dcfce7', fg: '#166534', bar: '#16a34a'};
  if (status === 'warning') return {bg: '#fef3c7', fg: '#92400e', bar: '#d97706'};
  if (status === 'critical') return {bg: '#fee2e2', fg: '#991b1b', bar: '#dc2626'};
  return {bg: '#e2e8f0', fg: '#475569', bar: '#64748b'};
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

/** Sütun grafik — sorumluluk alanları (uyum %) */
function ColumnChart({columns, height = 160, title}) {
  const cols = columns || [];
  if (!cols.length) {
    return <p style={{color: '#64748b', fontSize: 13}}>Grafik için veri yok.</p>;
  }
  return (
    <div>
      {title && <h4 style={{margin: '0 0 12px', fontSize: 14}}>{title}</h4>}
      <div style={{
        display: 'flex', alignItems: 'flex-end', gap: 10, height,
        borderBottom: '1px solid #e2e8f0', paddingBottom: 4,
      }}>
        {cols.map((c) => {
          const s = statusStyle(c.status);
          const h = Math.max(6, Math.round((Math.min(100, c.pct || 0) / 100) * (height - 28)));
          return (
            <div key={c.code} style={{flex: 1, minWidth: 0, textAlign: 'center'}} title={`${c.title}: %${c.pct}`}>
              <div style={{fontSize: 11, fontWeight: 700, color: s.fg, marginBottom: 4}}>%{c.pct}</div>
              <div style={{
                height: h, margin: '0 auto', width: '70%', maxWidth: 48,
                borderRadius: '8px 8px 2px 2px', background: s.bar,
              }} />
            </div>
          );
        })}
      </div>
      <div style={{display: 'flex', gap: 10, marginTop: 8}}>
        {cols.map((c) => (
          <div key={c.code} style={{flex: 1, minWidth: 0, textAlign: 'center', fontSize: 11, color: '#475569', lineHeight: 1.25}}>
            {c.title}
            {c.failed > 0 && <div style={{color: '#b91c1c', fontWeight: 650}}>{c.failed} eksik</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

function ScoreBar({score, status}) {
  const s = statusStyle(status);
  return (
    <div style={{minWidth: 110}}>
      <div style={{display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4}}>
        <span>Skor</span><strong>{score}%</strong>
      </div>
      <div style={{height: 8, background: '#e2e8f0', borderRadius: 99, overflow: 'hidden'}}>
        <div style={{width: `${Math.max(0, Math.min(100, score))}%`, height: '100%', background: s.bar}} />
      </div>
    </div>
  );
}

function goModuleHint(checkCode) {
  if (['risk_degerlendirme', 'risk_dof'].includes(checkCode)) return 'Risk Analizi';
  if (checkCode === 'yillik_plan') return 'Yıllık Plan';
  if (checkCode === 'egitim') return 'Eğitimler';
  if (checkCode === 'olay_takip') return 'Ramak Kala / İş Kazaları';
  if (['saglik_gozetim', 'muayene_gecikme', 'uygunluk'].includes(checkCode)) return 'Sağlık';
  if (checkCode === 'saha_sure') return 'Saha Takvimi';
  if (checkCode === 'gorevlendirme') return 'Görevlendirmeler';
  return 'İlgili modül';
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
  const [seedMsg, setSeedMsg] = useState('');

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
      const id = oid || osgbId || (o[0] ? String(o[0].id) : '');
      if (id && !osgbId) setOsgbId(id);
      const q = id ? `?osgb_id=${id}` : '';
      const r = await api(`/osgb/oversight${q}`);
      setData(r);
      setSelected((prev) => {
        if (!prev) return r.professionals?.[0] || null;
        return (r.professionals || []).find((p) => p.professional_id === prev.professional_id) || r.professionals?.[0] || null;
      });
    } catch (e) {
      setError(e.message || 'Yükleme başarısız.');
    } finally {
      setBusy(false);
    }
  }

  async function seedDemo() {
    setBusy(true);
    setSeedMsg('');
    setError('');
    try {
      const q = osgbId ? `?osgb_id=${osgbId}` : '';
      const r = await api(`/osgb/oversight/seed-demo${q}`, {method: 'POST'});
      setTypeFilter('');
      setStatusFilter('');
      setSeedMsg(
        `Test eklendi: ${(r.seeded?.professionals || []).map((p) => p.name).join(', ')}. `
        + `İşyeri: ${r.seeded?.company_name || '—'}. Eksik: ${r.gap_count ?? '—'}. `
        + `${r.seeded?.note || ''} Filtreler temizlendi — listeyi aşağıda görün.`,
      );
      if (r.seeded?.osgb_id) setOsgbId(String(r.seeded.osgb_id));
      await load(r.seeded?.osgb_id ? String(r.seeded.osgb_id) : osgbId);
    } catch (e) {
      setError(e.message);
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
  const globalColumns = data?.check_columns || [];
  const globalGaps = data?.gaps || [];

  return (
    <>
      <div className="page-title">
        <h3>OSGB Hizmet Denetimi</h3>
        <div className="actions">
          <button type="button" className="secondary" onClick={seedDemo} disabled={busy}>
            <Sparkles size={16} /> Test Uzman/Hekim/DSP
          </button>
          <button type="button" className="secondary" onClick={() => load()} disabled={busy}>
            <RefreshCw size={16} /> Yenile
          </button>
        </div>
      </div>

      <section className="panel" style={{marginBottom: 16}}>
        <p style={{marginTop: 0, color: '#475569'}}>
          Açılışta durum özeti ve sütun grafikler görünür. Profesyonel seçince sorumluluk alanları ve
          müdahale listesi açılır — eksikleri takip edip ilgili modüle yönelin.
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
            Dönem: {data.period.month}/{data.period.year} · Toplam müdahale kalemi: {data.gap_count ?? 0}
          </p>
        )}
        {seedMsg && <p style={{color: '#0f766e', marginBottom: 0}}>{seedMsg}</p>}
        {error && <p style={{color: '#b91c1c'}}>{error}</p>}
      </section>

      <div className="cards" style={{marginBottom: 16}}>
        <article className="metric"><span>Profesyonel</span><strong>{summary.professionals ?? 0}</strong></article>
        <article className="metric"><span>Görevlendirme</span><strong>{summary.assignments ?? 0}</strong></article>
        <article className="metric"><span>Uygun</span><strong style={{color: '#166534'}}>{summary.ok ?? 0}</strong></article>
        <article className="metric"><span>İzlem</span><strong style={{color: '#92400e'}}>{summary.warning ?? 0}</strong></article>
        <article className="metric"><span>Kritik</span><strong style={{color: '#991b1c'}}>{summary.critical ?? 0}</strong></article>
      </div>

      <section className="panel" style={{marginBottom: 16}}>
        <ColumnChart
          title="Sorumluluk alanları — OSGB geneli (uyum %)"
          columns={globalColumns}
          height={170}
        />
      </section>

      {globalGaps.length > 0 && (
        <section className="panel" style={{marginBottom: 16}}>
          <h3 style={{marginTop: 0, display: 'flex', alignItems: 'center', gap: 8}}>
            <AlertTriangle size={18} color="#b91c1c" /> Hemen müdahale listesi
          </h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Profesyonel</th>
                  <th>İşyeri</th>
                  <th>Eksik</th>
                  <th>Detay</th>
                  <th>Yönlendirme</th>
                </tr>
              </thead>
              <tbody>
                {globalGaps.slice(0, 12).map((g, i) => (
                  <tr key={`${g.professional_id}-${g.check_code}-${g.company_id}-${i}`}>
                    <td>
                      <button
                        type="button"
                        className="mini"
                        onClick={() => {
                          const p = (data.professionals || []).find((x) => x.professional_id === g.professional_id);
                          if (p) setSelected(p);
                        }}
                      >
                        {g.full_name}
                      </button>
                    </td>
                    <td>{g.company_name}</td>
                    <td><strong>{g.check_title}</strong></td>
                    <td style={{fontSize: 13}}>{g.detail}</td>
                    <td style={{fontSize: 12, color: '#0f766e'}}>{goModuleHint(g.check_code)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <div style={{display: 'grid', gridTemplateColumns: selected ? '1fr 1.15fr' : '1fr', gap: 16}}>
        <section className="panel">
          <h3 style={{marginTop: 0, display: 'flex', alignItems: 'center', gap: 8}}>
            <ClipboardCheck size={18} /> Profesyoneller
          </h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Profesyonel</th>
                  <th>Görev</th>
                  <th>İşyeri</th>
                  <th>Eksik</th>
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
                    <td style={{color: p.gap_count ? '#b91c1c' : '#166534', fontWeight: 650}}>{p.gap_count || 0}</td>
                    <td><ScoreBar score={p.score} status={p.status} /></td>
                    <td><StatusPill status={p.status} /></td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan={6} className="empty">
                      Kayıt yok. “Test Uzman/Hekim/DSP” ile örnek veri ekleyebilirsiniz.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {selected && (
          <section className="panel">
            <div style={{display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start'}}>
              <div>
                <h3 style={{marginTop: 0, marginBottom: 4}}>{selected.full_name}</h3>
                <p style={{color: '#64748b', margin: 0}}>
                  {TYPE_LABELS[selected.professional_type]} · {selected.firm_count} işyeri · skor {selected.score}%
                </p>
              </div>
              <StatusPill status={selected.status} />
            </div>

            <div style={{marginTop: 16, marginBottom: 8}}>
              <ColumnChart
                title="Sorumluluk alanları (bu profesyonel)"
                columns={selected.check_columns || []}
                height={150}
              />
            </div>

            {(selected.gaps || []).length > 0 && (
              <div style={{marginTop: 16}}>
                <h4 style={{margin: '0 0 8px'}}>Müdahale gerekenler</h4>
                <div style={{display: 'grid', gap: 8}}>
                  {selected.gaps.map((g, i) => (
                    <div
                      key={`${g.check_code}-${g.company_id}-${i}`}
                      style={{
                        border: '1px solid #fecaca',
                        background: '#fff1f2',
                        borderRadius: 10,
                        padding: '10px 12px',
                      }}
                    >
                      <div style={{fontWeight: 700}}>{g.check_title} — {g.company_name}</div>
                      <div style={{fontSize: 12, color: '#64748b'}}>{g.legal}</div>
                      <div style={{fontSize: 13, marginTop: 4}}>{g.detail}</div>
                      <div style={{fontSize: 12, color: '#0f766e', marginTop: 4}}>
                        Git → {goModuleHint(g.check_code)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div style={{marginTop: 18}}>
              <h4 style={{margin: '0 0 10px'}}>İşyeri detayı</h4>
              {selected.firms.map((f) => (
                <div
                  key={f.assignment_id}
                  style={{
                    border: '1px solid #e2e8f0',
                    borderRadius: 12,
                    padding: 14,
                    marginBottom: 12,
                  }}
                >
                  <div style={{display: 'flex', justifyContent: 'space-between', gap: 12}}>
                    <div>
                      <strong>{f.company_name}</strong>
                      <div style={{fontSize: 12, color: '#64748b'}}>
                        {f.hazard_class || '—'}
                        {f.isg_katip_contract_number ? ` · ${f.isg_katip_contract_number}` : ''}
                      </div>
                    </div>
                    <div style={{textAlign: 'right'}}>
                      <StatusPill status={f.status} />
                      <div style={{fontSize: 12, marginTop: 6}}>{f.score}%</div>
                    </div>
                  </div>
                  <div style={{marginTop: 10, display: 'grid', gap: 6}}>
                    {f.checks.map((c) => (
                      <div
                        key={c.code}
                        style={{
                          display: 'grid',
                          gridTemplateColumns: '18px 1fr',
                          gap: 8,
                          padding: '6px 8px',
                          borderRadius: 8,
                          background: c.passed ? '#f8fafc' : '#fff1f2',
                        }}
                      >
                        {c.passed
                          ? <CheckCircle2 size={15} color="#16a34a" />
                          : <AlertTriangle size={15} color="#b91c1c" />}
                        <div>
                          <div style={{fontWeight: 650, fontSize: 13}}>{c.title}</div>
                          <div style={{fontSize: 12, color: '#64748b'}}>{c.detail}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </>
  );
}
