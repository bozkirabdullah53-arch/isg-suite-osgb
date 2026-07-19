import React, {useEffect, useState} from 'react';
import {AlertTriangle, CheckCircle2, FileStack, Printer, RefreshCw} from 'lucide-react';
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

export function CsgbAuditPackPage({user}) {
  const [orgs, setOrgs] = useState([]);
  const [osgbId, setOsgbId] = useState('');
  const [data, setData] = useState(null);
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
    } catch (e) {
      setError(e.message || 'Paket yüklenemedi.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const sum = data?.summary;

  return (
    <>
      <div className="page-title" style={{display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap'}}>
        <div>
          <h3>ÇSGB Denetim Belge Paketi</h3>
          <p style={{margin: '4px 0 0', color: '#64748b', fontSize: 13}}>
            Müfettişin OSGB denetiminde istediği tipik belge ve kayıtların sistemdeki hazırlık durumu.
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
                  Yetki: {data.osgb?.authorization_number || '—'} ·
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
                <AlertTriangle size={18} color="#d97706" /> Öncelikli tamamlanması gerekenler
              </h3>
              <ul style={{margin: 0, paddingLeft: 18, color: '#475569', fontSize: 13, lineHeight: 1.55}}>
                {data.gaps.slice(0, 12).map((g, i) => <li key={i}>{g}</li>)}
              </ul>
            </section>
          )}

          <section className="panel">
            <h3 style={{marginTop: 0}}>Belge / kayıt kalemleri</h3>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Durum</th>
                    <th>Kalem</th>
                    <th>Adet</th>
                    <th>Açıklama</th>
                    <th>Dayanak</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.items || []).map((it) => (
                    <tr key={it.code}>
                      <td><StatusPill status={it.status} /></td>
                      <td>
                        <strong>{it.title}</strong>
                        {it.status === 'ready' && (
                          <CheckCircle2 size={14} color="#16a34a" style={{marginLeft: 6, verticalAlign: 'middle'}} />
                        )}
                      </td>
                      <td>{it.count}</td>
                      <td style={{fontSize: 13}}>{it.detail}</td>
                      <td style={{fontSize: 12, color: '#64748b', maxWidth: 220}}>{it.legal}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p style={{marginTop: 12, fontSize: 12, color: '#94a3b8'}}>
              Üretim tarihi: {data.generated_at}. Resmi asıl belgeler (yetki belgesi fotokopisi, imzalı sözleşmeler vb.)
              fiziksel / dijital arşivde ayrıca tutulmalıdır.
            </p>
          </section>
        </>
      )}
    </>
  );
}
