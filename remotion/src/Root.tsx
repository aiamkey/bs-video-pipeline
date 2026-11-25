import { Composition } from 'remotion';
import { BsFilm, BS_TOTAL } from './bs/FilmBs';
import { DataFilm, DATA_TOTAL } from './bs/DataFilm';
import { DataFilm3, DATA_TOTAL3 } from './bs/DataFilm3';
import { DataFilm4, DATA_TOTAL4 } from './bs/DataFilm4';
import { CartoonDemo, CARTOON_DEMO_TOTAL } from './bs/CartoonDemo';

/**
 * 当前只服务「男生变帅」口播片。
 * DataFilm = pipeline 主入口（读 src/data/film.json，一句一镜）。
 * LBR / AiflPromo 相关 composition 已移除，需要时另行恢复。
 */
export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="DataFilm"
        component={DataFilm}
        durationInFrames={DATA_TOTAL}
        fps={30}
        width={1280}
        height={720}
      />
      <Composition
        id="BsFilm"
        component={BsFilm}
        durationInFrames={BS_TOTAL}
        fps={30}
        width={1280}
        height={720}
      />
      <Composition
        id="DataFilm3"
        component={DataFilm3}
        durationInFrames={DATA_TOTAL3}
        fps={30}
        width={1280}
        height={720}
      />
      <Composition
        id="DataFilm4"
        component={DataFilm4}
        durationInFrames={DATA_TOTAL4}
        fps={30}
        width={1280}
        height={720}
      />
      <Composition
        id="CartoonDemo"
        component={CartoonDemo}
        durationInFrames={CARTOON_DEMO_TOTAL}
        fps={30}
        width={1280}
        height={720}
      />
    </>
  );
};
