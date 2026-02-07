"""
TTS Generation Skill - Gemini TTS for multi-speaker dialogue.

Generates speech audio from character dialogue with:
- Multi-speaker support (up to 2 characters)
- Consistent voice per character
- Duration tracking for Veo sync
- Expressive speech via emotion hints
"""

import asyncio
import logging
import uuid
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

from config import (
    GOOGLE_API_KEY,
    OUTPUT_DIR,
    TTS_MODEL,
)

logger = logging.getLogger(__name__)

# Audio format constants
SAMPLE_RATE = 24000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit


@dataclass
class TTSResult:
    """Result of TTS generation."""
    audio_path: Path
    duration_seconds: float
    voice_used: str
    character_name: str


# Available voices with their characteristics
VOICES = {
    # Energetic/Youthful
    "Leda": "youthful",
    "Zephyr": "bright",
    "Fenrir": "excitable",
    "Puck": "upbeat",
    # Calm/Warm
    "Aoede": "breezy",
    "Sulafat": "warm",
    "Enceladus": "breathy",
    "Achernar": "soft",
    # Confident/Informative
    "Kore": "firm",
    "Charon": "informative",
}

# Default voice mapping by character type (fallback)
DEFAULT_VOICE_MAP = {
    "pet": "Fenrir",      # Excitable for pets
    "cat": "Leda",        # Youthful for cats
    "dog": "Fenrir",      # Excitable for dogs
    "child": "Zephyr",    # Bright for children
    "adult": "Kore",      # Firm for adults
    "default": "Puck",    # Upbeat default
}

# Persona-based voice selection for pets
# Maps personality traits from character analysis to voice + default emotion
PET_PERSONALITY_MAP = {
    # High energy traits
    "playful": {"voice": "Fenrir", "emotion": "excited"},
    "mischievous": {"voice": "Puck", "emotion": "cheerful"},
    "energetic": {"voice": "Fenrir", "emotion": "excited"},
    "adventurous": {"voice": "Zephyr", "emotion": "excited"},
    "curious": {"voice": "Leda", "emotion": "curious"},
    "excitable": {"voice": "Fenrir", "emotion": "excited"},
    # Medium energy traits
    "friendly": {"voice": "Puck", "emotion": "cheerful"},
    "loyal": {"voice": "Sulafat", "emotion": "neutral"},
    "affectionate": {"voice": "Sulafat", "emotion": "cheerful"},
    # Low energy traits
    "calm": {"voice": "Aoede", "emotion": "neutral"},
    "dignified": {"voice": "Charon", "emotion": "neutral"},
    "wise": {"voice": "Charon", "emotion": "neutral"},
    "shy": {"voice": "Achernar", "emotion": "neutral"},
    "timid": {"voice": "Achernar", "emotion": "neutral"},
    "lazy": {"voice": "Enceladus", "emotion": "neutral"},
    "sleepy": {"voice": "Enceladus", "emotion": "neutral"},
}

# Archetype to voice mapping for people
ARCHETYPE_VOICE_MAP = {
    "loyal companion": "Puck",
    "mischievous trickster": "Fenrir",
    "wise mentor": "Charon",
    "brave hero": "Kore",
    "curious explorer": "Zephyr",
    "gentle soul": "Aoede",
    "mysterious stranger": "Enceladus",
    "cheerful friend": "Leda",
    "protagonist": "Kore",
    "sidekick": "Puck",
    "comic relief": "Fenrir",
}

# Energy level fallback voices
ENERGY_LEVEL_VOICES = {
    "very_high": {"voice": "Fenrir", "emotion": "excited"},
    "high": {"voice": "Puck", "emotion": "cheerful"},
    "medium": {"voice": "Leda", "emotion": "neutral"},
    "low": {"voice": "Aoede", "emotion": "neutral"},
}


def _write_wav(filename: Path, pcm_data: bytes) -> None:
    """Write PCM data to a WAV file."""
    with wave.open(str(filename), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_data)


def _calculate_duration(pcm_data: bytes) -> float:
    """Calculate audio duration from PCM data."""
    return len(pcm_data) / (SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH)


class TTSGenerator:
    """
    Generate speech audio using Gemini TTS.

    Supports single-speaker and multi-speaker dialogue generation
    with consistent voice mapping per character.
    """

    def __init__(self, client: genai.Client = None):
        """Initialize with Gemini client."""
        self.client = client or genai.Client(api_key=GOOGLE_API_KEY)
        self.model = TTS_MODEL
        self.output_dir = OUTPUT_DIR / "audio"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Track voice assignments for consistency
        self._voice_assignments: dict[str, str] = {}

    def _select_voice(
        self,
        character_name: str,
        character_type: str = None,
        voice_name: str = None,
    ) -> str:
        """
        Select a voice for a character.

        Priority:
        1. Explicit voice_name parameter
        2. Previously assigned voice (consistency)
        3. Default based on character_type
        4. Fallback to Puck
        """
        # Explicit voice
        if voice_name and voice_name in VOICES:
            self._voice_assignments[character_name] = voice_name
            return voice_name

        # Previously assigned
        if character_name in self._voice_assignments:
            return self._voice_assignments[character_name]

        # Default by type
        if character_type and character_type.lower() in DEFAULT_VOICE_MAP:
            voice = DEFAULT_VOICE_MAP[character_type.lower()]
            self._voice_assignments[character_name] = voice
            return voice

        # Fallback
        voice = DEFAULT_VOICE_MAP["default"]
        self._voice_assignments[character_name] = voice
        return voice

    def _select_voice_from_character(
        self,
        character_name: str,
        character_data: dict,
    ) -> tuple[str, str]:
        """
        Select voice based on character persona and personality traits.

        Uses analysis.personality_traits and concept.character_archetype
        to pick the most appropriate voice.

        Args:
            character_name: Name of character
            character_data: Dict containing:
                - source_type: "pet" | "person" | etc.
                - personality_traits: ["playful", "curious", ...] from analysis
                - archetype: "loyal companion" from concept
                - energy_level: "high" | "medium" | "low"

        Returns:
            (voice_name, default_emotion) tuple
        """
        # 1. Check for previously assigned voice (consistency across calls)
        if character_name in self._voice_assignments:
            return self._voice_assignments[character_name], "neutral"

        source_type = character_data.get("source_type", "unknown")
        personality_traits = character_data.get("personality_traits", [])
        archetype = character_data.get("archetype", "")
        energy_level = character_data.get("energy_level", "medium")

        voice = None
        emotion = "neutral"

        # 2. For pets, use personality traits for voice selection
        if source_type in ["pet", "cat", "dog"]:
            for trait in personality_traits:
                trait_lower = trait.lower()
                if trait_lower in PET_PERSONALITY_MAP:
                    voice = PET_PERSONALITY_MAP[trait_lower]["voice"]
                    emotion = PET_PERSONALITY_MAP[trait_lower]["emotion"]
                    logger.info(f"[TTS] Voice for {character_name}: {voice} (trait: {trait_lower})")
                    break

            # Fallback to energy level
            if not voice and energy_level:
                energy_key = energy_level.lower()
                if energy_key in ENERGY_LEVEL_VOICES:
                    voice = ENERGY_LEVEL_VOICES[energy_key]["voice"]
                    emotion = ENERGY_LEVEL_VOICES[energy_key]["emotion"]
                    logger.info(f"[TTS] Voice for {character_name}: {voice} (energy: {energy_key})")

        # 3. For people, use archetype
        elif source_type == "person":
            if archetype:
                archetype_lower = archetype.lower()
                if archetype_lower in ARCHETYPE_VOICE_MAP:
                    voice = ARCHETYPE_VOICE_MAP[archetype_lower]
                    logger.info(f"[TTS] Voice for {character_name}: {voice} (archetype: {archetype_lower})")

            # Try matching traits if no archetype match
            if not voice:
                for trait in personality_traits:
                    trait_lower = trait.lower()
                    # Check if trait matches any voice profile
                    for v_name, v_style in VOICES.items():
                        if trait_lower in v_style or v_style in trait_lower:
                            voice = v_name
                            break
                    if voice:
                        break

        # 4. Final fallback
        if not voice:
            voice = DEFAULT_VOICE_MAP.get(source_type, DEFAULT_VOICE_MAP["default"])
            logger.info(f"[TTS] Voice for {character_name}: {voice} (fallback)")

        self._voice_assignments[character_name] = voice
        return voice, emotion

    def _detect_emotion_from_text(self, text: str) -> str:
        """
        Detect emotion from dialogue text markers.

        Looks for explicit markers and punctuation cues.
        """
        text_lower = text.lower()

        # Explicit emotion markers in parentheses
        if "(excited)" in text_lower:
            return "excited"
        elif "(sad)" in text_lower:
            return "sad"
        elif "(angry)" in text_lower:
            return "angry"
        elif "(whisper)" in text_lower:
            return "whisper"
        elif "(shout)" in text_lower:
            return "shout"
        elif "(cheerful)" in text_lower:
            return "cheerful"
        elif "(curious)" in text_lower:
            return "curious"

        # Punctuation and context cues
        if text.isupper() and len(text) > 3:
            return "shout"
        elif "!" in text and "?" in text:
            return "excited"
        elif text.count("!") >= 2:
            return "excited"
        elif "?" in text:
            return "curious"
        elif "..." in text:
            return "sad"
        elif "*gasp*" in text_lower or "*wow*" in text_lower:
            return "excited"
        elif "*sigh*" in text_lower:
            return "sad"

        return "neutral"

    def _build_emotion_prompt(self, dialogue: str, emotion: str = "neutral") -> str:
        """Build prompt with emotion instruction."""
        emotion_instructions = {
            "neutral": "",
            "cheerful": "Say cheerfully: ",
            "excited": "Say with excitement: ",
            "sad": "Say sadly: ",
            "angry": "Say angrily: ",
            "curious": "Say with curiosity: ",
            "whisper": "Whisper: ",
            "shout": "Shout: ",
        }

        prefix = emotion_instructions.get(emotion.lower(), "")
        return f"{prefix}{dialogue}"

    async def generate_dialogue(
        self,
        dialogue: str,
        character_name: str,
        voice_name: str = None,
        character_type: str = None,
        emotion: str = "neutral",
    ) -> TTSResult:
        """
        Generate speech for a single character's dialogue.

        Args:
            dialogue: Text to speak
            character_name: Who is speaking
            voice_name: Specific voice (or auto-select)
            character_type: Hint for voice selection (pet, child, adult)
            emotion: Emotional tone (cheerful, sad, excited, etc.)

        Returns:
            TTSResult with audio path and duration
        """
        if not dialogue or not dialogue.strip():
            raise ValueError("Dialogue cannot be empty")

        voice = self._select_voice(character_name, character_type, voice_name)
        prompt = self._build_emotion_prompt(dialogue, emotion)

        logger.info(f"[TTS] Generating for {character_name} with voice {voice}: {dialogue[:50]}...")

        def call_tts():
            return self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice,
                            )
                        )
                    ),
                )
            )

        response = await asyncio.to_thread(call_tts)

        # Extract audio data
        audio_data = None
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    audio_data = part.inline_data.data
                    break

        if not audio_data:
            raise RuntimeError("TTS generation failed - no audio in response")

        # Calculate duration
        duration = _calculate_duration(audio_data)

        # Save to file
        audio_id = str(uuid.uuid4())[:8]
        filename = f"tts_{character_name.lower().replace(' ', '_')}_{audio_id}.wav"
        audio_path = self.output_dir / filename
        _write_wav(audio_path, audio_data)

        logger.info(f"[TTS] Saved: {filename} ({duration:.2f}s)")

        return TTSResult(
            audio_path=audio_path,
            duration_seconds=duration,
            voice_used=voice,
            character_name=character_name,
        )

    async def generate_conversation(
        self,
        dialogues: list[dict],
        voice_mapping: dict[str, str] = None,
    ) -> list[TTSResult]:
        """
        Generate speech for a multi-character conversation.

        Uses Gemini's multi-speaker TTS when there are exactly 2 speakers.
        Falls back to sequential single-speaker calls otherwise.

        Args:
            dialogues: List of {character, text, emotion} dicts
            voice_mapping: Optional {character_name: voice_name} mapping

        Returns:
            List of TTSResult, one per dialogue line
        """
        if not dialogues:
            return []

        # Apply voice mapping
        if voice_mapping:
            for char, voice in voice_mapping.items():
                self._voice_assignments[char] = voice

        # Get unique speakers
        speakers = list(set(d["character"] for d in dialogues))

        # If 2 speakers, use multi-speaker API for efficiency
        if len(speakers) == 2:
            return await self._generate_multi_speaker(dialogues, speakers)

        # Otherwise, generate sequentially
        results = []
        for d in dialogues:
            result = await self.generate_dialogue(
                dialogue=d["text"],
                character_name=d["character"],
                emotion=d.get("emotion", "neutral"),
            )
            results.append(result)

        return results

    async def _generate_multi_speaker(
        self,
        dialogues: list[dict],
        speakers: list[str],
    ) -> list[TTSResult]:
        """
        Generate multi-speaker conversation in one API call.

        Gemini TTS supports up to 2 speakers in multi-speaker mode.
        The transcript format uses speaker names as labels.
        """
        # Build transcript format
        # Format: "Speaker1: dialogue\nSpeaker2: dialogue\n..."
        transcript_lines = []
        for d in dialogues:
            emotion_prefix = ""
            if d.get("emotion") and d["emotion"] != "neutral":
                emotion_prefix = f"({d['emotion']}) "
            transcript_lines.append(f"{d['character']}: {emotion_prefix}{d['text']}")

        transcript = "\n".join(transcript_lines)

        # Get voices for each speaker
        voice1 = self._select_voice(speakers[0])
        voice2 = self._select_voice(speakers[1])

        logger.info(f"[TTS] Multi-speaker: {speakers[0]}={voice1}, {speakers[1]}={voice2}")

        def call_multi_tts():
            return self.client.models.generate_content(
                model=self.model,
                contents=transcript,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                            speaker_voice_configs=[
                                types.SpeakerVoiceConfig(
                                    speaker=speakers[0],
                                    voice_config=types.VoiceConfig(
                                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                            voice_name=voice1,
                                        )
                                    )
                                ),
                                types.SpeakerVoiceConfig(
                                    speaker=speakers[1],
                                    voice_config=types.VoiceConfig(
                                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                            voice_name=voice2,
                                        )
                                    )
                                ),
                            ]
                        )
                    )
                )
            )

        response = await asyncio.to_thread(call_multi_tts)

        # Extract audio
        audio_data = None
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    audio_data = part.inline_data.data
                    break

        if not audio_data:
            raise RuntimeError("Multi-speaker TTS failed - no audio in response")

        # Save combined audio
        duration = _calculate_duration(audio_data)
        audio_id = str(uuid.uuid4())[:8]
        filename = f"tts_conversation_{audio_id}.wav"
        audio_path = self.output_dir / filename
        _write_wav(audio_path, audio_data)

        logger.info(f"[TTS] Multi-speaker saved: {filename} ({duration:.2f}s)")

        # Return single result for combined audio
        # Note: Multi-speaker returns one audio file with all dialogue
        return [TTSResult(
            audio_path=audio_path,
            duration_seconds=duration,
            voice_used=f"{voice1}+{voice2}",
            character_name="+".join(speakers),
        )]

    async def generate_panel_audio(
        self,
        panel_dialogue: str,
        characters: list[dict],
        voice_mapping: dict[str, str] = None,
    ) -> tuple[Path, float]:
        """
        Generate audio for a single manga panel's dialogue.

        Parses dialogue in "Character: text" format and generates
        appropriate speech with persona-based voice selection.

        Args:
            panel_dialogue: Full dialogue text (may have multiple speakers)
            characters: List of character dicts with:
                - name: Character name
                - source_type: "pet" | "person" (optional)
                - analysis: Dict with personality_traits (optional)
                - concept: Dict with character_archetype (optional)
            voice_mapping: Optional explicit voice assignments

        Returns:
            (audio_path, duration_seconds)
        """
        if not panel_dialogue or not panel_dialogue.strip():
            # Silent panel - return minimal placeholder
            logger.info("[TTS] Silent panel, no audio generated")
            return None, 0.0

        # Build character lookup for voice selection
        char_lookup = {c["name"]: c for c in characters}
        char_names = list(char_lookup.keys())

        # Auto-select voices from character personas if no explicit mapping
        if not voice_mapping:
            voice_mapping = {}
            for char in characters:
                char_name = char["name"]
                if char_name not in self._voice_assignments:
                    # Build character data for voice selection
                    char_data = {
                        "source_type": char.get("source_type", "unknown"),
                        "personality_traits": char.get("analysis", {}).get("personality_traits", []),
                        "archetype": char.get("concept", {}).get("character_archetype", ""),
                        "energy_level": char.get("analysis", {}).get("energy_level", "medium"),
                    }
                    voice, _ = self._select_voice_from_character(char_name, char_data)
                    voice_mapping[char_name] = voice

        # Parse dialogue lines
        dialogues = []

        for line in panel_dialogue.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            # Try to parse "Character: dialogue" or "Character (emotion): dialogue"
            if ":" in line:
                parts = line.split(":", 1)
                speaker_part = parts[0].strip()
                text = parts[1].strip().strip('"')

                # Check for emotion in speaker part: "Mochi (excited)"
                emotion = "neutral"
                speaker = speaker_part
                if "(" in speaker_part and ")" in speaker_part:
                    paren_start = speaker_part.index("(")
                    paren_end = speaker_part.index(")")
                    emotion = speaker_part[paren_start + 1:paren_end].strip().lower()
                    speaker = speaker_part[:paren_start].strip()

                # Match to known character
                matched = None
                for name in char_names:
                    if name.lower() in speaker.lower():
                        matched = name
                        break

                # Detect emotion from text if not explicit
                if emotion == "neutral":
                    emotion = self._detect_emotion_from_text(text)

                if matched:
                    dialogues.append({
                        "character": matched,
                        "text": text,
                        "emotion": emotion,
                    })
                else:
                    # Unknown speaker, use first character
                    dialogues.append({
                        "character": char_names[0] if char_names else "Narrator",
                        "text": text,
                        "emotion": emotion,
                    })
            else:
                # No speaker prefix, use first character
                text = line.strip('"')
                emotion = self._detect_emotion_from_text(text)
                dialogues.append({
                    "character": char_names[0] if char_names else "Narrator",
                    "text": text,
                    "emotion": emotion,
                })

        if not dialogues:
            return None, 0.0

        # Apply voice mapping
        if voice_mapping:
            for char, voice in voice_mapping.items():
                self._voice_assignments[char] = voice

        # Generate
        results = await self.generate_conversation(dialogues, voice_mapping)

        if results:
            # Return first result (multi-speaker returns one combined file)
            return results[0].audio_path, results[0].duration_seconds

        return None, 0.0

    def set_voice_mapping(self, mapping: dict[str, str]) -> None:
        """
        Pre-set voice assignments for characters.

        Call this before generate_* methods to ensure
        consistent voices throughout a story.
        """
        self._voice_assignments.update(mapping)

    def get_voice_mapping(self) -> dict[str, str]:
        """Get current voice assignments."""
        return self._voice_assignments.copy()
