import React, {useEffect, useMemo, useRef, useState} from 'react';
import {Camera, ScanLine, ShieldCheck, Gavel, AlertTriangle, RefreshCw, CheckCircle2, FileText, MapPin} from 'lucide-react';
import {api} from './api';

const SEV_STYLE = {
  5: {bg: '#fee2e2', fg: '#991b1b', label: 'Kritik'},
  4: {bg: '#ffedd5', fg: '#9a3412', label: 'Yüksek'},
  3: {bg: '#fef3c7', fg: '#92400e', label: 'Orta'},
  2: {bg: '#e0f2fe', fg: '#1e40af', label: 'Düşük'},
  1: {bg: '#f1f5f9', fg: '#475569', label: 'Çok düşük'},
};

function sevLabel(s) {
  return SEV_STYLE[s]?.label || `Seviye ${s}`;
}

function sevColor(s) {
  return SEV_STYLE[s]?.fg || '#475569';
}

function formatTL(n) {
  return (n ?? 0).toLocaleString('tr-TR');
}

// Fotoğraf üzerinde bounding box çizimi (normalize 0-1 koordinat → px)
function BboxCanvas({imageSrc, annotations}) {
  const imgRef = useRef(null);
  const [size, setSize] = useState({w: 0, h: 0});

  useEffect(() => {
    function update() {
      if (imgRef.current) {
        setSize({w: imgRef.current.clientWidth, h: imgRef.current.clientHeight});
      }
    }
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  return (
    <div style={{position: 'relative', display: 'inline-block', maxWidth: '100%'}}>
      {imageSrc ? (
        <img
          ref={imgRef}
          src={imageSrc}
          alt="saha"
          onLoad={() => {
            if (imgRef.current) setSize({w: imgRef.current.clientWidth, h: imgRef.current.clientHeight});
          }}
          style={{maxWidth: '100%', maxHeight: 420, borderRadius: 8, display: 'block'}}
        />
      ) : (
        <div style={{width: '100%', height: 240, background: '#f1f5f9', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8'}}>
          <Camera size={40} />
        </div>
      )}
      {imageSrc && annotations?.length > 0 && size.w > 0 && annotations.map((a, i) => {
        const [x, y, w, h] = a.box || [0, 0, 1, 1];
        const left = x * size.w;
        const top = y * size.h;
        const width = w * size.w;
        const height = h * size.h;
        const c = sevColor(a.severity);
        return (
          <div key={i} style={{
            position: 'absolute', left, top, width, height,
            border: `3px solid ${c}`, borderRadius: 4, boxSizing: 'border-box',
            boxShadow: '0 0 0 2px rgba(255,255,255,0.6)',
          }}>
            <span style={{
              position: 'absolute', top: -22, left: 0,
              background: c, color: '#fff', fontSize: 11, fontWeight: 700,
              padding: '2px 8px', borderRadius: 4, whiteSpace: 'nowrap',
            }}>
              {a.label} · {sevLabel(a.severity)} · %{Math.round((a.confidence || 0) * 100)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function SahaAiTab({user, risks, reportCompanyId, effectiveCompanyId}) {
  const [selectedRiskId, setSelectedRiskId] = useState('');
  const [medias, setMedias] = useState([]);
  const [selectedMediaId, setSelectedMediaId] = useState('');
  const [mediaUrl, setMediaUrl] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadErr, setUploadErr] = useState('');
  const [applying, setApplying] = useState(null); // {hazard, dof} applying state
  const fileRef = useRef(null);

  const companyId = effectiveCompanyId || reportCompanyId || user?.company_id || '';

  // Risk listesi (sadece fotoğraf barındıranlar öncelikli)
  const riskList = useMemo(() => risks || [], [risks]);

  useEffect(() => {
    if (!selectedRiskId && riskList.length > 0) {
      setSelectedRiskId(String(riskList[0].id));
    }
  }, [riskList, selectedRiskId]);

  // Risk seçildiğinde medyaları yükle
  async function loadMedias(riskId) {
    if (!riskId) {
      setMedias([]);
      return;
    }
    try {
      const r = await api(`/risks/${riskId}`);
      setMedias(r.media_files || []);
    } catch (ex) {
      setMedias([]);
    }
  }

  useEffect(() => {
    loadMedias(selectedRiskId);
    setSelectedMediaId('');
    setMediaUrl('');
    setAnalysis(null);
  }, [selectedRiskId]);

  // Medya seçildiğinde fotoğrafı + varsa analizi yükle
  useEffect(() => {
    if (!selectedMediaId) {
      setMediaUrl('');
      setAnalysis(null);
      return;
    }
    const media = medias.find((m) => String(m.id) === String(selectedMediaId));
    if (media) {
      setMediaUrl(`${import.meta.env.VITE_API_URL || ''}/risks/${selectedRiskId}/media/${media.id}?t=${Date.now()}`);
    }
    // Önce kayıtlı analiz var mı dene
    api(`/risks/${selectedRiskId}/media/${selectedMediaId}/analysis`)
      .then((r) => setAnalysis(r))
      .catch(() => setAnalysis(null));
  }, [selectedMediaId, selectedRiskId, medias]);

  async function handleUpload(e) {
    const file = e.target.files?.[0];
    if (!file || !selectedRiskId) return;
    setUploadBusy(true);
    setUploadErr('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('tags', JSON.stringify({selected: []}));
      await api(`/risks/${selectedRiskId}/media`, {method: 'POST', body: fd});
      await loadMedias(selectedRiskId);
    } catch (ex) {
      setUploadErr(ex.message || 'Yükleme başarısız.');
    } finally {
      setUploadBusy(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  async function runAnalysis() {
    if (!selectedRiskId || !selectedMediaId) return;
    setBusy(true);
    setErr('');
    setAnalysis(null);
    try {
      const r = await api(`/risks/${selectedRiskId}/media/${selectedMediaId}/analyze`, {method: 'POST', timeoutMs: 60000});
      setAnalysis(r);
    } catch (ex) {
      setErr(ex.message || 'AI analizi başarısız. Özellik kapalı olabilir (VISION_ANALYSIS_ENABLED).');
    } finally {
      setBusy(false);
    }
  }

  async function applyDof(hazardIndex, dofIndex) {
    setApplying({hazard: hazardIndex, dof: dofIndex});
    try {
      await api(`/risks/${selectedRiskId}/media/${selectedMediaId}/analysis/apply-dof`, {
        method: 'POST',
        body: JSON.stringify({hazard_index: hazardIndex, dof_index: dofIndex}),
      });
      // Başarı bildirimi — DÖF listesini yenilemek için risk detayını çağır
      await api(`/risks/${selectedRiskId}`).catch(() => {});
      alert('DÖF kaydı oluşturuldu (uzman onayıyla). Risk detayından DÖF listesini görebilirsiniz.');
    } catch (ex) {
      alert(ex.message || 'DÖF oluşturulamadı.');
    } finally {
      setApplying(null);
    }
  }

  const photoMedias = medias.filter((m) => m.file_type === 'photo');
  const disabled = !selectedRiskId || !selectedMediaId;

  return (
    <div className="risk-pro-root" style={{padding: 0, color: '#1f2937'}}>
      <section className="panel" style={{marginBottom: 16}}>
        <div style={{display: 'flex', gap: 10, alignItems: 'center', marginBottom: 6}}>
          <ScanLine size={20} style={{color: '#7c3aed'}} />
          <h3 style={{margin: 0}}>Saha AI — Fotoğraf Tabanlı Risk Analizi</h3>
        </div>
        <p style={{color: '#64748b', fontSize: 13, marginTop: 0, marginBottom: 14}}>
          Saha fotoğrafını yükleyin; yapay zeka risk/tehlikeleri tespit eder, fotoğraf üzerinde işaretler,
          ilgili kanun/mevzuat maddelerini sıralar, önleyici/düzeltici faaliyetleri (DÖF) önerir ve
          termin süresini hesaplar. Öneriler uzman onayıyla DÖF kaydına dönüşür.
        </p>

        {/* Risk + medya seçimi */}
        <div style={{display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 14}}>
          <label className="field" style={{flex: '1 1 240px'}}>
            <span>Risk kaydı</span>
            <select value={selectedRiskId} onChange={(e) => setSelectedRiskId(e.target.value)}>
              <option value="">Risk seçin</option>
              {riskList.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.risk_code || `#${r.id}`} — {(r.activity || '').slice(0, 40)}
                </option>
              ))}
            </select>
          </label>
          <label className="field" style={{flex: '1 1 200px'}}>
            <span>Fotoğraf</span>
            <select value={selectedMediaId} onChange={(e) => setSelectedMediaId(e.target.value)} disabled={!selectedRiskId}>
              <option value="">Fotoğraf seçin</option>
              {photoMedias.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.original_name || `Medya #${m.id}`}
                  {m.tag_labels?.length > 0 ? ` (${m.tag_labels.join(', ')})` : ''}
                </option>
              ))}
            </select>
          </label>
          <div style={{display: 'flex', flexDirection: 'column', justifyContent: 'flex-end'}}>
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" onChange={handleUpload} style={{display: 'none'}} disabled={!selectedRiskId} />
            <button type="button" className="btn" onClick={() => fileRef.current?.click()} disabled={!selectedRiskId || uploadBusy}>
              {uploadBusy ? <RefreshCw size={14} className="spin" /> : <Camera size={14} />}
              {uploadBusy ? 'Yükleniyor…' : 'Yeni fotoğraf yükle'}
            </button>
          </div>
        </div>
        {uploadErr && <div className="error" style={{marginTop: 8}}>{uploadErr}</div>}
        {selectedRiskId && photoMedias.length === 0 && !uploadBusy && (
          <div style={{color: '#94a3b8', fontSize: 13, marginBottom: 12}}>
            Bu riskte henüz fotoğraf yok. Yukarıdan yeni fotoğraf yükleyebilirsiniz.
          </div>
        )}

        {/* Fotoğraf + bbox */}
        {mediaUrl && (
          <div style={{marginBottom: 14}}>
            <BboxCanvas imageSrc={mediaUrl} annotations={analysis?.bbox_annotations || []} />
          </div>
        )}

        {/* Analiz butonu */}
        <div className="form-actions" style={{marginBottom: 8}}>
          <button type="button" className="btn btn-primary" onClick={runAnalysis} disabled={disabled || busy}>
            {busy ? <RefreshCw size={14} className="spin" /> : <ScanLine size={14} />}
            {busy ? 'Analiz ediliyor…' : 'AI Analiz Et'}
          </button>
        </div>
        {err && <div className="error" style={{marginTop: 8}}>{err}</div>}

        {/* Analiz sonucu */}
        {analysis && (
          <div style={{marginTop: 16, display: 'flex', flexDirection: 'column', gap: 14}}>
            {/* Özet */}
            <div style={{
              background: '#f5f3ff', border: '1px solid #ddd6fe', borderRadius: 10, padding: '12px 14px',
            }}>
              <div style={{display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4}}>
                <AlertTriangle size={16} style={{color: '#7c3aed'}} />
                <strong>Analiz özeti</strong>
                <span style={{
                  background: '#ede9fe', color: '#6d28d9', borderRadius: 99, padding: '2px 8px',
                  fontSize: 11, fontWeight: 700,
                }}>
                  {analysis.provider === 'api' ? 'Vision API' : analysis.provider === 'yolo' ? 'YOLO' : 'Heuristik'}
                </span>
              </div>
              <p style={{margin: 0, fontSize: 13, color: '#374151'}}>{analysis.summary}</p>
              <p style={{margin: '4px 0 0', fontSize: 11, color: '#9ca3af'}}>{analysis.note}</p>
            </div>

            {/* Tehlike kartları */}
            {(analysis.hazards || []).map((h, hi) => {
              const sev = h.severity || 3;
              const st = SEV_STYLE[sev] || SEV_STYLE[3];
              return (
                <div key={hi} style={{
                  background: '#fff', border: `1px solid ${st.bg}`, borderRadius: 10, padding: '14px 16px',
                }}>
                  {/* Başlık */}
                  <div style={{display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8, flexWrap: 'wrap'}}>
                    <span style={{
                      background: st.bg, color: st.fg, borderRadius: 8, padding: '4px 10px',
                      fontSize: 12, fontWeight: 700,
                    }}>{sevLabel(sev)}</span>
                    <strong style={{fontSize: 15}}>{h.category}</strong>
                    <span style={{fontSize: 12, color: '#64748b'}}>
                      Güven: %{Math.round((h.confidence || 0) * 100)}
                    </span>
                    {h.source_tag && (
                      <span style={{fontSize: 11, color: '#9ca3af', background: '#f1f5f9', padding: '2px 8px', borderRadius: 6}}>
                        etiket: {h.source_tag}
                      </span>
                    )}
                  </div>
                  {h.note && <p style={{fontSize: 12, color: '#64748b', margin: '0 0 10px'}}>{h.note}</p>}

                  {/* Mevzuat */}
                  {h.mevzuat && (
                    <div style={{background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: '10px 12px', marginBottom: 10}}>
                      <div style={{display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6}}>
                        <Gavel size={14} style={{color: '#d97706'}} />
                        <strong style={{fontSize: 13, color: '#92400e'}}>İlgili mevzuat</strong>
                      </div>
                      <div style={{fontSize: 12, color: '#374151', marginBottom: 2}}>
                        <strong>{h.mevzuat.kanun}</strong> — {h.mevzuat.madde}
                      </div>
                      <div style={{fontSize: 12, color: '#64748b', marginBottom: 2}}>{h.mevzuat.yonetmelik}</div>
                      <div style={{fontSize: 11, color: '#9ca3af', marginBottom: 6}}>Standart: {h.mevzuat.standart}</div>
                      {h.mevzuat.ceza_riski && (
                        <div style={{fontSize: 12, color: '#991b1b'}}>
                          Ceza riski: {formatTL(h.mevzuat.ceza_riski.min_tl)} – {formatTL(h.mevzuat.ceza_riski.max_tl)} TL
                        </div>
                      )}
                    </div>
                  )}

                  {/* Termin */}
                  {h.termin && (
                    <div style={{display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 10}}>
                      <div style={{background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, padding: '8px 12px'}}>
                        <div style={{fontSize: 11, color: '#166534'}}>Önerilen termin</div>
                        <div style={{fontSize: 16, fontWeight: 700, color: '#166534'}}>
                          {h.termin.term_days} gün
                        </div>
                        <div style={{fontSize: 11, color: '#15803d'}}>{h.termin.term_date}</div>
                      </div>
                      <div style={{flex: '1 1 200px', fontSize: 11, color: '#64748b', alignSelf: 'center'}}>
                        {h.termin.basis}
                      </div>
                    </div>
                  )}

                  {/* DÖF önerileri */}
                  {h.dof_suggestions?.length > 0 && (
                    <div>
                      <div style={{display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6}}>
                        <FileText size={14} style={{color: '#2563eb'}} />
                        <strong style={{fontSize: 13, color: '#1e40af'}}>Önerilen DÖF ({h.dof_suggestions.length})</strong>
                      </div>
                      {h.dof_suggestions.map((d, di) => (
                        <div key={di} style={{
                          display: 'flex', gap: 8, alignItems: 'flex-start', padding: '8px 10px',
                          background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, marginBottom: 6,
                        }}>
                          <div style={{flex: 1}}>
                            <div style={{fontSize: 12, color: '#374151'}}>{d.description}</div>
                            <div style={{fontSize: 11, color: '#9ca3af', marginTop: 2}}>
                              {d.type === 'preventive' ? 'Önleyici' : 'Düzeltici'} · Termin: {d.term_date || '—'}
                            </div>
                          </div>
                          <button
                            type="button"
                            className="btn btn-primary"
                            style={{fontSize: 12, padding: '4px 10px'}}
                            onClick={() => applyDof(hi, di)}
                            disabled={applying && applying.hazard === hi && applying.dof === di}
                          >
                            {applying && applying.hazard === hi && applying.dof === di ? <RefreshCw size={12} className="spin" /> : <CheckCircle2 size={12} />}
                            DÖF oluştur
                          </button>
                        </div>
                      ))}
                      <button
                        type="button"
                        className="btn"
                        style={{marginTop: 4, fontSize: 12}}
                        onClick={() => applyDof(hi, null)}
                        disabled={applying && applying.hazard === hi && applying.dof === null}
                      >
                        Tüm DÖF'leri oluştur
                      </button>
                    </div>
                  )}
                </div>
              );
            })}

            {(!analysis.hazards || analysis.hazards.length === 0) && (
              <div style={{background: '#f1f5f9', borderRadius: 10, padding: 14, color: '#64748b'}}>
                Risk tespit edilmedi. Daha fazla bağlam (risk metni/etiket) eklemeyi deneyin.
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

export default SahaAiTab;
