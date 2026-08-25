import React, {useEffect, useMemo, useState} from 'react';
import {Sparkles, ShieldCheck, Gavel, AlertTriangle, Lightbulb, RefreshCw} from 'lucide-react';
import {api} from './api';

const SEVERITY_STYLE = {
  kritik: {bg: '#fee2e2', fg: '#991b1b', label: 'Kritik'},
  orta: {bg: '#fef3c7', fg: '#92400e', label: 'Orta'},
  dusuk: {bg: '#e0f2fe', fg: '#1e40af', label: 'Düşük'},
};

function scoreColor(score) {
  if (score >= 80) return '#16a34a';
  if (score >= 60) return '#ca8a04';
  if (score >= 40) return '#ea580c';
  return '#dc2626';
}

function severityLabel(s) {
  return SEVERITY_STYLE[s]?.label || s || '—';
}

function AiAssistantTab({user, companies, reportCompanyId, setReportCompanyId, effectiveCompanyId}) {
  // --- AI Asistan (karar destek) ---
  const [aiText, setAiText] = useState('');
  const [aiActivity, setAiActivity] = useState('');
  const [aiResult, setAiResult] = useState(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiErr, setAiErr] = useState('');

  // --- Sanal Müfettiş ---
  const [inspCompany, setInspCompany] = useState(effectiveCompanyId || reportCompanyId || user?.company_id || '');
  const [inspReport, setInspReport] = useState(null);
  const [inspBusy, setInspBusy] = useState(false);
  const [inspErr, setInspErr] = useState('');

  useEffect(() => {
    if (!inspCompany && (effectiveCompanyId || reportCompanyId || user?.company_id)) {
      setInspCompany(effectiveCompanyId || reportCompanyId || user?.company_id || '');
    }
  }, [effectiveCompanyId, reportCompanyId, user?.company_id, inspCompany]);

  const companyId = inspCompany || effectiveCompanyId || reportCompanyId || user?.company_id || '';

  async function runAssistant(e) {
    e?.preventDefault?.();
    setAiBusy(true);
    setAiErr('');
    setAiResult(null);
    try {
      const body = {
        text: aiText.trim(),
        activity: aiActivity.trim() || null,
      };
      if (companyId) body.company_id = Number(companyId);
      const r = await api('/risks/assistant', {method: 'POST', body: JSON.stringify(body)});
      setAiResult(r);
    } catch (ex) {
      setAiErr(ex.message || 'AI Asistan çalıştırılamadı.');
    } finally {
      setAiBusy(false);
    }
  }

  async function runInspector(e) {
    e?.preventDefault?.();
    if (!companyId) {
      setInspErr('Önce bir işyeri seçin.');
      return;
    }
    setInspBusy(true);
    setInspErr('');
    setInspReport(null);
    try {
      const r = await api('/risks/virtual-inspector', {
        method: 'POST',
        body: JSON.stringify({company_id: Number(companyId)}),
      });
      setInspReport(r);
    } catch (ex) {
      setInspErr(ex.message || 'Sanal Müfettiş çalıştırılamadı.');
    } finally {
      setInspBusy(false);
    }
  }

  const canPickCompany = !user?.company_id;
  const companyList = useMemo(() => companies || [], [companies]);

  return (
    <div className="risk-pro-root" style={{padding: 0}}>
      {/* ===================== AI ASİSTAN ===================== */}
      <section className="panel" style={{marginBottom: 16}}>
        <div style={{display: 'flex', gap: 10, alignItems: 'center', marginBottom: 6}}>
          <Sparkles size={20} style={{color: '#7c3aed'}} />
          <h3 style={{margin: 0}}>AI Asistan — Karar Destek</h3>
        </div>
        <p style={{color: '#64748b', fontSize: 13, marginTop: 0, marginBottom: 14}}>
          Faaliyet ve risk tanımını yazın; tehlike kategorisi, Fine-Kinney skor önerisi, foto etiketleri
          ve (işyeri seçiliyse) mevzuat uyum önizlemesi tek yanıtta gelir. Ücretli AI gerektirmez; kural tabanlı.
        </p>

        <form onSubmit={runAssistant} style={{display: 'flex', flexDirection: 'column', gap: 10}}>
          <label className="field">
            <span>Faaliyet / işlem</span>
            <input
              value={aiActivity}
              onChange={(e) => setAiActivity(e.target.value)}
              placeholder="Örn. boyama, kaynak, pres, ambar taşıma"
            />
          </label>
          <label className="field">
            <span>Risk tanımı (serbest metin)</span>
            <textarea
              rows={3}
              value={aiText}
              onChange={(e) => setAiText(e.target.value)}
              placeholder="Örn. solvent ile kaplama, dokuhasiyet ve gaz tehlikesi"
            />
          </label>
          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={aiBusy}>
              {aiBusy ? <RefreshCw size={14} className="spin" /> : <Sparkles size={14} />}
              {aiBusy ? 'Analiz ediliyor…' : 'AI öneri al'}
            </button>
          </div>
        </form>

        {aiErr && <div className="error" style={{marginTop: 10}}>{aiErr}</div>}

        {aiResult && (
          <div style={{marginTop: 16, display: 'flex', flexDirection: 'column', gap: 14}}>
            {/* Tehlike kategorisi */}
            {aiResult.hazard_hint?.matched ? (
              <div style={{
                background: '#f5f3ff', border: '1px solid #ddd6fe', borderRadius: 10,
                padding: '12px 14px',
              }}>
                <div style={{display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6}}>
                  <AlertTriangle size={16} style={{color: '#7c3aed'}} />
                  <strong>Önerilen tehlike: {aiResult.hazard_hint.suggested_category}</strong>
                  <span style={{
                    background: '#ede9fe', color: '#6d28d9', borderRadius: 99,
                    padding: '2px 8px', fontSize: 11, fontWeight: 700,
                  }}>
                    {Math.round((aiResult.hazard_hint.confidence || 0) * 100)}% güven
                  </span>
                </div>
                {aiResult.hazard_hint.matched_keywords?.length > 0 && (
                  <div style={{fontSize: 12, color: '#6b7280'}}>
                    Eşleşen anahtar kelimeler: {aiResult.hazard_hint.matched_keywords.join(', ')}
                  </div>
                )}
                {aiResult.hazard_hint.alternatives?.length > 0 && (
                  <div style={{fontSize: 12, color: '#6b7280', marginTop: 4}}>
                    Alternatif: {aiResult.hazard_hint.alternatives.map((a) => a.category).join(', ')}
                  </div>
                )}
                {aiResult.hazard_hint.suggested_photo_tags?.length > 0 && (
                  <div style={{marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap'}}>
                    {aiResult.hazard_hint.suggested_photo_tags.map((t) => (
                      <span key={t} style={{
                        background: '#fff', border: '1px solid #ddd6fe', color: '#6d28d9',
                        borderRadius: 6, padding: '2px 8px', fontSize: 11,
                      }}>{t}</span>
                    ))}
                  </div>
                )}
                <p style={{fontSize: 11, color: '#9ca3af', margin: '6px 0 0'}}>
                  {aiResult.hazard_hint.note}
                </p>
              </div>
            ) : (
              <div style={{background: '#f1f5f9', borderRadius: 10, padding: '12px 14px', color: '#64748b', fontSize: 13}}>
                {aiResult.hazard_hint?.note || 'Eşleşme yok; daha fazla detay girin.'}
              </div>
            )}

            {/* Risk skor önerisi */}
            {aiResult.risk_suggestion && (
              <div style={{
                background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '12px 14px',
              }}>
                <div style={{display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8}}>
                  <Lightbulb size={16} style={{color: '#ca8a04'}} />
                  <strong>Fine-Kinney skor önerisi ({aiResult.risk_suggestion.suggested_method})</strong>
                </div>
                <div style={{display: 'flex', gap: 12, flexWrap: 'wrap'}}>
                  {[
                    ['Olasılık (O)', aiResult.risk_suggestion.probability_hint],
                    ['Frekans (F)', aiResult.risk_suggestion.frequency_hint],
                    ['Şiddet (S)', aiResult.risk_suggestion.severity_hint],
                  ].map(([label, val]) => (
                    <div key={label} style={{
                      background: '#f8fafc', borderRadius: 8, padding: '8px 14px', textAlign: 'center',
                      minWidth: 90,
                    }}>
                      <div style={{fontSize: 11, color: '#64748b'}}>{label}</div>
                      <div style={{fontSize: 22, fontWeight: 700, color: '#0f172a'}}>{val ?? '—'}</div>
                    </div>
                  ))}
                </div>
                <p style={{fontSize: 11, color: '#9ca3af', margin: '8px 0 0'}}>
                  {aiResult.risk_suggestion.note}
                </p>
              </div>
            )}

            {/* Mevzuat uyum önizleme */}
            {aiResult.compliance_preview && (
              <div style={{
                background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 10, padding: '12px 14px',
              }}>
                <div style={{display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6}}>
                  <ShieldCheck size={16} style={{color: '#d97706'}} />
                  <strong>Mevzuat uyum önizleme (bu işyeri)</strong>
                  <span style={{
                    background: '#fef3c7', color: scoreColor(aiResult.compliance_preview.compliance_score),
                    borderRadius: 99, padding: '2px 10px', fontSize: 12, fontWeight: 700,
                  }}>
                    {aiResult.compliance_preview.compliance_score}/100
                  </span>
                </div>
                <p style={{fontSize: 12, color: '#6b7280', margin: 0}}>
                  {aiResult.compliance_preview.summary}
                </p>
              </div>
            )}

            {/* Sonraki aksiyonlar */}
            {aiResult.next_actions?.length > 0 && (
              <div style={{
                background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 10, padding: '12px 14px',
              }}>
                <strong style={{display: 'block', marginBottom: 6, color: '#166534'}}>
                  Önerilen sonraki adımlar
                </strong>
                <ul style={{margin: 0, paddingLeft: 18, fontSize: 13, color: '#374151'}}>
                  {aiResult.next_actions.map((a, i) => <li key={i}>{a}</li>)}
                </ul>
              </div>
            )}
          </div>
        )}
      </section>

      {/* ===================== SANAL MÜFETTİŞ ===================== */}
      <section className="panel" style={{marginBottom: 16}}>
        <div style={{display: 'flex', gap: 10, alignItems: 'center', marginBottom: 6}}>
          <Gavel size={20} style={{color: '#dc2626'}} />
          <h3 style={{margin: 0}}>Sanal Müfettiş — Mevzuat Uyum Denetimi</h3>
        </div>
        <p style={{color: '#64748b', fontSize: 13, marginTop: 0, marginBottom: 14}}>
          Seçili işyerinin 6331 sayılı Kanun ve alt yönetmeliklere uyumunu kural tabanlı denetler;
          uyum skoru (0-100), ihlal bulguları (kritik/orta/düşük) ve tahmini idari para cezası aralığı üretir.
        </p>

        <form onSubmit={runInspector} style={{display: 'flex', gap: 10, alignItems: 'flex-end', flexWrap: 'wrap', marginBottom: 4}}>
          <label className="field" style={{flex: '1 1 280px'}}>
            <span>Denetlenecek işyeri</span>
            {canPickCompany ? (
              <select value={inspCompany} onChange={(e) => setInspCompany(e.target.value)}>
                <option value="">İşyeri seçin</option>
                {companyList.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            ) : (
              <input value={companyList.find((c) => String(c.id) === String(companyId))?.name || 'İşyeriniz'} readOnly />
            )}
          </label>
          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={inspBusy}>
              {inspBusy ? <RefreshCw size={14} className="spin" /> : <Gavel size={14} />}
              {inspBusy ? 'Denetleniyor…' : 'Denetim başlat'}
            </button>
          </div>
        </form>

        {inspErr && <div className="error" style={{marginTop: 10}}>{inspErr}</div>}

        {inspReport && (
          <div style={{marginTop: 16, display: 'flex', flexDirection: 'column', gap: 14}}>
            {/* Skor + ceza özeti */}
            <div style={{display: 'flex', gap: 14, flexWrap: 'wrap'}}>
              <div style={{
                flex: '0 0 auto', background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10,
                padding: '14px 20px', textAlign: 'center', minWidth: 120,
              }}>
                <div style={{fontSize: 11, color: '#64748b'}}>Uyum skoru</div>
                <div style={{fontSize: 36, fontWeight: 800, color: scoreColor(inspReport.compliance_score), lineHeight: 1.1}}>
                  {inspReport.compliance_score}<span style={{fontSize: 16, color: '#94a3b8'}}>/100</span>
                </div>
              </div>
              <div style={{
                flex: '1 1 220px', background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10,
                padding: '14px 18px',
              }}>
                <div style={{fontSize: 11, color: '#64748b', marginBottom: 4}}>Tahmini idari para cezası riski</div>
                <div style={{fontSize: 18, fontWeight: 700, color: '#0f172a'}}>
                  {inspReport.penalty_estimate?.min_tl?.toLocaleString('tr-TR')} – {inspReport.penalty_estimate?.max_tl?.toLocaleString('tr-TR')} TL
                </div>
                <p style={{fontSize: 11, color: '#9ca3af', margin: '4px 0 0'}}>
                  {inspReport.penalty_estimate?.note}
                </p>
              </div>
              <div style={{
                flex: '1 1 200px', background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10,
                padding: '14px 18px',
              }}>
                <div style={{fontSize: 11, color: '#64748b', marginBottom: 6}}>Bulgu dağılımı</div>
                <div style={{display: 'flex', gap: 8, flexWrap: 'wrap'}}>
                  {['kritik', 'orta', 'dusuk'].map((sev) => {
                    const count = (inspReport.findings || []).filter((f) => f.severity === sev).length;
                    const st = SEVERITY_STYLE[sev];
                    return (
                      <span key={sev} style={{
                        background: st.bg, color: st.fg, borderRadius: 8, padding: '4px 12px',
                        fontSize: 12, fontWeight: 700,
                      }}>
                        {count} {st.label}
                      </span>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Özet */}
            <div style={{
              background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 10, padding: '12px 14px',
              color: '#92400e', fontSize: 13,
            }}>
              <strong style={{display: 'block', marginBottom: 4}}>Özet</strong>
              {inspReport.summary}
              <div style={{fontSize: 11, color: '#9ca3af', marginTop: 4}}>
                Denetim tarihi: {inspReport.inspection_date} · Motor: {inspReport.engine}
              </div>
            </div>

            {/* Bulgular tablosu */}
            {(inspReport.findings || []).length > 0 && (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Kod</th><th>Önem</th><th>Başlık</th><th>Mevzuat</th><th>Detay</th><th>Önerilen aksiyon</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inspReport.findings.map((f) => {
                      const st = SEVERITY_STYLE[f.severity] || {bg: '#f1f5f9', fg: '#475569'};
                      return (
                        <tr key={f.code}>
                          <td><strong>{f.code}</strong></td>
                          <td>
                            <span style={{
                              background: st.bg, color: st.fg, borderRadius: 6, padding: '2px 8px',
                              fontSize: 11, fontWeight: 700,
                            }}>{severityLabel(f.severity)}</span>
                          </td>
                          <td>{f.title}</td>
                          <td>{f.regulation_ref}</td>
                          <td style={{fontSize: 12, color: '#64748b'}}>{f.detail}</td>
                          <td style={{fontSize: 12, color: '#374151'}}>{f.suggested_action}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {(!inspReport.findings || inspReport.findings.length === 0) && (
              <div style={{
                background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 10, padding: '14px',
                color: '#166534', fontSize: 14,
              }}>
                <ShieldCheck size={18} style={{verticalAlign: 'middle', marginRight: 6}} />
                Bu işyerinde mevzuat uyum ihlali tespit edilmedi. Tam uyumlu.
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

export default AiAssistantTab;
