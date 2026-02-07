#!/usr/bin/env python3
"""
End-to-end test simulating exact web flow.

User input: "cat and dog going fishing together (use existing character library)"
"""

import asyncio
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from google import genai
from google.genai import types
from config import GOOGLE_API_KEY, GEMINI_MODEL, VEO_MODEL, OUTPUT_DIR
from skills.generate_manga.generate_manga import MangaGenerator

# Simulate existing character library (most recent character sheets)
CHARACTER_LIBRARY = {
    "Mochi": {
        "path": Path("assets/outputs/characters/18a428c6_full_body.png"),
        "type": "pet",
        "persona": "playful golden retriever",
    },
    "Whiskers": {
        "path": Path("assets/outputs/characters/78aff4d7_full_body.png"),
        "type": "pet",
        "persona": "curious orange tabby cat",
    },
}

USER_STORY_CONCEPT = "cat and dog going fishing together"


async def step1_generate_story_beats():
    """Use Gemini to generate 4 story beats from user concept."""
    print("\n" + "=" * 60)
    print("STEP 1: Generate Story Beats")
    print("=" * 60)
    print(f"User concept: {USER_STORY_CONCEPT}")
    print()

    client = genai.Client(api_key=GOOGLE_API_KEY)

    prompt = f"""You are a creative storytelling assistant. Generate 4 sequential story beats for a short manga/comic.

USER CONCEPT: {USER_STORY_CONCEPT}

CHARACTERS:
- Mochi: A playful golden retriever
- Whiskers: A curious orange tabby cat

Generate exactly 4 story beats that tell a complete mini-story with:
1. Setup/Introduction
2. Rising action
3. Climax/Fun moment
4. Resolution/Ending

For each beat, include:
- Camera angle suggestion (wide shot, close-up, medium shot, etc.)
- Brief dialogue if appropriate

Format as JSON:
{{
    "story_beats": [
        {{"beat": "Wide shot: Description...", "dialogue": "Character: Line..."}},
        ...
    ]
}}"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=1.0,
            response_mime_type="application/json",
        ),
    )

    import json
    result = json.loads(response.text)

    print("Generated story beats:")
    for i, beat in enumerate(result["story_beats"]):
        print(f"  {i+1}. {beat['beat'][:60]}...")
        if beat.get('dialogue'):
            print(f"     → {beat['dialogue'][:40]}...")

    return result["story_beats"]


async def step2_generate_manga(story_beats):
    """Generate 4 manga panels using MangaGenerator."""
    print("\n" + "=" * 60)
    print("STEP 2: Generate Manga Panels")
    print("=" * 60)

    # Prepare character refs (like web would)
    character_refs = []
    for name, data in CHARACTER_LIBRARY.items():
        if data["path"].exists():
            character_refs.append({
                "name": name,
                "path": str(data["path"]),
            })
            print(f"  Character: {name} → {data['path'].name}")

    if len(character_refs) < 2:
        print("ERROR: Need at least 2 characters")
        return None

    # Extract beats and dialogues
    beats = [b["beat"] for b in story_beats]
    dialogues = [b.get("dialogue", "") for b in story_beats]

    generator = MangaGenerator()
    panels = []

    async for event in generator.generate_manga_streaming(
        character_refs=character_refs[:2],  # Max 2 characters
        story_beats=beats,
        dialogues=dialogues,
        style="manga",
    ):
        if event.type == 'start':
            print(f"\n  Started manga generation: {event.data.get('manga_id')}")
        elif event.type == 'progress':
            print(f"  Generating panel {event.data.get('panel_index')}/{event.data.get('total')}...")
        elif event.type == 'panel':
            # Event data has: panel_index, image_url, story_beat, dialogue
            idx = event.data.get('panel_index', len(panels) + 1)
            image_url = event.data.get('image_url', '')
            # Convert URL to path: /assets/outputs/manga/xxx.png -> assets/outputs/manga/xxx.png
            image_path = Path(image_url.lstrip('/')) if image_url else None

            print(f"  ✓ Panel {idx} saved: {image_path.name if image_path else 'unknown'}")

            from skills.generate_manga.generate_manga import MangaPanel
            panels.append(MangaPanel(
                index=idx - 1,
                story_beat=event.data.get('story_beat', ''),
                dialogue=event.data.get('dialogue', ''),
                image_path=image_path,
                image_url=image_url,
            ))
        elif event.type == 'complete':
            print(f"\n  Manga complete! {len(panels)} panels generated")
        elif event.type == 'error':
            print(f"  ERROR: {event.data.get('message')}")
            return None

    return panels


async def step3_generate_interpolation_clips(panels):
    """Generate video clips using first+last frame interpolation."""
    print("\n" + "=" * 60)
    print("STEP 3: Generate Video Clips (Interpolation Mode)")
    print("=" * 60)

    if len(panels) < 2:
        print("ERROR: Need at least 2 panels")
        return []

    client = genai.Client(api_key=GOOGLE_API_KEY)
    output_dir = OUTPUT_DIR / "videos"
    output_dir.mkdir(parents=True, exist_ok=True)

    clips = []

    # Generate transitions between consecutive panels
    for i in range(len(panels) - 1):
        first_panel = panels[i]
        last_panel = panels[i + 1]

        print(f"\n  Clip {i+1}: Panel {i+1} → Panel {i+2}")
        print(f"    First: {first_panel.image_path.name}")
        print(f"    Last: {last_panel.image_path.name}")

        # Load images
        first_image = types.Image.from_file(location=str(first_panel.image_path))
        last_image = types.Image.from_file(location=str(last_panel.image_path))

        prompt = f"""Smoothly animate between the first and last frame.

SCENE CONTEXT:
First frame: {first_panel.story_beat}
Last frame: {last_panel.story_beat}

ANIMATION STYLE:
- Smooth, fluid transition between poses
- Maintain character appearance exactly (golden retriever + orange tabby cat)
- Natural motion, no jarring jumps
- Subtle ambient animation (breathing, fur movement, water ripples)

AUDIO:
- Peaceful nature sounds (water, birds, wind)
- NO speech, NO dialogue, NO vocals
- NO background music"""

        print(f"    Starting Veo interpolation...")

        try:
            operation = client.models.generate_videos(
                model=VEO_MODEL,
                prompt=prompt,
                image=first_image,
                config=types.GenerateVideosConfig(
                    aspect_ratio="9:16",
                    last_frame=last_image,
                ),
            )

            # Poll for completion
            start_time = time.time()
            while not operation.done:
                elapsed = time.time() - start_time
                print(f"    Waiting... ({elapsed:.0f}s)")
                await asyncio.sleep(10)
                operation = client.operations.get(operation)

            if not operation.response or not operation.response.generated_videos:
                print(f"    ERROR: No video generated")
                continue

            # Save video
            video = operation.response.generated_videos[0]
            video_id = str(uuid.uuid4())[:8]
            output_path = output_dir / f"fishing_clip{i+1}_{video_id}.mp4"

            client.files.download(file=video.video)
            video.video.save(str(output_path))

            elapsed = time.time() - start_time
            print(f"    ✓ Saved: {output_path.name} ({elapsed:.0f}s)")
            clips.append(output_path)

        except Exception as e:
            print(f"    ERROR: {e}")
            continue

    return clips


async def step4_open_results(panels, clips):
    """Open all generated content for review."""
    print("\n" + "=" * 60)
    print("STEP 4: Opening Results")
    print("=" * 60)

    import subprocess

    # Open panels
    print("\nPanels:")
    for panel in panels:
        print(f"  {panel.image_path.name}")
        subprocess.run(["open", str(panel.image_path)])
        await asyncio.sleep(0.5)

    # Open clips
    print("\nVideo clips:")
    for clip in clips:
        print(f"  {clip.name}")
        subprocess.run(["open", str(clip)])
        await asyncio.sleep(1)


async def main():
    """Run full web flow simulation."""
    print("=" * 60)
    print("WEB FLOW SIMULATION")
    print(f"User input: \"{USER_STORY_CONCEPT}\"")
    print("=" * 60)

    # Step 1: Generate story beats
    story_beats = await step1_generate_story_beats()

    # Step 2: Generate manga panels
    panels = await step2_generate_manga(story_beats)
    if not panels:
        print("\nFailed at manga generation")
        return

    # Step 3: Generate interpolation clips
    clips = await step3_generate_interpolation_clips(panels)

    # Step 4: Open results
    await step4_open_results(panels, clips)

    print("\n" + "=" * 60)
    print("COMPLETE!")
    print(f"  Panels: {len(panels)}")
    print(f"  Clips: {len(clips)}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
