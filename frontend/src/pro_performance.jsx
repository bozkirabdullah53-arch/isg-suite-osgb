import React, {useEffect, useMemo, useState} from 'react';
import {AlertTriangle, CheckCircle2, ClipboardList, Printer, RefreshCw, UserRound} from 'lucide-react';
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

function optionLabel(p) {
  const role = TYPE_LABELS[p.professional_type] || p.professional_type;
  const cls = p.certificate_class ? ` · Sınıf ${p.certificate_class}` : '';
  const inactive = p.is_active === false ? ' (pasif)' : '';
  return `${p.full_name} — ${role}${cls}${inactive}`;
}

export function ProPerformancePage({user}) {
  const [orgs, setOrgs] = useState([]);
  const [osgbId, setOsgbId] = useState('');
  const [directory, setDirectory] = useState([]);
  const [typeFilter, setTypeFilter] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  if (user.role !== 'global_admin') {
    return (
      <>
        <div className="page-title"><h3>Performans / İş Tamamlama</h3></div>
        <section className="panel">
          <p>Bu ekran yalnızca global yönetici tarafından görüntülenebilir.</p>
        </section>
      </>
    );
  }

  async function loadDirectory(oid = osgbId) {
    setBusy(true);
    setError('');
    try {
      const o = await api('/osgb');
      setOrgs(o);
      const id = oid || osgbId || (o[0] ? String(o[0].id) : '');
      if (id && !osgbId) setOsgbId(id);
      if (!id) {
        setDirectory([]);
        return;
      }
      const pros = await api(`/osgb/professionals?osgb_id=${id}`);
      setDirectory((pros || []).sort((a, b) => a.full_name.localeCompare(b.full_name, 'tr')));
    } catch (e) {
      setError(e.message || 'Liste yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  async function loadReport(pid = selectedId) {
    if (!pid) {
      setReport(null);
      return;
    }
    setBusy(true);
    setError('');
    try {
      const r = await api(`/osgb/professionals/${pid}/performance`);
      setReport(r);
    } catch (e) {
      setReport(null);
      setError(e.message || 'Rapor yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void loadDirectory(); }, []);

  const filtered = useMemo(() => {
    let rows = directory;
    if (typeFilter) rows = rows.filter((p) => p.professional_type === typeFilter);
    return rows;
  }, [directory, typeFilter]);

  const perf = report?.performance;
  const st = statusStyle(perf?.status);

  return (
    <>
      <div className="page-title" style={{display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap'}}>
        <div>
          <h3>Performans / İş Tamamlama</h3>
          <p style={{margin: '4px 0 0', color: '#64748b', fontSize: 13}}>
            Uzman, hekim veya DSP seçin — atanmış firmalardaki 6331 sorumluluk tamamlanma raporu.
          </p>
        </div>
        <div style={{display: 'flex', gap: 8}}>
          <button type="button" className="ghost" disabled={busy} onClick={() => { void loadDirectory(); if (selectedId) void loadReport(selectedId); }}>
            <RefreshCw size={16} /> Yenile
          </button>
          {report && (
            <button type="button" className="ghost" onClick={() => window.print()}>
              <Printer size={16} /> Yazdır
            </button>
          )}
        </div>
      </div>

      {error && <div className="error" style={{marginBottom: 12}}>{error}</div>}

      <section className="panel" style={{marginBottom: 16}}>
        <div className="form-grid" style={{gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12}}>
          {orgs.length > 1 && (
            <label className="field">
              <span>OSGB</span>
              <select
                value={osgbId}
                onChange={(e) => {
                  setOsgbId(e.target.value);
                  setSelectedId('');
                  setReport(null);
                  void loadDirectory(e.target.value);
                }}
              >
                {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            </label>
          )}
          <label className="field">
            <span>Rol filtresi</span>
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="">Tümü</option>
              <option value="safety_specialist">İş Güvenliği Uzmanı</option>
              <option value="workplace_physician">İşyeri Hekimi</option>
              <option value="other_health_personnel">DSP</option>
            </select>
          </label>
          <label className="field" style={{gridColumn: 'span 2'}}>
            <span>Profesyonel</span>
            <select
              value={selectedId}
              onChange={(e) => {
                const id = e.target.value;
                setSelectedId(id);
                void loadReport(id);
              }}
            >
              <option value="">Seçiniz…</option>
              {filtered.map((p) => (
                <option key={p.id} value={p.id}>{optionLabel(p)}</option>
              ))}
            </select>
          </label>
        </div>
      </section>

      {!selectedId && (
        <section className="panel" style={{textAlign: 'center', padding: '40px 20px', color: '#64748b'}}>
          <UserRound size={36} style={{marginBottom: 8, opacity: 0.5}} />
          <p>Rapor için listeden bir profesyonel seçin.</p>
        </section>
      )}

      {report && (
        <div className="pro-perf-print">
          <section className="panel" style={{marginBottom: 16}}>
            <div style={{display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start'}}>
              <div>
                <div style={{fontSize: 12, color: '#64748b', marginBottom: 4}}>İş Tamamlama / Performans Raporu</div>
                <h2 style={{margin: 0, fontSize: 22}}>{report.professional?.full_name}</h2>
                <p style={{margin: '6px 0 0', color: '#475569'}}>
                  {report.professional?.role_label}
                  {report.professional?.certificate_class ? ` · Sınıf ${report.professional.certificate_class}` : ''}
                  {report.professional?.certificate_number ? ` · Belge: ${report.professional.certificate_number}` : ''}
                  {report.professional?.is_active === false ? ' · Pasif' : ''}
                </p>
                <p style={{margin: '4px 0 0', fontSize: 12, color: '#94a3b8'}}>
                  Dönem: {report.period?.label || '—'} · Üretim: {report.generated_at}
                </p>
              </div>
              <div style={{
                minWidth: 140, textAlign: 'center', padding: '16px 20px',
                borderRadius: 12, background: st.bg, color: st.fg,
              }}>
                <div style={{fontSize: 36, fontWeight: 800, lineHeight: 1}}>{perf?.score ?? 0}%</div>
                <div style={{fontSize: 12, marginTop: 6, fontWeight: 700}}>Skor</div>
                <div style={{marginTop: 8}}><StatusPill status={perf?.status} /></div>
              </div>
            </div>

            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
              gap: 12, marginTop: 20,
            }}>
              {[
                ['Firma', perf?.firm_count ?? 0],
                ['Tamamlanan', perf?.completed_checks ?? 0],
                ['Toplam kontrol', perf?.total_checks ?? 0],
                ['Tamamlanma', `%${perf?.completion_pct ?? 0}`],
                ['Eksik', perf?.gap_count ?? 0],
              ].map(([label, val]) => (
                <div key={label} style={{padding: '12px 14px', background: '#f8fafc', borderRadius: 10}}>
                  <div style={{fontSize: 11, color: '#64748b'}}>{label}</div>
                  <div style={{fontSize: 20, fontWeight: 750, marginTop: 2}}>{val}</div>
                </div>
              ))}
            </div>
          </section>

          {(report.incomplete || []).length > 0 && (
            <section className="panel" style={{marginBottom: 16}}>
              <h3 style={{display: 'flex', alignItems: 'center', gap: 8, marginTop: 0}}>
                <AlertTriangle size={18} color="#dc2626" /> Eksik / tamamlanmayan işler ({report.incomplete.length})
              </h3>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>İşyeri</th>
                      <th>Kontrol</th>
                      <th>Detay</th>
                      <th>Dayanak</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.incomplete.map((g, i) => (
                      <tr key={`inc-${i}`}>
                        <td>{g.company_name || '—'}</td>
                        <td><strong>{g.check_title}</strong></td>
                        <td style={{fontSize: 13}}>{g.detail}</td>
                        <td style={{fontSize: 12, color: '#64748b'}}>{g.legal || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {(report.completed || []).length > 0 && (
            <section className="panel" style={{marginBottom: 16}}>
              <h3 style={{display: 'flex', alignItems: 'center', gap: 8, marginTop: 0}}>
                <CheckCircle2 size={18} color="#16a34a" /> Tamamlanan kontroller ({report.completed.length})
              </h3>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>İşyeri</th>
                      <th>Kontrol</th>
                      <th>Detay</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.completed.map((g, i) => (
                      <tr key={`ok-${i}`}>
                        <td>{g.company_name || '—'}</td>
                        <td>{g.check_title}</td>
                        <td style={{fontSize: 13, color: '#475569'}}>{g.detail}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {(report.firms || []).length > 0 && (
            <section className="panel">
              <h3 style={{display: 'flex', alignItems: 'center', gap: 8, marginTop: 0}}>
                <ClipboardList size={18} /> Firma bazlı checklist
              </h3>
              <div style={{display: 'flex', flexDirection: 'column', gap: 16}}>
                {report.firms.map((f) => (
                  <div key={f.company_id} style={{border: '1px solid #e2e8f0', borderRadius: 10, padding: 14}}>
                    <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: 10, flexWrap: 'wrap', gap: 8}}>
                      <strong>{f.company_name}</strong>
                      <StatusPill status={f.status} />
                    </div>
                    <div style={{display: 'grid', gap: 6}}>
                      {(f.checks || []).map((c) => (
                        <div key={c.code} style={{
                          display: 'flex', gap: 10, alignItems: 'flex-start', fontSize: 13,
                          padding: '6px 8px', borderRadius: 6,
                          background: c.passed ? '#f0fdf4' : '#fef2f2',
                        }}>
                          {c.passed
                            ? <CheckCircle2 size={15} color="#16a34a" style={{flexShrink: 0, marginTop: 2}} />
                            : <AlertTriangle size={15} color="#dc2626" style={{flexShrink: 0, marginTop: 2}} />}
                          <div>
                            <strong>{c.title}</strong>
                            <div style={{color: '#64748b'}}>{c.detail}</div>
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
      )}
    </>
  );
}
