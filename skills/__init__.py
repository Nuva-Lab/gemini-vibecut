"""
Skills - Composable capabilities for the Creative Agent.

Each skill is a directory containing:
- SKILL.md: Metadata with YAML frontmatter + detailed instructions
- skill_name.py: Implementation

Following Anthropic's agent skills pattern:
https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
"""

from pathlib import Path

# Skill directories
SKILLS_DIR = Path(__file__).parent

# Import skills from subdirectories
from .understand_image.understand_image import ImageUnderstanding
from .generate_character.generate_character import CharacterGenerator
from .generate_manga.generate_manga import MangaGenerator, MangaPanel, MangaResult, StreamEvent
from .generate_tts.generate_tts import TTSGenerator, TTSResult
from .generate_video.generate_video import VideoGenerator, VideoClipResult
from .generate_music.generate_music import MusicGenerator

from .generate_music.elevenlabs_music import ElevenLabsMusicGenerator
from .compose_final.compose_final import VideoComposer
from .generate_animated_story.generate_animated_story import (
    AnimatedStoryGenerator,
    AnimatedStoryResult,
    AnimationStreamEvent,
)
from .generate_animated_story.storyboard_planner import LyricsResult

# New skills for dialogue pipeline
from .qwen_tts.qwen_tts import QwenTTS, TTSResult as QwenTTSResult
from .align_captions.align_captions import CaptionAligner, AlignedCaption, WordSegment
from .render_captions.render_captions import CaptionRenderer, CaptionSegment

# Verification
from .verify_output import verify_video, VerificationResult

__all__ = [
    "ImageUnderstanding",
    "CharacterGenerator",
    "MangaGenerator",
    "MangaPanel",
    "MangaResult",
    "StreamEvent",
    "TTSGenerator",
    "TTSResult",
    "VideoGenerator",
    "VideoClipResult",
    "MusicGenerator",
    "ElevenLabsMusicGenerator",
    "VideoComposer",
    "AnimatedStoryGenerator",
    "AnimatedStoryResult",
    "AnimationStreamEvent",
    "LyricsResult",
    # Dialogue pipeline
    "QwenTTS",
    "QwenTTSResult",
    "CaptionAligner",
    "AlignedCaption",
    "WordSegment",
    "CaptionRenderer",
    "CaptionSegment",
    # Verification
    "verify_video",
    "VerificationResult",
    "SKILLS_DIR",
]


def list_skills() -> list[dict]:
    """
    List all available skills with their metadata.

    Returns list of dicts with name, description, and path.
    """
    import yaml

    skills = []
    for skill_dir in SKILLS_DIR.iterdir():
        if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                content = skill_md.read_text()
                # Extract YAML frontmatter
                if content.startswith("---"):
                    end = content.find("---", 3)
                    if end > 0:
                        frontmatter = content[3:end].strip()
                        try:
                            metadata = yaml.safe_load(frontmatter)
                            skills.append({
                                "name": metadata.get("name", skill_dir.name),
                                "description": metadata.get("description", ""),
                                "triggers": metadata.get("triggers", []),
                                "keywords": metadata.get("keywords", []),
                                "path": str(skill_dir),
                            })
                        except yaml.YAMLError:
                            pass
    return skills


def get_skill_context() -> str:
    """
    Get skill summaries for agent system prompt (Level 1 context).

    Returns formatted string with name + description for each skill.
    """
    skills = list_skills()
    lines = ["## Available Skills\n"]
    for skill in skills:
        lines.append(f"- **{skill['name']}**: {skill['description']}")
    return "\n".join(lines)
