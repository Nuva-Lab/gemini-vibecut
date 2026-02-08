"""
Caption Alignment: Align script text to audio timestamps.

Uses Qwen3-ForcedAligner for ~30ms precision word-level timestamps.
Perfect for karaoke-style rolling captions.

Supports:
- Local (mlx_audio): Fast on Mac M1/M2/M3
- Cloud (qwen_asr): Fallback when mlx_audio unavailable

For Chinese: Groups characters into proper words using jieba segmentation.
For English: Uses space-separated words.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Literal

logger = logging.getLogger(__name__)

# mlx_audio model for forced alignment
MLX_ALIGNER_MODEL = "mlx-community/Qwen3-ForcedAligner-0.6B-4bit"


@dataclass
class WordSegment:
    """Word-level timing segment."""
    text: str
    start_ms: int
    end_ms: int


@dataclass
class AlignedCaption:
    """Phrase-level caption with word timing for karaoke effect."""
    text: str
    start_ms: int
    end_ms: int
    words: list[WordSegment] = field(default_factory=list)


MIN_WORD_DURATION_MS = 50  # Minimum duration for any word segment


def _sanitize_word_segments(segments: list[dict]) -> list[dict]:
    """
    Ensure every word segment has endMs > startMs.

    Fixes zero-duration words from the aligner that cause caption rendering
    issues (zero-length karaoke segments).

    Rules:
    - If endMs <= startMs, set endMs = startMs + MIN_WORD_DURATION_MS
    - Cap endMs at the next word's startMs to avoid overlap
    - Last word gets MIN_WORD_DURATION_MS if zero-duration
    """
    if not segments:
        return segments

    sanitized = [dict(s) for s in segments]  # shallow copy each dict

    for i, seg in enumerate(sanitized):
        if seg["endMs"] <= seg["startMs"]:
            # Determine max end: next word's start, or uncapped for last word
            if i + 1 < len(sanitized):
                max_end = sanitized[i + 1]["startMs"]
            else:
                max_end = seg["startMs"] + MIN_WORD_DURATION_MS

            seg["endMs"] = min(seg["startMs"] + MIN_WORD_DURATION_MS, max_end)

            # If still zero (next word starts at same ms), nudge by 1ms
            if seg["endMs"] <= seg["startMs"]:
                seg["endMs"] = seg["startMs"] + 1

    return sanitized


def _segment_chinese_words(text: str) -> list[str]:
    """Segment Chinese text into words using jieba."""
    import jieba
    words = list(jieba.cut(text, cut_all=False))
    return [w for w in words if w.strip() and not re.match(r'^[,.!?;:"""()[\]{}\s]+$', w)]


def _split_into_phrases(text: str, language: str = "English") -> list[str]:
    """Split text into caption-sized phrases."""
    if language.lower() in ["chinese", "zh", "mandarin"]:
        pattern = r'([.!?;])'
        parts = re.split(pattern, text)
        combined = []
        for i, part in enumerate(parts):
            if i % 2 == 0:
                combined.append(part)
            else:
                if combined:
                    combined[-1] += part

        result = []
        for phrase in combined:
            if not phrase.strip():
                continue
            if len(phrase) > 20:
                sub_parts = re.split(r'([,])', phrase)
                temp = []
                for j, sub in enumerate(sub_parts):
                    if j % 2 == 0:
                        temp.append(sub)
                    else:
                        if temp:
                            temp[-1] += sub
                result.extend([p.strip() for p in temp if p.strip()])
            else:
                result.append(phrase.strip())
        return result
    else:
        # English: split by sentence boundaries
        pattern = r'[.!?;]'
        parts = re.split(pattern, text)
        return [p.strip() for p in parts if p.strip()]


def _group_chars_into_words(
    char_segments: list[dict],
    script: str,
    language: str = "English"
) -> list[dict]:
    """
    Group character-level timestamps into word-level timestamps.

    For Chinese: Uses jieba segmentation
    For English: Assumes space-separated words in transcript
    """
    if language.lower() in ["chinese", "zh", "mandarin"]:
        words = _segment_chinese_words(script)

        word_segments = []
        char_idx = 0

        for word in words:
            word_len = len(word)
            start_idx = char_idx
            matched_chars = 0

            while char_idx < len(char_segments) and matched_chars < word_len:
                char_text = char_segments[char_idx]["text"]
                if re.match(r'^[,.!?;:"""()[\]{}\s]+$', char_text):
                    char_idx += 1
                    continue
                matched_chars += len(char_text)
                char_idx += 1

            if start_idx < len(char_segments) and char_idx > start_idx:
                word_segments.append({
                    "text": word,
                    "startMs": char_segments[start_idx]["startMs"],
                    "endMs": char_segments[char_idx - 1]["endMs"],
                })

        return word_segments
    else:
        # For English, the aligner often returns word-level already
        return char_segments


class CaptionAligner:
    """
    Align text to audio timestamps using Qwen3-ForcedAligner.

    Supports two modes:
    - Local (mlx_audio): Fast on Mac M1/M2/M3
    - Cloud (qwen_asr): Fallback when mlx_audio unavailable

    Produces word-level timestamps (~30ms precision) for karaoke captions.

    Usage:
        aligner = CaptionAligner(mode="local")  # Use mlx_audio
        captions = await aligner.align_audio("audio.wav", "Hello world!")
        # Returns list of AlignedCaption with word-level timing
    """

    def __init__(
        self,
        device: str = "cpu",
        mode: Literal["local", "cloud", "auto"] = "auto",
    ):
        """
        Initialize aligner.

        Args:
            device: Device to use for cloud mode ('cpu' or 'mps')
            mode: "local" (mlx_audio), "cloud" (qwen_asr), or "auto" (detect)
        """
        self.device = device

        # Determine mode
        if mode == "auto":
            self.mode = self._detect_mode()
        else:
            self.mode = mode

        logger.info(f"CaptionAligner initialized in {self.mode} mode")
        self._aligner = None

    def _detect_mode(self) -> str:
        """Auto-detect best mode based on available resources."""
        try:
            import mlx_audio
            return "local"  # Prefer local on Mac
        except ImportError:
            return "cloud"

    def _load_aligner(self):
        """Lazy-load the aligner model (cloud mode only)."""
        if self._aligner is None:
            import torch
            from qwen_asr import Qwen3ForcedAligner

            logger.info(f"Loading Qwen3-ForcedAligner on {self.device}...")
            self._aligner = Qwen3ForcedAligner.from_pretrained(
                "Qwen/Qwen3-ForcedAligner-0.6B",
                dtype=torch.float32,
                device_map=self.device,
            )
        return self._aligner

    async def align_audio(
        self,
        audio_path: Path,
        text: str,
        language: str = "English",
        phrase_level: bool = True,
    ) -> list[AlignedCaption]:
        """
        Align text to audio and return word-level timestamps.

        Args:
            audio_path: Path to audio file
            text: Text to align (should match audio content)
            language: Language ('English' or 'Chinese')
            phrase_level: Group words into phrases for captions

        Returns:
            List of AlignedCaption with word-level timing
        """
        audio_path = Path(audio_path).resolve()

        # Run alignment in thread pool (model inference is CPU-bound)
        loop = asyncio.get_event_loop()

        if self.mode == "local":
            result = await loop.run_in_executor(
                None,
                lambda: self._align_local(str(audio_path), text, language, phrase_level)
            )
        else:
            result = await loop.run_in_executor(
                None,
                lambda: self._align_sync(str(audio_path), text, language, phrase_level)
            )

        return result

    def _align_local(
        self,
        audio_path: str,
        text: str,
        language: str,
        phrase_level: bool,
    ) -> list[AlignedCaption]:
        """Align using local mlx_audio model."""
        from mlx_audio.stt.generate import generate_transcription

        logger.info(f"Aligning with mlx_audio: {audio_path}")

        # Run forced alignment
        result = generate_transcription(
            model=MLX_ALIGNER_MODEL,
            audio=audio_path,
            text=text,
            verbose=False,
        )

        # Convert ForcedAlignResult to word segments
        word_segments = []
        for item in result.items:
            word_segments.append({
                "text": item.text,
                "startMs": int(item.start_time * 1000),
                "endMs": int(item.end_time * 1000),
            })

        logger.info(f"Aligned {len(word_segments)} words")

        # Sanitize zero-duration words (ensures min 50ms per word for captions)
        word_segments = _sanitize_word_segments(word_segments)

        if not phrase_level:
            return [
                AlignedCaption(
                    text=w["text"],
                    start_ms=w["startMs"],
                    end_ms=w["endMs"],
                    words=[WordSegment(w["text"], w["startMs"], w["endMs"])],
                )
                for w in word_segments
            ]

        # Group words into phrase-level captions
        return self._group_into_phrases(word_segments, text, language)

    def _group_into_phrases(
        self,
        word_segments: list[dict],
        text: str,
        language: str,
    ) -> list[AlignedCaption]:
        """Group word segments into phrase-level captions."""
        phrases = _split_into_phrases(text, language)
        phrase_captions = []

        # Build clean text for position matching
        all_words_text = ""
        word_positions = []

        for i, w in enumerate(word_segments):
            wtext = w["text"]
            if re.match(r'^[,.!?;:"""()[\]{}\s]+$', wtext):
                continue
            start_pos = len(all_words_text)
            all_words_text += wtext
            word_positions.append((start_pos, len(all_words_text), i))

        # Clean script text
        script_clean = re.sub(r'[,.!?;:"""()[\]{}\s]', '', text)

        current_pos = 0
        for phrase in phrases:
            phrase_clean = re.sub(r'[,.!?;:"""()[\]{}\s]', '', phrase)
            phrase_start = current_pos
            phrase_end = phrase_start + len(phrase_clean)
            current_pos = phrase_end

            phrase_words = []
            for start_pos, end_pos, word_idx in word_positions:
                if start_pos < phrase_end and end_pos > phrase_start:
                    ws = word_segments[word_idx]
                    phrase_words.append(WordSegment(
                        text=ws["text"],
                        start_ms=ws["startMs"],
                        end_ms=ws["endMs"],
                    ))

            if phrase_words:
                phrase_captions.append(AlignedCaption(
                    text=phrase,
                    start_ms=phrase_words[0].start_ms,
                    end_ms=phrase_words[-1].end_ms,
                    words=phrase_words,
                ))

        return phrase_captions

    def _align_sync(
        self,
        audio_path: str,
        text: str,
        language: str,
        phrase_level: bool,
    ) -> list[AlignedCaption]:
        """Synchronous alignment (for executor)."""
        aligner = self._load_aligner()

        logger.info(f"Aligning text to audio: {audio_path}")

        # Get alignment from model
        results = aligner.align(
            audio=audio_path,
            text=text,
            language=language,
        )

        # Build character/word-level segments
        char_segments = []
        for char in results[0]:
            char_segments.append({
                "text": char.text,
                "startMs": int(char.start_time * 1000),
                "endMs": int(char.end_time * 1000),
            })

        # Group into proper words (especially for Chinese)
        logger.debug("Grouping into words...")
        word_segments = _group_chars_into_words(char_segments, text, language)

        # Sanitize zero-duration words (ensures min 50ms per word for captions)
        word_segments = _sanitize_word_segments(word_segments)
        logger.info(f"Aligned {len(char_segments)} chars -> {len(word_segments)} words")

        if not phrase_level:
            # Return word-level only
            return [
                AlignedCaption(
                    text=w["text"],
                    start_ms=w["startMs"],
                    end_ms=w["endMs"],
                    words=[WordSegment(w["text"], w["startMs"], w["endMs"])],
                )
                for w in word_segments
            ]

        # Group words into phrase-level captions
        phrases = _split_into_phrases(text, language)
        phrase_captions = []

        # Build clean text for position matching
        all_words_text = ""
        word_positions = []

        for i, w in enumerate(word_segments):
            wtext = w["text"]
            if re.match(r'^[,.!?;:"""()[\]{}\s]+$', wtext):
                continue
            start_pos = len(all_words_text)
            all_words_text += wtext
            word_positions.append((start_pos, len(all_words_text), i))

        # Clean script text
        script_clean = re.sub(r'[,.!?;:"""()[\]{}\s]', '', text)

        current_pos = 0
        for phrase in phrases:
            phrase_clean = re.sub(r'[,.!?;:"""()[\]{}\s]', '', phrase)
            phrase_start = current_pos
            phrase_end = phrase_start + len(phrase_clean)
            current_pos = phrase_end

            phrase_words = []
            for start_pos, end_pos, word_idx in word_positions:
                if start_pos < phrase_end and end_pos > phrase_start:
                    ws = word_segments[word_idx]
                    phrase_words.append(WordSegment(
                        text=ws["text"],
                        start_ms=ws["startMs"],
                        end_ms=ws["endMs"],
                    ))

            if phrase_words:
                phrase_captions.append(AlignedCaption(
                    text=phrase,
                    start_ms=phrase_words[0].start_ms,
                    end_ms=phrase_words[-1].end_ms,
                    words=phrase_words,
                ))

        return phrase_captions

    async def align_dialogue_lines(
        self,
        audio_paths: list[Path],
        texts: list[str],
        language: str = "English",
    ) -> list[AlignedCaption]:
        """
        Align multiple audio files with their corresponding text.

        Useful for multi-character dialogue where each line is a separate audio file.

        Args:
            audio_paths: List of audio file paths
            texts: List of corresponding text for each audio
            language: Language for alignment

        Returns:
            List of AlignedCaption, one per audio file
        """
        results = []
        time_offset = 0

        for audio_path, text in zip(audio_paths, texts):
            captions = await self.align_audio(
                audio_path, text, language, phrase_level=False
            )

            # Offset timestamps to account for concatenated position
            for caption in captions:
                adjusted = AlignedCaption(
                    text=caption.text,
                    start_ms=caption.start_ms + time_offset,
                    end_ms=caption.end_ms + time_offset,
                    words=[
                        WordSegment(
                            text=w.text,
                            start_ms=w.start_ms + time_offset,
                            end_ms=w.end_ms + time_offset,
                        )
                        for w in caption.words
                    ]
                )
                results.append(adjusted)

            # Update offset for next audio
            if captions:
                time_offset = results[-1].end_ms

        return results
