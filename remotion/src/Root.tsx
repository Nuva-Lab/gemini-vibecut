import {Composition} from 'remotion';
import {MangaClip} from './MangaClip';
import type {MangaClipProps} from './types';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* Manga clip with captions - 9:16 vertical */}
      <Composition
        id="MangaClip"
        component={MangaClip}
        durationInFrames={480}  // 16s at 30fps (default, overridden by props)
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          videoSrc: '',
          audioSrc: undefined,
          captions: [],
          audioVolume: 1.0,
        } satisfies MangaClipProps}
      />

      {/* Manga clip - 16:9 horizontal (for testing) */}
      <Composition
        id="MangaClipHorizontal"
        component={MangaClip}
        durationInFrames={480}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          videoSrc: '',
          audioSrc: undefined,
          captions: [],
          audioVolume: 1.0,
        } satisfies MangaClipProps}
      />
    </>
  );
};
