import React from 'react';
import {EXTINGUISHER_SUBTYPES, SYMBOL_BY_TYPE} from './symbols';

/** ISO 7010 tarzı (yeşil/kırmızı kare + beyaz piktogram) — operasyonel uyumluluk için sade geometri. */

function SignPlate({bg, size, children, selected}) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden>
      <rect
        x="1" y="1" width="46" height="46" rx="3"
        fill={bg}
        stroke={selected ? '#fbbf24' : 'rgba(255,255,255,0.35)'}
        strokeWidth={selected ? 3 : 1}
      />
      {children}
    </svg>
  );
}

function pictogram(type, subtype) {
  const white = '#fff';
  switch (type) {
    case 'exit':
    case 'door_exit':
      return (
        <g fill="none" stroke={white} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10 34 V14 h10 a8 8 0 0 1 0 20 H10" />
          <path d="M28 24 h12" />
          <path d="M36 18 l6 6 -6 6" />
          <circle cx="22" cy="18" r="1.6" fill={white} stroke="none" />
        </g>
      );
    case 'stairs':
      return (
        <g fill="none" stroke={white} strokeWidth="2.4" strokeLinecap="square">
          <path d="M10 34 h8 v-6 h8 v-6 h8 v-6 h4" />
        </g>
      );
    case 'assembly':
      return (
        <g fill={white}>
          <circle cx="18" cy="16" r="3.2" />
          <circle cx="30" cy="16" r="3.2" />
          <path d="M12 34 c0-6 4-10 10-10 s10 4 10 10" />
          <path d="M24 34 c0-5 3-8 8-8 3 0 5 1.5 6.5 4" opacity="0.85" />
        </g>
      );
    case 'youarehere':
      return (
        <g>
          <circle cx="24" cy="24" r="10" fill="#1d4ed8" stroke="#fff" strokeWidth="3" />
          <circle cx="24" cy="24" r="4" fill="#fff" />
        </g>
      );
    case 'route':
      return (
        <g fill="none" stroke={white} strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round">
          <path d="M6 24 h28" />
          <path d="M26 14 l14 10 -14 10" />
          <path d="M6 24 h8" opacity="0.55" />
        </g>
      );
    case 'extinguisher': {
      const code = (EXTINGUISHER_SUBTYPES.find((s) => s.id === subtype) || EXTINGUISHER_SUBTYPES[0]).code;
      return (
        <g>
          <g fill="none" stroke={white} strokeWidth="2.2" strokeLinecap="round">
            <rect x="16" y="16" width="12" height="18" rx="2" />
            <path d="M22 16 V11 h6" />
            <path d="M28 12 h4 l2 3" />
            <path d="M18 22 h8" />
          </g>
          <text x="24" y="42" textAnchor="middle" fill={white} fontSize="7" fontWeight="800" fontFamily="system-ui,sans-serif">
            {code.length > 4 ? code.slice(0, 4) : code}
          </text>
        </g>
      );
    }
    case 'hose':
      return (
        <g fill="none" stroke={white} strokeWidth="2.2" strokeLinecap="round">
          <rect x="12" y="12" width="24" height="24" rx="2" />
          <path d="M18 20 h12 v8 H18 z" />
          <path d="M28 28 q8 2 6 10" />
        </g>
      );
    case 'alarm':
      return (
        <g fill="none" stroke={white} strokeWidth="2.2" strokeLinecap="round">
          <path d="M16 22 a8 8 0 0 1 16 0 v6 H16 z" />
          <path d="M14 28 h20" />
          <path d="M24 14 v4" />
          <path d="M20 34 h8" />
        </g>
      );
    case 'firstaid':
      /* Türkiye: Kızılay hilali (haç değil) — yeşil zemin üzeri beyaz hilal */
      return (
        <g fill={white}>
          <path d="M30.5 9.5a15.2 15.2 0 1 0 0 29 12.2 12.2 0 1 1 0-29z" />
        </g>
      );
    case 'aed':
      return (
        <g fill={white}>
          <path d="M14 28 l6-14 h5 l-3 8 h6 l-8 14 h-5 l3-8 h-6 z" />
        </g>
      );
    case 'electric':
      return (
        <g fill="#fff">
          <path d="M26 10 L16 26 h8 l-2 12 12-18 h-8 z" />
        </g>
      );
    case 'north':
      return (
        <g fill="#0f172a" stroke="#0f172a">
          <path d="M24 10 l8 22 h-5 l-3-8 -3 8 h-5 z" fill="#0f172a" />
          <text x="24" y="44" textAnchor="middle" fontSize="8" fontWeight="800">K</text>
        </g>
      );
    case 'door':
      return (
        <g fill="none" stroke="#475569" strokeWidth="2.2">
          <rect x="14" y="10" width="20" height="28" rx="1" />
          <path d="M34 38 A14 14 0 0 0 20 14" />
          <circle cx="30" cy="24" r="1.5" fill="#475569" />
        </g>
      );
    default:
      return (
        <text x="24" y="28" textAnchor="middle" fill={white} fontSize="11" fontWeight="800">
          {SYMBOL_BY_TYPE[type]?.short || '?'}
        </text>
      );
  }
}

export function SymbolGlyph({type, size = 28, subtype, selected = false}) {
  const meta = SYMBOL_BY_TYPE[type] || {color: '#64748b', signClass: 'info', short: '•'};
  if (type === 'room' || type === 'wall' || type === 'text') {
    return (
      <span
        style={{
          width: size, height: size, borderRadius: 6, display: 'inline-grid', placeItems: 'center',
          background: type === 'wall' ? '#0f172a' : '#e2e8f0',
          color: type === 'wall' ? '#fff' : '#334155',
          fontSize: size * 0.32, fontWeight: 800, border: selected ? '2px solid #fbbf24' : '1px solid #cbd5e1',
        }}
        title={meta.label}
      >
        {meta.short || '•'}
      </span>
    );
  }
  const bg = meta.signClass === 'fire' ? '#b91c1c'
    : meta.signClass === 'safe' ? '#15803d'
      : meta.signClass === 'info' ? (type === 'youarehere' ? '#dbeafe' : meta.color)
        : meta.color;
  return (
    <span style={{display: 'inline-flex', lineHeight: 0}} title={`${meta.label}${meta.iso ? ` · ${meta.iso}` : ''}`}>
      <SignPlate bg={bg} size={size} selected={selected}>
        {pictogram(type, subtype)}
      </SignPlate>
    </span>
  );
}

/** SVG sahnede kullanılan tam boyutlu işaret. */
export function SceneSymbol({o, selected}) {
  const meta = SYMBOL_BY_TYPE[o.type] || {color: '#64748b', label: o.type, signClass: 'info'};
  const rw = o.w || 48;
  const rh = o.h || 48;

  if (o.type === 'wall') {
    return (
      <g>
        <line
          x1={o.x1} y1={o.y1} x2={o.x2} y2={o.y2}
          stroke={selected ? '#fbbf24' : (o.color || '#0f172a')}
          strokeWidth={o.stroke || 10}
          strokeLinecap="square"
        />
      </g>
    );
  }
  if (o.type === 'room') {
    return (
      <g>
        <rect
          x={o.x} y={o.y} width={o.w} height={o.h} rx={2}
          fill="rgba(248,250,252,0.72)"
          stroke={selected ? '#fbbf24' : (o.color || '#334155')}
          strokeWidth={selected ? 3 : 2}
        />
        <text
          x={o.x + o.w / 2}
          y={o.y + o.h / 2}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={Math.min(20, Math.max(11, Math.min(o.w, o.h) / 6))}
          fontWeight="700"
          fill="#1e293b"
        >
          {o.label || 'Mahal'}
        </text>
      </g>
    );
  }
  if (o.type === 'text') {
    return (
      <g transform={`translate(${o.x},${o.y}) rotate(${o.rotation || 0})`}>
        <text
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={16}
          fontWeight="650"
          fill="#0f172a"
          stroke={selected ? '#fbbf24' : 'none'}
          strokeWidth={selected ? 0.5 : 0}
        >
          {o.label || 'Metin'}
        </text>
      </g>
    );
  }

  const bg = meta.signClass === 'fire' ? '#b91c1c'
    : meta.signClass === 'safe' ? '#15803d'
      : meta.signClass === 'info' ? (o.type === 'youarehere' ? '#dbeafe' : meta.color)
        : meta.color;

  return (
    <g transform={`translate(${o.x},${o.y}) rotate(${o.rotation || 0})`}>
      <g transform={`translate(${-rw / 2},${-rh / 2})`}>
        <svg width={rw} height={rh} viewBox="0 0 48 48">
          <rect
            x="1" y="1" width="46" height="46" rx="3"
            fill={bg}
            stroke={selected ? '#fbbf24' : 'rgba(255,255,255,0.4)'}
            strokeWidth={selected ? 3 : 1}
          />
          {pictogram(o.type, o.subtype)}
        </svg>
      </g>
      <text y={rh / 2 + 14} textAnchor="middle" fontSize={11} fontWeight="650" fill="#0f172a">
        {o.label || meta.label}
      </text>
    </g>
  );
}
