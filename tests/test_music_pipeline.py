#!/usr/bin/env python3
"""
Test the ElevenLabs music + rolling lyrics pipeline.

Usage:
    python tests/test_music_pipeline.py --music-only   # ElevenLabs generation only
    python tests/test_music_pipeline.py --lyrics-only   # Gemini lyrics generation only
    python tests/test_music_pipeline.py --full          # Full pipeline (Veo + ElevenLabs + lyrics)
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path (tests/ is one level down)
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from skills.generate_manga.generate_manga import MangaResult, MangaPanel
from skills.generate_animated_story import AnimatedStoryGenerator


def create_test_manga() -> MangaResult:
    """Create a test manga with dialogue for testing."""
    manga_dir = Path(__file__).parent.parent / "assets" / "outputs" / "manga"

    # Use most recent panels
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


async def test_music_only():
    """Test ElevenLabs music generation alone."""
    print("\n=== Testing ElevenLabs Music Generation ===")

    from skills.generate_music.elevenlabs_music import ElevenLabsMusicGenerator

    try:
        gen = ElevenLabsMusicGenerator()
    except ValueError as e:
        print(f"ERROR: {e}")
        print("Set ELEVENLABS_API_KEY in your .env file")
        return

    print("Generating music...")

    result = await gen.generate_music(
        prompt="upbeat anime pop, piano, electronic drums, synth bass, female vocals, energetic, bright, full instrumentation from first beat, 125 BPM",
        lyrics=(
            "[Verse 1]\n"
            "Running through the morning light\n"
            "Every color shining bright\n"
            "[Verse 2]\n"
            "Following the winding road\n"
            "Carrying our heavy load\n"
            "[Chorus]\n"
            "We can fly together now\n"
            "Nothing gonna hold us down\n"
            "[Outro]\n"
            "Stars are shining just for us\n"
            "This is where our story starts"
        ),
        duration=16,
        clip_duration=4,
        vocal_style="energetic",
        negative_tags="slow, dark, heavy metal, sad, spoken word, silence, slow intro, fade in, sparse, thin",
        bpm=125,
    )

    print(f"Music saved: {result.audio_path}")
    print(f"Duration: {result.duration_seconds:.1f}s")
    print(f"Tags: {result.tags}")
    return result


async def test_lyrics_only():
    """Test Gemini lyrics generation."""
    print("\n=== Testing Lyrics Generation ===")

    from skills.generate_animated_story.storyboard_planner import StoryboardPlanner

    manga = create_test_manga()
    planner = StoryboardPlanner()

    result = await planner.generate_lyrics_and_tags(
        panels=manga.panels,
        character_name="Mochi",
        story_summary="Mochi the golden retriever and Hero discover a treasure map and go on an adventure.",
    )

    print(f"Mood: {result.mood}")
    print(f"BPM: {result.bpm}")
    print(f"Vocal style: {result.vocal_style}")
    print(f"Tags: {result.tags}")
    print(f"Negative: {result.negative_tags}")
    print(f"Lyrics:\n{result.lyrics}")

    # Validate couplet structure (2 lines per panel)
    import re
    lines = [l.strip() for l in result.lyrics.splitlines()
             if l.strip() and not re.match(r'^\[.*\]$', l.strip())]
    print(f"\nValidation:")
    print(f"  Lines: {len(lines)} (expected: 8, couplet structure)")
    for i, line in enumerate(lines):
        word_count = len(line.split())
        status = "OK" if 3 <= word_count <= 6 else "WARN"
        panel_num = (i // 2) + 1
        line_in_panel = (i % 2) + 1
        print(f"  [{status}] Panel {panel_num}, Line {line_in_panel}: '{line}' ({word_count} words)")
    if len(lines) != 8:
        print(f"  WARNING: Expected 8 lines (2 per panel couplet), got {len(lines)}")
    if hasattr(result, 'panel_local_styles') and result.panel_local_styles:
        print(f"  Section styles: {len(result.panel_local_styles)} sections")
        for i, styles in enumerate(result.panel_local_styles):
            print(f"    Section {i+1}: {styles}")

    return result


async def test_full_pipeline():
    """Test the full music pipeline: Veo clips + ElevenLabs + lyrics + captions."""
    print("\n=== Testing Full Music Pipeline ===")

    manga = create_test_manga()
    print(f"Manga ID: {manga.manga_id}")
    print(f"Panels: {len(manga.panels)}")
    for p in manga.panels:
        exists = "Y" if p.image_path.exists() else "N"
        print(f"  [{exists}] Panel {p.index + 1}: {p.story_beat}")

    story_gen = AnimatedStoryGenerator()

    print("\nStarting music pipeline (Veo + ElevenLabs in parallel)...")

    async for event in story_gen.generate_animated_story_with_music_streaming(
        manga_result=manga,
        character_name="Mochi",
        story_summary="Mochi the golden retriever and Hero discover a treasure map and go on an adventure.",
        enable_lyrics=True,
        clip_duration=4,
    ):
        if event.type == 'start':
            print(f"Started: {event.data.get('mode')} mode, {event.data.get('total_duration')}s expected")
        elif event.type == 'lyrics_progress':
            msg = event.data.get('message', '')
            print(f"Lyrics: {msg}")
            if 'lyrics' in event.data:
                print(f"  Tags: {event.data.get('tags')}")
                lines = event.data['lyrics'].splitlines()
                for line in lines[:4]:
                    print(f"  {line}")
                if len(lines) > 4:
                    print(f"  ... ({len(lines)} lines total)")
        elif event.type == 'video_progress':
            print(f"Video: {event.data.get('message')}")
        elif event.type == 'music_progress':
            print(f"Music: {event.data.get('message')}")
        elif event.type == 'caption_progress':
            print(f"Captions: {event.data.get('message')}")
        elif event.type == 'compose':
            print(f"Compose: {event.data.get('message')}")
        elif event.type == 'complete':
            verified = event.data.get('verified')
            symbol = "Y" if verified else "!"
            print(f"\n[{symbol}] Complete! (verified={verified})")
            print(f"  Video: {event.data.get('final_video_path')}")
            print(f"  Duration: {event.data.get('total_duration')}s (actual: {event.data.get('actual_duration')}s)")
            print(f"  Resolution: {event.data.get('actual_resolution')}")
            print(f"  Has music: {event.data.get('has_music')}")
            print(f"  Has lyrics: {event.data.get('has_lyrics')}")
            print(f"  Music tags: {event.data.get('music_tags')}")
            if not verified:
                print(f"  Failures: {event.data.get('verification_failures')}")
        elif event.type == 'error':
            print(f"\n[X] Error: {event.data.get('message')}")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Test ElevenLabs music pipeline")
    parser.add_argument("--music-only", action="store_true", help="Test ElevenLabs music generation")
    parser.add_argument("--lyrics-only", action="store_true", help="Test lyrics generation only")
    parser.add_argument("--full", action="store_true", help="Full pipeline (Veo + ElevenLabs + lyrics)")
    args = parser.parse_args()

    if args.music_only:
        await test_music_only()
    elif args.lyrics_only:
        await test_lyrics_only()
    elif args.full:
        await test_full_pipeline()
    else:
        print("Usage: python tests/test_music_pipeline.py [--music-only | --lyrics-only | --full]")
        print("  --music-only   Test ElevenLabs music generation")
        print("  --lyrics-only  Test Gemini lyrics generation")
        print("  --full         Full pipeline (Veo + ElevenLabs + lyrics + captions)")


if __name__ == "__main__":
    asyncio.run(main())
