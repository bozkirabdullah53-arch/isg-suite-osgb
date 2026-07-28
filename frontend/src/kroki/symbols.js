/** İSG acil durum kroki sembol kataloğu (V2’den taşındı / genişletildi). */

export const KROKI_SYMBOLS = [
  {type: 'exit', label: 'Acil Çıkış', group: 'Tahliye', color: '#15803d', emoji: '🚪'},
  {type: 'stairs', label: 'Acil Merdiven', group: 'Tahliye', color: '#2563eb', emoji: '🪜'},
  {type: 'assembly', label: 'Toplanma Alanı', group: 'Tahliye', color: '#b45309', emoji: '🚩'},
  {type: 'youarehere', label: 'Siz Buradasınız', group: 'Tahliye', color: '#2563eb', emoji: '📍'},
  {type: 'route', label: 'Tahliye Oku', group: 'Tahliye', color: '#16a34a', emoji: '➡️'},
  {type: 'extinguisher', label: 'Yangın Söndürücü', group: 'Yangın', color: '#b91c1c', emoji: '🧯'},
  {type: 'hose', label: 'Yangın Dolabı', group: 'Yangın', color: '#dc2626', emoji: '🧰'},
  {type: 'alarm', label: 'Yangın Alarmı', group: 'Yangın', color: '#dc2626', emoji: '🔔'},
  {type: 'firstaid', label: 'İlk Yardım', group: 'Sağlık', color: '#15803d', emoji: '➕'},
  {type: 'aed', label: 'AED', group: 'Sağlık', color: '#16a34a', emoji: '❤️'},
  {type: 'electric', label: 'Elektrik Kesme', group: 'Tesisat', color: '#f59e0b', emoji: '⚡'},
  {type: 'north', label: 'Kuzey', group: 'Diğer', color: '#0f172a', emoji: '⬆'},
  {type: 'text', label: 'Metin', group: 'Diğer', color: '#0f172a', emoji: 'T'},
];

export const SYMBOL_BY_TYPE = Object.fromEntries(KROKI_SYMBOLS.map((s) => [s.type, s]));

export function emptyScene() {
  return {version: 1, objects: [], paths: []};
}

export function parseScene(raw) {
  if (!raw) return emptyScene();
  try {
    const data = typeof raw === 'string' ? JSON.parse(raw) : raw;
    if (!data || typeof data !== 'object') return emptyScene();
    return {
      version: data.version || 1,
      objects: Array.isArray(data.objects) ? data.objects : [],
      paths: Array.isArray(data.paths) ? data.paths : [],
    };
  } catch {
    return emptyScene();
  }
}

export function newObjectId() {
  return `o_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
}

export function createSymbolObject(type, x, y) {
  const meta = SYMBOL_BY_TYPE[type] || {label: type, color: '#334155'};
  const base = {
    id: newObjectId(),
    type,
    x: Math.round(x),
    y: Math.round(y),
    rotation: 0,
    label: meta.label,
    w: 44,
    h: 44,
  };
  if (type === 'text') {
    base.w = 120;
    base.h = 28;
    base.label = 'Etiket';
  }
  if (type === 'route') {
    base.w = 56;
    base.h = 28;
    base.rotation = 0;
  }
  if (type === 'assembly') {
    base.w = 64;
    base.h = 64;
  }
  return base;
}

export const SYMBOL_GROUPS = [...new Set(KROKI_SYMBOLS.map((s) => s.group))];
