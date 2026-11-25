import React from 'react';
import { AbsoluteFill, Audio, Sequence, interpolate, staticFile, useCurrentFrame } from 'remotion';
import film from '../data/film.json';
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
  TeacherCard,
  BoardCard,
  WrongCard,
  AnnotateCard,
  SlidesCard,
} from './Cards';
import { PanelLayer, type PanelT } from './Panel';

export const DATA_TOTAL = Math.round(film.totalSeconds * FPS);
const sec = (s: number) => Math.round(s * FPS);
const PANELS: PanelT[] = ((film as unknown as { panels?: PanelT[] }).panels ?? []) as PanelT[];

type Line = (typeof film.lines)[number];
type Card = NonNullable<Line['card']>;

const renderCard = (card: Card): React.ReactNode => {
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
    case 'teacher':
      return <TeacherCard text={card.text ?? ''} sub={card.sub} dark={card.dark} />;
    case 'board':
      return <BoardCard items={card.items ?? []} title={card.title} no={card.no} />;
    case 'wrong':
      return <WrongCard text={card.text ?? ''} sub={card.sub} />;
    case 'annotate':
      return <AnnotateCard src={card.src ?? 'textures/bs/bs-brow.jpg'} points={card.points ?? []} text={card.text} />;
    case 'slides':
      return (
        <SlidesCard
          frames={card.frames ?? []}
          captions={card.captions}
          text={card.text}
          hold={card.hold}
          push={card.push}
          fit={card.fit as never}
          paper={card.paper}
        />
      );
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
  const globalP = Math.min(1, frame / DATA_TOTAL);
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

const Subtitle: React.FC<{ text: string; dur: number }> = ({ text, dur }) => {
  const frame = useCurrentFrame();
  const i = interpolate(frame, [0, 4], [0, 1], clamp);
  const o = interpolate(frame, [dur - 5, dur], [1, 0], clamp);
  return (
    <div style={{ position: 'absolute', left: 0, right: 0, bottom: 66, display: 'flex', justifyContent: 'center', opacity: i * o, pointerEvents: 'none' }}>
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

/**
 * 镜头进出。kind 来自每句 card 的 transition 字段：
 *   cut 硬切（凯哥原片最常用）/ fade 淡入（默认）/ slideL 左滑入 / slideR 右滑入
 *   zoom 微缩放 / slam 冲击缩放
 * 起点 opacity 用 0.15 起步，避免切点闪白。
 */
const Enter: React.FC<{ kind?: string; dur: number; children: React.ReactNode }> = ({ kind = 'fade', dur, children }) => {
  const frame = useCurrentFrame();
  const k = interpolate(frame, [0, Math.max(1, dur)], [0, 1], clamp);
  const push = 1 + 0.028 * k; // 全片极慢推近：消掉静止画面，也让切点有生气
  const span = kind === 'slam' ? 4 : 6;
  const p = interpolate(frame, [0, span], [0, 1], clamp);
  const out = interpolate(frame, [Math.max(1, dur - 4), dur], [1, 0], clamp);
  let tx = 0;
  let sc = push;
  if (kind === 'slideL') tx = (1 - p) * 70;
  if (kind === 'slideR') tx = (1 - p) * -70;
  if (kind === 'zoom') sc = (0.94 + p * 0.06) * push;
  if (kind === 'slam') sc = 1.16 - p * 0.16;
  const base = kind === 'slam' ? 1 : 0.15 + p * 0.85;
  return (
    <AbsoluteFill style={{ opacity: base * out, transform: `translateX(${tx}px) scale(${sc})`, transformOrigin: '50% 50%' }}>
      {children}
    </AbsoluteFill>
  );
};

const FilmCore: React.FC<{ subs?: boolean }> = ({ subs = true }) => {
  const frame = useCurrentFrame();
  const lines = film.lines;
  return (
    <AbsoluteFill style={{ backgroundColor: PAPER }}>
      <Audio src={staticFile(film.voice)} volume={1} />
      <Audio src={staticFile('audio/bgm/house-vibez.mp3')} volume={0.07} loop />

      {PANELS.map((p, i) => {
        const from = sec(p.start);
        const dur = Math.max(4, sec(p.end) - from);
        return (
          <Sequence key={`panel-${i}`} from={from} durationInFrames={dur}>
            <PanelLayer panel={p} />
          </Sequence>
        );
      })}

      {lines.map((line, i) => {
        if ((line as { panel?: string | null }).panel) return null; // 屏内句子只有字幕，不画卡片
        const from = sec(line.start);
        const next = i + 1 < lines.length ? sec(lines[i + 1].start) : DATA_TOTAL;
        const dur = Math.max(2, next - from);
        return (
          <Sequence key={i} from={from} durationInFrames={dur}>
            <Enter kind={(line.card as { transition?: string } | null)?.transition} dur={dur}>
              {line.card ? renderCard(line.card) : <CopyCard text={line.text} />}
            </Enter>
          </Sequence>
        );
      })}

      {subs && lines.map((line, i) => {
        if ((line as { sub?: boolean }).sub === false) return null; // 卡片大字已等于这句，不再叠字幕
        const from = sec(line.start);
        const dur = Math.max(8, sec(line.end) - from);
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
      <SectionBar frame={frame} />
    </AbsoluteFill>
  );
};

export const DataFilm: React.FC = () => <FilmCore />;

/** 无字幕版：给剪映导"卡片静帧"用（字幕交给剪映文字轨，避免烧死重复） */
export const DataFilmNoSub: React.FC = () => <FilmCore subs={false} />;
