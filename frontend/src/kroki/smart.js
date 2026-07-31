/** v2.2 akıllı tahliye asistanı + şablon + doğrulama — Suite entegrasyonu. */

import {createSymbolObject, newObjectId, objectCenter, SYMBOL_BY_TYPE} from './symbols';

function dist(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function nearest(target, candidates) {
  return candidates.reduce((best, item) => {
    const d = dist(target, objectCenter(item));
    return !best || d < best.d ? {item, d} : best;
  }, null);
}

export function buildOfficeTemplate() {
  const objs = [];
  const add = (type, extras) => {
    if (type === 'route') {
      objs.push({
        id: newObjectId(),
        type: 'route',
        x1: extras.x1, y1: extras.y1, x2: extras.x2, y2: extras.y2,
        stroke: 8, label: 'Kaçış Yönü', color: '#15803d',
      });
      return;
    }
    if (type === 'room') {
      objs.push(createSymbolObject('room', extras.x, extras.y, {w: extras.w, h: extras.h, label: extras.label}));
      return;
    }
    const o = createSymbolObject(type, extras.x, extras.y, extras);
    if (extras.label) o.label = extras.label;
    objs.push(o);
  };
  add('room', {x: 170, y: 150, w: 560, h: 330, label: 'Ofis Alanı'});
  add('room', {x: 730, y: 150, w: 330, h: 330, label: 'Toplantı Odası'});
  add('door', {x: 730, y: 315});
  add('exit', {x: 170, y: 315});
  add('youarehere', {x: 900, y: 400});
  add('extinguisher', {x: 230, y: 210, subtype: 'abc'});
  add('firstaid', {x: 980, y: 210});
  add('route', {x1: 900, y1: 400, x2: 600, y2: 315});
  add('route', {x1: 600, y1: 315, x2: 190, y2: 315});
  add('north', {x: 1450, y: 110});
  add('assembly', {x: 200, y: 560});
  return objs;
}

export function buildWorkshopTemplate() {
  const objs = [];
  const add = (type, extras) => {
    if (type === 'route') {
      objs.push({
        id: newObjectId(),
        type: 'route',
        x1: extras.x1, y1: extras.y1, x2: extras.x2, y2: extras.y2,
        stroke: 8, label: 'Kaçış Yönü', color: '#15803d',
      });
      return;
    }
    if (type === 'room') {
      objs.push(createSymbolObject('room', extras.x, extras.y, {w: extras.w, h: extras.h, label: extras.label}));
      return;
    }
    const o = createSymbolObject(type, extras.x, extras.y, extras);
    if (extras.label) o.label = extras.label;
    objs.push(o);
  };
  add('room', {x: 120, y: 120, w: 700, h: 420, label: 'Üretim / Atölye'});
  add('room', {x: 840, y: 120, w: 360, h: 200, label: 'Depo'});
  add('room', {x: 840, y: 340, w: 360, h: 200, label: 'İdare'});
  add('door', {x: 840, y: 330});
  add('exit', {x: 140, y: 330, label: 'ACİL ÇIKIŞ'});
  add('exit', {x: 780, y: 520, label: 'ACİL ÇIKIŞ'});
  add('youarehere', {x: 480, y: 340});
  add('extinguisher', {x: 200, y: 180, subtype: 'abc'});
  add('extinguisher', {x: 700, y: 180, subtype: 'co2'});
  add('hose', {x: 420, y: 160});
  add('alarm', {x: 300, y: 160});
  add('firstaid', {x: 980, y: 400});
  add('electric', {x: 200, y: 480});
  add('route', {x1: 480, y1: 340, x2: 200, y2: 330});
  add('route', {x1: 480, y1: 340, x2: 760, y2: 500});
  add('north', {x: 1450, y: 100});
  add('assembly', {x: 200, y: 620});
  return objs;
}

export function runValidation(objects, meta = {}) {
  const count = (t) => objects.filter((o) => o.type === t).length;
  const checks = [
    {ok: count('exit') + count('door_exit') > 0, pass: 'En az bir acil çıkış tanımlı.', fail: 'Acil çıkış yok.', w: 20},
    {ok: count('route') > 0, pass: 'Kaçış yönü gösterilmiş.', fail: 'Kaçış oku eklenmemiş.', w: 15},
    {ok: count('extinguisher') > 0, pass: 'Yangın söndürücü var.', fail: 'Yangın söndürücü yok.', w: 15},
    {ok: count('firstaid') > 0, pass: 'İlk yardım noktası var.', fail: 'İlk yardım noktası yok.', w: 10},
    {ok: count('assembly') > 0, pass: 'Toplanma alanı var.', fail: 'Toplanma alanı yok.', w: 15},
    {ok: count('youarehere') > 0, pass: '«Siz buradasınız» işareti var.', fail: '«Siz buradasınız» yok.', w: 10},
    {ok: count('wall') + count('room') > 0 || meta.hasBackground, pass: 'Plan geometrisi veya arka plan var.', fail: 'Duvar/oda veya plan görseli yok.', w: 10},
    {ok: count('north') > 0, pass: 'Kuzey yönü belirtilmiş.', fail: 'Kuzey oku eklenmemiş.', w: 5, soft: true},
    {ok: count('youarehere') <= 1, pass: 'Tek «Siz buradasınız» noktası.', fail: 'Birden fazla «Siz buradasınız» var.', w: 5, soft: true},
  ];
  let score = 0;
  let max = 0;
  const items = checks.map((c) => {
    max += c.w;
    if (c.ok) score += c.w;
    return {...c, status: c.ok ? 'ok' : (c.soft ? 'warn' : 'error')};
  });
  const pct = max ? Math.round((score / max) * 100) : 0;
  return {items, pct, score, max};
}

/**
 * Kural tabanlı akıllı yerleştirme (v2.2).
 * Önceki aiSuggested nesneleri temizler; yeni öneriler ekler.
 */
export function runSmartPlan(objects, opts = {}) {
  const {
    routesOn = true,
    equipmentOn = true,
    legendOn = true,
    occupancy = 1,
    hazard = 'normal',
    canvasW = 1600,
    canvasH = 1000,
  } = opts;

  const exits = objects.filter((o) => o.type === 'exit' || o.type === 'door_exit');
  if (!exits.length) {
    return {
      objects,
      error: 'En az bir acil çıkış işaretleyin. Akıllı asistan çıkış olmadan çalışmaz.',
      summary: [],
      confidence: 'Eksik veri',
    };
  }

  let next = objects.filter((o) => !o.aiSuggested);
  const summary = [];
  let routeCount = 0;
  let equipmentCount = 0;

  const smartAdd = (partial) => {
    const base = partial.type === 'route' || partial.type === 'wall' || partial.type === 'measure'
      ? {
          id: newObjectId(),
          color: SYMBOL_BY_TYPE[partial.type]?.color || '#15803d',
          stroke: partial.stroke || 8,
          label: partial.label || '',
          note: 'Akıllı asistan önerisi — uzman doğrulaması gerekli',
          aiSuggested: true,
          ...partial,
        }
      : {
          ...createSymbolObject(partial.type, partial.x, partial.y, partial),
          note: 'Akıllı asistan önerisi — uzman doğrulaması gerekli',
          aiSuggested: true,
          label: partial.label || createSymbolObject(partial.type, partial.x, partial.y, partial).label,
        };
    next = [...next, base];
  };

  const doors = next.filter((o) => o.type === 'door');
  const rooms = next.filter((o) => o.type === 'room');
  const starts = next.filter((o) => o.type === 'youarehere');

  if (routesOn) {
    const routeStarts = starts.length ? starts : (doors.length ? doors : rooms);
    routeStarts.forEach((start, index) => {
      const p = objectCenter(start);
      const n = nearest(p, exits);
      if (!n || n.d < 45) return;
      const q = objectCenter(n.item);
      if (n.d > 360) {
        const mid = {x: p.x + (q.x - p.x) * 0.52, y: p.y + (q.y - p.y) * 0.52};
        smartAdd({type: 'route', x1: p.x, y1: p.y, x2: mid.x, y2: mid.y, label: `Otomatik Kaçış ${index + 1}`});
        smartAdd({type: 'route', x1: mid.x, y1: mid.y, x2: q.x, y2: q.y, label: `Otomatik Kaçış ${index + 1}`});
        routeCount += 2;
      } else {
        smartAdd({type: 'route', x1: p.x, y1: p.y, x2: q.x, y2: q.y, label: `Otomatik Kaçış ${index + 1}`});
        routeCount += 1;
      }
    });
  }

  if (equipmentOn) {
    const extinguishers = next.filter((o) => o.type === 'extinguisher');
    exits.forEach((exit, index) => {
      const p = objectCenter(exit);
      const near = extinguishers.some((e) => dist(objectCenter(e), p) < 170);
      if (!near) {
        const side = index % 2 ? -1 : 1;
        smartAdd({
          type: 'extinguisher',
          x: Math.max(55, Math.min(canvasW - 55, p.x + 85 * side)),
          y: Math.max(55, Math.min(canvasH - 55, p.y + 65)),
          subtype: 'abc',
          label: 'Önerilen Söndürücü (ABC)',
        });
        equipmentCount += 1;
      }
    });
    if (!next.some((o) => o.type === 'firstaid')) {
      const anchor = starts[0] ? objectCenter(starts[0]) : objectCenter(exits[0]);
      smartAdd({
        type: 'firstaid',
        x: Math.min(canvasW - 70, anchor.x + 130),
        y: Math.max(70, anchor.y - 100),
        label: 'Önerilen İlk Yardım',
      });
      equipmentCount += 1;
    }
  }

  if (legendOn && !next.some((o) => o.type === 'text' && o.label === 'LEJANT VE TEKNİK NOTLAR')) {
    const lines = [
      'LEJANT VE TEKNİK NOTLAR',
      'Yeşil ok: Kaçış / tahliye yönü',
      'ÇIKIŞ: Acil çıkış',
      'YS: Yangın söndürücü',
      'Hilal: İlk yardım',
      'T: Toplanma alanı',
      '●: Siz buradasınız',
      'Öneriler saha ölçümü ve uzman onayı gerektirir.',
      'Dayanak: 6331 · Acil Durumlar Yön. · TS EN ISO 7010/23601',
    ];
    lines.forEach((line, i) => {
      smartAdd({
        type: 'text',
        x: Math.min(canvasW - 220, 1080),
        y: Math.min(canvasH - 40, 650 + i * 28),
        label: line,
      });
    });
    summary.push(`${lines.length} satırlık lejant eklendi.`);
  }

  summary.unshift(`${routeCount} kaçış oku üretildi.`);
  summary.unshift(`${equipmentCount} ekipman konumu önerildi.`);
  if (!starts.length) summary.push('«Siz buradasınız» yoktu; başlangıç kapı/oda merkezlerinden tahmin edildi.');
  if (occupancy >= 50) summary.push('Yüksek kullanıcı sayısı: çıkış kapasitesi uzman tarafından doğrulanmalı.');
  if (hazard === 'high') summary.push('Yüksek tehlike: özel riskler bu otomatik yerleşimin dışında değerlendirilmeli.');

  const dataSignals = [opts.hasBackground, exits.length, doors.length, rooms.length, starts.length].filter(Boolean).length;
  const confidence = dataSignals >= 4 ? 'Orta-yüksek' : dataSignals >= 2 ? 'Orta' : 'Düşük';

  return {objects: next, summary, confidence, error: null};
}
