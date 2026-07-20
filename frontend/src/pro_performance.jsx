import React, {useEffect, useMemo, useState} from 'react';
import {AlertTriangle, CheckCircle2, ClipboardList, Printer, RefreshCw, UserRound} from 'lucide-react';
import {api, downloadFile} from './api';

const TYPE_LABELS = {
  safety_specialist: 'İş Güvenliği Uzmanı',
  workplace_physician: 'İşyeri Hekimi',
  other_health_personnel: 'Diğer Sağlık Personeli',
};

const ROLE_TABS = [
  {id: 'safety_specialist', short: 'Uzman', label: 'İş Güvenliği Uzmanları'},
  {id: 'workplace_physician', short: 'Hekim', label: 'İşyeri Hekimleri'},
  {id: 'other_health_personnel', short: 'DSP', label: 'Diğer Sağlık Personeli'},
];

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

function periodText(period) {
  if (!period) return '—';
  if (period.label) return period.label;
  if (period.month && period.year) return `${period.month}/${period.year}`;
  return '—';
}

export function ProPerformancePage({user}) {
  const [orgs, setOrgs] = useState([]);
  const [osgbId, setOsgbId] = useState('');
  const [directory, setDirectory] = useState([]);
  const [roleTab, setRoleTab] = useState('safety_specialist');
  const [selectedId, setSelectedId] = useState('');
  const [report, setReport] = useState(null);
  const [section, setSection] = useState('incomplete'); // incomplete | completed | firms
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const isOsgbAdmin = user.role === 'company_admin';
  const canView = user.role === 'global_admin' || isOsgbAdmin;

  async function loadDirectory(oid = osgbId) {
    if (!canView) return;
    setBusy(true);
    setError('');
    try {
      const o = await api('/osgb');
      setOrgs(o);
      const locked = isOsgbAdmin && user.osgb_id ? String(user.osgb_id) : '';
      const id = locked || oid || osgbId || (o[0] ? String(o[0].id) : '');
      if (id && id !== osgbId) setOsgbId(id);
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

  async function loadReport(pid) {
    if (!pid) {
      setReport(null);
      return;
    }
    setBusy(true);
    setError('');
    try {
      const r = await api(`/osgb/professionals/${pid}/performance`);
      setReport(r);
      const gaps = (r.incomplete || []).length;
      setSection(gaps > 0 ? 'incomplete' : ((r.firms || []).length ? 'firms' : 'completed'));
    } catch (e) {
      setReport(null);
      setError(e.message || 'Rapor yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void loadDirectory(); }, []);

  useEffect(() => {
    try {
      const preset = sessionStorage.getItem('pro_performance_id');
      if (!preset) return;
      sessionStorage.removeItem('pro_performance_id');
      setSelectedId(preset);
      void loadReport(preset);
    } catch (_) { /* ignore */ }
  }, []);

  // Preset seçilince rol sekmesini profesyonelin tipine hizala
  useEffect(() => {
    if (!selectedId || !directory.length) return;
    const p = directory.find((x) => String(x.id) === String(selectedId));
    if (p?.professional_type) setRoleTab(p.professional_type);
  }, [selectedId, directory]);

  const roleCounts = useMemo(() => {
    const c = {safety_specialist: 0, workplace_physician: 0, other_health_personnel: 0};
    for (const p of directory) {
      if (c[p.professional_type] != null) c[p.professional_type] += 1;
    }
    return c;
  }, [directory]);

  const filtered = useMemo(
    () => directory.filter((p) => p.professional_type === roleTab),
    [directory, roleTab],
  );

  const perf = report?.performance;
  const st = statusStyle(perf?.status);

  if (!canView) {
    return (
      <>
        <div className="page-title"><h3>Performans / İş Tamamlama</h3></div>
        <section className="panel">
          <p>Bu ekran OSGB yöneticisi veya EİSA tarafından görüntülenebilir.</p>
        </section>
      </>
    );
  }
  const incomplete = report?.incomplete || [];
  const completed = report?.completed || [];
  const firms = report?.firms || [];

  return (
    <>
      <div className="page-title" style={{display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap'}}>
        <div>
          <h3>Performans / İş Tamamlama</h3>
          <p style={{margin: '4px 0 0', color: '#64748b', fontSize: 13}}>
            Rol seçin → profesyoneli seçin → atanmış firmalardaki 6331 iş tamamlama raporu.
          </p>
        </div>
        <div style={{display: 'flex', gap: 8}}>
          <button
            type="button"
            className="ghost"
            disabled={busy}
            onClick={() => { void loadDirectory(); if (selectedId) void loadReport(selectedId); }}
          >
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
        {user.role === 'global_admin' && orgs.length > 1 && (
          <label className="field" style={{maxWidth: 360, marginBottom: 12}}>
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

        <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14}}>
          {ROLE_TABS.map((t) => {
            const active = roleTab === t.id;
            return (
              <button
                key={t.id}
                type="button"
                className={active ? '' : 'secondary'}
                onClick={() => {
                  setRoleTab(t.id);
                  setSelectedId('');
                  setReport(null);
                }}
                style={active ? undefined : undefined}
              >
                {t.label} ({roleCounts[t.id] || 0})
              </button>
            );
          })}
        </div>

        <label className="field" style={{marginBottom: 0}}>
          <span>{ROLE_TABS.find((t) => t.id === roleTab)?.label || 'Profesyonel'}</span>
          <select
            value={selectedId}
            onChange={(e) => {
              const id = e.target.value;
              setSelectedId(id);
              void loadReport(id);
            }}
            style={{fontWeight: 650}}
          >
            <option value="">Seçiniz…</option>
            {filtered.map((p) => (
              <option key={p.id} value={p.id}>
                {p.full_name}
                {p.certificate_class ? ` · Sınıf ${p.certificate_class}` : ''}
                {p.is_active === false ? ' (pasif)' : ''}
              </option>
            ))}
          </select>
        </label>
        {!filtered.length && (
          <p style={{margin: '10px 0 0', fontSize: 13, color: '#92400e'}}>
            Bu rolde kayıtlı profesyonel yok. İSG Profesyonelleri menüsünden ekleyin.
          </p>
        )}
      </section>

      {!selectedId && (
        <section className="panel" style={{textAlign: 'center', padding: '40px 20px', color: '#64748b'}}>
          <UserRound size={36} style={{marginBottom: 8, opacity: 0.5}} />
          <p style={{margin: 0}}>Önce rol, sonra profesyonel seçin.</p>
        </section>
      )}

      {report && (
        <div className="pro-perf-print">
          <section className="panel" style={{marginBottom: 16}}>
            <div style={{display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start'}}>
              <div>
                <div style={{fontSize: 12, color: '#64748b', marginBottom: 4}}>
                  {report.report_title || 'İş Tamamlama / Performans Raporu'}
                </div>
                <h2 style={{margin: 0, fontSize: 22}}>{report.professional?.full_name}</h2>
                <p style={{margin: '6px 0 0', color: '#475569'}}>
                  {report.professional?.role_label}
                  {report.professional?.certificate_class ? ` · Sınıf ${report.professional.certificate_class}` : ''}
                  {report.professional?.certificate_number ? ` · Belge: ${report.professional.certificate_number}` : ''}
                  {report.professional?.is_active === false ? ' · Pasif' : ''}
                </p>
                <p style={{margin: '4px 0 0', fontSize: 12, color: '#94a3b8'}}>
                  Dönem: {periodText(report.period)} · Üretim: {report.generated_at}
                  {perf?.unassigned ? ' · Görevlendirme yok' : ''}
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
              display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))',
              gap: 10, marginTop: 18,
            }}>
              {[
                ['İşyeri', perf?.firm_count ?? 0],
                ['Tamamlanan', perf?.completed_checks ?? completed.length],
                ['Eksik', perf?.gap_count ?? incomplete.length],
                ['Tamamlanma', `%${perf?.completion_pct ?? 0}`],
              ].map(([label, val]) => (
                <div key={label} style={{padding: '12px 14px', background: '#f8fafc', borderRadius: 10}}>
                  <div style={{fontSize: 11, color: '#64748b'}}>{label}</div>
                  <div style={{
                    fontSize: 20, fontWeight: 750, marginTop: 2,
                    color: label === 'Eksik' && Number(val) > 0 ? '#b91c1c' : undefined,
                  }}>{val}</div>
                </div>
              ))}
            </div>
          </section>

          <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12}}>
            <button
              type="button"
              className={section === 'incomplete' ? '' : 'secondary'}
              onClick={() => setSection('incomplete')}
            >
              Eksikler ({incomplete.length})
            </button>
            <button
              type="button"
              className={section === 'completed' ? '' : 'secondary'}
              onClick={() => setSection('completed')}
            >
              Tamamlanan ({completed.length})
            </button>
            <button
              type="button"
              className={section === 'firms' ? '' : 'secondary'}
              onClick={() => setSection('firms')}
            >
              Firma checklist ({firms.length})
            </button>
          </div>

          {section === 'incomplete' && (
            <section className="panel" style={{marginBottom: 16}}>
              <h3 style={{display: 'flex', alignItems: 'center', gap: 8, marginTop: 0}}>
                <AlertTriangle size={18} color="#dc2626" /> Eksik / tamamlanmayan işler
              </h3>
              {incomplete.length ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>İşyeri</th>
                        <th>Kontrol</th>
                        <th>Detay</th>
                        <th>Dayanak</th>
                      </tr>
                    </thead>
                    <tbody>
                      {incomplete.map((g, i) => (
                        <tr key={`inc-${i}`}>
                          <td>{i + 1}</td>
                          <td>{g.company_name || '—'}</td>
                          <td><strong>{g.check_title}</strong></td>
                          <td style={{fontSize: 13}}>{g.detail}</td>
                          <td style={{fontSize: 12, color: '#64748b'}}>{g.legal || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p style={{margin: 0, color: '#166534', display: 'flex', alignItems: 'center', gap: 8}}>
                  <CheckCircle2 size={16} /> Eksik iş yok.
                </p>
              )}
            </section>
          )}

          {section === 'completed' && (
            <section className="panel" style={{marginBottom: 16}}>
              <h3 style={{display: 'flex', alignItems: 'center', gap: 8, marginTop: 0}}>
                <CheckCircle2 size={18} color="#16a34a" /> Tamamlanan kontroller
              </h3>
              {completed.length ? (
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
                      {completed.map((g, i) => (
                        <tr key={`ok-${i}`}>
                          <td>{g.company_name || '—'}</td>
                          <td>{g.check_title}</td>
                          <td style={{fontSize: 13, color: '#475569'}}>{g.detail}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p style={{margin: 0, color: '#64748b'}}>Tamamlanan kontrol kaydı yok.</p>
              )}
            </section>
          )}

          {section === 'firms' && (
            <section className="panel">
              <h3 style={{display: 'flex', alignItems: 'center', gap: 8, marginTop: 0}}>
                <ClipboardList size={18} /> Firma bazlı checklist
              </h3>
              {!firms.length ? (
                <p style={{margin: 0, color: '#92400e'}}>
                  Atanmış işyeri yok. Önce <strong>Görevlendirmeler</strong> menüsünden atayın.
                </p>
              ) : (
                <div style={{display: 'flex', flexDirection: 'column', gap: 14}}>
                  {firms.map((f) => (
                    <div key={f.company_id || f.assignment_id} style={{border: '1px solid #e2e8f0', borderRadius: 10, padding: 14}}>
                      <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: 10, flexWrap: 'wrap', gap: 8}}>
                        <div>
                          <strong>{f.company_name}</strong>
                          {f.hazard_class && (
                            <div style={{fontSize: 12, color: '#64748b'}}>{f.hazard_class}</div>
                          )}
                        </div>
                        <div style={{textAlign: 'right'}}>
                          <StatusPill status={f.status} />
                          {f.score != null && <div style={{fontSize: 12, marginTop: 4}}>{f.score}%</div>}
                        </div>
                      </div>
                      <div style={{display: 'grid', gap: 6}}>
                        {(f.checks || []).map((c) => (
                          <div
                            key={c.code}
                            style={{
                              display: 'flex', gap: 10, alignItems: 'flex-start', fontSize: 13,
                              padding: '6px 8px', borderRadius: 6,
                              background: c.passed ? '#f0fdf4' : '#fef2f2',
                            }}
                          >
                            {c.passed
                              ? <CheckCircle2 size={15} color="#16a34a" style={{flexShrink: 0, marginTop: 2}} />
                              : <AlertTriangle size={15} color="#dc2626" style={{flexShrink: 0, marginTop: 2}} />}
                            <div>
                              <strong>{c.passed ? 'Yapıldı' : 'Yapılmadı'} — {c.title}</strong>
                              <div style={{color: '#64748b'}}>{c.detail}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                      <div style={{marginTop: 12, paddingTop: 12, borderTop: '1px solid #e2e8f0'}}>
                        <div style={{fontSize: 12, fontWeight: 700, color: '#0f766e', marginBottom: 8}}>
                          Saha ziyaretleri / tespit öneri defteri
                          {' · '}{(f.visits || []).length} kayıt
                          {' · '}{f.notebook_count || 0} defter
                        </div>
                        {(f.visits || []).length ? (
                          <div className="table-wrap">
                            <table>
                              <thead>
                                <tr>
                                  <th>Tarih</th>
                                  <th>Süre</th>
                                  <th>Konu</th>
                                  <th>Durum</th>
                                  <th>Defter</th>
                                </tr>
                              </thead>
                              <tbody>
                                {(f.visits || []).map((v) => (
                                  <tr key={v.id}>
                                    <td>{v.visit_date || '—'}</td>
                                    <td>{v.duration_minutes || 0} dk</td>
                                    <td style={{fontSize: 13}}>{v.subject || '—'}</td>
                                    <td>{v.status || '—'}</td>
                                    <td>
                                      {v.has_notebook ? (
                                        <button
                                          type="button"
                                          className="mini"
                                          onClick={() => downloadFile(v.notebook_url, v.notebook_file_name || 'tespit-defteri').catch((e) => alert(e.message))}
                                        >
                                          {v.notebook_file_name || 'İndir'}
                                        </button>
                                      ) : '—'}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <p style={{margin: 0, fontSize: 13, color: '#92400e'}}>
                            Bu dönemde saha ziyareti / tespit defteri kaydı yok.
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {(report.legal_basis || []).length > 0 && (
            <p style={{marginTop: 12, fontSize: 11, color: '#94a3b8'}}>
              Dayanak: {(report.legal_basis || []).join(' · ')}
            </p>
          )}
        </div>
      )}
    </>
  );
}
