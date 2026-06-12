import os
import asyncio
import subprocess
from typing import List, Optional
from app.models.scene import Scene
from app.services.client import logger

logger = logger

# Constants — 9:16 vertical short format
WIDTH  = 1080
HEIGHT = 1920
FPS    = 30

MUSIC_VOLUME       = 0.13
SCENE_TAIL_PAD     = 0.3   # silence buffer added after each audio clip
CAPTION_CHUNK_SIZE = 5     # words per caption chunk (TikTok style)

# Genre → caption colour palette: (text_color, background_box_color, box_opacity)
GENRE_CAPTION_STYLE = {
    "finance":    ("#00FFFF", "#001A33", 0.55),
    "history":    ("#FAF0DC", "#3B2A1A", 0.55),
    "motivation": ("#FFFFFF", "#290303", 0.55),
}
DEFAULT_CAPTION_STYLE = ("#FFFFFF", "#000000", 0.52)


class VideoCompilerService:
    def __init__(self, static_path: str, music_path: Optional[str] = None):
        self.static_path = static_path
        self.output_dir  = os.path.join(static_path, "generated_videos")
        self.temp_dir    = os.path.join(static_path, "temp_render")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        self.music_path = music_path

    # ── Public async entry point ──────────────────────────────────────────────
    async def compile(self, scenes: List[Scene], job_id: str, niche: str = "general") -> str:
        """Runs the CPU-heavy FFmpeg compilation in a separate thread."""
        loop = asyncio.get_event_loop()
        output_path = await loop.run_in_executor(
            None, self._compile_sync, scenes, job_id, niche
        )
        return output_path

    # ── Main sync compilation ─────────────────────────────────────────────────
    def _compile_sync(self, scenes: List[Scene], job_id: str, niche: str) -> str:
        logger.info("FFmpeg compile: %s (%s) | %d scenes", job_id[:8], niche, len(scenes))

        valid_scenes = [s for s in scenes if s.image_url and s.audio_url]
        if not valid_scenes:
            raise RuntimeError("No valid scenes with both image and audio.")

        caption_style = GENRE_CAPTION_STYLE.get(niche.strip().lower(), DEFAULT_CAPTION_STYLE)

        output_path = os.path.join(self.output_dir, f"{job_id}.mp4")

        # Just filenames — FFmpeg runs inside temp_dir so relative paths work
        ass_filename    = f"{job_id}.ass"
        filter_filename = f"{job_id}_filter.txt"

        # Full paths for Python file I/O
        ass_path    = os.path.join(self.temp_dir, ass_filename)
        filter_path = os.path.join(self.temp_dir, filter_filename)

        # 1. Generate the ASS subtitle file
        self._generate_ass_file(valid_scenes, caption_style, ass_path)

        # 2. Build FFmpeg inputs
        cmd = ["ffmpeg", "-y"]
        filter_chains = []
        video_streams = []
        audio_streams = []

        for i, scene in enumerate(valid_scenes):
            img_path = self._url_to_local(scene.image_url, "generated_images")
            aud_path = self._url_to_local(scene.audio_url, "generated_audios")

            duration = (scene.duration or 3.0) + SCENE_TAIL_PAD
            img_idx  = i * 2
            aud_idx  = i * 2 + 1

            cmd.extend(["-loop", "1", "-t", str(duration), "-i", img_path])
            cmd.extend(["-i", aud_path])

            total_frames = int(duration * FPS)
            beat = (scene.beat_tag or "setup").lower()

            # ── Ken Burns zoom/pan expressions ──
            if beat == "reveal":
                z_expr = "min(zoom+0.0015,1.5)"
                x_expr = "iw/2-(iw/zoom)/2"
                y_expr = "ih/2-(ih/zoom)/2"
            elif beat == "resolution":
                z_expr = "max(1.15-(in*0.0015),1.0)"
                x_expr = "iw/2-(iw/zoom)/2"
                y_expr = "ih/2-(ih/zoom)/2"
            elif beat == "conflict":
                z_expr = "1.1"
                x_expr = f"(iw-iw/zoom)*(1-in/({total_frames}-1))"
                y_expr = "ih/2-(ih/zoom)/2"
            else:  # setup / default
                z_expr = "1.1"
                x_expr = f"(iw-iw/zoom)*(in/({total_frames}-1))"
                y_expr = "ih/2-(ih/zoom)/2"

            z_filter = (
                f"z='{z_expr}':x='{x_expr}':y='{y_expr}'"
                f":d={total_frames}:s={WIDTH}x{HEIGHT}:fps={FPS}"
            )

            # FIX 1: add format=yuv420p after zoompan so FFmpeg knows the
            #         output is video — prevents the "media type mismatch"
            #         error when feeding into concat.
            vf = (
                f"[{img_idx}:v]"
                f"scale=w='max(2160,ih*2160/3840)':h='max(3840,iw*3840/2160)',"
                f"crop=2160:3840,"
                f"zoompan={z_filter},"
                f"trim=duration={duration},"
                f"setpts=PTS-STARTPTS,"
                f"format=yuv420p"          # ← critical fix
            )

            trans = (scene.transition_type or "").strip().lower()
            if trans in ["fade_black", "dip_to_black"]:
                vf += f",fade=t=out:st={duration - 0.5}:d=0.5"

            vf += f"[v_out_{i}];"
            filter_chains.append(vf)
            video_streams.append(f"[v_out_{i}]")

            # FIX 2: apad needs pad_dur so it knows how long to pad;
            #         atrim then clamps to exactly `duration` seconds.
            af = (
                f"[{aud_idx}:a]"
                f"apad=pad_dur={duration},"
                f"atrim=0:{duration},"
                f"asetpts=PTS-STARTPTS"
                f"[a_out_{i}];"
            )
            filter_chains.append(af)
            audio_streams.append(f"[a_out_{i}]")

        # 3. Concat all scenes (interleaved v/a as concat expects)
        n_scenes = len(valid_scenes)
        concat_inputs = "".join(
            f"{video_streams[i]}{audio_streams[i]}" for i in range(n_scenes)
        )
        filter_chains.append(
            f"{concat_inputs}concat=n={n_scenes}:v=1:a=1[outv_raw][outa_raw];"
        )

        # 4. Burn subtitles (relative filename — FFmpeg runs from temp_dir)
        # Escape backslashes and colons for ASS filter on Windows
        safe_ass = ass_filename.replace("\\", "/").replace(":", "\\:")
        filter_chains.append(f"[outv_raw]subtitles='{safe_ass}'[outv_sub];")

        # 5. Fade in/out on the final video
        total_duration = sum(
            (s.duration or 3.0) + SCENE_TAIL_PAD for s in valid_scenes
        )
        filter_chains.append(
            f"[outv_sub]"
            f"fade=t=in:st=0:d=0.3,"
            f"fade=t=out:st={total_duration - 0.5}:d=0.5"
            f"[outv_final];"
        )

        # 6. Background music + sidechain ducking
        if self.music_path and os.path.exists(self.music_path):
            bg_idx = len(valid_scenes) * 2
            cmd.extend(["-stream_loop", "-1", "-i", self.music_path])

            filter_chains.append(f"[{bg_idx}:a]volume={MUSIC_VOLUME}[bg_vol];")
            filter_chains.append(f"[outa_raw]asplit[speech1][speech2];")
            filter_chains.append(
                f"[bg_vol][speech1]"
                f"sidechaincompress=threshold=0.08:ratio=4:attack=5:release=50"
                f"[bg_ducked];"
            )
            filter_chains.append(
                f"[speech2][bg_ducked]"
                f"amix=inputs=2:duration=first:weights=1 1"
                f"[outa_mixed];"
            )
            filter_chains.append(f"[outa_mixed]volume=2[outa_final]")
            out_audio_map = "[outa_final]"
        else:
            # No music — rename outa_raw so the map label is consistent
            filter_chains.append(f"[outa_raw]anull[outa_final]")
            out_audio_map = "[outa_final]"

        # 7. Write filter script file
        with open(filter_path, "w", encoding="utf-8") as f:
            f.write("\n".join(filter_chains))

        # FIX 3: use -/filter_complex (new FFmpeg 8.x file-reading syntax)
        #         instead of the deprecated -filter_complex_script.
        cmd.extend([
            "-/filter_complex", filter_filename,
            "-map", "[outv_final]",
            "-map", out_audio_map,
            "-c:v", "libx264",
            "-preset", "superfast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path,
        ])

        try:
            logger.info("Compiling video...")
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.temp_dir,
            )
            logger.info("✓ Video compiled")
            return output_path
        except subprocess.CalledProcessError as e:
            error_log = e.stderr.decode(errors="replace")
            logger.error("✗ FFmpeg error: %s", error_log[:100])
            raise RuntimeError(f"FFmpeg error: {error_log}")
        finally:
            if os.path.exists(ass_path):
                os.remove(ass_path)
            if os.path.exists(filter_path):
                os.remove(filter_path)

    # ── Subtitle Generator (Advanced SubStation Alpha) ────────────────────────
    def _generate_ass_file(
        self, scenes: List[Scene], caption_style: tuple, output_path: str
    ):
        """Generates a customizable .ass subtitle file."""
        text_color_hex, bg_color_hex, bar_opacity = caption_style

        def to_ass_color(hex_str: str, alpha_float: float) -> str:
            hex_str = hex_str.lstrip("#")
            r, g, b = hex_str[0:2], hex_str[2:4], hex_str[4:6]
            alpha_hex = f"{int((1.0 - alpha_float) * 255):02X}"
            return f"&H{alpha_hex}{b}{g}{r}"

        ass_text_color = to_ass_color(text_color_hex, 1.0)
        ass_bg_color   = to_ass_color(bg_color_hex, bar_opacity)

        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {WIDTH}
PlayResY: {HEIGHT}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: Caption,Arial,58,{ass_text_color},{ass_bg_color},&H00000000,-1,3,12,0,2,60,60,350

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        def format_time(seconds: float) -> str:
            h  = int(seconds // 3600)
            m  = int((seconds % 3600) // 60)
            s  = int(seconds % 60)
            cs = int((seconds - int(seconds)) * 100)
            return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

        events       = []
        current_time = 0.0

        for scene in scenes:
            duration = (scene.duration or 3.0) + SCENE_TAIL_PAD
            words    = scene.script_segment.split()
            chunks   = [
                " ".join(words[i: i + CAPTION_CHUNK_SIZE])
                for i in range(0, len(words), CAPTION_CHUNK_SIZE)
            ]

            if not chunks:
                current_time += duration
                continue

            chunk_duration = duration / len(chunks)
            for chunk in chunks:
                start_str = format_time(current_time)
                end_str   = format_time(current_time + chunk_duration)
                clean_txt = chunk.replace("\n", " ").replace("'", "\\'").strip()
                events.append(
                    f"Dialogue: 0,{start_str},{end_str},Caption,,0,0,0,,{clean_txt}"
                )
                current_time += chunk_duration

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(header + "\n".join(events))

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _url_to_local(self, url: str, sub_folder: str) -> str:
        filename = url.split("/")[-1]
        return os.path.abspath(os.path.join(self.static_path, sub_folder, filename))
