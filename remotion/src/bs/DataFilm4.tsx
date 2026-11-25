import React from 'react';
import { AbsoluteFill, Audio, Sequence, interpolate, staticFile, useCurrentFrame } from 'remotion';
import film from '../data/film-04.json';
import {
  FPS,
  INK,
  PAPER,
  SANS,
  RED,
  clamp,
  Frame,
  CopyCard,
  SectionTitle,
  ImageCard,
  TriList,
  CmdCard,
  StatCard,
  QuoteCard,
  ChipRow,
  BrowCard,
  PostureCard,
  ColorCard,
  HookCard,
  OutroCard,
} from './Cards';
import { PhotoPush, BeforeAfter, PhotoMark, CountUp, Grid21, TypeLine } from './Motion';

export const DATA_TOTAL4 = Math.round(film.totalSeconds * FPS);
const sec = (s: number) => Math.round(s * FPS);

type Line = (typeof film.lines)[number];
type Card = NonNullable<Line['card']>;

const renderCard = (card: Card): React.ReactNode => {
  const c = card as any;
  switch (card.type) {
    case 'hook':
      return <HookCard text={card.text ?? ''} face={card.face as never} pose={card.pose as never} />;
    case 'copy':
      return <CopyCard text={card.text ?? ''} size={card.size} dark={card.dark} sub={card.sub} />;
    case 'section':
      return <SectionTitle no={card.no ?? '01'} title={card.title ?? ''} sub={card.sub} />;
    case 'image':
      return <ImageCard src={card.src ?? 'textures/bs/bs-mirror.jpg'} text={card.text ?? ''} sub={card.sub} dark={card.dark} />;
    case 'list':
      return <TriList items={card.items ?? []} title={card.title} kind="ok" dark={card.dark} />;
    case 'no-list':
      return <TriList items={card.items ?? []} title={card.title} kind="no" dark={card.dark} />;
    case 'cmd':
      return <CmdCard lines={card.items ?? []} note={card.title} />;
    case 'stat':
      return <StatCard value={card.value ?? '0'} unit={card.unit} label={card.title ?? ''} dark={card.dark} />;
    case 'quote':
      return <QuoteCard text={card.text ?? ''} by={card.sub} dark={card.dark} />;
    case 'chips':
      return <ChipRow items={card.items ?? []} title={card.title} />;
    case 'brow':
      return <BrowCard />;
    case 'posture':
      return <PostureCard />;
    case 'color':
      return <ColorCard title={card.title} />;
    case 'outro':
      return <OutroCard text={card.text ?? ''} accent={card.accent} kicker={card.kicker} />;
    case 'photo':
      return (
        <PhotoPush
          src={c.src ?? 'textures/bs/bs-skin.jpg'}
          text={c.text ?? ''}
          sub={c.sub}
          dir={c.dir}
          dur={c.dur}
        />
      );
    case 'compare':
      return (
        <BeforeAfter
          src={c.src ?? 'textures/bs/bs-skin.jpg'}
          text={c.text ?? ''}
          left={c.left}
          right={c.right}
          sub={c.sub}
        />
      );
    case 'mark':
      return (
        <PhotoMark
          src={c.src ?? 'textures/bs/bs-skin.jpg'}
          text={c.text ?? ''}
          sub={c.sub}
          cx={c.cx}
          cy={c.cy}
          rx={c.rx}
          ry={c.ry}
          arrow={c.arrow}
          vline={c.vline}
          vx={c.vx}
          vy1={c.vy1}
          vy2={c.vy2}
        />
      );
    case 'count':
      return (
        <CountUp
          value={Number(c.value ?? 0)}
          suffix={c.unit}
          prefix={c.prefix}
          text={c.title ?? c.text ?? ''}
          sub={c.sub}
          dec={c.dec}
          dark={c.dark}
        />
      );
    case 'grid21':
      return <Grid21 text={c.text ?? ''} sub={c.sub} days={c.days} title={c.title} />;
    case 'type':
      return <TypeLine text={c.text ?? ''} sub={c.sub} speed={c.speed} dark={c.dark} size={c.size} />;
    default:
      return <CopyCard text={card.text ?? ''} />;
  }
};

const SectionBar: React.FC<{ frame: number }> = ({ frame }) => {
  const secs = film.sections;
  const n = secs.length;
  const w = 1280 / n;
  const idx = secs.findIndex((s) => frame >= sec(s.start) && frame < sec(s.end));
  const active = idx < 0 ? n - 1 : idx;
  const globalP = Math.min(1, frame / DATA_TOTAL4);
  return (
    <>
      <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 46, background: '#0d0b09', display: 'flex' }}>
        {secs.map((s0, i) => {
          const from = sec(s0.start);
          const to = sec(s0.end);
          const p = frame <= from ? 0 : Math.min(1, (frame - from) / Math.max(1, to - from));
          return (
            <div
              key={s0.label + i}
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
                }}
              >
                {s0.label}
              </span>
            </div>
          );
        })}
      </div>
      <div style={{ position: 'absolute', left: 0, bottom: 46, height: 3, width: `${globalP * 100}%`, background: RED, opacity: 0.9 }} />
    </>
  );
};

const ChapterNo: React.FC<{ frame: number }> = ({ frame }) => {
  const secs = film.sections;
  const idx = secs.findIndex((s) => frame >= sec(s.start) && frame < sec(s.end));
  const n = idx < 0 ? secs.length : idx + 1;
  return (
    <div
      style={{
        position: 'absolute',
        left: 26,
        top: 22,
        width: 42,
        height: 42,
        borderRadius: 21,
        background: '#5ea8d8',
        color: '#fff',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 22,
        fontWeight: 800,
        boxShadow: '0 2px 8px rgba(0,0,0,0.25)',
      }}
    >
      {n}
    </div>
  );
};

const DAY_OF_SECTION = [1, 4, 11, 21];

const DayStamp: React.FC<{ frame: number }> = ({ frame }) => {
  const secs = film.sections;
  let idx = 0;
  for (let i = 0; i < secs.length; i++) if (frame >= sec(secs[i].start)) idx = i;
  const day = DAY_OF_SECTION[Math.min(idx, DAY_OF_SECTION.length - 1)];
  const pop = interpolate(frame % 90, [0, 8], [1.18, 1], clamp);
  return (
    <div
      style={{
        position: 'absolute',
        right: 30,
        top: 22,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '6px 14px',
        border: '3px solid #ff3b30',
        borderRadius: 6,
        background: 'rgba(0,0,0,0.42)',
        color: '#fff',
        fontFamily: SANS,
        fontSize: 24,
        fontWeight: 900,
        letterSpacing: '0.08em',
        transform: `scale(${pop})`,
      }}
    >
      <span style={{ width: 9, height: 9, borderRadius: 5, background: '#ff3b30', display: 'inline-block' }} />
      DAY {day}
    </div>
  );
};

const Subtitle: React.FC<{ text: string; dur: number }> = ({ text, dur }) => {
  const frame = useCurrentFrame();
  const i = interpolate(frame, [0, 4], [0, 1], clamp);
  const o = interpolate(frame, [dur - 5, dur], [1, 0], clamp);
  return (
    <div style={{ position: 'absolute', left: 0, right: 0, bottom: 96, display: 'flex', justifyContent: 'center', opacity: i * o, pointerEvents: 'none' }}>
      <span
        style={{
          fontFamily: SANS,
          fontSize: 30,
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

export const DataFilm4: React.FC = () => {
  const frame = useCurrentFrame();
  const lines = film.lines;
  return (
    <AbsoluteFill style={{ backgroundColor: PAPER }}>
      {film.voice ? <Audio src={staticFile(film.voice)} volume={1} /> : null}
      <Audio src={staticFile('audio/bgm/house-vibez.mp3')} volume={0.07} loop />

      {lines.map((line, i) => {
        const from = sec(line.start);
        const next = i + 1 < lines.length ? sec(lines[i + 1].start) : DATA_TOTAL4;
        const dur = Math.max(2, next - from);
        return (
          <Sequence key={i} from={from} durationInFrames={dur}>
            {line.card ? renderCard(line.card) : <CopyCard text={line.text} />}
          </Sequence>
        );
      })}

      {lines.map((line, i) => {
        const from = sec(line.start);
        const dur = Math.max(8, sec(line.end) - from);
        // 动效卡自带主文字，再压一条字幕会三行叠在一起
        const t = (line.card as any)?.type;
        if (t === 'photo' || t === 'compare' || t === 'mark' || t === 'count' || t === 'grid21' || t === 'type' || t === 'outro') return null;
        return (
          <Sequence key={`sub-${i}`} from={from} durationInFrames={dur}>
            <Subtitle text={line.text} dur={dur} />
          </Sequence>
        );
      })}

      {film.sections.slice(1).map((s, i) => (
        <Sequence key={`sfx-${i}`} from={sec(s.start) - 4} durationInFrames={54}>
          <Audio src={staticFile('audio/transition-soft.mp3')} volume={0.3} />
        </Sequence>
      ))}

      <ChapterNo frame={frame} />
      <DayStamp frame={frame} />
      <SectionBar frame={frame} />
    </AbsoluteFill>
  );
};

