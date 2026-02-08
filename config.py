"""
Configuration for Gemini VibeCut.

Model Selection:
- Default: gemini-3-flash-preview (fast, cost-effective)
- Optional: gemini-3-pro-preview (better quality, set USE_PRO_MODEL=true)

API Access:
- Development: Google AI Studio (GOOGLE_API_KEY)
- Production: Vertex AI (GOOGLE_CLOUD_PROJECT + service account)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# Model Configuration
# =============================================================================

# Model selection flag: set USE_PRO_MODEL=true for better quality
USE_PRO_MODEL = os.getenv("USE_PRO_MODEL", "false").lower() == "true"

# Gemini model IDs
GEMINI_FLASH_MODEL = "gemini-3-flash-preview"
GEMINI_PRO_MODEL = "gemini-3-pro-preview"
GEMINI_MODEL = GEMINI_PRO_MODEL if USE_PRO_MODEL else GEMINI_FLASH_MODEL

# Lyrics always use Pro for higher quality storytelling (small context, low thinking)
GEMINI_LYRICS_MODEL = GEMINI_PRO_MODEL

# Generation model IDs
# Nano Banana Pro (Gemini 3 Pro Image) - supports 2K resolution and interleaved output
NANO_BANANA_MODEL = os.getenv("NANO_BANANA_MODEL", "gemini-3-pro-image-preview")
NANO_BANANA_RESOLUTION = "2K"  # Options: 1K, 2K, 4K
# Veo 3.1 fast for prototyping, switch to veo-3.1-generate-preview for final quality
VEO_MODEL = os.getenv("VEO_MODEL", "veo-3.1-fast-generate-preview")
TTS_MODEL = os.getenv("TTS_MODEL", "gemini-2.5-pro-preview-tts")

# =============================================================================
# API Configuration
# =============================================================================

# Google AI Studio (for development/prototyping)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Vertex AI (for production)
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
USE_VERTEX_AI = os.getenv("USE_VERTEX_AI", "false").lower() == "true"


def get_gemini_client():
    """
    Get the appropriate Gemini client based on configuration.

    Returns either AI Studio client or Vertex AI client.
    """
    if USE_VERTEX_AI:
        # Use Vertex AI
        from google.cloud import aiplatform
        from vertexai.generative_models import GenerativeModel

        aiplatform.init(
            project=GOOGLE_CLOUD_PROJECT,
            location=GOOGLE_CLOUD_LOCATION,
        )
        return GenerativeModel(GEMINI_MODEL)
    else:
        # Use AI Studio
        from google import genai

        if not GOOGLE_API_KEY:
            raise ValueError(
                "GOOGLE_API_KEY not set. Either set GOOGLE_API_KEY for AI Studio, "
                "or set USE_VERTEX_AI=true with GOOGLE_CLOUD_PROJECT for Vertex AI."
            )
        return genai.Client(api_key=GOOGLE_API_KEY)


# =============================================================================
# Paths
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.resolve()  # Always absolute
ASSETS_DIR = PROJECT_ROOT / "assets"
# Always resolve OUTPUT_DIR relative to PROJECT_ROOT, not CWD
_output_env = os.getenv("OUTPUT_DIR")
if _output_env:
    OUTPUT_DIR = (PROJECT_ROOT / _output_env).resolve()
else:
    OUTPUT_DIR = ASSETS_DIR / "outputs"
SKILLS_DIR = PROJECT_ROOT / "skills"

# Asset subdirectories
PETS_DIR = ASSETS_DIR / "pets"
PEOPLE_DIR = ASSETS_DIR / "people"
WORLDS_DIR = ASSETS_DIR / "worlds"

# Ensure directories exist
for dir_path in [OUTPUT_DIR, PETS_DIR, PEOPLE_DIR, WORLDS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# =============================================================================
# Generation Settings
# =============================================================================

# Character generation
CHARACTER_STYLES = [
    "anime",
    "studio_ghibli",
    "cyberpunk_anime",
    "watercolor_anime",
    "chibi",
]

DEFAULT_CHARACTER_STYLE = "anime"

# Video generation
VIDEO_DURATION_SECONDS = 10
VIDEO_RESOLUTION = (1080, 1920)  # 9:16 vertical for social
VIDEO_FPS = 24

# Video clip duration constraints (for TTS sync)
MIN_CLIP_DURATION_SECONDS = 2.0   # Minimum duration for Veo clips
MAX_CLIP_DURATION_SECONDS = 8.0   # Maximum duration per clip

# Music generation
MUSIC_DURATION_SECONDS = 30
MUSIC_STYLES = [
    "adventurous_orchestral",
    "chill_lofi",
    "epic_cinematic",
    "cute_playful",
    "mysterious_ambient",
]

# =============================================================================
# Agent Settings
# =============================================================================

# Temperature for ALL Gemini calls - ALWAYS 1.0
# Project convention: never change temperature, always use 1.0
TEMPERATURE_UNDERSTANDING = 1
TEMPERATURE_CREATIVE = 1
TEMPERATURE_GENERATION = 1

# Max retries for API calls
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

# =============================================================================
# Logging
# =============================================================================

import logging

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# =============================================================================
# Print Configuration (for debugging)
# =============================================================================


def print_config():
    """Print current configuration for debugging."""
    print(f"""
Creative Universe Configuration
================================
Model: {GEMINI_MODEL} {"(Pro)" if USE_PRO_MODEL else "(Flash)"}
API Mode: {"Vertex AI" if USE_VERTEX_AI else "AI Studio"}
Project Root: {PROJECT_ROOT}
Output Dir: {OUTPUT_DIR}
Log Level: {LOG_LEVEL}
""")


if __name__ == "__main__":
    print_config()
