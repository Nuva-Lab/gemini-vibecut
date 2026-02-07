#!/usr/bin/env python3
"""
Test the full dialogue pipeline: TTS → Alignment → Video → Captions
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dataclasses import dataclass
from skills.generate_manga.generate_manga import MangaResult, MangaPanel
from skills.generate_animated_story import AnimatedStoryGenerator


# Create a mock MangaResult with dialogue
def create_test_manga() -> MangaResult:
    """Create a test manga with dialogue for testing."""
    manga_dir = Path(__file__).parent / "assets" / "outputs" / "manga"

    # Use most recent panels (10231fd9)
    manga_id = "10231fd9"

    panels = [
        MangaPanel(
            index=0,
            story_beat="Mochi discovers something exciting",
            dialogue="Mochi: Wow, what's this shiny thing?",
            image_path=manga_dir / f"{manga_id}_panel_1.png",
            image_url=f"/assets/outputs/manga/{manga_id}_panel_1.png",
        ),
        MangaPanel(
            index=1,
            story_beat="Hero joins the adventure",
            dialogue="Hero: It looks like a treasure map!",
            image_path=manga_dir / f"{manga_id}_panel_2.png",
            image_url=f"/assets/outputs/manga/{manga_id}_panel_2.png",
        ),
        MangaPanel(
            index=2,
            story_beat="They set off together",
            dialogue="Mochi: Let's go on an adventure!",
            image_path=manga_dir / f"{manga_id}_panel_3.png",
            image_url=f"/assets/outputs/manga/{manga_id}_panel_3.png",
        ),
        MangaPanel(
            index=3,
            story_beat="The journey begins",
            dialogue="Hero: Together we can do anything!",
            image_path=manga_dir / f"{manga_id}_panel_4.png",
            image_url=f"/assets/outputs/manga/{manga_id}_panel_4.png",
        ),
    ]

    # Verify panels exist
    for panel in panels:
        if not panel.image_path.exists():
            print(f"Warning: Panel not found: {panel.image_path}")

    return MangaResult(
        manga_id=manga_id,
        character_name="Mochi",
        style="manga",
        panels=panels,
    )


async def test_tts_only():
    """Test just the TTS generation."""
    print("\n=== Testing TTS Only (Cloud Mode) ===")
    from skills.qwen_tts import QwenTTS

    tts = QwenTTS(mode="cloud")
    result = await tts.generate_speech(
        text="Hello! This is a test of the Qwen TTS system.",
        output_path=Path("test_tts_output.wav"),
    )
    print(f"TTS Result: {result.audio_path} ({result.duration_seconds:.2f}s)")
    return result


async def test_local_tts():
    """Test local TTS with persona instruction."""
    print("\n=== Testing Local TTS with Persona ===")
    from skills.qwen_tts import QwenTTS

    tts = QwenTTS(mode="local")
    result = await tts.generate_speech(
        text="Hello! This is a test of the local Qwen TTS system with persona.",
        instruct="A cheerful young woman with an excited and curious tone",
        output_path=Path("test_local_tts.wav"),
    )
    print(f"Local TTS Result: {result.audio_path} ({result.duration_seconds:.2f}s)")
    return result


async def test_alignment(audio_path: Path, text: str):
    """Test caption alignment."""
    print("\n=== Testing Alignment ===")
    from skills.align_captions import CaptionAligner

    aligner = CaptionAligner(device="cpu")
    captions = await aligner.align_audio(
        audio_path=audio_path,
        text=text,
        language="English",
        phrase_level=False,
    )

    print(f"Aligned {len(captions)} segments:")
    for cap in captions[:5]:
        print(f"  [{cap.start_ms}-{cap.end_ms}ms] {cap.text}")

    return captions


async def test_full_pipeline(tts_mode: str = "torch"):
    """Test the full animated story with dialogue pipeline."""
    print(f"\n=== Testing Full Pipeline (TTS: {tts_mode}, Veo: fast) ===")

    manga = create_test_manga()
    print(f"Manga ID: {manga.manga_id}")
    print(f"Panels: {len(manga.panels)}")
    for p in manga.panels:
        exists = "✓" if p.image_path.exists() else "✗"
        print(f"  [{exists}] Panel {p.index + 1}: {p.dialogue[:40]}...")

    gen = AnimatedStoryGenerator()

    # Character personas for voice design
    character_personas = {
        "Mochi": "A cheerful young girl with a high-pitched, excited and curious tone",
        "Hero": "A brave young man with a confident, warm baritone voice",
    }

    print(f"\nStarting pipeline (tts_mode={tts_mode})...")
    print(f"  Mochi: {character_personas['Mochi']}")
    print(f"  Hero: {character_personas['Hero']}")

    async for event in gen.generate_animated_story_with_dialogue_streaming(
        manga_result=manga,
        character_personas=character_personas,
        enable_captions=True,  # Karaoke captions via Remotion
        language="English",
        clip_duration=4,
        tts_mode=tts_mode,
    ):
        if event.type == 'start':
            print(f"Started: {event.data.get('mode')} mode")
        elif event.type == 'tts_progress':
            print(f"TTS: {event.data.get('message')}")
        elif event.type == 'align_progress':
            print(f"Align: {event.data.get('message')}")
        elif event.type == 'video_progress':
            print(f"Video: {event.data.get('message')}")
        elif event.type == 'caption_progress':
            print(f"Captions: {event.data.get('message')}")
        elif event.type == 'compose':
            print(f"Compose: {event.data.get('message')}")
        elif event.type == 'complete':
            verified = event.data.get('verified')
            print(f"\n{'✓' if verified else '⚠'} Complete! (verified={verified})")
            print(f"  Video: {event.data.get('final_video_path')}")
            print(f"  Duration: {event.data.get('total_duration')}s (actual: {event.data.get('actual_duration')}s)")
            print(f"  Resolution: {event.data.get('actual_resolution')}")
            print(f"  Has dialogue: {event.data.get('has_dialogue')}")
            print(f"  Has captions: {event.data.get('has_captions')}")
            if not verified:
                print(f"  Failures: {event.data.get('verification_failures')}")
        elif event.type == 'error':
            print(f"\n✗ Error: {event.data.get('message')}")


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tts", action="store_true", help="Test cloud TTS only")
    parser.add_argument("--local", action="store_true", help="Test local TTS with persona")
    parser.add_argument("--align", action="store_true", help="Test alignment (after TTS)")
    parser.add_argument("--full", action="store_true", help="Full pipeline (torch TTS + Veo fast)")
    parser.add_argument("--full-local", action="store_true", help="Full pipeline with local mlx TTS")
    parser.add_argument("--tts-mode", default="torch", help="TTS mode for --full (torch/local/cloud)")
    args = parser.parse_args()

    if args.tts:
        await test_tts_only()
    elif args.local:
        await test_local_tts()
    elif args.align:
        tts_result = await test_local_tts()
        await test_alignment(tts_result.audio_path, tts_result.text)
    elif args.full:
        await test_full_pipeline(tts_mode=args.tts_mode)
    elif args.full_local:
        await test_full_pipeline(tts_mode="local")
    else:
        print("Usage: python test_dialogue_pipeline.py [--tts | --local | --align | --full]")
        print("  --full          Full pipeline with torch TTS (VoiceDesign → Clone)")
        print("  --full-local    Full pipeline with local mlx TTS")
        print("  --tts-mode X    Override TTS mode for --full (torch/local/cloud)")
        print("\nRunning torch TTS test by default...")
        await test_full_pipeline(tts_mode="torch")


if __name__ == "__main__":
    asyncio.run(main())
