"""
Qwen3-TTS: Text-to-speech with three modes.

Modes:
- "torch": Official qwen_tts package (PyTorch). VoiceDesign → Clone pattern
  for consistent multi-character dialogue. Best quality. Works on CUDA + MPS.
- "local": mlx_audio (Mac MLX). Fast but no voice consistency across lines.
- "cloud": FAL API. Predefined voices or voice embeddings.

The "torch" mode implements the recommended "Voice Design then Clone" pattern:
1. VoiceDesign model generates a reference audio from persona description (once)
2. Base model creates a voice_clone_prompt from that reference (once)
3. All subsequent lines use generate_voice_clone with the cached prompt (consistent)
"""

import asyncio
import gc
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Literal

import numpy as np
import requests
import soundfile as sf
from dotenv import load_dotenv

# Compatibility patch: qwen_tts 0.1.0 uses rope_type="default" which was removed
# in transformers 5.x. Reimplement the base RoPE computation (no scaling factor).
try:
    from transformers.modeling_rope_utils import ROPE_INIT_FUNCTIONS
    if "default" not in ROPE_INIT_FUNCTIONS:
        import torch as _torch

        def _compute_default_rope_parameters(config, device=None, **kwargs):
            base = config.rope_theta
            dim = config.head_dim
            inv_freq = 1.0 / (
                base ** (_torch.arange(0, dim, 2, dtype=_torch.float32, device=device) / dim)
            )
            return inv_freq, 1.0  # (inv_freq, attention_scaling=1.0)

        ROPE_INIT_FUNCTIONS["default"] = _compute_default_rope_parameters
except ImportError:
    pass

# Load environment
load_dotenv(Path(__file__).parent.parent.parent / ".env")

FAL_KEY = os.getenv("FAL_KEY")

logger = logging.getLogger(__name__)

# Available predefined voices (for FAL API / CustomVoice)
AVAILABLE_VOICES = [
    "Vivian",    # Female, English
    "Serena",    # Female
    "Dylan",     # Male, English
    "Eric",      # Male
    "Ryan",      # Male
    "Aiden",     # Male
    "Ono_Anna",  # Female, Japanese
    "Sohee",     # Female, Korean
    "Uncle_Fu",  # Male, Chinese
]

DEFAULT_VOICE = "Dylan"  # Default English male voice

# mlx_audio models on HuggingFace
MLX_MODELS = {
    "voice_design": "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-4bit",
    "custom_voice": "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit",
    "base": "mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit",
}

# Official qwen_tts models (PyTorch, for torch mode)
TORCH_MODELS = {
    "voice_design": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "base": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
}

# Default reference sentences per language for voice design initialization
DEFAULT_REF_SENTENCES = {
    "english": "Hello there! I'm so excited to be part of this adventure with you today!",
    "chinese": "你好！今天能和你一起冒险，我真的太开心了！",
    "japanese": "こんにちは！今日あなたと一緒に冒険できて、とても嬉しいです！",
}

# Language code normalization (short -> full name for qwen_tts)
LANGUAGE_MAP = {
    "en": "english", "zh": "chinese", "ja": "japanese", "ko": "korean",
    "fr": "french", "de": "german", "es": "spanish", "it": "italian",
    "pt": "portuguese", "ru": "russian",
    # Full names pass through
    "english": "english", "chinese": "chinese", "japanese": "japanese",
    "korean": "korean", "auto": "auto",
}


@dataclass
class TTSResult:
    """Result from TTS generation."""
    audio_path: Path
    duration_seconds: float
    text: str


@dataclass
class CharacterVoice:
    """Cached voice data for a character (torch mode)."""
    name: str
    persona: str
    ref_audio: np.ndarray
    ref_text: str
    sample_rate: int
    clone_prompt: object = None  # VoiceClonePromptItem list


class QwenTTS:
    """
    Text-to-speech using Qwen3-TTS.

    Supports three modes:
    - "torch": Official qwen_tts package. VoiceDesign → Clone for consistent voices.
    - "local": mlx_audio on Mac. Fast, persona-based, but voice varies per call.
    - "cloud": FAL API. Predefined voices or voice embeddings.

    Usage:
        # Torch mode with VoiceDesign → Clone (recommended)
        tts = QwenTTS(mode="torch")
        await tts.initialize_character_voices({
            "Mochi": "A cheerful young girl with an excited and curious tone",
            "Hero": "A brave young man with a confident and warm voice",
        })
        results = await tts.generate_dialogue([
            ("Mochi", "Hi! What's that?"),
            ("Hero", "Looks like a treasure map!"),
        ])

        # Local with persona (fast on Mac, no consistency guarantee)
        tts = QwenTTS(mode="local")
        result = await tts.generate_speech(
            "Hello!",
            instruct="A cheerful young woman with an excited tone",
        )

        # Cloud with predefined voice
        tts = QwenTTS(mode="cloud")
        result = await tts.generate_speech("Hello!", voice="Dylan")
    """

    def __init__(
        self,
        output_dir: Path = None,
        mode: Literal["torch", "local", "cloud", "auto"] = "auto",
    ):
        """
        Initialize TTS.

        Args:
            output_dir: Output directory for audio files
            mode: "torch" (official package), "local" (mlx_audio),
                  "cloud" (FAL API), or "auto" (detect best)
        """
        self.output_dir = output_dir or (
            Path(__file__).parent.parent.parent / "assets" / "outputs" / "audio"
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Determine mode
        if mode == "auto":
            self.mode = self._detect_mode()
        else:
            self.mode = mode

        # Validate cloud mode has FAL_KEY
        if self.mode == "cloud" and not FAL_KEY:
            raise ValueError("FAL_KEY not found in .env for cloud mode")

        logger.info(f"QwenTTS initialized in {self.mode} mode")

        # Cache for loaded models
        self._local_model = None  # mlx_audio model (local mode)
        self._torch_clone_model = None  # qwen_tts Base model (torch mode)

        # Cached character voices (torch mode): name -> CharacterVoice
        self._character_voices: dict[str, CharacterVoice] = {}

    def _detect_mode(self) -> str:
        """Auto-detect best mode based on available resources."""
        # Prefer torch mode (best quality with voice consistency)
        try:
            import qwen_tts
            return "torch"
        except ImportError:
            pass
        try:
            import mlx_audio
            return "local"
        except ImportError:
            if FAL_KEY:
                return "cloud"
            raise ValueError("Neither qwen_tts, mlx_audio, nor FAL_KEY available")

    # ── Torch mode: VoiceDesign → Clone ─────────────────────────────

    def _get_torch_device(self) -> str:
        """Detect best PyTorch device."""
        import torch
        if torch.cuda.is_available():
            return "cuda:0"
        if torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _get_torch_dtype(self):
        """Get dtype appropriate for the current device."""
        import torch
        device = self._get_torch_device()
        if device.startswith("cuda"):
            return torch.bfloat16
        # MPS and CPU: use float16 (bfloat16 not supported on MPS)
        return torch.float16

    async def initialize_character_voices(
        self,
        character_personas: dict[str, str],
        language: str = "en",
        ref_sentences: dict[str, str] = None,
    ) -> dict[str, CharacterVoice]:
        """
        Design and cache a consistent voice for each character.

        Uses VoiceDesign model to generate reference audio from persona,
        then Base model to create reusable voice_clone_prompts.

        Args:
            character_personas: {name: persona_instruction}
                e.g. {"Mochi": "A cheerful young girl with excited tone"}
            language: Language for reference sentences ("en", "zh", "ja")
            ref_sentences: Optional custom reference sentences per character.
                If not provided, uses a default sentence in the given language.

        Returns:
            Dict of character name -> CharacterVoice with cached clone prompts
        """
        if self.mode != "torch":
            logger.warning(
                f"initialize_character_voices only works in torch mode "
                f"(current: {self.mode}). Skipping."
            )
            return {}

        loop = asyncio.get_event_loop()
        voices = await loop.run_in_executor(
            None,
            lambda: self._initialize_voices_sync(
                character_personas, language, ref_sentences
            ),
        )
        self._character_voices.update(voices)
        return voices

    def _normalize_language(self, language: str) -> str:
        """Normalize language code to full name for qwen_tts package."""
        return LANGUAGE_MAP.get(language.lower(), language.lower())

    def _initialize_voices_sync(
        self,
        character_personas: dict[str, str],
        language: str,
        ref_sentences: dict[str, str] = None,
    ) -> dict[str, CharacterVoice]:
        """Synchronous voice initialization (runs in executor)."""
        import torch
        from qwen_tts import Qwen3TTSModel

        language = self._normalize_language(language)
        device = self._get_torch_device()
        dtype = self._get_torch_dtype()
        ref_sentences = ref_sentences or {}
        default_ref = DEFAULT_REF_SENTENCES.get(language, DEFAULT_REF_SENTENCES["english"])
        voices = {}

        # ── Step 1: VoiceDesign model → generate reference audio per character ──
        logger.info(f"Loading VoiceDesign model on {device} ({dtype})...")
        design_model = Qwen3TTSModel.from_pretrained(
            TORCH_MODELS["voice_design"],
            device_map=device,
            dtype=dtype,
        )

        ref_dir = self.output_dir / "voice_refs"
        ref_dir.mkdir(parents=True, exist_ok=True)

        for name, persona in character_personas.items():
            ref_text = ref_sentences.get(name, default_ref)
            logger.info(f"Designing voice for '{name}': {persona[:60]}...")

            ref_wavs, sr = design_model.generate_voice_design(
                text=ref_text,
                instruct=persona,
                language=language,
            )

            ref_path = ref_dir / f"{name}_ref.wav"
            sf.write(str(ref_path), ref_wavs[0], sr)
            logger.info(f"Reference audio saved: {ref_path} ({len(ref_wavs[0])/sr:.1f}s)")

            voices[name] = CharacterVoice(
                name=name,
                persona=persona,
                ref_audio=ref_wavs[0],
                ref_text=ref_text,
                sample_rate=sr,
            )

        # Free VoiceDesign model
        del design_model
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        gc.collect()
        logger.info("VoiceDesign model unloaded.")

        # ── Step 2: Base model → create voice_clone_prompts ──
        logger.info(f"Loading Base model on {device} ({dtype})...")
        clone_model = Qwen3TTSModel.from_pretrained(
            TORCH_MODELS["base"],
            device_map=device,
            dtype=dtype,
        )

        for name, voice in voices.items():
            logger.info(f"Creating clone prompt for '{name}'...")
            prompt_items = clone_model.create_voice_clone_prompt(
                ref_audio=(voice.ref_audio, voice.sample_rate),
                ref_text=voice.ref_text,
            )
            voice.clone_prompt = prompt_items

        # Keep Base model loaded for generation
        self._torch_clone_model = clone_model
        logger.info(f"Voice initialization complete. {len(voices)} character(s) ready.")

        return voices

    async def _generate_torch(
        self,
        text: str,
        output_path: Path,
        character_name: str = None,
        language: str = "en",
    ) -> TTSResult:
        """Generate speech using torch mode with cached voice clone prompt."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._generate_torch_sync(
                text, output_path, character_name, language
            ),
        )
        return result

    def _generate_torch_sync(
        self,
        text: str,
        output_path: Path,
        character_name: str = None,
        language: str = "en",
    ) -> TTSResult:
        """Synchronous torch generation (runs in executor)."""
        import torch

        language = self._normalize_language(language)
        voice = self._character_voices.get(character_name) if character_name else None

        if voice and voice.clone_prompt and self._torch_clone_model:
            # Use cached clone prompt for consistent voice
            wavs, sr = self._torch_clone_model.generate_voice_clone(
                text=text,
                language=language,
                voice_clone_prompt=voice.clone_prompt,
            )
        elif self._torch_clone_model:
            # No cached voice — use base model without clone prompt
            logger.warning(
                f"No cached voice for '{character_name}', using default clone."
            )
            wavs, sr = self._torch_clone_model.generate_voice_clone(
                text=text,
                language=language,
            )
        else:
            raise RuntimeError(
                "Torch clone model not loaded. "
                "Call initialize_character_voices() first."
            )

        sf.write(str(output_path), wavs[0], sr)
        duration = len(wavs[0]) / sr

        return TTSResult(
            audio_path=output_path,
            duration_seconds=duration,
            text=text,
        )

    def _upload_embedding(self, file_path: Path) -> str:
        """Upload embedding file to fal.ai storage."""
        content_type = "application/octet-stream"

        response = requests.post(
            "https://rest.alpha.fal.ai/storage/upload/initiate",
            headers={"Authorization": f"Key {FAL_KEY}"},
            json={
                "file_name": file_path.name,
                "content_type": content_type
            }
        )
        response.raise_for_status()
        upload_data = response.json()

        with open(file_path, "rb") as f:
            upload_response = requests.put(
                upload_data["upload_url"],
                data=f,
                headers={"Content-Type": content_type}
            )
            upload_response.raise_for_status()

        return upload_data["file_url"]

    def _get_audio_duration(self, audio_path: Path) -> float:
        """Get duration of audio file using ffprobe."""
        import subprocess

        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.warning(f"Could not get audio duration: {e}")
            return 0.0

    async def generate_speech(
        self,
        text: str,
        output_path: Path = None,
        voice: str = None,
        instruct: str = None,
        voice_embedding: Optional[Path] = None,
        ref_audio: Optional[Path] = None,
        character_name: str = None,
        language: str = "en",
    ) -> TTSResult:
        """
        Generate speech from text.

        Args:
            text: Text to speak
            output_path: Output file path (default: auto-generated)
            voice: Predefined voice name (cloud mode only)
            instruct: Persona instruction, e.g. "A cheerful young woman" (local mode)
            voice_embedding: .safetensors voice embedding file (cloud mode)
            ref_audio: Reference audio for voice cloning (local mode)
            character_name: Character name for cached voice (torch mode)
            language: Language code (torch mode, default "en")

        Returns:
            TTSResult with audio_path and duration
        """
        # Prepare output path
        if output_path is None:
            import uuid
            output_path = self.output_dir / f"tts_{uuid.uuid4().hex[:8]}.wav"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Generating speech ({self.mode}): \"{text[:50]}...\"" if len(text) > 50 else f"Generating speech ({self.mode}): \"{text}\"")

        if self.mode == "torch":
            result = await self._generate_torch(
                text=text,
                output_path=output_path,
                character_name=character_name,
                language=language,
            )
        elif self.mode == "local":
            result = await self._generate_local(
                text=text,
                output_path=output_path,
                instruct=instruct,
                ref_audio=ref_audio,
            )
        else:
            result = await self._generate_cloud(
                text=text,
                output_path=output_path,
                voice=voice,
                voice_embedding=voice_embedding,
            )

        return result

    async def _generate_local(
        self,
        text: str,
        output_path: Path,
        instruct: str = None,
        ref_audio: Path = None,
    ) -> TTSResult:
        """Generate speech using local mlx_audio."""
        from mlx_audio.tts.generate import generate_audio

        # Select model based on parameters
        if ref_audio:
            model = MLX_MODELS["custom_voice"]
        elif instruct:
            model = MLX_MODELS["voice_design"]
        else:
            model = MLX_MODELS["base"]

        # Run in thread pool (CPU-bound)
        loop = asyncio.get_event_loop()

        def _generate():
            generate_audio(
                text=text,
                model=model,
                output_path=str(output_path.parent),
                file_prefix=output_path.stem,
                instruct=instruct,
                ref_audio=str(ref_audio) if ref_audio else None,
                verbose=False,
            )
            # mlx_audio appends _000 to filename
            actual_path = output_path.parent / f"{output_path.stem}_000.wav"
            if actual_path.exists():
                actual_path.rename(output_path)
            return output_path

        await loop.run_in_executor(None, _generate)

        duration = self._get_audio_duration(output_path)

        return TTSResult(
            audio_path=output_path,
            duration_seconds=duration,
            text=text,
        )

    async def _generate_cloud(
        self,
        text: str,
        output_path: Path,
        voice: str = None,
        voice_embedding: Path = None,
    ) -> TTSResult:
        """Generate speech using FAL API."""
        # Get embedding URL if provided
        embedding_url = None
        if voice_embedding:
            voice_embedding = Path(voice_embedding)
            if voice_embedding.exists():
                logger.info(f"Uploading voice embedding: {voice_embedding.name}")
                embedding_url = self._upload_embedding(voice_embedding)
            elif str(voice_embedding).startswith("http"):
                embedding_url = str(voice_embedding)

        request_data = {
            "text": text,
            "max_new_tokens": 8192,
        }

        if embedding_url:
            request_data["speaker_voice_embedding_file_url"] = embedding_url
        else:
            request_data["voice"] = voice or DEFAULT_VOICE

        # Call TTS API
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._call_tts_api(request_data, output_path)
        )

        duration = self._get_audio_duration(result)

        return TTSResult(
            audio_path=result,
            duration_seconds=duration,
            text=text,
        )

    def _call_tts_api(self, request_data: dict, output_path: Path) -> Path:
        """Call FAL TTS API synchronously (for use in executor)."""
        # Submit request
        response = requests.post(
            "https://queue.fal.run/fal-ai/qwen-3-tts/text-to-speech/1.7b",
            headers={
                "Authorization": f"Key {FAL_KEY}",
                "Content-Type": "application/json"
            },
            json=request_data
        )
        response.raise_for_status()

        queue_data = response.json()
        request_id = queue_data.get("request_id")
        status_url = queue_data.get("status_url")
        response_url = queue_data.get("response_url")

        if not request_id:
            # Synchronous response
            result = queue_data
        else:
            # Poll for result
            while True:
                status_response = requests.get(
                    status_url,
                    headers={"Authorization": f"Key {FAL_KEY}"}
                )
                status_data = status_response.json()
                status = status_data.get("status")

                if status == "COMPLETED":
                    result_response = requests.get(
                        response_url,
                        headers={"Authorization": f"Key {FAL_KEY}"}
                    )
                    result = result_response.json()
                    break
                elif status == "FAILED":
                    raise RuntimeError(f"TTS failed: {status_data}")
                else:
                    logger.debug(f"TTS status: {status}...")
                    time.sleep(2)

        # Get audio URL
        audio_data = result.get("audio", {})
        audio_url = audio_data.get("url")

        if not audio_url:
            raise RuntimeError(f"No audio URL in response: {result}")

        # Download audio
        logger.debug("Downloading audio...")
        audio_response = requests.get(audio_url)
        audio_response.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(audio_response.content)

        logger.info(f"Audio saved: {output_path}")
        return output_path

    async def generate_dialogue(
        self,
        dialogue_lines: list[tuple[str, str]],
        character_personas: dict[str, str] = None,
        character_voices: dict[str, str] = None,
        character_ref_audio: dict[str, Path] = None,
        output_dir: Path = None,
        language: str = "en",
    ) -> list[TTSResult]:
        """
        Generate TTS for multi-character dialogue.

        In torch mode: auto-initializes character voices from personas if needed,
        then uses cached clone prompts for consistent timbre across all lines.

        In local mode: uses character_personas for persona-based voice design.
        In cloud mode: uses character_voices for predefined voices.

        Args:
            dialogue_lines: List of (character_name, dialogue_text) tuples
            character_personas: Mapping of character name -> persona instruction
                e.g. {"Mochi": "A cheerful young girl", "Hero": "A brave young man"}
            character_voices: Mapping of character name -> predefined voice (cloud mode)
            character_ref_audio: Mapping of character name -> reference audio (local mode)
            output_dir: Output directory for audio files
            language: Language code for TTS (default "en")

        Returns:
            List of TTSResult, one per dialogue line
        """
        output_dir = output_dir or self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        character_personas = character_personas or {}
        character_voices = character_voices or {}
        character_ref_audio = character_ref_audio or {}

        # Torch mode: auto-initialize voices for any new characters
        if self.mode == "torch" and character_personas:
            new_chars = {
                name: persona
                for name, persona in character_personas.items()
                if name not in self._character_voices
            }
            if new_chars:
                logger.info(
                    f"Auto-initializing voices for: {list(new_chars.keys())}"
                )
                await self.initialize_character_voices(
                    new_chars, language=language
                )

        results = []
        for i, (character, text) in enumerate(dialogue_lines):
            output_path = output_dir / f"dialogue_{i:02d}_{character}.wav"

            if self.mode == "torch":
                result = await self.generate_speech(
                    text=text,
                    output_path=output_path,
                    character_name=character,
                    language=language,
                )
            elif self.mode == "local":
                instruct = character_personas.get(character)
                ref_audio = character_ref_audio.get(character)
                result = await self.generate_speech(
                    text=text,
                    output_path=output_path,
                    instruct=instruct,
                    ref_audio=ref_audio,
                )
            else:
                voice = character_voices.get(character)
                result = await self.generate_speech(
                    text=text,
                    output_path=output_path,
                    voice=voice,
                )

            results.append(result)

        return results
