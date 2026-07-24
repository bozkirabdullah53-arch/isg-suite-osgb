import {useEffect, useState} from 'react';
import {api} from './api';

/**
 * P1-12: Versiyonlu hukuki onay paneli — Aydınlatma / açık rıza ayrı kayıt.
 */
export function LegalAcceptancesPanel() {
  const [docs, setDocs] = useState([]);
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  const load = () =>
    api('/legal/documents')
      .then(setDocs)
      .catch((e) => setMsg(e.message));

  useEffect(() => {
    void load();
  }, []);

  async function accept(key) {
    setBusy(true);
    setMsg('');
    try {
      await api('/legal/accept', {method: 'POST', body: JSON.stringify({document_key: key})});
      setMsg('Onay kaydedildi.');
      await load();
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  const basisLabel = {
    kvkk_art_10: 'Aydınlatma (KVKK md.10)',
    explicit_consent: 'Açık rıza',
    contract: 'Sözleşme',
  };

  return (
    <section className="panel" style={{marginTop: 16}}>
      <h3>Hukuki Onaylar</h3>
      <p style={{marginTop: 0, color: '#64748b', fontSize: 14}}>
        Aydınlatma ile açık rıza ayrı kayıttır. Onaylar sürüm bazlıdır; metin güncellenince yeniden onay gerekir.
      </p>
      {msg && (
        <p style={{color: msg.includes('kaydedildi') ? '#166534' : '#b91c1c'}}>{msg}</p>
      )}
      <div style={{display: 'grid', gap: 12}}>
        {docs.map((d) => (
          <div
            key={d.key}
            style={{
              border: '1px solid #e2e8f0',
              borderRadius: 8,
              padding: '12px 14px',
              background: d.accepted ? '#f0fdf4' : '#fff',
            }}
          >
            <div style={{display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap'}}>
              <div>
                <strong>{d.title}</strong>
                <div style={{fontSize: 13, color: '#64748b', marginTop: 4}}>
                  {basisLabel[d.legal_basis] || d.legal_basis} · sürüm {d.version}
                </div>
                <div style={{fontSize: 13, marginTop: 6}}>{d.summary}</div>
                {d.accepted && d.accepted_at && (
                  <div style={{fontSize: 12, color: '#166534', marginTop: 6}}>
                    Onaylandı: {new Date(d.accepted_at).toLocaleString('tr-TR')}
                  </div>
                )}
              </div>
              <div>
                {d.accepted ? (
                  <span style={{fontSize: 13, color: '#166534'}}>Kayıtlı</span>
                ) : (
                  <button type="button" disabled={busy} onClick={() => accept(d.key)}>
                    Okudum, onaylıyorum
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
        {!docs.length && !msg && <p style={{color: '#64748b'}}>Belgeler yükleniyor…</p>}
      </div>
    </section>
  );
}
