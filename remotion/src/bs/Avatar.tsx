import React from 'react';

type Face = 'flat' | 'wow' | 'sad' | 'smirk' | 'think';
type Pose = 'idle' | 'point' | 'shrug' | 'flex';

/** 2D 扁平卡通男生：白脸、黑发、灰 V 领 T、圆头手。
 * 表情 / 手势可切换，用于口播类视频的"讲解人"位。 */
export const Avatar: React.FC<{ width?: number; face?: Face; pose?: Pose; flip?: boolean }> = ({
  width = 260,
  face = 'flat',
  pose = 'idle',
  flip,
}) => {
  const h = width * 1.75;
  const eyeY = 250;
  const eyeRx = face === 'wow' ? 30 : 26;
  const eyeRy = face === 'wow' ? 34 : 28;
  const browTilt = face === 'sad' ? 1 : face === 'smirk' ? 0.5 : 0;

  const mouth =
    face === 'wow' ? (
      <ellipse cx={200} cy={330} rx={20} ry={26} fill="#8c2a22" />
    ) : face === 'smirk' ? (
      <path d="M168 328 Q204 344 236 322" stroke="#1a1714" strokeWidth={7} fill="none" strokeLinecap="round" />
    ) : face === 'sad' ? (
      <path d="M170 336 Q200 320 232 336" stroke="#1a1714" strokeWidth={7} fill="none" strokeLinecap="round" />
    ) : face === 'think' ? (
      <path d="M172 330 L230 330" stroke="#1a1714" strokeWidth={7} strokeLinecap="round" />
    ) : (
      <path d="M172 326 Q200 336 230 326" stroke="#1a1714" strokeWidth={7} fill="none" strokeLinecap="round" />
    );

  const armLeft =
    pose === 'point'
      ? 'M132 430 L64 320'
      : pose === 'shrug'
        ? 'M132 430 L70 380'
        : pose === 'flex'
          ? 'M132 430 L96 380'
          : 'M132 430 L110 560';
  const armRight =
    pose === 'point'
      ? 'M268 430 L330 350'
      : pose === 'shrug'
        ? 'M268 430 L330 380'
        : pose === 'flex'
          ? 'M268 430 L304 380'
          : 'M268 430 L290 560';

  return (
    <svg
      width={width}
      height={h}
      viewBox="0 0 400 700"
      style={{ transform: flip ? 'scaleX(-1)' : undefined, overflow: 'visible' }}
    >
      {/* 身体 */}
      <rect x={124} y={392} width={152} height={300} rx={28} fill="#9aa4b2" stroke="#1a1714" strokeWidth={4} />
      <path d="M164 392 L200 452 L236 392 Z" fill="#cfd6df" stroke="#1a1714" strokeWidth={4} />
      <rect x={182} y={430} width={12} height={12} fill="#5c6673" />
      <rect x={206} y={430} width={12} height={12} fill="#5c6673" />

      {/* 手臂 */}
      <path d={armLeft} stroke="#f6f2ee" strokeWidth={30} strokeLinecap="round" fill="none" />
      <path d={armLeft} stroke="#1a1714" strokeWidth={30} strokeLinecap="round" fill="none" opacity={0} />
      <circle cx={pose === 'point' ? 64 : pose === 'shrug' ? 70 : pose === 'flex' ? 96 : 110}
              cy={pose === 'point' ? 320 : pose === 'shrug' ? 380 : pose === 'flex' ? 380 : 560} r={19} fill="#f6f2ee" stroke="#1a1714" strokeWidth={4} />
      <path d={armRight} stroke="#f6f2ee" strokeWidth={30} strokeLinecap="round" fill="none" />
      <circle cx={pose === 'point' ? 330 : pose === 'shrug' ? 330 : pose === 'flex' ? 304 : 290}
              cy={pose === 'point' ? 350 : pose === 'shrug' ? 380 : pose === 'flex' ? 380 : 560} r={19} fill="#f6f2ee" stroke="#1a1714" strokeWidth={4} />

      {/* 头 */}
      <ellipse cx={200} cy={262} rx={118} ry={124} fill="#f8f4f0" stroke="#1a1714" strokeWidth={4} />
      {/* 耳朵 */}
      <ellipse cx={86} cy={266} rx={16} ry={22} fill="#f8f4f0" stroke="#1a1714" strokeWidth={3} />
      <ellipse cx={314} cy={266} rx={16} ry={22} fill="#f8f4f0" stroke="#1a1714" strokeWidth={3} />
      {/* 头发 */}
      <path
        d="M84 240 C 86 130, 150 92, 200 92 C 252 92, 316 130, 316 240
           C 300 214, 292 196, 278 188 C 262 216, 240 226, 216 214
           C 200 236, 176 238, 160 220 C 142 232, 118 236, 84 240 Z"
        fill="#221f1c"
        stroke="#1a1714"
        strokeWidth={4}
        strokeLinejoin="round"
      />
      {/* 眉毛 */}
      <path d={`M150 ${eyeY - 54 - browTilt * 6} L186 ${eyeY - 60 + browTilt * 10}`} stroke="#221f1c" strokeWidth={9} strokeLinecap="round" />
      <path d={`M214 ${eyeY - 60 - browTilt * 10} L250 ${eyeY - 54 + browTilt * 6}`} stroke="#221f1c" strokeWidth={9} strokeLinecap="round" />
      {/* 眼睛 */}
      <ellipse cx={168} cy={eyeY} rx={eyeRx} ry={eyeRy} fill="#ffffff" stroke="#1a1714" strokeWidth={4} />
      <ellipse cx={232} cy={eyeY} rx={eyeRx} ry={eyeRy} fill="#ffffff" stroke="#1a1714" strokeWidth={4} />
      <circle cx={172} cy={eyeY + 2} r={11} fill="#1a1714" />
      <circle cx={228} cy={eyeY + 2} r={11} fill="#1a1714" />
      {/* 嘴 */}
      {mouth}
    </svg>
  );
};
