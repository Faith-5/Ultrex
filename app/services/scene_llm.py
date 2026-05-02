import json
import random
from fastapi import HTTPException
from app.services.client import client
from app.models.scene import SceneRequest, SceneResponse, Scene, SceneResult, StyleBible

# ── Genre prompt registry
GENRE_PROMPT_MAP = {
    "motivation":         "app.prompts.motivation",
    "history":            "app.prompts.history",
    "finance":            "app.prompts.finance",
}

FALLBACK_SYSTEM_PROMPT = """
You are a professional short-form video director.
Break the provided script into scenes of 3-6 seconds of narration each.

STYLE RULES (apply to EVERY image prompt):
- Art style: ultra-realistic cinematic photography
- Lighting: dramatic natural lighting appropriate to the mood
- Camera: mix of wide establishing shots and intimate close-ups
- Texture: film grain, shallow depth of field
- Every image prompt MUST describe: camera angle, lighting, subject + expression, environment, color palette
- Negative: NO cartoon, anime, blurry, watermark, text, logo

Return ONLY valid JSON, no extra text, no markdown:
{
  "total_scenes": int,
  "style_bible": {
    "art_style": str,
    "lighting": str,
    "color_palette": str,
    "camera_style": str,
    "mood": str,
    "video_seed": int
  },
  "scenes": [
    {
      "scene_number": int,
      "script_segment": str,
      "ai_image_prompt": str,
      "beat_tag": str
    }
  ]
}
"""


def _load_genre_prompt(niche: str) -> str:
    key = niche.strip().lower()
    module_path = GENRE_PROMPT_MAP.get(key)

    if module_path:
        try:
            import importlib
            module = importlib.import_module(module_path)
            return module.SYSTEM_PROMPT
        except (ImportError, AttributeError) as e:
            # Log the issue but don't crash — fall back gracefully
            print(f"[scene_llm] Warning: could not load prompt for '{niche}': {e}")

    return FALLBACK_SYSTEM_PROMPT


class LLMService:
    def __init__(self):
        self.client = client

    def process_scene(self, request: SceneRequest) -> SceneResult:
        """
        Returns:
            {
                "scenes": List[Scene],
                "style_bible": dict   ← includes video_seed
            }
        """
        system_prompt = _load_genre_prompt(request.niche)

        # Use caller-supplied seed (for retries/reproducibility) or generate fresh one
        video_seed = request.video_seed if request.video_seed else random.randint(1000, 9999)

        user_message = f"""
SCRIPT:
{request.script}

GENRE: {request.niche}

IMPORTANT — use {video_seed} as the video_seed value in your style_bible JSON.
This seed must be identical across ALL scenes.
"""

        try:
            chat_completion = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=0.7,      # balanced creativity vs consistency
                max_tokens=4096,
            )

            raw_content = chat_completion.choices[0].message.content
            data = json.loads(raw_content)

            # ── Validate scenes via existing Pydantic model ────────────────────
            validated = SceneResponse(**data)

            # ── Extract + validate style_bible ────────────────────────────────
            raw_bible = data.get("style_bible", {})
            try:
                style_bible = StyleBible(**raw_bible)
            except Exception:
                style_bible = StyleBible()  # safe defaults from model

            # Guarantee seed is always what Python decided, not the LLM
            style_bible.video_seed = video_seed

            return SceneResult(scenes=validated.scenes, style_bible=style_bible)

        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=500,
                detail=f"LLM returned invalid JSON: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"LLM processing error: {str(e)}"
            )
