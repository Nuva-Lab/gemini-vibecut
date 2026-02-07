#!/usr/bin/env python3
"""Test the storyboard planner."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from skills.generate_animated_story.storyboard_planner import (
    StoryboardPlanner,
    build_veo_motion_prompt,
)
from skills.generate_manga.generate_manga import MangaPanel

# Test with existing assets
PANELS = [
    Path("assets/outputs/manga/1233de66_panel_1.png"),
    Path("assets/outputs/manga/1233de66_panel_2.png"),
    Path("assets/outputs/manga/1233de66_panel_3.png"),
    Path("assets/outputs/manga/1233de66_panel_4.png"),
]
CHARACTER_SHEET = Path("assets/outputs/characters/18a428c6_full_body.png")

# Mock panel data
MOCK_PANELS = [
    MangaPanel(index=0, story_beat="Wide shot: Character discovers a mysterious garden", dialogue="Mochi: Wow, what is this place?"),
    MangaPanel(index=1, story_beat="Close-up: Character examines a glowing flower", dialogue="Mochi: It's so beautiful..."),
    MangaPanel(index=2, story_beat="Medium shot: Character reaches toward the flower", dialogue=""),
    MangaPanel(index=3, story_beat="Close-up: Character's face lights up with wonder", dialogue="Mochi: Magic!"),
]


async def test_planner():
    """Test the storyboard planner."""
    print("=" * 60)
    print("Storyboard Planner Test")
    print("=" * 60)

    # Check assets
    valid_panels = [p for p in PANELS if p.exists()]
    print(f"Found {len(valid_panels)}/{len(PANELS)} panels")

    if not CHARACTER_SHEET.exists():
        print(f"ERROR: Character sheet not found: {CHARACTER_SHEET}")
        return

    print(f"Character sheet: {CHARACTER_SHEET.name}")
    print()

    planner = StoryboardPlanner()

    # Plan animation
    print("Planning animation...")
    print("-" * 40)

    plan = await planner.plan_animation(
        panels=MOCK_PANELS,
        panel_paths=valid_panels,
        character_sheets=[CHARACTER_SHEET],
        character_name="Mochi",
    )

    print(f"\nOverall mood: {plan.overall_mood}")
    print(f"Total duration: {plan.total_duration}s")
    print(f"Consistency notes: {plan.consistency_notes[:100]}...")
    print()

    print("Per-panel plans:")
    print("-" * 40)
    for pp in plan.panel_plans:
        print(f"\nPanel {pp.panel_index + 1}:")
        print(f"  Duration: {pp.duration_seconds}s")
        print(f"  Motion: {pp.motion_type}")
        print(f"  Camera: {pp.camera_movement}")
        print(f"  Subject motion: {pp.subject_motion}")
        print(f"  Emotion: {pp.emotion}")
        print(f"  Transition: {pp.transition_in} → {pp.transition_out}")

    # Test motion prompt building
    print("\n" + "=" * 60)
    print("Sample Veo Motion Prompt (Panel 1):")
    print("=" * 60)
    if plan.panel_plans:
        prompt = build_veo_motion_prompt(plan.panel_plans[0], plan.consistency_notes)
        print(prompt)

    return plan


if __name__ == "__main__":
    plan = asyncio.run(test_planner())
