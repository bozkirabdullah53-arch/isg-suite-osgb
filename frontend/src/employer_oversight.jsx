import React, {useEffect, useState} from 'react';
import {AlertTriangle, BarChart3, CheckCircle2, RefreshCw, Shield} from 'lucide-react';
import {api} from './api';

function stepColor(status, dark) {
  if (status === 'approved') return dark ? '#4ade80' : '#166534';
  if (status === 'active') return dark ? '#fbbf24' : '#b45309';
  if (status === 'rejected') return dark ? '#f87171' : '#b91c1c';
  return dark ? 'rgba(248,250,252,.55)' : '#64748b';
}

function stepStatusTr(status) {
  if (status === 'approved') return 'Onayladı';
  if (status === 'active') return 'Sırada / bekliyor';
  if (status === 'rejected') return 'Reddetti';
  if (status === 'pending') return 'Bekliyor';
  return status || '—';
}

/** İşveren / işyeri paneli — imza akışı + denetim özeti. */
export function EmployerOversightPanel({companyId, user = null, compact = false, dark = false}) {
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

  async function decide(wfId, approve) {
    const note = window.prompt(approve ? 'Onay notu (isteğe bağlı):' : 'Red nedeni:') || '';
    if (!approve && !note.trim()) {
      setErr('Red için not gerekli.');
      return;
    }
    setBusy(true);
    setErr('');
    try {
      await api(`/eyas/workflows/${wfId}/${approve ? 'approve' : 'reject'}`, {
        method: 'POST',
        body: JSON.stringify({
          note: note || null,
          device_note: typeof navigator !== 'undefined' ? navigator.userAgent.slice(0, 200) : null,
        }),
      });
      await load();
    } catch (e) {
      setErr(e.message || 'Onay işlemi başarısız');
    } finally {
      setBusy(false);
    }
  }

  const fg = dark ? '#f8fafc' : '#0f172a';
  const muted = dark ? 'rgba(248,250,252,.75)' : '#64748b';
  const cardBg = dark ? 'rgba(15,23,42,.55)' : '#fff';
  const border = dark ? '1px solid rgba(255,255,255,.15)' : '1px solid #e2e8f0';

  if (!companyId) {
    return <p style={{color: muted}}>İşyeri seçilmedi.</p>;
  }
  if (err && !data) {
    return <div className="error" style={dark ? {background: 'rgba(127,29,29,.4)', color: '#fecaca'} : undefined}>{err}</div>;
  }
  if (!data) {
    return <p style={{color: muted}}>{busy ? 'Yükleniyor…' : '—'}</p>;
  }

  const v = data.visits || {};
  const w = data.work || {};
  const r = data.readiness || {};
  const flows = data.approval_flows || [];
  const visitMax = Math.max(1, v.this_month || 1);
  const workTotal = Math.max(1, (w.done || 0) + (w.open || 0));
  const pct = Math.max(0, Math.min(100, Number(r.pct) || 0));
  const verdictColor =
    data.verdict === 'hazir' ? '#4ade80' : data.verdict === 'kismi' ? '#fbbf24' : '#f87171';
  const myId = user?.id;

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
          <div style={{fontSize: 13, color: muted}}>Dönem: {data.period}</div>
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

      {err && (
        <div className="error" style={{marginBottom: 12, ...(dark ? {background: 'rgba(127,29,29,.4)', color: '#fecaca'} : {})}}>
          {err}
        </div>
      )}

      {/* İmza akışı — en üstte */}
      <div style={{padding: 14, borderRadius: 12, background: cardBg, border, marginBottom: 16}}>
        <div style={{fontWeight: 700, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 8}}>
          <CheckCircle2 size={18} /> İmza / onay akışı
        </div>
        <div style={{fontSize: 13, color: muted, marginBottom: 12}}>
          {(data.approval_chain || []).join(' → ')}
        </div>
        {flows.length === 0 ? (
          <p style={{margin: 0, fontSize: 13, color: muted}}>
            Bu işyerinde henüz onay akışı yok. Uzman Belge Onay’dan akış başlatınca burada görünür.
          </p>
        ) : (
          flows.map((wf) => {
            const mine = myId && wf.waiting_user_id === myId && wf.status === 'in_progress';
            return (
              <div
                key={wf.id}
                style={{
                  padding: '12px 0',
                  borderTop: dark ? '1px solid rgba(255,255,255,.1)' : '1px solid #e2e8f0',
                }}
              >
                <div style={{fontWeight: 600, marginBottom: 4}}>{wf.title}</div>
                <div style={{fontSize: 12, color: muted, marginBottom: 8}}>
                  {wf.document_kind} · {wf.status}
                  {wf.waiting_on ? ` · Bekleyen: ${wf.waiting_on}` : ''}
                </div>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: compact ? '1fr' : 'repeat(3, minmax(0, 1fr))',
                  gap: 8,
                  marginBottom: mine ? 10 : 0,
                }}>
                  {(wf.steps || []).map((s) => (
                    <div
                      key={s.id}
                      style={{
                        padding: '10px 12px',
                        borderRadius: 10,
                        border: dark ? '1px solid rgba(255,255,255,.12)' : '1px solid #e2e8f0',
                        background: dark ? 'rgba(0,0,0,.2)' : '#f8fafc',
                      }}
                    >
                      <div style={{fontSize: 12, color: muted}}>{s.step_order}. {s.role_label}</div>
                      <div style={{fontWeight: 600, fontSize: 14}}>{s.assignee_name || `Kullanıcı #${s.assignee_user_id}`}</div>
                      <div style={{marginTop: 4, fontSize: 13, fontWeight: 700, color: stepColor(s.status, dark)}}>
                        {stepStatusTr(s.status)}
                      </div>
                    </div>
                  ))}
                </div>
                {mine && (
                  <div style={{display: 'flex', gap: 8, flexWrap: 'wrap'}}>
                    <button type="button" className="mini" disabled={busy} onClick={() => void decide(wf.id, true)}>
                      İşveren olarak onayla
                    </button>
                    <button type="button" className="mini secondary" disabled={busy} onClick={() => void decide(wf.id, false)}
                      style={dark ? {background: 'rgba(255,255,255,.1)', color: '#fff', border: '1px solid rgba(255,255,255,.3)'} : undefined}
                    >
                      Reddet
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
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
          İmza akışı (Uzman → Hekim → İşveren) + ziyaretler + denetime hazırlık. Sırası size geldiyse buradan onaylayabilirsiniz.
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
        <EmployerOversightPanel companyId={companyId ? Number(companyId) : null} user={user} />
      </section>
    </>
  );
}
