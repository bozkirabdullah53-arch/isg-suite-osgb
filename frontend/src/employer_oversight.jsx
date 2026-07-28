import React, {useEffect, useState} from 'react';
import {AlertTriangle, BarChart3, CheckCircle2, RefreshCw, Shield} from 'lucide-react';
import {api} from './api';

/** Salt okunur işveren / işyeri denetim özeti — müdahale yok. */
export function EmployerOversightPanel({companyId, compact = false, dark = false}) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    if (!companyId) return;
    setBusy(true);
    setErr('');
    try {
      setData(await api(`/companies/${companyId}/employer-oversight`));
    } catch (e) {
      setErr(e.message || 'Özet yüklenemedi');
      setData(null);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(); }, [companyId]);

  const fg = dark ? '#f8fafc' : '#0f172a';
  const muted = dark ? 'rgba(248,250,252,.75)' : '#64748b';
  const cardBg = dark ? 'rgba(15,23,42,.55)' : '#fff';
  const border = dark ? '1px solid rgba(255,255,255,.15)' : '1px solid #e2e8f0';

  if (!companyId) {
    return <p style={{color: muted}}>İşyeri seçilmedi.</p>;
  }
  if (err) {
    return <div className="error" style={dark ? {background: 'rgba(127,29,29,.4)', color: '#fecaca'} : undefined}>{err}</div>;
  }
  if (!data) {
    return <p style={{color: muted}}>{busy ? 'Yükleniyor…' : '—'}</p>;
  }

  const v = data.visits || {};
  const w = data.work || {};
  const r = data.readiness || {};
  const visitMax = Math.max(1, v.this_month || 1);
  const workTotal = Math.max(1, (w.done || 0) + (w.open || 0));
  const pct = Math.max(0, Math.min(100, Number(r.pct) || 0));
  const verdictColor =
    data.verdict === 'hazir' ? '#4ade80' : data.verdict === 'kismi' ? '#fbbf24' : '#f87171';

  function Bar({label, value, max, color}) {
    const width = Math.round((100 * (value || 0)) / Math.max(1, max));
    return (
      <div style={{marginBottom: 10}}>
        <div style={{display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 4, color: muted}}>
          <span>{label}</span><strong style={{color: fg}}>{value ?? 0}</strong>
        </div>
        <div style={{height: 10, borderRadius: 6, background: dark ? 'rgba(255,255,255,.12)' : '#e2e8f0', overflow: 'hidden'}}>
          <div style={{width: `${width}%`, height: '100%', background: color, borderRadius: 6}} />
        </div>
      </div>
    );
  }

  return (
    <div style={{color: fg}}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, marginBottom: 14, flexWrap: 'wrap'}}>
        <div>
          <div style={{fontSize: compact ? 16 : 20, fontWeight: 700}}>{data.company_name}</div>
          <div style={{fontSize: 13, color: muted}}>Dönem: {data.period} · Salt görüntüleme</div>
        </div>
        <button
          type="button"
          className="mini secondary"
          disabled={busy}
          onClick={() => void load()}
          style={dark ? {background: 'rgba(255,255,255,.12)', color: '#fff', border: '1px solid rgba(255,255,255,.35)'} : undefined}
        >
          <RefreshCw size={14} /> Yenile
        </button>
      </div>

      <div style={{
        padding: '12px 14px', borderRadius: 12, marginBottom: 16,
        background: dark ? 'rgba(0,0,0,.25)' : '#f8fafc', border,
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <Shield size={22} color={verdictColor} />
        <div>
          <div style={{fontWeight: 700, color: verdictColor}}>{data.verdict_label}</div>
          <div style={{fontSize: 12, color: muted}}>{data.notice}</div>
        </div>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit,minmax(220px,1fr))',
        gap: 12,
        marginBottom: 16,
      }}>
        <div style={{padding: 14, borderRadius: 12, background: cardBg, border}}>
          <div style={{display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, fontWeight: 600}}>
            <BarChart3 size={18} /> Bu ay ziyaretler
          </div>
          <Bar label="Toplam" value={v.this_month} max={visitMax} color="#2dd4bf" />
          <Bar label="Tamamlanan" value={v.completed} max={visitMax} color="#4ade80" />
          <Bar label="Planlı" value={v.planned} max={visitMax} color="#60a5fa" />
          <Bar label="Sahada (açık giriş)" value={v.open_on_site} max={visitMax} color="#fbbf24" />
        </div>

        <div style={{padding: 14, borderRadius: 12, background: cardBg, border}}>
          <div style={{display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, fontWeight: 600}}>
            <CheckCircle2 size={18} /> İSG işleri
          </div>
          <Bar label="Tamamlanan" value={w.done} max={workTotal} color="#4ade80" />
          <Bar label="Açık / eksik" value={w.open} max={workTotal} color="#f87171" />
          <div style={{marginTop: 8, fontSize: 12, color: muted}}>
            {(w.items || []).slice(0, compact ? 4 : 8).map((it) => (
              <div key={it.kind} style={{display: 'flex', justifyContent: 'space-between', padding: '3px 0'}}>
                <span>{it.label}</span>
                <span>{it.done}/{it.count} · {it.status}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{padding: 14, borderRadius: 12, background: cardBg, border}}>
          <div style={{display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, fontWeight: 600}}>
            <AlertTriangle size={18} /> Denetime hazırlık
          </div>
          <div style={{fontSize: 36, fontWeight: 800, lineHeight: 1.1, marginBottom: 8}}>{pct}%</div>
          <div style={{height: 12, borderRadius: 8, background: dark ? 'rgba(255,255,255,.12)' : '#e2e8f0', overflow: 'hidden', marginBottom: 10}}>
            <div style={{
              width: `${pct}%`, height: '100%', borderRadius: 8,
              background: pct >= 80 ? '#4ade80' : pct >= 50 ? '#fbbf24' : '#f87171',
            }} />
          </div>
          <div style={{fontSize: 13, color: muted}}>
            Hazır {r.ready} · Kısmi {r.partial} · Eksik {r.missing}
          </div>
        </div>
      </div>

      {!compact && (r.gaps || []).length > 0 && (
        <div style={{padding: 14, borderRadius: 12, background: cardBg, border}}>
          <div style={{fontWeight: 600, marginBottom: 8}}>Öncelikli eksikler</div>
          <ul style={{margin: 0, paddingLeft: 18, fontSize: 13, color: muted}}>
            {(r.gaps || []).slice(0, 10).map((g, i) => <li key={i}>{g}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

export function EmployerOversightPage({user}) {
  const [companies, setCompanies] = useState([]);
  const [companyId, setCompanyId] = useState(user.company_id || '');
  const [err, setErr] = useState('');

  useEffect(() => {
    api('/companies')
      .then((rows) => {
        setCompanies(rows || []);
        if (!companyId && rows?.length) setCompanyId(String(rows[0].id));
      })
      .catch((e) => setErr(e.message));
  }, []);

  return (
    <>
      <div className="page-title">
        <h3><Shield size={20} /> İşyeri Denetim Durumu</h3>
      </div>
      <section className="panel">
        <p style={{marginTop: 0, color: '#64748b', fontSize: 14}}>
          OSGB hizmetinin işyerinde sağlıklı yürüyüp yürümediğini tek ekranda görün.
          Kayıt oluşturma / onay / silme yok — yalnızca mevzuata göre hazırlık ve iş durumu.
        </p>
        {err && <div className="error">{err}</div>}
        {!user.company_id && (
          <label className="field" style={{maxWidth: 420, marginBottom: 16}}>
            <span>İşyeri</span>
            <select value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
              <option value="">Seçiniz</option>
              {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
        )}
        <EmployerOversightPanel companyId={companyId ? Number(companyId) : null} />
      </section>
    </>
  );
}
