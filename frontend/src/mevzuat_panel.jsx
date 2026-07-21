import React, {useEffect, useMemo, useState} from 'react';
import {BookOpen, RefreshCw, Search} from 'lucide-react';
import {api} from './api';

export function MevzuatPanelPage() {
  const [data, setData] = useState(null);
  const [q, setQ] = useState('');
  const [category, setCategory] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  async function load(nextQ = q, nextCat = category) {
    setBusy(true);
    setErr('');
    try {
      const params = new URLSearchParams();
      if ((nextQ || '').trim()) params.set('q', nextQ.trim());
      if (nextCat) params.set('category', nextCat);
      const qs = params.toString();
      setData(await api(`/osgb/mevzuat-panel${qs ? `?${qs}` : ''}`));
    } catch (e) {
      setErr(e.message || 'Mevzuat paneli yüklenemedi.');
      setData(null);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load('', '');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const categories = data?.categories || [];
  const highlights = data?.highlights || [];
  const catalog = data?.catalog || [];

  const catOptions = useMemo(
    () => [{name: '', label: 'Genel / tümü'}, ...categories.map((c) => ({
      name: c.name,
      label: `${c.name} (${c.regulation_count})`,
    }))],
    [categories],
  );

  return (
    <>
      <div className="page-title">
        <h3>Mevzuat Özeti</h3>
        <div className="actions">
          <button type="button" className="secondary" disabled={busy} onClick={() => void load()}>
            <RefreshCw size={16} /> Yenile
          </button>
        </div>
      </div>

      <section className="panel" style={{marginBottom: 16}}>
        <p style={{margin: '0 0 12px', color: '#475569', fontSize: 14, lineHeight: 1.5}}>
          OSGB yöneticisi için küratörlü İSG mevzuat hatırlatmaları ve tehlike kategorisine göre
          referans listesi. Resmî metin ve Resmî Gazete esas alınmalıdır.
        </p>
        <div style={{display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'end'}}>
          <label className="field" style={{flex: '1 1 220px', margin: 0}}>
            <span>Ara</span>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void load()}
              placeholder="örn. yangın, eğitim, KATİP"
            />
          </label>
          <label className="field" style={{flex: '1 1 220px', margin: 0}}>
            <span>Tehlike kategorisi</span>
            <select
              value={category}
              onChange={(e) => {
                const v = e.target.value;
                setCategory(v);
                void load(q, v);
              }}
            >
              {catOptions.map((c) => (
                <option key={c.name || '_all'} value={c.name}>{c.label}</option>
              ))}
            </select>
          </label>
          <button type="button" disabled={busy} onClick={() => void load()}>
            <Search size={16} /> Filtrele
          </button>
        </div>
        {data && (
          <p style={{margin: '12px 0 0', fontSize: 13, color: '#64748b'}}>
            Motor: <strong>{data.engine}</strong>
            {' · '}Son gözden geçirme: <strong>{data.last_reviewed}</strong>
            {' · '}Katalog: <strong>{data.catalog_total}</strong> başlık
          </p>
        )}
        {err && <p className="error" style={{marginTop: 12}}>{err}</p>}
      </section>

      <section className="panel" style={{marginBottom: 16}}>
        <h4 style={{margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 8}}>
          <BookOpen size={18} /> Öne çıkanlar
        </h4>
        {busy && !data ? (
          <p className="empty">Yükleniyor…</p>
        ) : highlights.length === 0 ? (
          <p className="empty">Aramayla eşleşen özet yok.</p>
        ) : (
          <div style={{display: 'grid', gap: 12}}>
            {highlights.map((h) => (
              <article
                key={h.id}
                style={{
                  border: '1px solid #e2e8f0',
                  borderRadius: 10,
                  padding: '12px 14px',
                  background: '#f8fafc',
                }}
              >
                <div style={{display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'baseline'}}>
                  <strong style={{fontSize: 15}}>{h.title}</strong>
                  <span style={{
                    fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 999,
                    background: '#e0e7ff', color: '#3730a3',
                  }}>{h.topic}</span>
                </div>
                <p style={{margin: '8px 0', fontSize: 14, color: '#334155', lineHeight: 1.5}}>{h.summary}</p>
                <p style={{margin: '0 0 6px', fontSize: 12, color: '#64748b'}}>
                  Dayanak: {h.instrument}
                </p>
                {h.osgb_tip && (
                  <p style={{margin: 0, fontSize: 13, color: '#0f766e'}}>
                    OSGB ipucu: {h.osgb_tip}
                  </p>
                )}
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <h4 style={{margin: '0 0 12px'}}>
          Referans listesi
          {data?.selected_category ? ` — ${data.selected_category}` : ' — genel'}
          {catalog.length ? ` (${catalog.length})` : ''}
        </h4>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Mevzuat / düzenleme adı</th></tr>
            </thead>
            <tbody>
              {catalog.length ? catalog.map((row) => (
                <tr key={row.name}><td>{row.name}</td></tr>
              )) : (
                <tr><td className="empty">Kayıt yok.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        {data?.disclaimer && (
          <p style={{margin: '12px 0 0', fontSize: 12, color: '#94a3b8', lineHeight: 1.45}}>
            {data.disclaimer}
          </p>
        )}
      </section>
    </>
  );
}
