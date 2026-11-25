// 卡通体系样片：三个场景 + 龙诚配音（每段时长按实际语音长度定，不硬切）
import React from 'react';
import { AbsoluteFill, Audio, Sequence, staticFile } from 'remotion';
import { PodiumScene, BlackboardScene, CartoonVs } from './Cartoon';

const S1 = 108; // 3.6s  配音 d1 2.88s
const S2 = 173; // 5.8s  配音 d2 5.04s
const S3 = 159; // 5.3s  配音 d3 4.37s

export const CARTOON_DEMO_TOTAL = S1 + S2 + S3;

export const CartoonDemo: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: '#f6f2ec' }}>
      <Sequence from={0} durationInFrames={S1}>
        <PodiumScene text="兄弟们，|先泼盆冷水|" sub="不是胖，是糊了" pose="point" accent />
        <Audio src={staticFile('audio/cartoon/d1.mp3')} />
      </Sequence>
      <Sequence from={S1} durationInFrames={S2}>
        <BlackboardScene lines={['睡前 1 小时', '尽量少喝水']} no sub="高糖饮料喝完，第二天脸肿给你看" />
        <Audio src={staticFile('audio/cartoon/d2.mp3')} />
      </Sequence>
      <Sequence from={S1 + S2} durationInFrames={S3}>
        <CartoonVs
          src="textures/bs2/face-45.jpg"
          text="你的脸不是胖，|是糊了|"
          left="你以为"
          right="其实"
          sub="21 天后，脸型线条自己会说话"
        />
        <Audio src={staticFile('audio/cartoon/d3.mp3')} />
      </Sequence>
    </AbsoluteFill>
  );
};
