import React from 'react';
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { FPS, INK, PAPER, RED, SANS, clamp } from './Cards';

/**
 * 一屏（panel）：底板固定不动，元素逐句弹入。
 * 这是「凯哥式」衔接的关键——不换画面，只往画面上加东西。
 */

export type PanelEl = {
  at: number;
  kind: 'bubble' | 'label' | 'num' | 'icon' | 'arrow' | 'dot' | 'box';
  text?: string;
  name?: string;
  x?: number; // 百分比，元素中心
  y?: number;
  w?: number; // 宽度 px（bubble/label/box）
  size?: number; // 尺寸 px（icon/num/dot）
  color?: string;
  dark?: boolean;
};

export type PanelT = {
  id: string;
  bg: string;
  start: number;
  end: number;
  count: number;
  elements: PanelEl[];
};

const easeOut = (p: number) => 1 - Math.pow(1 - p, 3);

const Icon: React.FC<{ name?: string; size: number; color: string }> = ({ name = 'check', size, color }) => {
  const s = size;
  const box = { width: s, height: s, viewBox: '0 0 100 100', display: 'block' } as const;
  switch (name) {
    case 'cross':
      return (
        <svg {...box}>
          <path d="M24 24 L76 76 M76 24 L24 76" stroke={color} strokeWidth={14} strokeLinecap="round" fill="none" />
        </svg>
      );
    case 'house':
      return (
        <svg {...box}>
          <path d="M50 14 L88 44 H79 V86 H21 V44 H12 Z" fill={color} />
          <rect x="42" y="60" width="16" height="26" fill={PAPER} />
        </svg>
      );
    case 'family':
      return (
        <svg {...box}>
          <circle cx="32" cy="30" r="11" fill={color} />
          <rect x="22" y="45" width="20" height="38" rx="7" fill={color} />
          <circle cx="70" cy="36" r="9" fill={color} />
          <rect x="61" y="49" width="18" height="34" rx="6" fill={color} />
        </svg>
      );
    case 'clock':
      return (
        <svg {...box}>
          <circle cx="50" cy="50" r="38" stroke={color} strokeWidth={9} fill="none" />
          <path d="M50 26 V52 H72" stroke={color} strokeWidth={9} strokeLinecap="round" fill="none" />
        </svg>
      );
    case 'phone':
      return (
        <svg {...box}>
          <rect x="28" y="10" width="44" height="80" rx="9" stroke={color} strokeWidth={8} fill="none" />
          <rect x="38" y="26" width="24" height="4" rx="2" fill={color} />
          <rect x="38" y="36" width="18" height="4" rx="2" fill={color} opacity={0.6} />
        </svg>
      );
    case 'money':
      return (
        <svg {...box}>
          <circle cx="50" cy="50" r="37" stroke={color} strokeWidth={9} fill="none" />
          <path d="M50 30 V70 M40 40 H58 A8 8 0 0 1 58 56 H40" stroke={color} strokeWidth={8} strokeLinecap="round" fill="none" />
        </svg>
      );
    case 'up':
      return (
        <svg {...box}>
          <path d="M50 88 V16 M26 40 L50 14 L74 40" stroke={color} strokeWidth={12} strokeLinecap="round" strokeLinejoin="round" fill="none" />
        </svg>
      );
    case 'down':
      return (
        <svg {...box}>
          <path d="M50 12 V84 M26 60 L50 86 L74 60" stroke={color} strokeWidth={12} strokeLinecap="round" strokeLinejoin="round" fill="none" />
        </svg>
      );
    case 'arrow':
      return (
        <svg {...box}>
          <path d="M14 50 H82 M60 26 L86 50 L60 74" stroke={color} strokeWidth={11} strokeLinecap="round" strokeLinejoin="round" fill="none" />
        </svg>
      );
    default:
      return (
        <svg {...box}>
          <path d="M18 52 L40 74 L84 26" stroke={color} strokeWidth={13} strokeLinecap="round" strokeLinejoin="round" fill="none" />
        </svg>
      );
  }
};

const El: React.FC<{ el: PanelEl; frame: number }> = ({ el, frame }) => {
  const atF = Math.round((el.at ?? 0) * FPS);
  const p = interpolate(frame - atF, [0, 8], [0, 1], clamp);
  if (frame < atF) return null;
  const e = easeOut(p);
  const x = el.x ?? 50;
  const y = el.y ?? 50;
  const color = el.color ?? INK;
  const base: React.CSSProperties = {
    position: 'absolute',
    left: `${Math.min(88, Math.max(12, x))}%`,
    top: `${Math.min(84, Math.max(12, y))}%`,
    transform: `translate(-50%, -50%) scale(${1.15 - 0.15 * e})`,
    opacity: e,
    maxWidth: '62%',
  };

  switch (el.kind) {
    case 'bubble':
      return (
        <div style={{ ...base, width: el.w ?? 520, boxSizing: 'border-box' }}>
          <div
            style={{
              background: '#fff',
              border: `3px solid ${INK}`,
              borderRadius: 20,
              padding: '18px 24px',
              fontFamily: SANS,
              fontSize: el.size ?? 32,
              fontWeight: 700,
              color: INK,
              lineHeight: 1.35,
              boxShadow: '0 10px 26px rgba(0,0,0,0.18)',
              textAlign: 'center',
            }}
          >
            {el.text}
          </div>
          <div
            style={{
              width: 0,
              height: 0,
              margin: '0 auto',
              borderLeft: '14px solid transparent',
              borderRight: '14px solid transparent',
              borderTop: `16px solid ${INK}`,
            }}
          />
        </div>
      );
    case 'label':
      return (
        <div
          style={{
            ...base,
            background: el.color ?? RED,
            color: '#fff',
            fontFamily: SANS,
            fontSize: el.size ?? 40,
            fontWeight: 800,
            letterSpacing: '0.02em',
            padding: '10px 22px',
            borderRadius: 8,
            whiteSpace: 'nowrap',
          }}
        >
          {el.text}
        </div>
      );
    case 'num':
      return (
        <div
          style={{
            ...base,
            fontFamily: SANS,
            fontSize: el.size ?? 190,
            fontWeight: 900,
            color: el.color ?? RED,
            lineHeight: 0.9,
            letterSpacing: '-0.03em',
          }}
        >
          {el.text}
        </div>
      );
    case 'icon':
      return (
        <div style={base}>
          <Icon name={el.name} size={el.size ?? 96} color={color} />
        </div>
      );
    case 'arrow':
      return (
        <div style={base}>
          <svg width={el.size ?? 220} height={(el.size ?? 220) * 0.5} viewBox="0 0 100 50">
            <path d="M6 25 H86 M68 8 L92 25 L68 42" stroke={color} strokeWidth={9} strokeLinecap="round" strokeLinejoin="round" fill="none" />
          </svg>
        </div>
      );
    case 'dot':
      return (
        <div style={{ ...base, display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ width: el.size ?? 18, height: el.size ?? 18, borderRadius: '50%', background: el.color ?? RED, display: 'block' }} />
          {el.text ? (
            <span style={{ fontFamily: SANS, fontSize: 30, fontWeight: 700, color: '#fff', textShadow: '0 2px 8px rgba(0,0,0,0.9)' }}>
              {el.text}
            </span>
          ) : null}
        </div>
      );
    case 'box':
      return (
        <div style={{ ...base, width: el.w ?? 420, height: el.size ?? 220, border: `5px dashed ${el.color ?? RED}`, borderRadius: 14 }} />
      );
    default:
      return null;
  }
};

export const PanelLayer: React.FC<{ panel: PanelT }> = ({ panel }) => {
  const frame = useCurrentFrame();
  const dur = Math.max(1, Math.round((panel.end - panel.start) * FPS));
  const push = 1 + 0.03 * Math.min(1, frame / dur);
  return (
    <AbsoluteFill style={{ backgroundColor: PAPER, overflow: 'hidden' }}>
      <Img
        src={staticFile(panel.bg)}
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform: `scale(${push})`,
          transformOrigin: '50% 46%',
        }}
      />
      {panel.elements.map((el, i) => (
        <El key={i} el={el} frame={frame} />
      ))}
    </AbsoluteFill>
  );
};
