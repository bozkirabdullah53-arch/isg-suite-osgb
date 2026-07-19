import React, {useEffect, useMemo, useState} from 'react';
import {AlertTriangle, CheckCircle2, ClipboardCheck, RefreshCw, ShieldAlert, Sparkles, Stethoscope, UserRound} from 'lucide-react';
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

function optionLabel(p) {
  const role = TYPE_LABELS[p.professional_type] || p.professional_type;
  const cls = p.certificate_class ? ` · Sınıf ${p.certificate_class}` : '';
  const inactive = p.is_active === false ? ' (pasif)' : '';
  return `${p.full_name} — ${role}${cls}${inactive}`;
}

/** Seçilen kişinin tüm eksikleri — firma checklist’inden türetilir (kesilmez). */
function collectPersonGaps(person) {
  if (!person) return [];
  const out = [];
  if (person.unassigned || !person.firms?.length) {
    for (const g of person.gaps || []) out.push(g);
    return out;
  }
  for (const f of person.firms || []) {
    for (const c of f.checks || []) {
      if (c.passed) continue;
      out.push({
        company_id: f.company_id,
        company_name: f.company_name,
        check_code: c.code,
        check_title: c.title,
        detail: c.detail,
        legal: c.legal,
      });
    }
  }
  return out;
}

export function OsgbOversightPage({user}) {
  const [orgs, setOrgs] = useState([]);
  const [osgbId, setOsgbId] = useState('');
  const [data, setData] = useState(null);
  const [selectedId, setSelectedId] = useState('');
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
      const [r, prosDir] = await Promise.all([
        api(`/osgb/oversight${q}`),
        id ? api(`/osgb/professionals${q}`).catch(() => []) : Promise.resolve([]),
      ]);

      const fromOversight = r.directory?.length
        ? r.directory
        : (r.professionals || []).map((p) => ({
          professional_id: p.professional_id,
          full_name: p.full_name,
          professional_type: p.professional_type,
          certificate_class: p.certificate_class,
          is_active: p.is_active !== false,
        }));
      const byId = new Map(fromOversight.map((p) => [p.professional_id, p]));
      for (const p of prosDir || []) {
        if (!byId.has(p.id)) {
          byId.set(p.id, {
            professional_id: p.id,
            full_name: p.full_name,
            professional_type: p.professional_type,
            certificate_class: p.certificate_class,
            is_active: p.is_active !== false,
          });
        }
      }
      const directory = [...byId.values()].sort((a, b) => a.full_name.localeCompare(b.full_name, 'tr'));

      const rowById = new Map((r.professionals || []).map((p) => [p.professional_id, p]));
      for (const d of directory) {
        if (!rowById.has(d.professional_id)) {
          rowById.set(d.professional_id, {
            professional_id: d.professional_id,
            full_name: d.full_name,
            professional_type: d.professional_type,
            certificate_class: d.certificate_class,
            is_active: d.is_active,
            firm_count: 0,
            score: 0,
            status: 'critical',
            firms: [],
            check_columns: [],
            gaps: [{
              company_id: null,
              company_name: '—',
              check_code: 'gorevlendirme',
              check_title: 'İşyeri görevlendirmesi yok',
              detail: 'Bu profesyonel henüz hiçbir işyerine atanmamış. Önce Görevlendirmeler’den atayın.',
              legal: 'İSG Hizmetleri Yön. — işyerine uzman/hekim/DSP görevlendirme zorunluluğu',
            }],
            gap_count: 1,
            unassigned: true,
          });
        }
      }

      const merged = {
        ...r,
        directory,
        professionals: [...rowById.values()],
        summary: {
          ...(r.summary || {}),
          professionals: Math.max(r.summary?.professionals || 0, directory.length),
        },
      };
      setData(merged);
      // Açılışta genel görünüm: seçim zorunlu değil; önceki seçim varsa koru
      setSelectedId((prev) => {
        if (!prev) return '';
        if (rowById.has(Number(prev)) || rowById.has(prev)) return String(prev);
        return '';
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
        + `İşyeri: ${r.seeded?.company_name || '—'}. Eksik: ${r.gap_count ?? '—'}.`,
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

  const directory = useMemo(() => {
    let list = data?.directory || [];
    if (typeFilter) list = list.filter((p) => p.professional_type === typeFilter);
    return list;
  }, [data, typeFilter]);

  const selected = useMemo(() => {
    if (!selectedId || !data?.professionals) return null;
    const idNum = Number(selectedId);
    return data.professionals.find((p) => p.professional_id === idNum || String(p.professional_id) === selectedId) || null;
  }, [data, selectedId]);

  const personGaps = useMemo(() => collectPersonGaps(selected), [selected]);

  const roleCatalog = useMemo(() => {
    if (!selected || !data?.check_catalog) return [];
    return data.check_catalog[selected.professional_type] || [];
  }, [selected, data]);

  const summary = data?.summary || {};
  const globalColumns = data?.check_columns || [];
  const globalGaps = useMemo(() => {
    let list = data?.gaps || [];
    if (typeFilter) list = list.filter((g) => g.professional_type === typeFilter);
    if (statusFilter) {
      const ids = new Set(rows.map((p) => p.professional_id));
      list = list.filter((g) => ids.has(g.professional_id));
    }
    return list;
  }, [data, typeFilter, statusFilter, rows]);

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
          <strong>1) Genel:</strong> Açılışta tüm personelin durum özeti, sütun grafikler ve OSGB geneli eksik listesi.
          {' '}<strong>2) Personel:</strong> İsim seçince (ör. Abdullah BOZKIR) yalnızca o kişinin tüm 6331 eksikleri
          ve firma bazlı görev durumu açılır — iş akışını buradan takip edin.
        </p>
        <div className="form-grid" style={{gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', marginBottom: 0}}>
          <label className="field">
            <span>OSGB</span>
            <select
              value={osgbId}
              onChange={(e) => {
                setOsgbId(e.target.value);
                setSelectedId('');
                load(e.target.value);
              }}
            >
              {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Meslek (genel filtre)</span>
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="">Tümü</option>
              {Object.entries(TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Durum (genel filtre)</span>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">Tümü</option>
              {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
        </div>
        {data?.period && (
          <p style={{marginBottom: 0, fontSize: 13, color: '#64748b'}}>
            Dönem: {data.period.month}/{data.period.year}
            {' · '}Toplam müdahale kalemi: {globalGaps.length}
            {directory.length ? ` · Personel: ${directory.length}` : ''}
          </p>
        )}
        {seedMsg && <p style={{color: '#0f766e', marginBottom: 0}}>{seedMsg}</p>}
        {error && <p style={{color: '#b91c1c'}}>{error}</p>}
      </section>

      {/* ——— GENEL: tüm personel ——— */}
      <h3 style={{margin: '0 0 10px', fontSize: 16, color: '#0f766e'}}>Genel durum — tüm personel</h3>

      <div className="cards" style={{marginBottom: 16}}>
        <article className="metric"><span>Profesyonel</span><strong>{summary.professionals ?? directory.length ?? 0}</strong></article>
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

      <section className="panel" style={{marginBottom: 16}}>
        <h3 style={{marginTop: 0, display: 'flex', alignItems: 'center', gap: 8}}>
          <AlertTriangle size={18} color="#b91c1c" /> OSGB geneli — tüm eksikler ({globalGaps.length})
        </h3>
        <p style={{marginTop: 0, fontSize: 13, color: '#64748b'}}>
          İsme tıklayınca aşağıda o personelin özel takip paneli açılır.
        </p>
        {globalGaps.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Profesyonel</th>
                  <th>İşyeri</th>
                  <th>Eksik görev</th>
                  <th>Detay</th>
                  <th>Modül</th>
                </tr>
              </thead>
              <tbody>
                {globalGaps.map((g, i) => (
                  <tr key={`${g.professional_id}-${g.check_code}-${g.company_id}-${i}`}>
                    <td>
                      <button
                        type="button"
                        className="mini"
                        onClick={() => {
                          setSelectedId(String(g.professional_id));
                          requestAnimationFrame(() => {
                            document.getElementById('personel-takip')?.scrollIntoView({behavior: 'smooth', block: 'start'});
                          });
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
        ) : (
          <p style={{color: '#166534', margin: 0}}>Genel listede eksik kalem yok.</p>
        )}
      </section>

      <section className="panel" style={{marginBottom: 24}}>
        <h3 style={{marginTop: 0, display: 'flex', alignItems: 'center', gap: 8}}>
          <ClipboardCheck size={18} /> Tüm profesyoneller
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
                  onClick={() => {
                    setSelectedId(String(p.professional_id));
                    requestAnimationFrame(() => {
                      document.getElementById('personel-takip')?.scrollIntoView({behavior: 'smooth', block: 'start'});
                    });
                  }}
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
                    Kayıt yok. İSG Profesyonelleri’nden uzman ekleyin veya “Test Uzman/Hekim/DSP” ile örnek veri oluşturun.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* ——— ÖZEL: seçilen personel ——— */}
      <div id="personel-takip" style={{scrollMarginTop: 16}}>
        <h3 style={{margin: '0 0 10px', fontSize: 16, color: '#0f766e'}}>
          Personel takibi — seçilen kişinin tüm eksikleri
        </h3>
      </div>

      <section className="panel" style={{marginBottom: 16, borderColor: '#99f6e4', background: '#f0fdfa'}}>
        <h3 style={{marginTop: 0, display: 'flex', alignItems: 'center', gap: 8}}>
          <UserRound size={18} /> Profesyonel seç
        </h3>
        <p style={{marginTop: 0, color: '#475569'}}>
          Seçince yalnızca bu kişinin atanmış firmalarındaki 6331 görevlerinden yapılmayanların tamamı listelenir.
        </p>
        <label className="field" style={{maxWidth: 520, marginBottom: 0}}>
          <span>Profesyonel (isim)</span>
          <select
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            style={{fontWeight: 650}}
          >
            <option value="">— Genel görünüm (henüz seçilmedi) —</option>
            {directory.map((p) => (
              <option key={p.professional_id} value={p.professional_id}>
                {optionLabel(p)}
              </option>
            ))}
          </select>
        </label>
      </section>

      {!selected && (
        <section className="panel" style={{marginBottom: 16}}>
          <p style={{margin: 0, color: '#64748b'}}>
            Yukarıdaki genel özet tüm personeli gösterir. Belirli bir uzmanın iş akışını izlemek için isim seçin
            veya genel eksik listesinden isme tıklayın.
          </p>
        </section>
      )}

      {selected && (
        <section className="panel" style={{marginBottom: 16}}>
          <div style={{display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', flexWrap: 'wrap'}}>
            <div>
              <h3 style={{marginTop: 0, marginBottom: 4}}>{selected.full_name}</h3>
              <p style={{color: '#475569', margin: 0}}>
                {TYPE_LABELS[selected.professional_type]}
                {selected.certificate_class ? ` · Sınıf ${selected.certificate_class}` : ''}
                {' · '}{selected.firm_count} işyeri · skor {selected.score}%
                {selected.is_active === false ? ' · pasif' : ''}
              </p>
            </div>
            <div style={{display: 'flex', gap: 8, alignItems: 'center'}}>
              <StatusPill status={selected.status} />
              <button type="button" className="mini" onClick={() => setSelectedId('')}>
                Seçimi kaldır
              </button>
            </div>
          </div>

          <div style={{marginTop: 16}}>
            <h4 style={{margin: '0 0 8px', color: personGaps.length ? '#991b1b' : '#166534', display: 'flex', alignItems: 'center', gap: 8}}>
              {personGaps.length
                ? <><AlertTriangle size={16} /> Bu personelin tüm eksikleri ({personGaps.length})</>
                : <><CheckCircle2 size={16} /> Bu personelde eksik görev yok</>}
            </h4>
            {personGaps.length > 0 && (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>İşyeri / firma</th>
                      <th>Eksik 6331 görevi</th>
                      <th>Açıklama</th>
                      <th>Yasal dayanak</th>
                      <th>Modül</th>
                    </tr>
                  </thead>
                  <tbody>
                    {personGaps.map((g, i) => (
                      <tr key={`${g.check_code}-${g.company_id}-${i}`}>
                        <td>{i + 1}</td>
                        <td><strong>{g.company_name || '—'}</strong></td>
                        <td style={{color: '#991b1b', fontWeight: 700}}>{g.check_title}</td>
                        <td style={{fontSize: 13}}>{g.detail}</td>
                        <td style={{fontSize: 12, color: '#64748b'}}>{g.legal}</td>
                        <td style={{fontSize: 12, color: '#0f766e'}}>{goModuleHint(g.check_code)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {roleCatalog.length > 0 && (
            <div style={{marginTop: 18}}>
              <h4 style={{margin: '0 0 8px'}}>
                {TYPE_LABELS[selected.professional_type]} — kontrol edilen 6331 sorumluluklar
              </h4>
              <ul style={{margin: 0, paddingLeft: 18, fontSize: 13, color: '#334155'}}>
                {roleCatalog.map((c) => (
                  <li key={c.code} style={{marginBottom: 4}}>
                    <strong>{c.title}</strong>
                    <span style={{color: '#64748b'}}> — {c.legal}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div style={{marginTop: 16, marginBottom: 8}}>
            <ColumnChart
              title="Sorumluluk alanları (bu personel)"
              columns={selected.check_columns || []}
              height={140}
            />
          </div>

          <div style={{marginTop: 18}}>
            <h4 style={{margin: '0 0 10px'}}>Firma bazlı görev durumu (yapıldı / yapılmadı)</h4>
            {!selected.firms?.length ? (
              <p style={{color: '#92400e', margin: 0}}>
                Atanmış işyeri yok. Önce <strong>Görevlendirmeler</strong> menüsünden bu uzmana firma atayın.
              </p>
            ) : selected.firms.map((f) => (
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
                      {' · '}eksik: {f.failed_count ?? (f.checks || []).filter((c) => !c.passed).length}
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
                        background: c.passed ? '#f0fdf4' : '#fff1f2',
                      }}
                    >
                      {c.passed
                        ? <CheckCircle2 size={15} color="#16a34a" />
                        : <AlertTriangle size={15} color="#b91c1c" />}
                      <div>
                        <div style={{fontWeight: 650, fontSize: 13}}>
                          {c.passed ? 'Yapıldı' : 'Yapılmadı'} — {c.title}
                        </div>
                        <div style={{fontSize: 12, color: '#64748b'}}>{c.detail}</div>
                        {!c.passed && (
                          <div style={{fontSize: 12, color: '#0f766e', marginTop: 2}}>
                            Git → {goModuleHint(c.code)}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
