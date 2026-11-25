import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  Easing,
} from 'remotion';
import timeline from '../data/voice-bs-timeline.json';
import { Avatar } from './Avatar';

export const FPS = 30;
export const BS_TOTAL = Math.round(timeline.totalSeconds * FPS);

const INK = '#17140f';
const RED = '#c8231b';
const PAPER = '#f4f1ec';
const SANS = '"Microsoft YaHei", "PingFang SC", "Noto Sans SC", ui-sans-serif, sans-serif';
const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;

const CH = timeline.chapters;
const sec = (s: number) => Math.round(s * FPS);
const at = (ci: number, li: number) => sec(CH[ci].lines[Math.min(li, CH[ci].lines.length - 1)].start);
const chStart = (ci: number) => sec(CH[ci].start);
const chEnd = (ci: number) => sec(CH[ci].end);

type Shot = { from: number; dur: number; node: React.ReactNode };
const SHOTS: Shot[] = [];

/* ------------------------------------------------------------------ 底框 */

const Frame: React.FC<{ children: React.ReactNode; dark?: boolean; tone?: string }> = ({ children, dark, tone }) => (
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
  </AbsoluteFill>
);

const Reveal: React.FC<{ delay?: number; children: React.ReactNode; y?: number; style?: React.CSSProperties }> = ({
  delay = 0,
  children,
  y = 22,
  style,
}) => {
  const frame = useCurrentFrame();
  const t = spring({ frame: (frame - delay) * 1.4, fps: FPS, config: { damping: 200, mass: 0.6 } });
  return <div style={{ opacity: 0.1 + t * 0.9, transform: `translateY(${(1 - t) * y}px)`, ...style }}>{children}</div>;
};

const Big: React.FC<{ children: React.ReactNode; size?: number; color?: string; weight?: number; style?: React.CSSProperties }> = ({
  children,
  size = 84,
  color,
  weight = 800,
  style,
}) => (
  <div style={{ fontFamily: SANS, fontSize: size, fontWeight: weight, lineHeight: 1.28, letterSpacing: '-0.01em', color, ...style }}>
    {children}
  </div>
);

const SectionTitle: React.FC<{ no: string; title: string; sub?: string }> = ({ no, title, sub }) => (
  <Frame dark>
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 26 }}>
        <Reveal delay={0}>
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

const ImageCard: React.FC<{ src: string; text: string; sub?: string; dark?: boolean }> = ({ src, text, sub, dark }) => {
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

const TriList: React.FC<{ items: string[]; kind?: 'ok' | 'no'; title?: string; dark?: boolean }> = ({ items, kind = 'ok', title, dark }) => {
  const frame = useCurrentFrame();
  return (
    <Frame dark={dark}>
      <AbsoluteFill style={{ justifyContent: 'center', paddingLeft: 96 }}>
        {title ? (
          <Reveal delay={0} style={{ marginBottom: 26 }}>
            <div style={{ fontSize: 30, color: dark ? 'rgba(246,242,236,0.6)' : '#6b655d', letterSpacing: '0.14em' }}>{title}</div>
          </Reveal>
        ) : null}
        {items.map((t, i) => {
          const s = spring({ frame: frame * 1.6 - i * 6, fps: FPS, config: { damping: 15, stiffness: 150 } });
          return (
            <div key={t} style={{ display: 'flex', alignItems: 'center', gap: 20, marginBottom: 22, opacity: 0.15 + s * 0.85, transform: `translateX(${(1 - s) * -30}px)` }}>
              <div style={{ width: 44, height: 44, borderRadius: 22, background: kind === 'no' ? RED : '#2f7d4f', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26, fontWeight: 800 }}>
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

const CmdCard: React.FC<{ lines: string[]; note?: string }> = ({ lines, note }) => {
  const frame = useCurrentFrame();
  return (
    <Frame>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
        <Reveal delay={0}>
          <div style={{ fontSize: 30, color: '#6b655d', letterSpacing: '0.16em', marginBottom: 30 }}>去剪头就这么说</div>
        </Reveal>
        {lines.map((l, i) => (
          <Reveal key={l} delay={6 + i * 10} style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 62, fontWeight: 800, padding: '10px 34px', border: `3px solid ${INK}`, background: i === 0 ? INK : '#fff', color: i === 0 ? '#fff' : INK }}>
              {l}
            </div>
          </Reveal>
        ))}
        {note ? (
          <Reveal delay={40} style={{ marginTop: 22 }}>
            <div style={{ fontSize: 26, color: '#6b655d' }}>{note}</div>
          </Reveal>
        ) : null}
      </AbsoluteFill>
    </Frame>
  );
};

const StatCard: React.FC<{ value: string; unit?: string; label: string; dark?: boolean }> = ({ value, unit, label, dark }) => (
  <Frame dark={dark}>
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 16 }}>
        <Reveal delay={0}>
          <div style={{ fontSize: 230, fontWeight: 900, color: dark ? '#fff' : INK, lineHeight: 1 }}>{value}</div>
        </Reveal>
        {unit ? <Reveal delay={10}><div style={{ fontSize: 70, fontWeight: 800, color: RED }}>{unit}</div></Reveal> : null}
      </div>
      <Reveal delay={18} style={{ marginTop: 10 }}>
        <div style={{ fontSize: 32, color: dark ? 'rgba(246,242,236,0.6)' : '#6b655d', letterSpacing: '0.1em' }}>{label}</div>
      </Reveal>
    </AbsoluteFill>
  </Frame>
);

/* ---------------------------------------------------------- 图形示意卡 */

const BrowDiagram: React.FC = () => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [8, 46], [0, 1], clamp);
  return (
    <Frame>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
        <Reveal delay={0}>
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

const PostureDiagram: React.FC = () => {
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

const ColorChips: React.FC = () => {
  const frame = useCurrentFrame();
  const items = [
    { c: '#17140f', n: '黑' },
    { c: '#ffffff', n: '白' },
    { c: '#9a958d', n: '灰' },
    { c: '#1d3557', n: '藏青' },
  ];
  return (
    <Frame>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
        <Reveal delay={0}>
          <div style={{ fontSize: 28, color: '#6b655d', letterSpacing: '0.14em', marginBottom: 30 }}>颜色别超过三种</div>
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
        <Reveal delay={26} style={{ marginTop: 34 }}>
          <div style={{ fontSize: 32, color: '#6b655d' }}>先把这四个穿明白，再谈风格</div>
        </Reveal>
      </AbsoluteFill>
    </Frame>
  );
};

const HookCard: React.FC = () => {
  const frame = useCurrentFrame();
  const s = spring({ frame, fps: FPS, config: { damping: 16, stiffness: 90 } });
  const bubble = interpolate(frame, [16, 34], [0, 1], clamp);
  return (
    <Frame>
      <AbsoluteFill style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 40 }}>
        <div style={{ transform: `translateY(${(1 - s) * 40}px)`, opacity: s }}>
          <Avatar width={230} face="smirk" pose="shrug" />
        </div>
        <div style={{ position: 'relative', opacity: bubble }}>
          <div style={{ background: '#fff', border: `4px solid ${INK}`, borderRadius: 18, padding: '26px 34px', maxWidth: 560 }}>
            <div style={{ fontSize: 52, fontWeight: 800, lineHeight: 1.35 }}>你长得不丑，<br />只是没打理。</div>
          </div>
          <svg width={40} height={40} style={{ position: 'absolute', left: -26, top: 46 }}>
            <path d="M40 0 L0 20 L40 40 Z" fill="#fff" stroke={INK} strokeWidth={4} />
          </svg>
        </div>
      </AbsoluteFill>
    </Frame>
  );
};

const OutroCard: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <Frame dark>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
        <Reveal delay={0}>
          <div style={{ fontSize: 24, letterSpacing: '0.4em', color: 'rgba(246,242,236,0.5)' }}>START TODAY</div>
        </Reveal>
        <Reveal delay={8} style={{ marginTop: 18 }}>
          <div style={{ fontSize: 96, fontWeight: 900, textAlign: 'center', lineHeight: 1.4 }}>
            变帅从来不是脸的问题，<br />
            <span style={{ color: RED }}>是你愿不愿意开始。</span>
          </div>
        </Reveal>
        <Reveal delay={30} style={{ marginTop: 40 }}>
          <div style={{ width: 120, height: 5, background: RED }} />
        </Reveal>
      </AbsoluteFill>
    </Frame>
  );
};

/* ------------------------------------------------------------ 时间线 */

const add = (from: number, to: number, node: React.ReactNode) =>
  SHOTS.push({ from, dur: Math.max(1, to - from), node });

// 序
add(chStart(0), at(0, 1), <HookCard />);
add(at(0, 1), at(0, 2), <Frame><AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}><Reveal><Big size={96} weight={900}>你只是<Big size={96} color={RED} weight={900} style={{ display: 'inline' }}>没打理</Big></Big></Reveal></AbsoluteFill></Frame>);
add(at(0, 2), at(0, 3), <ImageCard src="textures/bs/bs-mirror.jpg" text="收拾干净，是两个人" sub="同一张脸，两种状态" />);
add(at(0, 3), chEnd(0), <TriList title="今天这五件事" items={['不用动刀', '不用花大钱', '看完就能做']} />);

// 头发
add(chStart(1), at(1, 1), <SectionTitle no="01" title="头发" sub="HAIR" />);
add(at(1, 1), at(1, 2), <Frame><AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}><Reveal><Big size={88} weight={900}>性价比最高的<Big size={88} color={RED} weight={900} style={{ display: 'inline' }}>整容</Big></Big></Reveal></AbsoluteFill></Frame>);
add(at(1, 2), at(1, 3), <TriList title="记住三条" items={['两侧不留长', '头顶要蓬松', '刘海别压眉']} />);
add(at(1, 3), at(1, 5), <TriList kind="no" title="反过来就是" items={['两侧长 → 脸显宽', '头顶塌 → 头显小', '压眉毛 → 显得呆']} />);
add(at(1, 5), at(1, 7), <CmdCard lines={['两侧推短', '头顶留三指', '后面上短下长']} note="别再说「随便修一下」" />);
add(at(1, 7), chEnd(1), <StatCard value="3" unit="个月 4 次" label="比买十件衣服都管用" />);

// 眉毛
add(chStart(2), at(2, 1), <SectionTitle no="02" title="眉毛" sub="BROWS" />);
add(at(2, 1), at(2, 2), <Frame><AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}><Reveal><Big size={80} weight={900}>决定你是<Big size={80} color={RED} weight={900} style={{ display: 'inline' }}>精神</Big>还是没睡醒</Big></Reveal></AbsoluteFill></Frame>);
add(at(2, 2), at(2, 4), <BrowDiagram />);
add(at(2, 4), at(2, 5), <Frame><AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}><Reveal><Big size={96} weight={900}>别修太细，<Big size={96} color={RED} weight={900} style={{ display: 'inline' }}>要有量</Big></Big></Reveal></AbsoluteFill></Frame>);
add(at(2, 5), chEnd(2), <ImageCard src="textures/bs/bs-brow.jpg" text="不用化妆，脸就干净了" />);

// 体态
add(chStart(3), at(3, 1), <SectionTitle no="03" title="体态" sub="POSTURE" />);
add(at(3, 1), at(3, 2), <StatCard value="−3" unit="CM" label="含胸驼背偷走的身高" dark />);
add(at(3, 2), at(3, 4), <PostureDiagram />);
add(at(3, 4), at(3, 5), <Frame><AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}><Reveal><Big size={88} weight={900}>头顶有根线，<br /><Big size={88} color={RED} weight={900} style={{ display: 'inline' }}>往上提</Big></Big></Reveal></AbsoluteFill></Frame>);
add(at(3, 5), chEnd(3), <ImageCard src="textures/bs/bs-posture.jpg" text="一个月，走路都不一样" />);

// 皮肤
add(chStart(4), at(4, 1), <SectionTitle no="04" title="皮肤" sub="SKIN" />);
add(at(4, 1), at(4, 2), <Frame><AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}><Reveal><Big size={84} weight={900}>不需要白，<Big size={84} color={RED} weight={900} style={{ display: 'inline' }}>需要干净</Big></Big></Reveal></AbsoluteFill></Frame>);
add(at(4, 2), at(4, 3), <TriList title="每天三步" items={['早上 · 清水洗脸', '晚上 · 洁面', '擦干 · 抹一层保湿']} />);
add(at(4, 3), at(4, 4), <TriList kind="no" title="三件事别做" items={['毛巾使劲搓', '用手挤', '熬夜到脸发黄']} />);
add(at(4, 4), chEnd(4), <ImageCard src="textures/bs/bs-skin.jpg" text="干净，比帅更耐看" />);

// 穿搭
add(chStart(5), at(5, 1), <SectionTitle no="05" title="穿合身" sub="FIT" />);
add(at(5, 1), at(5, 2), <ImageCard src="textures/bs/bs-wear.jpg" text="不合身，再贵也像借的" />);
add(at(5, 2), at(5, 3), <TriList title="三个位置对齐" items={['肩线 → 对齐肩点', '袖长 → 到手腕', '裤长 → 到鞋面']} />);
add(at(5, 3), at(5, 4), <ColorChips />);
add(at(5, 4), chEnd(5), <Frame><AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}><Reveal><Big size={92} weight={900}>合身 =<Big size={92} color={RED} weight={900} style={{ display: 'inline' }}>最快的高级感</Big></Big></Reveal></AbsoluteFill></Frame>);

// 收尾
add(chStart(6), at(6, 1), <StatCard value="1" unit="个月" label="五件事，做满一个月" dark />);
add(at(6, 1), BS_TOTAL, <OutroCard />);

/* -------------------------------------------------------- 顶层装帧 */

const ChapterNo: React.FC<{ frame: number }> = ({ frame }) => {
  const idx = CH.findIndex((c) => frame >= sec(c.start) && frame < sec(c.end));
  const i = idx < 0 ? CH.length - 1 : idx;
  const n = CH[i].ch + 1;
  return (
    <div style={{ position: 'absolute', left: 26, top: 22, width: 42, height: 42, borderRadius: 21, background: '#5ea8d8', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, fontWeight: 800, boxShadow: '0 2px 8px rgba(0,0,0,0.25)' }}>
      {n}
    </div>
  );
};

const SectionBar: React.FC<{ frame: number }> = ({ frame }) => {
  const n = CH.length;
  const w = 1280 / n;
  const idx = CH.findIndex((c) => frame >= sec(c.start) && frame < sec(c.end));
  const active = idx < 0 ? n - 1 : idx;
  const globalP = Math.min(1, frame / BS_TOTAL);
  return (
    <>
      <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 46, background: '#0d0b09', display: 'flex' }}>
        {CH.map((c, i) => {
          const from = sec(c.start);
          const to = sec(c.end);
          const p = frame <= from ? 0 : Math.min(1, (frame - from) / Math.max(1, to - from));
          return (
            <div
              key={c.ch}
              style={{
                width: w,
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRight: i < n - 1 ? '1px solid rgba(246,242,236,0.16)' : 'none',
                overflow: 'hidden',
              }}
            >
              <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${p * 100}%`, background: i === active ? 'rgba(246,242,236,0.92)' : 'rgba(246,242,236,0.2)' }} />
              {i === active && p > 0 && p < 1 ? (
                <div style={{ position: 'absolute', left: `${p * 100}%`, top: 0, bottom: 0, width: 3, background: RED }} />
              ) : null}
              <span
                style={{
                  position: 'relative',
                  fontSize: 20,
                  fontWeight: 600,
                  letterSpacing: '0.06em',
                  color: i === active ? (p > 0.55 ? '#0d0b09' : 'rgba(246,242,236,0.95)') : 'rgba(246,242,236,0.5)',
                  transition: 'none',
                }}
              >
                {c.label}
              </span>
            </div>
          );
        })}
      </div>
      <div style={{ position: 'absolute', left: 0, bottom: 46, height: 3, width: `${globalP * 100}%`, background: RED, opacity: 0.9 }} />
    </>
  );
};

const Subtitle: React.FC<{ text: string; dur: number }> = ({ text, dur }) => {
  const frame = useCurrentFrame();
  const i = interpolate(frame, [0, 4], [0, 1], clamp);
  const o = interpolate(frame, [dur - 5, dur], [1, 0], clamp);
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: 66,
        display: 'flex',
        justifyContent: 'center',
        opacity: i * o,
        pointerEvents: 'none',
      }}
    >
      <span
        style={{
          fontFamily: SANS,
          fontSize: 34,
          fontWeight: 700,
          color: '#fff',
          textShadow: '0 0 4px #000, 2px 2px 0 #000, -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000',
          padding: '2px 10px',
          whiteSpace: 'nowrap',
        }}
      >
        {text}
      </span>
    </div>
  );
};

export const BsFilm: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ backgroundColor: PAPER }}>
      <Audio src={staticFile('audio/voice-bs.wav')} volume={1} />
      <Audio src={staticFile('audio/bgm/house-vibez.mp3')} volume={0.07} loop />

      {SHOTS.map((s, i) => (
        <Sequence key={i} from={s.from} durationInFrames={s.dur}>
          {s.node}
        </Sequence>
      ))}

      {CH.flatMap((ch, ci) =>
        ch.lines.map((line, li) => {
          const from = sec(line.start);
          const dur = Math.max(8, sec(line.end) - from);
          return (
            <Sequence key={`s-${ci}-${li}`} from={from} durationInFrames={dur}>
              <Subtitle text={line.text} dur={dur} />
            </Sequence>
          );
        }),
      )}

      {CH.slice(1).map((ch) => (
        <Sequence key={`sfx-${ch.ch}`} from={sec(ch.start) - 4} durationInFrames={54}>
          <Audio src={staticFile('audio/transition-soft.mp3')} volume={0.3} />
        </Sequence>
      ))}

      <ChapterNo frame={frame} />
      <SectionBar frame={frame} />
    </AbsoluteFill>
  );
};
