import os
import asyncio
import edge_tts
from typing import List
from app.models.scene import Scene
from app.services.client import APP_BASE_URL, logger

try:
    from mutagen.mp3 import MP3
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

logger = logger

VERIFIED_VOICES = {
    "arnold": ("en-US-ChristopherNeural", "+0Hz"),   # Finance (Authoritative)
    "brian":  ("en-US-ChristopherNeural", "-18Hz"),  # Motivation (Deep/Energetic)
    "fable":  ("en-US-EricNeural", "+0Hz"),          # History (Storyteller)
}

GENRE_VOICE_MAP = {
    "finance":    "arnold",
    "motivation": "brian",
    "history":    "fable",
}

class AudioService:
    DEFAULT_VOICE = "arnold"
    MAX_RETRIES = 3
    MAX_CONCURRENT = 5
    WORDS_PER_SECOND = 2.5

    def __init__(self, static_path: str):
        self.base_url = APP_BASE_URL
        self.static_dir = os.path.join(static_path, "generated_audios")
        os.makedirs(self.static_dir, exist_ok=True)
        # Semaphore prevents overloading the Edge-TTS websocket
        self.semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)

    # ── Public entry point ─────────────────────────────────────────────────────
    async def generate_all_audios(
        self,
        scenes: List[Scene],
        niche: str = "general",
        voice: str = None,
        model: str = None, # Kept for compatibility with main.py, though unused here
    ):
        
        if voice and voice not in VERIFIED_VOICES:
            logger.warning(
                "Voice '%s' not in verified list. Falling back to genre auto-select.", voice
            )
            voice = None

        resolved_voice_key = (
            voice
            or GENRE_VOICE_MAP.get(niche.strip().lower())
            or self.DEFAULT_VOICE
        )

        edge_voice_name, edge_pitch = VERIFIED_VOICES[resolved_voice_key]

        logger.info(
            "Audio generation started for %d scenes | genre: '%s' | edge-voice: '%s' | pitch: '%s'",
            len(scenes), niche, edge_voice_name, edge_pitch
        )

        tasks =[
            self._bounded_generate(scene, edge_voice_name, edge_pitch)
            for scene in scenes
        ]
        await asyncio.gather(*tasks)

        successful = sum(1 for s in scenes if s.audio_url is not None)
        logger.info(
            "Audio generation complete. Success: %d | Failed: %d",
            successful, len(scenes) - successful,
        )

    # ── Concurrency wrapper ────────────────────────────────────────────────────
    async def _bounded_generate(self, scene: Scene, edge_voice_name: str, edge_pitch: str):
        async with self.semaphore:
            await self._generate_audio(scene, edge_voice_name, edge_pitch)

    # ── Core generation (Edge-TTS) ──────────────────────────────────────────────
    async def _generate_audio(self, scene: Scene, edge_voice_name: str, edge_pitch: str):
        filename = f"audio_{scene.scene_number}.mp3"
        filepath = os.path.join(self.static_dir, filename)

        # Clean text to prevent TTS from reading weird symbols or breaking
        clean_text = scene.script_segment.replace("*", "").replace("_", "").strip()

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                # Microsoft Edge TTS generation
                communicate = edge_tts.Communicate(
                    text=clean_text, 
                    voice=edge_voice_name, 
                    pitch=edge_pitch,
                    rate="+0%" # Adjust this (e.g. "+10%") if you want it faster
                )
                await communicate.save(filepath)

                # Guard against silent failures (empty file)
                if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                    raise ValueError("Edge-TTS generated an empty file or connection dropped.")

                # Populate duration — video_compiler reads this per scene
                scene.duration = self._get_audio_duration(filepath, clean_text)
                scene.audio_url = f"{self.base_url}/static/generated_audios/{filename}"

                logger.info(
                    "✓ Scene %d audio saved. Duration: %.2fs | Voice: %s",
                    scene.scene_number, scene.duration, edge_voice_name,
                )
                return  # SUCCESS — exit retry loop immediately

            except Exception as e:
                logger.warning(
                    "Attempt %d/%d failed for scene %d audio: %s",
                    attempt, self.MAX_RETRIES, scene.scene_number, str(e),
                )
                if attempt == self.MAX_RETRIES:
                    logger.error(
                        "✗ Permanent audio failure for scene %d. Skipping.",
                        scene.scene_number,
                    )
                    scene.audio_url = None
                    # Still set duration so video_compiler doesn't crash
                    scene.duration = self._estimate_duration_from_text(clean_text)
                else:
                    await asyncio.sleep(2 * attempt)  # 2s, 4s, 6s backoff

    # ── Duration helpers ───────────────────────────────────────────────────────
    def _get_audio_duration(self, filepath: str, fallback_text: str) -> float:
        """Read actual MP3 duration via mutagen. Falls back to word-count estimate."""
        if HAS_MUTAGEN:
            try:
                audio = MP3(filepath)
                if audio.info.length > 0:
                    return round(audio.info.length, 3)
            except Exception as e:
                logger.warning(
                    "mutagen failed on %s: %s. Using word-count estimate.", filepath, e
                )
        return self._estimate_duration_from_text(fallback_text)

    def _estimate_duration_from_text(self, text: str) -> float:
        """Rough duration estimate: word count / speaking rate + 0.5s pause buffer."""
        word_count = len(text.split())
        estimated  = (word_count / self.WORDS_PER_SECOND) + 0.5
        return round(max(estimated, 1.5), 3)