from pydantic import BaseModel, Field
from typing import List, Optional


# ── Style Bible ────────────────────────────────────────────────────────────────
# Generated once per video by scene_llm.py and passed downstream to
# image_llm.py so every Pollinations call shares the same visual DNA and seed.

class StyleBible(BaseModel):
    art_style: str = "ultra-realistic cinematic photography"
    lighting: str = "dramatic natural lighting"
    color_palette: str = "rich cinematic tones"
    camera_style: str = "dynamic mix of wides and close-ups"
    mood: str = "engaging and cinematic"
    video_seed: int = Field(default=1234, ge=1000, le=9999)


# ── Scene ──────────────────────────────────────────────────────────────────────
# Represents one scene in the video.
# beat_tag drives emotional pacing; transition_type drives video_compiler.py

class Scene(BaseModel):
    scene_number: int
    script_segment: str
    ai_image_prompt: str

    beat_tag: Optional[str] = "setup"
    # Valid values: "setup" | "conflict" | "reveal" | "resolution"

    transition_type: Optional[str] = "crossfade"
    # Valid values: "crossfade" | "dip_to_black" | "cut"
    # crossfade    → smooth dissolve (default, works for most genres)
    # dip_to_black → hard dip to black (good for horror, true crime reveals)
    # cut          → instant cut (good for fast-paced motivation, tech)

    image_url: Optional[str] = None   # filled by image_llm.py
    audio_url: Optional[str] = None   # filled by audio_llm.py
    duration: Optional[float] = None  # filled by audio_llm.py (seconds)


# ── LLM Raw Response ───────────────────────────────────────────────────────────
# Validates the raw JSON the LLM returns before we extract scenes + style_bible.

class SceneResponse(BaseModel):
    total_scenes: int
    style_bible: Optional[StyleBible] = None
    scenes: List[Scene]


# ── Final Processed Result ─────────────────────────────────────────────────────
# What scene_llm.process_scene() returns to your router/pipeline.
# Carries both the validated scenes and the style_bible as a single typed object
# so downstream services (image_llm, video_compiler) can unpack cleanly.

class SceneResult(BaseModel):
    scenes: List[Scene]
    style_bible: StyleBible


# ── Request ────────────────────────────────────────────────────────────────────

class SceneRequest(BaseModel):
    script: str
    niche: str = "finance"
    voice: Optional[str] = Field(
        default=None,
        description="Optional: user-selected TTS voice from the frontend dropdown. "
                    "If None, audio_llm auto-selects based on niche.",
    )
    video_seed: Optional[int] = Field(
        default=None,
        ge=1000,
        le=9999,
        description="Optional: pass a specific seed to reproduce a previous video's visual style.",
    )
