"""
Test VoiceDesign → Clone pattern for consistent multi-character TTS.

Usage:
    python test_voice_clone.py              # Full test (design + clone dialogue)
    python test_voice_clone.py --design     # Only voice design step
    python test_voice_clone.py --dialogue   # Only dialogue (requires prior --design)
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from skills.qwen_tts.qwen_tts import QwenTTS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


CHARACTER_PERSONAS = {
    "Mochi": (
        "A cheerful young girl with a high-pitched, excited and curious tone. "
        "She speaks with lots of energy and wonder."
    ),
    "Hero": (
        "A brave young man with a confident, warm baritone voice. "
        "He speaks calmly but with determination."
    ),
}

DIALOGUE = [
    ("Mochi", "Oh wow, what's that shiny thing over there?"),
    ("Hero", "Careful, Mochi. It looks like an old treasure map!"),
    ("Mochi", "A treasure map! Let's go find it right now!"),
    ("Hero", "Alright, but stay close. We don't know what's out there."),
    ("Mochi", "This is going to be the best adventure ever!"),
    ("Hero", "I have to admit, your excitement is contagious."),
]


async def test_voice_design():
    """Test voice design + clone prompt creation."""
    tts = QwenTTS(mode="torch")

    print("\n=== Step 1: Designing character voices ===")
    voices = await tts.initialize_character_voices(CHARACTER_PERSONAS)

    for name, voice in voices.items():
        print(f"  {name}: ref_audio={voice.ref_audio.shape}, sr={voice.sample_rate}")
        print(f"    clone_prompt items: {len(voice.clone_prompt)}")

    print("\n=== Voice design complete ===")
    return tts


async def test_dialogue(tts: QwenTTS = None):
    """Test multi-character dialogue generation."""
    if tts is None:
        tts = QwenTTS(mode="torch")
        # Need to initialize voices first
        await tts.initialize_character_voices(CHARACTER_PERSONAS)

    print("\n=== Step 2: Generating dialogue ===")
    results = await tts.generate_dialogue(
        dialogue_lines=DIALOGUE,
        character_personas=CHARACTER_PERSONAS,
        language="en",
    )

    print("\n=== Results ===")
    for i, result in enumerate(results):
        speaker, text = DIALOGUE[i]
        print(f"  [{speaker}] \"{text}\"")
        print(f"    → {result.audio_path} ({result.duration_seconds:.1f}s)")

    print(f"\nTotal: {len(results)} audio files generated")
    print(f"Output dir: {results[0].audio_path.parent}")


async def main():
    args = sys.argv[1:]

    if "--design" in args:
        await test_voice_design()
    elif "--dialogue" in args:
        await test_dialogue()
    else:
        # Full test
        tts = await test_voice_design()
        await test_dialogue(tts)


if __name__ == "__main__":
    asyncio.run(main())
