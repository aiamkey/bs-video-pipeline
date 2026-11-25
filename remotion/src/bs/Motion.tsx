import React from 'react';
import { AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame } from 'remotion';
import { FPS, INK, PAPER, RED, SANS, clamp } from './Cards';

/**
 * Motion.tsx —— 让画面"自己会动"的卡组。
 * 凯哥那种片子耐看的核心不是字多，而是每一秒都有东西在动：推、拉、扫、点亮、计数。
 * 这些组件全部只用代码动效，不依赖任何外部素材，渲染零成本。
 */

const VIGNETTE = 'radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 38%, rgba(0,0,0,0.42) 100%)';
const BOTTOM_GRAD = 'linear-gradient(0deg, rgba(12,10,8,0.86) 0%, rgba(12,10,8,0.28) 46%, rgba(12,10,8,0.02) 78%)';

const Big_: React.FC<{ children: React.ReactNode; size?: number; color?: string; weight?: number; style?: React.CSSProperties }> = ({
  children,
  size = 76,
  color = '#fff',
  weight = 900,
  style,
}) => (
  <div style={{ fontFamily: SANS, fontSize: size, fontWeight: weight, lineHeight: 1.26, letterSpacing: '-0.015em', color, ...style }}>
    {children}
  </div>
);

const accent = (text: string) =>
  text.split('|').map((seg, i) =>
    i % 2 === 1 ? (
      <span key={i} style={{ color: '#ff5a4d' }}>{seg}</span>
    ) : (
      <span key={i}>{seg}</span>
    ),
  );

/* ── 1. 推拉实拍：全屏图 + 缓推 + 横向漂移 + 呼吸暗角 ───────────────── */
export const PhotoPush: React.FC<{ src: string; text: string; sub?: string; dir?: 'in' | 'out' | 'left' | 'right'; dur?: number }> = ({
  src,
  text,
  sub,
  dir = 'in',
  dur = 150,
}) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [0, dur], [0, 1], { ...clamp, easing: Easing.inOut(Easing.quad) });

  let transform = '';
  if (dir === 'in') transform = `scale(${1.02 + p * 0.2})`;
  else if (dir === 'out') transform = `scale(${1.22 - p * 0.2})`;
  else if (dir === 'left') transform = `scale(1.16) translateX(${4 - p * 8}%)`;
  else transform = `scale(1.16) translateX(${-4 + p * 8}%)`;

  const vign = 0.34 + Math.sin(frame / 26) * 0.05;

  return (
    <AbsoluteFill style={{ backgroundColor: INK, fontFamily: SANS, overflow: 'hidden' }}>
      <AbsoluteFill>
        <Img src={staticFile(src)} style={{ width: '100%', height: '100%', objectFit: 'cover', transform }} />
      </AbsoluteFill>
      <AbsoluteFill style={{ background: BOTTOM_GRAD }} />
      <AbsoluteFill style={{ background: VIGNETTE, opacity: vign + 0.6 }} />
      <div style={{ position: 'absolute', left: 64, right: 64, bottom: 118 }}>
        <Big_ size={78}>{accent(text)}</Big_>
        {sub ? <div style={{ marginTop: 14, fontSize: 28, color: 'rgba(255,255,255,0.7)' }}>{sub}</div> : null}
      </div>
    </AbsoluteFill>
  );
};

/* ── 2. 前后对比：同一张脸，左边是现在的你，右边是 21 天后的你 ───────── */
export const BeforeAfter: React.FC<{ src: string; text: string; left?: string; right?: string; sub?: string }> = ({
  src,
  text,
  left = '现在',
  right = '21 天后',
  sub,
}) => {
  const frame = useCurrentFrame();
  // 分界线左右扫，形成"拉帘"对比
  const sweep = interpolate(frame, [0, 110], [34, 66], { ...clamp, easing: Easing.inOut(Easing.sin) });
  const labelIn = spring({ frame, fps: FPS, config: { damping: 200 } });

  return (
    <AbsoluteFill style={{ backgroundColor: INK, fontFamily: SANS, overflow: 'hidden' }}>
      {/* 左：现在 —— 灰、暗、略压扁（显脸糊/显垮） */}
      <AbsoluteFill style={{ clipPath: `inset(0 ${100 - sweep}% 0 0)` }}>
        <Img
          src={staticFile(src)}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            filter: 'grayscale(0.72) brightness(0.66) contrast(1.08)',
            transform: 'scale(1.06, 0.99)',
          }}
        />
        <AbsoluteFill style={{ background: 'rgba(20,18,16,0.18)' }} />
      </AbsoluteFill>

      {/* 右：21 天后 —— 原色、微亮、挺拔一点 */}
      <AbsoluteFill style={{ clipPath: `inset(0 0 0 ${sweep}%)` }}>
        <Img src={staticFile(src)} style={{ width: '100%', height: '100%', objectFit: 'cover', filter: 'brightness(1.06) saturate(1.05)', transform: 'scale(1.06, 1.01)' }} />
      </AbsoluteFill>

      {/* 分界线 + 把手 */}
      <div style={{ position: 'absolute', top: 0, bottom: 0, left: `${sweep}%`, width: 3, background: '#fff', opacity: 0.9, boxShadow: '0 0 18px rgba(255,255,255,0.55)' }} />
      <div
        style={{
          position: 'absolute',
          top: '46%',
          left: `${sweep}%`,
          transform: 'translate(-50%,-50%)',
          width: 58,
          height: 58,
          borderRadius: 29,
          background: '#fff',
          color: INK,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 22,
          fontWeight: 900,
        }}
      >
        ⇔
      </div>

      {/* 两侧标签 */}
      <div style={{ position: 'absolute', top: 100, left: 48, fontSize: 26, background: 'rgba(0,0,0,0.45)', padding: '4px 12px', borderRadius: 4, fontWeight: 800, color: 'rgba(255,255,255,0.82)', letterSpacing: '0.16em', opacity: labelIn }}>{left}</div>
      <div style={{ position: 'absolute', top: 100, right: 48, fontSize: 26, background: 'rgba(0,0,0,0.45)', padding: '4px 12px', borderRadius: 4, fontWeight: 800, color: '#ff5a4d', letterSpacing: '0.16em', opacity: labelIn }}>{right}</div>

      <AbsoluteFill style={{ background: BOTTOM_GRAD }} />
      <div style={{ position: 'absolute', left: 64, right: 64, bottom: 118 }}>
        <Big_ size={72}>{accent(text)}</Big_>
        {sub ? <div style={{ marginTop: 12, fontSize: 27, color: 'rgba(255,255,255,0.7)' }}>{sub}</div> : null}
      </div>
    </AbsoluteFill>
  );
};

/* ── 3. 图上手绘圈注：红圈/箭头一笔画出来，像拿笔在你脸上画 ─────────── */
export const PhotoMark: React.FC<{
  src: string;
  text: string;
  sub?: string;
  cx?: number; // 圈心 x（0-100）
  cy?: number; // 圈心 y（0-100）
  rx?: number; // 半径 x（像素）
  ry?: number;
  arrow?: boolean;
  vline?: boolean; // 画一条竖向虚线（垂线对比：耳垂对肩峰、后脑贴墙）
  vx?: number; // 竖线横坐标（0-100）
  vy1?: number; // 起点 y（0-100）
  vy2?: number; // 终点 y（0-100）
}> = ({ src, text, sub, cx = 62, cy = 46, rx = 190, ry = 130, arrow = true, vline = false, vx = 50, vy1 = 12, vy2 = 30 }) => {
  const frame = useCurrentFrame();
  const draw = interpolate(frame, [6, 34], [0, 1], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  const arrowP = interpolate(frame, [34, 52], [0, 1], clamp);
  const zoom = interpolate(frame, [0, 220], [1.16, 1.03], { ...clamp, easing: Easing.out(Easing.cubic) });

  return (
    <AbsoluteFill style={{ backgroundColor: INK, fontFamily: SANS, overflow: 'hidden' }}>
      <AbsoluteFill>
        <Img src={staticFile(src)} style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${zoom})` }} />
      </AbsoluteFill>
      <AbsoluteFill style={{ background: BOTTOM_GRAD }} />

      <svg width="100%" height="100%" viewBox="0 0 1280 720" style={{ position: 'absolute', inset: 0 }}>
        {vline ? (
          <g opacity={draw}>
            <line
              x1={(vx / 100) * 1280}
              y1={(vy1 / 100) * 720}
              x2={(vx / 100) * 1280}
              y2={(vy1 / 100) * 720 + ((vy2 - vy1) / 100) * 720 * draw}
              stroke="#ff3b30"
              strokeWidth={5.5}
              strokeDasharray="15 13"
              strokeLinecap="round"
              style={{ filter: 'drop-shadow(0 0 10px rgba(255,59,48,0.5))' }}
            />
            <circle cx={(vx / 100) * 1280} cy={(vy1 / 100) * 720} r={10} fill="#ff3b30" />
            <circle cx={(vx / 100) * 1280} cy={(vy2 / 100) * 720} r={10} fill="#ff3b30" opacity={draw} />
          </g>
        ) : (
        <ellipse
          cx={(cx / 100) * 1280}
          cy={(cy / 100) * 720}
          rx={rx}
          ry={ry}
          fill="none"
          stroke="#ff3b30"
          strokeWidth={7}
          strokeLinecap="round"
          pathLength={1}
          strokeDasharray={1}
          strokeDashoffset={1 - draw}
          transform={`rotate(-9 ${(cx / 100) * 1280} ${(cy / 100) * 720})`}
          style={{ filter: 'drop-shadow(0 0 12px rgba(255,59,48,0.55))' }}
        />
        )}
        {arrow ? (
          <g opacity={arrowP}>
            <line
              x1={(cx / 100) * 1280 + rx + 26}
              y1={(cy / 100) * 720 - ry - 18}
              x2={(cx / 100) * 1280 + rx + 26 + 120 * arrowP}
              y2={(cy / 100) * 720 - ry - 18 - 86 * arrowP}
              stroke="#ff3b30"
              strokeWidth={7}
              strokeLinecap="round"
            />
            <polygon
              points={`${(cx / 100) * 1280 + rx + 146},${(cy / 100) * 720 - ry - 104} ${(cx / 100) * 1280 + rx + 118},${(cy / 100) * 720 - ry - 96} ${(cx / 100) * 1280 + rx + 140},${(cy / 100) * 720 - ry - 66}`}
              fill="#ff3b30"
              opacity={arrowP}
            />
          </g>
        ) : null}
      </svg>

      <div style={{ position: 'absolute', left: 64, right: 64, bottom: 118 }}>
        <Big_ size={70}>{accent(text)}</Big_>
        {sub ? <div style={{ marginTop: 12, fontSize: 27, color: 'rgba(255,255,255,0.72)' }}>{sub}</div> : null}
      </div>
    </AbsoluteFill>
  );
};

/* ── 4. 数字滚动：0 → 目标值，像仪表盘跳数 ─────────────────────────── */
export const CountUp: React.FC<{ value: number; suffix?: string; prefix?: string; text: string; sub?: string; dec?: number; dark?: boolean }> = ({
  value,
  suffix = '',
  prefix = '',
  text,
  sub,
  dec = 0,
  dark,
}) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [4, 42], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const shown = (value * p).toFixed(dec);
  const pop = spring({ frame: frame - 4, fps: FPS, config: { damping: 13, stiffness: 140 } });

  return (
    <AbsoluteFill
      style={{
        background: dark ? INK : PAPER,
        backgroundImage: dark ? 'radial-gradient(circle at 30% 20%, rgba(255,255,255,0.07), transparent 62%)' : 'radial-gradient(circle at 78% 12%, rgba(255,255,255,0.9), transparent 60%)',
        fontFamily: SANS,
        color: dark ? '#f6f2ec' : INK,
        justifyContent: 'center',
        alignItems: 'center',
        overflow: 'hidden',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', transform: `scale(${0.86 + pop * 0.14})` }}>
        <div style={{ fontSize: 190, fontWeight: 900, lineHeight: 1, color: RED, letterSpacing: '-0.03em' }}>
          {prefix}
          {shown}
        </div>
        {suffix ? <div style={{ fontSize: 76, fontWeight: 900, marginLeft: 10, color: RED }}>{suffix}</div> : null}
      </div>
      <div style={{ marginTop: 26, fontSize: 46, fontWeight: 800, textAlign: 'center', paddingHorizontal: 40 }}>{accent(text)}</div>
      {sub ? <div style={{ marginTop: 14, fontSize: 27, color: dark ? 'rgba(246,242,236,0.6)' : '#6b655d' }}>{sub}</div> : null}
    </AbsoluteFill>
  );
};

/* ── 5. 21 天打卡格：一格一格点亮，最后整体闪一下 ───────────────────── */
export const Grid21: React.FC<{ text: string; sub?: string; days?: number; title?: string }> = ({ text, sub, days = 21, title = '21 天打卡' }) => {
  const frame = useCurrentFrame();
  const cols = 7;
  const cell = 86;
  const gap = 12;

  return (
    <AbsoluteFill style={{ backgroundColor: PAPER, fontFamily: SANS, color: INK, justifyContent: 'center', alignItems: 'center', overflow: 'hidden' }}>
      <div style={{ fontSize: 30, letterSpacing: '0.18em', color: '#6b655d', marginBottom: 22 }}>{title}</div>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, ${cell}px)`, gap }}>
        {Array.from({ length: days }).map((_, i) => {
          const s = spring({ frame: frame - 6 - i * 2.6, fps: FPS, config: { damping: 14, stiffness: 180 } });
          const on = s > 0.05;
          return (
            <div
              key={i}
              style={{
                width: cell,
                height: cell,
                borderRadius: 10,
                background: on ? RED : 'rgba(23,20,15,0.07)',
                color: on ? '#fff' : 'rgba(23,20,15,0.34)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 26,
                fontWeight: 800,
                transform: `scale(${on ? 0.72 + s * 0.28 : 1})`,
                opacity: on ? 1 : 0.85,
              }}
            >
              {i + 1}
            </div>
          );
        })}
      </div>
      <div style={{ marginTop: 34, fontSize: 52, fontWeight: 900, textAlign: 'center', paddingHorizontal: 60 }}>{accent(text)}</div>
      {sub ? <div style={{ marginTop: 12, fontSize: 26, color: '#6b655d' }}>{sub}</div> : null}
    </AbsoluteFill>
  );
};

/* ── 6. 打字机：一个字一个字敲出来，光标闪 ─────────────────────────── */
export const TypeLine: React.FC<{ text: string; sub?: string; speed?: number; dark?: boolean; size?: number }> = ({
  text,
  sub,
  speed = 1.7,
  dark = true,
  size = 72,
}) => {
  const frame = useCurrentFrame();
  const n = Math.min(text.length, Math.floor(frame / speed));
  const shown = text.slice(0, n);
  const blink = Math.floor(frame / 9) % 2 === 0;
  const done = n >= text.length;

  return (
    <AbsoluteFill
      style={{
        background: dark ? INK : PAPER,
        fontFamily: SANS,
        color: dark ? '#f6f2ec' : INK,
        justifyContent: 'center',
        paddingLeft: 96,
        paddingRight: 96,
        overflow: 'hidden',
      }}
    >
      <div style={{ fontSize: size, fontWeight: 900, lineHeight: 1.34, letterSpacing: '-0.015em' }}>
        {shown}
        <span style={{ color: RED, opacity: blink && !done ? 1 : done ? 0.85 : 0 }}>▍</span>
      </div>
      {sub && done ? <div style={{ marginTop: 18, fontSize: 27, color: dark ? 'rgba(246,242,236,0.6)' : '#6b655d' }}>{sub}</div> : null}
    </AbsoluteFill>
  );
};
