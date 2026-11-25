import React from 'react';
import { AbsoluteFill, Audio, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame, Easing } from 'remotion';
import { Avatar } from './Avatar';

export const FPS = 30;
export const INK = '#17140f';
export const RED = '#c8231b';
export const PAPER = '#f4f1ec';
export const SANS = '"Microsoft YaHei", "PingFang SC", "Noto Sans SC", ui-sans-serif, sans-serif';
export const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;

export const Frame: React.FC<{ children: React.ReactNode; dark?: boolean; tone?: string; watermark?: string }> = ({
  children,
  dark,
  tone,
  watermark = '',
}) => (
  <AbsoluteFill
    style={{
      backgroundColor: dark ? INK : tone ?? PAPER,
      backgroundImage: dark
        ? 'radial-gradient(circle at 25% 15%, rgba(255,255,255,0.06), transparent 60%)'
        : 'radial-gradient(circle at 75% 8%, rgba(255,255,255,0.85), transparent 58%)',
      fontFamily: SANS,
      color: dark ? '#f6f2ec' : INK,
      overflow: 'hidden',
    }}
  >
    {children}
    {watermark ? (
      <div style={{ position: 'absolute', right: 26, top: 24, fontSize: 20, fontWeight: 600, letterSpacing: '0.06em', color: dark ? 'rgba(246,242,236,0.35)' : 'rgba(23,20,15,0.28)' }}>
        {watermark}
      </div>
    ) : null}
  </AbsoluteFill>
);

export const Reveal: React.FC<{ delay?: number; children: React.ReactNode; y?: number; style?: React.CSSProperties }> = ({
  delay = 0,
  children,
  y = 22,
  style,
}) => {
  const frame = useCurrentFrame();
  const t = spring({ frame: (frame - delay) * 1.4, fps: FPS, config: { damping: 200, mass: 0.6 } });
  return <div style={{ opacity: 0.1 + t * 0.9, transform: `translateY(${(1 - t) * y}px)`, ...style }}>{children}</div>;
};

export const Big: React.FC<{
  children: React.ReactNode;
  size?: number;
  color?: string;
  weight?: number;
  style?: React.CSSProperties;
}> = ({ children, size = 84, color, weight = 800, style }) => (
  <div style={{ fontFamily: SANS, fontSize: size, fontWeight: weight, lineHeight: 1.28, letterSpacing: '-0.01em', color, ...style }}>
    {children}
  </div>
);

/* 大字卡：支持 "文字|红字|文字" 用 | 分段上色 */
const renderAccent = (text: string, size: number) =>
  text.split('|').map((seg, i) =>
    i % 2 === 1 ? (
      <span key={i} style={{ color: RED }}>{seg}</span>
    ) : (
      <span key={i}>{seg}</span>
    ),
  );

export const CopyCard: React.FC<{ text: string; size?: number; dark?: boolean; sub?: string; center?: boolean }> = ({
  text,
  size = 84,
  dark,
  sub,
  center = true,
}) => (
  <Frame dark={dark}>
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: center ? 'center' : 'flex-start', paddingLeft: center ? 0 : 110 }}>
      <Reveal>
        <Big size={size} weight={900} style={{ textAlign: center ? 'center' : 'left' }}>
          {renderAccent(text, size)}
        </Big>
      </Reveal>
      {sub ? (
        <Reveal delay={12} style={{ marginTop: 18 }}>
          <div style={{ fontSize: 28, color: dark ? 'rgba(246,242,236,0.6)' : '#6b655d' }}>{sub}</div>
        </Reveal>
      ) : null}
    </AbsoluteFill>
  </Frame>
);

export const SectionTitle: React.FC<{ no: string; title: string; sub?: string }> = ({ no, title, sub }) => (
  <Frame dark>
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 26 }}>
        <Reveal>
          <div style={{ fontSize: 150, fontWeight: 900, color: RED, lineHeight: 1 }}>{no}</div>
        </Reveal>
        <Reveal delay={6}>
          <div style={{ fontSize: 130, fontWeight: 900, lineHeight: 1 }}>{title}</div>
        </Reveal>
      </div>
      {sub ? (
        <Reveal delay={16} style={{ marginTop: 24 }}>
          <div style={{ fontSize: 30, color: 'rgba(246,242,236,0.6)', letterSpacing: '0.12em' }}>{sub}</div>
        </Reveal>
      ) : null}
    </AbsoluteFill>
  </Frame>
);

export const ImageCard: React.FC<{ src: string; text: string; sub?: string; dark?: boolean }> = ({ src, text, sub, dark }) => {
  const frame = useCurrentFrame();
  const zoom = interpolate(frame, [0, 200], [1.12, 1.0], { ...clamp, easing: Easing.out(Easing.cubic) });
  return (
    <Frame dark={dark}>
      <AbsoluteFill>
        <Img src={staticFile(src)} style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${zoom})` }} />
        <AbsoluteFill style={{ background: 'linear-gradient(0deg, rgba(15,13,11,0.78) 0%, rgba(15,13,11,0.1) 52%, rgba(15,13,11,0.05) 100%)' }} />
        <div style={{ position: 'absolute', left: 64, right: 64, bottom: 118 }}>
          <Reveal delay={2}>
            <Big size={72} color="#fff" weight={900}>{text}</Big>
          </Reveal>
          {sub ? (
            <Reveal delay={12} style={{ marginTop: 12 }}>
              <div style={{ fontSize: 28, color: 'rgba(255,255,255,0.72)' }}>{sub}</div>
            </Reveal>
          ) : null}
        </div>
      </AbsoluteFill>
    </Frame>
  );
};

export const TriList: React.FC<{ items: string[]; kind?: 'ok' | 'no'; title?: string; dark?: boolean }> = ({
  items,
  kind = 'ok',
  title,
  dark,
}) => {
  const frame = useCurrentFrame();
  return (
    <Frame dark={dark}>
      <AbsoluteFill style={{ justifyContent: 'center', paddingLeft: 96 }}>
        {title ? (
          <Reveal style={{ marginBottom: 26 }}>
            <div style={{ fontSize: 30, color: dark ? 'rgba(246,242,236,0.6)' : '#6b655d', letterSpacing: '0.14em' }}>{title}</div>
          </Reveal>
        ) : null}
        {items.map((t, i) => {
          const s = spring({ frame: frame * 1.6 - i * 6, fps: FPS, config: { damping: 15, stiffness: 150 } });
          return (
            <div
              key={t}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 20,
                marginBottom: 22,
                opacity: 0.15 + s * 0.85,
                transform: `translateX(${(1 - s) * -30}px)`,
              }}
            >
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: 22,
                  background: kind === 'no' ? RED : '#2f7d4f',
                  color: '#fff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 26,
                  fontWeight: 800,
                }}
              >
                {kind === 'no' ? '✕' : '✓'}
              </div>
              <div style={{ fontSize: 48, fontWeight: 700 }}>{t}</div>
            </div>
          );
        })}
      </AbsoluteFill>
    </Frame>
  );
};

export const CmdCard: React.FC<{ lines: string[]; note?: string }> = ({ lines, note }) => (
  <Frame>
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <Reveal>
        <div style={{ fontSize: 30, color: '#6b655d', letterSpacing: '0.16em', marginBottom: 30 }}>{note ?? '照着做就行'}</div>
      </Reveal>
      {lines.map((l, i) => (
        <Reveal key={l} delay={6 + i * 10} style={{ marginBottom: 14 }}>
          <div
            style={{
              fontSize: 58,
              fontWeight: 800,
              padding: '10px 34px',
              border: `3px solid ${INK}`,
              background: i === 0 ? INK : '#fff',
              color: i === 0 ? '#fff' : INK,
            }}
          >
            {l}
          </div>
        </Reveal>
      ))}
    </AbsoluteFill>
  </Frame>
);

export const StatCard: React.FC<{ value: string; unit?: string; label: string; dark?: boolean }> = ({ value, unit, label, dark }) => (
  <Frame dark={dark}>
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 16 }}>
        <Reveal>
          <div style={{ fontSize: 230, fontWeight: 900, color: dark ? '#fff' : INK, lineHeight: 1 }}>{value}</div>
        </Reveal>
        {unit ? (
          <Reveal delay={10}>
            <div style={{ fontSize: 70, fontWeight: 800, color: RED }}>{unit}</div>
          </Reveal>
        ) : null}
      </div>
      <Reveal delay={18} style={{ marginTop: 10 }}>
        <div style={{ fontSize: 32, color: dark ? 'rgba(246,242,236,0.6)' : '#6b655d', letterSpacing: '0.1em' }}>{label}</div>
      </Reveal>
    </AbsoluteFill>
  </Frame>
);

export const QuoteCard: React.FC<{ text: string; by?: string; dark?: boolean }> = ({ text, by, dark }) => (
  <Frame dark={dark}>
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', padding: '0 120px' }}>
      <Reveal>
        <div style={{ fontFamily: 'Georgia, serif', fontSize: 130, color: RED, lineHeight: 0.7 }}>“</div>
      </Reveal>
      <Reveal delay={6} style={{ marginTop: 8 }}>
        <div style={{ fontSize: 62, fontWeight: 800, lineHeight: 1.45, textAlign: 'center' }}>{text}</div>
      </Reveal>
      {by ? (
        <Reveal delay={20} style={{ marginTop: 26 }}>
          <div style={{ fontSize: 26, color: dark ? 'rgba(246,242,236,0.55)' : '#6b655d', letterSpacing: '0.16em' }}>—— {by}</div>
        </Reveal>
      ) : null}
    </AbsoluteFill>
  </Frame>
);

export const ChipRow: React.FC<{ items: string[]; title?: string }> = ({ items, title }) => {
  const frame = useCurrentFrame();
  return (
    <Frame>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', gap: 22 }}>
        {title ? (
          <Reveal style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 30, color: '#6b655d', letterSpacing: '0.14em' }}>{title}</div>
          </Reveal>
        ) : null}
        {items.map((t, i) => {
          const s = spring({ frame: frame * 1.6 - i * 8, fps: FPS, config: { damping: 15, stiffness: 150 } });
          return (
            <div
              key={t}
              style={{
                fontSize: 44,
                fontWeight: 800,
                padding: '16px 44px',
                border: `3px solid ${INK}`,
                background: i === 0 ? INK : '#fff',
                color: i === 0 ? '#fff' : INK,
                opacity: 0.15 + s * 0.85,
                transform: `translateY(${(1 - s) * 20}px)`,
              }}
            >
              {t}
            </div>
          );
        })}
      </AbsoluteFill>
    </Frame>
  );
};

export const BrowCard: React.FC = () => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [8, 46], [0, 1], clamp);
  return (
    <Frame>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
        <Reveal>
          <div style={{ fontSize: 28, color: '#6b655d', letterSpacing: '0.14em', marginBottom: 24 }}>这三处修干净</div>
        </Reveal>
        <svg width={760} height={300} viewBox="0 0 760 300">
          <path d="M90 190 Q 220 120 350 170" stroke="#221f1c" strokeWidth={22} fill="none" strokeLinecap="round" />
          <path d="M410 170 Q 540 120 670 190" stroke="#221f1c" strokeWidth={22} fill="none" strokeLinecap="round" />
          <ellipse cx={195} cy={232} rx={52} ry={34} fill="#fff" stroke="#221f1c" strokeWidth={5} />
          <ellipse cx={565} cy={232} rx={52} ry={34} fill="#fff" stroke="#221f1c" strokeWidth={5} />
          <circle cx={195} cy={236} r={15} fill="#221f1c" />
          <circle cx={565} cy={236} r={15} fill="#221f1c" />
          <circle cx={120} cy={176} r={26} fill="none" stroke={RED} strokeWidth={4} opacity={p} />
          <circle cx={380} cy={160} r={26} fill="none" stroke={RED} strokeWidth={4} opacity={p} />
          <circle cx={660} cy={178} r={26} fill="none" stroke={RED} strokeWidth={4} opacity={p} />
          <text x={120} y={110} textAnchor="middle" fontSize={24} fill={RED} opacity={p}>上面杂毛</text>
          <text x={380} y={110} textAnchor="middle" fontSize={24} fill={RED} opacity={p}>眉心</text>
          <text x={660} y={110} textAnchor="middle" fontSize={24} fill={RED} opacity={p}>眉尾散毛</text>
        </svg>
      </AbsoluteFill>
    </Frame>
  );
};

export const PostureCard: React.FC = () => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [6, 50], [0, 1], clamp);
  const dots = [
    { y: 96, label: '后脑勺' },
    { y: 168, label: '肩胛骨' },
    { y: 250, label: '臀部' },
    { y: 330, label: '脚跟' },
  ];
  return (
    <Frame>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', flexDirection: 'row', gap: 80 }}>
        <svg width={320} height={420} viewBox="0 0 320 420">
          <line x1={250} y1={20} x2={250} y2={400} stroke="#c9c2b8" strokeWidth={8} />
          <path d="M240 96 Q 200 90 190 120 L190 260 Q 190 300 200 330 L200 390" stroke="#221f1c" strokeWidth={14} fill="none" strokeLinecap="round" />
          <circle cx={196} cy={96} r={26} fill="#221f1c" />
          {dots.map((d, i) => (
            <circle key={d.label} cx={236} cy={d.y} r={12} fill={RED} opacity={p > i * 0.22 ? 1 : 0.15} />
          ))}
        </svg>
        <div>
          {dots.map((d, i) => (
            <div key={d.label} style={{ fontSize: 40, fontWeight: 700, marginBottom: 22, opacity: p > i * 0.22 ? 1 : 0.25 }}>
              {d.label}
            </div>
          ))}
        </div>
      </AbsoluteFill>
    </Frame>
  );
};

export const ColorCard: React.FC<{ items?: { c: string; n: string }[]; title?: string }> = ({
  items = [
    { c: '#17140f', n: '黑' },
    { c: '#ffffff', n: '白' },
    { c: '#9a958d', n: '灰' },
    { c: '#1d3557', n: '藏青' },
  ],
  title = '颜色别超过三种',
}) => {
  const frame = useCurrentFrame();
  return (
    <Frame>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
        <Reveal>
          <div style={{ fontSize: 28, color: '#6b655d', letterSpacing: '0.14em', marginBottom: 30 }}>{title}</div>
        </Reveal>
        <div style={{ display: 'flex', gap: 28 }}>
          {items.map((it, i) => {
            const s = spring({ frame: frame * 1.5 - i * 8, fps: FPS, config: { damping: 16, stiffness: 140 } });
            return (
              <div key={it.n} style={{ textAlign: 'center', opacity: 0.15 + s * 0.85, transform: `translateY(${(1 - s) * 24}px)` }}>
                <div style={{ width: 150, height: 150, background: it.c, border: `3px solid ${INK}` }} />
                <div style={{ marginTop: 12, fontSize: 28, fontWeight: 700 }}>{it.n}</div>
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    </Frame>
  );
};

export const HookCard: React.FC<{ text: string; face?: 'flat' | 'wow' | 'sad' | 'smirk' | 'think'; pose?: 'idle' | 'point' | 'shrug' | 'flex' }> = ({
  text,
  face = 'smirk',
  pose = 'shrug',
}) => {
  const frame = useCurrentFrame();
  const s = spring({ frame, fps: FPS, config: { damping: 16, stiffness: 90 } });
  const bubble = interpolate(frame, [14, 32], [0, 1], clamp);
  return (
    <Frame>
      <AbsoluteFill style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 40 }}>
        <div style={{ transform: `translateY(${(1 - s) * 40}px)`, opacity: s }}>
          <Avatar width={230} face={face} pose={pose} />
        </div>
        <div style={{ position: 'relative', opacity: bubble }}>
          <div style={{ background: '#fff', border: `4px solid ${INK}`, borderRadius: 18, padding: '26px 34px', maxWidth: 580 }}>
            <div style={{ fontSize: 50, fontWeight: 800, lineHeight: 1.35 }}>{text}</div>
          </div>
          <svg width={40} height={40} style={{ position: 'absolute', left: -26, top: 46 }}>
            <path d="M40 0 L0 20 L40 40 Z" fill="#fff" stroke={INK} strokeWidth={4} />
          </svg>
        </div>
      </AbsoluteFill>
    </Frame>
  );
};

export const OutroCard: React.FC<{ text: string; accent?: string; kicker?: string }> = ({ text, accent, kicker = '21 DAYS' }) => (  <Frame dark>
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <Reveal>
        <div style={{ fontSize: 24, letterSpacing: '0.4em', color: 'rgba(246,242,236,0.5)' }}>{kicker}</div>
      </Reveal>
      <Reveal delay={8} style={{ marginTop: 18 }}>
        <div style={{ fontSize: 92, fontWeight: 900, textAlign: 'center', lineHeight: 1.42 }}>
          {text}
          {accent ? (
            <>
              <br />
              <span style={{ color: RED }}>{accent}</span>
            </>
          ) : null}
        </div>
      </Reveal>
      <Reveal delay={30} style={{ marginTop: 40 }}>
        <div style={{ width: 120, height: 5, background: RED }} />
      </Reveal>
    </AbsoluteFill>
  </Frame>
);

/* ───────────── 场景卡：讲师 / 黑板 / 错误示范 / 实拍标注 ─────────────
 * 对应凯哥原片"讲师提问 → 黑板列条 → 学员演错 → 局部图解 → 真人手把手"的五步循环。
 * 用法见 pipeline/SPEC.md 3.7，卡型字段见 pipeline/README.md。
 */

/** teacher：深色底，左侧讲师剪影，右侧一句提问。用于每段开头"提出问题"。 */
export const TeacherCard: React.FC<{ text: string; sub?: string; dark?: boolean }> = ({ text, sub, dark = true }) => {
  const frame = useCurrentFrame();
  const s = spring({ frame, fps: FPS, config: { damping: 200, mass: 0.7 } });
  const breathe = Math.sin(frame / 11) * 2;
  return (
    <Frame dark={dark}>
      <div style={{ position: 'absolute', left: 92, bottom: 104, width: 200, opacity: 0.2 + s * 0.8, transform: `translateY(${breathe}px)` }}>
        <svg viewBox="0 0 200 320" width="100%">
          <path d="M54 320 C54 216 146 216 146 320 Z" fill="#f6f2ec" opacity={0.94} />
          <circle cx="100" cy="98" r="45" fill="#f6f2ec" opacity={0.94} />
          <path d="M100 134 l-14 22 l14 9 l14 -9 Z" fill={RED} />
          <circle cx="86" cy="94" r="4.2" fill={INK} />
          <circle cx="114" cy="94" r="4.2" fill={INK} />
        </svg>
      </div>
      <div style={{ position: 'absolute', left: 350, right: 92, top: '33%' }}>
        <div style={{ width: 46, height: 4, background: RED, marginBottom: 26, opacity: s }} />
        <div style={{ fontSize: 62, fontWeight: 800, lineHeight: 1.4, opacity: 0.15 + s * 0.85, transform: `translateY(${(1 - s) * 16}px)` }}>
          {text}
        </div>
        {sub ? <div style={{ marginTop: 22, fontSize: 30, color: 'rgba(246,242,236,0.52)' }}>{sub}</div> : null}
      </div>
    </Frame>
  );
};

/** board：墨绿黑板 + 木框 + 编号条目，逐条滑入。用于"记住三条 / 这五件事"。 */
export const BoardCard: React.FC<{ items: string[]; title?: string; no?: string }> = ({ items, title, no }) => {
  const frame = useCurrentFrame();
  return (
    <Frame tone="#173f33">
      <div style={{ position: 'absolute', inset: 24, border: '10px solid #6f4a24', borderRadius: 4, boxShadow: 'inset 0 0 90px rgba(0,0,0,0.45)' }} />
      {no ? (
        <div style={{ position: 'absolute', right: 62, top: 50, fontSize: 26, letterSpacing: '0.24em', color: 'rgba(255,255,255,0.45)' }}>{no}</div>
      ) : null}
      <div style={{ position: 'absolute', left: 92, right: 92, top: 136 }}>
        {title ? (
          <div style={{ fontSize: 40, color: 'rgba(255,255,255,0.7)', marginBottom: 38, letterSpacing: '0.04em' }}>{title}</div>
        ) : null}
        {items.map((it, i) => {
          const p = interpolate(frame, [i * 7, i * 7 + 9], [0, 1], clamp);
          return (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'baseline',
                gap: 26,
                marginBottom: 24,
                opacity: p,
                transform: `translateX(${(1 - p) * 28}px)`,
              }}
            >
              <span style={{ fontSize: 54, fontWeight: 900, color: '#fff', minWidth: 46 }}>{i + 1}</span>
              <span style={{ fontSize: 50, fontWeight: 700, color: '#f3f0e8', lineHeight: 1.25 }}>{it}</span>
            </div>
          );
        })}
      </div>
    </Frame>
  );
};

/** wrong：错误示范。红叉 + 一句"这么做就废了"。用在学员演错的镜头位。 */
export const WrongCard: React.FC<{ text: string; sub?: string }> = ({ text, sub }) => {
  const frame = useCurrentFrame();
  const s = spring({ frame, fps: FPS, config: { damping: 13, stiffness: 120 } });
  return (
    <Frame>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', opacity: 0.15 + s * 0.85 }}>
          <svg width={92} height={92} style={{ transform: `scale(${0.86 + s * 0.14}) rotate(${(1 - s) * -12}deg)` }}>
            <g stroke={RED} strokeWidth={13} strokeLinecap="round">
              <line x1="16" y1="16" x2="76" y2="76" />
              <line x1="76" y1="16" x2="16" y2="76" />
            </g>
          </svg>
          <div style={{ marginTop: 26, fontSize: 66, fontWeight: 800, textAlign: 'center', maxWidth: 980, lineHeight: 1.35 }}>{text}</div>
          {sub ? <div style={{ marginTop: 22, fontSize: 30, color: '#8a8378', textAlign: 'center' }}>{sub}</div> : null}
        </div>
      </AbsoluteFill>
    </Frame>
  );
};

/** annotate：实拍图 + 红色点位标注（替代手绘解剖线稿，用现成照片做"证据"）。 */
export const AnnotateCard: React.FC<{
  src: string;
  points?: { x: number; y: number; label: string }[];
  text?: string;
  dim?: number;
}> = ({ src, points = [], text, dim = 0.32 }) => {
  const frame = useCurrentFrame();
  return (
    <Frame dark>
      <AbsoluteFill>
        <img
          src={staticFile(src)}
          style={{ width: '100%', height: '100%', objectFit: 'cover', filter: `brightness(${1 - dim * 0.35})` }}
        />
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(0,0,0,0.28) 0%, rgba(0,0,0,0.02) 40%, rgba(0,0,0,0.55) 100%)' }} />
        {points.map((p, i) => {
          const t = interpolate(frame, [8 + i * 9, 16 + i * 9], [0, 1], clamp);
          return (
            <div key={i} style={{ position: 'absolute', left: `${p.x}%`, top: `${p.y}%`, opacity: t }}>
              <div style={{ width: 16, height: 16, borderRadius: 8, background: RED, boxShadow: '0 0 0 6px rgba(200,35,27,0.22)' }} />
              <div
                style={{
                  position: 'absolute',
                  left: 24,
                  top: -14,
                  padding: '6px 12px',
                  background: 'rgba(20,17,14,0.82)',
                  borderLeft: `3px solid ${RED}`,
                  color: '#fff',
                  fontSize: 24,
                  fontWeight: 700,
                  whiteSpace: 'nowrap',
                }}
              >
                {p.label}
              </div>
            </div>
          );
        })}
        {text ? (
          <div style={{ position: 'absolute', left: 60, right: 60, bottom: 96, fontSize: 44, fontWeight: 800, color: '#fff', textShadow: '0 2px 12px rgba(0,0,0,0.6)', lineHeight: 1.3 }}>
            {text}
          </div>
        ) : null}
      </AbsoluteFill>
    </Frame>
  );
};

export const SlidesCard: React.FC<{
  frames: string[];
  captions?: string[];
  text?: string;
  hold?: number;          // 每张停留秒数，默认 1.4
  push?: boolean;         // 每张 1.00→1.035 极慢推近，默认开
  fit?: 'contain' | 'cover';
  paper?: boolean;        // contain 时铺纸白底
}> = ({ frames, captions = [], text, hold = 1.4, push = true, fit = 'contain', paper = true }) => {
  const frame = useCurrentFrame();
  const per = Math.max(6, Math.round(hold * FPS));
  const idx = Math.min(frames.length - 1, Math.floor(frame / per));
  const local = frame - idx * per;
  const z = push ? interpolate(local, [0, per], [1.0, 1.035], clamp) : 1;
  const cap = captions[idx];
  return (
    <Frame dark={!paper}>
      <AbsoluteFill style={{ background: paper ? PAPER : '#111' }}>
        <Img
          key={idx}
          src={staticFile(frames[idx])}
          style={{ width: '100%', height: '100%', objectFit: fit, transform: `scale(${z})` }}
        />
        {text ? (
          <>
            <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 300, background: 'linear-gradient(0deg, rgba(12,10,8,0.72) 0%, rgba(12,10,8,0.35) 45%, rgba(12,10,8,0) 100%)' }} />
            <div style={{ position: 'absolute', left: 56, right: 56, bottom: 176, fontSize: 46, fontWeight: 900, color: '#fff', lineHeight: 1.28, textShadow: '0 2px 14px rgba(0,0,0,0.8)' }}>
              {text}
            </div>
          </>
        ) : null}
        {cap ? (
          <div style={{ position: 'absolute', right: 56, top: 64, padding: '8px 16px', background: 'rgba(23,20,15,0.82)', color: '#fff', fontSize: 24, fontWeight: 700 }}>
            {cap}
          </div>
        ) : null}
      </AbsoluteFill>
    </Frame>
  );
};
