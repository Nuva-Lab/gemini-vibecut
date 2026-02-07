import {AbsoluteFill, Audio, Video, useCurrentFrame, useVideoConfig, Sequence, staticFile} from 'remotion';
import {RollingCaption, CaptionSegment} from './components/RollingCaption';

interface MangaClipProps {
  videoSrc: string;
  audioSrc?: string;
  captions: CaptionSegment[];
  audioVolume?: number;
}

/**
 * Resolve a source path — if it's just a filename, load from public/ via staticFile().
 * If it's an absolute path or URL, use as-is.
 */
function resolveSrc(src: string): string {
  if (src.startsWith('http') || src.startsWith('/') || src.startsWith('file://')) {
    return src;
  }
  return staticFile(src);
}

export const MangaClip: React.FC<MangaClipProps> = ({
  videoSrc,
  audioSrc,
  captions,
  audioVolume = 1.0,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const resolvedVideo = resolveSrc(videoSrc);
  const resolvedAudio = audioSrc ? resolveSrc(audioSrc) : undefined;

  return (
    <AbsoluteFill>
      {/* Video layer */}
      <Video
        src={resolvedVideo}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
        }}
      />

      {/* Audio layer (separate from video) */}
      {resolvedAudio && <Audio src={resolvedAudio} volume={audioVolume} />}

      {/* Caption layer - render each caption as a Sequence */}
      {captions.map((caption, index) => {
        const startFrame = Math.floor((caption.startMs / 1000) * fps);
        const durationFrames = Math.max(1, Math.ceil(((caption.endMs - caption.startMs) / 1000) * fps));

        return (
          <Sequence
            key={index}
            from={startFrame}
            durationInFrames={durationFrames}
          >
            <RollingCaption caption={caption} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
