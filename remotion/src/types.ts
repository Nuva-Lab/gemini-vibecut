export interface WordSegment {
  text: string;
  startMs: number;
  endMs: number;
}

export interface CaptionSegment {
  text: string;
  startMs: number;
  endMs: number;
  speaker?: string;  // Character name for dialogue
  words?: WordSegment[];  // For karaoke-style highlighting
}

export interface MangaClipProps {
  videoSrc: string;
  audioSrc?: string;
  captions: CaptionSegment[];
  audioVolume?: number;  // Default 1.0
}
