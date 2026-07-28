import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {
  ArrowLeft, Download, Lock, Plus, RefreshCw, Save, Trash2, Unlock, Upload,
} from 'lucide-react';
import {API_URL, api, uploadFile} from './api';
import {
  KROKI_SYMBOLS, SYMBOL_BY_TYPE, SYMBOL_GROUPS, createSymbolObject,
  emptyScene, parseScene,
} from './kroki/symbols';

function cloneScene(s) {
  return JSON.parse(JSON.stringify(s));
}

function SymbolGlyph({type, size = 28}) {
  const meta = SYMBOL_BY_TYPE[type] || {emoji: '•', color: '#64748b'};
  return (
    <span
      style={{
        width: size, height: size, borderRadius: 8, display: 'inline-grid', placeItems: 'center',
        background: meta.color, color: '#fff', fontSize: size * 0.45, fontWeight: 800,
      }}
      title={meta.label}
    >
      {meta.emoji}
    </span>
  );
}

/** Kat bazlı acil durum kroki editörü (SVG, hafif). */
export function EmergencyKrokiEditor({planId, user, onClose}) {
  const canEdit = ['safety_specialist', 'global_admin'].includes(user?.role) ;
  const [plan, setPlan] = useState(null);
  const [floors, setFloors] = useState([]);
  const [floorId, setFloorId] = useState(null);
  const [scene, setScene] = useState(emptyScene());
  const [tool, setTool] = useState('select');
  const [selectedId, setSelectedId] = useState(null);
  const [pan, setPan] = useState({x: 40, y: 40});
  const [zoom, setZoom] = useState(0.7);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [dirty, setDirty] = useState(false);
  const [legend, setLegend] = useState(null);
  const [bgUrl, setBgUrl] = useState(null);
  const [showLegend, setShowLegend] = useState(true);
  const undoRef = useRef([]);
  const dragRef = useRef(null);
  const panRef = useRef(null);
  const svgRef = useRef(null);
  const saveTimer = useRef(null);
  const viewportRef = useRef(null);

  const floor = floors.find((f) => f.id === floorId) || null;
  const locked = !!plan?.locked_at;
  const editable = canEdit && !locked;

  const selected = useMemo(
    () => (scene.objects || []).find((o) => o.id === selectedId) || null,
    [scene, selectedId],
  );

  const pushUndo = useCallback((prev) => {
    undoRef.current = [...undoRef.current.slice(-49), cloneScene(prev)];
  }, []);

  const applyScene = useCallback((next, {undo = true} = {}) => {
    setScene((prev) => {
      if (undo) pushUndo(prev);
      return next;
    });
    setDirty(true);
  }, [pushUndo]);

  async function loadAll() {
    setBusy(true);
    setErr('');
    try {
      const rows = await api(`/emergency-plans`);
      const p = (rows || []).find((r) => r.id === planId);
      if (!p) throw new Error('Plan bulunamadı');
      setPlan(p);
      let fl = await api(`/emergency-plans/${planId}/floors`);
      if (!fl?.length) {
        fl = [await api(`/emergency-plans/${planId}/floors`, {
          method: 'POST',
          body: JSON.stringify({name: 'Zemin'}),
        })];
      }
      setFloors(fl);
      const active = fl.find((f) => f.id === floorId) || fl[0];
      setFloorId(active.id);
      setScene(parseScene(active.scene_json));
      setDirty(false);
      undoRef.current = [];
      try {
        setLegend(await api(`/emergency-plans/${planId}/legend`));
      } catch {
        setLegend(null);
      }
    } catch (e) {
      setErr(e.message || 'Yüklenemedi');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void loadAll(); }, [planId]);

  useEffect(() => {
    if (!floorId || !planId) {
      setBgUrl(null);
      return undefined;
    }
    const fl = floors.find((f) => f.id === floorId);
    if (!fl?.background_storage_path) {
      setBgUrl(null);
      return undefined;
    }
    let revoked = false;
    const token = localStorage.getItem('isg_token');
    fetch(`${API_URL}/emergency-plans/${planId}/floors/${floorId}/background`, {
      headers: token ? {Authorization: `Bearer ${token}`} : {},
    })
      .then((r) => (r.ok ? r.blob() : null))
      .then((b) => {
        if (!b || revoked) return;
        const u = URL.createObjectURL(b);
        setBgUrl((old) => {
          if (old) URL.revokeObjectURL(old);
          return u;
        });
      })
      .catch(() => setBgUrl(null));
    return () => {
      revoked = true;
    };
  }, [planId, floorId, floors]);

  // Prefer api base from api.js pattern
  useEffect(() => {
    // reload scene when switching floor (already set in switchFloor)
  }, [floorId]);

  async function switchFloor(id) {
    if (dirty && editable) {
      await saveScene(false);
    }
    const fl = floors.find((f) => f.id === id);
    if (!fl) return;
    setFloorId(id);
    setScene(parseScene(fl.scene_json));
    setSelectedId(null);
    setDirty(false);
    undoRef.current = [];
  }

  async function saveScene(silent = true) {
    if (!editable || !floorId) return;
    setBusy(true);
    if (!silent) setErr('');
    try {
      const body = {
        scene_json: JSON.stringify(scene),
        width: floor?.width || 1600,
        height: floor?.height || 1000,
      };
      const updated = await api(`/emergency-plans/${planId}/floors/${floorId}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      setFloors((prev) => prev.map((f) => (f.id === floorId ? updated : f)));
      setDirty(false);
      try {
        setLegend(await api(`/emergency-plans/${planId}/legend`));
      } catch { /* */ }
    } catch (e) {
      setErr(e.message || 'Kayıt başarısız');
    } finally {
      setBusy(false);
    }
  }

  // Autosave debounce
  useEffect(() => {
    if (!dirty || !editable) return undefined;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => { void saveScene(true); }, 1200);
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
    };
  }, [scene, dirty, editable, floorId]);

  function undo() {
    const prev = undoRef.current.pop();
    if (!prev) return;
    setScene(prev);
    setDirty(true);
  }

  function clientToWorld(clientX, clientY) {
    const svg = svgRef.current;
    if (!svg) return {x: 0, y: 0};
    const pt = svg.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return {x: 0, y: 0};
    const sp = pt.matrixTransform(ctm.inverse());
    return {
      x: (sp.x - pan.x) / zoom,
      y: (sp.y - pan.y) / zoom,
    };
  }

  function onSvgPointerDown(e) {
    if (!editable && tool !== 'pan') return;
    const world = clientToWorld(e.clientX, e.clientY);
    if (tool === 'pan' || e.button === 1 || e.shiftKey) {
      panRef.current = {x: e.clientX, y: e.clientY, ox: pan.x, oy: pan.y};
      return;
    }
    if (tool !== 'select') {
      if (tool === 'route') {
        const obj = createSymbolObject('route', world.x, world.y);
        applyScene({...scene, objects: [...scene.objects, obj]});
        setSelectedId(obj.id);
        setTool('select');
        return;
      }
      const obj = createSymbolObject(tool, world.x, world.y);
      if (tool === 'text') {
        const label = window.prompt('Metin:', obj.label);
        if (label != null) obj.label = label;
      }
      applyScene({...scene, objects: [...scene.objects, obj]});
      setSelectedId(obj.id);
      setTool('select');
      return;
    }
    // select mode — hit test topmost
    const hit = [...(scene.objects || [])].reverse().find((o) => {
      const hw = (o.w || 44) / 2;
      const hh = (o.h || 44) / 2;
      return world.x >= o.x - hw && world.x <= o.x + hw && world.y >= o.y - hh && world.y <= o.y + hh;
    });
    setSelectedId(hit?.id || null);
    if (hit && editable) {
      dragRef.current = {id: hit.id, ox: world.x - hit.x, oy: world.y - hit.y, start: cloneScene(scene)};
    }
  }

  function onSvgPointerMove(e) {
    if (panRef.current) {
      const d = panRef.current;
      setPan({x: d.ox + (e.clientX - d.x), y: d.oy + (e.clientY - d.y)});
      return;
    }
    if (!dragRef.current || !editable) return;
    const world = clientToWorld(e.clientX, e.clientY);
    const {id, ox, oy} = dragRef.current;
    setScene((prev) => ({
      ...prev,
      objects: prev.objects.map((o) => (
        o.id === id ? {...o, x: Math.round(world.x - ox), y: Math.round(world.y - oy)} : o
      )),
    }));
    setDirty(true);
  }

  function onSvgPointerUp() {
    if (dragRef.current?.start) {
      pushUndo(dragRef.current.start);
    }
    dragRef.current = null;
    panRef.current = null;
  }

  function deleteSelected() {
    if (!selected || !editable) return;
    applyScene({...scene, objects: scene.objects.filter((o) => o.id !== selected.id)});
    setSelectedId(null);
  }

  function updateSelected(patch) {
    if (!selected || !editable) return;
    applyScene({
      ...scene,
      objects: scene.objects.map((o) => (o.id === selected.id ? {...o, ...patch} : o)),
    });
  }

  async function addFloor() {
    if (!editable) return;
    const name = window.prompt('Kat adı:', `${floors.length + 1}. Kat`);
    if (!name) return;
    setBusy(true);
    try {
      if (dirty) await saveScene(true);
      const fl = await api(`/emergency-plans/${planId}/floors`, {
        method: 'POST',
        body: JSON.stringify({name}),
      });
      setFloors((prev) => [...prev, fl]);
      setFloorId(fl.id);
      setScene(emptyScene());
      setDirty(false);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function removeFloor() {
    if (!editable || !floorId || floors.length <= 1) return;
    if (!window.confirm(`«${floor?.name}» katı silinsin mi?`)) return;
    setBusy(true);
    try {
      await api(`/emergency-plans/${planId}/floors/${floorId}`, {method: 'DELETE'});
      const rest = floors.filter((f) => f.id !== floorId);
      setFloors(rest);
      setFloorId(rest[0].id);
      setScene(parseScene(rest[0].scene_json));
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function uploadBg(file) {
    if (!file || !editable || !floorId) return;
    setBusy(true);
    try {
      const updated = await uploadFile(`/emergency-plans/${planId}/floors/${floorId}/background`, file);
      setFloors((prev) => prev.map((f) => (f.id === floorId ? updated : f)));
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleLock() {
    if (!canEdit) return;
    setBusy(true);
    try {
      const path = locked ? 'unlock' : 'lock';
      const p = await api(`/emergency-plans/${planId}/${path}`, {method: 'POST', body: '{}'});
      setPlan(p);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function exportPoster() {
    if (!floor) return;
    setBusy(true);
    setErr('');
    try {
      if (dirty && editable) await saveScene(true);
      const w = floor.width || 1600;
      const h = floor.height || 1000;
      const canvas = document.createElement('canvas');
      canvas.width = w;
      canvas.height = h + 120;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#0f172a';
      ctx.font = 'bold 22px sans-serif';
      ctx.fillText(plan?.title || 'Acil Durum Krokisi', 24, 36);
      ctx.font = '14px sans-serif';
      ctx.fillStyle = '#475569';
      ctx.fillText(`Rev ${plan?.revision_no || '00'} · ${floor.name}`, 24, 58);

      if (bgUrl) {
        await new Promise((resolve) => {
          const img = new Image();
          img.onload = () => {
            ctx.globalAlpha = 0.55;
            ctx.drawImage(img, 0, 120, w, h);
            ctx.globalAlpha = 1;
            resolve();
          };
          img.onerror = resolve;
          img.src = bgUrl;
        });
      } else {
        ctx.strokeStyle = '#e2e8f0';
        for (let x = 0; x < w; x += 40) {
          ctx.beginPath(); ctx.moveTo(x, 120); ctx.lineTo(x, 120 + h); ctx.stroke();
        }
        for (let y = 0; y < h; y += 40) {
          ctx.beginPath(); ctx.moveTo(0, 120 + y); ctx.lineTo(w, 120 + y); ctx.stroke();
        }
      }

      for (const o of scene.objects || []) {
        const meta = SYMBOL_BY_TYPE[o.type] || {color: '#334155', emoji: '•', label: o.type};
        const x = o.x;
        const y = o.y + 120;
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(((o.rotation || 0) * Math.PI) / 180);
        ctx.fillStyle = meta.color;
        const rw = o.w || 44;
        const rh = o.h || 44;
        ctx.beginPath();
        ctx.roundRect?.(-rw / 2, -rh / 2, rw, rh, 8);
        if (!ctx.roundRect) {
          ctx.rect(-rw / 2, -rh / 2, rw, rh);
        }
        ctx.fill();
        ctx.fillStyle = '#fff';
        ctx.font = '16px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(meta.emoji || '•', 0, 0);
        ctx.restore();
        ctx.fillStyle = '#0f172a';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(o.label || meta.label, x, y + (o.h || 44) / 2 + 14);
      }

      // mini legend
      let ly = 80;
      ctx.textAlign = 'left';
      ctx.font = '12px sans-serif';
      ctx.fillStyle = '#334155';
      const used = [...new Set((scene.objects || []).map((o) => o.type))];
      used.slice(0, 8).forEach((t, i) => {
        const m = SYMBOL_BY_TYPE[t];
        if (!m) return;
        ctx.fillText(`${m.emoji} ${m.label}`, w - 220, 28 + i * 16);
        ly = 28 + i * 16;
      });
      void ly;

      const blob = await new Promise((res) => canvas.toBlob(res, 'image/png'));
      if (!blob) throw new Error('PNG oluşturulamadı');
      const file = new File([blob], `kroki-${planId}-${floor.name}.png`, {type: 'image/png'});
      const updated = await uploadFile(`/emergency-plans/${planId}/export-poster`, file);
      setPlan(updated);
      // also download locally
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = file.name;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      setErr(e.message || 'Export başarısız');
    } finally {
      setBusy(false);
    }
  }

  const w = floor?.width || 1600;
  const h = floor?.height || 1000;

  return (
    <div style={{display: 'flex', flexDirection: 'column', gap: 12, minHeight: '70vh'}}>
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center',
        paddingBottom: 12, borderBottom: '1px solid #e2e8f0',
      }}>
        <button type="button" className="mini secondary" onClick={onClose}><ArrowLeft size={14} /> Plan listesi</button>
        <div style={{minWidth: 180}}>
          <div style={{fontSize: 11, letterSpacing: '.05em', textTransform: 'uppercase', color: '#0f766e', fontWeight: 700}}>
            Kroki Studio
          </div>
          <div style={{fontSize: 16, fontWeight: 750, color: '#0f172a'}}>{plan?.title || 'Acil durum krokisi'}</div>
          <div style={{fontSize: 12, color: '#64748b'}}>Revizyon {plan?.revision_no || '—'} · {floor?.name || 'Kat'}</div>
        </div>
        {locked && <span className="badge off">Yayın kilitli</span>}
        {dirty && <span className="badge">Kaydedilmedi</span>}
        <div style={{flex: 1}} />
        <button type="button" className="mini secondary" disabled={busy} onClick={() => void loadAll()}><RefreshCw size={14} /> Yenile</button>
        {canEdit && (
          <button type="button" className="mini secondary" disabled={busy} onClick={() => void toggleLock()}>
            {locked ? <><Unlock size={14} /> Kilidi aç</> : <><Lock size={14} /> Kilitle</>}
          </button>
        )}
        {editable && (
          <button type="button" className="mini" disabled={busy || !dirty} onClick={() => void saveScene(false)}>
            <Save size={14} /> Kaydet
          </button>
        )}
        <button type="button" className="mini" disabled={busy} onClick={() => void exportPoster()}>
          <Download size={14} /> Duvar posteri (PNG)
        </button>
      </div>

      {err && <div className="error">{err}</div>}

      <div style={{display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center'}}>
        {floors.map((f) => (
          <button
            key={f.id}
            type="button"
            className={f.id === floorId ? 'mini' : 'mini secondary'}
            onClick={() => void switchFloor(f.id)}
          >
            {f.name}
          </button>
        ))}
        {editable && (
          <button type="button" className="mini secondary" onClick={() => void addFloor()}><Plus size={14} /> Kat</button>
        )}
        {editable && floors.length > 1 && (
          <button type="button" className="mini secondary" onClick={() => void removeFloor()}><Trash2 size={14} /> Katı sil</button>
        )}
        {editable && (
          <label className="mini secondary" style={{cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4}}>
            <Upload size={14} /> Plan görseli
            <input type="file" hidden accept=".png,.jpg,.jpeg,.webp" onChange={(e) => { void uploadBg(e.target.files?.[0]); e.target.value = ''; }} />
          </label>
        )}
        <button type="button" className="mini secondary" onClick={() => setShowLegend((v) => !v)}>
          {showLegend ? 'Lejantı gizle' : 'Lejant'}
        </button>
        <button type="button" className="mini secondary" onClick={undo} disabled={!undoRef.current.length}>Geri al</button>
      </div>

      <div className="kroki-editor-grid" style={{display: 'grid', gridTemplateColumns: '200px minmax(0,1fr) 240px', gap: 10, alignItems: 'stretch'}}>
        <aside className="panel" style={{padding: 10, margin: 0, maxHeight: 560, overflow: 'auto'}}>
          <div style={{fontWeight: 700, marginBottom: 8, fontSize: 13}}>Araçlar</div>
          <button
            type="button"
            className={tool === 'select' ? 'mini' : 'mini secondary'}
            style={{width: '100%', marginBottom: 4, justifyContent: 'flex-start'}}
            onClick={() => setTool('select')}
          >Seç / taşı</button>
          <button
            type="button"
            className={tool === 'pan' ? 'mini' : 'mini secondary'}
            style={{width: '100%', marginBottom: 10, justifyContent: 'flex-start'}}
            onClick={() => setTool('pan')}
          >Kaydır</button>
          {SYMBOL_GROUPS.map((g) => (
            <div key={g} style={{marginBottom: 10}}>
              <div style={{fontSize: 11, color: '#64748b', marginBottom: 4}}>{g}</div>
              {KROKI_SYMBOLS.filter((s) => s.group === g).map((s) => (
                <button
                  key={s.type}
                  type="button"
                  disabled={!editable}
                  className={tool === s.type ? 'mini' : 'mini secondary'}
                  style={{width: '100%', marginBottom: 4, justifyContent: 'flex-start', gap: 8}}
                  onClick={() => setTool(s.type)}
                >
                  <SymbolGlyph type={s.type} size={22} /> {s.label}
                </button>
              ))}
            </div>
          ))}
        </aside>

        <div
          ref={viewportRef}
          className="panel"
          style={{margin: 0, padding: 0, overflow: 'hidden', height: 560, background: '#f1f5f9', position: 'relative'}}
          onWheel={(e) => {
            e.preventDefault();
            setZoom((z) => Math.min(2.5, Math.max(0.25, z * (e.deltaY > 0 ? 0.9 : 1.1))));
          }}
        >
          <svg
            ref={svgRef}
            width="100%"
            height="100%"
            style={{cursor: tool === 'pan' ? 'grab' : (tool === 'select' ? 'default' : 'crosshair'), touchAction: 'none'}}
            onPointerDown={onSvgPointerDown}
            onPointerMove={onSvgPointerMove}
            onPointerUp={onSvgPointerUp}
            onPointerLeave={onSvgPointerUp}
          >
            <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>
              <rect x={0} y={0} width={w} height={h} fill="#fff" stroke="#cbd5e1" />
              {bgUrl && (
                <image href={bgUrl} x={0} y={0} width={w} height={h} opacity={0.55} preserveAspectRatio="xMidYMid meet" />
              )}
              {/* grid */}
              {Array.from({length: Math.floor(w / 40) + 1}, (_, i) => (
                <line key={`vx${i}`} x1={i * 40} y1={0} x2={i * 40} y2={h} stroke="#e2e8f0" strokeWidth={1} />
              ))}
              {Array.from({length: Math.floor(h / 40) + 1}, (_, i) => (
                <line key={`hy${i}`} x1={0} y1={i * 40} x2={w} y2={i * 40} stroke="#e2e8f0" strokeWidth={1} />
              ))}
              {(scene.objects || []).map((o) => {
                const meta = SYMBOL_BY_TYPE[o.type] || {color: '#64748b', emoji: '•', label: o.type};
                const rw = o.w || 44;
                const rh = o.h || 44;
                const sel = o.id === selectedId;
                return (
                  <g key={o.id} transform={`translate(${o.x},${o.y}) rotate(${o.rotation || 0})`}>
                    <rect
                      x={-rw / 2} y={-rh / 2} width={rw} height={rh} rx={8}
                      fill={meta.color}
                      stroke={sel ? '#fbbf24' : '#fff'}
                      strokeWidth={sel ? 3 : 1}
                    />
                    <text textAnchor="middle" dominantBaseline="central" fontSize={16} fill="#fff">{meta.emoji}</text>
                    <text y={rh / 2 + 14} textAnchor="middle" fontSize={11} fill="#0f172a">{o.label || meta.label}</text>
                  </g>
                );
              })}
            </g>
          </svg>
          <div style={{position: 'absolute', right: 8, bottom: 8, display: 'flex', gap: 4}}>
            <button type="button" className="mini secondary" onClick={() => setZoom((z) => Math.min(2.5, z * 1.15))}>+</button>
            <button type="button" className="mini secondary" onClick={() => setZoom((z) => Math.max(0.25, z / 1.15))}>−</button>
            <button type="button" className="mini secondary" onClick={() => { setZoom(0.7); setPan({x: 40, y: 40}); }}>Sıfırla</button>
          </div>
        </div>

        <aside className="panel" style={{padding: 10, margin: 0, maxHeight: 560, overflow: 'auto'}}>
          <div style={{fontWeight: 700, marginBottom: 8, fontSize: 13}}>Özellikler</div>
          {!selected ? (
            <p style={{fontSize: 13, color: '#64748b'}}>Nesne seçin veya paletten yerleştirin.</p>
          ) : (
            <>
              <div style={{fontSize: 13, marginBottom: 8}}>
                <SymbolGlyph type={selected.type} /> {SYMBOL_BY_TYPE[selected.type]?.label || selected.type}
              </div>
              <label className="field">
                <span>Etiket</span>
                <input
                  value={selected.label || ''}
                  disabled={!editable}
                  onChange={(e) => updateSelected({label: e.target.value})}
                />
              </label>
              <label className="field">
                <span>Döndürme (°)</span>
                <input
                  type="number"
                  value={selected.rotation || 0}
                  disabled={!editable}
                  onChange={(e) => updateSelected({rotation: Number(e.target.value) || 0})}
                />
              </label>
              {editable && (
                <button type="button" className="mini secondary" style={{marginTop: 8}} onClick={deleteSelected}>
                  <Trash2 size={14} /> Sil
                </button>
              )}
            </>
          )}

          {showLegend && legend && (
            <div style={{marginTop: 16, borderTop: '1px solid #e2e8f0', paddingTop: 12}}>
              <div style={{fontWeight: 700, fontSize: 13, marginBottom: 6}}>Lejant / kontrol</div>
              {(legend.missing || []).length > 0 && (
                <div className="error" style={{fontSize: 12, marginBottom: 8}}>
                  {(legend.missing || []).map((m) => <div key={m}>{m}</div>)}
                </div>
              )}
              <div style={{fontSize: 12, color: '#475569', marginBottom: 8}}>
                Eyas: <code>{legend.eyas_source_key}</code>
              </div>
              {(legend.teams || []).slice(0, 6).map((t) => (
                <div key={t.id} style={{marginBottom: 8, fontSize: 12}}>
                  <strong>{t.name}</strong>
                  {(t.members || []).slice(0, 4).map((m, i) => (
                    <div key={i} style={{color: '#64748b'}}>
                      {m.name}{m.role ? ` · ${m.role}` : ''}{m.phone ? ` · ${m.phone}` : ''}
                    </div>
                  ))}
                </div>
              ))}
              {!legend.teams?.length && (
                <p style={{fontSize: 12, color: '#94a3b8'}}>Acil ekipler kaydı yok (Acil Ekipler modülü).</p>
              )}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
