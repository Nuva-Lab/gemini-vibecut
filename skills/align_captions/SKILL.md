---
name: Caption Alignment
description: Align text to audio timestamps using Qwen3-ForcedAligner (~30ms precision)
triggers:
  - Karaoke captions
  - Word-level timestamps
  - Subtitle synchronization
---

# Caption Alignment Skill

Align text to audio timestamps for karaoke-style rolling captions.

## Usage

```python
from skills.align_captions import CaptionAligner

aligner = CaptionAligner()

# Single audio file
captions = await aligner.align_audio(
    audio_path=Path("speech.wav"),
    text="Hello world!",
    language="English",
)
# Returns list of AlignedCaption with word-level timing

# Multi-file dialogue
captions = await aligner.align_dialogue_lines(
    audio_paths=[Path("line1.wav"), Path("line2.wav")],
    texts=["Hello!", "Hi there!"],
)
```

## Output Format

```python
@dataclass
class WordSegment:
    text: str
    start_ms: int
    end_ms: int

@dataclass
class AlignedCaption:
    text: str        # Phrase text
    start_ms: int    # Phrase start
    end_ms: int      # Phrase end
    words: list[WordSegment]  # Word-level timing for karaoke
```

## Dependencies

- qwen-asr (Qwen3-ForcedAligner)
- jieba (for Chinese word segmentation)
- torch

## Install

```bash
pip install qwen-asr jieba torch
```
