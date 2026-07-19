import React, {useEffect, useMemo, useState} from 'react';
import {AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, FileStack, Printer, RefreshCw} from 'lucide-react';
import {api} from './api';

const STATUS_LABELS = {
  ready: 'Hazır',
  partial: 'Kısmi',
  missing: 'Eksik',
};

function statusStyle(status) {
  if (status === 'ready') return {bg: '#dcfce7', fg: '#166534'};
  if (status === 'partial') return {bg: '#fef3c7', fg: '#92400e'};
  return {bg: '#fee2e2', fg: '#991b1b'};
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

function evidenceLine(ev) {
  if (!ev || typeof ev !== 'object') return String(ev ?? '');
  if (ev.name) {
    return `${ev.name}${ev.certificate_number ? ` · ${ev.certificate_number}` : ''}${ev.certificate_class ? ` · Sınıf ${ev.certificate_class}` : ''}`;
  }
  if (ev.contract_number) return `Sözleşme ${ev.contract_number} (${ev.status || '—'})`;
  if (ev.isg_katip != null) return `Görevlendirme #${ev.id} · KATİP: ${ev.isg_katip || 'yok'}`;
  if (ev.category) return `${ev.category}: ${ev.count}`;
  if (ev.field) return `${ev.field}: ${ev.value}`;
  return JSON.stringify(ev);
}

export function CsgbAuditPackPage({user}) {
  const [orgs, setOrgs] = useState([]);
  const [osgbId, setOsgbId] = useState('');
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState('priority'); // all | priority | ready
  const [openCode, setOpenCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  if (user.role !== 'global_admin') {
    return (
      <>
        <div className="page-title"><h3>ÇSGB Denetim Belge Paketi</h3></div>
        <section className="panel"><p>Bu ekran yalnızca global yönetici tarafından görüntülenebilir.</p></section>
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
      const r = await api(`/osgb/csgb-audit-pack${q}`);
      setData(r);
      const pri = (r.summary?.priority_count ?? (r.gaps || []).length) > 0;
      setFilter(pri ? 'priority' : 'all');
    } catch (e) {
      setError(e.message || 'Paket yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const sum = data?.summary;
  const items = data?.items || [];

  const filtered = useMemo(() => {
    if (filter === 'ready') return items.filter((i) => i.status === 'ready');
    if (filter === 'priority') return items.filter((i) => i.status === 'missing' || i.status === 'partial');
    return items;
  }, [items, filter]);

  const byGroup = useMemo(() => {
    const map = new Map();
    for (const it of filtered) {
      const key = it.group || 'genel';
      if (!map.has(key)) map.set(key, {id: key, label: it.group_label || 'Genel', items: []});
      map.get(key).items.push(it);
    }
    return [...map.values()];
  }, [filtered]);

  return (
    <>
      <div className="page-title" style={{display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap'}}>
        <div>
          <h3>ÇSGB Denetim Belge Paketi</h3>
          <p style={{margin: '4px 0 0', color: '#64748b', fontSize: 13}}>
            Müfettiş checklist’i: kurumsal, kadro, sözleşme ve saha kayıtlarının hazırlık durumu.
          </p>
        </div>
        <div style={{display: 'flex', gap: 8}}>
          <button type="button" className="ghost" disabled={busy} onClick={() => void load()}>
            <RefreshCw size={16} /> Yenile
          </button>
          {data && (
            <button type="button" className="ghost" onClick={() => window.print()}>
              <Printer size={16} /> Yazdır
            </button>
          )}
        </div>
      </div>

      {error && <div className="error" style={{marginBottom: 12}}>{error}</div>}

      {orgs.length > 1 && (
        <section className="panel" style={{marginBottom: 16}}>
          <label className="field" style={{maxWidth: 360}}>
            <span>OSGB</span>
            <select
              value={osgbId}
              onChange={(e) => {
                setOsgbId(e.target.value);
                void load(e.target.value);
              }}
            >
              {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          </label>
        </section>
      )}

      {data && (
        <>
          <section className="panel" style={{marginBottom: 16}}>
            <div style={{display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap'}}>
              <div>
                <div style={{display: 'flex', alignItems: 'center', gap: 8, color: '#475569', fontSize: 13}}>
                  <FileStack size={18} /> {data.report_title}
                </div>
                <h2 style={{margin: '6px 0 0', fontSize: 20}}>{data.osgb?.name || '—'}</h2>
                <p style={{margin: '6px 0 0', fontSize: 13, color: '#64748b'}}>
                  Yetki: {data.osgb?.authorization_number || '—'}
                  {data.osgb?.tax_number ? ` · VKN: ${data.osgb.tax_number}` : ''}
                  {data.osgb?.responsible_manager ? ` · Sorumlu: ${data.osgb.responsible_manager}` : ''}
                </p>
                <p style={{margin: '4px 0 0', fontSize: 13, color: '#64748b'}}>
                  İşyeri: {data.osgb?.company_count ?? 0} ·
                  Profesyonel: {data.osgb?.professional_count ?? 0} ·
                  Görevlendirme: {data.osgb?.assignment_count ?? 0}
                </p>
                <p style={{margin: '8px 0 0', fontSize: 12, color: '#94a3b8', maxWidth: 640}}>
                  {data.legal_note}
                </p>
              </div>
              <div style={{
                minWidth: 120, textAlign: 'center', padding: '14px 18px',
                borderRadius: 12, background: '#eff6ff', color: '#1e40af',
              }}>
                <div style={{fontSize: 32, fontWeight: 800}}>%{sum?.readiness_pct ?? 0}</div>
                <div style={{fontSize: 12, fontWeight: 700}}>Hazırlık</div>
              </div>
            </div>
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))',
              gap: 10, marginTop: 16,
            }}>
              {[
                ['Hazır', sum?.ready ?? 0, '#166534', '#dcfce7'],
                ['Kısmi', sum?.partial ?? 0, '#92400e', '#fef3c7'],
                ['Eksik', sum?.missing ?? 0, '#991b1b', '#fee2e2'],
                ['Toplam', sum?.total ?? 0, '#334155', '#f1f5f9'],
              ].map(([label, val, fg, bg]) => (
                <div key={label} style={{padding: '10px 12px', borderRadius: 10, background: bg, color: fg}}>
                  <div style={{fontSize: 11}}>{label}</div>
                  <div style={{fontSize: 22, fontWeight: 750}}>{val}</div>
                </div>
              ))}
            </div>
          </section>

          {(data.gaps || []).length > 0 && (
            <section className="panel" style={{marginBottom: 16}}>
              <h3 style={{display: 'flex', alignItems: 'center', gap: 8, marginTop: 0}}>
                <AlertTriangle size={18} color="#d97706" /> Denetim öncesi tamamlanması gerekenler ({data.gaps.length})
              </h3>
              <ul style={{margin: 0, paddingLeft: 18, color: '#475569', fontSize: 13, lineHeight: 1.55}}>
                {data.gaps.map((g, i) => <li key={i}>{g}</li>)}
              </ul>
            </section>
          )}

          <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12}}>
            <button type="button" className={filter === 'priority' ? '' : 'secondary'} onClick={() => setFilter('priority')}>
              Öncelikli ({sum?.priority_count ?? (data.gaps || []).length})
            </button>
            <button type="button" className={filter === 'all' ? '' : 'secondary'} onClick={() => setFilter('all')}>
              Tümü ({sum?.total ?? items.length})
            </button>
            <button type="button" className={filter === 'ready' ? '' : 'secondary'} onClick={() => setFilter('ready')}>
              Hazır ({sum?.ready ?? 0})
            </button>
          </div>

          {byGroup.map((grp) => (
            <section key={grp.id} className="panel" style={{marginBottom: 16}}>
              <h3 style={{marginTop: 0}}>{grp.label}</h3>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th style={{width: 36}} />
                      <th>Durum</th>
                      <th>Kalem</th>
                      <th>Adet</th>
                      <th>Açıklama</th>
                      <th>Dayanak</th>
                    </tr>
                  </thead>
                  <tbody>
                    {grp.items.map((it) => {
                      const open = openCode === it.code;
                      const hasEv = (it.evidence || []).length > 0;
                      return (
                        <React.Fragment key={it.code}>
                          <tr
                            style={{cursor: hasEv ? 'pointer' : undefined}}
                            onClick={() => hasEv && setOpenCode(open ? '' : it.code)}
                          >
                            <td>
                              {hasEv
                                ? (open ? <ChevronDown size={16} /> : <ChevronRight size={16} />)
                                : null}
                            </td>
                            <td><StatusPill status={it.status} /></td>
                            <td>
                              <strong>{it.title}</strong>
                              {it.status === 'ready' && (
                                <CheckCircle2 size={14} color="#16a34a" style={{marginLeft: 6, verticalAlign: 'middle'}} />
                              )}
                            </td>
                            <td>{it.count}</td>
                            <td style={{fontSize: 13}}>{it.detail}</td>
                            <td style={{fontSize: 12, color: '#64748b', maxWidth: 200}}>{it.legal}</td>
                          </tr>
                          {open && hasEv && (
                            <tr>
                              <td colSpan={6} style={{background: '#f8fafc', fontSize: 12, color: '#475569'}}>
                                <strong style={{display: 'block', marginBottom: 6}}>Kanıt / kayıt özeti</strong>
                                <ul style={{margin: 0, paddingLeft: 18}}>
                                  {(it.evidence || []).slice(0, 20).map((ev, i) => (
                                    <li key={i}>{evidenceLine(ev)}</li>
                                  ))}
                                </ul>
                                {(it.evidence || []).length > 20 && (
                                  <div style={{marginTop: 6}}>+{(it.evidence || []).length - 20} kayıt daha</div>
                                )}
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          ))}

          {!filtered.length && (
            <section className="panel">
              <p style={{margin: 0, color: '#166534'}}>
                {filter === 'priority' ? 'Öncelikli eksik/kısmi kalem yok — paket hazır görünüyor.' : 'Kayıt yok.'}
              </p>
            </section>
          )}

          <p style={{marginTop: 4, fontSize: 12, color: '#94a3b8'}}>
            Üretim: {data.generated_at}. Resmi asıllar (yetki belgesi, imzalı sözleşmeler, İSG-KATİP çıktıları)
            fiziksel/dijital arşivde ayrıca tutulmalıdır.
          </p>
        </>
      )}
    </>
  );
}
