// 卡通视觉体系：扁平矢量讲师 + 场景卡（纯 SVG，零素材、风格绝对统一）
import React from 'react';
import { AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';

const PAPER = '#f6f2ec';
const INK = '#17140f';
const RED = '#c8402f';
const NAVY = '#2b3a53';
const SANS = '"PingFang SC","Microsoft YaHei","Noto Sans SC",sans-serif';

export type Pose = 'stand' | 'point' | 'shrug' | 'cheer' | 'no';

/** 扁平讲师角色：头身比 1:3，圆头 + 深色短发 + 西装领带 */
export const Teacher: React.FC<{ pose?: Pose; x?: number; y?: number; s?: number; frame: number }> = ({
  pose = 'stand',
  x = 640,
  y = 470,
  s = 1,
  frame,
}) => {
  const bob = Math.sin(frame / 12) * 2.2;
  // 教鞭挥动
  const whip = Math.sin(frame / 9) * 8;
  const armL =
    pose === 'point' ? `M-70,-120 l-52,${-6 + whip} l0,0` : pose === 'shrug' ? 'M-70,-120 l-46,-46' : 'M-70,-120 l-14,96';
  const armR =
    pose === 'point' ? 'M70,-120 l54,-30' : pose === 'shrug' ? 'M70,-120 l46,-46' : pose === 'cheer' ? 'M70,-120 l44,-72' : 'M70,-120 l14,96';

  return (
    <g transform={`translate(${x},${y + bob}) scale(${s})`}>
      {/* 影子 */}
      <ellipse cx={0} cy={168} rx={92} ry={12} fill="rgba(23,20,15,0.10)" />
      {/* 身体 —— 西装 */}
      <path d="M-76,-150 q76,-34 152,0 l14,160 q-90,16 -180,0 z" fill={NAVY} />
      {/* 白衬衫领口 */}
      <path d="M-30,-152 l30,46 l30,-46 q-30,-14 -60,0 z" fill="#fdfdfb" />
      {/* 领带 */}
      <path d="M-9,-106 l9,-12 l9,12 l-5,64 l-8,0 z" fill={RED} />
      {/* 手臂 */}
      <path d={armL} stroke={NAVY} strokeWidth={26} strokeLinecap="round" fill="none" />
      <path d={armR} stroke={NAVY} strokeWidth={26} strokeLinecap="round" fill="none" />
      {/* 手 */}
      <circle cx={pose === 'point' ? -122 : pose === 'shrug' ? -116 : -84} cy={pose === 'point' ? -126 : pose === 'shrug' ? -166 : -24} r={13} fill="#f2d3b8" />
      <circle cx={pose === 'point' ? 124 : pose === 'shrug' ? 116 : pose === 'cheer' ? 114 : 84} cy={pose === 'point' ? -150 : pose === 'shrug' ? -166 : pose === 'cheer' ? -192 : -24} r={13} fill="#f2d3b8" />
      {/* 教鞭：point 姿势从右手伸出，指向右侧文字 */}
      {pose === 'point' ? (
        <line x1={124} y1={-150} x2={192} y2={-198 + whip} stroke="#8a2f24" strokeWidth={7} strokeLinecap="round" />
      ) : null}
      {/* 脖子 */}
      <rect x={-15} y={-176} width={30} height={30} rx={10} fill="#e8c6aa" />
      {/* 头 */}
      <circle cx={0} cy={-240} r={64} fill="#f2d3b8" />
      {/* 头发：上半圆外壳 + 刘海，下沿停在额头 -254，不遮眼 */}
      <path d="M-64,-240 A64,64 0 0 1 64,-240 Q0,-256 -64,-240 Z" fill="#33241a" />
      <path d="M-42,-262 q20,-8 30,6 q-16,10 -32,4 z" fill="#33241a" />
      {/* 眼睛 */}
      {pose === 'no' ? (
        <>
          <path d="M-31,-244 l15,15 M-16,-244 l-15,15" stroke={INK} strokeWidth={5} strokeLinecap="round" />
          <path d="M15,-244 l15,15 M30,-244 l-15,15" stroke={INK} strokeWidth={5} strokeLinecap="round" />
        </>
      ) : (
        <>
          <circle cx={-22} cy={-240} r={6.5} fill={INK} />
          <circle cx={22} cy={-240} r={6.5} fill={INK} />
        </>
      )}
      {/* 腮红 */}
      <circle cx={-41} cy={-218} r={9} fill="rgba(200,64,47,0.26)" />
      <circle cx={41} cy={-218} r={9} fill="rgba(200,64,47,0.26)" />
      {/* 嘴 */}
      {pose === 'shrug' ? (
        <path d="M-14,-206 q14,-8 28,0" stroke={INK} strokeWidth={4.5} fill="none" strokeLinecap="round" />
      ) : pose === 'no' ? (
        <path d="M-14,-210 q14,-9 28,0" stroke={INK} strokeWidth={4.5} fill="none" strokeLinecap="round" />
      ) : pose === 'cheer' ? (
        <path d="M-14,-208 q14,16 28,0 z" fill="#c2504a" stroke={INK} strokeWidth={3} strokeLinejoin="round" />
      ) : (
        <path d="M-13,-206 q13,11 26,0" stroke={INK} strokeWidth={4.5} fill="none" strokeLinecap="round" />
      )}
    </g>
  );
};

/** 讲台场景：讲师 + 讲台 + 标题 */
export const PodiumScene: React.FC<{ text: string; sub?: string; pose?: Pose; accent?: string }> = ({
  text,
  sub,
  pose = 'point',
  accent,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame, fps, config: { damping: 16, mass: 0.7 } });
  return (
    <AbsoluteFill style={{ backgroundColor: PAPER, fontFamily: SANS }}>
      {/* 背景色块 */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 300, background: '#e9e2d6' }} />
      <div style={{ position: 'absolute', top: 300, left: 0, right: 0, height: 4, background: 'rgba(23,20,15,0.10)' }} />
      <svg width="100%" height="100%" viewBox="0 0 1280 720" style={{ position: 'absolute', inset: 0 }}>
        <Teacher pose={pose} x={350} y={470} s={1.05} frame={frame} />
        {/* 讲台 */}
        <path d="M188,470 h324 l-14,196 h-296 z" fill="#b98b5e" />
        <path d="M188,470 h324 l-6,26 h-312 z" fill="#a1754c" />
        <text x={350} y={566} textAnchor="middle" fontSize={22} fill="rgba(255,255,255,0.55)" letterSpacing={6}>LESSON 01</text>
      </svg>
      {accent ? (
        <svg width="100%" height="100%" viewBox="0 0 1280 720" style={{ position: 'absolute', inset: 0 }}>
          <rect x={556} y={252} width={11} height={72} fill={RED} />
        </svg>
      ) : null}
      <div style={{ position: 'absolute', left: 622, top: 244, right: 84 }}>
        <div style={{ fontSize: 60, lineHeight: 1.22, fontWeight: 900, color: INK, letterSpacing: -0.5 }}>
          {text.split('|').map((t, i) =>
            i % 2 === 1 ? (
              <span key={i} style={{ color: RED }}>{t}</span>
            ) : (
              <span key={i}>{t}</span>
            )
          )}
        </div>
        {sub ? <div style={{ marginTop: 18, fontSize: 28, color: 'rgba(23,20,15,0.55)', fontWeight: 600 }}>{sub}</div> : null}
      </div>
    </AbsoluteFill>
  );
};

/** 黑板场景：绿板 + 粉笔字 + 讲师侧身 */
export const BlackboardScene: React.FC<{ lines: string[]; no?: boolean; sub?: string }> = ({ lines, no, sub }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [4, 26], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ backgroundColor: '#dfd7c8', fontFamily: SANS }}>
      <div style={{ position: 'absolute', left: 76, top: 74, width: 1128, height: 512, background: '#1f3d33', borderRadius: 8, boxShadow: '0 18px 40px rgba(0,0,0,0.22)' }} />
      <div style={{ position: 'absolute', left: 76, top: 74, width: 1128, height: 512, borderRadius: 8, border: '14px solid #8a6a45' }} />
      <svg width="100%" height="100%" viewBox="0 0 1280 720" style={{ position: 'absolute', inset: 0 }}>
        <Teacher pose="no" x={1052} y={620} s={0.86} frame={frame} />
      </svg>
      <div style={{ position: 'absolute', left: 140, top: 150, width: 640 }}>
        {lines.map((l, i) => (
          <div key={i} style={{ fontSize: i === 0 ? 72 : 52, fontWeight: 900, color: i === 0 ? '#fff' : 'rgba(255,255,255,0.82)', lineHeight: 1.3, opacity: p, letterSpacing: 1 }}>
            {l}
          </div>
        ))}
        {sub ? <div style={{ marginTop: 24, fontSize: 28, color: 'rgba(255,255,255,0.5)', fontWeight: 600 }}>{sub}</div> : null}
      </div>
      {no ? (
        <svg width="100%" height="100%" viewBox="0 0 1280 720" style={{ position: 'absolute', inset: 0 }}>
          <g opacity={p} transform="translate(900,330) rotate(-12)">
            <circle r={92} fill="none" stroke={RED} strokeWidth={13} />
            <line x1={-66} y1={66} x2={66} y2={-66} stroke={RED} strokeWidth={13} strokeLinecap="round" />
          </g>
        </svg>
      ) : null}
    </AbsoluteFill>
  );
};

/** 对比卡：左卡通（错）右实拍（对） */
export const CartoonVs: React.FC<{ src: string; text: string; left: string; right: string; sub?: string }> = ({
  src,
  text,
  left,
  right,
  sub,
}) => {
  const frame = useCurrentFrame();
  const p = spring({ frame, fps: 30, config: { damping: 18, mass: 0.6 } });
  return (
    <AbsoluteFill style={{ backgroundColor: PAPER, fontFamily: SANS }}>
      <div style={{ position: 'absolute', left: 40, top: 44, width: 600, height: 402, background: '#eee7db', borderRadius: 14, overflow: 'hidden' }}>
        <svg width="100%" height="100%" viewBox="0 0 600 402" style={{ position: 'absolute' }}>
          <Teacher pose="no" x={300} y={352} s={0.84} frame={frame} />
        </svg>
        <div style={{ position: 'absolute', left: 20, top: 16, background: 'rgba(23,20,15,0.72)', color: '#fff', fontSize: 22, fontWeight: 800, padding: '6px 14px', borderRadius: 6 }}>{left}</div>
      </div>
      <div style={{ position: 'absolute', left: 660, top: 44, width: 580, height: 402, borderRadius: 14, overflow: 'hidden', transform: `scale(${0.96 + 0.04 * p})` }}>
        <Img src={staticFile(src)} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        <div style={{ position: 'absolute', left: 20, top: 16, background: RED, color: '#fff', fontSize: 22, fontWeight: 800, padding: '6px 14px', borderRadius: 6 }}>{right}</div>
      </div>
      <div style={{ position: 'absolute', left: 60, right: 60, bottom: 110 }}>
        <div style={{ fontSize: 68, fontWeight: 900, color: INK, lineHeight: 1.16 }}>
          {text.split('|').map((t, i) => (i % 2 === 1 ? <span key={i} style={{ color: RED }}>{t}</span> : <span key={i}>{t}</span>))}
        </div>
        {sub ? <div style={{ marginTop: 10, fontSize: 26, color: 'rgba(23,20,15,0.52)', fontWeight: 600 }}>{sub}</div> : null}
      </div>
    </AbsoluteFill>
  );
};


