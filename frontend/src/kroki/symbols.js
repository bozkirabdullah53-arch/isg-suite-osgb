/** İSG acil durum kroki sembol kataloğu — TR / TS EN ISO 7010 & 23601 referansları. */

export const KROKI_SYMBOLS = [
  {type: 'room', label: 'Mahal / Oda', group: 'Çizim', signClass: 'layout', color: '#334155', short: 'ODA'},
  {type: 'wall', label: 'Duvar', group: 'Çizim', signClass: 'layout', color: '#0f172a', short: 'D'},
  {type: 'door', label: 'Kapı', group: 'Çizim', signClass: 'layout', color: '#475569', short: 'K', iso: '—'},
  {type: 'measure', label: 'Ölçü (m)', group: 'Çizim', signClass: 'layout', color: '#2563eb', short: 'm'},

  {type: 'exit', label: 'Acil Çıkış', group: 'Tahliye', signClass: 'safe', color: '#15803d', short: 'ÇIKIŞ', iso: 'E001'},
  {type: 'door_exit', label: 'Acil Çıkış Kapısı', group: 'Tahliye', signClass: 'safe', color: '#15803d', short: 'KAPI', iso: 'E002'},
  {type: 'stairs', label: 'Acil Merdiven', group: 'Tahliye', signClass: 'safe', color: '#15803d', short: 'M', iso: 'E016'},
  {type: 'assembly', label: 'Toplanma Alanı', group: 'Tahliye', signClass: 'safe', color: '#15803d', short: 'T', iso: 'E007'},
  {type: 'youarehere', label: 'Siz Buradasınız', group: 'Tahliye', signClass: 'info', color: '#1d4ed8', short: '●', iso: '23601'},
  {type: 'route', label: 'Tahliye Oku (çiz)', group: 'Tahliye', signClass: 'safe', color: '#15803d', short: '→', iso: 'E005'},

  {type: 'extinguisher', label: 'Yangın Söndürücü', group: 'Yangın', signClass: 'fire', color: '#b91c1c', short: 'YS', iso: 'F001', hasSubtype: true},
  {type: 'hose', label: 'Yangın Dolabı', group: 'Yangın', signClass: 'fire', color: '#b91c1c', short: 'YD', iso: 'F002'},
  {type: 'alarm', label: 'Yangın Alarmı', group: 'Yangın', signClass: 'fire', color: '#b91c1c', short: 'AL', iso: 'F005'},

  {type: 'firstaid', label: 'İlk Yardım (Hilal)', group: 'Sağlık', signClass: 'safe', color: '#15803d', short: '☪', iso: 'EC003-TR'},
  {type: 'aed', label: 'AED / Defibrilatör', group: 'Sağlık', signClass: 'safe', color: '#15803d', short: 'AED', iso: 'EC010'},

  {type: 'electric', label: 'Elektrik Kesme', group: 'Tesisat', signClass: 'info', color: '#b45309', short: 'EL'},
  {type: 'north', label: 'Kuzey', group: 'Diğer', signClass: 'info', color: '#0f172a', short: 'K'},
  {type: 'text', label: 'Metin', group: 'Diğer', signClass: 'layout', color: '#0f172a', short: 'T'},
];

export const EXTINGUISHER_SUBTYPES = [
  {id: 'abc', label: 'ABC Toz', code: 'ABC'},
  {id: 'co2', label: 'CO₂ (Karbondioksit)', code: 'CO₂'},
  {id: 'foam', label: 'Köpük (AFFF)', code: 'KÖPÜK'},
  {id: 'water', label: 'Su', code: 'SU'},
  {id: 'other', label: 'Diğer / Belirtilmemiş', code: 'YS'},
];

export const ROOM_PRESETS = [
  'Atölye', 'İdare', 'Üretim', 'Depo', 'Soyunma', 'Yemekhane', 'WC', 'Koridor', 'Makine Dairesi', 'Ofis',
];

export const LINE_TOOLS = new Set(['wall', 'route', 'measure']);

export const SYMBOL_BY_TYPE = Object.fromEntries(KROKI_SYMBOLS.map((s) => [s.type, s]));

export function emptyScene() {
  return {
    version: 3,
    meta: {planOpacity: 0.88, pixelsPerMeter: 100},
    objects: [],
    paths: [],
  };
}

/** Eski nokta-tipi tahliye okunu çizgiye çevir. */
function migrateObject(o) {
  if (!o || typeof o !== 'object') return o;
  if (o.type === 'route' && o.x1 == null && o.x != null) {
    const len = Math.max(56, o.w || 80);
    const rad = (((o.rotation || 0) * Math.PI) / 180);
    return {
      id: o.id,
      type: 'route',
      x1: Math.round(o.x),
      y1: Math.round(o.y),
      x2: Math.round(o.x + Math.cos(rad) * len),
      y2: Math.round(o.y + Math.sin(rad) * len),
      stroke: 8,
      label: o.label || 'Tahliye Yönü',
      color: o.color || '#15803d',
      aiSuggested: o.aiSuggested,
      note: o.note,
    };
  }
  return o;
}

export function parseScene(raw) {
  if (!raw) return emptyScene();
  try {
    const data = typeof raw === 'string' ? JSON.parse(raw) : raw;
    if (!data || typeof data !== 'object') return emptyScene();
    const meta = {
      planOpacity: Number(data.meta?.planOpacity ?? 0.88) || 0.88,
      pixelsPerMeter: Number(data.meta?.pixelsPerMeter ?? 100) || 100,
    };
    return {
      version: data.version || 1,
      meta,
      objects: (Array.isArray(data.objects) ? data.objects : []).map(migrateObject).filter(Boolean),
      paths: Array.isArray(data.paths) ? data.paths : [],
    };
  } catch {
    return emptyScene();
  }
}

export function newObjectId() {
  return `o_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
}

export function createSymbolObject(type, x, y, extras = {}) {
  const meta = SYMBOL_BY_TYPE[type] || {label: type, color: '#334155'};
  if (LINE_TOOLS.has(type)) {
    return {
      id: newObjectId(),
      type,
      x1: Math.round(x),
      y1: Math.round(y),
      x2: Math.round(extras.x2 ?? x + (type === 'measure' ? 120 : 100)),
      y2: Math.round(extras.y2 ?? y),
      stroke: type === 'wall' ? 10 : type === 'route' ? 8 : 3,
      label: type === 'route' ? 'Tahliye Yönü' : (type === 'measure' ? '' : ''),
      color: meta.color,
    };
  }
  if (type === 'room') {
    return {
      id: newObjectId(),
      type: 'room',
      x: Math.round(x),
      y: Math.round(y),
      w: Math.max(40, Math.round(extras.w ?? 160)),
      h: Math.max(40, Math.round(extras.h ?? 100)),
      label: extras.label || 'Mahal',
      color: meta.color,
    };
  }
  const base = {
    id: newObjectId(),
    type,
    x: Math.round(x),
    y: Math.round(y),
    rotation: 0,
    label: meta.label,
    w: 48,
    h: 48,
  };
  if (type === 'text') {
    base.w = 140;
    base.h = 28;
    base.label = extras.label || 'Etiket';
  }
  if (type === 'assembly') {
    base.w = 64;
    base.h = 64;
    base.label = 'TOPLANMA ALANI';
  }
  if (type === 'exit' || type === 'door_exit') {
    base.label = type === 'exit' ? 'ACİL ÇIKIŞ' : 'ACİL ÇIKIŞ KAPISI';
  }
  if (type === 'extinguisher') {
    const sub = EXTINGUISHER_SUBTYPES.find((s) => s.id === (extras.subtype || 'abc')) || EXTINGUISHER_SUBTYPES[0];
    base.subtype = sub.id;
    base.label = extras.label || `Yangın Söndürücü (${sub.code})`;
    base.w = 52;
    base.h = 52;
  }
  if (type === 'youarehere') base.label = 'SİZ BURADASINIZ';
  if (type === 'firstaid') base.label = extras.label || 'İLK YARDIM';
  if (type === 'hose') base.label = 'YANGIN DOLABI';
  if (type === 'alarm') base.label = 'YANGIN ALARMI';
  if (type === 'stairs') base.label = 'ACİL MERDİVEN';
  if (type === 'aed') base.label = 'AED';
  if (type === 'electric') base.label = 'ELEKTRİK KESME';
  if (type === 'door') base.label = extras.label || 'Kapı';
  if (type === 'north') base.label = 'KUZEY';
  return base;
}

export function objectCenter(o) {
  if (!o) return {x: 0, y: 0};
  if (LINE_TOOLS.has(o.type)) {
    return {x: (o.x1 + o.x2) / 2, y: (o.y1 + o.y2) / 2};
  }
  if (o.type === 'room') return {x: o.x + o.w / 2, y: o.y + o.h / 2};
  return {x: o.x, y: o.y};
}

export function hitTestObject(o, wx, wy) {
  if (!o) return false;
  if (LINE_TOOLS.has(o.type)) {
    if (o.x1 == null || o.x2 == null) return false;
    const dx = o.x2 - o.x1;
    const dy = o.y2 - o.y1;
    const len2 = dx * dx + dy * dy || 1;
    const t = Math.max(0, Math.min(1, ((wx - o.x1) * dx + (wy - o.y1) * dy) / len2));
    const px = o.x1 + t * dx;
    const py = o.y1 + t * dy;
    return Math.hypot(wx - px, wy - py) <= (o.type === 'wall' ? 12 : 14);
  }
  if (o.type === 'room') {
    return wx >= o.x && wx <= o.x + o.w && wy >= o.y && wy <= o.y + o.h;
  }
  const hw = (o.w || 44) / 2;
  const hh = (o.h || 44) / 2;
  return wx >= o.x - hw && wx <= o.x + hw && wy >= o.y - hh && wy <= o.y + hh;
}

export const SYMBOL_GROUPS = [...new Set(KROKI_SYMBOLS.map((s) => s.group))];
