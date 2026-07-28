import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {
  ArrowLeft, BookOpen, Download, Lock, Map, Plus, RefreshCw, Save, Trash2, Unlock, Upload,
} from 'lucide-react';
import {API_URL, api, uploadFile} from './api';
import {
  KROKI_SYMBOLS, SYMBOL_BY_TYPE, SYMBOL_GROUPS, EXTINGUISHER_SUBTYPES, ROOM_PRESETS,
  createSymbolObject, emptyScene, parseScene, hitTestObject,
} from './kroki/symbols';
import {SceneSymbol, SymbolGlyph} from './kroki/glyphs';
import {MEVZUAT_BLOCKS, SYMBOL_LEGAL_HINT} from './kroki/mevzuat';

function cloneScene(s) {
  return JSON.parse(JSON.stringify(s));
}

function clampCanvasSize(w, h) {
  const maxSide = 2400;
  const scale = Math.min(1, maxSide / Math.max(w, h, 1));
  return {
    width: Math.min(8000, Math.max(400, Math.round(w * scale))),
    height: Math.min(8000, Math.max(400, Math.round(h * scale))),
  };
}

function readImageSize(src) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve({width: img.naturalWidth || 0, height: img.naturalHeight || 0});
    img.onerror = () => resolve(null);
    img.src = src;
  });
}

/** Kat bazlı acil durum kroki editörü — TR işaret + foto üzerine yerleştirme. */
export function EmergencyKrokiEditor({planId, user, onClose}) {
  const canEdit = ['safety_specialist', 'global_admin'].includes(user?.role);
  const [plan, setPlan] = useState(null);
  const [floors, setFloors] = useState([]);
  const [floorId, setFloorId] = useState(null);
  const [scene, setScene] = useState(emptyScene());
  const [tool, setTool] = useState('select');
  const [extSubtype, setExtSubtype] = useState('abc');
  const [selectedId, setSelectedId] = useState(null);
  const [pan, setPan] = useState({x: 40, y: 40});
  const [zoom, setZoom] = useState(0.95);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [okMsg, setOkMsg] = useState('');
  const [dirty, setDirty] = useState(false);
  const [legend, setLegend] = useState(null);
  const [bgUrl, setBgUrl] = useState(null);
  const [rightTab, setRightTab] = useState('ozellik'); // ozellik | mevzuat | lejant
  const [helpOpen, setHelpOpen] = useState(false);
  const undoRef = useRef([]);
  const dragRef = useRef(null);
  const panRef = useRef(null);
  const draftRef = useRef(null);
  const [draftPreview, setDraftPreview] = useState(null);
  const svgRef = useRef(null);
  const canvasPanelRef = useRef(null);
  const saveTimer = useRef(null);
  const fileBgRef = useRef(null);
  const sceneRef = useRef(scene);
  const floorIdRef = useRef(floorId);
  const sizeSyncRef = useRef('');
  sceneRef.current = scene;
  floorIdRef.current = floorId;

  const floor = floors.find((f) => f.id === floorId) || null;
  const locked = !!plan?.locked_at;
  const editable = canEdit && !locked;

  const selected = useMemo(
    () => (scene.objects || []).find((o) => o.id === selectedId) || null,
    [scene, selectedId],
  );

  const hasGeometry = useMemo(
    () => (scene.objects || []).some((o) => o.type === 'room' || o.type === 'wall' || o.type === 'exit'),
    [scene],
  );
  const showUploadHint = editable && !bgUrl && !hasGeometry;

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

  const fitView = useCallback((fw, fh) => {
    const el = canvasPanelRef.current;
    const width = fw || floor?.width || 1600;
    const height = fh || floor?.height || 1000;
    const vw = el?.clientWidth || 900;
    const vh = el?.clientHeight || 640;
    const pad = 20;
    const z = Math.min((vw - pad * 2) / width, (vh - pad * 2) / height, 2.2);
    const nz = Math.max(0.12, Number.isFinite(z) ? z : 0.6);
    setZoom(nz);
    setPan({
      x: Math.max(8, (vw - width * nz) / 2),
      y: Math.max(8, (vh - height * nz) / 2),
    });
  }, [floor?.width, floor?.height]);

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

  const bgPath = floor?.background_storage_path || '';
  const floorW = floor?.width || 1600;
  const floorH = floor?.height || 1000;

  useEffect(() => {
    if (!floorId || !planId) {
      setBgUrl(null);
      return undefined;
    }
    if (!bgPath) {
      setBgUrl(null);
      requestAnimationFrame(() => fitView(floorW, floorH));
      return undefined;
    }
    let revoked = false;
    const token = localStorage.getItem('isg_token');
    fetch(`${API_URL}/emergency-plans/${planId}/floors/${floorId}/background`, {
      headers: token ? {Authorization: `Bearer ${token}`} : {},
    })
      .then((r) => (r.ok ? r.blob() : null))
      .then(async (b) => {
        if (!b || revoked) return;
        const u = URL.createObjectURL(b);
        setBgUrl((old) => {
          if (old) URL.revokeObjectURL(old);
          return u;
        });
        const natural = await readImageSize(u);
        if (revoked || !natural?.width || !natural?.height) {
          requestAnimationFrame(() => fitView(floorW, floorH));
          return;
        }
        const next = clampCanvasSize(natural.width, natural.height);
        const aspectDiff = Math.abs((floorW / floorH) - (next.width / next.height));
        const sizeKey = `${floorId}:${next.width}x${next.height}`;
        const needsResize = aspectDiff > 0.04
          || (floorW === 1600 && floorH === 1000)
          || Math.abs(floorW - next.width) > 40
          || Math.abs(floorH - next.height) > 40;
        if (editable && needsResize && sizeSyncRef.current !== sizeKey) {
          sizeSyncRef.current = sizeKey;
          try {
            const updated = await api(`/emergency-plans/${planId}/floors/${floorId}`, {
              method: 'PATCH',
              body: JSON.stringify({width: next.width, height: next.height}),
            });
            if (!revoked) {
              setFloors((prev) => prev.map((f) => (f.id === floorId ? updated : f)));
              requestAnimationFrame(() => fitView(next.width, next.height));
              return;
            }
          } catch { /* boyut senkronu başarısız olsa da sığdır */ }
        }
        if (!revoked) requestAnimationFrame(() => fitView(next.width, next.height));
      })
      .catch(() => setBgUrl(null));
    return () => { revoked = true; };
  }, [planId, floorId, bgPath, floorW, floorH, editable, fitView]);

  async function switchFloor(id) {
    if (dirty && editable) await saveScene(false);
    const fl = floors.find((f) => f.id === id);
    if (!fl) return;
    setFloorId(id);
    setScene(parseScene(fl.scene_json));
    setSelectedId(null);
    setDirty(false);
    undoRef.current = [];
  }

  async function saveScene(silent = true) {
    const fid = floorIdRef.current;
    if (!editable || !fid) return false;
    if (saveTimer.current) {
      clearTimeout(saveTimer.current);
      saveTimer.current = null;
    }
    setBusy(true);
    if (!silent) {
      setErr('');
      setOkMsg('');
    }
    try {
      const fl = floors.find((f) => f.id === fid);
      const body = {
        scene_json: JSON.stringify(sceneRef.current),
        width: fl?.width || 1600,
        height: fl?.height || 1000,
      };
      const updated = await api(`/emergency-plans/${planId}/floors/${fid}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      setFloors((prev) => prev.map((f) => (f.id === fid ? updated : f)));
      setDirty(false);
      if (!silent) setOkMsg('Kroki kaydedildi.');
      try {
        setLegend(await api(`/emergency-plans/${planId}/legend`));
      } catch { /* */ }
      return true;
    } catch (e) {
      setErr(e.message || 'Kayıt başarısız');
      setOkMsg('');
      return false;
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!dirty || !editable) return undefined;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => { void saveScene(true); }, 900);
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
    if (tool === 'wall' || tool === 'room') {
      draftRef.current = {type: tool, x0: world.x, y0: world.y};
      setDraftPreview({type: tool, x0: world.x, y0: world.y, x1: world.x, y1: world.y});
      e.currentTarget.setPointerCapture?.(e.pointerId);
      return;
    }
    if (tool !== 'select') {
      const extras = tool === 'extinguisher' ? {subtype: extSubtype} : {};
      const obj = createSymbolObject(tool, world.x, world.y, extras);
      if (tool === 'text') {
        const label = window.prompt('Metin (Türkçe):', obj.label);
        if (label != null) obj.label = label;
      }
      if (tool === 'room') {
        // room without drag fallback
      }
      applyScene({...scene, objects: [...scene.objects, obj]});
      setSelectedId(obj.id);
      setTool('select');
      return;
    }
    const hit = [...(scene.objects || [])].reverse().find((o) => hitTestObject(o, world.x, world.y));
    setSelectedId(hit?.id || null);
    if (hit && editable) {
      dragRef.current = {
        id: hit.id,
        ox: world.x - (hit.type === 'room' ? hit.x : hit.type === 'wall' ? hit.x1 : hit.x),
        oy: world.y - (hit.type === 'room' ? hit.y : hit.type === 'wall' ? hit.y1 : hit.y),
        start: cloneScene(scene),
        kind: hit.type,
        wallDx: hit.type === 'wall' ? hit.x2 - hit.x1 : 0,
        wallDy: hit.type === 'wall' ? hit.y2 - hit.y1 : 0,
      };
    }
  }

  function onSvgPointerMove(e) {
    if (panRef.current) {
      const d = panRef.current;
      setPan({x: d.ox + (e.clientX - d.x), y: d.oy + (e.clientY - d.y)});
      return;
    }
    if (draftRef.current) {
      const world = clientToWorld(e.clientX, e.clientY);
      setDraftPreview({
        type: draftRef.current.type,
        x0: draftRef.current.x0,
        y0: draftRef.current.y0,
        x1: world.x,
        y1: world.y,
      });
      return;
    }
    if (!dragRef.current || !editable) return;
    const world = clientToWorld(e.clientX, e.clientY);
    const {id, ox, oy, kind, wallDx, wallDy} = dragRef.current;
    setScene((prev) => ({
      ...prev,
      objects: prev.objects.map((o) => {
        if (o.id !== id) return o;
        if (kind === 'room') {
          return {...o, x: Math.round(world.x - ox), y: Math.round(world.y - oy)};
        }
        if (kind === 'wall') {
          const nx = Math.round(world.x - ox);
          const ny = Math.round(world.y - oy);
          return {...o, x1: nx, y1: ny, x2: nx + wallDx, y2: ny + wallDy};
        }
        return {...o, x: Math.round(world.x - ox), y: Math.round(world.y - oy)};
      }),
    }));
    setDirty(true);
  }

  function onSvgPointerUp() {
    if (draftRef.current && draftPreview) {
      const {type, x0, y0, x1, y1} = draftPreview;
      if (type === 'wall') {
        if (Math.hypot(x1 - x0, y1 - y0) >= 8) {
          const obj = createSymbolObject('wall', x0, y0, {x2: x1, y2: y1});
          applyScene({...scene, objects: [...scene.objects, obj]});
          setSelectedId(obj.id);
        }
      } else if (type === 'room') {
        const rx = Math.min(x0, x1);
        const ry = Math.min(y0, y1);
        const rw = Math.abs(x1 - x0);
        const rh = Math.abs(y1 - y0);
        if (rw >= 24 && rh >= 24) {
          const preset = window.prompt(
            `Mahal adı (örn. ${ROOM_PRESETS.slice(0, 4).join(', ')}):`,
            'Atölye',
          );
          const obj = createSymbolObject('room', rx, ry, {
            w: rw,
            h: rh,
            label: (preset && preset.trim()) || 'Mahal',
          });
          applyScene({...scene, objects: [...scene.objects, obj]});
          setSelectedId(obj.id);
        }
      }
      draftRef.current = null;
      setDraftPreview(null);
      setTool('select');
    }
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
    setErr('');
    try {
      const previewUrl = URL.createObjectURL(file);
      const natural = await readImageSize(previewUrl);
      URL.revokeObjectURL(previewUrl);
      let updated = await uploadFile(`/emergency-plans/${planId}/floors/${floorId}/background`, file);
      if (natural?.width && natural?.height) {
        const next = clampCanvasSize(natural.width, natural.height);
        sizeSyncRef.current = `${floorId}:${next.width}x${next.height}`;
        updated = await api(`/emergency-plans/${planId}/floors/${floorId}`, {
          method: 'PATCH',
          body: JSON.stringify({width: next.width, height: next.height}),
        });
        requestAnimationFrame(() => fitView(next.width, next.height));
      }
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

  function drawSignOnCanvas(ctx, o, ox, oy) {
    const meta = SYMBOL_BY_TYPE[o.type] || {color: '#334155', label: o.type, signClass: 'info', short: '?'};
    if (o.type === 'wall') {
      ctx.strokeStyle = o.color || '#0f172a';
      ctx.lineWidth = o.stroke || 10;
      ctx.lineCap = 'square';
      ctx.beginPath();
      ctx.moveTo(o.x1, o.y1 + oy);
      ctx.lineTo(o.x2, o.y2 + oy);
      ctx.stroke();
      return;
    }
    if (o.type === 'room') {
      ctx.fillStyle = 'rgba(248,250,252,0.85)';
      ctx.strokeStyle = o.color || '#334155';
      ctx.lineWidth = 2;
      ctx.fillRect(o.x, o.y + oy, o.w, o.h);
      ctx.strokeRect(o.x, o.y + oy, o.w, o.h);
      ctx.fillStyle = '#1e293b';
      ctx.font = 'bold 14px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(o.label || 'Mahal', o.x + o.w / 2, o.y + oy + o.h / 2);
      return;
    }
    if (o.type === 'text') {
      ctx.fillStyle = '#0f172a';
      ctx.font = '600 16px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(o.label || 'Metin', o.x, o.y + oy);
      return;
    }
    const bg = meta.signClass === 'fire' ? '#b91c1c'
      : meta.signClass === 'safe' ? '#15803d'
        : meta.color;
    const rw = o.w || 48;
    const rh = o.h || 48;
    const x = o.x;
    const y = o.y + oy;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(((o.rotation || 0) * Math.PI) / 180);
    ctx.fillStyle = bg;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(-rw / 2, -rh / 2, rw, rh, 4);
    else ctx.rect(-rw / 2, -rh / 2, rw, rh);
    ctx.fill();
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 11px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    let short = meta.short || '•';
    if (o.type === 'extinguisher') {
      short = (EXTINGUISHER_SUBTYPES.find((s) => s.id === o.subtype) || EXTINGUISHER_SUBTYPES[0]).code;
    }
    ctx.fillText(short, 0, 0);
    ctx.restore();
    ctx.fillStyle = '#0f172a';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(o.label || meta.label, x, y + rh / 2 + 14);
  }

  async function exportPoster() {
    if (!floor) return;
    setBusy(true);
    setErr('');
    try {
      if (dirty && editable) await saveScene(true);
      const w = floor.width || 1600;
      const h = floor.height || 1000;
      const footerH = 160;
      const canvas = document.createElement('canvas');
      canvas.width = w;
      canvas.height = h + 100 + footerH;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#0f172a';
      ctx.font = 'bold 22px sans-serif';
      ctx.fillText(plan?.title || 'Acil Durum Krokisi', 24, 36);
      ctx.font = '14px sans-serif';
      ctx.fillStyle = '#475569';
      ctx.fillText(`Rev ${plan?.revision_no || '00'} · ${floor.name} · TS EN ISO 7010 / 23601 uyumlu işaretler`, 24, 58);

      if (bgUrl) {
        await new Promise((resolve) => {
          const img = new Image();
          img.onload = () => {
            ctx.globalAlpha = 0.55;
            ctx.drawImage(img, 0, 100, w, h);
            ctx.globalAlpha = 1;
            resolve();
          };
          img.onerror = resolve;
          img.src = bgUrl;
        });
      } else {
        ctx.strokeStyle = '#e2e8f0';
        for (let x = 0; x < w; x += 40) {
          ctx.beginPath(); ctx.moveTo(x, 100); ctx.lineTo(x, 100 + h); ctx.stroke();
        }
        for (let y = 0; y < h; y += 40) {
          ctx.beginPath(); ctx.moveTo(0, 100 + y); ctx.lineTo(w, 100 + y); ctx.stroke();
        }
      }

      for (const o of scene.objects || []) {
        drawSignOnCanvas(ctx, o, 100);
      }

      // Mevzuat şeridi
      const fy = h + 110;
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(0, fy - 8, w, footerH);
      ctx.fillStyle = '#0f766e';
      ctx.font = 'bold 12px sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText('Mevzuat dayanağı (özet)', 24, fy + 8);
      ctx.fillStyle = '#334155';
      ctx.font = '11px sans-serif';
      const lines = [
        '6331 İSG K. md. 11–12 · İşyerlerinde Acil Durumlar Hakkında Yönetmelik md. 7–12',
        'İşyeri Bina ve Eklentileri Yönetmeliği (kaçış yolu / işaretleme)',
        'İşaretler: TS EN ISO 7010 · Kroki düzeni: TS EN ISO 23601',
      ];
      lines.forEach((t, i) => ctx.fillText(t, 24, fy + 28 + i * 16));

      const blob = await new Promise((res) => canvas.toBlob(res, 'image/png'));
      if (!blob) throw new Error('PNG oluşturulamadı');
      const file = new File([blob], `kroki-${planId}-${floor.name}.png`, {type: 'image/png'});
      const updated = await uploadFile(`/emergency-plans/${planId}/export-poster`, file);
      setPlan(updated);
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
    <div className="kroki-studio-root" style={{display: 'flex', flexDirection: 'column', gap: 10, minHeight: '70vh', width: '100%'}}>
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center',
        paddingBottom: 12, borderBottom: '1px solid #e2e8f0',
      }}>
        <button type="button" className="mini secondary" onClick={onClose}><ArrowLeft size={14} /> Plan listesi</button>
        <div style={{minWidth: 180}}>
          <div style={{fontSize: 11, letterSpacing: '.05em', textTransform: 'uppercase', color: '#0f766e', fontWeight: 700}}>
            Kroki Studio · TR standart
          </div>
          <div style={{fontSize: 16, fontWeight: 750, color: '#0f172a'}}>{plan?.title || 'Acil durum krokisi'}</div>
          <div style={{fontSize: 12, color: '#64748b'}}>Revizyon {plan?.revision_no || '—'} · {floor?.name || 'Kat'}</div>
        </div>
        {locked && <span className="badge off">Yayın kilitli</span>}
        {dirty && <span className="badge">Kaydedilmedi</span>}
        {!dirty && okMsg && <span className="badge ok">{okMsg}</span>}
        <div style={{flex: 1}} />
        <button type="button" className="mini secondary" disabled={busy} onClick={() => void loadAll()}><RefreshCw size={14} /> Yenile</button>
        {canEdit && (
          <button type="button" className="mini secondary" disabled={busy} onClick={() => void toggleLock()}>
            {locked ? <><Unlock size={14} /> Kilidi aç</> : <><Lock size={14} /> Kilitle</>}
          </button>
        )}
        {editable && (
          <button
            type="button"
            className="mini"
            disabled={busy}
            onClick={() => { void saveScene(false); }}
            title={dirty ? 'Değişiklikleri kaydet' : 'Tekrar kaydet'}
          >
            <Save size={14} /> Kaydet
          </button>
        )}
        <button type="button" className="mini" disabled={busy} onClick={() => void exportPoster()}>
          <Download size={14} /> Duvar posteri (PNG)
        </button>
        <button type="button" className="mini secondary" onClick={() => setHelpOpen((v) => !v)}>
          {helpOpen ? 'Yardımı gizle' : 'Yardım'}
        </button>
      </div>

      {err && <div className="error">{err}</div>}
      {okMsg && !err && <div className="badge ok" style={{alignSelf: 'flex-start'}}>{okMsg}</div>}

      {helpOpen && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 10,
          padding: '10px 12px',
          borderRadius: 12,
          border: '1px solid #d1e7e3',
          background: 'linear-gradient(135deg, #f0fdfa 0%, #fff 70%)',
          fontSize: 13,
          color: '#334155',
        }}>
          <div><strong style={{color: '#0f766e'}}>1.</strong> Kat planı fotoğrafı yükleyin</div>
          <div><strong style={{color: '#0f766e'}}>2.</strong> İşaretleri yerleştirin; ok yönünü sağ panelden seçin</div>
          <div><strong style={{color: '#0f766e'}}>3.</strong> Kaydet → PNG poster</div>
        </div>
      )}

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
          <button
            type="button"
            className="mini"
            style={{display: 'inline-flex', alignItems: 'center', gap: 6}}
            onClick={() => fileBgRef.current?.click()}
          >
            <Upload size={14} /> Kat planı / fotoğraf yükle
          </button>
        )}
        <input
          ref={fileBgRef}
          type="file"
          hidden
          accept=".png,.jpg,.jpeg,.webp"
          onChange={(e) => { void uploadBg(e.target.files?.[0]); e.target.value = ''; }}
        />
        {bgUrl && <span className="badge ok">Plan görseli yüklü</span>}
        <button type="button" className="mini secondary" onClick={undo} disabled={!undoRef.current.length}>Geri al</button>
      </div>

      <div className="kroki-editor-grid" style={{
        display: 'grid',
        gridTemplateColumns: '168px minmax(0,1fr) 220px',
        gap: 8,
        alignItems: 'stretch',
        minHeight: 'min(82vh, 920px)',
      }}>
        <aside className="panel" style={{padding: 8, margin: 0, maxHeight: 'min(82vh, 920px)', overflow: 'auto'}}>
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
                  title={s.iso ? `ISO ${s.iso}` : s.label}
                >
                  <SymbolGlyph type={s.type} size={26} subtype={s.type === 'extinguisher' ? extSubtype : undefined} />
                  <span style={{textAlign: 'left', lineHeight: 1.2}}>
                    {s.label}
                    {s.iso && <span style={{display: 'block', fontSize: 10, color: '#94a3b8'}}>{s.iso}</span>}
                  </span>
                </button>
              ))}
            </div>
          ))}
          {tool === 'extinguisher' && (
            <label className="field" style={{marginTop: 4}}>
              <span>Söndürücü türü</span>
              <select value={extSubtype} onChange={(e) => setExtSubtype(e.target.value)}>
                {EXTINGUISHER_SUBTYPES.map((s) => (
                  <option key={s.id} value={s.id}>{s.label}</option>
                ))}
              </select>
            </label>
          )}
          {(tool === 'wall' || tool === 'room') && (
            <p style={{fontSize: 12, color: '#64748b', marginTop: 8}}>
              {tool === 'wall' ? 'Sürükleyerek duvar çizin.' : 'Köşeden köşeye sürükleyerek mahal (oda) çizin.'}
            </p>
          )}
        </aside>

        <div
          ref={canvasPanelRef}
          className="panel kroki-canvas-panel"
          style={{
            margin: 0, padding: 0, overflow: 'hidden',
            height: 'min(84vh, 960px)', minHeight: 560,
            background: '#e8eef3', position: 'relative',
          }}
          onWheel={(e) => {
            e.preventDefault();
            setZoom((z) => Math.min(2.5, Math.max(0.12, z * (e.deltaY > 0 ? 0.9 : 1.1))));
          }}
        >
          {showUploadHint && (
            <div style={{
              position: 'absolute', zIndex: 5, inset: 16, display: 'grid', placeItems: 'center',
              pointerEvents: 'none',
            }}>
              <div style={{
                pointerEvents: 'auto',
                maxWidth: 420,
                padding: '22px 24px',
                borderRadius: 16,
                background: 'rgba(255,255,255,0.96)',
                border: '1px solid #99f6e4',
                boxShadow: '0 12px 40px #0f172a18',
                textAlign: 'center',
              }}>
                <Map size={28} color="#0f766e" style={{marginBottom: 8}} />
                <div style={{fontWeight: 750, fontSize: 16, marginBottom: 6}}>Broşürü / krokisini buradan üretin</div>
                <p style={{margin: '0 0 14px', fontSize: 13, color: '#475569', lineHeight: 1.5}}>
                  En pratik yol: binanın kat planı fotoğrafını veya tarama görselini yükleyin.
                  Sonra odaları etiketleyip acil çıkış / söndürücü işaretlerini yerleştirin.
                  İsterseniz soldan <strong>Mahal / Duvar</strong> ile sıfırdan da çizebilirsiniz.
                </p>
                <button
                  type="button"
                  onClick={() => fileBgRef.current?.click()}
                  style={{display: 'inline-flex', alignItems: 'center', gap: 8}}
                >
                  <Upload size={16} /> Kat planı fotoğrafı yükle
                </button>
              </div>
            </div>
          )}
          <svg
            ref={svgRef}
            width="100%"
            height="100%"
            style={{
              cursor: tool === 'pan' ? 'grab' : (tool === 'select' ? 'default' : 'crosshair'),
              touchAction: 'none',
            }}
            onPointerDown={onSvgPointerDown}
            onPointerMove={onSvgPointerMove}
            onPointerUp={onSvgPointerUp}
            onPointerLeave={onSvgPointerUp}
          >
            <defs>
              <marker id="arrowHead" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
                <path d="M0,0 L6,3 L0,6 Z" fill="#15803d" />
              </marker>
            </defs>
            <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>
              <rect x={0} y={0} width={w} height={h} fill="#fff" stroke="#94a3b8" strokeWidth={2} />
              {bgUrl ? (
                <image
                  href={bgUrl}
                  x={0}
                  y={0}
                  width={w}
                  height={h}
                  opacity={0.92}
                  preserveAspectRatio="none"
                />
              ) : (
                <>
                  {Array.from({length: Math.floor(w / 40) + 1}, (_, i) => (
                    <line key={`vx${i}`} x1={i * 40} y1={0} x2={i * 40} y2={h} stroke="#e2e8f0" strokeWidth={1} />
                  ))}
                  {Array.from({length: Math.floor(h / 40) + 1}, (_, i) => (
                    <line key={`hy${i}`} x1={0} y1={i * 40} x2={w} y2={i * 40} stroke="#e2e8f0" strokeWidth={1} />
                  ))}
                </>
              )}
              {(scene.objects || []).map((o) => (
                <SceneSymbol key={o.id} o={o} selected={o.id === selectedId} />
              ))}
              {draftPreview && draftPreview.type === 'wall' && (
                <line
                  x1={draftPreview.x0} y1={draftPreview.y0}
                  x2={draftPreview.x1} y2={draftPreview.y1}
                  stroke="#0f172a" strokeWidth={10} strokeLinecap="square" opacity={0.5}
                />
              )}
              {draftPreview && draftPreview.type === 'room' && (
                <rect
                  x={Math.min(draftPreview.x0, draftPreview.x1)}
                  y={Math.min(draftPreview.y0, draftPreview.y1)}
                  width={Math.abs(draftPreview.x1 - draftPreview.x0)}
                  height={Math.abs(draftPreview.y1 - draftPreview.y0)}
                  fill="rgba(15,118,110,0.08)"
                  stroke="#0f766e"
                  strokeWidth={2}
                  strokeDasharray="6 4"
                />
              )}
            </g>
          </svg>
          <div style={{position: 'absolute', right: 8, bottom: 8, display: 'flex', gap: 4, flexWrap: 'wrap', justifyContent: 'flex-end'}}>
            <button type="button" className="mini" onClick={() => fitView()}>Sığdır</button>
            <button type="button" className="mini secondary" onClick={() => setZoom((z) => Math.min(2.5, z * 1.15))}>+</button>
            <button type="button" className="mini secondary" onClick={() => setZoom((z) => Math.max(0.12, z / 1.15))}>−</button>
          </div>
        </div>

        <aside className="panel" style={{padding: 8, margin: 0, maxHeight: 'min(82vh, 920px)', overflow: 'auto'}}>
          <div style={{display: 'flex', gap: 4, marginBottom: 10, flexWrap: 'wrap'}}>
            {[
              ['ozellik', 'Özellik'],
              ['mevzuat', 'Mevzuat'],
              ['lejant', 'Lejant'],
            ].map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={rightTab === id ? 'mini' : 'mini secondary'}
                onClick={() => setRightTab(id)}
              >
                {id === 'mevzuat' ? <><BookOpen size={12} /> {label}</> : label}
              </button>
            ))}
          </div>

          {rightTab === 'ozellik' && (
            <>
              <div style={{fontWeight: 700, marginBottom: 8, fontSize: 13}}>Özellikler</div>
              {!selected ? (
                <p style={{fontSize: 13, color: '#64748b'}}>
                  Paletten işaret seçip krokıye tıklayın. Mahal/duvar için sürükleyin.
                </p>
              ) : (
                <>
                  <div style={{fontSize: 13, marginBottom: 8, display: 'flex', gap: 8, alignItems: 'center'}}>
                    <SymbolGlyph type={selected.type} subtype={selected.subtype} size={32} />
                    <div>
                      <div style={{fontWeight: 650}}>{SYMBOL_BY_TYPE[selected.type]?.label || selected.type}</div>
                      {SYMBOL_BY_TYPE[selected.type]?.iso && (
                        <div style={{fontSize: 11, color: '#64748b'}}>Ref: {SYMBOL_BY_TYPE[selected.type].iso}</div>
                      )}
                    </div>
                  </div>
                  {SYMBOL_LEGAL_HINT[selected.type] && (
                    <p style={{fontSize: 11, color: '#0f766e', background: '#f0fdfa', padding: '6px 8px', borderRadius: 8, marginBottom: 8}}>
                      {SYMBOL_LEGAL_HINT[selected.type]}
                    </p>
                  )}
                  <label className="field">
                    <span>Türkçe etiket</span>
                    <input
                      value={selected.label || ''}
                      disabled={!editable}
                      onChange={(e) => updateSelected({label: e.target.value})}
                    />
                  </label>
                  {selected.type === 'extinguisher' && (
                    <label className="field">
                      <span>Söndürücü türü</span>
                      <select
                        value={selected.subtype || 'abc'}
                        disabled={!editable}
                        onChange={(e) => {
                          const sub = EXTINGUISHER_SUBTYPES.find((s) => s.id === e.target.value);
                          updateSelected({
                            subtype: e.target.value,
                            label: `Yangın Söndürücü (${sub?.code || 'YS'})`,
                          });
                        }}
                      >
                        {EXTINGUISHER_SUBTYPES.map((s) => (
                          <option key={s.id} value={s.id}>{s.label}</option>
                        ))}
                      </select>
                    </label>
                  )}
                  {selected.type === 'room' && (
                    <label className="field">
                      <span>Hazır mahal adı</span>
                      <select
                        disabled={!editable}
                        value=""
                        onChange={(e) => {
                          if (e.target.value) updateSelected({label: e.target.value});
                        }}
                      >
                        <option value="">Seç / uygula…</option>
                        {ROOM_PRESETS.map((r) => <option key={r} value={r}>{r}</option>)}
                      </select>
                    </label>
                  )}
                  {['route', 'exit', 'door_exit', 'stairs'].includes(selected.type) && (
                    <div style={{marginBottom: 10}}>
                      <div style={{fontSize: 12, fontWeight: 650, marginBottom: 6}}>Yön</div>
                      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6}}>
                        {[
                          [0, '→ Sağ'],
                          [180, '← Sol'],
                          [270, '↑ Yukarı'],
                          [90, '↓ Aşağı'],
                        ].map(([deg, label]) => (
                          <button
                            key={deg}
                            type="button"
                            disabled={!editable}
                            className={(selected.rotation || 0) === deg ? 'mini' : 'mini secondary'}
                            onClick={() => updateSelected({rotation: deg})}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                      <p style={{fontSize: 11, color: '#64748b', margin: '6px 0 0'}}>
                        Tahliye oku / çıkış işareti bu yöne döner.
                      </p>
                    </div>
                  )}
                  {selected.type !== 'wall' && selected.type !== 'room' && !['route', 'exit', 'door_exit', 'stairs'].includes(selected.type) && (
                    <label className="field">
                      <span>Döndürme (°)</span>
                      <input
                        type="number"
                        value={selected.rotation || 0}
                        disabled={!editable}
                        onChange={(e) => updateSelected({rotation: Number(e.target.value) || 0})}
                      />
                    </label>
                  )}
                  {editable && (
                    <button type="button" className="mini secondary" style={{marginTop: 8}} onClick={deleteSelected}>
                      <Trash2 size={14} /> Sil
                    </button>
                  )}
                </>
              )}
            </>
          )}

          {rightTab === 'mevzuat' && (
            <div>
              <div style={{fontWeight: 700, marginBottom: 8, fontSize: 13}}>Bu plan hangi maddeye göre?</div>
              <p style={{fontSize: 12, color: '#64748b', marginBottom: 10, lineHeight: 1.45}}>
                Kroki ve işaretler aşağıdaki mevzuat / standartlara dayandırılır. Poster çıktısında da özet basılır.
              </p>
              {MEVZUAT_BLOCKS.map((b) => (
                <div key={b.id} style={{marginBottom: 12, paddingBottom: 10, borderBottom: '1px solid #e2e8f0'}}>
                  <div style={{fontWeight: 700, fontSize: 12, color: '#0f172a', marginBottom: 6}}>{b.title}</div>
                  {b.articles.map((a) => (
                    <div key={a.ref} style={{fontSize: 11, marginBottom: 6, lineHeight: 1.4}}>
                      <span style={{color: '#0f766e', fontWeight: 700}}>{a.ref}</span>
                      <span style={{color: '#475569'}}> — {a.text}</span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}

          {rightTab === 'lejant' && (
            <div>
              <div style={{fontWeight: 700, fontSize: 13, marginBottom: 6}}>Lejant / kontrol</div>
              {(legend?.missing || []).length > 0 && (
                <div className="error" style={{fontSize: 12, marginBottom: 8}}>
                  {(legend.missing || []).map((m) => <div key={m}>{m}</div>)}
                </div>
              )}
              <div style={{fontSize: 12, color: '#475569', marginBottom: 8}}>
                Eyas: <code>{legend?.eyas_source_key || '—'}</code>
              </div>
              {(legend?.teams || []).slice(0, 6).map((t) => (
                <div key={t.id} style={{marginBottom: 8, fontSize: 12}}>
                  <strong>{t.name}</strong>
                  {(t.members || []).slice(0, 4).map((m, i) => (
                    <div key={i} style={{color: '#64748b'}}>
                      {m.name}{m.role ? ` · ${m.role}` : ''}{m.phone ? ` · ${m.phone}` : ''}
                    </div>
                  ))}
                </div>
              ))}
              {!legend?.teams?.length && (
                <p style={{fontSize: 12, color: '#94a3b8'}}>Acil ekipler kaydı yok (Acil Ekipler modülü).</p>
              )}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
