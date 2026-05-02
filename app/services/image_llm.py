import os
import httpx
import asyncio
from urllib.parse import quote
from typing import List, Optional
from app.services.client import POLLINATIONS_BASE, POLLINATION_API_KEY, APP_BASE_URL, logger
from app.models.scene import Scene, StyleBible

logger = logger

class ImageService:
    WIDTH = 1080
    HEIGHT = 1920
    MODEL = "flux"
    MAX_RETRIES = 3
    RETRY_DELAY = 2
    MAX_CONCURRENT = 5
    TIMEOUT = 60.0

    POLLINATIONS_BASE = POLLINATIONS_BASE

    def __init__(self, static_path: str):
        self.key = POLLINATION_API_KEY
        self.base_url = APP_BASE_URL
        self.static_dir = os.path.join(static_path, "generated_images")
        os.makedirs(self.static_dir, exist_ok=True)
        self.semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)

    async def generate_all_images(self, scenes: List[Scene], style_bible: Optional[StyleBible] = None, model: str = None):
        logger.info("Image generation started for %d scenes.", len(scenes))
        model = model or self.MODEL

        tasks =[self._bounded_generate(scene, style_bible, model) for scene in scenes]
        await asyncio.gather(*tasks)

        successful = sum(1 for s in scenes if s.image_url is not None)
        failed     = len(scenes) - successful
        logger.info("Image generation complete. Success: %d | Failed: %d", successful, failed)

    async def _bounded_generate(self, scene: Scene, style_bible: Optional[StyleBible], model: str):
        async with self.semaphore:
            await self._generate_image(scene, style_bible, model)

    async def _generate_image(self, scene: Scene, style_bible: Optional[StyleBible], model: str):
        filename = f"scene_{scene.scene_number}.png"
        filepath = os.path.join(self.static_dir, filename)

        full_prompt = self._build_prompt(scene.ai_image_prompt, style_bible)
        negative_prompt = self._build_negative_prompt(style_bible)

        # ── THE SEED MATH FIX ──
        # Guarantees a different physical composition per scene, while maintaining the exact 
        # same color grading and texture.
        base_seed = style_bible.video_seed if style_bible else 1234
        scene_seed = base_seed + scene.scene_number

        url = self._build_url(full_prompt, negative_prompt, scene_seed, model)

        logger.debug("Scene %d prompt: %s", scene.scene_number, full_prompt[:120])

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                    response = await client.get(url, headers={"Authorization": f"Bearer {self.key}"})
                    response.raise_for_status()

                    content_type = response.headers.get("content-type", "")
                    if "image" not in content_type:
                        raise ValueError(f"Non-image response (content-type: {content_type}).")

                    with open(filepath, "wb") as f:
                        f.write(response.content)

                    scene.image_url = f"{self.base_url}/static/generated_images/{filename}"
                    logger.info("✓ Scene %d image saved.", scene.scene_number)
                    return 

            except Exception as e:
                logger.warning("Attempt %d failed for scene %d: %s", attempt, scene.scene_number, str(e))
                if attempt == self.MAX_RETRIES:
                    scene.image_url = None
                else:
                    await asyncio.sleep(self.RETRY_DELAY * attempt)

    def _build_prompt(self, scene_prompt: str, style_bible: Optional[StyleBible]) -> str:
        """
        ACTION FIRST, STYLE SECOND. 
        Forces the AI to draw the dynamic shot first before applying the cinematic look.
        """
        if not style_bible:
            return f"{scene_prompt}, highly detailed, 8k resolution, cinematic 9:16 vertical frame"

        return (
            f"{scene_prompt}, "
            f"Style of {style_bible.art_style}, "
            f"{style_bible.lighting}, "
            f"{style_bible.color_palette}, "
            f"highly detailed, 8k resolution, cinematic 9:16 vertical frame"
        )

    def _build_negative_prompt(self, style_bible: Optional[StyleBible]) -> str:
        return "blurry, low quality, pixelated, watermark, text overlay, logo, signature, frame, border, letterbox, multiple panels, comic strip, split screen"

    def _build_url(self, prompt: str, negative: str, seed: int, model: str) -> str:
        encoded_prompt   = quote(prompt)
        encoded_negative = quote(negative)

        return (
            f"{self.POLLINATIONS_BASE}/{encoded_prompt}"
            f"?model={model}"
            f"&width={self.WIDTH}"
            f"&height={self.HEIGHT}"
            f"&seed={seed}"
            f"&nologo=true"
            f"&enhance=false"
            f"&negative={encoded_negative}"
            f"&private=true"
        )